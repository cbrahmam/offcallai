# backend/app/models/synthetic.py
import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class SyntheticCheckType(str, enum.Enum):
    """Types of synthetic checks"""
    HTTP = "http"
    API = "api"
    BROWSER = "browser"
    TCP = "tcp"
    DNS = "dns"
    SSL = "ssl"
    PING = "ping"
    GRPC = "grpc"


class CheckStatus(str, enum.Enum):
    """Status of a synthetic check"""
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


class CheckResultStatus(str, enum.Enum):
    """Result status of a check execution"""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    ERROR = "error"


class SyntheticCheck(Base):
    """Synthetic monitoring check configuration"""
    __tablename__ = "synthetic_checks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Check identification
    name = Column(String(255), nullable=False)
    description = Column(Text)
    check_type = Column(String(20), nullable=False, index=True)
    status = Column(String(20), default="active", index=True)

    # Target configuration
    target_url = Column(String(2048), nullable=False)
    method = Column(String(10), default="GET")  # For HTTP/API checks
    headers = Column(JSONB, default=dict)
    body = Column(Text)
    body_type = Column(String(20))  # json, form, raw, graphql

    # Authentication
    auth_type = Column(String(20))  # none, basic, bearer, api_key, oauth
    auth_config = Column(JSONB, default=dict)  # Encrypted in production

    # Validation/Assertions
    assertions = Column(JSONB, default=list)
    # Example: [
    #   {"type": "status_code", "operator": "equals", "value": 200},
    #   {"type": "response_time", "operator": "less_than", "value": 2000},
    #   {"type": "body_contains", "value": "success"},
    #   {"type": "json_path", "path": "$.status", "operator": "equals", "value": "ok"},
    #   {"type": "header", "name": "content-type", "operator": "contains", "value": "json"}
    # ]

    # SSL Certificate validation
    verify_ssl = Column(Boolean, default=True)
    ssl_check_expiry = Column(Boolean, default=True)
    ssl_expiry_warning_days = Column(Integer, default=30)

    # Scheduling
    interval_seconds = Column(Integer, default=60, nullable=False)  # Check frequency
    timeout_seconds = Column(Integer, default=30)
    retries = Column(Integer, default=0)
    retry_delay_seconds = Column(Integer, default=5)

    # Locations (where to run checks from)
    locations = Column(JSONB, default=list)
    # Example: ["us-east-1", "eu-west-1", "ap-southeast-1"]

    # Alerting
    alert_on_failure = Column(Boolean, default=True)
    alert_after_failures = Column(Integer, default=2)  # Alert after N consecutive failures
    alert_channels = Column(JSONB, default=list)  # notification channel IDs
    escalation_policy_id = Column(UUID(as_uuid=True), ForeignKey("escalation_policies.id", ondelete="SET NULL"))

    # Browser test specific
    browser_script = Column(Text)  # Playwright/Puppeteer script
    browser_type = Column(String(20))  # chromium, firefox, webkit
    viewport_width = Column(Integer, default=1920)
    viewport_height = Column(Integer, default=1080)
    wait_for_selector = Column(String(500))
    screenshots_enabled = Column(Boolean, default=True)

    # Performance thresholds
    warning_threshold_ms = Column(Integer, default=2000)
    critical_threshold_ms = Column(Integer, default=5000)

    # State tracking
    current_status = Column(String(20), default="unknown")  # up, down, degraded, unknown
    last_check_at = Column(DateTime(timezone=True))
    last_success_at = Column(DateTime(timezone=True))
    last_failure_at = Column(DateTime(timezone=True))
    consecutive_failures = Column(Integer, default=0)
    consecutive_successes = Column(Integer, default=0)

    # Statistics
    uptime_percentage_24h = Column(Float)
    uptime_percentage_7d = Column(Float)
    uptime_percentage_30d = Column(Float)
    avg_response_time_24h = Column(Float)
    p95_response_time_24h = Column(Float)
    p99_response_time_24h = Column(Float)
    total_checks_24h = Column(Integer, default=0)
    failed_checks_24h = Column(Integer, default=0)

    # Service association
    service_id = Column(UUID(as_uuid=True), ForeignKey("services.id", ondelete="SET NULL"))

    # Metadata
    tags = Column(JSONB, default=list)
    labels = Column(JSONB, default=dict)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", backref="synthetic_checks")
    results = relationship("SyntheticCheckResult", back_populates="check", cascade="all, delete-orphan")


