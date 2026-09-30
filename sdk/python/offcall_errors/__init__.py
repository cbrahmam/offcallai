"""
OffCall AI - Python Error Tracking SDK

Usage:
    import offcall_errors

    offcall_errors.init(
        api_key="ofc_your_api_key",
        environment="production",
        release="1.0.0",
    )

    # Automatic exception capture
    try:
        raise ValueError("Something went wrong")
    except Exception as e:
        offcall_errors.capture_exception(e)

    # Manual message capture
    offcall_errors.capture_message("Something happened", level="warning")

    # Set user context
    offcall_errors.set_user({"id": "123", "email": "user@example.com"})

Flask integration:
    from offcall_errors.integrations.flask import OffCallFlask
    app = Flask(__name__)
    OffCallFlask(app, api_key="ofc_your_api_key")

Django integration:
    # settings.py
    MIDDLEWARE = [
        'offcall_errors.integrations.django.OffCallMiddleware',
        ...
    ]
    OFFCALL_API_KEY = "ofc_your_api_key"

FastAPI integration:
    from offcall_errors.integrations.fastapi import OffCallFastAPI
    app = FastAPI()
    OffCallFastAPI(app, api_key="ofc_your_api_key")
"""

from .client import OffCallClient

__version__ = "1.0.0"
__all__ = [
    "init",
    "capture_exception",
    "capture_message",
    "set_user",
    "clear_user",
    "set_tag",
    "set_tags",
    "set_extra",
    "set_extras",
    "add_breadcrumb",
    "configure_scope",
    "get_client",
    "start_span",
    "get_current_span",
]

# Global client instance
_client: OffCallClient = None


def init(
    api_key: str,
    environment: str = "production",
    release: str = None,
    service: str = None,
    debug: bool = False,
    enabled: bool = True,
    sample_rate: float = 1.0,
    max_breadcrumbs: int = 100,
    before_send=None,
    ignore_exceptions: list = None,
    endpoint: str = None,
):
    """
    Initialize the OffCall SDK.

    Args:
        api_key: Your OffCall API key (required)
        environment: Environment name (e.g., "production", "staging")
        release: Release/version string
        service: Service name
        debug: Enable debug logging
        enabled: Enable/disable error reporting
        sample_rate: Sample rate for errors (0.0 to 1.0)
        max_breadcrumbs: Maximum number of breadcrumbs to keep
        before_send: Callback to modify events before sending
        ignore_exceptions: List of exception types to ignore
        endpoint: Custom API endpoint
    """
    global _client
    _client = OffCallClient(
        api_key=api_key,
        environment=environment,
        release=release,
        service=service,
        debug=debug,
        enabled=enabled,
        sample_rate=sample_rate,
        max_breadcrumbs=max_breadcrumbs,
        before_send=before_send,
        ignore_exceptions=ignore_exceptions or [],
        endpoint=endpoint,
    )
    return _client


def get_client() -> OffCallClient:
    """Get the global client instance."""
    return _client


def capture_exception(exception: Exception = None, **kwargs):
    """
    Capture an exception and send it to OffCall.

    Args:
        exception: The exception to capture (uses sys.exc_info() if None)
        **kwargs: Additional context (tags, extra, user, etc.)
    """
    if _client is None:
        raise RuntimeError("OffCall SDK not initialized. Call offcall_errors.init() first.")
    return _client.capture_exception(exception, **kwargs)


def capture_message(message: str, level: str = "info", **kwargs):
    """
    Capture a message and send it to OffCall.

    Args:
        message: The message to capture
        level: Severity level (debug, info, warning, error, fatal)
        **kwargs: Additional context (tags, extra, user, etc.)
    """
    if _client is None:
        raise RuntimeError("OffCall SDK not initialized. Call offcall_errors.init() first.")
    return _client.capture_message(message, level, **kwargs)


def set_user(user: dict):
    """
    Set user context for future events.

    Args:
        user: User info dict with id, email, name, etc.
    """
    if _client is None:
        raise RuntimeError("OffCall SDK not initialized. Call offcall_errors.init() first.")
    _client.set_user(user)


def clear_user():
    """Clear user context."""
    if _client is None:
        raise RuntimeError("OffCall SDK not initialized. Call offcall_errors.init() first.")
    _client.clear_user()


def set_tag(key: str, value: str):
    """Set a tag for future events."""
    if _client is None:
        raise RuntimeError("OffCall SDK not initialized. Call offcall_errors.init() first.")
    _client.set_tag(key, value)


def set_tags(tags: dict):
    """Set multiple tags for future events."""
    if _client is None:
        raise RuntimeError("OffCall SDK not initialized. Call offcall_errors.init() first.")
    _client.set_tags(tags)


def set_extra(key: str, value):
    """Set extra context for future events."""
    if _client is None:
        raise RuntimeError("OffCall SDK not initialized. Call offcall_errors.init() first.")
    _client.set_extra(key, value)


def set_extras(extras: dict):
    """Set multiple extra context values for future events."""
    if _client is None:
        raise RuntimeError("OffCall SDK not initialized. Call offcall_errors.init() first.")
    _client.set_extras(extras)


def add_breadcrumb(
    message: str = None,
    category: str = "default",
    level: str = "info",
    type: str = "default",
    data: dict = None,
):
    """
    Add a breadcrumb to the current scope.

    Args:
        message: Breadcrumb message
        category: Category (e.g., "http", "navigation", "user")
        level: Severity level
        type: Breadcrumb type
        data: Additional data dict
    """
    if _client is None:
        raise RuntimeError("OffCall SDK not initialized. Call offcall_errors.init() first.")
    _client.add_breadcrumb(
        message=message,
        category=category,
        level=level,
        type=type,
        data=data or {},
    )


def configure_scope(callback):
    """
    Configure the current scope using a callback.

    Args:
        callback: Function that receives the scope and modifies it

    Example:
        def configure(scope):
            scope.set_tag("key", "value")
            scope.set_user({"id": "123"})

        offcall_errors.configure_scope(configure)
    """
    if _client is None:
        raise RuntimeError("OffCall SDK not initialized. Call offcall_errors.init() first.")
    _client.configure_scope(callback)


def start_span(operation_name: str, kind: str = "internal", attributes: dict = None):
    """
    Start a new trace span. Use as a context manager.

    Args:
        operation_name: Name of the operation (e.g., "db.query", "http.request")
        kind: Span kind (internal, server, client, producer, consumer)
        attributes: Optional span attributes

    Example:
        with offcall_errors.start_span("db.get_user", kind="client") as span:
            span.set_attribute("db.statement", "SELECT * FROM users")
            result = db.query(...)
    """
    from .tracing import start_span as _start_span
    return _start_span(operation_name, kind=kind, attributes=attributes)


def get_current_span():
    """Get the currently active span, or None."""
    from .tracing import get_current_span as _get_current_span
    return _get_current_span()
