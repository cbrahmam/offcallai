# backend/app/schemas/synthetic.py
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


# Enums
class SyntheticCheckType(str, Enum):
    HTTP = "http"
    API = "api"
    BROWSER = "browser"
    TCP = "tcp"
    DNS = "dns"
    SSL = "ssl"
    PING = "ping"
    GRPC = "grpc"


class CheckStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


class CheckResultStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    ERROR = "error"


# ==================== Assertion Schemas ====================

class AssertionSchema(BaseModel):
    type: str  # status_code, response_time, body_contains, json_path, header, regex
    operator: Optional[str] = None  # equals, not_equals, greater_than, less_than, contains, regex
    value: Optional[Any] = None
    path: Optional[str] = None  # For json_path assertions
    name: Optional[str] = None  # For header assertions


# ==================== Check Schemas ====================

class SyntheticCheckBase(BaseModel):
    name: str
    description: Optional[str] = None
    check_type: str = "http"
    target_url: str
    method: str = "GET"
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Optional[str] = None
    body_type: Optional[str] = None
    auth_type: Optional[str] = None
    auth_config: Dict[str, Any] = Field(default_factory=dict)
    assertions: List[AssertionSchema] = Field(default_factory=list)
    verify_ssl: bool = True
    ssl_check_expiry: bool = True
    ssl_expiry_warning_days: int = 30
    interval_seconds: int = 60
    timeout_seconds: int = 30
    retries: int = 0
    retry_delay_seconds: int = 5
    locations: List[str] = Field(default_factory=list)
    alert_on_failure: bool = True
    alert_after_failures: int = 2
    alert_channels: List[str] = Field(default_factory=list)
    escalation_policy_id: Optional[UUID] = None
    browser_script: Optional[str] = None
    browser_type: Optional[str] = None
    viewport_width: int = 1920
    viewport_height: int = 1080
    wait_for_selector: Optional[str] = None
    screenshots_enabled: bool = True
    warning_threshold_ms: int = 2000
    critical_threshold_ms: int = 5000
    service_id: Optional[UUID] = None
    tags: List[str] = Field(default_factory=list)
    labels: Dict[str, str] = Field(default_factory=dict)


class SyntheticCheckCreate(SyntheticCheckBase):
    pass


class SyntheticCheckUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target_url: Optional[str] = None
    method: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    body: Optional[str] = None
    body_type: Optional[str] = None
    auth_type: Optional[str] = None
    auth_config: Optional[Dict[str, Any]] = None
    assertions: Optional[List[AssertionSchema]] = None
    verify_ssl: Optional[bool] = None
    ssl_check_expiry: Optional[bool] = None
    ssl_expiry_warning_days: Optional[int] = None
    interval_seconds: Optional[int] = None
    timeout_seconds: Optional[int] = None
    retries: Optional[int] = None
    retry_delay_seconds: Optional[int] = None
    locations: Optional[List[str]] = None
    alert_on_failure: Optional[bool] = None
    alert_after_failures: Optional[int] = None
    alert_channels: Optional[List[str]] = None
    escalation_policy_id: Optional[UUID] = None
    browser_script: Optional[str] = None
    browser_type: Optional[str] = None
    viewport_width: Optional[int] = None
    viewport_height: Optional[int] = None
    wait_for_selector: Optional[str] = None
    screenshots_enabled: Optional[bool] = None
    warning_threshold_ms: Optional[int] = None
    critical_threshold_ms: Optional[int] = None
    service_id: Optional[UUID] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None
    labels: Optional[Dict[str, str]] = None


class SyntheticCheckResponse(SyntheticCheckBase):
    id: UUID
    organization_id: UUID
    status: str = "active"
    current_status: str = "unknown"
    last_check_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    uptime_percentage_24h: Optional[float] = None
    uptime_percentage_7d: Optional[float] = None
    uptime_percentage_30d: Optional[float] = None
    avg_response_time_24h: Optional[float] = None
    p95_response_time_24h: Optional[float] = None
    p99_response_time_24h: Optional[float] = None
    total_checks_24h: int = 0
    failed_checks_24h: int = 0
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SyntheticCheckList(BaseModel):
    items: List[SyntheticCheckResponse]
    total: int
    page: int
    page_size: int


# ==================== Check Result Schemas ====================

class AssertionResultSchema(BaseModel):
    assertion: AssertionSchema
    passed: bool
    actual_value: Optional[Any] = None
    message: Optional[str] = None


