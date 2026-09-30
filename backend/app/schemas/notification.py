from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class NotificationType(str, Enum):
    INCIDENT = "incident"
    ALERT = "alert"
    SYSTEM = "system"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"

class NotificationSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class NotificationCreate(BaseModel):
    type: NotificationType
    title: str = Field(..., max_length=255)
    message: str
    severity: Optional[NotificationSeverity] = None
    incident_id: Optional[str] = None
    action_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class NotificationUpdate(BaseModel):
    read: Optional[bool] = None

class NotificationResponse(BaseModel):
    id: str
    type: NotificationType
    title: str
    message: str
    severity: Optional[NotificationSeverity]
    incident_id: Optional[str]
    action_url: Optional[str]
    metadata: Dict[str, Any]
    read: bool
    read_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

class NotificationStats(BaseModel):
    total_count: int
    unread_count: int
    incidents_count: int
    alerts_count: int
    system_count: int

class NotificationPreferences(BaseModel):
    email_notifications: bool = True
    browser_notifications: bool = True
    sound_enabled: bool = True
    critical_alerts_only: bool = False
    quiet_hours_enabled: bool = False
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "08:00"