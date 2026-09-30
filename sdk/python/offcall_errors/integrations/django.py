"""
OffCall AI - Django Integration

Usage:
    # settings.py
    MIDDLEWARE = [
        'offcall_errors.integrations.django.OffCallMiddleware',
        # ... other middleware
    ]

    OFFCALL_API_KEY = "ofc_your_api_key"
    OFFCALL_ENVIRONMENT = "production"  # optional
    OFFCALL_RELEASE = "1.0.0"  # optional
"""

import sys
import logging
from typing import Callable, Optional

logger = logging.getLogger("offcall")


class OffCallMiddleware:
    """
    Django middleware for automatic error tracking.

    Configuration via Django settings:
        OFFCALL_API_KEY: Your OffCall API key (required)
        OFFCALL_ENVIRONMENT: Environment name (default: "production")
        OFFCALL_RELEASE: Release/version string (optional)
        OFFCALL_SERVICE: Service name (default: Django project name)
        OFFCALL_DEBUG: Enable debug logging (default: False)
        OFFCALL_ENABLED: Enable/disable SDK (default: True)
        OFFCALL_SAMPLE_RATE: Sample rate 0.0-1.0 (default: 1.0)
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self._initialized = False
        self._init_sdk()

    def _init_sdk(self):
        """Initialize the OffCall SDK from Django settings."""
        try:
            from django.conf import settings
            import offcall_errors

            api_key = getattr(settings, "OFFCALL_API_KEY", None)
            if not api_key:
                logger.warning(
                    "OFFCALL_API_KEY not set in Django settings. "
                    "Error tracking is disabled."
                )
                return

            # Get configuration from settings
            config = {
                "api_key": api_key,
                "environment": getattr(settings, "OFFCALL_ENVIRONMENT", "production"),
                "release": getattr(settings, "OFFCALL_RELEASE", None),
                "service": getattr(settings, "OFFCALL_SERVICE", None) or self._get_project_name(),
                "debug": getattr(settings, "OFFCALL_DEBUG", settings.DEBUG),
                "enabled": getattr(settings, "OFFCALL_ENABLED", True),
                "sample_rate": getattr(settings, "OFFCALL_SAMPLE_RATE", 1.0),
            }

            offcall_errors.init(**config)
            self._initialized = True

            if config["debug"]:
                logger.info(f"[OffCall] Django middleware initialized")

        except Exception as e:
            logger.error(f"[OffCall] Failed to initialize: {e}")

    def _get_project_name(self) -> str:
        """Get Django project name from settings module."""
        try:
            from django.conf import settings
            settings_module = settings.SETTINGS_MODULE
            if settings_module:
                return settings_module.split(".")[0]
        except Exception:
            pass
        return "django-app"

    def __call__(self, request):
        """Process request and capture errors."""
        if not self._initialized:
            return self.get_response(request)

        import offcall_errors

        # Add request breadcrumb
        offcall_errors.add_breadcrumb(
            message=f"{request.method} {request.path}",
            category="http",
            type="http",
            data={
                "method": request.method,
                "url": request.build_absolute_uri(),
                "query_string": request.META.get("QUERY_STRING", ""),
            },
        )

        # Set user context if authenticated
        if hasattr(request, "user") and request.user.is_authenticated:
            offcall_errors.set_user({
                "id": str(request.user.pk),
                "email": getattr(request.user, "email", None),
                "username": getattr(request.user, "username", None),
            })

        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            # Capture the exception with request context
            offcall_errors.capture_exception(
                e,
                extra={
                    "request": self._get_request_data(request),
                },
            )
            raise

    def _get_request_data(self, request) -> dict:
        """Extract request data for error context."""
        return {
            "method": request.method,
            "url": request.build_absolute_uri(),
            "path": request.path,
            "query_string": request.META.get("QUERY_STRING", ""),
            "content_type": request.content_type,
            "headers": {
                k: v for k, v in request.META.items()
                if k.startswith("HTTP_") and k not in ("HTTP_COOKIE", "HTTP_AUTHORIZATION")
            },
        }

    def process_exception(self, request, exception):
        """Django exception handler hook."""
        if not self._initialized:
            return None

        import offcall_errors

        offcall_errors.capture_exception(
            exception,
            extra={
                "request": self._get_request_data(request),
            },
        )

        # Return None to let Django handle the exception
        return None


def get_client():
    """Get the OffCall client instance."""
    import offcall_errors
    return offcall_errors.get_client()
