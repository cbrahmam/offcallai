# backend/app/services/dashboard_service.py
"""
Service for managing custom dashboards.
"""

import uuid
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from sqlalchemy import select, func, and_, desc, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.dashboard import Dashboard, DashboardWidget, DashboardTemplate
from app.schemas.dashboard import (
    DashboardCreate, DashboardUpdate, DashboardResponse, DashboardListItem, DashboardListResponse,
    WidgetCreate, WidgetUpdate, WidgetResponse,
    WidgetDataResponse, WidgetDataSeries, WidgetDataPoint,
    DashboardTemplateCreate, DashboardTemplateResponse, DashboardTemplateListResponse,
    DashboardExport
)

logger = logging.getLogger(__name__)


class DashboardService:
    """Service for dashboard operations."""

    # ============================================
    # Dashboard CRUD
    # ============================================

    async def create_dashboard(
        self,
        data: DashboardCreate,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        db: AsyncSession
    ) -> DashboardResponse:
        """Create a new dashboard."""
        # Generate slug if not provided
        slug = data.slug or self._generate_slug(data.name)

        # Check slug uniqueness
        existing = await db.execute(
            select(Dashboard).where(
                Dashboard.organization_id == organization_id,
                Dashboard.slug == slug
            )
        )
        if existing.scalar_one_or_none():
            slug = f"{slug}-{str(uuid.uuid4())[:8]}"

        dashboard = Dashboard(
            organization_id=organization_id,
            name=data.name,
            description=data.description,
            slug=slug,
            created_by=user_id,
            is_shared="true" if data.is_shared else "false",
            layout=data.layout,
            columns=data.columns,
            refresh_interval=data.refresh_interval,
            default_time_range=data.default_time_range,
            theme=data.theme,
            tags=data.tags or []
        )
        db.add(dashboard)
        await db.flush()

        # Create widgets if provided
        if data.widgets:
            for widget_data in data.widgets:
                widget = DashboardWidget(
                    dashboard_id=dashboard.id,
                    organization_id=organization_id,
                    title=widget_data.title,
                    description=widget_data.description,
                    widget_type=widget_data.widget_type.value,
                    position_x=widget_data.position_x,
                    position_y=widget_data.position_y,
                    width=widget_data.width,
                    height=widget_data.height,
                    data_source=widget_data.data_source.value,
                    query_config=widget_data.query_config or {},
                    display_config=widget_data.display_config or {},
                    time_range_override=widget_data.time_range_override,
                    display_order=widget_data.display_order
                )
                db.add(widget)

        await db.commit()
        await db.refresh(dashboard)

        return await self.get_dashboard(dashboard.id, organization_id, db)

    async def get_dashboard(
        self,
        dashboard_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[DashboardResponse]:
        """Get a dashboard by ID."""
        result = await db.execute(
            select(Dashboard)
            .options(selectinload(Dashboard.widgets))
            .where(
                Dashboard.id == dashboard_id,
                Dashboard.organization_id == organization_id
            )
        )
        dashboard = result.scalar_one_or_none()

        if not dashboard:
            return None

        return self._dashboard_to_response(dashboard)

    async def get_dashboard_by_slug(
        self,
        slug: str,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[DashboardResponse]:
        """Get a dashboard by slug."""
        result = await db.execute(
            select(Dashboard)
            .options(selectinload(Dashboard.widgets))
            .where(
                Dashboard.slug == slug,
                Dashboard.organization_id == organization_id
            )
        )
        dashboard = result.scalar_one_or_none()

        if not dashboard:
            return None

        return self._dashboard_to_response(dashboard)

    async def list_dashboards(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession,
        limit: int = 50,
        offset: int = 0
    ) -> DashboardListResponse:
        """List all dashboards for an organization."""
        # Count total
        count_result = await db.execute(
            select(func.count()).select_from(Dashboard).where(
                Dashboard.organization_id == organization_id
            )
        )
        total = count_result.scalar()

        # Get dashboards
        result = await db.execute(
            select(Dashboard)
            .options(selectinload(Dashboard.widgets))
            .where(Dashboard.organization_id == organization_id)
            .order_by(desc(Dashboard.updated_at))
            .offset(offset)
            .limit(limit)
        )
        dashboards = result.scalars().all()

        return DashboardListResponse(
            dashboards=[
                DashboardListItem(
                    id=str(d.id),
                    name=d.name,
                    description=d.description,
                    slug=d.slug,
                    is_default=d.is_default == "true",
                    is_shared=d.is_shared == "true",
                    widget_count=len(d.widgets),
                    tags=d.tags or [],
                    created_at=d.created_at,
                    updated_at=d.updated_at
                )
                for d in dashboards
            ],
            total=total
        )

    async def update_dashboard(
        self,
        dashboard_id: uuid.UUID,
        data: DashboardUpdate,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[DashboardResponse]:
        """Update a dashboard."""
        result = await db.execute(
            select(Dashboard).where(
                Dashboard.id == dashboard_id,
                Dashboard.organization_id == organization_id
            )
        )
        dashboard = result.scalar_one_or_none()

        if not dashboard:
            return None

        # Update fields
        if data.name is not None:
            dashboard.name = data.name
        if data.description is not None:
            dashboard.description = data.description
        if data.slug is not None:
            dashboard.slug = data.slug
        if data.is_shared is not None:
            dashboard.is_shared = "true" if data.is_shared else "false"
        if data.layout is not None:
            dashboard.layout = data.layout
        if data.columns is not None:
            dashboard.columns = data.columns
        if data.refresh_interval is not None:
            dashboard.refresh_interval = data.refresh_interval
        if data.default_time_range is not None:
            dashboard.default_time_range = data.default_time_range
        if data.theme is not None:
            dashboard.theme = data.theme
        if data.tags is not None:
            dashboard.tags = data.tags

        await db.commit()
        return await self.get_dashboard(dashboard_id, organization_id, db)

    async def delete_dashboard(
        self,
        dashboard_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> bool:
        """Delete a dashboard."""
        result = await db.execute(
            select(Dashboard).where(
                Dashboard.id == dashboard_id,
                Dashboard.organization_id == organization_id
            )
        )
        dashboard = result.scalar_one_or_none()

        if not dashboard:
            return False

        await db.delete(dashboard)
        await db.commit()
        return True

    # ============================================
    # Widget CRUD
    # ============================================

    async def add_widget(
        self,
        dashboard_id: uuid.UUID,
        data: WidgetCreate,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[WidgetResponse]:
        """Add a widget to a dashboard."""
        # Verify dashboard exists
        result = await db.execute(
            select(Dashboard).where(
                Dashboard.id == dashboard_id,
                Dashboard.organization_id == organization_id
            )
        )
        if not result.scalar_one_or_none():
            return None

        widget = DashboardWidget(
            dashboard_id=dashboard_id,
            organization_id=organization_id,
            title=data.title,
            description=data.description,
            widget_type=data.widget_type.value,
            position_x=data.position_x,
            position_y=data.position_y,
            width=data.width,
            height=data.height,
            data_source=data.data_source.value,
            query_config=data.query_config or {},
            display_config=data.display_config or {},
            time_range_override=data.time_range_override,
            display_order=data.display_order
        )
        db.add(widget)
        await db.commit()
        await db.refresh(widget)

        return self._widget_to_response(widget)

    async def update_widget(
        self,
        widget_id: uuid.UUID,
        data: WidgetUpdate,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[WidgetResponse]:
        """Update a widget."""
        result = await db.execute(
            select(DashboardWidget).where(
                DashboardWidget.id == widget_id,
                DashboardWidget.organization_id == organization_id
            )
        )
        widget = result.scalar_one_or_none()

        if not widget:
            return None

        # Update fields
        if data.title is not None:
            widget.title = data.title
        if data.description is not None:
            widget.description = data.description
        if data.widget_type is not None:
            widget.widget_type = data.widget_type.value
        if data.position_x is not None:
            widget.position_x = data.position_x
        if data.position_y is not None:
            widget.position_y = data.position_y
        if data.width is not None:
            widget.width = data.width
        if data.height is not None:
            widget.height = data.height
        if data.data_source is not None:
            widget.data_source = data.data_source.value
        if data.query_config is not None:
            widget.query_config = data.query_config
        if data.display_config is not None:
            widget.display_config = data.display_config
        if data.time_range_override is not None:
            widget.time_range_override = data.time_range_override
        if data.display_order is not None:
            widget.display_order = data.display_order

        await db.commit()
        await db.refresh(widget)

        return self._widget_to_response(widget)

    async def delete_widget(
        self,
        widget_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> bool:
        """Delete a widget."""
        result = await db.execute(
            select(DashboardWidget).where(
                DashboardWidget.id == widget_id,
                DashboardWidget.organization_id == organization_id
            )
        )
        widget = result.scalar_one_or_none()

        if not widget:
            return False

        await db.delete(widget)
        await db.commit()
        return True

    async def update_widget_positions(
        self,
        dashboard_id: uuid.UUID,
        positions: List[Dict[str, Any]],
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> bool:
        """Update positions for multiple widgets."""
        for pos in positions:
            result = await db.execute(
                select(DashboardWidget).where(
                    DashboardWidget.id == uuid.UUID(pos["widget_id"]),
                    DashboardWidget.dashboard_id == dashboard_id,
                    DashboardWidget.organization_id == organization_id
                )
            )
            widget = result.scalar_one_or_none()
            if widget:
                widget.position_x = pos.get("x", widget.position_x)
                widget.position_y = pos.get("y", widget.position_y)
                widget.width = pos.get("width", widget.width)
                widget.height = pos.get("height", widget.height)

        await db.commit()
        return True

    # ============================================
    # Widget Data Queries
    # ============================================

    async def get_widget_data(
        self,
        widget_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Optional[WidgetDataResponse]:
        """Get data for a widget based on its query configuration."""
        result = await db.execute(
            select(DashboardWidget).where(
                DashboardWidget.id == widget_id,
                DashboardWidget.organization_id == organization_id
            )
        )
        widget = result.scalar_one_or_none()

        if not widget:
            return None

        # Default time range
        if not end_time:
            end_time = datetime.utcnow()
        if not start_time:
            # Parse time range from widget or default to 1h
            time_range = widget.time_range_override or "1h"
            hours = self._parse_time_range(time_range)
            start_time = end_time - timedelta(hours=hours)

        # Fetch data based on data source
        series = []
        if widget.data_source == "metrics":
            series = await self._fetch_metric_data(
                widget.query_config, organization_id, start_time, end_time, db
            )
        elif widget.data_source == "logs":
            series = await self._fetch_log_data(
                widget.query_config, organization_id, start_time, end_time, db
            )
        elif widget.data_source == "traces":
            series = await self._fetch_trace_data(
                widget.query_config, organization_id, start_time, end_time, db
            )
        elif widget.data_source == "alerts":
            series = await self._fetch_alert_data(
                widget.query_config, organization_id, start_time, end_time, db
            )

        return WidgetDataResponse(
            widget_id=str(widget_id),
            series=series,
            time_range={"start": start_time, "end": end_time}
        )

    async def _fetch_metric_data(
        self,
        query_config: Dict[str, Any],
        organization_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
        db: AsyncSession
    ) -> List[WidgetDataSeries]:
        """Fetch metric data for a widget."""
        metrics = query_config.get("metrics", ["cpu.usage"])
        hosts = query_config.get("hosts")
        aggregation = query_config.get("aggregation", "avg")
        group_by = query_config.get("group_by")

        series = []

        for metric_name in metrics:
            # Build query
            query = """
                SELECT
                    DATE_TRUNC('minute', timestamp) as bucket,
                    {agg}(value) as value
                FROM metric_data_points
                WHERE organization_id = :org_id
                  AND metric_name = :metric_name
                  AND timestamp >= :start_time
                  AND timestamp <= :end_time
            """.format(agg=aggregation.upper())

            params = {
                "org_id": organization_id,
                "metric_name": metric_name,
                "start_time": start_time,
                "end_time": end_time
            }

            if hosts:
                query += " AND host_id = ANY(:hosts)"
                params["hosts"] = hosts

            query += " GROUP BY bucket ORDER BY bucket"

            try:
                result = await db.execute(text(query), params)
                rows = result.fetchall()

                data_points = [
                    WidgetDataPoint(timestamp=row[0], value=float(row[1]) if row[1] else 0)
                    for row in rows
                ]

                series.append(WidgetDataSeries(
                    name=metric_name,
                    data=data_points
                ))
            except Exception as e:
                logger.error(f"Error fetching metric data: {e}")
                series.append(WidgetDataSeries(name=metric_name, data=[]))

        return series

    async def _fetch_log_data(
        self,
        query_config: Dict[str, Any],
        organization_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
        db: AsyncSession
    ) -> List[WidgetDataSeries]:
        """Fetch log count data for a widget."""
        try:
            result = await db.execute(
                text("""
                    SELECT
                        DATE_TRUNC('minute', timestamp) as bucket,
                        COUNT(*) as count
                    FROM log_entries
                    WHERE organization_id = :org_id
                      AND timestamp >= :start_time
                      AND timestamp <= :end_time
                    GROUP BY bucket
                    ORDER BY bucket
                """),
                {"org_id": organization_id, "start_time": start_time, "end_time": end_time}
            )
            rows = result.fetchall()

            return [WidgetDataSeries(
                name="Log Volume",
                data=[WidgetDataPoint(timestamp=row[0], value=float(row[1])) for row in rows]
            )]
        except Exception as e:
            logger.error(f"Error fetching log data: {e}")
            return []

    async def _fetch_trace_data(
        self,
        query_config: Dict[str, Any],
        organization_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
        db: AsyncSession
    ) -> List[WidgetDataSeries]:
        """Fetch trace/span data for a widget."""
        try:
            result = await db.execute(
                text("""
                    SELECT
                        DATE_TRUNC('minute', start_time) as bucket,
                        COUNT(*) as request_count,
                        AVG(duration_ms) as avg_latency
                    FROM spans
                    WHERE organization_id = :org_id
                      AND start_time >= :start_time
                      AND start_time <= :end_time
                      AND span_kind = 'server'
                    GROUP BY bucket
                    ORDER BY bucket
                """),
                {"org_id": organization_id, "start_time": start_time, "end_time": end_time}
            )
            rows = result.fetchall()

            return [
                WidgetDataSeries(
                    name="Request Count",
                    data=[WidgetDataPoint(timestamp=row[0], value=float(row[1])) for row in rows]
                ),
                WidgetDataSeries(
                    name="Avg Latency (ms)",
                    data=[WidgetDataPoint(timestamp=row[0], value=float(row[2]) if row[2] else 0) for row in rows]
                )
            ]
        except Exception as e:
            logger.error(f"Error fetching trace data: {e}")
            return []

    async def _fetch_alert_data(
        self,
        query_config: Dict[str, Any],
        organization_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
        db: AsyncSession
    ) -> List[WidgetDataSeries]:
        """Fetch alert count data for a widget."""
        try:
            result = await db.execute(
                text("""
                    SELECT
                        DATE_TRUNC('hour', created_at) as bucket,
                        COUNT(*) as count
                    FROM alerts
                    WHERE organization_id = :org_id
                      AND created_at >= :start_time
                      AND created_at <= :end_time
                    GROUP BY bucket
                    ORDER BY bucket
                """),
                {"org_id": organization_id, "start_time": start_time, "end_time": end_time}
            )
            rows = result.fetchall()

            return [WidgetDataSeries(
                name="Alert Count",
                data=[WidgetDataPoint(timestamp=row[0], value=float(row[1])) for row in rows]
            )]
        except Exception as e:
            logger.error(f"Error fetching alert data: {e}")
            return []

    # ============================================
    # Templates
    # ============================================

    async def list_templates(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession,
        category: Optional[str] = None
    ) -> DashboardTemplateListResponse:
        """List available dashboard templates."""
        stmt = select(DashboardTemplate).where(
            (DashboardTemplate.is_public == "true") |
            (DashboardTemplate.created_by_org == organization_id)
        )

        if category:
            stmt = stmt.where(DashboardTemplate.category == category)

        result = await db.execute(stmt)
        templates = result.scalars().all()

        return DashboardTemplateListResponse(
            templates=[
                DashboardTemplateResponse(
                    id=str(t.id),
                    name=t.name,
                    description=t.description,
                    category=t.category,
                    template_config=t.template_config,
                    thumbnail_url=t.thumbnail_url,
                    is_public=t.is_public == "true",
                    created_at=t.created_at
                )
                for t in templates
            ],
            total=len(templates)
        )

    async def create_from_template(
        self,
        template_id: uuid.UUID,
        name: Optional[str],
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[DashboardResponse]:
        """Create a dashboard from a template."""
        result = await db.execute(
            select(DashboardTemplate).where(DashboardTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()

        if not template:
            return None

        config = template.template_config
        dashboard_config = config.get("dashboard", {})
        widgets_config = config.get("widgets", [])

        # Create dashboard
        data = DashboardCreate(
            name=name or template.name,
            description=template.description,
            layout=dashboard_config.get("layout", "grid"),
            columns=dashboard_config.get("columns", 12),
            refresh_interval=dashboard_config.get("refresh_interval", 60),
            default_time_range=dashboard_config.get("default_time_range", "1h"),
            theme=dashboard_config.get("theme", "dark"),
            tags=dashboard_config.get("tags", []),
            widgets=[WidgetCreate(**w) for w in widgets_config]
        )

        return await self.create_dashboard(data, organization_id, user_id, db)

    # ============================================
    # Export/Import
    # ============================================

    async def export_dashboard(
        self,
        dashboard_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[DashboardExport]:
        """Export a dashboard to JSON format."""
        dashboard = await self.get_dashboard(dashboard_id, organization_id, db)
        if not dashboard:
            return None

        return DashboardExport(
            version="1.0",
            dashboard={
                "name": dashboard.name,
                "description": dashboard.description,
                "layout": dashboard.layout,
                "columns": dashboard.columns,
                "refresh_interval": dashboard.refresh_interval,
                "default_time_range": dashboard.default_time_range,
                "theme": dashboard.theme,
                "tags": dashboard.tags
            },
            widgets=[
                {
                    "title": w.title,
                    "description": w.description,
                    "widget_type": w.widget_type,
                    "position_x": w.position_x,
                    "position_y": w.position_y,
                    "width": w.width,
                    "height": w.height,
                    "data_source": w.data_source,
                    "query_config": w.query_config,
                    "display_config": w.display_config,
                    "time_range_override": w.time_range_override,
                    "display_order": w.display_order
                }
                for w in dashboard.widgets
            ]
        )

    # ============================================
    # Helpers
    # ============================================

    def _generate_slug(self, name: str) -> str:
        """Generate a URL-friendly slug from a name."""
        slug = name.lower()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        return slug.strip('-')[:100]

    def _parse_time_range(self, time_range: str) -> int:
        """Parse time range string to hours."""
        match = re.match(r'(\d+)([mhd])', time_range)
        if not match:
            return 1

        value = int(match.group(1))
        unit = match.group(2)

        if unit == 'm':
            return max(1, value // 60)
        elif unit == 'h':
            return value
        elif unit == 'd':
            return value * 24

        return 1

    def _dashboard_to_response(self, dashboard: Dashboard) -> DashboardResponse:
        """Convert dashboard model to response."""
        return DashboardResponse(
            id=str(dashboard.id),
            organization_id=str(dashboard.organization_id),
            name=dashboard.name,
            description=dashboard.description,
            slug=dashboard.slug,
            created_by=str(dashboard.created_by) if dashboard.created_by else None,
            is_default=dashboard.is_default == "true",
            is_shared=dashboard.is_shared == "true",
            layout=dashboard.layout,
            columns=dashboard.columns,
            refresh_interval=dashboard.refresh_interval,
            default_time_range=dashboard.default_time_range,
            theme=dashboard.theme,
            tags=dashboard.tags or [],
            widgets=[self._widget_to_response(w) for w in dashboard.widgets],
            created_at=dashboard.created_at,
            updated_at=dashboard.updated_at
        )

    def _widget_to_response(self, widget: DashboardWidget) -> WidgetResponse:
        """Convert widget model to response."""
        return WidgetResponse(
            id=str(widget.id),
            dashboard_id=str(widget.dashboard_id),
            title=widget.title,
            description=widget.description,
            widget_type=widget.widget_type,
            position_x=widget.position_x,
            position_y=widget.position_y,
            width=widget.width,
            height=widget.height,
            data_source=widget.data_source,
            query_config=widget.query_config or {},
            display_config=widget.display_config or {},
            time_range_override=widget.time_range_override,
            display_order=widget.display_order,
            created_at=widget.created_at,
            updated_at=widget.updated_at
        )


# Singleton instance
dashboard_service = DashboardService()
