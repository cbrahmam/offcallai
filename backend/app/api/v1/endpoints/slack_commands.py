# backend/app/api/v1/endpoints/slack_commands.py
"""Slack Bot Slash Commands - /oncall, /incident"""

from fastapi import APIRouter, Request, HTTPException, Depends, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional
from datetime import datetime
from uuid import uuid4
import hmac
import hashlib
import time

from app.database import get_async_session
from app.models.incident import Incident, IncidentStatus
from app.models.user import User
from app.models.integration import Integration, IntegrationType
from app.models.on_call_schedule import OnCallSchedule
from app.models.on_call_shift import OnCallShift
from app.core.config import settings

router = APIRouter(prefix="/slack", tags=["slack-commands"])


async def verify_slack_signature(request: Request) -> bool:
    """Verify the request is from Slack"""
    if not settings.SLACK_SIGNING_SECRET:
        return False

    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    # Check timestamp to prevent replay attacks
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False

    body = await request.body()
    sig_basestring = f"v0:{timestamp}:{body.decode()}"

    my_signature = "v0=" + hmac.new(
        settings.SLACK_SIGNING_SECRET.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(my_signature, signature)


def slack_response(text: str, response_type: str = "ephemeral", blocks: list = None):
    """Create a Slack response"""
    response = {
        "response_type": response_type,
        "text": text
    }
    if blocks:
        response["blocks"] = blocks
    return JSONResponse(content=response)


@router.post("/commands/oncall")
async def oncall_command(
    request: Request,
    text: str = Form(""),
    user_id: str = Form(...),
    user_name: str = Form(...),
    team_id: str = Form(...),
    channel_id: str = Form(...),
    command: str = Form(...),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Handle /oncall slash command
    Usage:
        /oncall - Show who's currently on-call
        /oncall who - Show who's currently on-call
        /oncall schedule - Show on-call schedule
        /oncall me - Show my upcoming shifts
    """
    # Verify request (optional in dev)
    # if not await verify_slack_signature(request):
    #     raise HTTPException(status_code=401, detail="Invalid signature")

    # Get organization from Slack team
    result = await db.execute(
        select(Integration).where(
            and_(
                Integration.type == IntegrationType.SLACK,
                Integration.is_active == True
            )
        )
    )
    integrations = result.scalars().all()

    # Find matching integration by team_id
    org_id = None
    for integration in integrations:
        if integration.config.get("team_id") == team_id:
            org_id = integration.organization_id
            break

    if not org_id:
        return slack_response("This Slack workspace is not connected to OffCall AI. Please connect via Settings > Integrations.")

    subcommand = text.strip().lower() if text else "who"

    if subcommand in ["", "who"]:
        # Show current on-call
        return await _handle_oncall_who(db, org_id)
    elif subcommand == "schedule":
        return await _handle_oncall_schedule(db, org_id)
    elif subcommand == "me":
        return await _handle_oncall_me(db, org_id, user_id)
    else:
        return slack_response(
            "Unknown command. Usage:\n"
            "• `/oncall` - Show who's on-call\n"
            "• `/oncall schedule` - Show schedule\n"
            "• `/oncall me` - Show my shifts"
        )


async def _handle_oncall_who(db: AsyncSession, org_id):
    """Show who's currently on-call"""
    now = datetime.utcnow()
    current_day = now.weekday()
    current_time = now.time()

    # Get active schedules
    result = await db.execute(
        select(OnCallSchedule).where(
            and_(
                OnCallSchedule.organization_id == org_id,
                OnCallSchedule.is_active == True
            )
        )
    )
    schedules = result.scalars().all()

    on_call_users = []

    for schedule in schedules:
        # Get shifts for current day/time
        shifts_result = await db.execute(
            select(OnCallShift, User)
            .join(User, OnCallShift.user_id == User.id)
            .where(
                and_(
                    OnCallShift.schedule_id == schedule.id,
                    OnCallShift.day_of_week == current_day
                )
            )
        )
        shifts = shifts_result.all()

        for shift, user in shifts:
            # Check if current time is within shift
            if shift.start_time <= current_time <= shift.end_time:
                on_call_users.append({
                    "name": user.full_name,
                    "schedule": schedule.name,
                    "until": shift.end_time.strftime("%H:%M")
                })

    if not on_call_users:
        return slack_response(
            "No one is currently on-call.",
            response_type="in_channel"
        )

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Currently On-Call"}
        }
    ]

    for u in on_call_users:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{u['name']}*\nSchedule: {u['schedule']}\nUntil: {u['until']} UTC"
            }
        })

    return slack_response(
        f"{len(on_call_users)} engineer(s) currently on-call",
        response_type="in_channel",
        blocks=blocks
    )


