"""Title search router"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import secrets
import logging

from app.database import get_db
from app.models.search import TitleSearch, SearchStatus, SearchPriority
from app.models.property import Property
from app.models.user import User
from app.models.document import Document, DocumentType, DocumentSource
from app.models.chain_of_title import ChainOfTitleEntry
from app.models.encumbrance import Encumbrance, EncumbranceType, EncumbranceStatus
from app.routers.auth import get_current_user
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/searches", tags=["Title Searches"])


# Request/Response Models
class CreateSearchRequest(BaseModel):
    """Request to create a new title search"""
    street_address: str = Field(..., min_length=5, max_length=255)
    city: str = Field(..., min_length=2, max_length=100)
    county: str = Field(..., min_length=2, max_length=100)
    state: str = Field(default="CO", max_length=2)
    zip_code: Optional[str] = Field(None, max_length=10)
    parcel_number: Optional[str] = Field(None, max_length=50)
    legal_description: Optional[str] = None

    search_type: str = Field(default="full")  # full, limited, update
    search_years: int = Field(default=40, ge=10, le=100)
    priority: SearchPriority = Field(default=SearchPriority.NORMAL)


class PropertyResponse(BaseModel):
    """Property details in response"""
    id: int
    street_address: str
    city: str
    county: str
    state: str
    zip_code: Optional[str]
    parcel_number: Optional[str]
    legal_description: Optional[str]

    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    """Search response model"""
    id: int
    reference_number: str
    status: SearchStatus
    status_message: Optional[str]
    progress_percent: int
    search_type: str
    search_years: int
    priority: SearchPriority

    # Property info
    property: PropertyResponse

    # Stats
    document_count: int = 0
    encumbrance_count: int = 0

    # Timestamps
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class SearchListResponse(BaseModel):
    """Paginated search list response"""
    items: List[SearchResponse]
    total: int
    page: int
    page_size: int
    pages: int


class SearchStatusResponse(BaseModel):
    """Real-time status response"""
    id: int
    reference_number: str
    status: SearchStatus
    status_message: Optional[str]
    progress_percent: int
    document_count: int
    encumbrance_count: int


# Helper to convert search to response
def search_to_response(search: TitleSearch, property_obj: Property = None, document_count: int = 0, encumbrance_count: int = 0) -> SearchResponse:
    # Use provided property or try to access from search (must be loaded)
    prop = property_obj if property_obj else search.property
    return SearchResponse(
        id=search.id,
        reference_number=search.reference_number,
        status=search.status,
        status_message=search.status_message,
        progress_percent=search.progress_percent,
        search_type=search.search_type,
        search_years=search.search_years,
        priority=search.priority,
        property=PropertyResponse.model_validate(prop),
        document_count=document_count,
        encumbrance_count=encumbrance_count,
        created_at=search.created_at,
        started_at=search.started_at,
        completed_at=search.completed_at
    )


# Endpoints
@router.post("", response_model=SearchResponse, status_code=status.HTTP_201_CREATED)
async def create_search(
    request: CreateSearchRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new title search"""
    # Create or get property
    property_query = select(Property).where(
        Property.street_address == request.street_address,
        Property.city == request.city,
        Property.county == request.county
    )
    result = await db.execute(property_query)
    property_obj = result.scalar_one_or_none()

    if not property_obj:
        property_obj = Property(
            street_address=request.street_address,
            city=request.city,
            county=request.county,
            state=request.state,
            zip_code=request.zip_code,
            parcel_number=request.parcel_number,
            legal_description=request.legal_description,
            raw_address_input=f"{request.street_address}, {request.city}, {request.state}"
        )
        db.add(property_obj)
        await db.commit()
        await db.refresh(property_obj)

    # Generate reference number
    year = datetime.utcnow().year
    ref_number = f"TS-{year}-{secrets.token_hex(4).upper()}"

    # Create search
    search = TitleSearch(
        reference_number=ref_number,
        property_id=property_obj.id,
        requested_by=current_user.id,
        search_type=request.search_type,
        search_years=request.search_years,
        priority=request.priority,
        status=SearchStatus.PENDING
    )

    db.add(search)
    await db.commit()
    await db.refresh(search)

    # Queue Celery task for search processing
    try:
        from tasks.search_tasks import orchestrate_search

        # Determine queue based on priority
        queue = "high_priority" if request.priority == SearchPriority.URGENT else "default"

        task = orchestrate_search.apply_async(
            args=[search.id],
            queue=queue,
            countdown=1  # Small delay to ensure DB commit completes
        )
        logger.info(f"Queued search {search.reference_number} as task {task.id}")

        # Store task ID for tracking
        search.celery_task_id = task.id
        await db.commit()

    except Exception as e:
        logger.error(f"Failed to queue search task: {e}")
        # Search is created but not started - can be retried later

    return search_to_response(search, property_obj=property_obj)


