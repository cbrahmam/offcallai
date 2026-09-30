# backend/app/models/log_entry.py
"""
Log Entry model for centralized log management.
Stores log data collected from agents running on monitored hosts.
"""

from sqlalchemy import Column, String, Text, DateTime, Integer, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from app.database import Base


class LogLevel(str, enum.Enum):
    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    FATAL = "fatal"


class LogEntry(Base):
    """
    Stores individual log entries from monitored hosts.
    Designed for efficient searching and filtering.
    """
    __tablename__ = "log_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    host_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Timestamp when the log was generated
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    # Log level
    level = Column(String(10), nullable=False, default="info", index=True)

    # Source information
    source = Column(String(255), index=True)  # e.g., "nginx", "app", "system"
    service = Column(String(255), index=True)  # Service/application name
    filename = Column(String(512))  # Original log file path
    line_number = Column(Integer)

    # Log content
    message = Column(Text, nullable=False)
    raw_message = Column(Text)  # Original unparsed line

    # Structured fields extracted from the log
    fields = Column(JSONB, default=dict)  # Additional parsed fields

    # Tags for filtering
    tags = Column(JSONB, default=list)

    # Ingestion metadata
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    # Indexes for common queries
    __table_args__ = (
        Index('ix_log_entries_org_timestamp', 'organization_id', 'timestamp'),
        Index('ix_log_entries_org_host_timestamp', 'organization_id', 'host_id', 'timestamp'),
        Index('ix_log_entries_org_level', 'organization_id', 'level'),
        Index('ix_log_entries_org_source', 'organization_id', 'source'),
        # Full-text search index would be added in PostgreSQL directly
    )

    def __repr__(self):
        return f"<LogEntry(id='{self.id}', level='{self.level}', source='{self.source}')>"


class LogSource(Base):
    """
    Tracks log sources configured for collection on each host.
    """
    __tablename__ = "log_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    host_id = Column(UUID(as_uuid=True), nullable=True)  # NULL = all hosts

    # Source identification
    name = Column(String(255), nullable=False)  # Friendly name
    type = Column(String(50), nullable=False, default="file")  # file, journald, docker, syslog

    # Collection settings
    path = Column(String(512))  # File path or pattern (e.g., /var/log/*.log)
    multiline_pattern = Column(String(255))  # Regex for multiline logs
    include_patterns = Column(JSONB, default=list)  # Include filters
    exclude_patterns = Column(JSONB, default=list)  # Exclude filters

    # Parsing
    parser = Column(String(50), default="auto")  # auto, json, regex, nginx, apache, etc.
    parser_config = Column(JSONB, default=dict)  # Parser-specific config

    # Tags to add to all logs from this source
    tags = Column(JSONB, default=list)

    # Status
    is_active = Column(String(10), default="active")
    last_collected_at = Column(DateTime(timezone=True))
    error_message = Column(Text)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<LogSource(id='{self.id}', name='{self.name}', type='{self.type}')>"
