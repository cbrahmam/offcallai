# backend/app/models/maintenance_window.py
from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.database import Base


class MaintenanceWindow(Base):
    """Scheduled maintenance windows for suppressing alerts"""
    __tablename__ = "maintenance_windows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)

    # Basic info
    name = Column(String(255), nullable=False)
    description = Column(Text)

    # Timing
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)

    # Scope - which services/tags are affected
    services = Column(JSONB, default=list)  # ["api-gateway", "database", "web-frontend"]
    tags = Column(JSONB, default=list)  # Additional tags for matching

    # Behavior
    suppress_alerts = Column(Boolean, default=True)  # Whether to suppress alerts during window
    auto_resolve_incidents = Column(Boolean, default=False)  # Auto-resolve incidents created during window

    # Recurrence
    is_recurring = Column(Boolean, default=False)
    recurrence_pattern = Column(JSONB, nullable=True)  # {"frequency": "weekly", "day": 0, "time": "02:00"}

    # Status
    is_active = Column(Boolean, default=True)
    is_cancelled = Column(Boolean, default=False)
    cancelled_at = Column(DateTime(timezone=True))
    cancelled_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Notifications
    notify_before_minutes = Column(Integer, default=30)  # Send reminder X minutes before
    notification_sent = Column(Boolean, default=False)

    # Audit
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="maintenance_windows")
    created_by = relationship("User", foreign_keys=[created_by_id])
    cancelled_by = relationship("User", foreign_keys=[cancelled_by_id])

    def __repr__(self):
        return f"<MaintenanceWindow(name='{self.name}', start='{self.start_time}', end='{self.end_time}')>"
