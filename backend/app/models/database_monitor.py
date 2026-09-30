# backend/app/models/database_monitor.py
"""
Database monitoring models.
"""

import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, Float, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class DatabaseType(str, Enum):
    """Supported database types."""
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    REDIS = "redis"
    ELASTICSEARCH = "elasticsearch"
    MARIADB = "mariadb"
    SQLSERVER = "sqlserver"
    ORACLE = "oracle"
    CASSANDRA = "cassandra"
    DYNAMODB = "dynamodb"


class DatabaseStatus(str, Enum):
    """Database health status."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNREACHABLE = "unreachable"
    UNKNOWN = "unknown"


class ReplicationRole(str, Enum):
    """Replication role."""
    PRIMARY = "primary"
    REPLICA = "replica"
    STANDALONE = "standalone"
    ARBITER = "arbiter"


class DatabaseInstance(Base):
    """Database instance being monitored."""
    __tablename__ = "database_instances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    host_id = Column(UUID(as_uuid=True), ForeignKey("hosts.id", ondelete="SET NULL"))

    # Database info
    name = Column(String(255), nullable=False)
    display_name = Column(String(255))
    description = Column(Text)
    database_type = Column(String(50), nullable=False, index=True)  # postgresql, mysql, mongodb, redis, etc.
    version = Column(String(50))

    # Connection details (encrypted in production)
    hostname = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    database_name = Column(String(255))  # Default database/schema
    username = Column(String(255))

    # Status
    status = Column(String(20), default="unknown", index=True)
    last_check = Column(DateTime(timezone=True))
    last_successful_check = Column(DateTime(timezone=True))
    connection_status = Column(String(20), default="unknown")  # connected, disconnected, error

    # Replication
    replication_role = Column(String(20), default="standalone")  # primary, replica, standalone
    replication_lag_seconds = Column(Float)
    primary_id = Column(UUID(as_uuid=True), ForeignKey("database_instances.id", ondelete="SET NULL"))

    # Resource usage
    connections_used = Column(Integer)
    connections_max = Column(Integer)
    connection_utilization = Column(Float)  # percentage

    # Storage
    storage_used_bytes = Column(Float)
    storage_total_bytes = Column(Float)
    storage_utilization = Column(Float)

    # Performance metrics (recent)
    queries_per_second = Column(Float)
    avg_query_time_ms = Column(Float)
    slow_queries_count = Column(Integer)
    active_transactions = Column(Integer)
    locks_waiting = Column(Integer)
    deadlocks_count = Column(Integer)

    # Cache stats (if applicable)
    cache_hit_ratio = Column(Float)
    buffer_pool_size = Column(Float)
    buffer_pool_used = Column(Float)

    # Settings
    monitoring_enabled = Column(String(10), default="true")
    collect_query_stats = Column(String(10), default="true")
    collect_slow_queries = Column(String(10), default="true")
    slow_query_threshold_ms = Column(Integer, default=1000)
    alert_on_connection_threshold = Column(Float, default=80.0)
    alert_on_storage_threshold = Column(Float, default=85.0)
    alert_on_replication_lag = Column(Float, default=30.0)

    # Tags and metadata
    tags = Column(JSONB, default=dict)
    labels = Column(JSONB, default=dict)
    extra_config = Column(JSONB, default=dict)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    queries = relationship("DatabaseQuery", back_populates="instance", cascade="all, delete-orphan")
    metrics_history = relationship("DatabaseMetricSnapshot", back_populates="instance", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_db_instance_org_type', 'organization_id', 'database_type'),
    )


class DatabaseQuery(Base):
    """Captured database queries for analysis."""
    __tablename__ = "database_queries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    instance_id = Column(UUID(as_uuid=True), ForeignKey("database_instances.id", ondelete="CASCADE"), nullable=False, index=True)

    # Query info
    query_hash = Column(String(64), index=True)  # Hash of normalized query
    query_normalized = Column(Text)  # Query with parameters replaced
    query_sample = Column(Text)  # Example with actual parameters (may be truncated)

    # Database info
    database_name = Column(String(255))
    schema_name = Column(String(255))
    table_names = Column(JSONB, default=list)  # Tables involved

    # Execution stats (aggregated)
    call_count = Column(Integer, default=0)
    total_time_ms = Column(Float, default=0)
    avg_time_ms = Column(Float)
    min_time_ms = Column(Float)
    max_time_ms = Column(Float)
    stddev_time_ms = Column(Float)

    # Row stats
    total_rows_returned = Column(Integer, default=0)
    avg_rows_returned = Column(Float)
    total_rows_affected = Column(Integer, default=0)

    # I/O stats
    total_shared_blks_hit = Column(Integer, default=0)
    total_shared_blks_read = Column(Integer, default=0)
    cache_hit_ratio = Column(Float)

    # Wait stats
    total_wait_time_ms = Column(Float)
    wait_events = Column(JSONB, default=dict)

    # Query plan (if captured)
    query_plan = Column(JSONB)
    plan_cost = Column(Float)

    # Time window
    first_seen = Column(DateTime(timezone=True))
    last_seen = Column(DateTime(timezone=True), index=True)

    # Classification
    is_slow = Column(String(10), default="false")
    query_type = Column(String(20))  # SELECT, INSERT, UPDATE, DELETE, etc.

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    instance = relationship("DatabaseInstance", back_populates="queries")

    __table_args__ = (
        Index('ix_db_query_instance_hash', 'instance_id', 'query_hash'),
        Index('ix_db_query_slow', 'organization_id', 'is_slow'),
    )


class DatabaseMetricSnapshot(Base):
    """Time-series metrics snapshots for database instances."""
    __tablename__ = "database_metric_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    instance_id = Column(UUID(as_uuid=True), ForeignKey("database_instances.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    # Connection metrics
    connections_active = Column(Integer)
    connections_idle = Column(Integer)
    connections_waiting = Column(Integer)
    connections_total = Column(Integer)

    # Query metrics
    queries_per_second = Column(Float)
    transactions_per_second = Column(Float)
    avg_query_time_ms = Column(Float)
    slow_queries = Column(Integer)

    # Lock metrics
    locks_held = Column(Integer)
    locks_waiting = Column(Integer)
    deadlocks = Column(Integer)
    lock_wait_time_ms = Column(Float)

    # Replication metrics
    replication_lag_seconds = Column(Float)
    replication_lag_bytes = Column(Float)

    # Buffer/Cache metrics
    cache_hit_ratio = Column(Float)
    buffer_pool_reads = Column(Integer)
    buffer_pool_writes = Column(Integer)

    # I/O metrics
    disk_read_bytes = Column(Float)
    disk_write_bytes = Column(Float)
    disk_read_time_ms = Column(Float)
    disk_write_time_ms = Column(Float)

    # Storage metrics
    storage_used_bytes = Column(Float)
    storage_free_bytes = Column(Float)

    # Table stats
    tables_count = Column(Integer)
    indexes_count = Column(Integer)
    table_bloat_bytes = Column(Float)
    index_bloat_bytes = Column(Float)

    # Checkpoint/WAL metrics (PostgreSQL specific)
    checkpoints_timed = Column(Integer)
    checkpoints_requested = Column(Integer)
    wal_bytes_written = Column(Float)

    # Additional metrics stored as JSON
    extra_metrics = Column(JSONB, default=dict)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    instance = relationship("DatabaseInstance", back_populates="metrics_history")

    __table_args__ = (
        Index('ix_db_metric_instance_time', 'instance_id', 'timestamp'),
    )


class DatabaseAlert(Base):
    """Database-specific alerts."""
    __tablename__ = "database_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    instance_id = Column(UUID(as_uuid=True), ForeignKey("database_instances.id", ondelete="CASCADE"), nullable=False, index=True)

    # Alert info
    alert_type = Column(String(50), nullable=False, index=True)  # connection_high, storage_full, replication_lag, slow_query, deadlock, etc.
    severity = Column(String(20), default="warning", index=True)
    status = Column(String(20), default="active", index=True)  # active, acknowledged, resolved

    # Alert details
    title = Column(String(255), nullable=False)
    message = Column(Text)
    metric_name = Column(String(100))
    metric_value = Column(Float)
    threshold_value = Column(Float)

    # Context
    context = Column(JSONB, default=dict)  # Additional context data

    # Query reference (for slow query alerts)
    query_id = Column(UUID(as_uuid=True), ForeignKey("database_queries.id", ondelete="SET NULL"))

    # Times
    triggered_at = Column(DateTime(timezone=True), nullable=False, index=True)
    acknowledged_at = Column(DateTime(timezone=True))
    acknowledged_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index('ix_db_alert_instance_status', 'instance_id', 'status'),
        Index('ix_db_alert_org_triggered', 'organization_id', 'triggered_at'),
    )
