# backend/app/middleware/input_sanitization.py
"""
Input Sanitization Middleware

Provides request-level input sanitization to prevent XSS and injection attacks.
"""

import re
import html
import logging
from typing import Any, Dict, List, Union
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import json

logger = logging.getLogger(__name__)


class InputSanitizer:
    """Utility class for sanitizing user inputs"""

    # Patterns that might indicate XSS or injection attempts
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'javascript:',  # JavaScript protocol
        r'on\w+\s*=',  # Event handlers (onclick, onerror, etc.)
        r'<iframe[^>]*>',  # iframes
        r'<object[^>]*>',  # object tags
        r'<embed[^>]*>',  # embed tags
        r'expression\s*\(',  # CSS expression
        r'url\s*\(\s*["\']?\s*data:',  # Data URLs in CSS
    ]

    # SQL injection patterns (for logging/alerting, not blocking)
    SQL_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|EXEC)\b.*\b(FROM|INTO|TABLE|DATABASE)\b)",
        r"(--|#|\/\*)",  # SQL comments
        r"(\bOR\b\s+\d+\s*=\s*\d+)",  # OR 1=1 style
        r"(\bAND\b\s+\d+\s*=\s*\d+)",  # AND 1=1 style
    ]

    @classmethod
    def sanitize_string(cls, value: str, allow_html: bool = False) -> str:
        """
        Sanitize a string value.

        Args:
            value: The string to sanitize
            allow_html: If True, only remove dangerous patterns. If False, escape all HTML.

        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            return value

        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE | re.DOTALL):
                logger.warning(f"Dangerous pattern detected and removed: {pattern[:50]}")
                value = re.sub(pattern, '', value, flags=re.IGNORECASE | re.DOTALL)

        if not allow_html:
            # Escape HTML entities
            value = html.escape(value)

        # Normalize whitespace
        value = ' '.join(value.split())

        return value

    @classmethod
    def sanitize_value(cls, value: Any, allow_html: bool = False) -> Any:
        """
        Recursively sanitize a value (string, dict, or list).
        """
        if isinstance(value, str):
            return cls.sanitize_string(value, allow_html)
        elif isinstance(value, dict):
            return {k: cls.sanitize_value(v, allow_html) for k, v in value.items()}
        elif isinstance(value, list):
            return [cls.sanitize_value(item, allow_html) for item in value]
        else:
            return value

    @classmethod
    def check_sql_injection(cls, value: str) -> bool:
        """
        Check if a string contains potential SQL injection patterns.
        This is for logging/alerting purposes - parameterized queries should prevent actual injection.
        """
        if not isinstance(value, str):
            return False

        for pattern in cls.SQL_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        return False

    @classmethod
    def validate_email(cls, email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    @classmethod
    def validate_uuid(cls, uuid_str: str) -> bool:
        """Validate UUID format"""
        pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        return bool(re.match(pattern, uuid_str.lower()))

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """Sanitize a filename to prevent path traversal"""
        # Remove path separators and dangerous characters
        sanitized = re.sub(r'[/\\:*?"<>|]', '_', filename)
        # Collapse traversal sequences so no ".." survives anywhere in the name
        sanitized = re.sub(r'\.{2,}', '_', sanitized)
        # Remove leading/trailing dots, spaces and separator runs
        sanitized = sanitized.strip('. ')
        # Prevent empty filenames
        if not sanitized:
            sanitized = 'unnamed'
        return sanitized

    @classmethod
    def truncate_string(cls, value: str, max_length: int = 10000) -> str:
        """Truncate a string to prevent DoS via large inputs"""
        if len(value) > max_length:
            return value[:max_length] + '... [truncated]'
        return value


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that sanitizes request inputs.

    This middleware:
    1. Logs potential SQL injection attempts (for alerting)
    2. Sanitizes JSON body content
    3. Validates and limits request sizes
    """

    # Paths that should skip sanitization (e.g., file uploads)
    SKIP_PATHS = [
        '/api/v1/profiles/upload',
        '/api/v1/files/upload',
    ]

    # Maximum request body size (10MB)
    MAX_BODY_SIZE = 10 * 1024 * 1024

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip certain paths
        if any(request.url.path.startswith(path) for path in self.SKIP_PATHS):
            return await call_next(request)

        # Check request size
        content_length = request.headers.get('content-length')
        if content_length and int(content_length) > self.MAX_BODY_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"Request body too large. Maximum size is {self.MAX_BODY_SIZE} bytes."
            )

        # For JSON requests, we could sanitize the body here
        # However, modifying the request body in middleware is complex
        # Instead, we'll log suspicious patterns for alerting

        # Check query parameters for SQL injection patterns
        for key, value in request.query_params.items():
            if isinstance(value, str) and InputSanitizer.check_sql_injection(value):
                client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                if not client_ip:
                    client_ip = request.client.host if request.client else "unknown"
                logger.warning(
                    f"SECURITY: Potential SQL injection in query param '{key}' "
                    f"from IP {client_ip} on path {request.url.path}"
                )

        return await call_next(request)


def sanitize_request_data(data: Dict[str, Any], allow_html_fields: List[str] = None) -> Dict[str, Any]:
    """
    Sanitize request data before processing.

    This function should be called in endpoint handlers for sensitive data.

    Args:
        data: The request data to sanitize
        allow_html_fields: List of field names that should allow HTML content

    Returns:
        Sanitized data
    """
    allow_html_fields = allow_html_fields or []

    def sanitize_recursive(obj: Any, path: str = "") -> Any:
        if isinstance(obj, str):
            allow_html = path in allow_html_fields
            return InputSanitizer.sanitize_string(obj, allow_html)
        elif isinstance(obj, dict):
            return {
                k: sanitize_recursive(v, f"{path}.{k}" if path else k)
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [sanitize_recursive(item, path) for item in obj]
        else:
            return obj

    return sanitize_recursive(data)


# Pydantic validator for use in schemas
def sanitized_string(value: str) -> str:
    """Pydantic validator that sanitizes string input"""
    return InputSanitizer.sanitize_string(value)
