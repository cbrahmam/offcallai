# backend/app/schemas/metrics.py - Metrics Schemas for Time-Series Data
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, validator
from enum import Enum


# ============================================
# Metric Types & Enums
# ============================================

class MetricType(str, Enum):
    """Standard metric types collected by agent."""
    # CPU Metrics
    CPU_USAGE = "system.cpu.usage"
    CPU_USER = "system.cpu.user"
    CPU_SYSTEM = "system.cpu.system"
    CPU_IDLE = "system.cpu.idle"
    CPU_IOWAIT = "system.cpu.iowait"
    LOAD_1M = "system.load.1"
    LOAD_5M = "system.load.5"
    LOAD_15M = "system.load.15"

    # Memory Metrics
    MEMORY_USED = "system.memory.used"
    MEMORY_FREE = "system.memory.free"
    MEMORY_CACHED = "system.memory.cached"
    MEMORY_BUFFERS = "system.memory.buffers"
    MEMORY_USAGE_PERCENT = "system.memory.usage_percent"
    SWAP_USED = "system.swap.used"
    SWAP_FREE = "system.swap.free"

    # Disk Metrics
    DISK_USED = "system.disk.used"
    DISK_FREE = "system.disk.free"
    DISK_USAGE_PERCENT = "system.disk.usage_percent"
    DISK_READ_BYTES = "system.disk.read_bytes"
    DISK_WRITE_BYTES = "system.disk.write_bytes"
    DISK_READ_OPS = "system.disk.read_ops"
    DISK_WRITE_OPS = "system.disk.write_ops"

    # Network Metrics
    NETWORK_BYTES_IN = "system.network.bytes_in"
    NETWORK_BYTES_OUT = "system.network.bytes_out"
    NETWORK_PACKETS_IN = "system.network.packets_in"
    NETWORK_PACKETS_OUT = "system.network.packets_out"
    NETWORK_ERRORS_IN = "system.network.errors_in"
    NETWORK_ERRORS_OUT = "system.network.errors_out"

    # Process Metrics
    PROCESS_COUNT = "system.process.count"
    PROCESS_RUNNING = "system.process.running"
    PROCESS_BLOCKED = "system.process.blocked"

    # Container Metrics
    CONTAINER_COUNT = "container.count"
    CONTAINER_CPU = "container.cpu.usage"
    CONTAINER_MEMORY = "container.memory.usage"

    # Custom/Application Metrics
    CUSTOM = "custom"


class AggregationType(str, Enum):
    """How to aggregate metrics over time."""
    AVG = "avg"
    SUM = "sum"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    LAST = "last"
    RATE = "rate"  # Per-second rate


# ============================================
# Metric Ingestion (from Agent)
# ============================================

class MetricPoint(BaseModel):
    """Single metric data point."""
    name: str = Field(..., min_length=1, max_length=255, description="Metric name, e.g., 'system.cpu.usage'")
    value: float = Field(..., description="Metric value")
    timestamp: Optional[datetime] = Field(None, description="When metric was collected. Defaults to server time.")
    tags: Optional[Dict[str, str]] = Field(default_factory=dict, description="Additional tags for this metric")
    unit: Optional[str] = Field(None, max_length=20, description="Unit of measurement, e.g., 'percent', 'bytes'")

    @validator('name', pre=True)
    def normalize_metric_name(cls, v):
        if v:
            return v.strip().lower().replace(' ', '_')
        return v


class MetricBatch(BaseModel):
    """Batch of metrics sent by agent."""
    host_id: Optional[str] = Field(None, description="Host UUID if known")
    agent_id: str = Field(..., min_length=1, max_length=100, description="Agent identifier for host lookup")
    metrics: List[MetricPoint] = Field(..., min_length=1, max_length=1000, description="Metric data points")
    agent_version: Optional[str] = Field(None, max_length=20)
    collected_at: Optional[datetime] = Field(None, description="When batch was collected")

    @validator('metrics')
    def validate_metrics_not_empty(cls, v):
        if not v:
            raise ValueError('At least one metric is required')
        return v


class MetricIngestResponse(BaseModel):
    """Response after ingesting metrics."""
    success: bool
    metrics_received: Optional[int] = None
    points_received: Optional[int] = None
    points_stored: Optional[int] = None
    host_id: Optional[str] = None
    message: Optional[str] = None
    errors: List[str] = Field(default_factory=list)


