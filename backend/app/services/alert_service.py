import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from sqlalchemy.orm import selectinload
import uuid
from app.models.alert import Alert
from app.models.incident import Incident
from app.models.organization import Organization
from app.schemas.alert import (
    GenericAlertPayload, AlertProcessingResult, AlertStatus, AlertSeverity,
    AlertResponse, AlertCreate, AlertUpdate, AlertListResponse
)
from app.schemas.incident import IncidentCreate, IncidentSeverity, IncidentStatus, IncidentUpdate
from app.services.notification_service import NotificationService
import logging

logger = logging.getLogger(__name__)

class AlertService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def generate_alert_fingerprint(self, alert_data: GenericAlertPayload) -> str:
        """Generate a unique fingerprint for alert deduplication"""
        # Use alert_id, title, service, and source to create fingerprint
        fingerprint_data = {
            "alert_id": alert_data.alert_id,
            "title": alert_data.title,
            "service": alert_data.service or "unknown",
            "source": alert_data.source.value if hasattr(alert_data.source, 'value') else str(alert_data.source),
            "environment": alert_data.environment or "unknown"
        }
        
        fingerprint_string = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.md5(fingerprint_string.encode()).hexdigest()

    async def get_alert_by_fingerprint(
        self, 
        fingerprint: str, 
        organization_id: str
    ) -> Optional[Alert]:
        """Find existing alert by fingerprint"""
        result = await self.db.execute(
            select(Alert).where(
                and_(
                    Alert.fingerprint == fingerprint,
                    Alert.organization_id == organization_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_alert_by_id(
        self, 
        alert_id: str, 
        organization_id: str
    ) -> Optional[Alert]:
        """Get alert by ID with organization check"""
        result = await self.db.execute(
            select(Alert).where(
                and_(
                    Alert.id == alert_id,
                    Alert.organization_id == organization_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_alerts(
        self,
        organization_id: str,
        status: Optional[AlertStatus] = None,
        severity: Optional[AlertSeverity] = None,
        service: Optional[str] = None,
        environment: Optional[str] = None,
        source: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> AlertListResponse:
        """List alerts with filtering and pagination"""
        
        query = select(Alert).where(Alert.organization_id == organization_id)
        
        # Apply filters
        if status:
            query = query.where(Alert.status == status)
        if severity:
            query = query.where(Alert.severity == severity)
        if service:
            query = query.where(Alert.service_name.ilike(f"%{service}%"))
        if environment:
            query = query.where(Alert.environment.ilike(f"%{environment}%"))
        if source:
            query = query.where(Alert.source == source)
        
        # Count total
        count_query = select(func.count(Alert.id)).where(Alert.organization_id == organization_id)
        if status:
            count_query = count_query.where(Alert.status == status)
        if severity:
            count_query = count_query.where(Alert.severity == severity)
        if service:
            count_query = count_query.where(Alert.service_name.ilike(f"%{service}%"))
        if environment:
            count_query = count_query.where(Alert.environment.ilike(f"%{environment}%"))
        if source:
            count_query = count_query.where(Alert.source == source)
        
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination and ordering
        offset = (page - 1) * per_page
        query = query.order_by(desc(Alert.created_at)).offset(offset).limit(per_page)
        
        result = await self.db.execute(query)
        alerts = result.scalars().all()
        
        # Convert to response format
        alert_responses = []
        for alert in alerts:
            alert_responses.append(AlertResponse(
                id=str(alert.id),
                external_id=alert.external_id,
                fingerprint=alert.fingerprint,
                title=alert.title,
                description=alert.description,
                severity=alert.severity,
                status=alert.status,
                source=alert.source,
                service_name=alert.service_name,
                environment=alert.environment,
                host=alert.host,
                incident_id=str(alert.incident_id) if alert.incident_id else None,
                started_at=alert.started_at,
                ended_at=alert.ended_at,
                created_at=alert.created_at,
                updated_at=alert.updated_at,
                labels=alert.labels,
                raw_data=alert.raw_data
            ))
        
        return AlertListResponse(
            alerts=alert_responses,
            total=total,
            page=page,
            per_page=per_page
        )

    async def process_alert(
        self, 
        alert_data: GenericAlertPayload, 
        organization_id: str
    ) -> AlertProcessingResult:
        """Process incoming alert and create/update incidents intelligently"""
        
        try:
            logger.info(f"Processing alert {alert_data.alert_id} for org {organization_id}")
            
            fingerprint = self.generate_alert_fingerprint(alert_data)
            
            # Check if we've seen this alert before
            existing_alert = await self.get_alert_by_fingerprint(fingerprint, organization_id)
            
            if alert_data.status == AlertStatus.RESOLVED:
                return await self._handle_resolved_alert(
                    alert_data, existing_alert, fingerprint, organization_id
                )
            else:
                return await self._handle_active_alert(
                    alert_data, existing_alert, fingerprint, organization_id
                )
                
        except Exception as e:
            logger.error(f"Error processing alert {alert_data.alert_id}: {e}")
            await self.db.rollback()  # Add rollback on error
            return AlertProcessingResult(
                success=False,
                message=f"Error processing alert: {str(e)}",
                alert_fingerprint=self.generate_alert_fingerprint(alert_data)
            )

    async def _handle_active_alert(
        self,
        alert_data: GenericAlertPayload,
        existing_alert: Optional[Alert],
        fingerprint: str,
        organization_id: str
    ) -> AlertProcessingResult:
        """Handle an active/triggered alert - FIXED VERSION"""
        
        if existing_alert:
            # Update existing alert
            existing_alert.status = AlertStatus.ACTIVE
            existing_alert.raw_data = alert_data.raw_payload or {}
            existing_alert.updated_at = datetime.utcnow()
            
            if alert_data.raw_payload:
                existing_alert.labels = existing_alert.labels or {}
                existing_alert.labels.update({
                    "last_updated": datetime.utcnow().isoformat(),
                    "update_count": existing_alert.labels.get("update_count", 0) + 1
                })

            await self.db.commit()
            
            return AlertProcessingResult(
                success=True,
                incident_id=str(existing_alert.incident_id) if existing_alert.incident_id else None,
                incident_created=False,
                incident_updated=True,
                message="Alert updated, incident already exists",
                alert_fingerprint=fingerprint
            )
        
        # Create new alert
        new_alert = Alert(
            organization_id=organization_id,
            external_id=alert_data.alert_id,
            fingerprint=fingerprint,
            title=alert_data.title,
            description=alert_data.description,
            severity=alert_data.severity,
            status=AlertStatus.ACTIVE,
            source=alert_data.source,
            service_name=alert_data.service,
            environment=alert_data.environment,
            host=alert_data.region or alert_data.host,
            started_at=alert_data.started_at or datetime.utcnow(),
            raw_data=alert_data.raw_payload or {},
            labels={
                "tags": alert_data.tags or [],
                "alert_url": alert_data.alert_url,
                "runbook_url": alert_data.runbook_url,
                "dashboard_url": alert_data.dashboard_url
            }
        )
        
        self.db.add(new_alert)
        await self.db.flush()  # Get the alert ID
        
        # Decide if we should create an incident
        should_create_incident = await self._should_create_incident(alert_data, organization_id)
        
        incident_id = None
        incident_created = False
        
        if should_create_incident:
            try:
                # FIXED: Create incident directly without service conflicts
                incident_id = str(uuid.uuid4())
                
                # Map alert severity to incident severity properly
                severity_map = {
                    AlertSeverity.INFO: "low",
                    AlertSeverity.WARNING: "medium", 
                    AlertSeverity.ERROR: "high",
                    AlertSeverity.HIGH: "high",
                    AlertSeverity.CRITICAL: "critical"
                }
                
                # Get severity string value
                alert_severity = alert_data.severity
                if hasattr(alert_severity, 'value'):
                    severity_key = alert_severity
                else:
                    # Handle string values
                    severity_key = AlertSeverity[alert_severity.upper()] if isinstance(alert_severity, str) else alert_severity
                
                mapped_severity = severity_map.get(severity_key, "medium")
                
                # Build comprehensive description
                description_parts = [alert_data.description or f"Alert from {alert_data.source}"]
                
                if alert_data.alert_url:
                    description_parts.append(f"🔗 **Alert URL**: {alert_data.alert_url}")
                if alert_data.dashboard_url:
                    description_parts.append(f"📊 **Dashboard**: {alert_data.dashboard_url}")
                if alert_data.runbook_url:
                    description_parts.append(f"📚 **Runbook**: {alert_data.runbook_url}")
                
                # Add technical context
                context_parts = []
                if alert_data.service:
                    context_parts.append(f"Service: {alert_data.service}")
                if alert_data.environment:
                    context_parts.append(f"Environment: {alert_data.environment}")
                if alert_data.region:
                    context_parts.append(f"Region: {alert_data.region}")
                if alert_data.host:
                    context_parts.append(f"Host: {alert_data.host}")
                
                if context_parts:
                    description_parts.append(f"**Context**: {' | '.join(context_parts)}")
                
                # Try to auto-assign to on-call user
                assigned_to_id = None
                try:
                    from app.services.on_call_service import on_call_service
                    on_call_user = await on_call_service.get_on_call_user_for_incident_assignment(
                        organization_id=organization_id,
                        db=self.db
                    )
                    if on_call_user:
                        assigned_to_id = on_call_user.id
                        logger.info(f"Auto-assigning incident to on-call user: {on_call_user.email}")
                except Exception as e:
                    logger.warning(f"Could not auto-assign incident to on-call user: {e}")

                incident = Incident(
                    id=incident_id,
                    organization_id=organization_id,
                    title=f"🚨 [{alert_data.service or 'Unknown'}] {alert_data.title}",
                    description="\n\n".join(description_parts),
                    severity=mapped_severity,  # Use string value
                    status="open",  # Use string value
                    assigned_to_id=assigned_to_id,  # Auto-assign to on-call user
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    tags=[
                        f"source:{alert_data.source.value if hasattr(alert_data.source, 'value') else str(alert_data.source)}",
                        f"alert_id:{alert_data.alert_id}",
                        f"severity:{alert_data.severity.value if hasattr(alert_data.severity, 'value') else str(alert_data.severity)}",
                        "auto-created"
                    ] + (alert_data.tags or [])
                )
                
                self.db.add(incident)
                await self.db.flush()
                
                # Link alert to incident
                new_alert.incident_id = incident_id
                incident_created = True
                
                logger.info(f"Created incident {incident_id} from alert {new_alert.id}")
                
            
            except Exception as e:
                logger.error(f"Failed to create incident for alert {new_alert.id}: {e}")
                # Don't fail the whole operation if incident creation fails
                pass
        
        await self.db.commit()

        if incident_created and incident_id:
            try:
                from sqlalchemy import select
                from app.models.incident import Incident as IncidentModel
                from app.services.notification_service import NotificationService
                
                result = await self.db.execute(
                    select(IncidentModel).where(IncidentModel.id == incident_id)
                )
                incident_obj = result.scalar_one()
                
                notification_service = NotificationService(self.db)
                await notification_service.notify_incident_created(incident_obj)
                logger.info(f"✅ Notifications sent for incident {incident_id}")
            except Exception as e:
                logger.error(f"❌ Failed to send notifications: {e}")
        
        return AlertProcessingResult(
            success=True,
            incident_id=incident_id,
            incident_created=incident_created,
            incident_updated=False,
            message="New alert processed" + (" and incident created" if incident_created else ""),
            alert_fingerprint=fingerprint
        )

    async def _handle_resolved_alert(
        self,
        alert_data: GenericAlertPayload,
        existing_alert: Optional[Alert],
        fingerprint: str,
        organization_id: str
    ) -> AlertProcessingResult:
        """Handle a resolved alert"""
        
        if not existing_alert:
            logger.warning(f"Cannot resolve alert that doesn't exist: {fingerprint}")
            return AlertProcessingResult(
                success=False,
                message="Cannot resolve alert that doesn't exist",
                alert_fingerprint=fingerprint
            )
        
        # Update alert status
        existing_alert.status = AlertStatus.RESOLVED
        existing_alert.ended_at = alert_data.resolved_at or datetime.utcnow()
        existing_alert.updated_at = datetime.utcnow()
        
        incident_updated = False
        incident_id = None
        
        # If alert has associated incident, consider auto-resolving it
        if existing_alert.incident_id:
            incident_id = str(existing_alert.incident_id)
            
            # Check if this is the only active alert for the incident
            other_active_alerts = await self._count_active_alerts_for_incident(
                existing_alert.incident_id, organization_id
            )
            
            if other_active_alerts == 0:
                # Auto-resolve the incident
                try:
                    incident_result = await self.db.execute(
                        select(Incident).where(Incident.id == existing_alert.incident_id)
                    )
                    incident = incident_result.scalar_one_or_none()
                    if incident:
                        incident.status = "resolved"
                        incident.resolved_at = datetime.utcnow()
                        incident.updated_at = datetime.utcnow()
                    incident_updated = True
                    logger.info(f"Auto-resolved incident {incident_id} as all alerts resolved")
                except Exception as e:
                    logger.error(f"Failed to auto-resolve incident {incident_id}: {e}")
        
        await self.db.commit()
        
        return AlertProcessingResult(
            success=True,
            incident_id=incident_id,
            incident_created=False,
            incident_updated=incident_updated,
            message="Alert resolved" + (" and incident auto-resolved" if incident_updated else ""),
            alert_fingerprint=fingerprint
        )

    async def _count_active_alerts_for_incident(
        self, 
        incident_id: str, 
        organization_id: str
    ) -> int:
        """Count active alerts for an incident (excluding the current one being resolved)"""
        result = await self.db.execute(
            select(func.count(Alert.id)).where(
                and_(
                    Alert.incident_id == incident_id,
                    Alert.organization_id == organization_id,
                    Alert.status == AlertStatus.ACTIVE
                )
            )
        )
        return result.scalar()

    async def _should_create_incident(
        self, 
        alert_data: GenericAlertPayload, 
        organization_id: str
    ) -> bool:
        """Enhanced AI-powered decision: should this alert create an incident?"""
        
        # Always create incident for critical alerts
        if alert_data.severity == AlertSeverity.CRITICAL:
            logger.info("Creating incident for critical alert")
            return True
        
        # Create incident for error severity in production
        if (alert_data.severity in [AlertSeverity.ERROR, AlertSeverity.HIGH] and 
            alert_data.environment and 
            alert_data.environment.lower() in ["prod", "production", "live"]):
            logger.info("Creating incident for production error")
            return True
        
        # Don't create incidents for info alerts unless in production
        if alert_data.severity == AlertSeverity.INFO:
            if alert_data.environment and alert_data.environment.lower() in ["prod", "production"]:
                # Only for critical services in production
                critical_services = ["payment", "auth", "database", "api-gateway"]
                if alert_data.service and any(cs in alert_data.service.lower() for cs in critical_services):
                    logger.info("Creating incident for critical service info alert in production")
                    return True
            logger.info("Skipping incident creation for info alert")
            return False
        
        # Check for alert frequency (don't create incidents for flapping alerts)
        if await self._is_flapping_alert(alert_data, organization_id):
            logger.info("Skipping incident creation for flapping alert")
            return False
        
        # Check for maintenance windows
        if await self._is_in_maintenance_window(alert_data, organization_id):
            logger.info("Skipping incident creation during maintenance window")
            return False
        
        # Default: create incident for warning/error alerts
        should_create = alert_data.severity in [AlertSeverity.WARNING, AlertSeverity.ERROR]
        logger.info(f"Default incident creation decision: {should_create} for severity {alert_data.severity}")
        return should_create

    async def _is_flapping_alert(
        self, 
        alert_data: GenericAlertPayload, 
        organization_id: str,
        time_window_minutes: int = 30,
        threshold: int = 5
    ) -> bool:
        """Check if this alert is flapping (firing and resolving repeatedly)"""
        try:
            # Look for alerts with same fingerprint in the last time window
            time_threshold = datetime.utcnow() - timedelta(minutes=time_window_minutes)
            fingerprint = self.generate_alert_fingerprint(alert_data)
            
            result = await self.db.execute(
                select(func.count(Alert.id)).where(
                    and_(
                        Alert.fingerprint == fingerprint,
                        Alert.organization_id == organization_id,
                        Alert.created_at >= time_threshold
                    )
                )
            )
            count = result.scalar()
            
            return count >= threshold
        except Exception as e:
            logger.error(f"Error checking flapping alert: {e}")
            return False

    async def _is_in_maintenance_window(
        self,
        alert_data: GenericAlertPayload,
        organization_id: str
    ) -> bool:
        """Check if alert is occurring during a maintenance window"""
        try:
            from app.services.maintenance_window_service import MaintenanceWindowService
            from uuid import UUID

            maintenance_service = MaintenanceWindowService(self.db)

            # Extract service name and tags from alert
            service = alert_data.service
            tags = alert_data.tags or []

            # Check if we should suppress this alert due to maintenance
            should_suppress = await maintenance_service.should_suppress_alert(
                organization_id=UUID(organization_id),
                service=service,
                tags=tags
            )

            if should_suppress:
                logger.info(
                    f"Alert {alert_data.alert_id} suppressed due to maintenance window "
                    f"(service={service}, tags={tags})"
                )

            return should_suppress

        except Exception as e:
            logger.error(f"Error checking maintenance window: {e}")
            # If we can't check maintenance windows, don't suppress
            return False

    async def acknowledge_alert(
        self, 
        alert_id: str, 
        organization_id: str, 
        user_id: Optional[str] = None
    ) -> AlertResponse:
        """Acknowledge an alert"""
        alert = await self.get_alert_by_id(alert_id, organization_id)
        if not alert:
            raise ValueError("Alert not found")
        
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.updated_at = datetime.utcnow()
        
        # Update labels with acknowledgment info
        if not alert.labels:
            alert.labels = {}
        alert.labels.update({
            "acknowledged_at": datetime.utcnow().isoformat(),
            "acknowledged_by": user_id if user_id else "system"
        })
        
        await self.db.commit()
        
        logger.info(f"Alert {alert_id} acknowledged by {user_id or 'system'}")
        
        return AlertResponse(
            id=str(alert.id),
            external_id=alert.external_id,
            fingerprint=alert.fingerprint,
            title=alert.title,
            description=alert.description,
            severity=alert.severity,
            status=alert.status,
            source=alert.source,
            service_name=alert.service_name,
            environment=alert.environment,
            host=alert.host,
            incident_id=str(alert.incident_id) if alert.incident_id else None,
            started_at=alert.started_at,
            ended_at=alert.ended_at,
            created_at=alert.created_at,
            updated_at=alert.updated_at,
            labels=alert.labels,
            raw_data=alert.raw_data
        )

    async def suppress_alert(
        self, 
        alert_id: str, 
        organization_id: str, 
        user_id: Optional[str] = None,
        reason: Optional[str] = None
    ) -> AlertResponse:
        """Suppress an alert (prevent it from creating incidents)"""
        alert = await self.get_alert_by_id(alert_id, organization_id)
        if not alert:
            raise ValueError("Alert not found")
        
        alert.status = AlertStatus.SUPPRESSED
        alert.updated_at = datetime.utcnow()
        
        # Update labels with suppression info
        if not alert.labels:
            alert.labels = {}
        alert.labels.update({
            "suppressed_at": datetime.utcnow().isoformat(),
            "suppressed_by": user_id if user_id else "system",
            "suppression_reason": reason or "Manual suppression"
        })
        
        await self.db.commit()
        
        logger.info(f"Alert {alert_id} suppressed by {user_id or 'system'}: {reason}")
        
        return AlertResponse(
            id=str(alert.id),
            external_id=alert.external_id,
            fingerprint=alert.fingerprint,
            title=alert.title,
            description=alert.description,
            severity=alert.severity,
            status=alert.status,
            source=alert.source,
            service_name=alert.service_name,
            environment=alert.environment,
            host=alert.host,
            incident_id=str(alert.incident_id) if alert.incident_id else None,
            started_at=alert.started_at,
            ended_at=alert.ended_at,
            created_at=alert.created_at,
            updated_at=alert.updated_at,
            labels=alert.labels,
            raw_data=alert.raw_data
        )

    async def get_alert_statistics(
        self, 
        organization_id: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get alert statistics for the organization"""
        
        try:
            time_threshold = datetime.utcnow() - timedelta(days=days)
            
            # Total alerts
            total_result = await self.db.execute(
                select(func.count(Alert.id)).where(
                    and_(
                        Alert.organization_id == organization_id,
                        Alert.created_at >= time_threshold
                    )
                )
            )
            total_alerts = total_result.scalar()
            
            # Active alerts
            active_result = await self.db.execute(
                select(func.count(Alert.id)).where(
                    and_(
                        Alert.organization_id == organization_id,
                        Alert.status == AlertStatus.ACTIVE,
                        Alert.created_at >= time_threshold
                    )
                )
            )
            active_alerts = active_result.scalar()
            
            # Alerts by severity
            severity_result = await self.db.execute(
                select(Alert.severity, func.count(Alert.id)).where(
                    and_(
                        Alert.organization_id == organization_id,
                        Alert.created_at >= time_threshold
                    )
                ).group_by(Alert.severity)
            )
            severity_counts = dict(severity_result.all())
            
            # Alerts by source
            source_result = await self.db.execute(
                select(Alert.source, func.count(Alert.id)).where(
                    and_(
                        Alert.organization_id == organization_id,
                        Alert.created_at >= time_threshold
                    )
                ).group_by(Alert.source)
            )
            source_counts = dict(source_result.all())
            
            # Top services by alert count
            service_result = await self.db.execute(
                select(Alert.service_name, func.count(Alert.id)).where(
                    and_(
                        Alert.organization_id == organization_id,
                        Alert.service_name.isnot(None),
                        Alert.created_at >= time_threshold
                    )
                ).group_by(Alert.service_name).order_by(desc(func.count(Alert.id))).limit(10)
            )
            top_services = dict(service_result.all())
            
            return {
                "period_days": days,
                "total_alerts": total_alerts,
                "active_alerts": active_alerts,
                "resolved_alerts": total_alerts - active_alerts,
                "resolution_rate": round((total_alerts - active_alerts) / total_alerts * 100, 1) if total_alerts > 0 else 0,
                "severity_breakdown": severity_counts,
                "source_breakdown": source_counts,
                "top_services": top_services,
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating alert statistics: {e}")
            return {
                "error": "Failed to generate statistics",
                "generated_at": datetime.utcnow().isoformat()
            }

    async def create_alert(
        self, 
        alert_data: AlertCreate, 
        organization_id: str
    ) -> AlertResponse:
        """Create a new alert directly (for API usage)"""
        
        # Generate fingerprint for deduplication
        generic_payload = GenericAlertPayload(
            alert_id=alert_data.external_id,
            title=alert_data.title,
            description=alert_data.description,
            severity=alert_data.severity,
            status=alert_data.status,
            source=alert_data.source,
            service=alert_data.service_name,
            environment=alert_data.environment,
            host=alert_data.host,
            started_at=alert_data.started_at,
            raw_payload=alert_data.raw_data or {}
        )
        
        fingerprint = self.generate_alert_fingerprint(generic_payload)
        
        new_alert = Alert(
            organization_id=organization_id,
            external_id=alert_data.external_id,
            fingerprint=fingerprint,
            title=alert_data.title,
            description=alert_data.description,
            severity=alert_data.severity,
            status=alert_data.status,
            source=alert_data.source,
            service_name=alert_data.service_name,
            environment=alert_data.environment,
            host=alert_data.host,
            started_at=alert_data.started_at or datetime.utcnow(),
            raw_data=alert_data.raw_data or {},
            labels=alert_data.labels or {}
        )
        
        self.db.add(new_alert)
        await self.db.commit()
        
        logger.info(f"Created alert {new_alert.id} via API")
        
        return AlertResponse(
            id=str(new_alert.id),
            external_id=new_alert.external_id,
            fingerprint=new_alert.fingerprint,
            title=new_alert.title,
            description=new_alert.description,
            severity=new_alert.severity,
            status=new_alert.status,
            source=new_alert.source,
            service_name=new_alert.service_name,
            environment=new_alert.environment,
            host=new_alert.host,
            incident_id=str(new_alert.incident_id) if new_alert.incident_id else None,
            started_at=new_alert.started_at,
            ended_at=new_alert.ended_at,
            created_at=new_alert.created_at,
            updated_at=new_alert.updated_at,
            labels=new_alert.labels,
            raw_data=new_alert.raw_data
        )