# backend/app/schemas/network.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


# Enums
class NetworkDeviceType(str, Enum):
    ROUTER = "router"
    SWITCH = "switch"
    FIREWALL = "firewall"
    LOAD_BALANCER = "load_balancer"
    ACCESS_POINT = "access_point"
    VPN_GATEWAY = "vpn_gateway"
    PROXY = "proxy"
    DNS_SERVER = "dns_server"
    DHCP_SERVER = "dhcp_server"
    OTHER = "other"


class DeviceStatus(str, Enum):
    UP = "up"
    DOWN = "down"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


# ==================== Network Device Schemas ====================

class NetworkDeviceBase(BaseModel):
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    device_type: str
    vendor: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    firmware_version: Optional[str] = None
    os_version: Optional[str] = None
    management_ip: Optional[str] = None
    management_port: Optional[int] = None
    mac_address: Optional[str] = None
    location: Optional[str] = None
    rack: Optional[str] = None
    rack_position: Optional[int] = None
    snmp_enabled: bool = False
    snmp_version: Optional[str] = None
    snmp_community: Optional[str] = None
    snmp_port: int = 161
    poll_interval_seconds: int = 300
    alert_on_down: bool = True
    alert_on_high_cpu: bool = True
    cpu_threshold_warning: float = 70.0
    cpu_threshold_critical: float = 90.0
    alert_on_high_memory: bool = True
    memory_threshold_warning: float = 80.0
    memory_threshold_critical: float = 95.0
    tags: List[str] = Field(default_factory=list)
    labels: Dict[str, str] = Field(default_factory=dict)


class NetworkDeviceCreate(NetworkDeviceBase):
    pass


class NetworkDeviceUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    device_type: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    management_ip: Optional[str] = None
    management_port: Optional[int] = None
    location: Optional[str] = None
    snmp_enabled: Optional[bool] = None
    snmp_version: Optional[str] = None
    snmp_community: Optional[str] = None
    snmp_port: Optional[int] = None
    poll_interval_seconds: Optional[int] = None
    alert_on_down: Optional[bool] = None
    alert_on_high_cpu: Optional[bool] = None
    cpu_threshold_warning: Optional[float] = None
    cpu_threshold_critical: Optional[float] = None
    alert_on_high_memory: Optional[bool] = None
    memory_threshold_warning: Optional[float] = None
    memory_threshold_critical: Optional[float] = None
    tags: Optional[List[str]] = None
    labels: Optional[Dict[str, str]] = None


class NetworkDeviceResponse(NetworkDeviceBase):
    id: UUID
    organization_id: UUID
    host_id: Optional[UUID] = None
    status: str = "unknown"
    last_seen: Optional[datetime] = None
    last_poll: Optional[datetime] = None
    last_poll_success: Optional[datetime] = None
    cpu_utilization: Optional[float] = None
    memory_utilization: Optional[float] = None
    memory_total_bytes: Optional[int] = None
    memory_used_bytes: Optional[int] = None
    uptime_seconds: Optional[int] = None
    temperature_celsius: Optional[float] = None
    interface_count: int = 0
    interfaces_up: int = 0
    interfaces_down: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NetworkDeviceList(BaseModel):
    items: List[NetworkDeviceResponse]
    total: int
    page: int
    page_size: int


# ==================== Network Interface Schemas ====================

class NetworkInterfaceBase(BaseModel):
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    if_index: Optional[int] = None
    if_type: Optional[str] = None
    mac_address: Optional[str] = None
    ip_address: Optional[str] = None
    subnet_mask: Optional[str] = None
    ipv6_address: Optional[str] = None
    speed_mbps: Optional[int] = None
    duplex: Optional[str] = None
    mtu: Optional[int] = None
    admin_status: str = "up"
    alert_on_down: bool = True
    alert_on_errors: bool = True
    error_threshold_percent: float = 1.0
    alert_on_high_utilization: bool = True
    utilization_threshold_warning: float = 70.0
    utilization_threshold_critical: float = 90.0
    tags: List[str] = Field(default_factory=list)


class NetworkInterfaceCreate(NetworkInterfaceBase):
    device_id: UUID


class NetworkInterfaceUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    admin_status: Optional[str] = None
    alert_on_down: Optional[bool] = None
    alert_on_errors: Optional[bool] = None
    error_threshold_percent: Optional[float] = None
    alert_on_high_utilization: Optional[bool] = None
    utilization_threshold_warning: Optional[float] = None
    utilization_threshold_critical: Optional[float] = None
    tags: Optional[List[str]] = None


class NetworkInterfaceResponse(NetworkInterfaceBase):
    id: UUID
    organization_id: UUID
    device_id: UUID
    oper_status: str = "unknown"
    actual_speed_mbps: Optional[int] = None
    last_status_change: Optional[datetime] = None
    bytes_in: int = 0
    bytes_out: int = 0
    packets_in: int = 0
    packets_out: int = 0
    errors_in: int = 0
    errors_out: int = 0
    discards_in: int = 0
    discards_out: int = 0
    utilization_in_percent: Optional[float] = None
    utilization_out_percent: Optional[float] = None
    bandwidth_in_bps: Optional[int] = None
    bandwidth_out_bps: Optional[int] = None
    connected_device_name: Optional[str] = None
    connected_interface_name: Optional[str] = None
    last_poll: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NetworkInterfaceList(BaseModel):
    items: List[NetworkInterfaceResponse]
    total: int


# ==================== Network Metrics Schemas ====================

