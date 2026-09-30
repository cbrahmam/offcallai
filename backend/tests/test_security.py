# backend/tests/test_security.py
"""
Security feature tests for OffCall AI.

Tests cover:
- Input sanitization
- Session management
- Audit logging
- Security headers
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
import uuid

from app.middleware.input_sanitization import InputSanitizer, sanitize_request_data
from app.services.audit_service import AuditService, SessionManager, AuditCategory


class TestInputSanitization:
    """Test input sanitization functionality."""

    def test_sanitize_removes_script_tags(self):
        """Script tags should be removed."""
        malicious = "<script>alert('xss')</script>Hello"
        result = InputSanitizer.sanitize_string(malicious)
        assert "<script>" not in result
        assert "Hello" in result

    def test_sanitize_removes_javascript_protocol(self):
        """JavaScript protocol should be removed."""
        malicious = "javascript:alert('xss')"
        result = InputSanitizer.sanitize_string(malicious)
        assert "javascript:" not in result

    def test_sanitize_removes_event_handlers(self):
        """Event handlers should be removed."""
        malicious = '<img onerror="alert(1)" src="x">'
        result = InputSanitizer.sanitize_string(malicious)
        assert "onerror=" not in result

    def test_sanitize_removes_iframe(self):
        """Iframe tags should be removed."""
        malicious = '<iframe src="https://evil.com"></iframe>Content'
        result = InputSanitizer.sanitize_string(malicious)
        assert "<iframe" not in result

    def test_sanitize_escapes_html_by_default(self):
        """HTML should be escaped by default."""
        html = "<div>Hello</div>"
        result = InputSanitizer.sanitize_string(html)
        assert "&lt;div&gt;" in result

    def test_sanitize_allows_html_when_specified(self):
        """HTML should not be escaped when allow_html=True."""
        html = "<div>Hello</div>"
        result = InputSanitizer.sanitize_string(html, allow_html=True)
        assert "<div>" in result

    def test_sanitize_dict_recursively(self):
        """Dictionaries should be sanitized recursively."""
        data = {
            "name": "<script>xss</script>John",
            "nested": {
                "value": "javascript:alert(1)"
            }
        }
        result = InputSanitizer.sanitize_value(data)
        assert "<script>" not in result["name"]
        assert "javascript:" not in result["nested"]["value"]

    def test_sanitize_list_recursively(self):
        """Lists should be sanitized recursively."""
        data = ["<script>xss</script>", "normal", "<img onerror=''>"]
        result = InputSanitizer.sanitize_value(data)
        for item in result:
            assert "<script>" not in item
            assert "onerror=" not in item

    def test_sql_injection_detection(self):
        """SQL injection patterns should be detected."""
        sql_patterns = [
            "' OR 1=1 --",
            "'; DROP TABLE users; --",
            "UNION SELECT * FROM passwords",
        ]
        for pattern in sql_patterns:
            assert InputSanitizer.check_sql_injection(pattern)

    def test_normal_text_not_flagged_as_sql(self):
        """Normal text should not be flagged as SQL injection."""
        normal = "This is a normal search query"
        assert not InputSanitizer.check_sql_injection(normal)

    def test_validate_email_valid(self):
        """Valid emails should pass validation."""
        assert InputSanitizer.validate_email("user@example.com")
        assert InputSanitizer.validate_email("user.name@company.co.uk")

    def test_validate_email_invalid(self):
        """Invalid emails should fail validation."""
        assert not InputSanitizer.validate_email("not-an-email")
        assert not InputSanitizer.validate_email("@missing-local.com")

    def test_validate_uuid_valid(self):
        """Valid UUIDs should pass validation."""
        valid_uuid = str(uuid.uuid4())
        assert InputSanitizer.validate_uuid(valid_uuid)

    def test_validate_uuid_invalid(self):
        """Invalid UUIDs should fail validation."""
        assert not InputSanitizer.validate_uuid("not-a-uuid")
        assert not InputSanitizer.validate_uuid("12345678-1234-1234-1234")

    def test_sanitize_filename_removes_path_traversal(self):
        """Path traversal attempts should be sanitized."""
        malicious = "../../../etc/passwd"
        result = InputSanitizer.sanitize_filename(malicious)
        assert ".." not in result
        assert "/" not in result

    def test_sanitize_filename_removes_special_chars(self):
        """Special characters should be replaced."""
        filename = 'file:name<with>special"chars?.txt'
        result = InputSanitizer.sanitize_filename(filename)
        assert ":" not in result
        assert "<" not in result
        assert "?" not in result

    def test_truncate_long_string(self):
        """Long strings should be truncated."""
        long_string = "x" * 20000
        result = InputSanitizer.truncate_string(long_string, max_length=100)
        assert len(result) <= 120  # 100 + "[truncated]"
        assert "[truncated]" in result


class TestSanitizeRequestData:
    """Test the sanitize_request_data function."""

    def test_sanitize_simple_dict(self):
        """Simple dictionaries should be sanitized."""
        data = {"name": "<script>xss</script>"}
        result = sanitize_request_data(data)
        assert "<script>" not in result["name"]

    def test_allow_html_in_specific_fields(self):
        """HTML should be allowed in specified fields."""
        data = {
            "title": "<b>Bold Title</b>",
            "content": "<script>xss</script>Content"
        }
        result = sanitize_request_data(data, allow_html_fields=["title"])
        assert "<b>" in result["title"]
        assert "<script>" not in result["content"]


class TestSessionManager:
    """Test session management functionality."""

    def setup_method(self):
        """Reset session manager state."""
        SessionManager._invalidated_users.clear()

    def test_session_valid_initially(self):
        """Sessions should be valid initially."""
        user_id = str(uuid.uuid4())
        token_issued = datetime.utcnow()
        assert SessionManager.is_session_valid(user_id, token_issued)

    def test_session_invalid_after_invalidation(self):
        """Sessions issued before invalidation should be invalid."""
        user_id = str(uuid.uuid4())
        token_issued = datetime.utcnow() - timedelta(hours=1)

        SessionManager.invalidate_user_sessions(user_id, "test")

        assert not SessionManager.is_session_valid(user_id, token_issued)

    def test_new_session_valid_after_invalidation(self):
        """Sessions issued after invalidation should be valid."""
        user_id = str(uuid.uuid4())

        SessionManager.invalidate_user_sessions(user_id, "test")

        token_issued = datetime.utcnow() + timedelta(seconds=1)
        assert SessionManager.is_session_valid(user_id, token_issued)

    def test_clear_invalidation(self):
        """Clearing invalidation should make old sessions valid again."""
        user_id = str(uuid.uuid4())
        token_issued = datetime.utcnow() - timedelta(hours=1)

        SessionManager.invalidate_user_sessions(user_id, "test")
        SessionManager.clear_user_invalidation(user_id)

        assert SessionManager.is_session_valid(user_id, token_issued)


@pytest.mark.asyncio
class TestAuditService:
    """Test audit logging service."""

    async def test_log_creates_entry(self):
        """Logging should create an audit entry."""
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        audit_service = AuditService(mock_db)

        org_id = uuid.uuid4()
        await audit_service.log(
            organization_id=org_id,
            action="test_action",
            description="Test description"
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    async def test_log_login_success(self):
        """Login success should be logged."""
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        mock_request = MagicMock()
        mock_request.headers = {"X-Forwarded-For": "1.2.3.4", "User-Agent": "Test"}
        mock_request.client = MagicMock()
        mock_request.client.host = "1.2.3.4"

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.organization_id = uuid.uuid4()
        mock_user.email = "test@example.com"
        mock_user.full_name = "Test User"

        audit_service = AuditService(mock_db)
        await audit_service.log_login_success(mock_request, mock_user)

        mock_db.add.assert_called_once()
        call_args = mock_db.add.call_args[0][0]
        assert call_args.action == "user_login"

    async def test_log_role_change_is_critical(self):
        """Role changes should be logged as critical."""
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client = MagicMock()
        mock_request.client.host = "1.2.3.4"

        mock_admin = MagicMock()
        mock_admin.id = uuid.uuid4()
        mock_admin.organization_id = uuid.uuid4()
        mock_admin.email = "admin@example.com"
        mock_admin.full_name = "Admin"

        mock_target = MagicMock()
        mock_target.id = uuid.uuid4()
        mock_target.email = "user@example.com"

        audit_service = AuditService(mock_db)
        await audit_service.log_role_change(
            mock_request, mock_admin, mock_target,
            old_role="user", new_role="admin"
        )

        call_args = mock_db.add.call_args[0][0]
        assert call_args.action == "role_change"
        assert call_args.extra_data.get("severity") == "critical"


class TestSecurityHeaders:
    """Test security headers are properly set."""

    def test_security_headers_in_response(self, client):
        """Security headers should be present in responses."""
        response = client.get("/health")

        # Check essential security headers
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert "max-age=" in response.headers.get("Strict-Transport-Security", "")
        assert response.headers.get("Referrer-Policy") is not None

    def test_csp_header_present(self, client):
        """Content-Security-Policy header should be present."""
        response = client.get("/health")
        csp = response.headers.get("Content-Security-Policy", "")

        assert "default-src" in csp
        assert "script-src" in csp
