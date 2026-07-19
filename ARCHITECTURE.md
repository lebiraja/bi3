# BI3 Smart Traffic Safety — Architecture & Documentation

---

## Table of Contents

1. [System Overview](#system-overview)
2. [High-Level Architecture Diagram](#high-level-architecture-diagram)
3. [Component Map](#component-map)
4. [Data Flow Diagrams](#data-flow-diagrams)
   - [Video File Analysis Flow](#video-file-analysis-flow)
   - [Live Stream Analysis Flow](#live-stream-analysis-flow)
   - [Incident Orchestration Flow](#incident-orchestration-flow)
   - [WebSocket Broadcast Flow](#websocket-broadcast-flow)
5. [Module Reference](#module-reference)
6. [Agent Subsystem](#agent-subsystem)
7. [Configuration Reference](#configuration-reference)
8. [API Reference](#api-reference)

---

## System Overview

**BI3** is a real-time smart traffic safety platform that ingests live video streams or uploaded
video files, detects vehicles using YOLO, analyzes driver behavior using Vision-Language Models
(VLMs), generates structured incident reports, and dispatches emergency alerts (SMS / GSM calls /
push notifications) when risk thresholds are exceeded.

**Technology Stack:**

| Layer           | Technology                                      |
|-----------------|-------------------------------------------------|
| API Server      | FastAPI (Python 3.11+)                          |
| Object Detection| YOLO11 (Ultralytics) + ByteTrack               |
| Vision-Language | Qwen3-VL-8B via OpenRouter OR Gemma3 via Ollama |
| Report LLM      | Gemma3:1B via Ollama (local)                    |
| Orchestration   | LangGraph + Langchain (ChatOllama)              |
| Storage         | MongoDB                                         |
| Stream Ingestion | yt-dlp + OpenCV                                |
| Frontend        | React + TypeScript + Vite + Tailwind            |
| Mobile App      | Flutter (Android/iOS)                           |

---

## High-Level Architecture Diagram

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                        BI3 SMART TRAFFIC SAFETY PLATFORM                        ║
╠══════════════════════════════════════════════════════════════════════════════════╣
║                                                                                  ║
║  ┌─────────────────────┐          ┌─────────────────────────────────────────┐   ║
║  │     INPUT SOURCES   │          │            FRONTEND CLIENTS             │   ║
║  │                     │          │                                         │   ║
║  │  ┌───────────────┐  │          │  ┌──────────────┐  ┌─────────────────┐ │   ║
║  │  │  Video Files  │  │          │  │ React Web UI │  │  Flutter Mobile │ │   ║
║  │  │  (.mp4 etc.)  │  │          │  │   (Vite/TS)  │  │  App (Android/  │ │   ║
║  │  └───────┬───────┘  │          │  │              │  │   iOS/Web)      │ │   ║
║  │          │           │          │  └──────┬───────┘  └────────┬────────┘ │   ║
║  │  ┌───────────────┐  │          └─────────┼──────────────────┼──────────-┘   ║
║  │  │  YouTube /    │  │                    │  REST / WS        │  REST / WS    ║
║  │  │  RTSP / HLS   │  │                    │                   │               ║
║  │  │  Live Streams │  │                    ▼                   ▼               ║
║  │  └───────┬───────┘  │    ╔═══════════════════════════════════════════════╗   ║
║  └──────────┼──────────┘    ║             FASTAPI SERVER  (server.py)       ║   ║
║             │                ║                                               ║   ║
║             │  HTTP POST     ║  REST Endpoints:  WebSocket Endpoints:        ║   ║
║             │  /api/stream   ║  /api/upload      /ws/{job_id}                ║   ║
║             └───────────────►║  /api/analyze     /ws/stream/{stream_id}      ║   ║
║                              ║  /api/jobs/*      /v1/incidents (agent)       ║   ║
║                              ║  /api/stream/*    /v1/devices                 ║   ║
║                              ╚════════════════════╤══════════════════════════╝   ║
║                                                   │                              ║
║             ┌─────────────────────────────────────┼────────────────────────┐    ║
║             │                                     │                        │    ║
║             ▼                                     ▼                        ▼    ║
║  ┌──────────────────────┐          ┌──────────────────────┐   ┌──────────────┐ ║
║  │   VIDEO PIPELINE     │          │   STREAM PIPELINE    │   │   INCIDENT   │ ║
║  │   (file analysis)    │          │   (live / YouTube)   │   │   AGENT      │ ║
║  │                      │          │                      │   │              │ ║
║  │  FrameSampler        │          │  StreamProcessor     │   │  LangGraph   │ ║
║  │  (3 fps sampling)    │          │  (yt-dlp + OpenCV)   │   │  Orchestrator│ ║
║  │         │            │          │         │            │   │              │ ║
║  │         ▼            │          │         ▼            │   │  PolicyEngine│ ║
║  │  YOLO Detection      │          │  ContinuousYOLO      │   │              │ ║
║  │  (frame-by-frame)    │          │  (GPU thread)        │   │  ActionExec  │ ║
║  │         │            │          │         │            │   │  (SMS/Call/  │ ║
║  │         ▼            │          │         ▼            │   │   Push)      │ ║
║  │  VLMClient           │          │  HybridVLMClient     │   └──────────────┘ ║
║  │  (OpenRouter)        │          │  (Ollama/OpenRouter) │                    ║
║  │         │            │          │         │            │                    ║
║  │         ▼            │          │         ▼            │                    ║
║  │  BehaviorAnalyzer    │          │  StreamAnalyzer      │                    ║
║  │         │            │          │  (RealTime)          │                    ║
║  │         ▼            │          │         │            │                    ║
║  │  ReportGenerator     │          │         │            │                    ║
║  │  (Ollama LLM)        │          │         │            │                    ║
║  └──────────┬───────────┘          └─────────┬────────────┘                    ║
║             │                                │                                  ║
║             └──────────────┬─────────────────┘                                  ║
║                            │                                                     ║
║                            ▼                                                     ║
║              ┌─────────────────────────┐                                        ║
║              │     MongoDB Storage     │                                        ║
║              │  ┌──────────────────┐   │                                        ║
║              │  │ frames           │   │                                        ║
║              │  │ detections       │   │                                        ║
║              │  │ analyses         │   │                                        ║
║              │  └──────────────────┘   │                                        ║
║              └─────────────────────────┘                                        ║
║                                                                                  ║
╚══════════════════════════════════════════════════════════════════════════════════╝
```

---

## Component Map

```
bi3/
├── server.py                  ← FastAPI entry-point; REST + WebSocket routes
├── config.py                  ← Central config (env vars, thresholds, model paths)
│
├── ── VIDEO FILE PIPELINE ────────────────────────────────────────────────────
│
├── frame_sampler.py           ← Reads video, extracts frames at 3 fps (OpenCV)
├── vlm_client.py              ← OpenRouter VLM client (async, multi-key LB)
├── behavior_analyzer.py       ← Parallel VLM calls → BehaviorObservation list
├── report_generator.py        ← Ollama LLM → enhanced documentation report
│
├── ── STREAM PIPELINE ────────────────────────────────────────────────────────
│
├── stream_processor.py        ← yt-dlp URL resolution + OpenCV frame buffer
│   ├── StreamExtractor         → single stream (buffer thread + cv2.VideoCapture)
│   └── StreamManager           → multi-stream lifecycle coordinator
│
├── continuous_yolo.py         ← GPU YOLO11 + ByteTrack in dedicated thread
│   └── ContinuousYOLOProcessor → DetectionResult + AnnotatedFrame queues
│
├── hybrid_vlm_client.py       ← VLM client supporting Ollama AND OpenRouter
│   └── HybridVLMClient         → auto-selects provider, concurrency semaphore
│
├── stream_analyzer.py         ← Real-time coordinator: YOLO + VLM + SMS trigger
│   └── RealTimeStreamAnalyzer  → _yolo_loop / _broadcast_loop / _vlm_loop tasks
│
├── vehicle_tracking.py        ← Standalone YOLO11 + ByteTrack script (utility)
├── video_analyzer.py          ← Offline video analysis helper
├── video_processor.py         ← Video processing utilities
├── vlm_sampler.py             ← VLM sampling utilities
│
├── ── SUPPORT MODULES ────────────────────────────────────────────────────────
│
├── mongodb_handler.py         ← MongoDB CRUD (frames / detections / analyses)
├── ollama_client.py           ← Async Ollama client for report generation LLM
├── system_prompt.py           ← SYSTEM_PROMPT + get_analysis_prompt() factory
│
├── ── AGENT SUBSYSTEM ────────────────────────────────────────────────────────
│
├── agent/
│   ├── __init__.py
│   ├── config.py              ← AgentConfig: thresholds, contacts, retry policy
│   ├── models.py              ← Pydantic schemas: IncidentInput, ActionPlan, etc.
│   ├── policies.py            ← PolicyEngine: risk/confidence gating rules
│   ├── actions.py             ← ActionExecutor: SMS, GSM call, push dispatch
│   ├── orchestrator.py        ← Legacy IncidentOrchestrator (rule-based)
│   ├── langgraph_orchestrator.py ← LangGraph stateful workflow (LLM-enhanced)
│   ├── routes.py              ← FastAPI router: /v1/incidents, /v1/devices, etc.
│   ├── llm_helper.py          ← LLM utility functions
│   └── api_spec.py            ← OpenAPI spec generator for mobile integration
│
├── ── PROMPTS ────────────────────────────────────────────────────────────────
│
├── prompts/
│   ├── __init__.py
│   └── enhanced_report_prompt.py  ← Prompt templates for Ollama report LLM
│
├── ── FRONTENDS ──────────────────────────────────────────────────────────────
│
├── frontend/                  ← React 18 + TypeScript + Vite + Tailwind CSS
│   └── src/                   ← Components, pages, hooks for dashboard
│
└── mobile/                    ← Flutter app (Android / iOS / Web)
    ├── lib/                   ← Dart source: screens, services, models
    ├── android/
    └── ios/
```

---

## Data Flow Diagrams

### Video File Analysis Flow

```
  User                  FastAPI               BackgroundTask          MongoDB
  ──────────────────────────────────────────────────────────────────────────────

  POST /api/upload ──►  Validate file
  (mp4/mov/avi)         Save to /uploads/
                        Create job_id
                        Start BG Task ──────────────────────────────────────►
  ◄─── job_id, ws_url                                                         │
                                                                               │
                                                                               ▼
                                                                    ╔══════════════════╗
                                                                    ║  FrameSampler    ║
                                                                    ║  OpenCV read     ║
                                                                    ║  Extract 1 frame ║
                                                                    ║  every 10 frames ║
                                                                    ║  (3 fps from 30) ║
                                                                    ╚════════╤═════════╝
                                                                             │ FrameData
                                                                             ▼
                                                                    ╔══════════════════╗
                                                                    ║  YOLO Detection  ║
                                                                    ║  yolo11n.pt      ║
                                                                    ║  Classes: car,   ║
                                                                    ║  moto, bus, truck║
                                                                    ║  ByteTrack IDs   ║
                                                                    ╚════════╤═════════╝
                                                                             │ detections[]
                                                                             ▼
                                                                    ╔══════════════════╗
                                                                    ║  BehaviorAnalyzer║
                                                                    ║  Group frames    ║
                                                                    ║  by 1-sec batch  ║
                                                                    ║  ┌────────────┐  ║
                                                                    ║  │VLMClient   │  ║
                                                                    ║  │(OpenRouter)│  ║
                                                                    ║  │Qwen3-VL-8B │  ║
                                                                    ║  │ async pool │  ║
                                                                    ║  └────────────┘  ║
                                                                    ║  → observations  ║
                                                                    ║  → risk_score    ║
                                                                    ╚════════╤═════════╝
                                                                             │ Summary
                                                                             ▼
                                                                    ╔══════════════════╗
                                                                    ║ ReportGenerator  ║
                                                                    ║  OllamaClient    ║
                                                                    ║  gemma3:1b (LLM) ║
                                                                    ║  → enhanced docs ║
                                                                    ║  → risk_score    ║
                                                                    ║  → evidence map  ║
                                                                    ╚════════╤═════════╝
                                                                             │ EnhancedReport
                                                                             ▼
                                                                    MongoDBHandler ──► MongoDB
                                                                    (frames/detections
                                                                    /analyses stored)
                                                                             │
  WebSocket (ws://…/ws/{job_id})                                             │
  ◄─── progress events ─────────────────────────────────────────────────────┘
  ◄─── final result

  GET /api/jobs/{job_id}/result  ──► JSON: observations, risk, summary
  GET /api/jobs/{job_id}/enhanced-report ──► Full Ollama-generated report
```

---

### Live Stream Analysis Flow

```
  Client          FastAPI Server          RealTimeStreamAnalyzer         Services
  ───────────────────────────────────────────────────────────────────────────────

  POST /api/stream/start
  { url, stream_id } ──►
                        StreamManager.create_stream()
                        StreamExtractor init
                              │
                              ├─ yt-dlp resolves HLS/DASH URL
                              ├─ cv2.VideoCapture opens stream
                              └─ _buffer_frames() thread starts
                                       (fills queue 90-frame buffer)
                        ◄── StreamInfo (title, fps, resolution)
  ◄── { stream_id, state:"active" }

  WS /ws/stream/{stream_id} ──► Connect

                        ┌─── asyncio.create_task(_yolo_loop) ─────────────────►
                        │         every frame from buffer
                        │         ContinuousYOLOProcessor._run_inference()
                        │         YOLO11n GPU ~15-25ms/frame
                        │         stores: latest_frame, latest_detections
                        │
                        ├─── asyncio.create_task(_broadcast_loop) ────────────►
                        │         30 FPS target
                        │         encode frame as JPEG base64
                        │         bundle with detections JSON
                        │         ◄── WebSocket push to all subscribers
                        │
                        └─── asyncio.create_task(_vlm_loop) ──────────────────►
                                  every STREAM_VLM_SAMPLE_INTERVAL seconds (3s)
                                  only if vehicle_count >= 2
                                  │
                                  ▼
                             HybridVLMClient.analyze()
                             ┌─── Ollama (local Gemma3:4b)  if VLM_PROVIDER=ollama
                             └─── OpenRouter (Qwen3-VL-8B)  if VLM_PROVIDER=openrouter
                                  │
                                  ▼
                             VLMAnalysisResult
                             { risk_score, observations, summary }
                                  │
                                  ├── risk_score >= 5 ──► Trigger Incident Agent ──►
                                  │                       POST /v1/incidents
                                  │
                                  └── Store in MongoDB (analyses collection)
                                       Broadcast VLM event via WebSocket

  GET /api/stream/live-yolo/{id} ──► Latest annotated frame (JPEG)
  GET /api/stream/live-vlm/{id}  ──► Latest VLM analysis JSON
  GET /api/stream/live-reports/{id} ──► Accumulated report history
  POST /api/stream/stop ──► Graceful shutdown + cleanup
```

---

### Incident Orchestration Flow

```
  Trigger              Routes (/v1/...)      Orchestrator          Actions
  ────────────────────────────────────────────────────────────────────────────

  VLM risk_score >= 5
  OR manual trigger
        │
        ▼
  POST /v1/incidents
  {
    incident_id,
    vlm_summary: {
      confidence,        ─────────────────────────────────────────────────
      incident_type,                                                       │
      recommended_alerts              ╔══════════════════════════╗         │
    },                                ║  LangGraphOrchestrator   ║         │
    enhanced_report: {                ║  (or IncidentOrchestrator)║        │
      risk_score,       ─────────────►║                          ║         │
      report_text                     ║  StateGraph nodes:       ║         │
    },                                ║  ┌─────────────────────┐ ║         │
    location: { lat, lon }            ║  │ 1. assess_risk       │ ║         │
  }                                   ║  │    LLM reasoning     │ ║         │
                                      ║  └──────────┬──────────┘ ║         │
                                      ║             ▼            ║         │
                                      ║  ┌─────────────────────┐ ║         │
                                      ║  │ 2. PolicyEngine      │ ║         │
                                      ║  │ evaluate_gating()   │ ║         │
                                      ║  │                      │ ║         │
                                      ║  │ risk >= 7 ──► AUTO   │ ║         │
                                      ║  │ risk 4-6  ──► QUEUE  │ ║         │
                                      ║  │ risk < 4  ──► LOG    │ ║         │
                                      ║  │ ambiguous ──► ESCALATE│ ║        │
                                      ║  └──────────┬──────────┘ ║         │
                                      ║             ▼            ║         │
                                      ║  ┌─────────────────────┐ ║         │
                                      ║  │ 3. build_action_plan │ ║         │
                                      ║  │ LLM selects targets: │ ║         │
                                      ║  │  ambulance/police/   │ ║         │
                                      ║  │  traffic_control     │ ║         │
                                      ║  └──────────┬──────────┘ ║         │
                                      ║             ▼            ║         │
                                      ║  ┌─────────────────────┐ ║         │
                                      ║  │ 4. ActionExecutor    │ ║         │
                                      ║  │ execute_action_plan()│ ║         │
                                      ╚══╪═════════════════════╪═╝         │
                                         │                     │           │
                              ┌──────────┼─────────────────────┤           │
                              ▼          ▼                     ▼           │
                         ┌─────────┐ ┌──────────┐     ┌───────────────┐   │
                         │  GSM    │ │   SMS    │     │ Push Notify   │   │
                         │  CALL   │ │          │     │ (FCM)         │   │
                         │via mobile│ │via mobile│     │               │   │
                         │ device  │ │ device  │     │               │   │
                         │WebSocket│ │WebSocket│     │               │   │
                         └─────────┘ └──────────┘     └───────────────┘   │
                              │          │                     │           │
                              ▼          ▼                     ▼           │
                         Police        Police/           Operator          │
                         +91-953...    Ambulance         Dashboard         │
                                       +91-636...                          │
                                                                           │
  ◄──── OrchestratorOutput: { action_result, api_spec, audit_trail } ─────┘

  POST /v1/incidents/{id}/override  ──► Manual approve/reject
  POST /v1/devices/register         ──► Register mobile GSM device
  POST /v1/devices/{id}/callback    ──► Receive call state updates
  GET  /v1/incidents/{id}           ──► Retrieve incident state
```

---

### WebSocket Broadcast Flow

```
  Browser / Mobile Client          FastAPI WebSocket Handler
  ──────────────────────────────────────────────────────────────────────────────

  ─── Video Job WebSocket ───────────────────────────────────────────────────────

  WS CONNECT /ws/{job_id} ──────────► ConnectionManager.connect()
                                       Add to ws_connections[job_id][]

  Background analysis task ──────────────────────────────────────────────────►
  running…                             Periodically:
                                       ConnectionManager.broadcast(job_id, {
                                         type: "progress",
                                         progress: 0.0 → 1.0,
                                         batch_results: [...],
                                         stage: "yolo|vlm|report"
                                       })
  ◄──── JSON progress events ─────────

  Analysis complete:
                                       broadcast(job_id, {
                                         type: "completed",
                                         result: { observations, risk_score,
                                                   summary, enhanced_report }
                                       })
  ◄──── Final result JSON ─────────

  WS DISCONNECT ───────────────────►  ConnectionManager.disconnect()


  ─── Live Stream WebSocket ─────────────────────────────────────────────────────

  WS CONNECT /ws/stream/{stream_id} ► Registered as stream subscriber

  _broadcast_loop (async, 30fps): ──────────────────────────────────────────►
                                       WS send({
                                         type: "frame",
                                         frame: "<base64 JPEG>",
                                         detections: [{id, class, bbox, conf}],
                                         vehicle_count: N,
                                         timestamp_ms: T
                                       })
  ◄──── 30fps annotated frames ────

  _vlm_loop triggers: ──────────────────────────────────────────────────────►
                                       WS send({
                                         type: "vlm_update",
                                         risk_score: 0-10,
                                         observations: [...],
                                         summary: "...",
                                         recommended_alerts: [...]
                                       })
  ◄──── VLM analysis events ───────
```

---

## Module Reference

### `server.py` — FastAPI Application

The main application entry-point. Manages two WebSocket connection managers
(`ConnectionManager` for jobs, `DeviceConnectionManager` for mobile devices),
one `VideoAnalysisPipeline` singleton, and a `RealTimeStreamAnalyzer` singleton.

**Key Responsibilities:**
- Upload and validate video files
- Create and track analysis jobs in-memory (`analysis_jobs` dict)
- Serve job status, results, frames, and processed video
- Start/stop live stream sessions
- Mount the agent router at `/v1/...`
- Broadcast progress and results via WebSocket

---

### `config.py` — Configuration

Single-class `Config` with class-level attributes loaded from environment variables.
All thresholds, model names, connection URIs, and rate limits live here.

| Key Setting               | Default                 | Purpose                              |
|---------------------------|-------------------------|--------------------------------------|
| `VLM_MODEL`               | `qwen/qwen3-vl-8b-instruct` | Cloud VLM model                  |
| `OLLAMA_VISION_MODEL`     | `gemma3:4b`             | Local vision model                   |
| `OLLAMA_MODEL`            | `gemma3:1b`             | Local report generation model        |
| `VLM_PROVIDER`            | `auto`                  | `ollama` / `openrouter` / `auto`     |
| `FRAMES_PER_SECOND`       | `3`                     | Sampling rate for file analysis      |
| `STREAM_VLM_SAMPLE_INTERVAL` | `3.0s`               | VLM trigger interval for streams     |
| `STREAM_VLM_MIN_VEHICLES` | `2`                     | Min vehicles before VLM fires        |
| `VLM_MAX_CONCURRENT`      | `15`                    | Semaphore for parallel VLM calls     |
| `MONGODB_URI`             | `mongodb://localhost:27017` | Storage connection               |

---

### `frame_sampler.py` — FrameSampler

Reads video files with OpenCV and yields `FrameData` objects.

```
FrameSampler(video_path)
    .get_video_info()         → { fps, total_frames, duration, width, height }
    .sample_frames()          → Generator[FrameData, ...]
    .get_frames_by_second()   → Dict[int, List[FrameData]]  (1-sec batches)
```

`FrameData` contains: `frame_number`, `timestamp_ms`, `image_data (ndarray)`,
`base64_encoded (str)`, `width`, `height`.

---

### `stream_processor.py` — StreamExtractor / StreamManager

**`StreamExtractor`** resolves a YouTube/RTSP/HLS URL via yt-dlp, opens it with
`cv2.VideoCapture`, and fills a thread-safe `Queue(maxsize=90)` in a daemon thread.

```
StreamExtractor(url, quality="720p")
    .start_stream(stream_id)  → StreamInfo
    .get_frame()              → (frame_no, frame, timestamp_ms) | None  [non-blocking]
    .get_batch_frames(15s)    → List[(frame_no, frame, timestamp_ms)]
    .stop_stream()            → cleanup
```

**`StreamManager`** is a thread-safe registry for up to `STREAM_MAX_CONCURRENT` (3)
simultaneous streams.

---

### `continuous_yolo.py` — ContinuousYOLOProcessor

Loads YOLO11n with optional ByteTrack tracking. Provides `_run_inference(frame)`
returning a list of detection dicts: `{id, class_id, class_name, bbox, confidence, color}`.

GPU-accelerated; expected ~15–25 ms per frame on RTX 4050.

---

### `hybrid_vlm_client.py` — HybridVLMClient

Auto-detects whether to use Ollama (local GPU) or OpenRouter (cloud) based on
`Config.VLM_PROVIDER`. Manages an `asyncio.Semaphore` for concurrency control.

```
HybridVLMClient(provider=None)         # auto-select
    .analyze_frame(base64, detections) → VisionAnalysisResult
    .analyze_frames_batch(frames[])    → List[VisionAnalysisResult]
```

`VisionAnalysisResult`: `success`, `content`, `parsed_json` (structured JSON),
`processing_time_ms`, `provider`, `model`.

---

### `vlm_client.py` — VLMClient

OpenRouter-only async VLM client. Supports multiple API keys with round-robin
load balancing and per-key concurrency semaphores.

---

### `behavior_analyzer.py` — BehaviorAnalyzer

Groups `FrameData` into 1-second intervals and fires parallel VLM requests
(up to `VLM_MAX_CONCURRENT`). Aggregates `BehaviorObservation` lists into a
`VideoAnalysisSummary`.

```
BehaviorObservation:
  behavior_type  | "tailgating" | "speeding" | "wrong_way" | ...
  vehicle_id     | ByteTrack persistent ID
  confidence     | "high" | "medium" | "low"
  risk_level     | "critical" | "high" | "medium" | "low"
  evidence       | Free-text description from VLM
  description    | Human-readable sentence

VideoAnalysisSummary:
  total_seconds_analyzed
  observations[]
  risk_score (1-10)
  recommended_alerts[]
  processing_time_ms
```

---

### `stream_analyzer.py` — RealTimeStreamAnalyzer

Coordinates three concurrent asyncio tasks per live stream:

| Task             | Frequency        | Responsibility                              |
|------------------|------------------|---------------------------------------------|
| `_yolo_loop`     | Every frame      | YOLO inference, update `latest_frame/detections` |
| `_broadcast_loop`| 30 FPS target    | JPEG-encode + WebSocket push to subscribers |
| `_vlm_loop`      | Every 3 seconds  | VLM analysis if ≥2 vehicles; SMS trigger    |

When `risk_score >= 5`, the VLM loop calls `POST /v1/incidents` to trigger the
incident orchestration agent.

---

### `report_generator.py` — ReportGenerator

Takes a `VideoAnalysisSummary` and calls the local Ollama `gemma3:1b` model to
produce an `EnhancedReport` with structured sections:

- Executive Summary
- Narrative Summary
- Incident Breakdown
- Evidence Mapping
- Classification (severity)
- Legal Notes

---

### `mongodb_handler.py` — MongoDBHandler

Three MongoDB collections:

| Collection    | Content                                      |
|---------------|----------------------------------------------|
| `frames`      | Extracted frame metadata + base64 image data |
| `detections`  | YOLO detection results per frame             |
| `analyses`    | VLM behavioral analysis results              |

---

### `ollama_client.py` — OllamaClient

Async HTTP client for the local Ollama `/api/generate` endpoint.
Uses `aiohttp` with connection reuse. Used exclusively for report generation
(text-only Gemma3:1b model).

---

### `system_prompt.py` — Prompts

Exports:
- `SYSTEM_PROMPT` — Comprehensive traffic safety analysis system instruction
- `get_analysis_prompt(detections, context)` — Builds per-frame analysis prompt

---

## Agent Subsystem

Located in `agent/`. Triggered when `risk_score >= 5` from stream analysis or via
direct API call.

```
agent/
 ├── config.py      AgentConfig
 │                   ├── RegionalContacts  (+91 police/ambulance hardcoded)
 │                   ├── PolicyConfig      (risk thresholds, confidence min)
 │                   ├── RetryPolicyConfig (3 attempts, 10s backoff)
 │                   ├── VoIPConfig        (provider URL, TTS voice)
 │                   └── FCMConfig         (Firebase push)
 │
 ├── models.py      Pydantic schemas
 │                   ├── IncidentInput     (vlm_summary + enhanced_report + location)
 │                   ├── ActionPlanItem    (type: call|sms|notify, target, priority)
 │                   ├── ActionResult      (plan + final_status + audit[])
 │                   └── OrchestratorOutput (action_result + api_spec)
 │
 ├── policies.py    PolicyEngine
 │                   └── evaluate_action_gating(incident) → PolicyDecision
 │                       Rules:
 │                         risk >= 7                    → AUTO_ACTION (dispatched)
 │                         confidence >= 0.85 + call/sms → AUTO_ACTION
 │                         risk 4-6                     → QUEUED_FOR_REVIEW
 │                         risk < 4                     → LOGGED_ONLY
 │                         ambiguous keywords detected  → ESCALATED
 │
 ├── actions.py     ActionExecutor
 │                   └── execute_action_plan(plan) → (updated_plan, audit[])
 │                       ├── GSM CALL  via mobile device WebSocket
 │                       ├── VoIP CALL as fallback
 │                       ├── SMS       via mobile device WebSocket
 │                       └── PUSH      via FCM
 │
 ├── orchestrator.py       Legacy rule-based IncidentOrchestrator
 │
 ├── langgraph_orchestrator.py  LangGraph stateful workflow (DEFAULT)
 │                   StateGraph nodes:
 │                     assess_risk    → LLM reasons about risk level
 │                     make_decision  → maps to auto/queue/log
 │                     build_plan     → LLM picks targets (ambulance/police/traffic)
 │                     execute        → ActionExecutor fires actions
 │                     finalize       → audit trail + output
 │
 └── routes.py      FastAPI Router (prefix=/v1)
                     POST /incidents                   create & process incident
                     GET  /incidents/{id}              get incident state
                     POST /incidents/{id}/override     manual approve/reject
                     POST /devices/register            register mobile GSM device
                     POST /devices/{id}/callback       receive call state update
                     POST /devices/{id}/voip-callback  VoIP result callback
                     POST /agent/decide                manual LLM decision trigger
```

### LangGraph Workflow State Machine

```
                    ┌─────────────────┐
                    │   START NODE    │
                    │  (incident in)  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  assess_risk    │
                    │  ChatOllama LLM │
                    │  → severity     │
                    │  → urgency      │
                    │  → reasoning    │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  make_decision  │
                    │  PolicyEngine + │
                    │  LLM refinement │
                    │  → policy_decision│
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        auto_dispatch   queue_review    log_only
              │              │              │
              ▼              │              ▼
     ┌─────────────────┐     │    ┌─────────────────┐
     │  build_plan     │     │    │    finalize     │
     │  LLM picks      │     │    │  (log + return) │
     │  emergency      │     │    └─────────────────┘
     │  contacts       │     │
     └────────┬────────┘     │
              │               │
              ▼               │
     ┌─────────────────┐     │
     │  execute        │     │
     │  ActionExecutor │     │
     │  SMS/Call/Push  │     │
     └────────┬────────┘     │
              │               │
              ▼               ▼
     ┌─────────────────────────┐
     │        finalize         │
     │  build OrchestratorOutput│
     │  with full audit trail  │
     └─────────────────────────┘
                    │
                    ▼
                  END
```

---

## Configuration Reference

All settings are in `config.py` and sourced from `.env`:

```
# API Keys
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_API_KEYS=key1,key2,key3   # multi-key load balancing

# MongoDB
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=video_analysis
MONGODB_COLLECTION=frames

# VLM Provider Selection
VLM_PROVIDER=auto                     # ollama | openrouter | auto

# Ollama (local GPU)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_VISION_MODEL=gemma3:4b
OLLAMA_MODEL=gemma3:1b

# Concurrency
VLM_MAX_CONCURRENT=15
VLM_REQUEST_TIMEOUT=60
VLM_RETRY_ATTEMPTS=2

# Streaming
STREAM_VLM_SAMPLE_INTERVAL=3.0       # seconds between VLM calls
STREAM_VLM_MIN_VEHICLES=2            # minimum vehicles to trigger VLM
```

---

## API Reference

### Video Analysis Endpoints

| Method | Path                              | Description                          |
|--------|-----------------------------------|--------------------------------------|
| GET    | `/health`                         | Health check                         |
| GET    | `/api/config`                     | Current configuration                |
| POST   | `/api/upload`                     | Upload video file, start analysis    |
| POST   | `/api/analyze`                    | Analyze existing file by path        |
| GET    | `/api/jobs`                       | List all jobs                        |
| GET    | `/api/jobs/{job_id}`              | Job status                           |
| GET    | `/api/jobs/{job_id}/result`       | Analysis result (observations)       |
| GET    | `/api/jobs/{job_id}/enhanced-report` | Ollama-generated report           |
| GET    | `/api/jobs/{job_id}/video`        | Download annotated video             |
| GET    | `/api/jobs/{job_id}/frame/{sec}`  | Preview frame at second N            |
| GET    | `/api/video-info`                 | Video metadata (fps, duration, etc.) |

### Stream Endpoints

| Method | Path                              | Description                          |
|--------|-----------------------------------|--------------------------------------|
| POST   | `/api/stream/start`               | Start live stream analysis           |
| POST   | `/api/stream/stop`                | Stop live stream                     |
| GET    | `/api/stream/status/{id}`         | Stream state                         |
| GET    | `/api/stream/live-yolo/{id}`      | Latest YOLO annotated frame (JPEG)   |
| GET    | `/api/stream/live-vlm/{id}`       | Latest VLM analysis JSON             |
| GET    | `/api/stream/live-reports/{id}`   | Accumulated reports                  |
| GET    | `/api/stream/list`                | List active streams                  |

### WebSocket Endpoints

| Path                        | Description                                        |
|-----------------------------|----------------------------------------------------|
| `/ws/{job_id}`              | Subscribe to video analysis progress + result      |
| `/ws/stream/{stream_id}`    | Subscribe to live 30fps annotated stream + VLM     |

### Agent / Incident Endpoints (`/v1/...`)

| Method | Path                              | Description                          |
|--------|-----------------------------------|--------------------------------------|
| POST   | `/v1/incidents`                   | Submit VLM event for orchestration   |
| GET    | `/v1/incidents/{id}`              | Get incident processing result       |
| POST   | `/v1/incidents/{id}/override`     | Manually approve or reject action    |
| POST   | `/v1/devices/register`            | Register mobile GSM device           |
| POST   | `/v1/devices/{id}/callback`       | Receive call state from mobile       |
| POST   | `/v1/devices/{id}/voip-callback`  | Receive VoIP result                  |
| POST   | `/v1/agent/decide`                | Trigger manual LLM decision          |
