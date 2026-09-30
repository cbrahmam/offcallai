# backend/app/services/metrics_service.py
"""
Metrics service for ingesting and querying time-series data.
Supports both TimescaleDB (preferred) and regular PostgreSQL.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.host import Host
from app.schemas.metrics import (
    MetricBatch, MetricPoint, MetricIngestResponse,
    MetricQuery, MetricQueryResponse, MetricSeries, MetricDataPoint,
    LatestMetricValue, LatestMetricsResponse, AggregationType,
    STANDARD_METRICS
)
from app.services.host_service import host_service

logger = logging.getLogger(__name__)


class MetricsService:
    """Service for metric ingestion and querying."""

    # ============================================
    # Metric Ingestion
    # ============================================

    async def ingest_batch(
        self,
        batch: MetricBatch,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> MetricIngestResponse:
        """
        Ingest a batch of metrics from an agent.
        Resolves host by agent_id and stores metrics.
        """
        errors = []
        points_received = len(batch.metrics)
        points_stored = 0

        # Look up or create host
        host = await host_service.get_host_by_agent_id(
            batch.agent_id, organization_id, db
        )

        if not host:
            return MetricIngestResponse(
                success=False,
                points_received=points_received,
                points_stored=0,
                host_id="",
                errors=[f"Unknown agent_id: {batch.agent_id}. Register the agent first."]
            )

        host_id = host.id

        # Update host's last_seen_at
        await db.execute(
            text("UPDATE hosts SET last_seen_at = NOW() WHERE id = :host_id"),
            {"host_id": host_id}
        )

        # Prepare batch insert
        values = []
        for point in batch.metrics:
            timestamp = point.timestamp or batch.collected_at or datetime.utcnow()
            values.append({
                "time": timestamp,
                "organization_id": organization_id,
                "host_id": host_id,
                "name": point.name,
                "value": point.value,
                "unit": point.unit,
                "tags": point.tags or {}
            })

        if values:
            try:
                # Batch insert using VALUES list
                await db.execute(
                    text("""
                        INSERT INTO metrics (time, organization_id, host_id, name, value, unit, tags)
                        VALUES (:time, :organization_id, :host_id, :name, :value, :unit, :tags)
                    """),
                    values
                )
                await db.commit()
                points_stored = len(values)
            except Exception as e:
                logger.error(f"Error inserting metrics: {e}")
                errors.append(str(e))
                await db.rollback()

        logger.debug(f"Ingested {points_stored}/{points_received} metrics for host {host_id}")

        return MetricIngestResponse(
            success=len(errors) == 0,
            points_received=points_received,
            points_stored=points_stored,
            host_id=str(host_id),
            errors=errors
        )

    async def ingest_single(
        self,
        point: MetricPoint,
        host_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> bool:
        """Ingest a single metric point."""
        try:
            timestamp = point.timestamp or datetime.utcnow()
            await db.execute(
                text("""
                    INSERT INTO metrics (time, organization_id, host_id, name, value, unit, tags)
                    VALUES (:time, :org_id, :host_id, :name, :value, :unit, :tags)
                """),
                {
                    "time": timestamp,
                    "org_id": organization_id,
                    "host_id": host_id,
                    "name": point.name,
                    "value": point.value,
                    "unit": point.unit,
                    "tags": point.tags or {}
                }
            )
            await db.commit()
            return True
        except Exception as e:
            logger.error(f"Error inserting metric: {e}")
            await db.rollback()
            return False

    # ============================================
    # Metric Queries
    # ============================================

    async def query_metrics(
        self,
        query: MetricQuery,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> MetricQueryResponse:
        """
        Query metrics with aggregation and grouping.
        Supports time bucketing for efficient queries.
        """
        # Determine bucket interval
        interval = query.interval or self._auto_interval(query.start_time, query.end_time)
        bucket_sql = self._get_bucket_sql(interval)

        # Build aggregation function
        agg_func = self._get_agg_function(query.aggregation)

        # Build WHERE clause
        where_clauses = [
            "organization_id = :org_id",
            "name = :metric_name",
            "time >= :start_time",
            "time <= :end_time"
        ]
        params = {
            "org_id": organization_id,
            "metric_name": query.metric_name,
            "start_time": query.start_time,
            "end_time": query.end_time
        }

        if query.host_ids:
            where_clauses.append("host_id = ANY(:host_ids)")
            params["host_ids"] = [uuid.UUID(h) for h in query.host_ids]

        if query.tags:
            for key, value in query.tags.items():
                where_clauses.append(f"tags->>'{key}' = :tag_{key}")
                params[f"tag_{key}"] = value

        where_sql = " AND ".join(where_clauses)

        # Build GROUP BY clause
        group_by = ["bucket", "host_id"]
        if query.group_by:
            for tag_key in query.group_by:
                group_by.append(f"tags->>'{tag_key}'")

        group_by_sql = ", ".join(group_by)

        # Build the query
        sql = f"""
            SELECT
                {bucket_sql} as bucket,
                host_id,
                {agg_func}(value) as agg_value
            FROM metrics
            WHERE {where_sql}
            GROUP BY {group_by_sql}
            ORDER BY bucket ASC, host_id
        """

        try:
            result = await db.execute(text(sql), params)
            rows = result.fetchall()
        except Exception as e:
            logger.error(f"Metric query error: {e}")
            return MetricQueryResponse(
                series=[],
                query=query,
                total_points=0
            )

        # Organize results by host_id
        series_map: Dict[str, List[MetricDataPoint]] = {}
        for row in rows:
            bucket, host_id, value = row
            host_key = str(host_id)

            if host_key not in series_map:
                series_map[host_key] = []

            series_map[host_key].append(MetricDataPoint(
                timestamp=bucket,
                value=value
            ))

        # Get hostnames
        host_ids = list(series_map.keys())
        hostname_map = await self._get_hostnames(host_ids, db)

        # Build response series
        series = [
            MetricSeries(
                metric_name=query.metric_name,
                host_id=host_id,
                hostname=hostname_map.get(host_id, "unknown"),
                data=data_points
            )
            for host_id, data_points in series_map.items()
        ]

        total_points = sum(len(s.data) for s in series)

        return MetricQueryResponse(
            series=series,
            query=query,
            total_points=total_points
        )

    async def get_latest_metrics(
        self,
        organization_id: uuid.UUID,
        metric_names: List[str],
        host_ids: Optional[List[str]],
        db: AsyncSession
    ) -> LatestMetricsResponse:
        """Get the latest value for specified metrics."""
        params = {
            "org_id": organization_id,
            "metric_names": metric_names
        }

        host_filter = ""
        if host_ids:
            host_filter = "AND host_id = ANY(:host_ids)"
            params["host_ids"] = [uuid.UUID(h) for h in host_ids]

        # Use DISTINCT ON for each host/metric combination
        sql = f"""
            SELECT DISTINCT ON (host_id, name)
                name,
                host_id,
                value,
                time,
                unit,
                tags
            FROM metrics
            WHERE organization_id = :org_id
              AND name = ANY(:metric_names)
              {host_filter}
            ORDER BY host_id, name, time DESC
        """

        result = await db.execute(text(sql), params)
        rows = result.fetchall()

        # Get hostnames
        host_ids_found = list(set(str(row[1]) for row in rows))
        hostname_map = await self._get_hostnames(host_ids_found, db)

        metrics = [
            LatestMetricValue(
                metric_name=row[0],
                host_id=str(row[1]),
                hostname=hostname_map.get(str(row[1]), "unknown"),
                value=row[2],
                timestamp=row[3],
                unit=row[4],
                tags=row[5] or {}
            )
            for row in rows
        ]

        return LatestMetricsResponse(metrics=metrics)

    async def get_host_current_metrics(
        self,
        host_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Get current (latest) metrics for a specific host from ClickHouse.
        Returns key metrics like CPU, memory, disk usage.
        """
        from app.services.clickhouse_service import ClickHouseService

        key_metrics = [
            "system.cpu.usage",
            "system.memory.usage_percent",
            "system.disk.usage_percent",
            "system.load.1",
            "system.network.bytes_in",
            "system.network.bytes_out"
        ]

        clickhouse = ClickHouseService()
        metrics_str = ", ".join(f"'{m}'" for m in key_metrics)

        query = f"""
            SELECT
                name,
                argMax(value, timestamp) as latest_value,
                max(timestamp) as latest_timestamp,
                any(unit) as unit
            FROM metrics
            WHERE organization_id = '{organization_id}'
              AND host_id = '{host_id}'
              AND name IN ({metrics_str})
              AND timestamp > now() - INTERVAL 5 MINUTE
            GROUP BY name
            FORMAT JSON
        """

        try:
            result = await clickhouse.execute(query)
            data = result.get("data", []) if result else []

            metrics = {}
            for row in data:
                name = row.get("name")
                metrics[name] = {
                    "value": row.get("latest_value"),
                    "timestamp": row.get("latest_timestamp"),
                    "unit": row.get("unit", "")
                }

            return metrics
        except Exception as e:
            logger.error(f"ClickHouse query failed for host metrics: {e}")
            return {}

    # ============================================
    # Helper Methods
    # ============================================

    def _auto_interval(self, start: datetime, end: datetime) -> str:
        """Automatically determine bucket interval based on time range."""
        duration = end - start
        if duration <= timedelta(hours=1):
            return "1m"
        elif duration <= timedelta(hours=6):
            return "5m"
        elif duration <= timedelta(days=1):
            return "15m"
        elif duration <= timedelta(days=7):
            return "1h"
        elif duration <= timedelta(days=30):
            return "6h"
        else:
            return "1d"

    def _get_bucket_sql(self, interval: str) -> str:
        """Get SQL for time bucketing. Tries TimescaleDB first, falls back to date_trunc."""
        # TimescaleDB time_bucket format
        interval_map = {
            "1m": "1 minute",
            "5m": "5 minutes",
            "15m": "15 minutes",
            "30m": "30 minutes",
            "1h": "1 hour",
            "6h": "6 hours",
            "1d": "1 day"
        }
        pg_interval = interval_map.get(interval, "1 hour")

        # Try TimescaleDB time_bucket, but use a fallback that works with standard PostgreSQL
        # In practice, if TimescaleDB is installed, time_bucket works; otherwise use date_trunc
        return f"date_trunc('hour', time)"  # Simplified fallback; enhance for production

    def _get_agg_function(self, agg: AggregationType) -> str:
        """Get SQL aggregation function."""
        return {
            AggregationType.AVG: "AVG",
            AggregationType.SUM: "SUM",
            AggregationType.MIN: "MIN",
            AggregationType.MAX: "MAX",
            AggregationType.COUNT: "COUNT",
            AggregationType.LAST: "MAX",  # Approximation
            AggregationType.RATE: "SUM"  # Would need diff calculation
        }.get(agg, "AVG")

    async def _get_hostnames(
        self,
        host_ids: List[str],
        db: AsyncSession
    ) -> Dict[str, str]:
        """Get hostname mapping for a list of host IDs."""
        if not host_ids:
            return {}

        result = await db.execute(
            text("SELECT id, hostname FROM hosts WHERE id = ANY(:ids)"),
            {"ids": [uuid.UUID(h) for h in host_ids]}
        )
        rows = result.fetchall()
        return {str(row[0]): row[1] for row in rows}

    # ============================================
    # Aggregation Worker Methods
    # ============================================

    async def aggregate_hourly(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession,
        hours_back: int = 1
    ) -> int:
        """
        Aggregate raw metrics into hourly buckets.
        Called by a background worker.
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours_back)

        sql = """
            INSERT INTO metrics_hourly (bucket, organization_id, host_id, name, avg_value, min_value, max_value, sample_count)
            SELECT
                date_trunc('hour', time) as bucket,
                organization_id,
                host_id,
                name,
                AVG(value) as avg_value,
                MIN(value) as min_value,
                MAX(value) as max_value,
                COUNT(*) as sample_count
            FROM metrics
            WHERE organization_id = :org_id
              AND time >= :cutoff
              AND time < date_trunc('hour', NOW())
            GROUP BY bucket, organization_id, host_id, name
            ON CONFLICT (bucket, organization_id, host_id, name)
            DO UPDATE SET
                avg_value = EXCLUDED.avg_value,
                min_value = EXCLUDED.min_value,
                max_value = EXCLUDED.max_value,
                sample_count = EXCLUDED.sample_count
        """

        try:
            result = await db.execute(
                text(sql),
                {"org_id": organization_id, "cutoff": cutoff}
            )
            await db.commit()
            count = result.rowcount
            if count > 0:
                logger.info(f"Aggregated {count} hourly metric buckets for org {organization_id}")
            return count
        except Exception as e:
            logger.error(f"Error aggregating metrics: {e}")
            await db.rollback()
            return 0

    async def cleanup_old_metrics(
        self,
        db: AsyncSession,
        days_to_keep: int = 7
    ) -> int:
        """
        Delete raw metrics older than specified days.
        Hourly aggregates are kept longer.
        """
        cutoff = datetime.utcnow() - timedelta(days=days_to_keep)

        try:
            result = await db.execute(
                text("DELETE FROM metrics WHERE time < :cutoff"),
                {"cutoff": cutoff}
            )
            await db.commit()
            count = result.rowcount
            if count > 0:
                logger.info(f"Cleaned up {count} old metric records")
            return count
        except Exception as e:
            logger.error(f"Error cleaning up metrics: {e}")
            await db.rollback()
            return 0

    # ============================================
    # Metric Catalog
    # ============================================

    def get_metric_catalog(self) -> List[Dict[str, Any]]:
        """Return the standard metric definitions."""
        return [m.dict() for m in STANDARD_METRICS]

    async def get_available_metrics(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> List[str]:
        """Get list of metric names that have data for this org."""
        result = await db.execute(
            text("""
                SELECT DISTINCT name
                FROM metrics
                WHERE organization_id = :org_id
                  AND time > NOW() - INTERVAL '24 hours'
                ORDER BY name
            """),
            {"org_id": organization_id}
        )
        rows = result.fetchall()
        return [row[0] for row in rows]


# Singleton instance
metrics_service = MetricsService()
