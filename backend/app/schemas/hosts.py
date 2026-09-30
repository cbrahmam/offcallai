# backend/app/schemas/hosts.py - Host Schemas for Metrics Infrastructure
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from enum import Enum


class HostStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ALERTING = "alerting"
    MAINTENANCE = "maintenance"


# ============================================
# Host Registration (from Agent)
# ============================================

class HostRegister(BaseModel):
    """Payload sent by agent when first connecting."""
    hostname: str = Field(..., min_length=1, max_length=255)
    agent_id: str = Field(..., min_length=1, max_length=100, description="Unique agent identifier")

    # System info collected by agent
    os: Optional[str] = Field(None, max_length=100)
    os_version: Optional[str] = Field(None, max_length=50)
    kernel: Optional[str] = Field(None, max_length=100)
    arch: Optional[str] = Field(None, max_length=20)
    cpu_cores: Optional[int] = Field(None, ge=1)
    cpu_model: Optional[str] = Field(None, max_length=255)
    memory_total_bytes: Optional[int] = Field(None, ge=0)

    # Agent info
    agent_version: Optional[str] = Field(None, max_length=20)

    # Optional metadata
    ip_address: Optional[str] = Field(None, max_length=45)
    display_name: Optional[str] = Field(None, max_length=255)
    tags: Optional[Dict[str, str]] = Field(default_factory=dict)
    description: Optional[str] = None

    @validator('hostname', pre=True)
    def normalize_hostname(cls, v):
        if v:
            return v.strip().lower()
        return v

    @validator('tags', pre=True)
    def normalize_tags(cls, v):
        if v is None:
            return {}
        # Ensure all values are strings
        return {str(k): str(val) for k, val in v.items()}


class HostHeartbeat(BaseModel):
    """Payload sent periodically by agent to indicate it's alive."""
    agent_id: str = Field(..., min_length=1, max_length=100)
    agent_version: Optional[str] = Field(None, max_length=20)

    # Optional updated system info
    ip_address: Optional[str] = None
    uptime_seconds: Optional[int] = None


# ============================================
# Host CRUD
# ============================================

class HostCreate(BaseModel):
    """Create a host manually (without agent)."""
    hostname: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)
    ip_address: Optional[str] = Field(None, max_length=45)

    os: Optional[str] = None
    os_version: Optional[str] = None
    arch: Optional[str] = None
    cpu_cores: Optional[int] = None
    memory_total_bytes: Optional[int] = None

    tags: Optional[Dict[str, str]] = Field(default_factory=dict)
    description: Optional[str] = None


class HostUpdate(BaseModel):
    """Update host details."""
    display_name: Optional[str] = Field(None, max_length=255)
    ip_address: Optional[str] = Field(None, max_length=45)
    tags: Optional[Dict[str, str]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


# ============================================
# Host Response
# ============================================

class HostResponse(BaseModel):
    """Host details returned by API."""
    id: str
    hostname: str
    display_name: Optional[str] = None
    ip_address: Optional[str] = None
    agent_id: Optional[str] = None

    # System info
    os: Optional[str] = None
    os_version: Optional[str] = None
    kernel: Optional[str] = None
    arch: Optional[str] = None
    cpu_cores: Optional[int] = None
    cpu_model: Optional[str] = None
    memory_total_bytes: Optional[int] = None
    memory_total_gb: Optional[float] = None

    # Agent info
    agent_version: Optional[str] = None
    last_seen_at: Optional[datetime] = None
    first_seen_at: Optional[datetime] = None

    # Status
    status: HostStatus = HostStatus.ACTIVE
    is_active: bool = True

    # Metadata
    tags: Dict[str, str] = Field(default_factory=dict)
    description: Optional[str] = None

    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class HostSummary(BaseModel):
    """Lightweight host info for lists."""
    id: str
    hostname: str
    display_name: Optional[str] = None
    os: Optional[str] = None
    status: HostStatus = HostStatus.ACTIVE
    last_seen_at: Optional[datetime] = None
    tags: Dict[str, str] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class HostListResponse(BaseModel):
    """Paginated list of hosts."""
    hosts: List[HostSummary]
    total: int
    page: int
    per_page: int


# ============================================
# Host with Latest Metrics
# ============================================

class HostMetricSnapshot(BaseModel):
    """Current metric value for a host."""
    name: str
    value: float
    unit: Optional[str] = None
    timestamp: datetime


class HostWithMetrics(HostResponse):
    """Host with latest metric values."""
    current_metrics: List[HostMetricSnapshot] = Field(default_factory=list)

    # Quick access to key metrics
    cpu_usage_percent: Optional[float] = None
    memory_usage_percent: Optional[float] = None
    disk_usage_percent: Optional[float] = None
    network_in_bytes: Optional[float] = None
    network_out_bytes: Optional[float] = None


# ============================================
# Agent API Key
# ============================================

class AgentAPIKeyCreate(BaseModel):
    """Create an API key for agent authentication."""
    name: str = Field(..., min_length=1, max_length=255, description="Friendly name for this key")
    description: Optional[str] = None
    tags: Optional[Dict[str, str]] = Field(default_factory=dict, description="Tags to apply to hosts using this key")


class AgentAPIKeyResponse(BaseModel):
    """API key response - key only shown on creation."""
    id: str
    name: str
    key_prefix: str  # First 8 chars for identification
    description: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    last_used_at: Optional[datetime] = None
    is_active: bool = True

    # Only included on creation
    api_key: Optional[str] = None  # Full key, only shown once


class AgentInstallInstructions(BaseModel):
    """Installation instructions for the agent."""
    one_liner: str
    api_key: str
    api_endpoint: str
    agent_download_url: str
    supported_platforms: List[str] = ["linux/amd64", "linux/arm64", "darwin/amd64", "darwin/arm64"]
