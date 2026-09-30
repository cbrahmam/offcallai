# backend/app/services/error_tracking_service.py
"""Service for Error Tracking (Sentry-like functionality)."""
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, update, literal_column
from sqlalchemy.dialects.postgresql import insert

from app.models.error_tracking import ErrorGroup, ErrorEvent, ErrorGroupStatus
from app.models.user import User
from app.schemas.error_tracking import (
    ErrorEventIngest,
    ErrorIngestResponse,
    ErrorGroupSummary,
    ErrorGroupDetail,
    ErrorEventSummary,
    ErrorEventDetail,
    ErrorStats,
    ErrorGroupFrequency,
)


class ErrorTrackingService:
    """Service for error ingestion, grouping, and tracking."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def ingest_error(
        self,
        error: ErrorEventIngest,
        organization_id: UUID
    ) -> ErrorIngestResponse:
        """
        Ingest an error event from an SDK.

        1. Calculate fingerprint for grouping
        2. Find or create error group
        3. Create error event
        4. Update group statistics
        """
        timestamp = error.timestamp or datetime.utcnow()

        # Calculate fingerprint
        fingerprint = self._calculate_fingerprint(error)

        # Find or create error group
        group, is_new = await self._find_or_create_group(
            organization_id=organization_id,
            fingerprint=fingerprint,
            error=error,
            timestamp=timestamp
        )

        # Create error event
        event = ErrorEvent(
            organization_id=organization_id,
            error_group_id=group.id,
            timestamp=timestamp,
            error_type=error.error_type,
            message=error.message,
            stack_trace=error.stack_trace,
            stack_frames=[f.model_dump() for f in error.stack_frames] if error.stack_frames else [],
            service_name=error.service_name,
            environment=error.environment,
            release=error.release,
            user_id=error.user_id,
            user_email=error.user_email,
            user_ip=error.user_ip,
            request_url=error.request_url,
            request_method=error.request_method,
            request_headers=error.request_headers or {},
            runtime=error.runtime,
            runtime_version=error.runtime_version,
            os=error.os,
            os_version=error.os_version,
            browser=error.browser,
            browser_version=error.browser_version,
            device=error.device,
            trace_id=error.trace_id,
            span_id=error.span_id,
            tags=error.tags or {},
            extra_data=error.extra or {},
            breadcrumbs=[b.model_dump() for b in error.breadcrumbs] if error.breadcrumbs else [],
            sdk_name=error.sdk_name,
            sdk_version=error.sdk_version,
        )
        self.db.add(event)

        # Update group statistics
        await self._update_group_stats(group, error, timestamp)

        await self.db.commit()
        await self.db.refresh(event)
        await self.db.refresh(group)

        return ErrorIngestResponse(
            event_id=event.id,
            group_id=group.id,
            is_new_group=is_new,
            group_event_count=group.event_count
        )

    def _calculate_fingerprint(self, error: ErrorEventIngest) -> str:
        """
        Calculate a fingerprint for error grouping.

        The fingerprint is based on:
        - Error type
        - Top stack frame (filename, function, line)
        - Error message (normalized)
        - Service name

        Custom fingerprint from SDK takes precedence if provided.
        """
        if error.fingerprint:
            # Use custom fingerprint from SDK
            fingerprint_data = "|".join(error.fingerprint)
        else:
            # Build automatic fingerprint
            parts = [error.error_type or "UnknownError"]

            # Add top stack frame info if available
            if error.stack_frames and len(error.stack_frames) > 0:
                top_frame = error.stack_frames[0]
                if top_frame.filename:
                    parts.append(top_frame.filename)
                if top_frame.function:
                    parts.append(top_frame.function)
                if top_frame.lineno:
                    parts.append(str(top_frame.lineno))
            elif error.stack_trace:
                # Extract first meaningful line from stack trace
                lines = error.stack_trace.strip().split('\n')
                for line in lines[:3]:
                    if 'at ' in line or 'File ' in line:
                        parts.append(line.strip()[:100])
                        break

            # Add normalized message (remove variable parts)
            if error.message:
                normalized_msg = self._normalize_message(error.message)
                parts.append(normalized_msg[:200])

            # Add service name
            if error.service_name:
                parts.append(error.service_name)

            fingerprint_data = "|".join(parts)

        # Hash to create fixed-length fingerprint
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()

    def _normalize_message(self, message: str) -> str:
        """
        Normalize error message for fingerprinting.

        Removes variable parts like:
        - IDs, UUIDs
        - Numbers
        - Timestamps
        - Memory addresses
        """
        import re

        normalized = message

        # Replace UUIDs
        normalized = re.sub(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '<UUID>',
            normalized,
            flags=re.IGNORECASE
        )

        # Replace hex addresses
        normalized = re.sub(r'0x[0-9a-f]+', '<ADDR>', normalized, flags=re.IGNORECASE)

        # Replace numbers (but keep error codes like E404)
        normalized = re.sub(r'(?<![A-Z])\b\d+\b', '<N>', normalized)

        # Replace quoted strings
        normalized = re.sub(r'"[^"]*"', '"<STR>"', normalized)
        normalized = re.sub(r"'[^']*'", "'<STR>'", normalized)

        return normalized

    async def _find_or_create_group(
        self,
        organization_id: UUID,
        fingerprint: str,
        error: ErrorEventIngest,
        timestamp: datetime
    ) -> Tuple[ErrorGroup, bool]:
        """Find existing error group or create new one."""
        # Try to find existing group
        query = select(ErrorGroup).where(
            ErrorGroup.organization_id == organization_id,
            ErrorGroup.fingerprint == fingerprint
        )
        result = await self.db.execute(query)
        group = result.scalar_one_or_none()

        if group:
            return group, False

        # Create new group
        title = self._generate_title(error)

        # Extract location from stack frames
        filename = None
        function_name = None
        line_number = None
        column_number = None

        if error.stack_frames and len(error.stack_frames) > 0:
            top_frame = error.stack_frames[0]
            filename = top_frame.filename
            function_name = top_frame.function
            line_number = top_frame.lineno
            column_number = top_frame.colno

        group = ErrorGroup(
            organization_id=organization_id,
            fingerprint=fingerprint,
            title=title,
            error_type=error.error_type,
            message=error.message,
            service_name=error.service_name,
            filename=filename,
            function_name=function_name,
            line_number=line_number,
            column_number=column_number,
            status=ErrorGroupStatus.UNRESOLVED.value,
            event_count=0,
            user_count=0,
            first_seen_at=timestamp,
            last_seen_at=timestamp,
            first_release=error.release,
            last_release=error.release,
            environments=[error.environment] if error.environment else [],
            tags=error.tags or {},
        )
        self.db.add(group)
        await self.db.flush()

        return group, True

    def _generate_title(self, error: ErrorEventIngest) -> str:
        """Generate a human-readable title for the error group."""
        parts = []

        if error.error_type:
            parts.append(error.error_type)

        if error.message:
            # Truncate and clean message for title
            msg = error.message[:200]
            if len(error.message) > 200:
                msg += "..."
            parts.append(msg)
        elif error.stack_frames and len(error.stack_frames) > 0:
            frame = error.stack_frames[0]
            if frame.function:
                parts.append(f"in {frame.function}")
            if frame.filename:
                parts.append(f"at {frame.filename}")

        return ": ".join(parts) if parts else "Unknown Error"

    async def _update_group_stats(
        self,
        group: ErrorGroup,
        error: ErrorEventIngest,
        timestamp: datetime
    ):
        """Update error group statistics."""
        group.event_count += 1
        group.last_seen_at = timestamp

        if error.release and error.release != group.last_release:
            group.last_release = error.release

        # Update environments
        if error.environment and (
            not group.environments or error.environment not in group.environments
        ):
            current_envs = group.environments or []
            if error.environment not in current_envs:
                group.environments = current_envs + [error.environment]

        # Track unique users
        if error.user_id:
            # Get distinct user count (simplified - in production use HyperLogLog)
            user_query = select(func.count(func.distinct(ErrorEvent.user_id))).where(
                ErrorEvent.error_group_id == group.id,
                ErrorEvent.user_id.isnot(None)
            )
            result = await self.db.execute(user_query)
            group.user_count = result.scalar() or 0

        # Re-open if was resolved and new error came in (regression)
        if group.status == ErrorGroupStatus.RESOLVED.value:
            group.status = ErrorGroupStatus.UNRESOLVED.value
            group.resolved_at = None
            group.is_regression = True

    async def list_error_groups(
        self,
        organization_id: UUID,
        status: Optional[str] = None,
        service_name: Optional[str] = None,
        environment: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "last_seen_at",
        sort_order: str = "desc",
        period: Optional[str] = None,
        include_sparkline: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[ErrorGroupSummary], int]:
        """List error groups with filtering and pagination."""
        query = select(ErrorGroup).outerjoin(
            User, ErrorGroup.assigned_to_id == User.id
        ).where(
            ErrorGroup.organization_id == organization_id
        )

        # Apply filters
        if status:
            query = query.where(ErrorGroup.status == status)
        if service_name:
            query = query.where(ErrorGroup.service_name == service_name)
        if environment:
            query = query.where(ErrorGroup.environments.contains([environment]))
        if search:
            query = query.where(
                or_(
                    ErrorGroup.title.ilike(f"%{search}%"),
                    ErrorGroup.error_type.ilike(f"%{search}%"),
                    ErrorGroup.message.ilike(f"%{search}%")
                )
            )

        # Time range filter
        if period:
            period_map = {"1h": 1/24, "24h": 1, "7d": 7, "14d": 14, "30d": 30}
            days = period_map.get(period)
            if days:
                cutoff = datetime.utcnow() - timedelta(days=days)
                query = query.where(ErrorGroup.last_seen_at >= cutoff)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Apply sorting
        sort_column = getattr(ErrorGroup, sort_by, ErrorGroup.last_seen_at)
        if sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(sort_column)

        # Apply pagination
        query = query.offset(offset).limit(limit)

        # Add User columns to result
        query = query.add_columns(User.full_name)

        result = await self.db.execute(query)
        rows = result.all()

        summaries = []
        group_ids = []
        for row in rows:
            g = row[0]
            assigned_name = row[1] if len(row) > 1 else None
            group_ids.append(g.id)
            summaries.append(
                ErrorGroupSummary(
                    id=g.id,
                    title=g.title,
                    error_type=g.error_type,
                    service_name=g.service_name,
                    status=g.status,
                    is_regression=g.is_regression or False,
                    event_count=g.event_count,
                    user_count=g.user_count,
                    first_seen_at=g.first_seen_at,
                    last_seen_at=g.last_seen_at,
                    last_release=g.last_release,
                    environments=g.environments,
                    assigned_to_name=assigned_name,
                )
            )

        # Batch sparkline data if requested
        if include_sparkline and group_ids:
            sparkline_map = await self._batch_sparkline(organization_id, group_ids)
            for s in summaries:
                s.sparkline_data = sparkline_map.get(s.id, [])

        return summaries, total

    async def _batch_sparkline(
        self,
        organization_id: UUID,
        group_ids: List[UUID],
        days: int = 14
    ) -> Dict[UUID, List[int]]:
        """Get 14-day daily event counts for a batch of groups."""
        since = datetime.utcnow() - timedelta(days=days)

        day_trunc = func.date_trunc(literal_column("'day'"), ErrorEvent.timestamp)
        query = select(
            ErrorEvent.error_group_id,
            day_trunc.label('day'),
            func.count(ErrorEvent.id).label('count')
        ).where(
            ErrorEvent.organization_id == organization_id,
            ErrorEvent.error_group_id.in_(group_ids),
            ErrorEvent.timestamp >= since
        ).group_by(
            ErrorEvent.error_group_id,
            day_trunc
        )

        result = await self.db.execute(query)
        rows = result.all()

        # Build day index
        day_list = [(since + timedelta(days=i)).date() for i in range(days)]

        # Initialize per-group
        sparkline_map: Dict[UUID, Dict] = {}
        for gid in group_ids:
            sparkline_map[gid] = {d: 0 for d in day_list}

        for row in rows:
            gid = row[0]
            day = row[1].date() if hasattr(row[1], 'date') else row[1]
            count = row[2]
            if gid in sparkline_map and day in sparkline_map[gid]:
                sparkline_map[gid][day] = count

        return {
            gid: [sparkline_map[gid][d] for d in day_list]
            for gid in group_ids
        }

    async def get_error_group(
        self,
        group_id: UUID,
        organization_id: UUID
    ) -> Optional[ErrorGroupDetail]:
        """Get error group details."""
        query = select(ErrorGroup).where(
            ErrorGroup.id == group_id,
            ErrorGroup.organization_id == organization_id
        )
        result = await self.db.execute(query)
        group = result.scalar_one_or_none()

        if not group:
            return None

        # Get assigned user name if assigned
        assigned_to_name = None
        if group.assigned_to:
            assigned_to_name = group.assigned_to.full_name

        return ErrorGroupDetail(
            id=group.id,
            title=group.title,
            error_type=group.error_type,
            message=group.message,
            service_name=group.service_name,
            filename=group.filename,
            function_name=group.function_name,
            line_number=group.line_number,
            column_number=group.column_number,
            status=group.status,
            is_regression=group.is_regression or False,
            assigned_to_id=group.assigned_to_id,
            assigned_to_name=assigned_to_name,
            event_count=group.event_count,
            user_count=group.user_count,
            first_seen_at=group.first_seen_at,
            last_seen_at=group.last_seen_at,
            resolved_at=group.resolved_at,
            first_release=group.first_release,
            last_release=group.last_release,
            environments=group.environments,
            tags=group.tags,
            fingerprint=group.fingerprint,
            created_at=group.created_at,
            updated_at=group.updated_at
        )

    async def update_error_group(
        self,
        group_id: UUID,
        organization_id: UUID,
        status: Optional[str] = None,
        assigned_to_id: Optional[UUID] = None
    ) -> Optional[ErrorGroupDetail]:
        """Update error group status or assignment."""
        query = select(ErrorGroup).where(
            ErrorGroup.id == group_id,
            ErrorGroup.organization_id == organization_id
        )
        result = await self.db.execute(query)
        group = result.scalar_one_or_none()

        if not group:
            return None

        if status:
            group.status = status
            if status == ErrorGroupStatus.RESOLVED.value:
                group.resolved_at = datetime.utcnow()
            else:
                group.resolved_at = None

        if assigned_to_id is not None:
            group.assigned_to_id = assigned_to_id if assigned_to_id else None

        await self.db.commit()
        await self.db.refresh(group)

        return await self.get_error_group(group_id, organization_id)

    async def list_error_events(
        self,
        group_id: UUID,
        organization_id: UUID,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[ErrorEventSummary], int]:
        """List error events for a group."""
        query = select(ErrorEvent).where(
            ErrorEvent.error_group_id == group_id,
            ErrorEvent.organization_id == organization_id
        ).order_by(desc(ErrorEvent.timestamp))

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Apply pagination
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        events = result.scalars().all()

        return [
            ErrorEventSummary(
                id=e.id,
                timestamp=e.timestamp,
                error_type=e.error_type,
                message=e.message[:200] if e.message else None,
                service_name=e.service_name,
                environment=e.environment,
                release=e.release,
                user_id=e.user_id,
                browser=e.browser,
                os=e.os
            )
            for e in events
        ], total

    async def get_error_event(
        self,
        event_id: UUID,
        organization_id: UUID
    ) -> Optional[ErrorEventDetail]:
        """Get error event details."""
        query = select(ErrorEvent).where(
            ErrorEvent.id == event_id,
            ErrorEvent.organization_id == organization_id
        )
        result = await self.db.execute(query)
        event = result.scalar_one_or_none()

        if not event:
            return None

        return ErrorEventDetail(
            id=event.id,
            error_group_id=event.error_group_id,
            timestamp=event.timestamp,
            error_type=event.error_type,
            message=event.message,
            stack_trace=event.stack_trace,
            stack_frames=event.stack_frames,
            service_name=event.service_name,
            environment=event.environment,
            release=event.release,
            user_id=event.user_id,
            user_email=event.user_email,
            user_ip=event.user_ip,
            request_url=event.request_url,
            request_method=event.request_method,
            request_headers=event.request_headers,
            runtime=event.runtime,
            runtime_version=event.runtime_version,
            os=event.os,
            os_version=event.os_version,
            browser=event.browser,
            browser_version=event.browser_version,
            device=event.device,
            trace_id=event.trace_id,
            span_id=event.span_id,
            tags=event.tags,
            extra_data=event.extra_data,
            breadcrumbs=event.breadcrumbs,
            sdk_name=event.sdk_name,
            sdk_version=event.sdk_version,
            created_at=event.created_at
        )

    async def get_error_stats(
        self,
        organization_id: UUID,
        days: int = 7
    ) -> ErrorStats:
        """Get error statistics for the organization."""
        since = datetime.utcnow() - timedelta(days=days)

        # Total events
        event_count_query = select(func.count(ErrorEvent.id)).where(
            ErrorEvent.organization_id == organization_id,
            ErrorEvent.timestamp >= since
        )
        event_result = await self.db.execute(event_count_query)
        total_events = event_result.scalar() or 0

        # Total groups
        group_count_query = select(func.count(ErrorGroup.id)).where(
            ErrorGroup.organization_id == organization_id
        )
        group_result = await self.db.execute(group_count_query)
        total_groups = group_result.scalar() or 0

        # Unresolved groups
        unresolved_query = select(func.count(ErrorGroup.id)).where(
            ErrorGroup.organization_id == organization_id,
            ErrorGroup.status == ErrorGroupStatus.UNRESOLVED.value
        )
        unresolved_result = await self.db.execute(unresolved_query)
        unresolved_groups = unresolved_result.scalar() or 0

        # Events by day
        stats_day_trunc = func.date_trunc(literal_column("'day'"), ErrorEvent.timestamp)
        events_by_day_query = select(
            stats_day_trunc.label('date'),
            func.count(ErrorEvent.id).label('count')
        ).where(
            ErrorEvent.organization_id == organization_id,
            ErrorEvent.timestamp >= since
        ).group_by(stats_day_trunc).order_by(stats_day_trunc)

        events_by_day_result = await self.db.execute(events_by_day_query)
        events_by_day = [
            {"date": row.date.isoformat(), "count": row.count}
            for row in events_by_day_result
        ]

        # Top errors
        top_errors_query = select(ErrorGroup).where(
            ErrorGroup.organization_id == organization_id,
            ErrorGroup.status == ErrorGroupStatus.UNRESOLVED.value
        ).order_by(desc(ErrorGroup.event_count)).limit(10)

        top_errors_result = await self.db.execute(top_errors_query)
        top_errors = [
            ErrorGroupSummary(
                id=g.id,
                title=g.title,
                error_type=g.error_type,
                service_name=g.service_name,
                status=g.status,
                event_count=g.event_count,
                user_count=g.user_count,
                first_seen_at=g.first_seen_at,
                last_seen_at=g.last_seen_at,
                last_release=g.last_release,
                environments=g.environments
            )
            for g in top_errors_result.scalars()
        ]

        # Affected users
        affected_users_query = select(func.count(func.distinct(ErrorEvent.user_id))).where(
            ErrorEvent.organization_id == organization_id,
            ErrorEvent.timestamp >= since,
            ErrorEvent.user_id.isnot(None)
        )
        users_result = await self.db.execute(affected_users_query)
        affected_users = users_result.scalar() or 0

        # Affected services
        services_query = select(func.distinct(ErrorEvent.service_name)).where(
            ErrorEvent.organization_id == organization_id,
            ErrorEvent.timestamp >= since,
            ErrorEvent.service_name.isnot(None)
        )
        services_result = await self.db.execute(services_query)
        affected_services = [s[0] for s in services_result if s[0]]

        return ErrorStats(
            total_events=total_events,
            total_groups=total_groups,
            unresolved_groups=unresolved_groups,
            events_by_day=events_by_day,
            top_errors=top_errors,
            affected_users=affected_users,
            affected_services=affected_services
        )

    async def delete_error_group(
        self,
        group_id: UUID,
        organization_id: UUID
    ) -> bool:
        """Delete an error group and all its events."""
        query = select(ErrorGroup).where(
            ErrorGroup.id == group_id,
            ErrorGroup.organization_id == organization_id
        )
        result = await self.db.execute(query)
        group = result.scalar_one_or_none()

        if not group:
            return False

        await self.db.delete(group)
        await self.db.commit()
        return True

    async def get_group_frequency(
        self,
        group_id: UUID,
        organization_id: UUID,
        period: str = "24h"
    ) -> ErrorGroupFrequency:
        """Get bucketed event frequency for a group."""
        # Map period to (timedelta, date_trunc interval)
        # PostgreSQL date_trunc accepts: minute, hour, day, week, month, etc.
        period_config = {
            "1h": (timedelta(hours=1), "minute"),
            "24h": (timedelta(days=1), "hour"),
            "7d": (timedelta(days=7), "hour"),
            "14d": (timedelta(days=14), "day"),
            "30d": (timedelta(days=30), "day"),
        }
        delta, trunc_field = period_config.get(period, period_config["24h"])
        since = datetime.utcnow() - delta

        bucket_trunc = func.date_trunc(literal_column(f"'{trunc_field}'"), ErrorEvent.timestamp)
        query = select(
            bucket_trunc.label('bucket'),
            func.count(ErrorEvent.id).label('count')
        ).where(
            ErrorEvent.error_group_id == group_id,
            ErrorEvent.organization_id == organization_id,
            ErrorEvent.timestamp >= since
        ).group_by(bucket_trunc).order_by(bucket_trunc)

        result = await self.db.execute(query)
        rows = result.all()

        buckets = [
            {"timestamp": row.bucket.isoformat(), "count": row.count}
            for row in rows
        ]

        total = sum(b["count"] for b in buckets)

        return ErrorGroupFrequency(
            buckets=buckets,
            period=period,
            total_events=total
        )

    async def get_environments(
        self,
        organization_id: UUID
    ) -> List[str]:
        """Get distinct environments across all error events."""
        query = select(func.distinct(ErrorEvent.environment)).where(
            ErrorEvent.organization_id == organization_id,
            ErrorEvent.environment.isnot(None)
        )
        result = await self.db.execute(query)
        return [row[0] for row in result if row[0]]

    async def bulk_update_groups(
        self,
        organization_id: UUID,
        group_ids: List[UUID],
        status: str
    ) -> int:
        """Bulk update status of multiple error groups."""
        now = datetime.utcnow()
        values: Dict[str, Any] = {"status": status}

        if status == "resolved":
            values["resolved_at"] = now
        else:
            values["resolved_at"] = None

        if status == "unresolved":
            values["is_regression"] = False

        stmt = (
            update(ErrorGroup)
            .where(
                ErrorGroup.organization_id == organization_id,
                ErrorGroup.id.in_(group_ids)
            )
            .values(**values)
        )

        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount
