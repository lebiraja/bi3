"""
Ollama Client Module.
Async client for Ollama API to interact with local LLM models (e.g., Gemma3-1B).
"""

import asyncio
import aiohttp
import json
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class OllamaResponse:
    """Container for Ollama API response."""
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    model: Optional[str] = None
    total_duration: Optional[int] = None  # nanoseconds
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "content": self.content,
            "error": self.error,
            "model": self.model,
            "total_duration": self.total_duration
        }


class OllamaClient:
    """
    Async client for Ollama API.
    
    Used for generating enhanced reports via local LLM models.
    Optimized for connection reuse and error handling.
    """
    
    def __init__(
        self,
        base_url: str = None,
        model: str = None,
        timeout: int = None
    ):
        """
        Initialize Ollama client.
        
        Args:
            base_url: Ollama API base URL (uses Config if not provided)
            model: Model identifier (uses Config if not provided)
            timeout: Request timeout in seconds (uses Config if not provided)
        """
        self.base_url = base_url or Config.OLLAMA_BASE_URL
        self.model = model or Config.OLLAMA_MODEL
        self.timeout = timeout or Config.OLLAMA_TIMEOUT
        
        # Reusable session for connection pooling
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def get_session(self) -> aiohttp.ClientSession:
        """
        Get or create aiohttp session with connection pooling.
        """
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=5,
                limit_per_host=5,
                ttl_dns_cache=300
            )
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self._session
    
    async def close(self):
        """Close the aiohttp session and cleanup resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    async def check_health(self) -> bool:
        """
        Check if Ollama is running and the model is available.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            session = await self.get_session()
            async with session.get(f"{self.base_url}/api/tags") as response:
                if response.status == 200:
                    data = await response.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    # Check if our model is available (with or without :latest tag)
                    model_base = self.model.split(":")[0]
                    return any(model_base in m for m in models)
                return False
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> OllamaResponse:
        """
        Generate text using Ollama API.
        
        Args:
            prompt: User prompt/input
            system_prompt: Optional system prompt for context
            temperature: Model temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
        
        Returns:
            OllamaResponse with generated text
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        try:
            session = await self.get_session()
            async with session.post(
                f"{self.base_url}/api/generate",
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Ollama API error {response.status}: {error_text}")
                    return OllamaResponse(
                        success=False,
                        error=f"API error {response.status}: {error_text}"
                    )
                
                result = await response.json()
                
                return OllamaResponse(
                    success=True,
                    content=result.get("response", ""),
                    model=result.get("model", self.model),
                    total_duration=result.get("total_duration")
                )
                
        except asyncio.TimeoutError:
            logger.warning(f"Ollama request timed out after {self.timeout}s")
            return OllamaResponse(
                success=False,
                error=f"Request timed out after {self.timeout}s"
            )
        except aiohttp.ClientError as e:
            logger.error(f"Ollama network error: {e}")
            return OllamaResponse(
                success=False,
                error=f"Network error: {str(e)}"
            )
        except Exception as e:
            logger.exception("Unexpected Ollama error")
            return OllamaResponse(
                success=False,
                error=f"Unexpected error: {str(e)}"
            )
    
    async def generate_enhanced_report(
        self,
        prompt: str,
        system_prompt: str
    ) -> OllamaResponse:
        """
        Generate enhanced report using specialized settings.
        
        Uses lower temperature for more consistent, formal output.
        
        Args:
            prompt: Report generation prompt with VLM data
            system_prompt: Enhanced report system prompt
        
        Returns:
            OllamaResponse with generated report
        """
        return await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,  # Lower for more consistent formal output
            max_tokens=6000   # Allow longer reports
        )


async def test_ollama_client():
    """Test Ollama client connectivity."""
    client = OllamaClient()
    
    print(f"Testing Ollama Client")
    print(f"Base URL: {client.base_url}")
    print(f"Model: {client.model}")
    
    # Health check
    healthy = await client.check_health()
    print(f"Ollama healthy: {healthy}")
    
    if healthy:
        # Simple test generation
        response = await client.generate(
            prompt="Say 'Hello, I am ready to generate reports.' in one sentence.",
            temperature=0.1
        )
        print(f"Response success: {response.success}")
        if response.success:
            print(f"Content: {response.content}")
        else:
            print(f"Error: {response.error}")
    
    await client.close()


if __name__ == "__main__":
    asyncio.run(test_ollama_client())
