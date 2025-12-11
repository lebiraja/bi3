"""
Frame Sampler Module.
Extracts frames from video at specified intervals for VLM analysis.
"""

import cv2
import base64
import numpy as np
from pathlib import Path
from typing import Generator, Tuple, List, Optional
from dataclasses import dataclass
from datetime import datetime

from config import Config


@dataclass
class FrameData:
    """Container for extracted frame data."""
    frame_number: int
    timestamp_ms: float
    image_data: np.ndarray
    base64_encoded: str
    width: int
    height: int
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "frame_number": self.frame_number,
            "timestamp_ms": self.timestamp_ms,
            "base64_encoded": self.base64_encoded,
            "width": self.width,
            "height": self.height,
            "extracted_at": datetime.utcnow().isoformat()
        }


class FrameSampler:
    """
    Extracts frames from video at specified intervals.
    
    Sampling Strategy:
    - For 30 FPS video: Extract 1 frame every 10 frames (3 frames per second)
    - Each 1-second interval yields 3 frames for parallel VLM processing
    """
    
    def __init__(self, video_path: str, sample_interval: int = None):
        """
        Initialize frame sampler.
        
        Args:
            video_path: Path to the input video file
            sample_interval: Extract 1 frame every N frames (default from config)
        """
        self.video_path = Path(video_path)
        if not self.video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        self.sample_interval = sample_interval or Config.SAMPLE_INTERVAL
        self.cap = None
        self._open_video()
    
    def _open_video(self):
        """Open video capture."""
        self.cap = cv2.VideoCapture(str(self.video_path))
        if not self.cap.isOpened():
            raise ValueError(f"Failed to open video: {self.video_path}")
        
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.duration_seconds = self.total_frames / self.fps if self.fps > 0 else 0
    
    @staticmethod
    def encode_frame_base64(frame: np.ndarray, format: str = ".jpg") -> str:
        """
        Encode frame to base64 string.
        
        Args:
            frame: OpenCV frame (BGR format)
            format: Image format (.jpg, .png)
        
        Returns:
            Base64 encoded string
        """
        _, buffer = cv2.imencode(format, frame)
        return base64.b64encode(buffer).decode("utf-8")
    
    def extract_frame(self, frame_number: int) -> Optional[FrameData]:
        """
        Extract a specific frame from the video.
        
        Args:
            frame_number: The frame index to extract
        
        Returns:
            FrameData object or None if extraction fails
        """
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = self.cap.read()
        
        if not ret:
            return None
        
        timestamp_ms = (frame_number / self.fps) * 1000 if self.fps > 0 else 0
        base64_encoded = self.encode_frame_base64(frame)
        
        return FrameData(
            frame_number=frame_number,
            timestamp_ms=timestamp_ms,
            image_data=frame,
            base64_encoded=base64_encoded,
            width=self.width,
            height=self.height
        )
    
    def sample_frames(self) -> Generator[List[FrameData], None, None]:
        """
        Generator that yields batches of 3 frames per second interval.
        
        Yields:
            List of 3 FrameData objects representing 1 second of video
        """
        frame_number = 0
        batch = []
        
        while frame_number < self.total_frames:
            # Check if this frame should be sampled
            if frame_number % self.sample_interval == 0:
                frame_data = self.extract_frame(frame_number)
                if frame_data:
                    batch.append(frame_data)
                
                # Yield batch when we have 3 frames (1 second)
                if len(batch) >= Config.FRAMES_PER_SECOND:
                    yield batch
                    batch = []
            
            frame_number += 1
        
        # Yield remaining frames if any
        if batch:
            yield batch
    
    def get_frame_batch_for_second(self, second: int) -> List[FrameData]:
        """
        Get the 3 frames for a specific second of video.
        
        Args:
            second: The second of video (0-indexed)
        
        Returns:
            List of FrameData objects
        """
        start_frame = int(second * self.fps)
        frames = []
        
        for i in range(Config.FRAMES_PER_SECOND):
            frame_number = start_frame + (i * self.sample_interval)
            if frame_number < self.total_frames:
                frame_data = self.extract_frame(frame_number)
                if frame_data:
                    frames.append(frame_data)
        
        return frames
    
    def get_video_info(self) -> dict:
        """Get video metadata."""
        return {
            "path": str(self.video_path),
            "fps": self.fps,
            "total_frames": self.total_frames,
            "duration_seconds": self.duration_seconds,
            "width": self.width,
            "height": self.height,
            "sample_interval": self.sample_interval,
            "frames_per_second_sampled": Config.FRAMES_PER_SECOND
        }
    
    def close(self):
        """Release video capture resources."""
        if self.cap:
            self.cap.release()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
