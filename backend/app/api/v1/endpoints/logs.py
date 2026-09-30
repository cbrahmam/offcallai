# backend/app/api/v1/endpoints/logs.py
"""
API endpoints for log management.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Header, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_async_session
from app.core.security import get_current_user
from app.core.config import settings
from app.models.user import User
from app.services.log_service import log_service
from app.services.host_service import host_service
from app.schemas.log import (
    LogBatch, LogIngestResponse,
    LogQuery, LogQueryResponse,
    LogStats, LogContext,
    LogSourceCreate, LogSourceUpdate, LogSourceResponse, LogSourceListResponse,
    LogLevel
)
from datetime import datetime, timedelta
from typing import Optional, List
import uuid
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================
# List Endpoint (convenience route)
# ============================================

@router.get("/")
async def list_logs(
    limit: int = Query(50, ge=1, le=1000, description="Number of logs to return"),
    query: Optional[str] = Query(None, description="Search query"),
    level: Optional[str] = Query(None, description="Filter by log level (INFO, WARN, ERROR, DEBUG)"),
    service: Optional[str] = Query(None, description="Filter by service name"),
    hours: int = Query(24, ge=1, le=168, description="Hours of history to search"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    List recent logs with optional filtering.
    This is a convenience endpoint - for advanced queries use POST /query.
    """
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        # Levels must be uppercase to match ClickHouse stored data
        levels = [level.upper()] if level else None
        services = [service] if service else None

        if settings.CLICKHOUSE_ENABLED:
            from app.services.clickhouse_service import ClickHouseService
            ch = ClickHouseService()
            try:
                result = await ch.search_logs(
                    organization_id=str(current_user.organization_id),
                    start_time=start_time,
                    end_time=end_time,
                    query=query,
                    levels=levels,
                    services=services,
                    limit=limit,
                    offset=0
                )
                return {
                    "logs": result.get("logs", []),
                    "total": result.get("total", 0),
                    "limit": limit,
                    "query": query,
                    "level": level,
                    "service": service,
                    "time_range": {"start": start_time.isoformat(), "end": end_time.isoformat()}
                }
            finally:
                await ch.close()
        else:
            # Fallback to PostgreSQL (log_entries table)
            response = await log_service.query_logs(
                LogQuery(
                    query=query,
                    start_time=start_time,
                    end_time=end_time,
                    levels=levels,
                    services=services,
                    limit=limit,
                ),
                current_user.organization_id,
                db,
            )
            result = {"logs": [e.model_dump() for e in response.logs], "total": response.total}
            return {
                "logs": result.get("logs", []),
                "total": result.get("total", 0),
                "limit": limit
            }
    except Exception as e:
        logger.error(f"Error listing logs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve logs: {str(e)}")


# ============================================
# ClickHouse Integration
# ============================================

async def write_logs_to_clickhouse(logs: List[dict], organization_id: uuid.UUID):
    """Write logs to ClickHouse."""
    if not settings.CLICKHOUSE_ENABLED:
        return

    try:
        from app.services.clickhouse_service import clickhouse_service

        # Convert logs to ClickHouse format
        ch_logs = []
        for log in logs:
            # Merge attributes and tags into fields
            fields = log.get("fields") or {}
            if log.get("attributes"):
                # Attributes from agent (parsed JSON fields)
                for k, v in log.get("attributes", {}).items():
                    fields[k] = str(v) if not isinstance(v, str) else v
            if log.get("tags"):
                # Tags from agent (map[string]string)
                for k, v in log.get("tags", {}).items():
                    fields[f"tag_{k}"] = v

            # Normalize log level
            level = log.get("level", "info")
            if isinstance(level, str):
                level = level.upper()
            else:
                level = "INFO"

            ch_logs.append({
                "timestamp": log.get("timestamp") or datetime.utcnow().isoformat(),
                "organization_id": str(organization_id),
                "host_id": str(log.get("host_id")) if log.get("host_id") else None,
                "level": level,
                "message": log.get("message", ""),
                "service": log.get("service", ""),
                "source": log.get("source", ""),
                "trace_id": log.get("trace_id", ""),
                "span_id": log.get("span_id", ""),
                "fields": fields,
            })

        await clickhouse_service.insert_logs(ch_logs)
        logger.debug(f"Wrote {len(ch_logs)} logs to ClickHouse")
    except Exception as e:
        logger.error(f"Failed to write logs to ClickHouse: {e}")


