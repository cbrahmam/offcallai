# ClickHouse Service for OffCall AI
# Handles all time-series data: metrics, logs, traces, profiles

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import httpx
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Shared connection pool for all ClickHouse requests
_shared_client: Optional[httpx.AsyncClient] = None
_client_lock: Optional[asyncio.Lock] = None


def _get_lock() -> asyncio.Lock:
    """Get or create the asyncio lock (must be called from async context)."""
    global _client_lock
    if _client_lock is None:
        _client_lock = asyncio.Lock()
    return _client_lock


async def get_shared_clickhouse_client() -> httpx.AsyncClient:
    """Get or create a shared httpx client for ClickHouse connections."""
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        lock = _get_lock()
        async with lock:
            # Double-check after acquiring lock
            if _shared_client is None or _shared_client.is_closed:
                _shared_client = httpx.AsyncClient(
                    timeout=60.0,
                    limits=httpx.Limits(
                        max_connections=100,
                        max_keepalive_connections=20,
                        keepalive_expiry=30.0
                    ),
                    auth=(
                        settings.CLICKHOUSE_USER or "default",
                        settings.CLICKHOUSE_PASSWORD
                    ),
                    headers={"Content-Type": "application/json"}
                )
    return _shared_client


def format_datetime_for_clickhouse(dt: datetime) -> str:
    """Format datetime for ClickHouse queries (no timezone info)."""
    # Remove timezone info and format as ClickHouse expects
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def _as_int(value, default: int = 0) -> int:
    """ClickHouse returns 64-bit integers as JSON strings."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value, default: float = 0.0) -> float:
    """ClickHouse returns some numeric aggregates as JSON strings."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class ClickHouseService:
    """
    ClickHouse client for time-series observability data.
    Uses HTTP interface for async compatibility.
    Uses a shared connection pool for efficient concurrent access.
    """

    def __init__(self):
        self.host = settings.CLICKHOUSE_HOST
        self.port = settings.CLICKHOUSE_PORT or 8443
        self.username = settings.CLICKHOUSE_USER or "default"
        self.password = settings.CLICKHOUSE_PASSWORD
        self.database = settings.CLICKHOUSE_DATABASE or "offcall"
        self.use_ssl = settings.CLICKHOUSE_USE_SSL if hasattr(settings, 'CLICKHOUSE_USE_SSL') else True

        protocol = "https" if self.use_ssl else "http"
        self.base_url = f"{protocol}://{self.host}:{self.port}"

    async def get_client(self) -> httpx.AsyncClient:
        """Get the shared httpx client."""
        return await get_shared_clickhouse_client()

    async def close(self):
        """No-op for shared client - client is managed globally."""
        pass

    async def ensure_tables(self):
        """Create required ClickHouse tables if they don't exist."""
        tables = [
            """CREATE TABLE IF NOT EXISTS spans (
                timestamp DateTime64(3) DEFAULT now64(3),
                organization_id UUID,
                trace_id String,
                span_id String,
                parent_span_id String DEFAULT '',
                service_name LowCardinality(String),
                operation_name String,
                span_kind LowCardinality(String) DEFAULT 'INTERNAL',
                duration_ms Float64 DEFAULT 0,
                status_code LowCardinality(String) DEFAULT 'OK',
                status_message String DEFAULT '',
                attributes Map(String, String) DEFAULT map(),
                events String DEFAULT '[]',
                links String DEFAULT '[]',
                INDEX idx_trace_id trace_id TYPE bloom_filter GRANULARITY 4,
                INDEX idx_service service_name TYPE bloom_filter GRANULARITY 4,
                INDEX idx_status status_code TYPE set(10) GRANULARITY 4
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMMDD(timestamp)
            ORDER BY (organization_id, trace_id, timestamp)
            TTL timestamp + INTERVAL 14 DAY
            SETTINGS index_granularity = 8192""",
            """CREATE TABLE IF NOT EXISTS metrics (
                timestamp DateTime64(3) DEFAULT now64(3),
                organization_id UUID,
                host_id Nullable(UUID),
                name LowCardinality(String),
                value Float64,
                unit LowCardinality(String) DEFAULT '',
                tags Map(LowCardinality(String), String) DEFAULT map(),
                INDEX idx_name name TYPE bloom_filter GRANULARITY 4,
                INDEX idx_tags_keys mapKeys(tags) TYPE bloom_filter GRANULARITY 4
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMM(timestamp)
            ORDER BY (organization_id, name, timestamp)
            TTL timestamp + INTERVAL 90 DAY
            SETTINGS index_granularity = 8192""",
            """CREATE TABLE IF NOT EXISTS logs (
                timestamp DateTime64(3) DEFAULT now64(3),
                organization_id UUID,
                host_id Nullable(UUID),
                level LowCardinality(String) DEFAULT 'INFO',
                message String,
                service LowCardinality(String) DEFAULT '',
                source LowCardinality(String) DEFAULT '',
                trace_id String DEFAULT '',
                span_id String DEFAULT '',
                fields Map(String, String) DEFAULT map(),
                INDEX idx_message message TYPE tokenbf_v1(10240, 3, 0) GRANULARITY 4,
                INDEX idx_level level TYPE set(10) GRANULARITY 4,
                INDEX idx_service service TYPE bloom_filter GRANULARITY 4
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMMDD(timestamp)
            ORDER BY (organization_id, timestamp, level)
            TTL timestamp + INTERVAL 30 DAY
            SETTINGS index_granularity = 8192""",
            """CREATE TABLE IF NOT EXISTS rum_events (
                timestamp DateTime64(3) DEFAULT now64(3),
                organization_id UUID,
                application_id UUID,
                session_id String,
                event_type LowCardinality(String),
                url String DEFAULT '',
                url_path String DEFAULT '',
                page_title String DEFAULT '',
                time_on_page_ms Int64 DEFAULT 0,
                lcp_ms Int64 DEFAULT 0,
                fid_ms Int64 DEFAULT 0,
                cls Float64 DEFAULT 0,
                fcp_ms Int64 DEFAULT 0,
                ttfb_ms Int64 DEFAULT 0,
                inp_ms Int64 DEFAULT 0,
                dns_lookup_ms Int64 DEFAULT 0,
                tcp_connect_ms Int64 DEFAULT 0,
                request_time_ms Int64 DEFAULT 0,
                response_time_ms Int64 DEFAULT 0,
                dom_interactive_ms Int64 DEFAULT 0,
                dom_complete_ms Int64 DEFAULT 0,
                load_event_ms Int64 DEFAULT 0,
                error_type String DEFAULT '',
                error_name String DEFAULT '',
                error_message String DEFAULT '',
                stack_trace String DEFAULT '',
                filename String DEFAULT '',
                line_number Int32 DEFAULT 0,
                column_number Int32 DEFAULT 0,
                action_type LowCardinality(String) DEFAULT '',
                action_name String DEFAULT '',
                target_selector String DEFAULT '',
                user_agent String DEFAULT '',
                country LowCardinality(String) DEFAULT '',
                attributes Map(String, String) DEFAULT map(),
                INDEX idx_session session_id TYPE bloom_filter GRANULARITY 4,
                INDEX idx_event_type event_type TYPE set(10) GRANULARITY 4,
                INDEX idx_url_path url_path TYPE bloom_filter GRANULARITY 4
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMMDD(timestamp)
            ORDER BY (organization_id, application_id, session_id, timestamp)
            TTL timestamp + INTERVAL 30 DAY
            SETTINGS index_granularity = 8192""",
        ]
        for ddl in tables:
            try:
                await self.execute(ddl)
            except Exception as e:
                logger.warning(f"ClickHouse table creation skipped: {e}")

    async def execute(self, query: str, params: Optional[Dict] = None) -> Any:
        """Execute a ClickHouse query."""
        client = await self.get_client()

        url = f"{self.base_url}/?database={self.database}"

        if params:
            # Use parameterized queries for safety
            for key, value in params.items():
                if isinstance(value, str):
                    query = query.replace(f"{{{key}}}", f"'{value}'")
                elif isinstance(value, (list, tuple)):
                    formatted = ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in value)
                    query = query.replace(f"{{{key}}}", f"({formatted})")
                else:
                    query = query.replace(f"{{{key}}}", str(value))

        try:
            response = await client.post(url, content=query)
            response.raise_for_status()

            if response.text.strip():
                # Try to parse as JSON if FORMAT JSON was used
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return response.text
            return None
        except httpx.HTTPStatusError as e:
            error_text = e.response.text
            # Handle missing tables gracefully - return empty result
            if "UNKNOWN_TABLE" in error_text or "doesn't exist" in error_text.lower():
                logger.warning(f"ClickHouse table not found, returning empty result: {error_text[:100]}")
                return {"data": [], "rows": 0}
            logger.error(f"ClickHouse query error: {error_text}")
            raise
        except httpx.ConnectError as e:
            logger.warning(f"ClickHouse connection failed, returning empty result: {e}")
            return {"data": [], "rows": 0}
        except httpx.ConnectTimeout as e:
            logger.warning(f"ClickHouse connection timeout, returning empty result: {e}")
            return {"data": [], "rows": 0}
        except Exception as e:
            logger.error(f"ClickHouse connection error: {e}")
            raise

    async def insert_json(self, table: str, rows: List[Dict]) -> None:
        """Insert rows into a table using JSONEachRow format."""
        if not rows:
            return

        client = await self.get_client()
        url = f"{self.base_url}/?database={self.database}&query=INSERT INTO {table} FORMAT JSONEachRow"

        # Convert rows to JSONEachRow format (newline-delimited JSON)
        body = "\n".join(json.dumps(row, default=str) for row in rows)

        try:
            response = await client.post(url, content=body)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            error_text = e.response.text
            # Silently ignore missing tables - they'll be created when ClickHouse is properly initialized
            if "UNKNOWN_TABLE" in error_text or "doesn't exist" in error_text.lower():
                logger.warning(f"ClickHouse table '{table}' not found, skipping insert")
                return
            logger.error(f"ClickHouse insert error: {error_text}")
            raise
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            logger.warning(f"ClickHouse connection issue during insert, skipping: {e}")
            return

    # =========================================================================
    # METRICS
    # =========================================================================

    async def insert_metrics(self, metrics: List[Dict]) -> None:
        """Insert metrics batch."""
        rows = []
        for m in metrics:
            # Handle timestamp - convert to ClickHouse-compatible format
            ts = m.get("timestamp")
            if ts is None:
                ts = format_datetime_for_clickhouse(datetime.utcnow())
            elif isinstance(ts, datetime):
                ts = format_datetime_for_clickhouse(ts)
            elif isinstance(ts, str):
                # Remove timezone suffix if present (e.g., +00:00, Z)
                ts = ts.replace('+00:00', '').replace('Z', '').replace('T', ' ')
                # Trim to seconds precision if needed
                if '.' in ts:
                    ts = ts[:ts.index('.') + 7]  # Keep up to 6 decimal places

            rows.append({
                "timestamp": ts,
                "organization_id": m["organization_id"],
                "host_id": m.get("host_id"),
                "name": m["name"],
                "value": float(m["value"]),
                "unit": m.get("unit", ""),
                "tags": m.get("tags", {}),
            })
        await self.insert_json("metrics", rows)

    async def query_metrics(
        self,
        organization_id: str,
        name: str,
        start_time: datetime,
        end_time: datetime,
        host_id: Optional[str] = None,
        interval: str = "1 MINUTE",
        aggregation: str = "avg"
    ) -> List[Dict]:
        """Query metrics with time bucketing."""

        host_filter = f"AND host_id = '{host_id}'" if host_id else ""

        query = f"""
        SELECT
            toStartOfInterval(timestamp, INTERVAL {interval}) as time_bucket,
            {aggregation}(value) as value,
            name
        FROM metrics
        WHERE organization_id = '{organization_id}'
            AND name = '{name}'
            AND timestamp >= '{format_datetime_for_clickhouse(start_time)}'
            AND timestamp <= '{format_datetime_for_clickhouse(end_time)}'
            {host_filter}
        GROUP BY time_bucket, name
        ORDER BY time_bucket
        FORMAT JSON
        """

        result = await self.execute(query)
        return result.get("data", []) if result else []

    async def get_metric_names(self, organization_id: str) -> List[str]:
        """Get all unique metric names for an org."""
        query = f"""
        SELECT DISTINCT name
        FROM metrics
        WHERE organization_id = '{organization_id}'
        FORMAT JSON
        """
        result = await self.execute(query)
        return [r["name"] for r in result.get("data", [])] if result else []

    # =========================================================================
    # LOGS
    # =========================================================================

    async def insert_logs(self, logs: List[Dict]) -> None:
        """Insert logs batch."""
        rows = []
        for log in logs:
            # Handle timestamp - convert to ClickHouse-compatible format
            ts = log.get("timestamp")
            if ts is None:
                ts = format_datetime_for_clickhouse(datetime.utcnow())
            elif isinstance(ts, datetime):
                ts = format_datetime_for_clickhouse(ts)
            elif isinstance(ts, str):
                # Remove timezone suffix if present (e.g., +00:00, Z)
                ts = ts.replace('+00:00', '').replace('Z', '').replace('T', ' ')
                # Trim to seconds precision if needed
                if '.' in ts:
                    ts = ts[:ts.index('.') + 7]  # Keep up to 6 decimal places

            rows.append({
                "timestamp": ts,
                "organization_id": log["organization_id"],
                "host_id": log.get("host_id"),
                "level": log.get("level", "INFO"),
                "message": log["message"],
                "service": log.get("service", ""),
                "source": log.get("source", ""),
                "trace_id": log.get("trace_id", ""),
                "span_id": log.get("span_id", ""),
                "fields": log.get("fields", {}),
            })
        await self.insert_json("logs", rows)

    async def search_logs(
        self,
        organization_id: str,
        start_time: datetime,
        end_time: datetime,
        query: Optional[str] = None,
        levels: Optional[List[str]] = None,
        services: Optional[List[str]] = None,
        host_id: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0
    ) -> Dict:
        """Search logs with full-text search and filters."""

        filters = [
            f"organization_id = '{organization_id}'",
            f"timestamp >= '{format_datetime_for_clickhouse(start_time)}'",
            f"timestamp <= '{format_datetime_for_clickhouse(end_time)}'",
        ]

        if query:
            # Full-text search on message
            filters.append(f"message ILIKE '%{query}%'")

        if levels:
            levels_str = ", ".join(f"'{l}'" for l in levels)
            filters.append(f"level IN ({levels_str})")

        if services:
            services_str = ", ".join(f"'{s}'" for s in services)
            filters.append(f"service IN ({services_str})")

        if host_id:
            filters.append(f"host_id = '{host_id}'")

        where_clause = " AND ".join(filters)

        # Single query: fetch logs + total count in one round trip
        logs_query = f"""
        SELECT
            timestamp,
            level,
            message,
            service,
            source,
            host_id,
            trace_id,
            span_id,
            fields,
            count() OVER () as _total
        FROM logs
        WHERE {where_clause}
        ORDER BY timestamp DESC
        LIMIT {limit}
        OFFSET {offset}
        FORMAT JSON
        """

        result = await self.execute(logs_query)
        raw_logs = result.get("data", []) if result else []

        # Extract total from window function, then strip _total from logs
        total = int(raw_logs[0].get("_total", 0)) if raw_logs else 0

        # Add id field for frontend compatibility
        logs = []
        for i, log in enumerate(raw_logs):
            log.pop("_total", None)
            log["id"] = f"{log.get('timestamp', '')}_{log.get('span_id', '')}_{i}"
            log["tags"] = []  # ClickHouse doesn't store tags separately
            logs.append(log)

        return {
            "logs": logs,
            "total": total,
            "limit": limit,
            "offset": offset
        }

    async def get_log_stats(
        self,
        organization_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> Dict:
        """Get log statistics (counts by level, by service)."""

        query = f"""
        SELECT
            level,
            count() as count
        FROM logs
        WHERE organization_id = '{organization_id}'
            AND timestamp >= '{format_datetime_for_clickhouse(start_time)}'
            AND timestamp <= '{format_datetime_for_clickhouse(end_time)}'
        GROUP BY level
        ORDER BY count DESC
        FORMAT JSON
        """

        result = await self.execute(query)
        by_level = result.get("data", []) if result else []

        # Total count
        total = sum(r.get("count", 0) for r in by_level)

        # Get by_source stats
        source_query = f"""
        SELECT
            service as source,
            count() as count
        FROM logs
        WHERE organization_id = '{organization_id}'
            AND timestamp >= '{format_datetime_for_clickhouse(start_time)}'
            AND timestamp <= '{format_datetime_for_clickhouse(end_time)}'
        GROUP BY service
        ORDER BY count DESC
        LIMIT 10
        FORMAT JSON
        """
        source_result = await self.execute(source_query)
        by_source = source_result.get("data", []) if source_result else []

        return {
            "total_logs": total,
            "time_range_hours": int((end_time - start_time).total_seconds() / 3600),
            "by_level": by_level,
            "by_source": by_source,
            "logs_per_hour": []
        }

    # =========================================================================
    # TRACES / SPANS
    # =========================================================================

    async def insert_spans(self, spans: List[Dict]) -> None:
        """Insert trace spans."""
        rows = []
        for span in spans:
            rows.append({
                "timestamp": span.get("start_time") or datetime.utcnow().isoformat(),
                "organization_id": span["organization_id"],
                "trace_id": span["trace_id"],
                "span_id": span["span_id"],
                "parent_span_id": span.get("parent_span_id", ""),
                "service_name": span["service_name"],
                "operation_name": span["operation_name"],
                "span_kind": span.get("span_kind", "INTERNAL"),
                "duration_ms": span.get("duration_ms", 0),
                "status_code": span.get("status_code", "OK"),
                "status_message": span.get("status_message", ""),
                "attributes": span.get("attributes", {}),
                "events": span.get("events", []),
                "links": span.get("links", []),
            })
        await self.insert_json("spans", rows)

    async def get_trace(self, organization_id: str, trace_id: str) -> Dict:
        """Get all spans for a trace. Returns data matching TraceResponse schema."""
        query = f"""
        SELECT
            trace_id,
            span_id,
            parent_span_id,
            service_name,
            operation_name,
            span_kind,
            timestamp,
            duration_ms,
            status_code,
            status_message,
            attributes,
            events
        FROM spans
        WHERE organization_id = '{organization_id}'
            AND trace_id = '{trace_id}'
        ORDER BY timestamp
        FORMAT JSON
        """

        result = await self.execute(query)
        raw_spans = result.get("data", []) if result else []

        if not raw_spans:
            return None

        # Transform spans to SpanResponse format
        spans = []
        root_span = None
        for s in raw_spans:
            span_id = s.get("span_id", "")
            parent_id = s.get("parent_span_id", "")

            # Find root span (no parent)
            if not parent_id and root_span is None:
                root_span = s

            spans.append({
                "id": span_id,  # Use span_id as id
                "trace_id": s.get("trace_id", trace_id),
                "span_id": span_id,
                "parent_span_id": parent_id if parent_id else None,
                "service_name": s.get("service_name", ""),
                "operation_name": s.get("operation_name", ""),
                "span_kind": s.get("span_kind", "INTERNAL"),
                "start_time": s.get("timestamp"),
                "end_time": None,  # ClickHouse only stores start + duration
                "duration_ms": s.get("duration_ms"),
                "status": s.get("status_code", "OK"),
                "status_message": s.get("status_message"),
                "resource_attributes": {},
                "attributes": s.get("attributes", {}),
                "events": s.get("events", []) if isinstance(s.get("events"), list) else [],
                "links": []
            })

        # Calculate trace-level metrics
        total_duration = max(s.get("duration_ms", 0) or 0 for s in raw_spans) if raw_spans else 0
        services = list(set(s.get("service_name") for s in raw_spans if s.get("service_name")))
        error_count = sum(1 for s in raw_spans if s.get("status_code") == "ERROR")
        has_error = error_count > 0

        # Get root span info
        root_service = root_span.get("service_name") if root_span else (services[0] if services else None)
        root_operation = root_span.get("operation_name") if root_span else None
        start_time = root_span.get("timestamp") if root_span else (raw_spans[0].get("timestamp") if raw_spans else None)

        return {
            "id": trace_id,
            "trace_id": trace_id,
            "root_service": root_service,
            "root_operation": root_operation,
            "start_time": start_time,
            "end_time": None,
            "duration_ms": total_duration,
            "span_count": len(spans),
            "service_count": len(services),
            "error_count": error_count,
            "has_error": has_error,
            "services": services,
            "spans": spans,
            "tags": {}
        }

    async def search_traces(
        self,
        organization_id: str,
        start_time: datetime,
        end_time: datetime,
        service: Optional[str] = None,
        operation: Optional[str] = None,
        min_duration_ms: Optional[float] = None,
        max_duration_ms: Optional[float] = None,
        has_error: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict:
        """Search for traces. Returns data matching TraceSummary schema."""

        filters = [
            f"organization_id = '{organization_id}'",
            f"timestamp >= '{format_datetime_for_clickhouse(start_time)}'",
            f"timestamp <= '{format_datetime_for_clickhouse(end_time)}'",
            "parent_span_id = ''"  # Root spans only
        ]

        if service:
            filters.append(f"service_name = '{service}'")

        if operation:
            filters.append(f"operation_name ILIKE '%{operation}%'")

        if min_duration_ms:
            filters.append(f"duration_ms >= {min_duration_ms}")

        if max_duration_ms:
            filters.append(f"duration_ms <= {max_duration_ms}")

        if has_error is not None:
            status = "ERROR" if has_error else "OK"
            filters.append(f"status_code = '{status}'")

        where_clause = " AND ".join(filters)

        # Get total count
        count_query = f"""
        SELECT count() as total
        FROM spans
        WHERE {where_clause}
        FORMAT JSON
        """
        count_result = await self.execute(count_query)
        total = _as_int(count_result.get("data", [{}])[0].get("total", 0)) if count_result else 0

        # Query root spans with aggregated trace info
        query = f"""
        SELECT
            root.trace_id,
            root.service_name as root_service,
            root.operation_name as root_operation,
            root.timestamp as start_time,
            root.duration_ms,
            root.status_code,
            trace_stats.span_count,
            trace_stats.error_count,
            trace_stats.services
        FROM spans root
        LEFT JOIN (
            SELECT
                trace_id,
                count() as span_count,
                countIf(status_code = 'ERROR') as error_count,
                groupArray(DISTINCT service_name) as services
            FROM spans
            WHERE organization_id = '{organization_id}'
                AND timestamp >= '{format_datetime_for_clickhouse(start_time)}'
                AND timestamp <= '{format_datetime_for_clickhouse(end_time)}'
            GROUP BY trace_id
        ) trace_stats ON root.trace_id = trace_stats.trace_id
        WHERE {where_clause}
        ORDER BY root.timestamp DESC
        LIMIT {limit}
        OFFSET {offset}
        FORMAT JSON
        """

        result = await self.execute(query)
        raw_traces = result.get("data", []) if result else []

        # Transform to TraceSummary format
        traces = []
        for t in raw_traces:
            trace_id = t.get("trace_id", "")
            error_count = _as_int(t.get("error_count", 0))
            traces.append({
                "id": trace_id,  # Use trace_id as id
                "trace_id": trace_id,
                "root_service": t.get("root_service"),
                "root_operation": t.get("root_operation"),
                "start_time": t.get("start_time"),
                "duration_ms": t.get("duration_ms"),
                "span_count": _as_int(t.get("span_count", 1), 1),
                "error_count": error_count,
                "has_error": error_count > 0 or t.get("status_code") == "ERROR",
                "services": t.get("services", [])
            })

        return {
            "traces": traces,
            "total": total,
            "has_more": (offset + len(traces)) < total,
            "query": {
                "start_time": start_time,
                "end_time": end_time,
                "service": service,
                "operation": operation,
                "min_duration_ms": min_duration_ms,
                "max_duration_ms": max_duration_ms,
                "has_error": has_error,
                "limit": limit,
                "offset": offset
            }
        }

    async def get_service_map(
        self,
        organization_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> Dict:
        """Build service dependency map from spans."""

        # Get service-to-service calls
        query = f"""
        SELECT
            s1.service_name as source,
            s2.service_name as target,
            count() as request_count,
            avg(s2.duration_ms) as avg_duration,
            countIf(s2.status_code = 'ERROR') as error_count
        FROM spans s1
        JOIN spans s2 ON s1.span_id = s2.parent_span_id
            AND s1.organization_id = s2.organization_id
            AND s1.trace_id = s2.trace_id
        WHERE s1.organization_id = '{organization_id}'
            AND s1.timestamp >= '{format_datetime_for_clickhouse(start_time)}'
            AND s1.timestamp <= '{format_datetime_for_clickhouse(end_time)}'
            AND s1.service_name != s2.service_name
        GROUP BY source, target
        ORDER BY request_count DESC
        FORMAT JSON
        """

        result = await self.execute(query)
        raw_edges = result.get("data", []) if result else []

        # Transform edges to include required fields
        edges = []
        for edge in raw_edges:
            req_count = _as_int(edge.get("request_count", 1), 1)
            error_count = _as_int(edge.get("error_count", 0))
            edges.append({
                "source": edge.get("source"),
                "target": edge.get("target"),
                "request_count": req_count,
                "error_rate": (error_count / req_count * 100) if req_count > 0 else 0,
                "latency_avg": edge.get("avg_duration", 0)
            })

        # Get unique services with stats
        services_query = f"""
        SELECT
            service_name,
            count() as request_count,
            avg(duration_ms) as avg_duration,
            quantile(0.95)(duration_ms) as p95_duration,
            countIf(status_code = 'ERROR') as error_count
        FROM spans
        WHERE organization_id = '{organization_id}'
            AND timestamp >= '{format_datetime_for_clickhouse(start_time)}'
            AND timestamp <= '{format_datetime_for_clickhouse(end_time)}'
        GROUP BY service_name
        FORMAT JSON
        """

        services_result = await self.execute(services_query)
        raw_services = services_result.get("data", []) if services_result else []

        # Transform nodes to include required fields
        nodes = []
        for svc in raw_services:
            req_count = _as_int(svc.get("request_count", 1), 1)
            error_count = _as_int(svc.get("error_count", 0))
            nodes.append({
                "service_name": svc.get("service_name"),
                "request_count": req_count,
                "error_rate": (error_count / req_count * 100) if req_count > 0 else 0,
                "latency_avg": svc.get("avg_duration", 0),
                "latency_p95": svc.get("p95_duration", 0)
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "time_range_hours": int((end_time - start_time).total_seconds() / 3600)
        }

    async def get_services(
        self,
        organization_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> Dict:
        """Get list of services with metrics."""

        time_range_seconds = (end_time - start_time).total_seconds()

        query = f"""
        SELECT
            service_name,
            count() as request_count,
            avg(duration_ms) as avg_latency,
            quantile(0.50)(duration_ms) as p50_latency,
            quantile(0.95)(duration_ms) as p95_latency,
            quantile(0.99)(duration_ms) as p99_latency,
            countIf(status_code = 'ERROR') as error_count,
            countIf(status_code = 'ERROR') / count() * 100 as error_rate
        FROM spans
        WHERE organization_id = '{organization_id}'
            AND timestamp >= '{format_datetime_for_clickhouse(start_time)}'
            AND timestamp <= '{format_datetime_for_clickhouse(end_time)}'
        GROUP BY service_name
        ORDER BY request_count DESC
        FORMAT JSON
        """

        result = await self.execute(query)
        raw_services = result.get("data", []) if result else []

        # Get service dependencies for upstream/downstream
        deps_query = f"""
        SELECT
            s1.service_name as source,
            s2.service_name as target
        FROM spans s1
        JOIN spans s2 ON s1.span_id = s2.parent_span_id
            AND s1.organization_id = s2.organization_id
            AND s1.trace_id = s2.trace_id
        WHERE s1.organization_id = '{organization_id}'
            AND s1.timestamp >= '{format_datetime_for_clickhouse(start_time)}'
            AND s1.timestamp <= '{format_datetime_for_clickhouse(end_time)}'
            AND s1.service_name != s2.service_name
        GROUP BY source, target
        FORMAT JSON
        """

        deps_result = await self.execute(deps_query)
        deps = deps_result.get("data", []) if deps_result else []

        # Build upstream/downstream maps
        upstream_map = {}  # service -> list of services that call it
        downstream_map = {}  # service -> list of services it calls

        for dep in deps:
            source = dep.get("source", "")
            target = dep.get("target", "")
            if source and target:
                downstream_map.setdefault(source, []).append(target)
                upstream_map.setdefault(target, []).append(source)

        # Transform to ServiceSummary format
        services = []
        for svc in raw_services:
            service_name = svc.get("service_name", "")
            req_count = _as_int(svc.get("request_count", 0))
            services.append({
                "service_name": service_name,
                "request_count": req_count,
                "error_count": _as_int(svc.get("error_count", 0)),
                "error_rate": svc.get("error_rate", 0),
                "latency_avg": svc.get("avg_latency", 0),
                "latency_p50": svc.get("p50_latency", 0),
                "latency_p95": svc.get("p95_latency", 0),
                "latency_p99": svc.get("p99_latency", 0),
                "requests_per_second": req_count / time_range_seconds if time_range_seconds > 0 else 0,
                "upstream_services": list(set(upstream_map.get(service_name, []))),
                "downstream_services": list(set(downstream_map.get(service_name, [])))
            })

        return {
            "services": services,
            "time_range_hours": int(time_range_seconds / 3600)
        }

    async def get_service_metrics(
        self,
        organization_id: str,
        service_name: str,
        start_time: datetime,
        end_time: datetime,
        interval: str = "5 MINUTE"
    ) -> List[Dict]:
        """Get service metrics over time (latency, throughput, errors)."""

        query = f"""
        SELECT
            toStartOfInterval(timestamp, INTERVAL {interval}) as time_bucket,
            count() as request_count,
            avg(duration_ms) as avg_duration,
            quantile(0.50)(duration_ms) as p50,
            quantile(0.95)(duration_ms) as p95,
            quantile(0.99)(duration_ms) as p99,
            countIf(status_code = 'ERROR') as error_count,
            error_count / request_count * 100 as error_rate
        FROM spans
        WHERE organization_id = '{organization_id}'
            AND service_name = '{service_name}'
            AND timestamp >= '{format_datetime_for_clickhouse(start_time)}'
            AND timestamp <= '{format_datetime_for_clickhouse(end_time)}'
        GROUP BY time_bucket
        ORDER BY time_bucket
        FORMAT JSON
        """

        result = await self.execute(query)
        return result.get("data", []) if result else []

    # =========================================================================
    # RUM (Real User Monitoring)
    # =========================================================================

    async def insert_rum_events(self, events: List[Dict]) -> None:
        """Insert RUM events (page views, errors, resources)."""
        rows = []
        for event in events:
            rows.append({
                "timestamp": event.get("timestamp") or datetime.utcnow().isoformat(),
                "organization_id": event["organization_id"],
                "application_id": event["application_id"],
                "session_id": event["session_id"],
                "event_type": event["event_type"],  # pageview, error, resource, webvital
                "url": event.get("url", ""),
                "user_id": event.get("user_id", ""),
                "device_type": event.get("device_type", ""),
                "browser": event.get("browser", ""),
                "os": event.get("os", ""),
                "country": event.get("country", ""),
                "duration_ms": event.get("duration_ms", 0),
                "lcp_ms": event.get("lcp_ms", 0),
                "fid_ms": event.get("fid_ms", 0),
                "cls_score": event.get("cls_score", 0),
                "error_message": event.get("error_message", ""),
                "error_stack": event.get("error_stack", ""),
                "metadata": event.get("metadata", {}),
            })
        await self.insert_json("rum_events", rows)

    async def get_rum_stats(
        self,
        organization_id: str,
        application_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> Dict:
        """Get RUM statistics for an application."""

        query = f"""
        SELECT
            countIf(event_type = 'pageview') as page_views,
            countIf(event_type = 'error') as errors,
            uniqExact(session_id) as unique_sessions,
            avg(lcp_ms) as avg_lcp,
            avg(fid_ms) as avg_fid,
            avg(cls_score) as avg_cls,
            quantile(0.75)(lcp_ms) as p75_lcp,
            quantile(0.75)(fid_ms) as p75_fid,
            quantile(0.75)(cls_score) as p75_cls
        FROM rum_events
        WHERE organization_id = '{organization_id}'
            AND application_id = '{application_id}'
            AND timestamp >= '{format_datetime_for_clickhouse(start_time)}'
            AND timestamp <= '{format_datetime_for_clickhouse(end_time)}'
        FORMAT JSON
        """

        result = await self.execute(query)
        data = result.get("data", [{}])[0] if result else {}

        return data


# Singleton instance
clickhouse_service = ClickHouseService()


async def get_clickhouse_service() -> ClickHouseService:
    """Dependency injection for ClickHouse service."""
    return clickhouse_service
