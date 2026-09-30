# backend/app/schemas/profile.py
"""Pydantic schemas for Continuous Profiling."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


class ProfileType(str, Enum):
    """Profile types."""
    CPU = "cpu"
    HEAP = "heap"
    GOROUTINE = "goroutine"
    BLOCK = "block"
    MUTEX = "mutex"
    ALLOCS = "allocs"
    WALL = "wall"
    LOCK = "lock"


class ProfileFormat(str, Enum):
    """Profile formats."""
    PPROF = "pprof"
    COLLAPSED = "collapsed"
    JFR = "jfr"
    PERF = "perf"


# ========================================
# Profile Upload / Ingestion
# ========================================

class ProfileUpload(BaseModel):
    """Schema for uploading a profile."""
    service_name: str = Field(..., description="Service name")
    profile_type: ProfileType = Field(..., description="Type of profile")
    format: ProfileFormat = Field(default=ProfileFormat.PPROF, description="Profile data format")

    # Profile data (base64 encoded)
    profile_data: str = Field(..., description="Base64-encoded profile data")

    # Time range
    start_time: datetime = Field(..., description="Profile start time")
    end_time: Optional[datetime] = Field(None, description="Profile end time")
    duration_seconds: Optional[int] = Field(None, description="Profile duration in seconds")

    # Environment
    environment: Optional[str] = Field("production", description="Environment name")
    runtime: Optional[str] = Field(None, description="Runtime (go, python, java, node)")
    runtime_version: Optional[str] = Field(None, description="Runtime version")

    # Correlation
    host_id: Optional[str] = Field(None, description="Host ID")
    trace_id: Optional[str] = Field(None, description="Trace ID for correlation")
    span_id: Optional[str] = Field(None, description="Span ID for correlation")

    # Metadata
    tags: Optional[Dict[str, str]] = Field(default_factory=dict, description="Tags")
    labels: Optional[Dict[str, str]] = Field(default_factory=dict, description="Labels")


class ProfileUploadResponse(BaseModel):
    """Response for profile upload."""
    id: UUID
    service_name: str
    profile_type: str
    profile_size_bytes: int
    sample_count: Optional[int]
    created_at: datetime


# ========================================
# Profile Retrieval
# ========================================

class ProfileSummary(BaseModel):
    """Summary of a profile for list views."""
    id: UUID
    service_name: str
    profile_type: str
    format: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: Optional[int]
    profile_size_bytes: Optional[int]
    sample_count: Optional[int]
    environment: Optional[str]
    runtime: Optional[str]
    trace_id: Optional[str]
    top_functions: Optional[List[Dict[str, Any]]]
    created_at: datetime


class ProfileDetail(ProfileSummary):
    """Full profile details."""
    host_id: Optional[UUID]
    runtime_version: Optional[str]
    span_id: Optional[str]
    tags: Optional[Dict[str, str]]
    labels: Optional[Dict[str, str]]
    total_samples: Optional[int]
    total_cpu_ns: Optional[int]
    total_alloc_bytes: Optional[int]


class ProfileWithData(ProfileDetail):
    """Profile with raw data (for download)."""
    profile_data_base64: Optional[str] = Field(None, description="Base64-encoded profile data")


# ========================================
# Flamegraph Data
# ========================================

class FlamegraphNode(BaseModel):
    """A node in the flamegraph."""
    name: str = Field(..., description="Function/method name")
    value: int = Field(..., description="Sample count or time")
    children: List["FlamegraphNode"] = Field(default_factory=list)

    # Optional metadata
    file: Optional[str] = Field(None, description="Source file")
    line: Optional[int] = Field(None, description="Line number")
    self_value: Optional[int] = Field(None, description="Self time (excluding children)")


FlamegraphNode.model_rebuild()  # Rebuild for recursive type


class FlamegraphData(BaseModel):
    """Flamegraph data for visualization."""
    profile_id: UUID
    profile_type: str
    service_name: str
    start_time: datetime
    duration_seconds: Optional[int]

    # The root of the flamegraph tree
    root: FlamegraphNode

    # Metadata
    total_samples: int
    unit: str = Field("samples", description="Unit for values (samples, nanoseconds, bytes)")


# ========================================
# Profile Comparison / Diff
# ========================================

class ProfileDiffRequest(BaseModel):
    """Request to compare two profiles."""
    base_profile_id: UUID = Field(..., description="Base profile ID")
    compare_profile_id: UUID = Field(..., description="Profile to compare against")


class FunctionDiff(BaseModel):
    """Diff for a single function."""
    name: str
    base_value: int
    compare_value: int
    diff: int
    diff_percent: float
    file: Optional[str]


class ProfileDiff(BaseModel):
    """Result of comparing two profiles."""
    base_profile_id: UUID
    compare_profile_id: UUID
    profile_type: str

    # Summary stats
    base_total_samples: int
    compare_total_samples: int
    total_diff: int
    total_diff_percent: float

    # Top functions with biggest changes
    top_increases: List[FunctionDiff]
    top_decreases: List[FunctionDiff]

    # Full diff tree (optional)
    diff_tree: Optional[FlamegraphNode] = None


# ========================================
# Aggregates and Stats
# ========================================

class ProfileStats(BaseModel):
    """Profile statistics for a service."""
    service_name: str
    profile_type: str
    environment: Optional[str]

    # Time range
    start_time: datetime
    end_time: datetime

    # Counts
    profile_count: int
    total_samples: int
    avg_duration_seconds: float

    # Top functions
    top_functions: List[Dict[str, Any]]


class ServiceProfilingOverview(BaseModel):
    """Profiling overview for a service."""
    service_name: str
    environments: List[str]
    profile_types: List[str]

    # Recent activity
    last_profile_at: Optional[datetime]
    profiles_last_24h: int
    profiles_last_7d: int

    # Trends (vs previous period)
    cpu_trend_percent: Optional[float]
    memory_trend_percent: Optional[float]

    # Top consuming functions
    top_cpu_functions: Optional[List[Dict[str, Any]]]
    top_memory_functions: Optional[List[Dict[str, Any]]]
