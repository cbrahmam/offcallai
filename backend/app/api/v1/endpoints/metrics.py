# backend/app/api/v1/endpoints/metrics.py
"""
API endpoints for metrics ingestion and querying.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Header, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_async_session
from app.core.security import get_current_user
from app.core.config import settings
from app.models.user import User
from app.services.host_service import host_service
from app.services.metrics_service import metrics_service
from app.schemas.metrics import (
    MetricBatch, MetricIngestResponse, MetricQuery, MetricQueryResponse,
    LatestMetricsResponse, MetricCatalogResponse, MetricDefinition,
    AggregationType, STANDARD_METRICS
)
from datetime import datetime, timedelta
from typing import Optional, List
import uuid
import logging
import asyncio

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================
# List Endpoint (convenience route)
# ============================================

@router.get("/")
async def list_metrics(
    metric_name: Optional[str] = Query(None, description="Filter by metric name"),
    host_id: Optional[str] = Query(None, description="Filter by host ID"),
    limit: int = Query(100, ge=1, le=1000, description="Number of data points"),
    hours: int = Query(1, ge=1, le=168, description="Hours of history"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    List recent metrics with optional filtering.
    If no metric_name specified, returns available metric names.
    """
    try:
        if settings.CLICKHOUSE_ENABLED:
            from app.services.clickhouse_service import ClickHouseService
            ch = ClickHouseService()
            try:
                if metric_name:
                    # Query specific metric
                    end_time = datetime.utcnow()
                    start_time = end_time - timedelta(hours=hours)
                    result = await ch.query_metrics(
                        organization_id=str(current_user.organization_id),
                        name=metric_name,
                        start_time=start_time,
                        end_time=end_time,
                        host_id=host_id,
                        limit=limit
                    )
                    return {
                        "metric_name": metric_name,
                        "data_points": result,
                        "count": len(result) if result else 0,
                        "time_range": {"start": start_time.isoformat(), "end": end_time.isoformat()}
                    }
                else:
                    # Return list of available metrics
                    metric_names = await ch.get_metric_names(str(current_user.organization_id))
                    return {
                        "available_metrics": metric_names,
                        "count": len(metric_names),
                        "hint": "Add ?metric_name=<name> to query specific metric data"
                    }
            finally:
                await ch.close()
        else:
            # Fallback: return catalog
            return {
                "available_metrics": [m.name for m in STANDARD_METRICS],
                "count": len(STANDARD_METRICS),
                "hint": "ClickHouse not enabled - showing standard metric definitions"
            }
    except Exception as e:
        logger.error(f"Error listing metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve metrics: {str(e)}")


# ============================================
# ClickHouse Integration
# ============================================

async def write_metrics_to_clickhouse(metrics: List[dict], organization_id: uuid.UUID, host_id: Optional[str] = None):
    """Write metrics to ClickHouse."""
    if not settings.CLICKHOUSE_ENABLED:
        return

    try:
        from app.services.clickhouse_service import clickhouse_service

        # Convert metrics to ClickHouse format
        ch_metrics = []
        for m in metrics:
            # Use batch-level host_id if metric doesn't have one
            metric_host_id = str(m.get("host_id")) if m.get("host_id") else host_id
            ch_metrics.append({
                "timestamp": m.get("timestamp") or datetime.utcnow().isoformat(),
                "organization_id": str(organization_id),
                "host_id": metric_host_id,
                "name": m["name"],
                "value": float(m["value"]),
                "unit": m.get("unit", ""),
                "tags": m.get("tags", {}),
            })

        await clickhouse_service.insert_metrics(ch_metrics)
        logger.debug(f"Wrote {len(ch_metrics)} metrics to ClickHouse")
    except Exception as e:
        logger.error(f"Failed to write metrics to ClickHouse: {e}")


