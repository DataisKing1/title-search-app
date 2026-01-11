"""Encumbrance management API router"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

from app.database import get_db
from app.models.search import TitleSearch
from app.models.document import Document
from app.models.encumbrance import Encumbrance, EncumbranceType, EncumbranceStatus
from app.models.user import User
from app.routers.auth import get_current_user
from app.services.encumbrance_detection import (
    detect_encumbrances_from_documents,
    create_encumbrance_from_detection,
)

router = APIRouter(prefix="/encumbrances", tags=["Encumbrances"])


class EncumbranceResponse(BaseModel):
    """Encumbrance response model"""
    id: int
    search_id: int
    document_id: Optional[int]
    encumbrance_type: str
    status: str
    holder_name: Optional[str]
    original_amount: Optional[float]
    current_amount: Optional[float]
    recorded_date: Optional[datetime]
    released_date: Optional[datetime]
    recording_reference: Optional[str]
    description: Optional[str]
    risk_level: str
    risk_notes: Optional[str]
    requires_action: bool
    action_description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class EncumbranceCreate(BaseModel):
    """Model for creating a new encumbrance"""
    search_id: int
    document_id: Optional[int] = None
    encumbrance_type: str
    status: Optional[str] = "active"
    holder_name: Optional[str] = None
    original_amount: Optional[float] = None
    current_amount: Optional[float] = None
    recorded_date: Optional[datetime] = None
    recording_reference: Optional[str] = None
    description: Optional[str] = None
    risk_level: Optional[str] = "medium"
    requires_action: Optional[bool] = True
    action_description: Optional[str] = None


class EncumbranceUpdate(BaseModel):
    """Model for updating an encumbrance"""
    status: Optional[str] = None
    current_amount: Optional[float] = None
    released_date: Optional[datetime] = None
    risk_level: Optional[str] = None
    risk_notes: Optional[str] = None
    requires_action: Optional[bool] = None
    action_description: Optional[str] = None


class DetectionResult(BaseModel):
    """Result of encumbrance detection"""
    total_detected: int
    encumbrances_created: int
    encumbrances: List[EncumbranceResponse]


@router.get("/search/{search_id}", response_model=List[EncumbranceResponse])
async def get_encumbrances(
    search_id: int,
    status_filter: Optional[str] = None,
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

    query = select(Encumbrance).where(Encumbrance.search_id == search_id)

    if status_filter:
        try:
            status_enum = EncumbranceStatus(status_filter)
            query = query.where(Encumbrance.status == status_enum)
        except ValueError:
            pass

    query = query.order_by(Encumbrance.recorded_date.desc())

    result = await db.execute(query)
    encumbrances = result.scalars().all()

    return [
        EncumbranceResponse(
            id=enc.id,
            search_id=enc.search_id,
            document_id=enc.document_id,
            encumbrance_type=enc.encumbrance_type.value,
            status=enc.status.value,
            holder_name=enc.holder_name,
            original_amount=float(enc.original_amount) if enc.original_amount else None,
            current_amount=float(enc.current_amount) if enc.current_amount else None,
            recorded_date=enc.recorded_date,
            released_date=enc.released_date,
            recording_reference=enc.recording_reference,
            description=enc.description,
            risk_level=enc.risk_level,
            risk_notes=enc.risk_notes,
            requires_action=enc.requires_action,
            action_description=enc.action_description,
            created_at=enc.created_at,
        )
        for enc in encumbrances
    ]


@router.get("/{encumbrance_id}", response_model=EncumbranceResponse)
async def get_encumbrance(
    encumbrance_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific encumbrance"""
    result = await db.execute(
        select(Encumbrance).where(Encumbrance.id == encumbrance_id)
    )
    enc = result.scalar_one_or_none()

    if not enc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encumbrance not found"
        )

    return EncumbranceResponse(
        id=enc.id,
        search_id=enc.search_id,
        document_id=enc.document_id,
        encumbrance_type=enc.encumbrance_type.value,
        status=enc.status.value,
        holder_name=enc.holder_name,
        original_amount=float(enc.original_amount) if enc.original_amount else None,
        current_amount=float(enc.current_amount) if enc.current_amount else None,
        recorded_date=enc.recorded_date,
        released_date=enc.released_date,
        recording_reference=enc.recording_reference,
        description=enc.description,
        risk_level=enc.risk_level,
        risk_notes=enc.risk_notes,
        requires_action=enc.requires_action,
        action_description=enc.action_description,
        created_at=enc.created_at,
    )


