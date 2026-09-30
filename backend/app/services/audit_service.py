# backend/app/services/audit_service.py
"""
Audit Logging Service

Provides comprehensive audit logging for security-critical actions and
session management for privilege changes.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from fastapi import Request

from app.models.audit_log import AuditLog, AuditAction
from app.models.user import User

logger = logging.getLogger(__name__)


class AuditCategory:
    """Categories for audit events"""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    SECURITY = "security"
    ADMIN = "admin"
    SYSTEM = "system"


class AuditService:
    """Service for comprehensive audit logging"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        organization_id: UUID,
        action: str,
        description: str,
        user_id: Optional[UUID] = None,
        user_name: Optional[str] = None,
        incident_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        category: str = AuditCategory.SYSTEM,
        severity: str = "info",
        details: Optional[Dict[str, Any]] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Create an audit log entry.

        Args:
            organization_id: The organization this event belongs to
            action: The action being logged (e.g., "user_login", "role_change")
            description: Human-readable description of the event
            user_id: The user who performed the action (if applicable)
            user_name: The user's name for display
            incident_id: Related incident (if applicable)
            ip_address: Client IP address
            user_agent: Client user agent string
            category: Category of the audit event
            severity: Event severity (info, warning, critical)
            details: Structured details about the event
            extra_data: Additional context data

        Returns:
            The created AuditLog entry
        """
        audit_entry = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            user_name=user_name,
            incident_id=incident_id,
            action=action,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
            extra_data={
                "category": category,
                "severity": severity,
                **(extra_data or {})
            }
        )

        self.db.add(audit_entry)
        await self.db.commit()

        # Log to application logs as well for monitoring
        log_msg = f"AUDIT [{category}] [{severity}] {action}: {description}"
        if severity == "critical":
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        return audit_entry

    async def log_from_request(
        self,
        request: Request,
        organization_id: UUID,
        action: str,
        description: str,
        user: Optional[User] = None,
        **kwargs
    ) -> AuditLog:
        """
        Create an audit log entry with request context.

        Automatically extracts IP address and user agent from the request.
        """
        # Get client IP (handle proxies)
        ip_address = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if not ip_address:
            ip_address = request.client.host if request.client else None

        user_agent = request.headers.get("User-Agent", "")[:500]

        return await self.log(
            organization_id=organization_id,
            action=action,
            description=description,
            user_id=user.id if user else None,
            user_name=user.full_name if user else None,
            ip_address=ip_address,
            user_agent=user_agent,
            **kwargs
        )

    # ==================== Authentication Events ====================

    async def log_login_success(
        self,
        request: Request,
        user: User,
        mfa_used: bool = False
    ) -> AuditLog:
        """Log successful login"""
        return await self.log_from_request(
            request=request,
            organization_id=user.organization_id,
            action="user_login",
            description=f"User {user.email} logged in successfully",
            user=user,
            category=AuditCategory.AUTHENTICATION,
            severity="info",
            details={
                "mfa_used": mfa_used,
                "login_method": "password"
            }
        )

    async def log_login_failure(
        self,
        request: Request,
        email: str,
        reason: str,
        organization_id: Optional[UUID] = None
    ) -> Optional[AuditLog]:
        """Log failed login attempt"""
        if not organization_id:
            # Can't log without org context, but log to application logs
            ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            if not ip:
                ip = request.client.host if request.client else "unknown"
            logger.warning(f"AUDIT [authentication] [warning] login_failed: Failed login for {email} from {ip} - {reason}")
            return None

        return await self.log_from_request(
            request=request,
            organization_id=organization_id,
            action="login_failed",
            description=f"Failed login attempt for {email}: {reason}",
            category=AuditCategory.AUTHENTICATION,
            severity="warning",
            details={
                "email": email,
                "reason": reason
            }
        )

    async def log_logout(
        self,
        request: Request,
        user: User
    ) -> AuditLog:
        """Log user logout"""
        return await self.log_from_request(
            request=request,
            organization_id=user.organization_id,
            action="user_logout",
            description=f"User {user.email} logged out",
            user=user,
            category=AuditCategory.AUTHENTICATION,
            severity="info"
        )

    # ==================== Authorization Events ====================

    async def log_role_change(
        self,
        request: Request,
        admin_user: User,
        target_user: User,
        old_role: str,
        new_role: str
    ) -> AuditLog:
        """Log user role change - this is a security-critical event"""
        return await self.log_from_request(
            request=request,
            organization_id=admin_user.organization_id,
            action="role_change",
            description=f"User {target_user.email} role changed from {old_role} to {new_role} by {admin_user.email}",
            user=admin_user,
            category=AuditCategory.AUTHORIZATION,
            severity="critical",
            details={
                "target_user_id": str(target_user.id),
                "target_user_email": target_user.email,
                "old_role": old_role,
                "new_role": new_role
            }
        )

    async def log_permission_denied(
        self,
        request: Request,
        user: User,
        resource: str,
        action_attempted: str
    ) -> AuditLog:
        """Log when a user attempts to access something they don't have permission for"""
        return await self.log_from_request(
            request=request,
            organization_id=user.organization_id,
            action="permission_denied",
            description=f"User {user.email} denied access to {resource} for action {action_attempted}",
            user=user,
            category=AuditCategory.AUTHORIZATION,
            severity="warning",
            details={
                "resource": resource,
                "action_attempted": action_attempted
            }
        )

    # ==================== Data Events ====================

    async def log_data_export(
        self,
        request: Request,
        user: User,
        export_type: str,
        record_count: int
    ) -> AuditLog:
        """Log data export for compliance"""
        return await self.log_from_request(
            request=request,
            organization_id=user.organization_id,
            action="data_export",
            description=f"User {user.email} exported {record_count} {export_type} records",
            user=user,
            category=AuditCategory.DATA_ACCESS,
            severity="info",
            details={
                "export_type": export_type,
                "record_count": record_count
            }
        )

    async def log_data_deletion(
        self,
        request: Request,
        user: User,
        data_type: str,
        record_ids: List[str]
    ) -> AuditLog:
        """Log data deletion for compliance"""
        return await self.log_from_request(
            request=request,
            organization_id=user.organization_id,
            action="data_deletion",
            description=f"User {user.email} deleted {len(record_ids)} {data_type} records",
            user=user,
            category=AuditCategory.DATA_MODIFICATION,
            severity="warning",
            details={
                "data_type": data_type,
                "record_count": len(record_ids),
                "record_ids": record_ids[:10]  # Only store first 10 for brevity
            }
        )

    # ==================== Security Events ====================

    async def log_api_key_created(
        self,
        request: Request,
        user: User,
        key_name: str,
        key_id: str
    ) -> AuditLog:
        """Log API key creation"""
        return await self.log_from_request(
            request=request,
            organization_id=user.organization_id,
            action="api_key_created",
            description=f"API key '{key_name}' created by {user.email}",
            user=user,
            category=AuditCategory.SECURITY,
            severity="info",
            details={
                "key_name": key_name,
                "key_id": key_id
            }
        )

    async def log_api_key_revoked(
        self,
        request: Request,
        user: User,
        key_name: str,
        key_id: str
    ) -> AuditLog:
        """Log API key revocation"""
        return await self.log_from_request(
            request=request,
            organization_id=user.organization_id,
            action="api_key_revoked",
            description=f"API key '{key_name}' revoked by {user.email}",
            user=user,
            category=AuditCategory.SECURITY,
            severity="warning",
            details={
                "key_name": key_name,
                "key_id": key_id
            }
        )

    async def log_mfa_enabled(
        self,
        request: Request,
        user: User
    ) -> AuditLog:
        """Log MFA enablement"""
        return await self.log_from_request(
            request=request,
            organization_id=user.organization_id,
            action="mfa_enabled",
            description=f"MFA enabled for user {user.email}",
            user=user,
            category=AuditCategory.SECURITY,
            severity="info"
        )

    async def log_mfa_disabled(
        self,
        request: Request,
        user: User,
        admin_user: Optional[User] = None
    ) -> AuditLog:
        """Log MFA disablement - security critical"""
        actor = admin_user or user
        return await self.log_from_request(
            request=request,
            organization_id=user.organization_id,
            action="mfa_disabled",
            description=f"MFA disabled for user {user.email}" + (f" by admin {admin_user.email}" if admin_user else ""),
            user=actor,
            category=AuditCategory.SECURITY,
            severity="critical",
            details={
                "target_user_id": str(user.id),
                "disabled_by_admin": admin_user is not None
            }
        )

    async def log_suspicious_activity(
        self,
        request: Request,
        user: Optional[User],
        activity_type: str,
        details: Dict[str, Any],
        organization_id: Optional[UUID] = None
    ) -> Optional[AuditLog]:
        """Log suspicious activity detected"""
        org_id = organization_id or (user.organization_id if user else None)
        if not org_id:
            logger.warning(f"AUDIT [security] [critical] suspicious_activity: {activity_type} - {details}")
            return None

        return await self.log_from_request(
            request=request,
            organization_id=org_id,
            action="suspicious_activity",
            description=f"Suspicious activity detected: {activity_type}",
            user=user,
            category=AuditCategory.SECURITY,
            severity="critical",
            details=details
        )

    # ==================== Query Methods ====================

    async def get_audit_logs(
        self,
        organization_id: UUID,
        limit: int = 100,
        offset: int = 0,
        action: Optional[str] = None,
        user_id: Optional[UUID] = None,
        category: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[AuditLog]:
        """Query audit logs with filters"""
        query = select(AuditLog).where(
            AuditLog.organization_id == organization_id
        )

        if action:
            query = query.where(AuditLog.action == action)

        if user_id:
            query = query.where(AuditLog.user_id == user_id)

        if category:
            query = query.where(AuditLog.extra_data["category"].astext == category)

        if start_date:
            query = query.where(AuditLog.created_at >= start_date)

        if end_date:
            query = query.where(AuditLog.created_at <= end_date)

        query = query.order_by(AuditLog.created_at.desc())
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        return result.scalars().all()


class SessionManager:
    """
    Manages user sessions and handles privilege changes.

    When a user's role or permissions change, their existing sessions
    should be invalidated to ensure they get fresh tokens with updated claims.
    """

    # In-memory store for invalidated sessions (use Redis in production)
    _invalidated_users: Dict[str, datetime] = {}

    @classmethod
    def invalidate_user_sessions(cls, user_id: str, reason: str = "privilege_change"):
        """
        Invalidate all sessions for a user.

        This should be called when:
        - User's role changes
        - User's permissions change
        - User is deactivated
        - Security concern requires re-authentication
        """
        cls._invalidated_users[user_id] = datetime.utcnow()
        logger.info(f"All sessions invalidated for user {user_id}: {reason}")

    @classmethod
    def is_session_valid(cls, user_id: str, token_issued_at: datetime) -> bool:
        """
        Check if a session is still valid.

        Returns False if the user's sessions were invalidated after the token was issued.
        """
        if user_id not in cls._invalidated_users:
            return True

        invalidation_time = cls._invalidated_users[user_id]
        return token_issued_at > invalidation_time

    @classmethod
    def clear_user_invalidation(cls, user_id: str):
        """Clear invalidation after user successfully re-authenticates"""
        if user_id in cls._invalidated_users:
            del cls._invalidated_users[user_id]
