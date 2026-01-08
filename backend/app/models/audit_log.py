"""Audit log model for tracking user actions"""
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey
from datetime import datetime
from app.database import Base


class AuditLog(Base):
    """Audit log for tracking administrative and significant user actions"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    # User who performed the action
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Action details
    action = Column(String(100), nullable=False, index=True)  # create, update, delete, login, etc.
    resource_type = Column(String(100), nullable=False, index=True)  # search, document, report, etc.
    resource_id = Column(Integer, nullable=True)

    # Request context
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # Details
    details = Column(JSON, nullable=True)  # Additional context
    old_values = Column(JSON, nullable=True)  # Previous state for updates
    new_values = Column(JSON, nullable=True)  # New state for updates

    # Status
    status = Column(String(20), default="success")  # success, failed, error

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
