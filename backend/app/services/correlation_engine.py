# backend/app/services/correlation_engine.py
"""
Enhanced Alert Correlation Engine
Uses multiple techniques including ML-based similarity
"""

from typing import Dict, List, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
import logging
import re
from collections import Counter

logger = logging.getLogger(__name__)

class CorrelationEngine:
    """
    Advanced alert correlation with multiple scoring methods
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
        # Configurable weights for different correlation factors
        self.weights = {
            'service': 0.35,        # Same service
            'host': 0.25,           # Same host
            'environment': 0.15,    # Same environment
            'title_similarity': 0.20,  # Title text similarity
            'severity': 0.05,       # Same severity
            'tags': 0.10,           # Tag overlap
            'temporal': 0.10,       # Time proximity
            'error_pattern': 0.15   # Error pattern matching
        }
    
    def update_weights(self, new_weights: Dict[str, float]):
        """Allow dynamic weight tuning based on feedback"""
        self.weights.update(new_weights)
        logger.info(f"Updated correlation weights: {self.weights}")
    
    async def find_correlated_alerts(
        self,
        alert,
        organization_id: str,
        time_window_minutes: int = 30,
        min_score: float = 0.3
    ) -> List[Dict]:
        """
        Find correlated alerts using enhanced scoring
        """
        from app.models.alert import Alert
        
        alert_time = alert.started_at or alert.created_at
        time_start = alert_time - timedelta(minutes=time_window_minutes)
        time_end = alert_time + timedelta(minutes=10)
        
        # Find candidate alerts
        result = await self.db.execute(
            select(Alert).where(
                and_(
                    Alert.organization_id == organization_id,
                    Alert.id != alert.id,
                    Alert.started_at.between(time_start, time_end),
                    Alert.status.in_(['active', 'acknowledged'])
                )
            )
        )
        candidates = result.scalars().all()
        
        if not candidates:
            return []
        
        # Score each candidate
        correlations = []
        for candidate in candidates:
            score, breakdown = self._calculate_correlation_score_v2(alert, candidate)
            
            if score >= min_score:
                correlations.append({
                    'alert_id': str(candidate.id),
                    'score': round(score, 3),
                    'title': candidate.title,
                    'service': candidate.service_name,
                    'severity': candidate.severity.value,
                    'breakdown': breakdown,
                    'reason': self._generate_correlation_reason(breakdown)
                })
        
        # Sort by score
        correlations.sort(key=lambda x: x['score'], reverse=True)
        
        return correlations[:10]  # Return top 10
    
    def _calculate_correlation_score_v2(self, alert1, alert2) -> Tuple[float, Dict]:
        """
        Enhanced correlation scoring with breakdown
        """
        breakdown = {}
        total_score = 0.0
        
        # 1. Service matching
        if alert1.service_name and alert2.service_name:
            if alert1.service_name == alert2.service_name:
                score = self.weights['service']
                breakdown['service'] = score
                total_score += score
        
        # 2. Host matching
        if alert1.host and alert2.host:
            if alert1.host == alert2.host:
                score = self.weights['host']
                breakdown['host'] = score
                total_score += score
        
        # 3. Environment matching
        if alert1.environment and alert2.environment:
            if alert1.environment == alert2.environment:
                score = self.weights['environment']
                breakdown['environment'] = score
                total_score += score
        
        # 4. Title similarity (semantic)
        title_sim = self._calculate_text_similarity_enhanced(
            alert1.title, alert2.title
        )
        if title_sim > 0:
            score = title_sim * self.weights['title_similarity']
            breakdown['title_similarity'] = score
            total_score += score
        
        # 5. Severity matching
        if alert1.severity == alert2.severity:
            score = self.weights['severity']
            breakdown['severity'] = score
            total_score += score
        
        # 6. Tag/label overlap
        tags1 = self._extract_tags(alert1)
        tags2 = self._extract_tags(alert2)
        if tags1 and tags2:
            tag_overlap = len(tags1 & tags2) / len(tags1 | tags2)
            if tag_overlap > 0:
                score = tag_overlap * self.weights['tags']
                breakdown['tags'] = score
                total_score += score
        
        # 7. Temporal proximity
        time_diff = abs((alert1.started_at - alert2.started_at).total_seconds())
        if time_diff < 300:  # Within 5 minutes
            temporal_score = (1 - time_diff / 300) * self.weights['temporal']
            breakdown['temporal'] = temporal_score
            total_score += temporal_score
        
        # 8. Error pattern matching
        error_sim = self._match_error_patterns(alert1, alert2)
        if error_sim > 0:
            score = error_sim * self.weights['error_pattern']
            breakdown['error_pattern'] = score
            total_score += score
        
        return min(total_score, 1.0), breakdown
    
    def _calculate_text_similarity_enhanced(self, text1: str, text2: str) -> float:
        """
        Enhanced text similarity using multiple techniques
        """
        if not text1 or not text2:
            return 0.0
        
        # Normalize texts
        text1 = text1.lower()
        text2 = text2.lower()
        
        # 1. Exact match
        if text1 == text2:
            return 1.0
        
        # 2. Jaccard similarity (word overlap)
        words1 = set(self._tokenize(text1))
        words2 = set(self._tokenize(text2))
        
        if not words1 or not words2:
            return 0.0
        
        jaccard = len(words1 & words2) / len(words1 | words2)
        
        # 3. Common error keywords
        error_keywords = {'error', 'fail', 'timeout', 'exception', 'crash', 
                         'down', 'unavailable', 'latency', 'spike', 'high'}
        
        error_words1 = words1 & error_keywords
        error_words2 = words2 & error_keywords
        
        if error_words1 and error_words2:
            error_sim = len(error_words1 & error_words2) / len(error_words1 | error_words2)
            jaccard = (jaccard * 0.6) + (error_sim * 0.4)
        
        # 4. Substring matching bonus
        if text1 in text2 or text2 in text1:
            jaccard += 0.1
        
        return min(jaccard, 1.0)
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into meaningful words"""
        # Remove special characters, keep alphanumeric and hyphens
        text = re.sub(r'[^a-zA-Z0-9\s\-]', ' ', text)
        
        # Split and filter stopwords
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'is', 'was'}
        words = [w for w in text.split() if w and w not in stopwords and len(w) > 2]
        
        return words
    
    def _extract_tags(self, alert) -> set:
        """Extract all tags/labels from an alert"""
        tags = set()
        
        # From labels
        if alert.labels:
            if isinstance(alert.labels, dict):
                for key, value in alert.labels.items():
                    if isinstance(value, (list, tuple)):
                        tags.update(str(v).lower() for v in value)
                    else:
                        tags.add(str(value).lower())
            elif isinstance(alert.labels, list):
                tags.update(str(t).lower() for t in alert.labels)
        
        # From raw_data tags
        if alert.raw_data and 'tags' in alert.raw_data:
            raw_tags = alert.raw_data['tags']
            if isinstance(raw_tags, list):
                tags.update(str(t).lower() for t in raw_tags)
        
        return tags
    
    def _match_error_patterns(self, alert1, alert2) -> float:
        """
        Match common error patterns between alerts
        """
        # Extract error patterns from title and description
        patterns = [
            r'(timeout|timed out)',
            r'(connection refused|connection failed)',
            r'(out of memory|oom)',
            r'(disk full|no space)',
            r'(high cpu|cpu spike)',
            r'(database|db) (down|error)',
            r'(5\d{2}|50[0-9])',  # HTTP 5xx errors
            r'(latency|slow response)',
            r'(pod|container) (crash|restart)',
            r'(authentication|auth) (fail|error)'
        ]
        
        def extract_patterns(text):
            if not text:
                return set()
            found = set()
            for pattern in patterns:
                if re.search(pattern, text.lower()):
                    found.add(pattern)
            return found
        
        text1 = f"{alert1.title} {alert1.description or ''}"
        text2 = f"{alert2.title} {alert2.description or ''}"
        
        patterns1 = extract_patterns(text1)
        patterns2 = extract_patterns(text2)
        
        if not patterns1 or not patterns2:
            return 0.0
        
        overlap = len(patterns1 & patterns2) / len(patterns1 | patterns2)
        return overlap
    
    def _generate_correlation_reason(self, breakdown: Dict) -> str:
        """Generate human-readable correlation reason"""
        reasons = []
        
        for factor, score in sorted(breakdown.items(), key=lambda x: x[1], reverse=True):
            if score > 0.05:  # Only significant factors
                factor_name = factor.replace('_', ' ').title()
                reasons.append(f"{factor_name} ({score:.2f})")
        
        if not reasons:
            return "Low correlation"
        
        return f"Correlated by: {', '.join(reasons[:3])}"  # Top 3 factors
    
    async def get_correlation_statistics(
        self, 
        organization_id: str,
        days: int = 7
    ) -> Dict:
        """
        Analyze correlation accuracy over time
        Helps tune weights based on real data
        """
        from app.models.alert import Alert
        from app.models.incident import Incident
        
        # Get incidents from past N days
        since = datetime.utcnow() - timedelta(days=days)
        
        result = await self.db.execute(
            select(Incident).where(
                and_(
                    Incident.organization_id == organization_id,
                    Incident.created_at >= since
                )
            )
        )
        incidents = result.scalars().all()
        
        stats = {
            'total_incidents': len(incidents),
            'incidents_with_multiple_alerts': 0,
            'avg_alerts_per_incident': 0,
            'correlation_accuracy': 0.0,
            'common_correlation_factors': Counter()
        }
        
        # Analyze each incident
        alert_counts = []
        for incident in incidents:
            # Count alerts for this incident
            result = await self.db.execute(
                select(func.count(Alert.id)).where(
                    Alert.incident_id == incident.id
                )
            )
            alert_count = result.scalar()
            alert_counts.append(alert_count)
            
            if alert_count > 1:
                stats['incidents_with_multiple_alerts'] += 1
        
        if alert_counts:
            stats['avg_alerts_per_incident'] = sum(alert_counts) / len(alert_counts)
        
        # Calculate accuracy (incidents with multiple alerts / total)
        if stats['total_incidents'] > 0:
            stats['correlation_accuracy'] = (
                stats['incidents_with_multiple_alerts'] / stats['total_incidents']
            )
        
        return stats


class MLBasedCorrelation:
    """
    Machine Learning based correlation (future enhancement)
    Uses embeddings and clustering for similarity
    """
    
    def __init__(self):
        self.model = None  # Placeholder for ML model
    
    async def train_on_historical_data(self, incidents: List):
        """
        Train ML model on historical incident data
        Learn which alerts typically cluster together
        """
        # TODO: Implement using sklearn or similar
        # Features: alert text embeddings, service, host, tags
        # Labels: incident_id (alerts with same incident are related)
        pass
    
    async def predict_correlation(self, alert1, alert2) -> float:
        """
        Predict correlation score using ML model
        """
        # TODO: Implement
        # Extract features, run through model, return probability
        return 0.0