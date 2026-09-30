# backend/app/schemas/user.py - User schemas for the users endpoint
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class UserResponse(BaseModel):
    """User profile response schema"""
    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    full_name: str = Field(..., description="User full name")
    role: str = Field(..., description="User role")
    organization_id: str = Field(..., description="Organization ID")
    organization_name: Optional[str] = Field(None, description="Organization name")
    is_active: bool = Field(..., description="Whether user is active")
    is_verified: bool = Field(default=False, description="Whether email is verified")
    phone_number: Optional[str] = Field(None, description="Phone number")
    timezone: Optional[str] = Field("UTC", description="User timezone")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    notification_preferences: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Notification preferences")
    skills: Optional[List[str]] = Field(default_factory=list, description="User skills")

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    """User profile update schema"""
    full_name: Optional[str] = Field(None, min_length=1, description="User full name")
    phone_number: Optional[str] = Field(None, description="Phone number")
    timezone: Optional[str] = Field(None, description="User timezone")
    notification_preferences: Optional[Dict[str, Any]] = Field(None, description="Notification preferences")
    skills: Optional[List[str]] = Field(None, description="User skills")

class UserListResponse(BaseModel):
    """Response for listing users"""
    users: List[UserResponse] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users")
    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")

class UserCreateAdmin(BaseModel):
    """Schema for creating users (admin only)"""
    email: EmailStr = Field(..., description="User email")
    full_name: str = Field(..., min_length=1, description="User full name")
    role: str = Field("member", description="User role (member, admin)")
    phone_number: Optional[str] = Field(None, description="Phone number")
    password: Optional[str] = Field(None, min_length=8, description="Password (optional for OAuth)")

class UserInviteRequest(BaseModel):
    """Schema for inviting users"""
    email: EmailStr = Field(..., description="Email to invite")
    role: str = Field("member", description="Role for invited user")
    message: Optional[str] = Field(None, description="Custom invitation message")

class UserInviteResponse(BaseModel):
    """Response after sending invitation"""
    message: str = Field(..., description="Success message")
    email: str = Field(..., description="Invited email")
    role: str = Field(..., description="Assigned role")
    status: str = Field(..., description="Invitation status")