async def search_logs_from_clickhouse(
    organization_id: uuid.UUID,
    start_time: datetime,
    end_time: datetime,
    query: Optional[str] = None,
    levels: Optional[List[str]] = None,
    services: Optional[List[str]] = None,
    host_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> dict:
    """Search logs from ClickHouse."""
    from app.services.clickhouse_service import ClickHouseService

    # Create fresh instance to avoid stale connection issues under load
    ch = ClickHouseService()
    try:
        result = await ch.search_logs(
            organization_id=str(organization_id),
            start_time=start_time,
            end_time=end_time,
            query=query,
            levels=levels,
            services=services,
            host_id=host_id,
            limit=limit,
            offset=offset
        )
        return result
    finally:
        await ch.close()


async def get_log_stats_from_clickhouse(
    organization_id: uuid.UUID,
    hours: int = 24
) -> dict:
    """Get log statistics from ClickHouse."""
    from app.services.clickhouse_service import ClickHouseService

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)

    # Create fresh instance to avoid stale connection issues
    ch = ClickHouseService()
    try:
        result = await ch.get_log_stats(
            organization_id=str(organization_id),
            start_time=start_time,
            end_time=end_time
        )
        return result
    finally:
        await ch.close()


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

@router.post("/ingest", response_model=LogIngestResponse, tags=["agent"])
async def ingest_logs(
    batch: LogBatch,
    organization_id: uuid.UUID = Depends(get_org_from_agent_key),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Ingest a batch of logs from an agent.
    Requires agent API key authentication via X-API-Key header.

    Maximum 1000 log entries per batch.
    Writes to ClickHouse (primary) for time-series data.
    """
    try:
        if settings.CLICKHOUSE_ENABLED:
            # Write to ClickHouse (primary for time-series)
            logs_data = [log.model_dump() for log in batch.logs]
            await write_logs_to_clickhouse(logs_data, organization_id)
            return LogIngestResponse(
                success=True,
                logs_received=len(batch.logs),
                logs_stored=len(batch.logs),
                message=f"Ingested {len(batch.logs)} logs"
            )
        else:
            # Fallback to PostgreSQL if ClickHouse not enabled
            result = await log_service.ingest_batch(batch, organization_id, db)
            return result
    except Exception as e:
        logger.error(f"Log ingestion failed: {e}")
        raise HTTPException(status_code=500, detail="Ingestion failed")


# ============================================
# Query Endpoints (User Auth)
# ============================================

@router.post("/query", response_model=LogQueryResponse)
async def query_logs(
    query: LogQuery,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Query logs with filtering, full-text search, and pagination.

    Supports:
    - Full-text search in message, source, service
    - Filter by log level, source, service, host, tags
    - Time range filtering
    - Field-based filtering
    """
    try:
        if settings.CLICKHOUSE_ENABLED:
            # Query from ClickHouse - levels must be uppercase to match stored data
            levels = [l.value.upper() for l in query.levels] if query.levels else None
            host_id = query.host_ids[0] if query.host_ids else None
            result = await search_logs_from_clickhouse(
                organization_id=current_user.organization_id,
                start_time=query.start_time,
                end_time=query.end_time,
                query=query.query,
                levels=levels,
                services=query.services,
                host_id=host_id,
                limit=query.limit,
                offset=query.offset
            )
            return result
        else:
            return await log_service.query_logs(query, current_user.organization_id, db)
    except Exception as e:
        logger.error(f"Log query failed: {e}")
        raise HTTPException(status_code=500, detail="Query failed")

@router.get("/search")
async def search_logs(
    q: Optional[str] = Query(None, description="Search query"),
    start: Optional[str] = Query(None, description="Start time (ISO format)"),
    end: Optional[str] = Query(None, description="End time (ISO format)"),
    levels: Optional[str] = Query(None, description="Comma-separated log levels"),
    sources: Optional[str] = Query(None, description="Comma-separated sources"),
    host_ids: Optional[str] = Query(None, description="Comma-separated host IDs"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Search logs with query parameters (alternative to POST /query).
    More convenient for simple queries and URL sharing.
    """
    # Parse time range
    now = datetime.utcnow()
    end_time = datetime.fromisoformat(end) if end else now
    start_time = datetime.fromisoformat(start) if start else (now - timedelta(hours=1))

    # Parse levels
    level_list = None
    if levels:
        level_list = [LogLevel(l.strip()) for l in levels.split(",")]

    # Parse sources and host_ids
    source_list = [s.strip() for s in sources.split(",")] if sources else None
    host_list = [h.strip() for h in host_ids.split(",")] if host_ids else None

    try:
        if settings.CLICKHOUSE_ENABLED:
            # Query from ClickHouse - levels must be uppercase to match stored data
            levels = [l.value.upper() for l in level_list] if level_list else None
            host_id = host_list[0] if host_list else None
            result = await search_logs_from_clickhouse(
                organization_id=current_user.organization_id,
                start_time=start_time,
                end_time=end_time,
                query=q,
                levels=levels,
                services=source_list,
                host_id=host_id,
                limit=limit,
                offset=offset
            )
            return result
        else:
            query = LogQuery(
                query=q,
                start_time=start_time,
                end_time=end_time,
                levels=level_list,
                sources=source_list,
                host_ids=host_list,
                limit=limit,
                offset=offset,
                order=order
            )
            return await log_service.query_logs(query, current_user.organization_id, db)
    except Exception as e:
        logger.error(f"Log search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.get("/stats")
async def get_log_stats_simple(
    hours: int = Query(24, ge=1, le=168, description="Time range in hours"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get log statistics summary (alias for /stats/summary).
    Includes counts by level, source, and hourly histogram.
    """
    try:
        if settings.CLICKHOUSE_ENABLED:
            return await get_log_stats_from_clickhouse(
                current_user.organization_id, hours
            )
        else:
            return await log_service.get_log_stats(
                current_user.organization_id, db, hours
            )
    except Exception as e:
        logger.error(f"Error getting log stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve stats")

@router.get("/services")
async def get_log_services(
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get distinct services with log counts (alias for /stats/services)."""
    from sqlalchemy import select, func
    from app.models.log_entry import LogEntry

    since = datetime.utcnow() - timedelta(hours=hours)

    result = await db.execute(
        select(LogEntry.service, func.count(LogEntry.id))
        .where(
            LogEntry.organization_id == current_user.organization_id,
            LogEntry.timestamp >= since,
            LogEntry.service.isnot(None)
        )
        .group_by(LogEntry.service)
        .order_by(func.count(LogEntry.id).desc())
        .limit(100)
    )

    return {
        "services": [
            {"service": row[0], "count": row[1]}
            for row in result.fetchall()
        ]
    }

@router.get("/stats/summary", response_model=LogStats)
async def get_log_stats(
    hours: int = Query(24, ge=1, le=168, description="Time range in hours"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get log statistics summary.
    Includes counts by level, source, and hourly histogram.
    """
    try:
        if settings.CLICKHOUSE_ENABLED:
            return await get_log_stats_from_clickhouse(
                current_user.organization_id, hours
            )
        else:
            return await log_service.get_log_stats(
                current_user.organization_id, db, hours
            )
    except Exception as e:
        logger.error(f"Error getting log stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve stats")

@router.get("/stats/sources")
async def get_log_sources_stats(
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get distinct log sources with counts."""
    from sqlalchemy import select, func
    from app.models.log_entry import LogEntry

    since = datetime.utcnow() - timedelta(hours=hours)

    result = await db.execute(
        select(LogEntry.source, func.count(LogEntry.id))
        .where(
            LogEntry.organization_id == current_user.organization_id,
            LogEntry.timestamp >= since,
            LogEntry.source.isnot(None)
        )
        .group_by(LogEntry.source)
        .order_by(func.count(LogEntry.id).desc())
        .limit(100)
    )

    return {
        "sources": [
            {"source": row[0], "count": row[1]}
            for row in result.fetchall()
        ]
    }

@router.get("/stats/services")
async def get_log_services_stats(
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get distinct services with log counts."""
    from sqlalchemy import select, func
    from app.models.log_entry import LogEntry

    since = datetime.utcnow() - timedelta(hours=hours)

    result = await db.execute(
        select(LogEntry.service, func.count(LogEntry.id))
        .where(
            LogEntry.organization_id == current_user.organization_id,
            LogEntry.timestamp >= since,
            LogEntry.service.isnot(None)
        )
        .group_by(LogEntry.service)
        .order_by(func.count(LogEntry.id).desc())
        .limit(100)
    )

    return {
        "services": [
            {"service": row[0], "count": row[1]}
            for row in result.fetchall()
        ]
    }


# ============================================
# Log Source Management
# ============================================

@router.post("/sources", response_model=LogSourceResponse, status_code=201)
async def create_log_source(
    data: LogSourceCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Create a log source configuration.
    Defines which logs to collect from hosts.
    """
    try:
        source = await log_service.create_log_source(
            data, current_user.organization_id, db
        )
        return log_service._source_to_response(source)
    except Exception as e:
        logger.error(f"Error creating log source: {e}")
        raise HTTPException(status_code=500, detail="Failed to create log source")

@router.get("/sources", response_model=LogSourceListResponse)
async def list_log_sources(
    host_id: Optional[str] = Query(None, description="Filter by host ID"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """List all log source configurations."""
    try:
        return await log_service.list_log_sources(
            current_user.organization_id, db, host_id
        )
    except Exception as e:
        logger.error(f"Error listing log sources: {e}")
        raise HTTPException(status_code=500, detail="Failed to list log sources")

@router.get("/{log_id}")
async def get_log_entry(
    log_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get a single log entry by ID."""
    try:
        log_uuid = uuid.UUID(log_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid log ID")

    # Query single log
    query = LogQuery(
        start_time=datetime.min,
        end_time=datetime.max,
        limit=1
    )

    # Use direct query instead
    from sqlalchemy import select
    from app.models.log_entry import LogEntry

    result = await db.execute(
        select(LogEntry).where(
            LogEntry.id == log_uuid,
            LogEntry.organization_id == current_user.organization_id
        )
    )
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=404, detail="Log entry not found")

    return {
        "id": str(entry.id),
        "timestamp": entry.timestamp.isoformat(),
        "level": entry.level,
        "source": entry.source,
        "service": entry.service,
        "filename": entry.filename,
        "line_number": entry.line_number,
        "message": entry.message,
        "fields": entry.fields or {},
        "tags": entry.tags or [],
        "host_id": str(entry.host_id)
    }

@router.get("/{log_id}/context", response_model=LogContext)
async def get_log_context(
    log_id: str,
    lines: int = Query(10, ge=1, le=50, description="Number of context lines"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get a log entry with surrounding context (logs before and after).
    Useful for debugging and understanding the sequence of events.
    """
    try:
        log_uuid = uuid.UUID(log_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid log ID")

    context = await log_service.get_log_context(
        log_uuid, current_user.organization_id, db, lines
    )

    if not context:
        raise HTTPException(status_code=404, detail="Log entry not found")

    return context


# ============================================
# Statistics
# ============================================

@router.patch("/sources/{source_id}", response_model=LogSourceResponse)
async def update_log_source(
    source_id: str,
    data: LogSourceUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update a log source configuration."""
    try:
        source_uuid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid source ID")

    source = await log_service.update_log_source(
        source_uuid, current_user.organization_id, data, db
    )

    if not source:
        raise HTTPException(status_code=404, detail="Log source not found")

    return log_service._source_to_response(source)

@router.delete("/sources/{source_id}")
async def delete_log_source(
    source_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Delete a log source configuration."""
    try:
        source_uuid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid source ID")

    success = await log_service.delete_log_source(
        source_uuid, current_user.organization_id, db
    )

    if not success:
        raise HTTPException(status_code=404, detail="Log source not found")

    return {"status": "deleted", "source_id": source_id}
