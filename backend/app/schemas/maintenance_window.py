# backend/app/schemas/maintenance_window.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class RecurrencePattern(BaseModel):
    """Recurrence pattern for maintenance windows"""
    frequency: str = Field(..., description="weekly, monthly, or custom")
    day_of_week: Optional[int] = Field(None, ge=0, le=6, description="0=Monday, 6=Sunday")
    day_of_month: Optional[int] = Field(None, ge=1, le=31)
    time: str = Field(..., description="Time in HH:MM format")
    timezone: str = Field(default="UTC")


class MaintenanceWindowCreate(BaseModel):
    """Schema for creating a maintenance window"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    services: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    suppress_alerts: bool = True
    auto_resolve_incidents: bool = False
    is_recurring: bool = False
    recurrence_pattern: Optional[RecurrencePattern] = None
    notify_before_minutes: int = Field(default=30, ge=0, le=1440)


class MaintenanceWindowUpdate(BaseModel):
    """Schema for updating a maintenance window"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    services: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    suppress_alerts: Optional[bool] = None
    auto_resolve_incidents: Optional[bool] = None
    is_recurring: Optional[bool] = None
    recurrence_pattern: Optional[RecurrencePattern] = None
    notify_before_minutes: Optional[int] = Field(None, ge=0, le=1440)
    is_active: Optional[bool] = None


class MaintenanceWindowResponse(BaseModel):
    """Schema for maintenance window response"""
    id: UUID
    organization_id: UUID
    name: str
    description: Optional[str]
    start_time: datetime
    end_time: datetime
    services: List[str]
    tags: List[str]
    suppress_alerts: bool
    auto_resolve_incidents: bool
    is_recurring: bool
    recurrence_pattern: Optional[Dict[str, Any]]
    is_active: bool
    is_cancelled: bool
    cancelled_at: Optional[datetime]
    notify_before_minutes: int
    notification_sent: bool
    created_by_id: UUID
    created_by_name: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime]
    is_currently_active: bool = False  # Computed field

    class Config:
        from_attributes = True


class MaintenanceWindowListResponse(BaseModel):
    """Schema for paginated maintenance window list"""
    windows: List[MaintenanceWindowResponse]
    total: int
    page: int
    per_page: int


class MaintenanceCheckResponse(BaseModel):
    """Schema for checking if a service is in maintenance"""
    in_maintenance: bool
    active_windows: List[MaintenanceWindowResponse] = []
    message: str
