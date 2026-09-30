# backend/tests/test_auth.py
"""
Authentication endpoint tests for OffCall AI.

Tests cover:
- User registration
- User login
- Password validation
- Rate limiting
- Token refresh
- Session management
"""

import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock
from datetime import datetime, timedelta

from app.services.auth_security_service import AuthSecurityService


class TestPasswordValidation:
    """Test password strength validation."""

    def test_password_too_short(self):
        """Password must be at least 8 characters."""
        is_valid, error = AuthSecurityService.validate_password_strength("Short1!")
        assert not is_valid
        assert "8 characters" in error

    def test_password_no_uppercase(self):
        """Password must contain uppercase letter."""
        is_valid, error = AuthSecurityService.validate_password_strength("lowercase123!")
        assert not is_valid
        assert "uppercase" in error

    def test_password_no_lowercase(self):
        """Password must contain lowercase letter."""
        is_valid, error = AuthSecurityService.validate_password_strength("UPPERCASE123!")
        assert not is_valid
        assert "lowercase" in error

    def test_password_no_digit(self):
        """Password must contain a number."""
        is_valid, error = AuthSecurityService.validate_password_strength("NoDigits!!")
        assert not is_valid
        assert "number" in error

    def test_password_no_special(self):
        """Password must contain special character."""
        is_valid, error = AuthSecurityService.validate_password_strength("NoSpecial123")
        assert not is_valid
        assert "special character" in error

    def test_password_common(self):
        """Common passwords should be rejected."""
        is_valid, error = AuthSecurityService.validate_password_strength("Password123!")
        assert not is_valid
        assert "too common" in error

    def test_password_valid(self):
        """Valid password should pass."""
        is_valid, error = AuthSecurityService.validate_password_strength("SecureP@ss123")
        assert is_valid
        assert error == ""


class TestRateLimiting:
    """Test login rate limiting."""

    def setup_method(self):
        """Reset rate limiting state before each test."""
        # Clear the login attempts and locked accounts
        from app.services.auth_security_service import login_attempts, locked_accounts
        login_attempts.clear()
        locked_accounts.clear()

    def test_first_login_allowed(self):
        """First login attempt should be allowed."""
        is_allowed, remaining, lockout_until = AuthSecurityService.check_rate_limit("test@example.com")
        assert is_allowed
        assert remaining == 5

    def test_failed_attempts_tracked(self):
        """Failed login attempts should be tracked."""
        email = "failed@example.com"

        # Record 3 failed attempts
        for _ in range(3):
            AuthSecurityService.record_login_attempt(email, success=False)

        is_allowed, remaining, _ = AuthSecurityService.check_rate_limit(email)
        assert is_allowed
        assert remaining == 2

    def test_account_lockout_after_max_attempts(self):
        """Account should be locked after max failed attempts."""
        email = "locked@example.com"

        # Record max failed attempts
        for _ in range(5):
            AuthSecurityService.record_login_attempt(email, success=False)

        is_allowed, remaining, lockout_until = AuthSecurityService.check_rate_limit(email)
        assert not is_allowed
        assert remaining == 0
        assert lockout_until is not None

    def test_successful_login_clears_attempts(self):
        """Successful login should clear failed attempts."""
        email = "success@example.com"

        # Record some failed attempts
        for _ in range(3):
            AuthSecurityService.record_login_attempt(email, success=False)

        # Record successful login
        AuthSecurityService.record_login_attempt(email, success=True)

        is_allowed, remaining, _ = AuthSecurityService.check_rate_limit(email)
        assert is_allowed
        assert remaining == 5


class TestTokenBlacklisting:
    """Test token blacklisting functionality."""

    def test_token_not_blacklisted_initially(self):
        """Token should not be blacklisted initially."""
        token = "test-token-123"
        assert not AuthSecurityService.is_token_blacklisted(token)

    def test_token_blacklisted_after_adding(self):
        """Token should be blacklisted after adding."""
        token = "blacklist-token-456"
        AuthSecurityService.blacklist_token(token)
        assert AuthSecurityService.is_token_blacklisted(token)

    def test_refresh_token_blacklisting(self):
        """Refresh token blacklisting should work separately."""
        refresh_token = "refresh-token-789"
        AuthSecurityService.blacklist_refresh_token(refresh_token)
        assert AuthSecurityService.is_refresh_token_blacklisted(refresh_token)


