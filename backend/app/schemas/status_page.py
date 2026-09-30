# backend/app/schemas/status_page.py
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


class ServiceStatus(str, Enum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    PARTIAL_OUTAGE = "partial_outage"
    MAJOR_OUTAGE = "major_outage"
    MAINTENANCE = "maintenance"


# Service schemas
class StatusPageServiceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    status: ServiceStatus = ServiceStatus.OPERATIONAL
    display_order: int = 0
    is_visible: bool = True
    group_name: Optional[str] = None
    health_check_url: Optional[str] = None
    health_check_interval_minutes: int = 5


class StatusPageServiceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[ServiceStatus] = None
    display_order: Optional[int] = None
    is_visible: Optional[bool] = None
    group_name: Optional[str] = None
    health_check_url: Optional[str] = None
    health_check_interval_minutes: Optional[int] = None


class StatusPageServiceResponse(BaseModel):
    id: UUID
    status_page_id: UUID
    name: str
    description: Optional[str]
    status: ServiceStatus
    display_order: int
    is_visible: bool
    group_name: Optional[str]
    health_check_url: Optional[str]
    health_check_interval_minutes: int
    last_health_check: Optional[datetime]
    last_health_check_status: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# Status Page schemas
class StatusPageCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r'^[a-z0-9-]+$')
    description: Optional[str] = None
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    primary_color: str = "#3B82F6"
    is_public: bool = True
    show_historical_uptime: bool = True
    historical_days: int = 90
    show_incident_history: bool = True
    incident_history_days: int = 14
    allow_subscriptions: bool = True
    support_url: Optional[str] = None
    support_email: Optional[str] = None


class StatusPageUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    slug: Optional[str] = Field(None, min_length=1, max_length=100, pattern=r'^[a-z0-9-]+$')
    description: Optional[str] = None
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    primary_color: Optional[str] = None
    custom_css: Optional[str] = None
    custom_header_html: Optional[str] = None
    custom_footer_html: Optional[str] = None
    is_public: Optional[bool] = None
    show_historical_uptime: Optional[bool] = None
    historical_days: Optional[int] = None
    show_incident_history: Optional[bool] = None
    incident_history_days: Optional[int] = None
    allow_subscriptions: Optional[bool] = None
    support_url: Optional[str] = None
    support_email: Optional[str] = None


class StatusPageResponse(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    slug: str
    description: Optional[str]
    logo_url: Optional[str]
    favicon_url: Optional[str]
    primary_color: str
    custom_css: Optional[str]
    custom_header_html: Optional[str]
    custom_footer_html: Optional[str]
    is_public: bool
    show_historical_uptime: bool
    historical_days: int
    show_incident_history: bool
    incident_history_days: int
    allow_subscriptions: bool
    support_url: Optional[str]
    support_email: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    services: List[StatusPageServiceResponse] = []

    class Config:
        from_attributes = True


# Uptime record schemas
class UptimeRecordResponse(BaseModel):
    date: datetime
    uptime_percentage: int
    total_incidents: int
    total_downtime_minutes: int

    class Config:
        from_attributes = True


class ServiceWithUptimeResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    status: ServiceStatus
    group_name: Optional[str]
    uptime_records: List[UptimeRecordResponse] = []

    class Config:
        from_attributes = True


# Public status page response (what external users see)
class PublicIncidentResponse(BaseModel):
    id: UUID
    title: str
    status: str
    severity: str
    created_at: datetime
    resolved_at: Optional[datetime]
    description: Optional[str]


class PublicMaintenanceResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    start_time: datetime
    end_time: datetime
    services: List[str]
    is_currently_active: bool


class PublicStatusPageResponse(BaseModel):
    name: str
    description: Optional[str]
    logo_url: Optional[str]
    primary_color: str
    overall_status: ServiceStatus
    services: List[ServiceWithUptimeResponse]
    active_incidents: List[PublicIncidentResponse] = []
    scheduled_maintenance: List[PublicMaintenanceResponse] = []
    past_incidents: List[PublicIncidentResponse] = []
    allow_subscriptions: bool
    support_url: Optional[str]
    support_email: Optional[str]


# Subscriber schemas
class SubscriberCreate(BaseModel):
    email: EmailStr
    notify_on_incidents: bool = True
    notify_on_maintenance: bool = True
    notify_on_resolved: bool = True


class SubscriberResponse(BaseModel):
    id: UUID
    email: str
    is_verified: bool
    notify_on_incidents: bool
    notify_on_maintenance: bool
    notify_on_resolved: bool
    subscribed_at: datetime

    class Config:
        from_attributes = True


class SubscriberListResponse(BaseModel):
    subscribers: List[SubscriberResponse]
    total: int
