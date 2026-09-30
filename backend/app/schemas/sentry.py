# backend/app/schemas/sentry.py
"""Schemas for Sentry SDK compatibility layer."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime


class SentryStackFrame(BaseModel):
    """Sentry stack frame format."""
    filename: Optional[str] = None
    function: Optional[str] = None
    module: Optional[str] = None
    lineno: Optional[int] = None
    colno: Optional[int] = None
    abs_path: Optional[str] = None
    context_line: Optional[str] = None
    pre_context: Optional[List[str]] = None
    post_context: Optional[List[str]] = None
    in_app: Optional[bool] = True
    vars: Optional[Dict[str, Any]] = None


class SentryStacktrace(BaseModel):
    """Sentry stacktrace container."""
    frames: Optional[List[SentryStackFrame]] = []


class SentryException(BaseModel):
    """Single exception in Sentry format."""
    type: Optional[str] = None
    value: Optional[str] = None
    module: Optional[str] = None
    stacktrace: Optional[SentryStacktrace] = None
    mechanism: Optional[Dict[str, Any]] = None


class SentryExceptionContainer(BaseModel):
    """Container for exception values."""
    values: Optional[List[SentryException]] = []


class SentryUser(BaseModel):
    """Sentry user context."""
    id: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None
    ip_address: Optional[str] = None
    name: Optional[str] = None
    geo: Optional[Dict[str, Any]] = None


class SentryRequest(BaseModel):
    """Sentry request context."""
    url: Optional[str] = None
    method: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    query_string: Optional[str] = None
    data: Optional[Any] = None
    cookies: Optional[Dict[str, str]] = None
    env: Optional[Dict[str, str]] = None


class SentryBreadcrumb(BaseModel):
    """Sentry breadcrumb format."""
    timestamp: Optional[Union[str, float, datetime]] = None
    type: Optional[str] = None
    category: Optional[str] = None
    message: Optional[str] = None
    level: Optional[str] = "info"
    data: Optional[Dict[str, Any]] = None


class SentryBreadcrumbs(BaseModel):
    """Container for breadcrumbs."""
    values: Optional[List[SentryBreadcrumb]] = []


class SentryContexts(BaseModel):
    """Sentry contexts container."""
    runtime: Optional[Dict[str, Any]] = None
    os: Optional[Dict[str, Any]] = None
    browser: Optional[Dict[str, Any]] = None
    device: Optional[Dict[str, Any]] = None
    app: Optional[Dict[str, Any]] = None
    trace: Optional[Dict[str, Any]] = None
    # Allow additional context types
    class Config:
        extra = "allow"


class SentrySDK(BaseModel):
    """Sentry SDK info."""
    name: Optional[str] = None
    version: Optional[str] = None
    integrations: Optional[List[str]] = None
    packages: Optional[List[Dict[str, str]]] = None


class SentryMessage(BaseModel):
    """Sentry message format."""
    formatted: Optional[str] = None
    message: Optional[str] = None
    params: Optional[List[Any]] = None


class SentryEvent(BaseModel):
    """
    Full Sentry event format.

    This matches the format sent by @sentry/browser and sentry-python SDKs.
    Reference: https://develop.sentry.dev/sdk/event-payloads/
    """
    # Required
    event_id: Optional[str] = None
    timestamp: Optional[Union[str, float, datetime]] = None
    platform: Optional[str] = None

    # Error info
    level: Optional[str] = "error"  # fatal, error, warning, info, debug
    logger: Optional[str] = None
    transaction: Optional[str] = None
    server_name: Optional[str] = None
    release: Optional[str] = None
    dist: Optional[str] = None
    environment: Optional[str] = "production"

    # Message (for message events)
    message: Optional[Union[str, SentryMessage]] = None

    # Exception (for error events)
    exception: Optional[SentryExceptionContainer] = None

    # Contexts
    contexts: Optional[SentryContexts] = None
    user: Optional[SentryUser] = None
    request: Optional[SentryRequest] = None

    # Breadcrumbs
    breadcrumbs: Optional[Union[SentryBreadcrumbs, List[SentryBreadcrumb]]] = None

    # Tags and extra
    tags: Optional[Dict[str, str]] = None
    extra: Optional[Dict[str, Any]] = None

    # Fingerprint for grouping
    fingerprint: Optional[List[str]] = None

    # SDK info
    sdk: Optional[SentrySDK] = None

    # Modules (Python/Node specific)
    modules: Optional[Dict[str, str]] = None

    class Config:
        extra = "allow"


class SentryEnvelopeHeader(BaseModel):
    """
    Sentry envelope header.

    The envelope format is:
    {header}\n
    {item_header}\n
    {item_payload}\n
    ...
    """
    event_id: Optional[str] = None
    sent_at: Optional[str] = None
    dsn: Optional[str] = None
    sdk: Optional[Dict[str, Any]] = None

    class Config:
        extra = "allow"


class SentryItemHeader(BaseModel):
    """Sentry envelope item header."""
    type: str  # event, session, attachment, etc.
    length: Optional[int] = None
    content_type: Optional[str] = None

    class Config:
        extra = "allow"


class ParsedEnvelope(BaseModel):
    """Result of parsing a Sentry envelope."""
    header: SentryEnvelopeHeader
    events: List[SentryEvent] = []
    sessions: List[Dict[str, Any]] = []
    other_items: List[Dict[str, Any]] = []
