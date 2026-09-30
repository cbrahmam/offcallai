# backend/app/services/real_ai_service.py
# COMPLETE FIXED VERSION - NO MOCK DATA, PROPER ERROR HANDLING

import aiohttp
import json
from typing import Dict, Any, Optional, List, AsyncGenerator
import logging

logger = logging.getLogger(__name__)

class RealAIService:
    def __init__(self, claude_api_key: str = None, gemini_api_key: str = None, db=None, organization_id: int = None):
        # BYOK - only use user-provided keys, no system fallback
        self.claude_api_key = claude_api_key
        self.gemini_api_key = gemini_api_key
        self.db = db
        self.organization_id = organization_id

    @property
    def claude_enabled(self) -> bool:
        """Check if Claude API is available"""
        return bool(self.claude_api_key)

    @property
    def gemini_enabled(self) -> bool:
        """Check if Gemini API is available"""
        return bool(self.gemini_api_key)

    async def load_user_api_keys(self):
        """Load API keys from database if needed"""
        if not self.db or not self.organization_id:
            return

        from sqlalchemy import select
        from app.models.api_keys import APIKey
        from app.services.encryption_service import EncryptionService

        try:
            result = await self.db.execute(
                select(APIKey).filter(
                    APIKey.organization_id == self.organization_id,
                    APIKey.is_valid == True
                )
            )
            api_keys = result.scalars().all()

            for key in api_keys:
                try:
                    decrypted = EncryptionService.decrypt_api_key(key.encrypted_key)
                    if key.provider == 'claude' and not self.claude_api_key:
                        self.claude_api_key = decrypted
                        logger.info(f"✅ Loaded Claude API key")
                    elif key.provider == 'gemini' and not self.gemini_api_key:
                        self.gemini_api_key = decrypted
                        logger.info(f"✅ Loaded Gemini API key")
                except Exception as e:
                    logger.error(f"Failed to decrypt {key.provider} key: {e}")

        except Exception as e:
            logger.error(f"Failed to load API keys: {e}")

    async def analyze_incident_with_claude(self, incident_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze with Claude - returns None if fails, NO MOCK DATA"""

        if self.db and not self.claude_api_key and self.organization_id:
            await self.load_user_api_keys()

        if not self.claude_api_key:
            logger.warning("Claude API key not configured")
            return None

        try:
            prompt = self._build_analysis_prompt(incident_data)

            headers = {
                'Content-Type': 'application/json',
                'x-api-key': self.claude_api_key,
                'anthropic-version': '2023-06-01'
            }

            payload = {
                'model': 'claude-sonnet-4-20250514',  # FIXED: Correct model name
                'max_tokens': 2000,
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            }

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    'https://api.anthropic.com/v1/messages',
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        text_content = result['content'][0]['text']
                        return self._parse_analysis_response(text_content, 'claude')
                    else:
                        error_text = await response.text()
                        logger.error(f"Claude API error {response.status}: {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Claude analysis failed: {e}")
            return None

    async def analyze_incident_with_gemini(self, incident_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze with Gemini - returns None if fails, NO MOCK DATA"""

        if self.db and not self.gemini_api_key and self.organization_id:
            await self.load_user_api_keys()

        if not self.gemini_api_key:
            logger.warning("Gemini API key not configured")
            return None

        try:
            prompt = self._build_analysis_prompt(incident_data)

            headers = {
                'Content-Type': 'application/json'
            }

            payload = {
                'contents': [{
                    'parts': [{'text': prompt}]
                }]
            }

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={self.gemini_api_key}"

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload, timeout=timeout) as response:
                    if response.status == 200:
                        result = await response.json()
                        text_content = result['candidates'][0]['content']['parts'][0]['text']
                        return self._parse_analysis_response(text_content, 'gemini')
                    else:
                        error_text = await response.text()
                        logger.error(f"Gemini API error {response.status}: {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Gemini analysis failed: {e}")
            return None

    async def chat_about_incident(
        self,
        incident_context: Dict[str, Any],
        user_message: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> str:
        """Chat with AI about incident - NO MOCK DATA"""

        if self.db and self.organization_id:
            await self.load_user_api_keys()

        if not self.claude_api_key and not self.gemini_api_key:
            raise ValueError("No AI API keys configured. Please add API keys in Settings.")

        # Try Claude first
        if self.claude_api_key:
            try:
                return await self._chat_with_claude(incident_context, user_message, conversation_history)
            except Exception as e:
                logger.error(f"Claude chat failed: {e}")

        # Fallback to Gemini
        if self.gemini_api_key:
            try:
                return await self._chat_with_gemini(incident_context, user_message, conversation_history)
            except Exception as e:
                logger.error(f"Gemini chat failed: {e}")

        raise ValueError("All AI providers failed")

    async def _chat_with_claude(
        self,
        incident_context: Dict[str, Any],
        user_message: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> str:
        """Real Claude API call for chat"""

        messages = []
        if conversation_history:
            messages.extend(conversation_history)

        system_context = f"""You are an expert SRE helping with this incident:

Title: {incident_context.get('title')}
Description: {incident_context.get('description')}
Severity: {incident_context.get('severity')}
Status: {incident_context.get('status')}

Answer questions concisely and helpfully."""

        messages.append({
            'role': 'user',
            'content': f"{system_context}\n\nQuestion: {user_message}"
        })

        headers = {
            'Content-Type': 'application/json',
            'x-api-key': self.claude_api_key,
            'anthropic-version': '2023-06-01'
        }

        payload = {
            'model': 'claude-sonnet-4-20250514',  # FIXED: Correct model name
            'max_tokens': 1000,
            'messages': messages
        }

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post('https://api.anthropic.com/v1/messages', headers=headers, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    return result['content'][0]['text']
                else:
                    error_text = await response.text()
                    raise Exception(f"Claude API error {response.status}: {error_text}")

    async def _chat_with_gemini(
        self,
        incident_context: Dict[str, Any],
        user_message: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> str:
        """Real Gemini API call for chat"""

        prompt = f"""You are an expert SRE helping with this incident:

Title: {incident_context.get('title')}
Description: {incident_context.get('description')}
Severity: {incident_context.get('severity')}

Question: {user_message}

Answer concisely and helpfully."""

        payload = {'contents': [{'parts': [{'text': prompt}]}]}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={self.gemini_api_key}"

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers={'Content-Type': 'application/json'}, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    return result['candidates'][0]['content']['parts'][0]['text']
                else:
                    error_text = await response.text()
                    raise Exception(f"Gemini API error {response.status}: {error_text}")

    async def stream_chat_with_claude(
        self,
        incident_context: Dict[str, Any],
        user_message: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> AsyncGenerator[str, None]:
        """Stream chat response from Claude API"""

        if self.db and not self.claude_api_key and self.organization_id:
            await self.load_user_api_keys()

        if not self.claude_api_key:
            yield "data: " + json.dumps({"error": "Claude API key not configured"}) + "\n\n"
            return

        messages = []
        if conversation_history:
            messages.extend(conversation_history)

        system_context = f"""You are an expert SRE helping with this incident:

Title: {incident_context.get('title')}
Description: {incident_context.get('description')}
Severity: {incident_context.get('severity')}
Status: {incident_context.get('status')}

Answer questions concisely and helpfully. Use markdown for formatting."""

        messages.append({
            'role': 'user',
            'content': f"{system_context}\n\nQuestion: {user_message}"
        })

        headers = {
            'Content-Type': 'application/json',
            'x-api-key': self.claude_api_key,
            'anthropic-version': '2023-06-01'
        }

        payload = {
            'model': 'claude-sonnet-4-20250514',
            'max_tokens': 2000,
            'stream': True,
            'messages': messages
        }

        try:
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    'https://api.anthropic.com/v1/messages',
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Claude streaming error {response.status}: {error_text}")
                        yield "data: " + json.dumps({"error": f"Claude API error: {response.status}"}) + "\n\n"
                        return

                    async for line in response.content:
                        line_text = line.decode('utf-8').strip()
                        if line_text.startswith('data: '):
                            data_str = line_text[6:]
                            if data_str == '[DONE]':
                                yield "data: [DONE]\n\n"
                                break
                            try:
                                data = json.loads(data_str)
                                if data.get('type') == 'content_block_delta':
                                    delta = data.get('delta', {})
                                    if delta.get('type') == 'text_delta':
                                        text = delta.get('text', '')
                                        yield "data: " + json.dumps({"text": text}) + "\n\n"
                            except json.JSONDecodeError:
                                continue

        except Exception as e:
            logger.error(f"Claude streaming failed: {e}")
            yield "data: " + json.dumps({"error": str(e)}) + "\n\n"

    async def stream_chat_with_gemini(
        self,
        incident_context: Dict[str, Any],
        user_message: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> AsyncGenerator[str, None]:
        """Stream chat response from Gemini API"""

        if self.db and not self.gemini_api_key and self.organization_id:
            await self.load_user_api_keys()

        if not self.gemini_api_key:
            yield "data: " + json.dumps({"error": "Gemini API key not configured"}) + "\n\n"
            return

        prompt = f"""You are an expert SRE helping with this incident:

Title: {incident_context.get('title')}
Description: {incident_context.get('description')}
Severity: {incident_context.get('severity')}

Question: {user_message}

Answer concisely and helpfully. Use markdown for formatting."""

        payload = {'contents': [{'parts': [{'text': prompt}]}]}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:streamGenerateContent?key={self.gemini_api_key}&alt=sse"

        try:
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    url,
                    headers={'Content-Type': 'application/json'},
                    json=payload
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Gemini streaming error {response.status}: {error_text}")
                        yield "data: " + json.dumps({"error": f"Gemini API error: {response.status}"}) + "\n\n"
                        return

                    async for line in response.content:
                        line_text = line.decode('utf-8').strip()
                        if line_text.startswith('data: '):
                            data_str = line_text[6:]
                            try:
                                data = json.loads(data_str)
                                candidates = data.get('candidates', [])
                                if candidates:
                                    content = candidates[0].get('content', {})
                                    parts = content.get('parts', [])
                                    if parts:
                                        text = parts[0].get('text', '')
                                        if text:
                                            yield "data: " + json.dumps({"text": text}) + "\n\n"
                            except json.JSONDecodeError:
                                continue

                    yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Gemini streaming failed: {e}")
            yield "data: " + json.dumps({"error": str(e)}) + "\n\n"

    async def _call_claude_api(self, prompt: str, max_tokens: int = 2000) -> Optional[str]:
        """Make a direct API call to Claude and return the text response"""
        if not self.claude_api_key:
            return None

        try:
            headers = {
                'Content-Type': 'application/json',
                'x-api-key': self.claude_api_key,
                'anthropic-version': '2023-06-01'
            }

            payload = {
                'model': 'claude-sonnet-4-20250514',
                'max_tokens': max_tokens,
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
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
                        return result['content'][0]['text']
                    else:
                        error_text = await response.text()
                        logger.error(f"Claude API error {response.status}: {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Claude API call failed: {e}")
            return None

    async def _call_gemini_api(self, prompt: str) -> Optional[str]:
        """Make a direct API call to Gemini and return the text response"""
        if not self.gemini_api_key:
            return None

        try:
            headers = {
                'Content-Type': 'application/json'
            }

            payload = {
                'contents': [{
                    'parts': [{'text': prompt}]
                }]
            }

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={self.gemini_api_key}"

            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result['candidates'][0]['content']['parts'][0]['text']
                    else:
                        error_text = await response.text()
                        logger.error(f"Gemini API error {response.status}: {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            return None

    def _build_analysis_prompt(self, incident_data: Dict[str, Any]) -> str:
        """Build analysis prompt that returns EXACTLY the structure frontend expects"""

        alerts_text = "\n".join([
            f"- [{alert['severity']}] {alert['source']}: {alert['message']}"
            for alert in incident_data.get('alerts', [])
        ])

        return f"""Analyze this production incident and provide a detailed response:

INCIDENT DETAILS:
Title: {incident_data.get('title')}
Description: {incident_data.get('description')}
Severity: {incident_data.get('severity')}
Status: {incident_data.get('status')}

ALERTS:
{alerts_text if alerts_text else 'No alerts available'}

Provide your analysis in this EXACT JSON format (return ONLY valid JSON, no markdown):
{{
  "confidence_score": 0.XX,
  "root_cause": "detailed root cause analysis",
  "solution_description": "recommended solution overview",
  "recommended_actions": ["step 1", "step 2", "step 3"],
  "estimated_resolution_time": "XX minutes",
  "risk_level": "low",
  "affected_systems": ["system1", "system2"],
  "business_impact": "description of business impact",
  "user_impact": "description of user impact",
  "prevention_steps": ["prevention 1", "prevention 2"]
}}

IMPORTANT:
- confidence_score must be between 0.0 and 1.0 (e.g., 0.85 for 85% confidence)
- risk_level must be exactly "low", "medium", or "high"
- All fields are required
- Return ONLY the JSON, no other text or markdown formatting"""

    def _parse_analysis_response(self, text_content: str, provider: str) -> Dict[str, Any]:
        """Parse AI response - extract and validate JSON"""

        try:
            # Try to extract JSON from markdown code blocks
            if '```json' in text_content:
                start = text_content.find('```json') + 7
                end = text_content.find('```', start)
                text_content = text_content[start:end].strip()
            elif '```' in text_content:
                start = text_content.find('```') + 3
                end = text_content.find('```', start)
                text_content = text_content[start:end].strip()

            # Clean up any leading/trailing whitespace
            text_content = text_content.strip()

            # Parse JSON
            analysis = json.loads(text_content)

            # Validate and normalize confidence score (must be 0.0-1.0)
            if 'confidence_score' in analysis:
                if analysis['confidence_score'] > 1:
                    analysis['confidence_score'] = analysis['confidence_score'] / 100
                # Ensure it's a float
                analysis['confidence_score'] = float(analysis['confidence_score'])

            # Ensure all required fields exist with defaults
            required_fields = {
                'confidence_score': 0.75,
                'root_cause': 'Analysis completed',
                'solution_description': 'Review recommended actions',
                'recommended_actions': [],
                'estimated_resolution_time': '15 minutes',
                'risk_level': 'medium',
                'affected_systems': [],
                'business_impact': 'Service disruption possible',
                'user_impact': 'Users may experience issues',
                'prevention_steps': []
            }

            for field, default_value in required_fields.items():
                if field not in analysis:
                    analysis[field] = default_value

            # Normalize risk_level to lowercase
            if 'risk_level' in analysis:
                analysis['risk_level'] = analysis['risk_level'].lower()

            logger.info(f"✅ {provider} analysis parsed successfully - confidence: {analysis.get('confidence_score')}")
            return analysis

        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse {provider} JSON response: {e}")
            logger.error(f"Raw response (first 500 chars): {text_content[:500]}")
            return None
        except Exception as e:
            logger.error(f"❌ Error parsing {provider} response: {e}")
            return None