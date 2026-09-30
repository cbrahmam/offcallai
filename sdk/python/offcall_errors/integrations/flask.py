"""
OffCall AI - Flask Integration

Usage:
    from flask import Flask
    from offcall_errors.integrations.flask import OffCallFlask

    app = Flask(__name__)
    OffCallFlask(app, api_key="ofc_your_api_key")

Or with factory pattern:
    offcall = OffCallFlask()

    def create_app():
        app = Flask(__name__)
        offcall.init_app(app, api_key="ofc_your_api_key")
        return app
"""

import sys
import logging
from functools import wraps
from typing import Optional, Callable

logger = logging.getLogger("offcall")


class OffCallFlask:
    """
    Flask extension for automatic error tracking.

    Args:
        app: Flask application instance
        api_key: Your OffCall API key
        environment: Environment name (default: "production")
        release: Release/version string
        service: Service name (default: Flask app name)
        debug: Enable debug logging
        enabled: Enable/disable SDK
        sample_rate: Sample rate 0.0-1.0
    """

    def __init__(
        self,
        app=None,
        api_key: str = None,
        environment: str = "production",
        release: str = None,
        service: str = None,
        debug: bool = False,
        enabled: bool = True,
        sample_rate: float = 1.0,
    ):
        self.api_key = api_key
        self.environment = environment
        self.release = release
        self.service = service
        self.debug = debug
        self.enabled = enabled
        self.sample_rate = sample_rate
        self._initialized = False

        if app is not None:
            self.init_app(app)

    def init_app(
        self,
        app,
        api_key: str = None,
        environment: str = None,
        release: str = None,
        service: str = None,
        debug: bool = None,
        enabled: bool = None,
        sample_rate: float = None,
    ):
        """
        Initialize the extension with a Flask app.

        Can also read from app.config:
            OFFCALL_API_KEY
            OFFCALL_ENVIRONMENT
            OFFCALL_RELEASE
            OFFCALL_SERVICE
            OFFCALL_DEBUG
            OFFCALL_ENABLED
            OFFCALL_SAMPLE_RATE
        """
        import offcall_errors

        # Get config from parameters, instance vars, or app.config
        config = {
            "api_key": api_key or self.api_key or app.config.get("OFFCALL_API_KEY"),
            "environment": environment or self.environment or app.config.get("OFFCALL_ENVIRONMENT", "production"),
            "release": release or self.release or app.config.get("OFFCALL_RELEASE"),
            "service": service or self.service or app.config.get("OFFCALL_SERVICE") or app.name,
            "debug": debug if debug is not None else (self.debug or app.config.get("OFFCALL_DEBUG", app.debug)),
            "enabled": enabled if enabled is not None else (self.enabled if self.enabled is not None else app.config.get("OFFCALL_ENABLED", True)),
            "sample_rate": sample_rate or self.sample_rate or app.config.get("OFFCALL_SAMPLE_RATE", 1.0),
        }

        if not config["api_key"]:
            logger.warning(
                "OffCall API key not provided. Set api_key parameter or "
                "OFFCALL_API_KEY in app.config. Error tracking is disabled."
            )
            return

        try:
            offcall_errors.init(**config)
            self._initialized = True

            # Register error handler
            app.register_error_handler(Exception, self._handle_exception)

            # Register before/after request hooks
            app.before_request(self._before_request)
            app.after_request(self._after_request)

            if config["debug"]:
                logger.info(f"[OffCall] Flask extension initialized for {app.name}")

        except Exception as e:
            logger.error(f"[OffCall] Failed to initialize: {e}")

    def _before_request(self):
        """Add request breadcrumb and user context."""
        if not self._initialized:
            return

        from flask import request, g
        import offcall_errors

        # Add request breadcrumb
        offcall_errors.add_breadcrumb(
            message=f"{request.method} {request.path}",
            category="http",
            type="http",
            data={
                "method": request.method,
                "url": request.url,
                "query_string": request.query_string.decode("utf-8", errors="replace"),
            },
        )

        # Set user context if available (e.g., from Flask-Login)
        if hasattr(g, "user") and g.user and hasattr(g.user, "id"):
            offcall_errors.set_user({
                "id": str(g.user.id),
                "email": getattr(g.user, "email", None),
                "username": getattr(g.user, "username", None),
            })

    def _after_request(self, response):
        """Add response breadcrumb."""
        if not self._initialized:
            return response

        from flask import request
        import offcall_errors

        offcall_errors.add_breadcrumb(
            message=f"Response {response.status_code}",
            category="http",
            type="http",
            level="warning" if response.status_code >= 400 else "info",
            data={
                "status_code": response.status_code,
                "url": request.url,
            },
        )

        return response

    def _handle_exception(self, exception):
        """Capture exceptions and re-raise."""
        if not self._initialized:
            raise exception

        from flask import request
        import offcall_errors

        offcall_errors.capture_exception(
            exception,
            extra={
                "request": {
                    "method": request.method,
                    "url": request.url,
                    "path": request.path,
                    "query_string": request.query_string.decode("utf-8", errors="replace"),
                    "headers": {
                        k: v for k, v in request.headers
                        if k.lower() not in ("cookie", "authorization", "x-api-key")
                    },
                    "remote_addr": request.remote_addr,
                },
            },
        )

        # Re-raise to let Flask handle it
        raise exception

    def capture_exception(self, exception: Exception = None, **kwargs):
        """Manually capture an exception."""
        if not self._initialized:
            logger.warning("[OffCall] SDK not initialized")
            return

        import offcall_errors
        return offcall_errors.capture_exception(exception, **kwargs)

    def capture_message(self, message: str, level: str = "info", **kwargs):
        """Manually capture a message."""
        if not self._initialized:
            logger.warning("[OffCall] SDK not initialized")
            return

        import offcall_errors
        return offcall_errors.capture_message(message, level, **kwargs)


def capture_exceptions(func: Callable) -> Callable:
    """
    Decorator to capture exceptions from a function.

    Usage:
        @app.route('/api/data')
        @capture_exceptions
        def get_data():
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            import offcall_errors
            offcall_errors.capture_exception(e)
            raise

    return wrapper
