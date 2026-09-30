# backend/app/core/enhanced_security.py
"""
Enterprise-grade security system for OffCall AI
Implements JWT hardening, MFA, rate limiting, and session management
"""

import asyncio
import hashlib
import secrets
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

import pyotp
import qrcode
from io import BytesIO
import base64
import redis
from fastapi import HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from cryptography.fernet import Fernet
import bcrypt

from app.core.config import settings
from app.database import get_redis

# Security Configuration
@dataclass
class SecurityConfig:
    # JWT Settings
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # Short-lived tokens
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    TOKEN_FAMILY_SIZE: int = 5  # Max refresh token family size
    
    # MFA Settings
    TOTP_WINDOW: int = 2  # Allow 2 time windows for TOTP
    BACKUP_CODES_COUNT: int = 10
    
    # Rate Limiting
    GLOBAL_RATE_LIMIT: int = 1000  # requests per minute per IP
    USER_RATE_LIMIT: int = 100     # requests per minute per user
    LOGIN_RATE_LIMIT: int = 5      # login attempts per minute
    
    # Session Security
    MAX_SESSIONS_PER_USER: int = 5
    SESSION_INACTIVITY_MINUTES: int = 30
    
    # Security Monitoring
    MAX_FAILED_LOGINS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15

security_config = SecurityConfig()