@router.get("", response_model=SearchListResponse)
async def list_searches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[SearchStatus] = Query(None),
    county: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List title searches with pagination and filtering"""
    # Base query
    query = select(TitleSearch).join(Property)

    # Apply filters
    if status_filter:
        query = query.where(TitleSearch.status == status_filter)
    if county:
        query = query.where(Property.county.ilike(f"%{county}%"))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and eager load property
    query = query.options(selectinload(TitleSearch.property))
    query = query.order_by(desc(TitleSearch.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    searches = result.scalars().all()

    pages = (total + page_size - 1) // page_size if total > 0 else 1

    return SearchListResponse(
        items=[search_to_response(s, property_obj=s.property) for s in searches],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages
    )


@router.get("/{search_id}", response_model=SearchResponse)
async def get_search(
    search_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed search information"""
    result = await db.execute(
        select(TitleSearch)
        .options(selectinload(TitleSearch.property))
        .where(TitleSearch.id == search_id)
    )
    search = result.scalar_one_or_none()

    if not search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search not found"
        )

    return search_to_response(search, property_obj=search.property)


@router.get("/{search_id}/status", response_model=SearchStatusResponse)
async def get_search_status(
    search_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get real-time search status"""
    # Eager load documents and encumbrances to avoid N+1 queries
    result = await db.execute(
        select(TitleSearch)
        .options(
            selectinload(TitleSearch.documents),
            selectinload(TitleSearch.encumbrances)
        )
        .where(TitleSearch.id == search_id)
    )
    search = result.scalar_one_or_none()

    if not search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search not found"
        )

    return SearchStatusResponse(
        id=search.id,
        reference_number=search.reference_number,
        status=search.status,
        status_message=search.status_message,
        progress_percent=search.progress_percent,
        document_count=len(search.documents) if search.documents else 0,
        encumbrance_count=len(search.encumbrances) if search.encumbrances else 0
    )


@router.post("/{search_id}/cancel")
async def cancel_search(
    search_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Cancel a pending or in-progress search"""
    result = await db.execute(
        select(TitleSearch).where(TitleSearch.id == search_id)
    )
    search = result.scalar_one_or_none()

    if not search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search not found"
        )

    if search.status in [SearchStatus.COMPLETED, SearchStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel a completed or already cancelled search"
        )

    search.status = SearchStatus.CANCELLED
    search.status_message = "Cancelled by user"

    # Revoke Celery task if running
    if search.celery_task_id:
        try:
            from tasks.celery_app import celery_app
            celery_app.control.revoke(search.celery_task_id, terminate=True)
            logger.info(f"Revoked task {search.celery_task_id} for search {search_id}")
        except Exception as e:
            logger.error(f"Failed to revoke task: {e}")

    await db.commit()

    return {"message": "Search cancelled successfully"}


@router.post("/{search_id}/retry")
async def retry_search(
    search_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retry a failed search"""
    result = await db.execute(
        select(TitleSearch).where(TitleSearch.id == search_id)
    )
    search = result.scalar_one_or_none()

    if not search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search not found"
        )

    if search.status != SearchStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only retry failed searches"
        )

    search.status = SearchStatus.PENDING
    search.status_message = "Retrying..."
    search.retry_count += 1
    search.progress_percent = 0

    # Queue Celery task for retry
    try:
        from tasks.search_tasks import orchestrate_search

        task = orchestrate_search.apply_async(
            args=[search.id],
            queue="default",
            countdown=1
        )
        search.celery_task_id = task.id
        logger.info(f"Queued retry for search {search_id} as task {task.id}")

    except Exception as e:
        logger.error(f"Failed to queue retry task: {e}")
        search.status = SearchStatus.FAILED
        search.status_message = f"Failed to queue retry: {str(e)}"

    await db.commit()

    return {"message": "Search retry initiated"}


@router.get("/{search_id}/task-status")
async def get_task_status(
    search_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get Celery task status for a search"""
    result = await db.execute(
        select(TitleSearch).where(TitleSearch.id == search_id)
    )
    search = result.scalar_one_or_none()

    if not search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search not found"
        )

    task_info = {
        "search_id": search_id,
        "celery_task_id": search.celery_task_id,
        "status": search.status.value,
        "progress_percent": search.progress_percent,
        "status_message": search.status_message,
    }

    # Get Celery task status if available
    if search.celery_task_id:
        try:
            from tasks.celery_app import celery_app
            task_result = celery_app.AsyncResult(search.celery_task_id)

            task_info["celery_status"] = task_result.status
            task_info["celery_ready"] = task_result.ready()

            if task_result.failed():
                task_info["celery_error"] = str(task_result.result)
            elif task_result.successful():
                task_info["celery_result"] = task_result.result

        except Exception as e:
            task_info["celery_error"] = str(e)

    return task_info


