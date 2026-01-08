"""Batch upload router"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import secrets
import csv
import io
import logging

from app.database import get_db
from app.models.batch import BatchUpload, BatchItem, BatchStatus
from app.models.user import User
from app.routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/batch", tags=["Batch Processing"])


class BatchItemResponse(BaseModel):
    """Batch item response"""
    id: int
    row_number: int
    street_address: Optional[str]
    city: Optional[str]
    county: Optional[str]
    parcel_number: Optional[str]
    status: str
    error_message: Optional[str]
    search_id: Optional[int]
    processed_at: Optional[datetime]

    class Config:
        from_attributes = True


class BatchResponse(BaseModel):
    """Batch upload response"""
    id: int
    batch_number: str
    original_filename: str
    status: BatchStatus
    total_records: int
    processed_records: int
    successful_records: int
    failed_records: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class BatchDetailResponse(BatchResponse):
    """Detailed batch response with items"""
    items: List[BatchItemResponse]


@router.post("/upload", response_model=BatchResponse)
async def upload_batch(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload a CSV file for batch processing"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported"
        )

    # Read CSV content
    content = await file.read()
    text_content = content.decode('utf-8')

    # Parse CSV
    csv_reader = csv.DictReader(io.StringIO(text_content))
    rows = list(csv_reader)

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file is empty"
        )

    # Generate batch number
    year = datetime.utcnow().year
    batch_number = f"BATCH-{year}-{secrets.token_hex(4).upper()}"

    # Create batch record
    batch = BatchUpload(
        batch_number=batch_number,
        uploaded_by=current_user.id,
        original_filename=file.filename,
        status=BatchStatus.PENDING,
        total_records=len(rows)
    )

    db.add(batch)
    await db.commit()
    await db.refresh(batch)

    # Create batch items
    for i, row in enumerate(rows):
        item = BatchItem(
            batch_id=batch.id,
            row_number=i + 1,
            raw_input=row,
            street_address=row.get('street_address') or row.get('address'),
            city=row.get('city'),
            county=row.get('county'),
            parcel_number=row.get('parcel_number') or row.get('parcel') or row.get('apn'),
            status="pending"
        )
        db.add(item)

    await db.commit()

    return BatchResponse.model_validate(batch)


@router.get("/{batch_id}", response_model=BatchDetailResponse)
async def get_batch(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get batch status and details"""
    result = await db.execute(
        select(BatchUpload).where(BatchUpload.id == batch_id)
    )
    batch = result.scalar_one_or_none()

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )

    return BatchDetailResponse(
        id=batch.id,
        batch_number=batch.batch_number,
        original_filename=batch.original_filename,
        status=batch.status,
        total_records=batch.total_records,
        processed_records=batch.processed_records,
        successful_records=batch.successful_records,
        failed_records=batch.failed_records,
        created_at=batch.created_at,
        started_at=batch.started_at,
        completed_at=batch.completed_at,
        items=[BatchItemResponse.model_validate(item) for item in batch.items]
    )


@router.post("/{batch_id}/process")
async def process_batch(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Start processing a batch"""
    result = await db.execute(
        select(BatchUpload).where(BatchUpload.id == batch_id)
    )
    batch = result.scalar_one_or_none()

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )

    if batch.status != BatchStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch is already processing or completed"
        )

    batch.status = BatchStatus.PROCESSING
    batch.started_at = datetime.utcnow()
    await db.commit()

    # Queue Celery task for batch processing
    try:
        from tasks.batch_tasks import process_batch as process_batch_task

        task = process_batch_task.apply_async(
            args=[batch.id],
            queue="default",
            countdown=1  # Small delay to ensure DB commit completes
        )
        logger.info(f"Queued batch processing task {task.id} for batch {batch.batch_number}")

    except Exception as e:
        logger.error(f"Failed to queue batch processing task: {e}")
        batch.status = BatchStatus.FAILED
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start batch processing"
        )

    return {"message": "Batch processing started", "batch_id": batch.id}


@router.delete("/{batch_id}")
async def cancel_batch(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Cancel a batch"""
    result = await db.execute(
        select(BatchUpload).where(BatchUpload.id == batch_id)
    )
    batch = result.scalar_one_or_none()

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )

    if batch.status in [BatchStatus.COMPLETED, BatchStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel completed or already cancelled batch"
        )

    batch.status = BatchStatus.CANCELLED
    await db.commit()

    return {"message": "Batch cancelled"}
