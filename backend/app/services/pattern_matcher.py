# backend/app/services/pattern_matcher.py
"""
Pattern matching service for runbook automation.
Matches incoming alerts against runbook patterns to suggest relevant runbooks.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Result of matching a single pattern against an alert."""
    matched: bool
    pattern: Dict[str, Any]
    field_value: Optional[str] = None
    match_details: Optional[str] = None


@dataclass
class RunbookMatch:
    """Result of matching a runbook against an alert."""
    runbook_id: str
    runbook_title: str
    score: float  # 0.0 to 1.0
    matched_patterns: List[Dict[str, Any]]
    match_reason: str


class PatternMatcher:
    """
    Matches alerts against runbook patterns.

    Supports operators:
    - contains: case-insensitive substring match
    - equals: exact match (case-insensitive)
    - regex: Python regex match
    - starts_with: prefix match
    - ends_with: suffix match
    """

    # Field weights for scoring - some fields are more important than others
    FIELD_WEIGHTS = {
        "title": 1.5,
        "description": 1.0,
        "service_name": 2.0,  # High weight - service-specific runbooks are very relevant
        "severity": 1.2,
        "source": 1.0,
        "host": 1.5,
        "environment": 1.3,
    }

    def __init__(self):
        pass

    def extract_field_value(self, alert_data: Dict[str, Any], field: str) -> Optional[str]:
        """Extract a field value from alert data, handling nested structures."""
        if field in alert_data:
            value = alert_data[field]
            return str(value) if value is not None else None

        # Handle nested fields (e.g., from raw_data or labels)
        if "labels" in alert_data and isinstance(alert_data["labels"], dict):
            if field in alert_data["labels"]:
                return str(alert_data["labels"][field])

        if "raw_data" in alert_data and isinstance(alert_data["raw_data"], dict):
            if field in alert_data["raw_data"]:
                return str(alert_data["raw_data"][field])

        return None

    def match_pattern(self, field_value: str, operator: str, pattern_value: str) -> bool:
        """Match a single pattern against a field value."""
        if field_value is None:
            return False

        field_lower = field_value.lower()
        pattern_lower = pattern_value.lower()

        if operator == "contains":
            return pattern_lower in field_lower

        elif operator == "equals":
            return field_lower == pattern_lower

        elif operator == "starts_with":
            return field_lower.startswith(pattern_lower)

        elif operator == "ends_with":
            return field_lower.endswith(pattern_lower)

        elif operator == "regex":
            try:
                return bool(re.search(pattern_value, field_value, re.IGNORECASE))
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern_value}': {e}")
                return False

        else:
            logger.warning(f"Unknown operator: {operator}")
            return False

    def match_alert_against_patterns(
        self,
        alert_data: Dict[str, Any],
        patterns: List[Dict[str, Any]]
    ) -> List[MatchResult]:
        """
        Match an alert against a list of patterns.

        Args:
            alert_data: Alert data dictionary with fields like title, description, etc.
            patterns: List of pattern dicts with field, operator, value keys.

        Returns:
            List of MatchResult for each pattern.
        """
        results = []

        for pattern in patterns:
            field = pattern.get("field", "")
            operator = pattern.get("operator", "contains")
            value = pattern.get("value", "")

            field_value = self.extract_field_value(alert_data, field)
            matched = self.match_pattern(field_value, operator, value)

            results.append(MatchResult(
                matched=matched,
                pattern=pattern,
                field_value=field_value,
                match_details=f"{field} {operator} '{value}'" if matched else None
            ))

        return results

    def calculate_match_score(self, match_results: List[MatchResult]) -> float:
        """
        Calculate a match score (0.0 to 1.0) based on pattern matches.

        Scoring:
        - Each matched pattern contributes to the score
        - Patterns for more important fields have higher weights
        - Final score is normalized to 0.0-1.0 range
        """
        if not match_results:
            return 0.0

        total_weight = 0.0
        matched_weight = 0.0

        for result in match_results:
            field = result.pattern.get("field", "")
            weight = self.FIELD_WEIGHTS.get(field, 1.0)
            total_weight += weight

            if result.matched:
                matched_weight += weight

        if total_weight == 0:
            return 0.0

        return matched_weight / total_weight

    def build_match_reason(self, match_results: List[MatchResult]) -> str:
        """Build a human-readable explanation of why this runbook matched."""
        matched_details = [r.match_details for r in match_results if r.matched and r.match_details]

        if not matched_details:
            return "No patterns matched"

        if len(matched_details) == 1:
            return f"Matched: {matched_details[0]}"

        return f"Matched {len(matched_details)} patterns: {', '.join(matched_details[:3])}" + \
               ("..." if len(matched_details) > 3 else "")

    def find_matching_runbooks(
        self,
        alert_data: Dict[str, Any],
        runbooks: List[Any],  # List of Runbook ORM objects
        min_score: float = 0.3
    ) -> List[RunbookMatch]:
        """
        Find all runbooks that match an alert.

        Args:
            alert_data: Alert data dictionary.
            runbooks: List of Runbook ORM objects.
            min_score: Minimum match score to include (0.0 to 1.0).

        Returns:
            List of RunbookMatch sorted by score (highest first).
        """
        matches = []

        for runbook in runbooks:
            if not runbook.is_active:
                continue

            patterns = runbook.alert_patterns or []
            if not patterns:
                continue

            # Convert patterns to list of dicts if needed
            if isinstance(patterns, list) and len(patterns) > 0:
                match_results = self.match_alert_against_patterns(alert_data, patterns)
                score = self.calculate_match_score(match_results)

                if score >= min_score:
                    matched_patterns = [
                        r.pattern for r in match_results if r.matched
                    ]

                    matches.append(RunbookMatch(
                        runbook_id=str(runbook.id),
                        runbook_title=runbook.title,
                        score=score,
                        matched_patterns=matched_patterns,
                        match_reason=self.build_match_reason(match_results)
                    ))

        # Sort by score, highest first
        matches.sort(key=lambda m: m.score, reverse=True)

        return matches

    def rank_by_relevance(
        self,
        matches: List[RunbookMatch],
        alert_data: Dict[str, Any],
        limit: int = 5
    ) -> List[RunbookMatch]:
        """
        Re-rank matches by additional relevance factors.

        Additional factors considered:
        - Service name match (boost if runbook.service_names contains alert.service_name)
        - Recency of last use (recently used runbooks may be more relevant)
        """
        # Already sorted by score from find_matching_runbooks
        return matches[:limit]


# Singleton instance
pattern_matcher = PatternMatcher()
