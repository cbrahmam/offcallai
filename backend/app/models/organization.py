# backend/app/models/organization.py
from sqlalchemy import Column, String, DateTime, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.database import Base

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    max_users = Column(Integer, default=5)
    max_incidents_per_month = Column(Integer, default=100)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships - ALL FIXED WITH PROPER BIDIRECTIONAL DEFINITIONS
    api_keys = relationship("APIKey", back_populates="organization")
    notifications = relationship("Notification", back_populates="organization")
    incidents = relationship("Incident", back_populates="organization")
    alerts = relationship("Alert", back_populates="organization") 
    escalation_policies = relationship("EscalationPolicy", back_populates="organization")
    integrations = relationship("Integration", back_populates="organization")
    runbooks = relationship("Runbook", back_populates="organization")
    audit_logs = relationship("AuditLog", back_populates="organization")
    users = relationship("User", back_populates="organization")
    teams = relationship("Team", back_populates="organization")
    on_call_schedules = relationship("OnCallSchedule", back_populates="organization")
    maintenance_windows = relationship("MaintenanceWindow", back_populates="organization")
    post_mortems = relationship("PostMortem", back_populates="organization")
    status_page = relationship("StatusPage", back_populates="organization", uselist=False)
    services = relationship("Service", back_populates="organization")
    slos = relationship("SLO", back_populates="organization")
    hosts = relationship("Host", back_populates="organization")
    alert_rules = relationship("AlertRule", back_populates="organization")

    def __repr__(self):
        return f"<Organization(name='{self.name}', slug='{self.slug}')>"