# ============================================
# Metric Queries
# ============================================

class MetricQuery(BaseModel):
    """Query parameters for fetching metrics."""
    metric_name: str = Field(..., description="Metric name to query")
    host_ids: Optional[List[str]] = Field(None, description="Filter by specific hosts")
    tags: Optional[Dict[str, str]] = Field(None, description="Filter by tags")
    start_time: datetime = Field(..., description="Query start time")
    end_time: datetime = Field(..., description="Query end time")
    aggregation: AggregationType = Field(AggregationType.AVG, description="How to aggregate values")
    interval: Optional[str] = Field(None, description="Bucket interval, e.g., '1m', '5m', '1h'")
    group_by: Optional[List[str]] = Field(None, description="Group by tag keys")

    @validator('end_time')
    def validate_time_range(cls, v, values):
        if 'start_time' in values and v < values['start_time']:
            raise ValueError('end_time must be after start_time')
        return v


class MetricDataPoint(BaseModel):
    """Single point in query results."""
    timestamp: datetime
    value: float
    tags: Optional[Dict[str, str]] = None


class MetricSeries(BaseModel):
    """Time series data for a metric."""
    metric_name: str
    host_id: Optional[str] = None
    hostname: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict)
    data: List[MetricDataPoint]
    unit: Optional[str] = None


class MetricQueryResponse(BaseModel):
    """Response for metric queries."""
    series: List[MetricSeries]
    query: MetricQuery
    total_points: int


# ============================================
# Real-time / Latest Metrics
# ============================================

class LatestMetricRequest(BaseModel):
    """Request latest values for specific metrics."""
    metric_names: List[str] = Field(..., min_length=1, max_length=50)
    host_ids: Optional[List[str]] = None


class LatestMetricValue(BaseModel):
    """Latest value for a metric on a host."""
    metric_name: str
    host_id: str
    hostname: str
    value: float
    timestamp: datetime
    unit: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict)


class LatestMetricsResponse(BaseModel):
    """Response with latest metric values."""
    metrics: List[LatestMetricValue]


# ============================================
# Metric Metadata
# ============================================

class MetricDefinition(BaseModel):
    """Metadata about a metric type."""
    name: str
    display_name: str
    description: str
    unit: str
    category: str  # cpu, memory, disk, network, container, custom
    aggregation_default: AggregationType = AggregationType.AVG


class MetricCatalogResponse(BaseModel):
    """List of available metrics and their definitions."""
    metrics: List[MetricDefinition]


# ============================================
# Metric Alerts (Threshold-based)
# ============================================

