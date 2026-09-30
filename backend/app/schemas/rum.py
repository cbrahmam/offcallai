# backend/app/schemas/rum.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


# ==================== RUM Application Schemas ====================

class RUMApplicationBase(BaseModel):
    name: str
    description: Optional[str] = None
    domain: Optional[str] = None
    allowed_origins: List[str] = Field(default_factory=list)
    enabled: bool = True
    sample_rate: float = 100.0
    track_errors: bool = True
    track_performance: bool = True
    track_user_actions: bool = True
    track_resources: bool = True
    track_long_tasks: bool = True
    mask_user_input: bool = True
    excluded_urls: List[str] = Field(default_factory=list)
    error_rate_threshold: float = 5.0
    lcp_threshold_ms: int = 2500
    fid_threshold_ms: int = 100
    cls_threshold: float = 0.1
    tags: List[str] = Field(default_factory=list)


class RUMApplicationCreate(RUMApplicationBase):
    pass


class RUMApplicationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    domain: Optional[str] = None
    allowed_origins: Optional[List[str]] = None
    enabled: Optional[bool] = None
    sample_rate: Optional[float] = None
    track_errors: Optional[bool] = None
    track_performance: Optional[bool] = None
    track_user_actions: Optional[bool] = None
    track_resources: Optional[bool] = None
    track_long_tasks: Optional[bool] = None
    mask_user_input: Optional[bool] = None
    excluded_urls: Optional[List[str]] = None
    error_rate_threshold: Optional[float] = None
    lcp_threshold_ms: Optional[int] = None
    fid_threshold_ms: Optional[int] = None
    cls_threshold: Optional[float] = None
    tags: Optional[List[str]] = None


class RUMApplicationResponse(RUMApplicationBase):
    id: UUID
    organization_id: UUID
    api_key: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RUMApplicationList(BaseModel):
    items: List[RUMApplicationResponse]
    total: int


# ==================== RUM Session Schemas ====================

class RUMSessionCreate(BaseModel):
    session_id: str
    user_id: Optional[str] = None
    anonymous_id: Optional[str] = None
    session_start: datetime
    user_agent: Optional[str] = None
    browser_name: Optional[str] = None
    browser_version: Optional[str] = None
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    device_type: Optional[str] = None
    screen_width: Optional[int] = None
    screen_height: Optional[int] = None
    viewport_width: Optional[int] = None
    viewport_height: Optional[int] = None
    connection_type: Optional[str] = None
    effective_bandwidth_mbps: Optional[float] = None
    entry_url: Optional[str] = None
    referrer: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None


class RUMSessionUpdate(BaseModel):
    session_end: Optional[datetime] = None
    duration_ms: Optional[int] = None
    page_views: Optional[int] = None
    interactions: Optional[int] = None
    errors_count: Optional[int] = None
    is_bounce: Optional[bool] = None


class RUMSessionResponse(BaseModel):
    id: UUID
    organization_id: UUID
    application_id: UUID
    session_id: str
    user_id: Optional[str] = None
    anonymous_id: Optional[str] = None
    session_start: datetime
    session_end: Optional[datetime] = None
    duration_ms: Optional[int] = None
    page_views: int = 0
    interactions: int = 0
    errors_count: int = 0
    browser_name: Optional[str] = None
    browser_version: Optional[str] = None
    os_name: Optional[str] = None
    device_type: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    entry_url: Optional[str] = None
    is_bounce: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class RUMSessionList(BaseModel):
    items: List[RUMSessionResponse]
    total: int
    page: int
    page_size: int


# ==================== RUM Page View Schemas ====================

class RUMPageViewCreate(BaseModel):
    session_id: str  # Client session ID to look up
    url: str
    url_path: Optional[str] = None
    page_title: Optional[str] = None
    timestamp: datetime
    time_on_page_ms: Optional[int] = None
    # Core Web Vitals
    lcp_ms: Optional[int] = None
    fid_ms: Optional[int] = None
    cls: Optional[float] = None
    fcp_ms: Optional[int] = None
    ttfb_ms: Optional[int] = None
    inp_ms: Optional[int] = None
    # Navigation timing
    dns_lookup_ms: Optional[int] = None
    tcp_connect_ms: Optional[int] = None
    ssl_handshake_ms: Optional[int] = None
    request_time_ms: Optional[int] = None
    response_time_ms: Optional[int] = None
    dom_interactive_ms: Optional[int] = None
    dom_complete_ms: Optional[int] = None
    load_event_ms: Optional[int] = None
    # Resources
    resource_count: Optional[int] = None
    total_resource_size_bytes: Optional[int] = None
    total_resource_load_time_ms: Optional[int] = None
    # Custom
    custom_attributes: Dict[str, Any] = Field(default_factory=dict)


class RUMPageViewResponse(BaseModel):
    id: UUID
    organization_id: UUID
    application_id: UUID
    session_id: UUID
    url: str
    url_path: Optional[str] = None
    page_title: Optional[str] = None
    timestamp: datetime
    time_on_page_ms: Optional[int] = None
    lcp_ms: Optional[int] = None
    fid_ms: Optional[int] = None
    cls: Optional[float] = None
    fcp_ms: Optional[int] = None
    ttfb_ms: Optional[int] = None
    load_event_ms: Optional[int] = None
    resource_count: int = 0
    js_errors_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class RUMPageViewList(BaseModel):
    items: List[RUMPageViewResponse]
    total: int
    page: int
    page_size: int


# ==================== RUM Error Schemas ====================

class RUMErrorCreate(BaseModel):
    session_id: str
    error_type: str
    error_name: Optional[str] = None
    message: str
    stack_trace: Optional[str] = None
    filename: Optional[str] = None
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    url: Optional[str] = None
    url_path: Optional[str] = None
    timestamp: datetime
    user_id: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    is_handled: bool = False


