# backend/app/models/service_catalog.py
"""Service Catalog models for tracking services and dependencies"""

from sqlalchemy import Column, String, Text, Boolean, Integer, ForeignKey, Table, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


# Many-to-many relationship for service dependencies
service_dependencies = Table(
    'service_dependencies',
    Base.metadata,
    Column('upstream_service_id', UUID(as_uuid=True), ForeignKey('services.id', ondelete='CASCADE'), primary_key=True),
    Column('downstream_service_id', UUID(as_uuid=True), ForeignKey('services.id', ondelete='CASCADE'), primary_key=True),
    Column('dependency_type', String(50), default='requires'),  # requires, optional, calls
    Column('created_at', DateTime(timezone=True), server_default=func.now())
)


class Service(Base):
    """Service in the catalog"""
    __tablename__ = 'services'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)

    # Basic info
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False)  # URL-friendly identifier
    description = Column(Text)
    tier = Column(String(20), default='tier3')  # tier1 (critical), tier2 (important), tier3 (standard)

    # Ownership
    owner_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    team_id = Column(UUID(as_uuid=True), ForeignKey('teams.id'))

    # Technical details
    repository_url = Column(String(500))
    documentation_url = Column(String(500))
    dashboard_url = Column(String(500))
    runbook_id = Column(UUID(as_uuid=True), ForeignKey('runbooks.id'))

    # Health & monitoring
    health_check_url = Column(String(500))
    last_health_check = Column(DateTime(timezone=True))
    health_status = Column(String(20), default='unknown')  # healthy, degraded, down, unknown

    # Categorization
    tags = Column(ARRAY(String), default=[])
    environment = Column(String(50), default='production')  # production, staging, development
    service_type = Column(String(50))  # api, web, worker, database, cache, queue, etc.

    # Extra data
    extra_data = Column(JSONB, default={})
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="services")
    owner = relationship("User", foreign_keys=[owner_id])
    team = relationship("Team", back_populates="services")
    runbook = relationship("Runbook")
    slos = relationship("SLO", back_populates="service", cascade="all, delete-orphan")

    # Self-referential many-to-many for dependencies
    dependencies = relationship(
        "Service",
        secondary=service_dependencies,
        primaryjoin=id == service_dependencies.c.upstream_service_id,
        secondaryjoin=id == service_dependencies.c.downstream_service_id,
        backref="dependents"
    )

    def __repr__(self):
        return f"<Service {self.name}>"


class SLO(Base):
    """Service Level Objective"""
    __tablename__ = 'slos'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)
    service_id = Column(UUID(as_uuid=True), ForeignKey('services.id', ondelete='CASCADE'))

    # SLO definition
    name = Column(String(255), nullable=False)
    description = Column(Text)
    slo_type = Column(String(50), nullable=False)  # availability, latency, error_rate, throughput

    # Target
    target_percentage = Column(Integer, nullable=False)  # e.g., 9990 for 99.90%
    target_value = Column(Integer)  # For latency SLOs: target in ms
    measurement_window = Column(String(20), default='30d')  # 7d, 30d, 90d

    # Error budget
    error_budget_policy = Column(Text)  # What happens when budget is exhausted

    # Current status (cached, updated by worker)
    current_percentage = Column(Integer)  # Current SLI value * 100
    error_budget_remaining = Column(Integer)  # Percentage remaining * 100
    error_budget_consumed = Column(Integer, default=0)
    last_calculated_at = Column(DateTime(timezone=True))

    # Alert thresholds
    alert_threshold_warning = Column(Integer, default=5000)  # 50% budget consumed
    alert_threshold_critical = Column(Integer, default=8000)  # 80% budget consumed

    # Status
    is_active = Column(Boolean, default=True)
    is_breached = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="slos")
    service = relationship("Service", back_populates="slos")
    records = relationship("SLIRecord", back_populates="slo", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SLO {self.name} target={self.target_percentage/100}%>"


class SLIRecord(Base):
    """Service Level Indicator record - actual measurements"""
    __tablename__ = 'sli_records'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slo_id = Column(UUID(as_uuid=True), ForeignKey('slos.id', ondelete='CASCADE'), nullable=False)

    # Measurement
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    period = Column(String(20), default='1h')  # 1h, 1d granularity

    # Values
    total_requests = Column(Integer, default=0)
    good_requests = Column(Integer, default=0)
    bad_requests = Column(Integer, default=0)

    # Calculated
    sli_value = Column(Integer)  # Percentage * 100 (e.g., 9995 = 99.95%)

    # For latency SLOs
    p50_latency_ms = Column(Integer)
    p95_latency_ms = Column(Integer)
    p99_latency_ms = Column(Integer)

    # Relationships
    slo = relationship("SLO", back_populates="records")

    def __repr__(self):
        return f"<SLIRecord {self.slo_id} {self.timestamp} value={self.sli_value}>"
