"""
VLM Sampler Module.
Smart frame sampling for efficient VLM analysis.
Selects optimal frames based on time interval and activity level.
"""

import logging
import time
import base64
import cv2
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class SampledFrame:
    """Container for a frame selected for VLM analysis."""
    frame_number: int
    timestamp_ms: float
    frame: Any  # numpy array
    base64_encoded: str
    detections: List[Dict[str, Any]]
    vehicle_count: int


@dataclass
class VLMContext:
    """Context data for VLM analysis including multiple frames."""
    current_timestamp_ms: float
    frames: List[SampledFrame]  # 3 frames: -2s, -1s, now
    yolo_context: Dict[str, Any]  # YOLO detection data formatted for VLM


class VLMSampler:
    """
    Smart VLM sampling based on activity and interval.

    Instead of processing 15-second batches, samples individual frames
    every N seconds for continuous, low-latency analysis.

    Features:
    - Time-based sampling: Analyze every N seconds (configurable)
    - Activity filtering: Skip frames with too few vehicles
    - Change detection: Trigger on significant activity changes
    - Context window: Provides 3-frame context (-2s, -1s, now)
    """

    def __init__(
        self,
        sample_interval: float = 2.0,
        min_vehicles: int = 2,
        activity_threshold: float = 0.3,
        context_window: float = 6.0
    ):
        """
        Initialize VLM sampler.

        Args:
            sample_interval: Seconds between VLM samples (default: 2.0)
            min_vehicles: Minimum vehicles required to trigger VLM
            activity_threshold: Change ratio to trigger immediate analysis
            context_window: Seconds of history to maintain for context
        """
        self.sample_interval = sample_interval
        self.min_vehicles = min_vehicles
        self.activity_threshold = activity_threshold
        self.context_window = context_window

        # State
        self.last_sample_time: float = 0.0
        self.last_sample_frame: int = 0

        # Detection buffer for context (6 seconds at 30fps = 180 entries)
        self.detection_buffer: deque = deque(maxlen=int(context_window * 30))

        # Statistics
        self.stats = {
            "samples_triggered": 0,
            "samples_skipped_interval": 0,
            "samples_skipped_activity": 0,
            "forced_samples": 0
        }

        logger.info(
            f"VLMSampler initialized: interval={sample_interval}s, "
            f"min_vehicles={min_vehicles}, activity_threshold={activity_threshold}"
        )

    def add_detection(
        self,
        frame_number: int,
        timestamp_ms: float,
        frame: Any,
        detections: List[Dict[str, Any]]
    ):
        """
        Add a detection result to the buffer.

        Args:
            frame_number: Frame sequence number
            timestamp_ms: Timestamp in milliseconds
            frame: OpenCV frame (numpy array)
            detections: YOLO detection results
        """
        self.detection_buffer.append({
            'frame_number': frame_number,
            'timestamp_ms': timestamp_ms,
            'frame': frame,
            'detections': detections,
            'vehicle_count': len(detections)
        })

    def should_sample(
        self,
        timestamp_ms: float,
        detections: List[Dict[str, Any]],
        force: bool = False
    ) -> Tuple[bool, str]:
        """
        Decide if current frame should be sent to VLM.

        Args:
            timestamp_ms: Current timestamp in milliseconds
            detections: Current frame detections
            force: Force sample regardless of rules

        Returns:
            Tuple of (should_sample, reason)
        """
        timestamp_s = timestamp_ms / 1000.0

        if force:
            self.stats["forced_samples"] += 1
            return True, "forced"

        # Rule 1: Time interval check
        time_since_last = timestamp_s - self.last_sample_time
        if time_since_last < self.sample_interval:
            self.stats["samples_skipped_interval"] += 1
            return False, f"interval ({time_since_last:.1f}s < {self.sample_interval}s)"

        # Rule 2: Minimum activity check
        vehicle_count = len(detections)
        if vehicle_count < self.min_vehicles:
            self.stats["samples_skipped_activity"] += 1
            return False, f"low_activity ({vehicle_count} < {self.min_vehicles})"

        # Rule 3: Significant change detection (optional, always sample if interval passed)
        if self._detect_significant_change():
            self.stats["samples_triggered"] += 1
            return True, "significant_change"

        # Default: sample if interval passed and activity sufficient
        self.stats["samples_triggered"] += 1
        return True, "interval_passed"

    def _detect_significant_change(self) -> bool:
        """
        Detect if vehicle count or positions changed significantly.

        Returns:
            True if significant change detected
        """
        if len(self.detection_buffer) < 30:  # Need at least 1 second of history
            return False

        # Compare current vehicle count with 1 second ago
        current = self.detection_buffer[-1]
        past = self.detection_buffer[-30]  # ~1 second ago at 30fps

        current_count = current['vehicle_count']
        past_count = past['vehicle_count']

        if past_count == 0:
            return current_count >= self.min_vehicles

        change_ratio = abs(current_count - past_count) / max(past_count, 1)
        return change_ratio > self.activity_threshold

    def get_context_frames(
        self,
        current_timestamp_ms: float
    ) -> Optional[VLMContext]:
        """
        Get 3 frames for VLM context: -2s, -1s, and current.

        Args:
            current_timestamp_ms: Current timestamp in milliseconds

        Returns:
            VLMContext with 3 frames and YOLO data, or None if insufficient data
        """
        if len(self.detection_buffer) < 60:  # Need at least 2 seconds of history
            logger.warning("Insufficient buffer for context frames")
            return None

        # Find frames at approximate timestamps
        target_offsets = [-2000, -1000, 0]  # -2s, -1s, now (in ms)
        frames = []

        for offset in target_offsets:
            target_time = current_timestamp_ms + offset
            closest = self._find_closest_frame(target_time)

            if closest is None:
                logger.warning(f"Could not find frame for offset {offset}ms")
                return None

            # Encode frame to base64
            _, buffer = cv2.imencode('.jpg', closest['frame'], [cv2.IMWRITE_JPEG_QUALITY, 85])
            base64_encoded = base64.b64encode(buffer).decode('utf-8')

            sampled = SampledFrame(
                frame_number=closest['frame_number'],
                timestamp_ms=closest['timestamp_ms'],
                frame=closest['frame'],
                base64_encoded=base64_encoded,
                detections=closest['detections'],
                vehicle_count=closest['vehicle_count']
            )
            frames.append(sampled)

        # Build YOLO context for VLM prompt
        yolo_context = self._build_yolo_context(frames)

        # Update last sample time
        self.last_sample_time = current_timestamp_ms / 1000.0

        return VLMContext(
            current_timestamp_ms=current_timestamp_ms,
            frames=frames,
            yolo_context=yolo_context
        )

    def _find_closest_frame(self, target_timestamp_ms: float) -> Optional[Dict]:
        """
        Find the frame closest to target timestamp.

        Args:
            target_timestamp_ms: Target timestamp in milliseconds

        Returns:
            Detection buffer entry or None
        """
        if not self.detection_buffer:
            return None

        closest = min(
            self.detection_buffer,
            key=lambda x: abs(x['timestamp_ms'] - target_timestamp_ms)
        )

        return closest

    def _build_yolo_context(self, frames: List[SampledFrame]) -> Dict[str, Any]:
        """
        Build YOLO context dictionary for VLM prompt.

        Args:
            frames: List of SampledFrame objects

        Returns:
            Dictionary formatted for get_analysis_prompt()
        """
        detections_list = []

        for frame in frames:
            frame_dets = []
            for det in frame.detections:
                frame_dets.append({
                    'track_id': det.get('track_id', 'N/A'),
                    'class_name': det.get('class_name', 'unknown'),
                    'bbox': det.get('bbox', []),
                    'confidence': det.get('confidence', 0.0)
                })
            detections_list.append(frame_dets)

        return {
            "detections": detections_list,
            "timestamps": [f.timestamp_ms for f in frames],
            "vehicle_counts": [f.vehicle_count for f in frames]
        }

    def get_base64_frames(self, context: VLMContext) -> List[str]:
        """
        Extract base64-encoded frames from context.

        Args:
            context: VLMContext object

        Returns:
            List of base64 strings
        """
        return [f.base64_encoded for f in context.frames]

    def reset(self):
        """Reset sampler state for new stream."""
        self.last_sample_time = 0.0
        self.last_sample_frame = 0
        self.detection_buffer.clear()
        logger.info("VLMSampler reset")

    def get_stats(self) -> Dict[str, Any]:
        """Get sampling statistics."""
        return {
            **self.stats,
            "buffer_size": len(self.detection_buffer),
            "last_sample_time": self.last_sample_time
        }


