# backend/app/api/v1/endpoints/calendar.py
"""Calendar Integration API - ICS feeds for on-call schedules"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta
import hashlib

from app.database import get_async_session
from app.core.security import get_current_user
from app.models.user import User
from app.models.on_call_schedule import OnCallSchedule
from app.models.on_call_shift import OnCallShift
from app.core.config import settings

router = APIRouter(prefix="/calendar", tags=["calendar"])


def generate_ics_uid(shift_id: str, date: datetime) -> str:
    """Generate a unique UID for an ICS event"""
    unique_string = f"{shift_id}-{date.isoformat()}"
    return hashlib.md5(unique_string.encode()).hexdigest() + "@offcall.local"


def format_datetime_ics(dt: datetime) -> str:
    """Format datetime for ICS (UTC)"""
    return dt.strftime("%Y%m%dT%H%M%SZ")


def generate_ics_content(
    events: list,
    calendar_name: str,
    description: str = ""
) -> str:
    """Generate ICS calendar content"""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//OffCall AI//On-Call Schedule//EN",
        f"X-WR-CALNAME:{calendar_name}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH"
    ]

    if description:
        lines.append(f"X-WR-CALDESC:{description}")

    for event in events:
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{event['uid']}",
            f"DTSTAMP:{format_datetime_ics(datetime.utcnow())}",
            f"DTSTART:{format_datetime_ics(event['start'])}",
            f"DTEND:{format_datetime_ics(event['end'])}",
            f"SUMMARY:{event['summary']}",
        ])

        if event.get('description'):
            # Escape special characters in description
            desc = event['description'].replace('\n', '\\n').replace(',', '\\,')
            lines.append(f"DESCRIPTION:{desc}")

        if event.get('location'):
            lines.append(f"LOCATION:{event['location']}")

        # Add alarm 15 minutes before
        lines.extend([
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            "TRIGGER:-PT15M",
            f"DESCRIPTION:On-call shift starting: {event['summary']}",
            "END:VALARM"
        ])

        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")

    return "\r\n".join(lines)


@router.get("/schedules/{schedule_id}/ics")
async def get_schedule_ics(
    schedule_id: UUID,
    token: str = Query(..., description="Calendar access token"),
    weeks: int = Query(8, ge=1, le=52, description="Weeks of events to generate"),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Get ICS feed for an on-call schedule.
    Use this URL in Google Calendar or Outlook to sync.
    """
    # Verify token and get schedule
    # Token format: {user_id}_{schedule_id}_{hash}
    try:
        parts = token.split("_")
        if len(parts) != 3:
            raise HTTPException(status_code=401, detail="Invalid token")

        user_id = UUID(parts[0])
        token_schedule_id = UUID(parts[1])
        token_hash = parts[2]

        # Verify hash
        expected_hash = hashlib.md5(
            f"{user_id}{token_schedule_id}{settings.SECRET_KEY}".encode()
        ).hexdigest()[:16]

        if token_hash != expected_hash or token_schedule_id != schedule_id:
            raise HTTPException(status_code=401, detail="Invalid token")

    except (ValueError, IndexError):
        raise HTTPException(status_code=401, detail="Invalid token")

    # Get schedule
    result = await db.execute(
        select(OnCallSchedule).where(OnCallSchedule.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Get shifts
    result = await db.execute(
        select(OnCallShift)
        .where(OnCallShift.schedule_id == schedule_id)
        .order_by(OnCallShift.day_of_week, OnCallShift.start_time)
    )
    shifts = result.scalars().all()

    # Generate events for the next N weeks
    events = []
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    for week_offset in range(weeks):
        week_start = today + timedelta(weeks=week_offset)

        for shift in shifts:
            if shift.shift_type == "recurring":
                # Calculate the date for this shift in this week
                days_until_shift = (shift.day_of_week - week_start.weekday()) % 7
                shift_date = week_start + timedelta(days=days_until_shift)

                # Create start and end datetimes
                start_dt = shift_date.replace(
                    hour=shift.start_time.hour,
                    minute=shift.start_time.minute
                )
                end_dt = shift_date.replace(
                    hour=shift.end_time.hour,
                    minute=shift.end_time.minute
                )

                # Handle overnight shifts
                if end_dt <= start_dt:
                    end_dt += timedelta(days=1)

                # Get user name
                user_result = await db.execute(
                    select(User).where(User.id == shift.user_id)
                )
                user = user_result.scalar_one_or_none()
                user_name = user.full_name if user else "Unknown"

                events.append({
                    "uid": generate_ics_uid(str(shift.id), shift_date),
                    "start": start_dt,
                    "end": end_dt,
                    "summary": f"On-Call: {user_name}",
                    "description": f"On-call shift for {schedule.name}\\nEngineer: {user_name}"
                })

            elif shift.shift_type == "one_time" and shift.start_datetime and shift.end_datetime:
                # One-time shift - only include if within range
                if week_offset == 0 or (shift.start_datetime >= today and shift.start_datetime <= today + timedelta(weeks=weeks)):
                    user_result = await db.execute(
                        select(User).where(User.id == shift.user_id)
                    )
                    user = user_result.scalar_one_or_none()
                    user_name = user.full_name if user else "Unknown"

                    events.append({
                        "uid": generate_ics_uid(str(shift.id), shift.start_datetime),
                        "start": shift.start_datetime,
                        "end": shift.end_datetime,
                        "summary": f"On-Call: {user_name}",
                        "description": f"On-call shift for {schedule.name}\\nEngineer: {user_name}"
                    })

    # Generate ICS content
    ics_content = generate_ics_content(
        events=events,
        calendar_name=f"On-Call: {schedule.name}",
        description=f"On-call schedule for {schedule.name}"
    )

    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="{schedule.name.replace(" ", "_")}_oncall.ics"'
        }
    )


