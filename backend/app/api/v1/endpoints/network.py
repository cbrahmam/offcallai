# backend/app/api/v1/endpoints/network.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID
from datetime import datetime

from app.database import get_db
from app.core.security import get_current_user
from app.core.deps import get_current_organization
from app.models.user import User
from app.models.organization import Organization
from app.services.network_service import NetworkService
from app.schemas.network import (
    NetworkDeviceCreate,
    NetworkDeviceUpdate,
    NetworkDeviceResponse,
    NetworkDeviceList,
    NetworkInterfaceCreate,
    NetworkInterfaceUpdate,
    NetworkInterfaceResponse,
    NetworkInterfaceList,
    NetworkFlowCreate,
    NetworkFlowResponse,
    NetworkFlowList,
    NetworkAlertResponse,
    NetworkAlertList,
    NetworkTopology,
    NetworkStats,
    DeviceOverview,
    DeviceMetricsIngest,
    FlowDataIngest,
)

router = APIRouter()


# ==================== Network Devices ====================

@router.get("/devices", response_model=NetworkDeviceList)
async def list_network_devices(
    device_type: Optional[str] = None,
    status: Optional[str] = None,
    location: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """List all network devices for the organization"""
    service = NetworkService(db)
    items, total = await service.list_devices(
        organization_id=organization.id,
        device_type=device_type,
        status=status,
        location=location,
        page=page,
        page_size=page_size,
    )
    return NetworkDeviceList(items=items, total=total, page=page, page_size=page_size)


@router.post("/devices", response_model=NetworkDeviceResponse)
async def create_network_device(
    device: NetworkDeviceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Create a new network device"""
    service = NetworkService(db)
    return await service.create_device(organization.id, device)


@router.get("/devices/{device_id}", response_model=NetworkDeviceResponse)
async def get_network_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get a specific network device"""
    service = NetworkService(db)
    device = await service.get_device(device_id, organization.id)
    if not device:
        raise HTTPException(status_code=404, detail="Network device not found")
    return device


@router.put("/devices/{device_id}", response_model=NetworkDeviceResponse)
async def update_network_device(
    device_id: UUID,
    device_update: NetworkDeviceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Update a network device"""
    service = NetworkService(db)
    device = await service.update_device(device_id, organization.id, device_update)
    if not device:
        raise HTTPException(status_code=404, detail="Network device not found")
    return device


@router.delete("/devices/{device_id}")
async def delete_network_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Delete a network device"""
    service = NetworkService(db)
    success = await service.delete_device(device_id, organization.id)
    if not success:
        raise HTTPException(status_code=404, detail="Network device not found")
    return {"status": "deleted"}


@router.get("/devices/{device_id}/overview", response_model=DeviceOverview)
async def get_device_overview(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get comprehensive overview for a device"""
    service = NetworkService(db)
    overview = await service.get_device_overview(device_id, organization.id)
    if not overview:
        raise HTTPException(status_code=404, detail="Network device not found")
    return overview


# ==================== Network Interfaces ====================

@router.get("/devices/{device_id}/interfaces", response_model=NetworkInterfaceList)
async def list_device_interfaces(
    device_id: UUID,
    oper_status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """List all interfaces for a network device"""
    service = NetworkService(db)
    return await service.list_interfaces(
        device_id=device_id,
        organization_id=organization.id,
        oper_status=oper_status,
    )


@router.post("/interfaces", response_model=NetworkInterfaceResponse)
async def create_network_interface(
    interface: NetworkInterfaceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Create a new network interface"""
    service = NetworkService(db)
    return await service.create_interface(organization.id, interface)


@router.get("/interfaces/{interface_id}", response_model=NetworkInterfaceResponse)
async def get_network_interface(
    interface_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get a specific network interface"""
    service = NetworkService(db)
    interface = await service.get_interface(interface_id, organization.id)
    if not interface:
        raise HTTPException(status_code=404, detail="Network interface not found")
    return interface


@router.put("/interfaces/{interface_id}", response_model=NetworkInterfaceResponse)
async def update_network_interface(
    interface_id: UUID,
    interface_update: NetworkInterfaceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Update a network interface"""
    service = NetworkService(db)
    interface = await service.update_interface(interface_id, organization.id, interface_update)
    if not interface:
        raise HTTPException(status_code=404, detail="Network interface not found")
    return interface


@router.delete("/interfaces/{interface_id}")
async def delete_network_interface(
    interface_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Delete a network interface"""
    service = NetworkService(db)
    success = await service.delete_interface(interface_id, organization.id)
    if not success:
        raise HTTPException(status_code=404, detail="Network interface not found")
    return {"status": "deleted"}


# ==================== Network Flows ====================

@router.get("/flows", response_model=NetworkFlowList)
async def list_network_flows(
    device_id: Optional[UUID] = None,
    interface_id: Optional[UUID] = None,
    src_ip: Optional[str] = None,
    dst_ip: Optional[str] = None,
    protocol: Optional[str] = None,
    application: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """List network flows"""
    service = NetworkService(db)
    result = await service.list_flows(
        organization_id=organization.id,
        device_id=device_id,
        interface_id=interface_id,
        src_ip=src_ip,
        dst_ip=dst_ip,
        protocol=protocol,
        application=application,
        start_time=start_time,
        end_time=end_time,
        page=page,
        page_size=page_size,
    )
    return NetworkFlowList(
        items=result["items"],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"]
    )


@router.get("/flows/{flow_id}", response_model=NetworkFlowResponse)
async def get_network_flow(
    flow_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get a specific network flow"""
    service = NetworkService(db)
    flow = await service.get_flow(flow_id, organization.id)
    if not flow:
        raise HTTPException(status_code=404, detail="Network flow not found")
    return flow


@router.get("/flows/top-talkers", response_model=list)
async def get_top_talkers(
    limit: int = Query(10, ge=1, le=50),
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get top traffic sources/destinations"""
    service = NetworkService(db)
    return await service.get_top_talkers(organization.id, limit=limit, hours=hours)


# ==================== Network Alerts ====================

@router.get("/alerts", response_model=NetworkAlertList)
async def list_network_alerts(
    device_id: Optional[UUID] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """List network alerts"""
    service = NetworkService(db)
    alerts, total = await service.list_alerts(
        organization_id=organization.id,
        device_id=device_id,
        severity=severity,
        status=status,
        page=page,
        page_size=page_size,
    )
    return NetworkAlertList(items=alerts, total=total, page=page, page_size=page_size)


@router.get("/alerts/{alert_id}", response_model=NetworkAlertResponse)
async def get_network_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get a specific network alert"""
    service = NetworkService(db)
    alert = await service.get_alert(alert_id, organization.id)
    if not alert:
        raise HTTPException(status_code=404, detail="Network alert not found")
    return alert


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_network_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Acknowledge a network alert"""
    service = NetworkService(db)
    alert = await service.acknowledge_alert(alert_id, organization.id, current_user.id)
    if not alert:
        raise HTTPException(status_code=404, detail="Network alert not found")
    return alert


@router.post("/alerts/{alert_id}/resolve")
async def resolve_network_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Resolve a network alert"""
    service = NetworkService(db)
    alert = await service.resolve_alert(alert_id, organization.id)
    if not alert:
        raise HTTPException(status_code=404, detail="Network alert not found")
    return alert


# ==================== Network Topology ====================

@router.get("/topology", response_model=NetworkTopology)
async def get_network_topology(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get network topology (devices and links)"""
    service = NetworkService(db)
    devices, links = await service.get_topology(organization.id)
    return NetworkTopology(devices=devices, links=links)


@router.post("/topology/discover")
async def discover_topology(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Trigger topology discovery"""
    service = NetworkService(db)
    await service.discover_topology(organization.id)
    return {"status": "discovery_started"}


# ==================== Statistics ====================

@router.get("/stats", response_model=NetworkStats)
async def get_network_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Get network monitoring statistics"""
    service = NetworkService(db)
    return await service.get_stats(organization.id)


# ==================== Data Ingestion ====================

@router.post("/ingest/device-metrics")
async def ingest_device_metrics(
    metrics: DeviceMetricsIngest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Ingest device metrics from monitoring agent"""
    service = NetworkService(db)
    await service.ingest_device_metrics(organization.id, metrics)
    return {"status": "ingested"}


@router.post("/ingest/flows")
async def ingest_flow_data(
    flow_data: FlowDataIngest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Ingest flow data (NetFlow/sFlow/IPFIX)"""
    service = NetworkService(db)
    await service.ingest_flow_data(organization.id, flow_data)
    return {"status": "ingested", "flow_count": len(flow_data.flows)}


# ==================== Polling ====================

@router.post("/devices/{device_id}/poll")
async def poll_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
):
    """Manually trigger polling for a device"""
    service = NetworkService(db)
    device = await service.get_device(device_id, organization.id)
    if not device:
        raise HTTPException(status_code=404, detail="Network device not found")

    await service.poll_device(device_id, organization.id)
    return {"status": "poll_triggered"}
