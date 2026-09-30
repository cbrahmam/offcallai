# backend/app/api/v1/endpoints/traces.py
"""
APM/Tracing API endpoints for distributed trace ingestion and querying.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import datetime, timedelta
from uuid import UUID
import logging

from app.database import get_db
from app.core.config import settings
from app.services.trace_service import trace_service
from app.schemas.trace import (
    SpanBatch,
    SpanIngestResponse,
    TraceQuery,
    TraceResponse,
    TraceListResponse,
    ServiceListResponse,
    ServiceOperations,
    ServiceMap,
    SpanResponse,
)
from app.api.deps import get_current_user, get_current_organization, get_api_key_host
from app.models.user import User
from app.models.organization import Organization
from app.models.host import Host

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================
# List Endpoint (convenience route)
# ============================================

@router.get("/")
async def list_traces(
    limit: int = Query(50, ge=1, le=1000, description="Number of traces to return"),
    service: Optional[str] = Query(None, description="Filter by service name"),
    operation: Optional[str] = Query(None, description="Filter by operation name"),
    min_duration_ms: Optional[float] = Query(None, description="Minimum duration in ms"),
    has_error: Optional[bool] = Query(None, description="Filter to error traces only"),
    hours: int = Query(24, ge=1, le=168, description="Hours of history to search"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List recent traces with optional filtering.
    This is a convenience endpoint - for advanced queries use POST /query.
    """
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        if settings.CLICKHOUSE_ENABLED:
            from app.services.clickhouse_service import ClickHouseService
            ch = ClickHouseService()
            try:
                result = await ch.search_traces(
                    organization_id=str(current_user.organization_id),
                    start_time=start_time,
                    end_time=end_time,
                    service=service,
                    operation=operation,
                    min_duration_ms=min_duration_ms,
                    has_error=has_error,
                    limit=limit,
                    offset=0
                )
                return {
                    "traces": result.get("traces", []),
                    "total": result.get("total", 0),
                    "limit": limit,
                    "service": service,
                    "operation": operation,
                    "time_range": {"start": start_time.isoformat(), "end": end_time.isoformat()}
                }
            finally:
                await ch.close()
        else:
            # Fallback to PostgreSQL (traces table)
            response = await trace_service.query_traces(
                TraceQuery(
                    start_time=start_time,
                    end_time=end_time,
                    service=service,
                    operation=operation,
                    min_duration_ms=min_duration_ms,
                    has_error=has_error,
                    limit=limit,
                ),
                current_user.organization_id,
                db,
            )
            return {
                "traces": [t.model_dump() for t in response.traces],
                "total": response.total,
                "limit": limit
            }
    except Exception as e:
        logger.error(f"Error listing traces: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve traces: {str(e)}")


# ============================================
# ClickHouse Integration
# ============================================

async def write_spans_to_clickhouse(spans: List[dict], organization_id: UUID):
    """Background task to write spans to ClickHouse."""
    if not settings.CLICKHOUSE_ENABLED:
        return

    try:
        from app.services.clickhouse_service import clickhouse_service

        # Convert spans to ClickHouse format
        ch_spans = []
        for span in spans:
            ch_spans.append({
                "timestamp": span.get("start_time") or datetime.utcnow().isoformat(),
                "organization_id": str(organization_id),
                "trace_id": span["trace_id"],
                "span_id": span["span_id"],
                "parent_span_id": span.get("parent_span_id", ""),
                "service_name": span.get("service_name", ""),
                "operation_name": span.get("operation_name", ""),
                "span_kind": span.get("span_kind", "INTERNAL"),
                "duration_ms": span.get("duration_ms", 0),
                "status_code": span.get("status_code", "OK"),
                "status_message": span.get("status_message", ""),
                "attributes": span.get("attributes", {}),
                "events": span.get("events", "[]"),
                "links": span.get("links", "[]"),
            })

        await clickhouse_service.insert_spans(ch_spans)
        logger.debug(f"Wrote {len(ch_spans)} spans to ClickHouse")
    except Exception as e:
        logger.error(f"Failed to write spans to ClickHouse: {e}")


