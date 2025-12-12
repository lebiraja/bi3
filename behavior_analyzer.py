"""
Behavior Analyzer Module.
Orchestrates parallel VLM analysis and aggregates behavioral summaries.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from config import Config
from frame_sampler import FrameData
from vlm_client import VLMClient, VLMResponse

logger = logging.getLogger(__name__)


@dataclass
class BehaviorObservation:
    """Single behavioral observation."""
    behavior_type: str
    vehicle_id: str
    confidence: str
    evidence: str
    risk_level: str
    description: str
    
    @classmethod
    def from_dict(cls, data: dict) -> "BehaviorObservation":
        return cls(
            behavior_type=data.get("behavior_type", "unknown"),
            vehicle_id=data.get("vehicle_id", "unknown"),
            confidence=data.get("confidence", "low"),
            evidence=data.get("evidence", ""),
            risk_level=data.get("risk_level", "low"),
            description=data.get("description", "")
        )


@dataclass
class SecondAnalysis:
    """Analysis result for a 1-second interval."""
    second_index: int
    timestamp_start_ms: float
    timestamp_end_ms: float
    frame_numbers: List[int]
    observations: List[BehaviorObservation] = field(default_factory=list)
    risk_score: int = 0
    summary: str = ""
    recommended_alerts: List[str] = field(default_factory=list)
    raw_response: Optional[dict] = None
    success: bool = True
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "second_index": self.second_index,
            "timestamp_start_ms": self.timestamp_start_ms,
            "timestamp_end_ms": self.timestamp_end_ms,
            "frame_numbers": self.frame_numbers,
            "observations": [
                {
                    "behavior_type": obs.behavior_type,
                    "vehicle_id": obs.vehicle_id,
                    "confidence": obs.confidence,
                    "evidence": obs.evidence,
                    "risk_level": obs.risk_level,
                    "description": obs.description
                }
                for obs in self.observations
            ],
            "risk_score": self.risk_score,
            "summary": self.summary,
            "recommended_alerts": self.recommended_alerts,
            "success": self.success,
            "error": self.error
        }


@dataclass
class VideoAnalysisSummary:
    """Complete analysis summary for a video."""
    video_id: str
    total_seconds: int
    analyzed_seconds: int
    avg_risk_score: float
    max_risk_score: int
    critical_observations: List[BehaviorObservation]
    all_analyses: List[SecondAnalysis]
    analysis_timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        return {
            "video_id": self.video_id,
            "total_seconds": self.total_seconds,
            "analyzed_seconds": self.analyzed_seconds,
            "avg_risk_score": round(self.avg_risk_score, 2),
            "max_risk_score": self.max_risk_score,
            "critical_observations": [
                {
                    "behavior_type": obs.behavior_type,
                    "risk_level": obs.risk_level,
                    "description": obs.description
                }
                for obs in self.critical_observations
            ],
            "analysis_timestamp": self.analysis_timestamp.isoformat()
        }


class BehaviorAnalyzer:
    """
    Orchestrates behavioral analysis pipeline.
    
    Processes 3 frames per second in parallel using VLM,
    integrates YOLO detection data, and aggregates results.
    """
    
    def __init__(self, vlm_client: VLMClient = None, is_stream: bool = False):
        """
        Initialize behavior analyzer.
        
        Args:
            vlm_client: VLM client instance (creates new if not provided)
            is_stream: Whether this is for live stream analysis (uses lower concurrency limits)
        """
        if vlm_client:
            self.vlm_client = vlm_client
        elif is_stream:
            # For live streams, use per-key concurrency limits to reduce latency
            from config import Config
            self.vlm_client = VLMClient(max_concurrent_per_key=Config.STREAM_VLM_MAX_PER_KEY)
            logger.info(f"BehaviorAnalyzer initialized for LIVE STREAM with {Config.STREAM_VLM_MAX_PER_KEY} requests per API key")
        else:
            # For video uploads, use default (no per-key limits)
            self.vlm_client = VLMClient()
            logger.info("BehaviorAnalyzer initialized for VIDEO UPLOAD (no per-key limits)")
    
    def _prepare_yolo_data(
        self,
        detections: Dict[int, List[dict]],
        frame_numbers: List[int]
    ) -> dict:
        """
        Format YOLO detections for VLM context.
        
        Args:
            detections: Dictionary mapping frame_number to detection list
            frame_numbers: List of frame numbers in the batch
        
        Returns:
            Formatted YOLO data dictionary
        """
        formatted_detections = []
        
        for frame_num in frame_numbers:
            frame_dets = detections.get(frame_num, [])
            formatted_detections.append(frame_dets)
        
        return {"detections": formatted_detections}
    
    def _parse_vlm_response(
        self,
        parsed_json: dict,
        second_index: int,
        timestamp_start: float,
        timestamp_end: float,
        frame_numbers: List[int]
    ) -> SecondAnalysis:
        """
        Parse VLM response into SecondAnalysis.
        
        Args:
            parsed_json: Parsed JSON response from VLM
            second_index: Index of the second being analyzed
            timestamp_start: Start timestamp in ms
            timestamp_end: End timestamp in ms
            frame_numbers: List of frame numbers
        
        Returns:
            SecondAnalysis object
        """
        # Extract observations
        observations = [
            BehaviorObservation.from_dict(obs)
            for obs in parsed_json.get("observations", [])
        ]
        
        # Extract overall assessment
        assessment = parsed_json.get("overall_assessment", {})
        
        return SecondAnalysis(
            second_index=second_index,
            timestamp_start_ms=timestamp_start,
            timestamp_end_ms=timestamp_end,
            frame_numbers=frame_numbers,
            observations=observations,
            risk_score=assessment.get("risk_score", 0),
            summary=assessment.get("summary", ""),
            recommended_alerts=assessment.get("recommended_alerts", []),
            raw_response=parsed_json,  # Fixed: was 'parsed'
            success=True
        )
    
    async def analyze_second(
        self,
        frames: List[FrameData],
        yolo_detections: Dict[int, List[dict]],
        second_index: int
    ) -> SecondAnalysis:
        """
        Analyze a 1-second interval (3 frames) with VLM.
        
        Args:
            frames: List of FrameData objects (3 frames)
            yolo_detections: YOLO detection data per frame
            second_index: Index of the second being analyzed
        
        Returns:
            SecondAnalysis result
        """
        # Extract base64 images
        base64_frames = [f.base64_encoded for f in frames]
        
        # Prepare YOLO context
        frame_numbers = [f.frame_number for f in frames]
        yolo_data = self._prepare_yolo_data(yolo_detections, frame_numbers)
        
        # Extract timestamps
        timestamp_start = min(f.timestamp_ms for f in frames) if frames else 0
        timestamp_end = max(f.timestamp_ms for f in frames) if frames else 0
        
        # Call VLM
        response = await self.vlm_client.analyze_frames(base64_frames, yolo_data)
        
        # Check for VLM errors
        if not response.success:
            logger.error(f"❌ VLM analysis failed for second {second_index}: {response.error}")
            return SecondAnalysis(
                second_index=second_index,
                timestamp_start_ms=timestamp_start,
                timestamp_end_ms=timestamp_end,
                frame_numbers=frame_numbers,
                success=False,
                error=response.error
            )
        
        # Parse response with correct parameters
        return self._parse_vlm_response(
            response.parsed_json,
            second_index,
            timestamp_start,
            timestamp_end,
            frame_numbers
        )
    
    async def analyze_video_parallel(
        self,
        frame_batches: List[List[FrameData]],
        yolo_detections: Dict[int, List[dict]],
        max_concurrent: int = None,
        progress_callback=None
    ) -> List[SecondAnalysis]:
        """
        Analyze multiple seconds of video in parallel with optimized concurrency.
        
        Args:
            frame_batches: List of frame batches (each batch = 3 frames from 1 second)
            yolo_detections: All YOLO detections indexed by frame number
            max_concurrent: Maximum concurrent API calls (uses Config.VLM_MAX_CONCURRENT if None)
            progress_callback: Optional callback for progress updates (receives completed_count, total_count)
        
        Returns:
            List of SecondAnalysis results
        """
        if max_concurrent is None:
            max_concurrent = Config.VLM_MAX_CONCURRENT
        
        logger.info(f"Starting parallel analysis of {len(frame_batches)} seconds with concurrency={max_concurrent}")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        completed_count = 0
        total_count = len(frame_batches)
        
        async def analyze_with_semaphore(batch: List[FrameData], idx: int):
            nonlocal completed_count
            async with semaphore:
                result = await self.analyze_second(batch, yolo_detections, idx)
                completed_count += 1
                
                if progress_callback:
                    try:
                        await progress_callback(completed_count, total_count)
                    except Exception as e:
                        logger.warning(f"Progress callback error: {e}")
                
                logger.debug(f"Completed {completed_count}/{total_count} seconds")
                return result
        
        tasks = [
            analyze_with_semaphore(batch, idx)
            for idx, batch in enumerate(frame_batches)
        ]
        
        return await asyncio.gather(*tasks, return_exceptions=False)
    
    def create_video_summary(
        self,
        video_id: str,
        analyses: List[SecondAnalysis],
        total_video_seconds: int
    ) -> VideoAnalysisSummary:
        """
        Create overall video analysis summary.
        
        Args:
            video_id: Video identifier
            analyses: List of per-second analyses
            total_video_seconds: Total duration of video in seconds
        
        Returns:
            VideoAnalysisSummary object
        """
        successful_analyses = [a for a in analyses if a.success]
        
        # Calculate statistics
        risk_scores = [a.risk_score for a in successful_analyses if a.risk_score > 0]
        avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0
        max_risk = max(risk_scores) if risk_scores else 0
        
        # Collect critical observations (warning or critical risk level)
        critical_observations = []
        for analysis in successful_analyses:
            for obs in analysis.observations:
                if obs.risk_level in ["critical", "warning"]:
                    critical_observations.append(obs)
        
        return VideoAnalysisSummary(
            video_id=video_id,
            total_seconds=total_video_seconds,
            analyzed_seconds=len(successful_analyses),
            avg_risk_score=avg_risk,
            max_risk_score=max_risk,
            critical_observations=critical_observations,
            all_analyses=analyses
        )
