# backend/app/api/v1/endpoints/organizations.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Dict, Any
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
import secrets
import json
import logging

from app.database import get_async_session
from app.models.organization import Organization
from app.models.user import User
from app.models.team import Team
from app.core.security import get_current_user
from app.services.organization_service import OrganizationService

router = APIRouter()
logger = logging.getLogger(__name__)


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: str = "member"

@router.get("/me")
async def get_my_organization(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get current user's organization"""
    try:
        result = await db.execute(
            select(Organization).where(Organization.id == current_user.organization_id)
        )
        organization = result.scalar_one_or_none()
        
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        return {
            "id": str(organization.id),
            "name": organization.name,
            "slug": organization.slug,
            "is_active": organization.is_active,
            "max_users": organization.max_users or 5,
            "max_incidents_per_month": organization.max_incidents_per_month or 100,
            "created_at": organization.created_at.isoformat() if organization.created_at else None,
            "updated_at": organization.updated_at.isoformat() if organization.updated_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Organization error: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching organization: {str(e)}")

@router.get("/me/members")
async def get_organization_members(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get organization members - MISSING ENDPOINT THAT FRONTEND CALLS"""
    try:
        result = await db.execute(
            select(User).where(
                User.organization_id == current_user.organization_id,
                User.is_active == True
            )
        )
        users = result.scalars().all()
        
        return {
            "members": [{
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login_at": user.last_login_at.isoformat() if hasattr(user, 'last_login_at') and user.last_login_at else None
            } for user in users],
            "total": len(users)
        }
        
    except Exception as e:
        print(f"Members error: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching members: {str(e)}")

@router.get("/teams")
async def list_organization_teams(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """List the organization's teams, with member counts."""
    try:
        result = await db.execute(
            select(Team)
            .where(Team.organization_id == current_user.organization_id)
            .options(selectinload(Team.members))
            .order_by(Team.name)
        )
        teams = result.scalars().all()

        return {
            "teams": [
                {
                    "id": str(team.id),
                    "name": team.name,
                    "description": team.description,
                    "is_active": team.is_active,
                    "member_count": len(team.members),
                    "created_at": team.created_at.isoformat() if team.created_at else None,
                }
                for team in teams
            ],
            "total": len(teams),
        }
    except Exception as e:
        logger.error(f"Error listing teams: {e}")
        raise HTTPException(status_code=500, detail="Failed to list teams")


@router.get("/stats")
async def get_organization_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get organization statistics"""
    try:
        org_service = OrganizationService(db)
        stats = await org_service.get_organization_stats(str(current_user.organization_id))
        return stats
        
    except Exception as e:
        print(f"Organization stats error: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching organization stats: {str(e)}")

@router.patch("/me")
async def update_my_organization(
    update_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Update current user's organization (admin only)"""
    try:
        # Only org admins can update organization
        if current_user.role not in ["admin", "owner"]:
            raise HTTPException(status_code=403, detail="Only organization admins can update organization")
        
        org_service = OrganizationService(db)
        
        # Create update object
        from app.schemas.organization import OrganizationUpdate
        org_update = OrganizationUpdate(**update_data)
        
        updated_org = await org_service.update_organization(
            str(current_user.organization_id),
            org_update
        )
        
        if not updated_org:
            raise HTTPException(status_code=404, detail="Organization not found")
            
        return {
            "id": str(updated_org.id),
            "name": updated_org.name,
            "updated_at": updated_org.updated_at.isoformat() if updated_org.updated_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Organization update error: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating organization: {str(e)}")


@router.post("/me/invite")
async def invite_member(
    invite_data: InviteMemberRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Invite a new member to the organization.
    Sends an email with an invitation link.
    """
    try:
        # Only admins can invite members
        if current_user.role not in ["admin", "owner"]:
            raise HTTPException(status_code=403, detail="Only organization admins can invite members")

        # Check if user already exists in the organization
        result = await db.execute(
            select(User).where(
                User.email == invite_data.email,
                User.organization_id == current_user.organization_id
            )
        )
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(status_code=400, detail="User already exists in this organization")

        # Get organization details
        org_result = await db.execute(
            select(Organization).where(Organization.id == current_user.organization_id)
        )
        organization = org_result.scalar_one_or_none()
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")

        # Generate invitation token
        invite_token = secrets.token_urlsafe(32)
        token_expiry = datetime.utcnow() + timedelta(days=7)  # Valid for 7 days
        from app.core.config import settings

        invite_data_json = {
            "email": invite_data.email,
            "role": invite_data.role,
            "organization_id": str(current_user.organization_id),
            "organization_name": organization.name,
            "invited_by": current_user.full_name,
            "invited_by_email": current_user.email,
            "created_at": datetime.utcnow().isoformat()
        }

        # Try to store invitation in Redis
        redis_stored = False
        try:
            from app.database import get_redis
            redis = get_redis()
            await redis.setex(
                f"org_invite:{invite_token}",
                604800,  # 7 days in seconds
                json.dumps(invite_data_json)
            )
            redis_stored = True
        except Exception as redis_error:
            logger.warning(f"Redis not available for storing invite, continuing without: {redis_error}")

        # Send invitation email
        from app.services.email_service import EmailService

        frontend_url = settings.FRONTEND_URL
        invite_link = f"{frontend_url}/auth/register?invite={invite_token}"

        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="text-align: center; padding: 20px;">
                <h1 style="color: #2563eb;">OffCall AI</h1>
            </div>
            <div style="background: #f8fafc; padding: 24px; border-radius: 8px;">
                <h2 style="color: #1e293b; margin-top: 0;">You're Invited!</h2>
                <p style="color: #475569;">Hi,</p>
                <p style="color: #475569;">
                    <strong>{current_user.full_name}</strong> has invited you to join
                    <strong>{organization.name}</strong> on OffCall AI.
                </p>
                <p style="color: #475569;">
                    OffCall AI is an incident response platform that helps teams manage alerts,
                    on-call schedules, and incident resolution with AI assistance.
                </p>
                <div style="text-align: center; margin: 32px 0;">
                    <a href="{invite_link}"
                       style="background: #2563eb; color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block;">
                        Accept Invitation
                    </a>
                </div>
                <p style="color: #64748b; font-size: 14px;">This invitation expires in 7 days.</p>
            </div>
            <div style="text-align: center; padding: 20px; color: #94a3b8; font-size: 12px;">
                <p>OffCall AI - Incident Response Platform</p>
            </div>
        </div>
        """

        email_sent = await EmailService.send_email(
            to_email=invite_data.email,
            subject=f"{current_user.full_name} invited you to join {organization.name} on OffCall AI",
            body=f"You've been invited to join {organization.name}. Click here to accept: {invite_link}",
            html_content=html_content
        )

        if not email_sent:
            logger.warning(f"Failed to send invitation email to {invite_data.email}")

        logger.info(f"Invitation created for {invite_data.email} for org {organization.name}")

        # Return success with invite link (for manual sharing if email failed)
        response = {
            "message": f"Invitation {'sent to' if email_sent else 'created for'} {invite_data.email}",
            "success": True,
            "email": invite_data.email,
            "email_sent": email_sent,
        }

        # Include invite link if email wasn't sent (so user can share manually)
        if not email_sent:
            response["invite_link"] = invite_link
            response["message"] = f"Invitation created for {invite_data.email}. Email sending failed - please share the invite link manually."

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Invite member error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send invitation: {str(e)}")