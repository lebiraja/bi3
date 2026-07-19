# BI3 Smart Traffic Safety — Complete Project Documentation

> **Version:** 1.0 · **Stack:** Python 3.11 / FastAPI / YOLO11 / LangGraph / React / Flutter

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Technology Stack](#2-technology-stack)
3. [System Architecture](#3-system-architecture)
4. [Project Structure](#4-project-structure)
5. [Core Features](#5-core-features)
6. [Pipeline Deep-Dives](#6-pipeline-deep-dives)
   - [6.1 Video File Analysis Pipeline](#61-video-file-analysis-pipeline)
   - [6.2 Live Stream Analysis Pipeline](#62-live-stream-analysis-pipeline)
   - [6.3 Incident Orchestration Agent](#63-incident-orchestration-agent)
   - [6.4 WebSocket Real-Time Communication](#64-websocket-real-time-communication)
7. [AI & ML Layer](#7-ai--ml-layer)
8. [Module Reference](#8-module-reference)
9. [Agent Subsystem](#9-agent-subsystem)
10. [Frontend — React Web Dashboard](#10-frontend--react-web-dashboard)
11. [Mobile App — Flutter](#11-mobile-app--flutter)
12. [Database Schema](#12-database-schema)
13. [Configuration Reference](#13-configuration-reference)
14. [API Reference](#14-api-reference)
15. [Installation & Setup](#15-installation--setup)
16. [Performance Characteristics](#16-performance-characteristics)
17. [Data Models & Schemas](#17-data-models--schemas)
18. [Security & Policies](#18-security--policies)

---

## 1. Project Overview

**BI3** is a production-grade, real-time smart traffic safety platform. It ingests live video
streams from YouTube, RTSP, or HLS sources — as well as uploaded video files — runs AI-powered
vehicle detection and behavior analysis, generates formal incident reports, and autonomously
dispatches emergency alerts to police, ambulance, and traffic control services when dangerous
situations are detected.

### What It Does

| Capability | Description |
|---|---|
| **Live Stream Monitoring** | Connect any YouTube / RTSP / HLS URL and monitor traffic in real-time |
| **Vehicle Detection** | Detect and track cars, motorcycles, buses, and trucks using YOLO11 + ByteTrack |
| **Behavior Analysis** | Identify speeding, erratic movement, sudden stops, wrong-way driving, and collisions using Vision-Language Models |
| **Risk Scoring** | Every analyzed interval receives a risk score from 1–10 |
| **Automated Reporting** | Generate formal, police-ready documentation reports using a local LLM |
| **Emergency Dispatch** | Automatically send SMS alerts to police and ambulance when risk score ≥ 5 |
| **Operator Dashboard** | React web UI for monitoring, reviewing jobs, and watching live feeds |
| **Mobile Agent** | Flutter Android/iOS app that acts as a GSM relay, executing calls and SMS using the phone's native telephony |
| **Audit Trail** | Every decision, action, and outcome is logged in a complete audit trail |

### Problem It Solves

Traditional traffic monitoring systems are passive — they record but do not respond. BI3 closes
the loop between *detection* and *action* by coupling computer vision with an autonomous
orchestration agent that evaluates risk, decides whether to act, builds an action plan, and
executes emergency notifications — all within seconds of a dangerous event being detected.

---

## 2. Technology Stack

### Backend

| Component | Technology | Version / Notes |
|---|---|---|
| API Framework | FastAPI | Python 3.11+, async-first |
| ASGI Server | Uvicorn | Production-ready |
| Object Detection | Ultralytics YOLO11 | `yolo11n.pt` (nano model) |
| Vehicle Tracking | ByteTrack | Persistent vehicle IDs across frames |
| Vision-Language Model (Cloud) | Qwen3-VL-8B | Via OpenRouter API |
| Vision-Language Model (Local) | Gemma3:4b | Via Ollama (local GPU) |
| Report Generation LLM | Gemma3:1b | Via Ollama (local, text-only) |
| LLM Orchestration | LangGraph + LangChain | Stateful multi-step workflows |
| LLM Interface | ChatOllama (LangChain-Ollama) | Connects LangGraph to Ollama |
| Stream Ingestion | yt-dlp | Resolves YouTube/HLS/RTSP URLs |
| Video Processing | OpenCV (cv2) | Frame extraction and annotation |
| Database | MongoDB | pymongo driver |
| HTTP Client | aiohttp | Async for VLM API calls |
| Environment Config | python-dotenv | `.env` file loading |
| Data Validation | Pydantic v2 | Request/response schemas |

### Frontend

| Component | Technology |
|---|---|
| Framework | React 18 |
| Language | TypeScript |
| Build Tool | Vite |
| Styling | Tailwind CSS v4 |
| HTTP Client | Axios |
| Routing | React Router DOM v6 |
| Charts | Recharts |
| Animation | Framer Motion |
| Icons | Lucide React |
| Date Handling | date-fns |

### Mobile (Flutter)

| Component | Technology |
|---|---|
| Framework | Flutter |
| Language | Dart |
| HTTP Client | http |
| WebSocket | web_socket_channel |
| State Management | Provider |
| Text-to-Speech | flutter_tts |
| Native Telephony | Platform Channels (Android MethodChannel) |
| Local Storage | shared_preferences |
| Permissions | permission_handler |
| Unique IDs | uuid |

### Infrastructure

| Component | Technology |
|---|---|
| Database | MongoDB (local or Atlas) |
| Local AI Runtime | Ollama (runs Gemma3 models) |
| Cloud AI | OpenRouter (proxies Qwen3-VL-8B) |
| Object Detection Model | YOLO11n (Ultralytics, ~6MB) |

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    BI3 SMART TRAFFIC SAFETY PLATFORM                    │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
   ┌─────▼──────┐      ┌───────▼──────┐     ┌───────▼──────┐
   │ React Web  │      │  Flutter     │     │  Video Files │
   │ Dashboard  │      │  Mobile App  │     │  (Upload)    │
   │ (Vite/TS)  │      │  (Android/   │     │              │
   └─────┬──────┘      │  iOS/Web)    │     └───────┬──────┘
         │             └───────┬──────┘             │
         │  REST / WebSocket   │                    │  HTTP POST
         └──────────┬──────────┘                    │
                    │                               │
         ┌──────────▼───────────────────────────────▼──────┐
         │              FastAPI Server (server.py)          │
         │                                                  │
         │  ┌─────────────┐  ┌──────────────────────────┐  │
         │  │ REST Routes │  │  WebSocket Managers       │  │
         │  │ /api/...    │  │  ConnectionManager (jobs) │  │
         │  │ /v1/...     │  │  DeviceConnectionManager  │  │
         │  └──────┬──────┘  └─────────────┬────────────┘  │
         └─────────┼───────────────────────┼───────────────┘
                   │                       │
        ┌──────────┼──────────┐            │ WebSocket push
        │          │          │            │
        ▼          ▼          ▼            ▼
   ┌─────────┐ ┌───────┐ ┌────────┐  ┌──────────┐
   │  Video  │ │Stream │ │ Agent  │  │ Clients  │
   │  File   │ │ Live  │ │ /v1/   │  │ (React / │
   │Pipeline │ │Pipeline│ │incidents│ │ Flutter) │
   └────┬────┘ └───┬───┘ └────┬───┘  └──────────┘
        │          │          │
        ▼          ▼          │
   ┌──────────────────────┐   │
   │   AI / ML Layer      │   │
   │  YOLO11 + ByteTrack  │   │
   │  HybridVLMClient     │   │
   │  ReportGenerator     │   │
   └──────────┬───────────┘   │
              │               │
              ▼               ▼
   ┌──────────────────────────────────────────┐
   │                MongoDB                    │
   │  frames | detections | analyses           │
   └──────────────────────────────────────────┘
              │
              ▼ (risk_score >= 5)
   ┌──────────────────────────────────────────┐
   │   LangGraph Incident Orchestrator         │
   │   PolicyEngine → ActionExecutor           │
   │                                           │
   │   SMS → Police (+91-9535879330)           │
   │   SMS → Ambulance (+91-6369445764)        │
   │   SMS → Traffic Control                   │
   └──────────────────────────────────────────┘
```

---

## 4. Project Structure

```
bi3/
│
├── server.py                     Main FastAPI application
├── config.py                     Centralized configuration (env vars)
│
├── ─── VIDEO FILE PIPELINE ──────────────────────────────────────────────
├── frame_sampler.py              OpenCV-based frame extractor (3 fps sampling)
├── vlm_client.py                 OpenRouter VLM async client (multi-key LB)
├── behavior_analyzer.py          Parallel VLM orchestration + aggregation
├── report_generator.py           Ollama LLM report generation
├── video_analyzer.py             Offline video analysis helper
├── video_processor.py            YOLO annotation + video encoding utilities
├── vlm_sampler.py                VLM sampling helper utilities
│
├── ─── STREAM PIPELINE ──────────────────────────────────────────────────
├── stream_processor.py           yt-dlp + OpenCV stream ingestion
├── continuous_yolo.py            GPU YOLO11 processor (dedicated thread)
├── hybrid_vlm_client.py          Ollama/OpenRouter auto-select VLM client
├── stream_analyzer.py            Real-time coordinator (3 async loops)
├── vehicle_tracking.py           Standalone YOLO + ByteTrack script
│
├── ─── SUPPORT ──────────────────────────────────────────────────────────
├── mongodb_handler.py            MongoDB CRUD operations
├── ollama_client.py              Async Ollama HTTP client
├── system_prompt.py              VLM system prompt + prompt factory
│
├── ─── AGENT SUBSYSTEM ──────────────────────────────────────────────────
├── agent/
│   ├── __init__.py
│   ├── config.py                 AgentConfig (thresholds, contacts, retry)
│   ├── models.py                 Pydantic schemas for all agent I/O
│   ├── policies.py               PolicyEngine (risk/confidence gating)
│   ├── actions.py                ActionExecutor (SMS / GSM call / push)
│   ├── orchestrator.py           Legacy rule-based orchestrator
│   ├── langgraph_orchestrator.py LangGraph stateful workflow (DEFAULT)
│   ├── routes.py                 FastAPI router (/v1/...)
│   ├── llm_helper.py             LLM utility functions
│   └── api_spec.py               OpenAPI 3.0 spec generator
│
├── ─── PROMPTS ──────────────────────────────────────────────────────────
├── prompts/
│   ├── __init__.py
│   └── enhanced_report_prompt.py Ollama report prompt templates
├── system_prompt.py              VLM behavior analysis system prompt
│
├── ─── FRONTENDS ────────────────────────────────────────────────────────
├── frontend/                     React 18 + TypeScript + Vite
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Upload.tsx
│   │   │   ├── Jobs.tsx
│   │   │   ├── JobDetail.tsx
│   │   │   ├── LiveStream.tsx
│   │   │   └── Settings.tsx
│   │   ├── components/
│   │   │   ├── ui/               (Button, Card, Badge, ProgressBar, ...)
│   │   │   └── layout/           (Header, Sidebar, Layout)
│   │   ├── services/
│   │   │   └── api.ts            Axios API client
│   │   ├── types/                TypeScript type definitions
│   │   ├── hooks/                React hooks
│   │   └── contexts/             React context providers
│   └── package.json
│
└── mobile/                       Flutter app (Android/iOS/Web)
    ├── lib/
    │   ├── main.dart             App entry, permissions init, Provider setup
    │   ├── config.dart           App configuration (server URL, etc.)
    │   ├── models/               Dart data models
    │   ├── screens/
    │   │   ├── home_screen.dart        Dashboard + incident feed
    │   │   ├── incident_detail_screen.dart
    │   │   ├── logs_screen.dart
    │   │   └── settings_screen.dart
    │   └── services/
    │       ├── agent_service.dart      Main orchestration service
    │       ├── api_service.dart        REST API client
    │       ├── websocket_service.dart  WebSocket client (auto-reconnect)
    │       ├── native_telephony_service.dart  Platform channel (Android)
    │       ├── call_sms_service.dart   High-level call/SMS interface
    │       ├── phone_service.dart      Phone number management
    │       ├── tts_service.dart        Text-to-speech for alerts
    │       ├── preferences_service.dart  SharedPreferences wrapper
    │       └── logger_service.dart     In-app logging
    ├── android/                  Native Android code (MethodChannel impl.)
    └── pubspec.yaml
```

---

## 5. Core Features

### 5.1 Video File Analysis

Upload any `.mp4`, `.mov`, or `.avi` file and the system:

1. Extracts frames at 3 fps using OpenCV
2. Runs YOLO11n detection on every frame (cars, motorcycles, buses, trucks)
3. Groups frames into 1-second batches
4. Sends each batch to a Vision-Language Model (VLM) for behavior analysis
5. Aggregates all observations into a `VideoAnalysisSummary`
6. Generates a formal, police-ready report using a local Ollama LLM
7. Stores everything in MongoDB
8. Streams progress to the frontend via WebSocket in real-time

### 5.2 Live Stream Monitoring

Paste any YouTube URL (including live streams), RTSP, or HLS URL and the system:

1. Resolves the direct stream URL using yt-dlp
2. Opens it with OpenCV `VideoCapture`
3. Runs three concurrent async loops:
   - **YOLO Loop:** Processes every incoming frame at full speed
   - **Broadcast Loop:** Sends JPEG-encoded annotated frames at 30 FPS via WebSocket
   - **VLM Loop:** Analyzes a frame every 3 seconds if ≥ 2 vehicles are visible
4. When `risk_score ≥ 5`, automatically triggers the Incident Orchestration Agent
5. The agent sends SMS alerts to emergency services

### 5.3 Behavior Detection Categories

The VLM is instructed to detect these specific behaviors:

| Behavior Type | Description |
|---|---|
| `speeding` | Rapid displacement across frames, inconsistent with environment |
| `erratic_movement` | Abrupt lateral shifts, weaving, zig-zag motion |
| `sudden_stop` | Sharp deceleration, brake light cues, emergency stop |
| `violation` | Wrong-way driving, red-light violation, tailgating, illegal turns |
| `collision` | Only if actual physical impact is visible (conservative threshold) |

Each observation includes: `vehicle_id`, `confidence` (high/medium/low), `risk_level`
(critical/warning/low), `evidence` (specific visual evidence), and `description`.

### 5.4 Risk Scoring

Every analyzed interval receives a `risk_score` from 1–10:

| Score | Interpretation | Action |
|---|---|---|
| 1–3 | Low risk, normal traffic | Log only |
| 4–6 | Medium risk, review warranted | Queue for operator review |
| 5+ | Elevated risk (live stream) | Trigger SMS alert |
| 7–10 | High/Critical risk | Auto-dispatch emergency services |

### 5.5 Incident Orchestration

When an incident is triggered, the LangGraph agent:

1. **Analyzes** the incident with an LLM (`gemma3:1b`) for severity and urgency
2. **Decides** based on policy rules + LLM reasoning: auto-dispatch / queue / log-only
3. **Builds** an action plan (which emergency services to contact, what to say)
4. **Executes** actions via the Flutter mobile app's native telephony (SMS/calls)
5. **Monitors** callbacks and retries failed actions (up to 3 attempts, 10s backoff)
6. **Finalizes** with a complete audit trail

### 5.6 Emergency Response Actions

| Action Type | Method | Target |
|---|---|---|
| SMS Alert | Mobile device native SMS via Android MethodChannel | Police, Ambulance, Traffic Control |
| GSM Call | Mobile device native call via Android MethodChannel | Police, Ambulance |
| VoIP Call | Fallback TTS call via configured VoIP provider | Any |
| Push Notification | Firebase Cloud Messaging (FCM) | Operator dashboard |

SMS messages are customized per recipient:
- **Police:** Incident type, severity, risk score, location, timestamp
- **Ambulance:** Medical emergency framing, location, dispatch request
- **Traffic Control:** Traffic incident framing, risk level, coordinates

### 5.7 Enhanced Report Generation

After video file analysis, a formal documentation report is generated using Ollama's
`gemma3:1b` model. The report includes:

- **Executive Summary** (3–4 paragraphs: what, who, severity)
- **Detailed Narrative Summary** (complete incident description, step-by-step)
- **Chronological Incident Breakdown** (timeline with exact timestamps)
- **Evidence Mapping** (frame references, YOLO data, VLM signals)
- **Classification & Severity** (category, risk justification)
- **Legal / Procedural Notes** (why it matters, what authorities should know)

### 5.8 Multi-Key API Load Balancing

The VLM client supports multiple OpenRouter API keys (comma-separated in `.env`).
Requests are distributed round-robin across keys, with per-key concurrency semaphores,
enabling much higher throughput without hitting individual key rate limits.

---

## 6. Pipeline Deep-Dives

### 6.1 Video File Analysis Pipeline

```
User uploads file
       │
       ▼
FastAPI: POST /api/upload
  • Validates file type
  • Saves to /uploads/{video_id}.ext
  • Creates job entry (status: pending)
  • Starts background task
  • Returns { job_id, ws_url }
       │
       ▼ (background task)
VideoAnalysisPipeline.run_analysis()
       │
       ├── Stage 1: Frame Extraction
       │   FrameSampler(video_path)
       │   • Opens with cv2.VideoCapture
       │   • Extracts 1 frame every SAMPLE_INTERVAL frames (default: 10)
       │   • At 30fps → 3 frames per second
       │   • Each frame: base64-encoded + metadata → FrameData
       │   • Stores frames → MongoDB (frames collection)
       │
       ├── Stage 2: YOLO Detection (per-frame)
       │   YOLO11n model + ByteTrack
       │   • Classes: car(2), motorcycle(3), bus(5), truck(7)
       │   • Confidence: 0.3, IOU: 0.5
       │   • Returns bounding boxes + persistent track IDs
       │   • Stores detections → MongoDB (detections collection)
       │
       ├── Stage 3: VLM Behavior Analysis
       │   BehaviorAnalyzer
       │   • Groups FrameData into 1-second batches
       │   • For each batch: fires async VLM request (parallel pool)
       │   • asyncio.Semaphore(VLM_MAX_CONCURRENT) controls concurrency
       │   • VLMClient → OpenRouter API → Qwen3-VL-8B
       │   • Prompt: system_prompt.py SYSTEM_PROMPT + YOLO context
       │   • Response: JSON with observations[] + overall_assessment
       │   • Aggregates all → VideoAnalysisSummary
       │   • Stores analyses → MongoDB (analyses collection)
       │
       ├── Stage 4: Report Generation
       │   ReportGenerator
       │   • Formats VideoAnalysisSummary as classical report
       │   • Calls OllamaClient → gemma3:1b
       │   • Parses response into EnhancedReport sections
       │   • Stores report alongside analysis results
       │
       └── Stage 5: WebSocket Broadcast
           ConnectionManager.broadcast(job_id, event)
           • type: "progress" (during processing)
           • type: "batch_result" (per VLM batch)
           • type: "completed" (final result + report)
           • type: "error" (on failure)
```

### 6.2 Live Stream Analysis Pipeline

```
User submits stream URL
       │
       ▼
FastAPI: POST /api/stream/start
  { stream_id, url, quality }
       │
       ▼
RealTimeStreamAnalyzer.start_analysis()
       │
       ├── StreamManager.create_stream(stream_id, url)
       │   • Checks max concurrent limit (3)
       │   • Creates StreamExtractor instance
       │
       ├── StreamExtractor.start_stream(stream_id)
       │   • yt-dlp extracts direct HLS/DASH URL from any YouTube/stream URL
       │   • cv2.VideoCapture opens the direct stream URL
       │   • Starts daemon thread: _buffer_frames()
       │     → Reads frames continuously into Queue(maxsize=90)
       │     → Reconnects automatically on timeout
       │     → 90-frame buffer ≈ 3 seconds at 30fps
       │
       ├── ContinuousYOLOProcessor.load_model()
       │   • Loads yolo11n.pt once (shared across all streams)
       │   • GPU-accelerated with ByteTrack enabled
       │
       └── Three asyncio tasks launched in parallel:
           │
           ├── Task 1: _yolo_loop (every frame, ~1ms yield)
           │   • extractor.get_frame() → non-blocking queue get
           │   • yolo_processor._run_inference(frame) → ~15-25ms GPU
           │   • Updates state atomically:
           │     latest_frame, latest_detections, frame_count, timestamp_ms
           │   • Every vlm_interval_frames: saves vlm_frame for VLM loop
           │
           ├── Task 2: _broadcast_loop (30fps rate-limited)
           │   • Reads latest_frame + latest_detections
           │   • yolo_processor._draw_detections() → annotated frame
           │   • cv2.imencode('.jpg', frame, quality=75) → JPEG bytes
           │   • base64.b64encode() → string
           │   • event_callback({
           │       type: "yolo_video_frame",
           │       frame_base64, vehicle_count, detections, timestamp_ms
           │     })
           │   • WebSocket push to all subscribed clients
           │
           └── Task 3: _vlm_loop (every STREAM_VLM_SAMPLE_INTERVAL seconds)
               • Waits 3s initial delay for buffer to fill
               • Skips if vehicle_count < STREAM_VLM_MIN_VEHICLES (2)
               • Resizes frame to max 480px height (VLM optimization)
               • Encodes at JPEG quality 65
               • HybridVLMClient.analyze_frames([frame_b64], yolo_context)
               • Parses VisionAnalysisResult
               • Broadcasts vlm_analysis event via WebSocket
               │
               └── If risk_score >= 5:
                   _trigger_sms_notification()
                   • Creates VLMSummary + EnhancedReportData Pydantic objects
                   • Creates incident_data dict with new UUID incident_id
                   • Calls orchestrator.process_incident_async(incident_data)
                   • SMS dispatched to emergency services
```

### 6.3 Incident Orchestration Agent

The agent is implemented as a **LangGraph stateful workflow** (enabled by default via
`USE_LANGGRAPH=true` environment variable). There is also a legacy rule-based
`IncidentOrchestrator` as fallback.

#### LangGraph Workflow Nodes

```
START
  │
  ▼
[analyze_incident]  ── ChatOllama(gemma3:1b) ──────────────────────────
  │                                                                      │
  │  Prompt: incident_type, confidence, risk_score,                     │
  │          vehicles_involved, executive_summary                        │
  │  Output: severity (critical/high/medium/low)                        │
  │          urgency (immediate/urgent/standard)                         │
  │  Fallback: rule-based if LLM unavailable                            │
  │                                                                      │
  ▼                                                                      │
[policy_decision]  ── Hybrid: rules + LLM insights ────────────────────┘
  │
  │  Rules applied:
  │    risk >= 8 AND confidence >= 0.85 AND severity=critical → auto_dispatch
  │    risk >= 7 AND urgency=immediate                        → auto_dispatch
  │    risk >= 6 OR severity in [critical, high]             → queue_review
  │    else                                                   → log_only
  │
  ├── "auto_dispatch" ──────────────────────────────────────────────────►
  │                                                                       │
  │   [build_action_plan]                                                 │
  │     • risk >= 7       → SMS to Police                                │
  │     • "injury"/"accident" in description → SMS to Ambulance          │
  │     • always          → SMS to Traffic Control                       │
  │     • Generates custom SMS text per recipient                        │
  │       (incident type, severity, risk score, location, timestamp)     │
  │                          │                                           │
  │   [execute_actions]      │                                           │
  │     ActionExecutor:      │                                           │
  │     • For each SMS action:                                           │
  │       _execute_sms() → _send_sms()                                   │
  │       1. Checks DeviceConnectionManager for connected Flutter device │
  │       2. If device online: sends WebSocket command {type:sms_action} │
  │       3. Flutter native code → Android SMS Manager                   │
  │       4. If no device: logs "simulated SMS"                          │
  │     • Updates ActionStatus: SENT / FAILED                            │
  │                          │                                           │
  │   [monitor_callbacks]    │                                           │
  │     • Checks if any actions need retry                               │
  │     • needs_retry=True → loop back to execute                       │
  │     • needs_retry=False → finalize                                   │
  │                                                                       │
  ├── "queue_review" ──────────────────────────────────────────────────►
  │   [queue_for_review]                                                  │
  │     • final_status = "queued_for_review"                             │
  │     • operator_message generated for dashboard                       │
  │     → END                                                            │
  │                                                                       │
  └── "log_only" ───────────────────────────────────────────────────────►
      [finalize_incident]
        • final_status = "logged_only"
        • Audit entry recorded
        → END

[finalize_incident]
  • Determines final_status:
    - failed_actions present → "escalated"
    - executed_actions present → "dispatched"
    - no actions → "logged_only"
  • Appends final audit entry
  → END
```

#### Emergency Contact Numbers

| Service | Primary Number | Notes |
|---|---|---|
| Police | +91-9535879330 | Hardcoded in `agent/config.py` |
| Ambulance | +91-6369445764 | Hardcoded in `agent/config.py` |
| Traffic Control | +91-9535879330 | Uses police number as fallback |
| Fire Department | +91-1234567890 | Available in LangGraph helper |

#### Policy Engine Thresholds

| Threshold | Default Value | Setting |
|---|---|---|
| Auto-action minimum risk score | 7 | `policy.auto_action_min_risk_score` |
| Auto-action minimum confidence | 0.85 | `policy.auto_action_min_confidence` |
| Queue for review minimum risk | 4 | `policy.queue_for_review_min_risk_score` |
| Ambiguity keywords | ambiguous, unclear, uncertain, possible, might be | `policy.ambiguous_keywords` |
| Retry attempts | 3 | `retry_policy.max_attempts` |
| Retry backoff | 10 seconds | `retry_policy.backoff_seconds` |
| Call timeout | 30 seconds | `retry_policy.call_timeout_seconds` |

### 6.4 WebSocket Real-Time Communication

Two WebSocket connection managers run inside the FastAPI server:

#### ConnectionManager (Job Progress)

```
Client: WS CONNECT /ws/{job_id}
Server: ConnectionManager.connect(websocket, job_id)
        • Adds to ws_connections[job_id][]

Events pushed to client:
  { type: "progress",      progress: 0.0-1.0, stage: "yolo|vlm|report" }
  { type: "batch_result",  second_index: N, observations: [...], risk_score: N }
  { type: "frame_preview", frame_number: N, frame_base64: "..." }
  { type: "completed",     result: { observations, risk_score, enhanced_report } }
  { type: "error",         message: "..." }
```

#### DeviceConnectionManager (Flutter Mobile)

```
Flutter: WS CONNECT /ws/device/{device_id}
Server:  DeviceConnectionManager.connect(websocket, device_id)

Commands sent to Flutter:
  { type: "sms_action",    number: "+91...", text: "🚨 POLICE ALERT..." }
  { type: "call_command",  number: "+91...", action_id: "...", spoken_message: "..." }
  { type: "action_plan",   actions: [...] }
  { type: "heartbeat" }

Callbacks from Flutter:
  { type: "action_ack",    action_id: "...", status: "sent|failed" }
  { type: "call_state",    state: "CALL_STATE_OFFHOOK|IDLE|RINGING" }
```

#### Stream WebSocket

```
Client: WS CONNECT /ws/stream/{stream_id}
Server: stream_websocket_endpoint()

Events pushed at 30fps:
  { type: "yolo_video_frame",
    frame_base64: "<JPEG base64>",
    vehicle_count: N,
    frame_number: N,
    timestamp_ms: T }

  { type: "yolo_detection",
    detections: [{ track_id, class_name, bbox, confidence, color }],
    vehicle_count: N }

  { type: "vlm_analysis",
    analysis: { risk_score, observations, summary, recommended_alerts } }

  { type: "initialization_complete" | "error" }
```

---

## 7. AI & ML Layer

### 7.1 YOLO Object Detection

**Model:** YOLO11n (nano) — `yolo11n.pt` (~6 MB, fastest variant)

**Tracked Vehicle Classes (COCO dataset):**

| Class ID | Label | Color (BGR) |
|---|---|---|
| 2 | car | (0, 255, 0) — Green |
| 3 | motorcycle | (255, 0, 0) — Blue |
| 5 | bus | (0, 165, 255) — Orange |
| 7 | truck | (0, 255, 255) — Yellow |

**Tracker:** ByteTrack (`bytetrack.yaml`)
- Assigns persistent numeric IDs to vehicles across frames
- Handles occlusion and re-identification
- Alternative: BoT-SORT (`botsort.yaml`) — better for camera motion

**Detection Parameters:**
- Confidence threshold: `0.3`
- IOU threshold (NMS): `0.5`
- Expected inference speed: ~15–25ms on RTX 4050 GPU

### 7.2 Vision-Language Model (VLM)

**Purpose:** Analyze annotated video frames for dangerous driving behaviors.

**Two providers supported:**

| Provider | Model | When Used |
|---|---|---|
| OpenRouter (cloud) | `qwen/qwen3-vl-8b-instruct` | `VLM_PROVIDER=openrouter` or auto fallback |
| Ollama (local) | `gemma3:4b` (vision) | `VLM_PROVIDER=ollama` or auto primary |

**Auto-selection logic (`VLM_PROVIDER=auto`):**
1. Tries Ollama first (lower latency, no API cost)
2. Falls back to OpenRouter if Ollama unavailable

**System Prompt Design:**
The VLM is given a detailed `SYSTEM_PROMPT` that enforces:
- Context-aware scene interpretation (urban/highway/parking lot/toll)
- Conservative collision detection (only if actual impact visible)
- Anti-hallucination guidance ("never exaggerate")
- Strict JSON output format (no extra text)

**Output JSON schema (strict):**
```json
{
  "timestamp_range": "start_time - end_time",
  "observations": [
    {
      "behavior_type": "speeding|erratic_movement|sudden_stop|violation",
      "vehicle_id": "track_id or description",
      "confidence": "high|medium|low",
      "evidence": "specific visual evidence",
      "risk_level": "critical|warning|low",
      "description": "detailed description"
    }
  ],
  "overall_assessment": {
    "risk_score": 5,
    "summary": "brief narrative",
    "recommended_alerts": ["sms", "call"]
  }
}
```

### 7.3 Report Generation LLM

**Model:** `gemma3:1b` via Ollama (local, text-only, fast)

**Purpose:** Generate formal, police-ready documentation from VLM analysis summaries.

**Input:** Formatted classical report (observations + statistics + timestamps)

**Output:** Full structured document with 6 named sections:
1. Executive Summary
2. Detailed Narrative Summary
3. Chronological Incident Breakdown
4. Evidence Mapping
5. Classification & Severity
6. Legal / Procedural Notes

### 7.4 LangGraph Decision LLM

**Model:** `gemma3:1b` via ChatOllama (LangChain interface)

**Purpose:** Enhanced risk assessment and action plan generation within the LangGraph workflow.

**Prompt structure:**
- Input: incident_type, VLM confidence, risk_score, vehicles_involved, executive_summary
- Output: severity (critical/high/medium/low), urgency (immediate/urgent/standard), required emergency services, reasoning

**Fallback:** If LLM is unavailable (Ollama offline), rule-based assessment kicks in automatically using `risk_score` thresholds.

---

## 8. Module Reference

### `server.py`

The FastAPI application entry point. Contains:

- **`VideoAnalysisPipeline`** class — singleton managing the full file analysis workflow,
  including YOLO model initialization, MongoDB setup, and progress broadcasting
- **`ConnectionManager`** — manages WebSocket connections keyed by `job_id`
- **`DeviceConnectionManager`** — manages WebSocket connections keyed by `device_id`
  for the Flutter mobile app; provides `send_command()` and `broadcast()` methods
- **`lifespan()`** — async context manager that initializes the Ollama client,
  stream manager, stream analyzer, and incident orchestrator on startup
- **All REST route handlers** for `/api/...` and `/ws/...` endpoints
- **Agent router** mounted from `agent/routes.py` at `/v1/...`

---

### `config.py`

Single class `Config` with all settings as class-level attributes loaded from environment.
No instantiation needed — use `Config.SETTING_NAME` directly.

Key setting groups:
- OpenRouter API keys + model
- Ollama URLs + models + timeouts
- MongoDB URI + database + collection
- YOLO model path + thresholds + vehicle classes
- Frame sampling rates
- VLM concurrency + timeout + retry
- Stream batch durations + quality + max concurrent
- Continuous stream VLM interval + min vehicles
- WebSocket FPS

---

### `frame_sampler.py`

```python
class FrameSampler:
    def __init__(self, video_path: str, sample_interval: int = None)

    def get_video_info(self) -> dict
    # Returns: fps, total_frames, duration_seconds, width, height,
    #          sample_interval, frames_per_second_sampled

    def sample_frames(self) -> Generator[FrameData, None, None]
    # Yields one FrameData per sampled frame

    def get_frames_by_second(self) -> Dict[int, List[FrameData]]
    # Returns dict keyed by second_index → list of FrameData in that second

@dataclass
class FrameData:
    frame_number: int
    timestamp_ms: float
    image_data: np.ndarray
    base64_encoded: str
    width: int
    height: int
```

---

### `stream_processor.py`

```python
class StreamExtractor:
    def __init__(self, url: str, quality: str = "720p", timeout: int = 30)

    def start_stream(self, stream_id: str) -> StreamInfo
    # Resolves URL with yt-dlp, opens cv2.VideoCapture, starts buffer thread

    def get_frame(self) -> Optional[Tuple[int, np.ndarray, float]]
    # Non-blocking: returns (frame_no, frame, timestamp_ms) or None

    def get_batch_frames(self, duration: int = 15, target_fps: int = 3) -> List[tuple]
    # Blocking: extracts N seconds of frames at target fps

    def stop_stream(self) -> None

class StreamManager:
    def create_stream(self, stream_id: str, url: str, quality: str) -> StreamExtractor
    def get_stream(self, stream_id: str) -> Optional[StreamExtractor]
    def update_state(self, stream_id: str, state: StreamState, error: str = None)
    def get_status(self, stream_id: str) -> Optional[dict]
    def remove_stream(self, stream_id: str)
    def list_streams(self) -> List[dict]

class StreamState(Enum):
    INITIALIZING | ACTIVE | PAUSED | STOPPED | ERROR
```

---

### `continuous_yolo.py`

```python
class ContinuousYOLOProcessor:
    def __init__(self, model_path: str = None, use_tracking: bool = True)

    def load_model(self) -> None
    # Loads yolo11n.pt with ByteTrack tracker

    def _run_inference(self, frame: np.ndarray) -> List[dict]
    # Returns list of:
    # { track_id, class_id, class_name, bbox:[x1,y1,x2,y2],
    #   confidence, color:(B,G,R) }

    def _draw_detections(self, frame: np.ndarray, detections: List[dict]) -> np.ndarray
    # Returns annotated frame with bounding boxes + labels + IDs
```

---

### `hybrid_vlm_client.py`

```python
class HybridVLMClient:
    def __init__(self, provider: VLMProvider = None, ...)
    # provider=None → auto-detect based on Config.VLM_PROVIDER

    async def analyze_frames(
        self,
        frames: List[str],          # base64-encoded JPEG strings
        yolo_context: dict          # { detections, vehicle_counts }
    ) -> VisionAnalysisResult

    async def analyze_frames_batch(
        self,
        frame_batches: List[List[str]]
    ) -> List[VisionAnalysisResult]

class VisionAnalysisResult:
    success: bool
    content: Optional[str]
    parsed_json: Optional[dict]     # The structured JSON from VLM
    error: Optional[str]
    model: Optional[str]
    processing_time_ms: Optional[float]
    provider: Optional[str]         # "ollama" or "openrouter"

class VLMProvider(Enum):
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
```

---

### `behavior_analyzer.py`

```python
class BehaviorAnalyzer:
    async def analyze_video(
        self,
        frames_by_second: Dict[int, List[FrameData]],
        yolo_detections: Dict[int, List[dict]]
    ) -> VideoAnalysisSummary

@dataclass
class BehaviorObservation:
    behavior_type: str
    vehicle_id: str
    confidence: str        # "high" | "medium" | "low"
    evidence: str
    risk_level: str        # "critical" | "warning" | "low"
    description: str

@dataclass
class VideoAnalysisSummary:
    total_seconds_analyzed: int
    observations: List[BehaviorObservation]
    risk_score: float                       # average across all seconds
    recommended_alerts: List[str]
    processing_time_ms: int
    success: bool
```

---

### `report_generator.py`

```python
class ReportGenerator:
    async def generate_enhanced_report(
        self,
        summary: VideoAnalysisSummary,
        video_id: str
    ) -> EnhancedReport

@dataclass
class EnhancedReport:
    report_type: str = "enhanced"
    video_id: str
    generated_at: str
    content: str                    # Full Ollama-generated document
    executive_summary: str
    narrative_summary: str
    incident_breakdown: str
    evidence_mapping: str
    classification: str
    legal_notes: str
    vlm_risk_score: float
    observation_count: int
    generation_time_ms: int
    success: bool
```

---

### `mongodb_handler.py`

```python
class MongoDBHandler:
    def connect(self) -> None
    def disconnect(self) -> None

    # Frames
    def store_frame(self, frame_data: FrameData, video_id: str) -> str
    def get_frames(self, video_id: str) -> List[dict]

    # Detections
    def store_detection(self, detection: dict, video_id: str) -> str
    def get_detections(self, video_id: str) -> List[dict]

    # Analyses
    def store_analysis(self, analysis: dict, video_id: str) -> str
    def get_analysis(self, video_id: str) -> Optional[dict]
```

Collections: `frames`, `detections`, `analyses`

---

### `ollama_client.py`

```python
class OllamaClient:
    def __init__(self, base_url: str = None, model: str = None, timeout: int = None)

    async def generate(self, prompt: str, system_prompt: str = None) -> OllamaResponse

@dataclass
class OllamaResponse:
    success: bool
    content: Optional[str]
    error: Optional[str]
    model: Optional[str]
    total_duration: Optional[int]    # nanoseconds
```

---

### `system_prompt.py`

```python
SYSTEM_PROMPT: str
# Full traffic safety analysis system instruction (~800 words)
# Covers: scene context, behavior detection, anti-hallucination rules,
#         strict JSON output format

def get_analysis_prompt(yolo_data: dict, frame_count: int = 3) -> str
# Builds the user message with YOLO detection context
# Lists all detected vehicles by frame with their track IDs and positions
```

---

## 9. Agent Subsystem

### Overview

Located in `agent/`. Provides the autonomous incident response capability.
Mounted into FastAPI as a sub-application router at prefix `/v1`.

Selected via environment variable:
- `USE_LANGGRAPH=true` → `LangGraphOrchestrator` (default, LLM-enhanced)
- `USE_LANGGRAPH=false` → `IncidentOrchestrator` (legacy, rule-based)

### `agent/config.py`

```python
@dataclass
class AgentConfig:
    agent_id: str = "incident-orchestrator-v1"
    regional_contacts: RegionalContacts
    retry_policy: RetryPolicyConfig       # max 3 attempts, 10s backoff
    voip: VoIPConfig                      # VoIP provider settings
    fcm: FCMConfig                        # Firebase push settings
    policy: PolicyConfig                  # risk thresholds
    log_level: str = "INFO"
    audit_retention_days: int = 365
    max_actions_per_minute: int = 60
    max_calls_per_minute: int = 10
```

### `agent/models.py` — Key Schemas

```python
class IncidentInput(BaseModel):
    incident_id: str
    vlm_summary: VLMSummary
    enhanced_report: EnhancedReportData
    location: Optional[Location]          # { lat, lon }
    history: List[HistoricalIncident]

class VLMSummary(BaseModel):
    confidence: float                     # 0.0–1.0
    incident_type: str
    description: Optional[str]
    vehicles_involved: Optional[int]
    recommended_alerts: List[str]         # ["sms", "call", "notify"]
    ambiguous: bool = False

class EnhancedReportData(BaseModel):
    report_text: str
    risk_score: int                       # 1–10
    executive_summary: Optional[str]
    evidence_mapping: Optional[dict]

class ActionPlanItem(BaseModel):
    action_id: str
    type: ActionType                      # call | sms | notify
    target_role: str                      # police | ambulance | traffic_control
    number: str
    text: Optional[str]                   # SMS content or spoken message
    status: ActionStatus                  # pending | sent | acknowledged | failed | escalated
    attempts: int = 0
    retry_policy: RetryPolicy
    last_result: Optional[dict]

class FinalStatus(Enum):
    DISPATCHED        = "dispatched"
    ESCALATED         = "escalated"
    QUEUED_FOR_REVIEW = "queued_for_review"
    LOGGED_ONLY       = "logged_only"
```

### `agent/policies.py` — PolicyEngine

```python
class PolicyDecision:
    should_auto_action: bool
    should_queue_for_review: bool
    should_log_only: bool
    is_ambiguous: bool
    reason: str
    final_status: FinalStatus

class PolicyEngine:
    def evaluate_action_gating(self, incident: IncidentInput) -> PolicyDecision
    # Applies rules in order:
    # 1. Ambiguity check (any ambiguous keywords → QUEUED_FOR_REVIEW)
    # 2. Auto-action: risk >= 7 OR (confidence >= 0.85 AND call/sms recommended)
    # 3. Queue: risk 4-6
    # 4. Log only: risk < 4
```

### `agent/actions.py` — ActionExecutor

```python
class ActionExecutor:
    def __init__(self, config: AgentConfig, device_manager=None)

    async def execute_action_plan(
        self,
        action_plan: List[ActionPlanItem],
        agent_id: str
    ) -> Tuple[List[ActionPlanItem], List[AuditEntry]]

    # Internally:
    async def _execute_sms(action, agent_id) → sends via mobile device WebSocket
    async def _execute_call(action, agent_id) → GSM via mobile or VoIP fallback
    async def _execute_notify(action, agent_id) → FCM push notification

class DeviceManager:
    def register_device(self, device: DeviceInfo)
    def get_device(self, device_id: str) -> Optional[DeviceInfo]
    def verify_phone_number(self, device_id: str, phone_number: str) -> bool
    def handle_mobile_callback(self, callback: MobileCallback) -> bool
    def handle_voip_callback(self, callback: VoIPCallbackPayload) -> dict
```

### `agent/langgraph_orchestrator.py` — LangGraph Workflow

**State:** `IncidentState` (TypedDict) — carries all data through the graph:
- `incident_id`, `vlm_summary`, `enhanced_report`, `location`, `history`
- `messages` (LLM conversation, append-only via `Annotated[List, add]`)
- `policy_decision`, `risk_assessment`, `llm_reasoning`
- `action_plan`, `executed_actions`, `failed_actions`, `needs_retry`
- `final_status`, `audit_trail` (append-only), `operator_message`

**Graph:** `StateGraph(IncidentState)` compiled with `MemorySaver` checkpointing.
- Entry: `analyze`
- Edges: `analyze` → `policy` → (conditional) → `build_plan` / `queue` / `finalize`
- `build_plan` → `execute` → `monitor` → (conditional: retry or `finalize`)
- `queue` → END, `finalize` → END

---

## 10. Frontend — React Web Dashboard

**Start:** `cd frontend && npm run dev` → `http://localhost:5173`

### Pages

| Page | Route | Description |
|---|---|---|
| Dashboard | `/` | System overview, active jobs, recent detections |
| Upload | `/upload` | Drag-and-drop video upload with progress |
| Jobs | `/jobs` | List of all analysis jobs with status |
| Job Detail | `/jobs/:id` | Full analysis result, video playback, observations |
| Live Stream | `/stream` | Connect a stream URL, watch annotated 30fps feed |
| Settings | `/settings` | Server URL, configuration |

### Components

| Component | Purpose |
|---|---|
| `VideoPlayer` | Plays the annotated processed video |
| `EnhancedReport` | Renders the structured Ollama-generated report |
| `FramePreview` | Shows specific frames from the analysis |
| `ProgressBar` | Displays real-time analysis progress |
| `StatusIndicator` | Badge showing job/stream state |
| `ReportTabs` | Tabbed view for different report sections |
| `NotificationDropdown` | Toast alerts for new incidents |
| `Sidebar` + `Header` | Application chrome |

### Services

`frontend/src/services/api.ts` — All API calls using Axios:
- `uploadVideo(file, onProgress)` — multipart upload with progress callback
- `getJob(jobId)` — polling job status
- `getJobResult(jobId)` — final analysis result
- `listJobs()` — all jobs
- `getConfig()` — server configuration
- `getHealth()` — health check

WebSocket connection logic is implemented inline in relevant page components using the
native browser `WebSocket` API.

---

## 11. Mobile App — Flutter

**Purpose:** Act as a GSM relay between the BI3 server and the physical phone network.
The server cannot make phone calls or send SMS directly — the Flutter app bridges this gap.

### Architecture

```
BI3 Server
    │
    │  WebSocket command: { type: "sms_action", number, text }
    ▼
Flutter AgentService
    │
    ├── WebSocketService (auto-reconnect, heartbeat, message routing)
    │
    ├── NativeTelephonyService (Platform Channel: com.bi3.incident_agent/telephony)
    │   │
    │   └── Android Native (MethodChannel implementation)
    │       ├── makeCall(phoneNumber) → TelecomManager / Intent.ACTION_CALL
    │       ├── sendSMS(phoneNumber, message) → SmsManager.sendTextMessage()
    │       ├── requestPermissions() → CALL_PHONE + SEND_SMS + READ_PHONE_STATE
    │       └── Callbacks: onCallStateChanged, onSMSSent
    │
    ├── TtsService (flutter_tts) → speaks incident details aloud as alert
    ├── CallService → high-level call abstraction
    ├── SmsService → high-level SMS abstraction
    ├── ApiService → REST calls to BI3 server (/v1/devices/register, etc.)
    └── LoggerService → in-app log display (visible in Logs screen)
```

### Screens

| Screen | Description |
|---|---|
| `HomeScreen` | Dashboard showing connection status, active incident, quick actions |
| `IncidentDetailScreen` | Full incident details: type, risk, observations, actions taken |
| `LogsScreen` | Live scrolling log of all agent activity |
| `SettingsScreen` | Server URL, device phone number, preferences |

### Initialization Flow

```
main() → NativeTelephonyService.requestPermissions() → runApp()
         ↓
IncidentAgentApp → MultiProvider setup (LoggerService, AgentService)
         ↓
HomeScreen._initializeAgent()
         ↓
AgentService.initialize()
  • Get/create device UUID (SharedPreferences)
  • Load server URL from preferences
  • Load phone number from PhoneService
  • Initialize all sub-services
  • Register with server: POST /v1/devices/register
  ↓
AgentService.connect()
  • WebSocketService.connect(ws://{server}/ws/device/{device_id})
  • Heartbeat every 30s
  • Auto-reconnect on disconnect (exponential backoff)
```

### Message Handling

When a WebSocket message arrives:
```dart
_handleMessage(data)
  ├── type == "action_plan"    → store + notify UI
  ├── type == "sms_action"     → smsService.sendSms(number, text)
  │                               → NativeTelephonyService.sendSMS()
  │                               → Android SmsManager
  ├── type == "call_command"   → callService.makeCall(number)
  │                               → NativeTelephonyService.makeCall()
  │                               → Android TelecomManager
  └── type == "heartbeat"      → send ack
```

---

## 12. Database Schema

### MongoDB Collections

#### `frames` collection

```json
{
  "_id": "ObjectId",
  "video_id": "string",
  "frame_number": 150,
  "timestamp_ms": 5000.0,
  "base64_encoded": "data:image/jpeg;base64,...",
  "width": 1280,
  "height": 720,
  "extracted_at": "2026-01-01T12:00:00"
}
```

#### `detections` collection

```json
{
  "_id": "ObjectId",
  "video_id": "string",
  "frame_number": 150,
  "timestamp_ms": 5000.0,
  "detections": [
    {
      "track_id": 42,
      "class_id": 2,
      "class_name": "car",
      "bbox": [100, 200, 300, 400],
      "confidence": 0.87,
      "color": [0, 255, 0]
    }
  ],
  "vehicle_count": 3
}
```

#### `analyses` collection

```json
{
  "_id": "ObjectId",
  "video_id": "string",
  "second_index": 5,
  "timestamp_start_ms": 5000.0,
  "timestamp_end_ms": 6000.0,
  "observations": [
    {
      "behavior_type": "speeding",
      "vehicle_id": "42",
      "confidence": "high",
      "evidence": "Rapid displacement across 3 frames",
      "risk_level": "critical",
      "description": "Vehicle 42 exceeding safe speed limits"
    }
  ],
  "risk_score": 7,
  "summary": "High-speed vehicle detected...",
  "recommended_alerts": ["sms", "call"],
  "processing_time_ms": 1850,
  "success": true,
  "stored_at": "2026-01-01T12:00:05"
}
```

#### Indexes

- `frames`: `{ video_id: 1 }`, `{ frame_number: 1 }`
- `detections`: `{ video_id: 1 }`, `{ frame_number: 1 }`
- `analyses`: `{ video_id: 1 }`, `{ second_index: 1 }`

---

## 13. Configuration Reference

All settings live in `config.py` and are loaded from the `.env` file.

### Environment Variables

```bash
# ─── VLM Provider Selection ───────────────────────────────────────────
VLM_PROVIDER=auto
# Options: "ollama" | "openrouter" | "auto"
# auto: tries Ollama first, falls back to OpenRouter

# ─── OpenRouter (Cloud VLM) ───────────────────────────────────────────
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_API_KEYS=key1,key2,key3        # Multi-key load balancing (optional)

# ─── Ollama (Local GPU) ───────────────────────────────────────────────
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_VISION_MODEL=gemma3:4b             # Vision model for stream VLM
OLLAMA_VISION_TIMEOUT=120
OLLAMA_MODEL=gemma3:1b                    # Text model for report generation
OLLAMA_TIMEOUT=120

# ─── MongoDB ──────────────────────────────────────────────────────────
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=video_analysis
MONGODB_COLLECTION=frames

# ─── VLM Concurrency ──────────────────────────────────────────────────
VLM_MAX_CONCURRENT=15                     # Semaphore limit for parallel requests
VLM_REQUEST_TIMEOUT=60                    # Seconds per request
VLM_RETRY_ATTEMPTS=2                      # Retry on failure

# ─── Live Stream Settings ─────────────────────────────────────────────
STREAM_VLM_SAMPLE_INTERVAL=3.0            # Seconds between VLM calls
STREAM_VLM_MIN_VEHICLES=2                 # Min vehicles to trigger VLM analysis
STREAM_WEBSOCKET_FPS=30                   # Broadcast frame rate to clients

# ─── Agent Feature Flag ───────────────────────────────────────────────
USE_LANGGRAPH=true                        # true: LangGraph | false: legacy rules
```

### Hardcoded Values in `config.py`

| Setting | Value | Purpose |
|---|---|---|
| `VLM_MODEL` | `qwen/qwen3-vl-8b-instruct` | Default OpenRouter model |
| `YOLO_MODEL_PATH` | `yolo11n.pt` | YOLO model file |
| `YOLO_CONFIDENCE` | `0.3` | Detection confidence threshold |
| `YOLO_IOU` | `0.5` | NMS IOU threshold |
| `FRAMES_PER_SECOND` | `3` | File analysis sampling rate |
| `SAMPLE_INTERVAL` | `10` | Extract 1 of every 10 frames |
| `STREAM_MAX_CONCURRENT` | `3` | Max simultaneous live streams |
| `STREAM_CONTEXT_WINDOW` | `6.0s` | History for VLM context |

---

## 14. API Reference

### Health & Config

| Method | Endpoint | Response |
|---|---|---|
| GET | `/` | `{ status, service, version }` |
| GET | `/health` | `{ status: "healthy" }` |
| GET | `/api/config` | `{ vlm_model, frames_per_second, mongodb_connected, ... }` |

### Video File Analysis

| Method | Endpoint | Body | Response |
|---|---|---|---|
| POST | `/api/upload` | `multipart/form-data: file` | `{ job_id, video_id, ws_url }` |
| POST | `/api/analyze` | `{ video_path: str }` | `{ job_id, video_id, ws_url }` |
| GET | `/api/video-info` | `?path=...` | `{ fps, total_frames, duration, ... }` |

### Job Management

| Method | Endpoint | Response |
|---|---|---|
| GET | `/api/jobs` | `{ jobs: [...], total: N }` |
| GET | `/api/jobs/{id}` | `AnalysisJob` (status, progress, created_at) |
| GET | `/api/jobs/{id}/result` | Observations, risk_score, summary |
| GET | `/api/jobs/{id}/enhanced-report` | Full Ollama-generated report |
| GET | `/api/jobs/{id}/video` | Streaming annotated video file |
| GET | `/api/jobs/{id}/frame/{second}` | JPEG preview of frame at second N |

### Live Stream

| Method | Endpoint | Body | Response |
|---|---|---|---|
| POST | `/api/stream/start` | `{ stream_id, url, quality }` | `{ stream_id, state, title, fps }` |
| POST | `/api/stream/stop` | `{ stream_id }` | `{ status: "stopped" }` |
| GET | `/api/stream/status/{id}` | — | Stream state + stats |
| GET | `/api/stream/live-yolo/{id}` | — | Latest JPEG frame (binary) |
| GET | `/api/stream/live-vlm/{id}` | — | Latest VLM analysis JSON |
| GET | `/api/stream/live-reports/{id}` | — | List of accumulated VLM reports |
| GET | `/api/stream/list` | — | All active streams |

### WebSocket Endpoints

| Endpoint | Description |
|---|---|
| `WS /ws/{job_id}` | Subscribe to video analysis progress and result |
| `WS /ws/stream/{stream_id}` | Subscribe to 30fps annotated live stream + VLM events |
| `WS /ws/device/{device_id}` | Flutter mobile device registration and command channel |

### Incident Agent (`/v1/...`)

| Method | Endpoint | Body | Response |
|---|---|---|---|
| POST | `/v1/incidents` | `IncidentInput` | `OrchestratorOutput` (action_result + api_spec) |
| GET | `/v1/incidents/{id}` | — | Incident state + action plan + audit |
| POST | `/v1/incidents/{id}/override` | `ManualOverrideRequest` | Updated status |
| POST | `/v1/devices/register` | `DeviceRegisterRequest` | `{ device_id, status }` |
| POST | `/v1/devices/{id}/callback` | `MobileCallback` | `{ processed: bool }` |
| POST | `/v1/devices/{id}/voip-callback` | `VoIPCallbackPayload` | `{ action_id, status }` |
| POST | `/v1/agent/decide` | `AgentDecisionRequest` | Decision result |

### Request/Response Examples

**Start Live Stream:**
```json
POST /api/stream/start
{
  "stream_id": "my-stream-01",
  "url": "https://www.youtube.com/watch?v=...",
  "quality": "720p"
}
```

**Submit Incident:**
```json
POST /v1/incidents
{
  "incident_id": "inc-uuid-here",
  "vlm_summary": {
    "confidence": 0.91,
    "incident_type": "Traffic Safety Violation",
    "description": "Vehicle speeding through intersection",
    "vehicles_involved": 3,
    "recommended_alerts": ["sms"],
    "ambiguous": false
  },
  "enhanced_report": {
    "report_text": "Full report text...",
    "risk_score": 8,
    "executive_summary": "Critical speeding event detected"
  },
  "location": { "lat": 13.0827, "lon": 80.2707 }
}
```

**OrchestratorOutput Response:**
```json
{
  "action_result": {
    "incident_id": "inc-uuid-here",
    "final_status": "dispatched",
    "action_plan": [
      {
        "action_id": "sms-police-inc-uuid",
        "type": "sms",
        "target_role": "police",
        "number": "+919535879330",
        "text": "🚨 POLICE ALERT\nType: Traffic Safety Violation\n...",
        "status": "sent",
        "attempts": 1
      }
    ],
    "audit": [
      { "ts": "2026-01-01T12:00:00Z", "actor": "langgraph-orchestrator",
        "step": "LLM Analysis", "outcome": "Severity: critical, Urgency: immediate" },
      { "ts": "2026-01-01T12:00:01Z", "step": "Policy Decision",
        "outcome": "Auto-dispatch: risk 8, confidence 0.91, critical severity" },
      { "ts": "2026-01-01T12:00:02Z", "step": "SMS sent successfully",
        "outcome": "Message ID: a1b2c3d4" }
    ]
  },
  "api_spec": { "openapi": "3.0.3", "info": { ... } }
}
```

---

## 15. Installation & Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- MongoDB (local or Atlas)
- Ollama with `gemma3:1b` and `gemma3:4b` installed (`ollama pull gemma3:1b`)
- YOLO11n model file (`yolo11n.pt` — auto-downloaded by Ultralytics on first run)
- OpenRouter API key (for cloud VLM) — optional if using Ollama only

### Backend Setup

```bash
# 1. Clone and enter project directory
cd bi3

# 2. Install Python dependencies
pip install fastapi uvicorn aiohttp pymongo python-dotenv pillow
pip install ultralytics opencv-python yt-dlp
pip install -r requirements-langgraph.txt  # LangGraph, LangChain, LangChain-Ollama

# 3. Configure environment
cp .env.example .env
# Edit .env with your API keys and settings

# 4. Start MongoDB (if not already running)
mongod --dbpath /data/db

# 5. Start Ollama and pull models
ollama serve
ollama pull gemma3:1b
ollama pull gemma3:4b    # For vision analysis (if VLM_PROVIDER=ollama)

# 6. Start the server
python server.py
# Server starts on http://0.0.0.0:8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
# Dev server: http://localhost:5173

# Build for production:
npm run build
```

### Mobile App Setup

```bash
cd mobile
flutter pub get

# Run on connected Android device (required for native telephony)
flutter run

# Build release APK
flutter build apk --release
```

### Mobile App Configuration

1. Open app → Settings
2. Enter BI3 server URL (e.g., `http://192.168.1.x:8000`)
3. Enter device phone number (used for SMS routing)
4. Grant permissions when prompted: `CALL_PHONE`, `SEND_SMS`, `READ_PHONE_STATE`
5. App connects to server and registers as a device
6. Connection status shown in top-right corner of home screen

---

## 16. Performance Characteristics

### Video File Analysis

Processing time scales with `VLM_MAX_CONCURRENT`:

| Concurrency | 7-second video | 60-second video | Notes |
|---|---|---|---|
| 4 (conservative) | ~21s | ~180s | Safest for rate limits |
| 10 (default) | ~9s | ~77s | 2.3× faster |
| 15 (current default) | ~6s | ~52s | 3.5× faster |
| 20 (aggressive) | ~5s | ~42s | Check API limits |

### Live Stream

| Component | Metric |
|---|---|
| YOLO inference | 15–25ms per frame (RTX 4050) |
| Broadcast latency | < 50ms end-to-end |
| Broadcast frame rate | 30 FPS |
| VLM analysis interval | Every 3 seconds |
| Frame buffer | 90 frames (~3s at 30fps) |
| Max concurrent streams | 3 |

### Memory & Storage

| Item | Approximate Size |
|---|---|
| YOLO11n model | ~6 MB |
| Gemma3:1b (Ollama) | ~800 MB RAM |
| Gemma3:4b (Ollama) | ~3.2 GB RAM |
| MongoDB per frame | ~150–300 KB (with base64) |
| JPEG annotated frame (WebSocket) | ~30–50 KB |

---

## 17. Data Models & Schemas

### Pydantic Models (server.py)

```python
class AnalysisJob:
    job_id: str
    video_id: str
    video_name: str
    status: str          # pending | processing | completed | failed
    progress: float      # 0.0 to 1.0
    created_at: str
    completed_at: Optional[str]
    error: Optional[str]
    result: Optional[dict]

class UploadResponse:
    job_id: str
    video_id: str
    message: str
    ws_url: str

class VideoInfo:
    path: str
    fps: float
    total_frames: int
    duration_seconds: float
    width: int
    height: int
    sample_interval: int
    frames_per_second_sampled: int

class BehaviorObservationResponse:
    behavior_type: str
    vehicle_id: str
    confidence: str
    evidence: str
    risk_level: str
    description: str
```

### Stream Models

```python
class StreamStartRequest:
    stream_id: str
    url: str
    quality: str = "720p"

class StreamStatusResponse:
    stream_id: str
    state: str
    title: str
    is_live: bool
    fps: float
    resolution: str
    batch_count: int
    total_frames: int
    error: Optional[str]
```

---

## 18. Security & Policies

### Action Gating

The system never auto-dispatches emergency calls without meeting strict criteria:

```
Dispatch criteria (ALL must be true for calls):
  risk_score >= 7
  AND confidence >= 0.85
  AND recommended_alerts includes "call" or "sms"
  AND incident is NOT ambiguous

Automatic block conditions:
  - Any ambiguous keywords in VLM output → ESCALATED (never auto-dispatch)
  - risk_score < 4 → LOG_ONLY (no notification sent)
  - risk_score 4-6 → QUEUED_FOR_REVIEW (operator must approve)
```

### Anti-Hallucination

The VLM system prompt explicitly instructs:
- Never report a collision unless actual physical impact is visible
- Close vehicle proximity in urban/toll/parking contexts is NOT an incident
- Use `"ambiguous – no confirmed collision"` when uncertain
- Only report behaviors supported by visible evidence

### Rate Limiting

- Max 60 actions per minute per agent instance
- Max 10 calls per minute per agent instance
- Max 15 concurrent VLM API requests (configurable)
- Max 3 concurrent live streams per server instance

### Audit Trail

Every incident is fully audited:
- Every LLM call and its output
- Every policy decision with reasoning
- Every action attempt with timestamp and result
- Stored in agent's in-memory incident store (production: should be persisted to MongoDB)
- Retention: 365 days (configurable)

### Operator Override

Any auto-dispatched action can be overridden via:
```
POST /v1/incidents/{id}/override
{ action: "approve|reject|escalate|cancel", reason: "...", operator_id: "..." }
```

### Device Authentication

Mobile devices authenticate with:
- `device_id` (UUID, generated on first app launch)
- `device_api_key` (per-device secret, sent on registration)
- Phone number verification (optional but recommended)

---

*Documentation generated from full codebase analysis of BI3 Smart Traffic Safety Platform.*
*Last updated: March 2026*
