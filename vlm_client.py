"""
VLM Client Module.
Async client for OpenRouter API using Qwen3-VL-8B model.
"""

import asyncio
import aiohttp
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from config import Config
from system_prompt import SYSTEM_PROMPT, get_analysis_prompt

logger = logging.getLogger(__name__)


@dataclass
class VLMResponse:
    """Container for VLM API response."""
    success: bool
    content: Optional[str] = None
    parsed_json: Optional[dict] = None
    error: Optional[str] = None
    usage: Optional[dict] = None
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "content": self.content,
            "parsed_json": self.parsed_json,
            "error": self.error,
            "usage": self.usage
        }


class VLMClient:
    """
    Async client for OpenRouter Vision-Language Model API.
    
    Uses qwen/qwen3-vl-8b-instruct for video frame analysis.
    Optimized for parallel requests with connection pooling.
    """
    
    def __init__(self, api_key: str = None, model: str = None, max_concurrent_per_key: int = None):
        """
        Initialize VLM client.
        
        Args:
            api_key: OpenRouter API key (uses Config if not provided)
            model: Model identifier (uses Config if not provided)
            max_concurrent_per_key: Max concurrent requests per API key (for live streams)
        """
        # Support for multiple API keys (load balancing)
        self.api_keys = Config.OPENROUTER_API_KEYS if Config.OPENROUTER_API_KEYS else [api_key or Config.OPENROUTER_API_KEY]
        self.current_key_index = 0
        self.api_key = self.api_keys[0] if self.api_keys else ""
        
        self.model = model or Config.VLM_MODEL
        self.base_url = Config.OPENROUTER_BASE_URL
        self.timeout = Config.VLM_REQUEST_TIMEOUT
        
        # Per-key semaphores for limiting concurrent requests (live stream optimization)
        self.max_concurrent_per_key = max_concurrent_per_key
        if max_concurrent_per_key:
            self.per_key_semaphores = {
                key: asyncio.Semaphore(max_concurrent_per_key) 
                for key in self.api_keys
            }
            logger.info(f"VLM Client: Limiting to {max_concurrent_per_key} concurrent requests per API key")
        else:
            self.per_key_semaphores = None
        
        # Log API key configuration
        if len(self.api_keys) > 1:
            logger.info(f"VLM Client initialized with {len(self.api_keys)} API keys for load balancing")
        
        # Reusable session for connection pooling (improves parallel performance)
        self._session: Optional[aiohttp.ClientSession] = None
    
    def _get_next_api_key(self) -> str:
        """
        Get next API key using round-robin rotation.
        
        Returns:
            API key string
        """
        if not self.api_keys:
            return ""
        
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return key
    
    def _get_headers(self, api_key: str) -> dict:
        """
        Get request headers for specific API key.
        
        Args:
            api_key: API key to use
            
        Returns:
            Headers dictionary
        """
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "video-analysis-pipeline",
            "X-Title": "Video Behavior Analyzer"
        }
    
    def _build_image_content(self, base64_images: List[str]) -> List[dict]:
        """
        Build multi-image content for the API request.
        
        Args:
            base64_images: List of base64 encoded images
        
        Returns:
            List of content objects for the API
        """
        content = []
        
        for i, b64_img in enumerate(base64_images):
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64_img}"
                }
            })
        
        return content
    
    async def get_session(self) -> aiohttp.ClientSession:
        """
        Get or create aiohttp session with connection pooling.
        Reuses connections for better performance in parallel requests.
        """
        if self._session is None or self._session.closed:
            # Configure connector for better parallel performance
            connector = aiohttp.TCPConnector(
                limit=Config.VLM_MAX_CONCURRENT * 2,  # Allow more connections than concurrent requests
                limit_per_host=Config.VLM_MAX_CONCURRENT * 2,
                ttl_dns_cache=300  # Cache DNS for 5 minutes
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
    
    async def analyze_frames(
        self,
        base64_frames: List[str],
        yolo_data: dict,
        temperature: float = 0.3,
        max_tokens: int = 2000
    ) -> VLMResponse:
        """
        Analyze multiple frames with YOLO context.
        
        Args:
            base64_frames: List of base64 encoded frame images
            yolo_data: YOLO detection data dictionary
            temperature: Model temperature (lower = more deterministic)
            max_tokens: Maximum response tokens
        
        Returns:
            VLMResponse with analysis results
        """
        if not self.api_key:
            return VLMResponse(
                success=False,
                error="OpenRouter API key not configured"
            )
        
        # Build user message with images and YOLO context
        user_content = self._build_image_content(base64_frames)
        user_content.append({
            "type": "text",
            "text": get_analysis_prompt(yolo_data, len(base64_frames))
        })
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": user_content
                }
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"}
        }
        
        # Get API key and headers for this request
        api_key = self._get_next_api_key()
        headers = self._get_headers(api_key)
        
        # Use per-key semaphore if configured (for live stream rate limiting)
        semaphore = None
        if self.per_key_semaphores:
            semaphore = self.per_key_semaphores.get(api_key)
        
        try:
            session = await self.get_session()
            response_data = None
            
            if semaphore:
                # Acquire semaphore to limit concurrent requests per key
                async with semaphore:
                    async with session.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.timeout)
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"❌ VLM API error {response.status}: {error_text[:200]}")
                            return VLMResponse(
                                success=False,
                                error=f"API error {response.status}: {error_text}"
                            )
                        response_data = await response.json()
            else:
                # No rate limiting
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"❌ VLM API error {response.status}: {error_text[:200]}")
                        return VLMResponse(
                            success=False,
                            error=f"API error {response.status}: {error_text}"
                        )
                    response_data = await response.json()
            
            # Extract content from response
            content = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            usage = response_data.get("usage", {})
            
            # Try to parse JSON response (may be wrapped in markdown)
            parsed_json = None
            try:
                parsed_json = json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code block
                import re
                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
                if json_match:
                    try:
                        parsed_json = json.loads(json_match.group(1))
                    except json.JSONDecodeError:
                        pass
                
                # If still no JSON, create a basic structure from content
                if parsed_json is None:
                    logger.debug("VLM response not JSON, using text-based fallback")
                    parsed_json = {
                        "observations": [],
                        "overall_assessment": {
                            "risk_score": 2,
                            "summary": content[:500] if content else "No analysis available",
                            "recommended_alerts": []
                        }
                    }
            
            return VLMResponse(
                success=True,
                content=content,
                parsed_json=parsed_json,
                usage=usage
            )
                    
        except asyncio.TimeoutError:
            logger.warning(f"VLM request timed out after {self.timeout}s")
            return VLMResponse(
                success=False,
                error=f"Request timed out after {self.timeout}s"
            )
        except aiohttp.ClientError as e:
            return VLMResponse(
                success=False,
                error=f"Network error: {str(e)}"
            )
        except Exception as e:
            return VLMResponse(
                success=False,
                error=f"Unexpected error: {str(e)}"
            )
    
    async def analyze_frames_parallel(
        self,
        frame_batches: List[List[str]],
        yolo_data_batches: List[dict]
    ) -> List[VLMResponse]:
        """
        Analyze multiple frame batches in parallel.
        
        Args:
            frame_batches: List of frame batches (each batch = 3 frames)
            yolo_data_batches: Corresponding YOLO data for each batch
        
        Returns:
            List of VLMResponse objects
        """
        tasks = [
            self.analyze_frames(frames, yolo_data)
            for frames, yolo_data in zip(frame_batches, yolo_data_batches)
        ]
        
        return await asyncio.gather(*tasks)


async def test_vlm_client():
    """Test VLM client with a simple request (no images)."""
    client = VLMClient()
    
    print(f"Testing VLM Client with model: {client.model}")
    print(f"API Key configured: {'Yes' if client.api_key else 'No'}")
    
    if not client.api_key:
        print("Error: Please set OPENROUTER_API_KEY in .env file")
        return
    
    # Simple test without images
    response = await client.analyze_frames(
        base64_frames=[],
        yolo_data={"detections": []}
    )
    
    print(f"Response success: {response.success}")
    if response.error:
        print(f"Error: {response.error}")
    else:
        print(f"Content: {response.content[:200] if response.content else 'None'}...")


if __name__ == "__main__":
    asyncio.run(test_vlm_client())
