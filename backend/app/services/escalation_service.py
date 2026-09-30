# backend/app/services/escalation_service.py
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.incident import Incident, IncidentStatus
from app.models.escalation_policy import EscalationPolicy
from app.models.notification import Notification
from app.models.user import User

logger = logging.getLogger(__name__)

class EscalationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_incidents_for_escalation(self) -> List[str]:
        """Check all open incidents and escalate if needed"""
        escalated_incidents = []
        
        # Find incidents that need escalation (open > 10 minutes, no acknowledgment)
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        
        query = select(Incident).where(
            and_(
                Incident.status == IncidentStatus.OPEN,
                Incident.created_at <= cutoff_time,
                Incident.acknowledged_at.is_(None)
            )
        )
        
        result = await self.db.execute(query)
        incidents = result.scalars().all()
        
        for incident in incidents:
            incident_id = str(incident.id)  # Extract ID safely
            escalation_level = await self.calculate_escalation_level(incident)
            if escalation_level > 0:
                await self.escalate_incident(incident, escalation_level)
                escalated_incidents.append(incident_id)
        
        return escalated_incidents

    async def calculate_escalation_level(self, incident: Incident) -> int:
        """Calculate what escalation level this incident should be at"""
        now = datetime.now(timezone.utc)
        # Ensure incident.created_at is timezone aware
        created_at = incident.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        
        minutes_since_created = (now - created_at).total_seconds() / 60
        
        # Escalation levels based on time
        if minutes_since_created >= 30:  # 30+ minutes = level 3
            return 3
        elif minutes_since_created >= 20:  # 20+ minutes = level 2  
            return 2
        elif minutes_since_created >= 10:  # 10+ minutes = level 1
            return 1
        else:
            return 0

    async def escalate_incident(self, incident: Incident, level: int) -> bool:
        """Escalate incident to next level"""
        incident_id = str(incident.id)  # Get ID before any operations
        try:
            # Update incident with escalation info
            incident.extra_data = incident.extra_data or {}
            previous_level = incident.extra_data.get('escalation_level', 0)
            incident.extra_data['escalation_level'] = level
            incident.extra_data['last_escalated_at'] = datetime.now(timezone.utc).isoformat()
            incident.extra_data['escalation_history'] = incident.extra_data.get('escalation_history', [])
            incident.extra_data['escalation_history'].append({
                'from_level': previous_level,
                'to_level': level,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })

            await self.db.commit()

            # Create escalation notification record
            try:
                # Get user_id - use created_by_id, assigned_to_id, or find any org user
                user_id = incident.created_by_id or incident.assigned_to_id

                if not user_id:
                    # Find any user in the organization as fallback
                    user_result = await self.db.execute(
                        select(User.id).where(User.organization_id == incident.organization_id).limit(1)
                    )
                    user_row = user_result.first()
                    user_id = user_row[0] if user_row else None

                if not user_id:
                    logger.warning(f"No user found to notify for incident {incident_id}, skipping notification")
                else:
                    severity_map = {1: 'medium', 2: 'high', 3: 'critical'}
                    notification = Notification(
                        user_id=user_id,
                        organization_id=incident.organization_id,
                        type='incident',
                        title=f'Incident Escalated to Level {level}',
                        message=f'Incident "{incident.title}" has been escalated to level {level} due to no acknowledgment.',
                        severity=severity_map.get(level, 'high'),
                        incident_id=incident.id,
                        action_url=f'/incidents/{incident_id}',
                        extra_data={
                            'escalation_level': level,
                            'previous_level': previous_level
                        }
                    )
                    self.db.add(notification)
                    await self.db.commit()
                    logger.info(f"Created escalation notification for incident {incident_id}")
            except Exception as notif_error:
                # Log notification error but don't fail the escalation
                await self.db.rollback()
                logger.warning(f"Failed to create escalation notification for incident {incident_id}: {notif_error}")

            logger.info(f"Escalated incident {incident_id} to level {level}")
            return True

        except Exception as e:
            logger.error(f"Escalation failed for incident {incident_id}: {e}")
            return False

    async def should_escalate_incident(self, incident: Incident) -> bool:
        """Check if incident should be escalated based on policy"""
        # Simple logic for now - escalate critical/high incidents faster
        now = datetime.now(timezone.utc)
        created_at = incident.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
            
        minutes_since_created = (now - created_at).total_seconds() / 60
        
        if incident.severity == 'critical':
            return minutes_since_created >= 5  # Critical: escalate after 5 minutes
        elif incident.severity == 'high':
            return minutes_since_created >= 10  # High: escalate after 10 minutes
        else:
            return minutes_since_created >= 15  # Medium/Low: escalate after 15 minutes

    async def get_escalation_policy(self, organization_id: str) -> Optional[EscalationPolicy]:
        """Get escalation policy for organization (placeholder for future)"""
        # For now, return None - using default escalation logic
        # In future, load from escalation_policies table
        return None