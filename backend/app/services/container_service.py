# backend/app/services/container_service.py
"""
Container and Kubernetes monitoring service.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, delete
from sqlalchemy.orm import selectinload

from app.models.container import (
    KubernetesCluster, KubernetesNamespace, KubernetesNode,
    KubernetesPod, KubernetesDeployment, KubernetesService, KubernetesEvent
)
from app.schemas.container import (
    ClusterCreate, ClusterUpdate, ClusterResponse, ClusterListResponse, ClusterSummary,
    NamespaceResponse, NamespaceListResponse,
    NodeResponse, NodeListResponse,
    PodResponse, PodListResponse, PodFilter,
    DeploymentResponse, DeploymentListResponse,
    K8sServiceResponse, K8sServiceListResponse,
    K8sEventResponse, K8sEventListResponse,
    ClusterSyncData, SyncResult
)


class ContainerService:
    """Service for managing Kubernetes clusters and resources."""

    # ============================================
    # Cluster Operations
    # ============================================

    async def create_cluster(
        self,
        data: ClusterCreate,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> ClusterResponse:
        """Create a new Kubernetes cluster."""
        cluster = KubernetesCluster(
            organization_id=organization_id,
            name=data.name,
            display_name=data.display_name or data.name,
            description=data.description,
            api_server_url=data.api_server_url,
            auth_type=data.auth_type,
            provider=data.provider,
            region=data.region,
            labels=data.labels,
            annotations=data.annotations,
            monitoring_enabled="true" if data.monitoring_enabled else "false",
            alert_on_pod_failure="true" if data.alert_on_pod_failure else "false",
            alert_on_node_pressure="true" if data.alert_on_node_pressure else "false",
            status="unknown",
            connection_status="disconnected"
        )

        db.add(cluster)
        await db.commit()
        await db.refresh(cluster)

        return self._cluster_to_response(cluster)

    async def get_cluster(
        self,
        cluster_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[ClusterResponse]:
        """Get a cluster by ID."""
        result = await db.execute(
            select(KubernetesCluster)
            .where(
                KubernetesCluster.id == cluster_id,
                KubernetesCluster.organization_id == organization_id
            )
        )
        cluster = result.scalar_one_or_none()
        if cluster:
            return self._cluster_to_response(cluster)
        return None

    async def list_clusters(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession,
        limit: int = 50,
        offset: int = 0
    ) -> ClusterListResponse:
        """List all clusters for an organization."""
        # Count total
        count_result = await db.execute(
            select(func.count())
            .select_from(KubernetesCluster)
            .where(KubernetesCluster.organization_id == organization_id)
        )
        total = count_result.scalar() or 0

        # Get clusters
        result = await db.execute(
            select(KubernetesCluster)
            .where(KubernetesCluster.organization_id == organization_id)
            .order_by(KubernetesCluster.name)
            .offset(offset)
            .limit(limit)
        )
        clusters = result.scalars().all()

        return ClusterListResponse(
            clusters=[self._cluster_to_response(c) for c in clusters],
            total=total
        )

    async def update_cluster(
        self,
        cluster_id: uuid.UUID,
        data: ClusterUpdate,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[ClusterResponse]:
        """Update a cluster."""
        result = await db.execute(
            select(KubernetesCluster)
            .where(
                KubernetesCluster.id == cluster_id,
                KubernetesCluster.organization_id == organization_id
            )
        )
        cluster = result.scalar_one_or_none()
        if not cluster:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key in ['monitoring_enabled', 'alert_on_pod_failure', 'alert_on_node_pressure']:
                setattr(cluster, key, "true" if value else "false")
            else:
                setattr(cluster, key, value)

        cluster.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(cluster)

        return self._cluster_to_response(cluster)

    async def delete_cluster(
        self,
        cluster_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> bool:
        """Delete a cluster."""
        result = await db.execute(
            select(KubernetesCluster)
            .where(
                KubernetesCluster.id == cluster_id,
                KubernetesCluster.organization_id == organization_id
            )
        )
        cluster = result.scalar_one_or_none()
        if not cluster:
            return False

        await db.delete(cluster)
        await db.commit()
        return True

    async def get_cluster_summary(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> ClusterSummary:
        """Get summary statistics for all clusters."""
        # Get cluster counts by status
        clusters_result = await db.execute(
            select(KubernetesCluster)
            .where(KubernetesCluster.organization_id == organization_id)
        )
        clusters = clusters_result.scalars().all()

        total_clusters = len(clusters)
        healthy_clusters = sum(1 for c in clusters if c.status == "healthy")
        warning_clusters = sum(1 for c in clusters if c.status == "warning")
        critical_clusters = sum(1 for c in clusters if c.status == "critical")

        total_nodes = sum(c.node_count or 0 for c in clusters)
        total_pods = sum(c.pod_count or 0 for c in clusters)
        total_cpu_capacity = sum(c.cpu_capacity or 0 for c in clusters)
        total_cpu_usage = sum(c.cpu_usage or 0 for c in clusters)
        total_memory_capacity = sum(c.memory_capacity or 0 for c in clusters)
        total_memory_usage = sum(c.memory_usage or 0 for c in clusters)

        # Get pod phase counts
        pods_result = await db.execute(
            select(KubernetesPod.phase, func.count())
            .where(KubernetesPod.organization_id == organization_id)
            .group_by(KubernetesPod.phase)
        )
        pod_phases = dict(pods_result.all())

        return ClusterSummary(
            total_clusters=total_clusters,
            healthy_clusters=healthy_clusters,
            warning_clusters=warning_clusters,
            critical_clusters=critical_clusters,
            total_nodes=total_nodes,
            total_pods=total_pods,
            running_pods=pod_phases.get("Running", 0),
            failed_pods=pod_phases.get("Failed", 0),
            pending_pods=pod_phases.get("Pending", 0),
            total_cpu_capacity=total_cpu_capacity,
            total_cpu_usage=total_cpu_usage,
            total_memory_capacity=total_memory_capacity,
            total_memory_usage=total_memory_usage
        )

    # ============================================
    # Namespace Operations
    # ============================================

    async def list_namespaces(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession,
        cluster_id: Optional[uuid.UUID] = None,
        limit: int = 100,
        offset: int = 0
    ) -> NamespaceListResponse:
        """List namespaces."""
        query = select(KubernetesNamespace).where(
            KubernetesNamespace.organization_id == organization_id
        )

        if cluster_id:
            query = query.where(KubernetesNamespace.cluster_id == cluster_id)

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        # Get data
        result = await db.execute(
            query.order_by(KubernetesNamespace.name)
            .offset(offset)
            .limit(limit)
        )
        namespaces = result.scalars().all()

        return NamespaceListResponse(
            namespaces=[self._namespace_to_response(ns) for ns in namespaces],
            total=total
        )

    async def get_namespace(
        self,
        namespace_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[NamespaceResponse]:
        """Get a namespace by ID."""
        result = await db.execute(
            select(KubernetesNamespace)
            .where(
                KubernetesNamespace.id == namespace_id,
                KubernetesNamespace.organization_id == organization_id
            )
        )
        namespace = result.scalar_one_or_none()
        if namespace:
            return self._namespace_to_response(namespace)
        return None

    # ============================================
    # Node Operations
    # ============================================

    async def list_nodes(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession,
        cluster_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> NodeListResponse:
        """List nodes."""
        query = select(KubernetesNode).where(
            KubernetesNode.organization_id == organization_id
        )

        if cluster_id:
            query = query.where(KubernetesNode.cluster_id == cluster_id)
        if status:
            query = query.where(KubernetesNode.status == status)

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        # Get data
        result = await db.execute(
            query.order_by(KubernetesNode.name)
            .offset(offset)
            .limit(limit)
        )
        nodes = result.scalars().all()

        return NodeListResponse(
            nodes=[self._node_to_response(n) for n in nodes],
            total=total
        )

    async def get_node(
        self,
        node_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[NodeResponse]:
        """Get a node by ID."""
        result = await db.execute(
            select(KubernetesNode)
            .where(
                KubernetesNode.id == node_id,
                KubernetesNode.organization_id == organization_id
            )
        )
        node = result.scalar_one_or_none()
        if node:
            return self._node_to_response(node)
        return None

    # ============================================
    # Pod Operations
    # ============================================

    async def list_pods(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession,
        filter_data: Optional[PodFilter] = None,
        limit: int = 100,
        offset: int = 0
    ) -> PodListResponse:
        """List pods with filtering."""
        query = select(KubernetesPod).where(
            KubernetesPod.organization_id == organization_id
        )

        if filter_data:
            if filter_data.cluster_id:
                query = query.where(KubernetesPod.cluster_id == filter_data.cluster_id)
            if filter_data.namespace_id:
                query = query.where(KubernetesPod.namespace_id == filter_data.namespace_id)
            if filter_data.node_name:
                query = query.where(KubernetesPod.node_name == filter_data.node_name)
            if filter_data.phase:
                query = query.where(KubernetesPod.phase == filter_data.phase)
            if filter_data.owner_kind:
                query = query.where(KubernetesPod.owner_kind == filter_data.owner_kind)
            if filter_data.deployment_id:
                query = query.where(KubernetesPod.deployment_id == filter_data.deployment_id)

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        # Get data
        result = await db.execute(
            query.order_by(KubernetesPod.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        pods = result.scalars().all()

        return PodListResponse(
            pods=[self._pod_to_response(p) for p in pods],
            total=total
        )

    async def get_pod(
        self,
        pod_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[PodResponse]:
        """Get a pod by ID."""
        result = await db.execute(
            select(KubernetesPod)
            .where(
                KubernetesPod.id == pod_id,
                KubernetesPod.organization_id == organization_id
            )
        )
        pod = result.scalar_one_or_none()
        if pod:
            return self._pod_to_response(pod)
        return None

    async def get_pod_logs(
        self,
        pod_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession,
        container: Optional[str] = None,
        tail_lines: int = 100
    ) -> Dict[str, Any]:
        """Get pod logs (placeholder - would need actual K8s connection)."""
        pod = await self.get_pod(pod_id, organization_id, db)
        if not pod:
            return {"error": "Pod not found"}

        # In a real implementation, this would connect to the K8s API
        return {
            "pod_name": pod.name,
            "container": container or (pod.containers[0]["name"] if pod.containers else "unknown"),
            "logs": f"[Logs would be fetched from Kubernetes cluster]\nPod: {pod.name}\nPhase: {pod.phase}",
            "tail_lines": tail_lines
        }

    # ============================================
    # Deployment Operations
    # ============================================

    async def list_deployments(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession,
        cluster_id: Optional[uuid.UUID] = None,
        namespace_id: Optional[uuid.UUID] = None,
        limit: int = 100,
        offset: int = 0
    ) -> DeploymentListResponse:
        """List deployments."""
        query = select(KubernetesDeployment).where(
            KubernetesDeployment.organization_id == organization_id
        )

        if cluster_id:
            query = query.where(KubernetesDeployment.cluster_id == cluster_id)
        if namespace_id:
            query = query.where(KubernetesDeployment.namespace_id == namespace_id)

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        # Get data
        result = await db.execute(
            query.order_by(KubernetesDeployment.name)
            .offset(offset)
            .limit(limit)
        )
        deployments = result.scalars().all()

        return DeploymentListResponse(
            deployments=[self._deployment_to_response(d) for d in deployments],
            total=total
        )

    async def get_deployment(
        self,
        deployment_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[DeploymentResponse]:
        """Get a deployment by ID."""
        result = await db.execute(
            select(KubernetesDeployment)
            .where(
                KubernetesDeployment.id == deployment_id,
                KubernetesDeployment.organization_id == organization_id
            )
        )
        deployment = result.scalar_one_or_none()
        if deployment:
            return self._deployment_to_response(deployment)
        return None

    async def scale_deployment(
        self,
        deployment_id: uuid.UUID,
        replicas: int,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[DeploymentResponse]:
        """Scale a deployment (placeholder)."""
        result = await db.execute(
            select(KubernetesDeployment)
            .where(
                KubernetesDeployment.id == deployment_id,
                KubernetesDeployment.organization_id == organization_id
            )
        )
        deployment = result.scalar_one_or_none()
        if not deployment:
            return None

        # In a real implementation, this would call the K8s API to scale
        deployment.replicas = replicas
        deployment.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(deployment)

        return self._deployment_to_response(deployment)

    # ============================================
    # Service Operations
    # ============================================

    async def list_services(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession,
        cluster_id: Optional[uuid.UUID] = None,
        namespace_id: Optional[uuid.UUID] = None,
        service_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> K8sServiceListResponse:
        """List Kubernetes services."""
        query = select(KubernetesService).where(
            KubernetesService.organization_id == organization_id
        )

        if cluster_id:
            query = query.where(KubernetesService.cluster_id == cluster_id)
        if namespace_id:
            query = query.where(KubernetesService.namespace_id == namespace_id)
        if service_type:
            query = query.where(KubernetesService.service_type == service_type)

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        # Get data
        result = await db.execute(
            query.order_by(KubernetesService.name)
            .offset(offset)
            .limit(limit)
        )
        services = result.scalars().all()

        return K8sServiceListResponse(
            services=[self._service_to_response(s) for s in services],
            total=total
        )

    # ============================================
    # Event Operations
    # ============================================

    async def list_events(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession,
        cluster_id: Optional[uuid.UUID] = None,
        namespace_name: Optional[str] = None,
        event_type: Optional[str] = None,
        involved_kind: Optional[str] = None,
        involved_name: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> K8sEventListResponse:
        """List Kubernetes events."""
        query = select(KubernetesEvent).where(
            KubernetesEvent.organization_id == organization_id
        )

        if cluster_id:
            query = query.where(KubernetesEvent.cluster_id == cluster_id)
        if namespace_name:
            query = query.where(KubernetesEvent.namespace_name == namespace_name)
        if event_type:
            query = query.where(KubernetesEvent.event_type == event_type)
        if involved_kind:
            query = query.where(KubernetesEvent.involved_kind == involved_kind)
        if involved_name:
            query = query.where(KubernetesEvent.involved_name == involved_name)

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        # Get data
        result = await db.execute(
            query.order_by(KubernetesEvent.last_timestamp.desc())
            .offset(offset)
            .limit(limit)
        )
        events = result.scalars().all()

        return K8sEventListResponse(
            events=[self._event_to_response(e) for e in events],
            total=total
        )

    # ============================================
    # Data Sync (from agent)
    # ============================================

    async def sync_cluster_data(
        self,
        cluster_id: uuid.UUID,
        data: ClusterSyncData,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> SyncResult:
        """Sync cluster data from agent."""
        errors = []
        result = SyncResult(
            cluster_id=cluster_id,
            cluster_name=data.cluster_name,
            success=True,
            sync_time=datetime.utcnow()
        )

        try:
            # Get or validate cluster
            cluster_result = await db.execute(
                select(KubernetesCluster)
                .where(
                    KubernetesCluster.id == cluster_id,
                    KubernetesCluster.organization_id == organization_id
                )
            )
            cluster = cluster_result.scalar_one_or_none()
            if not cluster:
                result.success = False
                result.errors = ["Cluster not found"]
                return result

            # Update cluster version
            if data.version:
                cluster.version = data.version

            # Sync namespaces
            namespace_map = {}
            for ns_name in data.namespaces:
                ns = await self._upsert_namespace(cluster, ns_name, organization_id, db)
                namespace_map[ns_name] = ns.id
                result.namespaces_synced += 1

            # Sync nodes
            for node_data in data.nodes:
                try:
                    await self._upsert_node(cluster, node_data, organization_id, db)
                    result.nodes_synced += 1
                except Exception as e:
                    errors.append(f"Node {node_data.name}: {str(e)}")

            # Sync deployments
            deployment_map = {}
            for dep_data in data.deployments:
                try:
                    ns_id = namespace_map.get(dep_data.namespace)
                    if ns_id:
                        dep = await self._upsert_deployment(cluster, ns_id, dep_data, organization_id, db)
                        deployment_map[f"{dep_data.namespace}/{dep_data.name}"] = dep.id
                        result.deployments_synced += 1
                except Exception as e:
                    errors.append(f"Deployment {dep_data.namespace}/{dep_data.name}: {str(e)}")

            # Sync pods
            for pod_data in data.pods:
                try:
                    ns_id = namespace_map.get(pod_data.namespace)
                    if ns_id:
                        # Find deployment if owned by ReplicaSet
                        deployment_id = None
                        if pod_data.owner_kind == "ReplicaSet" and pod_data.owner_name:
                            # ReplicaSets are named <deployment>-<hash>
                            parts = pod_data.owner_name.rsplit("-", 1)
                            if len(parts) == 2:
                                dep_key = f"{pod_data.namespace}/{parts[0]}"
                                deployment_id = deployment_map.get(dep_key)

                        await self._upsert_pod(cluster, ns_id, deployment_id, pod_data, organization_id, db)
                        result.pods_synced += 1
                except Exception as e:
                    errors.append(f"Pod {pod_data.namespace}/{pod_data.name}: {str(e)}")

            # Sync services
            for svc_data in data.services:
                try:
                    ns_id = namespace_map.get(svc_data.namespace)
                    if ns_id:
                        await self._upsert_service(cluster, ns_id, svc_data, organization_id, db)
                        result.services_synced += 1
                except Exception as e:
                    errors.append(f"Service {svc_data.namespace}/{svc_data.name}: {str(e)}")

            # Sync events
            for event_data in data.events:
                try:
                    await self._upsert_event(cluster, event_data, organization_id, db)
                    result.events_synced += 1
                except Exception as e:
                    errors.append(f"Event {event_data.name}: {str(e)}")

            # Update cluster stats
            await self._update_cluster_stats(cluster, db)

            cluster.last_sync = datetime.utcnow()
            cluster.connection_status = "connected"
            await db.commit()

        except Exception as e:
            result.success = False
            errors.append(f"Sync failed: {str(e)}")
            await db.rollback()

        result.errors = errors
        return result

    # ============================================
    # Helper Methods
    # ============================================

    async def _upsert_namespace(
        self,
        cluster: KubernetesCluster,
        name: str,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> KubernetesNamespace:
        """Create or update a namespace."""
        result = await db.execute(
            select(KubernetesNamespace)
            .where(
                KubernetesNamespace.cluster_id == cluster.id,
                KubernetesNamespace.name == name
            )
        )
        namespace = result.scalars().first()

        if not namespace:
            namespace = KubernetesNamespace(
                organization_id=organization_id,
                cluster_id=cluster.id,
                name=name,
                status="Active"
            )
            db.add(namespace)
            await db.flush()

        return namespace

    async def _upsert_node(
        self,
        cluster: KubernetesCluster,
        data,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> KubernetesNode:
        """Create or update a node."""
        result = await db.execute(
            select(KubernetesNode)
            .where(
                KubernetesNode.cluster_id == cluster.id,
                KubernetesNode.uid == data.uid
            )
        )
        node = result.scalars().first()

        if not node:
            node = KubernetesNode(
                organization_id=organization_id,
                cluster_id=cluster.id,
                name=data.name,
                uid=data.uid
            )
            db.add(node)

        # Update fields
        node.kubernetes_version = data.kubernetes_version
        node.os_image = data.os_image
        node.container_runtime = data.container_runtime
        node.architecture = data.architecture
        node.instance_type = data.instance_type
        node.instance_id = data.instance_id
        node.zone = data.zone
        node.cpu_capacity = data.cpu_capacity
        node.memory_capacity = data.memory_capacity
        node.pod_capacity = data.pod_capacity
        node.cpu_allocatable = data.cpu_allocatable
        node.memory_allocatable = data.memory_allocatable
        node.pod_allocatable = data.pod_allocatable
        node.cpu_usage = data.cpu_usage
        node.memory_usage = data.memory_usage
        node.status = data.status
        node.conditions = data.conditions
        node.taints = data.taints
        node.labels = data.labels
        node.roles = data.roles
        node.is_master = "true" if "master" in data.roles or "control-plane" in data.roles else "false"
        node.is_worker = "true" if "worker" in data.roles or not data.roles else "false"
        node.updated_at = datetime.utcnow()

        await db.flush()
        return node

    async def _upsert_pod(
        self,
        cluster: KubernetesCluster,
        namespace_id: uuid.UUID,
        deployment_id: Optional[uuid.UUID],
        data,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> KubernetesPod:
        """Create or update a pod."""
        result = await db.execute(
            select(KubernetesPod)
            .where(
                KubernetesPod.cluster_id == cluster.id,
                KubernetesPod.uid == data.uid
            )
        )
        pod = result.scalars().first()

        if not pod:
            pod = KubernetesPod(
                organization_id=organization_id,
                cluster_id=cluster.id,
                namespace_id=namespace_id,
                name=data.name,
                uid=data.uid
            )
            db.add(pod)

        # Update fields
        pod.owner_kind = data.owner_kind
        pod.owner_name = data.owner_name
        pod.deployment_id = deployment_id
        pod.node_name = data.node_name
        pod.phase = data.phase
        pod.conditions = data.conditions
        pod.reason = data.reason
        pod.message = data.message
        pod.containers = data.containers
        pod.container_count = len(data.containers)
        pod.ready_containers = sum(1 for c in data.containers if c.get("ready", False))
        pod.pod_ip = data.pod_ip
        pod.host_ip = data.host_ip
        pod.cpu_request = data.cpu_request
        pod.cpu_limit = data.cpu_limit
        pod.memory_request = data.memory_request
        pod.memory_limit = data.memory_limit
        pod.cpu_usage = data.cpu_usage
        pod.memory_usage = data.memory_usage
        pod.restart_count = data.restart_count
        pod.qos_class = data.qos_class
        pod.labels = data.labels
        pod.started_at = data.started_at
        pod.updated_at = datetime.utcnow()

        await db.flush()
        return pod

    async def _upsert_deployment(
        self,
        cluster: KubernetesCluster,
        namespace_id: uuid.UUID,
        data,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> KubernetesDeployment:
        """Create or update a deployment."""
        result = await db.execute(
            select(KubernetesDeployment)
            .where(
                KubernetesDeployment.cluster_id == cluster.id,
                KubernetesDeployment.uid == data.uid
            )
        )
        deployment = result.scalars().first()

        if not deployment:
            deployment = KubernetesDeployment(
                organization_id=organization_id,
                cluster_id=cluster.id,
                namespace_id=namespace_id,
                name=data.name,
                uid=data.uid
            )
            db.add(deployment)

        # Update fields
        deployment.strategy_type = data.strategy_type
        deployment.replicas = data.replicas
        deployment.ready_replicas = data.ready_replicas
        deployment.available_replicas = data.available_replicas
        deployment.updated_replicas = data.updated_replicas
        deployment.unavailable_replicas = data.replicas - data.available_replicas
        deployment.conditions = data.conditions
        deployment.containers = data.containers
        deployment.cpu_request = data.cpu_request
        deployment.cpu_limit = data.cpu_limit
        deployment.memory_request = data.memory_request
        deployment.memory_limit = data.memory_limit
        deployment.selector = data.selector
        deployment.labels = data.labels
        deployment.status = self._determine_deployment_status(data)
        deployment.updated_at = datetime.utcnow()

        await db.flush()
        return deployment

    async def _upsert_service(
        self,
        cluster: KubernetesCluster,
        namespace_id: uuid.UUID,
        data,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> KubernetesService:
        """Create or update a service."""
        result = await db.execute(
            select(KubernetesService)
            .where(
                KubernetesService.cluster_id == cluster.id,
                KubernetesService.uid == data.uid
            )
        )
        service = result.scalars().first()

        if not service:
            service = KubernetesService(
                organization_id=organization_id,
                cluster_id=cluster.id,
                namespace_id=namespace_id,
                name=data.name,
                uid=data.uid
            )
            db.add(service)

        # Update fields
        service.service_type = data.service_type
        service.cluster_ip = data.cluster_ip
        service.external_ips = data.external_ips
        service.ports = data.ports
        service.selector = data.selector
        service.endpoints = data.endpoints
        service.endpoint_count = len(data.endpoints)
        service.labels = data.labels
        service.updated_at = datetime.utcnow()

        await db.flush()
        return service

    async def _upsert_event(
        self,
        cluster: KubernetesCluster,
        data,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> KubernetesEvent:
        """Create or update an event."""
        result = await db.execute(
            select(KubernetesEvent)
            .where(
                KubernetesEvent.cluster_id == cluster.id,
                KubernetesEvent.uid == data.uid
            )
        )
        event = result.scalars().first()

        if not event:
            event = KubernetesEvent(
                organization_id=organization_id,
                cluster_id=cluster.id,
                namespace_name=data.namespace,
                name=data.name,
                uid=data.uid
            )
            db.add(event)

        # Update fields
        event.involved_kind = data.involved_kind
        event.involved_name = data.involved_name
        event.involved_uid = data.involved_uid
        event.involved_namespace = data.namespace
        event.event_type = data.event_type
        event.reason = data.reason
        event.message = data.message
        event.source_component = data.source_component
        event.source_host = data.source_host
        event.first_timestamp = data.first_timestamp
        event.last_timestamp = data.last_timestamp
        event.count = data.count

        await db.flush()
        return event

    async def _update_cluster_stats(self, cluster: KubernetesCluster, db: AsyncSession):
        """Update cluster statistics."""
        # Node count
        node_count = await db.execute(
            select(func.count()).select_from(KubernetesNode)
            .where(KubernetesNode.cluster_id == cluster.id)
        )
        cluster.node_count = node_count.scalar() or 0

        # Pod count
        pod_count = await db.execute(
            select(func.count()).select_from(KubernetesPod)
            .where(KubernetesPod.cluster_id == cluster.id)
        )
        cluster.pod_count = pod_count.scalar() or 0

        # Namespace count
        ns_count = await db.execute(
            select(func.count()).select_from(KubernetesNamespace)
            .where(KubernetesNamespace.cluster_id == cluster.id)
        )
        cluster.namespace_count = ns_count.scalar() or 0

        # Deployment count
        dep_count = await db.execute(
            select(func.count()).select_from(KubernetesDeployment)
            .where(KubernetesDeployment.cluster_id == cluster.id)
        )
        cluster.deployment_count = dep_count.scalar() or 0

        # Service count
        svc_count = await db.execute(
            select(func.count()).select_from(KubernetesService)
            .where(KubernetesService.cluster_id == cluster.id)
        )
        cluster.service_count = svc_count.scalar() or 0

        # Resource totals from nodes
        node_stats = await db.execute(
            select(
                func.sum(KubernetesNode.cpu_capacity),
                func.sum(KubernetesNode.cpu_usage),
                func.sum(KubernetesNode.memory_capacity),
                func.sum(KubernetesNode.memory_usage)
            )
            .where(KubernetesNode.cluster_id == cluster.id)
        )
        stats = node_stats.one()
        cluster.cpu_capacity = stats[0] or 0
        cluster.cpu_usage = stats[1] or 0
        cluster.memory_capacity = stats[2] or 0
        cluster.memory_usage = stats[3] or 0

        # Determine cluster status
        cluster.status = self._determine_cluster_status(cluster)

    def _determine_cluster_status(self, cluster: KubernetesCluster) -> str:
        """Determine overall cluster health status."""
        if cluster.connection_status != "connected":
            return "unknown"

        # Check resource utilization
        cpu_util = (cluster.cpu_usage / cluster.cpu_capacity * 100) if cluster.cpu_capacity else 0
        mem_util = (cluster.memory_usage / cluster.memory_capacity * 100) if cluster.memory_capacity else 0

        if cpu_util > 90 or mem_util > 90:
            return "critical"
        elif cpu_util > 75 or mem_util > 75:
            return "warning"

        return "healthy"

    def _determine_deployment_status(self, data) -> str:
        """Determine deployment status from conditions."""
        if data.available_replicas >= data.replicas and data.replicas > 0:
            return "Available"
        elif data.ready_replicas < data.replicas:
            return "Progressing"
        return "Unknown"

    def _cluster_to_response(self, cluster: KubernetesCluster) -> ClusterResponse:
        """Convert cluster model to response."""
        return ClusterResponse(
            id=cluster.id,
            organization_id=cluster.organization_id,
            name=cluster.name,
            display_name=cluster.display_name,
            description=cluster.description,
            api_server_url=cluster.api_server_url,
            auth_type=cluster.auth_type,
            version=cluster.version,
            provider=cluster.provider,
            region=cluster.region,
            status=cluster.status,
            last_sync=cluster.last_sync,
            connection_status=cluster.connection_status,
            node_count=cluster.node_count or 0,
            pod_count=cluster.pod_count or 0,
            namespace_count=cluster.namespace_count or 0,
            deployment_count=cluster.deployment_count or 0,
            service_count=cluster.service_count or 0,
            cpu_capacity=cluster.cpu_capacity,
            cpu_usage=cluster.cpu_usage,
            memory_capacity=cluster.memory_capacity,
            memory_usage=cluster.memory_usage,
            labels=cluster.labels or {},
            annotations=cluster.annotations or {},
            monitoring_enabled=cluster.monitoring_enabled == "true",
            alert_on_pod_failure=cluster.alert_on_pod_failure == "true",
            alert_on_node_pressure=cluster.alert_on_node_pressure == "true",
            created_at=cluster.created_at,
            updated_at=cluster.updated_at
        )

    def _namespace_to_response(self, namespace: KubernetesNamespace) -> NamespaceResponse:
        """Convert namespace model to response."""
        return NamespaceResponse(
            id=namespace.id,
            organization_id=namespace.organization_id,
            cluster_id=namespace.cluster_id,
            name=namespace.name,
            uid=namespace.uid,
            status=namespace.status,
            cpu_limit=namespace.cpu_limit,
            cpu_request=namespace.cpu_request,
            memory_limit=namespace.memory_limit,
            memory_request=namespace.memory_request,
            pod_limit=namespace.pod_limit,
            cpu_usage=namespace.cpu_usage,
            memory_usage=namespace.memory_usage,
            pod_count=namespace.pod_count or 0,
            labels=namespace.labels or {},
            annotations=namespace.annotations or {},
            created_at=namespace.created_at,
            updated_at=namespace.updated_at
        )

    def _node_to_response(self, node: KubernetesNode) -> NodeResponse:
        """Convert node model to response."""
        return NodeResponse(
            id=node.id,
            organization_id=node.organization_id,
            cluster_id=node.cluster_id,
            name=node.name,
            uid=node.uid,
            kubernetes_version=node.kubernetes_version,
            os_image=node.os_image,
            container_runtime=node.container_runtime,
            architecture=node.architecture,
            instance_type=node.instance_type,
            instance_id=node.instance_id,
            zone=node.zone,
            cpu_capacity=node.cpu_capacity,
            memory_capacity=node.memory_capacity,
            pod_capacity=node.pod_capacity,
            cpu_allocatable=node.cpu_allocatable,
            memory_allocatable=node.memory_allocatable,
            pod_allocatable=node.pod_allocatable,
            cpu_usage=node.cpu_usage,
            memory_usage=node.memory_usage,
            pod_count=node.pod_count or 0,
            status=node.status,
            conditions=node.conditions or [],
            taints=node.taints or [],
            labels=node.labels or {},
            annotations=node.annotations or {},
            is_master=node.is_master == "true",
            is_worker=node.is_worker == "true",
            roles=node.roles or [],
            created_at=node.created_at,
            updated_at=node.updated_at
        )

    def _pod_to_response(self, pod: KubernetesPod) -> PodResponse:
        """Convert pod model to response."""
        return PodResponse(
            id=pod.id,
            organization_id=pod.organization_id,
            cluster_id=pod.cluster_id,
            namespace_id=pod.namespace_id,
            name=pod.name,
            uid=pod.uid,
            owner_kind=pod.owner_kind,
            owner_name=pod.owner_name,
            deployment_id=pod.deployment_id,
            node_name=pod.node_name,
            phase=pod.phase,
            conditions=pod.conditions or [],
            reason=pod.reason,
            message=pod.message,
            container_count=pod.container_count or 0,
            ready_containers=pod.ready_containers or 0,
            containers=pod.containers or [],
            pod_ip=pod.pod_ip,
            host_ip=pod.host_ip,
            cpu_request=pod.cpu_request,
            cpu_limit=pod.cpu_limit,
            memory_request=pod.memory_request,
            memory_limit=pod.memory_limit,
            cpu_usage=pod.cpu_usage,
            memory_usage=pod.memory_usage,
            restart_count=pod.restart_count or 0,
            qos_class=pod.qos_class,
            labels=pod.labels or {},
            annotations=pod.annotations or {},
            started_at=pod.started_at,
            created_at=pod.created_at,
            updated_at=pod.updated_at
        )

    def _deployment_to_response(self, deployment: KubernetesDeployment) -> DeploymentResponse:
        """Convert deployment model to response."""
        return DeploymentResponse(
            id=deployment.id,
            organization_id=deployment.organization_id,
            cluster_id=deployment.cluster_id,
            namespace_id=deployment.namespace_id,
            name=deployment.name,
            uid=deployment.uid,
            strategy_type=deployment.strategy_type,
            max_surge=deployment.max_surge,
            max_unavailable=deployment.max_unavailable,
            replicas=deployment.replicas or 0,
            ready_replicas=deployment.ready_replicas or 0,
            available_replicas=deployment.available_replicas or 0,
            updated_replicas=deployment.updated_replicas or 0,
            unavailable_replicas=deployment.unavailable_replicas or 0,
            status=deployment.status,
            conditions=deployment.conditions or [],
            containers=deployment.containers or [],
            cpu_request=deployment.cpu_request,
            cpu_limit=deployment.cpu_limit,
            memory_request=deployment.memory_request,
            memory_limit=deployment.memory_limit,
            selector=deployment.selector or {},
            revision=deployment.revision or 1,
            labels=deployment.labels or {},
            annotations=deployment.annotations or {},
            created_at=deployment.created_at,
            updated_at=deployment.updated_at
        )

    def _service_to_response(self, service: KubernetesService) -> K8sServiceResponse:
        """Convert service model to response."""
        return K8sServiceResponse(
            id=service.id,
            organization_id=service.organization_id,
            cluster_id=service.cluster_id,
            namespace_id=service.namespace_id,
            name=service.name,
            uid=service.uid,
            service_type=service.service_type,
            cluster_ip=service.cluster_ip,
            external_ips=service.external_ips or [],
            load_balancer_ip=service.load_balancer_ip,
            ports=service.ports or [],
            selector=service.selector or {},
            endpoint_count=service.endpoint_count or 0,
            endpoints=service.endpoints or [],
            labels=service.labels or {},
            annotations=service.annotations or {},
            created_at=service.created_at,
            updated_at=service.updated_at
        )

    def _event_to_response(self, event: KubernetesEvent) -> K8sEventResponse:
        """Convert event model to response."""
        return K8sEventResponse(
            id=event.id,
            organization_id=event.organization_id,
            cluster_id=event.cluster_id,
            namespace_name=event.namespace_name,
            name=event.name,
            uid=event.uid,
            involved_kind=event.involved_kind,
            involved_name=event.involved_name,
            involved_uid=event.involved_uid,
            involved_namespace=event.involved_namespace,
            event_type=event.event_type,
            reason=event.reason,
            message=event.message,
            source_component=event.source_component,
            source_host=event.source_host,
            first_timestamp=event.first_timestamp,
            last_timestamp=event.last_timestamp,
            count=event.count or 1,
            created_at=event.created_at
        )


# Singleton instance
container_service = ContainerService()
