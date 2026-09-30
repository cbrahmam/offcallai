"""
OffCall AI - Distributed Tracing Module

Provides lightweight tracing without OpenTelemetry dependency.
Generates spans compatible with the OffCall traces/ingest API.

Usage:
    import offcall_errors
    offcall_errors.init(api_key="ofc_xxx", enable_tracing=True)

    # Auto-instrumented via FastAPI integration, or manually:
    with offcall_errors.start_span("db.query", kind="client") as span:
        span.set_attribute("db.statement", "SELECT * FROM users")
        result = db.execute(query)
"""

import os
import time
import random
import threading
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from contextvars import ContextVar


SDK_NAME = "offcall-python"
SDK_VERSION = "1.0.0"
DEFAULT_TRACES_ENDPOINT = "http://localhost:8000/api/v1/traces/ingest"

# Context variable for current span (async-safe)
_current_span: ContextVar[Optional["Span"]] = ContextVar("_current_span", default=None)


def _generate_trace_id() -> str:
    """Generate a 32-char hex trace ID."""
    return os.urandom(16).hex()


def _generate_span_id() -> str:
    """Generate a 16-char hex span ID."""
    return os.urandom(8).hex()


@dataclass
class SpanEvent:
    """Event within a span."""
    name: str
    timestamp: str
    attributes: Optional[Dict[str, Any]] = None


@dataclass
class Span:
    """A single span representing a unit of work."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    service_name: str
    operation_name: str
    span_kind: str  # internal, server, client, producer, consumer
    start_time: str
    end_time: Optional[str] = None
    duration_ms: Optional[float] = None
    status: str = "unset"  # unset, ok, error
    status_message: Optional[str] = None
    resource_attributes: Dict[str, Any] = field(default_factory=dict)
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    links: List[Dict[str, Any]] = field(default_factory=list)

    # Internal tracking (not serialized)
    _start_ns: int = field(default=0, repr=False)
    _token: Any = field(default=None, repr=False)

    def set_attribute(self, key: str, value: Any):
        """Set a span attribute."""
        self.attributes[key] = value

    def set_status(self, status: str, message: str = None):
        """Set span status (ok, error, unset)."""
        self.status = status
        if message:
            self.status_message = message

    def add_event(self, name: str, attributes: Dict[str, Any] = None):
        """Add an event to this span."""
        self.events.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {},
        })

    def end(self):
        """End the span and calculate duration."""
        end_ns = time.monotonic_ns()
        self.duration_ms = (end_ns - self._start_ns) / 1_000_000
        self.end_time = datetime.now(timezone.utc).isoformat()

        if self.status == "unset":
            self.status = "ok"

        # Restore parent span context
        if self._token is not None:
            _current_span.reset(self._token)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize span for API submission."""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "service_name": self.service_name,
            "operation_name": self.operation_name,
            "span_kind": self.span_kind,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "status_message": self.status_message,
            "resource_attributes": self.resource_attributes,
            "attributes": self.attributes,
            "events": self.events,
            "links": self.links,
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.set_status("error", str(exc_val))
            self.add_event("exception", {
                "exception.type": exc_type.__name__,
                "exception.message": str(exc_val),
            })
        self.end()
        # Queue span for sending
        if _tracer:
            _tracer._queue_span(self)
        return False  # Don't suppress exceptions


