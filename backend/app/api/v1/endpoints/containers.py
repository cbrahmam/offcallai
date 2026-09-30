# backend/app/api/v1/endpoints/containers.py
"""
Kubernetes and Container monitoring API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID

from app.database import get_db
from app.services.container_service import container_service
from app.schemas.container import (
    ClusterCreate, ClusterUpdate, ClusterResponse, ClusterListResponse, ClusterSummary,
    NamespaceResponse, NamespaceListResponse,
    NodeResponse, NodeListResponse,
    PodResponse, PodListResponse, PodFilter,
    DeploymentResponse, DeploymentListResponse, DeploymentScaleRequest,
    K8sServiceResponse, K8sServiceListResponse,
    K8sEventResponse, K8sEventListResponse,
    ClusterSyncData, SyncResult
)
from app.api.deps import get_current_user, get_current_organization, get_api_key_host
from app.models.user import User
from app.models.organization import Organization
from app.models.host import Host

router = APIRouter()


# ============================================
# Cluster Endpoints
# ============================================

@router.post("/clusters", response_model=ClusterResponse)
async def create_cluster(
    data: ClusterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Create a new Kubernetes cluster."""
    result = await container_service.create_cluster(
        data=data,
        organization_id=organization.id,
        db=db
    )
    return result


