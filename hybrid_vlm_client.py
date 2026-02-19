"""
Hybrid VLM Client Module.
Supports both Ollama (local) and OpenRouter (cloud) VLM providers.
Used for traffic behavior analysis from video frames.
"""

import asyncio
import aiohttp
import json
import logging
import time
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from config import Config
from system_prompt import SYSTEM_PROMPT, get_analysis_prompt

logger = logging.getLogger(__name__)


class VLMProvider(Enum):
    """VLM provider types."""
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"


@dataclass
class VisionAnalysisResult:
    """Container for vision analysis response."""
    success: bool
    content: Optional[str] = None
    parsed_json: Optional[dict] = None
    error: Optional[str] = None
    model: Optional[str] = None
    processing_time_ms: Optional[float] = None
    provider: Optional[str] = None
    usage: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "content": self.content,
            "parsed_json": self.parsed_json,
            "error": self.error,
            "model": self.model,
            "processing_time_ms": self.processing_time_ms,
            "provider": self.provider,
            "usage": self.usage
        }


class HybridVLMClient:
    """
    Hybrid VLM client supporting both Ollama (local) and OpenRouter (cloud).
    
    Automatically selects provider based on configuration or manual override.
    Optimized for GPU inference with concurrency control.
    """

    def __init__(
        self,
        provider: VLMProvider = None,
        base_url: str = None,
        model: str = None,
        api_key: str = None,
        timeout: int = None,
        max_concurrent: int = None
    ):
        """
        Initialize Hybrid VLM client.
        
        Args:
            provider: VLMProvider enum (auto-detects if None)
            base_url: API base URL (uses Config if not provided)
            model: Vision model identifier (uses Config if not provided)
            api_key: API key for OpenRouter (uses Config if not provided)
            timeout: Request timeout in seconds (uses Config if not provided)
            max_concurrent: Maximum concurrent requests
        """
        # Auto-detect provider based on config
        if provider is None:
            # Check if OpenRouter API key is configured
            if hasattr(Config, 'OPENROUTER_API_KEY') and Config.OPENROUTER_API_KEY:
                provider = VLMProvider.OPENROUTER
            else:
                provider = VLMProvider.OLLAMA
        
        self.provider = provider
        
        # Configure based on provider
        if self.provider == VLMProvider.OLLAMA:
            self.base_url = base_url or getattr(Config, 'OLLAMA_BASE_URL', 'http://localhost:11434')
            self.model = model or getattr(Config, 'OLLAMA_VISION_MODEL', 'gemma3:4b')
            self.timeout = timeout or getattr(Config, 'OLLAMA_VISION_TIMEOUT', 120)
            self.max_concurrent = max_concurrent or getattr(Config, 'VLM_MAX_CONCURRENT', 5)
            self.api_key = None
            self.api_keys = []
        else:  # OPENROUTER
            self.base_url = base_url or getattr(Config, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
            self.model = model or getattr(Config, 'VLM_MODEL', 'qwen/qwen3-vl-8b-instruct')
            self.timeout = timeout or getattr(Config, 'VLM_REQUEST_TIMEOUT', 60)
            self.max_concurrent = max_concurrent or getattr(Config, 'VLM_MAX_CONCURRENT', 10)
            
            # Support for multiple API keys (load balancing)
            self.api_keys = getattr(Config, 'OPENROUTER_API_KEYS', [])
            if not self.api_keys and hasattr(Config, 'OPENROUTER_API_KEY'):
                self.api_keys = [Config.OPENROUTER_API_KEY]
            self.api_key = self.api_keys[0] if self.api_keys else (api_key or "")
            self.current_key_index = 0
        
        # Semaphore for concurrency management
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        
        # Per-key semaphores for OpenRouter
        if self.provider == VLMProvider.OPENROUTER and self.api_keys:
            per_key_limit = getattr(Config, 'STREAM_VLM_MAX_PER_KEY', 3)
            self.per_key_semaphores = {
                key: asyncio.Semaphore(per_key_limit) 
                for key in self.api_keys
            }
            logger.info(f"OpenRouter: Limiting to {per_key_limit} concurrent requests per API key")
        else:
            self.per_key_semaphores = None
        
        # Reusable session for connection pooling
        self._session: Optional[aiohttp.ClientSession] = None
        
        logger.info(f"HybridVLMClient initialized: provider={self.provider.value}, model={self.model}, max_concurrent={self.max_concurrent}")

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session with connection pooling."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=self.max_concurrent * 2,
                limit_per_host=self.max_concurrent * 2,
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
        Check if VLM provider is running and model is available.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            session = await self.get_session()
            
            if self.provider == VLMProvider.OLLAMA:
                async with session.get(f"{self.base_url}/api/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        models = [m.get("name", "") for m in data.get("models", [])]
                        model_base = self.model.split(":")[0]
                        return any(model_base in m for m in models)
                    return False
            else:  # OPENROUTER
                # Simple connectivity test
                headers = self._get_openrouter_headers()
                async with session.get(f"{self.base_url}/models", headers=headers) as response:
                    return response.status == 200
                    
        except Exception as e:
            logger.warning(f"VLM health check failed: {e}")
            return False

    def _get_next_api_key(self) -> str:
        """Get next API key using round-robin rotation (OpenRouter only)."""
        if not self.api_keys:
            return self.api_key or ""
        
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return key

    def _get_openrouter_headers(self, api_key: str = None) -> dict:
        """Get request headers for OpenRouter."""
        key = api_key or self.api_key
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "video-analysis-pipeline",
            "X-Title": "Video Behavior Analyzer"
        }

    def _strip_base64_prefix(self, base64_str: str) -> str:
        """Remove data URI prefix from base64 string if present."""
        if base64_str.startswith("data:"):
            parts = base64_str.split(",", 1)
            if len(parts) > 1:
                return parts[1]
        return base64_str

    def _parse_json_response(self, content: str) -> Optional[dict]:
        """
        Parse JSON from VLM response, handling various formats.
        
        Args:
            content: Raw response content
        
        Returns:
            Parsed JSON dict or None if parsing fails
        """
        if not content:
            return None

        # Try direct JSON parsing first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code blocks
        json_pattern = r'```(?:json)?\s*([\s\S]*?)```'
        matches = re.findall(json_pattern, content)

        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

        # Try finding JSON object in content
        try:
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass

        logger.warning(f"Failed to parse JSON from response: {content[:200]}...")
        return None

    async def analyze_frames_ollama(
        self,
        base64_frames: List[str],
        yolo_context: Dict[str, Any],
        temperature: float = 0.2,
        max_tokens: int = 600
    ) -> VisionAnalysisResult:
        """Analyze frames using Ollama local API."""
        start_time = time.time()
        
        # Build the analysis prompt with YOLO context
        user_prompt = get_analysis_prompt(yolo_context, len(base64_frames))
        
        # Combine system prompt and user prompt for Ollama
        full_prompt = f"""{SYSTEM_PROMPT}

{user_prompt}"""
        
        # Strip any data URI prefixes from images
        clean_images = [self._strip_base64_prefix(img) for img in base64_frames]
        
        # Build Ollama request payload
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "images": clean_images,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        async with self.semaphore:
            try:
                session = await self.get_session()
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload
                ) as response:
                    processing_time = (time.time() - start_time) * 1000
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Ollama API error {response.status}: {error_text}")
                        
                        if "out of memory" in error_text.lower() or "cuda" in error_text.lower():
                            logger.warning("GPU OOM detected, consider reducing concurrency")
                        
                        return VisionAnalysisResult(
                            success=False,
                            error=f"API error {response.status}: {error_text}",
                            processing_time_ms=processing_time,
                            provider="ollama"
                        )
                    
                    result = await response.json()
                    content = result.get("response", "")
                    
                    # Parse JSON from response
                    parsed_json = self._parse_json_response(content)
                    
                    return VisionAnalysisResult(
                        success=True,
                        content=content,
                        parsed_json=parsed_json,
                        model=result.get("model", self.model),
                        processing_time_ms=processing_time,
                        provider="ollama"
                    )
                    
            except asyncio.TimeoutError:
                processing_time = (time.time() - start_time) * 1000
                logger.warning(f"Ollama request timed out after {self.timeout}s")
                return VisionAnalysisResult(
                    success=False,
                    error=f"Request timed out after {self.timeout}s",
                    processing_time_ms=processing_time,
                    provider="ollama"
                )
                
            except aiohttp.ClientError as e:
                processing_time = (time.time() - start_time) * 1000
                logger.error(f"Ollama network error: {e}")
                return VisionAnalysisResult(
                    success=False,
                    error=f"Network error: {str(e)}",
                    processing_time_ms=processing_time,
                    provider="ollama"
                )
                
            except Exception as e:
                processing_time = (time.time() - start_time) * 1000
                logger.exception("Unexpected Ollama error")
                return VisionAnalysisResult(
                    success=False,
                    error=f"Unexpected error: {str(e)}",
                    processing_time_ms=processing_time,
                    provider="ollama"
                )

    async def analyze_frames_openrouter(
        self,
        base64_frames: List[str],
        yolo_context: Dict[str, Any],
        temperature: float = 0.3,
        max_tokens: int = 2000
    ) -> VisionAnalysisResult:
        """Analyze frames using OpenRouter API."""
        start_time = time.time()
        
        if not self.api_key:
            return VisionAnalysisResult(
                success=False,
                error="OpenRouter API key not configured",
                provider="openrouter"
            )
        
        # Build user message with images and YOLO context
        user_content = []
        for img in base64_frames:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img}"}
            })
        
        user_content.append({
            "type": "text",
            "text": get_analysis_prompt(yolo_context, len(base64_frames))
        })
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"}
        }
        
        # Get API key and headers for this request
        api_key = self._get_next_api_key()
        headers = self._get_openrouter_headers(api_key)
        
        # Use per-key semaphore if configured
        semaphore = self.per_key_semaphores.get(api_key) if self.per_key_semaphores else self.semaphore
        
        async with semaphore:
            try:
                session = await self.get_session()
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                ) as response:
                    processing_time = (time.time() - start_time) * 1000
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenRouter API error {response.status}: {error_text[:200]}")
                        return VisionAnalysisResult(
                            success=False,
                            error=f"API error {response.status}: {error_text}",
                            processing_time_ms=processing_time,
                            provider="openrouter"
                        )
                    
                    result = await response.json()
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    usage = result.get("usage", {})
                    
                    # Parse JSON from response
                    parsed_json = self._parse_json_response(content)
                    
                    return VisionAnalysisResult(
                        success=True,
                        content=content,
                        parsed_json=parsed_json,
                        model=self.model,
                        processing_time_ms=processing_time,
                        provider="openrouter",
                        usage=usage
                    )
                    
            except asyncio.TimeoutError:
                processing_time = (time.time() - start_time) * 1000
                logger.warning(f"OpenRouter request timed out after {self.timeout}s")
                return VisionAnalysisResult(
                    success=False,
                    error=f"Request timed out after {self.timeout}s",
                    processing_time_ms=processing_time,
                    provider="openrouter"
                )
                
            except aiohttp.ClientError as e:
                processing_time = (time.time() - start_time) * 1000
                logger.error(f"OpenRouter network error: {e}")
                return VisionAnalysisResult(
                    success=False,
                    error=f"Network error: {str(e)}",
                    processing_time_ms=processing_time,
                    provider="openrouter"
                )
                
            except Exception as e:
                processing_time = (time.time() - start_time) * 1000
                logger.exception("Unexpected OpenRouter error")
                return VisionAnalysisResult(
                    success=False,
                    error=f"Unexpected error: {str(e)}",
                    processing_time_ms=processing_time,
                    provider="openrouter"
                )

    async def analyze_frames(
        self,
        base64_frames: List[str],
        yolo_context: Dict[str, Any],
        temperature: float = None,
        max_tokens: int = None
    ) -> VisionAnalysisResult:
        """
        Analyze video frames with vision model (auto-routes to provider).
        
        Args:
            base64_frames: List of base64-encoded frame images
            yolo_context: YOLO detection data for context
            temperature: Model temperature (provider-specific defaults)
            max_tokens: Maximum tokens in response (provider-specific defaults)
        
        Returns:
            VisionAnalysisResult with analysis data
        """
        # Set provider-specific defaults
        if temperature is None:
            temperature = 0.2 if self.provider == VLMProvider.OLLAMA else 0.3
        
        if max_tokens is None:
            max_tokens = 600 if self.provider == VLMProvider.OLLAMA else 2000
        
        # Route to appropriate provider
        if self.provider == VLMProvider.OLLAMA:
            return await self.analyze_frames_ollama(
                base64_frames, yolo_context, temperature, max_tokens
            )
        else:
            return await self.analyze_frames_openrouter(
                base64_frames, yolo_context, temperature, max_tokens
            )

    async def analyze_frames_batch(
        self,
        frame_batches: List[List[str]],
        yolo_contexts: List[Dict[str, Any]],
        temperature: float = None,
        progress_callback: Optional[callable] = None
    ) -> List[VisionAnalysisResult]:
        """
        Analyze multiple frame batches in parallel.
        
        Args:
            frame_batches: List of frame batches (each batch is base64 images)
            yolo_contexts: List of YOLO contexts for each batch
            temperature: Model temperature
            progress_callback: Optional callback for progress updates
        
        Returns:
            List of VisionAnalysisResult for each batch
        """
        if len(frame_batches) != len(yolo_contexts):
            raise ValueError("frame_batches and yolo_contexts must have same length")

        async def analyze_with_progress(idx: int, frames: List[str], context: Dict):
            result = await self.analyze_frames(frames, context, temperature)
            if progress_callback:
                try:
                    await progress_callback(idx, len(frame_batches), result)
                except Exception as e:
                    logger.warning(f"Progress callback error: {e}")
            return result

        # Run all analyses in parallel (semaphore controls concurrency)
        tasks = [
            analyze_with_progress(i, frames, context)
            for i, (frames, context) in enumerate(zip(frame_batches, yolo_contexts))
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append(VisionAnalysisResult(
                    success=False,
                    error=str(result),
                    provider=self.provider.value
                ))
            else:
                processed_results.append(result)

        return processed_results


async def test_hybrid_vlm_client():
    """Test Hybrid VLM client connectivity and basic inference."""
    import cv2
    import base64
    import numpy as np

    # Test both providers
    for provider in [VLMProvider.OLLAMA, VLMProvider.OPENROUTER]:
        print(f"\n{'='*60}")
        print(f"Testing {provider.value.upper()} Provider")
        print(f"{'='*60}")
        
        try:
            client = HybridVLMClient(provider=provider)
            
            print(f"Base URL: {client.base_url}")
            print(f"Model: {client.model}")
            print(f"Max Concurrent: {client.max_concurrent}")
            
            # Health check
            healthy = await client.check_health()
            print(f"Provider healthy: {healthy}")
            
            if healthy:
                # Create a simple test image
                test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.rectangle(test_frame, (100, 100), (200, 200), (255, 0, 0), 2)
                
                # Encode to base64
                _, buffer = cv2.imencode('.jpg', test_frame)
                test_base64 = base64.b64encode(buffer).decode('utf-8')
                
                # Test analysis
                print("\nTesting vision analysis...")
                result = await client.analyze_frames(
                    base64_frames=[test_base64],
                    yolo_context={
                        "detections": [[{"track_id": 1, "class_name": "car"}]],
                        "vehicle_counts": [1]
                    }
                )
                
                print(f"Success: {result.success}")
                print(f"Processing time: {result.processing_time_ms:.0f}ms")
                if result.success:
                    print(f"Parsed JSON: {result.parsed_json is not None}")
                    if result.parsed_json:
                        risk = result.parsed_json.get('overall_assessment', {}).get('risk_score', 'N/A')
                        print(f"Risk score: {risk}")
                else:
                    print(f"Error: {result.error}")
            
            await client.close()
            
        except Exception as e:
            print(f"Test failed for {provider.value}: {e}")


if __name__ == "__main__":
    asyncio.run(test_hybrid_vlm_client())
