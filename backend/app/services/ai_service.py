# backend/app/services/ai_service.py
"""AI Service for incident analysis with plan-based provider selection"""

from typing import Dict, Any, Optional, List
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import anthropic
import google.generativeai as genai

from app.models.organization import Organization
from app.models.api_keys import APIKey
from app.models.incident import Incident

logger = logging.getLogger(__name__)


class AIService:
    """Handle AI analysis with plan-based provider selection"""

    @staticmethod
    async def analyze_incident(
        incident: Incident,
        org: Organization,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Analyze an incident with every AI provider the organization has a key for.

        With two or more providers configured the responses are merged into a
        consensus; with one it falls through to that provider's answer.
        """
        return await AIService._multi_ai_analysis(incident, org, db)

    @staticmethod
    async def _multi_ai_analysis(
        incident: Incident,
        org: Organization,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Multi-AI consensus analysis across all configured providers."""

        # Get API keys
        api_keys_result = await db.execute(
            select(APIKey).where(APIKey.organization_id == org.id)
        )
        keys = api_keys_result.scalars().all()

        claude_key = next((k for k in keys if k.provider == 'claude'), None)
        gemini_key = next((k for k in keys if k.provider == 'gemini'), None)

        responses = {}

        # Call Claude
        if claude_key:
            try:
                responses['claude'] = await AIService._call_claude(
                    incident,
                    claude_key.api_key
                )
            except Exception as e:
                logger.error(f"Claude API error: {e}")

        # Call Gemini
        if gemini_key:
            try:
                responses['gemini'] = await AIService._call_gemini(
                    incident,
                    gemini_key.api_key
                )
            except Exception as e:
                logger.error(f"Gemini API error: {e}")

        # If we have both, create consensus
        if len(responses) >= 2:
            return AIService._create_consensus(responses)
        elif len(responses) == 1:
            # Fall back to single provider
            return list(responses.values())[0]
        else:
            raise ValueError("No AI API keys configured")

    @staticmethod
    async def _call_claude(incident: Incident, api_key: str) -> Dict[str, Any]:
        """Call Claude API for analysis"""
        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""Analyze this incident and provide:
1. Root cause analysis
2. Severity assessment (critical/high/medium/low)
3. Immediate action items
4. Prevention recommendations

Incident Details:
Title: {incident.title}
Description: {incident.description}
Service: {incident.service or 'Unknown'}
Status: {incident.status}
"""

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            return {
                "provider": "claude",
                "analysis": response.content[0].text,
                "model": "claude-sonnet-4",
                "success": True
            }
        except Exception as e:
            logger.error(f"Claude API call failed: {e}")
            raise

    @staticmethod
    async def _call_gemini(incident: Incident, api_key: str) -> Dict[str, Any]:
        """Call Gemini API for analysis"""
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-pro')

        prompt = f"""Analyze this incident and provide:
1. Root cause analysis
2. Severity assessment (critical/high/medium/low)
3. Immediate action items
4. Prevention recommendations

Incident Details:
Title: {incident.title}
Description: {incident.description}
Service: {incident.service or 'Unknown'}
Status: {incident.status}
"""

        try:
            response = model.generate_content(prompt)

            return {
                "provider": "gemini",
                "analysis": response.text,
                "model": "gemini-1.5-pro",
                "success": True
            }
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise

    @staticmethod
    def _create_consensus(responses: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Create consensus from multiple AI responses"""

        analyses = []
        for provider, response in responses.items():
            analyses.append(f"## {provider.upper()} Analysis:\n{response['analysis']}")

        combined_analysis = "\n\n".join(analyses)

        return {
            "provider": "multi-ai-consensus",
            "analysis": combined_analysis,
            "individual_responses": responses,
            "providers_used": list(responses.keys()),
            "confidence": "high" if len(responses) >= 2 else "medium",
            "success": True
        }
