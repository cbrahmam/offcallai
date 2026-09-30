# backend/app/models/dashboard.py
"""
Custom Dashboard models for user-configurable monitoring dashboards.
"""

from sqlalchemy import Column, String, Text, DateTime, Integer, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
import enum
from app.database import Base


class WidgetType(str, enum.Enum):
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


class Dashboard(Base):
    """
    Custom dashboard container.
    """
    __tablename__ = "dashboards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Dashboard metadata
    name = Column(String(255), nullable=False)
    description = Column(Text)
    slug = Column(String(100), index=True)  # URL-friendly name

    # Ownership and sharing
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    is_default = Column(String(10), default="false")  # Whether this is a default dashboard
    is_shared = Column(String(10), default="true")  # Whether it's visible to all org members

    # Layout settings
    layout = Column(String(20), default="grid")  # grid, free
    columns = Column(Integer, default=12)  # Grid columns for responsive layout
    refresh_interval = Column(Integer, default=60)  # Auto-refresh in seconds, 0 = disabled

    # Time range settings
    default_time_range = Column(String(20), default="1h")  # 15m, 1h, 6h, 24h, 7d, 30d, custom
    default_start_time = Column(DateTime(timezone=True))
    default_end_time = Column(DateTime(timezone=True))

    # Visual settings
    theme = Column(String(20), default="dark")
    tags = Column(JSONB, default=list)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    widgets = relationship("DashboardWidget", back_populates="dashboard", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_dashboards_org_slug', 'organization_id', 'slug', unique=True),
    )

    def __repr__(self):
        return f"<Dashboard(name='{self.name}', slug='{self.slug}')>"


class DashboardWidget(Base):
    """
    Individual widget within a dashboard.
    """
    __tablename__ = "dashboard_widgets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dashboard_id = Column(UUID(as_uuid=True), ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Widget metadata
    title = Column(String(255), nullable=False)
    description = Column(Text)
    widget_type = Column(String(30), nullable=False, default="line_chart")

    # Position in grid (x, y, width, height)
    position_x = Column(Integer, default=0)
    position_y = Column(Integer, default=0)
    width = Column(Integer, default=4)  # Grid units
    height = Column(Integer, default=3)  # Grid units

    # Data source configuration
    data_source = Column(String(50), nullable=False, default="metrics")  # metrics, logs, traces, alerts, custom

    # Query configuration
    query_config = Column(JSONB, default=dict)  # Metric names, filters, aggregations, etc.
    # Example query_config:
    # {
    #   "metrics": ["cpu.usage", "memory.used_percent"],
    #   "hosts": ["host-id-1", "host-id-2"],  # null = all hosts
    #   "services": ["api-gateway"],  # null = all services
    #   "aggregation": "avg",  # avg, sum, min, max, count, p50, p95, p99
    #   "group_by": "host",  # null, host, service
    #   "filters": {"key": "value"}
    # }

    # Display configuration
    display_config = Column(JSONB, default=dict)
    # Example display_config:
    # {
    #   "show_legend": true,
    #   "stack": false,
    #   "fill": 0.2,
    #   "colors": ["#3B82F6", "#10B981"],
    #   "unit": "percent",  # percent, bytes, ms, requests, custom
    #   "thresholds": [{"value": 80, "color": "yellow"}, {"value": 90, "color": "red"}],
    #   "decimal_places": 2
    # }

    # Thresholds for alerting/coloring
    thresholds = Column(JSONB, default=list)

    # Override dashboard time range
    time_range_override = Column(String(20))  # null = use dashboard default

    # Order for rendering
    display_order = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    dashboard = relationship("Dashboard", back_populates="widgets")

    __table_args__ = (
        Index('ix_dashboard_widgets_dashboard_order', 'dashboard_id', 'display_order'),
    )

    def __repr__(self):
        return f"<DashboardWidget(title='{self.title}', type='{self.widget_type}')>"


class DashboardTemplate(Base):
    """
    Pre-built dashboard templates that users can import.
    """
    __tablename__ = "dashboard_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Template metadata
    name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(50), index=True)  # infrastructure, apm, logs, security, custom

    # Template content
    template_config = Column(JSONB, nullable=False)  # Full dashboard + widgets config

    # Preview
    thumbnail_url = Column(String(500))

    # Visibility
    is_public = Column(String(10), default="true")  # Available to all orgs
    created_by_org = Column(UUID(as_uuid=True))  # Org that created it (null = system template)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<DashboardTemplate(name='{self.name}', category='{self.category}')>"