async def query_metrics_from_clickhouse(
    organization_id: uuid.UUID,
    metric_name: str,
    start_time: datetime,
    end_time: datetime,
    host_id: Optional[str] = None,
    aggregation: str = "avg"
) -> dict:
    """Query metrics from ClickHouse."""
    from app.services.clickhouse_service import clickhouse_service

    # Calculate appropriate interval based on time range
    duration = (end_time - start_time).total_seconds()
    if duration <= 3600:  # 1 hour
        interval = "1 MINUTE"
    elif duration <= 86400:  # 24 hours
        interval = "5 MINUTE"
    elif duration <= 604800:  # 7 days
        interval = "1 HOUR"
    else:
        interval = "1 DAY"

    data = await clickhouse_service.query_metrics(
        organization_id=str(organization_id),
        name=metric_name,
        start_time=start_time,
        end_time=end_time,
        host_id=host_id,
        interval=interval,
        aggregation=aggregation
    )

    return {
        "metric_name": metric_name,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "interval": interval,
        "data_points": data
    }


async def get_latest_metrics_from_clickhouse(
    organization_id: uuid.UUID,
    metric_names: List[str],
    host_ids: Optional[List[str]] = None
) -> dict:
    """Get latest metric values from ClickHouse."""
    from app.services.clickhouse_service import clickhouse_service

    host_filter = ""
    if host_ids:
        host_ids_str = ", ".join(f"'{h}'" for h in host_ids)
        host_filter = f"AND host_id IN ({host_ids_str})"

    names_str = ", ".join(f"'{n}'" for n in metric_names)

    query = f"""
    SELECT
        name,
        host_id,
        argMax(value, timestamp) as value,
        max(timestamp) as last_timestamp,
        any(unit) as unit,
        any(tags) as tags
    FROM metrics
    WHERE organization_id = '{organization_id}'
        AND name IN ({names_str})
        AND timestamp >= now() - INTERVAL 1 HOUR
        {host_filter}
    GROUP BY name, host_id
    ORDER BY name, host_id
    FORMAT JSON
    """

    result = await clickhouse_service.execute(query)
    data = result.get("data", []) if result else []

    return {
        "metrics": [
            {
                "metric_name": row.get("name"),
                "host_id": row.get("host_id"),
                "value": row.get("value"),
                "timestamp": row.get("last_timestamp"),
                "unit": row.get("unit", ""),
                "tags": row.get("tags", {})
            }
            for row in data
        ]
    }


async def get_available_metrics_from_clickhouse(organization_id: uuid.UUID) -> List[str]:
    """Get list of available metric names from ClickHouse."""
    from app.services.clickhouse_service import clickhouse_service

    return await clickhouse_service.get_metric_names(str(organization_id))


# ============================================
# Agent Ingestion Endpoints (API Key Auth)
# ============================================

async def get_org_from_agent_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_async_session)
) -> uuid.UUID:
    """Validate agent API key and return organization ID."""
    org_id = await host_service.verify_agent_api_key(x_api_key, db)
    if not org_id:
        raise HTTPException(status_code=401, detail="Invalid or expired API key")
    return org_id


