"""Encumbrance model for liens, easements, and other title issues"""
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Enum, Boolean, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


class EncumbranceType(str, enum.Enum):
    """Types of encumbrances"""
    MORTGAGE = "mortgage"
    DEED_OF_TRUST = "deed_of_trust"
    TAX_LIEN = "tax_lien"
    MECHANICS_LIEN = "mechanics_lien"
    JUDGMENT_LIEN = "judgment_lien"
    HOA_LIEN = "hoa_lien"
    IRS_LIEN = "irs_lien"
    STATE_TAX_LIEN = "state_tax_lien"
    EASEMENT = "easement"
    RESTRICTION = "restriction"
    COVENANT = "covenant"
    LIS_PENDENS = "lis_pendens"
    BANKRUPTCY = "bankruptcy"
    UCC_FILING = "ucc_filing"
    ASSESSMENT = "assessment"
    OTHER = "other"


class EncumbranceStatus(str, enum.Enum):
    """Status of the encumbrance"""
    ACTIVE = "active"
    RELEASED = "released"
    SATISFIED = "satisfied"
    DISPUTED = "disputed"
    UNKNOWN = "unknown"


class Encumbrance(Base):
    """Encumbrance model for title issues that affect property ownership"""
    __tablename__ = "encumbrances"

    id = Column(Integer, primary_key=True, index=True)
    search_id = Column(Integer, ForeignKey("title_searches.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)

    # Type and status
    encumbrance_type = Column(Enum(EncumbranceType), nullable=False)
    status = Column(Enum(EncumbranceStatus), default=EncumbranceStatus.ACTIVE)

    # Details
    holder_name = Column(String(255), nullable=True)  # Lienholder, beneficiary, etc.
    original_amount = Column(Numeric(15, 2), nullable=True)
    current_amount = Column(Numeric(15, 2), nullable=True)

    # Dates
    recorded_date = Column(DateTime, nullable=True)
    effective_date = Column(DateTime, nullable=True)
    maturity_date = Column(DateTime, nullable=True)
    released_date = Column(DateTime, nullable=True)

    # Recording info
    recording_reference = Column(String(200), nullable=True)

    # Description
    description = Column(Text, nullable=True)

    # Risk assessment
    risk_level = Column(String(20), default="medium")  # low, medium, high, critical
    risk_notes = Column(Text, nullable=True)

    # Resolution
    requires_action = Column(Boolean, default=True)
    action_description = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    search = relationship("TitleSearch", back_populates="encumbrances")
    document = relationship("Document")
