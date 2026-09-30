# backend/app/api/v1/endpoints/profiles.py
"""API endpoints for Continuous Profiling."""

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID
from datetime import datetime

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.api_keys import APIKey
from app.schemas.profile import (
    ProfileUpload,
    ProfileUploadResponse,
    ProfileSummary,
    ProfileDetail,
    ProfileWithData,
    FlamegraphData,
    ProfileDiff,
    ProfileDiffRequest,
    ServiceProfilingOverview,
)
from app.services.profiling_service import ProfilingService
from sqlalchemy import select

router = APIRouter()


async def get_org_from_api_key(api_key: str, db: AsyncSession) -> Optional[UUID]:
    """Get organization ID from API key."""
    query = select(APIKey).where(
        APIKey.key == api_key,
        APIKey.is_active == True
    )
    result = await db.execute(query)
    key_record = result.scalar_one_or_none()

    if key_record:
        return key_record.organization_id
    return None


# ========================================
# Profile Upload (API Key Auth for Agents)
# ========================================

@router.post(
    "/profiles/upload",
    response_model=ProfileUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_profile(
    profile: ProfileUpload,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a profile from an agent.

    Authentication: API Key (X-API-Key header) or Bearer token.

    Profiles are stored compressed and indexed for quick retrieval.
    """
    organization_id = None

    # Try API key auth first
    if x_api_key:
        organization_id = await get_org_from_api_key(x_api_key, db)

    # Fall back to Bearer token
    if not organization_id and authorization:
        if authorization.startswith("Bearer "):
            token = authorization[7:]
            organization_id = await get_org_from_api_key(token, db)

    if not organization_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )

    service = ProfilingService(db)
    try:
        return await service.upload_profile(profile, organization_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ========================================
# Profile Retrieval (JWT Auth)
# ========================================

@router.get(
    "/profiles",
    response_model=dict,
)
async def list_profiles(
    service_name: Optional[str] = None,
    profile_type: Optional[str] = None,
    environment: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List profiles with filtering and pagination.
    """
    service = ProfilingService(db)
    profiles, total = await service.list_profiles(
        organization_id=current_user.organization_id,
        service_name=service_name,
        profile_type=profile_type,
        environment=environment,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )

    return {
        "profiles": [p.model_dump() for p in profiles],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/profiles/services",
    response_model=dict,
)
async def list_profiled_services(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all services with profiling data.
    """
    from sqlalchemy import func
    from app.models.profile import Profile

    query = select(
        Profile.service_name,
        func.count(Profile.id).label("profile_count"),
        func.max(Profile.start_time).label("last_profile_at"),
    ).where(
        Profile.organization_id == current_user.organization_id
    ).group_by(Profile.service_name)

    result = await db.execute(query)
    services = [
        {
            "service_name": row.service_name,
            "profile_count": row.profile_count,
            "last_profile_at": row.last_profile_at.isoformat() if row.last_profile_at else None,
        }
        for row in result.all()
    ]

    return {"services": services}


@router.get(
    "/profiles/services/{service_name}/overview",
    response_model=ServiceProfilingOverview,
)
async def get_service_profiling_overview(
    service_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get profiling overview for a service.

    Returns summary statistics and recent activity.
    """
    service = ProfilingService(db)
    overview = await service.get_service_overview(
        service_name=service_name,
        organization_id=current_user.organization_id,
    )

    if not overview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profiling data found for service"
        )

    return overview


@router.post(
    "/profiles/compare",
    response_model=ProfileDiff,
)
async def compare_profiles(
    request: ProfileDiffRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Compare two profiles and return the diff.

    Useful for identifying performance regressions between deployments.
    """
    service = ProfilingService(db)
    diff = await service.compare_profiles(
        base_profile_id=request.base_profile_id,
        compare_profile_id=request.compare_profile_id,
        organization_id=current_user.organization_id,
    )

    if not diff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both profiles not found"
        )

    return diff


@router.get(
    "/profiles/{profile_id}",
    response_model=ProfileDetail,
)
async def get_profile(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get profile details.
    """
    service = ProfilingService(db)
    profile = await service.get_profile(
        profile_id=profile_id,
        organization_id=current_user.organization_id,
    )

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )

    return profile


@router.get(
    "/profiles/{profile_id}/flamegraph",
    response_model=FlamegraphData,
)
async def get_flamegraph(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get flamegraph data for a profile.

    Returns the profile data converted to a hierarchical format
    suitable for flamegraph visualization.
    """
    service = ProfilingService(db)
    flamegraph = await service.get_flamegraph_data(
        profile_id=profile_id,
        organization_id=current_user.organization_id,
    )

    if not flamegraph:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found or has no data"
        )

    return flamegraph


@router.delete(
    "/profiles/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_profile(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a profile.

    Only admins can delete profiles.
    """
    if current_user.role not in ["admin", "owner"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete profiles"
        )

    from app.models.profile import Profile

    query = select(Profile).where(
        Profile.id == profile_id,
        Profile.organization_id == current_user.organization_id,
    )
    result = await db.execute(query)
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )

    await db.delete(profile)
    await db.commit()


@router.post(
    "/profiles/cleanup",
    response_model=dict,
)
async def cleanup_old_profiles(
    retention_days: int = 7,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Clean up old profiles based on retention policy.

    Only admins can trigger cleanup.
    """
    if current_user.role not in ["admin", "owner"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can trigger cleanup"
        )

    service = ProfilingService(db)
    deleted_count = await service.cleanup_old_profiles(
        organization_id=current_user.organization_id,
        retention_days=retention_days,
    )

    return {
        "deleted_count": deleted_count,
        "retention_days": retention_days,
    }