@router.post("/", response_model=EncumbranceResponse, status_code=status.HTTP_201_CREATED)
async def create_encumbrance(
    encumbrance: EncumbranceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Manually create an encumbrance"""
    # Verify search exists
    search_result = await db.execute(
        select(TitleSearch).where(TitleSearch.id == encumbrance.search_id)
    )
    if not search_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search not found"
        )

    try:
        enc_type = EncumbranceType(encumbrance.encumbrance_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid encumbrance type: {encumbrance.encumbrance_type}"
        )

    try:
        enc_status = EncumbranceStatus(encumbrance.status)
    except ValueError:
        enc_status = EncumbranceStatus.ACTIVE

    enc = Encumbrance(
        search_id=encumbrance.search_id,
        document_id=encumbrance.document_id,
        encumbrance_type=enc_type,
        status=enc_status,
        holder_name=encumbrance.holder_name,
        original_amount=Decimal(str(encumbrance.original_amount)) if encumbrance.original_amount else None,
        current_amount=Decimal(str(encumbrance.current_amount)) if encumbrance.current_amount else None,
        recorded_date=encumbrance.recorded_date,
        recording_reference=encumbrance.recording_reference,
        description=encumbrance.description,
        risk_level=encumbrance.risk_level or "medium",
        requires_action=encumbrance.requires_action if encumbrance.requires_action is not None else True,
        action_description=encumbrance.action_description,
    )

    db.add(enc)
    await db.commit()
    await db.refresh(enc)

    return EncumbranceResponse(
        id=enc.id,
        search_id=enc.search_id,
        document_id=enc.document_id,
        encumbrance_type=enc.encumbrance_type.value,
        status=enc.status.value,
        holder_name=enc.holder_name,
        original_amount=float(enc.original_amount) if enc.original_amount else None,
        current_amount=float(enc.current_amount) if enc.current_amount else None,
        recorded_date=enc.recorded_date,
        released_date=enc.released_date,
        recording_reference=enc.recording_reference,
        description=enc.description,
        risk_level=enc.risk_level,
        risk_notes=enc.risk_notes,
        requires_action=enc.requires_action,
        action_description=enc.action_description,
        created_at=enc.created_at,
    )


@router.patch("/{encumbrance_id}", response_model=EncumbranceResponse)
async def update_encumbrance(
    encumbrance_id: int,
    update: EncumbranceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update an encumbrance"""
    result = await db.execute(
        select(Encumbrance).where(Encumbrance.id == encumbrance_id)
    )
    enc = result.scalar_one_or_none()

    if not enc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encumbrance not found"
        )

    # Update fields
    if update.status is not None:
        try:
            enc.status = EncumbranceStatus(update.status)
        except ValueError:
            pass

    if update.current_amount is not None:
        enc.current_amount = Decimal(str(update.current_amount))

    if update.released_date is not None:
        enc.released_date = update.released_date

    if update.risk_level is not None:
        enc.risk_level = update.risk_level

    if update.risk_notes is not None:
        enc.risk_notes = update.risk_notes

    if update.requires_action is not None:
        enc.requires_action = update.requires_action

    if update.action_description is not None:
        enc.action_description = update.action_description

    await db.commit()
    await db.refresh(enc)

    return EncumbranceResponse(
        id=enc.id,
        search_id=enc.search_id,
        document_id=enc.document_id,
        encumbrance_type=enc.encumbrance_type.value,
        status=enc.status.value,
        holder_name=enc.holder_name,
        original_amount=float(enc.original_amount) if enc.original_amount else None,
        current_amount=float(enc.current_amount) if enc.current_amount else None,
        recorded_date=enc.recorded_date,
        released_date=enc.released_date,
        recording_reference=enc.recording_reference,
        description=enc.description,
        risk_level=enc.risk_level,
        risk_notes=enc.risk_notes,
        requires_action=enc.requires_action,
        action_description=enc.action_description,
        created_at=enc.created_at,
    )


