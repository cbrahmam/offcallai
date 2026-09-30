# backend/app/services/ai_rca_service.py
"""
AI Root Cause Analysis Service

Automatically correlates metrics, logs, traces, and deployments
to identify the root cause of incidents using AI.
"""
import aiohttp
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
import logging

from app.models.ai_root_cause_analysis import AIRootCauseAnalysis, AnalysisStatus
from app.models.incident import Incident
from app.models.alert import Alert
from app.models.log_entry import LogEntry
from app.models.trace import Span
from app.models.host import Host
from app.models.deployment_event import DeploymentEvent
from app.schemas.ai_rca import (
    AnalysisRequest, AnalysisResponse, AnalysisStartResponse,
    AnalysisContext, TimelineEvent, RecommendedAction,
    AnalysisStatus as SchemaStatus, RootCauseCategory
)

logger = logging.getLogger(__name__)


class AIRootCauseAnalysisService:
    """Service for AI-powered root cause analysis."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze_incident(
        self,
        incident_id: UUID,
        organization_id: UUID,
        user_id: UUID,
        request: AnalysisRequest
    ) -> AnalysisStartResponse:
        """
        Trigger AI root cause analysis for an incident.

        1. Creates analysis record
        2. Gathers context (metrics, logs, traces, deployments, alerts)
        3. Calls AI provider
        4. Stores results

        Returns immediately with analysis ID - check status via get_analysis()
        """
        # Get incident
        incident = await self._get_incident(incident_id, organization_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")

        # Check for existing analysis
        existing = await self._get_existing_analysis(incident_id, organization_id)
        if existing and existing.status in [AnalysisStatus.PENDING, AnalysisStatus.ANALYZING]:
            return AnalysisStartResponse(
                analysis_id=existing.id,
                status=SchemaStatus(existing.status.value),
                message="Analysis already in progress",
                context_gathered=AnalysisContext()
            )

        # Create analysis record
        analysis = AIRootCauseAnalysis(
            organization_id=organization_id,
            incident_id=incident_id,
            requested_by_id=user_id,
            status=AnalysisStatus.PENDING
        )
        self.db.add(analysis)
        await self.db.commit()
        await self.db.refresh(analysis)

        # Gather context
        context = await self._gather_context(
            incident=incident,
            organization_id=organization_id,
            time_window_minutes=request.time_window_minutes,
            include_metrics=request.include_metrics,
            include_logs=request.include_logs,
            include_traces=request.include_traces,
            include_deployments=request.include_deployments
        )

        # Store context
        analysis.context_metrics = context.get("metrics", {})
        analysis.context_logs = context.get("logs", {})
        analysis.context_traces = context.get("traces", {})
        analysis.context_deployments = context.get("deployments", {})
        analysis.context_alerts = context.get("alerts", {})
        analysis.status = AnalysisStatus.ANALYZING
        await self.db.commit()

        # Perform analysis (async)
        try:
            start_time = time.time()
            result = await self._perform_analysis(
                analysis=analysis,
                incident=incident,
                context=context,
                organization_id=organization_id,
                provider=request.provider
            )
            duration_ms = int((time.time() - start_time) * 1000)

            if result:
                analysis.status = AnalysisStatus.COMPLETED
                analysis.root_cause = result.get("root_cause")
                analysis.root_cause_confidence = result.get("confidence", 0.7)
                analysis.root_cause_category = result.get("category", "unknown")
                analysis.contributing_factors = result.get("contributing_factors", [])
                analysis.affected_services = result.get("affected_services", [])
                analysis.timeline_of_events = result.get("timeline", [])
                analysis.recommended_actions = result.get("recommendations", [])
                analysis.provider = result.get("provider")
                analysis.model = result.get("model")
                analysis.tokens_used = result.get("tokens_used")
                analysis.raw_response = result.get("raw_response", {})
                analysis.analysis_duration_ms = duration_ms
                analysis.completed_at = datetime.utcnow()
            else:
                analysis.status = AnalysisStatus.FAILED
                analysis.error_message = "AI analysis returned no results"

        except Exception as e:
            logger.error(f"Analysis failed for incident {incident_id}: {e}")
            analysis.status = AnalysisStatus.FAILED
            analysis.error_message = str(e)

        await self.db.commit()
        await self.db.refresh(analysis)

        context_summary = AnalysisContext(
            metrics_count=len(context.get("metrics", {}).get("data", [])),
            logs_count=len(context.get("logs", {}).get("entries", [])),
            traces_count=len(context.get("traces", {}).get("spans", [])),
            deployments_count=len(context.get("deployments", {}).get("events", [])),
            alerts_count=len(context.get("alerts", {}).get("alerts", [])),
            time_window_minutes=request.time_window_minutes
        )

        return AnalysisStartResponse(
            analysis_id=analysis.id,
            status=SchemaStatus(analysis.status.value),
            message="Analysis completed" if analysis.status == AnalysisStatus.COMPLETED else "Analysis failed",
            context_gathered=context_summary
        )

    async def get_analysis(
        self,
        analysis_id: UUID,
        organization_id: UUID
    ) -> Optional[AIRootCauseAnalysis]:
        """Get analysis by ID."""
        result = await self.db.execute(
            select(AIRootCauseAnalysis).where(
                and_(
                    AIRootCauseAnalysis.id == analysis_id,
                    AIRootCauseAnalysis.organization_id == organization_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_analysis_for_incident(
        self,
        incident_id: UUID,
        organization_id: UUID
    ) -> Optional[AIRootCauseAnalysis]:
        """Get the latest analysis for an incident."""
        result = await self.db.execute(
            select(AIRootCauseAnalysis).where(
                and_(
                    AIRootCauseAnalysis.incident_id == incident_id,
                    AIRootCauseAnalysis.organization_id == organization_id
                )
            ).order_by(desc(AIRootCauseAnalysis.created_at)).limit(1)
        )
        return result.scalar_one_or_none()

    async def submit_feedback(
        self,
        analysis_id: UUID,
        organization_id: UUID,
        helpful: bool,
        comment: Optional[str] = None
    ) -> bool:
        """Submit user feedback on analysis quality."""
        analysis = await self.get_analysis(analysis_id, organization_id)
        if not analysis:
            return False

        analysis.feedback_helpful = helpful
        analysis.feedback_comment = comment
        await self.db.commit()
        return True

    # ============================================
    # Private Methods
    # ============================================

    async def _get_incident(
        self,
        incident_id: UUID,
        organization_id: UUID
    ) -> Optional[Incident]:
        """Get incident by ID."""
        result = await self.db.execute(
            select(Incident).where(
                and_(
                    Incident.id == incident_id,
                    Incident.organization_id == organization_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def _get_existing_analysis(
        self,
        incident_id: UUID,
        organization_id: UUID
    ) -> Optional[AIRootCauseAnalysis]:
        """Get existing pending/analyzing analysis."""
        result = await self.db.execute(
            select(AIRootCauseAnalysis).where(
                and_(
                    AIRootCauseAnalysis.incident_id == incident_id,
                    AIRootCauseAnalysis.organization_id == organization_id,
                    AIRootCauseAnalysis.status.in_([AnalysisStatus.PENDING, AnalysisStatus.ANALYZING])
                )
            ).order_by(desc(AIRootCauseAnalysis.created_at)).limit(1)
        )
        return result.scalar_one_or_none()

    async def _gather_context(
        self,
        incident: Incident,
        organization_id: UUID,
        time_window_minutes: int,
        include_metrics: bool,
        include_logs: bool,
        include_traces: bool,
        include_deployments: bool
    ) -> Dict[str, Any]:
        """
        Gather all relevant context for analysis.

        Collects:
        - Related alerts
        - Metric snapshots around incident time
        - Log entries around incident time
        - Trace data
        - Recent deployments
        """
        context = {}
        incident_time = incident.created_at or datetime.utcnow()
        window_start = incident_time - timedelta(minutes=time_window_minutes)
        window_end = incident_time + timedelta(minutes=30)  # Include 30 min after

        # Get related alerts
        alerts_result = await self.db.execute(
            select(Alert).where(
                and_(
                    Alert.organization_id == organization_id,
                    Alert.created_at >= window_start,
                    Alert.created_at <= window_end
                )
            ).order_by(Alert.created_at).limit(50)
        )
        alerts = alerts_result.scalars().all()
        context["alerts"] = {
            "alerts": [
                {
                    "id": str(a.id),
                    "title": a.title,
                    "description": a.description,
                    "severity": a.severity.value if hasattr(a.severity, 'value') else str(a.severity),
                    "service": a.service_name,
                    "created_at": a.created_at.isoformat() if a.created_at else None
                }
                for a in alerts
            ]
        }

        # Get logs
        if include_logs:
            logs_result = await self.db.execute(
                select(LogEntry).where(
                    and_(
                        LogEntry.organization_id == organization_id,
                        LogEntry.timestamp >= window_start,
                        LogEntry.timestamp <= window_end,
                        LogEntry.level.in_(['error', 'critical', 'warning'])
                    )
                ).order_by(LogEntry.timestamp).limit(100)
            )
            logs = logs_result.scalars().all()
            context["logs"] = {
                "entries": [
                    {
                        "timestamp": l.timestamp.isoformat() if l.timestamp else None,
                        "level": l.level.value if hasattr(l.level, 'value') else str(l.level),
                        "message": l.message[:500] if l.message else None,  # Truncate long messages
                        "service": l.service_name,
                        "host": l.hostname
                    }
                    for l in logs
                ]
            }

        # Get traces
        if include_traces:
            traces_result = await self.db.execute(
                select(Span).where(
                    and_(
                        Span.organization_id == organization_id,
                        Span.start_time >= window_start,
                        Span.start_time <= window_end,
                        Span.status == 'error'
                    )
                ).order_by(Span.start_time).limit(50)
            )
            spans = traces_result.scalars().all()
            context["traces"] = {
                "spans": [
                    {
                        "trace_id": str(s.trace_id),
                        "name": s.name,
                        "service": s.service_name,
                        "status": s.status.value if hasattr(s.status, 'value') else str(s.status),
                        "duration_ms": s.duration_ms,
                        "start_time": s.start_time.isoformat() if s.start_time else None
                    }
                    for s in spans
                ]
            }

        # Get recent deployments
        if include_deployments:
            deploys_result = await self.db.execute(
                select(DeploymentEvent).where(
                    and_(
                        DeploymentEvent.organization_id == organization_id,
                        DeploymentEvent.deployed_at >= window_start,
                        DeploymentEvent.deployed_at <= window_end
                    )
                ).order_by(DeploymentEvent.deployed_at).limit(20)
            )
            deployments = deploys_result.scalars().all()
            context["deployments"] = {
                "events": [
                    {
                        "id": str(d.id),
                        "service": d.service_name,
                        "version": d.version,
                        "environment": d.environment,
                        "deployed_at": d.deployed_at.isoformat() if d.deployed_at else None,
                        "deployed_by": d.deployed_by,
                        "commit_sha": d.commit_sha,
                        "status": d.status.value if hasattr(d.status, 'value') else str(d.status)
                    }
                    for d in deployments
                ]
            }

        return context

    async def _perform_analysis(
        self,
        analysis: AIRootCauseAnalysis,
        incident: Incident,
        context: Dict[str, Any],
        organization_id: UUID,
        provider: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Perform the actual AI analysis.

        Uses BYOK (Bring Your Own Key) pattern.
        """
        # Build the analysis prompt
        prompt = self._build_rca_prompt(incident, context)
        analysis.raw_prompt = prompt

        # Load API keys from organization settings
        from app.models.api_keys import APIKey
        from app.services.encryption_service import EncryptionService

        claude_key = None
        gemini_key = None

        try:
            result = await self.db.execute(
                select(APIKey).where(
                    and_(
                        APIKey.organization_id == organization_id,
                        APIKey.is_valid == True
                    )
                )
            )
            api_keys = result.scalars().all()

            for key in api_keys:
                try:
                    decrypted = EncryptionService.decrypt_api_key(key.encrypted_key)
                    if key.provider == 'claude':
                        claude_key = decrypted
                    elif key.provider == 'gemini':
                        gemini_key = decrypted
                except Exception as e:
                    logger.warning(f"Failed to decrypt {key.provider} key: {e}")
        except Exception as e:
            logger.error(f"Failed to load API keys: {e}")

        # Try preferred provider first
        if provider == 'gemini' and gemini_key:
            result = await self._call_gemini(prompt, gemini_key)
            if result:
                result["provider"] = "gemini"
                return result

        if provider == 'claude' and claude_key:
            result = await self._call_claude(prompt, claude_key)
            if result:
                result["provider"] = "claude"
                return result

        # Fallback to any available provider
        if claude_key:
            result = await self._call_claude(prompt, claude_key)
            if result:
                result["provider"] = "claude"
                return result

        if gemini_key:
            result = await self._call_gemini(prompt, gemini_key)
            if result:
                result["provider"] = "gemini"
                return result

        logger.warning("No AI providers configured")
        return None

    def _build_rca_prompt(self, incident: Incident, context: Dict[str, Any]) -> str:
        """Build the prompt for root cause analysis."""
        alerts = context.get("alerts", {}).get("alerts", [])
        logs = context.get("logs", {}).get("entries", [])
        traces = context.get("traces", {}).get("spans", [])
        deployments = context.get("deployments", {}).get("events", [])

        severity = incident.severity.value if hasattr(incident.severity, 'value') else str(incident.severity)
        status = incident.status.value if hasattr(incident.status, 'value') else str(incident.status)
        created = incident.created_at.isoformat() if incident.created_at else 'Unknown'

        prompt = f"""You are a Principal Site Reliability Engineer preparing a formal Root Cause Analysis (RCA) report for an engineering leadership review.

══════════════════════════════════════════════════════════════════════════════
                         INCIDENT ROOT CAUSE ANALYSIS
══════════════════════════════════════════════════════════════════════════════

SECTION 1: INCIDENT SUMMARY
────────────────────────────────────────────────────────────────────────────────
• Incident Title: {incident.title}
• Severity Level: {severity.upper()}
• Current Status: {status.upper()}
• Detection Time: {created}
• Description: {incident.description or 'No description provided'}

SECTION 2: OBSERVABILITY DATA
────────────────────────────────────────────────────────────────────────────────

2.1 TRIGGERED ALERTS ({len(alerts)} total)
"""
        if alerts:
            for i, alert in enumerate(alerts[:10], 1):
                prompt += f"    {i}. [{alert.get('severity', 'UNKNOWN').upper()}] {alert.get('title', 'Unknown')}\n"
                prompt += f"       Service: {alert.get('service', 'unknown')} | Time: {alert.get('created_at', 'N/A')}\n"
        else:
            prompt += "    No alerts captured in analysis window.\n"

        prompt += f"""
2.2 ERROR LOGS ({len(logs)} entries captured)
"""
        if logs:
            for i, log in enumerate(logs[:15], 1):
                msg = log.get('message', '')[:150]
                prompt += f"    {i}. [{log.get('level', 'INFO').upper()}] {log.get('service', 'unknown')}\n"
                prompt += f"       {msg}\n"
        else:
            prompt += "    No error/warning logs captured in analysis window.\n"

        prompt += f"""
2.3 DISTRIBUTED TRACES ({len(traces)} error spans)
"""
        if traces:
            for i, span in enumerate(traces[:10], 1):
                prompt += f"    {i}. {span.get('service', 'unknown')}/{span.get('name', 'unknown')}\n"
                prompt += f"       Duration: {span.get('duration_ms', 0)}ms | Status: {span.get('status', 'unknown').upper()}\n"
        else:
            prompt += "    No error traces captured in analysis window.\n"

        prompt += f"""
2.4 DEPLOYMENT ACTIVITY ({len(deployments)} deployments)
"""
        if deployments:
            for i, deploy in enumerate(deployments[:5], 1):
                prompt += f"    {i}. {deploy.get('service', 'unknown')} v{deploy.get('version', 'unknown')}\n"
                prompt += f"       Deployed: {deploy.get('deployed_at', 'N/A')} by {deploy.get('deployed_by', 'unknown')}\n"
                if deploy.get('commit_sha'):
                    prompt += f"       Commit: {deploy.get('commit_sha', 'N/A')[:8]}\n"
        else:
            prompt += "    No deployments in analysis window.\n"

        prompt += """
══════════════════════════════════════════════════════════════════════════════
                            ANALYSIS REQUIREMENTS
══════════════════════════════════════════════════════════════════════════════

Generate a professional RCA report with the following sections:

1. ROOT CAUSE STATEMENT
   - Provide a clear, technical explanation of what caused the incident
   - Be specific: name the component, version, configuration, or code path
   - Explain the failure mechanism in engineering terms

2. CONFIDENCE ASSESSMENT
   - Rate your confidence (0.0-1.0) based on evidence quality
   - Higher confidence requires direct evidence (logs, traces, metrics)

3. ROOT CAUSE CATEGORY
   - Classify as: deployment, config_change, capacity, dependency, code_bug,
     infrastructure, network, database, security, or unknown

4. CONTRIBUTING FACTORS
   - List factors that enabled or worsened the incident
   - Include both technical and process factors

5. AFFECTED SERVICES
   - List all services impacted (primary and downstream)

6. INCIDENT TIMELINE
   - Chronological sequence of events with timestamps
   - Include: initial trigger, propagation, detection, response

7. REMEDIATION ACTIONS
   - Prioritized list (1 = highest priority)
   - Include: immediate fixes, short-term mitigations, long-term preventions
   - Be specific and actionable

══════════════════════════════════════════════════════════════════════════════
                              OUTPUT FORMAT
══════════════════════════════════════════════════════════════════════════════

Respond with ONLY this JSON structure:

```json
{
  "root_cause": "Precise technical explanation. Example: 'Memory leak in order-service v3.2.1 caused by unbounded cache growth in the ProductCatalogClient class. The cache lacked TTL configuration, causing heap exhaustion after 4.2 hours of operation under normal load. GC overhead exceeded 90% triggering OOMKiller at 14:32 UTC.'",
  "confidence": 0.85,
  "category": "code_bug",
  "contributing_factors": [
    "Missing cache eviction policy in ProductCatalogClient",
    "No memory alerting threshold configured for order-service",
    "Inadequate load testing for long-running scenarios"
  ],
  "affected_services": ["order-service", "checkout-api", "payment-gateway"],
  "timeline": [
    {
      "timestamp": "2024-01-28T10:15:00Z",
      "event_type": "deployment",
      "title": "order-service v3.2.1 deployed",
      "description": "New version deployed with ProductCatalogClient changes",
      "service": "order-service",
      "severity": "info"
    },
    {
      "timestamp": "2024-01-28T14:28:00Z",
      "event_type": "metric_spike",
      "title": "Memory utilization exceeded 85%",
      "description": "Heap memory crossed warning threshold",
      "service": "order-service",
      "severity": "warning"
    },
    {
      "timestamp": "2024-01-28T14:32:00Z",
      "event_type": "log_error",
      "title": "OutOfMemoryError",
      "description": "JVM terminated by OOMKiller",
      "service": "order-service",
      "severity": "critical"
    }
  ],
  "recommendations": [
    {
      "priority": 1,
      "action": "Rollback order-service to v3.1.0",
      "description": "Immediately revert to last known stable version to restore service",
      "category": "immediate",
      "estimated_effort": "quick_fix"
    },
    {
      "priority": 2,
      "action": "Implement cache TTL and size limits",
      "description": "Add maxSize=10000 and expireAfterWrite=1h to ProductCatalogClient cache configuration",
      "category": "short_term",
      "estimated_effort": "hours"
    },
    {
      "priority": 3,
      "action": "Add memory utilization alerts",
      "description": "Configure alerts at 70% (warning) and 85% (critical) heap utilization thresholds",
      "category": "short_term",
      "estimated_effort": "hours"
    },
    {
      "priority": 4,
      "action": "Implement long-running load tests",
      "description": "Add 8-hour soak tests to CI/CD pipeline to catch memory leaks before production",
      "category": "long_term",
      "estimated_effort": "days"
    }
  ]
}
```

Respond ONLY with the JSON object. No additional text or markdown.
"""
        return prompt

    async def _call_claude(self, prompt: str, api_key: str) -> Optional[Dict[str, Any]]:
        """Call Claude API for analysis."""
        try:
            headers = {
                'Content-Type': 'application/json',
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01'
            }

            payload = {
                'model': 'claude-sonnet-4-20250514',
                'max_tokens': 4000,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ]
            }

            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    'https://api.anthropic.com/v1/messages',
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        text_content = result['content'][0]['text']
                        tokens = result.get('usage', {}).get('output_tokens', 0)
                        return self._parse_rca_response(text_content, "claude", "claude-sonnet-4-20250514", tokens)
                    else:
                        error_text = await response.text()
                        logger.error(f"Claude API error {response.status}: {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Claude RCA failed: {e}")
            return None

    async def _call_gemini(self, prompt: str, api_key: str) -> Optional[Dict[str, Any]]:
        """Call Gemini API for analysis."""
        try:
            headers = {'Content-Type': 'application/json'}

            payload = {
                'contents': [{'parts': [{'text': prompt}]}]
            }

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={api_key}"

            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        text_content = result['candidates'][0]['content']['parts'][0]['text']
                        return self._parse_rca_response(text_content, "gemini", "gemini-2.0-flash-exp", 0)
                    else:
                        error_text = await response.text()
                        logger.error(f"Gemini API error {response.status}: {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Gemini RCA failed: {e}")
            return None

    def _parse_rca_response(
        self,
        text: str,
        provider: str,
        model: str,
        tokens: int
    ) -> Dict[str, Any]:
        """Parse the AI response into structured data."""
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(text)

            return {
                "root_cause": data.get("root_cause", "Unable to determine root cause"),
                "confidence": min(max(data.get("confidence", 0.5), 0.0), 1.0),
                "category": data.get("category", "unknown"),
                "contributing_factors": data.get("contributing_factors", []),
                "affected_services": data.get("affected_services", []),
                "timeline": data.get("timeline", []),
                "recommendations": data.get("recommendations", []),
                "provider": provider,
                "model": model,
                "tokens_used": tokens,
                "raw_response": {"text": text}
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {e}")
            # Return a basic analysis with the raw text
            return {
                "root_cause": text[:500] if len(text) > 500 else text,
                "confidence": 0.3,
                "category": "unknown",
                "contributing_factors": [],
                "affected_services": [],
                "timeline": [],
                "recommendations": [],
                "provider": provider,
                "model": model,
                "tokens_used": tokens,
                "raw_response": {"text": text, "parse_error": str(e)}
            }