async def _handle_oncall_schedule(db: AsyncSession, org_id):
    """Show on-call schedule summary"""
    result = await db.execute(
        select(OnCallSchedule).where(
            and_(
                OnCallSchedule.organization_id == org_id,
                OnCallSchedule.is_active == True
            )
        )
    )
    schedules = result.scalars().all()

    if not schedules:
        return slack_response("No on-call schedules configured.")

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "On-Call Schedules"}
        }
    ]

    for schedule in schedules:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{schedule.name}*\n{schedule.description or 'No description'}"
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "View"},
                "url": f"{settings.FRONTEND_URL}/on-call-schedules"
            }
        })

    return slack_response(
        f"{len(schedules)} schedule(s) configured",
        blocks=blocks
    )


async def _handle_oncall_me(db: AsyncSession, org_id, slack_user_id: str):
    """Show user's upcoming shifts"""
    # Try to find user by Slack ID in metadata
    # For now, show a message to link account
    return slack_response(
        f"To see your shifts, visit: {settings.FRONTEND_URL}/on-call-schedules\n\n"
        "_Account linking coming soon!_"
    )


@router.post("/commands/incident")
async def incident_command(
    request: Request,
    text: str = Form(""),
    user_id: str = Form(...),
    user_name: str = Form(...),
    team_id: str = Form(...),
    channel_id: str = Form(...),
    command: str = Form(...),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Handle /incident slash command
    Usage:
        /incident create [title] - Create a new incident
        /incident list - List open incidents
        /incident [id] - View incident details
    """
    # Get organization
    result = await db.execute(
        select(Integration).where(
            and_(
                Integration.type == IntegrationType.SLACK,
                Integration.is_active == True
            )
        )
    )
    integrations = result.scalars().all()

    org_id = None
    for integration in integrations:
        if integration.config.get("team_id") == team_id:
            org_id = integration.organization_id
            break

    if not org_id:
        return slack_response("This Slack workspace is not connected to OffCall AI.")

    parts = text.strip().split(" ", 1)
    subcommand = parts[0].lower() if parts else ""
    args = parts[1] if len(parts) > 1 else ""

    if subcommand == "create":
        return await _handle_incident_create(db, org_id, args, user_name, channel_id)
    elif subcommand == "list":
        return await _handle_incident_list(db, org_id)
    elif subcommand and len(subcommand) > 8:  # Likely a UUID
        return await _handle_incident_view(db, org_id, subcommand)
    else:
        return slack_response(
            "Usage:\n"
            "• `/incident create [title]` - Create incident\n"
            "• `/incident list` - List open incidents\n"
            "• `/incident [id]` - View incident"
        )


async def _handle_incident_create(db: AsyncSession, org_id, title: str, user_name: str, channel_id: str):
    """Create a new incident from Slack"""
    if not title:
        return slack_response("Please provide an incident title: `/incident create Database outage`")

    incident_id = uuid4()
    incident = Incident(
        id=incident_id,
        organization_id=org_id,
        title=title,
        description=f"Created from Slack by @{user_name}",
        severity="high",  # Default to high for Slack-created incidents
        status="open",
        tags=["slack", f"channel:{channel_id}"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    db.add(incident)
    await db.commit()

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Incident Created"}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{title}*\nSeverity: HIGH\nStatus: OPEN"
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Incident"},
                    "url": f"{settings.FRONTEND_URL}/incidents/{incident_id}",
                    "style": "primary"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Acknowledge"},
                    "value": f"ack_{incident_id}",
                    "action_id": "acknowledge_incident"
                }
            ]
        }
    ]

    return slack_response(
        f"Incident created: {title}",
        response_type="in_channel",
        blocks=blocks
    )


async def _handle_incident_list(db: AsyncSession, org_id):
    """List open incidents"""
    result = await db.execute(
        select(Incident).where(
            and_(
                Incident.organization_id == org_id,
                Incident.status.in_([IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED])
            )
        ).order_by(Incident.created_at.desc()).limit(10)
    )
    incidents = result.scalars().all()

    if not incidents:
        return slack_response("No open incidents! Everything looks good.")

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Open Incidents ({len(incidents)})"}
        }
    ]

    severity_emoji = {
        "critical": ":red_circle:",
        "high": ":large_orange_circle:",
        "medium": ":large_yellow_circle:",
        "low": ":large_green_circle:"
    }

    for inc in incidents:
        emoji = severity_emoji.get(inc.severity, ":white_circle:")
        status_text = "ACK" if inc.status == "acknowledged" else "OPEN"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{emoji} *{inc.title}*\n`{status_text}` | {inc.severity.upper()} | {inc.created_at.strftime('%m/%d %H:%M')}"
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "View"},
                "url": f"{settings.FRONTEND_URL}/incidents/{inc.id}"
            }
        })

    return slack_response(
        f"{len(incidents)} open incident(s)",
        response_type="in_channel",
        blocks=blocks
    )


async def _handle_incident_view(db: AsyncSession, org_id, incident_id: str):
    """View incident details"""
    try:
        from uuid import UUID
        inc_uuid = UUID(incident_id)
    except ValueError:
        return slack_response("Invalid incident ID")

    result = await db.execute(
        select(Incident).where(
            and_(
                Incident.id == inc_uuid,
                Incident.organization_id == org_id
            )
        )
    )
    incident = result.scalar_one_or_none()

    if not incident:
        return slack_response("Incident not found")

    severity_emoji = {
        "critical": ":red_circle:",
        "high": ":large_orange_circle:",
        "medium": ":large_yellow_circle:",
        "low": ":large_green_circle:"
    }
    emoji = severity_emoji.get(incident.severity, ":white_circle:")

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": incident.title}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Severity:*\n{emoji} {incident.severity.upper()}"},
                {"type": "mrkdwn", "text": f"*Status:*\n{incident.status.upper()}"},
                {"type": "mrkdwn", "text": f"*Created:*\n{incident.created_at.strftime('%Y-%m-%d %H:%M')}"},
                {"type": "mrkdwn", "text": f"*ID:*\n`{incident.id}`"}
            ]
        }
    ]

    if incident.description:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Description:*\n{incident.description[:500]}"}
        })

    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View in OffCall"},
                "url": f"{settings.FRONTEND_URL}/incidents/{incident.id}",
                "style": "primary"
            }
        ]
    })

    return slack_response(
        f"Incident: {incident.title}",
        blocks=blocks
    )


@router.post("/interactions")
async def handle_interactions(
    request: Request,
    db: AsyncSession = Depends(get_async_session)
):
    """Handle Slack interactive components (buttons, etc.)"""
    import json
    from urllib.parse import parse_qs

    body = await request.body()
    parsed = parse_qs(body.decode())
    payload = json.loads(parsed.get("payload", ["{}"])[0])

    action_id = payload.get("actions", [{}])[0].get("action_id", "")
    action_value = payload.get("actions", [{}])[0].get("value", "")

    if action_id == "acknowledge_incident":
        # Extract incident ID
        incident_id = action_value.replace("ack_", "")
        try:
            from uuid import UUID
            inc_uuid = UUID(incident_id)

            result = await db.execute(
                select(Incident).where(Incident.id == inc_uuid)
            )
            incident = result.scalar_one_or_none()

            if incident and incident.status == "open":
                incident.status = "acknowledged"
                incident.acknowledged_at = datetime.utcnow()
                await db.commit()

                return JSONResponse({
                    "response_type": "in_channel",
                    "text": f"Incident acknowledged by <@{payload.get('user', {}).get('id', 'unknown')}>"
                })

        except Exception as e:
            print(f"Error acknowledging incident: {e}")

    return JSONResponse({"text": "Action processed"})