@router.post("/ingest", response_model=MetricIngestResponse, tags=["agent"])
async def ingest_metrics(
    batch: MetricBatch,
    organization_id: uuid.UUID = Depends(get_org_from_agent_key),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Ingest a batch of metrics from an agent.
    Requires agent API key authentication via X-API-Key header.

    Maximum 1000 metrics per batch.
    Writes to ClickHouse (primary) for time-series data.
    """
    try:
        # Resolve host_id from agent_id
        host_id = batch.host_id
        if not host_id and batch.agent_id:
            host = await host_service.get_host_by_agent_id(
                batch.agent_id, organization_id, db
            )
            if host:
                host_id = str(host.id)
                # Update last_seen_at
                from sqlalchemy import text
                await db.execute(
                    text("UPDATE hosts SET last_seen_at = NOW() WHERE id = :host_id"),
                    {"host_id": host.id}
                )
                await db.commit()

        if settings.CLICKHOUSE_ENABLED:
            # Write to ClickHouse (primary for time-series)
            metrics_data = [m.model_dump() for m in batch.metrics]
            await write_metrics_to_clickhouse(metrics_data, organization_id, host_id)
            return MetricIngestResponse(
                success=True,
                metrics_received=len(batch.metrics),
                message=f"Ingested {len(batch.metrics)} metrics"
            )
        else:
            # Fallback to PostgreSQL if ClickHouse not enabled
            result = await metrics_service.ingest_batch(batch, organization_id, db)
            return result
    except Exception as e:
        logger.error(f"Metric ingestion failed: {e}")
        raise HTTPException(status_code=500, detail="Ingestion failed")


# ============================================
# Query Endpoints (User Auth)
# ============================================

@router.post("/query")
async def query_metrics(
    query: MetricQuery,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Query time-series metrics with aggregation and grouping.

    Supports:
    - Filtering by host_ids and tags
    - Time bucketing with automatic interval selection
    - Aggregation functions: avg, sum, min, max, count, last, rate
    - Grouping by tag keys
    """
    try:
        if settings.CLICKHOUSE_ENABLED:
            # Query from ClickHouse
            host_id = query.host_ids[0] if query.host_ids else None
            result = await query_metrics_from_clickhouse(
                organization_id=current_user.organization_id,
                metric_name=query.metric_name,
                start_time=query.start_time,
                end_time=query.end_time,
                host_id=host_id,
                aggregation=query.aggregation.value if query.aggregation else "avg"
            )
            return result
        else:
            result = await metrics_service.query_metrics(
                query, current_user.organization_id, db
            )
            return result
    except Exception as e:
        logger.error(f"Metric query failed: {e}")
        raise HTTPException(status_code=500, detail="Query failed")


@router.get("/latest")
async def get_latest_metrics(
    metric_names: str = Query(..., description="Comma-separated list of metric names"),
    host_ids: Optional[str] = Query(None, description="Comma-separated list of host IDs"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get the latest value for specified metrics across hosts.

    Example: /metrics/latest?metric_names=system.cpu.usage,system.memory.usage_percent
    """
    try:
        names = [n.strip() for n in metric_names.split(",")]
        hosts = [h.strip() for h in host_ids.split(",")] if host_ids else None

        if settings.CLICKHOUSE_ENABLED:
            result = await get_latest_metrics_from_clickhouse(
                current_user.organization_id, names, hosts
            )
            return result
        else:
            result = await metrics_service.get_latest_metrics(
                current_user.organization_id, names, hosts, db
            )
            return result
    except Exception as e:
        logger.error(f"Error getting latest metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")


@router.get("/hosts/{host_id}/current")
async def get_host_current_metrics(
    host_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get current (latest) metrics for a specific host.
    Returns key metrics like CPU, memory, disk usage.
    """
    try:
        host_uuid = uuid.UUID(host_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid host ID")

    try:
        metrics = await metrics_service.get_host_current_metrics(
            host_uuid, current_user.organization_id, db
        )
        return {"host_id": host_id, "metrics": metrics}
    except Exception as e:
        logger.error(f"Error getting host metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")


@router.get("/hosts/{host_id}/history")
async def get_host_metric_history(
    host_id: str,
    metric_name: Optional[str] = Query(None, description="Metric name (singular)"),
    metric_names: Optional[str] = Query(None, description="Comma-separated metric names"),
    period: Optional[str] = Query(None, description="Time period: 1h, 6h, 24h, 7d, 30d"),
    start_time: Optional[str] = Query(None, description="Start time (ISO format)"),
    end_time: Optional[str] = Query(None, description="End time (ISO format)"),
    aggregation: AggregationType = Query(AggregationType.AVG, description="Aggregation function"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get historical metric data for a specific host.
    Supports both single metric_name and comma-separated metric_names.
    Supports both period (1h, 6h, etc.) and explicit start_time/end_time.
    """
    try:
        host_uuid = uuid.UUID(host_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid host ID")

    # Determine metric names to query
    names_to_query = []
    if metric_names:
        names_to_query = [n.strip() for n in metric_names.split(",")]
    elif metric_name:
        names_to_query = [metric_name]
    else:
        raise HTTPException(status_code=400, detail="Either metric_name or metric_names is required")

    # Determine time range
    if start_time and end_time:
        try:
            query_start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            query_end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid time format")
    else:
        # Use period
        period_map = {
            "1h": timedelta(hours=1),
            "6h": timedelta(hours=6),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30)
        }
        delta = period_map.get(period or "1h", timedelta(hours=1))
        query_end = datetime.utcnow()
        query_start = query_end - delta

    # Query each metric and combine results
    all_results = []
    try:
        if settings.CLICKHOUSE_ENABLED:
            for name in names_to_query:
                result = await query_metrics_from_clickhouse(
                    organization_id=current_user.organization_id,
                    metric_name=name,
                    start_time=query_start,
                    end_time=query_end,
                    host_id=host_id,
                    aggregation=aggregation.value
                )
                if result.get("data_points"):
                    all_results.append({
                        "metric_name": name,
                        "data_points": result["data_points"]
                    })
        else:
            for name in names_to_query:
                query = MetricQuery(
                    metric_name=name,
                    host_ids=[host_id],
                    start_time=query_start,
                    end_time=query_end,
                    aggregation=aggregation
                )
                result = await metrics_service.query_metrics(
                    query, current_user.organization_id, db
                )
                all_results.append(result)

        return {
            "host_id": host_id,
            "metrics": all_results,
            "start_time": query_start.isoformat(),
            "end_time": query_end.isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting metric history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")


# ============================================
# Metric Catalog
# ============================================

@router.get("/catalog", response_model=MetricCatalogResponse)
async def get_metric_catalog():
    """
    Get the catalog of standard metric definitions.
    Includes metric names, display names, descriptions, and units.
    """
    return MetricCatalogResponse(metrics=STANDARD_METRICS)


@router.get("/available")
async def get_available_metrics(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get list of metrics that have data for this organization.
    Only returns metrics with data from the last 24 hours.
    """
    try:
        if settings.CLICKHOUSE_ENABLED:
            metrics = await get_available_metrics_from_clickhouse(current_user.organization_id)
            return {"metrics": metrics}
        else:
            raise HTTPException(
                status_code=503,
                detail="Metric storage requires ClickHouse. Set CLICKHOUSE_ENABLED=true and "
                       "the CLICKHOUSE_* connection settings.",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting available metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")


# ============================================
# Dashboard Helpers
# ============================================

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get a summary of metrics for the dashboard.
    Includes host count, active hosts, and key metric averages.
    """
    try:
        # Get host stats
        host_stats = await host_service.get_host_stats(
            current_user.organization_id, db
        )

        # Metric samples live in ClickHouse; without it the host counts are
        # still meaningful, so report those and leave the averages unset.
        rows = []
        if settings.CLICKHOUSE_ENABLED:
            latest = await get_latest_metrics_from_clickhouse(
                current_user.organization_id,
                ["system.cpu.usage", "system.memory.usage_percent"],
            )
            rows = latest.get("metrics", [])

        cpu_values = [r["value"] for r in rows if r["metric_name"] == "system.cpu.usage" and r["value"] is not None]
        memory_values = [r["value"] for r in rows if r["metric_name"] == "system.memory.usage_percent" and r["value"] is not None]

        avg_cpu = sum(cpu_values) / len(cpu_values) if cpu_values else None
        avg_memory = sum(memory_values) / len(memory_values) if memory_values else None

        return {
            "hosts": host_stats,
            "metrics": {
                "avg_cpu_usage": round(avg_cpu, 2) if avg_cpu else None,
                "avg_memory_usage": round(avg_memory, 2) if avg_memory else None,
                "hosts_with_metrics": len(cpu_values)
            }
        }
    except Exception as e:
        logger.error(f"Error getting dashboard summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve summary")


@router.get("/dashboard/top-hosts")
async def get_top_hosts(
    metric: str = Query("system.cpu.usage", description="Metric to rank by"),
    limit: int = Query(10, ge=1, le=50, description="Number of hosts to return"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get top hosts by a specific metric (e.g., highest CPU usage).
    """
    try:
        if not settings.CLICKHOUSE_ENABLED:
            raise HTTPException(
                status_code=503,
                detail="Ranking hosts by metric requires ClickHouse. Set CLICKHOUSE_ENABLED=true "
                       "and the CLICKHOUSE_* connection settings.",
            )

        latest = await get_latest_metrics_from_clickhouse(current_user.organization_id, [metric])
        rows = [r for r in latest.get("metrics", []) if r.get("value") is not None]
        rows.sort(key=lambda r: r["value"], reverse=True)

        return {
            "metric": metric,
            "hosts": [
                {
                    "host_id": r.get("host_id"),
                    "value": round(r["value"], 2),
                    "timestamp": r.get("timestamp"),
                    "unit": r.get("unit", ""),
                }
                for r in rows[:limit]
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting top hosts: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve data")
