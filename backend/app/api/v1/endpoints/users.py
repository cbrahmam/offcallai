# backend/app/api/v1/endpoints/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.database import get_async_session
from app.models.user import User
from app.core.security import get_current_user

router = APIRouter()

@router.get("/me")
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current user profile - CRITICAL MISSING ENDPOINT"""
    try:
        return {
            "id": str(current_user.id),
            "email": current_user.email,
            "full_name": current_user.full_name,
            "role": current_user.role,
            "organization_id": str(current_user.organization_id),
            "is_active": current_user.is_active,
            "is_verified": getattr(current_user, 'is_verified', False),
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
            "updated_at": current_user.updated_at.isoformat() if hasattr(current_user, 'updated_at') and current_user.updated_at else None,
            "last_login": current_user.last_login_at.isoformat() if hasattr(current_user, 'last_login_at') and current_user.last_login_at else None,
            "notification_preferences": getattr(current_user, 'notification_preferences', {}),
            "phone_number": getattr(current_user, 'phone_number', None),
            "timezone": getattr(current_user, 'timezone', 'UTC'),
            "skills": getattr(current_user, 'skills', [])
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user profile: {str(e)}"
        )

@router.patch("/me")
async def update_current_user(
    update_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Update current user profile"""
    try:
        # Update allowed fields
        if "full_name" in update_data and update_data["full_name"]:
            current_user.full_name = update_data["full_name"]
        
        if "phone_number" in update_data:
            current_user.phone_number = update_data["phone_number"]
            
        if "timezone" in update_data and update_data["timezone"]:
            current_user.timezone = update_data["timezone"]
            
        if "notification_preferences" in update_data and isinstance(update_data["notification_preferences"], dict):
            current_user.notification_preferences = update_data["notification_preferences"]
            
        if "skills" in update_data and isinstance(update_data["skills"], list):
            current_user.skills = update_data["skills"]
            
        # Update timestamp
        if hasattr(current_user, 'updated_at'):
            current_user.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(current_user)
        
        return {
            "message": "Profile updated successfully",
            "user": {
                "id": str(current_user.id),
                "email": current_user.email,
                "full_name": current_user.full_name,
                "role": current_user.role,
                "organization_id": str(current_user.organization_id),
                "phone_number": getattr(current_user, 'phone_number', None),
                "timezone": getattr(current_user, 'timezone', 'UTC'),
                "notification_preferences": getattr(current_user, 'notification_preferences', {}),
                "skills": getattr(current_user, 'skills', [])
            }
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user: {str(e)}"
        )

