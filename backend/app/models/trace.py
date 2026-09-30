# backend/app/models/trace.py
"""
APM Trace and Span models for distributed tracing.
Based on OpenTelemetry data model for compatibility.
"""

from sqlalchemy import Column, String, Text, DateTime, BigInteger, Integer, Float, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
import enum
from app.database import Base


class SpanKind(str, enum.Enum):
    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatus(str, enum.Enum):
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


class Trace(Base):
    """
    Represents a distributed trace - a collection of spans
    showing the execution path across services.
    """
    __tablename__ = "traces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id = Column(String(32), nullable=False, unique=True, index=True)  # 128-bit hex trace ID
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Root span info (for quick filtering)
    root_service = Column(String(255), index=True)
    root_operation = Column(String(255), index=True)

    # Timing
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True))
    duration_ms = Column(Float)  # Total trace duration in milliseconds

    # Aggregated info
    span_count = Column(Integer, default=0)
    service_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    has_error = Column(String(10), default="false", index=True)

    # Services involved (for filtering)
    services = Column(JSONB, default=list)  # List of service names in this trace

    # Metadata
    tags = Column(JSONB, default=dict)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('ix_traces_org_start', 'organization_id', 'start_time'),
        Index('ix_traces_org_root_service', 'organization_id', 'root_service'),
        Index('ix_traces_org_has_error', 'organization_id', 'has_error'),
    )

    def __repr__(self):
        return f"<Trace(trace_id='{self.trace_id}', root_service='{self.root_service}')>"


class Span(Base):
    """
    Represents a single span within a trace.
    A span represents a unit of work or operation.
    """
    __tablename__ = "spans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id = Column(String(32), nullable=False, index=True)  # Reference to parent trace
    span_id = Column(String(16), nullable=False, index=True)  # 64-bit hex span ID
    parent_span_id = Column(String(16), index=True)  # NULL for root span
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Identification
    service_name = Column(String(255), nullable=False, index=True)
    operation_name = Column(String(255), nullable=False, index=True)
    span_kind = Column(String(20), default="internal")  # server, client, producer, consumer, internal

    # Timing
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True))
    duration_ms = Column(Float)  # Span duration in milliseconds

    # Status
    status = Column(String(10), default="unset")  # unset, ok, error
    status_message = Column(Text)

    # Resource attributes (from OTel resource)
    resource_attributes = Column(JSONB, default=dict)  # host, container, k8s info

    # Span attributes (custom attributes)
    attributes = Column(JSONB, default=dict)  # http.method, db.statement, etc.

    # Events (like logs within the span)
    events = Column(JSONB, default=list)  # [{name, timestamp, attributes}, ...]

    # Links to related spans
    links = Column(JSONB, default=list)  # [{trace_id, span_id, attributes}, ...]

    # Host info
    host_id = Column(UUID(as_uuid=True), index=True)

    # Timestamps
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('ix_spans_trace_id_start', 'trace_id', 'start_time'),
        Index('ix_spans_org_service', 'organization_id', 'service_name'),
        Index('ix_spans_org_operation', 'organization_id', 'operation_name'),
        Index('ix_spans_org_start', 'organization_id', 'start_time'),
        Index('ix_spans_parent', 'parent_span_id'),
    )

    def __repr__(self):
        return f"<Span(span_id='{self.span_id}', service='{self.service_name}', operation='{self.operation_name}')>"


class ServiceMetrics(Base):
    """
    Aggregated APM metrics per service.
    Pre-computed for dashboard performance.
    """
    __tablename__ = "service_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    service_name = Column(String(255), nullable=False, index=True)

    # Time bucket
    bucket = Column(DateTime(timezone=True), nullable=False, index=True)
    bucket_size = Column(String(10), default="1h")  # 1m, 5m, 1h, 1d

    # Request metrics
    request_count = Column(BigInteger, default=0)
    error_count = Column(BigInteger, default=0)
    error_rate = Column(Float)  # error_count / request_count

    # Latency metrics (in milliseconds)
    latency_avg = Column(Float)
    latency_p50 = Column(Float)
    latency_p90 = Column(Float)
    latency_p95 = Column(Float)
    latency_p99 = Column(Float)
    latency_min = Column(Float)
    latency_max = Column(Float)

    # Throughput
    requests_per_second = Column(Float)

    # Dependencies
    upstream_services = Column(JSONB, default=list)
    downstream_services = Column(JSONB, default=list)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('ix_service_metrics_org_service_bucket', 'organization_id', 'service_name', 'bucket'),
    )

    def __repr__(self):
        return f"<ServiceMetrics(service='{self.service_name}', bucket='{self.bucket}')>"
