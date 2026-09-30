# backend/app/services/status_page_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import logging
import secrets

from app.models.status_page import (
    StatusPage, StatusPageService, ServiceUptimeRecord,
    StatusPageSubscriber, ServiceStatus
)
from app.models.incident import Incident, IncidentStatus
from app.models.maintenance_window import MaintenanceWindow
from app.schemas.status_page import (
    StatusPageCreate, StatusPageUpdate, StatusPageResponse,
    StatusPageServiceCreate, StatusPageServiceUpdate, StatusPageServiceResponse,
    PublicStatusPageResponse, ServiceWithUptimeResponse, UptimeRecordResponse,
    PublicIncidentResponse, PublicMaintenanceResponse,
    SubscriberCreate, SubscriberResponse
)

logger = logging.getLogger(__name__)


class StatusPageService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # Status Page CRUD
    async def create_status_page(
        self,
        organization_id: UUID,
        data: StatusPageCreate
    ) -> StatusPage:
        """Create a new status page"""
        # Check if org already has a status page
        existing = await self.db.execute(
            select(StatusPage).where(StatusPage.organization_id == organization_id)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Organization already has a status page")

        # Check slug uniqueness
        slug_check = await self.db.execute(
            select(StatusPage).where(StatusPage.slug == data.slug)
        )
        if slug_check.scalar_one_or_none():
            raise ValueError("Slug already in use")

        status_page = StatusPage(
            organization_id=organization_id,
            name=data.name,
            slug=data.slug,
            description=data.description,
            logo_url=data.logo_url,
            favicon_url=data.favicon_url,
            primary_color=data.primary_color,
            is_public=data.is_public,
            show_historical_uptime=data.show_historical_uptime,
            historical_days=data.historical_days,
            show_incident_history=data.show_incident_history,
            incident_history_days=data.incident_history_days,
            allow_subscriptions=data.allow_subscriptions,
            support_url=data.support_url,
            support_email=data.support_email
        )

        self.db.add(status_page)
        await self.db.commit()
        await self.db.refresh(status_page)

        logger.info(f"Created status page: {status_page.name} ({status_page.slug})")
        return status_page

    async def get_status_page(
        self,
        organization_id: UUID
    ) -> Optional[StatusPage]:
        """Get status page for an organization"""
        result = await self.db.execute(
            select(StatusPage)
            .options(selectinload(StatusPage.services))
            .where(StatusPage.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def get_status_page_by_slug(
        self,
        slug: str
    ) -> Optional[StatusPage]:
        """Get status page by public slug"""
        result = await self.db.execute(
            select(StatusPage)
            .options(selectinload(StatusPage.services))
            .where(StatusPage.slug == slug)
        )
        return result.scalar_one_or_none()

    async def update_status_page(
        self,
        organization_id: UUID,
        data: StatusPageUpdate
    ) -> Optional[StatusPage]:
        """Update status page settings"""
        status_page = await self.get_status_page(organization_id)
        if not status_page:
            return None

        update_data = data.model_dump(exclude_unset=True)

        # Check slug uniqueness if being changed
        if 'slug' in update_data and update_data['slug'] != status_page.slug:
            slug_check = await self.db.execute(
                select(StatusPage).where(StatusPage.slug == update_data['slug'])
            )
            if slug_check.scalar_one_or_none():
                raise ValueError("Slug already in use")

        for field, value in update_data.items():
            setattr(status_page, field, value)

        await self.db.commit()
        await self.db.refresh(status_page)

        logger.info(f"Updated status page: {status_page.slug}")
        return status_page

    async def delete_status_page(
        self,
        organization_id: UUID
    ) -> bool:
        """Delete status page"""
        status_page = await self.get_status_page(organization_id)
        if not status_page:
            return False

        await self.db.delete(status_page)
        await self.db.commit()

        logger.info(f"Deleted status page for org: {organization_id}")
        return True

    # Service CRUD
    async def add_service(
        self,
        organization_id: UUID,
        data: StatusPageServiceCreate
    ) -> Optional[StatusPageService]:
        """Add a service to the status page"""
        status_page = await self.get_status_page(organization_id)
        if not status_page:
            return None

        service = StatusPageService(
            status_page_id=status_page.id,
            name=data.name,
            description=data.description,
            status=data.status,
            display_order=data.display_order,
            is_visible=data.is_visible,
            group_name=data.group_name,
            health_check_url=data.health_check_url,
            health_check_interval_minutes=data.health_check_interval_minutes
        )

        self.db.add(service)
        await self.db.commit()
        await self.db.refresh(service)

        return service

    async def get_service(
        self,
        service_id: UUID,
        organization_id: UUID
    ) -> Optional[StatusPageService]:
        """Get a specific service"""
        status_page = await self.get_status_page(organization_id)
        if not status_page:
            return None

        result = await self.db.execute(
            select(StatusPageService).where(
                and_(
                    StatusPageService.id == service_id,
                    StatusPageService.status_page_id == status_page.id
                )
            )
        )
        return result.scalar_one_or_none()

    async def update_service(
        self,
        service_id: UUID,
        organization_id: UUID,
        data: StatusPageServiceUpdate
    ) -> Optional[StatusPageService]:
        """Update a service"""
        service = await self.get_service(service_id, organization_id)
        if not service:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(service, field, value)

        await self.db.commit()
        await self.db.refresh(service)

        return service

    async def update_service_status(
        self,
        service_id: UUID,
        organization_id: UUID,
        status: ServiceStatus
    ) -> Optional[StatusPageService]:
        """Update just the status of a service"""
        service = await self.get_service(service_id, organization_id)
        if not service:
            return None

        service.status = status
        await self.db.commit()
        await self.db.refresh(service)

        return service

    async def delete_service(
        self,
        service_id: UUID,
        organization_id: UUID
    ) -> bool:
        """Delete a service"""
        service = await self.get_service(service_id, organization_id)
        if not service:
            return False

        await self.db.delete(service)
        await self.db.commit()

        return True

    # Public status page
    async def get_public_status(
        self,
        slug: str
    ) -> Optional[PublicStatusPageResponse]:
        """Get public status page data"""
        status_page = await self.get_status_page_by_slug(slug)
        if not status_page or not status_page.is_public:
            return None

        # Get visible services with uptime
        services_with_uptime = []
        for service in sorted(status_page.services, key=lambda s: s.display_order):
            if not service.is_visible:
                continue

            # Get uptime records
            uptime_records = []
            if status_page.show_historical_uptime:
                records_result = await self.db.execute(
                    select(ServiceUptimeRecord)
                    .where(ServiceUptimeRecord.service_id == service.id)
                    .where(ServiceUptimeRecord.date >= datetime.utcnow() - timedelta(days=status_page.historical_days))
                    .order_by(ServiceUptimeRecord.date.desc())
                )
                records = records_result.scalars().all()
                uptime_records = [
                    UptimeRecordResponse(
                        date=r.date,
                        uptime_percentage=r.uptime_percentage,
                        total_incidents=r.total_incidents,
                        total_downtime_minutes=r.total_downtime_minutes
                    )
                    for r in records
                ]

            services_with_uptime.append(ServiceWithUptimeResponse(
                id=service.id,
                name=service.name,
                description=service.description,
                status=service.status,
                group_name=service.group_name,
                uptime_records=uptime_records
            ))

        # Calculate overall status
        overall_status = self._calculate_overall_status([s.status for s in services_with_uptime])

        # Get active incidents
        active_incidents = []
        if status_page.show_incident_history:
            incidents_result = await self.db.execute(
                select(Incident)
                .where(
                    and_(
                        Incident.organization_id == status_page.organization_id,
                        Incident.status.in_([IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED])
                    )
                )
                .order_by(Incident.created_at.desc())
                .limit(10)
            )
            active_incidents = [
                PublicIncidentResponse(
                    id=i.id,
                    title=i.title,
                    status=i.status.value,
                    severity=i.severity.value,
                    created_at=i.created_at,
                    resolved_at=i.resolved_at,
                    description=i.description[:500] if i.description else None
                )
                for i in incidents_result.scalars().all()
            ]

        # Get past incidents
        past_incidents = []
        if status_page.show_incident_history:
            past_result = await self.db.execute(
                select(Incident)
                .where(
                    and_(
                        Incident.organization_id == status_page.organization_id,
                        Incident.status.in_([IncidentStatus.RESOLVED, IncidentStatus.CLOSED]),
                        Incident.resolved_at >= datetime.utcnow() - timedelta(days=status_page.incident_history_days)
                    )
                )
                .order_by(Incident.resolved_at.desc())
                .limit(20)
            )
            past_incidents = [
                PublicIncidentResponse(
                    id=i.id,
                    title=i.title,
                    status=i.status.value,
                    severity=i.severity.value,
                    created_at=i.created_at,
                    resolved_at=i.resolved_at,
                    description=i.description[:500] if i.description else None
                )
                for i in past_result.scalars().all()
            ]

        # Get scheduled maintenance
        scheduled_maintenance = []
        try:
            maint_result = await self.db.execute(
                select(MaintenanceWindow)
                .where(
                    and_(
                        MaintenanceWindow.organization_id == status_page.organization_id,
                        MaintenanceWindow.end_time >= datetime.utcnow(),
                        MaintenanceWindow.is_cancelled == False
                    )
                )
                .order_by(MaintenanceWindow.start_time.asc())
                .limit(10)
            )
            for m in maint_result.scalars().all():
                is_active = m.start_time <= datetime.utcnow() <= m.end_time
                scheduled_maintenance.append(PublicMaintenanceResponse(
                    id=m.id,
                    name=m.name,
                    description=m.description,
                    start_time=m.start_time,
                    end_time=m.end_time,
                    services=m.services or [],
                    is_currently_active=is_active
                ))
        except Exception:
            pass  # MaintenanceWindow table might not exist yet

        return PublicStatusPageResponse(
            name=status_page.name,
            description=status_page.description,
            logo_url=status_page.logo_url,
            primary_color=status_page.primary_color,
            overall_status=overall_status,
            services=services_with_uptime,
            active_incidents=active_incidents,
            scheduled_maintenance=scheduled_maintenance,
            past_incidents=past_incidents,
            allow_subscriptions=status_page.allow_subscriptions,
            support_url=status_page.support_url,
            support_email=status_page.support_email
        )

    def _calculate_overall_status(self, statuses: List[ServiceStatus]) -> ServiceStatus:
        """Calculate overall status from service statuses"""
        if not statuses:
            return ServiceStatus.OPERATIONAL

        if ServiceStatus.MAJOR_OUTAGE in statuses:
            return ServiceStatus.MAJOR_OUTAGE
        if ServiceStatus.PARTIAL_OUTAGE in statuses:
            return ServiceStatus.PARTIAL_OUTAGE
        if ServiceStatus.DEGRADED in statuses:
            return ServiceStatus.DEGRADED
        if ServiceStatus.MAINTENANCE in statuses:
            return ServiceStatus.MAINTENANCE
        return ServiceStatus.OPERATIONAL

    # Subscribers
    async def subscribe(
        self,
        slug: str,
        data: SubscriberCreate
    ) -> Optional[StatusPageSubscriber]:
        """Subscribe to status updates"""
        status_page = await self.get_status_page_by_slug(slug)
        if not status_page or not status_page.allow_subscriptions:
            return None

        # Check if already subscribed
        existing = await self.db.execute(
            select(StatusPageSubscriber).where(
                and_(
                    StatusPageSubscriber.status_page_id == status_page.id,
                    StatusPageSubscriber.email == data.email
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Email already subscribed")

        subscriber = StatusPageSubscriber(
            status_page_id=status_page.id,
            email=data.email,
            verification_token=secrets.token_urlsafe(32),
            notify_on_incidents=data.notify_on_incidents,
            notify_on_maintenance=data.notify_on_maintenance,
            notify_on_resolved=data.notify_on_resolved
        )

        self.db.add(subscriber)
        await self.db.commit()
        await self.db.refresh(subscriber)

        # TODO: Send verification email
        logger.info(f"New subscriber for {slug}: {data.email}")
        return subscriber

    async def verify_subscriber(
        self,
        token: str
    ) -> bool:
        """Verify a subscriber's email"""
        result = await self.db.execute(
            select(StatusPageSubscriber).where(
                StatusPageSubscriber.verification_token == token
            )
        )
        subscriber = result.scalar_one_or_none()
        if not subscriber:
            return False

        subscriber.is_verified = True
        subscriber.verified_at = datetime.utcnow()
        subscriber.verification_token = None

        await self.db.commit()
        return True

    async def unsubscribe(
        self,
        email: str,
        slug: str
    ) -> bool:
        """Unsubscribe from status updates"""
        status_page = await self.get_status_page_by_slug(slug)
        if not status_page:
            return False

        result = await self.db.execute(
            select(StatusPageSubscriber).where(
                and_(
                    StatusPageSubscriber.status_page_id == status_page.id,
                    StatusPageSubscriber.email == email
                )
            )
        )
        subscriber = result.scalar_one_or_none()
        if not subscriber:
            return False

        subscriber.unsubscribed_at = datetime.utcnow()
        await self.db.commit()

        return True

    async def get_subscribers(
        self,
        organization_id: UUID,
        page: int = 1,
        per_page: int = 50
    ) -> Tuple[List[StatusPageSubscriber], int]:
        """Get subscribers for org's status page"""
        status_page = await self.get_status_page(organization_id)
        if not status_page:
            return [], 0

        # Count
        count_result = await self.db.execute(
            select(func.count(StatusPageSubscriber.id)).where(
                and_(
                    StatusPageSubscriber.status_page_id == status_page.id,
                    StatusPageSubscriber.unsubscribed_at.is_(None)
                )
            )
        )
        total = count_result.scalar() or 0

        # Get subscribers
        result = await self.db.execute(
            select(StatusPageSubscriber)
            .where(
                and_(
                    StatusPageSubscriber.status_page_id == status_page.id,
                    StatusPageSubscriber.unsubscribed_at.is_(None)
                )
            )
            .order_by(StatusPageSubscriber.subscribed_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )

        return list(result.scalars().all()), total

    # Uptime calculation
    async def calculate_daily_uptime(
        self,
        service_id: UUID,
        date: datetime
    ) -> Optional[ServiceUptimeRecord]:
        """
        Calculate uptime for a service on a specific date.
        Returns the uptime record (creates or updates).
        """
        # Get the service
        result = await self.db.execute(
            select(StatusPageService).where(StatusPageService.id == service_id)
        )
        service = result.scalar_one_or_none()
        if not service:
            return None

        # Get the status page to find org_id
        sp_result = await self.db.execute(
            select(StatusPage).where(StatusPage.id == service.status_page_id)
        )
        status_page = sp_result.scalar_one_or_none()
        if not status_page:
            return None

        # Define the date range for this day
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        # Count incidents that affected this service on this date
        incident_result = await self.db.execute(
            select(func.count(Incident.id)).where(
                and_(
                    Incident.organization_id == status_page.organization_id,
                    Incident.created_at >= start_of_day,
                    Incident.created_at < end_of_day,
                    Incident.status.in_([IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED, IncidentStatus.RESOLVED, IncidentStatus.CLOSED])
                )
            )
        )
        total_incidents = incident_result.scalar() or 0

        # Calculate downtime based on incidents
        # Get incidents with their duration
        incidents_result = await self.db.execute(
            select(Incident).where(
                and_(
                    Incident.organization_id == status_page.organization_id,
                    Incident.created_at >= start_of_day,
                    Incident.created_at < end_of_day
                )
            )
        )
        incidents = incidents_result.scalars().all()

        # Calculate downtime in minutes
        total_downtime_minutes = 0
        operational_minutes = 1440  # Full day in minutes
        degraded_minutes = 0
        outage_minutes = 0

        for incident in incidents:
            # Calculate incident duration
            start = max(incident.created_at, start_of_day)
            if incident.resolved_at:
                end = min(incident.resolved_at, end_of_day)
            else:
                end = min(datetime.utcnow(), end_of_day)

            duration_minutes = max(0, int((end - start).total_seconds() / 60))

            # Categorize based on severity
            severity = incident.severity if hasattr(incident.severity, 'value') else str(incident.severity)
            if severity in ['critical', 'high']:
                outage_minutes += duration_minutes
            elif severity in ['medium', 'warning']:
                degraded_minutes += duration_minutes
            else:
                degraded_minutes += duration_minutes  # Low severity = degraded

            total_downtime_minutes += duration_minutes

        # Adjust operational minutes
        operational_minutes = max(0, 1440 - degraded_minutes - outage_minutes)

        # Calculate uptime percentage
        uptime_percentage = 100
        if total_downtime_minutes > 0:
            uptime_percentage = max(0, int(100 - (total_downtime_minutes / 1440 * 100)))

        # Create or update uptime record
        existing_result = await self.db.execute(
            select(ServiceUptimeRecord).where(
                and_(
                    ServiceUptimeRecord.service_id == service_id,
                    ServiceUptimeRecord.date >= start_of_day,
                    ServiceUptimeRecord.date < end_of_day
                )
            )
        )
        existing_record = existing_result.scalar_one_or_none()

        if existing_record:
            existing_record.uptime_percentage = uptime_percentage
            existing_record.total_incidents = total_incidents
            existing_record.total_downtime_minutes = total_downtime_minutes
            existing_record.operational_minutes = operational_minutes
            existing_record.degraded_minutes = degraded_minutes
            existing_record.outage_minutes = outage_minutes
            record = existing_record
        else:
            record = ServiceUptimeRecord(
                service_id=service_id,
                date=start_of_day,
                uptime_percentage=uptime_percentage,
                total_incidents=total_incidents,
                total_downtime_minutes=total_downtime_minutes,
                operational_minutes=operational_minutes,
                degraded_minutes=degraded_minutes,
                outage_minutes=outage_minutes
            )
            self.db.add(record)

        await self.db.commit()
        await self.db.refresh(record)

        logger.info(f"Calculated uptime for service {service_id} on {date.date()}: {uptime_percentage}%")
        return record

    async def calculate_uptime_for_all_services(
        self,
        date: Optional[datetime] = None
    ) -> int:
        """
        Calculate uptime for all services across all status pages.
        Used by the daily background worker.
        Returns the number of records created/updated.
        """
        if date is None:
            # Default to yesterday
            date = datetime.utcnow() - timedelta(days=1)

        # Get all status page services
        result = await self.db.execute(select(StatusPageService))
        services = result.scalars().all()

        count = 0
        for service in services:
            try:
                record = await self.calculate_daily_uptime(service.id, date)
                if record:
                    count += 1
            except Exception as e:
                logger.error(f"Error calculating uptime for service {service.id}: {e}")

        logger.info(f"Calculated uptime for {count} services for date {date.date()}")
        return count

    async def backfill_uptime_records(
        self,
        service_id: UUID,
        days: int = 90
    ) -> int:
        """
        Backfill uptime records for a service for the past N days.
        """
        count = 0
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        for i in range(1, days + 1):
            date = today - timedelta(days=i)
            try:
                record = await self.calculate_daily_uptime(service_id, date)
                if record:
                    count += 1
            except Exception as e:
                logger.error(f"Error backfilling uptime for service {service_id}, date {date}: {e}")

        logger.info(f"Backfilled {count} uptime records for service {service_id}")
        return count

    # Response conversion
    def to_response(self, status_page: StatusPage) -> StatusPageResponse:
        """Convert model to response schema"""
        services = [
            StatusPageServiceResponse(
                id=s.id,
                status_page_id=s.status_page_id,
                name=s.name,
                description=s.description,
                status=s.status,
                display_order=s.display_order,
                is_visible=s.is_visible,
                group_name=s.group_name,
                health_check_url=s.health_check_url,
                health_check_interval_minutes=s.health_check_interval_minutes,
                last_health_check=s.last_health_check,
                last_health_check_status=s.last_health_check_status,
                created_at=s.created_at,
                updated_at=s.updated_at
            )
            for s in sorted(status_page.services, key=lambda x: x.display_order)
        ]

        return StatusPageResponse(
            id=status_page.id,
            organization_id=status_page.organization_id,
            name=status_page.name,
            slug=status_page.slug,
            description=status_page.description,
            logo_url=status_page.logo_url,
            favicon_url=status_page.favicon_url,
            primary_color=status_page.primary_color,
            custom_css=status_page.custom_css,
            custom_header_html=status_page.custom_header_html,
            custom_footer_html=status_page.custom_footer_html,
            is_public=status_page.is_public,
            show_historical_uptime=status_page.show_historical_uptime,
            historical_days=status_page.historical_days,
            show_incident_history=status_page.show_incident_history,
            incident_history_days=status_page.incident_history_days,
            allow_subscriptions=status_page.allow_subscriptions,
            support_url=status_page.support_url,
            support_email=status_page.support_email,
            created_at=status_page.created_at,
            updated_at=status_page.updated_at,
            services=services
        )
