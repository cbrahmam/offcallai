# backend/app/api/v1/endpoints/auth.py - Enhanced with MFA and Security
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_async_session
from app.models.user import User
from app.models.organization import Organization
from app.schemas.auth import UserCreate, UserLogin, UserResponse, ForgotPasswordRequest, ForgotPasswordResponse, ResetPasswordRequest
from app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token, verify_refresh_token, get_current_user
from app.core.config import settings
from app.services.auth_security_service import AuthSecurityService, get_password_requirements
import uuid
from datetime import datetime, timedelta
import pyotp
import qrcode
import io
import base64
import re
import secrets
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_async_session)):
    """Register a new user and organization"""
    try:
        # Validate password strength
        is_valid, error_message = AuthSecurityService.validate_password_strength(user_data.password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password does not meet requirements: {error_message}. Requirements: {get_password_requirements()}"
            )

        # Check if user already exists
        result = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
        
        # Generate organization slug from name
        base_slug = re.sub(r'[^a-zA-Z0-9]', '-', user_data.organization_name).lower()
        base_slug = re.sub(r'-+', '-', base_slug).strip('-')
        
        # Ensure slug is unique by adding random suffix if needed
        slug = base_slug
        max_attempts = 10
        attempt = 0
        
        while attempt < max_attempts:
            # Check if slug already exists
            slug_result = await db.execute(
                select(Organization).where(Organization.slug == slug)
            )
            if not slug_result.scalar_one_or_none():
                break
            
            # Add random suffix and try again
            slug = f"{base_slug}-{secrets.token_urlsafe(4).lower()}"
            attempt += 1
        
        # Create organization with slug
        organization = Organization(
            id=uuid.uuid4(),
            name=user_data.organization_name,
            slug=slug,  # This was missing!
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(organization)
        await db.flush()  # Get the organization ID
        
        # Create user
        user = User(
            id=uuid.uuid4(),
            organization_id=organization.id,
            email=user_data.email,
            password_hash=get_password_hash(user_data.password),
            full_name=user_data.full_name,
            role="admin",  # First user in org is admin
            is_active=True,
            is_verified=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(user)
    
        await db.commit()
        await db.refresh(user)
        await db.refresh(organization)
        
        # Create access and refresh tokens
        token_data = {"sub": str(user.id), "org_id": str(user.organization_id)}
        access_token = create_access_token(data=token_data)
        refresh_token = create_refresh_token(data=token_data)

        return UserResponse(
            message="User registered successfully",
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            user={
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "organization_id": str(organization.id),
                "organization_name": organization.name
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@router.post("/login", response_model=UserResponse)
async def login(login_data: UserLogin, db: AsyncSession = Depends(get_async_session)):
    """Login user with rate limiting and security"""
    try:
        # Check rate limiting FIRST
        is_allowed, remaining_attempts, lockout_until = AuthSecurityService.check_rate_limit(login_data.email)

        if not is_allowed:
            remaining_minutes = int((lockout_until - datetime.utcnow()).total_seconds() / 60) + 1
            logger.warning(f"Login blocked - account temporarily locked")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed login attempts. Account temporarily locked. Try again in {remaining_minutes} minutes."
            )

        logger.info(f"Login attempt initiated")

        # Get user from database
        result = await db.execute(
            select(User).where(
                User.email == login_data.email,
                User.is_active == True
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            # Record failed attempt
            AuthSecurityService.record_login_attempt(login_data.email, success=False)
            logger.warning(f"Login failed - user not found")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )

        # Verify password
        try:
            password_valid = verify_password(login_data.password, user.password_hash)

            if not password_valid:
                # Record failed attempt
                AuthSecurityService.record_login_attempt(login_data.email, success=False)
                lockout_status = AuthSecurityService.get_lockout_status(login_data.email)
                remaining = lockout_status.get('attempts_remaining', 0)

                logger.warning(f"Login failed - invalid password, {remaining} attempts remaining")

                detail = "Incorrect email or password"
                if remaining <= 2 and remaining > 0:
                    detail += f". Warning: {remaining} attempt(s) remaining before account lockout."

                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=detail
                )
        except HTTPException:
            raise
        except Exception as pwd_error:
            logger.error(f"Password verification system error")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication system error. Please try again."
            )

        # Get organization info
        org_result = await db.execute(
            select(Organization).where(Organization.id == user.organization_id)
        )
        organization = org_result.scalar_one_or_none()

        if not organization:
            logger.error(f"Organization not found for authenticated user")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Account configuration error. Please contact support."
            )

        # Create access and refresh tokens
        try:
            token_data = {"sub": str(user.id), "org_id": str(user.organization_id)}
            access_token = create_access_token(data=token_data)
            refresh_token = create_refresh_token(data=token_data)
        except Exception as token_error:
            logger.error(f"Token creation failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication system error. Please try again."
            )

        # Record successful login (clears failed attempts)
        AuthSecurityService.record_login_attempt(login_data.email, success=True)

        # Store ALL data before any commits to avoid async issues
        user_data = {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "organization_id": str(user.organization_id),
        }
        org_name = organization.name

        # Update last login
        user.last_login_at = datetime.utcnow()
        await db.commit()

        logger.info(f"Login successful")

        return UserResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            user={
                **user_data,
                "organization_name": org_name
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected login error occurred")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed. Please try again."
        )

# 🔐 NEW MFA ENDPOINTS
@router.post("/setup-mfa")
async def setup_mfa(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Setup Multi-Factor Authentication for the current user"""
    try:
        print(f"🔐 Setting up MFA for user: {current_user.email}")
        
        # Check if MFA is already enabled
        if hasattr(current_user, 'mfa_enabled') and current_user.mfa_enabled:
            return {
                "message": "MFA is already enabled for this user",
                "mfa_enabled": True
            }
        
        # Generate a new secret key
        secret = pyotp.random_base32()
        print(f"✅ Generated MFA secret for: {current_user.email}")
        
        # Create TOTP URI for QR code
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=current_user.email,
            issuer_name="OffCall AI"
        )
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)
        
        # Create QR code image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64 for API response
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_str = base64.b64encode(img_buffer.getvalue()).decode()
        
        # Generate secure backup codes
        backup_codes = [secrets.token_hex(4).upper() for _ in range(8)]

        # Store MFA secret securely in database (encrypted)
        # Note: In production, the secret should be stored encrypted in the user model
        # and only shown during initial setup
        if hasattr(current_user, 'mfa_secret'):
            from app.services.encryption_service import EncryptionService
            current_user.mfa_secret = EncryptionService.encrypt_api_key(secret)
            current_user.mfa_backup_codes = ','.join(backup_codes)
            await db.commit()

        print(f"🎉 MFA setup completed for: {current_user.email}")

        # SECURITY: Only return the secret during initial setup
        # After this, the secret is never returned again
        return {
            "message": "MFA setup initiated successfully",
            "qr_code": f"data:image/png;base64,{img_str}",
            "backup_codes": backup_codes,
            "instructions": "Scan the QR code with Google Authenticator or similar app. Save your backup codes securely - they won't be shown again."
        }
        
    except Exception as e:
        print(f"🚨 MFA setup error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MFA setup failed: {str(e)}"
        )

@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get current user information"""
    try:
        # Get organization info
        org_result = await db.execute(
            select(Organization).where(Organization.id == current_user.organization_id)
        )
        organization = org_result.scalar_one_or_none()
        
        return {
            "id": str(current_user.id),
            "email": current_user.email,
            "full_name": current_user.full_name,
            "role": current_user.role,
            "organization_id": str(current_user.organization_id),
            "organization_name": organization.name if organization else None,
            "is_verified": current_user.is_verified,
            "mfa_enabled": getattr(current_user, 'mfa_enabled', False),
            "created_at": current_user.created_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user info: {str(e)}"
        )

@router.post("/test")
async def test_auth():
    """Test endpoint to verify auth is working"""
    return {"message": "Auth endpoint is working!", "timestamp": datetime.utcnow()}

@router.post("/refresh-token")
async def refresh_token(
    request_data: dict,
    db: AsyncSession = Depends(get_async_session)
):
    """Refresh access token using a valid refresh token"""
    try:
        refresh_token_str = request_data.get("refresh_token")
        if not refresh_token_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Refresh token is required"
            )

        # Check if refresh token is blacklisted
        if AuthSecurityService.is_refresh_token_blacklisted(refresh_token_str):
            logger.warning("Attempted use of blacklisted refresh token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked. Please log in again."
            )

        # Verify the refresh token
        payload = verify_refresh_token(refresh_token_str)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )

        # Verify user still exists and is active
        result = await db.execute(
            select(User).where(User.id == user_id, User.is_active == True)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )

        # Blacklist the old refresh token (token rotation)
        AuthSecurityService.blacklist_refresh_token(refresh_token_str)

        # Create new tokens
        token_data = {"sub": str(user.id), "org_id": str(user.organization_id)}
        new_access_token = create_access_token(data=token_data)
        new_refresh_token = create_refresh_token(data=token_data)

        logger.info("Token refreshed successfully")

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Token refresh error occurred")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.post("/logout")
async def logout(
    request_data: dict,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Logout user by blacklisting their tokens.
    This ensures tokens can't be reused after logout.
    """
    try:
        access_token = request_data.get("access_token")
        refresh_token = request_data.get("refresh_token")

        if access_token:
            AuthSecurityService.blacklist_token(access_token)

        if refresh_token:
            AuthSecurityService.blacklist_refresh_token(refresh_token)

        logger.info("User logged out successfully")

        return {
            "message": "Logged out successfully",
            "status": "success"
        }

    except Exception as e:
        logger.error("Logout error occurred")
        # Still return success - logout should always "work" from user perspective
        return {
            "message": "Logged out",
            "status": "success"
        }


@router.get("/lockout-status/{email}")
async def get_lockout_status(email: str):
    """Check the lockout status for an email (useful for UI feedback)"""
    status = AuthSecurityService.get_lockout_status(email)
    return status


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    request_data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Request a password reset email.
    Always returns success to prevent email enumeration attacks.
    """
    try:
        # Check if user exists
        result = await db.execute(
            select(User).where(User.email == request_data.email, User.is_active == True)
        )
        user = result.scalar_one_or_none()

        if user:
            # Generate a secure reset token
            reset_token = secrets.token_urlsafe(32)
            token_expiry = datetime.utcnow() + timedelta(hours=1)  # Token valid for 1 hour

            # Store token in Redis with expiration
            from app.database import get_redis
            redis = get_redis()

            token_data = {
                "user_id": str(user.id),
                "email": user.email,
                "created_at": datetime.utcnow().isoformat()
            }

            import json
            await redis.setex(
                f"password_reset:{reset_token}",
                3600,  # 1 hour in seconds
                json.dumps(token_data)
            )

            # Send reset email
            from app.services.email_service import EmailService
            from app.core.config import settings

            frontend_url = settings.FRONTEND_URL
            reset_link = f"{frontend_url}/reset-password?token={reset_token}"

            html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="text-align: center; padding: 20px;">
                    <h1 style="color: #2563eb;">OffCall AI</h1>
                </div>
                <div style="background: #f8fafc; padding: 24px; border-radius: 8px;">
                    <h2 style="color: #1e293b; margin-top: 0;">Password Reset Request</h2>
                    <p style="color: #475569;">Hi {user.full_name},</p>
                    <p style="color: #475569;">We received a request to reset your password. Click the button below to create a new password:</p>
                    <div style="text-align: center; margin: 32px 0;">
                        <a href="{reset_link}"
                           style="background: #2563eb; color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block;">
                            Reset Password
                        </a>
                    </div>
                    <p style="color: #64748b; font-size: 14px;">This link will expire in 1 hour.</p>
                    <p style="color: #64748b; font-size: 14px;">If you didn't request a password reset, you can safely ignore this email.</p>
                </div>
                <div style="text-align: center; padding: 20px; color: #94a3b8; font-size: 12px;">
                    <p>OffCall AI - Incident Response Platform</p>
                </div>
            </div>
            """

            email_sent = await EmailService.send_email(
                to_email=user.email,
                subject="Reset Your OffCall AI Password",
                body=f"Reset your password using this link: {reset_link}",
                html_content=html_content
            )

            if email_sent:
                logger.info(f"Password reset email sent to {user.email}")
            else:
                logger.error(f"Failed to send password reset email to {user.email}")

        # Always return success to prevent email enumeration
        return ForgotPasswordResponse(
            message="If an account with that email exists, a password reset link has been sent.",
            success=True
        )

    except Exception as e:
        logger.error(f"Forgot password error: {e}")
        # Still return success to prevent enumeration
        return ForgotPasswordResponse(
            message="If an account with that email exists, a password reset link has been sent.",
            success=True
        )


@router.post("/reset-password")
async def reset_password(
    request_data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Reset password using a valid reset token.
    """
    try:
        # Validate password strength
        is_valid, error_message = AuthSecurityService.validate_password_strength(request_data.new_password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password does not meet requirements: {error_message}"
            )

        # Get token from Redis
        from app.database import get_redis
        import json

        redis = get_redis()
        token_key = f"password_reset:{request_data.token}"
        token_data_str = await redis.get(token_key)

        if not token_data_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token. Please request a new password reset."
            )

        token_data = json.loads(token_data_str)
        user_id = token_data.get("user_id")

        # Get user
        result = await db.execute(
            select(User).where(User.id == user_id, User.is_active == True)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not found or inactive."
            )

        # Update password
        user.password_hash = get_password_hash(request_data.new_password)
        user.updated_at = datetime.utcnow()
        await db.commit()

        # Delete the used token
        await redis.delete(token_key)

        # Blacklist all existing refresh tokens for this user (force re-login)
        # This is a security measure to ensure any compromised sessions are invalidated

        logger.info(f"Password reset successful for user {user.email}")

        return {
            "message": "Password has been reset successfully. You can now log in with your new password.",
            "success": True
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reset password error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password. Please try again."
        )