async def query_traces_from_clickhouse(
    organization_id: UUID,
    start_time: datetime,
    end_time: datetime,
    service: Optional[str] = None,
    operation: Optional[str] = None,
    min_duration_ms: Optional[float] = None,
    max_duration_ms: Optional[float] = None,
    has_error: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0
) -> dict:
    """Query traces from ClickHouse."""
    from app.services.clickhouse_service import ClickHouseService

    # Create fresh instance to avoid stale connection issues under load
    ch = ClickHouseService()
    try:
        return await ch.search_traces(
            organization_id=str(organization_id),
            start_time=start_time,
            end_time=end_time,
            service=service,
            operation=operation,
            min_duration_ms=min_duration_ms,
            max_duration_ms=max_duration_ms,
            has_error=has_error,
            limit=limit,
            offset=offset
        )
    finally:
        await ch.close()


async def get_trace_from_clickhouse(organization_id: UUID, trace_id: str) -> dict:
    """Get a single trace with all spans from ClickHouse."""
    from app.services.clickhouse_service import ClickHouseService

    ch = ClickHouseService()
    try:
        return await ch.get_trace(
            organization_id=str(organization_id),
            trace_id=trace_id
        )
    finally:
        await ch.close()


async def get_services_from_clickhouse(organization_id: UUID, hours: int = 24) -> dict:
    """Get service list from ClickHouse."""
    from app.services.clickhouse_service import ClickHouseService

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)

    ch = ClickHouseService()
    try:
        return await ch.get_services(
            organization_id=str(organization_id),
            start_time=start_time,
            end_time=end_time
        )
    finally:
        await ch.close()


async def get_service_map_from_clickhouse(organization_id: UUID, hours: int = 24) -> dict:
    """Get service dependency map from ClickHouse."""
    from app.services.clickhouse_service import ClickHouseService

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)

    ch = ClickHouseService()
    try:
        return await ch.get_service_map(
            organization_id=str(organization_id),
            start_time=start_time,
            end_time=end_time
        )
    finally:
        await ch.close()


# ============================================
# Agent Ingestion Endpoints
# ============================================

@router.post("/ingest", response_model=SpanIngestResponse)
async def ingest_spans(
    batch: SpanBatch,
    db: AsyncSession = Depends(get_db),
    host: Host = Depends(get_api_key_host),
):
    """
    Ingest a batch of spans from the agent.
    Requires API key authentication.
    Writes to ClickHouse (primary) for time-series data.
    """
    if settings.CLICKHOUSE_ENABLED:
        # Write to ClickHouse (primary for time-series)
        spans_data = [span.model_dump() for span in batch.spans]
        await write_spans_to_clickhouse(spans_data, host.organization_id)
        # Count unique trace IDs
        trace_ids = set(span.trace_id for span in batch.spans)
        return SpanIngestResponse(
            success=True,
            spans_received=len(batch.spans),
            spans_stored=len(batch.spans),
            traces_updated=len(trace_ids),
            host_id=str(host.id),
            errors=[]
        )
    else:
        # Fallback to PostgreSQL if ClickHouse not enabled
        result = await trace_service.ingest_spans(
            batch=batch,
            organization_id=host.organization_id,
            db=db,
        )
        return result


# ============================================
# Trace Query Endpoints
# ============================================

