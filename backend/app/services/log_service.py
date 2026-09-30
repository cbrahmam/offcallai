# backend/app/services/log_service.py
"""
Log Service for ingesting, querying, and managing log data.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy import select, func, and_, or_, desc, asc, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.log_entry import LogEntry, LogSource
from app.schemas.log import (
    LogBatch, LogEntryIngest, LogIngestResponse,
    LogQuery, LogQueryResponse, LogEntryResponse,
    LogStats, LogLevelCount, LogSourceCount,
    LogSourceCreate, LogSourceUpdate, LogSourceResponse, LogSourceListResponse,
    LogContext
)
from app.services.host_service import host_service

logger = logging.getLogger(__name__)


class LogService:
    """Service for log management operations."""

    # ============================================
    # Log Ingestion
    # ============================================

    async def ingest_batch(
        self,
        batch: LogBatch,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> LogIngestResponse:
        """Ingest a batch of logs from an agent."""
        errors = []
        logs_received = len(batch.logs)
        logs_stored = 0

        # Look up host by agent_id
        host = await host_service.get_host_by_agent_id(
            batch.agent_id, organization_id, db
        )

        if not host:
            return LogIngestResponse(
                success=False,
                logs_received=logs_received,
                logs_stored=0,
                host_id="",
                errors=[f"Unknown agent_id: {batch.agent_id}. Register the agent first."]
            )

        host_id = host.id

        # Update host's last_seen_at
        await db.execute(
            text("UPDATE hosts SET last_seen_at = NOW() WHERE id = :host_id"),
            {"host_id": host_id}
        )

        # Prepare batch insert
        for log_entry in batch.logs:
            try:
                entry = LogEntry(
                    organization_id=organization_id,
                    host_id=host_id,
                    timestamp=log_entry.timestamp,
                    level=log_entry.level.value if log_entry.level else "info",
                    source=log_entry.source,
                    service=log_entry.service,
                    filename=log_entry.filename,
                    line_number=log_entry.line_number,
                    message=log_entry.message,
                    raw_message=log_entry.raw_message,
                    fields=log_entry.fields or {},
                    tags=log_entry.tags or []
                )
                db.add(entry)
                logs_stored += 1
            except Exception as e:
                errors.append(str(e))

        try:
            await db.commit()
        except Exception as e:
            logger.error(f"Error storing logs: {e}")
            errors.append(f"Database error: {str(e)}")
            await db.rollback()
            logs_stored = 0

        logger.debug(f"Ingested {logs_stored}/{logs_received} logs for host {host_id}")

        return LogIngestResponse(
            success=len(errors) == 0,
            logs_received=logs_received,
            logs_stored=logs_stored,
            host_id=str(host_id),
            errors=errors
        )

    # ============================================
    # Log Queries
    # ============================================

    async def query_logs(
        self,
        query: LogQuery,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> LogQueryResponse:
        """Query logs with filtering and pagination."""
        # Build base query
        stmt = select(LogEntry).where(
            LogEntry.organization_id == organization_id,
            LogEntry.timestamp >= query.start_time,
            LogEntry.timestamp <= query.end_time
        )

        # Apply filters
        if query.levels:
            stmt = stmt.where(LogEntry.level.in_([l.value for l in query.levels]))

        if query.sources:
            stmt = stmt.where(LogEntry.source.in_(query.sources))

        if query.services:
            stmt = stmt.where(LogEntry.service.in_(query.services))

        if query.host_ids:
            stmt = stmt.where(LogEntry.host_id.in_([uuid.UUID(h) for h in query.host_ids]))

        if query.tags:
            # Check if any tag matches
            for tag in query.tags:
                stmt = stmt.where(LogEntry.tags.contains([tag]))

        if query.fields:
            for key, value in query.fields.items():
                stmt = stmt.where(LogEntry.fields[key].astext == value)

        # Full-text search (basic ILIKE - for production, use PostgreSQL FTS)
        if query.query:
            search_term = f"%{query.query}%"
            stmt = stmt.where(
                or_(
                    LogEntry.message.ilike(search_term),
                    LogEntry.source.ilike(search_term),
                    LogEntry.service.ilike(search_term)
                )
            )

        # Count total (before pagination)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await db.execute(count_stmt)
        total = total_result.scalar()

        # Order and paginate
        if query.order == "desc":
            stmt = stmt.order_by(desc(LogEntry.timestamp))
        else:
            stmt = stmt.order_by(asc(LogEntry.timestamp))

        stmt = stmt.offset(query.offset).limit(query.limit)

        # Execute query
        result = await db.execute(stmt)
        entries = result.scalars().all()

        # Get hostnames for the logs
        host_ids = list(set(str(e.host_id) for e in entries))
        hostname_map = await self._get_hostnames(host_ids, db)

        # Build response
        logs = [
            LogEntryResponse(
                id=str(e.id),
                timestamp=e.timestamp,
                level=e.level,
                source=e.source,
                service=e.service,
                filename=e.filename,
                line_number=e.line_number,
                message=e.message,
                fields=e.fields or {},
                tags=e.tags or [],
                host_id=str(e.host_id),
                hostname=hostname_map.get(str(e.host_id))
            )
            for e in entries
        ]

        return LogQueryResponse(
            logs=logs,
            total=total,
            query=query,
            has_more=(query.offset + len(logs)) < total
        )

    async def get_log_context(
        self,
        log_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession,
        context_lines: int = 10
    ) -> Optional[LogContext]:
        """Get a log entry with surrounding context."""
        # Get the target log
        result = await db.execute(
            select(LogEntry).where(
                LogEntry.id == log_id,
                LogEntry.organization_id == organization_id
            )
        )
        current = result.scalar_one_or_none()
        if not current:
            return None

        # Get logs before
        before_result = await db.execute(
            select(LogEntry)
            .where(
                LogEntry.organization_id == organization_id,
                LogEntry.host_id == current.host_id,
                LogEntry.timestamp < current.timestamp
            )
            .order_by(desc(LogEntry.timestamp))
            .limit(context_lines)
        )
        before_entries = list(reversed(before_result.scalars().all()))

        # Get logs after
        after_result = await db.execute(
            select(LogEntry)
            .where(
                LogEntry.organization_id == organization_id,
                LogEntry.host_id == current.host_id,
                LogEntry.timestamp > current.timestamp
            )
            .order_by(asc(LogEntry.timestamp))
            .limit(context_lines)
        )
        after_entries = list(after_result.scalars().all())

        # Get hostname
        hostname_map = await self._get_hostnames([str(current.host_id)], db)

        def entry_to_response(e):
            return LogEntryResponse(
                id=str(e.id),
                timestamp=e.timestamp,
                level=e.level,
                source=e.source,
                service=e.service,
                filename=e.filename,
                line_number=e.line_number,
                message=e.message,
                fields=e.fields or {},
                tags=e.tags or [],
                host_id=str(e.host_id),
                hostname=hostname_map.get(str(e.host_id))
            )

        return LogContext(
            before=[entry_to_response(e) for e in before_entries],
            current=entry_to_response(current),
            after=[entry_to_response(e) for e in after_entries]
        )

    # ============================================
    # Log Statistics
    # ============================================

    async def get_log_stats(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession,
        hours: int = 24
    ) -> LogStats:
        """Get log statistics for the organization."""
        since = datetime.utcnow() - timedelta(hours=hours)

        # Total count
        total_result = await db.execute(
            select(func.count(LogEntry.id))
            .where(
                LogEntry.organization_id == organization_id,
                LogEntry.timestamp >= since
            )
        )
        total_logs = total_result.scalar() or 0

        # By level
        level_result = await db.execute(
            select(LogEntry.level, func.count(LogEntry.id))
            .where(
                LogEntry.organization_id == organization_id,
                LogEntry.timestamp >= since
            )
            .group_by(LogEntry.level)
        )
        by_level = [
            LogLevelCount(level=row[0], count=row[1])
            for row in level_result.fetchall()
        ]

        # By source
        source_result = await db.execute(
            select(LogEntry.source, func.count(LogEntry.id))
            .where(
                LogEntry.organization_id == organization_id,
                LogEntry.timestamp >= since,
                LogEntry.source.isnot(None)
            )
            .group_by(LogEntry.source)
            .order_by(desc(func.count(LogEntry.id)))
            .limit(10)
        )
        by_source = [
            LogSourceCount(source=row[0], count=row[1])
            for row in source_result.fetchall()
        ]

        # Logs per hour (histogram)
        histogram_result = await db.execute(
            text("""
                SELECT
                    date_trunc('hour', timestamp) as hour,
                    count(*) as count
                FROM log_entries
                WHERE organization_id = :org_id
                  AND timestamp >= :since
                GROUP BY date_trunc('hour', timestamp)
                ORDER BY hour
            """),
            {"org_id": organization_id, "since": since}
        )
        logs_per_hour = [
            {"hour": row[0].isoformat(), "count": row[1]}
            for row in histogram_result.fetchall()
        ]

        return LogStats(
            total_logs=total_logs,
            time_range_hours=hours,
            by_level=by_level,
            by_source=by_source,
            logs_per_hour=logs_per_hour
        )

    # ============================================
    # Log Source Management
    # ============================================

    async def create_log_source(
        self,
        data: LogSourceCreate,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> LogSource:
        """Create a new log source configuration."""
        source = LogSource(
            organization_id=organization_id,
            host_id=uuid.UUID(data.host_id) if data.host_id else None,
            name=data.name,
            type=data.type.value,
            path=data.path,
            multiline_pattern=data.multiline_pattern,
            include_patterns=data.include_patterns or [],
            exclude_patterns=data.exclude_patterns or [],
            parser=data.parser,
            parser_config=data.parser_config or {},
            tags=data.tags or [],
            is_active="active"
        )

        db.add(source)
        await db.commit()
        await db.refresh(source)

        logger.info(f"Created log source: {source.name} (id={source.id})")
        return source

    async def list_log_sources(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession,
        host_id: Optional[str] = None
    ) -> LogSourceListResponse:
        """List log sources for the organization."""
        stmt = select(LogSource).where(LogSource.organization_id == organization_id)

        if host_id:
            stmt = stmt.where(
                or_(
                    LogSource.host_id == uuid.UUID(host_id),
                    LogSource.host_id.is_(None)  # Global sources
                )
            )

        result = await db.execute(stmt.order_by(LogSource.created_at.desc()))
        sources = result.scalars().all()

        return LogSourceListResponse(
            sources=[self._source_to_response(s) for s in sources],
            total=len(sources)
        )

    async def update_log_source(
        self,
        source_id: uuid.UUID,
        organization_id: uuid.UUID,
        data: LogSourceUpdate,
        db: AsyncSession
    ) -> Optional[LogSource]:
        """Update a log source configuration."""
        result = await db.execute(
            select(LogSource).where(
                LogSource.id == source_id,
                LogSource.organization_id == organization_id
            )
        )
        source = result.scalar_one_or_none()
        if not source:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(source, field):
                setattr(source, field, value)

        source.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(source)

        return source

    async def delete_log_source(
        self,
        source_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> bool:
        """Delete a log source configuration."""
        result = await db.execute(
            select(LogSource).where(
                LogSource.id == source_id,
                LogSource.organization_id == organization_id
            )
        )
        source = result.scalar_one_or_none()
        if not source:
            return False

        await db.delete(source)
        await db.commit()
        return True

    # ============================================
    # Cleanup
    # ============================================

    async def cleanup_old_logs(
        self,
        db: AsyncSession,
        days_to_keep: int = 7
    ) -> int:
        """Delete logs older than specified days."""
        cutoff = datetime.utcnow() - timedelta(days=days_to_keep)

        try:
            result = await db.execute(
                text("DELETE FROM log_entries WHERE timestamp < :cutoff"),
                {"cutoff": cutoff}
            )
            await db.commit()
            count = result.rowcount
            if count > 0:
                logger.info(f"Cleaned up {count} old log entries")
            return count
        except Exception as e:
            logger.error(f"Error cleaning up logs: {e}")
            await db.rollback()
            return 0

    # ============================================
    # Helpers
    # ============================================

    async def _get_hostnames(
        self,
        host_ids: List[str],
        db: AsyncSession
    ) -> Dict[str, str]:
        """Get hostname mapping for a list of host IDs."""
        if not host_ids:
            return {}

        result = await db.execute(
            text("SELECT id, hostname FROM hosts WHERE id = ANY(:ids)"),
            {"ids": [uuid.UUID(h) for h in host_ids]}
        )
        rows = result.fetchall()
        return {str(row[0]): row[1] for row in rows}

    def _source_to_response(self, source: LogSource) -> LogSourceResponse:
        """Convert LogSource model to response schema."""
        return LogSourceResponse(
            id=str(source.id),
            name=source.name,
            type=source.type,
            host_id=str(source.host_id) if source.host_id else None,
            path=source.path,
            multiline_pattern=source.multiline_pattern,
            include_patterns=source.include_patterns or [],
            exclude_patterns=source.exclude_patterns or [],
            parser=source.parser,
            parser_config=source.parser_config or {},
            tags=source.tags or [],
            is_active=source.is_active,
            last_collected_at=source.last_collected_at,
            error_message=source.error_message,
            created_at=source.created_at,
            updated_at=source.updated_at
        )


# Singleton instance
log_service = LogService()