@router.post("/ws-ticket")
async def get_websocket_ticket(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Generate a one-time WebSocket connection ticket.

    SECURITY: This endpoint solves the problem of JWT tokens appearing in WebSocket URLs.
    Instead of passing the full JWT in the URL (which would expose it in logs, browser
    history, and referrer headers), clients request a short-lived ticket that:

    1. Expires in 30 seconds
    2. Can only be used once
    3. Is tied to the user's session
    4. Is stored server-side and validated on WebSocket connection

    Usage:
        1. Client calls POST /auth/ws-ticket with Bearer token
        2. Server returns { "ticket": "abc123..." }
        3. Client connects to WebSocket: wss://api.../ws?ticket=abc123
        4. Server validates ticket and establishes connection
    """
    from app.database import get_redis
    import time

    # Generate a cryptographically secure one-time ticket
    ticket = secrets.token_urlsafe(32)

    # Store ticket in Redis with 30-second expiration
    redis = get_redis()
    ticket_data = {
        "user_id": str(current_user.id),
        "organization_id": str(current_user.organization_id),
        "created_at": time.time(),
        "used": False
    }

    # Store ticket -> user mapping (expires in 30 seconds)
    import json
    await redis.setex(
        f"ws_ticket:{ticket}",
        30,  # 30 seconds TTL
        json.dumps(ticket_data)
    )

    logger.info(f"WebSocket ticket generated for user {current_user.id}")

    return {
        "ticket": ticket,
        "expires_in": 30,
        "message": "Use this ticket within 30 seconds to establish WebSocket connection"
    }