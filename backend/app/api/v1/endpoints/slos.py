# backend/app/api/v1/endpoints/slos.py
"""SLO/SLI Tracking API endpoints - Premium Feature"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel
from datetime import datetime

from app.database import get_async_session
from app.core.security import get_current_user
from app.models.user import User
from app.services.slo_service import SLOService

router = APIRouter(prefix="/slos", tags=["slos"])


# Schemas
class SLOCreate(BaseModel):
    name: str
    slo_type: str  # availability, latency, error_rate, throughput
    target_percentage: int  # e.g., 9990 for 99.90%
    service_id: Optional[UUID] = None
    description: Optional[str] = None
    target_value: Optional[int] = None  # For latency: ms
    measurement_window: str = "30d"
    error_budget_policy: Optional[str] = None
    alert_threshold_warning: int = 5000
    alert_threshold_critical: int = 8000


class SLOUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target_percentage: Optional[int] = None
    target_value: Optional[int] = None
    measurement_window: Optional[str] = None
    error_budget_policy: Optional[str] = None
    alert_threshold_warning: Optional[int] = None
    alert_threshold_critical: Optional[int] = None
    is_active: Optional[bool] = None


class SLIRecordCreate(BaseModel):
    total_requests: int
    good_requests: int
    period: str = "1h"
    timestamp: Optional[datetime] = None
    p50_latency_ms: Optional[int] = None
    p95_latency_ms: Optional[int] = None
    p99_latency_ms: Optional[int] = None


# Endpoints
@router.get("/")
async def list_slos(
    service_id: Optional[UUID] = None,
    slo_type: Optional[str] = None,
    is_active: bool = True,
    is_breached: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """List all SLOs"""
    service = SLOService(db)
    slos, total = await service.list_slos(
        organization_id=current_user.organization_id,
        service_id=service_id,
        slo_type=slo_type,
        is_active=is_active,
        is_breached=is_breached,
        skip=skip,
        limit=limit
    )

    return {
        "slos": [
            {
                "id": str(s.id),
                "name": s.name,
                "description": s.description,
                "slo_type": s.slo_type,
                "target_percentage": s.target_percentage / 100,
                "target_value": s.target_value,
                "measurement_window": s.measurement_window,
                "current_percentage": (s.current_percentage or 0) / 100,
                "error_budget_remaining": (s.error_budget_remaining or 0) / 100,
                "error_budget_consumed": (s.error_budget_consumed or 0) / 100,
                "is_breached": s.is_breached,
                "is_active": s.is_active,
                "service_id": str(s.service_id) if s.service_id else None,
                "service_name": s.service.name if s.service else None,
                "last_calculated_at": s.last_calculated_at.isoformat() if s.last_calculated_at else None,
                "created_at": s.created_at.isoformat() if s.created_at else None
            }
            for s in slos
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/summary")
async def get_slo_summary(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get SLO summary for dashboard"""
    service = SLOService(db)
    return await service.get_slo_summary(current_user.organization_id)


@router.post("/")
async def create_slo(
    data: SLOCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new SLO"""
    service = SLOService(db)
    slo = await service.create_slo(
        organization_id=current_user.organization_id,
        **data.model_dump()
    )
    return {"id": str(slo.id), "message": "SLO created"}


@router.get("/{slo_id}")
async def get_slo(
    slo_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get an SLO by ID"""
    service = SLOService(db)
    slo = await service.get_slo(slo_id, current_user.organization_id)
    if not slo:
        raise HTTPException(status_code=404, detail="SLO not found")

    # Get burn rate
    burn_data = await service.get_error_budget_burn_rate(slo_id)

    return {
        "id": str(slo.id),
        "name": slo.name,
        "description": slo.description,
        "slo_type": slo.slo_type,
        "target_percentage": slo.target_percentage / 100,
        "target_value": slo.target_value,
        "measurement_window": slo.measurement_window,
        "error_budget_policy": slo.error_budget_policy,
        "current_percentage": (slo.current_percentage or 0) / 100,
        "error_budget_remaining": (slo.error_budget_remaining or 0) / 100,
        "error_budget_consumed": (slo.error_budget_consumed or 0) / 100,
        "burn_rate": burn_data.get("burn_rate"),
        "projected_exhaustion_hours": burn_data.get("projected_exhaustion_hours"),
        "alert_threshold_warning": slo.alert_threshold_warning / 100,
        "alert_threshold_critical": slo.alert_threshold_critical / 100,
        "is_breached": slo.is_breached,
        "is_active": slo.is_active,
        "service_id": str(slo.service_id) if slo.service_id else None,
        "service_name": slo.service.name if slo.service else None,
        "last_calculated_at": slo.last_calculated_at.isoformat() if slo.last_calculated_at else None,
        "created_at": slo.created_at.isoformat() if slo.created_at else None,
        "updated_at": slo.updated_at.isoformat() if slo.updated_at else None
    }


@router.patch("/{slo_id}")
async def update_slo(
    slo_id: UUID,
    data: SLOUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update an SLO"""
    service = SLOService(db)
    updated = await service.update_slo(
        slo_id, current_user.organization_id,
        **data.model_dump(exclude_unset=True)
    )
    if not updated:
        raise HTTPException(status_code=404, detail="SLO not found")
    return {"message": "SLO updated"}


@router.delete("/{slo_id}")
async def delete_slo(
    slo_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Delete an SLO"""
    service = SLOService(db)
    deleted = await service.delete_slo(slo_id, current_user.organization_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="SLO not found")
    return {"message": "SLO deleted"}


# SLI Records
@router.post("/{slo_id}/records")
async def record_sli(
    slo_id: UUID,
    data: SLIRecordCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Record an SLI measurement"""
    service = SLOService(db)

    # Verify SLO exists
    slo = await service.get_slo(slo_id, current_user.organization_id)
    if not slo:
        raise HTTPException(status_code=404, detail="SLO not found")

    record = await service.record_sli(
        slo_id=slo_id,
        **data.model_dump()
    )
    return {"id": str(record.id), "sli_value": record.sli_value / 100}


@router.get("/{slo_id}/records")
async def get_sli_records(
    slo_id: UUID,
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get SLI records for an SLO"""
    service = SLOService(db)

    # Verify SLO exists
    slo = await service.get_slo(slo_id, current_user.organization_id)
    if not slo:
        raise HTTPException(status_code=404, detail="SLO not found")

    from datetime import timedelta
    start_date = datetime.utcnow() - timedelta(days=days)
    records = await service.get_sli_records(slo_id, start_date=start_date)

    return {
        "records": [
            {
                "id": str(r.id),
                "timestamp": r.timestamp.isoformat(),
                "period": r.period,
                "total_requests": r.total_requests,
                "good_requests": r.good_requests,
                "bad_requests": r.bad_requests,
                "sli_value": r.sli_value / 100,
                "p50_latency_ms": r.p50_latency_ms,
                "p95_latency_ms": r.p95_latency_ms,
                "p99_latency_ms": r.p99_latency_ms
            }
            for r in records
        ]
    }


@router.get("/{slo_id}/burn-rate")
async def get_burn_rate(
    slo_id: UUID,
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get error budget burn rate"""
    service = SLOService(db)

    # Verify SLO exists
    slo = await service.get_slo(slo_id, current_user.organization_id)
    if not slo:
        raise HTTPException(status_code=404, detail="SLO not found")

    return await service.get_error_budget_burn_rate(slo_id, hours)
