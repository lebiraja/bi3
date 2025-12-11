"""
Video Analyzer - Main Pipeline Orchestration.
Coordinates frame sampling, YOLO detection, VLM analysis, and storage.
"""

import asyncio
import argparse
import logging
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

from config import Config
from frame_sampler import FrameSampler, FrameData
from mongodb_handler import MongoDBHandler
from vlm_client import VLMClient
from behavior_analyzer import BehaviorAnalyzer, VideoAnalysisSummary

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class YOLODetector:
    """
    YOLO detection wrapper for integration with the pipeline.
    Uses the existing ultralytics YOLO setup.
    """
    
    def __init__(self, model_path: str = None):
        """Initialize YOLO detector."""
        self.model_path = model_path or Config.YOLO_MODEL_PATH
        self.model = None
        
    def load_model(self):
        """Load YOLO model."""
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
            logger.info(f"Loaded YOLO model: {self.model_path}")
        except ImportError:
            logger.error("ultralytics not installed. Run: pip install ultralytics")
            raise
    
    def detect_in_frame(self, frame) -> List[dict]:
        """
        Run detection on a single frame.
        
        Args:
            frame: OpenCV frame (numpy array)
        
        Returns:
            List of detection dictionaries
        """
        if self.model is None:
            self.load_model()
        
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


class VideoAnalyzer:
    """
    Main video analysis pipeline.
    
    Pipeline flow:
    1. Load video and extract metadata
    2. Sample frames (3 per second)
    3. Run YOLO detection on sampled frames
    4. Process frames in parallel with VLM
    5. Store results in MongoDB
    6. Generate summary report
    """
    
    def __init__(
        self,
        video_path: str,
        use_mongodb: bool = True,
        verbose: bool = False
    ):
        """
        Initialize video analyzer.
        
        Args:
            video_path: Path to video file
            use_mongodb: Whether to store results in MongoDB
            verbose: Enable verbose logging
        """
        self.video_path = Path(video_path)
        self.use_mongodb = use_mongodb
        self.verbose = verbose
        
        if verbose:
            logging.getLogger().setLevel(logging.DEBUG)
        
        # Generate unique video ID
        self.video_id = self._generate_video_id()
        
        # Initialize components
        self.frame_sampler: Optional[FrameSampler] = None
        self.yolo_detector: Optional[YOLODetector] = None
        self.vlm_client: Optional[VLMClient] = None
        self.behavior_analyzer: Optional[BehaviorAnalyzer] = None
        self.mongodb: Optional[MongoDBHandler] = None
    
    def _generate_video_id(self) -> str:
        """Generate unique ID for the video based on path and timestamp."""
        content = f"{self.video_path.name}_{datetime.utcnow().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def _init_components(self):
        """Initialize all pipeline components."""
        logger.info("Initializing pipeline components...")
        
        # Validate config
        Config.validate()
        
        # Frame sampler
        self.frame_sampler = FrameSampler(str(self.video_path))
        logger.info(f"Video loaded: {self.frame_sampler.get_video_info()}")
        
        # YOLO detector
        self.yolo_detector = YOLODetector()
        self.yolo_detector.load_model()
        
        # VLM client and analyzer
        self.vlm_client = VLMClient()
        self.behavior_analyzer = BehaviorAnalyzer(self.vlm_client)
        
        # MongoDB (optional)
        if self.use_mongodb:
            try:
                self.mongodb = MongoDBHandler()
                self.mongodb.connect()
                logger.info("MongoDB connected")
            except Exception as e:
                logger.warning(f"MongoDB connection failed: {e}. Continuing without storage.")
                self.use_mongodb = False
    
    def _process_yolo_detections(
        self,
        frame_batches: List[List[FrameData]]
    ) -> Dict[int, List[dict]]:
        """
        Run YOLO detection on all sampled frames.
        
        Args:
            frame_batches: List of frame batches
        
        Returns:
            Dictionary mapping frame_number to detections
        """
        logger.info("Running YOLO detection...")
        detections = {}
        
        for batch in frame_batches:
            for frame_data in batch:
                dets = self.yolo_detector.detect_in_frame(frame_data.image_data)
                detections[frame_data.frame_number] = dets
                
                if self.verbose:
                    logger.debug(
                        f"Frame {frame_data.frame_number}: "
                        f"{len(dets)} vehicles detected"
                    )
                
                # Store in MongoDB
                if self.mongodb and self.use_mongodb:
                    self.mongodb.store_detection(
                        self.video_id,
                        frame_data.frame_number,
                        dets
                    )
        
        total_detections = sum(len(d) for d in detections.values())
        logger.info(f"YOLO detection complete: {total_detections} total detections")
        
        return detections
    
    async def _analyze_with_vlm(
        self,
        frame_batches: List[List[FrameData]],
        yolo_detections: Dict[int, List[dict]]
    ) -> VideoAnalysisSummary:
        """
        Run VLM analysis on all frame batches.
        
        Args:
            frame_batches: List of frame batches (3 frames each)
            yolo_detections: YOLO detection results
        
        Returns:
            VideoAnalysisSummary with all results
        """
        logger.info(f"Starting VLM analysis of {len(frame_batches)} seconds...")
        
        # Analyze all seconds in parallel (with rate limiting)
        analyses = await self.behavior_analyzer.analyze_video_parallel(
            frame_batches,
            yolo_detections,
            max_concurrent=3  # Limit concurrent API calls
        )
        
        # Store analyses in MongoDB
        if self.mongodb and self.use_mongodb:
            for analysis in analyses:
                if analysis.success:
                    self.mongodb.store_analysis(
                        self.video_id,
                        analysis.second_index,
                        analysis.to_dict(),
                        analysis.frame_numbers
                    )
        
        # Create summary
        video_info = self.frame_sampler.get_video_info()
        summary = self.behavior_analyzer.create_video_summary(
            self.video_id,
            analyses,
            int(video_info["duration_seconds"])
        )
        
        logger.info(
            f"VLM analysis complete. "
            f"Avg risk: {summary.avg_risk_score:.1f}, "
            f"Max risk: {summary.max_risk_score}, "
            f"Critical observations: {len(summary.critical_observations)}"
        )
        
        return summary
    
    async def analyze(self) -> VideoAnalysisSummary:
        """
        Run complete video analysis pipeline.
        
        Returns:
            VideoAnalysisSummary with full analysis results
        """
        try:
            # Initialize components
            self._init_components()
            
            # Extract frames
            logger.info("Sampling frames from video...")
            frame_batches = list(self.frame_sampler.sample_frames())
            logger.info(f"Extracted {len(frame_batches)} second-intervals")
            
            # Store frames in MongoDB
            if self.mongodb and self.use_mongodb:
                for batch in frame_batches:
                    frames_dict = [f.to_dict() for f in batch]
                    self.mongodb.store_frames_batch(self.video_id, frames_dict)
            
            # Run YOLO detection
            yolo_detections = self._process_yolo_detections(frame_batches)
            
            # Run VLM analysis
            summary = await self._analyze_with_vlm(frame_batches, yolo_detections)
            
            return summary
            
        finally:
            # Cleanup
            if self.frame_sampler:
                self.frame_sampler.close()
            if self.mongodb:
                self.mongodb.close()
    
    def run(self) -> VideoAnalysisSummary:
        """Synchronous wrapper for analyze()."""
        return asyncio.run(self.analyze())


