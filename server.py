"""
FastAPI Server for Video Analysis Pipeline.
Provides REST API and WebSocket endpoints for frontend integration.
"""

import asyncio
import uuid
import os
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from pydantic import BaseModel

from config import Config
from frame_sampler import FrameSampler
from mongodb_handler import MongoDBHandler
from vlm_client import VLMClient
from behavior_analyzer import BehaviorAnalyzer, VideoAnalysisSummary
from report_generator import ReportGenerator

# Import agent router for incident orchestration
from agent.routes import router as agent_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Storage for analysis jobs
analysis_jobs: Dict[str, dict] = {}

# WebSocket connections for real-time updates
ws_connections: Dict[str, List[WebSocket]] = {}

# Upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


# ============ Pydantic Models ============

class AnalysisJob(BaseModel):
    """Job status response model."""
    job_id: str
    video_id: str
    video_name: str
    video_path: str
    status: str  # pending, processing, completed, failed
    progress: float  # 0.0 to 1.0
    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None
    result: Optional[dict] = None


class UploadResponse(BaseModel):
    """Response from video upload endpoint."""
    job_id: str
    video_id: str
    message: str
    ws_url: str


class JobListResponse(BaseModel):
    """Response from list jobs endpoint."""
    jobs: List[AnalysisJob]
    total: int


class AnalysisRequest(BaseModel):
    """Request body for analyze endpoint."""
    video_path: str


class VideoInfo(BaseModel):
    """Video metadata response."""
    path: str
    fps: float
    total_frames: int
    duration_seconds: float
    width: int
    height: int
    sample_interval: int
    frames_per_second_sampled: int


class ConfigResponse(BaseModel):
    """Configuration response."""
    vlm_model: str
    frames_per_second: int
    sample_interval: int
    vehicle_classes: dict
    mongodb_connected: bool


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    version: str


class BehaviorObservationResponse(BaseModel):
    """Single behavior observation."""
    behavior_type: str
    vehicle_id: str
    confidence: str
    evidence: str
    risk_level: str
    description: str


class AnalysisResultResponse(BaseModel):
    """Analysis result response."""
    video_id: str
    total_seconds: int
    analyzed_seconds: int
    avg_risk_score: float
    max_risk_score: int
    critical_observations: List[dict]
    analysis_timestamp: str


class EnhancedReportResponse(BaseModel):
    """Enhanced documentation-style report response."""
    report_type: str
    video_id: str
    generated_at: str
    content: str
    sections: Optional[dict] = None
    metadata: Optional[dict] = None
    success: bool
    error: Optional[str] = None


# ============ Streaming Models ============

class StreamStartRequest(BaseModel):
    """Request to start a stream."""
    url: str
    stream_name: Optional[str] = None
    quality: Optional[str] = "720p"


class StreamStartResponse(BaseModel):
    """Response from stream start."""
    stream_id: str
    url: str
    title: str
    is_live: bool
    resolution: str
    fps: float
    ws_url: str
    message: str


class StreamStopRequest(BaseModel):
    """Request to stop a stream."""
    stream_id: str


class StreamStatusResponse(BaseModel):
    """Stream status response."""
    stream_id: str
    state: str
    created_at: str
    batch_count: int
    total_frames: int
    error: Optional[str] = None
    stream_info: Optional[dict] = None


# ============ WebSocket Manager ============