class SyntheticCheckResultBase(BaseModel):
    status: str
    location: Optional[str] = None
    executed_at: datetime
    response_time_ms: Optional[float] = None
    dns_time_ms: Optional[float] = None
    connect_time_ms: Optional[float] = None
    tls_time_ms: Optional[float] = None
    ttfb_ms: Optional[float] = None
    download_time_ms: Optional[float] = None
    total_time_ms: Optional[float] = None
    status_code: Optional[int] = None
    response_size_bytes: Optional[int] = None
    response_headers: Dict[str, str] = Field(default_factory=dict)
    response_body_preview: Optional[str] = None
    ssl_valid: Optional[bool] = None
    ssl_expiry_date: Optional[datetime] = None
    ssl_days_until_expiry: Optional[int] = None
    ssl_issuer: Optional[str] = None
    ssl_subject: Optional[str] = None
    assertions_passed: int = 0
    assertions_failed: int = 0
    assertion_results: List[AssertionResultSchema] = Field(default_factory=list)
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    error_details: Dict[str, Any] = Field(default_factory=dict)
    screenshots: List[str] = Field(default_factory=list)
    console_logs: List[Dict[str, Any]] = Field(default_factory=list)
    network_requests: List[Dict[str, Any]] = Field(default_factory=list)
    page_metrics: Dict[str, Any] = Field(default_factory=dict)
    retry_attempt: int = 0
    is_retry: bool = False


class SyntheticCheckResultCreate(BaseModel):
    check_id: UUID
    status: str
    location: Optional[str] = None
    executed_at: datetime
    response_time_ms: Optional[float] = None
    dns_time_ms: Optional[float] = None
    connect_time_ms: Optional[float] = None
    tls_time_ms: Optional[float] = None
    ttfb_ms: Optional[float] = None
    download_time_ms: Optional[float] = None
    total_time_ms: Optional[float] = None
    status_code: Optional[int] = None
    response_size_bytes: Optional[int] = None
    response_headers: Dict[str, str] = Field(default_factory=dict)
    response_body_preview: Optional[str] = None
    ssl_valid: Optional[bool] = None
    ssl_expiry_date: Optional[datetime] = None
    ssl_days_until_expiry: Optional[int] = None
    assertions_passed: int = 0
    assertions_failed: int = 0
    assertion_results: List[Dict[str, Any]] = Field(default_factory=list)
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    error_details: Dict[str, Any] = Field(default_factory=dict)
    retry_attempt: int = 0
    is_retry: bool = False


class SyntheticCheckResultResponse(SyntheticCheckResultBase):
    id: UUID
    organization_id: UUID
    check_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class SyntheticCheckResultList(BaseModel):
    items: List[SyntheticCheckResultResponse]
    total: int
    page: int
    page_size: int


# ==================== Location Schemas ====================

class SyntheticLocationBase(BaseModel):
    code: str
    name: str
    region: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    provider: Optional[str] = None
    provider_region: Optional[str] = None
    supports_browser: bool = True
    supports_http: bool = True
    supports_tcp: bool = True
    supports_dns: bool = True


class SyntheticLocationResponse(SyntheticLocationBase):
    id: UUID
    active: bool = True
    health_status: str = "healthy"
    last_health_check: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SyntheticLocationList(BaseModel):
    items: List[SyntheticLocationResponse]
    total: int


# ==================== Incident Schemas ====================

class SyntheticCheckIncidentResponse(BaseModel):
    id: UUID
    organization_id: UUID
    check_id: UUID
    incident_id: Optional[UUID] = None
    status: str
    started_at: datetime
    resolved_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    failure_count: int = 1
    locations_affected: List[str] = Field(default_factory=list)
    resolved_by: Optional[UUID] = None
    resolution_notes: Optional[str] = None
    auto_resolved: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== Statistics Schemas ====================

class SyntheticStats(BaseModel):
    total_checks: int
    active_checks: int
    paused_checks: int
    checks_up: int
    checks_down: int
    checks_degraded: int
    total_executions_24h: int
    successful_executions_24h: int
    failed_executions_24h: int
    avg_uptime_24h: float
    avg_response_time_24h: float
    open_incidents: int
    checks_by_type: Dict[str, int] = Field(default_factory=dict)
    checks_by_location: Dict[str, int] = Field(default_factory=dict)


class CheckOverview(BaseModel):
    check: SyntheticCheckResponse
    recent_results: List[SyntheticCheckResultResponse] = Field(default_factory=list)
    uptime_history: List[Dict[str, Any]] = Field(default_factory=list)
    response_time_history: List[Dict[str, Any]] = Field(default_factory=list)
    active_incidents: List[SyntheticCheckIncidentResponse] = Field(default_factory=list)


# ==================== Run Check Request ====================

class RunCheckRequest(BaseModel):
    """Request to manually run a check"""
    locations: Optional[List[str]] = None  # If not specified, use configured locations