@router.get("/user/ics")
async def get_user_ics(
    token: str = Query(..., description="Calendar access token"),
    weeks: int = Query(8, ge=1, le=52),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Get ICS feed for all of a user's on-call shifts across all schedules.
    """
    # Verify token
    try:
        parts = token.split("_")
        if len(parts) != 2:
            raise HTTPException(status_code=401, detail="Invalid token")

        user_id = UUID(parts[0])
        token_hash = parts[1]

        expected_hash = hashlib.md5(
            f"{user_id}user{settings.SECRET_KEY}".encode()
        ).hexdigest()[:16]

        if token_hash != expected_hash:
            raise HTTPException(status_code=401, detail="Invalid token")

    except (ValueError, IndexError):
        raise HTTPException(status_code=401, detail="Invalid token")

    # Get user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get all shifts for this user
    result = await db.execute(
        select(OnCallShift, OnCallSchedule)
        .join(OnCallSchedule, OnCallShift.schedule_id == OnCallSchedule.id)
        .where(
            and_(
                OnCallShift.user_id == user_id,
                OnCallSchedule.is_active == True
            )
        )
    )
    rows = result.all()

    # Generate events
    events = []
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    for shift, schedule in rows:
        for week_offset in range(weeks):
            week_start = today + timedelta(weeks=week_offset)

            if shift.shift_type == "recurring":
                days_until_shift = (shift.day_of_week - week_start.weekday()) % 7
                shift_date = week_start + timedelta(days=days_until_shift)

                start_dt = shift_date.replace(
                    hour=shift.start_time.hour,
                    minute=shift.start_time.minute
                )
                end_dt = shift_date.replace(
                    hour=shift.end_time.hour,
                    minute=shift.end_time.minute
                )

                if end_dt <= start_dt:
                    end_dt += timedelta(days=1)

                events.append({
                    "uid": generate_ics_uid(str(shift.id), shift_date),
                    "start": start_dt,
                    "end": end_dt,
                    "summary": f"On-Call: {schedule.name}",
                    "description": f"Your on-call shift for {schedule.name}"
                })

    ics_content = generate_ics_content(
        events=events,
        calendar_name=f"My On-Call Shifts",
        description=f"All on-call shifts for {user.full_name}"
    )

    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": 'attachment; filename="my_oncall_shifts.ics"'
        }
    )


@router.get("/generate-token")
async def generate_calendar_token(
    schedule_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Generate a calendar subscription token.
    Returns URLs for subscribing in various calendar apps.
    """
    base_url = settings.API_URL

    result = {}

    if schedule_id:
        # Verify user has access to this schedule
        schedule_result = await db.execute(
            select(OnCallSchedule).where(
                and_(
                    OnCallSchedule.id == schedule_id,
                    OnCallSchedule.organization_id == current_user.organization_id
                )
            )
        )
        schedule = schedule_result.scalar_one_or_none()
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")

        # Generate schedule token
        token_hash = hashlib.md5(
            f"{current_user.id}{schedule_id}{settings.SECRET_KEY}".encode()
        ).hexdigest()[:16]
        schedule_token = f"{current_user.id}_{schedule_id}_{token_hash}"

        schedule_url = f"{base_url}/api/v1/calendar/schedules/{schedule_id}/ics?token={schedule_token}"

        result["schedule"] = {
            "name": schedule.name,
            "ics_url": schedule_url,
            "google_calendar_url": f"https://calendar.google.com/calendar/r?cid={schedule_url}",
            "outlook_url": f"https://outlook.office.com/owa?path=/calendar/action/compose&rru=addsubscription&url={schedule_url}&name={schedule.name.replace(' ', '%20')}%20On-Call"
        }

    # Generate user token for personal calendar
    user_token_hash = hashlib.md5(
        f"{current_user.id}user{settings.SECRET_KEY}".encode()
    ).hexdigest()[:16]
    user_token = f"{current_user.id}_{user_token_hash}"

    user_url = f"{base_url}/api/v1/calendar/user/ics?token={user_token}"

    result["personal"] = {
        "ics_url": user_url,
        "google_calendar_url": f"https://calendar.google.com/calendar/r?cid={user_url}",
        "outlook_url": f"https://outlook.office.com/owa?path=/calendar/action/compose&rru=addsubscription&url={user_url}&name=My%20On-Call%20Shifts"
    }

    return result
