# backend/app/schemas/error_tracking.py
"""Schemas for Error Tracking API."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from uuid import UUID


class ErrorGroupStatus(str, Enum):
    """Status of an error group."""
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"
    IGNORED = "ignored"


# ============================================
# Stack Frame schemas
# ============================================

class StackFrame(BaseModel):
    """A single stack frame."""
    filename: Optional[str] = None
    function: Optional[str] = None
    lineno: Optional[int] = None
    colno: Optional[int] = None
    abs_path: Optional[str] = None
    context_line: Optional[str] = None
    pre_context: Optional[List[str]] = None
    post_context: Optional[List[str]] = None
    in_app: Optional[bool] = True
    module: Optional[str] = None
    vars: Optional[Dict[str, Any]] = None


class Breadcrumb(BaseModel):
    """User action breadcrumb."""
    timestamp: datetime
    category: Optional[str] = None
    message: Optional[str] = None
    level: Optional[str] = "info"
    data: Optional[Dict[str, Any]] = None


# ============================================
# Error Ingestion schemas (from SDKs)
# ============================================

class ErrorEventIngest(BaseModel):
    """Error event ingestion request from SDK."""
    # Error details
    error_type: str = Field(..., description="Error type/class name")
    message: str = Field(..., description="Error message")
    stack_trace: Optional[str] = Field(None, description="Raw stack trace")
    stack_frames: Optional[List[StackFrame]] = Field(default=[], description="Parsed stack frames")

    # Context
    service_name: Optional[str] = Field(None, description="Service/application name")
    environment: Optional[str] = Field("production", description="Environment")
    release: Optional[str] = Field(None, description="Application version")
    timestamp: Optional[datetime] = Field(None, description="When error occurred")

    # User info
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    user_ip: Optional[str] = None

    # Request context
    request_url: Optional[str] = None
    request_method: Optional[str] = None
    request_headers: Optional[Dict[str, str]] = None

    # Runtime info
    runtime: Optional[str] = None
    runtime_version: Optional[str] = None
    os: Optional[str] = None
    os_version: Optional[str] = None
    browser: Optional[str] = None
    browser_version: Optional[str] = None
    device: Optional[str] = None

    # Trace correlation
    trace_id: Optional[str] = None
    span_id: Optional[str] = None

    # Additional data
    tags: Optional[Dict[str, str]] = None
    extra: Optional[Dict[str, Any]] = None
    breadcrumbs: Optional[List[Breadcrumb]] = None

    # SDK info
    sdk_name: Optional[str] = None
    sdk_version: Optional[str] = None

    # Custom fingerprint (optional - system calculates if not provided)
    fingerprint: Optional[List[str]] = None


class ErrorIngestResponse(BaseModel):
    """Response after ingesting an error."""
    event_id: UUID
    group_id: UUID
    is_new_group: bool
    group_event_count: int


# ============================================
# Error Group schemas
# ============================================

class ErrorGroupSummary(BaseModel):
    """Summary of an error group for list views."""
    id: UUID
    title: str
    error_type: Optional[str]
    service_name: Optional[str]
    status: ErrorGroupStatus
    is_regression: bool = False
    event_count: int
    user_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    last_release: Optional[str]
    environments: Optional[List[str]]
    assigned_to_name: Optional[str] = None
    sparkline_data: Optional[List[int]] = None

    class Config:
        from_attributes = True


class ErrorGroupDetail(BaseModel):
    """Full error group details."""
    id: UUID
    title: str
    error_type: Optional[str]
    message: Optional[str]

    # Location
    service_name: Optional[str]
    filename: Optional[str]
    function_name: Optional[str]
    line_number: Optional[int]
    column_number: Optional[int]

    # Status
    status: ErrorGroupStatus
    is_regression: bool = False
    assigned_to_id: Optional[UUID]
    assigned_to_name: Optional[str] = None

    # Counts
    event_count: int
    user_count: int

    # Timeline
    first_seen_at: datetime
    last_seen_at: datetime
    resolved_at: Optional[datetime]

    # Releases
    first_release: Optional[str]
    last_release: Optional[str]
    environments: Optional[List[str]]

    # Metadata
    tags: Optional[Dict[str, Any]]
    fingerprint: str

    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ErrorGroupUpdate(BaseModel):
    """Update error group status/assignment."""
    status: Optional[ErrorGroupStatus] = None
    assigned_to_id: Optional[UUID] = None


class ErrorGroupFrequency(BaseModel):
    """Bucketed event frequency data for a group."""
    buckets: List[Dict[str, Any]]  # [{timestamp: str, count: int}]
    period: str
    total_events: int


class BulkUpdateRequest(BaseModel):
    """Bulk update request for multiple error groups."""
    group_ids: List[UUID]
    status: ErrorGroupStatus


# ============================================
# Error Event schemas
# ============================================

class ErrorEventSummary(BaseModel):
    """Summary of an error event for list views."""
    id: UUID
    timestamp: datetime
    error_type: Optional[str]
    message: Optional[str]
    service_name: Optional[str]
    environment: Optional[str]
    release: Optional[str]
    user_id: Optional[str]
    browser: Optional[str]
    os: Optional[str]

    class Config:
        from_attributes = True


class ErrorEventDetail(BaseModel):
    """Full error event details."""
    id: UUID
    error_group_id: UUID
    timestamp: datetime

    # Error details
    error_type: Optional[str]
    message: Optional[str]
    stack_trace: Optional[str]
    stack_frames: Optional[List[Dict[str, Any]]]

    # Context
    service_name: Optional[str]
    environment: Optional[str]
    release: Optional[str]

    # User info
    user_id: Optional[str]
    user_email: Optional[str]
    user_ip: Optional[str]

    # Request context
    request_url: Optional[str]
    request_method: Optional[str]
    request_headers: Optional[Dict[str, Any]]

    # Runtime info
    runtime: Optional[str]
    runtime_version: Optional[str]
    os: Optional[str]
    os_version: Optional[str]
    browser: Optional[str]
    browser_version: Optional[str]
    device: Optional[str]

    # Trace correlation
    trace_id: Optional[str]
    span_id: Optional[str]

    # Additional data
    tags: Optional[Dict[str, Any]]
    extra_data: Optional[Dict[str, Any]]
    breadcrumbs: Optional[List[Dict[str, Any]]]

    # SDK info
    sdk_name: Optional[str]
    sdk_version: Optional[str]

    created_at: datetime

    class Config:
        from_attributes = True


# ============================================
# Statistics schemas
# ============================================

class ErrorStats(BaseModel):
    """Error statistics for a time period."""
    total_events: int
    total_groups: int
    unresolved_groups: int
    events_by_day: List[Dict[str, Any]]  # [{date: str, count: int}]
    top_errors: List[ErrorGroupSummary]
    affected_users: int
    affected_services: List[str]


class ErrorTrend(BaseModel):
    """Error trend data point."""
    timestamp: datetime
    event_count: int
    group_count: int
