# backend/app/api/v1/endpoints/incidents.py - COMPLETE FIXED VERSION
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc, asc
from sqlalchemy.orm import selectinload
from app.database import get_async_session
from app.core.security import get_current_user
from app.models.user import User
from app.models.incident import Incident, IncidentStatus
from app.models.audit_log import AuditLog
from app.models.incident_comment import IncidentComment
from pydantic import BaseModel, Field
from app.schemas.incident import (
    IncidentCreate, IncidentUpdate, IncidentResponse,
    IncidentListResponse, IncidentFilters
)
from app.services.real_ai_service import RealAIService
from app.services.deployment_service import deployment_service
from app.services.notification_service import NotificationService
from typing import Optional, List
from datetime import datetime, timedelta
import uuid
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


async def send_incident_notifications(db: AsyncSession, incident: Incident, event_type: str, user: User = None):
    """Background task to send notifications for incident events"""
    try:
        notification_service = NotificationService(db)

        if event_type == "created":
            await notification_service.notify_incident_created(incident)
        elif event_type == "acknowledged" and user:
            await notification_service.notify_incident_acknowledged(incident, user)
        elif event_type == "resolved" and user:
            await notification_service.notify_incident_resolved(incident, user)
        elif event_type == "escalation":
            # Default to level 1 for basic escalation
            await notification_service.notify_escalation(incident, 1)

    except Exception as e:
        logger.error(f"Failed to send {event_type} notifications for incident {incident.id}: {e}")

@router.get("/", response_model=IncidentListResponse)
async def get_incidents(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),  # noqa: F811 - query param, shadows fastapi.status only in this scope
    severity: Optional[str] = Query(None, description="Filter by severity"),
    assigned_to: Optional[str] = Query(None, description="Filter by assigned user"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get paginated list of incidents for organization"""
    try:
        # Build query with organization isolation
        query = select(Incident).where(
            Incident.organization_id == current_user.organization_id
        )
        
        # Apply filters
        if status:
            query = query.where(Incident.status == status)
        if severity:
            query = query.where(Incident.severity == severity)
        if assigned_to:
            query = query.where(Incident.assigned_to_id == assigned_to)
        
        # Get total count
        count_query = select(func.count()).select_from(
            query.subquery()
        )
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination and ordering
        query = query.order_by(desc(Incident.created_at))
        query = query.offset((page - 1) * per_page).limit(per_page)
        
        # Execute query
        result = await db.execute(query)
        incidents = result.scalars().all()
        
        # Convert to response format
        incident_responses = []
        for incident in incidents:
            incident_responses.append(IncidentResponse(
                id=str(incident.id),
                organization_id=str(incident.organization_id),
                title=incident.title,
                description=incident.description or "",
                severity=incident.severity,
                status=incident.status,
                source="manual",  # Fixed - don't reference incident.source
                created_by="System",  # Fixed - don't reference incident.created_by_name
                assigned_to="",  # Fixed - don't reference incident.assigned_to_name
                created_at=incident.created_at,
                updated_at=incident.updated_at,
                resolved_at=incident.resolved_at,
                tags=incident.tags or []
            ))
        
        total_pages = (total + per_page - 1) // per_page
        
        return IncidentListResponse(
            incidents=incident_responses,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Error fetching incidents: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching incidents: {str(e)}")

@router.get("/stats")
async def get_incident_stats(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get incident statistics for the organization"""
    try:
        org_id = current_user.organization_id

        # Total incidents
        total_result = await db.execute(
            select(func.count(Incident.id)).where(Incident.organization_id == org_id)
        )
        total = total_result.scalar() or 0

        # By status
        status_result = await db.execute(
            select(Incident.status, func.count(Incident.id))
            .where(Incident.organization_id == org_id)
            .group_by(Incident.status)
        )
        by_status = {str(row[0].value) if hasattr(row[0], 'value') else str(row[0]): row[1] for row in status_result.all()}

        # By severity
        severity_result = await db.execute(
            select(Incident.severity, func.count(Incident.id))
            .where(Incident.organization_id == org_id)
            .group_by(Incident.severity)
        )
        by_severity = {str(row[0].value) if hasattr(row[0], 'value') else str(row[0]): row[1] for row in severity_result.all()}

        # Recent incidents (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_result = await db.execute(
            select(func.count(Incident.id)).where(
                and_(
                    Incident.organization_id == org_id,
                    Incident.created_at >= yesterday
                )
            )
        )
        recent_24h = recent_result.scalar() or 0

        # Average resolution time (for resolved incidents)
        resolved_result = await db.execute(
            select(Incident.created_at, Incident.resolved_at).where(
                and_(
                    Incident.organization_id == org_id,
                    Incident.status == IncidentStatus.RESOLVED,
                    Incident.resolved_at.isnot(None)
                )
            ).limit(100)
        )
        resolved_incidents = resolved_result.all()

        avg_resolution_minutes = None
        if resolved_incidents:
            resolution_times = []
            for created, resolved in resolved_incidents:
                if created and resolved:
                    delta = resolved - created
                    resolution_times.append(delta.total_seconds() / 60)
            if resolution_times:
                avg_resolution_minutes = int(sum(resolution_times) / len(resolution_times))

        return {
            "total": total,
            "by_status": by_status,
            "by_severity": by_severity,
            "recent_24h": recent_24h,
            "avg_resolution_minutes": avg_resolution_minutes,
            "open": by_status.get("open", 0),
            "acknowledged": by_status.get("acknowledged", 0),
            "resolved": by_status.get("resolved", 0),
            "closed": by_status.get("closed", 0)
        }

    except Exception as e:
        logger.error(f"Error fetching incident stats: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching incident stats: {str(e)}")


