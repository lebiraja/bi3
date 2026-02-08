"""
Continuous YOLO Processor Module.
Dedicated GPU thread for real-time YOLO detection with vehicle tracking.
Designed for low-latency streaming pipeline.
"""

import cv2
import queue
import threading
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    """Container for a single frame's detection results."""
    frame_number: int
    timestamp_ms: float
    detections: List[Dict[str, Any]]
    vehicle_count: int
    processing_time_ms: float


@dataclass
class AnnotatedFrame:
    """Container for an annotated frame ready for WebSocket broadcast."""
    frame_number: int
    timestamp_ms: float
    frame: Any  # numpy array
    detections: List[Dict[str, Any]]
    vehicle_count: int


class ContinuousYOLOProcessor:
    """
    Continuous YOLO processing with GPU optimization.

    Runs in a dedicated thread, processes every frame from stream buffer.
    Emits detection events and pre-annotated frames via output queues.

    Features:
    - GPU-accelerated inference (~30ms/frame on RTX 4050)
    - ByteTrack vehicle tracking for persistent IDs
    - Pre-computed frame annotations (removes blocking callback)
    - Frame decimation for WebSocket (30fps -> 15fps)
    """

    # Colors for different vehicle classes (BGR format)
    CLASS_COLORS = {
        2: (0, 255, 0),      # car - green
        3: (255, 0, 0),      # motorcycle - blue
        5: (0, 165, 255),    # bus - orange
        7: (0, 255, 255)     # truck - yellow
    }

    def __init__(
        self,
        model_path: str = None,
        detection_queue_size: int = 300,
        annotated_queue_size: int = 150,
        use_tracking: bool = True
    ):
        """
        Initialize continuous YOLO processor.

        Args:
            model_path: Path to YOLO model weights
            detection_queue_size: Max size for detection output queue (~10s at 30fps)
            annotated_queue_size: Max size for annotated frame queue (~5s at 30fps)
            use_tracking: Enable ByteTrack vehicle tracking
        """
        self.model_path = model_path or Config.YOLO_MODEL_PATH
        self.use_tracking = use_tracking
        self.model = None

        # Output queues
        self.detection_queue = queue.Queue(maxsize=detection_queue_size)
        self.annotated_frame_queue = queue.Queue(maxsize=annotated_queue_size)

        # Processing state
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.frame_count = 0
        self.total_processing_time = 0.0

        # Statistics
        self.stats = {
            "frames_processed": 0,
            "avg_processing_time_ms": 0.0,
            "detections_total": 0,
            "queue_drops": 0
        }

        logger.info(f"ContinuousYOLOProcessor initialized: model={self.model_path}, tracking={use_tracking}")

    def load_model(self):
        """Load YOLO model with GPU optimization."""
        try:
            from ultralytics import YOLO
            import torch

            self.model = YOLO(self.model_path)

            # Move to GPU if available
            if torch.cuda.is_available():
                self.model.to('cuda')
                logger.info(f"YOLO model loaded on CUDA GPU")
            else:
                logger.warning("CUDA not available, using CPU for YOLO")

            # Warm up the model
            logger.info("Warming up YOLO model...")
            import numpy as np
            dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)
            for _ in range(3):
                self._run_inference(dummy_frame)
            logger.info("YOLO model warm-up complete")

        except ImportError:
            logger.error("ultralytics not installed. Run: pip install ultralytics")
            raise

    def _run_inference(self, frame, use_tracking: bool = None) -> List[Dict[str, Any]]:
        """
        Run YOLO inference on a single frame.

        Args:
            frame: OpenCV frame (numpy array)
            use_tracking: Override instance tracking setting

        Returns:
            List of detection dictionaries
        """
        if self.model is None:
            self.load_model()

        track = use_tracking if use_tracking is not None else self.use_tracking

        if track:
            # Use tracking mode for persistent vehicle IDs
            results = self.model.track(
                frame,
                persist=True,
                classes=Config.VEHICLE_CLASSES,
                conf=Config.YOLO_CONFIDENCE,
                iou=Config.YOLO_IOU,
                verbose=False,
                tracker="bytetrack.yaml"
            )
        else:
            # Simple detection mode
            results = self.model(
                frame,
                classes=Config.VEHICLE_CLASSES,
                conf=Config.YOLO_CONFIDENCE,
                iou=Config.YOLO_IOU,
                verbose=False
            )

        detections = []
        for result in results:
            if result.boxes is not None:
                for box in result.boxes:
                    cls_id = int(box.cls.cpu().numpy()[0])
                    det = {
                        "class_id": cls_id,
                        "class_name": Config.CLASS_NAMES.get(cls_id, "unknown"),
                        "confidence": float(box.conf.cpu().numpy()[0]),
                        "bbox": box.xyxy.cpu().numpy()[0].tolist(),
                        "track_id": int(box.id.cpu().numpy()[0]) if box.id is not None else None
                    }
                    detections.append(det)

        return detections

    def _draw_detections(self, frame, detections: List[Dict[str, Any]]):
        """
        Draw YOLO detections on frame with bounding boxes and labels.

        Args:
            frame: OpenCV frame (numpy array)
            detections: List of detection dictionaries

        Returns:
            Annotated frame (numpy array)
        """
        annotated = frame.copy()

        for det in detections:
            bbox = det['bbox']
            class_name = det['class_name']
            confidence = det['confidence']
            class_id = det['class_id']
            track_id = det.get('track_id')

            # Get color for this class
            color = self.CLASS_COLORS.get(class_id, (255, 255, 255))

            # Draw bounding box
            x1, y1, x2, y2 = map(int, bbox)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            # Build label
            if track_id is not None:
                label = f"{class_name} #{track_id} {confidence:.2f}"
            else:
                label = f"{class_name} {confidence:.2f}"

            # Draw label background
            (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(annotated, (x1, y1 - label_h - 10), (x1 + label_w, y1), color, -1)

            # Draw label text
            cv2.putText(annotated, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX,
                       0.5, (0, 0, 0), 1, cv2.LINE_AA)

        return annotated

    def process_frame(
        self,
        frame,
        frame_number: int,
        timestamp_ms: float
    ) -> DetectionResult:
        """
        Process a single frame synchronously.

        Args:
            frame: OpenCV frame (numpy array)
            frame_number: Frame sequence number
            timestamp_ms: Timestamp in milliseconds

        Returns:
            DetectionResult with detections
        """
        start_time = time.time()

        detections = self._run_inference(frame)

        processing_time = (time.time() - start_time) * 1000

        return DetectionResult(
            frame_number=frame_number,
            timestamp_ms=timestamp_ms,
            detections=detections,
            vehicle_count=len(detections),
            processing_time_ms=processing_time
        )

    def start(self, frame_source: queue.Queue, decimate_factor: int = 2):
        """
        Start continuous processing from frame source.

        Args:
            frame_source: Queue providing (frame_number, frame, timestamp_ms) tuples
            decimate_factor: Only emit annotated frames every N frames (2 = 15fps from 30fps)
        """
        if self.is_running:
            logger.warning("Processor already running")
            return

        # Load model before starting thread
        if self.model is None:
            self.load_model()

        self.is_running = True
        self.thread = threading.Thread(
            target=self._process_loop,
            args=(frame_source, decimate_factor),
            daemon=True
        )
        self.thread.start()
        logger.info("ContinuousYOLOProcessor started")

    def _process_loop(self, frame_source: queue.Queue, decimate_factor: int):
        """
        Main processing loop - runs continuously in dedicated thread.

        Args:
            frame_source: Queue providing frame tuples
            decimate_factor: Frame decimation for annotated output
        """
        logger.info("YOLO processing loop started")

        while self.is_running:
            try:
                # Get next frame from source (with timeout)
                try:
                    frame_data = frame_source.get(timeout=1.0)
                except queue.Empty:
                    continue

                # Unpack frame data
                if isinstance(frame_data, tuple) and len(frame_data) == 3:
                    frame_number, frame, timestamp_ms = frame_data
                else:
                    logger.warning(f"Invalid frame data format: {type(frame_data)}")
                    continue

                # Process frame
                start_time = time.time()
                detections = self._run_inference(frame)
                processing_time = (time.time() - start_time) * 1000

                # Update stats
                self.frame_count += 1
                self.total_processing_time += processing_time
                self.stats["frames_processed"] = self.frame_count
                self.stats["avg_processing_time_ms"] = self.total_processing_time / self.frame_count
                self.stats["detections_total"] += len(detections)

                # Emit detection result
                detection_result = {
                    'frame_number': frame_number,
                    'timestamp_ms': timestamp_ms,
                    'detections': detections,
                    'vehicle_count': len(detections),
                    'processing_time_ms': processing_time
                }

                try:
                    self.detection_queue.put_nowait(detection_result)
                except queue.Full:
                    # Drop oldest and add new
                    try:
                        self.detection_queue.get_nowait()
                        self.detection_queue.put_nowait(detection_result)
                        self.stats["queue_drops"] += 1
                    except queue.Empty:
                        pass

                # Emit annotated frame (decimated for WebSocket)
                if frame_number % decimate_factor == 0:
                    annotated_frame = self._draw_detections(frame, detections)

                    annotated_data = AnnotatedFrame(
                        frame_number=frame_number,
                        timestamp_ms=timestamp_ms,
                        frame=annotated_frame,
                        detections=detections,
                        vehicle_count=len(detections)
                    )

                    try:
                        self.annotated_frame_queue.put_nowait(annotated_data)
                    except queue.Full:
                        # Drop oldest and add new
                        try:
                            self.annotated_frame_queue.get_nowait()
                            self.annotated_frame_queue.put_nowait(annotated_data)
                        except queue.Empty:
                            pass

            except Exception as e:
                logger.error(f"YOLO processing error: {e}")

        logger.info("YOLO processing loop stopped")

    def stop(self):
        """Stop the processing thread."""
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5.0)
        logger.info(f"ContinuousYOLOProcessor stopped. Stats: {self.stats}")

    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return self.stats.copy()

    def reset_tracking(self):
        """Reset vehicle tracking state (for new stream)."""
        if self.model is not None:
            # Reload model to reset tracking state
            self.load_model()
            logger.info("Vehicle tracking state reset")


