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


manager = ConnectionManager()


# ============ Analysis Engine ============

class AnalysisEngine:
    """Handles video analysis with progress tracking."""
    
    def __init__(self):
        self.mongodb: Optional[MongoDBHandler] = None
        self._init_mongodb()
    
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
                
                await report_generator.close()
                
                logger.info(f"Enhanced report generated in {enhanced_report.generation_time_ms}ms")
                
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

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Endpoints ============

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


# ============ WebSocket Endpoint ============

@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time analysis progress.
    
    Connect to receive live updates during video analysis.
    """
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