class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, job_id: str):
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, job_id: str):
        if job_id in self.active_connections:
            if websocket in self.active_connections[job_id]:
                self.active_connections[job_id].remove(websocket)
    
    async def broadcast(self, job_id: str, message: dict):
        if job_id in self.active_connections:
            for connection in self.active_connections[job_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass


class DeviceConnectionManager:
    """Manages WebSocket connections for mobile devices."""
    
    def __init__(self):
        self.device_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, device_id: str):
        await websocket.accept()
        self.device_connections[device_id] = websocket
        logger.info(f"Device {device_id} connected via WebSocket")
    
    def disconnect(self, device_id: str):
        if device_id in self.device_connections:
            del self.device_connections[device_id]
            logger.info(f"Device {device_id} disconnected")
    
    async def send_command(self, device_id: str, command: dict) -> bool:
        """Send command to specific device."""
        if device_id in self.device_connections:
            try:
                await self.device_connections[device_id].send_json(command)
                logger.info(f"Command sent to device {device_id}: {command.get('command')}")
                return True
            except Exception as e:
                logger.error(f"Failed to send command to device {device_id}: {e}")
                return False
        else:
            logger.warning(f"Device {device_id} not connected")
            return False
    
    async def broadcast(self, device_id: str, message: dict):
        """Broadcast message to specific device (alias for send_command for compatibility)."""
        if device_id in self.device_connections:
            try:
                await self.device_connections[device_id].send_json(message)
                logger.info(f"📤 Message broadcast to device {device_id}: {message.get('type')}")
            except Exception as e:
                logger.error(f"Failed to broadcast to device {device_id}: {e}")
                raise
        else:
            logger.warning(f"Device {device_id} not connected for broadcast")
            raise Exception(f"Device {device_id} not connected")
    
    def is_connected(self, device_id: str) -> bool:
        """Check if device is connected."""
        return device_id in self.device_connections


manager = ConnectionManager()
device_manager = DeviceConnectionManager()


# ============ Analysis Engine ============

