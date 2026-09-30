# backend/app/services/nl_query_service.py
"""Service for Natural Language Query processing."""
import json
import time
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc

from app.models.nl_query import NLQueryHistory, QueryIntent, QueryStatus
from app.models.host import Host, HostStatus
from app.models.incident import Incident
from app.models.alert import Alert
from app.models.log_entry import LogEntry
from app.models.trace import Trace, Span
from app.models.deployment_event import DeploymentEvent
from app.models.organization import Organization
from app.schemas.nl_query import (
    NLQueryRequest,
    NLQueryResponse,
    QueryResultData,
    MetricResult,
    LogResult,
    IncidentResult,
    HostResult,
    TraceResult,
    AlertResult,
    DeploymentResult,
)


class NLQueryService:
    """Service for processing natural language queries."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_query(
        self,
        request: NLQueryRequest,
        organization_id: UUID,
        user_id: UUID
    ) -> NLQueryResponse:
        """
        Process a natural language query.

        1. Detect intent from query
        2. Extract parameters (time range, filters, etc.)
        3. Generate and execute structured query
        4. Format and return results
        """
        start_time = time.time()

        # Create query history record
        query_record = NLQueryHistory(
            organization_id=organization_id,
            user_id=user_id,
            query_text=request.query,
            status=QueryStatus.PENDING.value
        )
        self.db.add(query_record)
        await self.db.flush()

        try:
            # Get organization's AI settings
            org_query = select(Organization).where(Organization.id == organization_id)
            org_result = await self.db.execute(org_query)
            org = org_result.scalar_one_or_none()

            # Detect intent and extract parameters
            intent, confidence, parameters = await self._detect_intent(
                request.query,
                org
            )

            query_record.intent = intent.value
            query_record.confidence = confidence
            query_record.query_parameters = parameters

            # Execute query based on intent
            result_data, result_count = await self._execute_query(
                intent,
                parameters,
                organization_id
            )

            # Generate result summary
            result_summary = self._generate_summary(
                intent,
                result_count,
                parameters
            )

            # Calculate execution time
            execution_time_ms = int((time.time() - start_time) * 1000)

            # Update query record
            query_record.result_count = result_count
            query_record.result_summary = result_summary
            query_record.result_data = result_data.model_dump() if result_data else {}
            query_record.execution_time_ms = execution_time_ms
            query_record.status = QueryStatus.COMPLETED.value

            await self.db.commit()
            await self.db.refresh(query_record)

            return NLQueryResponse(
                id=query_record.id,
                query_text=query_record.query_text,
                intent=intent,
                confidence=confidence,
                status=QueryStatus.COMPLETED,
                result_count=result_count,
                result_summary=result_summary,
                result_data=result_data,
                execution_time_ms=execution_time_ms,
                generated_query=parameters,
                created_at=query_record.created_at
            )

        except Exception as e:
            query_record.status = QueryStatus.FAILED.value
            query_record.error_message = str(e)
            await self.db.commit()

            return NLQueryResponse(
                id=query_record.id,
                query_text=query_record.query_text,
                intent=QueryIntent.GENERAL,
                confidence=0.0,
                status=QueryStatus.FAILED,
                result_count=0,
                error_message=str(e),
                created_at=query_record.created_at
            )

    async def _detect_intent(
        self,
        query: str,
        org: Optional[Organization]
    ) -> Tuple[QueryIntent, float, Dict[str, Any]]:
        """
        Detect intent from natural language query.

        Uses keyword matching and pattern recognition.
        Falls back to AI for complex queries if configured.
        """
        query_lower = query.lower()
        parameters = {}

        # Extract time range
        time_range = self._extract_time_range(query_lower)
        if time_range:
            parameters['time_range'] = time_range

        # Extract service/host names
        service_match = re.search(r'(?:service|app|application)\s+["\']?(\w+)["\']?', query_lower)
        if service_match:
            parameters['service_name'] = service_match.group(1)

        host_match = re.search(r'(?:host|server|machine)\s+["\']?(\w+)["\']?', query_lower)
        if host_match:
            parameters['host_name'] = host_match.group(1)

        # Detect intent based on keywords
        # Metrics queries
        if any(kw in query_lower for kw in ['cpu', 'memory', 'disk', 'usage', 'metrics', 'performance']):
            # Check for host-specific queries
            if any(kw in query_lower for kw in ['host', 'server', 'machine', 'high memory', 'high cpu']):
                return QueryIntent.HOST_STATUS, 0.9, parameters
            return QueryIntent.METRICS_QUERY, 0.85, parameters

        # Log queries
        if any(kw in query_lower for kw in ['log', 'logs', 'error log', 'find log']):
            # Extract log level if mentioned
            for level in ['error', 'warn', 'warning', 'info', 'debug']:
                if level in query_lower:
                    parameters['log_level'] = level.upper()
                    break
            # Extract search term
            search_match = re.search(r'(?:containing|with|about|for)\s+["\']?(.+?)["\']?(?:\s+in|\s+from|$)', query_lower)
            if search_match:
                parameters['search_term'] = search_match.group(1).strip()
            return QueryIntent.LOG_SEARCH, 0.9, parameters

        # Incident queries
        if any(kw in query_lower for kw in ['incident', 'incidents', 'outage', 'issue']):
            # Extract status if mentioned
            for status in ['open', 'resolved', 'acknowledged', 'closed']:
                if status in query_lower:
                    parameters['status'] = status
                    break
            # Extract severity if mentioned
            for severity in ['critical', 'high', 'medium', 'low']:
                if severity in query_lower:
                    parameters['severity'] = severity
                    break
            return QueryIntent.INCIDENT_LOOKUP, 0.9, parameters

        # Alert queries
        if any(kw in query_lower for kw in ['alert', 'alerts', 'alarm', 'notification', 'fire', 'fired', 'trigger']):
            for severity in ['critical', 'high', 'medium', 'low']:
                if severity in query_lower:
                    parameters['severity'] = severity
                    break
            return QueryIntent.ALERT_SEARCH, 0.9, parameters

        # Trace queries
        if any(kw in query_lower for kw in ['trace', 'traces', 'span', 'latency', 'slow request', 'slow trace']):
            # Extract latency threshold
            latency_match = re.search(r'(\d+)\s*(?:ms|millisecond|second|s)', query_lower)
            if latency_match:
                value = int(latency_match.group(1))
                # Convert to ms if seconds
                if 'second' in query_lower or query_lower[latency_match.end()-1] == 's':
                    if value < 100:  # Likely seconds
                        value *= 1000
                parameters['min_duration_ms'] = value
            return QueryIntent.TRACE_SEARCH, 0.85, parameters

        # Host status queries
        if any(kw in query_lower for kw in ['host', 'server', 'machine', 'infrastructure']):
            # Extract status filter
            if 'inactive' in query_lower or 'offline' in query_lower or 'down' in query_lower:
                parameters['status'] = 'inactive'
            elif 'active' in query_lower or 'online' in query_lower or 'up' in query_lower:
                parameters['status'] = 'active'
            return QueryIntent.HOST_STATUS, 0.9, parameters

        # Deployment queries
        if any(kw in query_lower for kw in ['deploy', 'deployment', 'release', 'rollout', 'shipped']):
            return QueryIntent.DEPLOYMENT_LOOKUP, 0.9, parameters

        # Service status queries
        if any(kw in query_lower for kw in ['service', 'how is', 'status of', 'health of']):
            return QueryIntent.SERVICE_STATUS, 0.7, parameters

        # Default to general
        return QueryIntent.GENERAL, 0.5, parameters

    def _extract_time_range(self, query: str) -> Optional[Dict[str, datetime]]:
        """Extract time range from query."""
        now = datetime.utcnow()

        # Pattern: "last X hours/days/weeks"
        last_match = re.search(r'(?:last|past)\s+(\d+)\s+(hour|day|week|minute)s?', query)
        if last_match:
            value = int(last_match.group(1))
            unit = last_match.group(2)
            if unit == 'minute':
                start = now - timedelta(minutes=value)
            elif unit == 'hour':
                start = now - timedelta(hours=value)
            elif unit == 'day':
                start = now - timedelta(days=value)
            elif unit == 'week':
                start = now - timedelta(weeks=value)
            return {'start': start, 'end': now}

        # Pattern: "today", "yesterday", "this week"
        if 'today' in query:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return {'start': start, 'end': now}
        if 'yesterday' in query:
            start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return {'start': start, 'end': end}
        if 'this week' in query:
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            return {'start': start, 'end': now}

        # Default to last 24 hours
        return {'start': now - timedelta(hours=24), 'end': now}

    async def _execute_query(
        self,
        intent: QueryIntent,
        parameters: Dict[str, Any],
        organization_id: UUID
    ) -> Tuple[Optional[QueryResultData], int]:
        """Execute query based on detected intent."""

        if intent == QueryIntent.HOST_STATUS:
            return await self._query_hosts(parameters, organization_id)

        if intent == QueryIntent.INCIDENT_LOOKUP:
            return await self._query_incidents(parameters, organization_id)

        if intent == QueryIntent.ALERT_SEARCH:
            return await self._query_alerts(parameters, organization_id)

        if intent == QueryIntent.LOG_SEARCH:
            return await self._query_logs(parameters, organization_id)

        if intent == QueryIntent.TRACE_SEARCH:
            return await self._query_traces(parameters, organization_id)

        if intent == QueryIntent.DEPLOYMENT_LOOKUP:
            return await self._query_deployments(parameters, organization_id)

        # Default empty result
        return QueryResultData(), 0

    async def _query_hosts(
        self,
        parameters: Dict[str, Any],
        organization_id: UUID
    ) -> Tuple[QueryResultData, int]:
        """Query hosts based on parameters."""
        query = select(Host).where(Host.organization_id == organization_id)

        # Apply status filter
        if 'status' in parameters:
            status_value = parameters['status']
            if status_value == 'active':
                query = query.where(Host.status == HostStatus.ACTIVE)
            elif status_value == 'inactive':
                query = query.where(Host.status == HostStatus.INACTIVE)

        # Apply host name filter
        if 'host_name' in parameters:
            query = query.where(Host.hostname.ilike(f"%{parameters['host_name']}%"))

        # Order by resource usage for "high memory/cpu" queries
        query = query.order_by(desc(Host.memory_percent))
        query = query.limit(50)

        result = await self.db.execute(query)
        hosts = result.scalars().all()

        host_results = [
            HostResult(
                id=h.id,
                hostname=h.hostname,
                status=h.status.value if h.status else 'unknown',
                cpu_percent=h.cpu_percent,
                memory_percent=h.memory_percent,
                disk_percent=h.disk_percent,
                last_seen_at=h.last_seen_at
            )
            for h in hosts
        ]

        return QueryResultData(hosts=host_results), len(host_results)

    async def _query_incidents(
        self,
        parameters: Dict[str, Any],
        organization_id: UUID
    ) -> Tuple[QueryResultData, int]:
        """Query incidents based on parameters."""
        query = select(Incident).where(Incident.organization_id == organization_id)

        # Apply time range
        if 'time_range' in parameters:
            time_range = parameters['time_range']
            query = query.where(Incident.created_at >= time_range['start'])
            query = query.where(Incident.created_at <= time_range['end'])

        # Apply status filter
        if 'status' in parameters:
            query = query.where(Incident.status == parameters['status'])

        # Apply severity filter
        if 'severity' in parameters:
            query = query.where(Incident.severity == parameters['severity'])

        query = query.order_by(desc(Incident.created_at))
        query = query.limit(50)

        result = await self.db.execute(query)
        incidents = result.scalars().all()

        incident_results = [
            IncidentResult(
                id=i.id,
                title=i.title,
                severity=i.severity,
                status=i.status,
                created_at=i.created_at,
                resolved_at=i.resolved_at
            )
            for i in incidents
        ]

        return QueryResultData(incidents=incident_results), len(incident_results)

    async def _query_alerts(
        self,
        parameters: Dict[str, Any],
        organization_id: UUID
    ) -> Tuple[QueryResultData, int]:
        """Query alerts based on parameters."""
        query = select(Alert).where(Alert.organization_id == organization_id)

        # Apply time range
        if 'time_range' in parameters:
            time_range = parameters['time_range']
            query = query.where(Alert.created_at >= time_range['start'])
            query = query.where(Alert.created_at <= time_range['end'])

        # Apply severity filter
        if 'severity' in parameters:
            query = query.where(Alert.severity == parameters['severity'])

        query = query.order_by(desc(Alert.created_at))
        query = query.limit(50)

        result = await self.db.execute(query)
        alerts = result.scalars().all()

        alert_results = [
            AlertResult(
                id=a.id,
                title=a.title,
                severity=a.severity,
                status=a.status,
                source=a.source or 'unknown',
                created_at=a.created_at
            )
            for a in alerts
        ]

        return QueryResultData(alerts=alert_results), len(alert_results)

    async def _query_logs(
        self,
        parameters: Dict[str, Any],
        organization_id: UUID
    ) -> Tuple[QueryResultData, int]:
        """Query logs based on parameters."""
        query = select(LogEntry).where(LogEntry.organization_id == organization_id)

        # Apply time range
        if 'time_range' in parameters:
            time_range = parameters['time_range']
            query = query.where(LogEntry.timestamp >= time_range['start'])
            query = query.where(LogEntry.timestamp <= time_range['end'])

        # Apply log level filter
        if 'log_level' in parameters:
            query = query.where(LogEntry.level == parameters['log_level'])

        # Apply service filter
        if 'service_name' in parameters:
            query = query.where(LogEntry.service_name.ilike(f"%{parameters['service_name']}%"))

        # Apply search term
        if 'search_term' in parameters:
            query = query.where(LogEntry.message.ilike(f"%{parameters['search_term']}%"))

        query = query.order_by(desc(LogEntry.timestamp))
        query = query.limit(100)

        result = await self.db.execute(query)
        logs = result.scalars().all()

        log_results = [
            LogResult(
                timestamp=log.timestamp,
                level=log.level.value if hasattr(log.level, 'value') else str(log.level),
                message=log.message,
                service_name=log.service_name,
                host_name=log.host_name,
                trace_id=log.trace_id
            )
            for log in logs
        ]

        return QueryResultData(logs=log_results), len(log_results)

    async def _query_traces(
        self,
        parameters: Dict[str, Any],
        organization_id: UUID
    ) -> Tuple[QueryResultData, int]:
        """Query traces based on parameters."""
        query = select(Trace).where(Trace.organization_id == organization_id)

        # Apply time range
        if 'time_range' in parameters:
            time_range = parameters['time_range']
            query = query.where(Trace.start_time >= time_range['start'])
            query = query.where(Trace.start_time <= time_range['end'])

        # Apply service filter
        if 'service_name' in parameters:
            query = query.where(Trace.root_service_name.ilike(f"%{parameters['service_name']}%"))

        # Apply minimum duration filter
        if 'min_duration_ms' in parameters:
            query = query.where(Trace.duration_ms >= parameters['min_duration_ms'])

        query = query.order_by(desc(Trace.duration_ms))
        query = query.limit(50)

        result = await self.db.execute(query)
        traces = result.scalars().all()

        trace_results = [
            TraceResult(
                trace_id=str(t.trace_id),
                service_name=t.root_service_name or 'unknown',
                operation_name=t.root_operation_name or 'unknown',
                duration_ms=t.duration_ms or 0,
                status=t.status.value if hasattr(t.status, 'value') else str(t.status or 'ok'),
                timestamp=t.start_time
            )
            for t in traces
        ]

        return QueryResultData(traces=trace_results), len(trace_results)

    async def _query_deployments(
        self,
        parameters: Dict[str, Any],
        organization_id: UUID
    ) -> Tuple[QueryResultData, int]:
        """Query deployments based on parameters."""
        query = select(DeploymentEvent).where(DeploymentEvent.organization_id == organization_id)

        # Apply time range
        if 'time_range' in parameters:
            time_range = parameters['time_range']
            query = query.where(DeploymentEvent.deployed_at >= time_range['start'])
            query = query.where(DeploymentEvent.deployed_at <= time_range['end'])

        # Apply service filter
        if 'service_name' in parameters:
            query = query.where(DeploymentEvent.service_name.ilike(f"%{parameters['service_name']}%"))

        query = query.order_by(desc(DeploymentEvent.deployed_at))
        query = query.limit(50)

        result = await self.db.execute(query)
        deployments = result.scalars().all()

        deployment_results = [
            DeploymentResult(
                id=d.id,
                service_name=d.service_name,
                version=d.version,
                status=d.status.value if hasattr(d.status, 'value') else str(d.status),
                deployed_at=d.deployed_at,
                deployed_by=d.deployed_by
            )
            for d in deployments
        ]

        return QueryResultData(deployments=deployment_results), len(deployment_results)

    def _generate_summary(
        self,
        intent: QueryIntent,
        result_count: int,
        parameters: Dict[str, Any]
    ) -> str:
        """Generate a human-readable summary of results."""
        if result_count == 0:
            return f"No results found for your query."

        time_desc = ""
        if 'time_range' in parameters:
            time_range = parameters['time_range']
            start = time_range['start']
            end = time_range['end']
            delta = end - start
            if delta.days > 0:
                time_desc = f" in the last {delta.days} day(s)"
            elif delta.seconds >= 3600:
                time_desc = f" in the last {delta.seconds // 3600} hour(s)"
            else:
                time_desc = f" in the last {delta.seconds // 60} minute(s)"

        if intent == QueryIntent.HOST_STATUS:
            return f"Found {result_count} host(s){time_desc}."

        if intent == QueryIntent.INCIDENT_LOOKUP:
            status = parameters.get('status', 'all')
            severity = parameters.get('severity')
            desc = f"Found {result_count} {status} incident(s)"
            if severity:
                desc += f" with {severity} severity"
            return desc + time_desc + "."

        if intent == QueryIntent.ALERT_SEARCH:
            severity = parameters.get('severity')
            desc = f"Found {result_count} alert(s)"
            if severity:
                desc += f" with {severity} severity"
            return desc + time_desc + "."

        if intent == QueryIntent.LOG_SEARCH:
            level = parameters.get('log_level')
            desc = f"Found {result_count} log entr{'y' if result_count == 1 else 'ies'}"
            if level:
                desc += f" at {level} level"
            return desc + time_desc + "."

        if intent == QueryIntent.TRACE_SEARCH:
            min_duration = parameters.get('min_duration_ms')
            desc = f"Found {result_count} trace(s)"
            if min_duration:
                desc += f" with duration >= {min_duration}ms"
            return desc + time_desc + "."

        if intent == QueryIntent.DEPLOYMENT_LOOKUP:
            return f"Found {result_count} deployment(s){time_desc}."

        return f"Found {result_count} result(s){time_desc}."

    async def get_query_history(
        self,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
        limit: int = 20
    ) -> List[NLQueryHistory]:
        """Get query history for an organization/user."""
        query = select(NLQueryHistory).where(
            NLQueryHistory.organization_id == organization_id
        )

        if user_id:
            query = query.where(NLQueryHistory.user_id == user_id)

        query = query.order_by(desc(NLQueryHistory.created_at))
        query = query.limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def submit_feedback(
        self,
        query_id: UUID,
        organization_id: UUID,
        helpful: bool,
        comment: Optional[str] = None
    ) -> Optional[NLQueryHistory]:
        """Submit feedback for a query."""
        query = select(NLQueryHistory).where(
            NLQueryHistory.id == query_id,
            NLQueryHistory.organization_id == organization_id
        )
        result = await self.db.execute(query)
        query_record = result.scalar_one_or_none()

        if query_record:
            query_record.feedback_helpful = helpful
            query_record.feedback_comment = comment
            await self.db.commit()
            await self.db.refresh(query_record)

        return query_record

    def get_suggested_queries(self) -> List[Dict[str, str]]:
        """Get suggested queries to help users get started."""
        return [
            {
                "query": "Show me hosts with high memory usage",
                "description": "Find hosts using the most memory",
                "intent": QueryIntent.HOST_STATUS.value
            },
            {
                "query": "What incidents happened today?",
                "description": "List all incidents from today",
                "intent": QueryIntent.INCIDENT_LOOKUP.value
            },
            {
                "query": "Find error logs from the last hour",
                "description": "Search for recent error logs",
                "intent": QueryIntent.LOG_SEARCH.value
            },
            {
                "query": "Show me slow traces over 1 second",
                "description": "Find traces with high latency",
                "intent": QueryIntent.TRACE_SEARCH.value
            },
            {
                "query": "What alerts fired this week?",
                "description": "List recent alerts",
                "intent": QueryIntent.ALERT_SEARCH.value
            },
            {
                "query": "What was deployed yesterday?",
                "description": "View recent deployments",
                "intent": QueryIntent.DEPLOYMENT_LOOKUP.value
            },
        ]
