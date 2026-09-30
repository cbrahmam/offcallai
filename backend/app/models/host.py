# backend/app/models/host.py - Monitored Host Model for Metrics Collection
from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, BigInteger, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from app.database import Base


class HostStatus(str, enum.Enum):
    ACTIVE = "active"           # Receiving metrics normally
    INACTIVE = "inactive"       # No metrics received recently
    ALERTING = "alerting"       # Has active alerts
    MAINTENANCE = "maintenance" # In maintenance window


class Host(Base):
    """
    Represents a monitored server/host running the OffCall AI agent.
    Collects system metrics (CPU, memory, disk, network) and logs.
    """
    __tablename__ = "hosts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Identification
    hostname = Column(String(255), nullable=False, index=True)
    display_name = Column(String(255))  # Optional friendly name
    ip_address = Column(String(45))  # IPv4 or IPv6
    agent_id = Column(String(100), unique=True, index=True)  # Unique agent identifier

    # System Info (populated by agent)
    os = Column(String(100))              # e.g., "Ubuntu 22.04", "Windows Server 2022"
    os_version = Column(String(50))
    kernel = Column(String(100))
    arch = Column(String(20))             # e.g., "amd64", "arm64"
    cpu_cores = Column(Integer)
    cpu_model = Column(String(255))
    memory_total_bytes = Column(BigInteger)

    # Agent Info
    agent_version = Column(String(20))
    last_seen_at = Column(DateTime(timezone=True))
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())

    # Status
    status = Column(String(20), default="active", index=True)
    is_active = Column(Boolean, default=True)

    # Tags for filtering and grouping
    tags = Column(JSONB, default=dict)    # e.g., {"env": "production", "service": "api", "region": "us-east-1"}

    # Metadata
    description = Column(Text)
    extra_data = Column(JSONB, default=dict)  # Any additional metadata from agent

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="hosts")

    def __repr__(self):
        return f"<Host(id='{self.id}', hostname='{self.hostname}', status='{self.status}')>"

    @property
    def memory_total_gb(self) -> float:
        """Return total memory in GB for display purposes."""
        if self.memory_total_bytes:
            return round(self.memory_total_bytes / (1024 ** 3), 2)
        return 0.0
