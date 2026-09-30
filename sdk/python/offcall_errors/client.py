"""
OffCall Error Tracking Client
"""

import sys
import os
import platform
import threading
import traceback
import hashlib
import random
from datetime import datetime
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field
import urllib.request
import urllib.error
import json


SDK_NAME = "offcall-python"
SDK_VERSION = "1.0.0"
DEFAULT_ENDPOINT = "http://localhost:8000/api/v1/errors/ingest/python"


@dataclass
class Breadcrumb:
    """Breadcrumb for tracking user actions and events."""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    type: str = "default"
    category: str = "default"
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    level: str = "info"


@dataclass
class StackFrame:
    """Stack frame information."""
    filename: str
    function: str
    lineno: int
    colno: Optional[int] = None
    abs_path: Optional[str] = None
    context_line: Optional[str] = None
    pre_context: Optional[List[str]] = None
    post_context: Optional[List[str]] = None
    in_app: bool = True
    module: Optional[str] = None
    vars: Optional[Dict[str, Any]] = None


@dataclass
class Scope:
    """Event scope containing context."""
    user: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)
    breadcrumbs: List[Breadcrumb] = field(default_factory=list)
    max_breadcrumbs: int = 100

    def set_user(self, user: Dict[str, Any]):
        self.user = user or {}

    def clear_user(self):
        self.user = {}

    def set_tag(self, key: str, value: str):
        self.tags[key] = value

    def set_tags(self, tags: Dict[str, str]):
        self.tags.update(tags)

    def set_extra(self, key: str, value: Any):
        self.extra[key] = value

    def set_extras(self, extras: Dict[str, Any]):
        self.extra.update(extras)

    def add_breadcrumb(self, breadcrumb: Breadcrumb):
        self.breadcrumbs.append(breadcrumb)
        if len(self.breadcrumbs) > self.max_breadcrumbs:
            self.breadcrumbs.pop(0)

    def clear_breadcrumbs(self):
        self.breadcrumbs = []


