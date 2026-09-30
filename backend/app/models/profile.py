# backend/app/models/profile.py
"""SQLAlchemy models for Continuous Profiling."""

import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, Integer, BigInteger, Float, LargeBinary, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class ProfileType(str, Enum):
    """Profile types."""
    CPU = "cpu"
    HEAP = "heap"
    GOROUTINE = "goroutine"
    BLOCK = "block"
    MUTEX = "mutex"
    ALLOCS = "allocs"
    THREADCREATE = "threadcreate"
    WALL = "wall"  # Wall-clock time
    LOCK = "lock"  # Lock contention


class ProfileFormat(str, Enum):
    """Profile data formats."""
    PPROF = "pprof"  # Go pprof format
    COLLAPSED = "collapsed"  # Brendan Gregg's collapsed stack format
    JFR = "jfr"  # Java Flight Recorder
    PERF = "perf"  # Linux perf format


class Profile(Base):
    """Profile storage for continuous profiling."""

    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    host_id = Column(UUID(as_uuid=True), ForeignKey("hosts.id", ondelete="SET NULL"), nullable=True)

    # Profile identification
    service_name = Column(String(255), nullable=False, index=True)
    profile_type = Column(String(50), nullable=False)  # ProfileType enum value
    format = Column(String(20), nullable=False, default=ProfileFormat.PPROF.value)

    # Time range
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Profile data (stored compressed with gzip/zstd)
    profile_data = Column(LargeBinary, nullable=True)
    profile_size_bytes = Column(BigInteger, nullable=True)
    sample_count = Column(Integer, nullable=True)

    # Correlation with distributed traces
    trace_id = Column(String(64), nullable=True, index=True)
    span_id = Column(String(32), nullable=True)

    # Environment info
    environment = Column(String(50), nullable=True, default="production")
    runtime = Column(String(50), nullable=True)  # go, python, java, node
    runtime_version = Column(String(50), nullable=True)

    # Metadata
    tags = Column(JSONB, nullable=True, default=dict)
    labels = Column(JSONB, nullable=True, default=dict)

    # Aggregated metrics for quick filtering
    total_samples = Column(BigInteger, nullable=True)
    total_cpu_ns = Column(BigInteger, nullable=True)  # For CPU profiles
    total_alloc_bytes = Column(BigInteger, nullable=True)  # For heap profiles
    top_functions = Column(JSONB, nullable=True)  # Top N functions for quick display

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships (no back_populates to avoid requiring changes to Organization/Host models)
    organization = relationship("Organization")
    host = relationship("Host")

    __table_args__ = (
        Index("ix_profiles_org_service", "organization_id", "service_name"),
        Index("ix_profiles_org_type", "organization_id", "profile_type"),
    )

    def to_dict(self, include_data: bool = False) -> dict:
        """Convert to dictionary for API response."""
        result = {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "host_id": str(self.host_id) if self.host_id else None,
            "service_name": self.service_name,
            "profile_type": self.profile_type,
            "format": self.format,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "profile_size_bytes": self.profile_size_bytes,
            "sample_count": self.sample_count,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "environment": self.environment,
            "runtime": self.runtime,
            "runtime_version": self.runtime_version,
            "tags": self.tags,
            "labels": self.labels,
            "total_samples": self.total_samples,
            "total_cpu_ns": self.total_cpu_ns,
            "total_alloc_bytes": self.total_alloc_bytes,
            "top_functions": self.top_functions,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

        if include_data and self.profile_data:
            import base64
            result["profile_data_base64"] = base64.b64encode(self.profile_data).decode()

        return result


class ProfileAggregate(Base):
    """Aggregated profile statistics for time buckets."""

    __tablename__ = "profile_aggregates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)

    # Aggregation key
    service_name = Column(String(255), nullable=False)
    profile_type = Column(String(50), nullable=False)
    environment = Column(String(50), nullable=True)

    # Time bucket (hourly aggregations)
    bucket_start = Column(DateTime(timezone=True), nullable=False, index=True)
    bucket_end = Column(DateTime(timezone=True), nullable=False)

    # Aggregated stats
    profile_count = Column(Integer, nullable=False, default=0)
    total_samples = Column(BigInteger, nullable=True)
    avg_duration_seconds = Column(Float, nullable=True)

    # Top functions aggregated across all profiles in bucket
    top_functions = Column(JSONB, nullable=True)

    # Flame graph diff data (comparison with previous bucket)
    diff_data = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_profile_agg_org_service", "organization_id", "service_name"),
        Index("ix_profile_agg_bucket", "bucket_start", "bucket_end"),
        UniqueConstraint(
            "organization_id", "service_name", "profile_type", "environment", "bucket_start",
            name="uq_profile_aggregate_bucket"
        ),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "service_name": self.service_name,
            "profile_type": self.profile_type,
            "environment": self.environment,
            "bucket_start": self.bucket_start.isoformat() if self.bucket_start else None,
            "bucket_end": self.bucket_end.isoformat() if self.bucket_end else None,
            "profile_count": self.profile_count,
            "total_samples": self.total_samples,
            "avg_duration_seconds": self.avg_duration_seconds,
            "top_functions": self.top_functions,
            "diff_data": self.diff_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
