# backend/app/api/deps.py
"""
API Dependencies - Common dependencies for API endpoints.
Re-exports from app.core.deps plus API-specific dependencies.
"""

from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.models.organization import Organization
from app.models.host import Host
from app.services.host_service import host_service
import uuid
import hashlib

# Re-export from core.security (consistent with working endpoints)
from app.core.security import get_current_user

# Get organization for current user
async def get_current_organization(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Organization:
    """Get current user's organization"""
    result = await db.execute(
        select(Organization).where(
            Organization.id == current_user.organization_id,
            Organization.is_active == True
        )
    )
    organization = result.scalar_one_or_none()

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    return organization


async def get_api_key_host(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db)
) -> Host:
    """
    Validate agent API key and return the associated Host.
    For agent ingestion endpoints that need host context.
    """
    org_id = await host_service.verify_agent_api_key(x_api_key, db)
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key"
        )

    # Create a minimal Host-like object with the organization_id
    # Since the API key is organization-level, not host-level
    class AgentHost:
        def __init__(self, organization_id: uuid.UUID):
            self.organization_id = organization_id
            self.id = None
            self.hostname = "agent"

    return AgentHost(org_id)


async def get_org_from_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db)
) -> uuid.UUID:
    """
    Validate agent API key and return organization ID.
    Simpler version for endpoints that only need org_id.
    """
    org_id = await host_service.verify_agent_api_key(x_api_key, db)
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key"
        )
    return org_id
