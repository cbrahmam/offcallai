"""
OffCall AI - FastAPI Integration

Provides automatic error tracking AND distributed tracing for FastAPI apps.

Usage:
    from fastapi import FastAPI
    from offcall_errors.integrations.fastapi import OffCallFastAPI

    app = FastAPI()
    OffCallFastAPI(app, api_key="ofc_your_api_key", enable_tracing=True)

This will:
- Auto-capture unhandled exceptions
- Auto-create spans for every HTTP request (APM)
- Track request duration, status codes, paths
- Propagate trace context via headers
"""

import sys
import time
import logging
from typing import Optional, Callable
from functools import wraps

logger = logging.getLogger("offcall")


class OffCallFastAPI:
    """
    FastAPI extension for automatic error tracking and APM tracing.
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
        enable_tracing: bool = True,
        traces_endpoint: str = None,
        traces_sample_rate: float = 1.0,
    ):
        self.api_key = api_key
        self.environment = environment
        self.release = release
        self.service = service
        self.debug = debug
        self.enabled = enabled
        self.sample_rate = sample_rate
        self.enable_tracing = enable_tracing
        self.traces_endpoint = traces_endpoint
        self.traces_sample_rate = traces_sample_rate
        self._initialized = False
        self._tracing_initialized = False

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
        """Initialize the extension with a FastAPI app."""
        import offcall_errors

        config = {
            "api_key": api_key or self.api_key,
            "environment": environment or self.environment,
            "release": release or self.release,
            "service": service or self.service or app.title or "fastapi-app",
            "debug": debug if debug is not None else self.debug,
            "enabled": enabled if enabled is not None else self.enabled,
            "sample_rate": sample_rate or self.sample_rate,
        }

        if not config["api_key"]:
            logger.warning(
                "OffCall API key not provided. Error tracking is disabled."
            )
            return

        try:
            offcall_errors.init(**config)
            self._initialized = True

            # Initialize tracing if enabled
            if self.enable_tracing:
                from offcall_errors.tracing import init_tracer
                init_tracer(
                    api_key=config["api_key"],
                    service_name=config["service"],
                    environment=config["environment"],
                    release=config["release"],
                    endpoint=self.traces_endpoint,
                    sample_rate=self.traces_sample_rate,
                    debug=config["debug"],
                    enabled=config["enabled"],
                )
                self._tracing_initialized = True
                if config["debug"]:
                    logger.info("[OffCall] Tracing initialized")

            # Add middleware for request tracking + tracing
            app.middleware("http")(self._middleware)

            # Add exception handler
            app.add_exception_handler(Exception, self._exception_handler)

            if config["debug"]:
                logger.info("[OffCall] FastAPI extension initialized")

        except Exception as e:
            logger.error(f"[OffCall] Failed to initialize: {e}")

    async def _middleware(self, request, call_next):
        """Middleware for error tracking and APM tracing."""
        if not self._initialized:
            return await call_next(request)

        import offcall_errors

        # --- APM Tracing ---
        span = None
        if self._tracing_initialized:
            from offcall_errors.tracing import get_tracer

            tracer = get_tracer()
            if tracer:
                # Check for incoming trace context (distributed tracing)
                trace_id = request.headers.get("x-trace-id") or request.headers.get("traceparent", "").split("-")[1] if "-" in request.headers.get("traceparent", "") else None
                parent_span_id = request.headers.get("x-parent-span-id")

                operation = f"{request.method} {request.url.path}"
                span = tracer.start_span(
                    operation_name=operation,
                    kind="server",
                    trace_id=trace_id,
                    attributes={
                        "http.method": request.method,
                        "http.url": str(request.url),
                        "http.path": request.url.path,
                        "http.query": str(request.query_params) if request.query_params else None,
                        "http.scheme": request.url.scheme,
                        "http.host": request.url.hostname,
                        "http.user_agent": request.headers.get("user-agent"),
                        "http.client_ip": request.client.host if request.client else None,
                    },
                )

        # --- Error Tracking Breadcrumb ---
        offcall_errors.add_breadcrumb(
            message=f"{request.method} {request.url.path}",
            category="http",
            type="http",
            data={
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
            },
        )

        # Set user context if available
        if hasattr(request.state, "user") and request.state.user:
            user = request.state.user
            offcall_errors.set_user({
                "id": str(getattr(user, "id", None)),
                "email": getattr(user, "email", None),
                "username": getattr(user, "username", None),
            })

        try:
            response = await call_next(request)

            # Update span with response info
            if span:
                span.set_attribute("http.status_code", response.status_code)
                if response.status_code >= 500:
                    span.set_status("error", f"HTTP {response.status_code}")
                elif response.status_code >= 400:
                    span.set_attribute("http.error", True)
                    span.set_status("ok")
                else:
                    span.set_status("ok")

                # End span and queue for sending
                span.end()
                tracer = get_tracer()
                if tracer:
                    tracer._queue_span(span)

            # Error tracking breadcrumb
            offcall_errors.add_breadcrumb(
                message=f"Response {response.status_code}",
                category="http",
                type="http",
                level="warning" if response.status_code >= 400 else "info",
                data={"status_code": response.status_code},
            )

            return response

        except Exception as e:
            # Mark span as error
            if span:
                span.set_status("error", str(e))
                span.add_event("exception", {
                    "exception.type": type(e).__name__,
                    "exception.message": str(e),
                })
                span.end()
                from offcall_errors.tracing import get_tracer
                tracer = get_tracer()
                if tracer:
                    tracer._queue_span(span)

            # Capture exception for error tracking
            offcall_errors.capture_exception(
                e,
                extra={"request": await self._get_request_data(request)},
            )
            raise

    async def _exception_handler(self, request, exc):
        """Exception handler to capture errors."""
        if not self._initialized:
            raise exc

        import offcall_errors

        offcall_errors.capture_exception(
            exc,
            extra={"request": await self._get_request_data(request)},
        )

        raise exc

    async def _get_request_data(self, request) -> dict:
        """Extract request data for error context."""
        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ("cookie", "authorization", "x-api-key")
        }

        return {
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": headers,
            "client": request.client.host if request.client else None,
        }

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
    Decorator to capture exceptions from async functions.

    Usage:
        @app.get('/api/data')
        @capture_exceptions
        async def get_data():
            ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            import offcall_errors
            offcall_errors.capture_exception(e)
            raise

    return wrapper


def trace_function(operation_name: str = None, kind: str = "internal"):
    """
    Decorator to create a span for a function call.

    Usage:
        @trace_function("db.get_users")
        async def get_users():
            ...
    """
    def decorator(func: Callable) -> Callable:
        op_name = operation_name or f"{func.__module__}.{func.__qualname__}"

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            from offcall_errors.tracing import get_tracer
            tracer = get_tracer()
            if not tracer:
                return await func(*args, **kwargs)

            with tracer.start_span(op_name, kind=kind) as span:
                result = await func(*args, **kwargs)
                return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            from offcall_errors.tracing import get_tracer
            tracer = get_tracer()
            if not tracer:
                return func(*args, **kwargs)

            with tracer.start_span(op_name, kind=kind) as span:
                result = func(*args, **kwargs)
                return result

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class OffCallMiddleware:
    """
    ASGI middleware for Starlette/FastAPI with tracing support.

    Usage:
        app.add_middleware(OffCallMiddleware, api_key="ofc_xxx", enable_tracing=True)
    """

    def __init__(
        self,
        app,
        api_key: str = None,
        environment: str = "production",
        release: str = None,
        service: str = None,
        debug: bool = False,
        enable_tracing: bool = True,
    ):
        self.app = app
        self._initialized = False
        self._tracing_initialized = False

        if api_key:
            import offcall_errors
            try:
                offcall_errors.init(
                    api_key=api_key,
                    environment=environment,
                    release=release,
                    service=service or "fastapi-app",
                    debug=debug,
                )
                self._initialized = True

                if enable_tracing:
                    from offcall_errors.tracing import init_tracer
                    init_tracer(
                        api_key=api_key,
                        service_name=service or "fastapi-app",
                        environment=environment,
                        release=release,
                        debug=debug,
                    )
                    self._tracing_initialized = True

            except Exception as e:
                logger.error(f"[OffCall] Failed to initialize: {e}")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not self._initialized:
            return await self.app(scope, receive, send)

        import offcall_errors
        path = scope.get("path", "/")
        method = scope.get("method", "GET")

        # Start span for tracing
        span = None
        if self._tracing_initialized:
            from offcall_errors.tracing import get_tracer
            tracer = get_tracer()
            if tracer:
                span = tracer.start_span(
                    operation_name=f"{method} {path}",
                    kind="server",
                    attributes={
                        "http.method": method,
                        "http.path": path,
                        "http.query": scope.get("query_string", b"").decode(),
                    },
                )

        offcall_errors.add_breadcrumb(
            message=f"{method} {path}",
            category="http",
            type="http",
            data={"method": method, "path": path},
        )

        try:
            result = await self.app(scope, receive, send)
            if span:
                span.set_status("ok")
                span.end()
                from offcall_errors.tracing import get_tracer
                tracer = get_tracer()
                if tracer:
                    tracer._queue_span(span)
            return result
        except Exception as e:
            if span:
                span.set_status("error", str(e))
                span.add_event("exception", {
                    "exception.type": type(e).__name__,
                    "exception.message": str(e),
                })
                span.end()
                from offcall_errors.tracing import get_tracer
                tracer = get_tracer()
                if tracer:
                    tracer._queue_span(span)

            offcall_errors.capture_exception(
                e,
                extra={"request": {"method": method, "path": path}},
            )
            raise
