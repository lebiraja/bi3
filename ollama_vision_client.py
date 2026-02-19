"""
Ollama Vision Client Module.
Async client for Ollama API with vision support for qwen2.5-vl model.
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

from config import Config
from system_prompt import SYSTEM_PROMPT, get_analysis_prompt

logger = logging.getLogger(__name__)


@dataclass
class VisionAnalysisResult:
    """Container for vision analysis response."""
    success: bool
    content: Optional[str] = None
    parsed_json: Optional[dict] = None
    error: Optional[str] = None
    model: Optional[str] = None
    processing_time_ms: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "content": self.content,
            "parsed_json": self.parsed_json,
            "error": self.error,
            "model": self.model,
            "processing_time_ms": self.processing_time_ms
        }


class OllamaVisionClient:
    """
    Async client for Ollama Vision API.

    Supports qwen2.5-vl:3b model for traffic frame analysis.
    Optimized for GPU inference with concurrency control.
    """

    def __init__(
        self,
        base_url: str = None,
        model: str = None,
        timeout: int = None,
        max_concurrent: int = None
    ):
        """
        Initialize Ollama Vision client.

        Args:
            base_url: Ollama API base URL (uses Config if not provided)
            model: Vision model identifier (uses Config if not provided)
            timeout: Request timeout in seconds (uses Config if not provided)
            max_concurrent: Maximum concurrent requests (for GPU memory management)
        """
        self.base_url = base_url or getattr(Config, 'OLLAMA_BASE_URL', 'http://localhost:11434')
        self.model = model or getattr(Config, 'OLLAMA_VISION_MODEL', 'qwen2.5vl:3b')
        self.timeout = timeout or getattr(Config, 'OLLAMA_VISION_TIMEOUT', 120)
        self.max_concurrent = max_concurrent or getattr(Config, 'VLM_MAX_CONCURRENT', 5)

        # Semaphore for GPU memory management
        self.semaphore = asyncio.Semaphore(self.max_concurrent)

        # Reusable session for connection pooling
        self._session: Optional[aiohttp.ClientSession] = None

        logger.info(f"OllamaVisionClient initialized: model={self.model}, max_concurrent={self.max_concurrent}")

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
        Check if Ollama is running and the vision model is available.

        Returns:
            True if healthy, False otherwise
        """
        try:
            session = await self.get_session()
            async with session.get(f"{self.base_url}/api/tags") as response:
                if response.status == 200:
                    data = await response.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    # Check if our model is available (with or without tag)
                    model_base = self.model.split(":")[0]
                    return any(model_base in m for m in models)
                return False
        except Exception as e:
            logger.warning(f"Ollama vision health check failed: {e}")
            return False

    def _strip_base64_prefix(self, base64_str: str) -> str:
        """Remove data URI prefix from base64 string if present."""
        if base64_str.startswith("data:"):
            # Remove "data:image/jpeg;base64," or similar
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

    async def analyze_frames(
        self,
        base64_frames: List[str],
        yolo_context: Dict[str, Any],
        temperature: float = 0.2,
        max_tokens: int = 600  # Slightly increased to avoid truncated JSON
    ) -> VisionAnalysisResult:
        """
        Analyze video frames with vision model.

        Args:
            base64_frames: List of base64-encoded frame images
            yolo_context: YOLO detection data for context
            temperature: Model temperature (0.0-1.0)
            max_tokens: Maximum tokens in response

        Returns:
            VisionAnalysisResult with analysis data
        """
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
                        logger.error(f"Ollama vision API error {response.status}: {error_text}")

                        # Check for CUDA OOM
                        if "out of memory" in error_text.lower() or "cuda" in error_text.lower():
                            logger.warning("GPU OOM detected, consider reducing concurrency")

                        return VisionAnalysisResult(
                            success=False,
                            error=f"API error {response.status}: {error_text}",
                            processing_time_ms=processing_time
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
                        processing_time_ms=processing_time
                    )

            except asyncio.TimeoutError:
                processing_time = (time.time() - start_time) * 1000
                logger.warning(f"Ollama vision request timed out after {self.timeout}s")
                return VisionAnalysisResult(
                    success=False,
                    error=f"Request timed out after {self.timeout}s",
                    processing_time_ms=processing_time
                )

            except aiohttp.ClientError as e:
                processing_time = (time.time() - start_time) * 1000
                logger.error(f"Ollama vision network error: {e}")
                return VisionAnalysisResult(
                    success=False,
                    error=f"Network error: {str(e)}",
                    processing_time_ms=processing_time
                )

            except Exception as e:
                processing_time = (time.time() - start_time) * 1000
                logger.exception("Unexpected Ollama vision error")
                return VisionAnalysisResult(
                    success=False,
                    error=f"Unexpected error: {str(e)}",
                    processing_time_ms=processing_time
                )

    async def analyze_frames_batch(
        self,
        frame_batches: List[List[str]],
        yolo_contexts: List[Dict[str, Any]],
        temperature: float = 0.3,
        progress_callback: Optional[callable] = None
    ) -> List[VisionAnalysisResult]:
        """
        Analyze multiple frame batches in parallel.

        Args:
            frame_batches: List of frame batches (each batch is 3 base64 images)
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
                    error=str(result)
                ))
            else:
                processed_results.append(result)

        return processed_results


async def test_ollama_vision_client():
    """Test Ollama vision client connectivity and basic inference."""
    import cv2
    import base64
    import numpy as np

    client = OllamaVisionClient()

    print(f"Testing Ollama Vision Client")
    print(f"Base URL: {client.base_url}")
    print(f"Model: {client.model}")
    print(f"Max Concurrent: {client.max_concurrent}")

    # Health check
    healthy = await client.check_health()
    print(f"Ollama healthy: {healthy}")

    if healthy:
        # Create a simple test image (black frame with some rectangles)
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.rectangle(test_frame, (100, 100), (200, 200), (255, 0, 0), 2)
        cv2.rectangle(test_frame, (300, 150), (450, 300), (0, 255, 0), 2)

        # Encode to base64
        _, buffer = cv2.imencode('.jpg', test_frame)
        test_base64 = base64.b64encode(buffer).decode('utf-8')

        # Test analysis
        print("\nTesting vision analysis...")
        result = await client.analyze_frames(
            base64_frames=[test_base64, test_base64, test_base64],
            yolo_context={
                "detections": [
                    [{"track_id": 1, "class_name": "car", "bbox": [100, 100, 200, 200]}],
                    [{"track_id": 1, "class_name": "car", "bbox": [105, 105, 205, 205]}],
                    [{"track_id": 1, "class_name": "car", "bbox": [110, 110, 210, 210]}]
                ]
            },
            temperature=0.3
        )

        print(f"Success: {result.success}")
        print(f"Processing time: {result.processing_time_ms:.0f}ms")
        if result.success:
            print(f"Parsed JSON: {result.parsed_json is not None}")
            if result.parsed_json:
                print(f"Risk score: {result.parsed_json.get('overall_assessment', {}).get('risk_score', 'N/A')}")
        else:
            print(f"Error: {result.error}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(test_ollama_vision_client())
