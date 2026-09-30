# backend/app/services/database_monitor_service.py
"""
Database monitoring service.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, delete
from sqlalchemy.orm import selectinload

from app.models.database_monitor import (
    DatabaseInstance, DatabaseQuery, DatabaseMetricSnapshot, DatabaseAlert
)
from app.schemas.database_monitor import (
    DatabaseInstanceCreate, DatabaseInstanceUpdate, DatabaseInstanceResponse, DatabaseInstanceListResponse,
    DatabaseSummary, DatabaseQueryResponse, DatabaseQueryListResponse, QueryFilter,
    MetricSnapshotResponse, MetricSnapshotListResponse,
    DatabaseAlertResponse, DatabaseAlertListResponse,
    DatabaseMetricsReport, QueryStatsReport, MetricsIngestResponse,
    DatabaseHealthCheck
)


class DatabaseMonitorService:
    """Service for managing database monitoring."""

    # ============================================
    # Instance Operations
    # ============================================

    async def create_instance(
        self,
        data: DatabaseInstanceCreate,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> DatabaseInstanceResponse:
        """Create a new database instance for monitoring."""
        instance = DatabaseInstance(
            organization_id=organization_id,
            name=data.name,
            display_name=data.display_name or data.name,
            description=data.description,
            database_type=data.database_type.value,
            hostname=data.hostname,
            port=data.port,
            database_name=data.database_name,
            username=data.username,
            replication_role=data.replication_role.value,
            primary_id=data.primary_id,
            host_id=data.host_id,
            tags=data.tags,
            labels=data.labels,
            monitoring_enabled="true" if data.monitoring_enabled else "false",
            collect_query_stats="true" if data.collect_query_stats else "false",
            collect_slow_queries="true" if data.collect_slow_queries else "false",
            slow_query_threshold_ms=data.slow_query_threshold_ms,
            alert_on_connection_threshold=data.alert_on_connection_threshold,
            alert_on_storage_threshold=data.alert_on_storage_threshold,
            alert_on_replication_lag=data.alert_on_replication_lag,
            status="unknown",
            connection_status="disconnected"
        )

        db.add(instance)
        await db.commit()
        await db.refresh(instance)

        return self._instance_to_response(instance)

    async def get_instance(
        self,
        instance_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[DatabaseInstanceResponse]:
        """Get a database instance by ID."""
        result = await db.execute(
            select(DatabaseInstance)
            .where(
                DatabaseInstance.id == instance_id,
                DatabaseInstance.organization_id == organization_id
            )
        )
        instance = result.scalar_one_or_none()
        if instance:
            return self._instance_to_response(instance)
        return None

    async def list_instances(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession,
        database_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> DatabaseInstanceListResponse:
        """List all database instances."""
        query = select(DatabaseInstance).where(
            DatabaseInstance.organization_id == organization_id
        )

        if database_type:
            query = query.where(DatabaseInstance.database_type == database_type)
        if status:
            query = query.where(DatabaseInstance.status == status)

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        # Get data
        result = await db.execute(
            query.order_by(DatabaseInstance.name)
            .offset(offset)
            .limit(limit)
        )
        instances = result.scalars().all()

        return DatabaseInstanceListResponse(
            instances=[self._instance_to_response(i) for i in instances],
            total=total
        )

    async def update_instance(
        self,
        instance_id: uuid.UUID,
        data: DatabaseInstanceUpdate,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[DatabaseInstanceResponse]:
        """Update a database instance."""
        result = await db.execute(
            select(DatabaseInstance)
            .where(
                DatabaseInstance.id == instance_id,
                DatabaseInstance.organization_id == organization_id
            )
        )
        instance = result.scalar_one_or_none()
        if not instance:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key in ['monitoring_enabled', 'collect_query_stats', 'collect_slow_queries']:
                setattr(instance, key, "true" if value else "false")
            elif key == 'replication_role':
                setattr(instance, key, value.value if value else None)
            else:
                setattr(instance, key, value)

        instance.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(instance)

        return self._instance_to_response(instance)

    async def delete_instance(
        self,
        instance_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> bool:
        """Delete a database instance."""
        result = await db.execute(
            select(DatabaseInstance)
            .where(
                DatabaseInstance.id == instance_id,
                DatabaseInstance.organization_id == organization_id
            )
        )
        instance = result.scalar_one_or_none()
        if not instance:
            return False

        await db.delete(instance)
        await db.commit()
        return True

    async def get_summary(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> DatabaseSummary:
        """Get summary statistics for all database instances."""
        # Get all instances
        result = await db.execute(
            select(DatabaseInstance)
            .where(DatabaseInstance.organization_id == organization_id)
        )
        instances = result.scalars().all()

        # Calculate stats
        total = len(instances)
        healthy = sum(1 for i in instances if i.status == "healthy")
        warning = sum(1 for i in instances if i.status == "warning")
        critical = sum(1 for i in instances if i.status == "critical")
        unreachable = sum(1 for i in instances if i.status == "unreachable")

        # By type
        by_type: Dict[str, int] = {}
        for i in instances:
            by_type[i.database_type] = by_type.get(i.database_type, 0) + 1

        # Totals
        total_connections_used = sum(i.connections_used or 0 for i in instances)
        total_connections_max = sum(i.connections_max or 0 for i in instances)
        total_storage_used = sum(i.storage_used_bytes or 0 for i in instances)
        total_storage = sum(i.storage_total_bytes or 0 for i in instances)
        total_slow_queries = sum(i.slow_queries_count or 0 for i in instances)

        # Average cache hit ratio
        cache_ratios = [i.cache_hit_ratio for i in instances if i.cache_hit_ratio is not None]
        avg_cache_hit = sum(cache_ratios) / len(cache_ratios) if cache_ratios else 0

        # Active alerts
        alerts_result = await db.execute(
            select(func.count())
            .select_from(DatabaseAlert)
            .where(
                DatabaseAlert.organization_id == organization_id,
                DatabaseAlert.status == "active"
            )
        )
        total_active_alerts = alerts_result.scalar() or 0

        return DatabaseSummary(
            total_instances=total,
            healthy_instances=healthy,
            warning_instances=warning,
            critical_instances=critical,
            unreachable_instances=unreachable,
            by_type=by_type,
            total_connections_used=total_connections_used,
            total_connections_max=total_connections_max,
            total_storage_used_bytes=total_storage_used,
            total_storage_bytes=total_storage,
            avg_cache_hit_ratio=avg_cache_hit,
            total_slow_queries=total_slow_queries,
            total_active_alerts=total_active_alerts
        )

    # ============================================
    # Query Operations
    # ============================================

    async def list_queries(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession,
        filter_data: Optional[QueryFilter] = None,
        order_by: str = "total_time_ms",
        limit: int = 50,
        offset: int = 0
    ) -> DatabaseQueryListResponse:
        """List database queries with filtering."""
        query = select(DatabaseQuery).where(
            DatabaseQuery.organization_id == organization_id
        )

        if filter_data:
            if filter_data.instance_id:
                query = query.where(DatabaseQuery.instance_id == filter_data.instance_id)
            if filter_data.database_name:
                query = query.where(DatabaseQuery.database_name == filter_data.database_name)
            if filter_data.query_type:
                query = query.where(DatabaseQuery.query_type == filter_data.query_type)
            if filter_data.is_slow is not None:
                query = query.where(DatabaseQuery.is_slow == ("true" if filter_data.is_slow else "false"))
            if filter_data.min_avg_time_ms is not None:
                query = query.where(DatabaseQuery.avg_time_ms >= filter_data.min_avg_time_ms)
            if filter_data.min_call_count is not None:
                query = query.where(DatabaseQuery.call_count >= filter_data.min_call_count)

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        # Order
        if order_by == "avg_time_ms":
            query = query.order_by(DatabaseQuery.avg_time_ms.desc().nullslast())
        elif order_by == "call_count":
            query = query.order_by(DatabaseQuery.call_count.desc())
        elif order_by == "last_seen":
            query = query.order_by(DatabaseQuery.last_seen.desc().nullslast())
        else:
            query = query.order_by(DatabaseQuery.total_time_ms.desc())

        # Get data
        result = await db.execute(
            query.offset(offset).limit(limit)
        )
        queries = result.scalars().all()

        return DatabaseQueryListResponse(
            queries=[self._query_to_response(q) for q in queries],
            total=total
        )

    async def get_query(
        self,
        query_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[DatabaseQueryResponse]:
        """Get a query by ID."""
        result = await db.execute(
            select(DatabaseQuery)
            .where(
                DatabaseQuery.id == query_id,
                DatabaseQuery.organization_id == organization_id
            )
        )
        query = result.scalar_one_or_none()
        if query:
            return self._query_to_response(query)
        return None

    # ============================================
    # Metrics Operations
    # ============================================

    async def get_metrics_history(
        self,
        instance_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> MetricSnapshotListResponse:
        """Get metrics history for an instance."""
        query = select(DatabaseMetricSnapshot).where(
            DatabaseMetricSnapshot.organization_id == organization_id,
            DatabaseMetricSnapshot.instance_id == instance_id
        )

        if start_time:
            query = query.where(DatabaseMetricSnapshot.timestamp >= start_time)
        if end_time:
            query = query.where(DatabaseMetricSnapshot.timestamp <= end_time)

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        # Get data
        result = await db.execute(
            query.order_by(DatabaseMetricSnapshot.timestamp.desc())
            .limit(limit)
        )
        snapshots = result.scalars().all()

        return MetricSnapshotListResponse(
            snapshots=[self._snapshot_to_response(s) for s in snapshots],
            total=total
        )

    # ============================================
    # Alert Operations
    # ============================================

    async def list_alerts(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession,
        instance_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> DatabaseAlertListResponse:
        """List database alerts."""
        query = select(DatabaseAlert).where(
            DatabaseAlert.organization_id == organization_id
        )

        if instance_id:
            query = query.where(DatabaseAlert.instance_id == instance_id)
        if status:
            query = query.where(DatabaseAlert.status == status)
        if severity:
            query = query.where(DatabaseAlert.severity == severity)

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        # Get data
        result = await db.execute(
            query.order_by(DatabaseAlert.triggered_at.desc())
            .offset(offset)
            .limit(limit)
        )
        alerts = result.scalars().all()

        return DatabaseAlertListResponse(
            alerts=[self._alert_to_response(a) for a in alerts],
            total=total
        )

    async def acknowledge_alert(
        self,
        alert_id: uuid.UUID,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession,
        comment: Optional[str] = None
    ) -> Optional[DatabaseAlertResponse]:
        """Acknowledge an alert."""
        result = await db.execute(
            select(DatabaseAlert)
            .where(
                DatabaseAlert.id == alert_id,
                DatabaseAlert.organization_id == organization_id
            )
        )
        alert = result.scalar_one_or_none()
        if not alert:
            return None

        alert.status = "acknowledged"
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = user_id
        if comment:
            context = alert.context or {}
            context["acknowledge_comment"] = comment
            alert.context = context

        await db.commit()
        await db.refresh(alert)

        return self._alert_to_response(alert)

    async def resolve_alert(
        self,
        alert_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[DatabaseAlertResponse]:
        """Resolve an alert."""
        result = await db.execute(
            select(DatabaseAlert)
            .where(
                DatabaseAlert.id == alert_id,
                DatabaseAlert.organization_id == organization_id
            )
        )
        alert = result.scalar_one_or_none()
        if not alert:
            return None

        alert.status = "resolved"
        alert.resolved_at = datetime.utcnow()

        await db.commit()
        await db.refresh(alert)

        return self._alert_to_response(alert)

    # ============================================
    # Metrics Ingestion
    # ============================================

    async def ingest_metrics(
        self,
        instance_id: uuid.UUID,
        report: DatabaseMetricsReport,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> MetricsIngestResponse:
        """Ingest metrics from monitoring agent."""
        errors = []
        alerts_generated = 0

        # Get instance
        result = await db.execute(
            select(DatabaseInstance)
            .where(
                DatabaseInstance.id == instance_id,
                DatabaseInstance.organization_id == organization_id
            )
        )
        instance = result.scalar_one_or_none()
        if not instance:
            return MetricsIngestResponse(
                success=False,
                instance_id=instance_id,
                metrics_stored=False,
                alerts_generated=0,
                errors=["Instance not found"]
            )

        try:
            # Update instance with latest metrics
            if report.version:
                instance.version = report.version

            if report.connections:
                instance.connections_used = report.connections.total
                instance.connections_max = report.connections.max_connections
                if report.connections.max_connections > 0:
                    instance.connection_utilization = (report.connections.total / report.connections.max_connections) * 100

            if report.storage:
                instance.storage_used_bytes = report.storage.used_bytes
                instance.storage_total_bytes = report.storage.total_bytes
                if report.storage.total_bytes > 0:
                    instance.storage_utilization = (report.storage.used_bytes / report.storage.total_bytes) * 100

            if report.performance:
                instance.queries_per_second = report.performance.queries_per_second
                instance.avg_query_time_ms = report.performance.avg_query_time_ms
                instance.slow_queries_count = report.performance.slow_queries
                instance.active_transactions = report.performance.active_transactions

            if report.replication:
                instance.replication_lag_seconds = report.replication.lag_seconds
                if report.replication.role:
                    instance.replication_role = report.replication.role

            if report.cache:
                instance.cache_hit_ratio = report.cache.hit_ratio

            if report.locks:
                instance.locks_waiting = report.locks.locks_waiting
                instance.deadlocks_count = report.locks.deadlocks

            # Update status
            instance.last_check = report.timestamp
            instance.last_successful_check = report.timestamp
            instance.connection_status = "connected"
            instance.status = self._determine_status(instance)

            # Create metric snapshot
            snapshot = DatabaseMetricSnapshot(
                organization_id=organization_id,
                instance_id=instance_id,
                timestamp=report.timestamp,
                connections_active=report.connections.active if report.connections else None,
                connections_idle=report.connections.idle if report.connections else None,
                connections_total=report.connections.total if report.connections else None,
                queries_per_second=report.performance.queries_per_second if report.performance else None,
                avg_query_time_ms=report.performance.avg_query_time_ms if report.performance else None,
                slow_queries=report.performance.slow_queries if report.performance else None,
                locks_waiting=report.locks.locks_waiting if report.locks else None,
                replication_lag_seconds=report.replication.lag_seconds if report.replication else None,
                cache_hit_ratio=report.cache.hit_ratio if report.cache else None,
                storage_used_bytes=report.storage.used_bytes if report.storage else None,
                storage_free_bytes=report.storage.free_bytes if report.storage else None,
                extra_metrics=report.extra_metrics
            )
            db.add(snapshot)

            # Check for alert conditions
            alerts_generated = await self._check_alert_conditions(instance, report, organization_id, db)

            await db.commit()

            return MetricsIngestResponse(
                success=True,
                instance_id=instance_id,
                metrics_stored=True,
                alerts_generated=alerts_generated,
                errors=errors
            )

        except Exception as e:
            await db.rollback()
            return MetricsIngestResponse(
                success=False,
                instance_id=instance_id,
                metrics_stored=False,
                alerts_generated=0,
                errors=[str(e)]
            )

    async def ingest_query_stats(
        self,
        instance_id: uuid.UUID,
        report: QueryStatsReport,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Ingest query statistics from monitoring agent."""
        queries_upserted = 0
        slow_queries_found = 0

        # Get instance for slow query threshold
        result = await db.execute(
            select(DatabaseInstance)
            .where(
                DatabaseInstance.id == instance_id,
                DatabaseInstance.organization_id == organization_id
            )
        )
        instance = result.scalar_one_or_none()
        if not instance:
            return {"success": False, "error": "Instance not found"}

        slow_threshold = instance.slow_query_threshold_ms or 1000

        for query_stat in report.queries:
            try:
                # Find existing query by hash
                existing_result = await db.execute(
                    select(DatabaseQuery)
                    .where(
                        DatabaseQuery.instance_id == instance_id,
                        DatabaseQuery.query_hash == query_stat.query_hash
                    )
                )
                existing = existing_result.scalar_one_or_none()

                is_slow = query_stat.max_time_ms >= slow_threshold

                if existing:
                    # Update existing
                    existing.call_count += query_stat.call_count
                    existing.total_time_ms += query_stat.total_time_ms
                    existing.avg_time_ms = existing.total_time_ms / existing.call_count if existing.call_count > 0 else 0
                    existing.min_time_ms = min(existing.min_time_ms or float('inf'), query_stat.min_time_ms)
                    existing.max_time_ms = max(existing.max_time_ms or 0, query_stat.max_time_ms)
                    existing.last_seen = report.timestamp
                    existing.is_slow = "true" if is_slow else "false"
                    existing.updated_at = datetime.utcnow()
                else:
                    # Create new
                    new_query = DatabaseQuery(
                        organization_id=organization_id,
                        instance_id=instance_id,
                        query_hash=query_stat.query_hash,
                        query_normalized=query_stat.query_normalized,
                        query_sample=query_stat.query_sample,
                        database_name=query_stat.database_name,
                        schema_name=query_stat.schema_name,
                        table_names=query_stat.table_names,
                        call_count=query_stat.call_count,
                        total_time_ms=query_stat.total_time_ms,
                        avg_time_ms=query_stat.total_time_ms / query_stat.call_count if query_stat.call_count > 0 else 0,
                        min_time_ms=query_stat.min_time_ms,
                        max_time_ms=query_stat.max_time_ms,
                        avg_rows_returned=query_stat.avg_rows_returned,
                        cache_hit_ratio=query_stat.cache_hit_ratio,
                        query_type=query_stat.query_type,
                        first_seen=report.timestamp,
                        last_seen=report.timestamp,
                        is_slow="true" if is_slow else "false"
                    )
                    db.add(new_query)

                queries_upserted += 1
                if is_slow:
                    slow_queries_found += 1

            except Exception as e:
                # Log error but continue with other queries
                pass

        await db.commit()

        return {
            "success": True,
            "queries_upserted": queries_upserted,
            "slow_queries_found": slow_queries_found
        }

    # ============================================
    # Helper Methods
    # ============================================

    def _determine_status(self, instance: DatabaseInstance) -> str:
        """Determine overall instance status."""
        if instance.connection_status != "connected":
            return "unreachable"

        # Check critical conditions
        if instance.storage_utilization and instance.storage_utilization > 95:
            return "critical"
        if instance.connection_utilization and instance.connection_utilization > 95:
            return "critical"
        if instance.replication_lag_seconds and instance.replication_lag_seconds > 120:
            return "critical"

        # Check warning conditions
        if instance.storage_utilization and instance.storage_utilization > 85:
            return "warning"
        if instance.connection_utilization and instance.connection_utilization > 80:
            return "warning"
        if instance.replication_lag_seconds and instance.replication_lag_seconds > 30:
            return "warning"
        if instance.deadlocks_count and instance.deadlocks_count > 0:
            return "warning"

        return "healthy"

    async def _check_alert_conditions(
        self,
        instance: DatabaseInstance,
        report: DatabaseMetricsReport,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> int:
        """Check for alert conditions and create alerts if needed."""
        alerts_created = 0

        # Connection threshold
        if instance.connection_utilization and instance.connection_utilization > instance.alert_on_connection_threshold:
            existing = await self._has_active_alert(instance.id, "connection_high", db)
            if not existing:
                await self._create_alert(
                    organization_id, instance.id,
                    "connection_high", "warning",
                    f"High connection usage on {instance.name}",
                    f"Connection utilization is {instance.connection_utilization:.1f}%",
                    "connection_utilization", instance.connection_utilization,
                    instance.alert_on_connection_threshold, db
                )
                alerts_created += 1

        # Storage threshold
        if instance.storage_utilization and instance.storage_utilization > instance.alert_on_storage_threshold:
            severity = "critical" if instance.storage_utilization > 95 else "warning"
            existing = await self._has_active_alert(instance.id, "storage_high", db)
            if not existing:
                await self._create_alert(
                    organization_id, instance.id,
                    "storage_high", severity,
                    f"High storage usage on {instance.name}",
                    f"Storage utilization is {instance.storage_utilization:.1f}%",
                    "storage_utilization", instance.storage_utilization,
                    instance.alert_on_storage_threshold, db
                )
                alerts_created += 1

        # Replication lag
        if instance.replication_lag_seconds and instance.replication_lag_seconds > instance.alert_on_replication_lag:
            severity = "critical" if instance.replication_lag_seconds > 120 else "warning"
            existing = await self._has_active_alert(instance.id, "replication_lag", db)
            if not existing:
                await self._create_alert(
                    organization_id, instance.id,
                    "replication_lag", severity,
                    f"Replication lag on {instance.name}",
                    f"Replication lag is {instance.replication_lag_seconds:.1f} seconds",
                    "replication_lag_seconds", instance.replication_lag_seconds,
                    instance.alert_on_replication_lag, db
                )
                alerts_created += 1

        # Deadlocks
        if report.locks and report.locks.deadlocks > 0:
            await self._create_alert(
                organization_id, instance.id,
                "deadlock", "warning",
                f"Deadlock detected on {instance.name}",
                f"{report.locks.deadlocks} deadlock(s) detected",
                "deadlocks", float(report.locks.deadlocks), 0.0, db
            )
            alerts_created += 1

        return alerts_created

    async def _has_active_alert(
        self,
        instance_id: uuid.UUID,
        alert_type: str,
        db: AsyncSession
    ) -> bool:
        """Check if there's an active alert of the given type."""
        result = await db.execute(
            select(func.count())
            .select_from(DatabaseAlert)
            .where(
                DatabaseAlert.instance_id == instance_id,
                DatabaseAlert.alert_type == alert_type,
                DatabaseAlert.status == "active"
            )
        )
        count = result.scalar() or 0
        return count > 0

    async def _create_alert(
        self,
        organization_id: uuid.UUID,
        instance_id: uuid.UUID,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        metric_name: str,
        metric_value: float,
        threshold_value: float,
        db: AsyncSession
    ):
        """Create a database alert."""
        alert = DatabaseAlert(
            organization_id=organization_id,
            instance_id=instance_id,
            alert_type=alert_type,
            severity=severity,
            status="active",
            title=title,
            message=message,
            metric_name=metric_name,
            metric_value=metric_value,
            threshold_value=threshold_value,
            triggered_at=datetime.utcnow()
        )
        db.add(alert)

    def _instance_to_response(self, instance: DatabaseInstance) -> DatabaseInstanceResponse:
        """Convert instance model to response."""
        return DatabaseInstanceResponse(
            id=instance.id,
            organization_id=instance.organization_id,
            host_id=instance.host_id,
            name=instance.name,
            display_name=instance.display_name,
            description=instance.description,
            database_type=instance.database_type,
            version=instance.version,
            hostname=instance.hostname,
            port=instance.port,
            database_name=instance.database_name,
            status=instance.status,
            last_check=instance.last_check,
            last_successful_check=instance.last_successful_check,
            connection_status=instance.connection_status,
            replication_role=instance.replication_role,
            replication_lag_seconds=instance.replication_lag_seconds,
            primary_id=instance.primary_id,
            connections_used=instance.connections_used,
            connections_max=instance.connections_max,
            connection_utilization=instance.connection_utilization,
            storage_used_bytes=instance.storage_used_bytes,
            storage_total_bytes=instance.storage_total_bytes,
            storage_utilization=instance.storage_utilization,
            queries_per_second=instance.queries_per_second,
            avg_query_time_ms=instance.avg_query_time_ms,
            slow_queries_count=instance.slow_queries_count,
            active_transactions=instance.active_transactions,
            locks_waiting=instance.locks_waiting,
            deadlocks_count=instance.deadlocks_count,
            cache_hit_ratio=instance.cache_hit_ratio,
            monitoring_enabled=instance.monitoring_enabled == "true",
            collect_query_stats=instance.collect_query_stats == "true",
            collect_slow_queries=instance.collect_slow_queries == "true",
            slow_query_threshold_ms=instance.slow_query_threshold_ms or 1000,
            tags=instance.tags or {},
            labels=instance.labels or {},
            created_at=instance.created_at,
            updated_at=instance.updated_at
        )

    def _query_to_response(self, query: DatabaseQuery) -> DatabaseQueryResponse:
        """Convert query model to response."""
        return DatabaseQueryResponse(
            id=query.id,
            organization_id=query.organization_id,
            instance_id=query.instance_id,
            query_hash=query.query_hash,
            query_normalized=query.query_normalized,
            query_sample=query.query_sample,
            database_name=query.database_name,
            schema_name=query.schema_name,
            table_names=query.table_names or [],
            call_count=query.call_count or 0,
            total_time_ms=query.total_time_ms or 0,
            avg_time_ms=query.avg_time_ms,
            min_time_ms=query.min_time_ms,
            max_time_ms=query.max_time_ms,
            avg_rows_returned=query.avg_rows_returned,
            cache_hit_ratio=query.cache_hit_ratio,
            is_slow=query.is_slow == "true",
            query_type=query.query_type,
            first_seen=query.first_seen,
            last_seen=query.last_seen,
            created_at=query.created_at,
            updated_at=query.updated_at
        )

    def _snapshot_to_response(self, snapshot: DatabaseMetricSnapshot) -> MetricSnapshotResponse:
        """Convert snapshot model to response."""
        return MetricSnapshotResponse(
            id=snapshot.id,
            instance_id=snapshot.instance_id,
            timestamp=snapshot.timestamp,
            connections_active=snapshot.connections_active,
            connections_idle=snapshot.connections_idle,
            connections_total=snapshot.connections_total,
            queries_per_second=snapshot.queries_per_second,
            avg_query_time_ms=snapshot.avg_query_time_ms,
            slow_queries=snapshot.slow_queries,
            locks_waiting=snapshot.locks_waiting,
            replication_lag_seconds=snapshot.replication_lag_seconds,
            cache_hit_ratio=snapshot.cache_hit_ratio,
            storage_used_bytes=snapshot.storage_used_bytes,
            storage_free_bytes=snapshot.storage_free_bytes,
            extra_metrics=snapshot.extra_metrics or {}
        )

    def _alert_to_response(self, alert: DatabaseAlert) -> DatabaseAlertResponse:
        """Convert alert model to response."""
        return DatabaseAlertResponse(
            id=alert.id,
            organization_id=alert.organization_id,
            instance_id=alert.instance_id,
            alert_type=alert.alert_type,
            severity=alert.severity,
            status=alert.status,
            title=alert.title,
            message=alert.message,
            metric_name=alert.metric_name,
            metric_value=alert.metric_value,
            threshold_value=alert.threshold_value,
            context=alert.context or {},
            query_id=alert.query_id,
            triggered_at=alert.triggered_at,
            acknowledged_at=alert.acknowledged_at,
            acknowledged_by=alert.acknowledged_by,
            resolved_at=alert.resolved_at,
            created_at=alert.created_at
        )


# Singleton instance
database_monitor_service = DatabaseMonitorService()
