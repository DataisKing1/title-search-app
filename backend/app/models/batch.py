"""Batch upload models for bulk processing"""
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


class BatchStatus(str, enum.Enum):
    """Status of batch processing"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL = "partial"  # Some succeeded, some failed
    FAILED = "failed"
    CANCELLED = "cancelled"


class BatchUpload(Base):
    """Batch upload model for bulk CSV/Excel processing"""
    __tablename__ = "batch_uploads"

    id = Column(Integer, primary_key=True, index=True)

    # Batch identification
    batch_number = Column(String(50), unique=True, index=True)  # BATCH-2026-00001

    # Upload info
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=True)

    # Status
    status = Column(Enum(BatchStatus), default=BatchStatus.PENDING)

    # Statistics
    total_records = Column(Integer, default=0)
    processed_records = Column(Integer, default=0)
    successful_records = Column(Integer, default=0)
    failed_records = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Error tracking
    error_log = Column(JSON, default=list)

    # Relationships
    items = relationship("BatchItem", back_populates="batch", cascade="all, delete-orphan")
    uploaded_by_user = relationship("User", back_populates="batch_uploads")


class BatchItem(Base):
    """Individual item in a batch upload"""
    __tablename__ = "batch_items"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batch_uploads.id"), nullable=False)

    # Row reference
    row_number = Column(Integer, nullable=False)

    # Input data
    raw_input = Column(JSON, nullable=False)  # Original CSV row

    # Parsed data
    street_address = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    county = Column(String(100), nullable=True)
    parcel_number = Column(String(50), nullable=True)

    # Link to created search
    search_id = Column(Integer, ForeignKey("title_searches.id"), nullable=True)

    # Status
    status = Column(String(50), default="pending")  # pending, processed, failed
    error_message = Column(Text, nullable=True)

    # Timestamps
    processed_at = Column(DateTime, nullable=True)

    # Relationships
    batch = relationship("BatchUpload", back_populates="items")
    search = relationship("TitleSearch")