class AnalysisEngine:
    """Handles video analysis with progress tracking."""
    
    def __init__(self):
        self.mongodb: Optional[MongoDBHandler] = None
        self._init_mongodb()
        
        # Initialize streaming components
        from stream_processor import StreamManager
        from stream_analyzer import StreamAnalyzer
        from config import Config
        
        self.stream_manager = StreamManager(max_concurrent=Config.STREAM_MAX_CONCURRENT)
        self.stream_analyzer = StreamAnalyzer(
            stream_manager=self.stream_manager,
            mongodb=self.mongodb,
            use_mongodb=True
        )
        logger.info("Streaming components initialized")
    
    def _init_mongodb(self):
        """Try to connect to MongoDB."""
        try:
            self.mongodb = MongoDBHandler()
            self.mongodb.connect()
            logger.info("MongoDB connected")
        except Exception as e:
            logger.warning(f"MongoDB not available: {e}")
            self.mongodb = None
    
    async def run_analysis(
        self,
        job_id: str,
        video_path: str,
        video_id: str
    ):
        """
        Run full video analysis pipeline with progress updates.
        """
        try:
            # Update job status
            analysis_jobs[job_id]["status"] = "processing"
            await manager.broadcast(job_id, {
                "type": "status",
                "status": "processing",
                "progress": 0.0,
                "message": "Initializing..."
            })
            
            # Initialize frame sampler
            sampler = FrameSampler(video_path)
            video_info = sampler.get_video_info()
            total_seconds = int(video_info["duration_seconds"])
            
            await manager.broadcast(job_id, {
                "type": "progress",
                "progress": 0.05,
                "message": f"Video loaded: {total_seconds} seconds"
            })
            
            # Extract all frame batches
            frame_batches = list(sampler.sample_frames())
            total_batches = len(frame_batches)
            
            await manager.broadcast(job_id, {
                "type": "progress",
                "progress": 0.1,
                "message": f"Extracted {total_batches} second-intervals"
            })
            
            # Run YOLO detection
            from video_analyzer import YOLODetector
            detector = YOLODetector()
            detector.load_model()
            
            yolo_detections = {}
            for i, batch in enumerate(frame_batches):
                for frame_data in batch:
                    dets = detector.detect_in_frame(frame_data.image_data)
                    yolo_detections[frame_data.frame_number] = dets
                    
                    # Store in MongoDB
                    if self.mongodb:
                        self.mongodb.store_detection(
                            video_id,
                            frame_data.frame_number,
                            dets
                        )
                
                progress = 0.1 + (0.3 * (i + 1) / total_batches)
                await manager.broadcast(job_id, {
                    "type": "progress",
                    "progress": progress,
                    "message": f"YOLO detection: {i + 1}/{total_batches}"
                })
                analysis_jobs[job_id]["progress"] = progress
            
            # Run VLM analysis
            vlm_client = VLMClient()
            analyzer = BehaviorAnalyzer(vlm_client)
            
            # Import video processor for frame previews
            from video_processor import VideoProcessor
            
            # Parallel VLM analysis configuration
            MAX_CONCURRENT_VLM = Config.VLM_MAX_CONCURRENT  # Max concurrent VLM API calls
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_VLM)
            
            # Track completed analyses for progress updates
            completed_count = [0]  # Use list to allow modification in nested function
            analyses = [None] * len(frame_batches)
            
            async def analyze_batch_with_preview(batch: list, batch_idx: int):
                """Analyze a single batch with frame preview and progress tracking."""
                async with semaphore:
                    # Send frame preview before analysis
                    if batch:
                        first_frame = batch[0]
                        frame_dets = yolo_detections.get(first_frame.frame_number, [])
                        
                        try:
                            # Create annotated frame preview
                            processor = VideoProcessor(video_path)
                            annotated_frame, _ = processor.get_annotated_frame(
                                first_frame.frame_number,
                                frame_dets
                            )
                            frame_b64 = processor.frame_to_base64(annotated_frame, quality=60)
                            processor.close()
                            
                            await manager.broadcast(job_id, {
                                "type": "frame_preview",
                                "second": batch_idx,
                                "frame": frame_b64,
                                "detections": len(frame_dets),
                                "message": f"Analyzing second {batch_idx + 1}..."
                            })
                        except Exception as e:
                            logger.debug(f"Frame preview failed: {e}")
                    
                    # Run VLM analysis
                    analysis = await analyzer.analyze_second(
                        batch,
                        yolo_detections,
                        batch_idx
                    )
                    
                    # Store in MongoDB
                    if self.mongodb and analysis.success:
                        self.mongodb.store_analysis(
                            video_id,
                            analysis.second_index,
                            analysis.to_dict(),
                            analysis.frame_numbers
                        )
                    
                    # Update progress
                    completed_count[0] += 1
                    progress = 0.4 + (0.55 * completed_count[0] / total_batches)
                    analysis_jobs[job_id]["progress"] = progress
                    
                    await manager.broadcast(job_id, {
                        "type": "progress",
                        "progress": progress,
                        "message": f"VLM analysis: {completed_count[0]}/{total_batches} (parallel)"
                    })
                    
                    return batch_idx, analysis
            
            # Run all analyses in parallel with semaphore limiting concurrency
            await manager.broadcast(job_id, {
                "type": "progress",
                "progress": 0.4,
                "message": f"Starting parallel VLM analysis ({MAX_CONCURRENT_VLM} concurrent)..."
            })
            
            # Create all analysis tasks
            tasks = [
                analyze_batch_with_preview(batch, idx)
                for idx, batch in enumerate(frame_batches)
            ]
            
            # Execute in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect results in order
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Parallel analysis failed: {result}")
                    continue
                batch_idx, analysis = result
                analyses[batch_idx] = analysis
            
            # Filter out None values (failed analyses)
            analyses = [a for a in analyses if a is not None]
            
            # Create summary
            summary = analyzer.create_video_summary(
                video_id,
                analyses,
                total_seconds
            )
            
            # Store classical result
            analysis_jobs[job_id]["result"] = summary.to_dict()
            
            # Generate enhanced report
            await manager.broadcast(job_id, {
                "type": "progress",
                "progress": 0.96,
                "message": "Generating enhanced documentation report..."
            })
            
            try:
                report_generator = ReportGenerator(
                    mongodb_handler=self.mongodb
                )
                
                enhanced_report = await report_generator.generate_enhanced_report(
                    vlm_analysis=summary.to_dict(),
                    video_metadata={
                        "video_id": video_id,
                        "total_seconds": total_seconds,
                        "analyzed_seconds": len(analyses),
                        "analysis_timestamp": datetime.now(timezone.utc).isoformat()
                    }
                )
                
                # Store enhanced report in DB
                if self.mongodb and enhanced_report.success:
                    self.mongodb.store_enhanced_report(
                        video_id,
                        enhanced_report.to_dict()
                    )
                
                # Add to job result
                analysis_jobs[job_id]["enhanced_report"] = enhanced_report.to_dict()
                
                logger.info(f"Enhanced report generated in {enhanced_report.generation_time_ms}ms")
                logger.info(f"Risk scores - Max: {summary.max_risk_score}, Avg: {summary.avg_risk_score}, Critical obs: {len(summary.critical_observations)}")
                
                # Trigger incident orchestrator for SMS notifications
                # Lowered threshold to 5 to catch more incidents
                if enhanced_report.success and (summary.max_risk_score >= 5 or len(summary.critical_observations) > 0):
                    try:
                        logger.info(f"Triggering SMS notification - Risk score: {summary.max_risk_score}, Critical observations: {len(summary.critical_observations)}")
                        from agent.routes import get_orchestrator
                        from agent.models import IncidentCreateRequest, VLMSummary, EnhancedReportData, Location
                        
                        orchestrator = get_orchestrator()
                        
                        # Create VLM summary from analysis
                        vlm_summary = VLMSummary(
                            confidence=min(summary.max_risk_score / 10.0, 1.0),
                            incident_type="Traffic Safety Violation",
                            description=f"Detected {len(summary.critical_observations)} critical observations with max risk score {summary.max_risk_score}",
                            vehicles_involved=len(set(obs.vehicle_id if hasattr(obs, 'vehicle_id') else 'unknown' for obs in summary.critical_observations)),
                            recommended_alerts=["sms"],
                            ambiguous=False,
                            raw_analysis=summary.to_dict()
                        )
                        
                        # Create enhanced report data
                        enhanced_report_data = EnhancedReportData(
                            report_text=enhanced_report.content,
                            risk_score=min(10, max(1, int(summary.max_risk_score))),
                            executive_summary=enhanced_report.executive_summary or enhanced_report.content[:200],
                            evidence_mapping={
                                "critical_observations": [
                                    {
                                        "behavior_type": obs.behavior_type if hasattr(obs, 'behavior_type') else 'unknown',
                                        "vehicle_id": obs.vehicle_id if hasattr(obs, 'vehicle_id') else 'unknown',
                                        "risk_level": obs.risk_level if hasattr(obs, 'risk_level') else 'unknown',
                                        "description": obs.description if hasattr(obs, 'description') else ''
                                    }
                                    for obs in summary.critical_observations
                                ]
                            }
                        )
                        
                        # Create location (optional, can be None)
                        location = None  # Could extract from video metadata if available
                        
                        # Create incident data for orchestrator
                        import uuid
                        incident_data = {
                            'incident_id': str(uuid.uuid4()),
                            'vlm_summary': vlm_summary.dict(),
                            'enhanced_report': enhanced_report_data.dict(),
                            'location': location,
                            'history': []
                        }
                        
                        # Create incident (this will trigger SMS via orchestrator)
                        incident_result = await orchestrator.process_incident_async(incident_data)
                        incident_id = incident_result.get('action_result', {}).get('incident_id', 'unknown')
                        logger.info(f"✅ Incident created: {incident_id} - SMS notifications triggered")
                        
                        # Store incident ID in job
                        analysis_jobs[job_id]["incident_id"] = incident_id
                        
                    except Exception as e:
                        logger.error(f"❌ Failed to create incident for SMS notification: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        # Don't fail the job if incident creation fails
                else:
                    logger.info(f"Skipping SMS notification - Risk score {summary.max_risk_score} below threshold (5) and no critical observations")
                
                await report_generator.close()
                
            except Exception as e:
                logger.warning(f"Enhanced report generation failed: {e}")
                analysis_jobs[job_id]["enhanced_report"] = {
                    "success": False,
                    "error": str(e)
                }
            
            # Update job as completed
            analysis_jobs[job_id]["status"] = "completed"
            analysis_jobs[job_id]["progress"] = 1.0
            analysis_jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
            
            await manager.broadcast(job_id, {
                "type": "completed",
                "progress": 1.0,
                "message": "Analysis complete",
                "result": summary.to_dict(),
                "has_enhanced_report": analysis_jobs[job_id].get("enhanced_report", {}).get("success", False)
            })
            
            # Cleanup
            sampler.close()
            
        except Exception as e:
            logger.exception("Analysis failed")
            analysis_jobs[job_id]["status"] = "failed"
            analysis_jobs[job_id]["error"] = str(e)
            
            await manager.broadcast(job_id, {
                "type": "error",
                "message": str(e)
            })


engine = AnalysisEngine()


# ============ FastAPI App ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Video Analysis API Server...")
    # Initialize orchestrator with device manager
    from agent.routes import init_orchestrator
    init_orchestrator(device_manager=device_manager)
    yield
    logger.info("Shutting down...")
    if engine.mongodb:
        engine.mongodb.close()


app = FastAPI(
    title="Video Behavior Analysis API",
    description="API for analyzing driving behavior in videos using VLM",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include agent router for incident orchestration endpoints
app.include_router(agent_router)


# ============ Endpoints ============

@app.get("/health")
async def health_check():
    """Health check endpoint for mobile app."""
    return {
        "status": "healthy",
        "service": "BI3 Smart Traffic Safety API",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/", response_model=HealthResponse)
async def root():
    """Health check endpoint."""
    return HealthResponse(
        status="running",
        service="Video Behavior Analysis API",
        version="1.0.0"
    )


@app.get("/api/config", response_model=ConfigResponse)
async def get_config():
    """Get current configuration (non-sensitive)."""
    return ConfigResponse(
        vlm_model=Config.VLM_MODEL,
        frames_per_second=Config.FRAMES_PER_SECOND,
        sample_interval=Config.SAMPLE_INTERVAL,
        vehicle_classes=Config.CLASS_NAMES,
        mongodb_connected=engine.mongodb is not None
    )


@app.post("/api/upload", response_model=UploadResponse)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Upload a video file and start analysis.
    
    Returns job_id for tracking progress.
    """
    # Validate file
    if not file.filename:
        raise HTTPException(400, "No filename provided")
    
    allowed_extensions = {".mp4", ".avi", ".mov", ".mkv"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(400, f"Invalid file type. Allowed: {allowed_extensions}")
    
    # Save uploaded file
    job_id = str(uuid.uuid4())[:8]
    video_id = f"vid_{job_id}"
    filename = f"{job_id}{ext}"
    filepath = UPLOAD_DIR / filename
    
    try:
        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(500, f"Failed to save file: {e}")
    
    # Create job entry
    analysis_jobs[job_id] = {
        "job_id": job_id,
        "video_id": video_id,
        "video_name": file.filename,
        "video_path": str(filepath),
        "status": "pending",
        "progress": 0.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "error": None,
        "result": None
    }
    
    # Start analysis in background
    background_tasks.add_task(
        engine.run_analysis,
        job_id,
        str(filepath),
        video_id
    )
    
    return UploadResponse(
        job_id=job_id,
        video_id=video_id,
        message="Upload successful. Analysis started.",
        ws_url=f"/ws/{job_id}"
    )


@app.post("/api/analyze", response_model=UploadResponse)
async def analyze_existing_video(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks
):
    """
    Start analysis on an existing video file.
    """
    video_path = Path(request.video_path)
    if not video_path.exists():
        raise HTTPException(404, f"Video not found: {video_path}")
    
    job_id = str(uuid.uuid4())[:8]
    video_id = f"vid_{job_id}"
    
    # Create job entry
    analysis_jobs[job_id] = {
        "job_id": job_id,
        "video_id": video_id,
        "video_name": video_path.name,
        "video_path": str(video_path),
        "status": "pending",
        "progress": 0.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "error": None,
        "result": None
    }
    
    # Start analysis in background
    background_tasks.add_task(
        engine.run_analysis,
        job_id,
        str(video_path),
        video_id
    )
    
    return UploadResponse(
        job_id=job_id,
        video_id=video_id,
        message="Analysis started.",
        ws_url=f"/ws/{job_id}"
    )


@app.get("/api/jobs", response_model=JobListResponse)
async def list_jobs():
    """List all analysis jobs."""
    return JobListResponse(
        jobs=[AnalysisJob(**job) for job in analysis_jobs.values()],
        total=len(analysis_jobs)
    )


@app.get("/api/jobs/{job_id}", response_model=AnalysisJob)
async def get_job(job_id: str):
    """Get status of a specific job."""
    if job_id not in analysis_jobs:
        raise HTTPException(404, f"Job not found: {job_id}")
    
    return AnalysisJob(**analysis_jobs[job_id])


@app.get("/api/jobs/{job_id}/result", response_model=AnalysisResultResponse)
async def get_job_result(job_id: str):
    """Get analysis result for a completed job."""
    if job_id not in analysis_jobs:
        raise HTTPException(404, f"Job not found: {job_id}")
    
    job = analysis_jobs[job_id]
    
    if job["status"] != "completed":
        raise HTTPException(400, f"Job not completed. Status: {job['status']}")
    
    return AnalysisResultResponse(**job["result"])


@app.get("/api/jobs/{job_id}/enhanced-report", response_model=EnhancedReportResponse)
async def get_enhanced_report(job_id: str):
    """
    Get enhanced documentation-style report for a completed job.
    
    Returns the police-ready detailed incident documentation.
    """
    if job_id not in analysis_jobs:
        raise HTTPException(404, f"Job not found: {job_id}")
    
    job = analysis_jobs[job_id]
    
    if job["status"] != "completed":
        raise HTTPException(400, f"Job not completed. Status: {job['status']}")
    
    # Check if enhanced report exists in job
    enhanced_report = job.get("enhanced_report")
    if enhanced_report:
        # Check if it's a failed report (missing required fields)
        if not enhanced_report.get("success", False):
            error_msg = enhanced_report.get("error", "Enhanced report generation failed")
            raise HTTPException(503, f"Enhanced report not available: {error_msg}")
        
        # Ensure all required fields are present
        if all(k in enhanced_report for k in ["report_type", "video_id", "generated_at", "content"]):
            return EnhancedReportResponse(**enhanced_report)
    
    # Try to fetch from MongoDB
    if engine.mongodb:
        video_id = job.get("video_id")
        stored_report = engine.mongodb.get_enhanced_report(video_id)
        if stored_report and stored_report.get("success", False):
            return EnhancedReportResponse(**stored_report)
    
    raise HTTPException(404, "Enhanced report not available for this job")


@app.get("/api/video-info")
async def get_video_info(path: str):
    """Get metadata for a video file."""
    video_path = Path(path)
    if not video_path.exists():
        raise HTTPException(404, f"Video not found: {path}")
    
    try:
        sampler = FrameSampler(str(video_path))
        info = sampler.get_video_info()
        sampler.close()
        return info
    except Exception as e:
        raise HTTPException(500, f"Failed to read video: {e}")


# Processed video directory
PROCESSED_DIR = Path("processed")
PROCESSED_DIR.mkdir(exist_ok=True)


@app.get("/api/jobs/{job_id}/video")
async def get_processed_video(job_id: str):
    """
    Get YOLO-annotated processed video for a job.
    Generates the video if not already processed.
    """
    if job_id not in analysis_jobs:
        raise HTTPException(404, f"Job not found: {job_id}")
    
    job = analysis_jobs[job_id]
    video_path = job.get("video_path")
    
    if not video_path or not Path(video_path).exists():
        raise HTTPException(404, "Original video not found")
    
    # Check if processed video exists
    processed_path = PROCESSED_DIR / f"{job_id}_annotated.mp4"
    
    if not processed_path.exists():
        # Generate processed video
        try:
            from video_processor import VideoProcessor
            processor = VideoProcessor(video_path, str(PROCESSED_DIR))
            processor.process_video(output_name=f"{job_id}_annotated")
            processor.close()
        except Exception as e:
            raise HTTPException(500, f"Failed to process video: {e}")
    
    return FileResponse(
        processed_path,
        media_type="video/mp4",
        filename=f"{job_id}_annotated.mp4"
    )


@app.get("/api/jobs/{job_id}/frame/{second}")
async def get_frame_preview(job_id: str, second: int):
    """
    Get an annotated frame preview for a specific second.
    
    Returns base64-encoded JPEG image.
    """
    if job_id not in analysis_jobs:
        raise HTTPException(404, f"Job not found: {job_id}")
    
    job = analysis_jobs[job_id]
    video_path = job.get("video_path")
    
    if not video_path or not Path(video_path).exists():
        raise HTTPException(404, "Original video not found")
    
    try:
        from video_processor import VideoProcessor
        
        # Calculate frame number (3 frames per second, use middle frame)
        sampler = FrameSampler(video_path)
        fps = sampler.fps
        frame_number = int(second * fps + fps / 2)
        sampler.close()
        
        processor = VideoProcessor(video_path)
        annotated_frame, detections = processor.get_annotated_frame(frame_number)
        frame_b64 = processor.frame_to_base64(annotated_frame, quality=80)
        processor.close()
        
        return {
            "second": second,
            "frame": frame_b64,
            "detections": detections,
            "frame_number": frame_number
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to get frame: {e}")


# ============ Streaming Endpoints ============

@app.post("/api/stream/start", response_model=StreamStartResponse)
async def start_stream(request: StreamStartRequest):
    """
    Start processing a live stream or YouTube video.
    
    Uses continuous real-time processing with YOLO at 30fps and VLM every 3 seconds.
    """
    # Generate stream ID
    stream_id = f"stream_{str(uuid.uuid4())[:8]}"
    
    # Event callback for WebSocket broadcasting
    async def event_callback(event: dict):
        """
        Broadcast events to WebSocket clients.
        The new continuous stream analyzer already sends annotated frames.
        """
        # Broadcast to WebSocket connections
        await manager.broadcast(stream_id, event)
    
    try:
        # Start stream analysis with continuous real-time processing
        result = await engine.stream_analyzer.start_analysis(
            stream_id=stream_id,
            url=request.url,
            quality=request.quality or "720p",
            event_callback=event_callback
        )
        
        return StreamStartResponse(
            stream_id=result['stream_id'],
            url=result['url'],
            title=result['title'],
            is_live=result['is_live'],
            resolution=result['resolution'],
            fps=result['fps'],
            ws_url=f"/ws/stream/{stream_id}",
            message="Stream started. Connect to WebSocket for real-time updates."
        )
        
    except Exception as e:
        logger.error(f"Failed to start stream: {e}")
        raise HTTPException(500, f"Failed to start stream: {str(e)}")


@app.post("/api/stream/stop")
async def stop_stream(request: StreamStopRequest):
    """Stop a running stream."""
    try:
        result = await engine.stream_analyzer.stop_analysis(request.stream_id)
        return {
            "stream_id": request.stream_id,
            "message": "Stream stopped",
            "final_stats": result
        }
    except Exception as e:
        logger.error(f"Failed to stop stream: {e}")
        raise HTTPException(500, f"Failed to stop stream: {str(e)}")


@app.get("/api/stream/status/{stream_id}", response_model=StreamStatusResponse)
async def get_stream_status(stream_id: str):
    """Get current stream status."""
    status = engine.stream_manager.get_status(stream_id)
    
    if not status:
        raise HTTPException(404, f"Stream not found: {stream_id}")
    
    return StreamStatusResponse(**status)


@app.get("/api/stream/live-yolo/{stream_id}")
async def get_live_yolo_frame(stream_id: str):
    """
    Get latest YOLO-annotated frame from stream.
    
    Returns base64-encoded JPEG image.
    """
    # This will be populated by the event_callback during stream processing
    # For now, return a placeholder response
    return {
        "stream_id": stream_id,
        "message": "Subscribe to WebSocket for real-time YOLO frames",
        "ws_url": f"/ws/stream/{stream_id}"
    }


@app.get("/api/stream/live-vlm/{stream_id}")
async def get_live_vlm_summary(stream_id: str):
    """
    Get latest VLM behavioral summary from stream.
    """
    # Check if stream exists
    status = engine.stream_manager.get_status(stream_id)
    if not status:
        raise HTTPException(404, f"Stream not found: {stream_id}")
    
    # Try to get latest batch from MongoDB
    if engine.mongodb:
        try:
            latest_batch = engine.mongodb.db['stream_batches'].find_one(
                {'stream_id': stream_id},
                sort=[('batch_index', -1)]
            )
            
            if latest_batch:
                return {
                    "stream_id": stream_id,
                    "batch_index": latest_batch['batch_index'],
                    "vlm_analyses": latest_batch['vlm_analyses'],
                    "avg_risk_score": latest_batch['avg_risk_score'],
                    "timestamp": latest_batch['timestamp'].isoformat() + 'Z'
                }
        except Exception as e:
            logger.error(f"Failed to fetch VLM summary: {e}")
    
    return {
        "stream_id": stream_id,
        "message": "No VLM summaries available yet. Subscribe to WebSocket for real-time updates.",
        "ws_url": f"/ws/stream/{stream_id}"
    }


@app.get("/api/stream/live-reports/{stream_id}")
async def get_live_reports(stream_id: str):
    """
    Get all enhanced reports generated during streaming.
    """
    # Check if stream exists
    status = engine.stream_manager.get_status(stream_id)
    if not status:
        raise HTTPException(404, f"Stream not found: {stream_id}")
    
    # Get all batches with reports
    if engine.mongodb:
        try:
            batches = list(engine.mongodb.db['stream_batches'].find(
                {'stream_id': stream_id, 'enhanced_reports': {'$ne': []}},
                sort=[('batch_index', 1)]
            ))
            
            all_reports = []
            for batch in batches:
                for report in batch.get('enhanced_reports', []):
                    report['batch_index'] = batch['batch_index']
                    all_reports.append(report)
            
            return {
                "stream_id": stream_id,
                "total_reports": len(all_reports),
                "reports": all_reports
            }
        except Exception as e:
            logger.error(f"Failed to fetch reports: {e}")
    
    return {
        "stream_id": stream_id,
        "total_reports": 0,
        "reports": [],
        "message": "Subscribe to WebSocket for real-time report notifications."
    }


@app.get("/api/stream/list")
async def list_streams():
    """List all active streams."""
    streams = engine.stream_manager.list_streams()
    return {
        "total": len(streams),
        "streams": streams
    }


# ============ WebSocket Endpoint ============

@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time analysis progress.
    
    Connect to receive live updates during video analysis.
    """
    # Check if this is a device ID (UUID format) or job ID
    if len(job_id) == 36 and job_id.count('-') == 4:  # Looks like a UUID (device_id)
        # This is a device connection
        await device_manager.connect(websocket, job_id)
        
        try:
            # Keep connection alive and handle messages
            while True:
                try:
                    data = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=60.0
                    )
                    import json
                    message = json.loads(data)
                    
                    # Handle different message types
                    msg_type = message.get('type')
                    if msg_type == 'connect':
                        await websocket.send_json({
                            "type": "connected",
                            "device_id": job_id,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                    elif msg_type == 'heartbeat':
                        await websocket.send_json({"type": "pong"})
                    elif msg_type == 'ack':
                        logger.info(f"Device {job_id} acknowledged message: {message}")
                        
                except asyncio.TimeoutError:
                    # Send keepalive
                    await websocket.send_json({"type": "keepalive"})
                    
        except WebSocketDisconnect:
            device_manager.disconnect(job_id)
            logger.info(f"Device {job_id} disconnected")
    else:
        # This is a job/analysis connection (original behavior)
        await manager.connect(websocket, job_id)
        
        try:
            # Send current status if job exists
            if job_id in analysis_jobs:
                await websocket.send_json({
                    "type": "status",
                    "status": analysis_jobs[job_id]["status"],
                    "progress": analysis_jobs[job_id]["progress"]
                })
            
            # Keep connection alive
            while True:
                try:
                    data = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=30.0
                    )
                    # Handle ping
                    if data == "ping":
                        await websocket.send_json({"type": "pong"})
                except asyncio.TimeoutError:
                    # Send keepalive
                    await websocket.send_json({"type": "keepalive"})
                    
        except WebSocketDisconnect:
            manager.disconnect(websocket, job_id)


# ============ Run Server ============

def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the FastAPI server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
