# backend/app/models/alert_rule.py
"""
Alert Rule model for defining metric-based alerting conditions.
Enables users to create custom alerts based on collected metrics.
"""

from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, Integer, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from app.database import Base


class AlertRuleSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertRuleOperator(str, enum.Enum):
    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "lte"
    EQUAL = "eq"
    NOT_EQUAL = "neq"


class AlertRuleStatus(str, enum.Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    FIRING = "firing"      # Currently in alert state
    PENDING = "pending"    # Threshold breached but waiting for duration


class AlertRule(Base):
    """
    Defines a metric-based alert rule.
    When the condition is met for the specified duration, an incident is created.
    """
    __tablename__ = "alert_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Rule identification
    name = Column(String(255), nullable=False)
    description = Column(Text)

    # Metric condition
    metric_name = Column(String(255), nullable=False, index=True)  # e.g., "system.cpu.usage"
    operator = Column(String(10), nullable=False, default="gt")  # gt, gte, lt, lte, eq, neq
    threshold = Column(Float, nullable=False)  # The threshold value

    # Aggregation
    aggregation = Column(String(20), default="avg")  # avg, max, min, sum, last
    evaluation_window = Column(Integer, default=300)  # Time window in seconds for aggregation (default: 5 min)

    # Duration requirements
    duration = Column(Integer, default=0)  # How long condition must be true (seconds). 0 = immediate

    # Filtering
    host_ids = Column(JSONB, default=list)  # Specific hosts to monitor (empty = all hosts)
    host_tags = Column(JSONB, default=dict)  # Filter by host tags, e.g., {"env": "production"}

    # Alerting behavior
    severity = Column(String(20), default="warning")  # info, warning, error, critical
    auto_create_incident = Column(Boolean, default=True)  # Create incident when triggered
    auto_resolve = Column(Boolean, default=True)  # Auto-resolve when condition clears

    # Cooldown
    cooldown_seconds = Column(Integer, default=300)  # Minimum time between alerts (5 min default)

    # State tracking
    status = Column(String(20), default="enabled", index=True)  # enabled, disabled, firing, pending
    last_evaluated_at = Column(DateTime(timezone=True))
    last_triggered_at = Column(DateTime(timezone=True))
    last_resolved_at = Column(DateTime(timezone=True))
    triggered_since = Column(DateTime(timezone=True))  # When it started firing (for duration checks)

    # Current state
    current_value = Column(Float)  # Last evaluated value

    # Actions (notifications)
    notify_channels = Column(JSONB, default=list)  # ["slack", "email", "sms"]
    notify_users = Column(JSONB, default=list)  # User IDs to notify

    # Metadata
    labels = Column(JSONB, default=dict)  # Custom labels for organization
    extra_data = Column(JSONB, default=dict)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Relationships
    organization = relationship("Organization", back_populates="alert_rules")
    created_by = relationship("User", foreign_keys=[created_by_id])

    def __repr__(self):
        return f"<AlertRule(id='{self.id}', name='{self.name}', metric='{self.metric_name}', status='{self.status}')>"

    @property
    def condition_text(self) -> str:
        """Human-readable condition string."""
        op_map = {
            "gt": ">",
            "gte": ">=",
            "lt": "<",
            "lte": "<=",
            "eq": "==",
            "neq": "!="
        }
        operator_symbol = op_map.get(self.operator, self.operator)
        duration_text = f" for {self.duration}s" if self.duration > 0 else ""
        return f"{self.metric_name} {operator_symbol} {self.threshold}{duration_text}"


class AlertRuleHistory(Base):
    """
    Tracks alert rule state changes for auditing and analytics.
    """
    __tablename__ = "alert_rule_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_rule_id = Column(UUID(as_uuid=True), ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    # State change
    previous_status = Column(String(20))
    new_status = Column(String(20), nullable=False)

    # Trigger info
    triggered_value = Column(Float)
    threshold = Column(Float)

    # Related incident
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"))

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    alert_rule = relationship("AlertRule")
    incident = relationship("Incident")
