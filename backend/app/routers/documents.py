"""Documents router"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import os
import hashlib
import aiofiles

from app.database import get_db
from app.models.document import Document, DocumentType, DocumentSource
from app.models.search import TitleSearch
from app.models.user import User
from app.routers.auth import get_current_user
from app.config import settings

router = APIRouter(prefix="/documents", tags=["Documents"])


class DocumentResponse(BaseModel):
    """Document response model"""
    id: int
    search_id: int
    document_type: DocumentType
    instrument_number: Optional[str]
    recording_date: Optional[datetime]
    grantor: List[str]
    grantee: List[str]
    source: DocumentSource
    file_name: Optional[str]
    file_size: Optional[int]
    ocr_confidence: Optional[int]
    ai_summary: Optional[str]
    needs_review: bool
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get document details"""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    return DocumentResponse.model_validate(document)


@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Download document file"""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    if not document.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not available"
        )

    return FileResponse(
        path=document.file_path,
        filename=document.file_name or f"document_{document_id}.pdf",
        media_type=document.mime_type or "application/pdf"
    )


@router.get("/{document_id}/ocr")
async def get_document_ocr(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get document OCR text"""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    return {
        "document_id": document.id,
        "ocr_text": document.ocr_text,
        "ocr_confidence": document.ocr_confidence
    }


def validate_upload_file(file: UploadFile, file_size: int) -> None:
    """Validate uploaded file type and size"""
    # Check file size
    if file_size > settings.max_upload_size_bytes:
        max_mb = settings.MAX_UPLOAD_SIZE_MB
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {max_mb}MB"
        )

    # Check file extension
    file_ext = ""
    if file.filename:
        file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext and file_ext not in settings.allowed_extensions_list:
        allowed = ", ".join(settings.allowed_extensions_list)
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type not allowed. Allowed extensions: {allowed}"
        )

    # Check MIME type
    content_type = (file.content_type or "").lower()
    if content_type and content_type not in settings.allowed_mimetypes_list:
        allowed = ", ".join(settings.allowed_mimetypes_list)
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"MIME type not allowed. Allowed types: {allowed}"
        )


def detect_mime_type(file_ext: str, content_type: Optional[str]) -> str:
    """Detect MIME type from extension or content type"""
    mime_map = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
    }

    # Try to get from extension first
    if file_ext and file_ext.lower() in mime_map:
        return mime_map[file_ext.lower()]

    # Fall back to provided content type
    if content_type and content_type in settings.allowed_mimetypes_list:
        return content_type

    # Default to octet-stream for unknown types
    return "application/octet-stream"


@router.post("/{search_id}/upload")
async def upload_document(
    search_id: int,
    document_type: DocumentType = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload a document for a search"""
    # Verify search exists
    result = await db.execute(
        select(TitleSearch).where(TitleSearch.id == search_id)
    )
    search = result.scalar_one_or_none()

    if not search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search not found"
        )

    # Read file content
    file_content = await file.read()
    file_size = len(file_content)

    # Validate file type and size
    validate_upload_file(file, file_size)

    # Calculate file hash
    file_hash = hashlib.sha256(file_content).hexdigest()

    # Create storage directory structure
    storage_dir = os.path.join(settings.STORAGE_PATH, "documents", str(search_id))
    os.makedirs(storage_dir, exist_ok=True)

    # Generate unique filename
    file_ext = os.path.splitext(file.filename)[1] if file.filename else ".pdf"
    stored_filename = f"{file_hash[:16]}{file_ext}"
    file_path = os.path.join(storage_dir, stored_filename)

    # Detect MIME type properly
    mime_type = detect_mime_type(file_ext, file.content_type)

    # Save file to storage
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(file_content)

    # Create document record
    document = Document(
        search_id=search_id,
        document_type=document_type,
        source=DocumentSource.MANUAL_UPLOAD,
        file_name=file.filename,
        file_path=file_path,
        file_size=file_size,
        file_hash=file_hash,
        mime_type=mime_type
    )

    db.add(document)
    await db.commit()
    await db.refresh(document)

    return DocumentResponse.model_validate(document)
