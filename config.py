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
    
    # OpenRouter API Settings
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1/chat/completions"
    VLM_MODEL: str = "qwen/qwen3-vl-8b-instruct"
    
    # MongoDB Settings
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "video_analysis")
    MONGODB_COLLECTION: str = os.getenv("MONGODB_COLLECTION", "frames")
    
    # Frame Sampling Settings
    FRAMES_PER_SECOND: int = 3  # Number of frames to sample per second
    SAMPLE_INTERVAL: int = 10  # Extract 1 frame every N frames (30fps / 3 = 10)
    
    # YOLO Settings
    YOLO_MODEL_PATH: str = "yolo11n.pt"
    YOLO_CONFIDENCE: float = 0.3
    YOLO_IOU: float = 0.5
    VEHICLE_CLASSES: list = [2, 3, 5, 7]  # car, motorcycle, bus, truck
    
    # Parallel Processing Settings
    VLM_MAX_CONCURRENT: int = int(os.getenv("VLM_MAX_CONCURRENT", "4"))  # Concurrent VLM API calls
    
    # Class name mapping (COCO dataset)
    CLASS_NAMES: dict = {
        2: "car",
        3: "motorcycle", 
        5: "bus",
        7: "truck"
    }
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration settings."""
        if not cls.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY is required. Please set it in .env file.")
        return True
