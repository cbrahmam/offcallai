# backend/app/schemas/alert_rule.py
"""
Pydantic schemas for Alert Rules API.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class AlertRuleSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertRuleOperator(str, Enum):
    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "lte"
    EQUAL = "eq"
    NOT_EQUAL = "neq"


class AlertRuleAggregation(str, Enum):
    AVG = "avg"
    MAX = "max"
    MIN = "min"
    SUM = "sum"
    LAST = "last"


class AlertRuleStatus(str, Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    FIRING = "firing"
    PENDING = "pending"


# ============================================
# Request Schemas
# ============================================

class AlertRuleCreate(BaseModel):
    """Schema for creating a new alert rule."""
    name: str = Field(..., min_length=1, max_length=255, description="Rule name")
    description: Optional[str] = Field(None, description="Rule description")

    # Metric condition
    metric_name: str = Field(..., description="Metric to monitor, e.g., 'system.cpu.usage'")
    operator: AlertRuleOperator = Field(AlertRuleOperator.GREATER_THAN, description="Comparison operator")
    threshold: float = Field(..., description="Threshold value")

    # Aggregation
    aggregation: AlertRuleAggregation = Field(AlertRuleAggregation.AVG, description="Aggregation function")
    evaluation_window: int = Field(300, ge=60, le=3600, description="Evaluation window in seconds (1-60 min)")

    # Duration
    duration: int = Field(0, ge=0, le=3600, description="How long condition must be true (seconds)")

    # Filtering
    host_ids: Optional[List[str]] = Field(None, description="Specific host IDs to monitor")
    host_tags: Optional[Dict[str, str]] = Field(None, description="Filter by host tags")

    # Alerting
    severity: AlertRuleSeverity = Field(AlertRuleSeverity.WARNING, description="Alert severity")
    auto_create_incident: bool = Field(True, description="Auto-create incident when triggered")
    auto_resolve: bool = Field(True, description="Auto-resolve when condition clears")
    cooldown_seconds: int = Field(300, ge=60, le=86400, description="Cooldown between alerts (seconds)")

    # Notifications
    notify_channels: Optional[List[str]] = Field(None, description="Notification channels: slack, email, sms")
    notify_users: Optional[List[str]] = Field(None, description="User IDs to notify")

    # Labels
    labels: Optional[Dict[str, str]] = Field(None, description="Custom labels")

    @validator('metric_name')
    def validate_metric_name(cls, v):
        if not v.strip():
            raise ValueError('Metric name cannot be empty')
        return v.strip()


class AlertRuleUpdate(BaseModel):
    """Schema for updating an existing alert rule."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    metric_name: Optional[str] = None
    operator: Optional[AlertRuleOperator] = None
    threshold: Optional[float] = None
    aggregation: Optional[AlertRuleAggregation] = None
    evaluation_window: Optional[int] = Field(None, ge=60, le=3600)
    duration: Optional[int] = Field(None, ge=0, le=3600)
    host_ids: Optional[List[str]] = None
    host_tags: Optional[Dict[str, str]] = None
    severity: Optional[AlertRuleSeverity] = None
    auto_create_incident: Optional[bool] = None
    auto_resolve: Optional[bool] = None
    cooldown_seconds: Optional[int] = Field(None, ge=60, le=86400)
    notify_channels: Optional[List[str]] = None
    notify_users: Optional[List[str]] = None
    labels: Optional[Dict[str, str]] = None


class AlertRuleToggle(BaseModel):
    """Schema for enabling/disabling an alert rule."""
    enabled: bool = Field(..., description="Enable or disable the rule")


# ============================================
# Response Schemas
# ============================================

class AlertRuleResponse(BaseModel):
    """Response schema for a single alert rule."""
    id: str
    name: str
    description: Optional[str]

    # Condition
    metric_name: str
    operator: str
    threshold: float
    condition_text: str  # Human-readable condition

    # Aggregation
    aggregation: str
    evaluation_window: int

    # Duration
    duration: int

    # Filtering
    host_ids: List[str]
    host_tags: Dict[str, str]

    # Alerting
    severity: str
    auto_create_incident: bool
    auto_resolve: bool
    cooldown_seconds: int

    # Notifications
    notify_channels: List[str]
    notify_users: List[str]

    # State
    status: str
    current_value: Optional[float]
    last_evaluated_at: Optional[datetime]
    last_triggered_at: Optional[datetime]
    last_resolved_at: Optional[datetime]

    # Labels
    labels: Dict[str, str]

    # Timestamps
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[str]

    class Config:
        from_attributes = True


class AlertRuleListResponse(BaseModel):
    """Response schema for list of alert rules."""
    rules: List[AlertRuleResponse]
    total: int
    page: int
    per_page: int


class AlertRuleSummary(BaseModel):
    """Summary statistics for alert rules."""
    total: int
    enabled: int
    disabled: int
    firing: int
    pending: int
    by_severity: Dict[str, int]


# ============================================
# History Schemas
# ============================================

class AlertRuleHistoryItem(BaseModel):
    """Schema for alert rule history entry."""
    id: str
    alert_rule_id: str
    previous_status: Optional[str]
    new_status: str
    triggered_value: Optional[float]
    threshold: Optional[float]
    incident_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AlertRuleHistoryResponse(BaseModel):
    """Response schema for alert rule history."""
    history: List[AlertRuleHistoryItem]
    total: int


# ============================================
# Test Schemas
# ============================================

class AlertRuleTestRequest(BaseModel):
    """Request to test an alert rule against recent data."""
    metric_name: str
    operator: AlertRuleOperator
    threshold: float
    aggregation: AlertRuleAggregation = AlertRuleAggregation.AVG
    evaluation_window: int = Field(300, ge=60, le=3600)
    host_ids: Optional[List[str]] = None


class AlertRuleTestResponse(BaseModel):
    """Response for alert rule test."""
    would_trigger: bool
    current_value: Optional[float]
    threshold: float
    operator: str
    hosts_checked: int
    hosts_triggering: int
    details: List[Dict[str, Any]]  # Per-host results
