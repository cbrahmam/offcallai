# backend/app/services/ai_providers.py - NEW FILE
import asyncio
import aiohttp
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from app.api.v1.endpoints.ai_analysis import AIAnalysisResponse

logger = logging.getLogger(__name__)

class ClaudeService:
    """Service for analyzing incidents with Anthropic Claude"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.anthropic.com/v1/messages"
        self.model = "claude-3-haiku-20240307"  # Fast and cost-effective
    
    async def analyze_incident(self, incident_context: Dict[str, Any]) -> AIAnalysisResponse:
        """Analyze incident using Claude API"""
        
        try:
            # Prepare the prompt for Claude
            prompt = self._build_analysis_prompt(incident_context)
            
            headers = {
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            }
            
            payload = {
                "model": self.model,
                "max_tokens": 1000,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Claude API error {response.status}: {error_text}")
                    
                    data = await response.json()
                    content = data["content"][0]["text"]
                    
                    # Parse Claude's response
                    return self._parse_claude_response(content, incident_context)
        
        except Exception as e:
            logger.error(f"Claude analysis failed: {e}")
            raise Exception(f"Claude analysis failed: {str(e)}")
    
    def _build_analysis_prompt(self, incident_context: Dict[str, Any]) -> str:
        """Build analysis prompt for Claude"""
        
        return f"""
You are an expert incident response analyst. Analyze this incident and provide structured recommendations.

INCIDENT DETAILS:
Title: {incident_context['title']}
Description: {incident_context['description']}
Severity: {incident_context['severity']}
Status: {incident_context['status']}
Created: {incident_context['created_at']}

Please provide your analysis in the following JSON format:
{{
    "summary": "Brief summary of the incident and its likely causes",
    "recommended_actions": [
        "Action 1: Specific step to take",
        "Action 2: Another specific step",
        "Action 3: Additional step"
    ],
    "severity_assessment": "Your assessment of severity (critical/high/medium/low)",
    "estimated_resolution_time": "Estimated time to resolve (e.g., '30 minutes', '2 hours')",
    "root_cause_suggestions": [
        "Possible root cause 1",
        "Possible root cause 2"
    ],
    "confidence_score": 85
}}

Focus on actionable steps and practical solutions. Be specific and prioritize the most impactful actions first.
"""
    
    def _parse_claude_response(self, content: str, incident_context: Dict[str, Any]) -> AIAnalysisResponse:
        """Parse Claude's response into structured format"""
        
        try:
            # Try to extract JSON from Claude's response
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_str = content[json_start:json_end]
                parsed = json.loads(json_str)
                
                return AIAnalysisResponse(
                    provider="claude",
                    summary=parsed.get("summary", "Analysis completed"),
                    recommended_actions=parsed.get("recommended_actions", []),
                    confidence_score=parsed.get("confidence_score", 75),
                    analysis_time=datetime.utcnow().isoformat(),
                    severity_assessment=parsed.get("severity_assessment"),
                    estimated_resolution_time=parsed.get("estimated_resolution_time"),
                    root_cause_suggestions=parsed.get("root_cause_suggestions", [])
                )
            else:
                # Fallback if JSON parsing fails
                return self._fallback_claude_parsing(content)
                
        except json.JSONDecodeError:
            return self._fallback_claude_parsing(content)
    
    def _fallback_claude_parsing(self, content: str) -> AIAnalysisResponse:
        """Fallback parsing if JSON extraction fails"""
        
        lines = content.strip().split('\n')
        summary = content[:200] + "..." if len(content) > 200 else content
        
        # Extract action items if possible
        actions = []
        for line in lines:
            if any(keyword in line.lower() for keyword in ['action', 'step', 'recommend', 'should']):
                actions.append(line.strip())
        
        return AIAnalysisResponse(
            provider="claude",
            summary=summary,
            recommended_actions=actions[:5],  # Limit to 5 actions
            confidence_score=70,  # Default confidence
            analysis_time=datetime.utcnow().isoformat()
        )

class GeminiService:
    """Service for analyzing incidents with Google Gemini"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash-exp:generateContent"
    
    async def analyze_incident(self, incident_context: Dict[str, Any]) -> AIAnalysisResponse:
        """Analyze incident using Gemini API"""
        
        try:
            # Prepare the prompt for Gemini
            prompt = self._build_analysis_prompt(incident_context)
            
            headers = {
                "Content-Type": "application/json"
            }
            
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ]
            }
            
            url = f"{self.base_url}?key={self.api_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Gemini API error {response.status}: {error_text}")
                    
                    data = await response.json()
                    content = data["candidates"][0]["content"]["parts"][0]["text"]
                    
                    # Parse Gemini's response
                    return self._parse_gemini_response(content, incident_context)
        
        except Exception as e:
            logger.error(f"Gemini analysis failed: {e}")
            raise Exception(f"Gemini analysis failed: {str(e)}")
    
    def _build_analysis_prompt(self, incident_context: Dict[str, Any]) -> str:
        """Build analysis prompt for Gemini"""
        
        return f"""
As an expert incident response analyst, analyze this production incident and provide actionable recommendations.

INCIDENT INFORMATION:
- Title: {incident_context['title']}
- Description: {incident_context['description']}  
- Current Severity: {incident_context['severity']}
- Status: {incident_context['status']}
- Occurred: {incident_context['created_at']}

Please provide your analysis in this exact JSON format:
{{
    "summary": "Concise analysis of the incident and probable causes",
    "recommended_actions": [
        "Immediate action 1",
        "Immediate action 2", 
        "Follow-up action 3"
    ],
    "severity_assessment": "critical|high|medium|low",
    "estimated_resolution_time": "realistic time estimate",
    "root_cause_suggestions": [
        "Likely root cause 1",
        "Likely root cause 2"
    ],
    "confidence_score": 80
}}

Prioritize immediate stabilization actions, then investigation steps. Be specific and actionable.
"""
    
    def _parse_gemini_response(self, content: str, incident_context: Dict[str, Any]) -> AIAnalysisResponse:
        """Parse Gemini's response into structured format"""
        
        try:
            # Try to extract JSON from Gemini's response
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_str = content[json_start:json_end]
                parsed = json.loads(json_str)
                
                return AIAnalysisResponse(
                    provider="gemini",
                    summary=parsed.get("summary", "Analysis completed"),
                    recommended_actions=parsed.get("recommended_actions", []),
                    confidence_score=parsed.get("confidence_score", 75),
                    analysis_time=datetime.utcnow().isoformat(),
                    severity_assessment=parsed.get("severity_assessment"),
                    estimated_resolution_time=parsed.get("estimated_resolution_time"),
                    root_cause_suggestions=parsed.get("root_cause_suggestions", [])
                )
            else:
                # Fallback if JSON parsing fails
                return self._fallback_gemini_parsing(content)
                
        except json.JSONDecodeError:
            return self._fallback_gemini_parsing(content)
    
    def _fallback_gemini_parsing(self, content: str) -> AIAnalysisResponse:
        """Fallback parsing if JSON extraction fails"""
        
        lines = content.strip().split('\n')
        summary = content[:200] + "..." if len(content) > 200 else content
        
        # Extract action items if possible
        actions = []
        for line in lines:
            if any(keyword in line.lower() for keyword in ['action', 'step', 'recommend', 'should']):
                actions.append(line.strip())
        
        return AIAnalysisResponse(
            provider="gemini",
            summary=summary,
            recommended_actions=actions[:5],  # Limit to 5 actions
            confidence_score=70,  # Default confidence
            analysis_time=datetime.utcnow().isoformat()
        )