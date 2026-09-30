# backend/app/services/rum_service.py
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_, Integer
from sqlalchemy.orm import selectinload

from ..models.rum import (
    RUMApplication, RUMSession, RUMPageView, RUMError,
    RUMUserAction, RUMResource, RUMAlert
)
from ..schemas.rum import (
    RUMApplicationCreate, RUMApplicationUpdate,
    RUMSessionCreate, RUMSessionUpdate,
    RUMPageViewCreate, RUMErrorCreate, RUMUserActionCreate,
    RUMResourceCreate, RUMStats, CoreWebVitalsStats
)


class RUMService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== Application Management ====================

    async def list_applications(
        self,
        organization_id: UUID,
    ) -> Dict[str, Any]:
        """List all RUM applications for an organization"""
        query = select(RUMApplication).where(
            RUMApplication.organization_id == organization_id
        ).order_by(desc(RUMApplication.created_at))

        result = await self.db.execute(query)
        items = result.scalars().all()

        return {
            "items": items,
            "total": len(items)
        }

    async def create_application(
        self,
        organization_id: UUID,
        app_data: RUMApplicationCreate
    ) -> RUMApplication:
        """Create a new RUM application"""
        # Generate unique API key
        api_key = f"rum_{secrets.token_hex(24)}"

        application = RUMApplication(
            organization_id=organization_id,
            api_key=api_key,
            **app_data.model_dump()
        )

        self.db.add(application)
        await self.db.commit()
        await self.db.refresh(application)

        return application

    async def get_application(
        self,
        app_id: UUID,
        organization_id: UUID
    ) -> Optional[RUMApplication]:
        """Get a specific RUM application"""
        query = select(RUMApplication).where(
            and_(
                RUMApplication.id == app_id,
                RUMApplication.organization_id == organization_id
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_application_by_api_key(
        self,
        api_key: str
    ) -> Optional[RUMApplication]:
        """Get application by API key (for SDK authentication)"""
        query = select(RUMApplication).where(
            RUMApplication.api_key == api_key
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update_application(
        self,
        app_id: UUID,
        organization_id: UUID,
        app_update: RUMApplicationUpdate
    ) -> Optional[RUMApplication]:
        """Update a RUM application"""
        application = await self.get_application(app_id, organization_id)
        if not application:
            return None

        update_data = app_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(application, field, value)

        application.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(application)

        return application

    async def delete_application(
        self,
        app_id: UUID,
        organization_id: UUID
    ) -> bool:
        """Delete a RUM application"""
        application = await self.get_application(app_id, organization_id)
        if not application:
            return False

        await self.db.delete(application)
        await self.db.commit()
        return True

    async def regenerate_api_key(
        self,
        app_id: UUID,
        organization_id: UUID
    ) -> Optional[str]:
        """Regenerate API key for an application"""
        application = await self.get_application(app_id, organization_id)
        if not application:
            return None

        new_api_key = f"rum_{secrets.token_hex(24)}"
        application.api_key = new_api_key
        application.updated_at = datetime.utcnow()

        await self.db.commit()
        return new_api_key

    # ==================== Session Management ====================

    async def list_sessions(
        self,
        organization_id: UUID,
        application_id: Optional[UUID] = None,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """List RUM sessions with filters"""
        query = select(RUMSession).where(
            RUMSession.organization_id == organization_id
        )

        if application_id:
            query = query.where(RUMSession.application_id == application_id)
        if user_id:
            query = query.where(RUMSession.user_id == user_id)
        if start_time:
            query = query.where(RUMSession.session_start >= start_time)
        if end_time:
            query = query.where(RUMSession.session_start <= end_time)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Get paginated results
        query = query.order_by(desc(RUMSession.session_start))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = result.scalars().all()

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size
        }

    async def create_or_update_session(
        self,
        organization_id: UUID,
        application_id: UUID,
        session_data: RUMSessionCreate
    ) -> RUMSession:
        """Create or update a session"""
        # Check if session exists
        query = select(RUMSession).where(
            and_(
                RUMSession.organization_id == organization_id,
                RUMSession.application_id == application_id,
                RUMSession.session_id == session_data.session_id
            )
        )
        result = await self.db.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing session
            return existing

        # Create new session
        session = RUMSession(
            organization_id=organization_id,
            application_id=application_id,
            **session_data.model_dump()
        )

        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        return session

    async def get_session(
        self,
        session_id: UUID,
        organization_id: UUID
    ) -> Optional[RUMSession]:
        """Get a specific session"""
        query = select(RUMSession).where(
            and_(
                RUMSession.id == session_id,
                RUMSession.organization_id == organization_id
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_session_by_client_id(
        self,
        client_session_id: str,
        organization_id: UUID,
        application_id: UUID
    ) -> Optional[RUMSession]:
        """Get session by client-generated session ID"""
        query = select(RUMSession).where(
            and_(
                RUMSession.session_id == client_session_id,
                RUMSession.organization_id == organization_id,
                RUMSession.application_id == application_id
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update_session(
        self,
        session_id: UUID,
        organization_id: UUID,
        update_data: RUMSessionUpdate
    ) -> Optional[RUMSession]:
        """Update session data"""
        session = await self.get_session(session_id, organization_id)
        if not session:
            return None

        for field, value in update_data.model_dump(exclude_unset=True).items():
            setattr(session, field, value)

        await self.db.commit()
        await self.db.refresh(session)

        return session

    # ==================== Page View Management ====================

    async def list_page_views(
        self,
        organization_id: UUID,
        application_id: Optional[UUID] = None,
        session_id: Optional[UUID] = None,
        url_path: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """List page views with filters"""
        query = select(RUMPageView).where(
            RUMPageView.organization_id == organization_id
        )

        if application_id:
            query = query.where(RUMPageView.application_id == application_id)
        if session_id:
            query = query.where(RUMPageView.session_id == session_id)
        if url_path:
            query = query.where(RUMPageView.url_path.ilike(f"%{url_path}%"))
        if start_time:
            query = query.where(RUMPageView.timestamp >= start_time)
        if end_time:
            query = query.where(RUMPageView.timestamp <= end_time)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Get paginated results
        query = query.order_by(desc(RUMPageView.timestamp))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = result.scalars().all()

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size
        }

    async def create_page_view(
        self,
        organization_id: UUID,
        application_id: UUID,
        page_view_data: RUMPageViewCreate
    ) -> RUMPageView:
        """Record a page view"""
        # Look up the session
        session = await self.get_session_by_client_id(
            page_view_data.session_id,
            organization_id,
            application_id
        )

        if not session:
            raise ValueError("Session not found")

        # Extract URL path if not provided
        url_path = page_view_data.url_path
        if not url_path and page_view_data.url:
            from urllib.parse import urlparse
            url_path = urlparse(page_view_data.url).path

        page_view = RUMPageView(
            organization_id=organization_id,
            application_id=application_id,
            session_id=session.id,
            url=page_view_data.url,
            url_path=url_path,
            page_title=page_view_data.page_title,
            timestamp=page_view_data.timestamp,
            time_on_page_ms=page_view_data.time_on_page_ms,
            lcp_ms=page_view_data.lcp_ms,
            fid_ms=page_view_data.fid_ms,
            cls=page_view_data.cls,
            fcp_ms=page_view_data.fcp_ms,
            ttfb_ms=page_view_data.ttfb_ms,
            inp_ms=page_view_data.inp_ms,
            dns_lookup_ms=page_view_data.dns_lookup_ms,
            tcp_connect_ms=page_view_data.tcp_connect_ms,
            ssl_handshake_ms=page_view_data.ssl_handshake_ms,
            request_time_ms=page_view_data.request_time_ms,
            response_time_ms=page_view_data.response_time_ms,
            dom_interactive_ms=page_view_data.dom_interactive_ms,
            dom_complete_ms=page_view_data.dom_complete_ms,
            load_event_ms=page_view_data.load_event_ms,
            resource_count=page_view_data.resource_count or 0,
            total_resource_size_bytes=page_view_data.total_resource_size_bytes,
            total_resource_load_time_ms=page_view_data.total_resource_load_time_ms,
            custom_attributes=page_view_data.custom_attributes
        )

        self.db.add(page_view)

        # Update session page view count
        session.page_views = (session.page_views or 0) + 1
        if session.page_views == 1:
            session.is_bounce = True
        else:
            session.is_bounce = False

        await self.db.commit()
        await self.db.refresh(page_view)

        return page_view

    # ==================== Error Management ====================

    async def list_errors(
        self,
        organization_id: UUID,
        application_id: Optional[UUID] = None,
        error_type: Optional[str] = None,
        fingerprint: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """List errors with filters"""
        query = select(RUMError).where(
            RUMError.organization_id == organization_id
        )

        if application_id:
            query = query.where(RUMError.application_id == application_id)
        if error_type:
            query = query.where(RUMError.error_type == error_type)
        if fingerprint:
            query = query.where(RUMError.fingerprint == fingerprint)
        if start_time:
            query = query.where(RUMError.timestamp >= start_time)
        if end_time:
            query = query.where(RUMError.timestamp <= end_time)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Get paginated results
        query = query.order_by(desc(RUMError.timestamp))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = result.scalars().all()

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size
        }

    async def create_error(
        self,
        organization_id: UUID,
        application_id: UUID,
        error_data: RUMErrorCreate
    ) -> RUMError:
        """Record an error"""
        # Look up the session
        session = await self.get_session_by_client_id(
            error_data.session_id,
            organization_id,
            application_id
        )

        # Generate fingerprint for grouping similar errors
        fingerprint_str = f"{error_data.error_type}:{error_data.error_name}:{error_data.message}"
        fingerprint = hashlib.md5(fingerprint_str.encode()).hexdigest()[:16]

        # Extract URL path if not provided
        url_path = error_data.url_path
        if not url_path and error_data.url:
            from urllib.parse import urlparse
            url_path = urlparse(error_data.url).path

        error = RUMError(
            organization_id=organization_id,
            application_id=application_id,
            session_id=session.id if session else None,
            error_type=error_data.error_type,
            error_name=error_data.error_name,
            message=error_data.message,
            stack_trace=error_data.stack_trace,
            filename=error_data.filename,
            line_number=error_data.line_number,
            column_number=error_data.column_number,
            url=error_data.url,
            url_path=url_path,
            fingerprint=fingerprint,
            timestamp=error_data.timestamp,
            user_id=error_data.user_id,
            context=error_data.context,
            is_handled=error_data.is_handled
        )

        self.db.add(error)

        # Update session error count
        if session:
            session.errors_count = (session.errors_count or 0) + 1

        await self.db.commit()
        await self.db.refresh(error)

        return error

    async def get_error_groups(
        self,
        organization_id: UUID,
        application_id: UUID,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get grouped errors by fingerprint"""
        since = datetime.utcnow() - timedelta(hours=hours)

        query = select(
            RUMError.fingerprint,
            RUMError.error_name,
            RUMError.message,
            func.count(RUMError.id).label('count'),
            func.min(RUMError.timestamp).label('first_seen'),
            func.max(RUMError.timestamp).label('last_seen'),
            func.count(func.distinct(RUMError.user_id)).label('affected_users'),
            func.count(func.distinct(RUMError.session_id)).label('affected_sessions')
        ).where(
            and_(
                RUMError.organization_id == organization_id,
                RUMError.application_id == application_id,
                RUMError.timestamp >= since
            )
        ).group_by(
            RUMError.fingerprint,
            RUMError.error_name,
            RUMError.message
        ).order_by(desc('count'))

        result = await self.db.execute(query)
        rows = result.all()

        return [
            {
                "fingerprint": row.fingerprint,
                "error_name": row.error_name,
                "message": row.message[:200] if row.message else "",
                "count": row.count,
                "first_seen": row.first_seen,
                "last_seen": row.last_seen,
                "affected_users": row.affected_users,
                "affected_sessions": row.affected_sessions
            }
            for row in rows
        ]

    # ==================== User Action Management ====================

    async def create_user_action(
        self,
        organization_id: UUID,
        application_id: UUID,
        action_data: RUMUserActionCreate
    ) -> RUMUserAction:
        """Record a user action"""
        session = await self.get_session_by_client_id(
            action_data.session_id,
            organization_id,
            application_id
        )

        if not session:
            raise ValueError("Session not found")

        action = RUMUserAction(
            organization_id=organization_id,
            application_id=application_id,
            session_id=session.id,
            action_type=action_data.action_type,
            action_name=action_data.action_name,
            target_selector=action_data.target_selector,
            target_tag=action_data.target_tag,
            target_id=action_data.target_id,
            target_class=action_data.target_class,
            target_text=action_data.target_text[:500] if action_data.target_text else None,
            timestamp=action_data.timestamp,
            duration_ms=action_data.duration_ms,
            page_x=action_data.page_x,
            page_y=action_data.page_y,
            url=action_data.url,
            url_path=action_data.url_path,
            custom_data=action_data.custom_data
        )

        self.db.add(action)

        # Update session interaction count
        session.interactions = (session.interactions or 0) + 1
        if session.is_bounce and session.interactions > 0:
            session.is_bounce = False

        await self.db.commit()
        await self.db.refresh(action)

        return action

    # ==================== Statistics ====================

    async def get_stats(
        self,
        organization_id: UUID,
        application_id: UUID,
        hours: int = 24
    ) -> RUMStats:
        """Get RUM statistics for an application"""
        since = datetime.utcnow() - timedelta(hours=hours)

        # Session stats
        session_query = select(
            func.count(RUMSession.id).label('total'),
            func.count(func.distinct(RUMSession.user_id)).label('unique_users'),
            func.avg(RUMSession.duration_ms).label('avg_duration'),
            func.sum(func.cast(RUMSession.is_bounce, Integer)).label('bounces')
        ).where(
            and_(
                RUMSession.organization_id == organization_id,
                RUMSession.application_id == application_id,
                RUMSession.session_start >= since
            )
        )

        session_result = await self.db.execute(session_query)
        session_stats = session_result.one()

        # Page view stats
        pv_query = select(
            func.count(RUMPageView.id).label('total'),
            func.percentile_cont(0.5).within_group(RUMPageView.lcp_ms).label('lcp_p50'),
            func.percentile_cont(0.75).within_group(RUMPageView.lcp_ms).label('lcp_p75'),
            func.percentile_cont(0.9).within_group(RUMPageView.lcp_ms).label('lcp_p90'),
            func.percentile_cont(0.5).within_group(RUMPageView.fid_ms).label('fid_p50'),
            func.percentile_cont(0.75).within_group(RUMPageView.fid_ms).label('fid_p75'),
            func.percentile_cont(0.5).within_group(RUMPageView.cls).label('cls_p50'),
            func.percentile_cont(0.75).within_group(RUMPageView.cls).label('cls_p75'),
            func.percentile_cont(0.5).within_group(RUMPageView.fcp_ms).label('fcp_p50'),
            func.percentile_cont(0.75).within_group(RUMPageView.fcp_ms).label('fcp_p75'),
            func.percentile_cont(0.5).within_group(RUMPageView.ttfb_ms).label('ttfb_p50'),
            func.percentile_cont(0.75).within_group(RUMPageView.ttfb_ms).label('ttfb_p75'),
        ).where(
            and_(
                RUMPageView.organization_id == organization_id,
                RUMPageView.application_id == application_id,
                RUMPageView.timestamp >= since
            )
        )

        try:
            pv_result = await self.db.execute(pv_query)
            pv_stats = pv_result.one()
        except Exception:
            # Fallback if percentile functions aren't available
            pv_stats = None

        # Error count
        error_query = select(func.count(RUMError.id)).where(
            and_(
                RUMError.organization_id == organization_id,
                RUMError.application_id == application_id,
                RUMError.timestamp >= since
            )
        )
        error_result = await self.db.execute(error_query)
        error_count = error_result.scalar() or 0

        # Active sessions (updated in last 5 minutes)
        active_since = datetime.utcnow() - timedelta(minutes=5)
        active_query = select(func.count(RUMSession.id)).where(
            and_(
                RUMSession.organization_id == organization_id,
                RUMSession.application_id == application_id,
                RUMSession.session_start >= active_since
            )
        )
        active_result = await self.db.execute(active_query)
        active_sessions = active_result.scalar() or 0

        # Top pages
        top_pages_query = select(
            RUMPageView.url_path,
            func.count(RUMPageView.id).label('views'),
            func.avg(RUMPageView.load_event_ms).label('avg_load_time')
        ).where(
            and_(
                RUMPageView.organization_id == organization_id,
                RUMPageView.application_id == application_id,
                RUMPageView.timestamp >= since
            )
        ).group_by(RUMPageView.url_path).order_by(desc('views')).limit(10)

        top_pages_result = await self.db.execute(top_pages_query)
        top_pages = [
            {"url_path": row.url_path, "views": row.views, "avg_load_time_ms": row.avg_load_time}
            for row in top_pages_result.all()
        ]

        # Browser breakdown
        browser_query = select(
            RUMSession.browser_name,
            func.count(RUMSession.id).label('count')
        ).where(
            and_(
                RUMSession.organization_id == organization_id,
                RUMSession.application_id == application_id,
                RUMSession.session_start >= since,
                RUMSession.browser_name.isnot(None)
            )
        ).group_by(RUMSession.browser_name).order_by(desc('count')).limit(10)

        browser_result = await self.db.execute(browser_query)
        browser_breakdown = {row.browser_name: row.count for row in browser_result.all()}

        # Device breakdown
        device_query = select(
            RUMSession.device_type,
            func.count(RUMSession.id).label('count')
        ).where(
            and_(
                RUMSession.organization_id == organization_id,
                RUMSession.application_id == application_id,
                RUMSession.session_start >= since,
                RUMSession.device_type.isnot(None)
            )
        ).group_by(RUMSession.device_type).order_by(desc('count'))

        device_result = await self.db.execute(device_query)
        device_breakdown = {row.device_type: row.count for row in device_result.all()}

        total_sessions = session_stats.total or 0
        total_page_views = pv_stats.total if pv_stats else 0
        bounces = session_stats.bounces or 0

        return RUMStats(
            total_sessions=total_sessions,
            active_sessions=active_sessions,
            total_page_views=total_page_views,
            total_errors=error_count,
            error_rate_percent=(error_count / total_page_views * 100) if total_page_views > 0 else 0,
            unique_users=session_stats.unique_users or 0,
            avg_session_duration_ms=int(session_stats.avg_duration or 0),
            bounce_rate_percent=(bounces / total_sessions * 100) if total_sessions > 0 else 0,
            avg_page_views_per_session=(total_page_views / total_sessions) if total_sessions > 0 else 0,
            core_web_vitals=CoreWebVitalsStats(
                lcp_p50_ms=pv_stats.lcp_p50 or 0 if pv_stats else 0,
                lcp_p75_ms=pv_stats.lcp_p75 or 0 if pv_stats else 0,
                fid_p50_ms=pv_stats.fid_p50 or 0 if pv_stats else 0,
                fid_p75_ms=pv_stats.fid_p75 or 0 if pv_stats else 0,
                cls_p50=pv_stats.cls_p50 or 0 if pv_stats else 0,
                cls_p75=pv_stats.cls_p75 or 0 if pv_stats else 0,
                fcp_p50_ms=pv_stats.fcp_p50 or 0 if pv_stats else 0,
                fcp_p75_ms=pv_stats.fcp_p75 or 0 if pv_stats else 0,
                ttfb_p50_ms=pv_stats.ttfb_p50 or 0 if pv_stats else 0,
                ttfb_p75_ms=pv_stats.ttfb_p75 or 0 if pv_stats else 0
            ),
            top_pages=top_pages,
            top_errors=await self.get_error_groups(organization_id, application_id, hours),
            browser_breakdown=browser_breakdown,
            device_breakdown=device_breakdown
        )

    # ==================== Alerts ====================

    async def list_alerts(
        self,
        organization_id: UUID,
        application_id: Optional[UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """List RUM alerts"""
        query = select(RUMAlert).where(
            RUMAlert.organization_id == organization_id
        )

        if application_id:
            query = query.where(RUMAlert.application_id == application_id)
        if status:
            query = query.where(RUMAlert.status == status)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Get paginated results
        query = query.order_by(desc(RUMAlert.triggered_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = result.scalars().all()

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size
        }

    async def acknowledge_alert(
        self,
        alert_id: UUID,
        organization_id: UUID,
        user_id: UUID
    ) -> Optional[RUMAlert]:
        """Acknowledge an alert"""
        query = select(RUMAlert).where(
            and_(
                RUMAlert.id == alert_id,
                RUMAlert.organization_id == organization_id
            )
        )
        result = await self.db.execute(query)
        alert = result.scalar_one_or_none()

        if not alert:
            return None

        alert.status = "acknowledged"
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = user_id

        await self.db.commit()
        await self.db.refresh(alert)

        return alert

    async def resolve_alert(
        self,
        alert_id: UUID,
        organization_id: UUID
    ) -> Optional[RUMAlert]:
        """Resolve an alert"""
        query = select(RUMAlert).where(
            and_(
                RUMAlert.id == alert_id,
                RUMAlert.organization_id == organization_id
            )
        )
        result = await self.db.execute(query)
        alert = result.scalar_one_or_none()

        if not alert:
            return None

        alert.status = "resolved"
        alert.resolved_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(alert)

        return alert
