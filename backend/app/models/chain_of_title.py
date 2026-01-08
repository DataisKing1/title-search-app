"""Chain of title entry model"""
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class ChainOfTitleEntry(Base):
    """Chain of title entry representing a link in ownership history"""
    __tablename__ = "chain_of_title_entries"

    id = Column(Integer, primary_key=True, index=True)
    search_id = Column(Integer, ForeignKey("title_searches.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)

    # Sequence
    sequence_number = Column(Integer, nullable=False)  # Order in chain

    # Transaction details
    transaction_type = Column(String(100), nullable=True)  # Sale, Transfer, Inheritance, etc.
    transaction_date = Column(DateTime, nullable=True)

    # Parties
    grantor_names = Column(JSON, default=list)
    grantee_names = Column(JSON, default=list)

    # Financial
    consideration = Column(Numeric(15, 2), nullable=True)  # Sale price

    # Recording reference
    recording_reference = Column(String(200), nullable=True)

    # Description
    description = Column(Text, nullable=True)

    # AI-generated content
    ai_narrative = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    search = relationship("TitleSearch", back_populates="chain_of_title")
    document = relationship("Document")
