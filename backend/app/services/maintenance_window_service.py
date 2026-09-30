# backend/app/services/maintenance_window_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from uuid import UUID
import logging

from app.models.maintenance_window import MaintenanceWindow
from app.models.user import User
from app.schemas.maintenance_window import (
    MaintenanceWindowCreate,
    MaintenanceWindowUpdate,
    MaintenanceWindowResponse
)

logger = logging.getLogger(__name__)


class MaintenanceWindowService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_window(
        self,
        organization_id: UUID,
        user_id: UUID,
        data: MaintenanceWindowCreate
    ) -> MaintenanceWindow:
        """Create a new maintenance window"""
        window = MaintenanceWindow(
            organization_id=organization_id,
            created_by_id=user_id,
            name=data.name,
            description=data.description,
            start_time=data.start_time,
            end_time=data.end_time,
            services=data.services,
            tags=data.tags,
            suppress_alerts=data.suppress_alerts,
            auto_resolve_incidents=data.auto_resolve_incidents,
            is_recurring=data.is_recurring,
            recurrence_pattern=data.recurrence_pattern.model_dump() if data.recurrence_pattern else None,
            notify_before_minutes=data.notify_before_minutes,
            is_active=True
        )

        self.db.add(window)
        await self.db.commit()
        await self.db.refresh(window)

        logger.info(f"Created maintenance window: {window.name} ({window.id})")
        return window

    async def get_window(
        self,
        window_id: UUID,
        organization_id: UUID
    ) -> Optional[MaintenanceWindow]:
        """Get a specific maintenance window"""
        result = await self.db.execute(
            select(MaintenanceWindow).where(
                and_(
                    MaintenanceWindow.id == window_id,
                    MaintenanceWindow.organization_id == organization_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_windows(
        self,
        organization_id: UUID,
        page: int = 1,
        per_page: int = 20,
        include_past: bool = False,
        include_cancelled: bool = False
    ) -> Tuple[List[MaintenanceWindow], int]:
        """List maintenance windows with pagination"""
        query = select(MaintenanceWindow).where(
            MaintenanceWindow.organization_id == organization_id
        )

        if not include_past:
            query = query.where(MaintenanceWindow.end_time >= datetime.utcnow())

        if not include_cancelled:
            query = query.where(MaintenanceWindow.is_cancelled == False)

        # Count total using the same filters as the listing
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Get paginated results
        query = query.order_by(MaintenanceWindow.start_time.asc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(query)
        windows = result.scalars().all()

        return list(windows), total

    async def update_window(
        self,
        window_id: UUID,
        organization_id: UUID,
        data: MaintenanceWindowUpdate
    ) -> Optional[MaintenanceWindow]:
        """Update a maintenance window"""
        window = await self.get_window(window_id, organization_id)
        if not window:
            return None

        update_data = data.model_dump(exclude_unset=True)

        # Handle recurrence pattern separately
        if 'recurrence_pattern' in update_data:
            pattern = update_data.pop('recurrence_pattern')
            window.recurrence_pattern = pattern.model_dump() if pattern else None

        for field, value in update_data.items():
            setattr(window, field, value)

        await self.db.commit()
        await self.db.refresh(window)

        logger.info(f"Updated maintenance window: {window.name} ({window.id})")
        return window

    async def cancel_window(
        self,
        window_id: UUID,
        organization_id: UUID,
        user_id: UUID
    ) -> Optional[MaintenanceWindow]:
        """Cancel a maintenance window"""
        window = await self.get_window(window_id, organization_id)
        if not window:
            return None

        window.is_cancelled = True
        window.cancelled_at = datetime.utcnow()
        window.cancelled_by_id = user_id

        await self.db.commit()
        await self.db.refresh(window)

        logger.info(f"Cancelled maintenance window: {window.name} ({window.id})")
        return window

    async def delete_window(
        self,
        window_id: UUID,
        organization_id: UUID
    ) -> bool:
        """Permanently delete a maintenance window"""
        window = await self.get_window(window_id, organization_id)
        if not window:
            return False

        await self.db.delete(window)
        await self.db.commit()

        logger.info(f"Deleted maintenance window: {window_id}")
        return True

    async def get_active_windows(
        self,
        organization_id: UUID,
        service: Optional[str] = None
    ) -> List[MaintenanceWindow]:
        """Get currently active maintenance windows"""
        now = datetime.utcnow()

        query = select(MaintenanceWindow).where(
            and_(
                MaintenanceWindow.organization_id == organization_id,
                MaintenanceWindow.is_active == True,
                MaintenanceWindow.is_cancelled == False,
                MaintenanceWindow.start_time <= now,
                MaintenanceWindow.end_time >= now
            )
        )

        result = await self.db.execute(query)
        windows = result.scalars().all()

        # Filter by service if specified
        if service:
            windows = [w for w in windows if service in (w.services or [])]

        return list(windows)

    async def is_service_in_maintenance(
        self,
        organization_id: UUID,
        service: str
    ) -> Tuple[bool, List[MaintenanceWindow]]:
        """Check if a specific service is currently in a maintenance window"""
        active_windows = await self.get_active_windows(organization_id, service)
        return len(active_windows) > 0, active_windows

    async def should_suppress_alert(
        self,
        organization_id: UUID,
        service: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """Check if an alert should be suppressed due to maintenance"""
        active_windows = await self.get_active_windows(organization_id)

        for window in active_windows:
            if not window.suppress_alerts:
                continue

            # Check service match
            if service and window.services:
                if service in window.services:
                    return True

            # Check tag match
            if tags and window.tags:
                if any(tag in window.tags for tag in tags):
                    return True

            # If window has no service/tag filters, it applies to all
            if not window.services and not window.tags:
                return True

        return False

    async def get_upcoming_windows(
        self,
        organization_id: UUID,
        hours_ahead: int = 24
    ) -> List[MaintenanceWindow]:
        """Get maintenance windows starting within the specified hours"""
        now = datetime.utcnow()
        future = now + timedelta(hours=hours_ahead)

        result = await self.db.execute(
            select(MaintenanceWindow).where(
                and_(
                    MaintenanceWindow.organization_id == organization_id,
                    MaintenanceWindow.is_active == True,
                    MaintenanceWindow.is_cancelled == False,
                    MaintenanceWindow.start_time >= now,
                    MaintenanceWindow.start_time <= future
                )
            ).order_by(MaintenanceWindow.start_time.asc())
        )

        return list(result.scalars().all())

    async def auto_resolve_maintenance_incidents(
        self,
        window_id: UUID,
        organization_id: UUID
    ) -> int:
        """
        Auto-resolve incidents created during a maintenance window.
        Called when a maintenance window ends and has auto_resolve_incidents=True.
        Returns the number of resolved incidents.
        """
        from app.models.incident import Incident

        window = await self.get_window(window_id, organization_id)
        if not window:
            logger.warning(f"Maintenance window {window_id} not found")
            return 0

        if not window.auto_resolve_incidents:
            logger.info(f"Maintenance window {window_id} does not have auto-resolve enabled")
            return 0

        # Find incidents created during the maintenance window
        query = select(Incident).where(
            and_(
                Incident.organization_id == organization_id,
                Incident.created_at >= window.start_time,
                Incident.created_at <= window.end_time,
                Incident.status.in_(['open', 'acknowledged'])
            )
        )

        # Filter by service if maintenance window has specific services
        result = await self.db.execute(query)
        incidents = result.scalars().all()

        resolved_count = 0
        now = datetime.utcnow()

        for incident in incidents:
            # Check if incident matches maintenance window's services/tags
            should_resolve = False

            if window.services:
                # Check if incident tags contain any of the maintenance services
                incident_tags = incident.tags or []
                for service in window.services:
                    if any(service.lower() in tag.lower() for tag in incident_tags):
                        should_resolve = True
                        break
                    # Also check incident title/description for service name
                    if service.lower() in (incident.title or '').lower():
                        should_resolve = True
                        break
            else:
                # No specific services = applies to all incidents during window
                should_resolve = True

            if should_resolve:
                incident.status = 'resolved'
                incident.resolved_at = now
                incident.updated_at = now
                resolved_count += 1
                logger.info(f"Auto-resolved incident {incident.id} due to maintenance window {window_id} ending")

        if resolved_count > 0:
            await self.db.commit()
            logger.info(f"Auto-resolved {resolved_count} incidents for maintenance window {window_id}")

        return resolved_count

    async def get_ended_windows_needing_resolution(
        self,
        organization_id: Optional[UUID] = None
    ) -> List[MaintenanceWindow]:
        """
        Get maintenance windows that have ended and need incident auto-resolution.
        Used by background worker.
        """
        now = datetime.utcnow()
        lookback = now - timedelta(hours=1)  # Check windows that ended in the last hour

        query = select(MaintenanceWindow).where(
            and_(
                MaintenanceWindow.auto_resolve_incidents == True,
                MaintenanceWindow.is_cancelled == False,
                MaintenanceWindow.end_time <= now,
                MaintenanceWindow.end_time >= lookback
            )
        )

        if organization_id:
            query = query.where(MaintenanceWindow.organization_id == organization_id)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    def to_response(
        self,
        window: MaintenanceWindow,
        created_by_name: Optional[str] = None
    ) -> MaintenanceWindowResponse:
        """Convert model to response schema"""
        from datetime import timezone
        now = datetime.now(timezone.utc)
        # Make comparison safe for both naive and aware datetimes
        try:
            start = window.start_time.replace(tzinfo=timezone.utc) if window.start_time.tzinfo is None else window.start_time
            end = window.end_time.replace(tzinfo=timezone.utc) if window.end_time.tzinfo is None else window.end_time
            is_currently_active = (
                window.is_active and
                not window.is_cancelled and
                start <= now <= end
            )
        except Exception:
            is_currently_active = False

        return MaintenanceWindowResponse(
            id=window.id,
            organization_id=window.organization_id,
            name=window.name,
            description=window.description,
            start_time=window.start_time,
            end_time=window.end_time,
            services=window.services or [],
            tags=window.tags or [],
            suppress_alerts=window.suppress_alerts,
            auto_resolve_incidents=window.auto_resolve_incidents,
            is_recurring=window.is_recurring,
            recurrence_pattern=window.recurrence_pattern,
            is_active=window.is_active,
            is_cancelled=window.is_cancelled,
            cancelled_at=window.cancelled_at,
            notify_before_minutes=window.notify_before_minutes,
            notification_sent=window.notification_sent,
            created_by_id=window.created_by_id,
            created_by_name=created_by_name,
            created_at=window.created_at,
            updated_at=window.updated_at,
            is_currently_active=is_currently_active
        )