def test_continuous_yolo():
    """Test continuous YOLO processor with synthetic frames."""
    import numpy as np

    processor = ContinuousYOLOProcessor()

    print("Testing ContinuousYOLOProcessor")
    print(f"Model: {processor.model_path}")
    print(f"Tracking: {processor.use_tracking}")

    # Create test frame
    test_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    # Add some rectangles to simulate vehicles
    cv2.rectangle(test_frame, (100, 200), (300, 400), (128, 128, 128), -1)
    cv2.rectangle(test_frame, (500, 300), (700, 500), (100, 100, 100), -1)

    # Process single frame
    print("\nProcessing single frame...")
    result = processor.process_frame(test_frame, 0, 0.0)
    print(f"Detections: {result.vehicle_count}")
    print(f"Processing time: {result.processing_time_ms:.1f}ms")

    # Benchmark 100 frames
    print("\nBenchmarking 100 frames...")
    times = []
    for i in range(100):
        result = processor.process_frame(test_frame, i, i * 33.3)
        times.append(result.processing_time_ms)

    avg_time = sum(times) / len(times)
    print(f"Average: {avg_time:.1f}ms/frame")
    print(f"FPS: {1000 / avg_time:.1f}")
    print(f"Min: {min(times):.1f}ms, Max: {max(times):.1f}ms")

    # Test threaded mode
    print("\nTesting threaded mode...")
    frame_queue = queue.Queue(maxsize=100)

    # Add frames to queue
    for i in range(30):
        frame_queue.put((i, test_frame, i * 33.3))

    processor.start(frame_queue, decimate_factor=2)

    # Wait for processing
    time.sleep(3)

    # Check results
    detection_count = processor.detection_queue.qsize()
    annotated_count = processor.annotated_frame_queue.qsize()

    print(f"Detection queue size: {detection_count}")
    print(f"Annotated queue size: {annotated_count}")
    print(f"Stats: {processor.get_stats()}")

    processor.stop()
    print("\nTest complete!")


if __name__ == "__main__":
    test_continuous_yolo()
