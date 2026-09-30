# backend/app/api/v1/endpoints/services.py
"""Service Catalog API endpoints - Premium Feature"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime

from app.database import get_async_session
from app.core.security import get_current_user
from app.models.user import User
from app.services.service_catalog_service import ServiceCatalogService

router = APIRouter(prefix="/services", tags=["services"])


# Schemas
class ServiceCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    tier: str = "tier3"
    owner_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    repository_url: Optional[str] = None
    documentation_url: Optional[str] = None
    dashboard_url: Optional[str] = None
    runbook_id: Optional[UUID] = None
    health_check_url: Optional[str] = None
    tags: List[str] = []
    environment: str = "production"
    service_type: Optional[str] = None
    extra_data: dict = {}


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tier: Optional[str] = None
    owner_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    repository_url: Optional[str] = None
    documentation_url: Optional[str] = None
    dashboard_url: Optional[str] = None
    runbook_id: Optional[UUID] = None
    health_check_url: Optional[str] = None
    tags: Optional[List[str]] = None
    environment: Optional[str] = None
    service_type: Optional[str] = None
    extra_data: Optional[dict] = None
    is_active: Optional[bool] = None


class ServiceResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: Optional[str]
    tier: str
    owner_id: Optional[UUID]
    owner_name: Optional[str]
    team_id: Optional[UUID]
    team_name: Optional[str]
    repository_url: Optional[str]
    documentation_url: Optional[str]
    dashboard_url: Optional[str]
    health_check_url: Optional[str]
    health_status: str
    tags: List[str]
    environment: str
    service_type: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DependencyCreate(BaseModel):
    downstream_service_id: UUID
    dependency_type: str = "requires"


# Endpoints
@router.get("/")
async def list_services(
    tier: Optional[str] = None,
    team_id: Optional[UUID] = None,
    environment: Optional[str] = None,
    service_type: Optional[str] = None,
    is_active: bool = True,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """List all services"""
    service = ServiceCatalogService(db)
    services, total = await service.list_services(
        organization_id=current_user.organization_id,
        tier=tier,
        team_id=team_id,
        environment=environment,
        service_type=service_type,
        is_active=is_active,
        skip=skip,
        limit=limit
    )

    return {
        "services": [
            {
                "id": str(s.id),
                "name": s.name,
                "slug": s.slug,
                "description": s.description,
                "tier": s.tier,
                "owner_id": str(s.owner_id) if s.owner_id else None,
                "owner_name": s.owner.full_name if s.owner else None,
                "team_id": str(s.team_id) if s.team_id else None,
                "team_name": s.team.name if s.team else None,
                "repository_url": s.repository_url,
                "documentation_url": s.documentation_url,
                "dashboard_url": s.dashboard_url,
                "health_check_url": s.health_check_url,
                "health_status": s.health_status,
                "tags": s.tags or [],
                "environment": s.environment,
                "service_type": s.service_type,
                "is_active": s.is_active,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None
            }
            for s in services
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.post("/")
async def create_service(
    data: ServiceCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new service"""
    service = ServiceCatalogService(db)
    try:
        new_service = await service.create_service(
            organization_id=current_user.organization_id,
            **data.model_dump()
        )
        return {"id": str(new_service.id), "message": "Service created"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/graph")
async def get_dependency_graph(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get the full service dependency graph"""
    service = ServiceCatalogService(db)
    return await service.get_dependency_graph(current_user.organization_id)


@router.get("/{service_id}")
async def get_service(
    service_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get a service by ID"""
    service = ServiceCatalogService(db)
    svc = await service.get_service(service_id, current_user.organization_id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")

    return {
        "id": str(svc.id),
        "name": svc.name,
        "slug": svc.slug,
        "description": svc.description,
        "tier": svc.tier,
        "owner_id": str(svc.owner_id) if svc.owner_id else None,
        "owner_name": svc.owner.full_name if svc.owner else None,
        "team_id": str(svc.team_id) if svc.team_id else None,
        "team_name": svc.team.name if svc.team else None,
        "repository_url": svc.repository_url,
        "documentation_url": svc.documentation_url,
        "dashboard_url": svc.dashboard_url,
        "runbook_id": str(svc.runbook_id) if svc.runbook_id else None,
        "health_check_url": svc.health_check_url,
        "health_status": svc.health_status,
        "last_health_check": svc.last_health_check.isoformat() if svc.last_health_check else None,
        "tags": svc.tags or [],
        "environment": svc.environment,
        "service_type": svc.service_type,
        "extra_data": svc.extra_data or {},
        "is_active": svc.is_active,
        "created_at": svc.created_at.isoformat() if svc.created_at else None,
        "updated_at": svc.updated_at.isoformat() if svc.updated_at else None
    }


@router.patch("/{service_id}")
async def update_service(
    service_id: UUID,
    data: ServiceUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update a service"""
    service = ServiceCatalogService(db)
    updated = await service.update_service(
        service_id, current_user.organization_id,
        **data.model_dump(exclude_unset=True)
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Service not found")
    return {"message": "Service updated"}


@router.delete("/{service_id}")
async def delete_service(
    service_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Delete a service"""
    service = ServiceCatalogService(db)
    deleted = await service.delete_service(service_id, current_user.organization_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Service not found")
    return {"message": "Service deleted"}


# Dependencies
@router.get("/{service_id}/dependencies")
async def get_dependencies(
    service_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get services that this service depends on"""
    service = ServiceCatalogService(db)
    deps = await service.get_dependencies(service_id, current_user.organization_id)
    return {
        "dependencies": [
            {"id": str(d.id), "name": d.name, "slug": d.slug, "tier": d.tier}
            for d in deps
        ]
    }


@router.get("/{service_id}/dependents")
async def get_dependents(
    service_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get services that depend on this service"""
    service = ServiceCatalogService(db)
    deps = await service.get_dependents(service_id, current_user.organization_id)
    return {
        "dependents": [
            {"id": str(d.id), "name": d.name, "slug": d.slug, "tier": d.tier}
            for d in deps
        ]
    }


@router.post("/{service_id}/dependencies")
async def add_dependency(
    service_id: UUID,
    data: DependencyCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Add a dependency to this service"""
    service = ServiceCatalogService(db)
    try:
        await service.add_dependency(
            upstream_id=service_id,
            downstream_id=data.downstream_service_id,
            organization_id=current_user.organization_id,
            dependency_type=data.dependency_type
        )
        return {"message": "Dependency added"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{service_id}/dependencies/{downstream_id}")
async def remove_dependency(
    service_id: UUID,
    downstream_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Remove a dependency"""
    service = ServiceCatalogService(db)
    await service.remove_dependency(service_id, downstream_id, current_user.organization_id)
    return {"message": "Dependency removed"}
