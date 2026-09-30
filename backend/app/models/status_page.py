# backend/app/models/status_page.py
from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, Integer, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from app.database import Base


class ServiceStatus(str, enum.Enum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    PARTIAL_OUTAGE = "partial_outage"
    MAJOR_OUTAGE = "major_outage"
    MAINTENANCE = "maintenance"


class StatusPage(Base):
    """Public status page configuration for an organization"""
    __tablename__ = "status_pages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, unique=True)

    # Configuration
    name = Column(String(255), nullable=False)  # e.g., "Acme Inc Status"
    slug = Column(String(100), nullable=False, unique=True, index=True)  # e.g. "acme-status" -> <your-host>/status/acme-status
    description = Column(Text)
    logo_url = Column(String(500))
    favicon_url = Column(String(500))

    # Customization
    primary_color = Column(String(7), default="#3B82F6")  # Hex color
    custom_css = Column(Text)
    custom_header_html = Column(Text)
    custom_footer_html = Column(Text)

    # Settings
    is_public = Column(Boolean, default=True)
    show_historical_uptime = Column(Boolean, default=True)
    historical_days = Column(Integer, default=90)  # Days of history to show
    show_incident_history = Column(Boolean, default=True)
    incident_history_days = Column(Integer, default=14)
    allow_subscriptions = Column(Boolean, default=True)  # Allow users to subscribe to updates

    # Contact info (optional)
    support_url = Column(String(500))
    support_email = Column(String(255))

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="status_page")
    services = relationship("StatusPageService", back_populates="status_page", cascade="all, delete-orphan")
    subscribers = relationship("StatusPageSubscriber", back_populates="status_page", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<StatusPage(name='{self.name}', slug='{self.slug}')>"


class StatusPageService(Base):
    """A service/component displayed on the status page"""
    __tablename__ = "status_page_services"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status_page_id = Column(UUID(as_uuid=True), ForeignKey("status_pages.id", ondelete="CASCADE"), nullable=False)

    name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(Enum(ServiceStatus), default=ServiceStatus.OPERATIONAL, nullable=False)
    display_order = Column(Integer, default=0)
    is_visible = Column(Boolean, default=True)

    # Group services into categories (optional)
    group_name = Column(String(100))

    # For automated status updates
    health_check_url = Column(String(500))  # Optional health check endpoint
    health_check_interval_minutes = Column(Integer, default=5)
    last_health_check = Column(DateTime(timezone=True))
    last_health_check_status = Column(String(20))

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    status_page = relationship("StatusPage", back_populates="services")
    uptime_records = relationship("ServiceUptimeRecord", back_populates="service", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<StatusPageService(name='{self.name}', status='{self.status}')>"


class ServiceUptimeRecord(Base):
    """Daily uptime record for a service"""
    __tablename__ = "service_uptime_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_id = Column(UUID(as_uuid=True), ForeignKey("status_page_services.id", ondelete="CASCADE"), nullable=False)

    date = Column(DateTime(timezone=True), nullable=False)  # The day this record is for
    uptime_percentage = Column(Integer, default=100)  # 0-100
    total_incidents = Column(Integer, default=0)
    total_downtime_minutes = Column(Integer, default=0)

    # Status breakdown (minutes in each status)
    operational_minutes = Column(Integer, default=1440)  # 24 hours
    degraded_minutes = Column(Integer, default=0)
    outage_minutes = Column(Integer, default=0)

    # Relationships
    service = relationship("StatusPageService", back_populates="uptime_records")

    def __repr__(self):
        return f"<ServiceUptimeRecord(service_id='{self.service_id}', date='{self.date}', uptime={self.uptime_percentage}%)>"


class StatusPageSubscriber(Base):
    """Subscribers who want to be notified of status updates"""
    __tablename__ = "status_page_subscribers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status_page_id = Column(UUID(as_uuid=True), ForeignKey("status_pages.id", ondelete="CASCADE"), nullable=False)

    email = Column(String(255), nullable=False)
    is_verified = Column(Boolean, default=False)
    verification_token = Column(String(100))

    # Notification preferences
    notify_on_incidents = Column(Boolean, default=True)
    notify_on_maintenance = Column(Boolean, default=True)
    notify_on_resolved = Column(Boolean, default=True)

    # Audit
    subscribed_at = Column(DateTime(timezone=True), server_default=func.now())
    verified_at = Column(DateTime(timezone=True))
    unsubscribed_at = Column(DateTime(timezone=True))

    # Relationships
    status_page = relationship("StatusPage", back_populates="subscribers")

    def __repr__(self):
        return f"<StatusPageSubscriber(email='{self.email}', verified={self.is_verified})>"
