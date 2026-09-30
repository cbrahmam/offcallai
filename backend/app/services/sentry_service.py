# backend/app/services/sentry_service.py
"""Service for Sentry SDK compatibility - parsing and transformation."""
import gzip
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID

from app.schemas.sentry import (
    SentryEvent,
    SentryEnvelopeHeader,
    SentryItemHeader,
    ParsedEnvelope,
    SentryStackFrame,
    SentryBreadcrumb,
    SentryBreadcrumbs,
)
from app.schemas.error_tracking import (
    ErrorEventIngest,
    StackFrame,
    Breadcrumb,
)

logger = logging.getLogger(__name__)


class SentryService:
    """
    Service for handling Sentry SDK compatibility.

    Parses Sentry envelope format and transforms events to OffCall format.
    """

    @staticmethod
    def parse_envelope(body: bytes) -> ParsedEnvelope:
        """
        Parse Sentry envelope format.

        Sentry envelopes are newline-delimited:
        1. First line: JSON envelope header
        2. Pairs of: item header (JSON) + item payload

        Format:
        {"event_id":"...", "dsn":"...", ...}\n
        {"type":"event", "length":123}\n
        {event JSON payload}\n
        {"type":"session"}\n
        {session payload}\n
        ...
        """
        result = ParsedEnvelope(
            header=SentryEnvelopeHeader(),
            events=[],
            sessions=[],
            other_items=[]
        )

        try:
            # Decompress gzip if needed (sentry-sdk sends gzip by default)
            if body[:2] == b'\x1f\x8b':
                try:
                    body = gzip.decompress(body)
                except Exception as e:
                    logger.warning(f"Failed to gzip-decompress envelope: {e}")

            # Split by newlines, handling potential \r\n
            lines = body.replace(b'\r\n', b'\n').split(b'\n')
            lines = [line for line in lines if line.strip()]  # Remove empty lines

            if not lines:
                return result

            # First line is always the envelope header
            try:
                header_data = json.loads(lines[0])
                result.header = SentryEnvelopeHeader(**header_data)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse envelope header: {e}")
                # Try to continue anyway

            # Process remaining lines as item header/payload pairs
            i = 1
            while i < len(lines):
                try:
                    # Parse item header
                    item_header_data = json.loads(lines[i])
                    item_header = SentryItemHeader(**item_header_data)
                    i += 1

                    # Get item payload
                    if i < len(lines):
                        try:
                            payload = json.loads(lines[i])
                        except json.JSONDecodeError:
                            # Some payloads might be binary or malformed
                            payload = {"raw": lines[i].decode('utf-8', errors='replace')}
                        i += 1
                    else:
                        payload = {}

                    # Route based on item type
                    if item_header.type == "event":
                        try:
                            event = SentryEvent(**payload)
                            result.events.append(event)
                        except Exception as e:
                            logger.warning(f"Failed to parse event: {e}")
                            result.other_items.append(payload)
                    elif item_header.type == "session":
                        result.sessions.append(payload)
                    else:
                        result.other_items.append({
                            "type": item_header.type,
                            "payload": payload
                        })

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse item header at line {i}: {e}")
                    i += 1
                except Exception as e:
                    logger.warning(f"Error processing envelope item: {e}")
                    i += 1

        except Exception as e:
            logger.error(f"Failed to parse Sentry envelope: {e}")

        return result

    @staticmethod
    def parse_dsn(dsn: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Parse Sentry DSN format.

        Format: https://<public_key>@<host>/<project_id>
        Returns: (public_key, host, project_id)
        """
        try:
            # Remove protocol
            if dsn.startswith('https://'):
                dsn = dsn[8:]
            elif dsn.startswith('http://'):
                dsn = dsn[7:]

            # Split key from rest
            if '@' in dsn:
                key_part, rest = dsn.split('@', 1)
                public_key = key_part

                # Split host from project_id
                if '/' in rest:
                    parts = rest.rsplit('/', 1)
                    host = parts[0]
                    project_id = parts[1] if len(parts) > 1 else None
                else:
                    host = rest
                    project_id = None

                return public_key, host, project_id

        except Exception as e:
            logger.warning(f"Failed to parse DSN: {e}")

        return None, None, None

    @staticmethod
    def transform_event(sentry_event: SentryEvent, service_name: Optional[str] = None) -> ErrorEventIngest:
        """
        Transform a Sentry event to OffCall ErrorEventIngest format.

        Maps Sentry's event structure to our internal format.
        """
        # Extract error type and message from exception
        error_type = "Error"
        message = ""
        stack_trace = None
        stack_frames: List[StackFrame] = []

        if sentry_event.exception and sentry_event.exception.values:
            exc = sentry_event.exception.values[0]  # Primary exception
            error_type = exc.type or "Error"
            message = exc.value or ""

            # Extract stack frames
            if exc.stacktrace and exc.stacktrace.frames:
                for frame in exc.stacktrace.frames:
                    stack_frames.append(StackFrame(
                        filename=frame.filename,
                        function=frame.function,
                        lineno=frame.lineno,
                        colno=frame.colno,
                        abs_path=frame.abs_path,
                        context_line=frame.context_line,
                        pre_context=frame.pre_context,
                        post_context=frame.post_context,
                        in_app=frame.in_app,
                        module=frame.module,
                        vars=frame.vars,
                    ))

                # Build raw stack trace string
                stack_lines = []
                for frame in reversed(exc.stacktrace.frames):
                    line = f"  File \"{frame.abs_path or frame.filename}\""
                    if frame.lineno:
                        line += f", line {frame.lineno}"
                    if frame.function:
                        line += f", in {frame.function}"
                    stack_lines.append(line)
                    if frame.context_line:
                        stack_lines.append(f"    {frame.context_line.strip()}")
                stack_trace = "\n".join(stack_lines)

        # Handle message-only events
        elif sentry_event.message:
            if isinstance(sentry_event.message, str):
                message = sentry_event.message
            else:
                message = sentry_event.message.formatted or sentry_event.message.message or ""
            error_type = "Message"

        # Parse timestamp
        timestamp = None
        if sentry_event.timestamp:
            if isinstance(sentry_event.timestamp, datetime):
                timestamp = sentry_event.timestamp
            elif isinstance(sentry_event.timestamp, (int, float)):
                timestamp = datetime.fromtimestamp(sentry_event.timestamp, tz=timezone.utc)
            elif isinstance(sentry_event.timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(sentry_event.timestamp.replace('Z', '+00:00'))
                except:
                    timestamp = datetime.now(timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)

        # Extract contexts
        runtime = None
        runtime_version = None
        os_name = None
        os_version = None
        browser = None
        browser_version = None
        device = None
        trace_id = None
        span_id = None

        if sentry_event.contexts:
            # Runtime context
            if sentry_event.contexts.runtime:
                runtime = sentry_event.contexts.runtime.get("name")
                runtime_version = sentry_event.contexts.runtime.get("version")

            # OS context
            if sentry_event.contexts.os:
                os_name = sentry_event.contexts.os.get("name")
                os_version = sentry_event.contexts.os.get("version")

            # Browser context
            if sentry_event.contexts.browser:
                browser = sentry_event.contexts.browser.get("name")
                browser_version = sentry_event.contexts.browser.get("version")

            # Device context
            if sentry_event.contexts.device:
                device = sentry_event.contexts.device.get("model")

            # Trace context (for distributed tracing)
            if sentry_event.contexts.trace:
                trace_id = sentry_event.contexts.trace.get("trace_id")
                span_id = sentry_event.contexts.trace.get("span_id")

        # Extract user info
        user_id = None
        user_email = None
        user_ip = None
        if sentry_event.user:
            user_id = sentry_event.user.id
            user_email = sentry_event.user.email
            user_ip = sentry_event.user.ip_address

        # Extract request info
        request_url = None
        request_method = None
        request_headers = None
        if sentry_event.request:
            request_url = sentry_event.request.url
            request_method = sentry_event.request.method
            request_headers = sentry_event.request.headers

        # Transform breadcrumbs
        breadcrumbs: List[Breadcrumb] = []
        if sentry_event.breadcrumbs:
            crumb_list = []
            if isinstance(sentry_event.breadcrumbs, SentryBreadcrumbs):
                crumb_list = sentry_event.breadcrumbs.values or []
            elif isinstance(sentry_event.breadcrumbs, list):
                crumb_list = sentry_event.breadcrumbs

            for crumb in crumb_list:
                if isinstance(crumb, dict):
                    crumb = SentryBreadcrumb(**crumb)

                # Parse breadcrumb timestamp
                crumb_ts = datetime.now(timezone.utc)
                if crumb.timestamp:
                    if isinstance(crumb.timestamp, datetime):
                        crumb_ts = crumb.timestamp
                    elif isinstance(crumb.timestamp, (int, float)):
                        crumb_ts = datetime.fromtimestamp(crumb.timestamp, tz=timezone.utc)
                    elif isinstance(crumb.timestamp, str):
                        try:
                            crumb_ts = datetime.fromisoformat(crumb.timestamp.replace('Z', '+00:00'))
                        except:
                            pass

                breadcrumbs.append(Breadcrumb(
                    timestamp=crumb_ts,
                    category=crumb.category or crumb.type,
                    message=crumb.message,
                    level=crumb.level,
                    data=crumb.data,
                ))

        # Extract SDK info
        sdk_name = None
        sdk_version = None
        if sentry_event.sdk:
            sdk_name = sentry_event.sdk.name
            sdk_version = sentry_event.sdk.version

        # Determine service name
        final_service_name = service_name
        if not final_service_name:
            # Try to extract from various places
            final_service_name = (
                sentry_event.transaction or
                sentry_event.server_name or
                sentry_event.logger or
                "unknown"
            )

        return ErrorEventIngest(
            error_type=error_type,
            message=message,
            stack_trace=stack_trace,
            stack_frames=stack_frames,
            service_name=final_service_name,
            environment=sentry_event.environment or "production",
            release=sentry_event.release,
            timestamp=timestamp,
            user_id=user_id,
            user_email=user_email,
            user_ip=user_ip,
            request_url=request_url,
            request_method=request_method,
            request_headers=request_headers,
            runtime=runtime,
            runtime_version=runtime_version,
            os=os_name,
            os_version=os_version,
            browser=browser,
            browser_version=browser_version,
            device=device,
            trace_id=trace_id,
            span_id=span_id,
            tags=sentry_event.tags,
            extra=sentry_event.extra,
            breadcrumbs=breadcrumbs if breadcrumbs else None,
            sdk_name=sdk_name or "sentry",
            sdk_version=sdk_version,
            fingerprint=sentry_event.fingerprint,
        )

    @staticmethod
    def extract_api_key_from_dsn(dsn: str) -> Optional[str]:
        """
        Extract the API key portion from a Sentry DSN.

        The DSN format is: https://<api_key>@<host>/<project_id>
        We use the api_key portion for authentication.
        """
        public_key, _, _ = SentryService.parse_dsn(dsn)
        return public_key