@router.delete("/{search_id}")
async def delete_search(
    search_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a search (admin only or owner)"""
    result = await db.execute(
        select(TitleSearch).where(TitleSearch.id == search_id)
    )
    search = result.scalar_one_or_none()

    if not search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search not found"
        )

    # Check permissions
    if not current_user.is_admin and search.requested_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this search"
        )

    await db.delete(search)
    await db.commit()

    return {"message": "Search deleted successfully"}


class SearchStatsResponse(BaseModel):
    """Dashboard statistics response"""
    total: int
    completed: int
    in_progress: int
    failed: int
    pending: int


@router.get("/stats/dashboard", response_model=SearchStatsResponse)
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get aggregated statistics for dashboard"""
    # Get total count
    total_result = await db.execute(select(func.count(TitleSearch.id)))
    total = total_result.scalar() or 0

    # Get completed count
    completed_result = await db.execute(
        select(func.count(TitleSearch.id)).where(TitleSearch.status == SearchStatus.COMPLETED)
    )
    completed = completed_result.scalar() or 0

    # Get failed count
    failed_result = await db.execute(
        select(func.count(TitleSearch.id)).where(TitleSearch.status == SearchStatus.FAILED)
    )
    failed = failed_result.scalar() or 0

    # Get pending count
    pending_result = await db.execute(
        select(func.count(TitleSearch.id)).where(TitleSearch.status == SearchStatus.PENDING)
    )
    pending = pending_result.scalar() or 0

    # Calculate in-progress (queued, scraping, analyzing, generating)
    in_progress_statuses = [
        SearchStatus.QUEUED,
        SearchStatus.SCRAPING,
        SearchStatus.ANALYZING,
        SearchStatus.GENERATING
    ]
    in_progress_result = await db.execute(
        select(func.count(TitleSearch.id)).where(TitleSearch.status.in_(in_progress_statuses))
    )
    in_progress = in_progress_result.scalar() or 0

    return SearchStatsResponse(
        total=total,
        completed=completed,
        in_progress=in_progress,
        failed=failed,
        pending=pending
    )


# Document response model for search documents
class SearchDocumentResponse(BaseModel):
    """Document in search context"""
    id: int
    document_type: DocumentType
    instrument_number: Optional[str]
    recording_date: Optional[datetime]
    grantor: List[str] = []
    grantee: List[str] = []
    consideration: Optional[str]
    source: DocumentSource
    file_name: Optional[str]
    ai_summary: Optional[str]
    needs_review: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ChainOfTitleResponse(BaseModel):
    """Chain of title entry response"""
    id: int
    sequence_number: int
    transaction_type: Optional[str]
    transaction_date: Optional[datetime]
    grantor_names: List[str] = []
    grantee_names: List[str] = []
    consideration: Optional[float]
    recording_reference: Optional[str]
    description: Optional[str]
    ai_narrative: Optional[str]

    class Config:
        from_attributes = True


class EncumbranceResponse(BaseModel):
    """Encumbrance response"""
    id: int
    encumbrance_type: EncumbranceType
    status: EncumbranceStatus
    holder_name: Optional[str]
    original_amount: Optional[float]
    current_amount: Optional[float]
    recorded_date: Optional[datetime]
    maturity_date: Optional[datetime]
    recording_reference: Optional[str]
    description: Optional[str]
    risk_level: str
    requires_action: bool

    class Config:
        from_attributes = True


@router.get("/{search_id}/documents", response_model=List[SearchDocumentResponse])
async def get_search_documents(
    search_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all documents for a search"""
    # Verify search exists
    search_result = await db.execute(
        select(TitleSearch).where(TitleSearch.id == search_id)
    )
    if not search_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search not found"
        )

    # Get documents
    result = await db.execute(
        select(Document)
        .where(Document.search_id == search_id)
        .order_by(Document.recording_date.desc())
    )
    documents = result.scalars().all()

    return [SearchDocumentResponse.model_validate(doc) for doc in documents]


@router.get("/{search_id}/chain-of-title", response_model=List[ChainOfTitleResponse])
async def get_chain_of_title(
    search_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get chain of title entries for a search"""
    # Verify search exists
    search_result = await db.execute(
        select(TitleSearch).where(TitleSearch.id == search_id)
    )
    if not search_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search not found"
        )

    # Get chain of title entries
    result = await db.execute(
        select(ChainOfTitleEntry)
        .where(ChainOfTitleEntry.search_id == search_id)
        .order_by(ChainOfTitleEntry.sequence_number)
    )
    entries = result.scalars().all()

    return [ChainOfTitleResponse.model_validate(entry) for entry in entries]


@router.get("/{search_id}/encumbrances", response_model=List[EncumbranceResponse])
async def get_encumbrances(
    search_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all encumbrances for a search"""
    # Verify search exists
    search_result = await db.execute(
        select(TitleSearch).where(TitleSearch.id == search_id)
    )
    if not search_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search not found"
        )

    # Get encumbrances
    result = await db.execute(
        select(Encumbrance)
        .where(Encumbrance.search_id == search_id)
        .order_by(Encumbrance.recorded_date.desc())
    )
    encumbrances = result.scalars().all()

    return [EncumbranceResponse.model_validate(enc) for enc in encumbrances]
