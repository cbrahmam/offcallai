# backend/app/api/v1/endpoints/notifications.py
# COMPLETE REWRITE - PRODUCTION READY
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update, desc, func, delete
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import logging

from app.database import get_async_session
from app.models.user import User
from app.models.notification import Notification
from app.core.security import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

from pydantic import BaseModel, Field

class NotificationCreate(BaseModel):
    type: str
    title: str
    message: str
    severity: Optional[str] = None
    incident_id: Optional[str] = None
    action_url: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None

class NotificationResponse(BaseModel):
    id: str
    type: str
    title: str
    message: str
    severity: Optional[str] = None
    incident_id: Optional[str] = None
    action_url: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
    read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

@router.get("/")
async def get_notifications(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=100),
    unread_only: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get notifications - FIXED RESPONSE FORMAT"""
    
    try:
        logger.info(f"Fetching notifications for user {current_user.id}")
        
        # Build query
        query = select(Notification).where(Notification.user_id == current_user.id)
        
        if unread_only:
            query = query.where(Notification.read == False)
        
        # Get counts
        total_result = await db.execute(
            select(func.count()).select_from(Notification).where(
                Notification.user_id == current_user.id
            )
        )
        total = total_result.scalar() or 0
        
        unread_result = await db.execute(
            select(func.count()).select_from(Notification).where(
                and_(
                    Notification.user_id == current_user.id,
                    Notification.read == False
                )
            )
        )
        unread_count = unread_result.scalar() or 0
        
        # Get notifications
        query = query.order_by(desc(Notification.created_at))
        query = query.offset((page - 1) * per_page).limit(per_page)
        
        result = await db.execute(query)
        notifications = result.scalars().all()
        
        logger.info(f"Found {len(notifications)} notifications, {unread_count} unread")
        
        # Format response
        notification_list = []
        for n in notifications:
            notification_list.append({
                "id": str(n.id),
                "type": n.type,
                "title": n.title,
                "message": n.message,
                "severity": n.severity,
                "incident_id": str(n.incident_id) if n.incident_id else None,
                "action_url": n.action_url,
                "extra_data": n.extra_data or {},
                "read": n.read,
                "read_at": n.read_at,
                "created_at": n.created_at
            })
        
        # CRITICAL: Frontend expects this exact format
        return {
            "notifications": notification_list,
            "stats": {
                "total_count": total,
                "unread_count": unread_count,
                "incidents_count": 0,
                "alerts_count": 0,
                "system_count": 0
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching notifications: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Mark single notification as read"""
    
    try:
        result = await db.execute(
            select(Notification).where(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == current_user.id
                )
            )
        )
        
        notification = result.scalar_one_or_none()
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        notification.read = True
        notification.read_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(notification)
        
        logger.info(f"Marked notification {notification_id} as read")
        
        return {
            "id": str(notification.id),
            "type": notification.type,
            "title": notification.title,
            "message": notification.message,
            "severity": notification.severity,
            "incident_id": str(notification.incident_id) if notification.incident_id else None,
            "action_url": notification.action_url,
            "extra_data": notification.extra_data or {},
            "read": notification.read,
            "read_at": notification.read_at,
            "created_at": notification.created_at
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking notification as read: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Mark all notifications as read"""
    
    try:
        await db.execute(
            update(Notification)
            .where(
                and_(
                    Notification.user_id == current_user.id,
                    Notification.read == False
                )
            )
            .values(read=True, read_at=datetime.utcnow())
        )
        
        await db.commit()
        logger.info(f"Marked all notifications as read for user {current_user.id}")
        
        return {"message": "All notifications marked as read", "success": True}
        
    except Exception as e:
        logger.error(f"Error marking all as read: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Delete single notification"""
    
    try:
        result = await db.execute(
            select(Notification).where(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == current_user.id
                )
            )
        )
        
        notification = result.scalar_one_or_none()
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        await db.delete(notification)
        await db.commit()
        
        logger.info(f"Deleted notification {notification_id}")
        
        return {"message": "Notification deleted", "success": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting notification: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/clear-all")
async def clear_all_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Delete all notifications"""
    
    try:
        await db.execute(
            delete(Notification).where(
                Notification.user_id == current_user.id
            )
        )
        
        await db.commit()
        logger.info(f"Cleared all notifications for user {current_user.id}")
        
        return {"message": "All notifications cleared", "success": True}
        
    except Exception as e:
        logger.error(f"Error clearing all notifications: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get unread count only"""
    
    try:
        result = await db.execute(
            select(func.count()).select_from(Notification).where(
                and_(
                    Notification.user_id == current_user.id,
                    Notification.read == False
                )
            )
        )
        
        unread_count = result.scalar() or 0
        
        return {"unread_count": unread_count}
        
    except Exception as e:
        logger.error(f"Error getting unread count: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test")
async def create_test_notification(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Create a test notification for debugging"""
    
    try:
        notification = Notification(
            id=uuid.uuid4(),
            user_id=current_user.id,
            organization_id=current_user.organization_id,
            type="system",
            title="Test Notification",
            message="This is a test notification created at " + datetime.utcnow().isoformat(),
            severity="medium",
            read=False,
            created_at=datetime.utcnow()
        )
        
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        
        logger.info(f"Created test notification {notification.id}")
        
        return {
            "id": str(notification.id),
            "message": "Test notification created successfully"
        }
        
    except Exception as e:
        logger.error(f"Error creating test notification: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))