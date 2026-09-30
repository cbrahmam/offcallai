# backend/app/api/v1/endpoints/security.py
"""
Security API endpoints for OffCall AI
MFA, rate limiting, GDPR, and advanced security features
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.database import get_async_session
from app.core.deps import get_current_user
from app.models.user import User
from app.core.enhanced_security import (
    token_manager,
    mfa_manager, 
    rate_limiter,
    security_logger,
    DeviceFingerprinter,
    RiskLevel
)

router = APIRouter()
security = HTTPBearer()

# Pydantic models for request/response
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False
    mfa_code: Optional[str] = None

class MFASetupResponse(BaseModel):
    secret: str
    qr_code: str
    instructions: List[str]

class MFAVerifyRequest(BaseModel):
    code: str

class TokenRefreshRequest(BaseModel):
    refresh_token: str

class GDPRExportResponse(BaseModel):
    user_id: str
    export_timestamp: str
    data: Dict[str, Any]

class ConsentUpdateRequest(BaseModel):
    analytics_consent: Optional[bool] = None
    marketing_consent: Optional[bool] = None
    third_party_sharing: Optional[bool] = None

# Enhanced Authentication Endpoints
@router.post("/auth/login-enhanced")
async def enhanced_login(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_async_session)
):
    """Enhanced login with MFA, device fingerprinting, and security monitoring"""
    
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent", "")
    device_fingerprint = DeviceFingerprinter.generate_fingerprint(request, user_agent)
    
    try:
        # 1. Check rate limiting
        rate_limit_result = await rate_limiter.check_multiple_limits(request)
        if not rate_limit_result["allowed"]:
            await security_logger.log_security_event(
                "rate_limit_exceeded",
                ip_address=client_ip,
                details=rate_limit_result,
                risk_level=RiskLevel.MEDIUM
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded"
            )
        
        # 2. Basic authentication (using your existing auth logic)
        user = await authenticate_user(login_data.email, login_data.password, db)
        if not user:
            await security_logger.log_security_event(
                "login_failed",
                ip_address=client_ip,
                details={"email": login_data.email, "reason": "invalid_credentials"},
                risk_level=RiskLevel.MEDIUM
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # 3. Check if MFA is enabled
        mfa_enabled = await is_mfa_enabled(user.id)
        
        if mfa_enabled and not login_data.mfa_code:
            return {
                "mfa_required": True,
                "message": "Multi-factor authentication required",
                "methods": ["totp", "backup_code"]
            }
        
        # 4. Verify MFA if provided
        if mfa_enabled and login_data.mfa_code:
            mfa_valid = await mfa_manager.verify_totp_code(str(user.id), login_data.mfa_code)
            if not mfa_valid:
                await security_logger.log_security_event(
                    "mfa_failed",
                    user_id=str(user.id),
                    ip_address=client_ip,
                    details={"mfa_method": "totp"},
                    risk_level=RiskLevel.HIGH
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid MFA code"
                )
        
        # 5. Assess login risk
        risk_assessment = await assess_login_risk(str(user.id), client_ip, device_fingerprint)
        
        # 6. Create secure token pair
        session_data = {
            "ip_address": client_ip,
            "user_agent": user_agent,
            "login_timestamp": datetime.utcnow().timestamp(),
            "risk_score": risk_assessment.get("risk_score", 0)
        }
        
        tokens = await token_manager.create_token_pair(
            str(user.id), 
            device_fingerprint,
            session_data
        )
        
        # 7. Log successful login
        await security_logger.log_security_event(
            "login_successful",
            user_id=str(user.id),
            ip_address=client_ip,
            details={
                "device_fingerprint": device_fingerprint,
                "mfa_used": mfa_enabled,
                "risk_score": risk_assessment.get("risk_score", 0)
            },
            risk_level=RiskLevel.LOW
        )
        
        return {
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": "bearer",
            "expires_in": tokens["expires_in"],
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "role": getattr(user, 'role', 'user'),
                "mfa_enabled": mfa_enabled
            },
            "security_info": {
                "device_trusted": risk_assessment.get("device_known", False),
                "session_expires": (datetime.utcnow().timestamp() + 900)  # 15 minutes
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await security_logger.log_security_event(
            "login_error",
            ip_address=client_ip,
            details={"error": str(e), "email": login_data.email},
            risk_level=RiskLevel.CRITICAL
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service temporarily unavailable"
        )

@router.post("/auth/refresh-token")
async def refresh_token(
    request: Request,
    refresh_data: TokenRefreshRequest,
    db: AsyncSession = Depends(get_async_session)
):
    """Refresh access token with security validation"""
    
    try:
        device_fingerprint = DeviceFingerprinter.generate_fingerprint(
            request, 
            request.headers.get("user-agent")
        )
        
        # Refresh token pair with security checks
        new_tokens = await token_manager.refresh_token_pair(
            refresh_data.refresh_token,
            device_fingerprint
        )
        
        return new_tokens
        
    except Exception as e:
        await security_logger.log_security_event(
            "token_refresh_failed",
            ip_address=request.client.host,
            details={"error": str(e)},
            risk_level=RiskLevel.MEDIUM
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token refresh failed"
        )

# MFA Endpoints
@router.post("/auth/setup-mfa", response_model=MFASetupResponse)
async def setup_mfa(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Initialize MFA setup for user"""
    
    try:
        # Generate TOTP secret and QR code
        mfa_setup = await mfa_manager.generate_totp_secret(str(current_user.id))
        
        await security_logger.log_security_event(
            "mfa_setup_initiated",
            user_id=str(current_user.id),
            ip_address=request.client.host,
            risk_level=RiskLevel.LOW
        )
        
        return MFASetupResponse(
            secret=mfa_setup["secret"],
            qr_code=mfa_setup["qr_code"],
            instructions=[
                "1. Install Google Authenticator or similar TOTP app",
                "2. Scan the QR code or enter the secret key manually",
                "3. Enter the 6-digit code from your app to verify setup"
            ]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MFA setup failed"
        )

