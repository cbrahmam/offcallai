# backend/app/schemas/nl_query.py
"""Schemas for Natural Language Queries."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from uuid import UUID


class QueryIntent(str, Enum):
    """Types of intents detected from natural language queries."""
    METRICS_QUERY = "metrics_query"
    LOG_SEARCH = "log_search"
    INCIDENT_LOOKUP = "incident_lookup"
    HOST_STATUS = "host_status"
    TRACE_SEARCH = "trace_search"
    ALERT_SEARCH = "alert_search"
    SERVICE_STATUS = "service_status"
    DEPLOYMENT_LOOKUP = "deployment_lookup"
    GENERAL = "general"


class QueryStatus(str, Enum):
    """Status of a query."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


# Request schemas
class NLQueryRequest(BaseModel):
    """Request to process a natural language query."""
    query: str = Field(..., min_length=3, max_length=500, description="Natural language query")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context for the query")


class QueryFeedback(BaseModel):
    """User feedback on query results."""
    helpful: bool = Field(..., description="Was the result helpful?")
    comment: Optional[str] = Field(None, max_length=1000, description="Optional feedback comment")


# Response schemas
class MetricResult(BaseModel):
    """A metric data point."""
    timestamp: datetime
    value: float
    metric_name: str
    host_name: Optional[str] = None
    service_name: Optional[str] = None
    tags: Optional[Dict[str, str]] = None


class LogResult(BaseModel):
    """A log entry result."""
    timestamp: datetime
    level: str
    message: str
    service_name: Optional[str] = None
    host_name: Optional[str] = None
    trace_id: Optional[str] = None


class IncidentResult(BaseModel):
    """An incident result."""
    id: UUID
    title: str
    severity: str
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None


class HostResult(BaseModel):
    """A host status result."""
    id: UUID
    hostname: str
    status: str
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    disk_percent: Optional[float] = None
    last_seen_at: Optional[datetime] = None


class TraceResult(BaseModel):
    """A trace result."""
    trace_id: str
    service_name: str
    operation_name: str
    duration_ms: float
    status: str
    timestamp: datetime


class AlertResult(BaseModel):
    """An alert result."""
    id: UUID
    title: str
    severity: str
    status: str
    source: str
    created_at: datetime


class DeploymentResult(BaseModel):
    """A deployment result."""
    id: UUID
    service_name: str
    version: str
    status: str
    deployed_at: datetime
    deployed_by: Optional[str] = None


class QueryResultData(BaseModel):
    """Container for query result data based on intent."""
    metrics: Optional[List[MetricResult]] = None
    logs: Optional[List[LogResult]] = None
    incidents: Optional[List[IncidentResult]] = None
    hosts: Optional[List[HostResult]] = None
    traces: Optional[List[TraceResult]] = None
    alerts: Optional[List[AlertResult]] = None
    deployments: Optional[List[DeploymentResult]] = None
    chart_data: Optional[Dict[str, Any]] = None  # For visualization


class NLQueryResponse(BaseModel):
    """Response from a natural language query."""
    id: UUID
    query_text: str
    intent: QueryIntent
    confidence: float = Field(ge=0, le=1)
    status: QueryStatus

    # Results
    result_count: int = 0
    result_summary: Optional[str] = None
    result_data: Optional[QueryResultData] = None

    # Execution info
    execution_time_ms: Optional[int] = None
    generated_query: Optional[Dict[str, Any]] = None

    # AI info
    provider: Optional[str] = None
    model: Optional[str] = None

    # Error info
    error_message: Optional[str] = None

    # Feedback status
    feedback_helpful: Optional[bool] = None

    # Timestamp
    created_at: datetime

    class Config:
        from_attributes = True


class NLQuerySummary(BaseModel):
    """Lightweight summary for query history."""
    id: UUID
    query_text: str
    intent: QueryIntent
    result_count: int
    status: QueryStatus
    created_at: datetime

    class Config:
        from_attributes = True


class SuggestedQuery(BaseModel):
    """A suggested query based on context."""
    query: str
    description: str
    intent: QueryIntent
