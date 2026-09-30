# backend/app/schemas/ai_rca.py
"""Schemas for AI Root Cause Analysis"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from uuid import UUID


class AnalysisStatus(str, Enum):
    """Status of AI root cause analysis."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class RootCauseCategory(str, Enum):
    """Categories of root causes."""
    DEPLOYMENT = "deployment"
    CONFIG_CHANGE = "config_change"
    CAPACITY = "capacity"
    DEPENDENCY = "dependency"
    CODE_BUG = "code_bug"
    INFRASTRUCTURE = "infrastructure"
    NETWORK = "network"
    DATABASE = "database"
    SECURITY = "security"
    UNKNOWN = "unknown"


# Request schemas
class AnalysisRequest(BaseModel):
    """Request to trigger AI root cause analysis."""
    include_metrics: bool = Field(default=True, description="Include metric context")
    include_logs: bool = Field(default=True, description="Include log context")
    include_traces: bool = Field(default=True, description="Include trace context")
    include_deployments: bool = Field(default=True, description="Include recent deployments")
    time_window_minutes: int = Field(default=60, ge=5, le=1440, description="Context time window")
    provider: Optional[str] = Field(None, description="AI provider (uses org default if not specified)")


class AnalysisFeedback(BaseModel):
    """User feedback on analysis quality."""
    helpful: bool = Field(..., description="Was the analysis helpful?")
    comment: Optional[str] = Field(None, max_length=1000, description="Optional feedback comment")


# Response schemas
class TimelineEvent(BaseModel):
    """Single event in the incident timeline."""
    timestamp: datetime
    event_type: str  # metric_spike, log_error, deployment, alert, etc.
    title: str
    description: Optional[str] = None
    service: Optional[str] = None
    severity: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class RecommendedAction(BaseModel):
    """Recommended action to resolve the incident."""
    priority: int = Field(ge=1, le=5, description="1=highest priority")
    action: str
    description: str
    category: str  # immediate, short_term, long_term
    estimated_effort: Optional[str] = None  # quick_fix, hours, days
    runbook_id: Optional[UUID] = None  # Link to relevant runbook


class SimilarIncident(BaseModel):
    """Summary of a similar past incident."""
    incident_id: UUID
    title: str
    severity: str
    root_cause: Optional[str] = None
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_time_seconds: Optional[int] = None
    similarity_score: float = Field(ge=0, le=1)


class AnalysisResponse(BaseModel):
    """Full AI root cause analysis response."""
    id: UUID
    incident_id: UUID
    status: AnalysisStatus
    requested_at: datetime
    requested_by_name: Optional[str] = None

    # Results (populated when status=completed)
    root_cause: Optional[str] = None
    root_cause_confidence: Optional[float] = Field(None, ge=0, le=1)
    root_cause_category: Optional[RootCauseCategory] = None
    contributing_factors: List[str] = []
    affected_services: List[str] = []
    timeline_of_events: List[TimelineEvent] = []
    recommended_actions: List[RecommendedAction] = []
    similar_incidents: List[SimilarIncident] = []

    # AI info
    provider: Optional[str] = None
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    analysis_duration_ms: Optional[int] = None

    # Error info (if failed)
    error_message: Optional[str] = None

    # Feedback
    feedback_helpful: Optional[bool] = None
    feedback_comment: Optional[str] = None

    # Timestamps
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AnalysisSummary(BaseModel):
    """Lightweight summary for lists."""
    id: UUID
    incident_id: UUID
    status: AnalysisStatus
    root_cause_category: Optional[RootCauseCategory] = None
    root_cause_confidence: Optional[float] = None
    requested_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AnalysisContext(BaseModel):
    """Context gathered for analysis (returned for transparency)."""
    metrics_count: int = 0
    logs_count: int = 0
    traces_count: int = 0
    deployments_count: int = 0
    alerts_count: int = 0
    time_window_minutes: int = 60


class AnalysisStartResponse(BaseModel):
    """Response when analysis is triggered."""
    analysis_id: UUID
    status: AnalysisStatus
    message: str
    context_gathered: AnalysisContext


class AnalysisNotFoundResponse(BaseModel):
    """Response when no analysis exists for an incident."""
    exists: bool = False
    message: str = "No AI analysis has been run for this incident yet."
    suggestion: str = "Click 'Run AI Analysis' to get AI-powered root cause analysis, timeline reconstruction, and recommended actions."
    how_to_trigger: str = "POST /api/v1/ai-rca/incidents/{incident_id}/analyze"
    benefits: List[str] = [
        "AI-powered root cause identification",
        "Timeline of events reconstruction",
        "Similar incident matching",
        "Recommended remediation actions",
        "Contributing factors analysis"
    ]
