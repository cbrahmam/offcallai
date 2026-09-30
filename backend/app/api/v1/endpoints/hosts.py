# backend/app/api/v1/endpoints/hosts.py
"""
API endpoints for managing monitored hosts and agent operations.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_async_session
from app.core.security import get_current_user
from app.models.user import User
from app.services.host_service import host_service
from app.schemas.hosts import (
    HostRegister, HostHeartbeat, HostCreate, HostUpdate,
    HostResponse, HostListResponse, HostWithMetrics,
    AgentAPIKeyCreate, AgentAPIKeyResponse, AgentInstallInstructions
)
from app.services.metrics_service import metrics_service
from app.core.config import settings
from typing import Optional, Dict
import uuid
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================
# Agent Endpoints (API Key Auth)
# ============================================

async def get_org_from_agent_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_async_session)
) -> uuid.UUID:
    """Validate agent API key and return organization ID."""
    org_id = await host_service.verify_agent_api_key(x_api_key, db)
    if not org_id:
        raise HTTPException(status_code=401, detail="Invalid or expired API key")
    return org_id


@router.post("/agent/register", response_model=HostResponse, tags=["agent"])
async def register_agent(
    data: HostRegister,
    organization_id: uuid.UUID = Depends(get_org_from_agent_key),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Register a new agent or update existing registration.
    Called when an agent first connects or restarts.
    Requires agent API key authentication via X-API-Key header.
    """
    try:
        host = await host_service.register_agent(data, organization_id, db)
        return HostResponse(
            id=str(host.id),
            hostname=host.hostname,
            display_name=host.display_name,
            ip_address=host.ip_address,
            agent_id=host.agent_id,
            os=host.os,
            os_version=host.os_version,
            kernel=host.kernel,
            arch=host.arch,
            cpu_cores=host.cpu_cores,
            cpu_model=host.cpu_model,
            memory_total_bytes=host.memory_total_bytes,
            memory_total_gb=host.memory_total_gb,
            agent_version=host.agent_version,
            last_seen_at=host.last_seen_at,
            first_seen_at=host.first_seen_at,
            status=host.status,
            is_active=host.is_active,
            tags=host.tags or {},
            description=host.description,
            created_at=host.created_at,
            updated_at=host.updated_at
        )
    except Exception as e:
        logger.error(f"Agent registration failed: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/agent/heartbeat", tags=["agent"])