class MetricAlertRuleCreate(BaseModel):
    """Create a threshold-based alert rule."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    metric_name: str = Field(..., description="Metric to monitor")

    # Threshold configuration
    operator: str = Field(..., description="Comparison operator: >, <, >=, <=, ==, !=")
    threshold: float = Field(..., description="Threshold value")
    duration_seconds: int = Field(60, ge=10, description="How long condition must be true")

    # Scope
    host_ids: Optional[List[str]] = Field(None, description="Specific hosts to monitor")
    tags: Optional[Dict[str, str]] = Field(None, description="Filter hosts by tags")

    # Notification
    severity: str = Field("medium", description="Alert severity: low, medium, high, critical")
    notify_channels: List[str] = Field(default_factory=list, description="Notification channels")

    is_enabled: bool = Field(True)

    @validator('operator')
    def validate_operator(cls, v):
        valid = ['>', '<', '>=', '<=', '==', '!=']
        if v not in valid:
            raise ValueError(f'Operator must be one of: {valid}')
        return v


class MetricAlertRuleResponse(BaseModel):
    """Alert rule details."""
    id: str
    name: str
    description: Optional[str] = None
    metric_name: str
    operator: str
    threshold: float
    duration_seconds: int
    host_ids: Optional[List[str]] = None
    tags: Optional[Dict[str, str]] = None
    severity: str
    notify_channels: List[str] = Field(default_factory=list)
    is_enabled: bool
    last_triggered_at: Optional[datetime] = None
    last_evaluated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================
# Dashboard Widgets (for metrics display)
# ============================================

class WidgetQuery(BaseModel):
    """Query configuration for a dashboard widget."""
    metric_name: str
    aggregation: AggregationType = AggregationType.AVG
    host_ids: Optional[List[str]] = None
    tags: Optional[Dict[str, str]] = None
    alias: Optional[str] = None  # Display name for legend


class WidgetConfig(BaseModel):
    """Dashboard widget configuration."""
    widget_type: str = Field(..., description="line_chart, bar_chart, gauge, stat, table")
    title: str
    queries: List[WidgetQuery]

    # Display settings
    unit: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    thresholds: Optional[List[Dict[str, Any]]] = None  # For gauge coloring

    # Time range (relative to dashboard time range)
    time_range: Optional[str] = None  # Override dashboard time range


# ============================================
# Standard Metric Catalog
# ============================================

STANDARD_METRICS: List[MetricDefinition] = [
    # CPU
    MetricDefinition(name="system.cpu.usage", display_name="CPU Usage", description="Total CPU utilization percentage", unit="percent", category="cpu"),
    MetricDefinition(name="system.cpu.user", display_name="CPU User", description="CPU time in user mode", unit="percent", category="cpu"),
    MetricDefinition(name="system.cpu.system", display_name="CPU System", description="CPU time in kernel mode", unit="percent", category="cpu"),
    MetricDefinition(name="system.load.1", display_name="Load 1m", description="1-minute load average", unit="", category="cpu"),
    MetricDefinition(name="system.load.5", display_name="Load 5m", description="5-minute load average", unit="", category="cpu"),
    MetricDefinition(name="system.load.15", display_name="Load 15m", description="15-minute load average", unit="", category="cpu"),

    # Memory
    MetricDefinition(name="system.memory.used", display_name="Memory Used", description="Used memory in bytes", unit="bytes", category="memory"),
    MetricDefinition(name="system.memory.free", display_name="Memory Free", description="Free memory in bytes", unit="bytes", category="memory"),
    MetricDefinition(name="system.memory.usage_percent", display_name="Memory Usage %", description="Memory utilization percentage", unit="percent", category="memory"),
    MetricDefinition(name="system.swap.used", display_name="Swap Used", description="Used swap space in bytes", unit="bytes", category="memory"),

    # Disk
    MetricDefinition(name="system.disk.used", display_name="Disk Used", description="Used disk space in bytes", unit="bytes", category="disk"),
    MetricDefinition(name="system.disk.free", display_name="Disk Free", description="Free disk space in bytes", unit="bytes", category="disk"),
    MetricDefinition(name="system.disk.usage_percent", display_name="Disk Usage %", description="Disk utilization percentage", unit="percent", category="disk"),
    MetricDefinition(name="system.disk.read_bytes", display_name="Disk Read", description="Bytes read from disk", unit="bytes/s", category="disk", aggregation_default=AggregationType.RATE),
    MetricDefinition(name="system.disk.write_bytes", display_name="Disk Write", description="Bytes written to disk", unit="bytes/s", category="disk", aggregation_default=AggregationType.RATE),

    # Network
    MetricDefinition(name="system.network.bytes_in", display_name="Network In", description="Bytes received", unit="bytes/s", category="network", aggregation_default=AggregationType.RATE),
    MetricDefinition(name="system.network.bytes_out", display_name="Network Out", description="Bytes sent", unit="bytes/s", category="network", aggregation_default=AggregationType.RATE),
    MetricDefinition(name="system.network.packets_in", display_name="Packets In", description="Packets received", unit="packets/s", category="network", aggregation_default=AggregationType.RATE),
    MetricDefinition(name="system.network.packets_out", display_name="Packets Out", description="Packets sent", unit="packets/s", category="network", aggregation_default=AggregationType.RATE),

    # Process
    MetricDefinition(name="system.process.count", display_name="Process Count", description="Total number of processes", unit="", category="process"),
    MetricDefinition(name="system.process.running", display_name="Running Processes", description="Number of running processes", unit="", category="process"),

    # Container
    MetricDefinition(name="container.count", display_name="Container Count", description="Number of containers", unit="", category="container"),
    MetricDefinition(name="container.cpu.usage", display_name="Container CPU", description="Container CPU usage", unit="percent", category="container"),
    MetricDefinition(name="container.memory.usage", display_name="Container Memory", description="Container memory usage", unit="bytes", category="container"),
]
