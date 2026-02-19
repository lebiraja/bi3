"""
Stream Analyzer Module - Real-Time with SMS Integration.
Continuous processing with YOLO, VLM, and incident orchestration for SMS/alerts.
Combines low-latency streaming with SMS notifications when risk_score >= 5.
"""

import asyncio
import logging
import time
import base64
import cv2
import threading
from collections import deque
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from dataclasses import dataclass

from stream_processor import StreamExtractor, StreamManager, StreamState
from continuous_yolo import ContinuousYOLOProcessor
from hybrid_vlm_client import HybridVLMClient, VLMProvider
from behavior_analyzer import BehaviorObservation
from mongodb_handler import MongoDBHandler
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


class RealTimeStreamAnalyzer:
    """
    Real-time stream analyzer with minimal latency and SMS integration.
    
    Architecture:
    - Frame capture: Background thread fills buffer
    - YOLO: Processes in dedicated thread, stores latest result
    - Broadcast: Async loop sends frames at 30fps with <50ms latency
    - VLM: Completely async, updates every few seconds
    - SMS: Triggers incident orchestrator when risk_score >= 5
    """

    def __init__(
        self,
        stream_manager: StreamManager,
        mongodb: Optional[MongoDBHandler] = None,
        use_mongodb: bool = True
    ):
        self.stream_manager = stream_manager
        self.use_mongodb = use_mongodb
        self.mongodb = mongodb or (MongoDBHandler() if use_mongodb else None)

        # YOLO processor (shared across streams)
        self.yolo_processor = ContinuousYOLOProcessor(use_tracking=True)
        
        # VLM client (hybrid: auto-selects based on config)
        vlm_provider = None
        provider_config = Config.VLM_PROVIDER.lower()
        if provider_config == "ollama":
            vlm_provider = VLMProvider.OLLAMA
        elif provider_config == "openrouter":
            vlm_provider = VLMProvider.OPENROUTER
        # else: auto-detect
        
        self.vlm_client = HybridVLMClient(
            provider=vlm_provider,
            max_concurrent=Config.VLM_MAX_CONCURRENT
        )

        # Stream state
        self.active_streams: Dict[str, dict] = {}

        logger.info(f"RealTimeStreamAnalyzer initialized with VLM provider: {self.vlm_client.provider.value}")

    async def start_analysis(
        self,
        stream_id: str,
        url: str,
        quality: str = "720p",
        event_callback: Optional[Callable] = None,
        progress_callback: Optional[Callable] = None
    ) -> dict:
        """Start real-time stream analysis."""

        extractor = self.stream_manager.create_stream(stream_id, url, quality)
        stream_info = extractor.start_stream(stream_id)

        self.stream_manager.update_state(stream_id, StreamState.INITIALIZING)

        # Store stream state
        self.active_streams[stream_id] = {
            'extractor': extractor,
            'event_callback': event_callback,
            'running': True,
            'latest_frame': None,
            'latest_detections': [],
            'frame_count': 0,
            'vlm_frame': None,  # Frame for VLM analysis
            'vlm_detections': [],
        }

        # Load YOLO model
        if self.yolo_processor.model is None:
            self.yolo_processor.load_model()

        # Start processing tasks
        asyncio.create_task(self._yolo_loop(stream_id))
        asyncio.create_task(self._broadcast_loop(stream_id))
        asyncio.create_task(self._vlm_loop(stream_id))

        if event_callback:
            await event_callback({
                'type': 'initialization_started',
                'stream_id': stream_id,
            })

        # Brief wait for buffer
        await asyncio.sleep(0.5)

        self.stream_manager.update_state(stream_id, StreamState.ACTIVE)

        if event_callback:
            await event_callback({
                'type': 'initialization_complete',
                'stream_id': stream_id,
            })

        return {
            'stream_id': stream_id,
            'url': url,
            'title': stream_info.title,
            'is_live': stream_info.is_live,
            'resolution': f"{stream_info.width}x{stream_info.height}",
            'fps': stream_info.fps,
            'state': StreamState.ACTIVE.value,
        }

    async def _yolo_loop(self, stream_id: str):
        """YOLO processing loop - runs as fast as possible."""
        state = self.active_streams.get(stream_id)
        if not state:
            return

        extractor = state['extractor']
        logger.info(f"[{stream_id}] YOLO loop started")

        while state['running'] and extractor.is_running:
            try:
                # Get frame (non-blocking)
                frame_data = extractor.get_frame()
                if frame_data is None:
                    await asyncio.sleep(0.005)  # 5ms wait
                    continue

                frame_number, frame, timestamp_ms = frame_data

                # Run YOLO (fast: ~15-25ms)
                detections = self.yolo_processor._run_inference(frame)

                # Store latest result (atomic update)
                state['latest_frame'] = frame
                state['latest_detections'] = detections
                state['frame_count'] = frame_number
                state['timestamp_ms'] = timestamp_ms

                # Store for VLM every 3 seconds
                vlm_interval_frames = int(Config.STREAM_VLM_SAMPLE_INTERVAL * 30)  # 30fps
                if frame_number % vlm_interval_frames == 0:
                    state['vlm_frame'] = frame.copy()
                    state['vlm_detections'] = detections.copy()

                await asyncio.sleep(0.001)  # Yield to other tasks

            except Exception as e:
                logger.error(f"[{stream_id}] YOLO error: {e}")
                await asyncio.sleep(0.1)

        logger.info(f"[{stream_id}] YOLO loop ended")

    async def _broadcast_loop(self, stream_id: str):
        """Broadcast annotated frames at 30fps with minimal latency."""
        state = self.active_streams.get(stream_id)
        if not state:
            return

        event_callback = state['event_callback']
        logger.info(f"[{stream_id}] Broadcast loop started")

        last_broadcast = 0
        broadcast_interval = 1.0 / Config.STREAM_WEBSOCKET_FPS  # 30 FPS

        while state['running']:
            try:
                current_time = time.time()

                # Rate limit to configured FPS
                if current_time - last_broadcast < broadcast_interval:
                    await asyncio.sleep(0.005)
                    continue

                frame = state.get('latest_frame')
                detections = state.get('latest_detections', [])

                if frame is None:
                    await asyncio.sleep(0.01)
                    continue

                last_broadcast = current_time

                # Draw detections on frame
                annotated = self.yolo_processor._draw_detections(frame.copy(), detections)

                # Encode to JPEG (fast)
                _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 75])
                frame_b64 = base64.b64encode(buffer).decode('utf-8')

                # Broadcast
                if event_callback:
                    await event_callback({
                        'type': 'yolo_video_frame',
                        'stream_id': stream_id,
                        'frame_number': state.get('frame_count', 0),
                        'timestamp_ms': state.get('timestamp_ms', 0),
                        'frame_base64': frame_b64,
                        'vehicle_count': len(detections),
                        'processing_time_ms': 0,  # Instant
                    })

                    # Send detection event
                    await event_callback({
                        'type': 'yolo_detection',
                        'stream_id': stream_id,
                        'frame_number': state.get('frame_count', 0),
                        'vehicle_count': len(detections),
                        'detections': detections,
                        'processing_time_ms': 0,
                    })

            except Exception as e:
                logger.error(f"[{stream_id}] Broadcast error: {e}")
                await asyncio.sleep(0.1)

        logger.info(f"[{stream_id}] Broadcast loop ended")

    async def _vlm_loop(self, stream_id: str):
        """VLM analysis loop - runs independently with SMS integration."""
        state = self.active_streams.get(stream_id)
        if not state:
            return

        event_callback = state['event_callback']
        logger.info(f"[{stream_id}] VLM loop started with SMS integration")

        # Wait for initial frames
        await asyncio.sleep(3)

        while state['running']:
            try:
                frame = state.get('vlm_frame')
                detections = state.get('vlm_detections', [])

                # Check minimum vehicle requirement
                if frame is None or len(detections) < Config.STREAM_VLM_MIN_VEHICLES:
                    await asyncio.sleep(1)
                    continue

                # Resize for VLM
                h, w = frame.shape[:2]
                if h > 480:
                    scale = 480 / h
                    frame = cv2.resize(frame, (int(w * scale), 480), interpolation=cv2.INTER_AREA)

                # Encode
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 65])
                frame_b64 = base64.b64encode(buffer).decode('utf-8')

                # Build context
                yolo_context = {
                    'detections': [[
                        {'track_id': d.get('track_id'), 'class_name': d.get('class_name')}
                        for d in detections[:10]  # Limit to 10 vehicles
                    ]],
                    'vehicle_counts': [len(detections)]
                }

                # Call VLM
                start_time = time.time()
                response = await self.vlm_client.analyze_frames([frame_b64], yolo_context)
                vlm_time = (time.time() - start_time) * 1000

                if response.success and response.parsed_json:
                    parsed = response.parsed_json
                    assessment = parsed.get('overall_assessment', {})

                    observations = []
                    for obs in parsed.get('observations', []):
                        try:
                            observations.append(BehaviorObservation.from_dict(obs))
                        except:
                            pass

                    result = VLMAnalysisResult(
                        timestamp_ms=state.get('timestamp_ms', 0),
                        observations=observations,
                        risk_score=assessment.get('risk_score', 1),
                        summary=assessment.get('summary', ''),
                        recommended_alerts=assessment.get('recommended_alerts', []),
                        processing_time_ms=vlm_time,
                        success=True
                    )

                    logger.info(f"[{stream_id}] VLM: risk={result.risk_score}, time={vlm_time:.0f}ms, provider={response.provider}")

                    if event_callback:
                        await event_callback({
                            'type': 'vlm_analysis',
                            'stream_id': stream_id,
                            'analysis': result.to_dict(),
                        })

                    # SMS Integration: Trigger incident orchestrator if risk >= 5
                    if result.risk_score >= 5:
                        try:
                            logger.info(f"[{stream_id}] High risk detected ({result.risk_score}), triggering SMS notification")
                            await self._trigger_sms_notification(stream_id, result, detections)
                        except Exception as e:
                            logger.error(f"[{stream_id}] Failed to trigger SMS: {e}")
                else:
                    logger.warning(f"[{stream_id}] VLM failed: {response.error}")

                # Wait before next analysis
                await asyncio.sleep(Config.STREAM_VLM_SAMPLE_INTERVAL)

            except Exception as e:
                logger.error(f"[{stream_id}] VLM error: {e}")
                await asyncio.sleep(2)

        logger.info(f"[{stream_id}] VLM loop ended")

    async def _trigger_sms_notification(
        self,
        stream_id: str,
        vlm_result: VLMAnalysisResult,
        detections: List[Dict]
    ):
        """
        Trigger SMS notification via incident orchestrator.
        
        Args:
            stream_id: Stream identifier
            vlm_result: VLM analysis result with high risk score
            detections: YOLO detection results
        """
        try:
            from agent.routes import get_orchestrator
            from agent.models import VLMSummary, EnhancedReportData

            orchestrator = get_orchestrator()

            # Create VLM summary from analysis
            vlm_summary = VLMSummary(
                confidence=min(vlm_result.risk_score / 10.0, 1.0),
                incident_type="Traffic Safety Violation (Live Stream)",
                description=vlm_result.summary or f"Detected {len(vlm_result.observations)} critical observations",
                vehicles_involved=len(set(obs.vehicle_id for obs in vlm_result.observations if hasattr(obs, 'vehicle_id'))),
                recommended_alerts=vlm_result.recommended_alerts or ["sms"],
                ambiguous=False,
                raw_analysis=vlm_result.to_dict()
            )

            # Create enhanced report data
            enhanced_report_data = EnhancedReportData(
                report_text=f"Live stream incident at {datetime.now().isoformat()}\n\n{vlm_result.summary}",
                risk_score=min(10, max(1, vlm_result.risk_score)),
                executive_summary=vlm_result.summary[:200] if vlm_result.summary else "High risk incident detected",
                evidence_mapping={
                    "stream_id": stream_id,
                    "timestamp_ms": vlm_result.timestamp_ms,
                    "observations": [
                        {
                            "behavior_type": obs.behavior_type if hasattr(obs, 'behavior_type') else 'unknown',
                            "vehicle_id": obs.vehicle_id if hasattr(obs, 'vehicle_id') else 'unknown',
                            "risk_level": obs.risk_level if hasattr(obs, 'risk_level') else 'unknown',
                            "description": obs.description if hasattr(obs, 'description') else ''
                        }
                        for obs in vlm_result.observations
                    ],
                    "total_vehicles": len(detections)
                }
            )

            # Create incident data
            import uuid
            incident_data = {
                'incident_id': str(uuid.uuid4()),
                'vlm_summary': vlm_summary.dict(),
                'enhanced_report': enhanced_report_data.dict(),
                'location': None,  # Could be added if GPS data available
                'history': []
            }

            # Process incident (triggers SMS)
            incident_result = await orchestrator.process_incident_async(incident_data)
            incident_id = incident_result.get('action_result', {}).get('incident_id', 'unknown')
            
            logger.info(f"[{stream_id}] ✅ Incident created: {incident_id} - SMS notifications triggered")

        except Exception as e:
            logger.error(f"[{stream_id}] ❌ Failed to create incident: {e}")
            import traceback
            logger.error(traceback.format_exc())

    async def stop_analysis(self, stream_id: str) -> dict:
        """Stop stream analysis."""
        state = self.active_streams.get(stream_id)
        if state:
            state['running'] = False

            extractor = state.get('extractor')
            if extractor:
                extractor.stop_stream()

            del self.active_streams[stream_id]

        self.stream_manager.remove_stream(stream_id)
        logger.info(f"[{stream_id}] Stream stopped")

        return {'stream_id': stream_id, 'status': 'stopped'}

    def get_stream_status(self, stream_id: str) -> Optional[dict]:
        """Get stream status."""
        state = self.active_streams.get(stream_id)
        if not state:
            return None

        return {
            'stream_id': stream_id,
            'frame_count': state.get('frame_count', 0),
            'vehicle_count': len(state.get('latest_detections', [])),
            'running': state.get('running', False),
        }


# Alias for backward compatibility
StreamAnalyzer = RealTimeStreamAnalyzer
