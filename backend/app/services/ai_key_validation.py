# backend/app/services/ai_key_validation.py - NEW FILE
import aiohttp
import asyncio
import logging
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)

class AIKeyValidationService:
    """Service for validating user-provided AI API keys"""
    
    @staticmethod
    async def validate_openai_key(api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate OpenAI API key"""
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Test with a simple models request
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.openai.com/v1/models",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        return True, None
                    else:
                        error_text = await response.text()
                        return False, f"OpenAI API error: {response.status} - {error_text}"
                        
        except asyncio.TimeoutError:
            return False, "OpenAI API timeout"
        except Exception as e:
            return False, f"OpenAI validation error: {str(e)}"
    
    @staticmethod
    async def validate_gemini_key(api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate Google Gemini API key"""
        try:
            # Test with a simple request to Gemini API
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://generativelanguage.googleapis.com/v1/models?key={api_key}",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        return True, None
                    else:
                        error_text = await response.text()
                        return False, f"Gemini API error: {response.status} - {error_text}"
                        
        except asyncio.TimeoutError:
            return False, "Gemini API timeout"
        except Exception as e:
            return False, f"Gemini validation error: {str(e)}"
    
    @staticmethod
    async def validate_claude_key(api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate Anthropic Claude API key"""
        try:
            headers = {
                "x-api-key": api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            }
            
            # Test with a simple messages request
            payload = {
                "model": "claude-3-haiku-20240307",
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "Hi"}]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        return True, None
                    else:
                        error_text = await response.text()
                        return False, f"Claude API error: {response.status} - {error_text}"
                        
        except asyncio.TimeoutError:
            return False, "Claude API timeout"
        except Exception as e:
            return False, f"Claude validation error: {str(e)}"
    
    @staticmethod
    async def validate_api_key(provider: str, api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate API key based on provider"""
        if provider == "openai":
            return await AIKeyValidationService.validate_openai_key(api_key)
        elif provider == "gemini":
            return await AIKeyValidationService.validate_gemini_key(api_key)
        elif provider == "claude":
            return await AIKeyValidationService.validate_claude_key(api_key)
        else:
            return False, f"Unsupported provider: {provider}"