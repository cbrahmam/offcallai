# backend/app/models/container.py
"""
Container and Kubernetes monitoring models.
"""

import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, Float, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class ClusterStatus(str, Enum):
    """Cluster health status."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class PodPhase(str, Enum):
    """Kubernetes Pod phases."""
    PENDING = "Pending"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    UNKNOWN = "Unknown"


class ContainerState(str, Enum):
    """Container states."""
    RUNNING = "running"
    WAITING = "waiting"
    TERMINATED = "terminated"


class KubernetesCluster(Base):
    """Kubernetes cluster configuration and status."""
    __tablename__ = "kubernetes_clusters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Cluster info
    name = Column(String(255), nullable=False)
    display_name = Column(String(255))
    description = Column(Text)

    # Connection settings
    api_server_url = Column(String(512))
    auth_type = Column(String(50), default="service_account")  # service_account, kubeconfig, token

    # Cluster metadata
    version = Column(String(50))
    provider = Column(String(50))  # eks, gke, aks, on-prem, kind, minikube
    region = Column(String(100))

    # Status
    status = Column(String(20), default="unknown", index=True)
    last_sync = Column(DateTime(timezone=True))
    connection_status = Column(String(20), default="unknown")  # connected, disconnected, error

    # Resource counts (cached)
    node_count = Column(Integer, default=0)
    pod_count = Column(Integer, default=0)
    namespace_count = Column(Integer, default=0)
    deployment_count = Column(Integer, default=0)
    service_count = Column(Integer, default=0)

    # Resource utilization (cached)
    cpu_capacity = Column(Float)  # Total CPU cores
    cpu_usage = Column(Float)
    memory_capacity = Column(Float)  # Total memory in bytes
    memory_usage = Column(Float)

    # Labels and annotations
    labels = Column(JSONB, default=dict)
    annotations = Column(JSONB, default=dict)

    # Settings
    monitoring_enabled = Column(String(10), default="true")
    alert_on_pod_failure = Column(String(10), default="true")
    alert_on_node_pressure = Column(String(10), default="true")

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    namespaces = relationship("KubernetesNamespace", back_populates="cluster", cascade="all, delete-orphan")
    nodes = relationship("KubernetesNode", back_populates="cluster", cascade="all, delete-orphan")


class KubernetesNamespace(Base):
    """Kubernetes namespace."""
    __tablename__ = "kubernetes_namespaces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("kubernetes_clusters.id", ondelete="CASCADE"), nullable=False, index=True)

    # Namespace info
    name = Column(String(255), nullable=False, index=True)
    uid = Column(String(255), index=True)  # Kubernetes UID

    # Status
    status = Column(String(20), default="Active", index=True)  # Active, Terminating

    # Resource quotas
    cpu_limit = Column(Float)
    cpu_request = Column(Float)
    memory_limit = Column(Float)
    memory_request = Column(Float)
    pod_limit = Column(Integer)

    # Current usage
    cpu_usage = Column(Float)
    memory_usage = Column(Float)
    pod_count = Column(Integer, default=0)

    # Labels and annotations
    labels = Column(JSONB, default=dict)
    annotations = Column(JSONB, default=dict)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    cluster = relationship("KubernetesCluster", back_populates="namespaces")
    pods = relationship("KubernetesPod", back_populates="namespace", cascade="all, delete-orphan")
    deployments = relationship("KubernetesDeployment", back_populates="namespace", cascade="all, delete-orphan")
    services = relationship("KubernetesService", back_populates="namespace", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_k8s_namespace_cluster_name', 'cluster_id', 'name'),
    )


class KubernetesNode(Base):
    """Kubernetes cluster node."""
    __tablename__ = "kubernetes_nodes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("kubernetes_clusters.id", ondelete="CASCADE"), nullable=False, index=True)

    # Node info
    name = Column(String(255), nullable=False, index=True)
    uid = Column(String(255), index=True)

    # Node metadata
    kubernetes_version = Column(String(50))
    os_image = Column(String(255))
    container_runtime = Column(String(100))
    architecture = Column(String(50))

    # Instance info (for cloud providers)
    instance_type = Column(String(100))
    instance_id = Column(String(255))
    zone = Column(String(100))

    # Capacity
    cpu_capacity = Column(Float)
    memory_capacity = Column(Float)  # bytes
    pod_capacity = Column(Integer)

    # Allocatable
    cpu_allocatable = Column(Float)
    memory_allocatable = Column(Float)
    pod_allocatable = Column(Integer)

    # Current usage
    cpu_usage = Column(Float)
    memory_usage = Column(Float)
    pod_count = Column(Integer, default=0)

    # Status
    status = Column(String(20), default="Unknown", index=True)  # Ready, NotReady, Unknown
    conditions = Column(JSONB, default=list)  # [{type, status, reason, message}]

    # Taints
    taints = Column(JSONB, default=list)

    # Labels and annotations
    labels = Column(JSONB, default=dict)
    annotations = Column(JSONB, default=dict)

    # Roles
    is_master = Column(String(10), default="false")
    is_worker = Column(String(10), default="true")
    roles = Column(JSONB, default=list)  # ["master", "worker", "control-plane"]

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    cluster = relationship("KubernetesCluster", back_populates="nodes")

    __table_args__ = (
        Index('ix_k8s_node_cluster_name', 'cluster_id', 'name'),
    )


class KubernetesPod(Base):
    """Kubernetes pod."""
    __tablename__ = "kubernetes_pods"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    cluster_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    namespace_id = Column(UUID(as_uuid=True), ForeignKey("kubernetes_namespaces.id", ondelete="CASCADE"), nullable=False, index=True)

    # Pod info
    name = Column(String(255), nullable=False, index=True)
    uid = Column(String(255), index=True)

    # Ownership
    owner_kind = Column(String(50))  # ReplicaSet, DaemonSet, StatefulSet, Job, etc.
    owner_name = Column(String(255))
    owner_uid = Column(String(255))
    deployment_id = Column(UUID(as_uuid=True), ForeignKey("kubernetes_deployments.id", ondelete="SET NULL"))

    # Scheduling
    node_name = Column(String(255), index=True)
    node_id = Column(UUID(as_uuid=True))

    # Status
    phase = Column(String(20), default="Unknown", index=True)  # Pending, Running, Succeeded, Failed, Unknown
    conditions = Column(JSONB, default=list)
    reason = Column(String(255))
    message = Column(Text)

    # Container info
    container_count = Column(Integer, default=0)
    ready_containers = Column(Integer, default=0)
    containers = Column(JSONB, default=list)  # [{name, image, state, restarts}]

    # IP
    pod_ip = Column(String(50))
    host_ip = Column(String(50))

    # Resources (total across containers)
    cpu_request = Column(Float)
    cpu_limit = Column(Float)
    memory_request = Column(Float)
    memory_limit = Column(Float)
    cpu_usage = Column(Float)
    memory_usage = Column(Float)

    # Restart count
    restart_count = Column(Integer, default=0)

    # QoS class
    qos_class = Column(String(20))  # Guaranteed, Burstable, BestEffort

    # Labels and annotations
    labels = Column(JSONB, default=dict)
    annotations = Column(JSONB, default=dict)

    # Timestamps
    started_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    namespace = relationship("KubernetesNamespace", back_populates="pods")
    deployment = relationship("KubernetesDeployment", back_populates="pods")

    __table_args__ = (
        Index('ix_k8s_pod_namespace_name', 'namespace_id', 'name'),
        Index('ix_k8s_pod_phase', 'organization_id', 'phase'),
        Index('ix_k8s_pod_node', 'cluster_id', 'node_name'),
    )


class KubernetesDeployment(Base):
    """Kubernetes deployment."""
    __tablename__ = "kubernetes_deployments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    cluster_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    namespace_id = Column(UUID(as_uuid=True), ForeignKey("kubernetes_namespaces.id", ondelete="CASCADE"), nullable=False, index=True)

    # Deployment info
    name = Column(String(255), nullable=False, index=True)
    uid = Column(String(255), index=True)

    # Strategy
    strategy_type = Column(String(50), default="RollingUpdate")  # RollingUpdate, Recreate
    max_surge = Column(String(20))
    max_unavailable = Column(String(20))

    # Replicas
    replicas = Column(Integer, default=1)
    ready_replicas = Column(Integer, default=0)
    available_replicas = Column(Integer, default=0)
    updated_replicas = Column(Integer, default=0)
    unavailable_replicas = Column(Integer, default=0)

    # Status
    status = Column(String(20), default="Unknown", index=True)  # Progressing, Available, ReplicaFailure
    conditions = Column(JSONB, default=list)

    # Container spec (from pod template)
    containers = Column(JSONB, default=list)  # [{name, image, ports, resources}]

    # Resource totals
    cpu_request = Column(Float)
    cpu_limit = Column(Float)
    memory_request = Column(Float)
    memory_limit = Column(Float)

    # Selector
    selector = Column(JSONB, default=dict)

    # Revision
    revision = Column(Integer, default=1)
    revision_history_limit = Column(Integer, default=10)

    # Labels and annotations
    labels = Column(JSONB, default=dict)
    annotations = Column(JSONB, default=dict)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    namespace = relationship("KubernetesNamespace", back_populates="deployments")
    pods = relationship("KubernetesPod", back_populates="deployment")

    __table_args__ = (
        Index('ix_k8s_deployment_namespace_name', 'namespace_id', 'name'),
    )


class KubernetesService(Base):
    """Kubernetes service."""
    __tablename__ = "kubernetes_services"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    cluster_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    namespace_id = Column(UUID(as_uuid=True), ForeignKey("kubernetes_namespaces.id", ondelete="CASCADE"), nullable=False, index=True)

    # Service info
    name = Column(String(255), nullable=False, index=True)
    uid = Column(String(255), index=True)

    # Type
    service_type = Column(String(50), default="ClusterIP", index=True)  # ClusterIP, NodePort, LoadBalancer, ExternalName

    # IPs
    cluster_ip = Column(String(50))
    external_ips = Column(JSONB, default=list)
    load_balancer_ip = Column(String(50))

    # Ports
    ports = Column(JSONB, default=list)  # [{name, port, targetPort, nodePort, protocol}]

    # Selector
    selector = Column(JSONB, default=dict)

    # Endpoints
    endpoint_count = Column(Integer, default=0)
    endpoints = Column(JSONB, default=list)  # [{ip, ports}]

    # Labels and annotations
    labels = Column(JSONB, default=dict)
    annotations = Column(JSONB, default=dict)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    namespace = relationship("KubernetesNamespace", back_populates="services")

    __table_args__ = (
        Index('ix_k8s_service_namespace_name', 'namespace_id', 'name'),
    )


class KubernetesEvent(Base):
    """Kubernetes cluster events."""
    __tablename__ = "kubernetes_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("kubernetes_clusters.id", ondelete="CASCADE"), nullable=False, index=True)
    namespace_name = Column(String(255), index=True)

    # Event info
    name = Column(String(255))
    uid = Column(String(255), index=True)

    # Involved object
    involved_kind = Column(String(50), index=True)  # Pod, Node, Deployment, etc.
    involved_name = Column(String(255), index=True)
    involved_uid = Column(String(255))
    involved_namespace = Column(String(255))

    # Event details
    event_type = Column(String(20), index=True)  # Normal, Warning
    reason = Column(String(255), index=True)
    message = Column(Text)

    # Source
    source_component = Column(String(100))
    source_host = Column(String(255))

    # Times
    first_timestamp = Column(DateTime(timezone=True))
    last_timestamp = Column(DateTime(timezone=True), index=True)
    count = Column(Integer, default=1)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index('ix_k8s_event_cluster_time', 'cluster_id', 'last_timestamp'),
        Index('ix_k8s_event_type_reason', 'event_type', 'reason'),
    )
