# backend/app/models/alert_enrichment.py
from sqlalchemy import Column, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid

class AlertEnrichment(Base):
    __tablename__ = "alert_enrichments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False, unique=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    
    # Context-rich data
    related_metrics = Column(JSONB, default=dict)
    related_logs = Column(JSONB, default=list)
    related_traces = Column(JSONB, default=list)
    service_health = Column(JSONB, default=dict)
    
    # Drill-down links
    dashboard_url = Column(String(500))
    logs_url = Column(String(500))
    traces_url = Column(String(500))
    runbook_url = Column(String(500))
    
    # Correlation data
    correlated_alert_ids = Column(JSONB, default=list)
    correlation_score = Column(Float, default=0.0)
    correlation_reason = Column(Text)
    
    # Smart severity
    ai_severity_score = Column(Float)
    severity_confidence = Column(Float)
    severity_factors = Column(JSONB, default=dict)
    original_severity = Column(String(50))
    adjusted_severity = Column(String(50))
    
    # Metadata
    enriched_at = Column(DateTime(timezone=True), server_default=func.now())
    enrichment_source = Column(String(100))
    processing_time_ms = Column(Float)
    
    # Relationships
    alert = relationship("Alert", back_populates="enrichment")
    organization = relationship("Organization")

    def __repr__(self):
        return f"<AlertEnrichment(alert_id='{self.alert_id}', score={self.ai_severity_score})>"