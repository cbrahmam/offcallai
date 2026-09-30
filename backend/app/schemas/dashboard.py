# backend/app/schemas/dashboard.py
"""
Pydantic schemas for Custom Dashboards API.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from uuid import UUID


class WidgetType(str, Enum):
    LINE_CHART = "line_chart"
    AREA_CHART = "area_chart"
    BAR_CHART = "bar_chart"
    GAUGE = "gauge"
    STAT = "stat"
    TABLE = "table"
    HEATMAP = "heatmap"
    PIE_CHART = "pie_chart"
    LOG_STREAM = "log_stream"
    ALERT_LIST = "alert_list"
    TEXT = "text"
    SERVICE_MAP = "service_map"


class DataSource(str, Enum):
    METRICS = "metrics"
    LOGS = "logs"
    TRACES = "traces"
    ALERTS = "alerts"
    CUSTOM = "custom"


# ============================================
# Widget Schemas
# ============================================

class WidgetQueryConfig(BaseModel):
    """Configuration for widget data query."""
    metrics: Optional[List[str]] = None  # Metric names to query
    hosts: Optional[List[str]] = None  # Host IDs to filter
    services: Optional[List[str]] = None  # Service names to filter
    aggregation: str = "avg"  # avg, sum, min, max, count, p50, p95, p99
    group_by: Optional[str] = None  # null, host, service, metric
    filters: Optional[Dict[str, Any]] = None  # Additional filters
    log_query: Optional[str] = None  # For log widgets
    trace_filters: Optional[Dict[str, Any]] = None  # For trace widgets


class WidgetDisplayConfig(BaseModel):
    """Configuration for widget display."""
    show_legend: bool = True
    stack: bool = False
    fill: float = 0.2
    colors: Optional[List[str]] = None
    unit: str = "auto"  # auto, percent, bytes, ms, requests, custom
    custom_unit: Optional[str] = None
    thresholds: Optional[List[Dict[str, Any]]] = None
    decimal_places: int = 2
    sparkline: bool = False
    show_value: bool = True


class WidgetCreate(BaseModel):
    """Schema for creating a widget."""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    widget_type: WidgetType = WidgetType.LINE_CHART
    position_x: int = Field(0, ge=0)
    position_y: int = Field(0, ge=0)
    width: int = Field(4, ge=1, le=12)
    height: int = Field(3, ge=1, le=8)
    data_source: DataSource = DataSource.METRICS
    query_config: Optional[Dict[str, Any]] = None
    display_config: Optional[Dict[str, Any]] = None
    time_range_override: Optional[str] = None
    display_order: int = 0


class WidgetUpdate(BaseModel):
    """Schema for updating a widget."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    widget_type: Optional[WidgetType] = None
    position_x: Optional[int] = Field(None, ge=0)
    position_y: Optional[int] = Field(None, ge=0)
    width: Optional[int] = Field(None, ge=1, le=12)
    height: Optional[int] = Field(None, ge=1, le=8)
    data_source: Optional[DataSource] = None
    query_config: Optional[Dict[str, Any]] = None
    display_config: Optional[Dict[str, Any]] = None
    time_range_override: Optional[str] = None
    display_order: Optional[int] = None


class WidgetResponse(BaseModel):
    """Schema for widget response."""
    id: str
    dashboard_id: str
    title: str
    description: Optional[str]
    widget_type: str
    position_x: int
    position_y: int
    width: int
    height: int
    data_source: str
    query_config: Dict[str, Any]
    display_config: Dict[str, Any]
    time_range_override: Optional[str]
    display_order: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================
# Dashboard Schemas
# ============================================

class DashboardCreate(BaseModel):
    """Schema for creating a dashboard."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    slug: Optional[str] = Field(None, max_length=100)
    is_shared: bool = True
    layout: str = "grid"
    columns: int = Field(12, ge=6, le=24)
    refresh_interval: int = Field(60, ge=0, le=3600)
    default_time_range: str = "1h"
    theme: str = "dark"
    tags: Optional[List[str]] = None
    widgets: Optional[List[WidgetCreate]] = None


class DashboardUpdate(BaseModel):
    """Schema for updating a dashboard."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    slug: Optional[str] = Field(None, max_length=100)
    is_shared: Optional[bool] = None
    layout: Optional[str] = None
    columns: Optional[int] = Field(None, ge=6, le=24)
    refresh_interval: Optional[int] = Field(None, ge=0, le=3600)
    default_time_range: Optional[str] = None
    theme: Optional[str] = None
    tags: Optional[List[str]] = None


class DashboardResponse(BaseModel):
    """Schema for dashboard response."""
    id: str
    organization_id: str
    name: str
    description: Optional[str]
    slug: Optional[str]
    created_by: Optional[str]
    is_default: bool
    is_shared: bool
    layout: str
    columns: int
    refresh_interval: int
    default_time_range: str
    theme: str
    tags: List[str]
    widgets: List[WidgetResponse]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DashboardListItem(BaseModel):
    """Schema for dashboard list item."""
    id: str
    name: str
    description: Optional[str]
    slug: Optional[str]
    is_default: bool
    is_shared: bool
    widget_count: int
    tags: List[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DashboardListResponse(BaseModel):
    """Response for dashboard list."""
    dashboards: List[DashboardListItem]
    total: int


# ============================================
# Widget Data Schemas
# ============================================

class WidgetDataPoint(BaseModel):
    """Single data point for a widget."""
    timestamp: datetime
    value: float
    label: Optional[str] = None


class WidgetDataSeries(BaseModel):
    """Data series for a widget."""
    name: str
    data: List[WidgetDataPoint]
    color: Optional[str] = None


class WidgetDataResponse(BaseModel):
    """Response for widget data query."""
    widget_id: str
    series: List[WidgetDataSeries]
    time_range: Dict[str, datetime]
    metadata: Optional[Dict[str, Any]] = None


# ============================================
# Template Schemas
# ============================================

class DashboardTemplateCreate(BaseModel):
    """Schema for creating a dashboard template."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: str = "custom"
    template_config: Dict[str, Any]
    thumbnail_url: Optional[str] = None
    is_public: bool = True


class DashboardTemplateResponse(BaseModel):
    """Schema for dashboard template response."""
    id: str
    name: str
    description: Optional[str]
    category: str
    template_config: Dict[str, Any]
    thumbnail_url: Optional[str]
    is_public: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DashboardTemplateListResponse(BaseModel):
    """Response for template list."""
    templates: List[DashboardTemplateResponse]
    total: int


# ============================================
# Import/Export Schemas
# ============================================

class DashboardExport(BaseModel):
    """Export format for a dashboard."""
    version: str = "1.0"
    dashboard: Dict[str, Any]
    widgets: List[Dict[str, Any]]


class DashboardImport(BaseModel):
    """Import format for a dashboard."""
    name: Optional[str] = None  # Override name
    dashboard: Dict[str, Any]
    widgets: List[Dict[str, Any]]
