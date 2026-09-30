# backend/app/api/v1/endpoints/post_mortems.py
"""Post-Mortems API endpoints - Premium Feature"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from uuid import UUID
import logging

from app.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.post_mortem import PostMortemStatus
from app.services.post_mortem_service import PostMortemService
from app.schemas.post_mortem import (
    PostMortemCreate,
    PostMortemUpdate,
    PostMortemResponse,
    PostMortemListResponse,
    PostMortemCommentCreate,
    PostMortemCommentResponse
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/generate/{incident_id}", response_model=PostMortemResponse, status_code=status.HTTP_201_CREATED)
async def generate_post_mortem_with_ai(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate a post-mortem using AI based on incident data"""
    service = PostMortemService(db)
    try:
        post_mortem = await service.generate_post_mortem_with_ai(
            incident_id=incident_id,
            organization_id=current_user.organization_id,
            user_id=current_user.id
        )
        return await service.to_response(post_mortem)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")


@router.post("/", response_model=PostMortemResponse, status_code=status.HTTP_201_CREATED)
async def create_post_mortem(
    data: PostMortemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new post-mortem for an incident"""
    service = PostMortemService(db)
    try:
        post_mortem = await service.create_post_mortem(
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            data=data
        )
        return await service.to_response(post_mortem)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/")
async def list_post_mortems(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    pm_status: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all post-mortems for the organization"""
    try:
        service = PostMortemService(db)

        # Convert status string to enum if provided
        status_enum = None
        if pm_status:
            try:
                status_enum = PostMortemStatus(pm_status)
            except ValueError:
                pass

        post_mortems, total = await service.list_post_mortems(
            organization_id=current_user.organization_id,
            page=page,
            per_page=per_page,
            status=status_enum,
            search=search
        )

        # Build response manually to avoid Pydantic serialization issues
        responses = []
        for pm in post_mortems:
            try:
                # Get creator name
                creator_name = None
                if pm.created_by_id:
                    creator_result = await db.execute(
                        select(User).where(User.id == pm.created_by_id)
                    )
                    creator = creator_result.scalar_one_or_none()
                    if creator:
                        creator_name = creator.full_name

                # Get incident info
                incident_title = None
                incident_severity = None
                if pm.incident_id:
                    from app.models.incident import Incident
                    inc_result = await db.execute(
                        select(Incident).where(Incident.id == pm.incident_id)
                    )
                    incident = inc_result.scalar_one_or_none()
                    if incident:
                        incident_title = incident.title
                        incident_severity = incident.severity.value if hasattr(incident.severity, 'value') else str(incident.severity) if incident.severity else None

                # Get status value safely
                status_val = pm.status.value if hasattr(pm.status, 'value') else str(pm.status)

                responses.append({
                    "id": str(pm.id),
                    "organization_id": str(pm.organization_id),
                    "incident_id": str(pm.incident_id),
                    "title": pm.title,
                    "status": status_val,
                    "summary": pm.summary,
                    "impact": pm.impact,
                    "root_cause": pm.root_cause,
                    "resolution": pm.resolution,
                    "lessons_learned": pm.lessons_learned,
                    "timeline": pm.timeline or [],
                    "action_items": pm.action_items or [],
                    "detection_time_minutes": pm.detection_time_minutes,
                    "response_time_minutes": pm.response_time_minutes,
                    "resolution_time_minutes": pm.resolution_time_minutes,
                    "total_downtime_minutes": pm.total_downtime_minutes,
                    "assessed_severity": pm.assessed_severity,
                    "customer_impact_score": pm.customer_impact_score,
                    "tags": pm.tags or [],
                    "contributing_factors": pm.contributing_factors or [],
                    "created_by_id": str(pm.created_by_id),
                    "created_by_name": creator_name,
                    "reviewed_by_id": str(pm.reviewed_by_id) if pm.reviewed_by_id else None,
                    "reviewed_by_name": None,
                    "reviewed_at": pm.reviewed_at.isoformat() if pm.reviewed_at else None,
                    "published_by_id": str(pm.published_by_id) if pm.published_by_id else None,
                    "published_at": pm.published_at.isoformat() if pm.published_at else None,
                    "created_at": pm.created_at.isoformat() if pm.created_at else None,
                    "updated_at": pm.updated_at.isoformat() if pm.updated_at else None,
                    "incident_title": incident_title,
                    "incident_severity": incident_severity
                })
            except Exception as e:
                logger.error(f"Error converting post-mortem {pm.id}: {e}")
                continue

        return {
            "post_mortems": responses,
            "total": total,
            "page": page,
            "per_page": per_page
        }
    except Exception as e:
        logger.error(f"Error in list_post_mortems: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/by-incident/{incident_id}", response_model=PostMortemResponse)
async def get_post_mortem_by_incident(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get post-mortem for a specific incident"""
    service = PostMortemService(db)
    post_mortem = await service.get_post_mortem_by_incident(
        incident_id=incident_id,
        organization_id=current_user.organization_id
    )

    if not post_mortem:
        raise HTTPException(status_code=404, detail="Post-mortem not found for this incident")

    return await service.to_response(post_mortem)


@router.get("/{post_mortem_id}", response_model=PostMortemResponse)
async def get_post_mortem(
    post_mortem_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific post-mortem"""
    service = PostMortemService(db)
    post_mortem = await service.get_post_mortem(
        post_mortem_id=post_mortem_id,
        organization_id=current_user.organization_id
    )

    if not post_mortem:
        raise HTTPException(status_code=404, detail="Post-mortem not found")

    return await service.to_response(post_mortem)


@router.patch("/{post_mortem_id}", response_model=PostMortemResponse)
async def update_post_mortem(
    post_mortem_id: UUID,
    data: PostMortemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a post-mortem"""
    service = PostMortemService(db)
    post_mortem = await service.update_post_mortem(
        post_mortem_id=post_mortem_id,
        organization_id=current_user.organization_id,
        data=data
    )

    if not post_mortem:
        raise HTTPException(status_code=404, detail="Post-mortem not found")

    return await service.to_response(post_mortem)


@router.post("/{post_mortem_id}/submit-for-review", response_model=PostMortemResponse)
async def submit_for_review(
    post_mortem_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Submit a post-mortem for review"""
    service = PostMortemService(db)
    post_mortem = await service.submit_for_review(
        post_mortem_id=post_mortem_id,
        organization_id=current_user.organization_id
    )

    if not post_mortem:
        raise HTTPException(status_code=404, detail="Post-mortem not found")

    return await service.to_response(post_mortem)


@router.post("/{post_mortem_id}/publish", response_model=PostMortemResponse)
async def publish_post_mortem(
    post_mortem_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Publish a post-mortem"""
    service = PostMortemService(db)
    post_mortem = await service.publish_post_mortem(
        post_mortem_id=post_mortem_id,
        organization_id=current_user.organization_id,
        user_id=current_user.id
    )

    if not post_mortem:
        raise HTTPException(status_code=404, detail="Post-mortem not found")

    return await service.to_response(post_mortem)


@router.post("/{post_mortem_id}/archive", response_model=PostMortemResponse)
async def archive_post_mortem(
    post_mortem_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Archive a post-mortem"""
    service = PostMortemService(db)
    post_mortem = await service.archive_post_mortem(
        post_mortem_id=post_mortem_id,
        organization_id=current_user.organization_id
    )

    if not post_mortem:
        raise HTTPException(status_code=404, detail="Post-mortem not found")

    return await service.to_response(post_mortem)


@router.delete("/{post_mortem_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post_mortem(
    post_mortem_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a post-mortem"""
    service = PostMortemService(db)
    deleted = await service.delete_post_mortem(
        post_mortem_id=post_mortem_id,
        organization_id=current_user.organization_id
    )

    if not deleted:
        raise HTTPException(status_code=404, detail="Post-mortem not found")


# Comment endpoints
@router.post("/{post_mortem_id}/comments", response_model=PostMortemCommentResponse, status_code=status.HTTP_201_CREATED)
async def add_comment(
    post_mortem_id: UUID,
    data: PostMortemCommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a comment to a post-mortem"""
    service = PostMortemService(db)
    comment = await service.add_comment(
        post_mortem_id=post_mortem_id,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        data=data
    )

    if not comment:
        raise HTTPException(status_code=404, detail="Post-mortem not found")

    return PostMortemCommentResponse(
        id=comment.id,
        post_mortem_id=comment.post_mortem_id,
        user_id=comment.user_id,
        user_name=current_user.full_name,
        content=comment.content,
        section=comment.section,
        created_at=comment.created_at,
        updated_at=comment.updated_at
    )


@router.get("/{post_mortem_id}/comments", response_model=list[PostMortemCommentResponse])
async def get_comments(
    post_mortem_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all comments for a post-mortem"""
    service = PostMortemService(db)
    comments = await service.get_comments(
        post_mortem_id=post_mortem_id,
        organization_id=current_user.organization_id
    )

    # Get user names for comments
    from sqlalchemy import select
    from app.models.user import User as UserModel

    result = []
    for comment in comments:
        user_result = await db.execute(
            select(UserModel).where(UserModel.id == comment.user_id)
        )
        user = user_result.scalar_one_or_none()

        result.append(PostMortemCommentResponse(
            id=comment.id,
            post_mortem_id=comment.post_mortem_id,
            user_id=comment.user_id,
            user_name=user.full_name if user else None,
            content=comment.content,
            section=comment.section,
            created_at=comment.created_at,
            updated_at=comment.updated_at
        ))

    return result


# Action item endpoints
@router.patch("/{post_mortem_id}/action-items/{action_item_id}", response_model=PostMortemResponse)
async def update_action_item_status(
    post_mortem_id: UUID,
    action_item_id: str,
    status: str = Query(..., pattern="^(open|in_progress|completed)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update the status of an action item"""
    service = PostMortemService(db)
    post_mortem = await service.update_action_item_status(
        post_mortem_id=post_mortem_id,
        organization_id=current_user.organization_id,
        action_item_id=action_item_id,
        status=status
    )

    if not post_mortem:
        raise HTTPException(status_code=404, detail="Post-mortem not found")

    return await service.to_response(post_mortem)
