# backend/app/services/deployment_tracking_service.py
"""
Deployment Tracking Service

Tracks deployments from CI/CD systems and correlates them with incidents/alerts.
Enables root cause analysis by identifying "3 incidents occurred within 30 min of this deploy".
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc, or_
from sqlalchemy.orm import selectinload
import logging

from app.models.deployment_event import DeploymentEvent, DeploymentStatus
from app.models.incident import Incident
from app.models.alert import Alert
from app.schemas.deployment import (
    DeploymentNotify, DeploymentUpdate, DeploymentResponse, DeploymentSummary,
    DeploymentListResponse, DeploymentCorrelation, DeploymentTimeline,
    DeploymentTimelineItem, DeploymentFilters, DeploymentStatus as SchemaDeploymentStatus
)

logger = logging.getLogger(__name__)


class DeploymentTrackingService:
    """Service for tracking and correlating deployments."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.correlation_window_minutes = 30  # Default correlation window

    async def record_deployment(
        self,
        organization_id: UUID,
        deployment_data: DeploymentNotify,
        deployed_at: Optional[datetime] = None
    ) -> DeploymentEvent:
        """
        Record a new deployment event from CI/CD webhook.

        Args:
            organization_id: Organization UUID
            deployment_data: Deployment notification payload
            deployed_at: Override deploy time (defaults to now)

        Returns:
            Created DeploymentEvent
        """
        deployment = DeploymentEvent(
            organization_id=organization_id,
            service_name=deployment_data.service_name,
            version=deployment_data.version,
            environment=deployment_data.environment,
            deployed_by=deployment_data.deployed_by,
            deployed_at=deployed_at or datetime.utcnow(),
            commit_sha=deployment_data.commit_sha,
            commit_message=deployment_data.commit_message,
            branch=deployment_data.branch,
            repository=deployment_data.repository,
            pull_request_url=deployment_data.pull_request_url,
            pull_request_number=deployment_data.pull_request_number,
            status=DeploymentStatus(deployment_data.status.value) if deployment_data.status else DeploymentStatus.SUCCESS,
            duration_seconds=deployment_data.duration_seconds,
            description=deployment_data.description,
            tags=deployment_data.tags or {},
            extra_data=deployment_data.extra_data or {}
        )

        self.db.add(deployment)
        await self.db.commit()
        await self.db.refresh(deployment)

        logger.info(
            f"Recorded deployment: {deployment.service_name} v{deployment.version} "
            f"to {deployment.environment} (org: {organization_id})"
        )

        # Trigger async correlation (don't block the webhook response)
        # In production, this would be queued for background processing
        try:
            await self.correlate_with_incidents(deployment.id, organization_id)
        except Exception as e:
            logger.warning(f"Failed to correlate deployment {deployment.id}: {e}")

        return deployment

    async def update_deployment(
        self,
        deployment_id: UUID,
        organization_id: UUID,
        update_data: DeploymentUpdate
    ) -> Optional[DeploymentEvent]:
        """Update a deployment event (e.g., mark as failed or rolled back)."""
        result = await self.db.execute(
            select(DeploymentEvent).where(
                and_(
                    DeploymentEvent.id == deployment_id,
                    DeploymentEvent.organization_id == organization_id
                )
            )
        )
        deployment = result.scalar_one_or_none()

        if not deployment:
            return None

        if update_data.status:
            deployment.status = DeploymentStatus(update_data.status.value)
        if update_data.duration_seconds is not None:
            deployment.duration_seconds = update_data.duration_seconds
        if update_data.description is not None:
            deployment.description = update_data.description
        if update_data.rollback_of:
            deployment.rollback_of = update_data.rollback_of
        if update_data.extra_data:
            deployment.extra_data = {**deployment.extra_data, **update_data.extra_data}

        deployment.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(deployment)

        return deployment

    async def correlate_with_incidents(
        self,
        deployment_id: UUID,
        organization_id: UUID,
        window_minutes: int = 30
    ) -> Dict[str, Any]:
        """
        Find incidents and alerts that occurred within N minutes of a deployment.

        This is the key feature for root cause analysis:
        "3 incidents occurred within 30 min of this deploy"

        Args:
            deployment_id: Deployment to correlate
            organization_id: Organization UUID
            window_minutes: Time window for correlation (default 30 min)

        Returns:
            Correlation results with incident/alert counts and IDs
        """
        # Get the deployment
        result = await self.db.execute(
            select(DeploymentEvent).where(
                and_(
                    DeploymentEvent.id == deployment_id,
                    DeploymentEvent.organization_id == organization_id
                )
            )
        )
        deployment = result.scalar_one_or_none()

        if not deployment:
            return {"error": "Deployment not found"}

        window_start = deployment.deployed_at - timedelta(minutes=5)  # 5 min before
        window_end = deployment.deployed_at + timedelta(minutes=window_minutes)

        # Find correlated incidents
        incidents_result = await self.db.execute(
            select(Incident).where(
                and_(
                    Incident.organization_id == organization_id,
                    Incident.created_at >= window_start,
                    Incident.created_at <= window_end
                )
            )
        )
        correlated_incidents = incidents_result.scalars().all()

        # Find correlated alerts
        alerts_result = await self.db.execute(
            select(Alert).where(
                and_(
                    Alert.organization_id == organization_id,
                    Alert.created_at >= window_start,
                    Alert.created_at <= window_end
                )
            )
        )
        correlated_alerts = alerts_result.scalars().all()

        # Update deployment with correlation data
        deployment.incidents_within_30min = len(correlated_incidents)
        deployment.alerts_within_30min = len(correlated_alerts)
        deployment.correlated_incident_ids = [inc.id for inc in correlated_incidents]
        deployment.correlated_alert_ids = [alert.id for alert in correlated_alerts]
        deployment.updated_at = datetime.utcnow()

        await self.db.commit()

        logger.info(
            f"Correlated deployment {deployment_id}: "
            f"{len(correlated_incidents)} incidents, {len(correlated_alerts)} alerts"
        )

        return {
            "deployment_id": str(deployment_id),
            "incidents_count": len(correlated_incidents),
            "alerts_count": len(correlated_alerts),
            "incident_ids": [str(inc.id) for inc in correlated_incidents],
            "alert_ids": [str(alert.id) for alert in correlated_alerts],
            "window_minutes": window_minutes
        }

    async def get_deployment(
        self,
        deployment_id: UUID,
        organization_id: UUID
    ) -> Optional[DeploymentEvent]:
        """Get a single deployment by ID."""
        result = await self.db.execute(
            select(DeploymentEvent).where(
                and_(
                    DeploymentEvent.id == deployment_id,
                    DeploymentEvent.organization_id == organization_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_deployments(
        self,
        organization_id: UUID,
        filters: Optional[DeploymentFilters] = None,
        page: int = 1,
        per_page: int = 20
    ) -> DeploymentListResponse:
        """List deployments with filtering and pagination."""
        query = select(DeploymentEvent).where(
            DeploymentEvent.organization_id == organization_id
        )

        # Apply filters
        if filters:
            if filters.service_name:
                query = query.where(
                    DeploymentEvent.service_name.ilike(f"%{filters.service_name}%")
                )
            if filters.environment:
                query = query.where(DeploymentEvent.environment == filters.environment)
            if filters.status:
                query = query.where(
                    DeploymentEvent.status == DeploymentStatus(filters.status.value)
                )
            if filters.branch:
                query = query.where(
                    DeploymentEvent.branch.ilike(f"%{filters.branch}%")
                )
            if filters.deployed_by:
                query = query.where(
                    DeploymentEvent.deployed_by.ilike(f"%{filters.deployed_by}%")
                )
            if filters.date_from:
                query = query.where(DeploymentEvent.deployed_at >= filters.date_from)
            if filters.date_to:
                query = query.where(DeploymentEvent.deployed_at <= filters.date_to)
            if filters.has_incidents is not None:
                if filters.has_incidents:
                    query = query.where(DeploymentEvent.incidents_within_30min > 0)
                else:
                    query = query.where(DeploymentEvent.incidents_within_30min == 0)

        # Count total
        count_query = select(func.count(DeploymentEvent.id)).where(
            DeploymentEvent.organization_id == organization_id
        )
        # Apply same filters to count
        if filters:
            if filters.service_name:
                count_query = count_query.where(
                    DeploymentEvent.service_name.ilike(f"%{filters.service_name}%")
                )
            if filters.environment:
                count_query = count_query.where(DeploymentEvent.environment == filters.environment)
            if filters.status:
                count_query = count_query.where(
                    DeploymentEvent.status == DeploymentStatus(filters.status.value)
                )
            if filters.has_incidents is not None:
                if filters.has_incidents:
                    count_query = count_query.where(DeploymentEvent.incidents_within_30min > 0)
                else:
                    count_query = count_query.where(DeploymentEvent.incidents_within_30min == 0)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination and ordering
        offset = (page - 1) * per_page
        query = query.order_by(desc(DeploymentEvent.deployed_at)).offset(offset).limit(per_page)

        result = await self.db.execute(query)
        deployments = result.scalars().all()

        # Convert to summaries
        deployment_summaries = [
            DeploymentSummary(
                id=d.id,
                service_name=d.service_name,
                version=d.version,
                environment=d.environment,
                deployed_by=d.deployed_by,
                deployed_at=d.deployed_at,
                status=SchemaDeploymentStatus(d.status.value),
                commit_sha=d.commit_sha,
                branch=d.branch,
                incidents_within_30min=d.incidents_within_30min or 0,
                alerts_within_30min=d.alerts_within_30min or 0
            )
            for d in deployments
        ]

        return DeploymentListResponse(
            deployments=deployment_summaries,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page if total > 0 else 1
        )

    async def get_deployment_timeline(
        self,
        organization_id: UUID,
        hours: int = 24,
        service_name: Optional[str] = None,
        environment: Optional[str] = None
    ) -> DeploymentTimeline:
        """
        Get deployment timeline with incident markers.

        Used for the deployment timeline visualization in the dashboard.
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        query = select(DeploymentEvent).where(
            and_(
                DeploymentEvent.organization_id == organization_id,
                DeploymentEvent.deployed_at >= cutoff
            )
        )

        if service_name:
            query = query.where(DeploymentEvent.service_name == service_name)
        if environment:
            query = query.where(DeploymentEvent.environment == environment)

        query = query.order_by(desc(DeploymentEvent.deployed_at))

        result = await self.db.execute(query)
        deployments = result.scalars().all()

        timeline_items = []
        deployments_with_issues = 0

        for d in deployments:
            has_issues = (d.incidents_within_30min or 0) > 0 or (d.alerts_within_30min or 0) > 0
            if has_issues:
                deployments_with_issues += 1

            timeline_items.append(DeploymentTimelineItem(
                id=d.id,
                service_name=d.service_name,
                version=d.version,
                environment=d.environment,
                deployed_at=d.deployed_at,
                status=SchemaDeploymentStatus(d.status.value),
                deployed_by=d.deployed_by,
                commit_sha=d.commit_sha,
                incidents_within_30min=d.incidents_within_30min or 0,
                alerts_within_30min=d.alerts_within_30min or 0,
                has_issues=has_issues
            ))

        return DeploymentTimeline(
            items=timeline_items,
            time_range_hours=hours,
            total_deployments=len(deployments),
            deployments_with_issues=deployments_with_issues
        )

    async def get_deployment_correlation(
        self,
        deployment_id: UUID,
        organization_id: UUID
    ) -> Optional[DeploymentCorrelation]:
        """
        Get full deployment correlation details with incident/alert summaries.

        Used when viewing a specific deployment to see what incidents/alerts
        occurred around that time.
        """
        deployment = await self.get_deployment(deployment_id, organization_id)
        if not deployment:
            return None

        # Get correlated incidents
        correlated_incidents = []
        if deployment.correlated_incident_ids:
            incidents_result = await self.db.execute(
                select(Incident).where(
                    and_(
                        Incident.id.in_(deployment.correlated_incident_ids),
                        Incident.organization_id == organization_id
                    )
                )
            )
            incidents = incidents_result.scalars().all()
            correlated_incidents = [
                {
                    "id": str(inc.id),
                    "title": inc.title,
                    "severity": inc.severity.value if hasattr(inc.severity, 'value') else str(inc.severity),
                    "status": inc.status.value if hasattr(inc.status, 'value') else str(inc.status),
                    "created_at": inc.created_at.isoformat() if inc.created_at else None
                }
                for inc in incidents
            ]

        # Get correlated alerts
        correlated_alerts = []
        if deployment.correlated_alert_ids:
            alerts_result = await self.db.execute(
                select(Alert).where(
                    and_(
                        Alert.id.in_(deployment.correlated_alert_ids),
                        Alert.organization_id == organization_id
                    )
                )
            )
            alerts = alerts_result.scalars().all()
            correlated_alerts = [
                {
                    "id": str(alert.id),
                    "title": alert.title,
                    "severity": alert.severity.value if hasattr(alert.severity, 'value') else str(alert.severity),
                    "status": alert.status.value if hasattr(alert.status, 'value') else str(alert.status),
                    "created_at": alert.created_at.isoformat() if alert.created_at else None
                }
                for alert in alerts
            ]

        deployment_response = DeploymentResponse(
            id=deployment.id,
            organization_id=deployment.organization_id,
            service_name=deployment.service_name,
            version=deployment.version,
            environment=deployment.environment,
            deployed_by=deployment.deployed_by,
            deployed_at=deployment.deployed_at,
            commit_sha=deployment.commit_sha,
            commit_message=deployment.commit_message,
            branch=deployment.branch,
            repository=deployment.repository,
            pull_request_url=deployment.pull_request_url,
            pull_request_number=deployment.pull_request_number,
            status=SchemaDeploymentStatus(deployment.status.value),
            duration_seconds=deployment.duration_seconds,
            rollback_of=deployment.rollback_of,
            incidents_within_30min=deployment.incidents_within_30min or 0,
            alerts_within_30min=deployment.alerts_within_30min or 0,
            correlated_incident_ids=deployment.correlated_incident_ids or [],
            correlated_alert_ids=deployment.correlated_alert_ids or [],
            tags=deployment.tags or {},
            extra_data=deployment.extra_data or {},
            description=deployment.description,
            created_at=deployment.created_at,
            updated_at=deployment.updated_at
        )

        return DeploymentCorrelation(
            deployment=deployment_response,
            correlated_incidents=correlated_incidents,
            correlated_alerts=correlated_alerts,
            correlation_window_minutes=self.correlation_window_minutes
        )

    async def find_deployments_for_incident(
        self,
        incident_id: UUID,
        organization_id: UUID,
        window_minutes: int = 30
    ) -> List[DeploymentEvent]:
        """
        Find deployments that occurred near a specific incident.

        This is the inverse of correlate_with_incidents - given an incident,
        find which deployments might have caused it.
        """
        # Get incident
        incident_result = await self.db.execute(
            select(Incident).where(
                and_(
                    Incident.id == incident_id,
                    Incident.organization_id == organization_id
                )
            )
        )
        incident = incident_result.scalar_one_or_none()

        if not incident:
            return []

        window_start = incident.created_at - timedelta(minutes=window_minutes)
        window_end = incident.created_at + timedelta(minutes=5)  # 5 min after

        result = await self.db.execute(
            select(DeploymentEvent).where(
                and_(
                    DeploymentEvent.organization_id == organization_id,
                    DeploymentEvent.deployed_at >= window_start,
                    DeploymentEvent.deployed_at <= window_end
                )
            ).order_by(desc(DeploymentEvent.deployed_at))
        )

        return result.scalars().all()

    async def get_deployment_stats(
        self,
        organization_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get deployment statistics for dashboard."""
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Total deployments
        total_result = await self.db.execute(
            select(func.count(DeploymentEvent.id)).where(
                and_(
                    DeploymentEvent.organization_id == organization_id,
                    DeploymentEvent.deployed_at >= cutoff
                )
            )
        )
        total_deployments = total_result.scalar() or 0

        # Deployments by status
        status_result = await self.db.execute(
            select(
                DeploymentEvent.status,
                func.count(DeploymentEvent.id)
            ).where(
                and_(
                    DeploymentEvent.organization_id == organization_id,
                    DeploymentEvent.deployed_at >= cutoff
                )
            ).group_by(DeploymentEvent.status)
        )
        status_counts = {row[0].value: row[1] for row in status_result}

        # Deployments with incidents
        incidents_result = await self.db.execute(
            select(func.count(DeploymentEvent.id)).where(
                and_(
                    DeploymentEvent.organization_id == organization_id,
                    DeploymentEvent.deployed_at >= cutoff,
                    DeploymentEvent.incidents_within_30min > 0
                )
            )
        )
        deployments_with_incidents = incidents_result.scalar() or 0

        # Top deployed services
        services_result = await self.db.execute(
            select(
                DeploymentEvent.service_name,
                func.count(DeploymentEvent.id).label('count')
            ).where(
                and_(
                    DeploymentEvent.organization_id == organization_id,
                    DeploymentEvent.deployed_at >= cutoff
                )
            ).group_by(DeploymentEvent.service_name)
            .order_by(desc('count'))
            .limit(5)
        )
        top_services = [{"service": row[0], "count": row[1]} for row in services_result]

        # Daily deployment count for chart
        daily_result = await self.db.execute(
            select(
                func.date_trunc('day', DeploymentEvent.deployed_at).label('date'),
                func.count(DeploymentEvent.id).label('count')
            ).where(
                and_(
                    DeploymentEvent.organization_id == organization_id,
                    DeploymentEvent.deployed_at >= cutoff
                )
            ).group_by('date')
            .order_by('date')
        )
        daily_counts = [
            {"date": row[0].isoformat() if row[0] else None, "count": row[1]}
            for row in daily_result
        ]

        return {
            "total_deployments": total_deployments,
            "status_breakdown": status_counts,
            "deployments_with_incidents": deployments_with_incidents,
            "incident_rate": (
                round(deployments_with_incidents / total_deployments * 100, 1)
                if total_deployments > 0 else 0
            ),
            "top_services": top_services,
            "daily_counts": daily_counts,
            "period_days": days
        }
