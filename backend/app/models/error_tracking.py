# backend/app/models/error_tracking.py
"""Models for Error Tracking (Sentry-like functionality)."""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from app.database import Base


class ErrorGroupStatus(str, enum.Enum):
    """Status of an error group."""
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class ErrorGroup(Base):
    """
    Error Group - represents a deduplicated group of similar errors.

    Similar to Sentry's "Issues" - groups multiple occurrences of the same
    error into a single trackable unit.
    """
    __tablename__ = "error_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )

    # Fingerprint for deduplication (SHA-256 hash)
    fingerprint = Column(String(64), nullable=False)

    # Error identification
    title = Column(String(500), nullable=False)  # Short title for display
    error_type = Column(String(255))  # TypeError, ValueError, etc.
    message = Column(Text)  # Error message template

    # Location info
    service_name = Column(String(255))
    filename = Column(String(500))
    function_name = Column(String(255))
    line_number = Column(Integer)
    column_number = Column(Integer)

    # Status
    status = Column(String(20), default=ErrorGroupStatus.UNRESOLVED.value)
    is_regression = Column(Boolean, default=False)

    # Counts
    event_count = Column(Integer, default=0)
    user_count = Column(Integer, default=0)

    # First/last occurrence
    first_seen_at = Column(DateTime(timezone=True), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)

    # Release tracking
    first_release = Column(String(100))
    last_release = Column(String(100))

    # Environments
    environments = Column(ARRAY(String(50)))

    # Assignment
    assigned_to_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL")
    )

    # Metadata
    tags = Column(JSONB, default=dict)
    extra_data = Column(JSONB, default=dict)

    # Timestamps
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", backref="error_groups")
    assigned_to = relationship("User", backref="assigned_error_groups")
    events = relationship("ErrorEvent", back_populates="error_group", cascade="all, delete-orphan")


class ErrorEvent(Base):
    """
    Error Event - represents a single occurrence of an error.

    Contains full context: stack trace, request info, user info,
    runtime environment, etc.
    """
    __tablename__ = "error_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    error_group_id = Column(
        UUID(as_uuid=True),
        ForeignKey("error_groups.id", ondelete="CASCADE"),
        nullable=False
    )

    # Timestamp
    timestamp = Column(DateTime(timezone=True), nullable=False)

    # Error details
    error_type = Column(String(255))
    message = Column(Text)
    stack_trace = Column(Text)  # Raw stack trace string
    stack_frames = Column(JSONB, default=list)  # Parsed frames

    # Context
    service_name = Column(String(255))
    environment = Column(String(50))  # production, staging, development
    release = Column(String(100))  # Application version/release

    # User info
    user_id = Column(String(255))  # Application user ID
    user_email = Column(String(255))
    user_ip = Column(String(45))

    # Request context (for web errors)
    request_url = Column(String(2000))
    request_method = Column(String(10))
    request_headers = Column(JSONB, default=dict)
    request_body = Column(Text)

    # Runtime info
    runtime = Column(String(50))  # node, python, go, browser
    runtime_version = Column(String(50))
    os = Column(String(100))
    os_version = Column(String(50))
    browser = Column(String(100))
    browser_version = Column(String(50))
    device = Column(String(100))

    # Trace correlation
    trace_id = Column(String(64))
    span_id = Column(String(32))

    # Additional context
    tags = Column(JSONB, default=dict)
    extra_data = Column(JSONB, default=dict)
    breadcrumbs = Column(JSONB, default=list)  # User actions before error

    # SDK info
    sdk_name = Column(String(100))
    sdk_version = Column(String(50))

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    organization = relationship("Organization", backref="error_events")
    error_group = relationship("ErrorGroup", back_populates="events")