class SpanBatcher:
    """Batches spans and flushes them periodically."""

    def __init__(self, api_key: str, endpoint: str, agent_id: str,
                 batch_size: int = 50, flush_interval: float = 5.0, debug: bool = False):
        self.api_key = api_key
        self.endpoint = endpoint
        self.agent_id = agent_id
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.debug = debug

        self._buffer: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None
        self._running = True

        self._schedule_flush()

    def add(self, span_dict: Dict[str, Any]):
        """Add a span to the buffer."""
        with self._lock:
            self._buffer.append(span_dict)
            if len(self._buffer) >= self.batch_size:
                self._flush_locked()

    def _schedule_flush(self):
        """Schedule the next periodic flush."""
        if not self._running:
            return
        self._timer = threading.Timer(self.flush_interval, self._periodic_flush)
        self._timer.daemon = True
        self._timer.start()

    def _periodic_flush(self):
        """Flush on timer."""
        with self._lock:
            self._flush_locked()
        self._schedule_flush()

    def _flush_locked(self):
        """Flush the buffer (must hold lock)."""
        if not self._buffer:
            return

        spans = self._buffer[:]
        self._buffer = []

        # Send in background thread
        t = threading.Thread(target=self._send, args=(spans,), daemon=True)
        t.start()

    def _send(self, spans: List[Dict[str, Any]]):
        """Send spans to the API."""
        payload = {
            "agent_id": self.agent_id,
            "spans": spans,
        }

        try:
            data = json.dumps(payload, default=str).encode("utf-8")
            request = urllib.request.Request(
                self.endpoint,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": self.api_key,
                    "User-Agent": f"offcall-python-tracing/{SDK_VERSION}",
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                if self.debug:
                    resp = json.loads(response.read().decode("utf-8"))
                    print(f"[OffCall Tracing] Flushed {len(spans)} spans: {resp}")
        except Exception as e:
            if self.debug:
                print(f"[OffCall Tracing] Failed to send {len(spans)} spans: {e}")

    def flush(self):
        """Force flush all buffered spans."""
        with self._lock:
            self._flush_locked()

    def shutdown(self):
        """Stop the batcher and flush remaining spans."""
        self._running = False
        if self._timer:
            self._timer.cancel()
        self.flush()


class Tracer:
    """Main tracer that creates and manages spans."""

    def __init__(
        self,
        api_key: str,
        service_name: str,
        environment: str = "production",
        release: str = None,
        endpoint: str = None,
        sample_rate: float = 1.0,
        debug: bool = False,
        enabled: bool = True,
    ):
        self.service_name = service_name
        self.environment = environment
        self.release = release
        self.sample_rate = sample_rate
        self.debug = debug
        self.enabled = enabled

        agent_id = f"{service_name}-{os.getpid()}"
        self._batcher = SpanBatcher(
            api_key=api_key,
            endpoint=endpoint or DEFAULT_TRACES_ENDPOINT,
            agent_id=agent_id,
            debug=debug,
        )

        self._resource_attributes = {
            "service.name": service_name,
            "service.version": release or "unknown",
            "deployment.environment": environment,
            "telemetry.sdk.name": SDK_NAME,
            "telemetry.sdk.version": SDK_VERSION,
            "host.name": os.environ.get("HOSTNAME", os.uname().nodename if hasattr(os, "uname") else "unknown"),
            "process.pid": os.getpid(),
        }

        if debug:
            print(f"[OffCall Tracing] Initialized: service={service_name}, env={environment}")

    def start_span(
        self,
        operation_name: str,
        kind: str = "internal",
        parent: Optional[Span] = None,
        trace_id: str = None,
        attributes: Dict[str, Any] = None,
    ) -> Span:
        """Start a new span."""
        if not self.enabled or not self._should_sample():
            # Return a no-op span
            return self._noop_span(operation_name)

        # Determine parent
        if parent is None:
            parent = _current_span.get()

        if parent and trace_id is None:
            trace_id = parent.trace_id
            parent_span_id = parent.span_id
        else:
            trace_id = trace_id or _generate_trace_id()
            parent_span_id = None

        span = Span(
            trace_id=trace_id,
            span_id=_generate_span_id(),
            parent_span_id=parent_span_id,
            service_name=self.service_name,
            operation_name=operation_name,
            span_kind=kind,
            start_time=datetime.now(timezone.utc).isoformat(),
            resource_attributes=self._resource_attributes.copy(),
            attributes=attributes or {},
            _start_ns=time.monotonic_ns(),
        )

        # Set as current span
        span._token = _current_span.set(span)

        return span

    def _noop_span(self, operation_name: str) -> Span:
        """Create a no-op span that doesn't get sent."""
        span = Span(
            trace_id=_generate_trace_id(),
            span_id=_generate_span_id(),
            parent_span_id=None,
            service_name=self.service_name,
            operation_name=operation_name,
            span_kind="internal",
            start_time=datetime.now(timezone.utc).isoformat(),
            _start_ns=time.monotonic_ns(),
        )
        span._token = _current_span.set(span)
        return span

    def _queue_span(self, span: Span):
        """Queue a completed span for sending."""
        if not self.enabled:
            return
        self._batcher.add(span.to_dict())

    def _should_sample(self) -> bool:
        if self.sample_rate >= 1.0:
            return True
        if self.sample_rate <= 0:
            return False
        return random.random() < self.sample_rate

    def get_current_span(self) -> Optional[Span]:
        """Get the current active span."""
        return _current_span.get()

    def flush(self):
        """Force flush all pending spans."""
        self._batcher.flush()

    def shutdown(self):
        """Shutdown the tracer."""
        self._batcher.shutdown()


# Global tracer instance
_tracer: Optional[Tracer] = None


def init_tracer(
    api_key: str,
    service_name: str,
    environment: str = "production",
    release: str = None,
    endpoint: str = None,
    sample_rate: float = 1.0,
    debug: bool = False,
    enabled: bool = True,
) -> Tracer:
    """Initialize the global tracer."""
    global _tracer
    _tracer = Tracer(
        api_key=api_key,
        service_name=service_name,
        environment=environment,
        release=release,
        endpoint=endpoint,
        sample_rate=sample_rate,
        debug=debug,
        enabled=enabled,
    )
    return _tracer


def get_tracer() -> Optional[Tracer]:
    """Get the global tracer instance."""
    return _tracer


def start_span(
    operation_name: str,
    kind: str = "internal",
    attributes: Dict[str, Any] = None,
) -> Span:
    """Start a new span using the global tracer."""
    if _tracer is None:
        raise RuntimeError("Tracer not initialized. Call offcall_errors.init(enable_tracing=True) first.")
    return _tracer.start_span(operation_name, kind=kind, attributes=attributes)


def get_current_span() -> Optional[Span]:
    """Get the current active span."""
    return _current_span.get()
