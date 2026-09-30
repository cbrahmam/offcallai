# backend/app/schemas/log.py
"""
Pydantic schemas for Log Management API.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class LogLevel(str, Enum):
    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    FATAL = "fatal"


class LogSourceType(str, Enum):
    FILE = "file"
    JOURNALD = "journald"
    DOCKER = "docker"
    SYSLOG = "syslog"
    KUBERNETES = "kubernetes"


# ============================================
# Log Ingestion Schemas
# ============================================

class LogEntryIngest(BaseModel):
    """Single log entry for ingestion."""
    timestamp: datetime
    level: Optional[str] = "info"  # Accept string from agent, normalize later
    source: Optional[str] = None
    service: Optional[str] = None
    host: Optional[str] = None  # Hostname from agent
    filename: Optional[str] = None
    line_number: Optional[int] = None
    message: str
    raw_message: Optional[str] = None
    fields: Optional[Dict[str, Any]] = None
    attributes: Optional[Dict[str, Any]] = None  # Alternative field name from agent
    tags: Optional[Dict[str, str]] = None  # Agent sends as map, not list


class LogBatch(BaseModel):
    """Batch of log entries for ingestion from agent."""
    agent_id: str = Field(..., description="Agent identifier")
    logs: List[LogEntryIngest] = Field(..., max_length=1000)
    collected_at: Optional[datetime] = None


class LogIngestResponse(BaseModel):
    """Response after log ingestion."""
    success: bool
    logs_received: int
    logs_stored: Optional[int] = None
    host_id: Optional[str] = None
    message: Optional[str] = None
    errors: List[str] = []


# ============================================
# Log Query Schemas
# ============================================

class LogQuery(BaseModel):
    """Query parameters for searching logs."""
    query: Optional[str] = Field(None, description="Full-text search query")
    start_time: datetime
    end_time: datetime
    levels: Optional[List[LogLevel]] = None
    sources: Optional[List[str]] = None
    services: Optional[List[str]] = None
    host_ids: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    fields: Optional[Dict[str, str]] = None  # Field filters
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)
    order: str = Field("desc", pattern="^(asc|desc)$")


class LogEntryResponse(BaseModel):
    """Single log entry in response."""
    id: str
    timestamp: datetime
    level: str
    source: Optional[str]
    service: Optional[str]
    filename: Optional[str]
    line_number: Optional[int]
    message: str
    fields: Dict[str, Any]
    tags: List[str]
    host_id: str
    hostname: Optional[str]

    class Config:
        from_attributes = True


class LogQueryResponse(BaseModel):
    """Response for log query."""
    logs: List[LogEntryResponse]
    total: int
    query: LogQuery
    has_more: bool


class LogStreamPosition(BaseModel):
    """Position for streaming logs (live tail)."""
    last_id: Optional[str] = None
    last_timestamp: Optional[datetime] = None


# ============================================
# Log Statistics
# ============================================

class LogLevelCount(BaseModel):
    """Count of logs per level."""
    level: str
    count: int


class LogSourceCount(BaseModel):
    """Count of logs per source."""
    source: str
    count: int


class LogStats(BaseModel):
    """Log statistics summary."""
    total_logs: int
    time_range_hours: int
    by_level: List[LogLevelCount]
    by_source: List[LogSourceCount]
    logs_per_hour: List[Dict[str, Any]]


# ============================================
# Log Source Management
# ============================================

class LogSourceCreate(BaseModel):
    """Create a new log source configuration."""
    name: str = Field(..., min_length=1, max_length=255)
    type: LogSourceType = LogSourceType.FILE
    host_id: Optional[str] = None  # NULL = all hosts
    path: Optional[str] = Field(None, max_length=512)
    multiline_pattern: Optional[str] = None
    include_patterns: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None
    parser: str = Field("auto", max_length=50)
    parser_config: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class LogSourceUpdate(BaseModel):
    """Update log source configuration."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    path: Optional[str] = Field(None, max_length=512)
    multiline_pattern: Optional[str] = None
    include_patterns: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None
    parser: Optional[str] = Field(None, max_length=50)
    parser_config: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    is_active: Optional[str] = None


class LogSourceResponse(BaseModel):
    """Log source configuration response."""
    id: str
    name: str
    type: str
    host_id: Optional[str]
    path: Optional[str]
    multiline_pattern: Optional[str]
    include_patterns: List[str]
    exclude_patterns: List[str]
    parser: str
    parser_config: Dict[str, Any]
    tags: List[str]
    is_active: str
    last_collected_at: Optional[datetime]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LogSourceListResponse(BaseModel):
    """List of log sources."""
    sources: List[LogSourceResponse]
    total: int


# ============================================
# Log Context
# ============================================

class LogContext(BaseModel):
    """Log entry with surrounding context."""
    before: List[LogEntryResponse]
    current: LogEntryResponse
    after: List[LogEntryResponse]
