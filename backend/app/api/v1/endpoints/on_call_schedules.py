"""
API endpoints for on-call schedule management.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import uuid
from datetime import datetime
import logging

from app.database import get_async_session
from app.core.security import get_current_user
from app.models.user import User
from app.models.audit_log import AuditLog
from app.services.on_call_service import on_call_service
from app.schemas.on_call_schedule import (
    OnCallScheduleCreate, OnCallScheduleUpdate, OnCallScheduleResponse,
    OnCallScheduleListResponse, OnCallShiftCreate, OnCallShiftUpdate,
    OnCallShiftResponse, CurrentOnCallResponse, OnCallUsersListResponse,
    UserSummary, TeamSummary, EscalationPolicySummary
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ============== Schedule CRUD ==============

@router.get("/", response_model=OnCallScheduleListResponse)
async def list_schedules(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    team_id: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """List all on-call schedules for organization."""
    try:
        schedules, total = await on_call_service.list_schedules(
            organization_id=current_user.organization_id,
            db=db,
            page=page,
            per_page=per_page,
            team_id=team_id,
            is_active=is_active,
            search=search
        )

        total_pages = (total + per_page - 1) // per_page if total > 0 else 0

        return OnCallScheduleListResponse(
            schedules=[_schedule_to_response(s) for s in schedules],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
    except Exception as e:
        logger.error(f"Error listing schedules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=OnCallScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    data: OnCallScheduleCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new on-call schedule."""
    try:
        schedule = await on_call_service.create_schedule(data, current_user, db)

        # Audit log
        audit = AuditLog(
            id=uuid.uuid4(),
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            action="on_call_schedule_created",
            description=f"Created on-call schedule: {data.name}",
            details={"schedule_id": str(schedule.id), "shifts_count": len(data.shifts)},
            created_at=datetime.utcnow()
        )
        db.add(audit)
        await db.commit()

        return _schedule_to_response(schedule)

    except Exception as e:
        logger.error(f"Error creating schedule: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/on-call/all", response_model=OnCallUsersListResponse)
