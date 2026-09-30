# backend/app/api/v1/endpoints/databases.py
"""
Database monitoring API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime
from uuid import UUID

from app.database import get_db
from app.services.database_monitor_service import database_monitor_service
from app.schemas.database_monitor import (
    DatabaseInstanceCreate, DatabaseInstanceUpdate, DatabaseInstanceResponse, DatabaseInstanceListResponse,
    DatabaseSummary, DatabaseQueryResponse, DatabaseQueryListResponse, QueryFilter,
    MetricSnapshotListResponse,
    DatabaseAlertResponse, DatabaseAlertListResponse, AlertAcknowledge,
    DatabaseMetricsReport, QueryStatsReport, MetricsIngestResponse
)
from app.api.deps import get_current_user, get_current_organization, get_api_key_host
from app.models.user import User
from app.models.organization import Organization
from app.models.host import Host

router = APIRouter()


# ============================================
# Instance Endpoints
# ============================================

@router.post("/instances", response_model=DatabaseInstanceResponse)
async def create_instance(
    data: DatabaseInstanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Create a new database instance for monitoring."""
    result = await database_monitor_service.create_instance(
        data=data,
        organization_id=organization.id,
        db=db
    )
    return result


@router.get("/instances", response_model=DatabaseInstanceListResponse)
async def list_instances(
    database_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """List all database instances."""
    result = await database_monitor_service.list_instances(
        organization_id=organization.id,
        db=db,
        database_type=database_type,
        status=status,
        limit=limit,
        offset=offset
    )
    return result


@router.get("/summary", response_model=DatabaseSummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get summary statistics for all database instances."""
    result = await database_monitor_service.get_summary(
        organization_id=organization.id,
        db=db
    )
    return result


@router.get("/instances/{instance_id}", response_model=DatabaseInstanceResponse)
async def get_instance(
    instance_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get a database instance by ID."""
    result = await database_monitor_service.get_instance(
        instance_id=instance_id,
        organization_id=organization.id,
        db=db
    )
    if not result:
        raise HTTPException(status_code=404, detail="Database instance not found")
    return result


@router.patch("/instances/{instance_id}", response_model=DatabaseInstanceResponse)
async def update_instance(
    instance_id: UUID,
    data: DatabaseInstanceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Update a database instance."""
    result = await database_monitor_service.update_instance(
        instance_id=instance_id,
        data=data,
        organization_id=organization.id,
        db=db
    )
    if not result:
        raise HTTPException(status_code=404, detail="Database instance not found")
    return result


@router.delete("/instances/{instance_id}")
async def delete_instance(
    instance_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Delete a database instance."""
    success = await database_monitor_service.delete_instance(
        instance_id=instance_id,
        organization_id=organization.id,
        db=db
    )
    if not success:
        raise HTTPException(status_code=404, detail="Database instance not found")
    return {"message": "Database instance deleted successfully"}


# ============================================
# Query Endpoints
# ============================================

@router.get("/queries", response_model=DatabaseQueryListResponse)
async def list_queries(
    instance_id: Optional[UUID] = Query(None),
    database_name: Optional[str] = Query(None),
    query_type: Optional[str] = Query(None),
    is_slow: Optional[bool] = Query(None),
    min_avg_time_ms: Optional[float] = Query(None),
    min_call_count: Optional[int] = Query(None),
    order_by: str = Query("total_time_ms"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """List database queries with filtering."""
    filter_data = QueryFilter(
        instance_id=instance_id,
        database_name=database_name,
        query_type=query_type,
        is_slow=is_slow,
        min_avg_time_ms=min_avg_time_ms,
        min_call_count=min_call_count
    )
    result = await database_monitor_service.list_queries(
        organization_id=organization.id,
        db=db,
        filter_data=filter_data,
        order_by=order_by,
        limit=limit,
        offset=offset
    )
    return result


@router.get("/queries/{query_id}", response_model=DatabaseQueryResponse)
async def get_query(
    query_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get a query by ID."""
    result = await database_monitor_service.get_query(
        query_id=query_id,
        organization_id=organization.id,
        db=db
    )
    if not result:
        raise HTTPException(status_code=404, detail="Query not found")
    return result


# ============================================
# Metrics Endpoints
# ============================================

@router.get("/instances/{instance_id}/metrics", response_model=MetricSnapshotListResponse)
async def get_metrics_history(
    instance_id: UUID,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get metrics history for a database instance."""
    result = await database_monitor_service.get_metrics_history(
        instance_id=instance_id,
        organization_id=organization.id,
        db=db,
        start_time=start_time,
        end_time=end_time,
        limit=limit
    )
    return result


# ============================================
# Alert Endpoints
# ============================================

@router.get("/alerts", response_model=DatabaseAlertListResponse)
async def list_alerts(
    instance_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """List database alerts."""
    result = await database_monitor_service.list_alerts(
        organization_id=organization.id,
        db=db,
        instance_id=instance_id,
        status=status,
        severity=severity,
        limit=limit,
        offset=offset
    )
    return result


@router.post("/alerts/{alert_id}/acknowledge", response_model=DatabaseAlertResponse)
async def acknowledge_alert(
    alert_id: UUID,
    data: AlertAcknowledge,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Acknowledge an alert."""
    result = await database_monitor_service.acknowledge_alert(
        alert_id=alert_id,
        user_id=current_user.id,
        organization_id=organization.id,
        db=db,
        comment=data.comment
    )
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return result


@router.post("/alerts/{alert_id}/resolve", response_model=DatabaseAlertResponse)
async def resolve_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Resolve an alert."""
    result = await database_monitor_service.resolve_alert(
        alert_id=alert_id,
        organization_id=organization.id,
        db=db
    )
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return result


# ============================================
# Data Ingestion Endpoints (for agent)
# ============================================

@router.post("/instances/{instance_id}/metrics", response_model=MetricsIngestResponse)
async def ingest_metrics(
    instance_id: UUID,
    report: DatabaseMetricsReport,
    db: AsyncSession = Depends(get_db),
    host: Host = Depends(get_api_key_host),
):
    """Ingest metrics from monitoring agent."""
    result = await database_monitor_service.ingest_metrics(
        instance_id=instance_id,
        report=report,
        organization_id=host.organization_id,
        db=db
    )
    return result


@router.post("/instances/{instance_id}/queries")
async def ingest_query_stats(
    instance_id: UUID,
    report: QueryStatsReport,
    db: AsyncSession = Depends(get_db),
    host: Host = Depends(get_api_key_host),
):
    """Ingest query statistics from monitoring agent."""
    result = await database_monitor_service.ingest_query_stats(
        instance_id=instance_id,
        report=report,
        organization_id=host.organization_id,
        db=db
    )
    return result
