# backend/app/services/alert_enrichment_service.py
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, or_
from sqlalchemy.orm import selectinload
import hashlib
import logging
from app.models.alert import Alert, AlertSeverity
from app.models.alert_enrichment import AlertEnrichment
from app.models.incident import Incident, IncidentSeverity
import redis.asyncio as redis

logger = logging.getLogger(__name__)

class AlertEnrichmentService:
    """
    Intelligent Alert Enrichment Engine
    - Fetches context from monitoring tools
    - Correlates alerts automatically
    - Smart severity scoring with AI
    - One-click drill-down links
    """
    
    def __init__(self, db: AsyncSession, redis_client: Optional[redis.Redis] = None):
        self.db = db
        self.redis = redis_client
       # self.ai_service = EnhancedAIService(db)
    
    async def enrich_alert(
        self, 
        alert_id: str, 
        organization_id: str,
        force_refresh: bool = False
    ) -> AlertEnrichment:
        """
        Main enrichment orchestrator
        Runs all enrichment steps in parallel for speed
        """
        # Note: do not roll back here. The caller's session is shared with
        # get_current_user, and a rollback expires those loaded objects -- the
        # next attribute read then attempts an implicit refresh and raises
        # "greenlet_spawn has not been called".
        start_time = datetime.utcnow()
        
        try:
            # Check cache first
            if not force_refresh and self.redis:
                cached = await self._get_cached_enrichment(alert_id)
                if cached:
                    return cached
            
            # Fetch alert
            logger.info(f"Fetching alert {alert_id}")
            result = await self.db.execute(
                select(Alert)
                .options(selectinload(Alert.incident))
                .where(
                    and_(
                        Alert.id == alert_id,
                        Alert.organization_id == organization_id
                    )
                )
            )
            alert = result.scalar_one_or_none()
            if not alert:
                raise ValueError(f"Alert {alert_id} not found")
            
            logger.info(f"Running enrichment tasks for alert {alert_id}")
            
            # These steps run one at a time on purpose. Several of them query
            # through self.db, and an AsyncSession cannot be used concurrently --
            # gathering them raised "greenlet_spawn has not been called" and made
            # enrichment fail outright. Each step is a small query, so the
            # sequential cost is minor next to being correct.
            steps = [
                ("metrics", self._fetch_related_metrics(alert)),
                ("logs", self._fetch_related_logs(alert)),
                ("traces", self._fetch_related_traces(alert)),
                ("drill_down_links", self._build_drill_down_links(alert)),
                ("correlation", self._correlate_with_other_alerts(alert, organization_id)),
                ("severity", self._calculate_smart_severity(alert)),
            ]

            results = []
            for name, coro in steps:
                try:
                    results.append(await coro)
                except Exception as step_error:
                    logger.error(f"Enrichment step '{name}' failed: {step_error}", exc_info=step_error)
                    results.append(step_error)
            
            # Unpack results
            metrics = results[0] if not isinstance(results[0], Exception) else {}
            logs = results[1] if not isinstance(results[1], Exception) else []
            traces = results[2] if not isinstance(results[2], Exception) else []
            drill_down_links = results[3] if not isinstance(results[3], Exception) else {}
            correlation_data = results[4] if not isinstance(results[4], Exception) else {}
            severity_data = results[5] if not isinstance(results[5], Exception) else {}
            
            logger.info(f"Creating enrichment record for alert {alert_id}")
            
            # Create or update enrichment
            existing = await self.db.execute(
                select(AlertEnrichment).where(AlertEnrichment.alert_id == alert_id)
            )
            enrichment = existing.scalar_one_or_none()
            
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            if enrichment:
                # Update existing
                enrichment.related_metrics = metrics
                enrichment.related_logs = logs
                enrichment.related_traces = traces
                enrichment.dashboard_url = drill_down_links.get('dashboard_url')
                enrichment.logs_url = drill_down_links.get('logs_url')
                enrichment.traces_url = drill_down_links.get('traces_url')
                enrichment.runbook_url = drill_down_links.get('runbook_url')
                enrichment.correlated_alert_ids = correlation_data.get('alert_ids', [])
                enrichment.correlation_score = correlation_data.get('score', 0.0)
                enrichment.correlation_reason = correlation_data.get('reason', '')
                enrichment.ai_severity_score = severity_data.get('score', 50)
                enrichment.severity_confidence = severity_data.get('confidence', 0.5)
                enrichment.severity_factors = severity_data.get('factors', {})
                enrichment.original_severity = alert.severity.value
                enrichment.adjusted_severity = severity_data.get('adjusted_severity', alert.severity.value)
                enrichment.enriched_at = datetime.utcnow()
                enrichment.processing_time_ms = processing_time
            else:
                # Create new
                enrichment = AlertEnrichment(
                    alert_id=alert_id,
                    organization_id=organization_id,
                    related_metrics=metrics,
                    related_logs=logs,
                    related_traces=traces,
                    dashboard_url=drill_down_links.get('dashboard_url'),
                    logs_url=drill_down_links.get('logs_url'),
                    traces_url=drill_down_links.get('traces_url'),
                    runbook_url=drill_down_links.get('runbook_url'),
                    correlated_alert_ids=correlation_data.get('alert_ids', []),
                    correlation_score=correlation_data.get('score', 0.0),
                    correlation_reason=correlation_data.get('reason', ''),
                    ai_severity_score=severity_data.get('score', 50),
                    severity_confidence=severity_data.get('confidence', 0.5),
                    severity_factors=severity_data.get('factors', {}),
                    original_severity=alert.severity.value,
                    adjusted_severity=severity_data.get('adjusted_severity', alert.severity.value),
                    enrichment_source='claude',
                    processing_time_ms=processing_time
                )
                self.db.add(enrichment)
            
            logger.info(f"Committing enrichment for alert {alert_id}")
            await self.db.commit()
            await self.db.refresh(enrichment)
            
            # Cache result
            if self.redis:
                await self._cache_enrichment(alert_id, enrichment)
            
            logger.info(f"Enriched alert {alert_id} in {processing_time:.2f}ms")
            return enrichment
            
        except Exception as e:
            # CRITICAL: Rollback on any error
            await self.db.rollback()
            logger.error(f"Enrichment failed for alert {alert_id}: {e}", exc_info=True)
            raise Exception(f"Enrichment failed: {e}")
    
    async def _fetch_related_metrics(self, alert: Alert) -> Dict[str, Any]:
        """
        Build metrics context from internal alert data.
        Note: External monitoring integrations have been removed.
        """
        metrics = {}

        # Time window: 15 min before alert to 5 min after
        alert_time = alert.started_at or alert.created_at
        start_time = alert_time - timedelta(minutes=15)
        end_time = alert_time + timedelta(minutes=5)

        try:
            # Build context from raw_data
            service = alert.service_name or alert.raw_data.get('service', {}).get('name', 'unknown')
            host = alert.host or alert.raw_data.get('host', 'unknown')
            environment = alert.environment or alert.raw_data.get('environment', 'production')

            # Return metadata only (no external monitoring data)
            metrics = {
                'service': service,
                'host': host,
                'environment': environment,
                'time_window': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat()
                }
            }

        except Exception as e:
            logger.error(f"Error fetching metrics for alert {alert.id}: {e}")

        return metrics
    
    async def _fetch_related_logs(self, alert: Alert) -> List[Dict[str, Any]]:
        """
        Return empty logs list.
        Note: External monitoring integrations have been removed.
        """
        # External log fetching has been removed
        return []
    
    async def _fetch_related_traces(self, alert: Alert) -> List[Dict[str, Any]]:
        """
        Return empty traces list.
        Note: External monitoring integrations have been removed.
        """
        # External trace fetching has been removed
        return []
    
    async def _build_drill_down_links(self, alert: Alert) -> Dict[str, str]:
        """
        Build drill-down links from internal data only.
        Note: External monitoring integrations have been removed.
        """
        links = {}

        try:
            # Only use runbook URL if provided in raw_data
            if 'runbook_url' in alert.raw_data:
                links['runbook_url'] = alert.raw_data['runbook_url']

        except Exception as e:
            logger.error(f"Error building drill-down links for alert {alert.id}: {e}")

        return links
    
    async def _correlate_with_other_alerts(
        self, 
        alert: Alert, 
        organization_id: str
    ) -> Dict[str, Any]:
        """
        Automatic Correlation Engine with Enhanced ML-based similarity
        """
        try:
            from app.services.correlation_engine import CorrelationEngine
            
            correlation_engine = CorrelationEngine(self.db)
            
            # Find correlated alerts using enhanced algorithm
            correlations = await correlation_engine.find_correlated_alerts(
                alert=alert,
                organization_id=organization_id,
                time_window_minutes=30,
                min_score=0.3
            )
            
            if not correlations:
                return {
                    'alert_ids': [],
                    'score': 0.0,
                    'reason': 'No correlated alerts found'
                }
            
            # Return top correlation
            top_correlation = correlations[0]
            
            return {
                'alert_ids': [c['alert_id'] for c in correlations],
                'score': top_correlation['score'],
                'reason': top_correlation['reason'],
                'breakdown': top_correlation.get('breakdown', {}),
                'all_correlations': correlations
            }
            
        except Exception as e:
            logger.error(f"Error correlating alert {alert.id}: {e}", exc_info=True)
            # Return empty correlation on any error
            return {
                'alert_ids': [],
                'score': 0.0,
                'reason': 'Correlation temporarily disabled'
            }
    
    async def _calculate_smart_severity(self, alert: Alert) -> Dict[str, Any]:
        """
        Smart Severity Scoring with AI
        Combines multiple factors to determine true impact
        """
        severity_data = {
            'score': 50,  # 0-100 scale
            'confidence': 0.5,  # How confident we are
            'factors': {},
            'adjusted_severity': alert.severity.value
        }
        
        try:
            factors = {}
            score = 50  # Start at middle
            
            # Factor 1: Original severity from monitoring tool
            severity_scores = {
                'info': 20,
                'warning': 40,
                'error': 70,
                'high': 85,
                'critical': 95
            }
            original_score = severity_scores.get(alert.severity.value, 50)
            score = original_score
            factors['original_severity'] = {
                'weight': 0.3,
                'value': original_score,
                'description': f"Original severity: {alert.severity.value}"
            }
            
            # Factor 2: Service criticality (from labels/tags)
            if alert.raw_data.get('priority') == 'P1':
                score += 20
                factors['service_priority'] = {
                    'weight': 0.2,
                    'value': 20,
                    'description': "P1 service affected"
                }
            
            # Factor 3: Number of correlated alerts
            # (Placeholder - would check enrichment data)
            factors['correlation'] = {
                'weight': 0.1,
                'value': 0,
                'description': "No correlated alerts yet"
            }
            
            # Factor 4: Historical incident data
            # Check if similar alerts caused incidents before
            similar_incidents_score = await self._check_historical_severity(alert)
            if similar_incidents_score:
                score += similar_incidents_score
                factors['historical'] = {
                    'weight': 0.2,
                    'value': similar_incidents_score,
                    'description': "Similar alerts caused incidents"
                }
            
            # Factor 5: Time of day (3am = higher impact)
            alert_hour = (alert.started_at or alert.created_at).hour
            if 0 <= alert_hour <= 6:  # Night time
                score += 10
                factors['time_of_day'] = {
                    'weight': 0.1,
                    'value': 10,
                    'description': "Alert during off-hours"
                }
            
            # Cap score at 100
            score = min(score, 100)
            
            # Determine adjusted severity
            if score >= 90:
                adjusted_severity = 'critical'
            elif score >= 70:
                adjusted_severity = 'high'
            elif score >= 40:
                adjusted_severity = 'warning'
            else:
                adjusted_severity = 'info'
            
            # Calculate confidence based on number of factors
            confidence = min(len(factors) / 5.0, 1.0)
            
            severity_data['score'] = score
            severity_data['confidence'] = confidence
            severity_data['factors'] = factors
            severity_data['adjusted_severity'] = adjusted_severity
            
        except Exception as e:
            logger.error(f"Error calculating smart severity for alert {alert.id}: {e}")
        
        return severity_data
    
    async def _check_historical_severity(self, alert: Alert) -> int:
        """
        Check if similar alerts created incidents in the past
        Returns bonus score (0-20)
        """
        try:
            # FIXED: Use async properly
            from sqlalchemy import func as sa_func
            
            # Find incidents with similar fingerprints or titles
            result = await self.db.execute(
                # Incident has no service column; the service lives on the
                # alerts attached to it, so correlate through those. Severity is
                # an Enum column, so compare against the enum members rather
                # than lowercase strings.
                select(sa_func.count(sa_func.distinct(Incident.id)))
                .join(Alert, Alert.incident_id == Incident.id)
                .where(
                    and_(
                        Incident.organization_id == alert.organization_id,
                        Alert.service_name == alert.service_name,
                        Incident.severity.in_([IncidentSeverity.HIGH, IncidentSeverity.CRITICAL]),
                        Incident.created_at > datetime.utcnow() - timedelta(days=30)
                    )
                )
            )
            incident_count = result.scalar()
            
            if incident_count >= 3:
                return 20  # High historical severity
            elif incident_count >= 1:
                return 10  # Moderate historical severity
            else:
                return 0
                
        except Exception as e:
            logger.error(f"Error checking historical severity: {e}")
            return 0
    
    async def _get_cached_enrichment(self, alert_id: str) -> Optional[AlertEnrichment]:
        """Get enrichment from Redis cache"""
        try:
            if not self.redis:
                return None
            
            cache_key = f"alert_enrichment:{alert_id}"
            cached_data = await self.redis.get(cache_key)
            
            if cached_data:
                logger.info(f"Cache hit for alert {alert_id}")
                # TODO: Deserialize cached data
                return None  # Placeholder
            
        except Exception as e:
            logger.error(f"Error getting cached enrichment: {e}")
        
        return None
    
    async def _cache_enrichment(self, alert_id: str, enrichment: AlertEnrichment):
        """Cache enrichment in Redis (5 min TTL)"""
        try:
            if not self.redis:
                return
            
            cache_key = f"alert_enrichment:{alert_id}"
            # TODO: Serialize enrichment data
            await self.redis.setex(cache_key, 300, "cached_data")  # 5 min TTL
            
        except Exception as e:
            logger.error(f"Error caching enrichment: {e}")