class RUMErrorResponse(BaseModel):
    id: UUID
    organization_id: UUID
    application_id: UUID
    session_id: Optional[UUID] = None
    error_type: str
    error_name: Optional[str] = None
    message: str
    stack_trace: Optional[str] = None
    filename: Optional[str] = None
    line_number: Optional[int] = None
    url: Optional[str] = None
    url_path: Optional[str] = None
    fingerprint: Optional[str] = None
    timestamp: datetime
    user_id: Optional[str] = None
    is_handled: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class RUMErrorList(BaseModel):
    items: List[RUMErrorResponse]
    total: int
    page: int
    page_size: int


class RUMErrorGroup(BaseModel):
    fingerprint: str
    error_name: Optional[str]
    message: str
    count: int
    first_seen: datetime
    last_seen: datetime
    affected_users: int
    affected_sessions: int


# ==================== RUM User Action Schemas ====================

class RUMUserActionCreate(BaseModel):
    session_id: str
    action_type: str
    action_name: Optional[str] = None
    target_selector: Optional[str] = None
    target_tag: Optional[str] = None
    target_id: Optional[str] = None
    target_class: Optional[str] = None
    target_text: Optional[str] = None
    timestamp: datetime
    duration_ms: Optional[int] = None
    page_x: Optional[int] = None
    page_y: Optional[int] = None
    url: Optional[str] = None
    url_path: Optional[str] = None
    custom_data: Dict[str, Any] = Field(default_factory=dict)


class RUMUserActionResponse(BaseModel):
    id: UUID
    organization_id: UUID
    application_id: UUID
    session_id: UUID
    action_type: str
    action_name: Optional[str] = None
    target_tag: Optional[str] = None
    target_text: Optional[str] = None
    timestamp: datetime
    duration_ms: Optional[int] = None
    url_path: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class RUMUserActionList(BaseModel):
    items: List[RUMUserActionResponse]
    total: int


# ==================== RUM Resource Schemas ====================

class RUMResourceCreate(BaseModel):
    page_view_id: UUID
    resource_url: str
    resource_type: Optional[str] = None
    timestamp: datetime
    start_time_ms: Optional[int] = None
    duration_ms: Optional[int] = None
    dns_time_ms: Optional[int] = None
    connect_time_ms: Optional[int] = None
    ssl_time_ms: Optional[int] = None
    ttfb_ms: Optional[int] = None
    download_time_ms: Optional[int] = None
    transfer_size_bytes: Optional[int] = None
    decoded_size_bytes: Optional[int] = None
    from_cache: bool = False
    status_code: Optional[int] = None
    failed: bool = False


class RUMResourceResponse(BaseModel):
    id: UUID
    resource_url: str
    resource_type: Optional[str] = None
    duration_ms: Optional[int] = None
    transfer_size_bytes: Optional[int] = None
    from_cache: bool = False
    status_code: Optional[int] = None
    failed: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== RUM Alert Schemas ====================

class RUMAlertResponse(BaseModel):
    id: UUID
    organization_id: UUID
    application_id: UUID
    alert_type: str
    severity: str
    status: str
    title: str
    message: Optional[str] = None
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold_value: Optional[float] = None
    url_pattern: Optional[str] = None
    triggered_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True


class RUMAlertList(BaseModel):
    items: List[RUMAlertResponse]
    total: int
    page: int
    page_size: int


# ==================== RUM Statistics Schemas ====================

class CoreWebVitalsStats(BaseModel):
    lcp_p50_ms: float = 0
    lcp_p75_ms: float = 0
    lcp_p90_ms: float = 0
    fid_p50_ms: float = 0
    fid_p75_ms: float = 0
    fid_p90_ms: float = 0
    cls_p50: float = 0
    cls_p75: float = 0
    cls_p90: float = 0
    fcp_p50_ms: float = 0
    fcp_p75_ms: float = 0
    ttfb_p50_ms: float = 0
    ttfb_p75_ms: float = 0


class RUMStats(BaseModel):
    total_sessions: int = 0
    active_sessions: int = 0
    total_page_views: int = 0
    total_errors: int = 0
    error_rate_percent: float = 0
    unique_users: int = 0
    avg_session_duration_ms: int = 0
    bounce_rate_percent: float = 0
    avg_page_views_per_session: float = 0
    core_web_vitals: CoreWebVitalsStats = Field(default_factory=CoreWebVitalsStats)
    top_pages: List[Dict[str, Any]] = Field(default_factory=list)
    top_errors: List[Dict[str, Any]] = Field(default_factory=list)
    browser_breakdown: Dict[str, int] = Field(default_factory=dict)
    device_breakdown: Dict[str, int] = Field(default_factory=dict)
    country_breakdown: Dict[str, int] = Field(default_factory=dict)


class RUMApplicationOverview(BaseModel):
    application: RUMApplicationResponse
    stats: RUMStats
    recent_errors: List[RUMErrorResponse] = Field(default_factory=list)
    recent_alerts: List[RUMAlertResponse] = Field(default_factory=list)


# ==================== Data Ingestion Schemas ====================

class RUMEventBatch(BaseModel):
    """Batch of RUM events from client SDK"""
    api_key: str
    session_id: str
    events: List[Dict[str, Any]]


class RUMBeaconData(BaseModel):
    """Beacon data sent on page unload"""
    api_key: str
    session_id: str
    page_view_id: Optional[str] = None
    time_on_page_ms: Optional[int] = None
    interactions: Optional[int] = None
    final_cls: Optional[float] = None