@router.delete("/{encumbrance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_encumbrance(
    encumbrance_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete an encumbrance"""
    result = await db.execute(
        select(Encumbrance).where(Encumbrance.id == encumbrance_id)
    )
    enc = result.scalar_one_or_none()

    if not enc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encumbrance not found"
        )

    await db.delete(enc)
    await db.commit()


@router.post("/detect/{search_id}", response_model=DetectionResult)
async def detect_encumbrances(
    search_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Automatically detect encumbrances from documents in a search.

    Analyzes all documents in the search and creates encumbrance records
    for any liens, mortgages, easements, or other encumbrances detected.
    """
    # Verify search exists
    search_result = await db.execute(
        select(TitleSearch).where(TitleSearch.id == search_id)
    )
    search = search_result.scalar_one_or_none()
    if not search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search not found"
        )

    # Get all documents for this search
    doc_result = await db.execute(
        select(Document).where(Document.search_id == search_id)
    )
    documents = doc_result.scalars().all()

    if not documents:
        return DetectionResult(
            total_detected=0,
            encumbrances_created=0,
            encumbrances=[]
        )

    # Detect encumbrances
    detections = detect_encumbrances_from_documents(documents)

    # Create encumbrance records
    created_encumbrances = []
    for detection in detections:
        enc = create_encumbrance_from_detection(
            search_id=search_id,
            document_id=detection.get("document_id"),
            detection=detection
        )
        db.add(enc)
        await db.flush()
        await db.refresh(enc)

        created_encumbrances.append(EncumbranceResponse(
            id=enc.id,
            search_id=enc.search_id,
            document_id=enc.document_id,
            encumbrance_type=enc.encumbrance_type.value,
            status=enc.status.value,
            holder_name=enc.holder_name,
            original_amount=float(enc.original_amount) if enc.original_amount else None,
            current_amount=float(enc.current_amount) if enc.current_amount else None,
            recorded_date=enc.recorded_date,
            released_date=enc.released_date,
            recording_reference=enc.recording_reference,
            description=enc.description,
            risk_level=enc.risk_level,
            risk_notes=enc.risk_notes,
            requires_action=enc.requires_action,
            action_description=enc.action_description,
            created_at=enc.created_at,
        ))

    await db.commit()

    return DetectionResult(
        total_detected=len(detections),
        encumbrances_created=len(created_encumbrances),
        encumbrances=created_encumbrances
    )


@router.get("/summary/{search_id}")
async def get_encumbrance_summary(
    search_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a summary of encumbrances for a search"""
    result = await db.execute(
        select(Encumbrance).where(Encumbrance.search_id == search_id)
    )
    encumbrances = result.scalars().all()

    active = [e for e in encumbrances if e.status == EncumbranceStatus.ACTIVE]
    released = [e for e in encumbrances if e.status in [EncumbranceStatus.RELEASED, EncumbranceStatus.SATISFIED]]

    total_active_amount = sum(
        float(e.current_amount or e.original_amount or 0)
        for e in active
    )

    critical = [e for e in active if e.risk_level == "critical"]
    high_risk = [e for e in active if e.risk_level == "high"]

    return {
        "total_encumbrances": len(encumbrances),
        "active_count": len(active),
        "released_count": len(released),
        "total_active_amount": total_active_amount,
        "critical_count": len(critical),
        "high_risk_count": len(high_risk),
        "requires_action_count": sum(1 for e in active if e.requires_action),
        "by_type": {
            enc_type.value: sum(1 for e in active if e.encumbrance_type == enc_type)
            for enc_type in EncumbranceType
            if any(e.encumbrance_type == enc_type for e in active)
        },
        "risk_summary": {
            "critical": len(critical),
            "high": len(high_risk),
            "medium": len([e for e in active if e.risk_level == "medium"]),
            "low": len([e for e in active if e.risk_level == "low"]),
        }
    }
