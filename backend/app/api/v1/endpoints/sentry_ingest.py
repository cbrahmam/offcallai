# backend/app/api/v1/endpoints/sentry_ingest.py
"""
Sentry SDK Compatibility Endpoint.

This endpoint allows users to use the official Sentry SDK (@sentry/browser, sentry-python, etc.)
with OffCall AI by simply changing the DSN URL.

DSN Format: https://<api_key>@<your-offcall-host>/api/sentry/<org_id>

Example:
    // Before (Sentry)
    Sentry.init({ dsn: "https://xxx@sentry.io/123" });

    // After (OffCall AI - just change DSN!)
    Sentry.init({ dsn: "https://ofc_xxx@<your-offcall-host>/api/sentry/your-org-id" });
"""
import hashlib
import logging
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.database import get_db
from app.schemas.error_tracking import ErrorIngestResponse
from app.services.sentry_service import SentryService
from app.services.error_tracking_service import ErrorTrackingService

router = APIRouter()
logger = logging.getLogger(__name__)


async def get_org_from_api_key(
    api_key: str,
    db: AsyncSession
) -> Optional[UUID]:
    """Get organization ID from API key (agent_api_keys table)."""
    # API keys are stored as SHA256 hashes
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


@router.post(
    "/sentry/{project_id}/envelope/",
    status_code=status.HTTP_200_OK,
)
async def ingest_sentry_envelope(
    project_id: str,
    request: Request,
    x_sentry_auth: Optional[str] = Header(None, alias="X-Sentry-Auth"),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Ingest errors from Sentry SDK envelope format.

    This endpoint accepts the standard Sentry envelope protocol,
    allowing drop-in replacement of Sentry with OffCall AI.

    Authentication methods:
    1. DSN in envelope header
    2. X-Sentry-Auth header: Sentry sentry_key=<api_key>, ...
    3. Authorization header: Bearer <api_key>

    The project_id from the URL is used for routing but authentication
    is done via the API key.
    """
    organization_id = None
    api_key = None

    # Read raw body (Sentry envelopes are newline-delimited)
    body = await request.body()

    if not body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty request body"
        )

    # Try to parse envelope to get DSN
    sentry_service = SentryService()
    parsed_envelope = sentry_service.parse_envelope(body)

    # Method 1: Extract API key from DSN in envelope header
    if parsed_envelope.header.dsn:
        api_key = sentry_service.extract_api_key_from_dsn(parsed_envelope.header.dsn)

    # Method 2: X-Sentry-Auth header
    # Format: Sentry sentry_key=xxx, sentry_version=7, ...
    if not api_key and x_sentry_auth:
        try:
            # Parse "Sentry sentry_key=xxx, sentry_version=7, ..."
            parts = x_sentry_auth.split(',')
            for part in parts:
                part = part.strip()
                if part.startswith('Sentry '):
                    part = part[7:]  # Remove "Sentry " prefix
                if '=' in part:
                    key, value = part.split('=', 1)
                    if key.strip() == 'sentry_key':
                        api_key = value.strip()
                        break
        except Exception as e:
            logger.warning(f"Failed to parse X-Sentry-Auth: {e}")

    # Method 3: Authorization header
    if not api_key and authorization:
        if authorization.startswith("Bearer "):
            api_key = authorization[7:]
        elif authorization.startswith("DSN "):
            dsn = authorization[4:]
            api_key = sentry_service.extract_api_key_from_dsn(dsn)

    # Validate API key
    if api_key:
        organization_id = await get_org_from_api_key(api_key, db)

    if not organization_id:
        # Log for debugging but don't expose details
        logger.warning(f"Sentry ingest: invalid API key for project {project_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )

    # Process all events in the envelope
    error_service = ErrorTrackingService(db)
    results: List[dict] = []

    for sentry_event in parsed_envelope.events:
        try:
            # Transform Sentry event to OffCall format
            offcall_event = sentry_service.transform_event(
                sentry_event,
                service_name=project_id if project_id != "0" else None
            )

            # Get client IP if not provided
            if not offcall_event.user_ip and request.client:
                offcall_event.user_ip = request.client.host

            # Ingest the error
            response = await error_service.ingest_error(offcall_event, organization_id)
            results.append({
                "event_id": str(response.event_id),
                "group_id": str(response.group_id),
                "status": "ok"
            })

        except Exception as e:
            logger.error(f"Failed to process Sentry event: {e}")
            results.append({
                "event_id": sentry_event.event_id or "unknown",
                "status": "error",
                "error": str(e)
            })

    # Log session data (we don't fully support sessions yet, but acknowledge them)
    if parsed_envelope.sessions:
        logger.info(f"Received {len(parsed_envelope.sessions)} session(s) from Sentry SDK")

    # Return Sentry-compatible response
    # Sentry expects an empty 200 response for successful ingestion
    return {"id": parsed_envelope.header.event_id, "results": results}


@router.post(
    "/sentry/{project_id}/store/",
    status_code=status.HTTP_200_OK,
)
async def ingest_sentry_store(
    project_id: str,
    request: Request,
    x_sentry_auth: Optional[str] = Header(None, alias="X-Sentry-Auth"),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Legacy Sentry store endpoint (for older SDK versions).

    This accepts single JSON events rather than the envelope format.
    """
    organization_id = None
    api_key = None

    # Parse X-Sentry-Auth header
    if x_sentry_auth:
        try:
            parts = x_sentry_auth.split(',')
            for part in parts:
                part = part.strip()
                if part.startswith('Sentry '):
                    part = part[7:]
                if '=' in part:
                    key, value = part.split('=', 1)
                    if key.strip() == 'sentry_key':
                        api_key = value.strip()
                        break
        except Exception as e:
            logger.warning(f"Failed to parse X-Sentry-Auth: {e}")

    # Try Authorization header
    if not api_key and authorization:
        if authorization.startswith("Bearer "):
            api_key = authorization[7:]

    # Validate API key
    if api_key:
        organization_id = await get_org_from_api_key(api_key, db)

    if not organization_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )

    # Parse JSON body
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON body: {e}"
        )

    # Transform and ingest
    sentry_service = SentryService()
    from app.schemas.sentry import SentryEvent

    try:
        sentry_event = SentryEvent(**body)
        offcall_event = sentry_service.transform_event(
            sentry_event,
            service_name=project_id if project_id != "0" else None
        )

        if not offcall_event.user_ip and request.client:
            offcall_event.user_ip = request.client.host

        error_service = ErrorTrackingService(db)
        response = await error_service.ingest_error(offcall_event, organization_id)

        return {
            "id": str(response.event_id),
            "group_id": str(response.group_id)
        }

    except Exception as e:
        logger.error(f"Failed to process Sentry store event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process event: {e}"
        )


@router.options(
    "/sentry/{project_id}/envelope/",
    status_code=status.HTTP_200_OK,
)
async def sentry_envelope_options(project_id: str):
    """Handle CORS preflight for Sentry envelope endpoint."""
    return {}


@router.options(
    "/sentry/{project_id}/store/",
    status_code=status.HTTP_200_OK,
)
async def sentry_store_options(project_id: str):
    """Handle CORS preflight for Sentry store endpoint."""
    return {}


# Health check endpoint for Sentry SDK
@router.get(
    "/sentry/health/",
    status_code=status.HTTP_200_OK,
)
async def sentry_health():
    """Health check for Sentry compatibility layer."""
    return {"status": "ok", "service": "offcall-sentry-compat"}
