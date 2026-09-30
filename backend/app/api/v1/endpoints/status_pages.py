# backend/app/api/v1/endpoints/status_pages.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID

from app.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.status_page import ServiceStatus
from app.services.status_page_service import StatusPageService
from app.schemas.status_page import (
    StatusPageCreate, StatusPageUpdate, StatusPageResponse,
    StatusPageServiceCreate, StatusPageServiceUpdate, StatusPageServiceResponse,
    PublicStatusPageResponse, SubscriberCreate, SubscriberResponse, SubscriberListResponse
)

router = APIRouter()


# Admin endpoints (require auth)
@router.post("/", response_model=StatusPageResponse, status_code=status.HTTP_201_CREATED)
async def create_status_page(
    data: StatusPageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a status page for the organization"""
    service = StatusPageService(db)
    try:
        status_page = await service.create_status_page(
            organization_id=current_user.organization_id,
            data=data
        )
        return service.to_response(status_page)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=StatusPageResponse)
async def get_status_page(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the organization's status page"""
    import logging
    import traceback
    logger = logging.getLogger(__name__)

    try:
        service = StatusPageService(db)
        status_page = await service.get_status_page(current_user.organization_id)

        if not status_page:
            raise HTTPException(status_code=404, detail="Status page not found")

        return service.to_response(status_page)
    except HTTPException:
        raise
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error getting status page: {e}\n{error_details}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve status page: {str(e)}")


@router.patch("/", response_model=StatusPageResponse)
async def update_status_page(
    data: StatusPageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update status page settings"""
    service = StatusPageService(db)
    try:
        status_page = await service.update_status_page(
            organization_id=current_user.organization_id,
            data=data
        )
        if not status_page:
            raise HTTPException(status_code=404, detail="Status page not found")
        return service.to_response(status_page)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_status_page(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete the organization's status page"""
    service = StatusPageService(db)
    deleted = await service.delete_status_page(current_user.organization_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Status page not found")


# Service endpoints
@router.post("/services", response_model=StatusPageServiceResponse, status_code=status.HTTP_201_CREATED)
async def add_service(
    data: StatusPageServiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a service to the status page"""
    service = StatusPageService(db)
    svc = await service.add_service(
        organization_id=current_user.organization_id,
        data=data
    )

    if not svc:
        raise HTTPException(status_code=404, detail="Status page not found")

    return StatusPageServiceResponse(
        id=svc.id,
        status_page_id=svc.status_page_id,
        name=svc.name,
        description=svc.description,
        status=svc.status,
        display_order=svc.display_order,
        is_visible=svc.is_visible,
        group_name=svc.group_name,
        health_check_url=svc.health_check_url,
        health_check_interval_minutes=svc.health_check_interval_minutes,
        last_health_check=svc.last_health_check,
        last_health_check_status=svc.last_health_check_status,
        created_at=svc.created_at,
        updated_at=svc.updated_at
    )


@router.patch("/services/{service_id}", response_model=StatusPageServiceResponse)
async def update_service(
    service_id: UUID,
    data: StatusPageServiceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a service"""
    service = StatusPageService(db)
    svc = await service.update_service(
        service_id=service_id,
        organization_id=current_user.organization_id,
        data=data
    )

    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")

    return StatusPageServiceResponse(
        id=svc.id,
        status_page_id=svc.status_page_id,
        name=svc.name,
        description=svc.description,
        status=svc.status,
        display_order=svc.display_order,
        is_visible=svc.is_visible,
        group_name=svc.group_name,
        health_check_url=svc.health_check_url,
        health_check_interval_minutes=svc.health_check_interval_minutes,
        last_health_check=svc.last_health_check,
        last_health_check_status=svc.last_health_check_status,
        created_at=svc.created_at,
        updated_at=svc.updated_at
    )


@router.patch("/services/{service_id}/status")
async def update_service_status(
    service_id: UUID,
    status: ServiceStatus = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Quick update just the status of a service"""
    service = StatusPageService(db)
    svc = await service.update_service_status(
        service_id=service_id,
        organization_id=current_user.organization_id,
        status=status
    )

    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")

    return {"message": "Status updated", "status": svc.status.value}


@router.delete("/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    service_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a service"""
    service = StatusPageService(db)
    deleted = await service.delete_service(
        service_id=service_id,
        organization_id=current_user.organization_id
    )

    if not deleted:
        raise HTTPException(status_code=404, detail="Service not found")


# Subscriber management (admin)
@router.get("/subscribers", response_model=SubscriberListResponse)
async def get_subscribers(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get subscribers for the status page"""
    service = StatusPageService(db)
    subscribers, total = await service.get_subscribers(
        organization_id=current_user.organization_id,
        page=page,
        per_page=per_page
    )

    return SubscriberListResponse(
        subscribers=[
            SubscriberResponse(
                id=s.id,
                email=s.email,
                is_verified=s.is_verified,
                notify_on_incidents=s.notify_on_incidents,
                notify_on_maintenance=s.notify_on_maintenance,
                notify_on_resolved=s.notify_on_resolved,
                subscribed_at=s.subscribed_at
            )
            for s in subscribers
        ],
        total=total
    )


# Admin tasks
@router.post("/admin/calculate-uptime")
async def trigger_uptime_calculation(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Manually trigger uptime calculation for all services (admin only)"""
    from datetime import datetime, timedelta

    service = StatusPageService(db)
    # Calculate for yesterday
    yesterday = datetime.utcnow() - timedelta(days=1)
    count = await service.calculate_uptime_for_all_services(yesterday)

    return {
        "message": "Uptime calculation completed",
        "services_processed": count,
        "date": yesterday.date().isoformat()
    }


@router.post("/services/{service_id}/backfill-uptime")
async def backfill_service_uptime(
    service_id: UUID,
    days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Backfill uptime records for a service (admin only)"""
    service = StatusPageService(db)

    # Verify service belongs to user's org
    svc = await service.get_service(service_id, current_user.organization_id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")

    count = await service.backfill_uptime_records(service_id, days)

    return {
        "message": "Backfill completed",
        "records_created": count,
        "days": days
    }


# Public endpoints (no auth required)
@router.get("/public/{slug}", response_model=PublicStatusPageResponse)
async def get_public_status_page(
    slug: str,
    db: AsyncSession = Depends(get_db)
):
    """Get public status page data (no auth required)"""
    service = StatusPageService(db)
    public_data = await service.get_public_status(slug)

    if not public_data:
        raise HTTPException(status_code=404, detail="Status page not found")

    return public_data


@router.post("/public/{slug}/subscribe", response_model=SubscriberResponse, status_code=status.HTTP_201_CREATED)
async def subscribe_to_status_page(
    slug: str,
    data: SubscriberCreate,
    db: AsyncSession = Depends(get_db)
):
    """Subscribe to status updates (no auth required)"""
    service = StatusPageService(db)
    try:
        subscriber = await service.subscribe(slug, data)
        if not subscriber:
            raise HTTPException(status_code=404, detail="Status page not found or subscriptions disabled")

        return SubscriberResponse(
            id=subscriber.id,
            email=subscriber.email,
            is_verified=subscriber.is_verified,
            notify_on_incidents=subscriber.notify_on_incidents,
            notify_on_maintenance=subscriber.notify_on_maintenance,
            notify_on_resolved=subscriber.notify_on_resolved,
            subscribed_at=subscriber.subscribed_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/public/verify/{token}")
async def verify_subscription(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """Verify email subscription"""
    service = StatusPageService(db)
    verified = await service.verify_subscriber(token)

    if not verified:
        raise HTTPException(status_code=404, detail="Invalid or expired token")

    return {"message": "Email verified successfully"}


@router.post("/public/{slug}/unsubscribe")
async def unsubscribe_from_status_page(
    slug: str,
    email: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Unsubscribe from status updates"""
    service = StatusPageService(db)
    unsubscribed = await service.unsubscribe(email, slug)

    if not unsubscribed:
        raise HTTPException(status_code=404, detail="Subscription not found")

    return {"message": "Unsubscribed successfully"}
