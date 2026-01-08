"""Property model for real estate properties"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Property(Base):
    """Property model representing a real estate parcel"""
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)

    # Address information
    street_address = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False)
    county = Column(String(100), nullable=False, index=True)
    state = Column(String(2), default="CO", nullable=False)
    zip_code = Column(String(10), nullable=True)

    # Parcel information
    parcel_number = Column(String(50), index=True, nullable=True)
    legal_description = Column(Text, nullable=True)

    # Geocoding (for mapping)
    latitude = Column(String(20), nullable=True)
    longitude = Column(String(20), nullable=True)

    # Metadata
    raw_address_input = Column(String(500), nullable=True)
    normalized_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    searches = relationship("TitleSearch", back_populates="property")

    __table_args__ = (
        Index("ix_property_address", "street_address", "city", "county"),
        Index("ix_property_parcel", "county", "parcel_number"),
    )
