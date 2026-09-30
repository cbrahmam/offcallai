# backend/app/api/v1/endpoints/maintenance_windows.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID
import logging

from app.database import get_async_session
from app.core.security import get_current_user
from app.models.user import User
from app.services.maintenance_window_service import MaintenanceWindowService
from app.schemas.maintenance_window import (
    MaintenanceWindowCreate,
    MaintenanceWindowUpdate,
    MaintenanceWindowResponse,
    MaintenanceWindowListResponse,
    MaintenanceCheckResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=MaintenanceWindowListResponse)
async def list_maintenance_windows(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    include_past: bool = Query(False, description="Include past maintenance windows"),
    include_cancelled: bool = Query(False, description="Include cancelled windows"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """List all maintenance windows for the organization"""
    service = MaintenanceWindowService(db)

    windows, total = await service.list_windows(
        organization_id=current_user.organization_id,
        page=page,
        per_page=per_page,
        include_past=include_past,
        include_cancelled=include_cancelled
    )

    return MaintenanceWindowListResponse(
        windows=[service.to_response(w) for w in windows],
        total=total,
        page=page,
        per_page=per_page
    )


@router.post("/", response_model=MaintenanceWindowResponse, status_code=201)
async def create_maintenance_window(
    data: MaintenanceWindowCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Create a new maintenance window"""
    # Validate time range
    if data.end_time <= data.start_time:
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time"
        )

    service = MaintenanceWindowService(db)

    window = await service.create_window(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        data=data
    )

    return service.to_response(window, created_by_name=current_user.full_name)


@router.get("/active", response_model=list[MaintenanceWindowResponse])
async def get_active_maintenance_windows(
    service_name: Optional[str] = Query(None, description="Filter by service name"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get currently active maintenance windows"""
    service = MaintenanceWindowService(db)

    windows = await service.get_active_windows(
        organization_id=current_user.organization_id,
        service=service_name
    )

    return [service.to_response(w) for w in windows]


@router.get("/upcoming", response_model=list[MaintenanceWindowResponse])
async def get_upcoming_maintenance_windows(
    hours: int = Query(24, ge=1, le=168, description="Hours to look ahead"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get upcoming maintenance windows"""
    service = MaintenanceWindowService(db)

    windows = await service.get_upcoming_windows(
        organization_id=current_user.organization_id,
        hours_ahead=hours
    )

    return [service.to_response(w) for w in windows]


@router.get("/check", response_model=MaintenanceCheckResponse)
async def check_maintenance_status(
    service_name: str = Query(..., description="Service name to check"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Check if a service is currently in a maintenance window"""
    mw_service = MaintenanceWindowService(db)

    in_maintenance, windows = await mw_service.is_service_in_maintenance(
        organization_id=current_user.organization_id,
        service=service_name
    )

    if in_maintenance:
        return MaintenanceCheckResponse(
            in_maintenance=True,
            active_windows=[mw_service.to_response(w) for w in windows],
            message=f"Service '{service_name}' is currently in maintenance"
        )

    return MaintenanceCheckResponse(
        in_maintenance=False,
        active_windows=[],
        message=f"Service '{service_name}' is not in maintenance"
    )


@router.get("/{window_id}", response_model=MaintenanceWindowResponse)
async def get_maintenance_window(
    window_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get a specific maintenance window"""
    service = MaintenanceWindowService(db)

    window = await service.get_window(
        window_id=window_id,
        organization_id=current_user.organization_id
    )

    if not window:
        raise HTTPException(status_code=404, detail="Maintenance window not found")

    return service.to_response(window)


@router.patch("/{window_id}", response_model=MaintenanceWindowResponse)
async def update_maintenance_window(
    window_id: UUID,
    data: MaintenanceWindowUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Update a maintenance window"""
    service = MaintenanceWindowService(db)

    # Validate time range if both provided
    if data.start_time and data.end_time:
        if data.end_time <= data.start_time:
            raise HTTPException(
                status_code=400,
                detail="End time must be after start time"
            )

    window = await service.update_window(
        window_id=window_id,
        organization_id=current_user.organization_id,
        data=data
    )

    if not window:
        raise HTTPException(status_code=404, detail="Maintenance window not found")

    return service.to_response(window)


@router.post("/{window_id}/cancel", response_model=MaintenanceWindowResponse)
async def cancel_maintenance_window(
    window_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Cancel a maintenance window"""
    service = MaintenanceWindowService(db)

    window = await service.cancel_window(
        window_id=window_id,
        organization_id=current_user.organization_id,
        user_id=current_user.id
    )

    if not window:
        raise HTTPException(status_code=404, detail="Maintenance window not found")

    return service.to_response(window)


@router.delete("/{window_id}", status_code=204)
async def delete_maintenance_window(
    window_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Permanently delete a maintenance window"""
    service = MaintenanceWindowService(db)

    deleted = await service.delete_window(
        window_id=window_id,
        organization_id=current_user.organization_id
    )

    if not deleted:
        raise HTTPException(status_code=404, detail="Maintenance window not found")

    return None
