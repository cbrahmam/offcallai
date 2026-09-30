# backend/app/services/trace_service.py
"""
APM Trace Service for distributed tracing and service metrics.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

from sqlalchemy import select, func, and_, or_, desc, asc, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trace import Trace, Span, ServiceMetrics
from app.schemas.trace import (
    SpanBatch, SpanIngest, SpanIngestResponse,
    TraceQuery, TraceResponse, TraceSummary, TraceListResponse,
    SpanResponse, ServiceSummary, ServiceListResponse,
    ServiceMap, ServiceNode, ServiceEdge, ServiceOperations, OperationMetrics,
    HealthStatus
)
from app.services.host_service import host_service

logger = logging.getLogger(__name__)


class TraceService:
    """Service for APM trace operations."""

    # ============================================
    # Span Ingestion
    # ============================================

    async def ingest_spans(
        self,
        batch: SpanBatch,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> SpanIngestResponse:
        """Ingest a batch of spans from an agent."""
        errors = []
        spans_received = len(batch.spans)
        spans_stored = 0
        trace_ids_affected = set()

        # Look up host by agent_id
        host = await host_service.get_host_by_agent_id(
            batch.agent_id, organization_id, db
        )

        host_id = host.id if host else None

        # Group spans by trace_id
        spans_by_trace: Dict[str, List[SpanIngest]] = defaultdict(list)
        for span in batch.spans:
            spans_by_trace[span.trace_id].append(span)

        # Process each trace's spans
        for trace_id, spans in spans_by_trace.items():
            try:
                # Store spans
                for span_data in spans:
                    duration_ms = span_data.duration_ms
                    if not duration_ms and span_data.end_time and span_data.start_time:
                        duration_ms = (span_data.end_time - span_data.start_time).total_seconds() * 1000

                    span = Span(
                        trace_id=trace_id,
                        span_id=span_data.span_id,
                        parent_span_id=span_data.parent_span_id,
                        organization_id=organization_id,
                        service_name=span_data.service_name,
                        operation_name=span_data.operation_name,
                        span_kind=span_data.span_kind.value,
                        start_time=span_data.start_time,
                        end_time=span_data.end_time,
                        duration_ms=duration_ms,
                        status=span_data.status.value,
                        status_message=span_data.status_message,
                        resource_attributes=span_data.resource_attributes or {},
                        attributes=span_data.attributes or {},
                        events=[e.model_dump() for e in (span_data.events or [])],
                        links=[l.model_dump() for l in (span_data.links or [])],
                        host_id=host_id
                    )
                    db.add(span)
                    spans_stored += 1

                trace_ids_affected.add(trace_id)

            except Exception as e:
                errors.append(f"Error processing trace {trace_id}: {str(e)}")

        try:
            await db.commit()

            # Update trace records
            for trace_id in trace_ids_affected:
                await self._update_trace_record(trace_id, organization_id, db)

        except Exception as e:
            logger.error(f"Error storing spans: {e}")
            errors.append(f"Database error: {str(e)}")
            await db.rollback()
            spans_stored = 0

        logger.debug(f"Ingested {spans_stored}/{spans_received} spans for {len(trace_ids_affected)} traces")

        return SpanIngestResponse(
            success=len(errors) == 0,
            spans_received=spans_received,
            spans_stored=spans_stored,
            traces_updated=len(trace_ids_affected),
            host_id=str(host_id) if host_id else "",
            errors=errors
        )

    async def _update_trace_record(
        self,
        trace_id: str,
        organization_id: uuid.UUID,
        db: AsyncSession
    ):
        """Update or create trace record from its spans."""
        # Get all spans for this trace
        result = await db.execute(
            select(Span).where(
                Span.trace_id == trace_id,
                Span.organization_id == organization_id
            ).order_by(Span.start_time)
        )
        spans = result.scalars().all()

        if not spans:
            return

        # Find root span (no parent)
        root_span = next((s for s in spans if not s.parent_span_id), spans[0])

        # Calculate aggregates
        services = list(set(s.service_name for s in spans))
        error_count = sum(1 for s in spans if s.status == "error")
        start_time = min(s.start_time for s in spans)
        end_times = [s.end_time for s in spans if s.end_time]
        end_time = max(end_times) if end_times else None
        duration_ms = (end_time - start_time).total_seconds() * 1000 if end_time else None

        # Check if trace exists
        result = await db.execute(
            select(Trace).where(
                Trace.trace_id == trace_id,
                Trace.organization_id == organization_id
            )
        )
        trace = result.scalar_one_or_none()

        if trace:
            # Update existing
            trace.root_service = root_span.service_name
            trace.root_operation = root_span.operation_name
            trace.start_time = start_time
            trace.end_time = end_time
            trace.duration_ms = duration_ms
            trace.span_count = len(spans)
            trace.service_count = len(services)
            trace.error_count = error_count
            trace.has_error = "true" if error_count > 0 else "false"
            trace.services = services
        else:
            # Create new
            trace = Trace(
                trace_id=trace_id,
                organization_id=organization_id,
                root_service=root_span.service_name,
                root_operation=root_span.operation_name,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                span_count=len(spans),
                service_count=len(services),
                error_count=error_count,
                has_error="true" if error_count > 0 else "false",
                services=services
            )
            db.add(trace)

        await db.commit()

    # ============================================
    # Trace Queries
    # ============================================

    async def query_traces(
        self,
        query: TraceQuery,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> TraceListResponse:
        """Query traces with filtering."""
        stmt = select(Trace).where(
            Trace.organization_id == organization_id,
            Trace.start_time >= query.start_time,
            Trace.start_time <= query.end_time
        )

        if query.service:
            stmt = stmt.where(Trace.services.contains([query.service]))

        if query.operation:
            stmt = stmt.where(Trace.root_operation.ilike(f"%{query.operation}%"))

        if query.min_duration_ms:
            stmt = stmt.where(Trace.duration_ms >= query.min_duration_ms)

        if query.max_duration_ms:
            stmt = stmt.where(Trace.duration_ms <= query.max_duration_ms)

        if query.has_error is not None:
            stmt = stmt.where(Trace.has_error == ("true" if query.has_error else "false"))

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await db.execute(count_stmt)
        total = total_result.scalar()

        # Order and paginate
        stmt = stmt.order_by(desc(Trace.start_time))
        stmt = stmt.offset(query.offset).limit(query.limit)

        result = await db.execute(stmt)
        traces = result.scalars().all()

        return TraceListResponse(
            traces=[
                TraceSummary(
                    id=str(t.id),
                    trace_id=t.trace_id,
                    root_service=t.root_service,
                    root_operation=t.root_operation,
                    start_time=t.start_time,
                    duration_ms=t.duration_ms,
                    span_count=t.span_count,
                    error_count=t.error_count,
                    has_error=t.has_error == "true",
                    services=t.services or []
                )
                for t in traces
            ],
            total=total,
            query=query,
            has_more=(query.offset + len(traces)) < total
        )

    async def get_trace(
        self,
        trace_id: str,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[TraceResponse]:
        """Get a full trace with all spans."""
        # Get trace record
        result = await db.execute(
            select(Trace).where(
                Trace.trace_id == trace_id,
                Trace.organization_id == organization_id
            )
        )
        trace = result.scalar_one_or_none()

        if not trace:
            return None

        # Get all spans
        spans_result = await db.execute(
            select(Span).where(
                Span.trace_id == trace_id,
                Span.organization_id == organization_id
            ).order_by(Span.start_time)
        )
        spans = spans_result.scalars().all()

        return TraceResponse(
            id=str(trace.id),
            trace_id=trace.trace_id,
            root_service=trace.root_service,
            root_operation=trace.root_operation,
            start_time=trace.start_time,
            end_time=trace.end_time,
            duration_ms=trace.duration_ms,
            span_count=trace.span_count,
            service_count=trace.service_count,
            error_count=trace.error_count,
            has_error=trace.has_error == "true",
            services=trace.services or [],
            spans=[
                SpanResponse(
                    id=str(s.id),
                    trace_id=s.trace_id,
                    span_id=s.span_id,
                    parent_span_id=s.parent_span_id,
                    service_name=s.service_name,
                    operation_name=s.operation_name,
                    span_kind=s.span_kind,
                    start_time=s.start_time,
                    end_time=s.end_time,
                    duration_ms=s.duration_ms,
                    status=s.status,
                    status_message=s.status_message,
                    resource_attributes=s.resource_attributes or {},
                    attributes=s.attributes or {},
                    events=s.events or [],
                    links=s.links or []
                )
                for s in spans
            ],
            tags=trace.tags or {}
        )

    # ============================================
    # Service Metrics
    # ============================================

    async def get_services(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession,
        hours: int = 24
    ) -> ServiceListResponse:
        """Get list of services with metrics."""
        since = datetime.utcnow() - timedelta(hours=hours)

        result = await db.execute(
            text("""
                SELECT
                    service_name,
                    COUNT(*) as request_count,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_count,
                    AVG(duration_ms) as latency_avg,
                    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY duration_ms) as latency_p50,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as latency_p95,
                    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_ms) as latency_p99
                FROM spans
                WHERE organization_id = :org_id
                  AND start_time >= :since
                  AND span_kind = 'server'
                GROUP BY service_name
                ORDER BY request_count DESC
            """),
            {"org_id": organization_id, "since": since}
        )
        rows = result.fetchall()

        services = []
        for row in rows:
            error_rate = (row[2] / row[1] * 100) if row[1] > 0 else 0
            rps = row[1] / (hours * 3600) if hours > 0 else 0

            services.append(ServiceSummary(
                service_name=row[0],
                request_count=row[1],
                error_count=row[2],
                error_rate=round(error_rate, 2),
                latency_avg=round(row[3] or 0, 2),
                latency_p50=round(row[4] or 0, 2),
                latency_p95=round(row[5] or 0, 2),
                latency_p99=round(row[6] or 0, 2),
                requests_per_second=round(rps, 2),
                upstream_services=[],
                downstream_services=[]
            ))

        return ServiceListResponse(
            services=services,
            time_range_hours=hours
        )

    async def get_service_operations(
        self,
        service_name: str,
        organization_id: uuid.UUID,
        db: AsyncSession,
        hours: int = 24
    ) -> ServiceOperations:
        """Get operations for a specific service."""
        since = datetime.utcnow() - timedelta(hours=hours)

        result = await db.execute(
            text("""
                SELECT
                    operation_name,
                    COUNT(*) as request_count,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_count,
                    AVG(duration_ms) as latency_avg,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as latency_p95
                FROM spans
                WHERE organization_id = :org_id
                  AND service_name = :service
                  AND start_time >= :since
                GROUP BY operation_name
                ORDER BY request_count DESC
            """),
            {"org_id": organization_id, "service": service_name, "since": since}
        )
        rows = result.fetchall()

        operations = []
        for row in rows:
            error_rate = (row[2] / row[1] * 100) if row[1] > 0 else 0
            operations.append(OperationMetrics(
                operation_name=row[0],
                request_count=row[1],
                error_count=row[2],
                error_rate=round(error_rate, 2),
                latency_avg=round(row[3] or 0, 2),
                latency_p95=round(row[4] or 0, 2)
            ))

        return ServiceOperations(
            service_name=service_name,
            operations=operations
        )

    def _calculate_health_status(self, error_rate: float, latency_p95: float) -> HealthStatus:
        """
        Calculate service health status based on error rate and latency.

        - HEALTHY (green): error_rate < 1% AND latency_p95 < 500ms
        - DEGRADED (yellow): error_rate < 5% AND latency_p95 < 1000ms
        - CRITICAL (red): error_rate >= 5% OR latency_p95 >= 1000ms
        """
        if error_rate >= 5.0 or latency_p95 >= 1000:
            return HealthStatus.CRITICAL
        elif error_rate >= 1.0 or latency_p95 >= 500:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    async def get_service_map(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession,
        hours: int = 24
    ) -> ServiceMap:
        """Generate service dependency map from traces with health status."""
        since = datetime.utcnow() - timedelta(hours=hours)

        # Get service nodes with latency percentiles for health calculation
        nodes_result = await db.execute(
            text("""
                SELECT
                    service_name,
                    COUNT(*) as request_count,
                    AVG(CASE WHEN status = 'error' THEN 1.0 ELSE 0.0 END) * 100 as error_rate,
                    AVG(duration_ms) as latency_avg,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as latency_p95
                FROM spans
                WHERE organization_id = :org_id
                  AND start_time >= :since
                GROUP BY service_name
            """),
            {"org_id": organization_id, "since": since}
        )

        nodes = []
        for row in nodes_result.fetchall():
            error_rate = round(row[2] or 0, 2)
            latency_p95 = round(row[4] or 0, 2)
            health_status = self._calculate_health_status(error_rate, latency_p95)

            nodes.append(ServiceNode(
                service_name=row[0],
                request_count=row[1],
                error_rate=error_rate,
                latency_avg=round(row[3] or 0, 2),
                latency_p95=latency_p95,
                health_status=health_status
            ))

        # Get service edges (dependencies)
        edges_result = await db.execute(
            text("""
                SELECT
                    parent.service_name as source,
                    child.service_name as target,
                    COUNT(*) as request_count,
                    AVG(CASE WHEN child.status = 'error' THEN 1.0 ELSE 0.0 END) * 100 as error_rate,
                    AVG(child.duration_ms) as latency_avg
                FROM spans child
                JOIN spans parent ON parent.span_id = child.parent_span_id
                    AND parent.trace_id = child.trace_id
                    AND parent.organization_id = child.organization_id
                WHERE child.organization_id = :org_id
                  AND child.start_time >= :since
                  AND parent.service_name != child.service_name
                GROUP BY parent.service_name, child.service_name
            """),
            {"org_id": organization_id, "since": since}
        )
        edges = [
            ServiceEdge(
                source=row[0],
                target=row[1],
                request_count=row[2],
                error_rate=round(row[3] or 0, 2),
                latency_avg=round(row[4] or 0, 2)
            )
            for row in edges_result.fetchall()
        ]

        return ServiceMap(nodes=nodes, edges=edges, time_range_hours=hours)

    # ============================================
    # Single Span Query
    # ============================================

    async def get_span(
        self,
        span_id: str,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[SpanResponse]:
        """Get a single span by span_id."""
        result = await db.execute(
            select(Span).where(
                Span.span_id == span_id,
                Span.organization_id == organization_id
            )
        )
        span = result.scalar_one_or_none()

        if not span:
            return None

        return SpanResponse(
            id=str(span.id),
            trace_id=span.trace_id,
            span_id=span.span_id,
            parent_span_id=span.parent_span_id,
            service_name=span.service_name,
            operation_name=span.operation_name,
            span_kind=span.span_kind,
            start_time=span.start_time,
            end_time=span.end_time,
            duration_ms=span.duration_ms,
            status=span.status,
            status_message=span.status_message,
            resource_attributes=span.resource_attributes or {},
            attributes=span.attributes or {},
            events=span.events or [],
            links=span.links or []
        )

    # ============================================
    # Cleanup
    # ============================================

    async def cleanup_old_traces(
        self,
        db: AsyncSession,
        days_to_keep: int = 7
    ) -> int:
        """Delete traces and spans older than specified days."""
        cutoff = datetime.utcnow() - timedelta(days=days_to_keep)

        try:
            # Delete spans first
            spans_result = await db.execute(
                text("DELETE FROM spans WHERE start_time < :cutoff"),
                {"cutoff": cutoff}
            )
            spans_deleted = spans_result.rowcount

            # Delete traces
            traces_result = await db.execute(
                text("DELETE FROM traces WHERE start_time < :cutoff"),
                {"cutoff": cutoff}
            )
            traces_deleted = traces_result.rowcount

            await db.commit()

            if spans_deleted > 0 or traces_deleted > 0:
                logger.info(f"Cleaned up {spans_deleted} spans and {traces_deleted} traces")

            return spans_deleted + traces_deleted

        except Exception as e:
            logger.error(f"Error cleaning up traces: {e}")
            await db.rollback()
            return 0


# Singleton instance
trace_service = TraceService()
