# backend/app/models/rum.py
import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class RUMApplication(Base):
    """RUM application configuration"""
    __tablename__ = "rum_applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Application info
    name = Column(String(255), nullable=False)
    description = Column(Text)
    domain = Column(String(255))  # Primary domain
    allowed_origins = Column(JSONB, default=list)  # List of allowed origins

    # API Key for client SDK
    api_key = Column(String(64), unique=True, nullable=False)

    # Configuration
    enabled = Column(Boolean, default=True)
    sample_rate = Column(Float, default=100.0)  # Percentage of sessions to track
    track_errors = Column(Boolean, default=True)
    track_performance = Column(Boolean, default=True)
    track_user_actions = Column(Boolean, default=True)
    track_resources = Column(Boolean, default=True)
    track_long_tasks = Column(Boolean, default=True)

    # Privacy settings
    mask_user_input = Column(Boolean, default=True)
    excluded_urls = Column(JSONB, default=list)  # URLs to exclude from tracking

    # Alerting thresholds
    error_rate_threshold = Column(Float, default=5.0)  # Alert if error rate > 5%
    lcp_threshold_ms = Column(Integer, default=2500)  # Largest Contentful Paint
    fid_threshold_ms = Column(Integer, default=100)  # First Input Delay
    cls_threshold = Column(Float, default=0.1)  # Cumulative Layout Shift

    # Metadata
    tags = Column(JSONB, default=list)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", backref="rum_applications")


class RUMSession(Base):
    """Browser session for a user"""
    __tablename__ = "rum_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(UUID(as_uuid=True), ForeignKey("rum_applications.id", ondelete="CASCADE"), nullable=False, index=True)

    # Session identification
    session_id = Column(String(64), nullable=False, index=True)  # Client-generated session ID
    user_id = Column(String(255), index=True)  # Optional user identifier
    anonymous_id = Column(String(64))  # Anonymous tracking ID

    # Session timing
    session_start = Column(DateTime(timezone=True), nullable=False, index=True)
    session_end = Column(DateTime(timezone=True))
    duration_ms = Column(BigInteger)

    # Session info
    page_views = Column(Integer, default=0)
    interactions = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)

    # Device & Browser info
    user_agent = Column(Text)
    browser_name = Column(String(50))
    browser_version = Column(String(30))
    os_name = Column(String(50))
    os_version = Column(String(30))
    device_type = Column(String(20))  # desktop, mobile, tablet
    screen_width = Column(Integer)
    screen_height = Column(Integer)
    viewport_width = Column(Integer)
    viewport_height = Column(Integer)

    # Connection info
    connection_type = Column(String(20))  # 4g, 3g, wifi, etc.
    effective_bandwidth_mbps = Column(Float)

    # Location (geo-ip)
    country = Column(String(100))
    region = Column(String(100))
    city = Column(String(100))
    ip_address = Column(String(45))

    # Entry point
    entry_url = Column(Text)
    referrer = Column(Text)
    utm_source = Column(String(100))
    utm_medium = Column(String(100))
    utm_campaign = Column(String(100))

    # Status
    is_bounce = Column(Boolean, default=False)  # Single page view, no interaction

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", backref="rum_sessions")
    application = relationship("RUMApplication", backref="sessions")