async def agent_heartbeat(
    data: HostHeartbeat,
    organization_id: uuid.UUID = Depends(get_org_from_agent_key),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Process agent heartbeat. Updates last_seen_at timestamp.
    Requires agent API key authentication via X-API-Key header.
    """
    host = await host_service.process_heartbeat(data, organization_id, db)
    if not host:
        raise HTTPException(status_code=404, detail="Agent not registered")
    return {"status": "ok", "host_id": str(host.id)}


# ============================================
# Agent API Key Management (MUST be before /{host_id})
# ============================================

@router.post("/api-keys", response_model=AgentAPIKeyResponse)
async def create_agent_api_key(
    data: AgentAPIKeyCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new API key for agent authentication.
    The full API key is only shown once in this response.
    """
    try:
        raw_key, key_info = await host_service.create_agent_api_key(
            data, current_user.organization_id, current_user.id, db
        )

        return AgentAPIKeyResponse(
            id=key_info["id"],
            name=key_info["name"],
            key_prefix=key_info["key_prefix"],
            description=key_info["description"],
            tags=key_info["tags"],
            created_at=key_info["created_at"],
            is_active=True,
            api_key=raw_key  # Only shown on creation
        )
    except Exception as e:
        logger.error(f"Error creating API key: {e}")
        raise HTTPException(status_code=500, detail="Failed to create API key")


@router.get("/api-keys")
async def list_agent_api_keys(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """List all agent API keys for the organization."""
    try:
        keys = await host_service.list_agent_api_keys(
            current_user.organization_id, db
        )
        return {"keys": keys}
    except Exception as e:
        logger.error(f"Error listing API keys: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve API keys")


@router.delete("/api-keys/{key_id}")
async def revoke_agent_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Revoke an agent API key."""
    try:
        key_uuid = uuid.UUID(key_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid key ID")

    success = await host_service.revoke_agent_api_key(
        key_uuid, current_user.organization_id, db
    )

    if not success:
        raise HTTPException(status_code=404, detail="API key not found")

    return {"status": "revoked", "key_id": key_id}


@router.get("/install-instructions", response_model=AgentInstallInstructions)
async def get_install_instructions(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get agent installation instructions.
    Includes a one-liner for easy installation.
    """
    # Get or create a default API key
    keys = await host_service.list_agent_api_keys(
        current_user.organization_id, db
    )

    if keys:
        api_key_hint = f"{keys[0]['key_prefix']}... (use your existing key)"
    else:
        api_key_hint = "YOUR_API_KEY (create one first with POST /api/v1/hosts/api-keys)"

    api_endpoint = settings.API_URL

    return AgentInstallInstructions(
        one_liner=f'curl -fsSL {api_endpoint}/install.sh | OFFCALL_API_KEY={api_key_hint} OFFCALL_API_URL={api_endpoint} bash',
        api_key=api_key_hint,
        api_endpoint=f"{api_endpoint}/api/v1",
        agent_download_url=f"{api_endpoint}/api/v1/hosts/agent/download",
        supported_platforms=["linux/amd64", "linux/arm64", "darwin/amd64", "darwin/arm64"]
    )


# ============================================
# Host Management Endpoints (User Auth)
# ============================================

@router.get("/", response_model=HostListResponse)
async def list_hosts(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status (active, inactive, alerting, maintenance)"),
    search: Optional[str] = Query(None, description="Search by hostname, display name, or IP"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get paginated list of monitored hosts for the organization."""
    try:
        return await host_service.list_hosts(
            organization_id=current_user.organization_id,
            db=db,
            status=status,
            search=search,
            page=page,
            per_page=per_page
        )
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error listing hosts: {e}\n{error_details}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve hosts: {str(e)}")


@router.get("/stats")
async def get_host_stats(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get host statistics for the organization."""
    try:
        stats = await host_service.get_host_stats(
            current_user.organization_id, db
        )
        return stats
    except Exception as e:
        logger.error(f"Error getting host stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve stats")


# Parameterized routes MUST come after specific routes
@router.get("/{host_id}", response_model=HostWithMetrics)
async def get_host(
    host_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get host details with current metrics."""
    try:
        host_uuid = uuid.UUID(host_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid host ID")

    host = await host_service.get_host(
        host_uuid, current_user.organization_id, db
    )

    if not host:
        raise HTTPException(status_code=404, detail="Host not found")

    # Get current metrics
    current_metrics = await metrics_service.get_host_current_metrics(
        host_uuid, current_user.organization_id, db
    )

    return HostWithMetrics(
        id=str(host.id),
        hostname=host.hostname,
        display_name=host.display_name,
        ip_address=host.ip_address,
        agent_id=host.agent_id,
        os=host.os,
        os_version=host.os_version,
        kernel=host.kernel,
        arch=host.arch,
        cpu_cores=host.cpu_cores,
        cpu_model=host.cpu_model,
        memory_total_bytes=host.memory_total_bytes,
        memory_total_gb=host.memory_total_gb,
        agent_version=host.agent_version,
        last_seen_at=host.last_seen_at,
        first_seen_at=host.first_seen_at,
        status=host.status,
        is_active=host.is_active,
        tags=host.tags or {},
        description=host.description,
        created_at=host.created_at,
        updated_at=host.updated_at,
        cpu_usage_percent=current_metrics.get("system.cpu.usage", {}).get("value"),
        memory_usage_percent=current_metrics.get("system.memory.usage_percent", {}).get("value"),
        disk_usage_percent=current_metrics.get("system.disk.usage_percent", {}).get("value"),
        network_in_bytes=current_metrics.get("system.network.bytes_in", {}).get("value"),
        network_out_bytes=current_metrics.get("system.network.bytes_out", {}).get("value")
    )


@router.post("/", response_model=HostResponse)
async def create_host(
    data: HostCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create a host manually (without agent)."""
    try:
        host = await host_service.create_host(
            data, current_user.organization_id, db
        )
        return HostResponse(
            id=str(host.id),
            hostname=host.hostname,
            display_name=host.display_name,
            ip_address=host.ip_address,
            agent_id=host.agent_id,
            os=host.os,
            os_version=host.os_version,
            kernel=host.kernel,
            arch=host.arch,
            cpu_cores=host.cpu_cores,
            cpu_model=host.cpu_model,
            memory_total_bytes=host.memory_total_bytes,
            memory_total_gb=host.memory_total_gb,
            agent_version=host.agent_version,
            last_seen_at=host.last_seen_at,
            first_seen_at=host.first_seen_at,
            status=host.status,
            is_active=host.is_active,
            tags=host.tags or {},
            description=host.description,
            created_at=host.created_at,
            updated_at=host.updated_at
        )
    except Exception as e:
        logger.error(f"Error creating host: {e}")
        raise HTTPException(status_code=500, detail="Failed to create host")


@router.patch("/{host_id}", response_model=HostResponse)
async def update_host(
    host_id: str,
    data: HostUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update host details."""
    try:
        host_uuid = uuid.UUID(host_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid host ID")

    host = await host_service.update_host(
        host_uuid, current_user.organization_id, data, db
    )

    if not host:
        raise HTTPException(status_code=404, detail="Host not found")

    return HostResponse(
        id=str(host.id),
        hostname=host.hostname,
        display_name=host.display_name,
        ip_address=host.ip_address,
        agent_id=host.agent_id,
        os=host.os,
        os_version=host.os_version,
        kernel=host.kernel,
        arch=host.arch,
        cpu_cores=host.cpu_cores,
        cpu_model=host.cpu_model,
        memory_total_bytes=host.memory_total_bytes,
        memory_total_gb=host.memory_total_gb,
        agent_version=host.agent_version,
        last_seen_at=host.last_seen_at,
        first_seen_at=host.first_seen_at,
        status=host.status,
        is_active=host.is_active,
        tags=host.tags or {},
        description=host.description,
        created_at=host.created_at,
        updated_at=host.updated_at
    )


@router.delete("/{host_id}")
async def delete_host(
    host_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Delete a host and its associated data."""
    try:
        host_uuid = uuid.UUID(host_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid host ID")

    success = await host_service.delete_host(
        host_uuid, current_user.organization_id, db
    )

    if not success:
        raise HTTPException(status_code=404, detail="Host not found")

    return {"status": "deleted", "host_id": host_id}
