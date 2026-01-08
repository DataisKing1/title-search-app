"""Title search model - core entity for search tracking"""
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


class SearchStatus(str, enum.Enum):
    """Status states for a title search"""
    PENDING = "pending"
    QUEUED = "queued"
    SCRAPING = "scraping"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SearchPriority(str, enum.Enum):
    """Priority levels for search processing"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TitleSearch(Base):
    """Title search model tracking a property title examination"""
    __tablename__ = "title_searches"

    id = Column(Integer, primary_key=True, index=True)

    # Reference
    reference_number = Column(String(50), unique=True, index=True)  # TS-2026-00001

    # Property link
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)

    # Request details
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    search_type = Column(String(50), default="full")  # full, limited, update
    search_years = Column(Integer, default=40)  # How far back to search
    priority = Column(Enum(SearchPriority), default=SearchPriority.NORMAL)

    # Status tracking
    status = Column(Enum(SearchStatus), default=SearchStatus.PENDING, index=True)
    status_message = Column(Text, nullable=True)
    progress_percent = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Processing metadata
    celery_task_id = Column(String(100), nullable=True)
    retry_count = Column(Integer, default=0)
    error_log = Column(JSON, default=list)

    # Source preference (for fallback logic)
    preferred_source = Column(String(50), default="scraping")  # scraping, api, hybrid

    # Relationships
    property = relationship("Property", back_populates="searches")
    requested_by_user = relationship("User", back_populates="searches")
    documents = relationship("Document", back_populates="search", cascade="all, delete-orphan")
    chain_of_title = relationship("ChainOfTitleEntry", back_populates="search", cascade="all, delete-orphan")
    encumbrances = relationship("Encumbrance", back_populates="search", cascade="all, delete-orphan")
    report = relationship("TitleReport", back_populates="search", uselist=False, cascade="all, delete-orphan")
