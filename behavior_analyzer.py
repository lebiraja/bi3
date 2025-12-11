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
    
    def __init__(self, vlm_client: VLMClient = None):
        """
        Initialize behavior analyzer.
        
        Args:
            vlm_client: VLM client instance (creates new if not provided)
        """
        self.vlm_client = vlm_client or VLMClient()
    
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
        response: VLMResponse,
        second_index: int,
        frame_data: List[FrameData]
    ) -> SecondAnalysis:
        """
        Parse VLM response into SecondAnalysis.
        
        Args:
            response: VLM API response
            second_index: Index of the second being analyzed
            frame_data: List of FrameData objects
        
        Returns:
            SecondAnalysis object
        """
        frame_numbers = [f.frame_number for f in frame_data]
        timestamp_start = min(f.timestamp_ms for f in frame_data) if frame_data else 0
        timestamp_end = max(f.timestamp_ms for f in frame_data) if frame_data else 0
        
        if not response.success:
            return SecondAnalysis(
                second_index=second_index,
                timestamp_start_ms=timestamp_start,
                timestamp_end_ms=timestamp_end,
                frame_numbers=frame_numbers,
                success=False,
                error=response.error
            )
        
        # Parse JSON response
        parsed = response.parsed_json or {}
        
        # Extract observations
        observations = [
            BehaviorObservation.from_dict(obs)
            for obs in parsed.get("observations", [])
        ]
        
        # Extract overall assessment
        assessment = parsed.get("overall_assessment", {})
        
        return SecondAnalysis(
            second_index=second_index,
            timestamp_start_ms=timestamp_start,
            timestamp_end_ms=timestamp_end,
            frame_numbers=frame_numbers,
            observations=observations,
            risk_score=assessment.get("risk_score", 0),
            summary=assessment.get("summary", ""),
            recommended_alerts=assessment.get("recommended_alerts", []),
            raw_response=parsed,
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
        
        # Call VLM
        response = await self.vlm_client.analyze_frames(base64_frames, yolo_data)
        
        # Parse response
        return self._parse_vlm_response(response, second_index, frames)
    
    async def analyze_video_parallel(
        self,
        frame_batches: List[List[FrameData]],
        yolo_detections: Dict[int, List[dict]],
        max_concurrent: int = 3
    ) -> List[SecondAnalysis]:
        """
        Analyze multiple seconds of video in parallel.
        
        Args:
            frame_batches: List of frame batches (each batch = 3 frames from 1 second)
            yolo_detections: All YOLO detections indexed by frame number
            max_concurrent: Maximum concurrent API calls
        
        Returns:
            List of SecondAnalysis results
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def analyze_with_semaphore(batch: List[FrameData], idx: int):
            async with semaphore:
                return await self.analyze_second(batch, yolo_detections, idx)
        
        tasks = [
            analyze_with_semaphore(batch, idx)
            for idx, batch in enumerate(frame_batches)
        ]
        
        return await asyncio.gather(*tasks)
    
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
