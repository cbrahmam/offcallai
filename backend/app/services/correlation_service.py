# backend/app/services/correlation_service.py
"""Service for AI-powered incident-telemetry correlation."""
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import anthropic

from app.models.incident import Incident
from app.models.api_keys import APIKey
from app.services.clickhouse_service import ClickHouseService
from app.schemas.correlation import (
    CorrelatedTelemetryResponse,
    CorrelatedTrace,
    CorrelatedLog,
    AICorrelationResult,
)

logger = logging.getLogger(__name__)


class CorrelationService:
    """
    Service for correlating incidents with traces and logs using AI.

    Uses Claude to intelligently identify relevant telemetry based on:
    - Error patterns
    - Service relationships
    - Timing correlation
    - Semantic similarity
    """

    def __init__(self, db: AsyncSession, clickhouse: Optional[ClickHouseService] = None):
        self.db = db
        self.clickhouse = clickhouse or ClickHouseService()

    async def get_correlated_telemetry(
        self,
        incident_id: UUID,
        organization_id: UUID,
        window_hours: float = 1.0
    ) -> CorrelatedTelemetryResponse:
        """
        Get AI-correlated traces and logs for an incident.

        1. Fetches incident details
        2. Queries traces/logs in time window around incident
        3. Uses Claude to analyze and rank relevance
        4. Returns correlated telemetry with AI analysis
        """
        start_time = time.time()

        # 1. Get incident
        incident = await self._get_incident(incident_id, organization_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")

        # Calculate time window
        incident_time = incident.created_at
        if incident_time.tzinfo is None:
            incident_time = incident_time.replace(tzinfo=timezone.utc)

        window_start = incident_time - timedelta(hours=window_hours)
        window_end = incident_time + timedelta(hours=window_hours)

        # 2. Fetch traces and logs from ClickHouse
        traces_data = await self._fetch_traces(
            organization_id, window_start, window_end
        )
        logs_data = await self._fetch_logs(
            organization_id, window_start, window_end
        )

        # 3. Get Claude API key for this org
        claude_key = await self._get_claude_api_key(organization_id)

        # 4. Analyze with Claude
        if claude_key and (traces_data or logs_data):
            ai_result = await self._analyze_with_claude(
                incident, traces_data, logs_data, claude_key
            )
        else:
            # Fallback: time-based correlation without AI
            ai_result = self._fallback_correlation(
                incident, traces_data, logs_data
            )

        # 5. Build correlated traces/logs with relevance scores
        correlated_traces = self._build_correlated_traces(
            traces_data, ai_result.related_trace_ids
        )
        correlated_logs = self._build_correlated_logs(
            logs_data, ai_result.related_log_timestamps
        )

        analysis_time = (time.time() - start_time) * 1000

        return CorrelatedTelemetryResponse(
            incident_id=incident_id,
            incident_title=incident.title,
            incident_time=incident_time,
            ai_analysis=ai_result,
            traces=correlated_traces,
            logs=correlated_logs,
            analysis_time_ms=analysis_time,
            telemetry_window_hours=window_hours,
            total_traces_analyzed=len(traces_data),
            total_logs_analyzed=len(logs_data),
        )

    async def _get_incident(
        self, incident_id: UUID, organization_id: UUID
    ) -> Optional[Incident]:
        """Fetch incident from database."""
        result = await self.db.execute(
            select(Incident).where(
                Incident.id == incident_id,
                Incident.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def _fetch_traces(
        self,
        organization_id: UUID,
        start_time: datetime,
        end_time: datetime,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Fetch traces from ClickHouse."""
        try:
            query = f"""
                SELECT
                    trace_id,
                    service_name,
                    operation_name,
                    duration_ms,
                    status_code,
                    toString(timestamp) as timestamp,
                    attributes
                FROM offcall.spans
                WHERE organization_id = '{organization_id}'
                    AND timestamp >= '{start_time.strftime('%Y-%m-%d %H:%M:%S')}'
                    AND timestamp <= '{end_time.strftime('%Y-%m-%d %H:%M:%S')}'
                ORDER BY timestamp DESC
                LIMIT {limit}
            """
            result = await self.clickhouse.execute_query(query)
            return result if result else []
        except Exception as e:
            logger.error(f"Failed to fetch traces: {e}")
            return []

    async def _fetch_logs(
        self,
        organization_id: UUID,
        start_time: datetime,
        end_time: datetime,
        limit: int = 200
    ) -> List[Dict[str, Any]]:
        """Fetch logs from ClickHouse."""
        try:
            query = f"""
                SELECT
                    toString(timestamp) as timestamp,
                    service,
                    level,
                    message,
                    toString(host_id) as host_id,
                    trace_id
                FROM offcall.logs
                WHERE organization_id = '{organization_id}'
                    AND timestamp >= '{start_time.strftime('%Y-%m-%d %H:%M:%S')}'
                    AND timestamp <= '{end_time.strftime('%Y-%m-%d %H:%M:%S')}'
                ORDER BY timestamp DESC
                LIMIT {limit}
            """
            result = await self.clickhouse.execute_query(query)
            return result if result else []
        except Exception as e:
            logger.error(f"Failed to fetch logs: {e}")
            return []

    async def _get_claude_api_key(self, organization_id: UUID) -> Optional[str]:
        """Get Claude API key for organization."""
        result = await self.db.execute(
            select(APIKey).where(
                APIKey.organization_id == organization_id,
                APIKey.provider == 'claude',
                APIKey.is_valid == True
            )
        )
        api_key = result.scalar_one_or_none()
        return api_key.api_key if api_key else None

    async def _analyze_with_claude(
        self,
        incident: Incident,
        traces: List[Dict[str, Any]],
        logs: List[Dict[str, Any]],
        api_key: str
    ) -> AICorrelationResult:
        """Use Claude to analyze and correlate telemetry."""
        try:
            client = anthropic.Anthropic(api_key=api_key)

            # Format telemetry for the prompt
            traces_text = self._format_traces_for_prompt(traces[:50])
            logs_text = self._format_logs_for_prompt(logs[:100])

            prompt = f"""You are a Senior Site Reliability Engineer preparing a Root Cause Analysis report for an engineering team.

## INCIDENT DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Title: {incident.title}
Description: {incident.description or 'No description provided'}
Affected Service: {incident.service or 'Unknown'}
Severity: {incident.severity}
Status: {incident.status}
Incident Time: {incident.created_at}

## TELEMETRY DATA (within ±1 hour window)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Distributed Traces:
{traces_text}

### Application Logs:
{logs_text}

## ANALYSIS REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Analyze the telemetry data and provide a professional engineering report with:

1. **Root Cause Hypothesis**: A clear, technical explanation of the probable root cause. Be specific about the failure mode, affected components, and the chain of events.

2. **Evidence Correlation**: Identify which traces and logs directly support your hypothesis. Explain the technical reasoning.

3. **Impact Assessment**: What systems/users were affected and how.

4. **Recommended Actions**: Prioritized, actionable remediation steps with technical specifics.

Write in a professional, concise style suitable for an engineering post-incident review.

## OUTPUT FORMAT
Respond with ONLY this JSON structure:
{{
  "root_cause_hypothesis": "Technical explanation of the root cause. Example: 'Database connection pool exhaustion caused by a connection leak in the user-service v2.3.1 deployment. The leak occurred when database transactions were not properly closed in error handling paths, leading to gradual pool depletion over 47 minutes until all 50 connections were consumed.'",
  "confidence": 0.85,
  "related_trace_ids": ["trace_id_1", "trace_id_2"],
  "related_log_timestamps": ["2024-01-28T10:30:00Z"],
  "analysis_summary": "Concise 1-2 sentence summary of findings",
  "recommended_actions": [
    "IMMEDIATE: [Specific technical action]",
    "SHORT-TERM: [Follow-up remediation]",
    "LONG-TERM: [Preventive measure]"
  ]
}}"""

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse response
            response_text = response.content[0].text.strip()

            # Try to extract JSON from the response
            try:
                # Handle potential markdown code blocks
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0]
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0]

                result_data = json.loads(response_text)

                return AICorrelationResult(
                    root_cause_hypothesis=result_data.get("root_cause_hypothesis", "Unable to determine root cause"),
                    confidence=float(result_data.get("confidence", 0.5)),
                    related_trace_ids=result_data.get("related_trace_ids", []),
                    related_log_timestamps=result_data.get("related_log_timestamps", []),
                    analysis_summary=result_data.get("analysis_summary", "Analysis complete"),
                    recommended_actions=result_data.get("recommended_actions"),
                )
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse Claude response as JSON: {response_text[:200]}")
                return self._extract_from_text(response_text, traces, logs)

        except Exception as e:
            logger.error(f"Claude analysis failed: {e}")
            return self._fallback_correlation(incident, traces, logs)

    def _format_traces_for_prompt(self, traces: List[Dict[str, Any]]) -> str:
        """Format traces for Claude prompt."""
        if not traces:
            return "No traces available in this time window."

        lines = []
        for t in traces:
            status = t.get('status_code', 'UNKNOWN')
            duration = t.get('duration_ms', 0)
            error_indicator = " [ERROR]" if status == 'ERROR' else ""
            slow_indicator = " [SLOW]" if duration > 1000 else ""

            lines.append(
                f"[{t.get('trace_id', 'N/A')[:12]}] "
                f"{t.get('service_name', 'unknown')} / {t.get('operation_name', 'unknown')} "
                f"({duration:.0f}ms) {status}{error_indicator}{slow_indicator}"
            )
        return "\n".join(lines)

    def _format_logs_for_prompt(self, logs: List[Dict[str, Any]]) -> str:
        """Format logs for Claude prompt."""
        if not logs:
            return "No logs available in this time window."

        lines = []
        for log in logs:
            level = log.get('level', 'INFO')
            level_indicator = ""
            if level in ['ERROR', 'FATAL', 'CRITICAL']:
                level_indicator = " [!]"
            elif level == 'WARN':
                level_indicator = " [?]"

            message = log.get('message', '')
            if len(message) > 150:
                message = message[:150] + "..."

            lines.append(
                f"[{log.get('timestamp', '')}] [{level}]{level_indicator} "
                f"{log.get('service', 'unknown')}: {message}"
            )
        return "\n".join(lines)

    def _extract_from_text(
        self,
        text: str,
        traces: List[Dict[str, Any]],
        logs: List[Dict[str, Any]]
    ) -> AICorrelationResult:
        """Extract correlation result from non-JSON Claude response."""
        # Fallback: extract trace IDs mentioned in the text
        related_trace_ids = []
        for t in traces:
            trace_id = t.get('trace_id', '')
            if trace_id and trace_id[:12] in text:
                related_trace_ids.append(trace_id)

        # Look for error logs
        related_log_timestamps = []
        for log in logs:
            if log.get('level') in ['ERROR', 'FATAL', 'CRITICAL']:
                ts = log.get('timestamp')
                if ts:
                    related_log_timestamps.append(str(ts))

        return AICorrelationResult(
            root_cause_hypothesis=text[:500] if text else "Analysis inconclusive",
            confidence=0.5,
            related_trace_ids=related_trace_ids[:10],
            related_log_timestamps=related_log_timestamps[:20],
            analysis_summary="Extracted from text analysis",
            recommended_actions=None,
        )

    def _fallback_correlation(
        self,
        incident: Incident,
        traces: List[Dict[str, Any]],
        logs: List[Dict[str, Any]]
    ) -> AICorrelationResult:
        """Fallback correlation when AI is unavailable."""
        # Simple heuristic: find error traces and error logs
        related_trace_ids = []
        for t in traces:
            if t.get('status_code') == 'ERROR':
                related_trace_ids.append(t.get('trace_id', ''))
            # Also include traces matching incident service
            if incident.service and t.get('service_name') == incident.service:
                related_trace_ids.append(t.get('trace_id', ''))

        related_log_timestamps = []
        for log in logs:
            if log.get('level') in ['ERROR', 'FATAL', 'CRITICAL', 'WARN']:
                ts = log.get('timestamp')
                if ts:
                    related_log_timestamps.append(str(ts))

        # Deduplicate
        related_trace_ids = list(set(related_trace_ids))[:10]
        related_log_timestamps = list(set(related_log_timestamps))[:20]

        return AICorrelationResult(
            root_cause_hypothesis="Unable to determine root cause (AI analysis unavailable). Review error traces and logs manually.",
            confidence=0.3,
            related_trace_ids=related_trace_ids,
            related_log_timestamps=related_log_timestamps,
            analysis_summary="Time-based correlation (AI unavailable - add Claude API key for intelligent analysis)",
            recommended_actions=[
                "Review error traces marked below",
                "Check error logs for stack traces",
                "Add Claude API key for AI-powered analysis"
            ],
        )

    def _build_correlated_traces(
        self,
        traces: List[Dict[str, Any]],
        related_ids: List[str]
    ) -> List[CorrelatedTrace]:
        """Build correlated trace objects with relevance scores."""
        correlated = []
        related_set = set(related_ids)

        for t in traces:
            trace_id = t.get('trace_id', '')
            is_related = trace_id in related_set
            is_error = t.get('status_code') == 'ERROR'

            # Calculate relevance score
            relevance = 0.0
            reason = []
            if is_related:
                relevance += 0.7
                reason.append("AI identified as related")
            if is_error:
                relevance += 0.2
                reason.append("Contains error")
            if t.get('duration_ms', 0) > 1000:
                relevance += 0.1
                reason.append("Slow response")

            relevance = min(relevance, 1.0)

            # Parse timestamp
            ts = t.get('timestamp', '')
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                except:
                    ts = datetime.now(timezone.utc)

            correlated.append(CorrelatedTrace(
                trace_id=trace_id,
                service_name=t.get('service_name', 'unknown'),
                operation_name=t.get('operation_name'),
                duration_ms=float(t.get('duration_ms', 0)),
                status_code=t.get('status_code', 'UNKNOWN'),
                error_message=t.get('attributes', {}).get('error.message') if isinstance(t.get('attributes'), dict) else None,
                timestamp=ts,
                relevance_score=relevance,
                relevance_reason="; ".join(reason) if reason else None,
            ))

        # Sort by relevance
        correlated.sort(key=lambda x: x.relevance_score, reverse=True)
        return correlated[:20]  # Return top 20

    def _build_correlated_logs(
        self,
        logs: List[Dict[str, Any]],
        related_timestamps: List[str]
    ) -> List[CorrelatedLog]:
        """Build correlated log objects with relevance scores."""
        correlated = []
        related_set = set(related_timestamps)

        for log in logs:
            ts_str = str(log.get('timestamp', ''))
            is_related = ts_str in related_set
            level = log.get('level', 'INFO')
            is_error = level in ['ERROR', 'FATAL', 'CRITICAL']

            # Calculate relevance score
            relevance = 0.0
            reason = []
            if is_related:
                relevance += 0.7
                reason.append("AI identified as related")
            if is_error:
                relevance += 0.25
                reason.append("Error level")
            elif level == 'WARN':
                relevance += 0.1
                reason.append("Warning level")

            relevance = min(relevance, 1.0)

            # Parse timestamp
            ts = log.get('timestamp', '')
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                except:
                    ts = datetime.now(timezone.utc)

            correlated.append(CorrelatedLog(
                timestamp=ts,
                service=log.get('service', 'unknown'),
                level=level,
                message=log.get('message', '')[:500],
                relevance_score=relevance,
                relevance_reason="; ".join(reason) if reason else None,
                host_id=log.get('host_id'),
            ))

        # Sort by relevance
        correlated.sort(key=lambda x: x.relevance_score, reverse=True)
        return correlated[:30]  # Return top 30
