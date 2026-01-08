"""Document model for title documents"""
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


class DocumentType(str, enum.Enum):
    """Types of title documents"""
    DEED = "deed"
    MORTGAGE = "mortgage"
    DEED_OF_TRUST = "deed_of_trust"
    LIEN = "lien"
    JUDGMENT = "judgment"
    EASEMENT = "easement"
    PLAT = "plat"
    SURVEY = "survey"
    TAX_RECORD = "tax_record"
    COURT_FILING = "court_filing"
    UCC_FILING = "ucc_filing"
    LIS_PENDENS = "lis_pendens"
    BANKRUPTCY = "bankruptcy"
    RELEASE = "release"
    SATISFACTION = "satisfaction"
    ASSIGNMENT = "assignment"
    SUBORDINATION = "subordination"
    OTHER = "other"


class DocumentSource(str, enum.Enum):
    """Source of the document"""
    COUNTY_RECORDER = "county_recorder"
    COURT_RECORDS = "court_records"
    COMMERCIAL_API = "commercial_api"
    MANUAL_UPLOAD = "manual_upload"


class Document(Base):
    """Document model for downloaded/uploaded title documents"""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    search_id = Column(Integer, ForeignKey("title_searches.id"), nullable=False)

    # Document identification
    document_type = Column(Enum(DocumentType), nullable=False)
    instrument_number = Column(String(100), index=True, nullable=True)
    recording_number = Column(String(100), nullable=True)
    book = Column(String(20), nullable=True)
    page = Column(String(20), nullable=True)

    # Recording info
    recording_date = Column(DateTime, nullable=True, index=True)
    effective_date = Column(DateTime, nullable=True)

    # Parties
    grantor = Column(JSON, default=list)  # List of names
    grantee = Column(JSON, default=list)  # List of names

    # Financial
    consideration = Column(String(50), nullable=True)  # Sale price or loan amount

    # Source information
    source = Column(Enum(DocumentSource), nullable=False)
    source_url = Column(String(500), nullable=True)

    # File storage
    file_path = Column(String(500), nullable=True)  # S3/MinIO/local path
    file_name = Column(String(255), nullable=True)
    file_size = Column(Integer, nullable=True)  # bytes
    file_hash = Column(String(64), nullable=True)  # SHA256
    mime_type = Column(String(100), default="application/pdf")

    # OCR and AI analysis
    ocr_text = Column(Text, nullable=True)
    ocr_confidence = Column(Integer, nullable=True)  # 0-100
    ai_summary = Column(Text, nullable=True)
    ai_extracted_data = Column(JSON, nullable=True)
    ai_analysis_at = Column(DateTime, nullable=True)

    # Flags
    is_critical = Column(Boolean, default=False)  # Flagged for manual review
    needs_review = Column(Boolean, default=False)
    review_notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    search = relationship("TitleSearch", back_populates="documents")
