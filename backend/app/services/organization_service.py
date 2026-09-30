# backend/app/services/organization_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter
from app.models.organization import Organization
from app.models.user import User
from app.models.incident import Incident, IncidentStatus
from app.models.alert import Alert
from app.schemas.organization import (
    OrganizationCreate, OrganizationUpdate, OrganizationResponse, OrganizationStatsResponse
)
import logging
router = APIRouter()
logger = logging.getLogger(__name__)

class OrganizationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_organization_by_id(self, organization_id: str) -> Optional[Organization]:
        """Get organization by ID"""
        result = await self.db.execute(
            select(Organization).where(Organization.id == organization_id)
        )
        return result.scalar_one_or_none()

    async def get_organization_by_slug(self, slug: str) -> Optional[Organization]:
        """Get organization by slug"""
        result = await self.db.execute(
            select(Organization).where(Organization.slug == slug)
        )
        return result.scalar_one_or_none()

    async def create_organization(self, org_data: OrganizationCreate) -> Organization:
        """Create a new organization"""
        organization = Organization(
            name=org_data.name,
            slug=org_data.slug,
            plan="free",
            is_active=True,
            max_users=5,  # Free plan default
            max_incidents_per_month=100,  # Free plan default
            created_at=datetime.utcnow()
        )
        
        self.db.add(organization)
        await self.db.commit()
        await self.db.refresh(organization)
        
        logger.info(f"Created organization: {organization.name} ({organization.id})")
        return organization

    async def update_organization(
        self, 
        organization_id: str, 
        update_data: OrganizationUpdate
    ) -> Optional[Organization]:
        """Update an organization"""
        organization = await self.get_organization_by_id(organization_id)
        if not organization:
            return None
        
        if update_data.name is not None:
            organization.name = update_data.name
        if update_data.settings is not None:
            organization.settings = update_data.settings

        organization.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(organization)
        
        logger.info(f"Updated organization: {organization.id}")
        return organization

    async def get_organization_stats(self, organization_id: str) -> OrganizationStatsResponse:
        """Get comprehensive organization statistics"""
        
        # Get total users
        users_result = await self.db.execute(
            select(func.count(User.id)).where(User.organization_id == organization_id)
        )
        total_users = users_result.scalar() or 0
        
        # Get total incidents
        incidents_result = await self.db.execute(
            select(func.count(Incident.id)).where(Incident.organization_id == organization_id)
        )
        total_incidents = incidents_result.scalar() or 0
        
        # Get active incidents
        active_incidents_result = await self.db.execute(
            select(func.count(Incident.id)).where(
                Incident.organization_id == organization_id,
                Incident.status.in_([IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED])
            )
        )
        active_incidents = active_incidents_result.scalar() or 0
        
        # Get resolved incidents
        resolved_incidents = total_incidents - active_incidents
        
        # Get total alerts
        alerts_result = await self.db.execute(
            select(func.count(Alert.id)).where(Alert.organization_id == organization_id)
        )
        total_alerts = alerts_result.scalar() or 0
        
        # Get 24h alert volume
        yesterday = datetime.utcnow() - timedelta(days=1)
        alert_24h_result = await self.db.execute(
            select(func.count(Alert.id)).where(
                Alert.organization_id == organization_id,
                Alert.created_at >= yesterday
            )
        )
        alert_volume_24h = alert_24h_result.scalar() or 0
        
        # Calculate MTTR (Mean Time To Resolution)
        mttr_hours = None
        try:
            # Get resolved incidents with resolution time
            resolved_incidents_query = await self.db.execute(
                select(Incident.created_at, Incident.resolved_at).where(
                    Incident.organization_id == organization_id,
                    Incident.status == IncidentStatus.RESOLVED,
                    Incident.resolved_at.isnot(None)
                ).limit(100)  # Last 100 resolved incidents
            )
            
            resolved_incidents_data = resolved_incidents_query.all()
            
            if resolved_incidents_data:
                total_resolution_time = sum(
                    (resolved_at - created_at).total_seconds() / 3600
                    for created_at, resolved_at in resolved_incidents_data
                )
                mttr_hours = total_resolution_time / len(resolved_incidents_data)
        except Exception as e:
            logger.error(f"Error calculating MTTR: {e}")
        
        # Get top services by incident count
        top_services = []
        try:
            top_services_result = await self.db.execute(
                select(Alert.service_name, func.count(Alert.id)).where(
                    Alert.organization_id == organization_id,
                    Alert.service_name.isnot(None)
                ).group_by(Alert.service_name).order_by(
                    func.count(Alert.id).desc()
                ).limit(5)
            )
            top_services = [service for service, count in top_services_result.all()]
        except Exception as e:
            logger.error(f"Error getting top services: {e}")
        
        return OrganizationStatsResponse(
            total_users=total_users,
            total_incidents=total_incidents,
            total_alerts=total_alerts,
            active_incidents=active_incidents,
            resolved_incidents=resolved_incidents,
            mttr_hours=round(mttr_hours, 2) if mttr_hours else None,
            alert_volume_24h=alert_volume_24h,
            top_services=top_services
        )

    async def delete_organization(self, organization_id: str) -> bool:
        """Delete an organization (soft delete by deactivating)"""
        organization = await self.get_organization_by_id(organization_id)
        if not organization:
            return False
        
        organization.is_active = False
        organization.updated_at = datetime.utcnow()
        
        await self.db.commit()
        
        logger.info(f"Deactivated organization: {organization.id}")
        return True

    async def list_organizations(
        self, 
        skip: int = 0, 
        limit: int = 100
    ) -> list[Organization]:
        """List all organizations (admin only)"""
        result = await self.db.execute(
            select(Organization)
            .where(Organization.is_active == True)
            .offset(skip)
            .limit(limit)
            .order_by(Organization.created_at.desc())
        )
        return result.scalars().all()