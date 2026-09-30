from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class DayOfWeek(int, Enum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


class ShiftType(str, Enum):
    RECURRING = "recurring"
    ONE_TIME = "one_time"


class NotifyChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    SLACK = "slack"
    PUSH = "push"


# ============== User Summary ==============

class UserSummary(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None


class TeamSummary(BaseModel):
    id: str
    name: str


class EscalationPolicySummary(BaseModel):
    id: str
    name: str


# ============== Shift Schemas ==============

class OnCallShiftCreate(BaseModel):
    user_id: str
    shift_type: ShiftType = ShiftType.RECURRING
    day_of_week: Optional[int] = Field(None, ge=0, le=6, description="0=Monday, 6=Sunday")
    start_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$", description="HH:MM format")
    end_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$", description="HH:MM format")
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    notify_channels: List[str] = []


class OnCallShiftUpdate(BaseModel):
    user_id: Optional[str] = None
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    start_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    end_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    notify_channels: Optional[List[str]] = None


class OnCallShiftResponse(BaseModel):
    id: str
    schedule_id: str
    user_id: str
    user: Optional[UserSummary] = None
    shift_type: str
    day_of_week: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    notify_channels: List[str] = []
    created_at: datetime

    class Config:
        from_attributes = True


# ============== Schedule Schemas ==============

class OnCallScheduleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    timezone: str = "UTC"
    team_id: Optional[str] = None
    escalation_policy_id: Optional[str] = None
    is_active: bool = True
    shifts: List[OnCallShiftCreate] = []


class OnCallScheduleUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    timezone: Optional[str] = None
    team_id: Optional[str] = None
    escalation_policy_id: Optional[str] = None
    is_active: Optional[bool] = None


class OnCallScheduleResponse(BaseModel):
    id: str
    organization_id: str
    team_id: Optional[str] = None
    team: Optional[TeamSummary] = None
    name: str
    description: Optional[str] = None
    timezone: str
    is_active: bool
    escalation_policy_id: Optional[str] = None
    escalation_policy: Optional[EscalationPolicySummary] = None
    shifts: List[OnCallShiftResponse] = []
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[UserSummary] = None

    class Config:
        from_attributes = True


class OnCallScheduleListResponse(BaseModel):
    schedules: List[OnCallScheduleResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


# ============== On-Call Status Schemas ==============

class CurrentOnCallUser(BaseModel):
    user_id: str
    user_email: str
    user_full_name: Optional[str] = None
    schedule_id: str
    schedule_name: str
    shift_start: datetime
    shift_end: datetime
    notify_channels: List[str] = []


class CurrentOnCallResponse(BaseModel):
    """Response for 'who is on-call now' query"""
    schedule_id: str
    schedule_name: str
    on_call_users: List[CurrentOnCallUser]
    escalation_policy_id: Optional[str] = None


class OnCallUsersListResponse(BaseModel):
    """All users currently on-call across all schedules"""
    users: List[CurrentOnCallUser]
    total: int
