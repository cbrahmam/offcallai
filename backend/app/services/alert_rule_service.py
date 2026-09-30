# backend/app/services/alert_rule_service.py
"""
Alert Rule Service for managing and evaluating metric-based alert rules.
"""

import re
import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.models.alert_rule import AlertRule, AlertRuleHistory
from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.models.host import Host
from app.schemas.alert_rule import (
    AlertRuleCreate, AlertRuleUpdate, AlertRuleResponse, AlertRuleListResponse,
    AlertRuleSummary, AlertRuleTestRequest, AlertRuleTestResponse,
    AlertRuleHistoryItem, AlertRuleHistoryResponse
)
from sqlalchemy import text
from app.core.config import settings
from app.services.clickhouse_service import clickhouse_service, format_datetime_for_clickhouse

logger = logging.getLogger(__name__)


class AlertRuleService:
    """Service for alert rule CRUD and evaluation."""

    # ============================================
    # CRUD Operations
    # ============================================

    async def create_rule(
        self,
        data: AlertRuleCreate,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        db: AsyncSession
    ) -> AlertRule:
        """Create a new alert rule."""
        rule = AlertRule(
            organization_id=organization_id,
            created_by_id=user_id,
            name=data.name,
            description=data.description,
            metric_name=data.metric_name,
            operator=data.operator.value,
            threshold=data.threshold,
            aggregation=data.aggregation.value,
            evaluation_window=data.evaluation_window,
            duration=data.duration,
            host_ids=data.host_ids or [],
            host_tags=data.host_tags or {},
            severity=data.severity.value,
            auto_create_incident=data.auto_create_incident,
            auto_resolve=data.auto_resolve,
            cooldown_seconds=data.cooldown_seconds,
            notify_channels=data.notify_channels or [],
            notify_users=data.notify_users or [],
            labels=data.labels or {},
            status="enabled"
        )

        db.add(rule)
        await db.commit()
        await db.refresh(rule)

        logger.info(f"Created alert rule: {rule.name} (id={rule.id})")
        return rule

    async def get_rule(
        self,
        rule_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[AlertRule]:
        """Get an alert rule by ID."""
        result = await db.execute(
            select(AlertRule).where(
                AlertRule.id == rule_id,
                AlertRule.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_rules(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession,
        status: Optional[str] = None,
        metric_name: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> AlertRuleListResponse:
        """List alert rules with filtering and pagination."""
        query = select(AlertRule).where(AlertRule.organization_id == organization_id)

        if status:
            query = query.where(AlertRule.status == status)
        if metric_name:
            query = query.where(AlertRule.metric_name.ilike(f"%{metric_name}%"))

        # Get total count
        count_query = select(func.count(AlertRule.id)).where(
            AlertRule.organization_id == organization_id
        )
        if status:
            count_query = count_query.where(AlertRule.status == status)
        if metric_name:
            count_query = count_query.where(AlertRule.metric_name.ilike(f"%{metric_name}%"))

        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Paginate
        offset = (page - 1) * per_page
        query = query.order_by(AlertRule.created_at.desc()).offset(offset).limit(per_page)

        result = await db.execute(query)
        rules = result.scalars().all()

        return AlertRuleListResponse(
            rules=[self._rule_to_response(r) for r in rules],
            total=total,
            page=page,
            per_page=per_page
        )

    async def update_rule(
        self,
        rule_id: uuid.UUID,
        organization_id: uuid.UUID,
        data: AlertRuleUpdate,
        db: AsyncSession
    ) -> Optional[AlertRule]:
        """Update an existing alert rule."""
        rule = await self.get_rule(rule_id, organization_id, db)
        if not rule:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(rule, field):
                if isinstance(value, enum.Enum):
                    value = value.value
                setattr(rule, field, value)

        rule.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(rule)

        logger.info(f"Updated alert rule: {rule.name} (id={rule.id})")
        return rule

    async def delete_rule(
        self,
        rule_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> bool:
        """Delete an alert rule."""
        rule = await self.get_rule(rule_id, organization_id, db)
        if not rule:
            return False

        await db.delete(rule)
        await db.commit()

        logger.info(f"Deleted alert rule: id={rule_id}")
        return True

    async def toggle_rule(
        self,
        rule_id: uuid.UUID,
        organization_id: uuid.UUID,
        enabled: bool,
        db: AsyncSession
    ) -> Optional[AlertRule]:
        """Enable or disable an alert rule."""
        rule = await self.get_rule(rule_id, organization_id, db)
        if not rule:
            return None

        old_status = rule.status
        rule.status = "enabled" if enabled else "disabled"

        # If disabling a firing rule, reset state
        if not enabled and old_status in ["firing", "pending"]:
            rule.triggered_since = None
            rule.current_value = None

        rule.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(rule)

        # Record history
        await self._record_history(
            rule_id=rule.id,
            organization_id=organization_id,
            previous_status=old_status,
            new_status=rule.status,
            db=db
        )

        logger.info(f"Toggled alert rule {rule.name}: {old_status} -> {rule.status}")
        return rule

    async def get_summary(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> AlertRuleSummary:
        """Get summary statistics for alert rules."""
        result = await db.execute(
            select(
                AlertRule.status,
                AlertRule.severity,
                func.count(AlertRule.id)
            ).where(
                AlertRule.organization_id == organization_id
            ).group_by(AlertRule.status, AlertRule.severity)
        )
        rows = result.fetchall()

        status_counts = {"enabled": 0, "disabled": 0, "firing": 0, "pending": 0}
        severity_counts = {"info": 0, "warning": 0, "error": 0, "critical": 0}

        for status, severity, count in rows:
            if status in status_counts:
                status_counts[status] += count
            if severity in severity_counts:
                severity_counts[severity] += count

        total = sum(status_counts.values())

        return AlertRuleSummary(
            total=total,
            enabled=status_counts["enabled"],
            disabled=status_counts["disabled"],
            firing=status_counts["firing"],
            pending=status_counts["pending"],
            by_severity=severity_counts
        )

    # ============================================
    # Rule Evaluation
    # ============================================

    async def evaluate_rules(
        self,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Evaluate all enabled alert rules for an organization.
        Called periodically by a background worker.
        Returns summary of evaluations.
        """
        # Get all enabled rules
        result = await db.execute(
            select(AlertRule).where(
                AlertRule.organization_id == organization_id,
                AlertRule.status.in_(["enabled", "firing", "pending"])
            )
        )
        rules = result.scalars().all()

        evaluated = 0
        triggered = 0
        resolved = 0
        errors = 0

        for rule in rules:
            try:
                result = await self._evaluate_single_rule(rule, organization_id, db)
                evaluated += 1
                if result == "triggered":
                    triggered += 1
                elif result == "resolved":
                    resolved += 1
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.id}: {e}")
                errors += 1

        await db.commit()

        return {
            "evaluated": evaluated,
            "triggered": triggered,
            "resolved": resolved,
            "errors": errors
        }

    async def _evaluate_single_rule(
        self,
        rule: AlertRule,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> str:
        """Evaluate a single alert rule. Returns 'ok', 'triggered', 'resolved', or 'pending'."""
        now = datetime.utcnow()

        # Get aggregated metric value
        current_value = await self._get_aggregated_value(rule, organization_id, db)

        if current_value is None:
            # No data available
            rule.last_evaluated_at = now
            return "ok"

        rule.current_value = current_value
        rule.last_evaluated_at = now

        # Check condition
        condition_met = self._check_condition(current_value, rule.operator, rule.threshold)

        if condition_met:
            if rule.status == "enabled":
                # First time breaching
                if rule.duration > 0:
                    # Need to wait for duration
                    rule.status = "pending"
                    rule.triggered_since = now
                    await self._record_history(
                        rule.id, organization_id, "enabled", "pending", db,
                        triggered_value=current_value
                    )
                    return "pending"
                else:
                    # Trigger immediately
                    return await self._trigger_rule(rule, organization_id, db, current_value)

            elif rule.status == "pending":
                # Check if duration threshold met
                if rule.triggered_since:
                    elapsed = (now - rule.triggered_since).total_seconds()
                    if elapsed >= rule.duration:
                        # Duration met, trigger
                        return await self._trigger_rule(rule, organization_id, db, current_value)
                return "pending"

            elif rule.status == "firing":
                # Already firing, nothing to do
                return "firing"

        else:
            # Condition not met
            if rule.status == "pending":
                # Reset pending state
                rule.status = "enabled"
                rule.triggered_since = None
                await self._record_history(
                    rule.id, organization_id, "pending", "enabled", db
                )
                return "ok"

            elif rule.status == "firing":
                # Check if should auto-resolve
                if rule.auto_resolve:
                    return await self._resolve_rule(rule, organization_id, db)
                return "firing"

        return "ok"

    async def _trigger_rule(
        self,
        rule: AlertRule,
        organization_id: uuid.UUID,
        db: AsyncSession,
        current_value: float
    ) -> str:
        """Trigger an alert rule - create incident and update state."""
        now = datetime.utcnow()

        # Check cooldown
        if rule.last_triggered_at:
            elapsed = (now - rule.last_triggered_at).total_seconds()
            if elapsed < rule.cooldown_seconds:
                logger.debug(f"Rule {rule.id} in cooldown, skipping trigger")
                return "ok"

        old_status = rule.status
        rule.status = "firing"
        rule.last_triggered_at = now

        incident_id = None

        # Create incident if configured
        if rule.auto_create_incident:
            incident = await self._create_incident_for_rule(rule, organization_id, current_value, db)
            incident_id = incident.id

        # Record history
        await self._record_history(
            rule.id, organization_id, old_status, "firing", db,
            triggered_value=current_value, incident_id=incident_id
        )

        logger.info(f"Alert rule triggered: {rule.name} (value={current_value}, threshold={rule.threshold})")
        return "triggered"

    async def _resolve_rule(
        self,
        rule: AlertRule,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> str:
        """Resolve a firing alert rule."""
        now = datetime.utcnow()

        old_status = rule.status
        rule.status = "enabled"
        rule.last_resolved_at = now
        rule.triggered_since = None

        # Record history
        await self._record_history(
            rule.id, organization_id, old_status, "enabled", db
        )

        logger.info(f"Alert rule resolved: {rule.name}")
        return "resolved"

    async def _get_aggregated_value(
        self,
        rule: AlertRule,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> Optional[float]:
        """Get the aggregated metric value for a rule."""
        window_start = datetime.utcnow() - timedelta(seconds=rule.evaluation_window)

        # Use ClickHouse for metrics when enabled
        if settings.CLICKHOUSE_ENABLED:
            return await self._get_aggregated_value_clickhouse(
                rule, organization_id, window_start
            )

        # Fallback to PostgreSQL
        return await self._get_aggregated_value_postgres(
            rule, organization_id, window_start, db
        )

    async def _get_aggregated_value_clickhouse(
        self,
        rule: AlertRule,
        organization_id: uuid.UUID,
        window_start: datetime
    ) -> Optional[float]:
        """Get aggregated metric value from ClickHouse."""
        # Build aggregation function for ClickHouse
        agg_map = {
            "avg": "avg(value)",
            "max": "max(value)",
            "min": "min(value)",
            "sum": "sum(value)",
            "last": "argMax(value, timestamp)"  # ClickHouse way to get last value
        }
        agg_func = agg_map.get(rule.aggregation, "avg(value)")

        # Build WHERE clauses
        filters = [
            f"organization_id = '{organization_id}'",
            f"name = '{rule.metric_name}'",
            f"timestamp >= '{format_datetime_for_clickhouse(window_start)}'"
        ]

        # Filter by host_ids
        if rule.host_ids:
            host_ids_str = ", ".join(f"'{h}'" for h in rule.host_ids)
            filters.append(f"host_id IN ({host_ids_str})")

        # Filter by host_tags using subquery to PostgreSQL isn't possible,
        # so we filter by host_ids if tags are specified (need to resolve them first)
        if rule.host_tags:
            # Note: For ClickHouse, we'd need to either:
            # 1. Store tags in ClickHouse metrics table
            # 2. Or pre-resolve host_ids from PostgreSQL
            # For now, we'll log a warning - tags filtering requires enhancement
            logger.warning(
                f"Host tags filtering not fully supported in ClickHouse mode for rule {rule.id}. "
                "Consider using host_ids instead."
            )

        where_clause = " AND ".join(filters)

        query = f"""
        SELECT {agg_func} as agg_value
        FROM metrics
        WHERE {where_clause}
        FORMAT JSON
        """

        try:
            result = await clickhouse_service.execute(query)
            if result and result.get("data"):
                data = result["data"]
                if data and len(data) > 0:
                    value = data[0].get("agg_value")
                    return float(value) if value is not None else None
            return None
        except Exception as e:
            logger.error(f"Error getting aggregated value from ClickHouse: {e}")
            return None

    async def _get_aggregated_value_postgres(
        self,
        rule: AlertRule,
        organization_id: uuid.UUID,
        window_start: datetime,
        db: AsyncSession
    ) -> Optional[float]:
        """Get aggregated metric value from PostgreSQL (fallback)."""
        # Build aggregation SQL
        agg_map = {
            "avg": "AVG(value)",
            "max": "MAX(value)",
            "min": "MIN(value)",
            "sum": "SUM(value)",
            "last": "MAX(value)"  # Approximation
        }
        agg_func = agg_map.get(rule.aggregation, "AVG(value)")

        params = {
            "org_id": organization_id,
            "metric_name": rule.metric_name,
            "window_start": window_start
        }

        where_clauses = [
            "organization_id = :org_id",
            "name = :metric_name",
            "time >= :window_start"
        ]

        # Filter by host_ids
        if rule.host_ids:
            where_clauses.append("host_id = ANY(:host_ids)")
            params["host_ids"] = [uuid.UUID(h) for h in rule.host_ids]

        # Filter by host_tags (requires join)
        # SECURITY: Sanitize tag keys to prevent SQL injection
        if rule.host_tags:
            for key, value in rule.host_tags.items():
                # Only allow alphanumeric keys with underscores/hyphens
                if not re.match(r'^[a-zA-Z0-9_-]+$', key):
                    logger.warning(f"Invalid host_tag key rejected: {key}")
                    continue
                # Use parameterized key lookup for safety
                safe_key = key.replace('-', '_')  # Param names can't have hyphens
                where_clauses.append(
                    f"host_id IN (SELECT id FROM hosts WHERE tags->>:tag_key_{safe_key} = :tag_val_{safe_key})"
                )
                params[f"tag_key_{safe_key}"] = key
                params[f"tag_val_{safe_key}"] = value

        where_sql = " AND ".join(where_clauses)

        sql = f"""
            SELECT {agg_func} as agg_value
            FROM metrics
            WHERE {where_sql}
        """

        try:
            result = await db.execute(text(sql), params)
            row = result.fetchone()
            return row[0] if row and row[0] is not None else None
        except Exception as e:
            logger.error(f"Error getting aggregated value from PostgreSQL: {e}")
            return None

    def _check_condition(self, value: float, operator: str, threshold: float) -> bool:
        """Check if the condition is met."""
        ops = {
            "gt": lambda v, t: v > t,
            "gte": lambda v, t: v >= t,
            "lt": lambda v, t: v < t,
            "lte": lambda v, t: v <= t,
            "eq": lambda v, t: v == t,
            "neq": lambda v, t: v != t,
        }
        op_func = ops.get(operator, lambda v, t: v > t)
        return op_func(value, threshold)

    async def _create_incident_for_rule(
        self,
        rule: AlertRule,
        organization_id: uuid.UUID,
        current_value: float,
        db: AsyncSession
    ) -> Incident:
        """Create an incident from a triggered alert rule."""
        severity_map = {
            "info": IncidentSeverity.LOW,
            "warning": IncidentSeverity.MEDIUM,
            "error": IncidentSeverity.HIGH,
            "critical": IncidentSeverity.CRITICAL
        }

        incident = Incident(
            organization_id=organization_id,
            title=f"Alert: {rule.name}",
            description=f"Alert rule '{rule.name}' triggered.\n\nCondition: {rule.condition_text}\nCurrent value: {current_value}",
            severity=severity_map.get(rule.severity, IncidentSeverity.MEDIUM),
            status=IncidentStatus.OPEN,
            tags=["auto-generated", "alert-rule"],
            extra_data={
                "alert_rule_id": str(rule.id),
                "metric_name": rule.metric_name,
                "threshold": rule.threshold,
                "triggered_value": current_value,
                "operator": rule.operator
            }
        )

        db.add(incident)
        await db.flush()  # Get the ID without committing

        logger.info(f"Created incident {incident.id} for alert rule {rule.id}")
        return incident

    async def _record_history(
        self,
        rule_id: uuid.UUID,
        organization_id: uuid.UUID,
        previous_status: Optional[str],
        new_status: str,
        db: AsyncSession,
        triggered_value: Optional[float] = None,
        incident_id: Optional[uuid.UUID] = None
    ):
        """Record a state change in alert rule history."""
        history = AlertRuleHistory(
            alert_rule_id=rule_id,
            organization_id=organization_id,
            previous_status=previous_status,
            new_status=new_status,
            triggered_value=triggered_value,
            incident_id=incident_id
        )
        db.add(history)

    # ============================================
    # Testing
    # ============================================

    async def test_rule(
        self,
        data: AlertRuleTestRequest,
        organization_id: uuid.UUID,
        db: AsyncSession
    ) -> AlertRuleTestResponse:
        """Test an alert rule configuration against recent data."""
        window_start = datetime.utcnow() - timedelta(seconds=data.evaluation_window)

        # Use ClickHouse when enabled
        if settings.CLICKHOUSE_ENABLED:
            return await self._test_rule_clickhouse(data, organization_id, window_start)

        # Fallback to PostgreSQL
        return await self._test_rule_postgres(data, organization_id, window_start, db)

    async def _test_rule_clickhouse(
        self,
        data: AlertRuleTestRequest,
        organization_id: uuid.UUID,
        window_start: datetime
    ) -> AlertRuleTestResponse:
        """Test alert rule against ClickHouse data."""
        # Build aggregation function
        agg_map = {
            "avg": "avg(value)",
            "max": "max(value)",
            "min": "min(value)",
            "sum": "sum(value)",
            "last": "argMax(value, timestamp)"
        }
        agg_func = agg_map.get(data.aggregation.value, "avg(value)")

        # Build WHERE clauses
        filters = [
            f"organization_id = '{organization_id}'",
            f"name = '{data.metric_name}'",
            f"timestamp >= '{format_datetime_for_clickhouse(window_start)}'"
        ]

        if data.host_ids:
            host_ids_str = ", ".join(f"'{h}'" for h in data.host_ids)
            filters.append(f"host_id IN ({host_ids_str})")

        where_clause = " AND ".join(filters)

        # Query per host
        query = f"""
        SELECT
            host_id,
            {agg_func} as agg_value
        FROM metrics
        WHERE {where_clause}
        GROUP BY host_id
        FORMAT JSON
        """

        try:
            result = await clickhouse_service.execute(query)
            rows = result.get("data", []) if result else []
        except Exception as e:
            logger.error(f"Error testing rule against ClickHouse: {e}")
            rows = []

        details = []
        hosts_triggering = 0
        overall_value = None
        values = []

        for row in rows:
            host_id = row.get("host_id", "")
            value = row.get("agg_value")
            if value is not None:
                value = float(value)
                values.append(value)

            would_trigger = self._check_condition(
                value or 0, data.operator.value, data.threshold
            ) if value is not None else False

            if would_trigger:
                hosts_triggering += 1

            details.append({
                "host_id": str(host_id),
                "hostname": str(host_id)[:8] + "...",  # ClickHouse doesn't have hostname
                "value": round(value, 2) if value else None,
                "would_trigger": would_trigger
            })

        # Calculate overall aggregated value
        if values:
            if data.aggregation.value == "avg":
                overall_value = sum(values) / len(values)
            elif data.aggregation.value == "max":
                overall_value = max(values)
            elif data.aggregation.value == "min":
                overall_value = min(values)
            elif data.aggregation.value == "sum":
                overall_value = sum(values)
            else:
                overall_value = values[0] if values else None

        would_trigger = self._check_condition(
            overall_value or 0,
            data.operator.value,
            data.threshold
        ) if overall_value is not None else False

        return AlertRuleTestResponse(
            would_trigger=would_trigger,
            current_value=round(overall_value, 2) if overall_value else None,
            threshold=data.threshold,
            operator=data.operator.value,
            hosts_checked=len(rows),
            hosts_triggering=hosts_triggering,
            details=details
        )

    async def _test_rule_postgres(
        self,
        data: AlertRuleTestRequest,
        organization_id: uuid.UUID,
        window_start: datetime,
        db: AsyncSession
    ) -> AlertRuleTestResponse:
        """Test alert rule against PostgreSQL data (fallback)."""
        # Build aggregation SQL
        agg_map = {
            "avg": "AVG(value)",
            "max": "MAX(value)",
            "min": "MIN(value)",
            "sum": "SUM(value)",
            "last": "MAX(value)"
        }
        agg_func = agg_map.get(data.aggregation.value, "AVG(value)")

        params = {
            "org_id": organization_id,
            "metric_name": data.metric_name,
            "window_start": window_start
        }

        where_clauses = [
            "m.organization_id = :org_id",
            "m.name = :metric_name",
            "m.time >= :window_start"
        ]

        if data.host_ids:
            where_clauses.append("m.host_id = ANY(:host_ids)")
            params["host_ids"] = [uuid.UUID(h) for h in data.host_ids]

        where_sql = " AND ".join(where_clauses)

        # Query per host
        sql = f"""
            SELECT
                m.host_id,
                h.hostname,
                {agg_func} as agg_value
            FROM metrics m
            JOIN hosts h ON h.id = m.host_id
            WHERE {where_sql}
            GROUP BY m.host_id, h.hostname
        """

        result = await db.execute(text(sql), params)
        rows = result.fetchall()

        details = []
        hosts_triggering = 0
        overall_value = None

        for host_id, hostname, value in rows:
            would_trigger = self._check_condition(value, data.operator.value, data.threshold)
            if would_trigger:
                hosts_triggering += 1

            details.append({
                "host_id": str(host_id),
                "hostname": hostname,
                "value": round(value, 2) if value else None,
                "would_trigger": would_trigger
            })

            if overall_value is None:
                overall_value = value

        # Calculate overall aggregated value
        if rows:
            values = [r[2] for r in rows if r[2] is not None]
            if values:
                if data.aggregation.value == "avg":
                    overall_value = sum(values) / len(values)
                elif data.aggregation.value == "max":
                    overall_value = max(values)
                elif data.aggregation.value == "min":
                    overall_value = min(values)
                elif data.aggregation.value == "sum":
                    overall_value = sum(values)

        would_trigger = self._check_condition(
            overall_value or 0,
            data.operator.value,
            data.threshold
        ) if overall_value is not None else False

        return AlertRuleTestResponse(
            would_trigger=would_trigger,
            current_value=round(overall_value, 2) if overall_value else None,
            threshold=data.threshold,
            operator=data.operator.value,
            hosts_checked=len(rows),
            hosts_triggering=hosts_triggering,
            details=details
        )

    # ============================================
    # History
    # ============================================

    async def get_rule_history(
        self,
        rule_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession,
        limit: int = 50
    ) -> AlertRuleHistoryResponse:
        """Get history of state changes for an alert rule."""
        result = await db.execute(
            select(AlertRuleHistory)
            .where(
                AlertRuleHistory.alert_rule_id == rule_id,
                AlertRuleHistory.organization_id == organization_id
            )
            .order_by(AlertRuleHistory.created_at.desc())
            .limit(limit)
        )
        history = result.scalars().all()

        return AlertRuleHistoryResponse(
            history=[
                AlertRuleHistoryItem(
                    id=str(h.id),
                    alert_rule_id=str(h.alert_rule_id),
                    previous_status=h.previous_status,
                    new_status=h.new_status,
                    triggered_value=h.triggered_value,
                    threshold=h.threshold,
                    incident_id=str(h.incident_id) if h.incident_id else None,
                    created_at=h.created_at
                )
                for h in history
            ],
            total=len(history)
        )

    # ============================================
    # Helpers
    # ============================================

    def _rule_to_response(self, rule: AlertRule) -> AlertRuleResponse:
        """Convert AlertRule model to response schema."""
        return AlertRuleResponse(
            id=str(rule.id),
            name=rule.name,
            description=rule.description,
            metric_name=rule.metric_name,
            operator=rule.operator,
            threshold=rule.threshold,
            condition_text=rule.condition_text,
            aggregation=rule.aggregation,
            evaluation_window=rule.evaluation_window,
            duration=rule.duration,
            host_ids=rule.host_ids or [],
            host_tags=rule.host_tags or {},
            severity=rule.severity,
            auto_create_incident=rule.auto_create_incident,
            auto_resolve=rule.auto_resolve,
            cooldown_seconds=rule.cooldown_seconds,
            notify_channels=rule.notify_channels or [],
            notify_users=rule.notify_users or [],
            status=rule.status,
            current_value=rule.current_value,
            last_evaluated_at=rule.last_evaluated_at,
            last_triggered_at=rule.last_triggered_at,
            last_resolved_at=rule.last_resolved_at,
            labels=rule.labels or {},
            created_at=rule.created_at,
            updated_at=rule.updated_at,
            created_by_id=str(rule.created_by_id) if rule.created_by_id else None
        )


# Missing import
import enum

# Singleton instance
alert_rule_service = AlertRuleService()
