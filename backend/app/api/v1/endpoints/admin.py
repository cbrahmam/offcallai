# backend/app/api/v1/endpoints/admin.py - ADMIN DASHBOARD ANALYTICS
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, extract
from datetime import datetime, timedelta
from typing import Optional, List
import logging

from app.database import get_async_session
from app.core.security import get_current_user
from app.models.user import User
from app.models.organization import Organization
from app.models.incident import Incident
from app.models.integration import Integration
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

# ============= RESPONSE MODELS =============

class UserMetrics(BaseModel):
    total_users: int
    new_users_today: int
    new_users_this_week: int
    new_users_this_month: int
    active_users_today: int
    active_users_this_week: int
    active_users_this_month: int

class UsageMetrics(BaseModel):
    total_incidents: int
    incidents_today: int
    incidents_this_week: int
    incidents_this_month: int
    total_integrations: int
    active_integrations: int
    total_organizations: int
    active_organizations: int

class UserGrowthData(BaseModel):
    date: str
    new_users: int
    total_users: int

class SystemHealthMetrics(BaseModel):
    avg_response_time: float
    error_rate: float
    uptime_percentage: float
    total_api_calls_today: int

# ============= SECURITY HELPER =============

async def get_super_admin_user(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> User:
    """Verify user is a super admin"""
    import os

    # SECURITY: Load super admin emails from environment variable
    # Format: comma-separated list of emails
    admin_emails_env = os.getenv('SUPER_ADMIN_EMAILS', '')
    SUPER_ADMIN_EMAILS = [email.strip() for email in admin_emails_env.split(',') if email.strip()]

    # Fallback for development only
    if not SUPER_ADMIN_EMAILS and os.getenv('ENVIRONMENT', 'development') == 'development':
        logger.warning("SUPER_ADMIN_EMAILS not set - using empty list. Set this in production!")
        SUPER_ADMIN_EMAILS = []

    if not SUPER_ADMIN_EMAILS:
        raise HTTPException(
            status_code=503,
            detail="Admin access not configured. Set SUPER_ADMIN_EMAILS environment variable."
        )

    if current_user.email not in SUPER_ADMIN_EMAILS:
        raise HTTPException(
            status_code=403,
            detail="Only super administrators can access this endpoint"
        )

    return current_user

# ============= ANALYTICS ENDPOINTS =============

@router.get("/analytics/users", response_model=UserMetrics)
async def get_user_analytics(
    current_user: User = Depends(get_super_admin_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get user growth and activity metrics"""
    
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)
    
    try:
        # Total users
        total_result = await db.execute(select(func.count(User.id)))
        total_users = total_result.scalar() or 0
        
        # New users today
        new_today_result = await db.execute(
            select(func.count(User.id))
            .where(User.created_at >= today_start)
        )
        new_users_today = new_today_result.scalar() or 0
        
        # New users this week
        new_week_result = await db.execute(
            select(func.count(User.id))
            .where(User.created_at >= week_start)
        )
        new_users_this_week = new_week_result.scalar() or 0
        
        # New users this month
        new_month_result = await db.execute(
            select(func.count(User.id))
            .where(User.created_at >= month_start)
        )
        new_users_this_month = new_month_result.scalar() or 0
        
        # Active users (users who logged in recently)
        active_today_result = await db.execute(
            select(func.count(User.id))
            .where(User.last_login_at >= today_start)
        )
        active_users_today = active_today_result.scalar() or 0
        
        active_week_result = await db.execute(
            select(func.count(User.id))
            .where(User.last_login_at >= week_start)
        )
        active_users_this_week = active_week_result.scalar() or 0
        
        active_month_result = await db.execute(
            select(func.count(User.id))
            .where(User.last_login_at >= month_start)
        )
        active_users_this_month = active_month_result.scalar() or 0
        
        return UserMetrics(
            total_users=total_users,
            new_users_today=new_users_today,
            new_users_this_week=new_users_this_week,
            new_users_this_month=new_users_this_month,
            active_users_today=active_users_today,
            active_users_this_week=active_users_this_week,
            active_users_this_month=active_users_this_month
        )
        
    except Exception as e:
        logger.error(f"Error fetching user analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch user analytics")

@router.get("/analytics/usage", response_model=UsageMetrics)
async def get_usage_analytics(
    current_user: User = Depends(get_super_admin_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get platform usage metrics"""
    
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)
    
    try:
        # Total incidents
        total_incidents_result = await db.execute(select(func.count(Incident.id)))
        total_incidents = total_incidents_result.scalar() or 0
        
        # Incidents today
        incidents_today_result = await db.execute(
            select(func.count(Incident.id))
            .where(Incident.created_at >= today_start)
        )
        incidents_today = incidents_today_result.scalar() or 0
        
        # Incidents this week
        incidents_week_result = await db.execute(
            select(func.count(Incident.id))
            .where(Incident.created_at >= week_start)
        )
        incidents_this_week = incidents_week_result.scalar() or 0
        
        # Incidents this month
        incidents_month_result = await db.execute(
            select(func.count(Incident.id))
            .where(Incident.created_at >= month_start)
        )
        incidents_this_month = incidents_month_result.scalar() or 0
        
        # Total integrations
        total_integrations_result = await db.execute(
            select(func.count(Integration.id))
        )
        total_integrations = total_integrations_result.scalar() or 0
        
        # Active integrations
        active_integrations_result = await db.execute(
            select(func.count(Integration.id))
            .where(Integration.is_active == True)
        )
        active_integrations = active_integrations_result.scalar() or 0
        
        # Total organizations
        total_orgs_result = await db.execute(select(func.count(Organization.id)))
        total_organizations = total_orgs_result.scalar() or 0
        
        # Active organizations (with is_active=True)
        active_orgs_result = await db.execute(
            select(func.count(Organization.id))
            .where(Organization.is_active == True)
        )
        active_organizations = active_orgs_result.scalar() or 0
        
        return UsageMetrics(
            total_incidents=total_incidents,
            incidents_today=incidents_today,
            incidents_this_week=incidents_this_week,
            incidents_this_month=incidents_this_month,
            total_integrations=total_integrations,
            active_integrations=active_integrations,
            total_organizations=total_organizations,
            active_organizations=active_organizations
        )
        
    except Exception as e:
        logger.error(f"Error fetching usage analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch usage analytics")

@router.get("/analytics/user-growth", response_model=List[UserGrowthData])
async def get_user_growth_chart(
    days: int = Query(30, description="Number of days to fetch"),
    current_user: User = Depends(get_super_admin_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get daily user growth data for charts"""
    
    try:
        result = await db.execute(
            select(
                func.date(User.created_at).label('date'),
                func.count(User.id).label('new_users')
            )
            .where(User.created_at >= datetime.utcnow() - timedelta(days=days))
            .group_by(func.date(User.created_at))
            .order_by(func.date(User.created_at))
        )
        
        data = []
        total_users = 0
        
        for row in result:
            total_users += row.new_users
            data.append(UserGrowthData(
                date=row.date.isoformat(),
                new_users=row.new_users,
                total_users=total_users
            ))
        
        return data
        
    except Exception as e:
        logger.error(f"Error fetching user growth data: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch user growth data")

@router.get("/analytics/organizations")
async def list_all_organizations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_super_admin_user),
    db: AsyncSession = Depends(get_async_session)
):
    """List all organizations with details"""
    
    try:
        # Get total count
        count_result = await db.execute(select(func.count(Organization.id)))
        total = count_result.scalar() or 0
        
        # Get paginated organizations
        result = await db.execute(
            select(Organization)
            .offset((page - 1) * per_page)
            .limit(per_page)
            .order_by(Organization.created_at.desc())
        )
        
        organizations = result.scalars().all()
        
        org_list = []
        for org in organizations:
            # Get user count for this org
            user_count_result = await db.execute(
                select(func.count(User.id))
                .where(User.organization_id == org.id)
            )
            user_count = user_count_result.scalar() or 0
            
            # Get incident count for this org
            incident_count_result = await db.execute(
                select(func.count(Incident.id))
                .where(Incident.organization_id == org.id)
            )
            incident_count = incident_count_result.scalar() or 0
            
            org_list.append({
                "id": str(org.id),
                "name": org.name,
                "slug": org.slug,
                "is_active": org.is_active,
                "user_count": user_count,
                "incident_count": incident_count,
                "created_at": org.created_at.isoformat() if org.created_at else None
            })
        
        return {
            "organizations": org_list,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page
        }
        
    except Exception as e:
        logger.error(f"Error listing organizations: {e}")
        raise HTTPException(status_code=500, detail="Failed to list organizations")

@router.get("/health-check")
async def admin_health_check(
    current_user: User = Depends(get_super_admin_user)
):
    """Simple health check for admin access"""
    return {
        "status": "ok",
        "admin_email": current_user.email,
        "timestamp": datetime.utcnow().isoformat()
    }