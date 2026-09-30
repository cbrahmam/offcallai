# backend/app/api/v1/endpoints/errors.py
"""API endpoints for Error Tracking."""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Optional
from uuid import UUID
import hashlib

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.organization import Organization
from app.schemas.error_tracking import (
    ErrorEventIngest,
    ErrorIngestResponse,
    ErrorGroupSummary,
    ErrorGroupDetail,
    ErrorGroupUpdate,
    ErrorEventSummary,
    ErrorEventDetail,
    ErrorStats,
    ErrorGroupFrequency,
    BulkUpdateRequest,
)
from app.services.error_tracking_service import ErrorTrackingService

router = APIRouter()


async def get_org_from_api_key(
    api_key: str,
    db: AsyncSession
) -> Optional[UUID]:
    """Get organization ID from API key (agent_api_keys table)."""
    # API keys are in format: oai_xxxxxxxxxxxxx
    # They are stored as SHA256 hashes in agent_api_keys table
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


# ============================================
# Public Ingestion Endpoints (API Key Auth)
# ============================================

@router.post(
    "/errors/ingest",
    response_model=ErrorIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_error(
    error: ErrorEventIngest,
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Ingest an error event from an SDK.

    Authentication: API Key (X-API-Key header) or Bearer token.

    This endpoint:
    1. Calculates fingerprint for error grouping
    2. Creates or updates error group
    3. Records error event with full context
    """
    organization_id = None

    # Try API key auth first
    if x_api_key:
        organization_id = await get_org_from_api_key(x_api_key, db)

    # Fall back to Bearer token
    if not organization_id and authorization:
        if authorization.startswith("Bearer "):
            token = authorization[7:]
            # Try as API key
            organization_id = await get_org_from_api_key(token, db)

    if not organization_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )

    # Get client IP if not provided
    if not error.user_ip:
        error.user_ip = request.client.host if request.client else None

    service = ErrorTrackingService(db)
    return await service.ingest_error(error, organization_id)


@router.post(
    "/errors/ingest/js",
    response_model=ErrorIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_error_js(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
):
    """
    Ingest error from JavaScript SDK format.

    Accepts the standard browser error format and normalizes it.
    """
    organization_id = None

    if x_api_key:
        organization_id = await get_org_from_api_key(x_api_key, db)

    if not organization_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )

    body = await request.json()

    # Convert JS SDK format to standard format
    error = ErrorEventIngest(
        error_type=body.get("name", body.get("type", "Error")),
        message=body.get("message", ""),
        stack_trace=body.get("stack", body.get("stacktrace")),
        stack_frames=[],  # Parse from stack if needed
        service_name=body.get("project", body.get("service")),
        environment=body.get("environment", "production"),
        release=body.get("release", body.get("version")),
        user_id=body.get("user", {}).get("id") if body.get("user") else None,
        user_email=body.get("user", {}).get("email") if body.get("user") else None,
        user_ip=request.client.host if request.client else None,
        request_url=body.get("url", body.get("request", {}).get("url")),
        request_method=body.get("request", {}).get("method"),
        runtime="browser",
        browser=body.get("browser", {}).get("name") if body.get("browser") else None,
        browser_version=body.get("browser", {}).get("version") if body.get("browser") else None,
        os=body.get("os", {}).get("name") if body.get("os") else None,
        os_version=body.get("os", {}).get("version") if body.get("os") else None,
        tags=body.get("tags", {}),
        extra=body.get("extra", body.get("context", {})),
        sdk_name="offcall-js",
        sdk_version=body.get("sdk", {}).get("version") if body.get("sdk") else None,
    )

    service = ErrorTrackingService(db)
    return await service.ingest_error(error, organization_id)


@router.post(
    "/errors/ingest/python",
    response_model=ErrorIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_error_python(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
):
    """
    Ingest error from Python SDK format.

    Accepts Python exception format and normalizes it.
    """
    organization_id = None

    if x_api_key:
        organization_id = await get_org_from_api_key(x_api_key, db)

    if not organization_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )

    body = await request.json()

    # Parse Python stack frames
    stack_frames = []
    exc_data = body.get("exception") or {}
    stacktrace = exc_data.get("stacktrace") or {}
    if stacktrace.get("frames"):
        for frame in stacktrace["frames"]:
            stack_frames.append({
                "filename": frame.get("filename"),
                "function": frame.get("function"),
                "lineno": frame.get("lineno"),
                "colno": frame.get("colno"),
                "abs_path": frame.get("abs_path"),
                "context_line": frame.get("context_line"),
                "pre_context": frame.get("pre_context"),
                "post_context": frame.get("post_context"),
                "in_app": frame.get("in_app", True),
                "module": frame.get("module"),
                "vars": frame.get("vars"),
            })

    exc = body.get("exception", {})
    error = ErrorEventIngest(
        error_type=exc.get("type", body.get("type", "Exception")),
        message=exc.get("value", body.get("message", "")),
        stack_trace=body.get("stacktrace"),
        stack_frames=stack_frames,
        service_name=body.get("project", body.get("service")),
        environment=body.get("environment", "production"),
        release=body.get("release"),
        user_id=body.get("user", {}).get("id") if body.get("user") else None,
        user_email=body.get("user", {}).get("email") if body.get("user") else None,
        user_ip=request.client.host if request.client else None,
        request_url=body.get("request", {}).get("url"),
        request_method=body.get("request", {}).get("method"),
        request_headers=body.get("request", {}).get("headers"),
        runtime="python",
        runtime_version=body.get("contexts", {}).get("runtime", {}).get("version"),
        os=body.get("contexts", {}).get("os", {}).get("name"),
        os_version=body.get("contexts", {}).get("os", {}).get("version"),
        trace_id=body.get("contexts", {}).get("trace", {}).get("trace_id"),
        span_id=body.get("contexts", {}).get("trace", {}).get("span_id"),
        tags=body.get("tags", {}),
        extra=body.get("extra", {}),
        sdk_name="offcall-python",
        sdk_version=body.get("sdk", {}).get("version") if body.get("sdk") else None,
    )

    service = ErrorTrackingService(db)
    return await service.ingest_error(error, organization_id)


# ============================================
# Authenticated Endpoints (JWT Auth)
# ============================================

@router.get(
    "/errors/groups",
    response_model=dict,
)
async def list_error_groups(
    status: Optional[str] = None,
    service_name: Optional[str] = None,
    environment: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "last_seen_at",
    sort_order: str = "desc",
    period: Optional[str] = None,
    include_sparkline: bool = False,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List error groups with filtering and pagination.

    Query params:
    - period: 1h | 24h | 7d | 14d | 30d — filter by last_seen_at
    - include_sparkline: true — include 14-day daily event counts per group
    """
    service = ErrorTrackingService(db)
    groups, total = await service.list_error_groups(
        organization_id=current_user.organization_id,
        status=status,
        service_name=service_name,
        environment=environment,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        period=period,
        include_sparkline=include_sparkline,
        limit=limit,
        offset=offset
    )

    return {
        "groups": groups,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get(
    "/errors/groups/{group_id}",
    response_model=ErrorGroupDetail,
)
async def get_error_group(
    group_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get error group details.
    """
    service = ErrorTrackingService(db)
    group = await service.get_error_group(group_id, current_user.organization_id)

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Error group not found"
        )

    return group


@router.patch(
    "/errors/groups/{group_id}",
    response_model=ErrorGroupDetail,
)
async def update_error_group(
    group_id: UUID,
    update: ErrorGroupUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update error group status or assignment.
    """
    service = ErrorTrackingService(db)
    group = await service.update_error_group(
        group_id=group_id,
        organization_id=current_user.organization_id,
        status=update.status.value if update.status else None,
        assigned_to_id=update.assigned_to_id
    )

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Error group not found"
        )

    return group


@router.delete(
    "/errors/groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_error_group(
    group_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete an error group and all its events.
    """
    if current_user.role not in ["admin", "owner"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete error groups"
        )

    service = ErrorTrackingService(db)
    deleted = await service.delete_error_group(group_id, current_user.organization_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Error group not found"
        )


@router.get(
    "/errors/groups/{group_id}/events",
    response_model=dict,
)
async def list_error_events(
    group_id: UUID,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List error events for a group.
    """
    service = ErrorTrackingService(db)
    events, total = await service.list_error_events(
        group_id=group_id,
        organization_id=current_user.organization_id,
        limit=limit,
        offset=offset
    )

    return {
        "events": events,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get(
    "/errors/events/{event_id}",
    response_model=ErrorEventDetail,
)
async def get_error_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get error event details.
    """
    service = ErrorTrackingService(db)
    event = await service.get_error_event(event_id, current_user.organization_id)

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Error event not found"
        )

    return event


@router.get(
    "/errors/stats",
    response_model=ErrorStats,
)
async def get_error_stats(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get error statistics for the organization.
    """
    service = ErrorTrackingService(db)
    return await service.get_error_stats(current_user.organization_id, days)


@router.post(
    "/errors/groups/{group_id}/resolve",
    response_model=ErrorGroupDetail,
)
async def resolve_error_group(
    group_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark an error group as resolved.
    """
    service = ErrorTrackingService(db)
    group = await service.update_error_group(
        group_id=group_id,
        organization_id=current_user.organization_id,
        status="resolved"
    )

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Error group not found"
        )

    return group


@router.post(
    "/errors/groups/{group_id}/ignore",
    response_model=ErrorGroupDetail,
)
async def ignore_error_group(
    group_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark an error group as ignored.
    """
    service = ErrorTrackingService(db)
    group = await service.update_error_group(
        group_id=group_id,
        organization_id=current_user.organization_id,
        status="ignored"
    )

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Error group not found"
        )

    return group


@router.post(
    "/errors/groups/{group_id}/reopen",
    response_model=ErrorGroupDetail,
)
async def reopen_error_group(
    group_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Reopen a resolved/ignored error group.
    """
    service = ErrorTrackingService(db)
    group = await service.update_error_group(
        group_id=group_id,
        organization_id=current_user.organization_id,
        status="unresolved"
    )

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Error group not found"
        )

    return group


@router.get(
    "/errors/groups/{group_id}/frequency",
    response_model=ErrorGroupFrequency,
)
async def get_group_frequency(
    group_id: UUID,
    period: str = "24h",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get bucketed event frequency for an error group.

    Period options: 1h, 24h, 7d, 14d, 30d
    Bucket size auto-selected: 5min, 1h, 6h, 1d, 1d
    """
    service = ErrorTrackingService(db)
    return await service.get_group_frequency(group_id, current_user.organization_id, period)


@router.get(
    "/errors/environments",
    response_model=List[str],
)
async def get_environments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get distinct environments across all error events.
    """
    service = ErrorTrackingService(db)
    return await service.get_environments(current_user.organization_id)


@router.post(
    "/errors/groups/bulk-update",
    response_model=dict,
)
async def bulk_update_groups(
    bulk_request: BulkUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Bulk update status of multiple error groups.
    """
    service = ErrorTrackingService(db)
    updated = await service.bulk_update_groups(
        organization_id=current_user.organization_id,
        group_ids=bulk_request.group_ids,
        status=bulk_request.status.value
    )
    return {"updated": updated}