@router.post("/query", response_model=TraceListResponse)
async def query_traces(
    query: TraceQuery,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """
    Query traces with filters.
    """
    if settings.CLICKHOUSE_ENABLED:
        result = await query_traces_from_clickhouse(
            organization_id=organization.id,
            start_time=query.start_time,
            end_time=query.end_time,
            service=query.service,
            operation=query.operation,
            min_duration_ms=query.min_duration_ms,
            max_duration_ms=query.max_duration_ms,
            has_error=query.has_error,
            limit=query.limit,
            offset=query.offset
        )
        return result
    else:
        result = await trace_service.query_traces(
            query=query,
            organization_id=organization.id,
            db=db,
        )
        return result


@router.get("/search", response_model=TraceListResponse)
async def search_traces(
    start_time: Optional[datetime] = Query(None, description="Start time filter"),
    end_time: Optional[datetime] = Query(None, description="End time filter"),
    service: Optional[str] = Query(None, description="Filter by service name"),
    operation: Optional[str] = Query(None, description="Filter by operation name"),
    min_duration_ms: Optional[float] = Query(None, description="Minimum duration in ms"),
    max_duration_ms: Optional[float] = Query(None, description="Maximum duration in ms"),
    has_error: Optional[bool] = Query(None, description="Filter by error status"),
    limit: int = Query(50, ge=1, le=200, description="Number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """
    Search traces with query parameters.
    If no time range specified, defaults to last 24 hours.
    """
    # Default time range
    if not end_time:
        end_time = datetime.utcnow()
    if not start_time:
        start_time = end_time - timedelta(hours=24)

    if settings.CLICKHOUSE_ENABLED:
        result = await query_traces_from_clickhouse(
            organization_id=organization.id,
            start_time=start_time,
            end_time=end_time,
            service=service,
            operation=operation,
            min_duration_ms=min_duration_ms,
            max_duration_ms=max_duration_ms,
            has_error=has_error,
            limit=limit,
            offset=offset
        )
        return result
    else:
        query = TraceQuery(
            start_time=start_time,
            end_time=end_time,
            service=service,
            operation=operation,
            min_duration_ms=min_duration_ms,
            max_duration_ms=max_duration_ms,
            has_error=has_error,
            limit=limit,
            offset=offset,
        )
        result = await trace_service.query_traces(
            query=query,
            organization_id=organization.id,
            db=db,
        )
        return result


@router.get("/{trace_id}", response_model=TraceResponse)
async def get_trace(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """
    Get a single trace with all its spans.
    """
    if settings.CLICKHOUSE_ENABLED:
        trace = await get_trace_from_clickhouse(
            organization_id=organization.id,
            trace_id=trace_id
        )
    else:
        trace = await trace_service.get_trace(
            trace_id=trace_id,
            organization_id=organization.id,
            db=db,
        )

    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")

    return trace


# ============================================
# Service Endpoints
# ============================================

@router.get("/services/list", response_model=ServiceListResponse)
async def get_services(
    hours: int = Query(24, ge=1, le=168, description="Time range in hours"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """
    Get list of services with metrics.
    """
    if settings.CLICKHOUSE_ENABLED:
        result = await get_services_from_clickhouse(
            organization_id=organization.id,
            hours=hours
        )
        return result
    else:
        result = await trace_service.get_services(
            organization_id=organization.id,
            db=db,
            hours=hours,
        )
        return result


@router.get("/services/{service_name}/operations", response_model=ServiceOperations)
async def get_service_operations(
    service_name: str,
    hours: int = Query(24, ge=1, le=168, description="Time range in hours"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """
    Get operations for a specific service with metrics.
    """
    result = await trace_service.get_service_operations(
        service_name=service_name,
        organization_id=organization.id,
        db=db,
        hours=hours,
    )
    return result


@router.get("/services/map", response_model=ServiceMap)
async def get_service_map(
    hours: int = Query(24, ge=1, le=168, description="Time range in hours"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """
    Get service dependency map showing how services connect.
    """
    if settings.CLICKHOUSE_ENABLED:
        result = await get_service_map_from_clickhouse(
            organization_id=organization.id,
            hours=hours
        )
        return result
    else:
        result = await trace_service.get_service_map(
            organization_id=organization.id,
            db=db,
            hours=hours,
        )
        return result


# ============================================
# Span Details Endpoint
# ============================================

@router.get("/spans/{span_id}", response_model=SpanResponse)
async def get_span(
    span_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """
    Get a single span by span_id.
    """
    span = await trace_service.get_span(
        span_id=span_id,
        organization_id=organization.id,
        db=db,
    )

    if not span:
        raise HTTPException(status_code=404, detail="Span not found")

    return span
