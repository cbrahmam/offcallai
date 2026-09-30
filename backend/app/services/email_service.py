# backend/app/services/email_service.py
"""
Outbound email.

Two providers are supported: SMTP (the default for self-hosted installs) and
Azure Communication Services. Whichever is configured wins; SMTP takes
precedence when both are set.
"""

import asyncio
import functools
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

from app.core.config import settings
from app.models.incident import Incident
from app.models.user import User


class EmailService:
    """Sends email over SMTP or Azure Communication Services."""

    def __init__(self):
        self.from_email = settings.FROM_EMAIL
        self._client = None
        self._initialized = False
        self._provider = None

        if settings.SMTP_HOST:
            self._provider = "smtp"
            self._initialized = True
            print(f"✅ SMTP email initialized ({settings.SMTP_HOST}:{settings.SMTP_PORT})")
        elif settings.AZURE_COMMUNICATION_CONNECTION_STRING:
            self._provider = "azure"
            self._init_azure()
        else:
            print(
                "⚠️ No email provider configured. Set SMTP_HOST (and SMTP_PORT / "
                "SMTP_USERNAME / SMTP_PASSWORD) or AZURE_COMMUNICATION_CONNECTION_STRING."
            )

    def _init_azure(self):
        """Initialize Azure Communication Services client"""
        try:
            from azure.communication.email import EmailClient
            self._client = EmailClient.from_connection_string(
                settings.AZURE_COMMUNICATION_CONNECTION_STRING
            )
            self._initialized = True
            print("✅ Azure Communication Services email initialized")
        except ImportError:
            print("❌ azure-communication-email not installed. Run: pip install azure-communication-email")
        except Exception as e:
            print(f"❌ Azure email init failed: {e}")

    async def _send_azure(self, to_email: str, subject: str, html_content: str) -> bool:
        """Send email via Azure Communication Services"""
        try:
            message = {
                "senderAddress": self.from_email,
                "recipients": {
                    "to": [{"address": to_email}]
                },
                "content": {
                    "subject": subject,
                    "html": html_content
                }
            }

            poller = self._client.begin_send(message)
            result = poller.result()

            if result["status"] == "Succeeded":
                print(f"✅ Email sent to {to_email}: {subject}")
                return True
            else:
                print(f"❌ Email failed: {result}")
                return False

        except Exception as e:
            print(f"❌ Azure email error to {to_email}: {e}")
            return False

    def _send_smtp_blocking(self, to_email: str, subject: str, html_content: str) -> bool:
        """Send one message over SMTP. Runs in a worker thread."""
        message = EmailMessage()
        message["From"] = self.from_email
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content("This message requires an HTML-capable mail client.")
        message.add_alternative(html_content, subtype="html")

        try:
            if settings.SMTP_USE_SSL:
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context, timeout=15)
            else:
                server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)

            with server:
                if settings.SMTP_USE_TLS and not settings.SMTP_USE_SSL:
                    server.starttls(context=ssl.create_default_context())
                if settings.SMTP_USERNAME:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD or "")
                server.send_message(message)

            print(f"✅ Email sent to {to_email}: {subject}")
            return True
        except Exception as e:
            print(f"❌ SMTP error to {to_email}: {e}")
            return False

    async def _send_smtp(self, to_email: str, subject: str, html_content: str) -> bool:
        """smtplib is blocking, so run it off the event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            functools.partial(self._send_smtp_blocking, to_email, subject, html_content),
        )

    async def send_email(self, to_email: str, subject: str, body: str, html_content: str = None) -> bool:
        """Generic method to send an email"""
        if not self._initialized:
            print("⚠️ Email service not initialized")
            return False

        # Convert plain text to HTML if not provided
        if html_content is None:
            html_content = f"<pre style='font-family: Arial, sans-serif; white-space: pre-wrap;'>{body}</pre>"

        if self._provider == "smtp":
            return await self._send_smtp(to_email, subject, html_content)
        return await self._send_azure(to_email, subject, html_content)

    async def send_incident_alert(self, user: User, incident: Incident) -> bool:
        """Send incident alert email"""
        subject = f"🚨 {incident.severity.upper()} Incident: {incident.title}"

        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px;">
            <h2 style="color: #dc2626;">New Incident Alert</h2>
            <div style="background: #fef2f2; padding: 16px; border-radius: 8px; margin: 16px 0;">
                <h3>{incident.title}</h3>
                <p><strong>Severity:</strong> {incident.severity.upper()}</p>
                <p><strong>Status:</strong> {incident.status}</p>
                <p><strong>Description:</strong> {incident.description or 'No description'}</p>
                <p><strong>Created:</strong> {incident.created_at}</p>
            </div>
            <div style="margin: 24px 0;">
                <a href="{settings.FRONTEND_URL}/incidents/{incident.id}"
                   style="background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
                    View Incident
                </a>
            </div>
            <p style="color: #666; font-size: 14px;">
                OffCall AI - Incident Response Platform
            </p>
        </div>
        """

        return await self.send_email(user.email, subject, "", html_content)

    async def send_incident_acknowledged(self, user: User, incident: Incident, acknowledged_by: User) -> bool:
        """Send incident acknowledged notification"""
        subject = f"👀 Incident Acknowledged: {incident.title}"

        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px;">
            <h2 style="color: #2563eb;">Incident Acknowledged</h2>
            <div style="background: #eff6ff; padding: 16px; border-radius: 8px; margin: 16px 0;">
                <h3>{incident.title}</h3>
                <p><strong>Acknowledged by:</strong> {acknowledged_by.full_name}</p>
                <p><strong>Severity:</strong> {incident.severity.upper()}</p>
                <p><strong>Status:</strong> {incident.status}</p>
                <p><strong>Acknowledged at:</strong> {incident.acknowledged_at}</p>
            </div>
            <div style="margin: 24px 0;">
                <a href="{settings.FRONTEND_URL}/incidents/{incident.id}"
                   style="background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
                    View Incident
                </a>
            </div>
            <p style="color: #666; font-size: 14px;">
                OffCall AI - Incident Response Platform
            </p>
        </div>
        """

        return await self.send_email(user.email, subject, "", html_content)

    async def send_incident_resolved(self, user: User, incident: Incident, resolved_by: User) -> bool:
        """Send incident resolved notification"""
        subject = f"✅ Incident Resolved: {incident.title}"

        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px;">
            <h2 style="color: #059669;">Incident Resolved</h2>
            <div style="background: #f0fdf4; padding: 16px; border-radius: 8px; margin: 16px 0;">
                <h3>{incident.title}</h3>
                <p><strong>Resolved by:</strong> {resolved_by.full_name}</p>
                <p><strong>Status:</strong> {incident.status}</p>
                <p><strong>Resolved at:</strong> {incident.resolved_at}</p>
            </div>
            <div style="margin: 24px 0;">
                <a href="{settings.FRONTEND_URL}/incidents/{incident.id}"
                   style="background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
                    View Incident
                </a>
            </div>
        </div>
        """

        return await self.send_email(user.email, subject, "", html_content)

    async def send_escalation_alert(self, user: User, incident: Incident, escalation_level: int) -> bool:
        """Send escalation alert email"""
        subject = f"🔴 ESCALATION Level {escalation_level}: {incident.title}"

        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px;">
            <h2 style="color: #dc2626;">Incident Escalation</h2>
            <div style="background: #fef2f2; padding: 16px; border-radius: 8px; margin: 16px 0; border-left: 4px solid #dc2626;">
                <h3>{incident.title}</h3>
                <p><strong>Escalation Level:</strong> {escalation_level}</p>
                <p><strong>Severity:</strong> {incident.severity.upper()}</p>
                <p><strong>Status:</strong> {incident.status}</p>
                <p><strong>No response for:</strong> {(incident.updated_at - incident.created_at).total_seconds() // 60:.0f} minutes</p>
            </div>
            <div style="margin: 24px 0;">
                <a href="{settings.FRONTEND_URL}/incidents/{incident.id}"
                   style="background: #dc2626; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
                    URGENT: View Incident
                </a>
            </div>
            <p style="color: #dc2626; font-weight: bold;">
                This incident requires immediate attention.
            </p>
        </div>
        """

        return await self.send_email(user.email, subject, "", html_content)
