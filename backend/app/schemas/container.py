# backend/app/schemas/container.py
"""
Container and Kubernetes monitoring schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


# ============================================
# Enums
# ============================================

class ClusterStatusEnum(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class PodPhaseEnum(str, Enum):
    PENDING = "Pending"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    UNKNOWN = "Unknown"


class ServiceTypeEnum(str, Enum):
    CLUSTER_IP = "ClusterIP"
    NODE_PORT = "NodePort"
    LOAD_BALANCER = "LoadBalancer"
    EXTERNAL_NAME = "ExternalName"


# ============================================
# Cluster Schemas
# ============================================

class ClusterCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = None
    description: Optional[str] = None
    api_server_url: Optional[str] = None
    auth_type: str = "service_account"
    provider: Optional[str] = None
    region: Optional[str] = None
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)
    monitoring_enabled: bool = True
    alert_on_pod_failure: bool = True
    alert_on_node_pressure: bool = True


class ClusterUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    api_server_url: Optional[str] = None
    auth_type: Optional[str] = None
    provider: Optional[str] = None
    region: Optional[str] = None
    labels: Optional[Dict[str, str]] = None
    annotations: Optional[Dict[str, str]] = None
    monitoring_enabled: Optional[bool] = None
    alert_on_pod_failure: Optional[bool] = None
    alert_on_node_pressure: Optional[bool] = None


class ClusterResponse(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    display_name: Optional[str]
    description: Optional[str]
    api_server_url: Optional[str]
    auth_type: str
    version: Optional[str]
    provider: Optional[str]
    region: Optional[str]
    status: str
    last_sync: Optional[datetime]
    connection_status: str
    node_count: int
    pod_count: int
    namespace_count: int
    deployment_count: int
    service_count: int
    cpu_capacity: Optional[float]
    cpu_usage: Optional[float]
    memory_capacity: Optional[float]
    memory_usage: Optional[float]
    labels: Dict[str, Any]
    annotations: Dict[str, Any]
    monitoring_enabled: bool
    alert_on_pod_failure: bool
    alert_on_node_pressure: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ClusterListResponse(BaseModel):
    clusters: List[ClusterResponse]
    total: int


class ClusterSummary(BaseModel):
    total_clusters: int
    healthy_clusters: int
    warning_clusters: int
    critical_clusters: int
    total_nodes: int
    total_pods: int
    running_pods: int
    failed_pods: int
    pending_pods: int
    total_cpu_capacity: float
    total_cpu_usage: float
    total_memory_capacity: float
    total_memory_usage: float


# ============================================
# Namespace Schemas
# ============================================

class NamespaceResponse(BaseModel):
    id: UUID
    organization_id: UUID
    cluster_id: UUID
    name: str
    uid: Optional[str]
    status: str
    cpu_limit: Optional[float]
    cpu_request: Optional[float]
    memory_limit: Optional[float]
    memory_request: Optional[float]
    pod_limit: Optional[int]
    cpu_usage: Optional[float]
    memory_usage: Optional[float]
    pod_count: int
    labels: Dict[str, Any]
    annotations: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NamespaceListResponse(BaseModel):
    namespaces: List[NamespaceResponse]
    total: int


# ============================================
# Node Schemas
# ============================================

class NodeResponse(BaseModel):
    id: UUID
    organization_id: UUID
    cluster_id: UUID
    name: str
    uid: Optional[str]
    kubernetes_version: Optional[str]
    os_image: Optional[str]
    container_runtime: Optional[str]
    architecture: Optional[str]
    instance_type: Optional[str]
    instance_id: Optional[str]
    zone: Optional[str]
    cpu_capacity: Optional[float]
    memory_capacity: Optional[float]
    pod_capacity: Optional[int]
    cpu_allocatable: Optional[float]
    memory_allocatable: Optional[float]
    pod_allocatable: Optional[int]
    cpu_usage: Optional[float]
    memory_usage: Optional[float]
    pod_count: int
    status: str
    conditions: List[Dict[str, Any]]
    taints: List[Dict[str, Any]]
    labels: Dict[str, Any]
    annotations: Dict[str, Any]
    is_master: bool
    is_worker: bool
    roles: List[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NodeListResponse(BaseModel):
    nodes: List[NodeResponse]
    total: int


# ============================================
# Pod Schemas
# ============================================

class ContainerInfo(BaseModel):
    name: str
    image: str
    state: str
    ready: bool
    restart_count: int
    started_at: Optional[datetime] = None
    reason: Optional[str] = None
    message: Optional[str] = None


class PodResponse(BaseModel):
    id: UUID
    organization_id: UUID
    cluster_id: UUID
    namespace_id: UUID
    name: str
    uid: Optional[str]
    owner_kind: Optional[str]
    owner_name: Optional[str]
    deployment_id: Optional[UUID]
    node_name: Optional[str]
    phase: str
    conditions: List[Dict[str, Any]]
    reason: Optional[str]
    message: Optional[str]
    container_count: int
    ready_containers: int
    containers: List[Dict[str, Any]]
    pod_ip: Optional[str]
    host_ip: Optional[str]
    cpu_request: Optional[float]
    cpu_limit: Optional[float]
    memory_request: Optional[float]
    memory_limit: Optional[float]
    cpu_usage: Optional[float]
    memory_usage: Optional[float]
    restart_count: int
    qos_class: Optional[str]
    labels: Dict[str, Any]
    annotations: Dict[str, Any]
    started_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PodListResponse(BaseModel):
    pods: List[PodResponse]
    total: int


class PodFilter(BaseModel):
    cluster_id: Optional[UUID] = None
    namespace_id: Optional[UUID] = None
    namespace_name: Optional[str] = None
    node_name: Optional[str] = None
    phase: Optional[str] = None
    owner_kind: Optional[str] = None
    deployment_id: Optional[UUID] = None
    labels: Optional[Dict[str, str]] = None


# ============================================
# Deployment Schemas
# ============================================

class DeploymentResponse(BaseModel):
    id: UUID
    organization_id: UUID
    cluster_id: UUID
    namespace_id: UUID
    name: str
    uid: Optional[str]
    strategy_type: str
    max_surge: Optional[str]
    max_unavailable: Optional[str]
    replicas: int
    ready_replicas: int
    available_replicas: int
    updated_replicas: int
    unavailable_replicas: int
    status: str
    conditions: List[Dict[str, Any]]
    containers: List[Dict[str, Any]]
    cpu_request: Optional[float]
    cpu_limit: Optional[float]
    memory_request: Optional[float]
    memory_limit: Optional[float]
    selector: Dict[str, Any]
    revision: int
    labels: Dict[str, Any]
    annotations: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeploymentListResponse(BaseModel):
    deployments: List[DeploymentResponse]
    total: int


class DeploymentScaleRequest(BaseModel):
    replicas: int = Field(..., ge=0, le=1000)


class DeploymentRestartRequest(BaseModel):
    reason: Optional[str] = None


# ============================================
# Service Schemas
# ============================================

class ServicePort(BaseModel):
    name: Optional[str]
    port: int
    target_port: Any  # Can be int or string
    node_port: Optional[int] = None
    protocol: str = "TCP"


class K8sServiceResponse(BaseModel):
    id: UUID
    organization_id: UUID
    cluster_id: UUID
    namespace_id: UUID
    name: str
    uid: Optional[str]
    service_type: str
    cluster_ip: Optional[str]
    external_ips: List[str]
    load_balancer_ip: Optional[str]
    ports: List[Dict[str, Any]]
    selector: Dict[str, Any]
    endpoint_count: int
    endpoints: List[Dict[str, Any]]
    labels: Dict[str, Any]
    annotations: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class K8sServiceListResponse(BaseModel):
    services: List[K8sServiceResponse]
    total: int


# ============================================
# Event Schemas
# ============================================

class K8sEventResponse(BaseModel):
    id: UUID
    organization_id: UUID
    cluster_id: UUID
    namespace_name: Optional[str]
    name: Optional[str]
    uid: Optional[str]
    involved_kind: Optional[str]
    involved_name: Optional[str]
    involved_uid: Optional[str]
    involved_namespace: Optional[str]
    event_type: Optional[str]
    reason: Optional[str]
    message: Optional[str]
    source_component: Optional[str]
    source_host: Optional[str]
    first_timestamp: Optional[datetime]
    last_timestamp: Optional[datetime]
    count: int
    created_at: datetime

    class Config:
        from_attributes = True


class K8sEventListResponse(BaseModel):
    events: List[K8sEventResponse]
    total: int


# ============================================
# Data Ingestion Schemas
# ============================================

class NodeData(BaseModel):
    name: str
    uid: str
    kubernetes_version: Optional[str] = None
    os_image: Optional[str] = None
    container_runtime: Optional[str] = None
    architecture: Optional[str] = None
    instance_type: Optional[str] = None
    instance_id: Optional[str] = None
    zone: Optional[str] = None
    cpu_capacity: Optional[float] = None
    memory_capacity: Optional[float] = None
    pod_capacity: Optional[int] = None
    cpu_allocatable: Optional[float] = None
    memory_allocatable: Optional[float] = None
    pod_allocatable: Optional[int] = None
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    status: str = "Unknown"
    conditions: List[Dict[str, Any]] = Field(default_factory=list)
    taints: List[Dict[str, Any]] = Field(default_factory=list)
    labels: Dict[str, str] = Field(default_factory=dict)
    roles: List[str] = Field(default_factory=list)


class PodData(BaseModel):
    namespace: str
    name: str
    uid: str
    owner_kind: Optional[str] = None
    owner_name: Optional[str] = None
    node_name: Optional[str] = None
    phase: str = "Unknown"
    conditions: List[Dict[str, Any]] = Field(default_factory=list)
    reason: Optional[str] = None
    message: Optional[str] = None
    containers: List[Dict[str, Any]] = Field(default_factory=list)
    pod_ip: Optional[str] = None
    host_ip: Optional[str] = None
    cpu_request: Optional[float] = None
    cpu_limit: Optional[float] = None
    memory_request: Optional[float] = None
    memory_limit: Optional[float] = None
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    restart_count: int = 0
    qos_class: Optional[str] = None
    labels: Dict[str, str] = Field(default_factory=dict)
    started_at: Optional[datetime] = None


class DeploymentData(BaseModel):
    namespace: str
    name: str
    uid: str
    strategy_type: str = "RollingUpdate"
    replicas: int = 1
    ready_replicas: int = 0
    available_replicas: int = 0
    updated_replicas: int = 0
    conditions: List[Dict[str, Any]] = Field(default_factory=list)
    containers: List[Dict[str, Any]] = Field(default_factory=list)
    cpu_request: Optional[float] = None
    cpu_limit: Optional[float] = None
    memory_request: Optional[float] = None
    memory_limit: Optional[float] = None
    selector: Dict[str, str] = Field(default_factory=dict)
    labels: Dict[str, str] = Field(default_factory=dict)


class ServiceData(BaseModel):
    namespace: str
    name: str
    uid: str
    service_type: str = "ClusterIP"
    cluster_ip: Optional[str] = None
    external_ips: List[str] = Field(default_factory=list)
    ports: List[Dict[str, Any]] = Field(default_factory=list)
    selector: Dict[str, str] = Field(default_factory=dict)
    endpoints: List[Dict[str, Any]] = Field(default_factory=list)
    labels: Dict[str, str] = Field(default_factory=dict)


class EventData(BaseModel):
    namespace: Optional[str] = None
    name: str
    uid: str
    involved_kind: str
    involved_name: str
    involved_uid: Optional[str] = None
    event_type: str
    reason: str
    message: Optional[str] = None
    source_component: Optional[str] = None
    source_host: Optional[str] = None
    first_timestamp: Optional[datetime] = None
    last_timestamp: Optional[datetime] = None
    count: int = 1


class ClusterSyncData(BaseModel):
    """Batch sync data from a cluster."""
    cluster_name: str
    version: Optional[str] = None
    nodes: List[NodeData] = Field(default_factory=list)
    pods: List[PodData] = Field(default_factory=list)
    deployments: List[DeploymentData] = Field(default_factory=list)
    services: List[ServiceData] = Field(default_factory=list)
    events: List[EventData] = Field(default_factory=list)
    namespaces: List[str] = Field(default_factory=list)


class SyncResult(BaseModel):
    cluster_id: UUID
    cluster_name: str
    success: bool
    nodes_synced: int = 0
    pods_synced: int = 0
    deployments_synced: int = 0
    services_synced: int = 0
    events_synced: int = 0
    namespaces_synced: int = 0
    errors: List[str] = Field(default_factory=list)
    sync_time: datetime
