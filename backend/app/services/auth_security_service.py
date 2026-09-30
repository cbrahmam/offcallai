# backend/app/services/auth_security_service.py
"""
Authentication Security Service
Handles rate limiting, account lockout, password validation, and token management
"""

import re
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, Set
from collections import defaultdict
import asyncio
from app.core.config import settings

logger = logging.getLogger(__name__)

# In-memory stores (in production, use Redis)
login_attempts: dict = defaultdict(list)  # email -> list of attempt timestamps
locked_accounts: dict = {}  # email -> unlock_time
blacklisted_tokens: Set[str] = set()  # Set of invalidated token hashes

# Configuration
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15
ATTEMPT_WINDOW_MINUTES = 15
TOKEN_BLACKLIST_CLEANUP_HOURS = 24


class AuthSecurityService:
    """Security service for authentication-related operations"""

    # Password requirements
    MIN_PASSWORD_LENGTH = 8
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL = True

    @staticmethod
    def validate_password_strength(password: str) -> Tuple[bool, str]:
        """
        Validate password meets security requirements
        Returns (is_valid, error_message)
        """
        if len(password) < AuthSecurityService.MIN_PASSWORD_LENGTH:
            return False, f"Password must be at least {AuthSecurityService.MIN_PASSWORD_LENGTH} characters long"

        if AuthSecurityService.REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"

        if AuthSecurityService.REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"

        if AuthSecurityService.REQUIRE_DIGIT and not re.search(r'\d', password):
            return False, "Password must contain at least one number"

        if AuthSecurityService.REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;\'`~]', password):
            return False, "Password must contain at least one special character (!@#$%^&*...)"

        # Check for common weak passwords
        common_passwords = [
            'password', '123456', 'password123', 'admin', 'letmein',
            'welcome', 'monkey', 'dragon', 'master', 'qwerty',
            'login', 'abc123', 'iloveyou', 'admin123', 'root'
        ]
        # Compare on the alphanumeric core so "Password123!" is caught as well
        # as "password123".
        stripped = re.sub(r'[^a-z0-9]', '', password.lower())
        if password.lower() in common_passwords or stripped in common_passwords:
            return False, "This password is too common. Please choose a stronger password"

        return True, ""

    @staticmethod
    def check_rate_limit(email: str) -> Tuple[bool, int, Optional[datetime]]:
        """
        Check if login is rate limited for this email
        Returns (is_allowed, remaining_attempts, lockout_until)
        """
        email_lower = email.lower()
        now = datetime.utcnow()

        # Check if account is locked
        if email_lower in locked_accounts:
            unlock_time = locked_accounts[email_lower]
            if now < unlock_time:
                return False, 0, unlock_time
            else:
                # Lockout expired, remove it
                del locked_accounts[email_lower]
                # Clear old attempts
                login_attempts[email_lower] = []

        # Clean up old attempts outside the window
        window_start = now - timedelta(minutes=ATTEMPT_WINDOW_MINUTES)
        login_attempts[email_lower] = [
            attempt for attempt in login_attempts[email_lower]
            if attempt > window_start
        ]

        # Calculate remaining attempts
        current_attempts = len(login_attempts[email_lower])
        remaining = MAX_LOGIN_ATTEMPTS - current_attempts

        if remaining <= 0:
            # Lock the account
            unlock_time = now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            locked_accounts[email_lower] = unlock_time
            return False, 0, unlock_time

        return True, remaining, None

    @staticmethod
    def record_login_attempt(email: str, success: bool) -> None:
        """Record a login attempt"""
        email_lower = email.lower()
        now = datetime.utcnow()

        if success:
            # Clear attempts on successful login
            login_attempts[email_lower] = []
            if email_lower in locked_accounts:
                del locked_accounts[email_lower]
            logger.info(f"Successful login for user (attempts cleared)")
        else:
            # Record failed attempt
            login_attempts[email_lower].append(now)
            logger.warning(f"Failed login attempt recorded for user")

    @staticmethod
    def get_lockout_status(email: str) -> Optional[dict]:
        """Get lockout status for an email"""
        email_lower = email.lower()
        now = datetime.utcnow()

        if email_lower in locked_accounts:
            unlock_time = locked_accounts[email_lower]
            if now < unlock_time:
                remaining_seconds = (unlock_time - now).total_seconds()
                return {
                    "locked": True,
                    "unlock_at": unlock_time.isoformat(),
                    "remaining_seconds": int(remaining_seconds)
                }

        attempts = len(login_attempts.get(email_lower, []))
        remaining = max(0, MAX_LOGIN_ATTEMPTS - attempts)

        return {
            "locked": False,
            "attempts_used": attempts,
            "attempts_remaining": remaining
        }

    @staticmethod
    def hash_token(token: str) -> str:
        """Create a hash of a token for blacklisting (don't store full tokens)"""
        return hashlib.sha256(token.encode()).hexdigest()[:32]

    @staticmethod
    def blacklist_token(token: str) -> None:
        """Add a token to the blacklist (for logout)"""
        token_hash = AuthSecurityService.hash_token(token)
        blacklisted_tokens.add(token_hash)
        logger.info("Token added to blacklist")

    @staticmethod
    def is_token_blacklisted(token: str) -> bool:
        """Check if a token has been blacklisted"""
        token_hash = AuthSecurityService.hash_token(token)
        return token_hash in blacklisted_tokens

    @staticmethod
    def blacklist_refresh_token(refresh_token: str) -> None:
        """Blacklist a refresh token"""
        token_hash = AuthSecurityService.hash_token(refresh_token)
        blacklisted_tokens.add(f"refresh_{token_hash}")
        logger.info("Refresh token added to blacklist")

    @staticmethod
    def is_refresh_token_blacklisted(refresh_token: str) -> bool:
        """Check if a refresh token has been blacklisted"""
        token_hash = AuthSecurityService.hash_token(refresh_token)
        return f"refresh_{token_hash}" in blacklisted_tokens

    @staticmethod
    def validate_redirect_url(url: str) -> bool:
        """
        Validate that a redirect URL is safe (prevent open redirect attacks)
        Only allow relative paths or same-origin URLs
        """
        if not url:
            return False

        # Allow relative paths starting with /
        if url.startswith('/'):
            # Block protocol-relative URLs like //evil.com
            if url.startswith('//'):
                return False

            # Block javascript: and data: URLs
            lower_url = url.lower()
            if 'javascript:' in lower_url or 'data:' in lower_url:
                return False

            # Block URLs with encoded characters that might bypass checks
            if '%' in url:
                try:
                    from urllib.parse import unquote
                    decoded = unquote(url)
                    if decoded.startswith('//') or 'javascript:' in decoded.lower():
                        return False
                except (ValueError, UnicodeDecodeError):
                    return False  # Block if decoding fails

            return True

        # Only redirect to this deployment's own frontend/API origins
        allowed_origins = [
            settings.FRONTEND_URL,
            settings.API_URL,
            *settings.CORS_ORIGINS,
        ]

        for origin in allowed_origins:
            if url.startswith(origin):
                return True

        return False

    @staticmethod
    def sanitize_log_message(message: str, sensitive_fields: list = None) -> str:
        """
        Sanitize log messages by removing sensitive data
        """
        if sensitive_fields is None:
            sensitive_fields = ['password', 'token', 'secret', 'key', 'authorization']

        sanitized = message
        for field in sensitive_fields:
            # Pattern to match field=value or "field": "value"
            patterns = [
                rf'{field}["\']?\s*[:=]\s*["\']?[^"\'\s,}}]+["\']?',
                rf'{field.upper()}["\']?\s*[:=]\s*["\']?[^"\'\s,}}]+["\']?',
            ]
            for pattern in patterns:
                sanitized = re.sub(pattern, f'{field}=[REDACTED]', sanitized, flags=re.IGNORECASE)

        return sanitized

    @staticmethod
    async def cleanup_expired_blacklist():
        """Periodically clean up expired tokens from blacklist"""
        # In a real implementation, tokens should have expiry timestamps
        # For now, we'll just limit the size of the blacklist
        max_blacklist_size = 10000
        if len(blacklisted_tokens) > max_blacklist_size:
            # Remove oldest entries (this is simplified - in production use Redis with TTL)
            excess = len(blacklisted_tokens) - max_blacklist_size
            for _ in range(excess):
                blacklisted_tokens.pop()


# Helper function for password validation message
def get_password_requirements() -> str:
    """Get human-readable password requirements"""
    requirements = [
        f"At least {AuthSecurityService.MIN_PASSWORD_LENGTH} characters"
    ]
    if AuthSecurityService.REQUIRE_UPPERCASE:
        requirements.append("One uppercase letter")
    if AuthSecurityService.REQUIRE_LOWERCASE:
        requirements.append("One lowercase letter")
    if AuthSecurityService.REQUIRE_DIGIT:
        requirements.append("One number")
    if AuthSecurityService.REQUIRE_SPECIAL:
        requirements.append("One special character")

    return ", ".join(requirements)