@router.get("/")
async def list_organization_users(
    page: int = 1,
    per_page: int = 20,
    role: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """List users in organization (admin only)"""
    
    # Only admins can list users
    if current_user.role not in ["admin", "owner"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can list organization users"
        )
    
    try:
        # Build query
        query = select(User).where(
            and_(
                User.organization_id == current_user.organization_id,
                User.is_active == True
            )
        )
        
        # Filter by role if provided
        if role:
            query = query.where(User.role == role)
        
        # Get total count
        count_result = await db.execute(query)
        total = len(count_result.scalars().all())
        
        # Apply pagination
        query = query.offset((page - 1) * per_page).limit(per_page)
        result = await db.execute(query)
        users = result.scalars().all()
        
        # Convert to response format
        user_list = []
        for user in users:
            user_list.append({
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login": user.last_login_at.isoformat() if hasattr(user, 'last_login_at') and user.last_login_at else None
            })
        
        return {
            "users": user_list,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list users: {str(e)}"
        )

@router.get("/profile/settings")
async def get_user_settings(
    current_user: User = Depends(get_current_user)
):
    """Get user settings and preferences"""
    
    return {
        "user_id": str(current_user.id),
        "notification_preferences": getattr(current_user, 'notification_preferences', {
            "email": True,
            "sms": False,
            "slack": True,
            "push": True
        }),
        "timezone": getattr(current_user, 'timezone', 'UTC'),
        "skills": getattr(current_user, 'skills', []),
        "on_call_preferences": {
            "auto_escalate": True,
            "escalation_delay_minutes": 15,
            "max_incidents_per_day": 50
        }
    }

@router.patch("/profile/settings")
async def update_user_settings(
    settings_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Update user settings and preferences"""

    try:
        updated = False

        if "notification_preferences" in settings_data:
            current_user.notification_preferences = settings_data["notification_preferences"]
            updated = True

        if "timezone" in settings_data:
            current_user.timezone = settings_data["timezone"]
            updated = True

        if "skills" in settings_data:
            current_user.skills = settings_data["skills"]
            updated = True

        if updated:
            if hasattr(current_user, 'updated_at'):
                current_user.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(current_user)

        return {
            "message": "Settings updated successfully",
            "settings": {
                "notification_preferences": getattr(current_user, 'notification_preferences', {}),
                "timezone": getattr(current_user, 'timezone', 'UTC'),
                "skills": getattr(current_user, 'skills', [])
            }
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update settings: {str(e)}"
        )


# ==================== UI PREFERENCES ENDPOINTS ====================

DEFAULT_UI_PREFERENCES = {
    "sidebar_favorites": ["dashboard", "incidents", "alerts", "logs"],
    "sidebar_favorites_order": ["dashboard", "incidents", "alerts", "logs"],
    "sidebar_collapsed": False,
    "all_features_expanded": True,
}

@router.get("/ui-preferences")
async def get_ui_preferences(
    current_user: User = Depends(get_current_user)
):
    """Get user UI preferences (sidebar favorites, etc.)"""

    ui_prefs = getattr(current_user, 'ui_preferences', None) or DEFAULT_UI_PREFERENCES

    return {
        "sidebar_favorites": ui_prefs.get("sidebar_favorites", DEFAULT_UI_PREFERENCES["sidebar_favorites"]),
        "sidebar_favorites_order": ui_prefs.get("sidebar_favorites_order", DEFAULT_UI_PREFERENCES["sidebar_favorites_order"]),
        "sidebar_collapsed": ui_prefs.get("sidebar_collapsed", False),
        "all_features_expanded": ui_prefs.get("all_features_expanded", True),
    }


@router.patch("/ui-preferences")
async def update_ui_preferences(
    preferences: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Update user UI preferences (sidebar favorites, collapse state, etc.)"""

    try:
        # Get existing preferences or use defaults
        current_prefs = getattr(current_user, 'ui_preferences', None) or DEFAULT_UI_PREFERENCES.copy()

        # Update only allowed fields
        allowed_fields = ["sidebar_favorites", "sidebar_favorites_order", "sidebar_collapsed", "all_features_expanded"]

        for field in allowed_fields:
            if field in preferences:
                current_prefs[field] = preferences[field]

        # Validate favorites are valid nav item IDs
        valid_nav_ids = [
            "dashboard", "incidents", "alerts", "alert-rules", "on-call-schedules",
            "maintenance-windows", "infrastructure", "containers", "databases", "network",
            "logs", "apm", "profiling", "errors", "rum", "runbooks", "auto-remediation",
            "anomaly-detection", "custom-dashboards", "synthetic", "deployments",
            "analytics", "slos", "cost-attribution", "services", "post-mortems",
            "settings", "docs"
        ]

        if "sidebar_favorites" in preferences:
            current_prefs["sidebar_favorites"] = [
                fav for fav in preferences["sidebar_favorites"]
                if fav in valid_nav_ids
            ]

        if "sidebar_favorites_order" in preferences:
            current_prefs["sidebar_favorites_order"] = [
                fav for fav in preferences["sidebar_favorites_order"]
                if fav in valid_nav_ids
            ]

        # Save to user
        current_user.ui_preferences = current_prefs

        if hasattr(current_user, 'updated_at'):
            current_user.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(current_user)

        return {
            "message": "UI preferences updated successfully",
            "ui_preferences": current_prefs
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update UI preferences: {str(e)}"
        )


# ==================== USER BY ID (must be last — catch-all route) ====================

@router.get("/{user_id}")
async def get_user_by_id(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get user by ID (same organization only)"""

    try:
        result = await db.execute(
            select(User).where(
                and_(
                    User.id == user_id,
                    User.organization_id == current_user.organization_id,
                    User.is_active == True
                )
            )
        )

        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        return {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "organization_id": str(user.organization_id),
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login": user.last_login_at.isoformat() if hasattr(user, 'last_login_at') and user.last_login_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user: {str(e)}"
        )