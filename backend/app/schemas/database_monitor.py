# backend/app/schemas/database_monitor.py
"""
Database monitoring schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


# ============================================
# Enums
# ============================================

class DatabaseTypeEnum(str, Enum):
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


class DatabaseStatusEnum(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNREACHABLE = "unreachable"
    UNKNOWN = "unknown"


class ReplicationRoleEnum(str, Enum):
    PRIMARY = "primary"
    REPLICA = "replica"
    STANDALONE = "standalone"
    ARBITER = "arbiter"


class AlertSeverityEnum(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# ============================================
# Database Instance Schemas
# ============================================

class DatabaseInstanceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = None
    description: Optional[str] = None
    database_type: DatabaseTypeEnum
    hostname: str = Field(..., min_length=1, max_length=255)
    port: int = Field(..., ge=1, le=65535)
    database_name: Optional[str] = None
    username: Optional[str] = None
    replication_role: ReplicationRoleEnum = ReplicationRoleEnum.STANDALONE
    primary_id: Optional[UUID] = None
    host_id: Optional[UUID] = None
    tags: Dict[str, str] = Field(default_factory=dict)
    labels: Dict[str, str] = Field(default_factory=dict)
    monitoring_enabled: bool = True
    collect_query_stats: bool = True
    collect_slow_queries: bool = True
    slow_query_threshold_ms: int = 1000
    alert_on_connection_threshold: float = 80.0
    alert_on_storage_threshold: float = 85.0
    alert_on_replication_lag: float = 30.0


class DatabaseInstanceUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    hostname: Optional[str] = None
    port: Optional[int] = None
    database_name: Optional[str] = None
    username: Optional[str] = None
    replication_role: Optional[ReplicationRoleEnum] = None
    primary_id: Optional[UUID] = None
    host_id: Optional[UUID] = None
    tags: Optional[Dict[str, str]] = None
    labels: Optional[Dict[str, str]] = None
    monitoring_enabled: Optional[bool] = None
    collect_query_stats: Optional[bool] = None
    collect_slow_queries: Optional[bool] = None
    slow_query_threshold_ms: Optional[int] = None
    alert_on_connection_threshold: Optional[float] = None
    alert_on_storage_threshold: Optional[float] = None
    alert_on_replication_lag: Optional[float] = None
    extra_config: Optional[Dict[str, Any]] = None


class DatabaseInstanceResponse(BaseModel):
    id: UUID
    organization_id: UUID
    host_id: Optional[UUID]
    name: str
    display_name: Optional[str]
    description: Optional[str]
    database_type: str
    version: Optional[str]
    hostname: str
    port: int
    database_name: Optional[str]
    status: str
    last_check: Optional[datetime]
    last_successful_check: Optional[datetime]
    connection_status: str
    replication_role: str
    replication_lag_seconds: Optional[float]
    primary_id: Optional[UUID]
    connections_used: Optional[int]
    connections_max: Optional[int]
    connection_utilization: Optional[float]
    storage_used_bytes: Optional[float]
    storage_total_bytes: Optional[float]
    storage_utilization: Optional[float]
    queries_per_second: Optional[float]
    avg_query_time_ms: Optional[float]
    slow_queries_count: Optional[int]
    active_transactions: Optional[int]
    locks_waiting: Optional[int]
    deadlocks_count: Optional[int]
    cache_hit_ratio: Optional[float]
    monitoring_enabled: bool
    collect_query_stats: bool
    collect_slow_queries: bool
    slow_query_threshold_ms: int
    tags: Dict[str, Any]
    labels: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DatabaseInstanceListResponse(BaseModel):
    instances: List[DatabaseInstanceResponse]
    total: int


class DatabaseSummary(BaseModel):
    total_instances: int
    healthy_instances: int
    warning_instances: int
    critical_instances: int
    unreachable_instances: int
    by_type: Dict[str, int]
    total_connections_used: int
    total_connections_max: int
    total_storage_used_bytes: float
    total_storage_bytes: float
    avg_cache_hit_ratio: float
    total_slow_queries: int
    total_active_alerts: int


# ============================================
# Database Query Schemas
# ============================================

class DatabaseQueryResponse(BaseModel):
    id: UUID
    organization_id: UUID
    instance_id: UUID
    query_hash: Optional[str]
    query_normalized: Optional[str]
    query_sample: Optional[str]
    database_name: Optional[str]
    schema_name: Optional[str]
    table_names: List[str]
    call_count: int
    total_time_ms: float
    avg_time_ms: Optional[float]
    min_time_ms: Optional[float]
    max_time_ms: Optional[float]
    avg_rows_returned: Optional[float]
    cache_hit_ratio: Optional[float]
    is_slow: bool
    query_type: Optional[str]
    first_seen: Optional[datetime]
    last_seen: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DatabaseQueryListResponse(BaseModel):
    queries: List[DatabaseQueryResponse]
    total: int


class QueryFilter(BaseModel):
    instance_id: Optional[UUID] = None
    database_name: Optional[str] = None
    query_type: Optional[str] = None
    is_slow: Optional[bool] = None
    min_avg_time_ms: Optional[float] = None
    min_call_count: Optional[int] = None


# ============================================
# Metric Snapshot Schemas
# ============================================

class MetricSnapshotResponse(BaseModel):
    id: UUID
    instance_id: UUID
    timestamp: datetime
    connections_active: Optional[int]
    connections_idle: Optional[int]
    connections_total: Optional[int]
    queries_per_second: Optional[float]
    avg_query_time_ms: Optional[float]
    slow_queries: Optional[int]
    locks_waiting: Optional[int]
    replication_lag_seconds: Optional[float]
    cache_hit_ratio: Optional[float]
    storage_used_bytes: Optional[float]
    storage_free_bytes: Optional[float]
    extra_metrics: Dict[str, Any]

    class Config:
        from_attributes = True


class MetricSnapshotListResponse(BaseModel):
    snapshots: List[MetricSnapshotResponse]
    total: int


# ============================================
# Database Alert Schemas
# ============================================

class DatabaseAlertResponse(BaseModel):
    id: UUID
    organization_id: UUID
    instance_id: UUID
    alert_type: str
    severity: str
    status: str
    title: str
    message: Optional[str]
    metric_name: Optional[str]
    metric_value: Optional[float]
    threshold_value: Optional[float]
    context: Dict[str, Any]
    query_id: Optional[UUID]
    triggered_at: datetime
    acknowledged_at: Optional[datetime]
    acknowledged_by: Optional[UUID]
    resolved_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class DatabaseAlertListResponse(BaseModel):
    alerts: List[DatabaseAlertResponse]
    total: int


class AlertAcknowledge(BaseModel):
    comment: Optional[str] = None


# ============================================
# Data Ingestion Schemas
# ============================================

class ConnectionMetrics(BaseModel):
    active: int = 0
    idle: int = 0
    waiting: int = 0
    total: int = 0
    max_connections: int = 0


class StorageMetrics(BaseModel):
    used_bytes: float = 0
    total_bytes: float = 0
    free_bytes: float = 0


class PerformanceMetrics(BaseModel):
    queries_per_second: float = 0
    transactions_per_second: float = 0
    avg_query_time_ms: float = 0
    slow_queries: int = 0
    active_transactions: int = 0


class ReplicationMetrics(BaseModel):
    lag_seconds: float = 0
    lag_bytes: float = 0
    role: str = "standalone"


class CacheMetrics(BaseModel):
    hit_ratio: float = 0
    buffer_pool_size: float = 0
    buffer_pool_used: float = 0


class LockMetrics(BaseModel):
    locks_held: int = 0
    locks_waiting: int = 0
    deadlocks: int = 0
    lock_wait_time_ms: float = 0


class DatabaseMetricsReport(BaseModel):
    """Metrics report sent by monitoring agent."""
    timestamp: datetime
    version: Optional[str] = None
    connections: Optional[ConnectionMetrics] = None
    storage: Optional[StorageMetrics] = None
    performance: Optional[PerformanceMetrics] = None
    replication: Optional[ReplicationMetrics] = None
    cache: Optional[CacheMetrics] = None
    locks: Optional[LockMetrics] = None
    extra_metrics: Dict[str, Any] = Field(default_factory=dict)


class QueryStats(BaseModel):
    """Query statistics from agent."""
    query_hash: str
    query_normalized: str
    query_sample: Optional[str] = None
    database_name: Optional[str] = None
    schema_name: Optional[str] = None
    table_names: List[str] = Field(default_factory=list)
    call_count: int = 0
    total_time_ms: float = 0
    min_time_ms: float = 0
    max_time_ms: float = 0
    avg_rows_returned: float = 0
    cache_hit_ratio: Optional[float] = None
    query_type: Optional[str] = None


class QueryStatsReport(BaseModel):
    """Query statistics report from agent."""
    timestamp: datetime
    queries: List[QueryStats] = Field(default_factory=list)


class MetricsIngestResponse(BaseModel):
    success: bool
    instance_id: UUID
    metrics_stored: bool
    alerts_generated: int
    errors: List[str] = Field(default_factory=list)


# ============================================
# Health Check Schemas
# ============================================

class DatabaseHealthCheck(BaseModel):
    instance_id: UUID
    status: str
    connection_status: str
    response_time_ms: Optional[float]
    version: Optional[str]
    uptime_seconds: Optional[int]
    is_primary: bool
    replication_lag_seconds: Optional[float]
    error_message: Optional[str]
    checked_at: datetime


class TestConnectionRequest(BaseModel):
    database_type: DatabaseTypeEnum
    hostname: str
    port: int
    database_name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


class TestConnectionResponse(BaseModel):
    success: bool
    message: str
    response_time_ms: Optional[float]
    version: Optional[str]
    error: Optional[str]
