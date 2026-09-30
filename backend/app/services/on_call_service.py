"""
Service for managing on-call schedules and determining who is on-call.
"""

from datetime import datetime, time, timedelta
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
import pytz
import logging

from app.models.on_call_schedule import OnCallSchedule
from app.models.on_call_shift import OnCallShift
from app.models.user import User
from app.schemas.on_call_schedule import (
    OnCallScheduleCreate, OnCallScheduleUpdate,
    OnCallShiftCreate, OnCallShiftUpdate,
    CurrentOnCallUser
)

logger = logging.getLogger(__name__)


class OnCallService:
    """Service for managing on-call schedules and determining who is on-call."""

    async def create_schedule(
        self,
        data: OnCallScheduleCreate,
        user: User,
        db: AsyncSession
    ) -> OnCallSchedule:
        """Create a new on-call schedule with shifts."""
        schedule = OnCallSchedule(
            organization_id=user.organization_id,
            name=data.name,
            description=data.description,
            timezone=data.timezone,
            team_id=data.team_id,
            escalation_policy_id=data.escalation_policy_id,
            is_active=data.is_active,
            created_by_id=user.id
        )
        db.add(schedule)
        await db.flush()

        # Create shifts
        for shift_data in data.shifts:
            shift = self._create_shift_from_data(shift_data, schedule.id)
            db.add(shift)

        await db.commit()

        # Reload with relationships
        return await self.get_schedule(schedule.id, user.organization_id, db)

    async def list_schedules(
        self,
        organization_id,
        db: AsyncSession,
        page: int = 1,
        per_page: int = 20,
        team_id: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None
    ) -> Tuple[List[OnCallSchedule], int]:
        """List schedules with pagination and filtering."""
        query = select(OnCallSchedule).where(
            OnCallSchedule.organization_id == organization_id
        ).options(
            selectinload(OnCallSchedule.shifts).selectinload(OnCallShift.user),
            selectinload(OnCallSchedule.team),
            selectinload(OnCallSchedule.escalation_policy),
            selectinload(OnCallSchedule.created_by)
        )

        if team_id:
            query = query.where(OnCallSchedule.team_id == team_id)
        if is_active is not None:
            query = query.where(OnCallSchedule.is_active == is_active)
        if search:
            query = query.where(OnCallSchedule.name.ilike(f"%{search}%"))

        # Count total
        count_query = select(func.count()).select_from(
            select(OnCallSchedule.id).where(
                OnCallSchedule.organization_id == organization_id
            ).subquery()
        )
        if team_id:
            count_query = select(func.count()).select_from(
                select(OnCallSchedule.id).where(
                    and_(
                        OnCallSchedule.organization_id == organization_id,
                        OnCallSchedule.team_id == team_id
                    )
                ).subquery()
            )

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        query = query.order_by(OnCallSchedule.name)
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await db.execute(query)
        schedules = result.scalars().unique().all()

        return list(schedules), total

    async def get_schedule(
        self,
        schedule_id,
        organization_id,
        db: AsyncSession
    ) -> Optional[OnCallSchedule]:
        """Get a single schedule by ID."""
        query = select(OnCallSchedule).where(
            and_(
                OnCallSchedule.id == schedule_id,
                OnCallSchedule.organization_id == organization_id
            )
        ).options(
            selectinload(OnCallSchedule.shifts).selectinload(OnCallShift.user),
            selectinload(OnCallSchedule.team),
            selectinload(OnCallSchedule.escalation_policy),
            selectinload(OnCallSchedule.created_by)
        )

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def update_schedule(
        self,
        schedule_id,
        data: OnCallScheduleUpdate,
        user: User,
        db: AsyncSession
    ) -> Optional[OnCallSchedule]:
        """Update a schedule."""
        schedule = await self.get_schedule(schedule_id, user.organization_id, db)
        if not schedule:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(schedule, key, value)

        await db.commit()
        return await self.get_schedule(schedule_id, user.organization_id, db)

    async def delete_schedule(
        self,
        schedule_id,
        user: User,
        db: AsyncSession
    ) -> bool:
        """Delete a schedule (cascades to shifts)."""
        schedule = await self.get_schedule(schedule_id, user.organization_id, db)
        if not schedule:
            return False

        await db.delete(schedule)
        await db.commit()
        return True

    # ============== Shift Management ==============

    async def add_shift(
        self,
        schedule_id,
        data: OnCallShiftCreate,
        user: User,
        db: AsyncSession
    ) -> Optional[OnCallShift]:
        """Add a shift to a schedule."""
        schedule = await self.get_schedule(schedule_id, user.organization_id, db)
        if not schedule:
            return None

        shift = self._create_shift_from_data(data, schedule_id)
        db.add(shift)
        await db.commit()

        # Reload with user
        query = select(OnCallShift).where(OnCallShift.id == shift.id).options(
            selectinload(OnCallShift.user)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def update_shift(
        self,
        shift_id,
        data: OnCallShiftUpdate,
        user: User,
        db: AsyncSession
    ) -> Optional[OnCallShift]:
        """Update a shift."""
        query = select(OnCallShift).join(OnCallSchedule).where(
            and_(
                OnCallShift.id == shift_id,
                OnCallSchedule.organization_id == user.organization_id
            )
        ).options(selectinload(OnCallShift.user))
        result = await db.execute(query)
        shift = result.scalar_one_or_none()

        if not shift:
            return None

        update_data = data.model_dump(exclude_unset=True)

        # Convert time strings if present
        if 'start_time' in update_data and update_data['start_time']:
            h, m = map(int, update_data['start_time'].split(':'))
            update_data['start_time'] = time(h, m)
        if 'end_time' in update_data and update_data['end_time']:
            h, m = map(int, update_data['end_time'].split(':'))
            update_data['end_time'] = time(h, m)

        for key, value in update_data.items():
            setattr(shift, key, value)

        await db.commit()

        # Reload with user
        query = select(OnCallShift).where(OnCallShift.id == shift_id).options(
            selectinload(OnCallShift.user)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def delete_shift(
        self,
        shift_id,
        user: User,
        db: AsyncSession
    ) -> bool:
        """Delete a shift."""
        query = select(OnCallShift).join(OnCallSchedule).where(
            and_(
                OnCallShift.id == shift_id,
                OnCallSchedule.organization_id == user.organization_id
            )
        )
        result = await db.execute(query)
        shift = result.scalar_one_or_none()

        if not shift:
            return False

        await db.delete(shift)
        await db.commit()
        return True

    # ============== On-Call Status ==============

    async def get_current_on_call_for_schedule(
        self,
        schedule_id,
        organization_id,
        db: AsyncSession,
        at_time: Optional[datetime] = None
    ) -> List[CurrentOnCallUser]:
        """Get who is currently on-call for a specific schedule."""
        schedule = await self.get_schedule(schedule_id, organization_id, db)
        if not schedule or not schedule.is_active:
            return []

        now = at_time or datetime.now(pytz.UTC)

        try:
            schedule_tz = pytz.timezone(schedule.timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            schedule_tz = pytz.UTC

        now_in_schedule_tz = now.astimezone(schedule_tz)

        on_call_users = []

        for shift in schedule.shifts:
            if self._is_shift_active(shift, now_in_schedule_tz):
                shift_start, shift_end = self._get_shift_window(shift, now_in_schedule_tz)
                on_call_users.append(CurrentOnCallUser(
                    user_id=str(shift.user.id),
                    user_email=shift.user.email,
                    user_full_name=shift.user.full_name,
                    schedule_id=str(schedule.id),
                    schedule_name=schedule.name,
                    shift_start=shift_start,
                    shift_end=shift_end,
                    notify_channels=shift.notify_channels or []
                ))

        return on_call_users

    async def get_all_on_call_users(
        self,
        organization_id,
        db: AsyncSession,
        at_time: Optional[datetime] = None
    ) -> List[CurrentOnCallUser]:
        """Get all users currently on-call across all schedules."""
        query = select(OnCallSchedule).where(
            and_(
                OnCallSchedule.organization_id == organization_id,
                OnCallSchedule.is_active == True
            )
        ).options(
            selectinload(OnCallSchedule.shifts).selectinload(OnCallShift.user)
        )

        result = await db.execute(query)
        schedules = result.scalars().unique().all()

        all_on_call = []
        now = at_time or datetime.now(pytz.UTC)

        for schedule in schedules:
            try:
                schedule_tz = pytz.timezone(schedule.timezone)
            except pytz.exceptions.UnknownTimeZoneError:
                schedule_tz = pytz.UTC

            now_in_schedule_tz = now.astimezone(schedule_tz)

            for shift in schedule.shifts:
                if self._is_shift_active(shift, now_in_schedule_tz):
                    shift_start, shift_end = self._get_shift_window(shift, now_in_schedule_tz)
                    all_on_call.append(CurrentOnCallUser(
                        user_id=str(shift.user.id),
                        user_email=shift.user.email,
                        user_full_name=shift.user.full_name,
                        schedule_id=str(schedule.id),
                        schedule_name=schedule.name,
                        shift_start=shift_start,
                        shift_end=shift_end,
                        notify_channels=shift.notify_channels or []
                    ))

        return all_on_call

    async def sync_user_on_call_status(
        self,
        organization_id,
        db: AsyncSession
    ) -> int:
        """
        Sync User.is_currently_on_call field based on active schedules.
        Returns count of users updated.
        """
        # Get all on-call users
        on_call_users = await self.get_all_on_call_users(organization_id, db)
        on_call_user_ids = {u.user_id for u in on_call_users}

        # Get all users in org
        query = select(User).where(User.organization_id == organization_id)
        result = await db.execute(query)
        users = result.scalars().all()

        updated_count = 0
        for user in users:
            should_be_on_call = str(user.id) in on_call_user_ids
            if user.is_currently_on_call != should_be_on_call:
                user.is_currently_on_call = should_be_on_call
                updated_count += 1

        await db.commit()
        return updated_count

    # ============== Helper Methods ==============

    def _create_shift_from_data(self, data: OnCallShiftCreate, schedule_id) -> OnCallShift:
        """Create a shift object from schema data."""
        shift = OnCallShift(
            schedule_id=schedule_id,
            user_id=data.user_id,
            shift_type=data.shift_type.value if hasattr(data.shift_type, 'value') else data.shift_type,
            notify_channels=data.notify_channels
        )

        if data.shift_type == "recurring" or data.shift_type.value == "recurring":
            shift.day_of_week = data.day_of_week
            if data.start_time:
                h, m = map(int, data.start_time.split(':'))
                shift.start_time = time(h, m)
            if data.end_time:
                h, m = map(int, data.end_time.split(':'))
                shift.end_time = time(h, m)
        else:  # one_time
            shift.start_datetime = data.start_datetime
            shift.end_datetime = data.end_datetime

        return shift

    def _is_shift_active(self, shift: OnCallShift, now: datetime) -> bool:
        """Check if a shift is active at the given time."""
        if shift.shift_type == "one_time":
            if shift.start_datetime and shift.end_datetime:
                # Convert to timezone-aware if needed
                start = shift.start_datetime
                end = shift.end_datetime
                if start.tzinfo is None:
                    start = pytz.UTC.localize(start)
                if end.tzinfo is None:
                    end = pytz.UTC.localize(end)
                return start <= now <= end
            return False

        # Recurring shift
        current_day = now.weekday()  # 0=Monday
        current_time = now.time()

        if shift.day_of_week != current_day:
            return False

        if not shift.start_time or not shift.end_time:
            return False

        # Handle overnight shifts (end_time < start_time)
        if shift.end_time < shift.start_time:
            return current_time >= shift.start_time or current_time <= shift.end_time

        return shift.start_time <= current_time <= shift.end_time

    def _get_shift_window(self, shift: OnCallShift, now: datetime) -> Tuple[datetime, datetime]:
        """Get the start and end datetime for the current shift window."""
        if shift.shift_type == "one_time":
            return shift.start_datetime, shift.end_datetime

        # For recurring, calculate based on today
        today = now.date()
        tz = now.tzinfo or pytz.UTC

        start_dt = datetime.combine(today, shift.start_time)
        end_dt = datetime.combine(today, shift.end_time)

        # Make timezone aware
        if hasattr(tz, 'localize'):
            start_dt = tz.localize(start_dt)
            end_dt = tz.localize(end_dt)
        else:
            start_dt = start_dt.replace(tzinfo=tz)
            end_dt = end_dt.replace(tzinfo=tz)

        # Handle overnight shifts
        if shift.end_time < shift.start_time:
            if now.time() < shift.end_time:
                start_dt -= timedelta(days=1)
            else:
                end_dt += timedelta(days=1)

        return start_dt, end_dt


    async def get_on_call_user_for_incident_assignment(
        self,
        organization_id,
        db: AsyncSession,
        team_id: Optional[str] = None
    ) -> Optional[User]:
        """
        Get the best user to assign an incident to based on on-call schedules.
        Returns the first on-call user found, preferring team-specific schedules.
        """
        on_call_users = await self.get_all_on_call_users(organization_id, db)

        if not on_call_users:
            return None

        # If team_id specified, prefer users from that team's schedule
        if team_id:
            for on_call in on_call_users:
                # Get the schedule to check team
                schedule = await self.get_schedule(on_call.schedule_id, organization_id, db)
                if schedule and str(schedule.team_id) == team_id:
                    # Return this user
                    result = await db.execute(
                        select(User).where(User.id == on_call.user_id)
                    )
                    return result.scalar_one_or_none()

        # Return first on-call user
        first_on_call = on_call_users[0]
        result = await db.execute(
            select(User).where(User.id == first_on_call.user_id)
        )
        return result.scalar_one_or_none()

    async def get_escalation_policy_for_incident(
        self,
        organization_id,
        db: AsyncSession,
        team_id: Optional[str] = None
    ) -> Optional[any]:
        """
        Get the escalation policy to use for a new incident.
        Checks on-call schedules for linked escalation policies.
        """
        from app.models.escalation_policy import EscalationPolicy

        # Get active schedules
        schedules, _ = await self.list_schedules(
            organization_id=organization_id,
            db=db,
            is_active=True
        )

        # If team specified, prefer that team's schedule
        if team_id:
            for schedule in schedules:
                if str(schedule.team_id) == team_id and schedule.escalation_policy_id:
                    result = await db.execute(
                        select(EscalationPolicy).where(
                            EscalationPolicy.id == schedule.escalation_policy_id
                        )
                    )
                    return result.scalar_one_or_none()

        # Return first schedule with escalation policy
        for schedule in schedules:
            if schedule.escalation_policy_id:
                result = await db.execute(
                    select(EscalationPolicy).where(
                        EscalationPolicy.id == schedule.escalation_policy_id
                    )
                )
                policy = result.scalar_one_or_none()
                if policy:
                    return policy

        return None


# Singleton instance
on_call_service = OnCallService()
