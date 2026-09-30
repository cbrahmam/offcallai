# backend/app/services/service_catalog_service.py
"""Service Catalog service for managing services and dependencies"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, delete
from sqlalchemy.orm import selectinload
import logging

from app.models.service_catalog import Service, service_dependencies

logger = logging.getLogger(__name__)


class ServiceCatalogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_service(
        self,
        organization_id: UUID,
        name: str,
        slug: str,
        description: str = None,
        tier: str = "tier3",
        owner_id: UUID = None,
        team_id: UUID = None,
        repository_url: str = None,
        documentation_url: str = None,
        dashboard_url: str = None,
        runbook_id: UUID = None,
        health_check_url: str = None,
        tags: List[str] = None,
        environment: str = "production",
        service_type: str = None,
        extra_data: Dict[str, Any] = None
    ) -> Service:
        """Create a new service"""
        # Check for duplicate slug
        existing = await self.db.execute(
            select(Service).where(
                and_(
                    Service.organization_id == organization_id,
                    Service.slug == slug
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Service with slug '{slug}' already exists")

        service = Service(
            organization_id=organization_id,
            name=name,
            slug=slug,
            description=description,
            tier=tier,
            owner_id=owner_id,
            team_id=team_id,
            repository_url=repository_url,
            documentation_url=documentation_url,
            dashboard_url=dashboard_url,
            runbook_id=runbook_id,
            health_check_url=health_check_url,
            tags=tags or [],
            environment=environment,
            service_type=service_type,
            extra_data=extra_data or {}
        )

        self.db.add(service)
        await self.db.commit()
        await self.db.refresh(service)

        logger.info(f"Created service: {name} ({service.id})")
        return service

    async def get_service(
        self,
        service_id: UUID,
        organization_id: UUID
    ) -> Optional[Service]:
        """Get a service by ID"""
        result = await self.db.execute(
            select(Service)
            .options(selectinload(Service.owner), selectinload(Service.team))
            .where(
                and_(
                    Service.id == service_id,
                    Service.organization_id == organization_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_service_by_slug(
        self,
        slug: str,
        organization_id: UUID
    ) -> Optional[Service]:
        """Get a service by slug"""
        result = await self.db.execute(
            select(Service)
            .options(selectinload(Service.owner), selectinload(Service.team))
            .where(
                and_(
                    Service.slug == slug,
                    Service.organization_id == organization_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_services(
        self,
        organization_id: UUID,
        tier: str = None,
        team_id: UUID = None,
        owner_id: UUID = None,
        environment: str = None,
        service_type: str = None,
        is_active: bool = True,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[Service], int]:
        """List services with filters"""
        query = select(Service).where(Service.organization_id == organization_id)

        if is_active is not None:
            query = query.where(Service.is_active == is_active)
        if tier:
            query = query.where(Service.tier == tier)
        if team_id:
            query = query.where(Service.team_id == team_id)
        if owner_id:
            query = query.where(Service.owner_id == owner_id)
        if environment:
            query = query.where(Service.environment == environment)
        if service_type:
            query = query.where(Service.service_type == service_type)

        # Count total
        count_query = select(func.count(Service.id)).where(Service.organization_id == organization_id)
        if is_active is not None:
            count_query = count_query.where(Service.is_active == is_active)
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Get services
        query = query.options(
            selectinload(Service.owner),
            selectinload(Service.team)
        ).order_by(Service.tier, Service.name).offset(skip).limit(limit)

        result = await self.db.execute(query)
        services = list(result.scalars().all())

        return services, total

    async def update_service(
        self,
        service_id: UUID,
        organization_id: UUID,
        **kwargs
    ) -> Optional[Service]:
        """Update a service"""
        service = await self.get_service(service_id, organization_id)
        if not service:
            return None

        for key, value in kwargs.items():
            if hasattr(service, key) and value is not None:
                setattr(service, key, value)

        service.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(service)

        return service

    async def delete_service(
        self,
        service_id: UUID,
        organization_id: UUID
    ) -> bool:
        """Delete a service"""
        service = await self.get_service(service_id, organization_id)
        if not service:
            return False

        await self.db.delete(service)
        await self.db.commit()

        logger.info(f"Deleted service: {service.name} ({service_id})")
        return True

    async def add_dependency(
        self,
        upstream_id: UUID,
        downstream_id: UUID,
        organization_id: UUID,
        dependency_type: str = "requires"
    ) -> bool:
        """Add a dependency: upstream depends on downstream"""
        # Verify both services exist and belong to org
        upstream = await self.get_service(upstream_id, organization_id)
        downstream = await self.get_service(downstream_id, organization_id)

        if not upstream or not downstream:
            return False

        # Check for circular dependency
        if await self._would_create_cycle(upstream_id, downstream_id, organization_id):
            raise ValueError("Adding this dependency would create a circular reference")

        # Add dependency
        await self.db.execute(
            service_dependencies.insert().values(
                upstream_service_id=upstream_id,
                downstream_service_id=downstream_id,
                dependency_type=dependency_type
            )
        )
        await self.db.commit()

        return True

    async def remove_dependency(
        self,
        upstream_id: UUID,
        downstream_id: UUID,
        organization_id: UUID
    ) -> bool:
        """Remove a dependency"""
        await self.db.execute(
            delete(service_dependencies).where(
                and_(
                    service_dependencies.c.upstream_service_id == upstream_id,
                    service_dependencies.c.downstream_service_id == downstream_id
                )
            )
        )
        await self.db.commit()
        return True

    async def get_dependencies(
        self,
        service_id: UUID,
        organization_id: UUID
    ) -> List[Service]:
        """Get services that this service depends on"""
        service = await self.get_service(service_id, organization_id)
        if not service:
            return []

        result = await self.db.execute(
            select(Service)
            .join(
                service_dependencies,
                Service.id == service_dependencies.c.downstream_service_id
            )
            .where(service_dependencies.c.upstream_service_id == service_id)
        )
        return list(result.scalars().all())

    async def get_dependents(
        self,
        service_id: UUID,
        organization_id: UUID
    ) -> List[Service]:
        """Get services that depend on this service"""
        service = await self.get_service(service_id, organization_id)
        if not service:
            return []

        result = await self.db.execute(
            select(Service)
            .join(
                service_dependencies,
                Service.id == service_dependencies.c.upstream_service_id
            )
            .where(service_dependencies.c.downstream_service_id == service_id)
        )
        return list(result.scalars().all())

    async def get_dependency_graph(
        self,
        organization_id: UUID
    ) -> Dict[str, Any]:
        """Get full dependency graph for visualization"""
        services, _ = await self.list_services(organization_id)

        nodes = []
        edges = []

        for service in services:
            nodes.append({
                "id": str(service.id),
                "name": service.name,
                "slug": service.slug,
                "tier": service.tier,
                "health_status": service.health_status,
                "service_type": service.service_type
            })

        # Get all edges
        result = await self.db.execute(
            select(service_dependencies).join(
                Service,
                service_dependencies.c.upstream_service_id == Service.id
            ).where(Service.organization_id == organization_id)
        )
        deps = result.all()

        for dep in deps:
            edges.append({
                "source": str(dep.upstream_service_id),
                "target": str(dep.downstream_service_id),
                "type": dep.dependency_type
            })

        return {"nodes": nodes, "edges": edges}

    async def _would_create_cycle(
        self,
        upstream_id: UUID,
        downstream_id: UUID,
        organization_id: UUID
    ) -> bool:
        """Check if adding this dependency would create a cycle"""
        # Simple DFS to check for cycles
        visited = set()

        async def dfs(current_id: UUID) -> bool:
            if current_id == upstream_id:
                return True
            if current_id in visited:
                return False

            visited.add(current_id)
            deps = await self.get_dependencies(current_id, organization_id)

            for dep in deps:
                if await dfs(dep.id):
                    return True

            return False

        return await dfs(downstream_id)

    async def update_health_status(
        self,
        service_id: UUID,
        organization_id: UUID,
        status: str
    ) -> Optional[Service]:
        """Update service health status"""
        service = await self.get_service(service_id, organization_id)
        if not service:
            return None

        service.health_status = status
        service.last_health_check = datetime.utcnow()
        await self.db.commit()

        return service

    async def get_services_by_tag(
        self,
        organization_id: UUID,
        tag: str
    ) -> List[Service]:
        """Get services with a specific tag"""
        result = await self.db.execute(
            select(Service).where(
                and_(
                    Service.organization_id == organization_id,
                    Service.tags.contains([tag])
                )
            )
        )
        return list(result.scalars().all())