class TokenType(Enum):
    ACCESS = "access"
    REFRESH = "refresh"
    MFA = "mfa"
    RESET = "reset"

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# Enhanced JWT Token Manager
class EnhancedTokenManager:
    def __init__(self):
        self.redis = redis.from_url(settings.REDIS_URL)
        
        # Fix Fernet key generation
        try:
            from cryptography.fernet import Fernet
            import hashlib
            
            # Use the encryption key to generate a proper Fernet key
            key_material = settings.ENCRYPTION_KEY.encode()
            # Hash it to get consistent 32 bytes
            key_hash = hashlib.sha256(key_material).digest()
            # Encode as base64 for Fernet
            fernet_key = base64.urlsafe_b64encode(key_hash)
            
            self.cipher = Fernet(fernet_key)
            
        except Exception as e:
            print(f"⚠️  Encryption setup failed: {e}, using new key")
            # Fallback: generate a new key
            self.cipher = Fernet(Fernet.generate_key())
    
    async def create_token_pair(self, user_id: str, device_fingerprint: str, 
                               session_data: Dict = None) -> Dict[str, str]:
        """Create access and refresh token pair with family tracking"""
        
        # Generate unique token family ID
        family_id = secrets.token_urlsafe(32)
        
        # Create device-bound tokens
        access_payload = {
            "sub": user_id,
            "type": TokenType.ACCESS.value,
            "family_id": family_id,
            "device_fp": device_fingerprint,
            "session_data": session_data or {},
            "iat": datetime.utcnow().timestamp(),
            "exp": (datetime.utcnow() + timedelta(minutes=security_config.ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()
        }
        
        refresh_payload = {
            "sub": user_id,
            "type": TokenType.REFRESH.value,
            "family_id": family_id,
            "device_fp": device_fingerprint,
            "iat": datetime.utcnow().timestamp(),
            "exp": (datetime.utcnow() + timedelta(days=security_config.REFRESH_TOKEN_EXPIRE_DAYS)).timestamp()
        }
        
        # Sign tokens
        access_token = self._sign_token(access_payload)
        refresh_token = self._sign_token(refresh_payload)
        
        # Store token family in Redis
        await self._store_token_family(family_id, user_id, refresh_token)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": security_config.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
    
    async def refresh_token_pair(self, refresh_token: str, 
                                device_fingerprint: str) -> Dict[str, str]:
        """Refresh token pair with rotation and family validation"""
        
        # Validate refresh token
        payload = self._verify_token(refresh_token)
        if not payload or payload.get("type") != TokenType.REFRESH.value:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        user_id = payload["sub"]
        family_id = payload["family_id"]
        token_device_fp = payload.get("device_fp")
        
        # Validate device fingerprint
        if token_device_fp != device_fingerprint:
            await self._invalidate_token_family(family_id)
            raise HTTPException(status_code=401, detail="Device fingerprint mismatch")
        
        # Check if token family exists and is valid
        if not await self._is_token_family_valid(family_id, refresh_token):
            raise HTTPException(status_code=401, detail="Token family compromised")
        
        # Create new token pair
        new_tokens = await self.create_token_pair(user_id, device_fingerprint)
        
        # Invalidate old refresh token
        await self._rotate_refresh_token(family_id, refresh_token, new_tokens["refresh_token"])
        
        return new_tokens
    
    def _sign_token(self, payload: Dict) -> str:
        """Sign token with additional security measures"""
        from jose import jwt
        
        # Add security headers
        headers = {
            "alg": "RS256",
            "typ": "JWT",
            "kid": settings.JWT_KEY_ID
        }
        
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="RS256", headers=headers)
    
    def _verify_token(self, token: str) -> Optional[Dict]:
        """Verify token with blacklist checking"""
        from jose import jwt, JWTError
        
        try:
            # Check token blacklist
            if self._is_token_blacklisted(token):
                return None
                
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["RS256"])
            return payload
        except JWTError:
            return None
    
    async def _store_token_family(self, family_id: str, user_id: str, refresh_token: str):
        """Store token family in Redis for tracking"""
        family_key = f"token_family:{family_id}"
        family_data = {
            "user_id": user_id,
            "tokens": [refresh_token],
            "created_at": datetime.utcnow().isoformat(),
            "last_used": datetime.utcnow().isoformat()
        }
        
        await self.redis.setex(
            family_key, 
            security_config.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
            self.cipher.encrypt(str(family_data).encode())
        )
    
    def _is_token_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted"""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return self.redis.exists(f"blacklist:{token_hash}")

# Multi-Factor Authentication Manager
class MFAManager:
    def __init__(self):
        self.redis = get_redis()
    
    async def generate_totp_secret(self, user_id: str) -> Dict[str, str]:
        """Generate TOTP secret and QR code for user"""
        secret = pyotp.random_base32()
        
        # Store secret temporarily (user must verify before enabling)
        await self.redis.setex(
            f"mfa_setup:{user_id}", 
            300,  # 5 minutes to complete setup
            secret
        )
        
        # Generate QR code
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=f"user_{user_id}",
            issuer_name="OffCall AI"
        )
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return {
            "secret": secret,
            "qr_code": f"data:image/png;base64,{qr_code_base64}",
            "provisioning_uri": provisioning_uri
        }
    
    async def verify_totp_setup(self, user_id: str, code: str) -> bool:
        """Verify TOTP code during setup"""
        secret = await self.redis.get(f"mfa_setup:{user_id}")
        if not secret:
            return False
        
        totp = pyotp.TOTP(secret.decode())
        if totp.verify(code, valid_window=security_config.TOTP_WINDOW):
            # Move secret to permanent storage
            await self.redis.delete(f"mfa_setup:{user_id}")
            await self.redis.set(f"mfa_secret:{user_id}", secret)
            return True
        
        return False
    
    async def verify_totp_code(self, user_id: str, code: str) -> bool:
        """Verify TOTP code for authentication"""
        secret = await self.redis.get(f"mfa_secret:{user_id}")
        if not secret:
            return False
        
        totp = pyotp.TOTP(secret.decode())
        return totp.verify(code, valid_window=security_config.TOTP_WINDOW)
    
    async def generate_backup_codes(self, user_id: str) -> List[str]:
        """Generate backup codes for MFA"""
        codes = [secrets.token_hex(4).upper() for _ in range(security_config.BACKUP_CODES_COUNT)]

        # Hash and store backup codes - use JSON for safe serialization
        hashed_codes = [bcrypt.hashpw(code.encode(), bcrypt.gensalt()).decode() for code in codes]
        import json
        await self.redis.set(f"mfa_backup:{user_id}", json.dumps(hashed_codes))

        return codes

    async def verify_backup_code(self, user_id: str, code: str) -> bool:
        """Verify and consume backup code"""
        stored_codes = await self.redis.get(f"mfa_backup:{user_id}")
        if not stored_codes:
            return False

        # SECURITY FIX: Use json.loads instead of eval to prevent code injection
        import json
        try:
            hashed_codes = json.loads(stored_codes.decode())
        except (json.JSONDecodeError, AttributeError):
            # Invalid data format - could be old format or corrupted
            return False

        for i, hashed_code in enumerate(hashed_codes):
            if bcrypt.checkpw(code.encode(), hashed_code.encode()):
                # Remove used code
                hashed_codes.pop(i)
                await self.redis.set(f"mfa_backup:{user_id}", json.dumps(hashed_codes))
                return True

        return False

# Advanced Rate Limiter
class RateLimiter:
    def __init__(self):
        self.redis = get_redis()
    
    async def check_rate_limit(self, identifier: str, limit: int, 
                              window_seconds: int = 60) -> Dict[str, Any]:
        """Sliding window rate limiter with Redis"""
        now = time.time()
        window_start = now - window_seconds
        
        # Clean old entries
        await self.redis.zremrangebyscore(f"rate_limit:{identifier}", 0, window_start)
        
        # Count current requests
        current_requests = await self.redis.zcard(f"rate_limit:{identifier}")
        
        if current_requests >= limit:
            # Get reset time
            oldest_request = await self.redis.zrange(f"rate_limit:{identifier}", 0, 0, withscores=True)
            reset_time = oldest_request[0][1] + window_seconds if oldest_request else now + window_seconds
            
            return {
                "allowed": False,
                "current": current_requests,
                "limit": limit,
                "reset_time": reset_time,
                "retry_after": int(reset_time - now)
            }
        
        # Add current request
        await self.redis.zadd(f"rate_limit:{identifier}", {str(now): now})
        await self.redis.expire(f"rate_limit:{identifier}", window_seconds)
        
        return {
            "allowed": True,
            "current": current_requests + 1,
            "limit": limit,
            "remaining": limit - current_requests - 1
        }
    
    async def check_multiple_limits(self, request: Request, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Check multiple rate limits simultaneously"""
        client_ip = request.client.host
        
        # Define rate limit checks
        checks = [
            ("global", f"ip:{client_ip}", security_config.GLOBAL_RATE_LIMIT, 60),
        ]
        
        if user_id:
            checks.append(("user", f"user:{user_id}", security_config.USER_RATE_LIMIT, 60))
        
        # Check all limits
        for limit_type, identifier, limit, window in checks:
            result = await self.check_rate_limit(identifier, limit, window)
            if not result["allowed"]:
                result["limit_type"] = limit_type
                return result
        
        return {"allowed": True}

