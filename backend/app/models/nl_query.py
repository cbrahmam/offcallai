# backend/app/models/nl_query.py
"""Model for Natural Language Query History."""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from app.database import Base


class QueryIntent(str, enum.Enum):
    """Types of intents that can be detected from natural language queries."""
    METRICS_QUERY = "metrics_query"      # "Show me CPU usage for the past hour"
    LOG_SEARCH = "log_search"            # "Find error logs from the API service"
    INCIDENT_LOOKUP = "incident_lookup"  # "What incidents happened yesterday?"
    HOST_STATUS = "host_status"          # "Show me hosts with high memory"
    TRACE_SEARCH = "trace_search"        # "Find slow traces in checkout"
    ALERT_SEARCH = "alert_search"        # "What alerts fired this week?"
    SERVICE_STATUS = "service_status"    # "How is the payment service doing?"
    DEPLOYMENT_LOOKUP = "deployment_lookup"  # "What was deployed yesterday?"
    GENERAL = "general"                  # General question


class QueryStatus(str, enum.Enum):
    """Status of a natural language query."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class NLQueryHistory(Base):
    """
    Natural Language Query History.

    Stores user queries, detected intents, generated structured queries,
    and results for auditing and learning.
    """
    __tablename__ = "nl_query_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL")
    )

    # Query details
    query_text = Column(Text, nullable=False)  # Original natural language query
    intent = Column(String(50))  # Detected intent
    confidence = Column(Float)  # Intent detection confidence 0-1

    # Generated query and execution
    generated_query = Column(JSONB, default=dict)  # Structured query generated
    query_parameters = Column(JSONB, default=dict)  # Parameters extracted
    result_count = Column(Integer)  # Number of results returned
    execution_time_ms = Column(Integer)  # How long the query took

    # AI info
    provider = Column(String(50))  # claude, openai, gemini
    model = Column(String(100))
    tokens_used = Column(Integer)

    # Results summary
    result_summary = Column(Text)  # AI-generated summary of results
    result_data = Column(JSONB, default=dict)  # Cached result data for display

    # Feedback
    feedback_helpful = Column(Boolean)
    feedback_comment = Column(Text)

    # Error handling
    error_message = Column(Text)
    status = Column(String(20), default=QueryStatus.COMPLETED.value)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    organization = relationship("Organization", backref="nl_queries")
    user = relationship("User", backref="nl_queries")
