from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Float, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from app.database import Base


class AnalysisStatus(str, enum.Enum):
    """Status of AI root cause analysis."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class RootCauseCategory(str, enum.Enum):
    """Categories of root causes."""
    DEPLOYMENT = "deployment"           # Recent deployment caused the issue
    CONFIG_CHANGE = "config_change"     # Configuration change
    CAPACITY = "capacity"               # Resource exhaustion
    DEPENDENCY = "dependency"           # External dependency failure
    CODE_BUG = "code_bug"              # Bug in application code
    INFRASTRUCTURE = "infrastructure"   # Infrastructure failure
    NETWORK = "network"                # Network issues
    DATABASE = "database"              # Database issues
    SECURITY = "security"              # Security incident
    UNKNOWN = "unknown"                # Could not determine


class AIRootCauseAnalysis(Base):
    """
    AI-generated root cause analysis for incidents.

    Automatically correlates metrics, logs, traces, and deployments
    to identify the root cause of an incident.
    """
    __tablename__ = "ai_root_cause_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False
    )

    # Who requested and when
    requested_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL")
    )
    requested_at = Column(DateTime(timezone=True), server_default=func.now())

    # Context gathered for analysis
    context_metrics = Column(JSONB, default=dict)      # Relevant metric snapshots
    context_logs = Column(JSONB, default=dict)         # Relevant log entries
    context_traces = Column(JSONB, default=dict)       # Relevant trace/span data
    context_deployments = Column(JSONB, default=dict)  # Recent deployments
    context_alerts = Column(JSONB, default=dict)       # Related alerts
    context_changes = Column(JSONB, default=dict)      # Config/infra changes

    # AI provider info
    provider = Column(String(50))   # claude, openai, gemini
    model = Column(String(100))     # claude-3-opus, gpt-4, etc.

    # Analysis status
    status = Column(
        Enum(AnalysisStatus),
        nullable=False,
        default=AnalysisStatus.PENDING
    )

    # Root cause analysis results
    root_cause = Column(Text)  # Primary root cause explanation
    root_cause_confidence = Column(Float)  # 0.0 to 1.0
    root_cause_category = Column(String(100))  # Category enum value

    # Contributing factors
    contributing_factors = Column(ARRAY(Text))  # List of contributing factors
    affected_services = Column(ARRAY(String(255)))  # Services involved

    # Timeline and recommendations
    timeline_of_events = Column(JSONB, default=list)  # Ordered list of events
    recommended_actions = Column(JSONB, default=list)  # Suggested fixes
    similar_incidents = Column(ARRAY(UUID(as_uuid=True)))  # Similar past incidents

    # Raw AI response (for debugging/audit)
    raw_prompt = Column(Text)
    raw_response = Column(JSONB, default=dict)

    # Error handling
    error_message = Column(Text)

    # Token usage for cost tracking
    tokens_used = Column(Integer)
    analysis_duration_ms = Column(Integer)

    # Feedback
    feedback_helpful = Column(Boolean)
    feedback_comment = Column(Text)

    # Timestamps
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", backref="ai_analyses")
    incident = relationship("Incident", backref="ai_analyses")
    requested_by = relationship("User", backref="requested_analyses")