@router.get("/clusters", response_model=ClusterListResponse)
async def list_clusters(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """List all Kubernetes clusters."""
    result = await container_service.list_clusters(
        organization_id=organization.id,
        db=db,
        limit=limit,
        offset=offset
    )
    return result


@router.get("/clusters/summary", response_model=ClusterSummary)
async def get_cluster_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get summary statistics for all clusters."""
    result = await container_service.get_cluster_summary(
        organization_id=organization.id,
        db=db
    )
    return result


@router.get("/clusters/{cluster_id}", response_model=ClusterResponse)
async def get_cluster(
    cluster_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get a cluster by ID."""
    result = await container_service.get_cluster(
        cluster_id=cluster_id,
        organization_id=organization.id,
        db=db
    )
    if not result:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return result


@router.patch("/clusters/{cluster_id}", response_model=ClusterResponse)
async def update_cluster(
    cluster_id: UUID,
    data: ClusterUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Update a cluster."""
    result = await container_service.update_cluster(
        cluster_id=cluster_id,
        data=data,
        organization_id=organization.id,
        db=db
    )
    if not result:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return result


@router.delete("/clusters/{cluster_id}")
async def delete_cluster(
    cluster_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Delete a cluster."""
    success = await container_service.delete_cluster(
        cluster_id=cluster_id,
        organization_id=organization.id,
        db=db
    )
    if not success:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return {"message": "Cluster deleted successfully"}


# ============================================
# Namespace Endpoints
# ============================================

@router.get("/namespaces", response_model=NamespaceListResponse)
async def list_namespaces(
    cluster_id: Optional[UUID] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """List Kubernetes namespaces."""
    result = await container_service.list_namespaces(
        organization_id=organization.id,
        db=db,
        cluster_id=cluster_id,
        limit=limit,
        offset=offset
    )
    return result


@router.get("/namespaces/{namespace_id}", response_model=NamespaceResponse)
async def get_namespace(
    namespace_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get a namespace by ID."""
    result = await container_service.get_namespace(
        namespace_id=namespace_id,
        organization_id=organization.id,
        db=db
    )
    if not result:
        raise HTTPException(status_code=404, detail="Namespace not found")
    return result


# ============================================
# Node Endpoints
# ============================================

@router.get("/nodes", response_model=NodeListResponse)
async def list_nodes(
    cluster_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """List Kubernetes nodes."""
    result = await container_service.list_nodes(
        organization_id=organization.id,
        db=db,
        cluster_id=cluster_id,
        status=status,
        limit=limit,
        offset=offset
    )
    return result


@router.get("/nodes/{node_id}", response_model=NodeResponse)
async def get_node(
    node_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get a node by ID."""
    result = await container_service.get_node(
        node_id=node_id,
        organization_id=organization.id,
        db=db
    )
    if not result:
        raise HTTPException(status_code=404, detail="Node not found")
    return result


# ============================================
# Pod Endpoints
# ============================================

@router.get("/pods", response_model=PodListResponse)
async def list_pods(
    cluster_id: Optional[UUID] = Query(None),
    namespace_id: Optional[UUID] = Query(None),
    node_name: Optional[str] = Query(None),
    phase: Optional[str] = Query(None),
    owner_kind: Optional[str] = Query(None),
    deployment_id: Optional[UUID] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """List Kubernetes pods with filtering."""
    filter_data = PodFilter(
        cluster_id=cluster_id,
        namespace_id=namespace_id,
        node_name=node_name,
        phase=phase,
        owner_kind=owner_kind,
        deployment_id=deployment_id
    )
    result = await container_service.list_pods(
        organization_id=organization.id,
        db=db,
        filter_data=filter_data,
        limit=limit,
        offset=offset
    )
    return result


@router.get("/pods/{pod_id}", response_model=PodResponse)
async def get_pod(
    pod_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get a pod by ID."""
    result = await container_service.get_pod(
        pod_id=pod_id,
        organization_id=organization.id,
        db=db
    )
    if not result:
        raise HTTPException(status_code=404, detail="Pod not found")
    return result


@router.get("/pods/{pod_id}/logs")
async def get_pod_logs(
    pod_id: UUID,
    container: Optional[str] = Query(None),
    tail_lines: int = Query(100, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get logs from a pod."""
    result = await container_service.get_pod_logs(
        pod_id=pod_id,
        organization_id=organization.id,
        db=db,
        container=container,
        tail_lines=tail_lines
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ============================================
# Deployment Endpoints
# ============================================

@router.get("/deployments", response_model=DeploymentListResponse)
async def list_deployments(
    cluster_id: Optional[UUID] = Query(None),
    namespace_id: Optional[UUID] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """List Kubernetes deployments."""
    result = await container_service.list_deployments(
        organization_id=organization.id,
        db=db,
        cluster_id=cluster_id,
        namespace_id=namespace_id,
        limit=limit,
        offset=offset
    )
    return result


@router.get("/deployments/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(
    deployment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get a deployment by ID."""
    result = await container_service.get_deployment(
        deployment_id=deployment_id,
        organization_id=organization.id,
        db=db
    )
    if not result:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return result


@router.post("/deployments/{deployment_id}/scale", response_model=DeploymentResponse)
async def scale_deployment(
    deployment_id: UUID,
    data: DeploymentScaleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Scale a deployment."""
    result = await container_service.scale_deployment(
        deployment_id=deployment_id,
        replicas=data.replicas,
        organization_id=organization.id,
        db=db
    )
    if not result:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return result


# ============================================
# Service Endpoints
# ============================================

@router.get("/services", response_model=K8sServiceListResponse)
async def list_services(
    cluster_id: Optional[UUID] = Query(None),
    namespace_id: Optional[UUID] = Query(None),
    service_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """List Kubernetes services."""
    result = await container_service.list_services(
        organization_id=organization.id,
        db=db,
        cluster_id=cluster_id,
        namespace_id=namespace_id,
        service_type=service_type,
        limit=limit,
        offset=offset
    )
    return result


# ============================================
# Event Endpoints
# ============================================

@router.get("/events", response_model=K8sEventListResponse)
async def list_events(
    cluster_id: Optional[UUID] = Query(None),
    namespace_name: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    involved_kind: Optional[str] = Query(None),
    involved_name: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """List Kubernetes events."""
    result = await container_service.list_events(
        organization_id=organization.id,
        db=db,
        cluster_id=cluster_id,
        namespace_name=namespace_name,
        event_type=event_type,
        involved_kind=involved_kind,
        involved_name=involved_name,
        limit=limit,
        offset=offset
    )
    return result


# ============================================
# Data Sync Endpoint (for agent)
# ============================================

@router.post("/clusters/{cluster_id}/sync", response_model=SyncResult)
async def sync_cluster_data(
    cluster_id: UUID,
    data: ClusterSyncData,
    db: AsyncSession = Depends(get_db),
    host: Host = Depends(get_api_key_host),
):
    """Sync cluster data from monitoring agent."""
    result = await container_service.sync_cluster_data(
        cluster_id=cluster_id,
        data=data,
        organization_id=host.organization_id,
        db=db
    )
    return result