@router.post("/", response_model=IncidentResponse)
async def create_incident(
    incident_data: IncidentCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create new incident"""
    try:
        incident_id = uuid.uuid4()
        
        new_incident = Incident(
            id=incident_id,
            organization_id=current_user.organization_id,
            title=incident_data.title,
            description=incident_data.description,
            severity=incident_data.severity,
            status="open",
            created_by_id=current_user.id,
            tags=incident_data.tags or [],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_incident)
        
        audit_log = AuditLog(
            id=uuid.uuid4(),
            incident_id=incident_id,
            user_id=current_user.id,
            action="incident_created",
            description=f"Incident created: {incident_data.title}",
            details={
                "severity": incident_data.severity,
                "tags": incident_data.tags
            },
            organization_id=current_user.organization_id,
            created_at=datetime.utcnow()
        )
        
        db.add(audit_log)
        
        # FIX: Add await here
        await db.commit()
        await db.refresh(new_incident)

        # Send notifications for new incident
        try:
            await send_incident_notifications(db, new_incident, "created")
        except Exception as e:
            logger.warning(f"Failed to send notifications for new incident: {e}")

        return IncidentResponse(
            id=str(new_incident.id),
            organization_id=str(new_incident.organization_id),
            title=new_incident.title,
            description=new_incident.description or "",
            severity=new_incident.severity,
            status=new_incident.status,
            source="manual",
            created_by=current_user.full_name or current_user.email,
            assigned_to="",
            created_at=new_incident.created_at,
            updated_at=new_incident.updated_at,
            resolved_at=new_incident.resolved_at,
            tags=new_incident.tags or []
        )
        
    except Exception as e:
        logger.error(f"Error creating incident: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating incident: {str(e)}")

@router.post("/{incident_id}/ai-chat")
async def chat_about_incident(
    incident_id: str,
    request: dict,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    '''Chat with AI about an incident''' 
    try:
        # Get incident
        result = await db.execute(
            select(Incident).where(
                and_(
                    Incident.id == incident_id,
                    Incident.organization_id == current_user.organization_id
                )
            )
        )
        incident = result.scalar_one_or_none()
        
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        # Get user message
        user_message = request.get('message', '')
        
        # Get AI service
        from app.services.real_ai_service import RealAIService
        ai_service = RealAIService(db=db, organization_id=current_user.organization_id)

        # CRITICAL FIX: Load API keys from database FIRST
        await ai_service.load_user_api_keys()

        # Build context
        context = {
            'title': incident.title,
            'description': incident.description,
            'severity': incident.severity,
            'status': incident.status,
            'tags': incident.tags,
            'created_at': incident.created_at.isoformat()
        }

        # Call AI (use Claude or Gemini)
        # This is a simplified version - you'd integrate with your real AI service
        ai_response = await ai_service.chat_about_incident(
            incident_context=context,
            user_message=user_message
        )
        
        return {
            "response": ai_response,
            "incident_id": incident_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in AI chat: {e}")
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")

@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get specific incident by ID"""
    try:
        result = await db.execute(
            select(Incident).where(
                and_(
                    Incident.id == incident_id,
                    Incident.organization_id == current_user.organization_id
                )
            )
        )
        incident = result.scalar_one_or_none()
        
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        return IncidentResponse(
            id=str(incident.id),
            organization_id=str(incident.organization_id),
            title=incident.title,
            description=incident.description or "",
            severity=incident.severity,
            status=incident.status,
            source="manual",  # Fixed - hardcoded value
            created_by="System",  # Fixed - hardcoded value
            assigned_to="",  # Fixed - empty string
            created_at=incident.created_at,
            updated_at=incident.updated_at,
            resolved_at=incident.resolved_at,
            tags=incident.tags or []
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching incident {incident_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching incident: {str(e)}")

@router.patch("/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: str,
    incident_update: IncidentUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update incident details"""
    try:
        result = await db.execute(
            select(Incident).where(
                and_(
                    Incident.id == incident_id,
                    Incident.organization_id == current_user.organization_id
                )
            )
        )
        incident = result.scalar_one_or_none()
        
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        # Track changes for audit log
        changes = {}
        
        # Update fields if provided
        if incident_update.title is not None:
            changes["title"] = {"old": incident.title, "new": incident_update.title}
            incident.title = incident_update.title
            
        if incident_update.description is not None:
            changes["description"] = {"old": incident.description, "new": incident_update.description}
            incident.description = incident_update.description
            
        if incident_update.severity is not None:
            changes["severity"] = {"old": incident.severity, "new": incident_update.severity}
            incident.severity = incident_update.severity
            
        if incident_update.status is not None:
            old_status = incident.status
            new_status = incident_update.status
            changes["status"] = {"old": old_status, "new": new_status}
            incident.status = new_status
            
            # Set status-specific timestamps
            if new_status == "acknowledged" and not incident.acknowledged_at:
                incident.acknowledged_at = datetime.utcnow()
                incident.assigned_to_id = current_user.id
                # REMOVED: incident.assigned_to_name (doesn't exist)
            elif new_status == "resolved" and not incident.resolved_at:
                incident.resolved_at = datetime.utcnow()
        
        if incident_update.tags is not None:
            changes["tags"] = {"old": incident.tags, "new": incident_update.tags}
            incident.tags = incident_update.tags
        
        incident.updated_at = datetime.utcnow()
        
        # Create audit log for changes
        if changes:
            audit_log = AuditLog(
                id=uuid.uuid4(),
                incident_id=uuid.UUID(incident_id),
                user_id=current_user.id,
                # REMOVED: user_name (doesn't exist in AuditLog model)
                action="incident_updated",
                description=f"Updated incident: {', '.join(changes.keys())}",
                details={"changes": changes},
                organization_id=current_user.organization_id,
                created_at=datetime.utcnow()
            )
            db.add(audit_log)
        
        await db.commit()
        await db.refresh(incident)

        # Send notifications based on status change
        if "status" in changes:
            try:
                new_status = changes["status"]["new"]
                if new_status == "acknowledged":
                    await send_incident_notifications(db, incident, "acknowledged", current_user)
                elif new_status == "resolved":
                    await send_incident_notifications(db, incident, "resolved", current_user)
            except Exception as e:
                logger.warning(f"Failed to send status change notifications: {e}")

        return IncidentResponse(
            id=str(incident.id),
            organization_id=str(incident.organization_id),
            title=incident.title,
            description=incident.description or "",
            severity=incident.severity,
            status=incident.status,
            source="manual",  # Fixed - hardcoded value
            created_by="System",  # Fixed - hardcoded value
            assigned_to="",  # Fixed - empty string
            created_at=incident.created_at,
            updated_at=incident.updated_at,
            resolved_at=incident.resolved_at,
            tags=incident.tags or []
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating incident {incident_id}: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating incident: {str(e)}")
# ============================================
# Comments
# ============================================

class IncidentCommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    is_internal: bool = False


async def _get_incident_for_org(incident_id: str, current_user: User, db: AsyncSession) -> Incident:
    """Load an incident, scoped to the caller's organization."""
    try:
        incident_uuid = uuid.UUID(incident_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident ID")

    result = await db.execute(
        select(Incident).where(
            and_(
                Incident.id == incident_uuid,
                Incident.organization_id == current_user.organization_id,
            )
        )
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.get("/{incident_id}/comments")
async def list_incident_comments(
    incident_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """List comments on an incident, oldest first."""
    incident = await _get_incident_for_org(incident_id, current_user, db)

    result = await db.execute(
        select(IncidentComment, User)
        .join(User, IncidentComment.user_id == User.id)
        .where(IncidentComment.incident_id == incident.id)
        .order_by(asc(IncidentComment.created_at))
    )

    comments = [
        {
            "id": str(comment.id),
            "content": comment.content,
            "user_id": str(comment.user_id),
            "user_name": user.full_name or user.email,
            "is_internal": comment.is_internal,
            "created_at": comment.created_at.isoformat() if comment.created_at else None,
            "updated_at": comment.updated_at.isoformat() if comment.updated_at else None,
            "attachments": [],
        }
        for comment, user in result.all()
    ]

    return {"comments": comments, "total": len(comments)}


@router.post("/{incident_id}/comments", status_code=201)
async def create_incident_comment(
    incident_id: str,
    payload: IncidentCommentCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Add a comment to an incident."""
    incident = await _get_incident_for_org(incident_id, current_user, db)

    comment = IncidentComment(
        id=uuid.uuid4(),
        incident_id=incident.id,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        content=payload.content,
        is_internal=payload.is_internal,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    return {
        "id": str(comment.id),
        "content": comment.content,
        "user_id": str(comment.user_id),
        "user_name": current_user.full_name or current_user.email,
        "is_internal": comment.is_internal,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "updated_at": None,
        "attachments": [],
    }


@router.delete("/{incident_id}/comments/{comment_id}", status_code=204)
async def delete_incident_comment(
    incident_id: str,
    comment_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Delete your own comment. Admins may delete any comment on their incidents."""
    incident = await _get_incident_for_org(incident_id, current_user, db)

    try:
        comment_uuid = uuid.UUID(comment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid comment ID")

    result = await db.execute(
        select(IncidentComment).where(
            and_(
                IncidentComment.id == comment_uuid,
                IncidentComment.incident_id == incident.id,
            )
        )
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if comment.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="You can only delete your own comments")

    await db.delete(comment)
    await db.commit()
    return None


# ============================================
# Timeline
# ============================================

@router.get("/{incident_id}/timeline")
async def get_incident_timeline(
    incident_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """
    Chronological history of an incident.

    Merges three sources: the incident's own lifecycle timestamps, audit log
    entries recorded against it, and comments.
    """
    incident = await _get_incident_for_org(incident_id, current_user, db)
    events: List[dict] = []

    async def _user_name(user_id) -> str:
        if not user_id:
            return "System"
        res = await db.execute(select(User).where(User.id == user_id))
        u = res.scalar_one_or_none()
        return (u.full_name or u.email) if u else "Unknown user"

    # Lifecycle milestones recorded on the incident itself
    if incident.created_at:
        events.append({
            "id": f"{incident.id}-created",
            "type": "created",
            "timestamp": incident.created_at.isoformat(),
            "user_id": str(incident.created_by_id) if incident.created_by_id else "",
            "user_name": await _user_name(incident.created_by_id),
            "description": f"Incident created: {incident.title}",
            "details": {"new_value": "open"},
        })
    if incident.acknowledged_at:
        events.append({
            "id": f"{incident.id}-acknowledged",
            "type": "acknowledged",
            "timestamp": incident.acknowledged_at.isoformat(),
            "user_id": str(incident.acknowledged_by_id) if incident.acknowledged_by_id else "",
            "user_name": await _user_name(incident.acknowledged_by_id),
            "description": "Incident acknowledged",
            "details": {"new_value": "acknowledged"},
        })
    if incident.resolved_at:
        events.append({
            "id": f"{incident.id}-resolved",
            "type": "resolved",
            "timestamp": incident.resolved_at.isoformat(),
            "user_id": str(incident.resolved_by_id) if incident.resolved_by_id else "",
            "user_name": await _user_name(incident.resolved_by_id),
            "description": "Incident resolved",
            "details": {"new_value": "resolved"},
        })

    # Audit entries recorded against this incident
    audit_result = await db.execute(
        select(AuditLog)
        .where(AuditLog.incident_id == incident.id)
        .order_by(asc(AuditLog.created_at))
    )
    for entry in audit_result.scalars().all():
        action = (entry.action or "").lower()
        if "assign" in action:
            event_type = "assigned"
        elif "escalat" in action:
            event_type = "escalated"
        elif "status" in action:
            event_type = "status_changed"
        else:
            event_type = "updated"

        events.append({
            "id": str(entry.id),
            "type": event_type,
            "timestamp": entry.created_at.isoformat() if entry.created_at else None,
            "user_id": str(entry.user_id) if entry.user_id else "",
            "user_name": entry.user_name or await _user_name(entry.user_id),
            "description": entry.description,
            "details": entry.details or {},
        })

    # Comments
    comment_result = await db.execute(
        select(IncidentComment, User)
        .join(User, IncidentComment.user_id == User.id)
        .where(IncidentComment.incident_id == incident.id)
        .order_by(asc(IncidentComment.created_at))
    )
    for comment, user in comment_result.all():
        events.append({
            "id": str(comment.id),
            "type": "comment",
            "timestamp": comment.created_at.isoformat() if comment.created_at else None,
            "user_id": str(comment.user_id),
            "user_name": user.full_name or user.email,
            "description": "Comment added",
            "details": {"comment": comment.content},
        })

    events.sort(key=lambda e: e["timestamp"] or "")
    return {"events": events, "total": len(events)}


@router.get("/{incident_id}/alerts")
async def get_incident_alerts(
    incident_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get all alerts related to an incident"""
    try:
        from sqlalchemy import select
        from app.models.alert import Alert
        
        result = await db.execute(
            select(Alert).where(
                Alert.incident_id == incident_id,
                Alert.organization_id == current_user.organization_id
            )
        )
        alerts = result.scalars().all()
        
        return {
            "alerts": [
                {
                    "id": str(alert.id),
                    "title": alert.title,
                    "description": alert.description,
                    "severity": alert.severity.value,
                    "status": alert.status.value,
                    "source": alert.source,
                    "service_name": alert.service_name,
                    "created_at": alert.created_at.isoformat() if alert.created_at else None
                }
                for alert in alerts
            ]
        }
    except Exception as e:
        logger.error(f"Failed to fetch incident alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
@router.post("/{incident_id}/ai-analysis")
async def analyze_incident_with_ai(
    incident_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get AI analysis for incident using both Claude and Gemini"""
    try:
        # Verify incident exists and user has access
        result = await db.execute(
            select(Incident).where(
                and_(
                    Incident.id == incident_id,
                    Incident.organization_id == current_user.organization_id
                )
            )
        )
        incident = result.scalar_one_or_none()
        
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        # Initialize AI service
        from app.services.real_ai_service import RealAIService
        ai_service = RealAIService(db=db, organization_id=str(current_user.organization_id))

        # CRITICAL FIX: Load API keys from database FIRST
        await ai_service.load_user_api_keys()

        # Prepare incident context
        incident_context = {
            "title": incident.title,
            "description": incident.description or "",
            "severity": incident.severity,
            "status": incident.status,
            "created_at": incident.created_at.isoformat() if incident.created_at else None,
            "tags": incident.tags or []
        }

        # Get AI analyses from both providers
        claude_analysis = await ai_service.analyze_incident_with_claude(incident_context)
        gemini_analysis = await ai_service.analyze_incident_with_gemini(incident_context)
        
        # CRITICAL: Handle None responses properly
        if not claude_analysis and not gemini_analysis:
            raise HTTPException(
                status_code=400, 
                detail="No AI providers configured. Please add API keys in Settings."
            )
        
        # Create audit log for AI analysis
        audit_log = AuditLog(
            id=uuid.uuid4(),
            incident_id=uuid.UUID(incident_id),
            user_id=current_user.id,
            user_name=current_user.full_name or current_user.email,
            action="ai_analysis_requested",
            description="AI analysis requested via API",
            details={"ai_providers": ["claude", "gemini"]},
            organization_id=current_user.organization_id,
            created_at=datetime.utcnow()
        )
        
        db.add(audit_log)
        await db.commit()
        
        # Calculate average confidence SAFELY
        claude_confidence = claude_analysis.get("confidence_score", 0) if claude_analysis else 0
        gemini_confidence = gemini_analysis.get("confidence_score", 0) if gemini_analysis else 0
        
        avg_confidence = 0
        if claude_confidence and gemini_confidence:
            avg_confidence = (claude_confidence + gemini_confidence) / 2
        elif claude_confidence:
            avg_confidence = claude_confidence
        elif gemini_confidence:
            avg_confidence = gemini_confidence
        
        # Combine analyses
        combined_analysis = {
            "incident_id": incident_id,
            "claude_analysis": claude_analysis,
            "gemini_analysis": gemini_analysis,
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "confidence_score": avg_confidence
        }
        
        return combined_analysis
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing incident {incident_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error analyzing incident: {str(e)}")


@router.post("/{incident_id}/deploy-solution")
async def deploy_incident_solution(
    incident_id: str,
    solution_data: dict,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Deploy AI-recommended solution for incident"""
    try:
        # Verify incident exists and user has access
        result = await db.execute(
            select(Incident).where(
                and_(
                    Incident.id == incident_id,
                    Incident.organization_id == current_user.organization_id
                )
            )
        )
        incident = result.scalar_one_or_none()
        
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        # Extract solution details
        solution_type = solution_data.get("solution_type", "automated")
        commands = solution_data.get("commands", [])
        provider = solution_data.get("provider", "claude")
        
        # Start deployment using deployment service
        deployment_id = await deployment_service.deploy_solution(
            incident_id=incident_id,
            solution_type=solution_type,
            commands=commands,
            user_id=current_user.id,
            organization_id=current_user.organization_id
        )
        
        # Create audit log for deployment
        audit_log = AuditLog(
            id=uuid.uuid4(),
            incident_id=uuid.UUID(incident_id),
            user_id=current_user.id,
            # REMOVED: user_name (doesn't exist in AuditLog model)
            action="solution_deployed",
            description=f"Deployed {provider} solution for incident",
            details={
                "deployment_id": deployment_id,
                "solution_type": solution_type,
                "provider": provider,
                "commands_count": len(commands)
            },
            organization_id=current_user.organization_id,
            created_at=datetime.utcnow()
        )
        
        db.add(audit_log)
        await db.commit()
        
        return {
            "success": True,
            "deployment_id": deployment_id,
            "incident_id": incident_id,
            "status": "deployment_started",
            "websocket_url": f"/api/v1/deployments/{deployment_id}/stream"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deploying solution for incident {incident_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error deploying solution: {str(e)}")

# Legacy endpoint compatibility
@router.post("/{incident_id}/acknowledge")
async def acknowledge_incident(
    incident_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Acknowledge incident (legacy endpoint)"""
    return await update_incident(
        incident_id=incident_id,
        incident_update=IncidentUpdate(status="acknowledged"),
        db=db,
        current_user=current_user
    )

@router.post("/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Resolve incident (legacy endpoint)"""
    return await update_incident(
        incident_id=incident_id,
        incident_update=IncidentUpdate(status="resolved"),
        db=db,
        current_user=current_user
    )


@router.get("/{incident_id}/similar")
async def get_similar_incidents(
    incident_id: str,
    limit: int = Query(5, ge=1, le=10),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get similar past incidents based on service, severity, and tags.
    Useful for showing engineers what worked before.
    """
    try:
        # Get the current incident
        result = await db.execute(
            select(Incident).where(
                and_(
                    Incident.id == incident_id,
                    Incident.organization_id == current_user.organization_id
                )
            )
        )
        incident = result.scalar_one_or_none()

        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")

        # Build query for similar incidents
        # Match by: same service, similar severity, or matching tags
        similar_query = select(Incident).where(
            and_(
                Incident.organization_id == current_user.organization_id,
                Incident.id != incident_id,  # Exclude current incident
                Incident.status == IncidentStatus.RESOLVED  # Only show resolved incidents (we know the solution)
            )
        ).order_by(desc(Incident.created_at)).limit(limit * 3)  # Get more to filter

        result = await db.execute(similar_query)
        candidates = result.scalars().all()

        # Score and rank similar incidents
        similar_incidents = []
        incident_tags = set(incident.tags or [])
        incident_title_words = set(incident.title.lower().split()) if incident.title else set()

        for candidate in candidates:
            score = 0
            match_reasons = []

            # Same severity = high relevance
            if candidate.severity == incident.severity:
                score += 30
                match_reasons.append(f"Same severity ({incident.severity})")

            # Matching tags
            candidate_tags = set(candidate.tags or [])
            common_tags = incident_tags & candidate_tags
            if common_tags:
                score += len(common_tags) * 20
                match_reasons.append(f"Matching tags: {', '.join(common_tags)}")

            # Title similarity (simple word overlap)
            candidate_title_words = set(candidate.title.lower().split()) if candidate.title else set()
            common_words = incident_title_words & candidate_title_words
            # Filter out common words
            common_words -= {'the', 'a', 'an', 'is', 'in', 'on', 'at', 'to', 'for', 'of', 'error', 'failed', '-'}
            if len(common_words) >= 2:
                score += len(common_words) * 10
                match_reasons.append(f"Similar title keywords")

            if score > 0:
                # Calculate resolution time if available
                resolution_time = None
                if candidate.resolved_at and candidate.created_at:
                    delta = candidate.resolved_at - candidate.created_at
                    resolution_time = int(delta.total_seconds() / 60)  # minutes

                similar_incidents.append({
                    "id": str(candidate.id),
                    "title": candidate.title,
                    "severity": candidate.severity,
                    "status": candidate.status,
                    "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
                    "resolved_at": candidate.resolved_at.isoformat() if candidate.resolved_at else None,
                    "resolution_time_minutes": resolution_time,
                    "match_score": score,
                    "match_reasons": match_reasons,
                    "tags": candidate.tags or []
                })

        # Sort by score and limit
        similar_incidents.sort(key=lambda x: x["match_score"], reverse=True)
        similar_incidents = similar_incidents[:limit]

        return {
            "similar_incidents": similar_incidents,
            "total_found": len(similar_incidents)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding similar incidents: {e}")
        raise HTTPException(status_code=500, detail=f"Error finding similar incidents: {str(e)}")


@router.get("/{incident_id}/quick-insights")
async def get_quick_insights(
    incident_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get quick AI-powered insights for an incident without full analysis.
    Returns suggested actions, risk assessment, and key information.
    """
    try:
        # Get the incident with related data
        result = await db.execute(
            select(Incident).where(
                and_(
                    Incident.id == incident_id,
                    Incident.organization_id == current_user.organization_id
                )
            )
        )
        incident = result.scalar_one_or_none()

        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")

        # Get similar resolved incidents for context
        similar_result = await db.execute(
            select(Incident).where(
                and_(
                    Incident.organization_id == current_user.organization_id,
                    Incident.id != incident_id,
                    Incident.status == IncidentStatus.RESOLVED,
                    Incident.severity == incident.severity
                )
            ).order_by(desc(Incident.created_at)).limit(5)
        )
        similar_resolved = similar_result.scalars().all()

        # Calculate average resolution time for similar incidents
        avg_resolution_time = None
        if similar_resolved:
            resolution_times = []
            for inc in similar_resolved:
                if inc.resolved_at and inc.created_at:
                    delta = inc.resolved_at - inc.created_at
                    resolution_times.append(delta.total_seconds() / 60)
            if resolution_times:
                avg_resolution_time = int(sum(resolution_times) / len(resolution_times))

        # Generate insights based on incident data
        suggested_action = _generate_suggested_action(incident)
        risk_assessment = _generate_risk_assessment(incident)

        return {
            "incident_id": str(incident.id),
            "suggested_action": suggested_action,
            "risk_assessment": risk_assessment,
            "similar_incidents_count": len(similar_resolved),
            "avg_resolution_time_minutes": avg_resolution_time,
            "severity": incident.severity,
            "tags": incident.tags or [],
            "generated_at": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating quick insights: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating insights: {str(e)}")


def _generate_suggested_action(incident: Incident) -> str:
    """Generate suggested action based on incident properties"""
    title_lower = (incident.title or "").lower()
    desc_lower = (incident.description or "").lower()
    tags = [t.lower() for t in (incident.tags or [])]

    # Database related
    if any(kw in title_lower or kw in desc_lower for kw in ['database', 'db', 'postgres', 'mysql', 'redis', 'connection pool']):
        return "Check database connection pools, verify credentials, and review recent schema changes. Consider restarting connection pools if exhausted."

    # Memory/OOM related
    if any(kw in title_lower or kw in desc_lower for kw in ['memory', 'oom', 'out of memory', 'heap']):
        return "Review memory usage patterns, check for memory leaks, and consider increasing container memory limits. Check recent deployments for memory-intensive changes."

    # CPU related
    if any(kw in title_lower or kw in desc_lower for kw in ['cpu', 'high cpu', 'throttl']):
        return "Check for runaway processes, review recent code changes for inefficient loops, and consider horizontal scaling if load is legitimate."

    # Network/connectivity
    if any(kw in title_lower or kw in desc_lower for kw in ['network', 'timeout', 'connection refused', 'dns']):
        return "Verify network policies, check DNS resolution, and review firewall rules. Test connectivity between services."

    # Kubernetes/pod related
    if any(kw in title_lower or kw in desc_lower for kw in ['pod', 'kubernetes', 'k8s', 'crashloop', 'restart']):
        return "Check pod logs with kubectl, review resource limits, and examine liveness/readiness probes. Consider rolling back recent deployments."

    # API/latency related
    if any(kw in title_lower or kw in desc_lower for kw in ['latency', 'slow', 'api', 'response time']):
        return "Review upstream dependencies, check for N+1 queries, and examine caching effectiveness. Consider enabling request tracing."

    # Authentication
    if any(kw in title_lower or kw in desc_lower for kw in ['auth', 'login', '401', '403', 'permission']):
        return "Verify authentication service health, check token expiration settings, and review recent permission changes."

    # Default based on severity
    if incident.severity == 'critical':
        return "Immediately page the on-call team, start incident bridge, and begin impact assessment. Consider customer communication."
    elif incident.severity == 'high':
        return "Investigate root cause, check monitoring dashboards, and prepare rollback if needed."
    else:
        return "Review logs and metrics, identify patterns, and document findings for future reference."


def _generate_risk_assessment(incident: Incident) -> str:
    """Generate risk assessment based on incident properties"""
    title_lower = (incident.title or "").lower()
    tags = [t.lower() for t in (incident.tags or [])]

    # Payment/financial systems
    if any(kw in title_lower or kw in str(tags) for kw in ['payment', 'billing', 'checkout', 'transaction', 'financial']):
        return "HIGH IMPACT: Payment systems affected. Potential revenue loss and customer trust impact."

    # Authentication/security
    if any(kw in title_lower or kw in str(tags) for kw in ['auth', 'security', 'login', 'user', 'session']):
        return "HIGH IMPACT: User authentication affected. Users may be unable to access the platform."

    # Core services
    if any(kw in title_lower or kw in str(tags) for kw in ['api', 'gateway', 'core', 'main']):
        return "MEDIUM-HIGH IMPACT: Core services affected. Multiple downstream services may be impacted."

    # Based on severity
    if incident.severity == 'critical':
        return "CRITICAL: Service-wide impact likely. Customer-facing functionality severely degraded."
    elif incident.severity == 'high':
        return "HIGH: Significant user impact expected. Monitor closely and prepare mitigation."
    elif incident.severity == 'medium':
        return "MEDIUM: Limited impact expected. Some users may experience degraded performance."
    else:
        return "LOW: Minimal user impact. Monitor for escalation."