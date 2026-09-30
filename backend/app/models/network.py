# backend/app/models/network.py
import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET, MACADDR
from sqlalchemy.orm import relationship
from app.database import Base


class NetworkDeviceType(str, enum.Enum):
    """Types of network devices"""
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


class DeviceStatus(str, enum.Enum):
    """Status of a network device"""
    UP = "up"
    DOWN = "down"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class InterfaceStatus(str, enum.Enum):
    """Status of a network interface"""
    UP = "up"
    DOWN = "down"
    ADMIN_DOWN = "admin_down"
    UNKNOWN = "unknown"


class NetworkDevice(Base):
    """Network device (router, switch, firewall, etc.)"""
    __tablename__ = "network_devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    host_id = Column(UUID(as_uuid=True), ForeignKey("hosts.id", ondelete="SET NULL"))

    # Device identification
    name = Column(String(255), nullable=False)
    display_name = Column(String(255))
    description = Column(Text)
    device_type = Column(String(30), nullable=False, index=True)
    vendor = Column(String(100))
    model = Column(String(100))
    serial_number = Column(String(100))
    firmware_version = Column(String(100))
    os_version = Column(String(100))

    # Network addressing
    management_ip = Column(String(45), index=True)  # IPv4 or IPv6
    management_port = Column(Integer)
    mac_address = Column(String(17))
    location = Column(String(255))
    rack = Column(String(50))
    rack_position = Column(Integer)

    # SNMP configuration
    snmp_enabled = Column(Boolean, default=False)
    snmp_version = Column(String(10))  # v1, v2c, v3
    snmp_community = Column(String(100))  # For v1/v2c (encrypted in production)
    snmp_port = Column(Integer, default=161)
    snmp_auth_protocol = Column(String(10))  # For v3: MD5, SHA
    snmp_priv_protocol = Column(String(10))  # For v3: DES, AES

    # Status tracking
    status = Column(String(20), default="unknown", index=True)
    last_seen = Column(DateTime(timezone=True))
    last_poll = Column(DateTime(timezone=True))
    last_poll_success = Column(DateTime(timezone=True))
    poll_interval_seconds = Column(Integer, default=300)

    # Performance metrics
    cpu_utilization = Column(Float)
    memory_utilization = Column(Float)
    memory_total_bytes = Column(BigInteger)
    memory_used_bytes = Column(BigInteger)
    uptime_seconds = Column(BigInteger)
    temperature_celsius = Column(Float)

    # Counts
    interface_count = Column(Integer, default=0)
    interfaces_up = Column(Integer, default=0)
    interfaces_down = Column(Integer, default=0)

    # Alerting
    alert_on_down = Column(Boolean, default=True)
    alert_on_high_cpu = Column(Boolean, default=True)
    cpu_threshold_warning = Column(Float, default=70.0)
    cpu_threshold_critical = Column(Float, default=90.0)
    alert_on_high_memory = Column(Boolean, default=True)
    memory_threshold_warning = Column(Float, default=80.0)
    memory_threshold_critical = Column(Float, default=95.0)

    # Metadata
    tags = Column(JSONB, default=list)
    labels = Column(JSONB, default=dict)
    extra_data = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", backref="network_devices")
    interfaces = relationship("NetworkInterface", back_populates="device", cascade="all, delete-orphan", foreign_keys="[NetworkInterface.device_id]")


