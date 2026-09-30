from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.organization import Organization
from app.core.security import get_password_hash, verify_password
from app.schemas.auth import UserRegister
from typing import Optional, Tuple
import uuid
import re

class AuthService:
    
    @staticmethod
    async def create_user_and_organization(
        db: AsyncSession, 
        user_data: UserRegister
    ) -> Tuple[User, Organization]:
        """Create a new user and organization"""
        
        # Create organization slug from name if not provided
        if not user_data.organization_slug:
            slug = re.sub(r'[^a-zA-Z0-9]', '-', user_data.organization_name or "my-org").lower()
            slug = re.sub(r'-+', '-', slug).strip('-')
        else:
            slug = user_data.organization_slug
        
        # Check if email already exists
        result = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        if result.scalar_one_or_none():
            raise ValueError("Email already registered")
        
        # Check if organization slug already exists
        result = await db.execute(
            select(Organization).where(Organization.slug == slug)
        )
        if result.scalar_one_or_none():
            raise ValueError("Organization slug already taken")
        
        # Create organization
        organization = Organization(
            name=user_data.organization_name or f"{user_data.full_name}'s Organization",
            slug=slug,
            plan="free"
        )
        db.add(organization)
        await db.flush()  # Get the ID without committing
        
        # Create user
        user = User(
            email=user_data.email,
            password_hash=get_password_hash(user_data.password),
            full_name=user_data.full_name,
            organization_id=organization.id,
            role="admin",  # First user is admin
            is_verified=True
        )
        db.add(user)
        
        await db.commit()
        await db.refresh(organization)
        await db.refresh(user)
        
        return user, organization
    
    @staticmethod
    async def authenticate_user(
        db: AsyncSession, 
        email: str, 
        password: str
    ) -> Optional[User]:
        """Authenticate a user"""
        
        result = await db.execute(
            select(User).where(
                User.email == email,
                User.is_active == True
            )
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        
        if not verify_password(password, user.password_hash):
            return None
        
        return user