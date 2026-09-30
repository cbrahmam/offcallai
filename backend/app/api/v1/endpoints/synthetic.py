# backend/app/api/v1/endpoints/synthetic.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta

from app.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.synthetic_service import SyntheticService
from app.schemas.synthetic import (
    SyntheticCheckCreate, SyntheticCheckUpdate, SyntheticCheckResponse, SyntheticCheckList,
    SyntheticCheckResultResponse, SyntheticCheckResultList,
    SyntheticLocationResponse, SyntheticLocationList,
    SyntheticStats, CheckOverview, RunCheckRequest
)

router = APIRouter()


# ==================== Check Endpoints ====================

@router.post("/checks", response_model=SyntheticCheckResponse)
async def create_check(
    data: SyntheticCheckCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new synthetic check"""
    service = SyntheticService(db)
    check = await service.create_check(
        current_user.organization_id,
        data,
        current_user.id
    )
    return check


@router.get("/checks", response_model=SyntheticCheckList)
async def list_checks(
    check_type: Optional[str] = None,
    status: Optional[str] = None,
    current_status: Optional[str] = None,
    service_id: Optional[UUID] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List synthetic checks"""
    service = SyntheticService(db)
    checks, total = await service.list_checks(
        current_user.organization_id,
        check_type=check_type,
        status=status,
        current_status=current_status,
        service_id=service_id,
        page=page,
        page_size=page_size
    )
    return SyntheticCheckList(items=checks, total=total, page=page, page_size=page_size)


@router.get("/checks/{check_id}", response_model=SyntheticCheckResponse)
async def get_check(
    check_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a synthetic check by ID"""
    service = SyntheticService(db)
    check = await service.get_check(current_user.organization_id, check_id)
    if not check:
        raise HTTPException(status_code=404, detail="Check not found")
    return check


@router.put("/checks/{check_id}", response_model=SyntheticCheckResponse)
async def update_check(
    check_id: UUID,
    data: SyntheticCheckUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a synthetic check"""
    service = SyntheticService(db)
    check = await service.update_check(current_user.organization_id, check_id, data)
    if not check:
        raise HTTPException(status_code=404, detail="Check not found")
    return check


@router.delete("/checks/{check_id}")
async def delete_check(
    check_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a synthetic check"""
    service = SyntheticService(db)
    deleted = await service.delete_check(current_user.organization_id, check_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Check not found")
    return {"status": "deleted"}


@router.post("/checks/{check_id}/toggle", response_model=SyntheticCheckResponse)
async def toggle_check(
    check_id: UUID,
    status: str = Query(..., regex="^(active|paused|disabled)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Change check status (active/paused/disabled)"""
    service = SyntheticService(db)
    check = await service.toggle_check(current_user.organization_id, check_id, status)
    if not check:
        raise HTTPException(status_code=404, detail="Check not found")
    return check


@router.post("/checks/{check_id}/run", response_model=SyntheticCheckResultResponse)
async def run_check(
    check_id: UUID,
    request: Optional[RunCheckRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Manually run a synthetic check"""
    service = SyntheticService(db)
    try:
        result = await service.execute_check(
            current_user.organization_id,
            check_id,
            location="manual"
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/checks/{check_id}/overview", response_model=CheckOverview)
async def get_check_overview(
    check_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get detailed overview of a check including recent results"""
    service = SyntheticService(db)

    check = await service.get_check(current_user.organization_id, check_id)
    if not check:
        raise HTTPException(status_code=404, detail="Check not found")

    # Get recent results
    results, _ = await service.list_results(
        current_user.organization_id,
        check_id=check_id,
        page_size=50
    )

    return CheckOverview(
        check=check,
        recent_results=results,
        uptime_history=[],
        response_time_history=[],
        active_incidents=[]
    )


# ==================== Results Endpoints ====================

@router.get("/results", response_model=SyntheticCheckResultList)
async def list_results(
    check_id: Optional[UUID] = None,
    status: Optional[str] = None,
    location: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List check results"""
    service = SyntheticService(db)
    results, total = await service.list_results(
        current_user.organization_id,
        check_id=check_id,
        status=status,
        location=location,
        since=since,
        until=until,
        page=page,
        page_size=page_size
    )
    return SyntheticCheckResultList(items=results, total=total, page=page, page_size=page_size)


@router.get("/results/{result_id}", response_model=SyntheticCheckResultResponse)
async def get_result(
    result_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a check result by ID"""
    service = SyntheticService(db)
    result = await service.get_result(current_user.organization_id, result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result


# ==================== Locations Endpoints ====================

@router.get("/locations", response_model=SyntheticLocationList)
async def list_locations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List available synthetic check locations"""
    service = SyntheticService(db)
    locations, total = await service.list_locations()
    return SyntheticLocationList(items=locations, total=total)


# ==================== Statistics Endpoints ====================

@router.get("/stats", response_model=SyntheticStats)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get synthetic monitoring statistics"""
    service = SyntheticService(db)
    return await service.get_stats(current_user.organization_id)