class NetworkInterface(Base):
    """Network interface on a device"""
    __tablename__ = "network_interfaces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(UUID(as_uuid=True), ForeignKey("network_devices.id", ondelete="CASCADE"), nullable=False, index=True)

    # Interface identification
    name = Column(String(100), nullable=False)
    display_name = Column(String(255))
    description = Column(Text)
    if_index = Column(Integer)  # SNMP ifIndex
    if_type = Column(String(50))  # ethernet, loopback, vlan, tunnel, etc.
    mac_address = Column(String(17))

    # IP addressing
    ip_address = Column(String(45))
    subnet_mask = Column(String(45))
    ipv6_address = Column(String(45))

    # Speed and duplex
    speed_mbps = Column(BigInteger)  # Configured speed
    actual_speed_mbps = Column(BigInteger)  # Negotiated speed
    duplex = Column(String(10))  # full, half, auto
    mtu = Column(Integer)

    # Status
    admin_status = Column(String(20), default="up")  # Configured state
    oper_status = Column(String(20), default="unknown", index=True)  # Actual state
    last_status_change = Column(DateTime(timezone=True))

    # Traffic counters (current values)
    bytes_in = Column(BigInteger, default=0)
    bytes_out = Column(BigInteger, default=0)
    packets_in = Column(BigInteger, default=0)
    packets_out = Column(BigInteger, default=0)
    errors_in = Column(BigInteger, default=0)
    errors_out = Column(BigInteger, default=0)
    discards_in = Column(BigInteger, default=0)
    discards_out = Column(BigInteger, default=0)
    unicast_in = Column(BigInteger, default=0)
    unicast_out = Column(BigInteger, default=0)
    multicast_in = Column(BigInteger, default=0)
    multicast_out = Column(BigInteger, default=0)
    broadcast_in = Column(BigInteger, default=0)
    broadcast_out = Column(BigInteger, default=0)

    # Utilization (calculated)
    utilization_in_percent = Column(Float)
    utilization_out_percent = Column(Float)
    bandwidth_in_bps = Column(BigInteger)
    bandwidth_out_bps = Column(BigInteger)

    # Connected device (for topology)
    connected_device_id = Column(UUID(as_uuid=True), ForeignKey("network_devices.id", ondelete="SET NULL"))
    connected_interface_id = Column(UUID(as_uuid=True))
    connected_device_name = Column(String(255))
    connected_interface_name = Column(String(100))

    # Alerting
    alert_on_down = Column(Boolean, default=True)
    alert_on_errors = Column(Boolean, default=True)
    error_threshold_percent = Column(Float, default=1.0)
    alert_on_high_utilization = Column(Boolean, default=True)
    utilization_threshold_warning = Column(Float, default=70.0)
    utilization_threshold_critical = Column(Float, default=90.0)

    # Metadata
    tags = Column(JSONB, default=list)
    last_poll = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", backref="network_interfaces")
    device = relationship("NetworkDevice", back_populates="interfaces", foreign_keys=[device_id])


class NetworkMetricSnapshot(Base):
    """Point-in-time metrics for network interfaces"""
    __tablename__ = "network_metric_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(UUID(as_uuid=True), ForeignKey("network_devices.id", ondelete="CASCADE"), nullable=False, index=True)
    interface_id = Column(UUID(as_uuid=True), ForeignKey("network_interfaces.id", ondelete="CASCADE"), index=True)

    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    # Device-level metrics (if interface_id is null)
    cpu_utilization = Column(Float)
    memory_utilization = Column(Float)
    temperature_celsius = Column(Float)

    # Interface-level metrics
    bytes_in = Column(BigInteger)
    bytes_out = Column(BigInteger)
    packets_in = Column(BigInteger)
    packets_out = Column(BigInteger)
    errors_in = Column(BigInteger)
    errors_out = Column(BigInteger)
    discards_in = Column(BigInteger)
    discards_out = Column(BigInteger)

    # Calculated rates (per second)
    bits_per_second_in = Column(BigInteger)
    bits_per_second_out = Column(BigInteger)
    packets_per_second_in = Column(BigInteger)
    packets_per_second_out = Column(BigInteger)
    error_rate_in = Column(Float)
    error_rate_out = Column(Float)

    # Utilization
    utilization_in_percent = Column(Float)
    utilization_out_percent = Column(Float)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", backref="network_metric_snapshots")