class RUMPageView(Base):
    """Individual page view within a session"""
    __tablename__ = "rum_page_views"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(UUID(as_uuid=True), ForeignKey("rum_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("rum_sessions.id", ondelete="CASCADE"), nullable=False, index=True)

    # Page info
    url = Column(Text, nullable=False)
    url_path = Column(String(500), index=True)  # Just the path portion
    page_title = Column(String(500))

    # Timing
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    time_on_page_ms = Column(BigInteger)

    # Core Web Vitals
    lcp_ms = Column(Integer)  # Largest Contentful Paint
    fid_ms = Column(Integer)  # First Input Delay
    cls = Column(Float)  # Cumulative Layout Shift
    fcp_ms = Column(Integer)  # First Contentful Paint
    ttfb_ms = Column(Integer)  # Time to First Byte
    inp_ms = Column(Integer)  # Interaction to Next Paint

    # Navigation timing
    dns_lookup_ms = Column(Integer)
    tcp_connect_ms = Column(Integer)
    ssl_handshake_ms = Column(Integer)
    request_time_ms = Column(Integer)
    response_time_ms = Column(Integer)
    dom_interactive_ms = Column(Integer)
    dom_complete_ms = Column(Integer)
    load_event_ms = Column(Integer)

    # Resource metrics
    resource_count = Column(Integer, default=0)
    total_resource_size_bytes = Column(BigInteger)
    total_resource_load_time_ms = Column(BigInteger)

    # JavaScript errors on this page
    js_errors_count = Column(Integer, default=0)

    # Custom attributes
    custom_attributes = Column(JSONB, default=dict)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", backref="rum_page_views")


class RUMError(Base):
    """JavaScript and client-side errors"""
    __tablename__ = "rum_errors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(UUID(as_uuid=True), ForeignKey("rum_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("rum_sessions.id", ondelete="CASCADE"), index=True)
    page_view_id = Column(UUID(as_uuid=True), ForeignKey("rum_page_views.id", ondelete="SET NULL"), index=True)

    # Error info
    error_type = Column(String(50), nullable=False, index=True)  # js_error, network_error, console_error
    error_name = Column(String(255))  # TypeError, ReferenceError, etc.
    message = Column(Text, nullable=False)
    stack_trace = Column(Text)

    # Source info
    filename = Column(Text)
    line_number = Column(Integer)
    column_number = Column(Integer)

    # Context
    url = Column(Text)
    url_path = Column(String(500), index=True)
    user_agent = Column(Text)

    # Grouping fingerprint
    fingerprint = Column(String(64), index=True)  # Hash for grouping similar errors

    # Timing
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    # User context
    user_id = Column(String(255), index=True)

    # Extra context
    context = Column(JSONB, default=dict)  # Custom error context

    # Status
    is_handled = Column(Boolean, default=False)  # Was error caught by try/catch

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", backref="rum_errors")


class RUMUserAction(Base):
    """User interactions (clicks, inputs, etc.)"""
    __tablename__ = "rum_user_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(UUID(as_uuid=True), ForeignKey("rum_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("rum_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    page_view_id = Column(UUID(as_uuid=True), ForeignKey("rum_page_views.id", ondelete="SET NULL"), index=True)

    # Action info
    action_type = Column(String(50), nullable=False, index=True)  # click, input, scroll, custom
    action_name = Column(String(255))  # Button text, input label, custom name

    # Target element
    target_selector = Column(Text)  # CSS selector
    target_tag = Column(String(30))  # button, a, input, etc.
    target_id = Column(String(255))
    target_class = Column(String(500))
    target_text = Column(String(500))  # Truncated inner text

    # Timing
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    duration_ms = Column(Integer)  # For long actions

    # Position
    page_x = Column(Integer)
    page_y = Column(Integer)

    # Context
    url = Column(Text)
    url_path = Column(String(500), index=True)

    # Custom data
    custom_data = Column(JSONB, default=dict)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", backref="rum_user_actions")


class RUMResource(Base):
    """Resource loading performance (scripts, images, etc.)"""
    __tablename__ = "rum_resources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(UUID(as_uuid=True), ForeignKey("rum_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    page_view_id = Column(UUID(as_uuid=True), ForeignKey("rum_page_views.id", ondelete="CASCADE"), nullable=False, index=True)

    # Resource info
    resource_url = Column(Text, nullable=False)
    resource_type = Column(String(30), index=True)  # script, stylesheet, image, font, xhr, fetch

    # Timing
    timestamp = Column(DateTime(timezone=True), nullable=False)
    start_time_ms = Column(Integer)
    duration_ms = Column(Integer)

    # Detailed timing
    dns_time_ms = Column(Integer)
    connect_time_ms = Column(Integer)
    ssl_time_ms = Column(Integer)
    ttfb_ms = Column(Integer)
    download_time_ms = Column(Integer)

    # Size
    transfer_size_bytes = Column(BigInteger)
    decoded_size_bytes = Column(BigInteger)

    # Cache
    from_cache = Column(Boolean, default=False)

    # Status
    status_code = Column(Integer)
    failed = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", backref="rum_resources")


class RUMAlert(Base):
    """Alerts generated from RUM data"""
    __tablename__ = "rum_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(UUID(as_uuid=True), ForeignKey("rum_applications.id", ondelete="CASCADE"), nullable=False, index=True)

    # Alert info
    alert_type = Column(String(50), nullable=False, index=True)  # error_spike, slow_lcp, high_cls, etc.
    severity = Column(String(20), default="warning", index=True)
    status = Column(String(20), default="active", index=True)

    title = Column(String(255), nullable=False)
    message = Column(Text)

    # Metric info
    metric_name = Column(String(100))
    metric_value = Column(Float)
    threshold_value = Column(Float)

    # Affected scope
    url_pattern = Column(String(500))  # Which URLs are affected

    # Timing
    triggered_at = Column(DateTime(timezone=True), nullable=False, index=True)
    acknowledged_at = Column(DateTime(timezone=True))
    acknowledged_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at = Column(DateTime(timezone=True))

    # Context
    context = Column(JSONB, default=dict)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", backref="rum_alerts")
    application = relationship("RUMApplication", backref="alerts")
