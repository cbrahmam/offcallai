# backend/app/services/network_service.py
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload

from ..models.network import (
    NetworkDevice, NetworkInterface, NetworkMetricSnapshot,
    NetworkFlow, NetworkAlert, NetworkTopologyLink
)
from ..schemas.network import (
    NetworkDeviceCreate, NetworkDeviceUpdate,
    NetworkInterfaceCreate, NetworkInterfaceUpdate,
    NetworkMetricSnapshotCreate, NetworkFlowCreate,
    DeviceMetricsIngest, NetworkStats
)


class NetworkService:
    """Service for managing network monitoring"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== Device CRUD ====================

    async def create_device(
        self,
        organization_id: uuid.UUID,
        data: NetworkDeviceCreate
    ) -> NetworkDevice:
        """Create a new network device"""
        device = NetworkDevice(
            id=uuid.uuid4(),
            organization_id=organization_id,
            **data.model_dump()
        )
        self.db.add(device)
        await self.db.commit()
        await self.db.refresh(device)
        return device

    async def get_device(
        self,
        organization_id: uuid.UUID,
        device_id: uuid.UUID
    ) -> Optional[NetworkDevice]:
        """Get a network device by ID"""
        result = await self.db.execute(
            select(NetworkDevice).where(
                and_(
                    NetworkDevice.organization_id == organization_id,
                    NetworkDevice.id == device_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_device_by_ip(
        self,
        organization_id: uuid.UUID,
        ip_address: str
    ) -> Optional[NetworkDevice]:
        """Get a network device by management IP"""
        result = await self.db.execute(
            select(NetworkDevice).where(
                and_(
                    NetworkDevice.organization_id == organization_id,
                    NetworkDevice.management_ip == ip_address
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_devices(
        self,
        organization_id: uuid.UUID,
        device_type: Optional[str] = None,
        status: Optional[str] = None,
        location: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[List[NetworkDevice], int]:
        """List network devices with filters"""
        query = select(NetworkDevice).where(
            NetworkDevice.organization_id == organization_id
        )

        if device_type:
            query = query.where(NetworkDevice.device_type == device_type)
        if status:
            query = query.where(NetworkDevice.status == status)
        if location:
            query = query.where(NetworkDevice.location.ilike(f"%{location}%"))

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()

        query = query.order_by(NetworkDevice.name)
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def update_device(
        self,
        organization_id: uuid.UUID,
        device_id: uuid.UUID,
        data: NetworkDeviceUpdate
    ) -> Optional[NetworkDevice]:
        """Update a network device"""
        device = await self.get_device(organization_id, device_id)
        if not device:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(device, key, value)

        device.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(device)
        return device

    async def delete_device(
        self,
        organization_id: uuid.UUID,
        device_id: uuid.UUID
    ) -> bool:
        """Delete a network device"""
        device = await self.get_device(organization_id, device_id)
        if not device:
            return False

        await self.db.delete(device)
        await self.db.commit()
        return True

    # ==================== Interface CRUD ====================

    async def create_interface(
        self,
        organization_id: uuid.UUID,
        data: NetworkInterfaceCreate
    ) -> NetworkInterface:
        """Create a new network interface"""
        interface = NetworkInterface(
            id=uuid.uuid4(),
            organization_id=organization_id,
            **data.model_dump()
        )
        self.db.add(interface)

        # Update device interface count
        device = await self.get_device(organization_id, data.device_id)
        if device:
            device.interface_count = (device.interface_count or 0) + 1

        await self.db.commit()
        await self.db.refresh(interface)
        return interface

    async def get_interface(
        self,
        organization_id: uuid.UUID,
        interface_id: uuid.UUID
    ) -> Optional[NetworkInterface]:
        """Get a network interface by ID"""
        result = await self.db.execute(
            select(NetworkInterface).where(
                and_(
                    NetworkInterface.organization_id == organization_id,
                    NetworkInterface.id == interface_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_interfaces(
        self,
        organization_id: uuid.UUID,
        device_id: Optional[uuid.UUID] = None,
        oper_status: Optional[str] = None
    ) -> Tuple[List[NetworkInterface], int]:
        """List network interfaces"""
        query = select(NetworkInterface).where(
            NetworkInterface.organization_id == organization_id
        )

        if device_id:
            query = query.where(NetworkInterface.device_id == device_id)
        if oper_status:
            query = query.where(NetworkInterface.oper_status == oper_status)

        query = query.order_by(NetworkInterface.name)
        result = await self.db.execute(query)
        interfaces = result.scalars().all()
        return interfaces, len(interfaces)

    async def update_interface(
        self,
        organization_id: uuid.UUID,
        interface_id: uuid.UUID,
        data: NetworkInterfaceUpdate
    ) -> Optional[NetworkInterface]:
        """Update a network interface"""
        interface = await self.get_interface(organization_id, interface_id)
        if not interface:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(interface, key, value)

        interface.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(interface)
        return interface

    # ==================== Metrics ====================

    async def record_metrics(
        self,
        organization_id: uuid.UUID,
        data: NetworkMetricSnapshotCreate
    ) -> NetworkMetricSnapshot:
        """Record a metric snapshot"""
        snapshot = NetworkMetricSnapshot(
            id=uuid.uuid4(),
            organization_id=organization_id,
            **data.model_dump()
        )
        self.db.add(snapshot)
        await self.db.commit()
        await self.db.refresh(snapshot)
        return snapshot

    async def get_device_metrics(
        self,
        organization_id: uuid.UUID,
        device_id: uuid.UUID,
        interface_id: Optional[uuid.UUID] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100
    ) -> List[NetworkMetricSnapshot]:
        """Get metric snapshots for a device or interface"""
        query = select(NetworkMetricSnapshot).where(
            and_(
                NetworkMetricSnapshot.organization_id == organization_id,
                NetworkMetricSnapshot.device_id == device_id
            )
        )

        if interface_id:
            query = query.where(NetworkMetricSnapshot.interface_id == interface_id)
        if since:
            query = query.where(NetworkMetricSnapshot.timestamp >= since)
        if until:
            query = query.where(NetworkMetricSnapshot.timestamp <= until)

        query = query.order_by(desc(NetworkMetricSnapshot.timestamp)).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    # ==================== Flows ====================

    async def record_flow(
        self,
        organization_id: uuid.UUID,
        data: NetworkFlowCreate
    ) -> NetworkFlow:
        """Record a network flow"""
        flow = NetworkFlow(
            id=uuid.uuid4(),
            organization_id=organization_id,
            **data.model_dump()
        )
        self.db.add(flow)
        await self.db.commit()
        await self.db.refresh(flow)
        return flow

    async def list_flows(
        self,
        organization_id: uuid.UUID,
        device_id: Optional[uuid.UUID] = None,
        interface_id: Optional[uuid.UUID] = None,
        src_ip: Optional[str] = None,
        dst_ip: Optional[str] = None,
        protocol: Optional[str] = None,
        application: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        since: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """List network flows"""
        query = select(NetworkFlow).where(
            NetworkFlow.organization_id == organization_id
        )

        if device_id:
            query = query.where(NetworkFlow.device_id == device_id)
        if interface_id:
            query = query.where(NetworkFlow.interface_id == interface_id)
        if src_ip:
            query = query.where(NetworkFlow.src_ip == src_ip)
        if dst_ip:
            query = query.where(NetworkFlow.dst_ip == dst_ip)
        if protocol:
            query = query.where(NetworkFlow.protocol == protocol)
        if application:
            query = query.where(NetworkFlow.application == application)
        if start_time:
            query = query.where(NetworkFlow.flow_start >= start_time)
        if end_time:
            query = query.where(NetworkFlow.flow_start <= end_time)
        if since:
            query = query.where(NetworkFlow.flow_start >= since)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(desc(NetworkFlow.flow_start))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        flows = result.scalars().all()

        return {
            "items": flows,
            "total": total,
            "page": page,
            "page_size": page_size
        }

    # ==================== Alerts ====================

    async def list_alerts(
        self,
        organization_id: uuid.UUID,
        device_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[List[NetworkAlert], int]:
        """List network alerts"""
        query = select(NetworkAlert).where(
            NetworkAlert.organization_id == organization_id
        )

        if device_id:
            query = query.where(NetworkAlert.device_id == device_id)
        if status:
            query = query.where(NetworkAlert.status == status)
        if severity:
            query = query.where(NetworkAlert.severity == severity)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()

        query = query.order_by(desc(NetworkAlert.triggered_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def acknowledge_alert(
        self,
        organization_id: uuid.UUID,
        alert_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> Optional[NetworkAlert]:
        """Acknowledge a network alert"""
        result = await self.db.execute(
            select(NetworkAlert).where(
                and_(
                    NetworkAlert.organization_id == organization_id,
                    NetworkAlert.id == alert_id
                )
            )
        )
        alert = result.scalar_one_or_none()
        if not alert:
            return None

        alert.status = "acknowledged"
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = user_id
        await self.db.commit()
        await self.db.refresh(alert)
        return alert

    async def resolve_alert(
        self,
        organization_id: uuid.UUID,
        alert_id: uuid.UUID
    ) -> Optional[NetworkAlert]:
        """Resolve a network alert"""
        result = await self.db.execute(
            select(NetworkAlert).where(
                and_(
                    NetworkAlert.organization_id == organization_id,
                    NetworkAlert.id == alert_id
                )
            )
        )
        alert = result.scalar_one_or_none()
        if not alert:
            return None

        alert.status = "resolved"
        alert.resolved_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(alert)
        return alert

    # ==================== Topology ====================

    async def get_topology(
        self,
        organization_id: uuid.UUID
    ) -> Tuple[List[NetworkDevice], List[NetworkTopologyLink]]:
        """Get network topology (devices and links)"""
        devices_result = await self.db.execute(
            select(NetworkDevice).where(
                NetworkDevice.organization_id == organization_id
            ).order_by(NetworkDevice.name)
        )
        devices = devices_result.scalars().all()

        links_result = await self.db.execute(
            select(NetworkTopologyLink).where(
                NetworkTopologyLink.organization_id == organization_id
            )
        )
        links = links_result.scalars().all()

        return devices, links

    # ==================== Data Ingestion ====================

    async def ingest_device_metrics(
        self,
        organization_id: uuid.UUID,
        data: DeviceMetricsIngest
    ) -> NetworkDevice:
        """Ingest metrics from monitoring agent"""
        # Find or create device
        device = await self.get_device_by_ip(organization_id, data.device_identifier)
        if not device:
            # Try by name
            result = await self.db.execute(
                select(NetworkDevice).where(
                    and_(
                        NetworkDevice.organization_id == organization_id,
                        NetworkDevice.name == data.device_identifier
                    )
                )
            )
            device = result.scalar_one_or_none()

        if not device:
            raise ValueError(f"Device not found: {data.device_identifier}")

        # Update device metrics
        device.last_poll = data.timestamp
        device.last_poll_success = data.timestamp
        device.last_seen = data.timestamp

        if data.cpu_utilization is not None:
            device.cpu_utilization = data.cpu_utilization
        if data.memory_utilization is not None:
            device.memory_utilization = data.memory_utilization
        if data.memory_total_bytes is not None:
            device.memory_total_bytes = data.memory_total_bytes
        if data.memory_used_bytes is not None:
            device.memory_used_bytes = data.memory_used_bytes
        if data.uptime_seconds is not None:
            device.uptime_seconds = data.uptime_seconds
        if data.temperature_celsius is not None:
            device.temperature_celsius = data.temperature_celsius

        device.status = "up"

        # Record device-level metrics
        await self.record_metrics(organization_id, NetworkMetricSnapshotCreate(
            device_id=device.id,
            timestamp=data.timestamp,
            cpu_utilization=data.cpu_utilization,
            memory_utilization=data.memory_utilization,
            temperature_celsius=data.temperature_celsius
        ))

        # Update interfaces
        interfaces_up = 0
        interfaces_down = 0

        for if_data in data.interfaces:
            interface = None
            if if_data.get("name"):
                result = await self.db.execute(
                    select(NetworkInterface).where(
                        and_(
                            NetworkInterface.device_id == device.id,
                            NetworkInterface.name == if_data["name"]
                        )
                    )
                )
                interface = result.scalar_one_or_none()

            if interface:
                # Update interface
                if if_data.get("oper_status"):
                    old_status = interface.oper_status
                    interface.oper_status = if_data["oper_status"]
                    if old_status != if_data["oper_status"]:
                        interface.last_status_change = data.timestamp

                if if_data.get("bytes_in") is not None:
                    interface.bytes_in = if_data["bytes_in"]
                if if_data.get("bytes_out") is not None:
                    interface.bytes_out = if_data["bytes_out"]
                if if_data.get("packets_in") is not None:
                    interface.packets_in = if_data["packets_in"]
                if if_data.get("packets_out") is not None:
                    interface.packets_out = if_data["packets_out"]
                if if_data.get("errors_in") is not None:
                    interface.errors_in = if_data["errors_in"]
                if if_data.get("errors_out") is not None:
                    interface.errors_out = if_data["errors_out"]
                if if_data.get("utilization_in_percent") is not None:
                    interface.utilization_in_percent = if_data["utilization_in_percent"]
                if if_data.get("utilization_out_percent") is not None:
                    interface.utilization_out_percent = if_data["utilization_out_percent"]
                if if_data.get("bandwidth_in_bps") is not None:
                    interface.bandwidth_in_bps = if_data["bandwidth_in_bps"]
                if if_data.get("bandwidth_out_bps") is not None:
                    interface.bandwidth_out_bps = if_data["bandwidth_out_bps"]

                interface.last_poll = data.timestamp

                if interface.oper_status == "up":
                    interfaces_up += 1
                else:
                    interfaces_down += 1

        device.interfaces_up = interfaces_up
        device.interfaces_down = interfaces_down

        await self.db.commit()
        await self.db.refresh(device)
        return device

    # ==================== Statistics ====================

    async def get_stats(self, organization_id: uuid.UUID) -> NetworkStats:
        """Get network monitoring statistics"""
        # Device counts
        total_result = await self.db.execute(
            select(func.count()).where(NetworkDevice.organization_id == organization_id)
        )
        total_devices = total_result.scalar()

        up_result = await self.db.execute(
            select(func.count()).where(
                and_(
                    NetworkDevice.organization_id == organization_id,
                    NetworkDevice.status == "up"
                )
            )
        )
        devices_up = up_result.scalar()

        down_result = await self.db.execute(
            select(func.count()).where(
                and_(
                    NetworkDevice.organization_id == organization_id,
                    NetworkDevice.status == "down"
                )
            )
        )
        devices_down = down_result.scalar()

        degraded_result = await self.db.execute(
            select(func.count()).where(
                and_(
                    NetworkDevice.organization_id == organization_id,
                    NetworkDevice.status == "degraded"
                )
            )
        )
        devices_degraded = degraded_result.scalar()

        # Interface counts
        total_if_result = await self.db.execute(
            select(func.count()).where(NetworkInterface.organization_id == organization_id)
        )
        total_interfaces = total_if_result.scalar()

        if_up_result = await self.db.execute(
            select(func.count()).where(
                and_(
                    NetworkInterface.organization_id == organization_id,
                    NetworkInterface.oper_status == "up"
                )
            )
        )
        interfaces_up = if_up_result.scalar()

        if_down_result = await self.db.execute(
            select(func.count()).where(
                and_(
                    NetworkInterface.organization_id == organization_id,
                    NetworkInterface.oper_status == "down"
                )
            )
        )
        interfaces_down = if_down_result.scalar()

        # Total bandwidth
        bw_result = await self.db.execute(
            select(
                func.sum(NetworkInterface.bandwidth_in_bps),
                func.sum(NetworkInterface.bandwidth_out_bps)
            ).where(NetworkInterface.organization_id == organization_id)
        )
        bw_row = bw_result.one()
        total_bandwidth_in = bw_row[0] or 0
        total_bandwidth_out = bw_row[1] or 0

        # Average CPU/Memory
        avg_result = await self.db.execute(
            select(
                func.avg(NetworkDevice.cpu_utilization),
                func.avg(NetworkDevice.memory_utilization)
            ).where(
                and_(
                    NetworkDevice.organization_id == organization_id,
                    NetworkDevice.cpu_utilization.isnot(None)
                )
            )
        )
        avg_row = avg_result.one()
        avg_cpu = avg_row[0] or 0
        avg_memory = avg_row[1] or 0

        # Active alerts
        alerts_result = await self.db.execute(
            select(func.count()).where(
                and_(
                    NetworkAlert.organization_id == organization_id,
                    NetworkAlert.status == "active"
                )
            )
        )
        active_alerts = alerts_result.scalar()

        return NetworkStats(
            total_devices=total_devices,
            devices_up=devices_up,
            devices_down=devices_down,
            devices_degraded=devices_degraded,
            total_interfaces=total_interfaces,
            interfaces_up=interfaces_up,
            interfaces_down=interfaces_down,
            total_bandwidth_in_bps=int(total_bandwidth_in),
            total_bandwidth_out_bps=int(total_bandwidth_out),
            avg_cpu_utilization=float(avg_cpu),
            avg_memory_utilization=float(avg_memory),
            active_alerts=active_alerts,
            devices_by_type={},
            top_talkers=[]
        )