async def get_all_on_call_users(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get all users currently on-call across all schedules."""
    try:
        on_call_users = await on_call_service.get_all_on_call_users(
            current_user.organization_id,
            db
        )

        return OnCallUsersListResponse(
            users=on_call_users,
            total=len(on_call_users)
        )
    except Exception as e:
        logger.error(f"Error getting on-call users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync-status")
async def sync_on_call_status(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Sync User.is_currently_on_call for all users based on schedules. Admin only."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        updated_count = await on_call_service.sync_user_on_call_status(
            current_user.organization_id,
            db
        )

        return {"message": f"Synced on-call status for {updated_count} users", "updated_count": updated_count}
    except Exception as e:
        logger.error(f"Error syncing on-call status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{schedule_id}", response_model=OnCallScheduleResponse)
async def get_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get a specific on-call schedule."""
    try:
        schedule = await on_call_service.get_schedule(
            uuid.UUID(schedule_id),
            current_user.organization_id,
            db
        )

        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")

        return _schedule_to_response(schedule)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting schedule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{schedule_id}", response_model=OnCallScheduleResponse)
async def update_schedule(
    schedule_id: str,
    data: OnCallScheduleUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update an on-call schedule."""
    try:
        schedule = await on_call_service.update_schedule(
            uuid.UUID(schedule_id),
            data,
            current_user,
            db
        )

        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")

        # Audit log
        audit = AuditLog(
            id=uuid.uuid4(),
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            action="on_call_schedule_updated",
            description=f"Updated on-call schedule: {schedule.name}",
            details={"schedule_id": str(schedule.id)},
            created_at=datetime.utcnow()
        )
        db.add(audit)
        await db.commit()

        return _schedule_to_response(schedule)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating schedule: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Delete an on-call schedule."""
    try:
        success = await on_call_service.delete_schedule(
            uuid.UUID(schedule_id),
            current_user,
            db
        )

        if not success:
            raise HTTPException(status_code=404, detail="Schedule not found")

        # Audit log
        audit = AuditLog(
            id=uuid.uuid4(),
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            action="on_call_schedule_deleted",
            description=f"Deleted on-call schedule",
            details={"schedule_id": schedule_id},
            created_at=datetime.utcnow()
        )
        db.add(audit)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting schedule: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{schedule_id}/on-call", response_model=CurrentOnCallResponse)
async def get_current_on_call_for_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get who is currently on-call for a specific schedule."""
    try:
        schedule = await on_call_service.get_schedule(
            uuid.UUID(schedule_id),
            current_user.organization_id,
            db
        )

        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")

        on_call_users = await on_call_service.get_current_on_call_for_schedule(
            uuid.UUID(schedule_id),
            current_user.organization_id,
            db
        )

        return CurrentOnCallResponse(
            schedule_id=str(schedule.id),
            schedule_name=schedule.name,
            on_call_users=on_call_users,
            escalation_policy_id=str(schedule.escalation_policy_id) if schedule.escalation_policy_id else None
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting on-call for schedule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== Shift Management ==============

@router.post("/{schedule_id}/shifts", response_model=OnCallShiftResponse, status_code=status.HTTP_201_CREATED)
async def add_shift(
    schedule_id: str,
    data: OnCallShiftCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Add a shift to a schedule."""
    try:
        shift = await on_call_service.add_shift(
            uuid.UUID(schedule_id),
            data,
            current_user,
            db
        )

        if not shift:
            raise HTTPException(status_code=404, detail="Schedule not found")

        return _shift_to_response(shift)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding shift: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/shifts/{shift_id}", response_model=OnCallShiftResponse)
async def update_shift(
    shift_id: str,
    data: OnCallShiftUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update a shift."""
    try:
        shift = await on_call_service.update_shift(
            uuid.UUID(shift_id),
            data,
            current_user,
            db
        )

        if not shift:
            raise HTTPException(status_code=404, detail="Shift not found")

        return _shift_to_response(shift)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating shift: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/shifts/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shift(
    shift_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Delete a shift."""
    try:
        success = await on_call_service.delete_shift(
            uuid.UUID(shift_id),
            current_user,
            db
        )

        if not success:
            raise HTTPException(status_code=404, detail="Shift not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting shift: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============== Helper Functions ==============

def _schedule_to_response(schedule) -> OnCallScheduleResponse:
    """Convert schedule ORM to response schema."""
    team = None
    if schedule.team:
        team = TeamSummary(id=str(schedule.team.id), name=schedule.team.name)

    escalation_policy = None
    if schedule.escalation_policy:
        escalation_policy = EscalationPolicySummary(
            id=str(schedule.escalation_policy.id),
            name=schedule.escalation_policy.name
        )

    created_by = None
    if schedule.created_by:
        created_by = UserSummary(
            id=str(schedule.created_by.id),
            email=schedule.created_by.email,
            full_name=schedule.created_by.full_name
        )

    return OnCallScheduleResponse(
        id=str(schedule.id),
        organization_id=str(schedule.organization_id),
        team_id=str(schedule.team_id) if schedule.team_id else None,
        team=team,
        name=schedule.name,
        description=schedule.description,
        timezone=schedule.timezone,
        is_active=schedule.is_active,
        escalation_policy_id=str(schedule.escalation_policy_id) if schedule.escalation_policy_id else None,
        escalation_policy=escalation_policy,
        shifts=[_shift_to_response(s) for s in schedule.shifts],
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
        created_by=created_by
    )


def _shift_to_response(shift) -> OnCallShiftResponse:
    """Convert shift ORM to response schema."""
    user = None
    if shift.user:
        user = UserSummary(
            id=str(shift.user.id),
            email=shift.user.email,
            full_name=shift.user.full_name
        )

    return OnCallShiftResponse(
        id=str(shift.id),
        schedule_id=str(shift.schedule_id),
        user_id=str(shift.user_id),
        user=user,
        shift_type=shift.shift_type,
        day_of_week=shift.day_of_week,
        start_time=shift.start_time.strftime("%H:%M") if shift.start_time else None,
        end_time=shift.end_time.strftime("%H:%M") if shift.end_time else None,
        start_datetime=shift.start_datetime,
        end_datetime=shift.end_datetime,
        notify_channels=shift.notify_channels or [],
        created_at=shift.created_at
    )
