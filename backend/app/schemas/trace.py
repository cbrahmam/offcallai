# backend/app/schemas/trace.py
"""
Pydantic schemas for APM/Tracing API.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class SpanKind(str, Enum):
    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatus(str, Enum):
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


# ============================================
# Ingestion Schemas
# ============================================

class SpanEvent(BaseModel):
    """Event within a span (like a log)."""
    name: str
    timestamp: datetime
    attributes: Optional[Dict[str, Any]] = None


class SpanLink(BaseModel):
    """Link to a related span."""
    trace_id: str
    span_id: str
    attributes: Optional[Dict[str, Any]] = None


class SpanIngest(BaseModel):
    """Single span for ingestion (OpenTelemetry compatible)."""
    trace_id: str = Field(..., min_length=32, max_length=32)
    span_id: str = Field(..., min_length=16, max_length=16)
    parent_span_id: Optional[str] = Field(None, min_length=16, max_length=16)
    service_name: str
    operation_name: str
    span_kind: SpanKind = SpanKind.INTERNAL
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    status: SpanStatus = SpanStatus.UNSET
    status_message: Optional[str] = None
    resource_attributes: Optional[Dict[str, Any]] = None
    attributes: Optional[Dict[str, Any]] = None
    events: Optional[List[SpanEvent]] = None
    links: Optional[List[SpanLink]] = None


class SpanBatch(BaseModel):
    """Batch of spans for ingestion from agent."""
    agent_id: str
    spans: List[SpanIngest] = Field(..., max_length=500)


class SpanIngestResponse(BaseModel):
    """Response after span ingestion."""
    success: bool
    spans_received: int
    spans_stored: int
    traces_updated: int
    host_id: str
    errors: List[str] = []


# ============================================
# Query Schemas
# ============================================

class TraceQuery(BaseModel):
    """Query parameters for searching traces."""
    start_time: datetime
    end_time: datetime
    service: Optional[str] = None
    operation: Optional[str] = None
    min_duration_ms: Optional[float] = None
    max_duration_ms: Optional[float] = None
    has_error: Optional[bool] = None
    tags: Optional[Dict[str, str]] = None
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)


class SpanResponse(BaseModel):
    """Single span in response."""
    id: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    service_name: str
    operation_name: str
    span_kind: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_ms: Optional[float]
    status: str
    status_message: Optional[str]
    resource_attributes: Dict[str, Any]
    attributes: Dict[str, Any]
    events: List[Dict[str, Any]]
    links: List[Dict[str, Any]]

    class Config:
        from_attributes = True


class TraceResponse(BaseModel):
    """Trace with all its spans."""
    id: str
    trace_id: str
    root_service: Optional[str]
    root_operation: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    duration_ms: Optional[float]
    span_count: int
    service_count: int
    error_count: int
    has_error: bool
    services: List[str]
    spans: List[SpanResponse]
    tags: Dict[str, Any]

    class Config:
        from_attributes = True


class TraceSummary(BaseModel):
    """Trace summary for list view."""
    id: str
    trace_id: str
    root_service: Optional[str]
    root_operation: Optional[str]
    start_time: datetime
    duration_ms: Optional[float]
    span_count: int
    error_count: int
    has_error: bool
    services: List[str]

    class Config:
        from_attributes = True


class TraceListResponse(BaseModel):
    """Response for trace list query."""
    traces: List[TraceSummary]
    total: int
    query: TraceQuery
    has_more: bool


# ============================================
# Service Metrics
# ============================================

class ServiceSummary(BaseModel):
    """Service summary from APM data."""
    service_name: str
    request_count: int
    error_count: int
    error_rate: float
    latency_avg: float
    latency_p50: float
    latency_p95: float
    latency_p99: float
    requests_per_second: float
    upstream_services: List[str]
    downstream_services: List[str]


class ServiceListResponse(BaseModel):
    """List of services with metrics."""
    services: List[ServiceSummary]
    time_range_hours: int


class OperationMetrics(BaseModel):
    """Metrics for a single operation."""
    operation_name: str
    request_count: int
    error_count: int
    error_rate: float
    latency_avg: float
    latency_p95: float


class ServiceOperations(BaseModel):
    """Operations for a service."""
    service_name: str
    operations: List[OperationMetrics]


# ============================================
# Service Map
# ============================================

class HealthStatus(str, Enum):
    """Service health status."""
    HEALTHY = "healthy"      # Green: error_rate < 1%, latency_p95 < 500ms
    DEGRADED = "degraded"    # Yellow: error_rate < 5%, latency_p95 < 1000ms
    CRITICAL = "critical"    # Red: error_rate >= 5% or latency_p95 >= 1000ms


class ServiceNode(BaseModel):
    """Node in service dependency map."""
    service_name: str
    request_count: int
    error_rate: float
    latency_avg: float
    latency_p95: Optional[float] = None
    health_status: Optional[HealthStatus] = None


class ServiceEdge(BaseModel):
    """Edge (dependency) in service map."""
    source: str
    target: str
    request_count: int
    error_rate: float
    latency_avg: float


class ServiceMap(BaseModel):
    """Service dependency map."""
    nodes: List[ServiceNode]
    edges: List[ServiceEdge]
    time_range_hours: int = 24
