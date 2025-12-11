"""
Video Processor Module.
Generates YOLO-annotated video with bounding boxes for visualization.
"""

import cv2
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import numpy as np

from config import Config

logger = logging.getLogger(__name__)


class VideoProcessor:
    """
    Process videos with YOLO detection overlays.
    Generates annotated video for visualization in UI.
    """
    
    # Colors for different vehicle classes (BGR format)
    COLORS = {
        2: (0, 255, 0),     # car - green
        3: (255, 165, 0),   # motorcycle - orange
        5: (255, 0, 0),     # bus - blue
        7: (0, 0, 255),     # truck - red
    }
    DEFAULT_COLOR = (128, 128, 128)  # gray for unknown
    
    def __init__(self, video_path: str, output_dir: str = "processed"):
        """
        Initialize video processor.
        
        Args:
            video_path: Path to input video
            output_dir: Directory to save processed videos
        """
        self.video_path = Path(video_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.cap: Optional[cv2.VideoCapture] = None
        self.yolo_model = None
        
    def _load_yolo(self):
        """Load YOLO model if not already loaded."""
        if self.yolo_model is None:
            try:
                from ultralytics import YOLO
                self.yolo_model = YOLO(Config.YOLO_MODEL_PATH)
                logger.info(f"Loaded YOLO model: {Config.YOLO_MODEL_PATH}")
            except ImportError:
                raise ImportError("ultralytics not installed")
    
    def _draw_detections(
        self,
        frame: np.ndarray,
        detections: List[dict]
    ) -> np.ndarray:
        """
        Draw bounding boxes and labels on frame.
        
        Args:
            frame: OpenCV frame (BGR)
            detections: List of detection dicts with bbox, class_id, confidence
            
        Returns:
            Annotated frame
        """
        annotated = frame.copy()
        
        for det in detections:
            # Get bounding box
            bbox = det.get("bbox", [])
            if len(bbox) != 4:
                continue
                
            x1, y1, x2, y2 = map(int, bbox)
            
            # Get color based on class
            class_id = det.get("class_id", -1)
            color = self.COLORS.get(class_id, self.DEFAULT_COLOR)
            
            # Draw bounding box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            
            # Prepare label
            class_name = det.get("class_name", "unknown")
            confidence = det.get("confidence", 0)
            label = f"{class_name}: {confidence:.0%}"
            
            # Draw label background
            (label_w, label_h), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )
            cv2.rectangle(
                annotated,
                (x1, y1 - label_h - 10),
                (x1 + label_w + 6, y1),
                color,
                -1
            )
            
            # Draw label text
            cv2.putText(
                annotated,
                label,
                (x1 + 3, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )
            
            # Draw track ID if available
            track_id = det.get("track_id")
            if track_id is not None:
                id_label = f"ID: {track_id}"
                cv2.putText(
                    annotated,
                    id_label,
                    (x1 + 3, y2 + 15),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    color,
                    1
                )
        
        return annotated
    
    def process_video(
        self,
        output_name: Optional[str] = None,
        progress_callback=None
    ) -> str:
        """
        Process entire video with YOLO detection overlays.
        
        Args:
            output_name: Name for output video (without extension)
            progress_callback: Callback(progress: float) for progress updates
            
        Returns:
            Path to processed video
        """
        self._load_yolo()
        
        # Open video
        self.cap = cv2.VideoCapture(str(self.video_path))
        if not self.cap.isOpened():
            raise ValueError(f"Could not open video: {self.video_path}")
        
        # Get video properties
        fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Output path (use MP4 for browser compatibility)
        if output_name is None:
            output_name = self.video_path.stem + "_annotated"
        output_path = self.output_dir / f"{output_name}.mp4"
        
        # Initialize video writer with H.264 codec for browser compatibility
        # Try different codecs in order of preference
        codecs_to_try = [
            ('avc1', '.mp4'),  # H.264 for Safari/Chrome/Firefox
            ('H264', '.mp4'),  # Another H.264 variant
            ('X264', '.mp4'),  # libx264
            ('mp4v', '.mp4'),  # Fallback MPEG-4
        ]
        
        writer = None
        for codec, ext in codecs_to_try:
            try:
                fourcc = cv2.VideoWriter_fourcc(*codec)
                output_path = self.output_dir / f"{output_name}{ext}"
                test_writer = cv2.VideoWriter(
                    str(output_path),
                    fourcc,
                    fps,
                    (width, height)
                )
                if test_writer.isOpened():
                    writer = test_writer
                    logger.info(f"Using codec: {codec}")
                    break
                test_writer.release()
            except Exception:
                continue
        
        if writer is None:
            # Final fallback
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            output_path = self.output_dir / f"{output_name}.mp4"
            writer = cv2.VideoWriter(
                str(output_path),
                fourcc,
                fps,
                (width, height)
            )
            logger.warning("Using fallback codec: mp4v")
        
        logger.info(f"Processing video: {self.video_path} ({total_frames} frames)")
        
        frame_count = 0
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    break
                
                # Run YOLO detection
                results = self.yolo_model(
                    frame,
                    classes=Config.VEHICLE_CLASSES,
                    conf=Config.YOLO_CONFIDENCE,
                    iou=Config.YOLO_IOU,
                    verbose=False
                )
                
                # Extract detections
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
                
                # Draw detections on frame
                annotated_frame = self._draw_detections(frame, detections)
                
                # Write frame
                writer.write(annotated_frame)
                
                frame_count += 1
                
                # Progress callback
                if progress_callback and frame_count % 30 == 0:
                    progress = frame_count / total_frames
                    progress_callback(progress)
                    
        finally:
            self.cap.release()
            writer.release()
        
        # Re-encode with FFmpeg for browser compatibility (H.264 + AAC)
        final_output = self._reencode_for_browser(output_path)
        
        logger.info(f"Processed video saved: {final_output}")
        return str(final_output)
    
    def _reencode_for_browser(self, input_path: Path) -> Path:
        """
        Re-encode video with FFmpeg for browser compatibility.
        
        Args:
            input_path: Path to input video
            
        Returns:
            Path to re-encoded video
        """
        import subprocess
        import shutil
        
        # Check if ffmpeg is available
        if shutil.which('ffmpeg') is None:
            logger.warning("FFmpeg not found, skipping re-encoding")
            return input_path
        
        output_path = input_path.with_suffix('.web.mp4')
        
        try:
            cmd = [
                'ffmpeg', '-y',
                '-i', str(input_path),
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '23',
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',  # Enable streaming
                '-an',  # No audio (source has none)
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0 and output_path.exists():
                # Remove original and rename
                input_path.unlink()
                final_path = input_path
                output_path.rename(final_path)
                logger.info("Re-encoded video for browser compatibility")
                return final_path
            else:
                logger.warning(f"FFmpeg failed: {result.stderr[:200]}")
                return input_path
                
        except subprocess.TimeoutExpired:
            logger.warning("FFmpeg timed out")
            return input_path
        except Exception as e:
            logger.warning(f"FFmpeg error: {e}")
            return input_path
    
    def get_annotated_frame(
        self,
        frame_number: int,
        detections: Optional[List[dict]] = None
    ) -> Tuple[np.ndarray, List[dict]]:
        """
        Get a single annotated frame.
        
        Args:
            frame_number: Frame number to extract
            detections: Optional pre-computed detections
            
        Returns:
            Tuple of (annotated_frame, detections)
        """
        self._load_yolo()
        
        if self.cap is None:
            self.cap = cv2.VideoCapture(str(self.video_path))
        
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = self.cap.read()
        
        if not ret:
            raise ValueError(f"Could not read frame {frame_number}")
        
        # Run YOLO if detections not provided
        if detections is None:
            results = self.yolo_model(
                frame,
                classes=Config.VEHICLE_CLASSES,
                conf=Config.YOLO_CONFIDENCE,
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
                        }
                        detections.append(det)
        
        annotated = self._draw_detections(frame, detections)
        return annotated, detections
    
    def frame_to_base64(self, frame: np.ndarray, quality: int = 80) -> str:
        """
        Convert frame to base64 JPEG string.
        
        Args:
            frame: OpenCV frame (BGR)
            quality: JPEG quality (0-100)
            
        Returns:
            Base64 encoded string
        """
        import base64
        
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        _, buffer = cv2.imencode('.jpg', frame, encode_params)
        return base64.b64encode(buffer).decode('utf-8')
    
    def close(self):
        """Release video capture."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None


def process_video_file(video_path: str, output_name: str = None) -> str:
    """
    Convenience function to process a video file.
    
    Args:
        video_path: Path to input video
        output_name: Name for output file
        
    Returns:
        Path to processed video
    """
    processor = VideoProcessor(video_path)
    try:
        return processor.process_video(output_name)
    finally:
        processor.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python video_processor.py <video_path>")
        sys.exit(1)
    
    video_path = sys.argv[1]
    output_path = process_video_file(video_path)
    print(f"Processed video: {output_path}")
