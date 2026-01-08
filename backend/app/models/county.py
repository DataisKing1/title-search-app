"""County configuration model for scraping settings"""
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean
from datetime import datetime
from app.database import Base


class CountyConfig(Base):
    """County configuration for scraping and API fallback"""
    __tablename__ = "county_configs"

    id = Column(Integer, primary_key=True, index=True)

    # County identification
    county_name = Column(String(100), unique=True, nullable=False, index=True)
    state = Column(String(2), default="CO", nullable=False)
    fips_code = Column(String(5), nullable=True)

    # Website info
    recorder_url = Column(String(500), nullable=True)
    court_records_url = Column(String(500), nullable=True)
    assessor_url = Column(String(500), nullable=True)

    # Scraping configuration
    scraping_enabled = Column(Boolean, default=True)
    scraping_adapter = Column(String(100), nullable=True)  # Class name of adapter
    scraping_config = Column(JSON, nullable=True)  # Adapter-specific config

    # Rate limiting
    requests_per_minute = Column(Integer, default=10)
    delay_between_requests_ms = Column(Integer, default=2000)

    # Authentication (if required)
    requires_auth = Column(Boolean, default=False)
    auth_config = Column(JSON, nullable=True)  # Encrypted credentials

    # Fallback API
    fallback_api_enabled = Column(Boolean, default=True)
    fallback_api_provider = Column(String(100), nullable=True)

    # Health tracking
    last_successful_scrape = Column(DateTime, nullable=True)
    last_failed_scrape = Column(DateTime, nullable=True)
    consecutive_failures = Column(Integer, default=0)
    is_healthy = Column(Boolean, default=True)

    # Notes
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