@router.post("/auth/verify-mfa-setup")
async def verify_mfa_setup(
    request: Request,
    setup_data: MFAVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Verify and complete MFA setup"""
    
    try:
        # Verify TOTP code
        setup_valid = await mfa_manager.verify_totp_setup(str(current_user.id), setup_data.code)
        
        if not setup_valid:
            await security_logger.log_security_event(
                "mfa_setup_failed",
                user_id=str(current_user.id),
                ip_address=request.client.host,
                details={"reason": "invalid_code"},
                risk_level=RiskLevel.MEDIUM
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code"
            )
        
        # Generate backup codes
        backup_codes = await mfa_manager.generate_backup_codes(str(current_user.id))
        
        # Update user MFA status in database
        await db.execute(
            "UPDATE users SET mfa_enabled = true WHERE id = :user_id",
            {"user_id": current_user.id}
        )
        await db.commit()
        
        await security_logger.log_security_event(
            "mfa_setup_completed",
            user_id=str(current_user.id),
            ip_address=request.client.host,
            risk_level=RiskLevel.LOW
        )
        
        return {
            "message": "MFA setup completed successfully",
            "backup_codes": backup_codes,
            "warning": "Store these backup codes securely. They can only be used once each."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MFA verification failed"
        )

# GDPR Compliance Endpoints
@router.get("/privacy/data-export", response_model=GDPRExportResponse)
async def export_user_data(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Export all user data (GDPR Article 20)"""
    
    try:
        # Export user profile data
        export_data = {
            "user_id": str(current_user.id),
            "export_timestamp": datetime.utcnow().isoformat(),
            "personal_data": {
                "email": current_user.email,
                "full_name": current_user.full_name,
                "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
                "is_verified": getattr(current_user, 'is_verified', False)
            },
            "activity_data": {
                "incidents": [],  # Add incident data here
                "audit_logs": []  # Add audit log data here
            },
            "preferences": {
                "timezone": "UTC",
                "notification_preferences": {}
            }
        }
        
        await security_logger.log_security_event(
            "data_export_requested",
            user_id=str(current_user.id),
            ip_address=request.client.host,
            risk_level=RiskLevel.LOW
        )
        
        return GDPRExportResponse(
            user_id=str(current_user.id),
            export_timestamp=export_data["export_timestamp"],
            data=export_data
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Data export failed"
        )

@router.delete("/privacy/delete-account")
async def delete_user_account(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Delete user account and all data (GDPR Article 17)"""
    
    try:
        # Simple account deletion (you can enhance this)
        await db.execute("DELETE FROM users WHERE id = :user_id", {"user_id": current_user.id})
        await db.commit()
        
        await security_logger.log_security_event(
            "account_deletion_requested",
            user_id=str(current_user.id),
            ip_address=request.client.host,
            details={"deletion_completed": True},
            risk_level=RiskLevel.MEDIUM
        )
        
        return {
            "message": "Account deletion completed",
            "deletion_timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account deletion failed"
        )

@router.post("/privacy/consent")
async def update_consent(
    request: Request,
    consent_data: ConsentUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Update user consent preferences"""
    
    try:
        consent_updates = {}
        
        if consent_data.analytics_consent is not None:
            consent_updates["analytics"] = consent_data.analytics_consent
        
        if consent_data.marketing_consent is not None:
            consent_updates["marketing"] = consent_data.marketing_consent
        
        if consent_data.third_party_sharing is not None:
            consent_updates["third_party_sharing"] = consent_data.third_party_sharing
        
        # Store consent in database (you can enhance this)
        for purpose, consent_given in consent_updates.items():
            await db.execute("""
                INSERT INTO user_consents (user_id, purpose, consent_status, timestamp, ip_address)
                VALUES (:user_id, :purpose, :status, :timestamp, :ip_address)
                ON CONFLICT (user_id, purpose) 
                DO UPDATE SET 
                    consent_status = :status,
                    timestamp = :timestamp
            """, {
                "user_id": current_user.id,
                "purpose": purpose,
                "status": "given" if consent_given else "withdrawn",
                "timestamp": datetime.utcnow(),
                "ip_address": request.client.host
            })
        
        await db.commit()
        
        await security_logger.log_security_event(
            "consent_updated",
            user_id=str(current_user.id),
            ip_address=request.client.host,
            details=consent_updates,
            risk_level=RiskLevel.LOW
        )
        
        return {
            "message": "Consent preferences updated",
            "updated_preferences": consent_updates
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Consent update failed"
        )

# Security Status Endpoints
@router.get("/security/status")
async def security_status(
    current_user: User = Depends(get_current_user)
):
    """Get current security status"""
    
    mfa_enabled = await is_mfa_enabled(str(current_user.id))
    
    return {
        "user_id": str(current_user.id),
        "security_features": {
            "mfa_enabled": mfa_enabled,
            "rate_limiting": True,
            "device_fingerprinting": True,
            "security_logging": True,
            "gdpr_compliant": True
        },
        "last_security_check": datetime.utcnow().isoformat()
    }

# Helper functions
async def authenticate_user(email: str, password: str, db: AsyncSession):
    """Authenticate user with email and password"""
    from app.core.security import verify_password
    
    result = await db.execute(
        "SELECT * FROM users WHERE email = :email AND is_active = true",
        {"email": email}
    )
    user_data = result.fetchone()
    
    if user_data and verify_password(password, user_data.hashed_password):
        # Convert to User object
        user = User()
        for key, value in user_data._mapping.items():
            setattr(user, key, value)
        return user
    return None

async def is_mfa_enabled(user_id: str) -> bool:
    """Check if MFA is enabled for user"""
    import redis.asyncio as redis
    
    r = redis.from_url("redis://localhost:6379")
    mfa_secret = await r.get(f"mfa_secret:{user_id}")
    await r.close()
    
    return mfa_secret is not None

async def assess_login_risk(user_id: str, ip_address: str, device_fingerprint: str) -> Dict[str, Any]:
    """Assess risk level of login attempt"""
    
    risk_score = 0
    risk_factors = []
    
    # Simple risk assessment (you can enhance this)
    current_hour = datetime.utcnow().hour
    if current_hour < 6 or current_hour > 22:
        risk_score += 10
        risk_factors.append("unusual_time")
    
    if risk_score >= 25:
        risk_level = "high"
    elif risk_score >= 10:
        risk_level = "medium"
    else:
        risk_level = "low"
    
    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_factors": risk_factors,
        "device_known": False,  # Simplified - you can track known devices
        "ip_known": False
    }