def print_summary(summary: VideoAnalysisSummary):
    """Print formatted analysis summary."""
    print("\n" + "=" * 60)
    print("VIDEO ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"Video ID: {summary.video_id}")
    print(f"Duration: {summary.total_seconds} seconds")
    print(f"Analyzed: {summary.analyzed_seconds} seconds")
    print(f"Average Risk Score: {summary.avg_risk_score:.1f}/10")
    print(f"Maximum Risk Score: {summary.max_risk_score}/10")
    print(f"Critical Observations: {len(summary.critical_observations)}")
    
    if summary.critical_observations:
        print("\n" + "-" * 40)
        print("CRITICAL OBSERVATIONS:")
        for i, obs in enumerate(summary.critical_observations, 1):
            print(f"\n{i}. [{obs.risk_level.upper()}] {obs.behavior_type}")
            print(f"   {obs.description}")
    
    print("\n" + "=" * 60)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Video Behavior Analysis Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--video", "-v",
        required=True,
        help="Path to input video file"
    )
    parser.add_argument(
        "--no-mongodb",
        action="store_true",
        help="Skip MongoDB storage"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output JSON file for results"
    )
    
    args = parser.parse_args()
    
    # Validate video exists
    video_path = Path(args.video)
    if not video_path.exists():
        print(f"Error: Video file not found: {video_path}")
        return 1
    
    # Run analysis
    analyzer = VideoAnalyzer(
        video_path=str(video_path),
        use_mongodb=not args.no_mongodb,
        verbose=args.verbose
    )
    
    try:
        summary = analyzer.run()
        
        # Print summary
        print_summary(summary)
        
        # Save to JSON if requested
        if args.output:
            output_path = Path(args.output)
            with open(output_path, "w") as f:
                json.dump(summary.to_dict(), f, indent=2)
            print(f"\nResults saved to: {output_path}")
        
        return 0
        
    except ValueError as e:
        print(f"Configuration Error: {e}")
        return 1
    except Exception as e:
        logger.exception("Analysis failed")
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
