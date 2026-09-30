# backend/app/services/host_service.py
"""
Host service for managing monitored hosts and agent registrations.
"""

import uuid
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy import select, func, desc, and_, or_, update, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.models.host import Host, HostStatus
from app.models.user import User
from app.schemas.hosts import (
    HostRegister, HostHeartbeat, HostCreate, HostUpdate,
    HostResponse, HostSummary, HostListResponse, HostWithMetrics,
    AgentAPIKeyCreate, AgentAPIKeyResponse
)

logger = logging.getLogger(__name__)


class HostService:
    """Service for host and agent operations."""

    # ============================================
    # Agent Registration & Heartbeat
    # ============================================

    async def register_agent(
        self,
        data: HostRegister,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Host:
        """
        Register a new agent or update existing one.
        Called when agent first connects or restarts.
        """
        # Check if host already exists by agent_id
        result = await db.execute(
            select(Host).where(
                and_(
                    Host.agent_id == data.agent_id,
                    Host.organization_id == organization_id
                )
            )
        )
        existing_host = result.scalar_one_or_none()

        if existing_host:
            # Update existing host
            existing_host.hostname = data.hostname
            existing_host.os = data.os
            existing_host.os_version = data.os_version
            existing_host.kernel = data.kernel
            existing_host.arch = data.arch
            existing_host.cpu_cores = data.cpu_cores
            existing_host.cpu_model = data.cpu_model
            existing_host.memory_total_bytes = data.memory_total_bytes
            existing_host.agent_version = data.agent_version
            existing_host.ip_address = data.ip_address
            existing_host.last_seen_at = datetime.utcnow()
            existing_host.status = HostStatus.ACTIVE.value
            existing_host.is_active = True

            if data.display_name:
                existing_host.display_name = data.display_name
            if data.tags:
                # Merge tags
                existing_tags = existing_host.tags or {}
                existing_tags.update(data.tags)
                existing_host.tags = existing_tags
            if data.description:
                existing_host.description = data.description

            await db.commit()
            await db.refresh(existing_host)
            logger.info(f"Updated host registration: {existing_host.hostname} ({existing_host.id})")
            return existing_host

        # Create new host
        host_id = uuid.uuid4()
        host = Host(
            id=host_id,
            organization_id=organization_id,
            hostname=data.hostname,
            display_name=data.display_name or data.hostname,
            ip_address=data.ip_address,
            agent_id=data.agent_id,
            os=data.os,
            os_version=data.os_version,
            kernel=data.kernel,
            arch=data.arch,
            cpu_cores=data.cpu_cores,
            cpu_model=data.cpu_model,
            memory_total_bytes=data.memory_total_bytes,
            agent_version=data.agent_version,
            first_seen_at=datetime.utcnow(),
            last_seen_at=datetime.utcnow(),
            status=HostStatus.ACTIVE.value,
            is_active=True,
            tags=data.tags or {},
            description=data.description
        )

        db.add(host)
        await db.commit()
        await db.refresh(host)

        logger.info(f"Registered new host: {host.hostname} ({host.id})")
        return host

    async def process_heartbeat(
        self,
        data: HostHeartbeat,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[Host]:
        """
        Process agent heartbeat. Updates last_seen_at.
        """
        result = await db.execute(
            select(Host).where(
                and_(
                    Host.agent_id == data.agent_id,
                    Host.organization_id == organization_id
                )
            )
        )
        host = result.scalar_one_or_none()

        if not host:
            logger.warning(f"Heartbeat from unknown agent: {data.agent_id}")
            return None

        host.last_seen_at = datetime.utcnow()
        if data.agent_version:
            host.agent_version = data.agent_version
        if data.ip_address:
            host.ip_address = data.ip_address

        # Mark as active if it was inactive
        if host.status == HostStatus.INACTIVE.value:
            host.status = HostStatus.ACTIVE.value

        await db.commit()
        return host

    async def get_host_by_agent_id(
        self,
        agent_id: str,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[Host]:
        """Get host by agent ID."""
        result = await db.execute(
            select(Host).where(
                and_(
                    Host.agent_id == agent_id,
                    Host.organization_id == organization_id
                )
            )
        )
        return result.scalar_one_or_none()

    # ============================================
    # Host CRUD Operations
    # ============================================

    async def get_host(
        self,
        host_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[Host]:
        """Get a host by ID."""
        result = await db.execute(
            select(Host).where(
                and_(
                    Host.id == host_id,
                    Host.organization_id == organization_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_hosts(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession,
        status: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> HostListResponse:
        """List hosts with filtering and pagination."""
        # Build base query
        query = select(Host).where(Host.organization_id == organization_id)

        # Apply filters
        if status:
            query = query.where(Host.status == status)
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    Host.hostname.ilike(search_pattern),
                    Host.display_name.ilike(search_pattern),
                    Host.ip_address.ilike(search_pattern)
                )
            )
        if tags:
            # Filter by tags using JSONB containment
            for key, value in tags.items():
                query = query.where(Host.tags.contains({key: value}))

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        # Apply pagination and ordering
        offset = (page - 1) * per_page
        query = query.order_by(desc(Host.last_seen_at)).offset(offset).limit(per_page)

        result = await db.execute(query)
        hosts = result.scalars().all()

        # Convert to response - handle status enum conversion
        from app.schemas.hosts import HostStatus as SchemaHostStatus

        host_summaries = []
        for h in hosts:
            # Convert status string to enum, default to ACTIVE
            try:
                status_value = SchemaHostStatus(h.status) if h.status else SchemaHostStatus.ACTIVE
            except ValueError:
                status_value = SchemaHostStatus.ACTIVE

            host_summaries.append(
                HostSummary(
                    id=str(h.id),
                    hostname=h.hostname,
                    display_name=h.display_name,
                    os=h.os,
                    status=status_value,
                    last_seen_at=h.last_seen_at,
                    tags=h.tags or {}
                )
            )

        return HostListResponse(
            hosts=host_summaries,
            total=total,
            page=page,
            per_page=per_page
        )

    async def create_host(
        self,
        data: HostCreate,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Host:
        """Create a host manually (without agent)."""
        host_id = uuid.uuid4()

        host = Host(
            id=host_id,
            organization_id=organization_id,
            hostname=data.hostname,
            display_name=data.display_name or data.hostname,
            ip_address=data.ip_address,
            os=data.os,
            os_version=data.os_version,
            arch=data.arch,
            cpu_cores=data.cpu_cores,
            memory_total_bytes=data.memory_total_bytes,
            tags=data.tags or {},
            description=data.description,
            status=HostStatus.INACTIVE.value,  # Manual hosts start as inactive
            is_active=True,
            first_seen_at=datetime.utcnow()
        )

        db.add(host)
        await db.commit()
        await db.refresh(host)

        logger.info(f"Created manual host: {host.hostname} ({host.id})")
        return host

    async def update_host(
        self,
        host_id: uuid.UUID,
        organization_id: uuid.UUID,
        data: HostUpdate,
        db: AsyncSession
    ) -> Optional[Host]:
        """Update host details."""
        host = await self.get_host(host_id, organization_id, db)
        if not host:
            return None

        if data.display_name is not None:
            host.display_name = data.display_name
        if data.ip_address is not None:
            host.ip_address = data.ip_address
        if data.tags is not None:
            host.tags = data.tags
        if data.description is not None:
            host.description = data.description
        if data.is_active is not None:
            host.is_active = data.is_active

        host.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(host)

        logger.info(f"Updated host: {host.hostname} ({host.id})")
        return host

    async def delete_host(
        self,
        host_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> bool:
        """Delete a host."""
        host = await self.get_host(host_id, organization_id, db)
        if not host:
            return False

        await db.delete(host)
        await db.commit()

        logger.info(f"Deleted host: {host.hostname} ({host_id})")
        return True

    # ============================================
    # Host Status Management
    # ============================================

    async def mark_inactive_hosts(
        self,
        db: AsyncSession,
        threshold_minutes: int = 5
    ) -> int:
        """
        Mark hosts as inactive if no heartbeat received within threshold.
        Called periodically by a background worker.
        """
        threshold_time = datetime.utcnow() - timedelta(minutes=threshold_minutes)

        result = await db.execute(
            update(Host)
            .where(
                and_(
                    Host.last_seen_at < threshold_time,
                    Host.status == HostStatus.ACTIVE.value
                )
            )
            .values(status=HostStatus.INACTIVE.value)
        )

        await db.commit()
        count = result.rowcount
        if count > 0:
            logger.info(f"Marked {count} hosts as inactive")
        return count

    async def get_host_stats(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get host statistics for an organization."""
        # Count by status
        result = await db.execute(
            select(Host.status, func.count(Host.id))
            .where(Host.organization_id == organization_id)
            .group_by(Host.status)
        )
        status_counts = dict(result.all())

        # Total hosts
        total = sum(status_counts.values())

        # Recent hosts (registered in last 24h)
        yesterday = datetime.utcnow() - timedelta(hours=24)
        result = await db.execute(
            select(func.count(Host.id))
            .where(
                and_(
                    Host.organization_id == organization_id,
                    Host.first_seen_at >= yesterday
                )
            )
        )
        recent_count = result.scalar() or 0

        return {
            "total": total,
            "active": status_counts.get(HostStatus.ACTIVE.value, 0),
            "inactive": status_counts.get(HostStatus.INACTIVE.value, 0),
            "alerting": status_counts.get(HostStatus.ALERTING.value, 0),
            "maintenance": status_counts.get(HostStatus.MAINTENANCE.value, 0),
            "new_last_24h": recent_count
        }

    # ============================================
    # Agent API Key Management
    # ============================================

    async def create_agent_api_key(
        self,
        data: AgentAPIKeyCreate,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        db: AsyncSession
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Create a new API key for agent authentication.
        Returns the raw API key (shown once) and key metadata.
        """
        # Generate a secure random API key
        raw_key = f"oai_{secrets.token_urlsafe(32)}"
        key_prefix = raw_key[:8]  # First 8 chars for display hint
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        key_id = uuid.uuid4()

        # Insert into agent_api_keys table
        import json
        tags_json = json.dumps(data.tags or {})
        await db.execute(
            text("""
                INSERT INTO agent_api_keys (id, organization_id, created_by_id, name, description, key_hash, key_prefix, tags, created_at)
                VALUES (:id, :org_id, :user_id, :name, :desc, :hash, :prefix, CAST(:tags AS jsonb), :created_at)
            """),
            {
                "id": key_id,
                "org_id": organization_id,
                "user_id": user_id,
                "name": data.name,
                "desc": data.description,
                "hash": key_hash,
                "prefix": key_prefix,
                "tags": tags_json,
                "created_at": datetime.utcnow()
            }
        )
        await db.commit()

        logger.info(f"Created agent API key: {data.name} ({key_prefix}...)")

        return raw_key, {
            "id": str(key_id),
            "name": data.name,
            "key_prefix": key_prefix,
            "description": data.description,
            "tags": data.tags or {},
            "created_at": datetime.utcnow().isoformat()
        }

    async def verify_agent_api_key(
        self,
        api_key: str,
        db: AsyncSession
    ) -> Optional[uuid.UUID]:
        """
        Verify an agent API key and return the organization_id if valid.
        """
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        result = await db.execute(
            text("""
                SELECT organization_id, id FROM agent_api_keys
                WHERE key_hash = :hash AND is_active = true
                AND (expires_at IS NULL OR expires_at > NOW())
            """),
            {"hash": key_hash}
        )
        row = result.fetchone()

        if row:
            # Update last_used_at and use_count
            await db.execute(
                text("""
                    UPDATE agent_api_keys
                    SET last_used_at = NOW(), use_count = use_count + 1
                    WHERE id = :key_id
                """),
                {"key_id": row[1]}
            )
            await db.commit()
            return row[0]

        return None

    async def list_agent_api_keys(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """List all agent API keys for an organization."""
        result = await db.execute(
            text("""
                SELECT id, name, key_prefix, description, tags, last_used_at, use_count, is_active, created_at
                FROM agent_api_keys
                WHERE organization_id = :org_id AND revoked_at IS NULL
                ORDER BY created_at DESC
            """),
            {"org_id": organization_id}
        )
        rows = result.fetchall()

        return [
            {
                "id": str(row[0]),
                "name": row[1],
                "key_prefix": row[2],
                "description": row[3],
                "tags": row[4] or {},
                "last_used_at": row[5].isoformat() if row[5] else None,
                "use_count": row[6],
                "is_active": row[7],
                "created_at": row[8].isoformat() if row[8] else None
            }
            for row in rows
        ]

    async def revoke_agent_api_key(
        self,
        key_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> bool:
        """Revoke an agent API key."""
        result = await db.execute(
            text("""
                UPDATE agent_api_keys
                SET is_active = false, revoked_at = NOW()
                WHERE id = :key_id AND organization_id = :org_id
            """),
            {"key_id": key_id, "org_id": organization_id}
        )
        await db.commit()

        if result.rowcount > 0:
            logger.info(f"Revoked agent API key: {key_id}")
            return True
        return False


# Singleton instance
host_service = HostService()
