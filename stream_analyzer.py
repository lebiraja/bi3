"""
Stream Analyzer Module.
Orchestrates continuous real-time analysis of live streams.
Uses frame-by-frame YOLO processing with async VLM sampling.
"""

import asyncio
import logging
import time
import base64
import cv2
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from dataclasses import dataclass

from stream_processor import StreamExtractor, StreamManager, StreamState
from continuous_yolo import ContinuousYOLOProcessor
from vlm_sampler import VLMSampler, VLMContext
from ollama_vision_client import OllamaVisionClient
from behavior_analyzer import BehaviorObservation
from mongodb_handler import MongoDBHandler
from report_generator import ReportGenerator
from config import Config

logger = logging.getLogger(__name__)


@dataclass
class VLMAnalysisResult:
    """Result from a VLM analysis."""
    timestamp_ms: float
    observations: List[BehaviorObservation]
    risk_score: int
    summary: str
    recommended_alerts: List[str]
    processing_time_ms: float
    success: bool
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "timestamp_ms": self.timestamp_ms,
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
            "processing_time_ms": self.processing_time_ms,
            "success": self.success,
            "error": self.error
        }


class StreamAnalyzer:
    """
    Orchestrates continuous analysis of live streams.

    Architecture:
    1. YOLO processes frames inline (~30ms/frame on GPU)
    2. VLMSampler selects frames every 2 seconds for VLM analysis
    3. VLM runs asynchronously (doesn't block YOLO)
    4. WebSocket broadcasts at ~15fps

    TARGET LATENCY: <5 seconds end-to-end
    """

    def __init__(
        self,
        stream_manager: StreamManager,
        mongodb: Optional[MongoDBHandler] = None,
        use_mongodb: bool = True
    ):
        """
        Initialize stream analyzer.

        Args:
            stream_manager: StreamManager instance
            mongodb: MongoDB handler (creates new if not provided)
            use_mongodb: Whether to store results in MongoDB
        """
        self.stream_manager = stream_manager
        self.use_mongodb = use_mongodb

        # Initialize components
        self.yolo_processor = ContinuousYOLOProcessor(use_tracking=True)
        self.vlm_client = OllamaVisionClient(max_concurrent=Config.VLM_MAX_CONCURRENT)
        self.report_generator = ReportGenerator()

        # MongoDB setup
        if use_mongodb:
            self.mongodb = mongodb or MongoDBHandler()
        else:
            self.mongodb = None

        # Active analysis tasks
        self.analysis_tasks: Dict[str, asyncio.Task] = {}
        self.vlm_tasks: Dict[str, asyncio.Task] = {}

        # Per-stream state
        self.stream_samplers: Dict[str, VLMSampler] = {}

        logger.info("StreamAnalyzer initialized with continuous pipeline architecture")

    async def start_analysis(
        self,
        stream_id: str,
        url: str,
        quality: str = "720p",
        progress_callback: Optional[Callable] = None,
        event_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Start continuous stream analysis.

        Args:
            stream_id: Unique stream identifier
            url: Stream URL
            quality: Preferred stream quality
            progress_callback: Callback for progress updates
            event_callback: Callback for real-time events (YOLO, VLM, reports)

        Returns:
            Initial stream info
        """
        try:
            # Create stream
            extractor = self.stream_manager.create_stream(stream_id, url, quality)

            # Start stream and get info
            logger.info(f"Starting stream analysis for: {stream_id}")
            stream_info = extractor.start_stream(stream_id)

            # Update state
            self.stream_manager.update_state(stream_id, StreamState.INITIALIZING)

            # Store stream session in MongoDB
            if self.mongodb:
                await self._store_stream_session(stream_id, url, stream_info)

            # Initialize VLM sampler for this stream
            self.stream_samplers[stream_id] = VLMSampler(
                sample_interval=Config.STREAM_VLM_SAMPLE_INTERVAL,
                min_vehicles=Config.STREAM_VLM_MIN_VEHICLES,
                context_window=Config.STREAM_CONTEXT_WINDOW
            )

            # Start continuous analysis task
            task = asyncio.create_task(
                self._continuous_analysis_loop(
                    stream_id,
                    extractor,
                    progress_callback,
                    event_callback
                )
            )
            self.analysis_tasks[stream_id] = task

            return {
                'stream_id': stream_id,
                'url': url,
                'title': stream_info.title,
                'is_live': stream_info.is_live,
                'resolution': f"{stream_info.width}x{stream_info.height}",
                'fps': stream_info.fps,
                'state': StreamState.INITIALIZING.value,
            }

        except Exception as e:
            logger.error(f"Failed to start stream analysis: {e}")
            self.stream_manager.update_state(stream_id, StreamState.ERROR, str(e))
            raise

    async def _continuous_analysis_loop(
        self,
        stream_id: str,
        extractor: StreamExtractor,
        progress_callback: Optional[Callable],
        event_callback: Optional[Callable]
    ):
        """
        Main continuous processing loop.
        Processes frames inline for reliability.
        """
        frame_count = 0
        start_time = time.time()
        last_broadcast_time = 0
        broadcast_interval = 1.0 / 15  # 15 FPS for WebSocket

        try:
            # Get VLM sampler for this stream
            vlm_sampler = self.stream_samplers[stream_id]

            # Load YOLO model
            if self.yolo_processor.model is None:
                self.yolo_processor.load_model()

            # Notify initialization
            if event_callback:
                await event_callback({
                    'type': 'initialization_started',
                    'stream_id': stream_id,
                    'architecture': 'continuous',
                    'vlm_interval': Config.STREAM_VLM_SAMPLE_INTERVAL,
                })

            logger.info(f"[{stream_id}] Starting continuous analysis pipeline")

            # Start VLM consumer task
            vlm_task = asyncio.create_task(
                self._vlm_consumer_loop(
                    stream_id,
                    vlm_sampler,
                    event_callback
                )
            )
            self.vlm_tasks[stream_id] = vlm_task

            # Wait for initial frames to buffer
            await asyncio.sleep(1.0)

            # Update to active state
            self.stream_manager.update_state(stream_id, StreamState.ACTIVE)

            if event_callback:
                await event_callback({
                    'type': 'initialization_complete',
                    'stream_id': stream_id,
                })

            logger.info(f"[{stream_id}] Pipeline active, entering main loop")

            # Main loop: Process frames with YOLO and broadcast results
            while extractor.is_running:
                try:
                    # Get frame from stream buffer
                    frame_data = extractor.get_frame()
                    if frame_data is None:
                        await asyncio.sleep(0.01)
                        continue

                    frame_number, frame, timestamp_ms = frame_data
                    frame_count += 1

                    # Run YOLO detection on this frame
                    yolo_start = time.time()
                    detections = self.yolo_processor._run_inference(frame)
                    yolo_time = (time.time() - yolo_start) * 1000

                    # Add to VLM sampler buffer
                    vlm_sampler.add_detection(
                        frame_number,
                        timestamp_ms,
                        frame.copy(),  # Copy frame to avoid reference issues
                        detections
                    )

                    # Send YOLO detection event (every frame)
                    if event_callback:
                        await event_callback({
                            'type': 'yolo_detection',
                            'stream_id': stream_id,
                            'frame_number': frame_number,
                            'vehicle_count': len(detections),
                            'detections': detections,
                            'processing_time_ms': yolo_time,
                        })

                    # Broadcast annotated frame at ~15fps
                    current_time = time.time()
                    if current_time - last_broadcast_time >= broadcast_interval:
                        last_broadcast_time = current_time

                        # Draw detections on frame
                        annotated_frame = self.yolo_processor._draw_detections(frame, detections)

                        # Encode to base64
                        _, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                        frame_base64 = base64.b64encode(buffer).decode('utf-8')

                        if event_callback:
                            await event_callback({
                                'type': 'yolo_video_frame',
                                'stream_id': stream_id,
                                'frame_number': frame_number,
                                'frame': frame_base64,
                                'detection_count': len(detections),
                                'timestamp': timestamp_ms,
                            })

                    # Small delay to prevent CPU spinning
                    await asyncio.sleep(0.001)

                except Exception as e:
                    logger.warning(f"[{stream_id}] Frame processing error: {e}")
                    await asyncio.sleep(0.1)
                    continue

            logger.info(f"[{stream_id}] Stream ended. Total frames: {frame_count}")

        except Exception as e:
            logger.error(f"[{stream_id}] Error in analysis loop: {e}")
            self.stream_manager.update_state(stream_id, StreamState.ERROR, str(e))

            if event_callback:
                await event_callback({
                    'type': 'error',
                    'stream_id': stream_id,
                    'error': str(e),
                })
        finally:
            # Clean up
            self._cleanup_stream(stream_id)
            self.stream_manager.update_state(stream_id, StreamState.STOPPED)

            elapsed = time.time() - start_time
            logger.info(f"[{stream_id}] Analysis complete. Frames: {frame_count}, Duration: {elapsed:.1f}s")

    async def _vlm_consumer_loop(
        self,
        stream_id: str,
        vlm_sampler: VLMSampler,
        event_callback: Optional[Callable]
    ):
        """
        Async VLM consumer that runs independently of YOLO.
        Samples frames every 2 seconds and sends to VLM for analysis.
        """
        logger.info(f"[{stream_id}] VLM consumer started")
        vlm_analysis_count = 0

        try:
            while stream_id in self.stream_samplers:
                # Check if we have enough buffer for context
                buffer_size = len(vlm_sampler.detection_buffer)
                if buffer_size < 60:
                    if buffer_size % 10 == 0:  # Log every 10 frames
                        logger.debug(f"[{stream_id}] VLM waiting for buffer: {buffer_size}/60")
                    await asyncio.sleep(0.5)
                    continue

                # Get latest detection
                latest = vlm_sampler.detection_buffer[-1]

                should_sample, reason = vlm_sampler.should_sample(
                    latest['timestamp_ms'],
                    latest['detections']
                )

                if not should_sample:
                    await asyncio.sleep(0.1)
                    continue

                logger.info(f"[{stream_id}] VLM sampling triggered: {reason}")

                # Get context frames
                context = vlm_sampler.get_context_frames(latest['timestamp_ms'])
                if context is None:
                    await asyncio.sleep(0.1)
                    continue

                # Run VLM analysis
                try:
                    start_time = time.time()

                    # Get base64 frames
                    base64_frames = vlm_sampler.get_base64_frames(context)

                    # Call VLM
                    response = await self.vlm_client.analyze_frames(
                        base64_frames,
                        context.yolo_context
                    )

                    processing_time = (time.time() - start_time) * 1000

                    if response.success:
                        # Parse response
                        parsed = response.parsed_json
                        observations = [
                            BehaviorObservation.from_dict(obs)
                            for obs in parsed.get("observations", [])
                        ]

                        assessment = parsed.get("overall_assessment", {})

                        result = VLMAnalysisResult(
                            timestamp_ms=context.current_timestamp_ms,
                            observations=observations,
                            risk_score=assessment.get("risk_score", 0),
                            summary=assessment.get("summary", ""),
                            recommended_alerts=assessment.get("recommended_alerts", []),
                            processing_time_ms=processing_time,
                            success=True
                        )

                        logger.info(
                            f"[{stream_id}] VLM analysis complete: "
                            f"risk={result.risk_score}, time={processing_time:.0f}ms"
                        )

                        # Send VLM event
                        if event_callback:
                            await event_callback({
                                'type': 'vlm_analysis',
                                'stream_id': stream_id,
                                'analysis': result.to_dict(),
                            })

                        # Generate report for critical incidents
                        if result.risk_score >= 7:
                            await self._generate_report_async(
                                stream_id,
                                result,
                                event_callback
                            )

                        # Store in MongoDB
                        if self.mongodb:
                            await self._store_vlm_analysis(stream_id, result)

                    else:
                        logger.warning(f"[{stream_id}] VLM analysis failed: {response.error}")

                except Exception as e:
                    logger.error(f"[{stream_id}] VLM error: {e}")

                # Wait before next sample
                await asyncio.sleep(0.5)

        except asyncio.CancelledError:
            logger.info(f"[{stream_id}] VLM consumer cancelled")
        except Exception as e:
            logger.error(f"[{stream_id}] VLM consumer error: {e}")

    async def _generate_report_async(
        self,
        stream_id: str,
        analysis: VLMAnalysisResult,
        event_callback: Optional[Callable]
    ):
        """Generate enhanced report asynchronously."""
        try:
            # Build VLM analysis dict for report generator
            vlm_analysis = {
                'observations': [
                    {
                        'behavior_type': obs.behavior_type,
                        'risk_level': obs.risk_level,
                        'description': obs.description,
                        'confidence': obs.confidence,
                        'evidence': obs.evidence
                    }
                    for obs in analysis.observations
                ],
                'overall_assessment': {
                    'risk_score': analysis.risk_score,
                    'summary': analysis.summary,
                    'recommended_alerts': analysis.recommended_alerts
                },
                'timestamp_ms': analysis.timestamp_ms
            }

            report = await self.report_generator.generate_enhanced_report(
                vlm_analysis=vlm_analysis,
                video_metadata={'stream_id': stream_id, 'type': 'live_stream'}
            )

            if event_callback:
                await event_callback({
                    'type': 'enhanced_report',
                    'stream_id': stream_id,
                    'report': report,
                })

            logger.info(f"[{stream_id}] Critical incident report generated")

        except Exception as e:
            logger.error(f"[{stream_id}] Failed to generate report: {e}")

    def _cleanup_stream(self, stream_id: str):
        """Clean up stream resources."""
        # Cancel VLM task
        if stream_id in self.vlm_tasks:
            self.vlm_tasks[stream_id].cancel()
            del self.vlm_tasks[stream_id]

        # Remove sampler
        if stream_id in self.stream_samplers:
            del self.stream_samplers[stream_id]

        # Remove from analysis tasks
        if stream_id in self.analysis_tasks:
            del self.analysis_tasks[stream_id]

        logger.info(f"[{stream_id}] Stream resources cleaned up")

    async def stop_analysis(self, stream_id: str) -> Dict[str, Any]:
        """
        Stop stream analysis.

        Args:
            stream_id: Stream to stop

        Returns:
            Final statistics
        """
        logger.info(f"Stopping analysis for stream: {stream_id}")

        # Cancel analysis task
        if stream_id in self.analysis_tasks:
            task = self.analysis_tasks[stream_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Get final status
        status = self.stream_manager.get_status(stream_id)

        # Add processor stats
        if status:
            status['yolo_stats'] = self.yolo_processor.get_stats()
            if stream_id in self.stream_samplers:
                status['vlm_stats'] = self.stream_samplers[stream_id].get_stats()

        # Remove stream
        self.stream_manager.remove_stream(stream_id)

        # Update MongoDB
        if self.mongodb:
            await self._finalize_stream_session(stream_id)

        logger.info(f"Stream {stream_id} stopped")
        return status or {}

    async def _store_stream_session(self, stream_id: str, url: str, stream_info):
        """Store stream session in MongoDB."""
        try:
            session_data = {
                'stream_id': stream_id,
                'url': url,
                'title': stream_info.title,
                'is_live': stream_info.is_live,
                'resolution': f"{stream_info.width}x{stream_info.height}",
                'fps': stream_info.fps,
                'start_time': datetime.utcnow(),
                'status': 'active',
                'architecture': 'continuous',
                'vlm_interval': Config.STREAM_VLM_SAMPLE_INTERVAL,
            }

            await asyncio.to_thread(
                self.mongodb.db['stream_sessions'].insert_one,
                session_data
            )

            logger.info(f"Stored stream session: {stream_id}")
        except Exception as e:
            logger.error(f"Failed to store stream session: {e}")

    async def _store_vlm_analysis(self, stream_id: str, analysis: VLMAnalysisResult):
        """Store VLM analysis result in MongoDB."""
        try:
            analysis_data = {
                'stream_id': stream_id,
                'timestamp_ms': analysis.timestamp_ms,
                'timestamp': datetime.utcnow(),
                'risk_score': analysis.risk_score,
                'summary': analysis.summary,
                'observations': [
                    {
                        'behavior_type': obs.behavior_type,
                        'vehicle_id': obs.vehicle_id,
                        'confidence': obs.confidence,
                        'risk_level': obs.risk_level,
                        'description': obs.description
                    }
                    for obs in analysis.observations
                ],
                'processing_time_ms': analysis.processing_time_ms,
            }

            await asyncio.to_thread(
                self.mongodb.db['stream_vlm_analyses'].insert_one,
                analysis_data
            )

        except Exception as e:
            logger.error(f"Failed to store VLM analysis: {e}")

    async def _finalize_stream_session(self, stream_id: str):
        """Finalize stream session in MongoDB."""
        try:
            await asyncio.to_thread(
                self.mongodb.db['stream_sessions'].update_one,
                {'stream_id': stream_id},
                {
                    '$set': {
                        'end_time': datetime.utcnow(),
                        'status': 'completed',
                    }
                }
            )
        except Exception as e:
            logger.error(f"Failed to finalize stream session: {e}")