def test_vlm_sampler():
    """Test VLM sampler with synthetic data."""
    import numpy as np

    sampler = VLMSampler(sample_interval=2.0, min_vehicles=2)

    print("Testing VLMSampler")
    print(f"Sample interval: {sampler.sample_interval}s")
    print(f"Min vehicles: {sampler.min_vehicles}")

    # Create test frame
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.rectangle(test_frame, (100, 100), (200, 200), (128, 128, 128), -1)

    # Simulate 5 seconds of detections at 30fps
    print("\nSimulating 5 seconds of detections...")
    for i in range(150):  # 5 seconds at 30fps
        timestamp_ms = i * 33.3
        detections = [
            {"track_id": 1, "class_name": "car", "bbox": [100, 100, 200, 200], "confidence": 0.9},
            {"track_id": 2, "class_name": "truck", "bbox": [300, 200, 450, 350], "confidence": 0.85}
        ]

        sampler.add_detection(i, timestamp_ms, test_frame, detections)

        should_sample, reason = sampler.should_sample(timestamp_ms, detections)

        if should_sample:
            print(f"  Frame {i} ({timestamp_ms:.0f}ms): SAMPLE - {reason}")

            context = sampler.get_context_frames(timestamp_ms)
            if context:
                print(f"    Context: {len(context.frames)} frames")
                print(f"    YOLO context: {len(context.yolo_context['detections'])} detection sets")

    print(f"\nStats: {sampler.get_stats()}")
    print("\nTest complete!")


if __name__ == "__main__":
    test_vlm_sampler()
