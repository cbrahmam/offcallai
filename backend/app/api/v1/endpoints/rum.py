# backend/app/api/v1/endpoints/rum.py
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID
from datetime import datetime

from app.database import get_db
from app.core.security import get_current_user
from app.core.deps import get_current_organization
from app.models.user import User
from app.models.organization import Organization
from app.services.rum_service import RUMService
from app.schemas.rum import (
    RUMApplicationCreate,
    RUMApplicationUpdate,
    RUMApplicationResponse,
    RUMApplicationList,
    RUMSessionCreate,
    RUMSessionResponse,
    RUMSessionList,
    RUMPageViewCreate,
    RUMPageViewResponse,
    RUMPageViewList,
    RUMErrorCreate,
    RUMErrorResponse,
    RUMErrorList,
    RUMErrorGroup,
    RUMUserActionCreate,
    RUMUserActionResponse,
    RUMAlertResponse,
    RUMAlertList,
    RUMStats,
    RUMApplicationOverview,
    RUMEventBatch,
    RUMBeaconData,
)

router = APIRouter()


# ==================== Applications ====================

@router.get("/applications", response_model=RUMApplicationList)
async def list_applications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """List all RUM applications"""
    service = RUMService(db)
    return await service.list_applications(organization.id)


@router.post("/applications", response_model=RUMApplicationResponse)
async def create_application(
    app_data: RUMApplicationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Create a new RUM application"""
    service = RUMService(db)
    return await service.create_application(organization.id, app_data)


@router.get("/applications/{app_id}", response_model=RUMApplicationResponse)
async def get_application(
    app_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get a specific RUM application"""
    service = RUMService(db)
    application = await service.get_application(app_id, organization.id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@router.put("/applications/{app_id}", response_model=RUMApplicationResponse)
async def update_application(
    app_id: UUID,
    app_update: RUMApplicationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Update a RUM application"""
    service = RUMService(db)
    application = await service.update_application(app_id, organization.id, app_update)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@router.delete("/applications/{app_id}")
async def delete_application(
    app_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Delete a RUM application"""
    service = RUMService(db)
    success = await service.delete_application(app_id, organization.id)
    if not success:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"status": "deleted"}


@router.post("/applications/{app_id}/regenerate-key")
async def regenerate_api_key(
    app_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Regenerate API key for an application"""
    service = RUMService(db)
    new_key = await service.regenerate_api_key(app_id, organization.id)
    if not new_key:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"api_key": new_key}


@router.get("/applications/{app_id}/overview", response_model=RUMApplicationOverview)
async def get_application_overview(
    app_id: UUID,
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get application overview with stats"""
    service = RUMService(db)
    application = await service.get_application(app_id, organization.id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    stats = await service.get_stats(organization.id, app_id, hours)
    errors = await service.list_errors(organization.id, application_id=app_id, page_size=5)
    alerts = await service.list_alerts(organization.id, application_id=app_id, status="active", page_size=5)

    return RUMApplicationOverview(
        application=application,
        stats=stats,
        recent_errors=errors["items"],
        recent_alerts=alerts["items"]
    )


@router.get("/applications/{app_id}/stats", response_model=RUMStats)
async def get_application_stats(
    app_id: UUID,
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get statistics for an application"""
    service = RUMService(db)
    return await service.get_stats(organization.id, app_id, hours)


# ==================== Sessions ====================

@router.get("/applications/{app_id}/sessions", response_model=RUMSessionList)
async def list_sessions(
    app_id: UUID,
    user_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """List sessions for an application"""
    service = RUMService(db)
    return await service.list_sessions(
        organization_id=organization.id,
        application_id=app_id,
        user_id=user_id,
        start_time=start_time,
        end_time=end_time,
        page=page,
        page_size=page_size
    )


@router.get("/sessions/{session_id}", response_model=RUMSessionResponse)
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get a specific session"""
    service = RUMService(db)
    session = await service.get_session(session_id, organization.id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# ==================== Page Views ====================

@router.get("/applications/{app_id}/pageviews", response_model=RUMPageViewList)
async def list_page_views(
    app_id: UUID,
    session_id: Optional[UUID] = None,
    url_path: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """List page views for an application"""
    service = RUMService(db)
    return await service.list_page_views(
        organization_id=organization.id,
        application_id=app_id,
        session_id=session_id,
        url_path=url_path,
        start_time=start_time,
        end_time=end_time,
        page=page,
        page_size=page_size
    )


# ==================== Errors ====================

@router.get("/applications/{app_id}/errors", response_model=RUMErrorList)
async def list_errors(
    app_id: UUID,
    error_type: Optional[str] = None,
    fingerprint: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """List errors for an application"""
    service = RUMService(db)
    return await service.list_errors(
        organization_id=organization.id,
        application_id=app_id,
        error_type=error_type,
        fingerprint=fingerprint,
        start_time=start_time,
        end_time=end_time,
        page=page,
        page_size=page_size
    )


@router.get("/applications/{app_id}/errors/groups", response_model=list)
async def get_error_groups(
    app_id: UUID,
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get grouped errors by fingerprint"""
    service = RUMService(db)
    return await service.get_error_groups(organization.id, app_id, hours)


# ==================== Alerts ====================

@router.get("/applications/{app_id}/alerts", response_model=RUMAlertList)
async def list_alerts(
    app_id: UUID,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """List alerts for an application"""
    service = RUMService(db)
    return await service.list_alerts(
        organization_id=organization.id,
        application_id=app_id,
        status=status,
        page=page,
        page_size=page_size
    )


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Acknowledge an alert"""
    service = RUMService(db)
    alert = await service.acknowledge_alert(alert_id, organization.id, current_user.id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Resolve an alert"""
    service = RUMService(db)
    alert = await service.resolve_alert(alert_id, organization.id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


# ==================== Data Ingestion (SDK Endpoints) ====================

@router.post("/ingest/session")
async def ingest_session(
    session_data: RUMSessionCreate,
    request: Request,
    api_key: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Ingest session data from SDK (no auth required, uses API key)"""
    service = RUMService(db)
    application = await service.get_application_by_api_key(api_key)
    if not application:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not application.enabled:
        return {"status": "disabled"}

    # Get geo info from request (simplified)
    client_ip = request.client.host if request.client else None

    session = await service.create_or_update_session(
        organization_id=application.organization_id,
        application_id=application.id,
        session_data=session_data
    )

    # Update IP if available
    if client_ip and not session.ip_address:
        session.ip_address = client_ip

    return {"session_id": str(session.id), "status": "created"}


@router.post("/ingest/pageview")
async def ingest_page_view(
    pageview_data: RUMPageViewCreate,
    api_key: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Ingest page view data from SDK"""
    service = RUMService(db)
    application = await service.get_application_by_api_key(api_key)
    if not application:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not application.enabled or not application.track_performance:
        return {"status": "disabled"}

    try:
        pageview = await service.create_page_view(
            organization_id=application.organization_id,
            application_id=application.id,
            page_view_data=pageview_data
        )
        return {"pageview_id": str(pageview.id), "status": "created"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ingest/error")
async def ingest_error(
    error_data: RUMErrorCreate,
    api_key: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Ingest error data from SDK"""
    service = RUMService(db)
    application = await service.get_application_by_api_key(api_key)
    if not application:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not application.enabled or not application.track_errors:
        return {"status": "disabled"}

    error = await service.create_error(
        organization_id=application.organization_id,
        application_id=application.id,
        error_data=error_data
    )
    return {"error_id": str(error.id), "status": "created"}


@router.post("/ingest/action")
async def ingest_user_action(
    action_data: RUMUserActionCreate,
    api_key: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Ingest user action data from SDK"""
    service = RUMService(db)
    application = await service.get_application_by_api_key(api_key)
    if not application:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not application.enabled or not application.track_user_actions:
        return {"status": "disabled"}

    try:
        action = await service.create_user_action(
            organization_id=application.organization_id,
            application_id=application.id,
            action_data=action_data
        )
        return {"action_id": str(action.id), "status": "created"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ingest/batch")
async def ingest_batch(
    batch: RUMEventBatch,
    db: AsyncSession = Depends(get_db),
):
    """Ingest batch of events from SDK"""
    import logging
    logger = logging.getLogger(__name__)

    service = RUMService(db)
    application = await service.get_application_by_api_key(batch.api_key)
    if not application:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not application.enabled:
        return {"status": "disabled"}

    # Auto-create session if it doesn't exist (SDK doesn't call /ingest/session)
    session = await service.get_session_by_client_id(
        batch.session_id,
        application.organization_id,
        application.id
    )
    if not session:
        session_data = RUMSessionCreate(
            session_id=batch.session_id,
            session_start=datetime.utcnow(),
        )
        session = await service.create_or_update_session(
            organization_id=application.organization_id,
            application_id=application.id,
            session_data=session_data,
        )
        logger.info(f"RUM: Auto-created session {batch.session_id} for app {application.name}")

    processed = 0
    errors = []

    for event in batch.events:
        event_type = event.get("type")
        try:
            if event_type == "pageview" and application.track_performance:
                pv_data = RUMPageViewCreate(session_id=batch.session_id, **event.get("data", {}))
                await service.create_page_view(application.organization_id, application.id, pv_data)
                processed += 1
            elif event_type == "error" and application.track_errors:
                err_data = RUMErrorCreate(session_id=batch.session_id, **event.get("data", {}))
                await service.create_error(application.organization_id, application.id, err_data)
                processed += 1
            elif event_type == "action" and application.track_user_actions:
                act_data = RUMUserActionCreate(session_id=batch.session_id, **event.get("data", {}))
                await service.create_user_action(application.organization_id, application.id, act_data)
                processed += 1
        except Exception as e:
            logger.warning(f"RUM batch event error ({event_type}): {e}")
            errors.append({"type": event_type, "error": str(e)})

    logger.info(f"RUM batch: processed={processed}, errors={len(errors)} for app={application.name}")
    return {"processed": processed, "errors": errors}


@router.post("/ingest/beacon")
async def ingest_beacon(
    beacon: RUMBeaconData,
    db: AsyncSession = Depends(get_db),
):
    """Ingest beacon data sent on page unload"""
    service = RUMService(db)
    application = await service.get_application_by_api_key(beacon.api_key)
    if not application:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Update session with final data
    session = await service.get_session_by_client_id(
        beacon.session_id,
        application.organization_id,
        application.id
    )

    if session:
        session.session_end = datetime.utcnow()
        if session.session_start:
            session.duration_ms = int((session.session_end - session.session_start).total_seconds() * 1000)
        await db.commit()

    return {"status": "received"}
