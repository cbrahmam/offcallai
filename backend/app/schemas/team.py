from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from enum import Enum

class TeamRole(str, Enum):
    LEAD = "lead"
    MEMBER = "member"
    OBSERVER = "observer"

class TeamCreate(BaseModel):
    name: str
    description: Optional[str] = None
    member_ids: Optional[List[str]] = []

class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class TeamMemberResponse(BaseModel):
    id: str
    full_name: str
    email: str
    role: str = "member"
    joined_at: datetime
    is_currently_on_call: bool = False
    
    class Config:
        from_attributes = True

class TeamResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    is_active: bool
    member_count: int
    members: List[TeamMemberResponse]
    created_at: datetime
    
    class Config:
        from_attributes = True