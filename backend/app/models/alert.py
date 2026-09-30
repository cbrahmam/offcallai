# backend/app/models/alert.py - COMPLETE FIXED VERSION
from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from app.database import Base

class AlertSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    HIGH = "high"
    CRITICAL = "critical"

class AlertStatus(str, enum.Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    ACKNOWLEDGED = "acknowledged"

class AlertSource(str, enum.Enum):
    DATADOG = "datadog"
    GRAFANA = "grafana"
    AWS_CLOUDWATCH = "aws_cloudwatch"
    NEW_RELIC = "new_relic"
    PROMETHEUS = "prometheus"
    PAGERDUTY = "pagerduty"
    PINGDOM = "pingdom"
    GENERIC = "generic"

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=True)
    integration_id = Column(UUID(as_uuid=True), ForeignKey("integrations.id"), nullable=True)
    
    # Alert identification
    external_id = Column(String(255), nullable=False)  # ID from source system
    fingerprint = Column(String(255), nullable=False, index=True)  # For deduplication
    
    # Alert details
    title = Column(String(255), nullable=False)
    description = Column(Text)
    severity = Column(Enum(AlertSeverity), nullable=False, default=AlertSeverity.WARNING)
    status = Column(Enum(AlertStatus), nullable=False, default=AlertStatus.ACTIVE)
    source = Column(String(50), nullable=False, default="generic")  # Temporarily use String instead of Enum
    
    # Context
    service_name = Column(String(255))
    environment = Column(String(50))  # prod, staging, dev
    host = Column(String(255))
    
    # Timing
    started_at = Column(DateTime(timezone=True))
    ended_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Metadata
    labels = Column(JSONB, default=dict)
    raw_data = Column(JSONB, default=dict)  # Original payload from monitoring tool
    
    # Relationships
    organization = relationship("Organization", back_populates="alerts")
    incident = relationship("Incident", back_populates="alerts")
    integration = relationship("Integration", back_populates="alerts")
    enrichment = relationship("AlertEnrichment", back_populates="alert", uselist=False)
    def __repr__(self):
        return f"<Alert(id='{self.id}', title='{self.title}', severity='{self.severity}')>"