class NetworkMetricSnapshotCreate(BaseModel):
    device_id: UUID
    interface_id: Optional[UUID] = None
    timestamp: datetime
    cpu_utilization: Optional[float] = None
    memory_utilization: Optional[float] = None
    temperature_celsius: Optional[float] = None
    bytes_in: Optional[int] = None
    bytes_out: Optional[int] = None
    packets_in: Optional[int] = None
    packets_out: Optional[int] = None
    errors_in: Optional[int] = None
    errors_out: Optional[int] = None
    bits_per_second_in: Optional[int] = None
    bits_per_second_out: Optional[int] = None
    utilization_in_percent: Optional[float] = None
    utilization_out_percent: Optional[float] = None


class NetworkMetricSnapshotResponse(BaseModel):
    id: UUID
    organization_id: UUID
    device_id: UUID
    interface_id: Optional[UUID] = None
    timestamp: datetime
    cpu_utilization: Optional[float] = None
    memory_utilization: Optional[float] = None
    temperature_celsius: Optional[float] = None
    bytes_in: Optional[int] = None
    bytes_out: Optional[int] = None
    packets_in: Optional[int] = None
    packets_out: Optional[int] = None
    errors_in: Optional[int] = None
    errors_out: Optional[int] = None
    bits_per_second_in: Optional[int] = None
    bits_per_second_out: Optional[int] = None
    utilization_in_percent: Optional[float] = None
    utilization_out_percent: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== Network Flow Schemas ====================

class NetworkFlowCreate(BaseModel):
    device_id: Optional[UUID] = None
    interface_id: Optional[UUID] = None
    flow_start: datetime
    flow_end: Optional[datetime] = None
    duration_ms: Optional[int] = None
    src_ip: str
    src_port: Optional[int] = None
    dst_ip: str
    dst_port: Optional[int] = None
    protocol: Optional[int] = None
    protocol_name: Optional[str] = None
    bytes_total: Optional[int] = None
    packets_total: Optional[int] = None
    application: Optional[str] = None
    direction: Optional[str] = None


class NetworkFlowResponse(BaseModel):
    id: UUID
    organization_id: UUID
    device_id: Optional[UUID] = None
    interface_id: Optional[UUID] = None
    flow_start: datetime
    flow_end: Optional[datetime] = None
    duration_ms: Optional[int] = None
    src_ip: str
    src_port: Optional[int] = None
    dst_ip: str
    dst_port: Optional[int] = None
    protocol: Optional[int] = None
    protocol_name: Optional[str] = None
    bytes_total: Optional[int] = None
    packets_total: Optional[int] = None
    bytes_per_second: Optional[float] = None
    application: Optional[str] = None
    application_category: Optional[str] = None
    direction: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class NetworkFlowList(BaseModel):
    items: List[NetworkFlowResponse]
    total: int
    page: int
    page_size: int


# ==================== Network Alert Schemas ====================

class NetworkAlertResponse(BaseModel):
    id: UUID
    organization_id: UUID
    device_id: Optional[UUID] = None
    interface_id: Optional[UUID] = None
    alert_type: str
    severity: str
    status: str
    title: str
    message: Optional[str] = None
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold_value: Optional[float] = None
    triggered_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[UUID] = None
    resolved_at: Optional[datetime] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True


class NetworkAlertList(BaseModel):
    items: List[NetworkAlertResponse]
    total: int
    page: int
    page_size: int


# ==================== Topology Schemas ====================

class TopologyLinkResponse(BaseModel):
    id: UUID
    organization_id: UUID
    source_device_id: UUID
    source_interface_id: Optional[UUID] = None
    target_device_id: UUID
    target_interface_id: Optional[UUID] = None
    link_type: Optional[str] = None
    speed_mbps: Optional[int] = None
    status: str = "unknown"
    latency_ms: Optional[float] = None
    packet_loss_percent: Optional[float] = None
    discovery_method: Optional[str] = None
    discovered_at: Optional[datetime] = None
    last_seen: Optional[datetime] = None

    class Config:
        from_attributes = True


class NetworkTopology(BaseModel):
    devices: List[NetworkDeviceResponse]
    links: List[TopologyLinkResponse]


# ==================== Statistics Schemas ====================

class NetworkStats(BaseModel):
    total_devices: int
    devices_up: int
    devices_down: int
    devices_degraded: int
    total_interfaces: int
    interfaces_up: int
    interfaces_down: int
    total_bandwidth_in_bps: int
    total_bandwidth_out_bps: int
    avg_cpu_utilization: float
    avg_memory_utilization: float
    active_alerts: int
    devices_by_type: Dict[str, int] = Field(default_factory=dict)
    top_talkers: List[Dict[str, Any]] = Field(default_factory=list)


class DeviceOverview(BaseModel):
    device: NetworkDeviceResponse
    interfaces: List[NetworkInterfaceResponse] = Field(default_factory=list)
    recent_metrics: List[NetworkMetricSnapshotResponse] = Field(default_factory=list)
    active_alerts: List[NetworkAlertResponse] = Field(default_factory=list)


# ==================== Data Ingestion Schemas ====================

class DeviceMetricsIngest(BaseModel):
    """Schema for ingesting device metrics from monitoring agent"""
    device_identifier: str  # IP or name
    timestamp: datetime
    cpu_utilization: Optional[float] = None
    memory_utilization: Optional[float] = None
    memory_total_bytes: Optional[int] = None
    memory_used_bytes: Optional[int] = None
    uptime_seconds: Optional[int] = None
    temperature_celsius: Optional[float] = None
    interfaces: List[Dict[str, Any]] = Field(default_factory=list)
    # Each interface: {name, oper_status, bytes_in, bytes_out, errors_in, errors_out, ...}


class FlowDataIngest(BaseModel):
    """Schema for ingesting flow data"""
    exporter_ip: str
    flows: List[NetworkFlowCreate]