class OffCallClient:
    """OffCall Error Tracking Client."""

    def __init__(
        self,
        api_key: str,
        environment: str = "production",
        release: str = None,
        service: str = None,
        debug: bool = False,
        enabled: bool = True,
        sample_rate: float = 1.0,
        max_breadcrumbs: int = 100,
        before_send: Callable = None,
        ignore_exceptions: List[type] = None,
        endpoint: str = None,
    ):
        self.api_key = api_key
        self.environment = environment
        self.release = release
        self.service = service or self._detect_service_name()
        self.debug = debug
        self.enabled = enabled
        self.sample_rate = sample_rate
        self.before_send = before_send
        self.ignore_exceptions = ignore_exceptions or []
        self.endpoint = endpoint or DEFAULT_ENDPOINT

        self._scope = Scope(max_breadcrumbs=max_breadcrumbs)
        self._lock = threading.Lock()

        # Install exception hook
        self._original_excepthook = sys.excepthook
        sys.excepthook = self._excepthook

        if self.debug:
            print(f"[OffCall] SDK initialized: environment={environment}, service={self.service}")

        # Add init breadcrumb
        self.add_breadcrumb(
            message="OffCall SDK initialized",
            category="sdk",
            data={"version": SDK_VERSION, "environment": environment},
        )

    def _detect_service_name(self) -> str:
        """Detect service name from environment or script name."""
        if "SERVICE_NAME" in os.environ:
            return os.environ["SERVICE_NAME"]
        if "APP_NAME" in os.environ:
            return os.environ["APP_NAME"]

        # Try to get from main script
        main = sys.modules.get("__main__")
        if main and hasattr(main, "__file__") and main.__file__:
            return os.path.basename(main.__file__).replace(".py", "")

        return "python-app"

    def _excepthook(self, exc_type, exc_value, exc_traceback):
        """Global exception hook."""
        self.capture_exception(exc_value)
        # Call original hook
        if self._original_excepthook:
            self._original_excepthook(exc_type, exc_value, exc_traceback)

    def _should_ignore(self, exception: Exception) -> bool:
        """Check if exception should be ignored."""
        for exc_type in self.ignore_exceptions:
            if isinstance(exception, exc_type):
                return True
        return False

    def _should_sample(self) -> bool:
        """Check if event should be sampled."""
        if self.sample_rate >= 1.0:
            return True
        if self.sample_rate <= 0:
            return False
        return random.random() < self.sample_rate

    def _extract_stack_frames(self, tb) -> List[Dict[str, Any]]:
        """Extract stack frames from traceback."""
        frames = []

        for frame_info in traceback.extract_tb(tb):
            frame = {
                "filename": os.path.basename(frame_info.filename),
                "abs_path": frame_info.filename,
                "function": frame_info.name,
                "lineno": frame_info.lineno,
                "module": self._get_module_name(frame_info.filename),
                "in_app": self._is_in_app(frame_info.filename),
            }

            # Try to get context lines
            try:
                if frame_info.line:
                    frame["context_line"] = frame_info.line
            except:
                pass

            frames.append(frame)

        return frames

    def _get_module_name(self, filename: str) -> Optional[str]:
        """Get module name from filename."""
        try:
            # Remove .py extension and convert path to module
            if filename.endswith(".py"):
                path = filename[:-3]
                # Try to make relative to site-packages or current dir
                for base in sys.path:
                    if base and path.startswith(base):
                        path = path[len(base):].lstrip(os.sep)
                        break
                return path.replace(os.sep, ".")
        except:
            pass
        return None

    def _is_in_app(self, filename: str) -> bool:
        """Check if frame is from application code (not library)."""
        if not filename:
            return True

        # Check if in site-packages
        for path in sys.path:
            if path and "site-packages" in path and filename.startswith(path):
                return False

        # Check common library paths
        lib_indicators = [
            "site-packages",
            "dist-packages",
            "/usr/lib",
            "/usr/local/lib",
            "\\lib\\",
            "\\Lib\\",
        ]

        for indicator in lib_indicators:
            if indicator in filename:
                return False

        return True

    def _get_runtime_context(self) -> Dict[str, Any]:
        """Get runtime context info."""
        return {
            "name": "Python",
            "version": platform.python_version(),
        }

    def _get_os_context(self) -> Dict[str, Any]:
        """Get OS context info."""
        return {
            "name": platform.system(),
            "version": platform.release(),
        }

    def _build_payload(
        self,
        exception: Exception = None,
        message: str = None,
        level: str = "error",
        extra_context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Build error payload."""
        extra_context = extra_context or {}

        # Get exception info
        exc_type = type(exception).__name__ if exception else "Message"
        exc_message = str(exception) if exception else message
        exc_traceback = exception.__traceback__ if exception else None

        # Extract stack frames
        frames = []
        stacktrace = None
        if exc_traceback:
            frames = self._extract_stack_frames(exc_traceback)
            stacktrace = "".join(traceback.format_exception(type(exception), exception, exc_traceback))

        payload = {
            "exception": {
                "type": exc_type,
                "value": exc_message,
                "stacktrace": {
                    "frames": frames,
                } if frames else None,
            },
            "type": exc_type,
            "message": exc_message,
            "stacktrace": stacktrace,

            # Service info
            "project": self.service,
            "service": self.service,
            "environment": self.environment,
            "release": self.release,

            # Contexts
            "contexts": {
                "runtime": self._get_runtime_context(),
                "os": self._get_os_context(),
            },

            # User context
            "user": self._scope.user if self._scope.user else None,

            # Tags
            "tags": {**self._scope.tags, **extra_context.get("tags", {})},

            # Extra data
            "extra": {**self._scope.extra, **extra_context.get("extra", {})},

            # Breadcrumbs
            "breadcrumbs": [
                {
                    "timestamp": b.timestamp,
                    "type": b.type,
                    "category": b.category,
                    "message": b.message,
                    "data": b.data,
                    "level": b.level,
                }
                for b in self._scope.breadcrumbs
            ],

            # SDK info
            "sdk": {
                "name": SDK_NAME,
                "version": SDK_VERSION,
            },

            # Timestamp
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
        }

        return payload

    def _send_event(self, payload: Dict[str, Any]):
        """Send event to OffCall API."""
        if not self.enabled or not self.api_key:
            if self.debug:
                print("[OffCall] SDK disabled or no API key")
            return

        # Apply before_send hook
        if self.before_send:
            payload = self.before_send(payload)
            if payload is None:
                if self.debug:
                    print("[OffCall] Event dropped by before_send")
                return

        try:
            data = json.dumps(payload).encode("utf-8")

            request = urllib.request.Request(
                self.endpoint,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": self.api_key,
                    "User-Agent": f"offcall-python/{SDK_VERSION}",
                },
                method="POST",
            )

            with urllib.request.urlopen(request, timeout=10) as response:
                if self.debug:
                    response_data = json.loads(response.read().decode("utf-8"))
                    print(f"[OffCall] Error reported: {response_data}")

        except urllib.error.HTTPError as e:
            if self.debug:
                print(f"[OffCall] HTTP error: {e.code} - {e.reason}")
        except urllib.error.URLError as e:
            if self.debug:
                print(f"[OffCall] URL error: {e.reason}")
        except Exception as e:
            if self.debug:
                print(f"[OffCall] Failed to send error: {e}")

    def capture_exception(self, exception: Exception = None, **kwargs) -> Optional[str]:
        """Capture an exception."""
        # Get exception from sys.exc_info() if not provided
        if exception is None:
            exc_info = sys.exc_info()
            if exc_info[1] is not None:
                exception = exc_info[1]
            else:
                if self.debug:
                    print("[OffCall] No exception to capture")
                return None

        # Check if should ignore
        if self._should_ignore(exception):
            if self.debug:
                print(f"[OffCall] Exception ignored: {type(exception).__name__}")
            return None

        # Check sampling
        if not self._should_sample():
            if self.debug:
                print("[OffCall] Exception sampled out")
            return None

        # Add error breadcrumb
        self.add_breadcrumb(
            message=str(exception),
            category="exception",
            type="error",
            level="error",
            data={"type": type(exception).__name__},
        )

        # Build and send payload
        payload = self._build_payload(exception=exception, extra_context=kwargs)
        self._send_event(payload)

        return None  # Event ID would go here

    def capture_message(self, message: str, level: str = "info", **kwargs) -> Optional[str]:
        """Capture a message."""
        # Check sampling
        if not self._should_sample():
            if self.debug:
                print("[OffCall] Message sampled out")
            return None

        # Add message breadcrumb
        self.add_breadcrumb(
            message=message,
            category="message",
            type="info",
            level=level,
        )

        # Build and send payload
        payload = self._build_payload(message=message, level=level, extra_context=kwargs)
        self._send_event(payload)

        return None  # Event ID would go here

    def set_user(self, user: Dict[str, Any]):
        """Set user context."""
        with self._lock:
            self._scope.set_user(user)

        self.add_breadcrumb(
            message="User context updated",
            category="user",
            data={"user_id": user.get("id")},
        )

    def clear_user(self):
        """Clear user context."""
        with self._lock:
            self._scope.clear_user()

    def set_tag(self, key: str, value: str):
        """Set a tag."""
        with self._lock:
            self._scope.set_tag(key, value)

    def set_tags(self, tags: Dict[str, str]):
        """Set multiple tags."""
        with self._lock:
            self._scope.set_tags(tags)

    def set_extra(self, key: str, value: Any):
        """Set extra context."""
        with self._lock:
            self._scope.set_extra(key, value)

    def set_extras(self, extras: Dict[str, Any]):
        """Set multiple extra context values."""
        with self._lock:
            self._scope.set_extras(extras)

    def add_breadcrumb(
        self,
        message: str = None,
        category: str = "default",
        level: str = "info",
        type: str = "default",
        data: Dict[str, Any] = None,
    ):
        """Add a breadcrumb."""
        breadcrumb = Breadcrumb(
            message=message or "",
            category=category,
            level=level,
            type=type,
            data=data or {},
        )

        with self._lock:
            self._scope.add_breadcrumb(breadcrumb)

    def configure_scope(self, callback: Callable[[Scope], None]):
        """Configure scope using callback."""
        with self._lock:
            callback(self._scope)

    def close(self):
        """Close the client and restore exception hook."""
        sys.excepthook = self._original_excepthook