class NetworkFlow(Base):
    """Network traffic flow records (NetFlow/sFlow/IPFIX style)"""
    __tablename__ = "network_flows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(UUID(as_uuid=True), ForeignKey("network_devices.id", ondelete="CASCADE"), index=True)
    interface_id = Column(UUID(as_uuid=True), ForeignKey("network_interfaces.id", ondelete="CASCADE"), index=True)

    # Flow timing
    flow_start = Column(DateTime(timezone=True), nullable=False, index=True)
    flow_end = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)

    # Source
    src_ip = Column(String(45), index=True)
    src_port = Column(Integer)
    src_mac = Column(String(17))
    src_as = Column(Integer)  # Autonomous System Number

    # Destination
    dst_ip = Column(String(45), index=True)
    dst_port = Column(Integer)
    dst_mac = Column(String(17))
    dst_as = Column(Integer)

    # Protocol info
    protocol = Column(Integer)  # IP protocol number (6=TCP, 17=UDP, 1=ICMP)
    protocol_name = Column(String(20))
    tcp_flags = Column(Integer)
    tos = Column(Integer)  # Type of Service

    # Traffic stats
    bytes_total = Column(BigInteger)
    packets_total = Column(BigInteger)
    bytes_per_second = Column(Float)
    packets_per_second = Column(Float)

    # Application detection
    application = Column(String(100))
    application_category = Column(String(50))

    # Direction
    direction = Column(String(10))  # inbound, outbound, internal

    # Metadata
    exporter_ip = Column(String(45))
    input_interface = Column(Integer)
    output_interface = Column(Integer)
    next_hop = Column(String(45))

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", backref="network_flows")


class NetworkAlert(Base):
    """Alerts generated from network monitoring"""
    __tablename__ = "network_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(UUID(as_uuid=True), ForeignKey("network_devices.id", ondelete="CASCADE"), index=True)
    interface_id = Column(UUID(as_uuid=True), ForeignKey("network_interfaces.id", ondelete="CASCADE"), index=True)

    # Alert details
    alert_type = Column(String(50), nullable=False, index=True)
    # Types: device_down, interface_down, high_cpu, high_memory, high_utilization, errors, packet_loss
    severity = Column(String(20), default="warning", index=True)
    status = Column(String(20), default="active", index=True)

    title = Column(String(255), nullable=False)
    message = Column(Text)

    # Metric info
    metric_name = Column(String(100))
    metric_value = Column(Float)
    threshold_value = Column(Float)

    # Timing
    triggered_at = Column(DateTime(timezone=True), nullable=False, index=True)
    acknowledged_at = Column(DateTime(timezone=True))
    acknowledged_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at = Column(DateTime(timezone=True))

    # Context
    context = Column(JSONB, default=dict)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", backref="network_alerts")
    device = relationship("NetworkDevice", backref="alerts")
    interface = relationship("NetworkInterface", backref="alerts")


class NetworkTopologyLink(Base):
    """Links between network devices (for topology visualization)"""
    __tablename__ = "network_topology_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Source
    source_device_id = Column(UUID(as_uuid=True), ForeignKey("network_devices.id", ondelete="CASCADE"), nullable=False, index=True)
    source_interface_id = Column(UUID(as_uuid=True), ForeignKey("network_interfaces.id", ondelete="SET NULL"))

    # Target
    target_device_id = Column(UUID(as_uuid=True), ForeignKey("network_devices.id", ondelete="CASCADE"), nullable=False, index=True)
    target_interface_id = Column(UUID(as_uuid=True), ForeignKey("network_interfaces.id", ondelete="SET NULL"))

    # Link properties
    link_type = Column(String(30))  # ethernet, fiber, wireless, vpn, vlan
    speed_mbps = Column(BigInteger)
    status = Column(String(20), default="unknown")
    latency_ms = Column(Float)
    packet_loss_percent = Column(Float)

    # Discovery
    discovery_method = Column(String(30))  # lldp, cdp, manual, arp
    discovered_at = Column(DateTime(timezone=True))
    last_seen = Column(DateTime(timezone=True))

    # Metadata
    labels = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", backref="network_topology_links")
    source_device = relationship("NetworkDevice", foreign_keys=[source_device_id], backref="outbound_links")
    target_device = relationship("NetworkDevice", foreign_keys=[target_device_id], backref="inbound_links")
