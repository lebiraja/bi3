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
    """
    
    def __init__(self, api_key: str = None, model: str = None):
        """
        Initialize VLM client.
        
        Args:
            api_key: OpenRouter API key (uses Config if not provided)
            model: Model identifier (uses Config if not provided)
        """
        self.api_key = api_key or Config.OPENROUTER_API_KEY
        self.model = model or Config.VLM_MODEL
        self.base_url = Config.OPENROUTER_BASE_URL
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
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
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.base_url,
                    headers=self.headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return VLMResponse(
                            success=False,
                            error=f"API error {response.status}: {error_text}"
                        )
                    
                    result = await response.json()
                    
                    # Extract content from response
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    usage = result.get("usage", {})
                    
                    # Try to parse JSON response
                    parsed_json = None
                    try:
                        parsed_json = json.loads(content)
                    except json.JSONDecodeError:
                        logger.warning("Failed to parse VLM response as JSON")
                    
                    return VLMResponse(
                        success=True,
                        content=content,
                        parsed_json=parsed_json,
                        usage=usage
                    )
                    
        except asyncio.TimeoutError:
            return VLMResponse(
                success=False,
                error="Request timed out"
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
