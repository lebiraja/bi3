"""
Configuration module for Video Analysis Pipeline.
Loads settings from environment variables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(Path(__file__).parent / ".env")


class Config:
    """Configuration settings for the video analysis pipeline."""

    # MongoDB Settings
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "video_analysis")
    MONGODB_COLLECTION: str = os.getenv("MONGODB_COLLECTION", "frames")

    # Frame Sampling Settings
    FRAMES_PER_SECOND: int = 3  # Number of frames to sample per second
    SAMPLE_INTERVAL: int = 10  # Extract 1 frame every N frames (30fps / 3 = 10)

    # YOLO Settings
    YOLO_MODEL_PATH: str = "yolo11n.pt"
    YOLO_CONFIDENCE: float = 0.25  # Lower for better detection in busy scenes
    YOLO_IOU: float = 0.45  # Slightly lower for overlapping vehicles
    VEHICLE_CLASSES: list = [2, 3, 5, 7]  # car, motorcycle, bus, truck

    # Class name mapping (COCO dataset)
    CLASS_NAMES: dict = {
        2: "car",
        3: "motorcycle",
        5: "bus",
        7: "truck"
    }

    # Ollama Vision Settings (Local VLM for traffic analysis)
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_VISION_MODEL: str = os.getenv("OLLAMA_VISION_MODEL", "gemma3:4b")
    OLLAMA_VISION_TIMEOUT: int = int(os.getenv("OLLAMA_VISION_TIMEOUT", "120"))

    # Ollama Text Settings (for enhanced report generation)
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "gemma3:1b")
    OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "120"))

    # VLM Processing Settings (for local GPU)
    VLM_MAX_CONCURRENT: int = int(os.getenv("VLM_MAX_CONCURRENT", "5"))  # Reduced for local GPU
    VLM_REQUEST_TIMEOUT: int = int(os.getenv("VLM_REQUEST_TIMEOUT", "120"))  # Longer for local inference
    VLM_RETRY_ATTEMPTS: int = int(os.getenv("VLM_RETRY_ATTEMPTS", "2"))

    # Continuous Streaming Configuration (NEW)
    STREAM_VLM_SAMPLE_INTERVAL: float = float(os.getenv("STREAM_VLM_SAMPLE_INTERVAL", "2.0"))  # Sample every N seconds
    STREAM_VLM_MIN_VEHICLES: int = int(os.getenv("STREAM_VLM_MIN_VEHICLES", "2"))  # Min vehicles to trigger VLM
    STREAM_YOLO_FPS: int = 30  # Process all frames from stream
    STREAM_WEBSOCKET_FPS: int = 15  # Broadcast annotated frames at this FPS
    STREAM_CONTEXT_WINDOW: float = 6.0  # Seconds of history for VLM context

    # Stream Connection Settings
    STREAM_MAX_CONCURRENT: int = 3  # max concurrent streams
    STREAM_QUALITY: str = "720p"  # preferred stream quality
    STREAM_TIMEOUT: int = 60  # stream connection timeout
    STREAM_BUFFER_SIZE: int = 90  # frame buffer size (~3s at 30fps)

    # Legacy batch settings (kept for backward compatibility, will be removed)
    STREAM_BATCH_DURATION: int = 15  # seconds to process per batch
    STREAM_WAIT_DURATION: int = 5  # seconds to wait between batches
    STREAM_INIT_DURATION: int = 20  # seconds for initialization

    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration settings."""
        # Check Ollama is accessible (optional - don't fail if not)
        return True

    @classmethod
    def get_vlm_info(cls) -> dict:
        """Get VLM configuration info for logging."""
        return {
            "model": cls.OLLAMA_VISION_MODEL,
            "base_url": cls.OLLAMA_BASE_URL,
            "max_concurrent": cls.VLM_MAX_CONCURRENT,
            "timeout": cls.OLLAMA_VISION_TIMEOUT,
            "sample_interval": cls.STREAM_VLM_SAMPLE_INTERVAL
        }
