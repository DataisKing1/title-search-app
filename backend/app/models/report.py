"""Title report model for generated reports and commitments"""
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


class ReportStatus(str, enum.Enum):
    """Status of the title report"""
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    ISSUED = "issued"


class TitleReport(Base):
    """Title report model for generated title commitments and reports"""
    __tablename__ = "title_reports"

    id = Column(Integer, primary_key=True, index=True)
    search_id = Column(Integer, ForeignKey("title_searches.id"), nullable=False)

    # Report identification
    report_number = Column(String(50), unique=True, index=True)  # TR-2026-00001
    report_type = Column(String(50), default="commitment")  # commitment, preliminary, final

    # Status
    status = Column(Enum(ReportStatus), default=ReportStatus.DRAFT)

    # Effective dates
    effective_date = Column(DateTime, nullable=True)
    expiration_date = Column(DateTime, nullable=True)

    # Content (structured)
    schedule_a = Column(JSON, nullable=True)  # Proposed insured, amount, property description
    schedule_b1 = Column(JSON, nullable=True)  # Requirements
    schedule_b2 = Column(JSON, nullable=True)  # Exceptions

    # AI-generated content
    chain_of_title_narrative = Column(Text, nullable=True)
    risk_assessment_summary = Column(Text, nullable=True)
    risk_score = Column(Integer, nullable=True)  # 0-100
    ai_recommendations = Column(JSON, nullable=True)

    # Generated files
    pdf_path = Column(String(500), nullable=True)
    pdf_generated_at = Column(DateTime, nullable=True)

    # Raw exports
    json_export_path = Column(String(500), nullable=True)
    csv_export_path = Column(String(500), nullable=True)

    # Approval workflow
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    search = relationship("TitleSearch", back_populates="report")
