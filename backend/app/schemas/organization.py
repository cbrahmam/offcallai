from pydantic import BaseModel
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List


class OrganizationCreate(BaseModel):
    name: str
    slug: str

class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    max_users: int
    max_incidents_per_month: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

class OrganizationStatsResponse(BaseModel):
    total_users: int
    total_incidents: int
    total_alerts: int
    active_incidents: int
    resolved_incidents: int
    mttr_hours: Optional[float] = None
    alert_volume_24h: int
    top_services: List[str] = []