# backend/app/services/notification_service.py
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException

from app.models.incident import Incident
from app.models.user import User
from app.models.team import Team, team_members
from app.models.organization import Organization
from app.services.email_service import EmailService
from app.services.slack_service import SlackService
from app.core.config import settings


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.email_service = EmailService()

    async def _get_slack_service(self, organization_id) -> Optional[SlackService]:
        """Get Slack service for organization (uses per-org token if available)"""
        try:
            return await SlackService.for_organization(self.db, organization_id)
        except Exception as e:
            print(f"Failed to get Slack service for org {organization_id}: {e}")
            return None

    async def notify_incident_created(self, incident: Incident) -> bool:
        """Notify relevant users when incident is created"""
        try:
            # Get organization to check plan permissions
            org_query = select(Organization).where(Organization.id == incident.organization_id)
            org_result = await self.db.execute(org_query)
            org = org_result.scalar_one_or_none()

            if not org:
                print(f"Organization not found for incident {incident.id}")
                return False

            # Get all active users in the organization
            query = (
                select(User)
                .where(
                    User.organization_id == incident.organization_id,
                    User.is_active == True
                )
            )
            result = await self.db.execute(query)
            users = result.scalars().all()

            # Filter users who should be notified
            users_to_notify = [u for u in users if u.notification_preferences.get('email', True)]

            # Send emails (always allowed)
            email_success_count = 0
            for user in users_to_notify:
                if await self.email_service.send_incident_alert(user, incident):
                    email_success_count += 1

            # Send Slack notification if plan allows (uses per-org token)
            slack_success = False
            if incident.severity in ['critical', 'high']:
                try:
                    slack_service = await self._get_slack_service(incident.organization_id)
                    if slack_service:
                        slack_success = await slack_service.send_incident_alert(
                            "#incidents", incident
                        )
                except HTTPException as e:
                    print(f"Slack notification blocked: {e.detail}")
                except Exception as e:
                    print(f"Slack notification error: {e}")

            print(f"Notifications sent - Email: {email_success_count}/{len(users_to_notify)}, Slack: {slack_success}")

            # Also notify status page subscribers (async, don't block)
            try:
                severity_str = incident.severity if isinstance(incident.severity, str) else incident.severity.value
                await self.notify_status_page_subscribers(
                    organization_id=incident.organization_id,
                    notification_type='incident',
                    title=incident.title,
                    description=incident.description or "An incident has been reported.",
                    severity=severity_str
                )
            except Exception as e:
                print(f"Status page subscriber notification error: {e}")

            return email_success_count > 0 or slack_success

        except Exception as e:
            print(f"Notification error: {e}")
            return False

    async def notify_incident_acknowledged(self, incident: Incident, acknowledged_by: User) -> bool:
        """Notify team when incident is acknowledged"""
        try:
            # Get organization users except the one who acknowledged
            query = (
                select(User)
                .where(
                    User.organization_id == incident.organization_id,
                    User.is_active == True,
                    User.id != acknowledged_by.id
                )
            )
            result = await self.db.execute(query)
            users = result.scalars().all()

            users_to_notify = [u for u in users if u.notification_preferences.get('email', True)]

            # Send email notifications
            email_success_count = 0
            for user in users_to_notify:
                if await self.email_service.send_incident_acknowledged(user, incident, acknowledged_by):
                    email_success_count += 1

            # Send Slack update (uses per-org token)
            slack_success = False
            try:
                slack_service = await self._get_slack_service(incident.organization_id)
                if slack_service:
                    slack_success = await slack_service.send_incident_update(
                        "#incidents", incident, "acknowledged", acknowledged_by
                    )
            except Exception as e:
                print(f"Slack update error: {e}")

            print(f"Acknowledgment notifications sent - Email: {email_success_count}/{len(users_to_notify)}, Slack: {slack_success}")
            return email_success_count > 0 or slack_success

        except Exception as e:
            print(f"Acknowledgment notification error: {e}")
            return False

    async def notify_incident_resolved(self, incident: Incident, resolved_by: User) -> bool:
        """Notify team when incident is resolved"""
        try:
            # Get organization users except the one who resolved
            query = (
                select(User)
                .where(
                    User.organization_id == incident.organization_id,
                    User.is_active == True,
                    User.id != resolved_by.id
                )
            )
            result = await self.db.execute(query)
            users = result.scalars().all()

            users_to_notify = [u for u in users if u.notification_preferences.get('email', True)]

            # Send email notifications
            email_success_count = 0
            for user in users_to_notify:
                if await self.email_service.send_incident_resolved(user, incident, resolved_by):
                    email_success_count += 1

            # Send Slack update (uses per-org token)
            slack_success = False
            try:
                slack_service = await self._get_slack_service(incident.organization_id)
                if slack_service:
                    slack_success = await slack_service.send_incident_update(
                        "#incidents", incident, "resolved", resolved_by
                    )
            except Exception as e:
                print(f"Slack update error: {e}")

            print(f"Resolution notifications sent - Email: {email_success_count}/{len(users_to_notify)}, Slack: {slack_success}")

            # Also notify status page subscribers
            try:
                await self.notify_status_page_subscribers(
                    organization_id=incident.organization_id,
                    notification_type='resolved',
                    title=incident.title,
                    description=f"This incident has been resolved by {resolved_by.full_name}."
                )
            except Exception as e:
                print(f"Status page subscriber resolution notification error: {e}")

            return email_success_count > 0 or slack_success

        except Exception as e:
            print(f"Resolution notification error: {e}")
            return False

    async def notify_status_page_subscribers(
        self,
        organization_id,
        notification_type: str,  # 'incident', 'resolved', 'maintenance'
        title: str,
        description: str,
        severity: str = None,
        status_page_url: str = None
    ) -> int:
        """
        Notify all verified status page subscribers about an event.
        Returns number of notifications sent.
        """
        try:
            from app.models.status_page import StatusPage, StatusPageSubscriber

            # Get status page for org
            sp_query = select(StatusPage).where(StatusPage.organization_id == organization_id)
            sp_result = await self.db.execute(sp_query)
            status_page = sp_result.scalar_one_or_none()

            if not status_page:
                return 0

            # Get verified subscribers based on preferences
            query = select(StatusPageSubscriber).where(
                StatusPageSubscriber.status_page_id == status_page.id,
                StatusPageSubscriber.is_verified == True,
                StatusPageSubscriber.unsubscribed_at.is_(None)
            )

            # Filter by notification preferences
            if notification_type == 'incident':
                query = query.where(StatusPageSubscriber.notify_on_incidents == True)
            elif notification_type == 'resolved':
                query = query.where(StatusPageSubscriber.notify_on_resolved == True)
            elif notification_type == 'maintenance':
                query = query.where(StatusPageSubscriber.notify_on_maintenance == True)

            result = await self.db.execute(query)
            subscribers = result.scalars().all()

            if not subscribers:
                return 0

            # Prepare email content based on type
            if notification_type == 'incident':
                subject = f"🚨 Incident: {title}"
                color = "#dc2626"
                header = "New Incident Reported"
            elif notification_type == 'resolved':
                subject = f"✅ Resolved: {title}"
                color = "#059669"
                header = "Incident Resolved"
            elif notification_type == 'maintenance':
                subject = f"🔧 Scheduled Maintenance: {title}"
                color = "#f59e0b"
                header = "Scheduled Maintenance"
            else:
                subject = f"Status Update: {title}"
                color = "#3b82f6"
                header = "Status Update"

            page_url = status_page_url or f"{settings.FRONTEND_URL}/status/{status_page.slug}"
            unsubscribe_base = f"{settings.API_URL}/api/v1/status-pages/public/{status_page.slug}/unsubscribe"

            sent_count = 0
            for subscriber in subscribers:
                try:
                    unsubscribe_url = f"{unsubscribe_base}?email={subscriber.email}"

                    html_content = f"""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <div style="background: {color}; color: white; padding: 20px; text-align: center;">
                            <h1 style="margin: 0;">{status_page.name}</h1>
                        </div>
                        <div style="padding: 24px; background: #f9fafb;">
                            <h2 style="color: {color}; margin-top: 0;">{header}</h2>
                            <div style="background: white; padding: 16px; border-radius: 8px; border-left: 4px solid {color};">
                                <h3 style="margin-top: 0;">{title}</h3>
                                {f'<p><strong>Severity:</strong> {severity.upper()}</p>' if severity else ''}
                                <p>{description}</p>
                            </div>
                            <div style="margin-top: 24px; text-align: center;">
                                <a href="{page_url}"
                                   style="background: {color}; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                                    View Status Page
                                </a>
                            </div>
                        </div>
                        <div style="padding: 16px; text-align: center; color: #666; font-size: 12px;">
                            <p>You're receiving this because you subscribed to {status_page.name} status updates.</p>
                            <a href="{unsubscribe_url}" style="color: #666;">Unsubscribe</a>
                        </div>
                    </div>
                    """

                    if await self.email_service.send_email(
                        subscriber.email,
                        subject,
                        description,
                        html_content
                    ):
                        sent_count += 1

                except Exception as e:
                    print(f"Failed to notify subscriber {subscriber.email}: {e}")

            print(f"Status page notifications sent: {sent_count}/{len(subscribers)}")
            return sent_count

        except Exception as e:
            print(f"Status page notification error: {e}")
            return 0

    async def notify_escalation(self, incident: Incident, escalation_level: int) -> bool:
        """Send escalation notifications"""
        try:
            # For now, escalate to all admins
            query = (
                select(User)
                .where(
                    User.organization_id == incident.organization_id,
                    User.is_active == True,
                    User.role == "admin"
                )
            )
            result = await self.db.execute(query)
            admin_users = result.scalars().all()

            if not admin_users:
                # Fallback to all users if no admins
                query = (
                    select(User)
                    .where(
                        User.organization_id == incident.organization_id,
                        User.is_active == True
                    )
                )
                result = await self.db.execute(query)
                admin_users = result.scalars().all()

            users_to_notify = [u for u in admin_users if u.notification_preferences.get('email', True)]

            # Send escalation emails
            email_success_count = 0
            for user in users_to_notify:
                if await self.email_service.send_escalation_alert(user, incident, escalation_level):
                    email_success_count += 1

            # Send urgent Slack alert (uses per-org token)
            slack_success = False
            try:
                slack_service = await self._get_slack_service(incident.organization_id)
                if slack_service:
                    slack_success = await slack_service.send_incident_alert(
                        "#incidents", incident
                    )
            except Exception as e:
                print(f"Slack escalation alert error: {e}")

            print(f"Escalation notifications sent - Email: {email_success_count}/{len(users_to_notify)}, Slack: {slack_success}")
            return email_success_count > 0 or slack_success

        except Exception as e:
            print(f"Escalation notification error: {e}")
            return False