# Device Fingerprinting
class DeviceFingerprinter:
    @staticmethod
    def generate_fingerprint(request: Request, user_agent: str = None) -> str:
        """Generate device fingerprint from request"""
        components = [
            request.client.host,
            user_agent or request.headers.get("user-agent", ""),
            request.headers.get("accept-language", ""),
            request.headers.get("accept-encoding", ""),
            str(request.url.port or 80),
        ]
        
        fingerprint_data = "|".join(components)
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:32]

# Security Event Logger
class SecurityEventLogger:
    def __init__(self):
        self.redis = get_redis()
    
    async def log_security_event(self, event_type: str, user_id: str = None, 
                                 ip_address: str = None, details: Dict = None,
                                 risk_level: RiskLevel = RiskLevel.LOW):
        """Log security event for monitoring"""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "ip_address": ip_address,
            "risk_level": risk_level.value,
            "details": details or {}
        }
        
        # Store in Redis for real-time monitoring
        await self.redis.lpush(
            "security_events",
            str(event)
        )
        await self.redis.ltrim("security_events", 0, 10000)  # Keep last 10k events
        
        # Alert on high/critical risk events
        if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            await self._send_security_alert(event)
    
    async def _send_security_alert(self, event: Dict):
        """Send security alert for high-risk events"""
        # TODO: Implement Slack/email alerting
        print(f"🚨 SECURITY ALERT: {event}")

# Initialize security components
token_manager = EnhancedTokenManager()
mfa_manager = MFAManager()
rate_limiter = RateLimiter()
security_logger = SecurityEventLogger()