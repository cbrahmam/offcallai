# backend/app/models/runbook_execution.py
from sqlalchemy import Column, String, Text, DateTime, Float, ForeignKey, Enum, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from app.database import Base


class RunbookExecutionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunbookTriggerType(str, enum.Enum):
    MANUAL = "manual"
    SUGGESTED = "suggested"
    AUTO = "auto"


class RunbookExecution(Base):
    __tablename__ = "runbook_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    runbook_id = Column(UUID(as_uuid=True), ForeignKey("runbooks.id"), nullable=False)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=True)
    triggered_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    deployment_id = Column(UUID(as_uuid=True), ForeignKey("deployments.id"), nullable=True)

    # Execution status
    status = Column(Enum(RunbookExecutionStatus), default=RunbookExecutionStatus.PENDING, nullable=False)
    trigger_type = Column(Enum(RunbookTriggerType), default=RunbookTriggerType.MANUAL, nullable=False)

    # Pattern matching context
    match_score = Column(Float, nullable=True)  # 0.0 to 1.0
    match_reason = Column(Text, nullable=True)
    matched_patterns = Column(JSONB, default=list)  # Which patterns triggered this

    # Execution context (variables passed to runbook)
    execution_context = Column(JSONB, default=dict)

    # Dry run mode
    is_dry_run = Column(Boolean, default=False)

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Results
    error_message = Column(Text, nullable=True)
    output_summary = Column(Text, nullable=True)

    # Relationships
    organization = relationship("Organization")
    runbook = relationship("Runbook", back_populates="executions")
    incident = relationship("Incident", back_populates="runbook_executions")
    triggered_by = relationship("User", foreign_keys=[triggered_by_id])
    deployment = relationship("Deployment")

    def __repr__(self):
        return f"<RunbookExecution(id={self.id}, runbook_id={self.runbook_id}, status={self.status})>"