class SyntheticCheckResult(Base):
    """Results from synthetic check executions"""
    __tablename__ = "synthetic_check_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    check_id = Column(UUID(as_uuid=True), ForeignKey("synthetic_checks.id", ondelete="CASCADE"), nullable=False, index=True)

    # Execution details
    status = Column(String(20), nullable=False, index=True)  # success, failure, timeout, error
    location = Column(String(50), index=True)
    executed_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # Timing metrics
    response_time_ms = Column(Float)
    dns_time_ms = Column(Float)
    connect_time_ms = Column(Float)
    tls_time_ms = Column(Float)
    ttfb_ms = Column(Float)  # Time to first byte
    download_time_ms = Column(Float)
    total_time_ms = Column(Float)

    # Response details
    status_code = Column(Integer)
    response_size_bytes = Column(Integer)
    response_headers = Column(JSONB, default=dict)
    response_body_preview = Column(Text)  # First N characters

    # SSL details
    ssl_valid = Column(Boolean)
    ssl_expiry_date = Column(DateTime(timezone=True))
    ssl_days_until_expiry = Column(Integer)
    ssl_issuer = Column(String(255))
    ssl_subject = Column(String(255))

    # Assertion results
    assertions_passed = Column(Integer, default=0)
    assertions_failed = Column(Integer, default=0)
    assertion_results = Column(JSONB, default=list)
    # Example: [{"assertion": {...}, "passed": true, "actual_value": 200, "message": null}]

    # Error details
    error_type = Column(String(100))
    error_message = Column(Text)
    error_details = Column(JSONB, default=dict)

    # Browser test results
    screenshots = Column(JSONB, default=list)  # URLs to stored screenshots
    console_logs = Column(JSONB, default=list)
    network_requests = Column(JSONB, default=list)
    page_metrics = Column(JSONB, default=dict)
    # Example: {"dom_content_loaded": 1234, "load": 2345, "first_paint": 456, "first_contentful_paint": 567}

    # Retry info
    retry_attempt = Column(Integer, default=0)
    is_retry = Column(Boolean, default=False)

    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", backref="synthetic_check_results")
    check = relationship("SyntheticCheck", back_populates="results")


class SyntheticCheckIncident(Base):
    """Incidents triggered by synthetic check failures"""
    __tablename__ = "synthetic_check_incidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    check_id = Column(UUID(as_uuid=True), ForeignKey("synthetic_checks.id", ondelete="CASCADE"), nullable=False, index=True)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"), index=True)

    # Incident details
    status = Column(String(20), default="open", index=True)  # open, resolved, acknowledged
    started_at = Column(DateTime(timezone=True), nullable=False)
    resolved_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Float)

    # Failure details
    failure_count = Column(Integer, default=1)
    first_failure_result_id = Column(UUID(as_uuid=True))
    locations_affected = Column(JSONB, default=list)

    # Resolution
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    resolution_notes = Column(Text)
    auto_resolved = Column(Boolean, default=False)

    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", backref="synthetic_check_incidents")
    check = relationship("SyntheticCheck", backref="incidents")
    incident = relationship("Incident", backref="synthetic_check_incidents")


class SyntheticLocation(Base):
    """Available locations for running synthetic checks"""
    __tablename__ = "synthetic_locations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Location identification
    code = Column(String(50), unique=True, nullable=False)  # us-east-1, eu-west-1
    name = Column(String(100), nullable=False)  # US East (N. Virginia)
    region = Column(String(50))  # Americas, Europe, Asia-Pacific
    country = Column(String(100))
    city = Column(String(100))

    # Geographic coordinates
    latitude = Column(Float)
    longitude = Column(Float)

    # Provider info
    provider = Column(String(50))  # aws, gcp, azure, custom
    provider_region = Column(String(50))

    # Capabilities
    supports_browser = Column(Boolean, default=True)
    supports_http = Column(Boolean, default=True)
    supports_tcp = Column(Boolean, default=True)
    supports_dns = Column(Boolean, default=True)

    # Status
    active = Column(Boolean, default=True)
    health_status = Column(String(20), default="healthy")
    last_health_check = Column(DateTime(timezone=True))

    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
