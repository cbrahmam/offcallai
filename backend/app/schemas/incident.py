# backend/app/schemas/incident.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class IncidentSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class IncidentStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"

# Request schemas
class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Incident title")
    description: str = Field(..., min_length=1, description="Detailed description")
    severity: IncidentSeverity = Field(default=IncidentSeverity.MEDIUM, description="Incident severity")
    source: Optional[str] = Field(default="manual", max_length=100, description="Source of the incident")
    tags: Optional[List[str]] = Field(default_factory=list, description="Incident tags")  # ADD THIS LINE

class IncidentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, min_length=1)
    severity: Optional[IncidentSeverity] = None
    status: Optional[IncidentStatus] = None
    assigned_to: Optional[str] = None
    tags: Optional[List[str]] = None  # ADD THIS LINE TOO

# Response schemas
class IncidentResponse(BaseModel):
    id: str
    organization_id: str
    title: str
    description: str
    severity: str
    status: str
    source: str
    created_by: Optional[str] = None
    assigned_to: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    tags: List[str] = []  # ADD THIS LINE

    class Config:
        from_attributes = True

class IncidentListResponse(BaseModel):
    incidents: List[IncidentResponse]
    total: int
    page: int
    per_page: int
    total_pages: int

# Filter schemas
class IncidentFilters(BaseModel):
    status: Optional[IncidentStatus] = None
    severity: Optional[IncidentSeverity] = None
    assigned_to: Optional[str] = None
    created_by: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    tags: Optional[List[str]] = None  # ADD THIS LINE