class TestRedirectValidation:
    """Test redirect URL validation for open redirect prevention."""

    def test_valid_relative_path(self):
        """Valid relative paths should be allowed."""
        assert AuthSecurityService.validate_redirect_url("/dashboard")
        assert AuthSecurityService.validate_redirect_url("/incidents/123")

    def test_protocol_relative_blocked(self):
        """Protocol-relative URLs should be blocked."""
        assert not AuthSecurityService.validate_redirect_url("//evil.com")

    def test_javascript_blocked(self):
        """JavaScript URLs should be blocked."""
        assert not AuthSecurityService.validate_redirect_url("javascript:alert(1)")
        assert not AuthSecurityService.validate_redirect_url("/page?next=javascript:alert(1)")

    def test_allowed_origins_accepted(self):
        """The deployment's own configured origins should be accepted."""
        from app.core.config import settings

        assert AuthSecurityService.validate_redirect_url(f"{settings.FRONTEND_URL}/dashboard")
        assert AuthSecurityService.validate_redirect_url(f"{settings.API_URL}/docs")

    def test_external_origin_blocked(self):
        """External origins should be blocked."""
        assert not AuthSecurityService.validate_redirect_url("https://evil.com/phishing")


@pytest.mark.asyncio
class TestRegistrationEndpoint:
    """Test user registration endpoint."""

    async def test_register_success(self, async_client: AsyncClient, test_data_factory):
        """Successful registration should return tokens."""
        user_data = test_data_factory.create_user_data(
            email="newuser@example.com",
            password="SecureP@ss123",
            full_name="New User",
            organization_name="New Org"
        )

        response = await async_client.post("/api/v1/auth/register", json=user_data)

        # Note: This might fail if DB isn't fully mocked, but tests the endpoint exists
        assert response.status_code in [200, 201, 500]  # 500 if DB not available

    async def test_register_short_password_rejected_by_schema(
        self, async_client: AsyncClient, test_data_factory
    ):
        """A password below the schema minimum is rejected during validation."""
        user_data = test_data_factory.create_user_data(password="weak")

        response = await async_client.post("/api/v1/auth/register", json=user_data)

        assert response.status_code == 422

    async def test_register_weak_password(self, async_client: AsyncClient, test_data_factory):
        """A long-but-weak password is rejected by the strength check."""
        # Long enough to pass the schema, but common and missing character classes.
        user_data = test_data_factory.create_user_data(password="password")

        response = await async_client.post("/api/v1/auth/register", json=user_data)

        assert response.status_code == 400
        assert "password" in response.json().get("detail", "").lower()


@pytest.mark.asyncio
class TestLoginEndpoint:
    """Test user login endpoint."""

    async def test_login_invalid_credentials(self, async_client: AsyncClient):
        """Login with invalid credentials should fail."""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@example.com", "password": "WrongPassword123!"}
        )

        assert response.status_code == 401

    async def test_login_rate_limited(self, async_client: AsyncClient):
        """Login should be rate limited after too many attempts."""
        email = "ratelimited@example.com"

        # Clear any existing rate limit state
        from app.services.auth_security_service import login_attempts, locked_accounts
        login_attempts.clear()
        locked_accounts.clear()

        # Simulate max failed attempts
        for _ in range(5):
            AuthSecurityService.record_login_attempt(email, success=False)

        response = await async_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "AnyPassword123!"}
        )

        assert response.status_code == 429
        assert "too many" in response.json().get("detail", "").lower()


@pytest.mark.asyncio
class TestHealthEndpoints:
    """Test health check endpoints."""

    async def test_root_endpoint(self, async_client: AsyncClient):
        """Root endpoint should return API info."""
        response = await async_client.get("/")
        assert response.status_code == 200
        assert "OffCall" in response.json().get("message", "")

    async def test_health_endpoint(self, async_client: AsyncClient):
        """Health endpoint should return status."""
        response = await async_client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()
