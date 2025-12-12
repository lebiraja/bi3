"""
Stream Analyzer Module.
Orchestrates continuous real-time analysis of live streams.
Implements 15-second batch processing with 5-second wait cycles.
"""

import asyncio
import logging
import uuid
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from dataclasses import dataclass

from stream_processor import StreamExtractor, StreamManager, StreamState
from video_analyzer import YOLODetector
from behavior_analyzer import BehaviorAnalyzer, SecondAnalysis, VideoAnalysisSummary
from frame_sampler import FrameData, FrameSampler
from mongodb_handler import MongoDBHandler
from report_generator import ReportGenerator
from config import Config

logger = logging.getLogger(__name__)


@dataclass
class StreamBatch:
    """Represents a processed batch of stream frames."""
    batch_index: int
    stream_id: str
    timestamp: datetime
    frame_count: int
    yolo_detections: Dict[int, List[dict]]
    vlm_analyses: List[SecondAnalysis]
    enhanced_reports: List[Dict[str, Any]]
    avg_risk_score: float
    processing_time: float


class StreamAnalyzer:
    """
    Orchestrates continuous analysis of live streams.
    
    Processing flow:
    1. Extract 15 seconds of frames (45 frames at 3fps)
    2. Run YOLO detection on all frames
    3. Run VLM analysis on frame batches
    4. Generate enhanced reports for critical incidents
    5. Wait 5 seconds
    6. Repeat until stopped
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
        self.yolo_detector = YOLODetector()
        self.behavior_analyzer = BehaviorAnalyzer(is_stream=True)  # Use stream-specific VLM limits
        self.report_generator = ReportGenerator()
        
        # MongoDB setup
        if use_mongodb:
            self.mongodb = mongodb or MongoDBHandler()
        else:
            self.mongodb = None
        
        # Active analysis tasks
        self.analysis_tasks: Dict[str, asyncio.Task] = {}
        
        logger.info("StreamAnalyzer initialized with stream-optimized VLM settings")
    
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
        Implements 15s processing + 5s wait cycle.
        """
        batch_index = 0
        
        try:
            # Initial 20-second window (process first 15 seconds)
            logger.info(f"[{stream_id}] Starting 20-second initialization...")
            
            if event_callback:
                await event_callback({
                    'type': 'initialization_started',
                    'stream_id': stream_id,
                    'duration': 20,
                })
            
            # Process first batch
            batch = await self._process_batch(
                stream_id,
                extractor,
                batch_index,
                progress_callback,
                event_callback
            )
            
            if batch:
                batch_index += 1
                self.stream_manager.increment_batch(stream_id, batch.frame_count)
            
            # Update to active state
            self.stream_manager.update_state(stream_id, StreamState.ACTIVE)
            
            if event_callback:
                await event_callback({
                    'type': 'initialization_complete',
                    'stream_id': stream_id,
                    'batch': batch,
                })
            
            logger.info(f"[{stream_id}] Initialization complete, entering continuous loop")
            
            # Continuous loop
            while extractor.is_running:
                # 5-second wait period
                logger.info(f"[{stream_id}] Waiting 5 seconds before next batch...")
                
                if event_callback:
                    await event_callback({
                        'type': 'wait_started',
                        'stream_id': stream_id,
                        'duration': 5,
                    })
                
                await asyncio.sleep(5)
                
                if not extractor.is_running:
                    break
                
                # Process next batch
                logger.info(f"[{stream_id}] Processing batch {batch_index}...")
                
                batch = await self._process_batch(
                    stream_id,
                    extractor,
                    batch_index,
                    progress_callback,
                    event_callback
                )
                
                if batch:
                    batch_index += 1
                    self.stream_manager.increment_batch(stream_id, batch.frame_count)
                else:
                    logger.warning(f"[{stream_id}] Failed to process batch {batch_index}")
                    break
            
            logger.info(f"[{stream_id}] Analysis loop completed. Total batches: {batch_index}")
            
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
            self.stream_manager.update_state(stream_id, StreamState.STOPPED)
            if stream_id in self.analysis_tasks:
                del self.analysis_tasks[stream_id]
    
    async def _process_batch(
        self,
        stream_id: str,
        extractor: StreamExtractor,
        batch_index: int,
        progress_callback: Optional[Callable],
        event_callback: Optional[Callable]
    ) -> Optional[StreamBatch]:
        """
        Process a 15-second batch of frames.
        
        Returns:
            StreamBatch with results or None on failure
        """
        import time
        start_time = time.time()
        
        try:
            # Extract frames (15 seconds at 3fps = 45 frames)
            logger.info(f"[{stream_id}] Extracting frames for batch {batch_index}...")
            frame_tuples = extractor.get_batch_frames(duration=15, target_fps=3)
            
            if not frame_tuples:
                logger.error(f"[{stream_id}] No frames extracted for batch {batch_index}")
                return None
            
            logger.info(f"[{stream_id}] Extracted {len(frame_tuples)} frames")
            
            # Convert to FrameData objects
            frame_data_list = []
            for frame_number, frame, timestamp_ms in frame_tuples:
                # Encode frame to base64 for storage
                base64_encoded = FrameSampler.encode_frame_base64(frame)
                
                frame_data = FrameData(
                    frame_number=frame_number,
                    timestamp_ms=timestamp_ms,
                    image_data=frame,  # Changed from 'frame' to 'image_data'
                    base64_encoded=base64_encoded,
                    width=frame.shape[1],
                    height=frame.shape[0],
                )
                frame_data.second_index = int(timestamp_ms / 1000)  # Add second_index attribute
                frame_data_list.append(frame_data)
            
            # Group into 1-second batches (3 frames each)
            frame_batches = []
            for i in range(0, len(frame_data_list), 3):
                batch = frame_data_list[i:i+3]
                if len(batch) == 3:  # Only process complete batches
                    frame_batches.append(batch)
            
            logger.info(f"[{stream_id}] Created {len(frame_batches)} 1-second batches")
            
            # Run YOLO detection on all frames
            logger.info(f"[{stream_id}] Running YOLO detection...")
            yolo_detections = {}
            
            for frame_data in frame_data_list:
                detections = self.yolo_detector.detect_in_frame(frame_data.image_data)
                yolo_detections[frame_data.frame_number] = detections
                
                # Send YOLO event (encode frame to base64 for JSON serialization)
                if event_callback:
                    # Use the already-encoded base64 from FrameData
                    await event_callback({
                        'type': 'yolo_detection',
                        'stream_id': stream_id,
                        'batch_index': batch_index,
                        'frame_number': frame_data.frame_number,
                        'detections': detections,
                        'frame_base64': frame_data.base64_encoded,  # Use pre-encoded base64
                    })
                
                # Send annotated video frame every 2 seconds (6 frames at 3fps)
                if event_callback and frame_data.frame_number % 6 == 0:
                    # Draw YOLO detections on frame
                    annotated_frame = self.yolo_detector.draw_detections(frame_data.image_data, detections)
                    
                    # Encode annotated frame to base64
                    import cv2
                    import base64
                    _, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    annotated_base64 = base64.b64encode(buffer).decode('utf-8')
                    
                    await event_callback({
                        'type': 'yolo_video_frame',
                        'stream_id': stream_id,
                        'batch_index': batch_index,
                        'frame_number': frame_data.frame_number,
                        'frame': annotated_base64,
                        'detection_count': len(detections),
                        'timestamp': time.time()
                    })
            
            logger.info(f"[{stream_id}] YOLO detection complete")
            
            # Apply VLM optimizations: interval sampling and activity filtering
            logger.info(f"[{stream_id}] Applying VLM optimizations (interval={Config.STREAM_VLM_INTERVAL}, skip_low_activity={Config.STREAM_SKIP_LOW_ACTIVITY})")
            
            # Filter batches for VLM analysis
            vlm_batches = []
            skipped_count = 0
            
            for idx, batch in enumerate(frame_batches):
                # Check interval sampling (analyze every Nth second)
                if idx % Config.STREAM_VLM_INTERVAL != 0:
                    skipped_count += 1
                    continue
                
                # Check activity level (skip if too few vehicles)
                if Config.STREAM_SKIP_LOW_ACTIVITY:
                    # Count total vehicles in this batch
                    total_vehicles = sum(
                        len(yolo_detections.get(f.frame_number, []))
                        for f in batch
                    )
                    if total_vehicles < Config.STREAM_MIN_VEHICLES_FOR_VLM:
                        skipped_count += 1
                        logger.debug(f"[{stream_id}] Skipping second {idx} - low activity ({total_vehicles} vehicles)")
                        continue
                
                vlm_batches.append((idx, batch))
            
            logger.info(f"[{stream_id}] VLM analysis: {len(vlm_batches)} seconds selected, {skipped_count} skipped")
            
            # Run VLM analysis on selected batches
            if vlm_batches:
                logger.info(f"[{stream_id}] Running VLM analysis on {len(vlm_batches)} seconds...")
                
                # Prepare batches with their indices
                batches_only = [batch for _, batch in vlm_batches]
                indices = [idx for idx, _ in vlm_batches]
                
                vlm_results = await self.behavior_analyzer.analyze_video_parallel(
                    batches_only,
                    yolo_detections,
                    max_concurrent=Config.VLM_MAX_CONCURRENT,
                    progress_callback=progress_callback
                )
                
                # Create full analysis list with placeholders for skipped seconds
                vlm_analyses = []
                result_idx = 0
                for idx in range(len(frame_batches)):
                    if idx in indices:
                        vlm_analyses.append(vlm_results[result_idx])
                        result_idx += 1
                    else:
                        # Create placeholder for skipped second
                        batch = frame_batches[idx]
                        vlm_analyses.append(SecondAnalysis(
                            second_index=idx,
                            timestamp_start_ms=min(f.timestamp_ms for f in batch),
                            timestamp_end_ms=max(f.timestamp_ms for f in batch),
                            frame_numbers=[f.frame_number for f in batch],
                            observations=[],
                            risk_score=0,
                            summary="Skipped (optimization)",
                            recommended_alerts=[],
                            success=True,
                            error=None
                        ))
            else:
                logger.info(f"[{stream_id}] No batches selected for VLM analysis (all skipped)")
                # Create placeholders for all seconds
                vlm_analyses = [
                    SecondAnalysis(
                        second_index=idx,
                        timestamp_start_ms=min(f.timestamp_ms for f in batch),
                        timestamp_end_ms=max(f.timestamp_ms for f in batch),
                        frame_numbers=[f.frame_number for f in batch],
                        observations=[],
                        risk_score=0,
                        summary="Skipped (low activity)",
                        recommended_alerts=[],
                        success=True,
                        error=None
                    )
                    for idx, batch in enumerate(frame_batches)
                ]
            
            logger.info(f"[{stream_id}] VLM analysis complete. Analyzed {len(vlm_analyses)} seconds")
            
            # Send VLM events
            for analysis in vlm_analyses:
                if event_callback:
                    await event_callback({
                        'type': 'vlm_summary',
                        'stream_id': stream_id,
                        'batch_index': batch_index,
                        'analysis': analysis.to_dict(),
                    })
            
            # Generate enhanced reports for critical incidents
            enhanced_reports = []
            critical_analyses = [a for a in vlm_analyses if a.risk_score >= 7]
            
            if critical_analyses:
                logger.info(f"[{stream_id}] Found {len(critical_analyses)} critical incidents, generating reports...")
                
                for analysis in critical_analyses:
                    try:
                        report = await self.report_generator.generate_enhanced_report(
                            video_id=stream_id,
                            analysis_summary={
                                'critical_observations': [obs.__dict__ for obs in analysis.observations],
                                'risk_score': analysis.risk_score,
                                'timestamp': analysis.timestamp_start_ms,
                            }
                        )
                        
                        enhanced_reports.append(report)
                        
                        # Send report event
                        if event_callback:
                            await event_callback({
                                'type': 'enhanced_report',
                                'stream_id': stream_id,
                                'batch_index': batch_index,
                                'report': report,
                            })
                    except Exception as e:
                        logger.error(f"[{stream_id}] Failed to generate report: {e}")
            
            # Calculate average risk score
            avg_risk = sum(a.risk_score for a in vlm_analyses) / len(vlm_analyses) if vlm_analyses else 0
            
            # Create batch result
            batch = StreamBatch(
                batch_index=batch_index,
                stream_id=stream_id,
                timestamp=datetime.utcnow(),
                frame_count=len(frame_data_list),
                yolo_detections=yolo_detections,
                vlm_analyses=vlm_analyses,
                enhanced_reports=enhanced_reports,
                avg_risk_score=avg_risk,
                processing_time=time.time() - start_time,
            )
            
            # Store in MongoDB
            if self.mongodb:
                await self._store_batch(batch)
            
            # Send batch complete event
            if event_callback:
                await event_callback({
                    'type': 'batch_complete',
                    'stream_id': stream_id,
                    'batch_index': batch_index,
                    'frame_count': batch.frame_count,
                    'avg_risk_score': batch.avg_risk_score,
                    'processing_time': batch.processing_time,
                    'critical_incidents': len(enhanced_reports),
                })
            
            logger.info(f"[{stream_id}] Batch {batch_index} complete in {batch.processing_time:.2f}s")
            return batch
            
        except Exception as e:
            logger.error(f"[{stream_id}] Error processing batch {batch_index}: {e}")
            return None
    
    def _sample_batches_adaptively(
        self,
        frame_batches: List[List[FrameData]],
        yolo_detections: Dict[int, List[dict]],
        stream_id: str = ""
    ) -> List[int]:
        """
        Adaptively select which frame batches (seconds) to run VLM analysis on.
        
        Uses intelligent heuristics instead of simple interval sampling:
        1. Always analyze seconds with high vehicle activity
        2. Analyze seconds with detected anomalies or behavior changes
        3. Analyze seconds with rapid vehicle count changes
        4. Skip seconds with no activity or repeated patterns
        
        Args:
            frame_batches: List of frame batches (each = 3 frames = 1 second)
            yolo_detections: Dict mapping frame numbers to detection lists
            stream_id: Stream ID for logging
            
        Returns:
            List of indices (0-based second numbers) to analyze with VLM
        """
        selected_indices = []
        activity_scores = []
        vehicle_counts = []
        
        # Calculate activity metrics for each second
        for idx, batch in enumerate(frame_batches):
            # Count total detections in this second
            total_vehicles = sum(
                len(yolo_detections.get(f.frame_number, []))
                for f in batch
            )
            
            # Calculate average vehicles per frame
            vehicles_per_frame = total_vehicles / len(batch) if batch else 0
            
            # Calculate detection variance (activity)
            frame_counts = [
                len(yolo_detections.get(f.frame_number, []))
                for f in batch
            ]
            activity = max(frame_counts) - min(frame_counts) if frame_counts else 0
            
            vehicle_counts.append(total_vehicles)
            activity_scores.append((vehicles_per_frame, activity))
        
        # Determine dynamic threshold based on average activity
        if vehicle_counts:
            avg_vehicles = sum(vehicle_counts) / len(vehicle_counts)
            threshold = max(1, avg_vehicles * 0.5)  # Analyze if >50% of average activity
        else:
            threshold = 1
        
        # Select indices based on heuristics
        for idx in range(len(frame_batches)):
            vehicles = vehicle_counts[idx]
            vehicles_per_frame, activity = activity_scores[idx]
            
            # Heuristic 1: High activity seconds (always include)
            if vehicles >= threshold * 1.5:
                selected_indices.append(idx)
                continue
            
            # Heuristic 2: Changing activity (vs previous/next second)
            activity_change = False
            if idx > 0:
                prev_vehicles = vehicle_counts[idx - 1]
                if abs(vehicles - prev_vehicles) >= 2:
                    activity_change = True
            if idx < len(vehicle_counts) - 1:
                next_vehicles = vehicle_counts[idx + 1]
                if abs(vehicles - next_vehicles) >= 2:
                    activity_change = True
            
            if activity_change:
                selected_indices.append(idx)
                continue
            
            # Heuristic 3: High variance within second (diverse behavior)
            if activity >= 2:
                selected_indices.append(idx)
                continue
            
            # Heuristic 4: Minimum coverage (sample every Nth second as fallback)
            if idx % Config.STREAM_VLM_INTERVAL == 0 and vehicles > 0:
                selected_indices.append(idx)
                continue
        
        # Ensure at least some analysis if stream has activity
        if not selected_indices and any(vc > 0 for vc in vehicle_counts):
            # Select top 2 busiest seconds
            sorted_indices = sorted(
                range(len(vehicle_counts)),
                key=lambda i: vehicle_counts[i],
                reverse=True
            )
            selected_indices = sorted(sorted_indices[:2])
        
        skipped = len(frame_batches) - len(selected_indices)
        skip_rate = (skipped / len(frame_batches) * 100) if frame_batches else 0
        
        logger.info(
            f"[{stream_id}] Adaptive VLM sampling: {len(selected_indices)} seconds selected, "
            f"{skipped} skipped ({skip_rate:.1f}% skip rate). "
            f"Threshold: {threshold:.1f} vehicles/sec"
        )
        
        return sorted(selected_indices)
    
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
                'total_batches': 0,
                'total_frames': 0,
                'incidents': [],
            }
            
            # Store in stream_sessions collection
            await asyncio.to_thread(
                self.mongodb.db['stream_sessions'].insert_one,
                session_data
            )
            
            logger.info(f"Stored stream session: {stream_id}")
        except Exception as e:
            logger.error(f"Failed to store stream session: {e}")
    
    async def _store_batch(self, batch: StreamBatch):
        """Store batch results in MongoDB."""
        try:
            # Convert integer keys to strings for MongoDB compatibility
            yolo_detections_str_keys = {str(k): v for k, v in batch.yolo_detections.items()}
            
            batch_data = {
                'stream_id': batch.stream_id,
                'batch_index': batch.batch_index,
                'timestamp': batch.timestamp,
                'frame_count': batch.frame_count,
                'yolo_detections': yolo_detections_str_keys,  # Use string keys
                'vlm_analyses': [a.to_dict() for a in batch.vlm_analyses],
                'enhanced_reports': batch.enhanced_reports,
                'avg_risk_score': batch.avg_risk_score,
                'processing_time': batch.processing_time,
            }
            
            # Store in stream_batches collection
            await asyncio.to_thread(
                self.mongodb.db['stream_batches'].insert_one,
                batch_data
            )
            
            # Update session
            await asyncio.to_thread(
                self.mongodb.db['stream_sessions'].update_one,
                {'stream_id': batch.stream_id},
                {
                    '$inc': {'total_batches': 1, 'total_frames': batch.frame_count},
                    '$push': {'incidents': {'$each': batch.enhanced_reports}},
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to store batch: {e}")
    
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
