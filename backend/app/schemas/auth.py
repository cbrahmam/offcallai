# backend/app/schemas/auth.py - Updated with refresh token support
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class UserCreate(BaseModel):
    """User registration schema"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    full_name: str = Field(..., min_length=2, description="Full name")
    organization_name: str = Field(..., min_length=2, description="Organization name")

class UserLogin(BaseModel):
    """User login schema"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")

class RefreshTokenRequest(BaseModel):
    """Refresh token request schema"""
    refresh_token: str = Field(..., description="Refresh token")

class UserResponse(BaseModel):
    """User response schema with tokens"""
    message: Optional[str] = None
    access_token: str = Field(..., description="JWT access token")
    refresh_token: Optional[str] = Field(None, description="Refresh token for automatic renewal")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user: dict = Field(..., description="User information")

class TokenRefreshResponse(BaseModel):
    """Token refresh response schema"""
    access_token: str = Field(..., description="New JWT access token")
    refresh_token: str = Field(..., description="New refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")

class LogoutResponse(BaseModel):
    """Logout response schema"""
    message: str = Field(default="Logged out successfully", description="Logout confirmation")

class UserInfo(BaseModel):
    """User information schema"""
    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    full_name: str = Field(..., description="User full name")
    role: str = Field(..., description="User role")
    organization_id: str = Field(..., description="Organization ID")
    is_verified: bool = Field(..., description="Email verification status")
    created_at: str = Field(..., description="Account creation timestamp")


class ForgotPasswordRequest(BaseModel):
    """Forgot password request schema"""
    email: EmailStr = Field(..., description="User email address")


class ForgotPasswordResponse(BaseModel):
    """Forgot password response schema"""
    message: str = Field(default="If an account with that email exists, a password reset link has been sent.")
    success: bool = Field(default=True)


class ResetPasswordRequest(BaseModel):
    """Reset password request schema"""
    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")