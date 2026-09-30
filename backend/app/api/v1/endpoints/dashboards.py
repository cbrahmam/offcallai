# backend/app/api/v1/endpoints/dashboards.py
"""
Custom Dashboards API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from app.database import get_db
from app.services.dashboard_service import dashboard_service
from app.schemas.dashboard import (
    DashboardCreate, DashboardUpdate, DashboardResponse, DashboardListResponse,
    WidgetCreate, WidgetUpdate, WidgetResponse, WidgetDataResponse,
    DashboardTemplateListResponse, DashboardExport
)
from app.api.deps import get_current_user, get_current_organization
from app.models.user import User
from app.models.organization import Organization

router = APIRouter()


# ============================================
# Dashboard CRUD
# ============================================

@router.post("/", response_model=DashboardResponse)
async def create_dashboard(
    data: DashboardCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Create a new custom dashboard."""
    result = await dashboard_service.create_dashboard(
        data=data,
        organization_id=organization.id,
        user_id=current_user.id,
        db=db
    )
    return result


@router.get("/", response_model=DashboardListResponse)
async def list_dashboards(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """List all dashboards for the organization."""
    result = await dashboard_service.list_dashboards(
        organization_id=organization.id,
        db=db,
        limit=limit,
        offset=offset
    )
    return result


@router.get("/{dashboard_id}", response_model=DashboardResponse)
async def get_dashboard(
    dashboard_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get a dashboard by ID."""
    result = await dashboard_service.get_dashboard(
        dashboard_id=dashboard_id,
        organization_id=organization.id,
        db=db
    )
    if not result:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return result


@router.get("/slug/{slug}", response_model=DashboardResponse)
async def get_dashboard_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get a dashboard by slug."""
    result = await dashboard_service.get_dashboard_by_slug(
        slug=slug,
        organization_id=organization.id,
        db=db
    )
    if not result:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return result


@router.patch("/{dashboard_id}", response_model=DashboardResponse)
async def update_dashboard(
    dashboard_id: UUID,
    data: DashboardUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Update a dashboard."""
    result = await dashboard_service.update_dashboard(
        dashboard_id=dashboard_id,
        data=data,
        organization_id=organization.id,
        db=db
    )
    if not result:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return result


@router.delete("/{dashboard_id}")
async def delete_dashboard(
    dashboard_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Delete a dashboard."""
    success = await dashboard_service.delete_dashboard(
        dashboard_id=dashboard_id,
        organization_id=organization.id,
        db=db
    )
    if not success:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return {"message": "Dashboard deleted successfully"}


# ============================================
# Widget CRUD
# ============================================

@router.post("/{dashboard_id}/widgets", response_model=WidgetResponse)
async def add_widget(
    dashboard_id: UUID,
    data: WidgetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Add a widget to a dashboard."""
    result = await dashboard_service.add_widget(
        dashboard_id=dashboard_id,
        data=data,
        organization_id=organization.id,
        db=db
    )
    if not result:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return result


@router.patch("/widgets/{widget_id}", response_model=WidgetResponse)
async def update_widget(
    widget_id: UUID,
    data: WidgetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Update a widget."""
    result = await dashboard_service.update_widget(
        widget_id=widget_id,
        data=data,
        organization_id=organization.id,
        db=db
    )
    if not result:
        raise HTTPException(status_code=404, detail="Widget not found")
    return result


@router.delete("/widgets/{widget_id}")
async def delete_widget(
    widget_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Delete a widget."""
    success = await dashboard_service.delete_widget(
        widget_id=widget_id,
        organization_id=organization.id,
        db=db
    )
    if not success:
        raise HTTPException(status_code=404, detail="Widget not found")
    return {"message": "Widget deleted successfully"}


@router.post("/{dashboard_id}/widgets/positions")
async def update_widget_positions(
    dashboard_id: UUID,
    positions: List[dict],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Update positions for multiple widgets."""
    success = await dashboard_service.update_widget_positions(
        dashboard_id=dashboard_id,
        positions=positions,
        organization_id=organization.id,
        db=db
    )
    if not success:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return {"message": "Widget positions updated"}


# ============================================
# Widget Data
# ============================================

@router.get("/widgets/{widget_id}/data", response_model=WidgetDataResponse)
async def get_widget_data(
    widget_id: UUID,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get data for a widget."""
    result = await dashboard_service.get_widget_data(
        widget_id=widget_id,
        organization_id=organization.id,
        db=db,
        start_time=start_time,
        end_time=end_time
    )
    if not result:
        raise HTTPException(status_code=404, detail="Widget not found")
    return result


# ============================================
# Templates
# ============================================

@router.get("/templates/list", response_model=DashboardTemplateListResponse)
async def list_templates(
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """List available dashboard templates."""
    result = await dashboard_service.list_templates(
        organization_id=organization.id,
        db=db,
        category=category
    )
    return result


@router.post("/templates/{template_id}/create", response_model=DashboardResponse)
async def create_from_template(
    template_id: UUID,
    name: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Create a dashboard from a template."""
    result = await dashboard_service.create_from_template(
        template_id=template_id,
        name=name,
        organization_id=organization.id,
        user_id=current_user.id,
        db=db
    )
    if not result:
        raise HTTPException(status_code=404, detail="Template not found")
    return result


# ============================================
# Export/Import
# ============================================

@router.get("/{dashboard_id}/export", response_model=DashboardExport)
async def export_dashboard(
    dashboard_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Export a dashboard to JSON format."""
    result = await dashboard_service.export_dashboard(
        dashboard_id=dashboard_id,
        organization_id=organization.id,
        db=db
    )
    if not result:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return result
