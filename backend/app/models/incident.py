from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from app.database import Base

class IncidentSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class IncidentStatus(str, enum.Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    CLOSED = "closed"

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    
    # Core incident data
    title = Column(String(255), nullable=False)
    description = Column(Text)
    severity = Column(Enum(IncidentSeverity), nullable=False, default=IncidentSeverity.MEDIUM)
    status = Column(Enum(IncidentStatus), nullable=False, default=IncidentStatus.OPEN)
    
    # Assignment and ownership
    assigned_to_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    acknowledged_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    resolved_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    acknowledged_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # AI analysis
    ai_summary = Column(Text)
    ai_suggested_actions = Column(JSONB)
    ai_confidence_score = Column(Integer)  # 0-100
    
    # Metadata - renamed to avoid conflict
    tags = Column(JSONB, default=list)
    extra_data = Column(JSONB, default=dict)  # Changed from 'metadata'
    
    # Relationships - FIXED with explicit foreign_keys
    organization = relationship("Organization", back_populates="incidents")
    alerts = relationship("Alert", back_populates="incident")
    audit_logs = relationship("AuditLog", back_populates="incident")
    deployments = relationship("Deployment", back_populates="incident")
    notifications = relationship("Notification", back_populates="incident")
    # Explicit foreign key relationships to avoid confusion
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    acknowledged_by = relationship("User", foreign_keys=[acknowledged_by_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_id])
    runbook_executions = relationship("RunbookExecution", back_populates="incident")
    post_mortem = relationship("PostMortem", back_populates="incident", uselist=False)