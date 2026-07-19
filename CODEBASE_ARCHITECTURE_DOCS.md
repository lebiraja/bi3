# Codebase Architecture & Flow Documentation

This document provides a detailed overview of the video analysis pipeline architecture, including ASCII diagrams of the system structure and the data flow.

## 1. System Architecture Diagram

```text
+-------------------+       +-------------------+
|                   |       |                   |
|  React Frontend   |       |  Flutter Mobile   |
|   (Web UI)        |       |    (App UI)       |
|                   |       |                   |
+--------+----------+       +---------+---------+
         |                            |
         | HTTP/REST & WebSocket      | HTTP/REST & WebSocket
         v                            v
+-------------------------------------------------------------+
|                                                             |
|                     FastAPI Backend                         |
|                      (server.py)                            |
|                                                             |
|  +----------------+  +----------------+  +---------------+  |
|  |                |  |                |  |               |  |
|  | WS Connections |  |   REST APIs    |  | Job & Stream  |  |
|  |   Manager      |  |                |  |   Manager     |  |
|  +----------------+  +-------+--------+  +-------+-------+  |
|                              |                   |          |
+------------------------------|-------------------|----------+
                               v                   v
+-------------------------------------------------------------+
|                                                             |
|                  Video / Stream Processing                  |
|                                                             |
|  +---------------+   +-----------------------------------+  |
|  | FrameSampler /|-->| YOLODetector (video_analyzer.py)  |  |
|  | StreamExtract |   | - Detects vehicles (cars, trucks) |  |
|  +---------------+   +-----------------+-----------------+  |
|          |                             |                    |
|          v                             v                    |
|  +-------------------------------------------------------+  |
|  |               BehaviorAnalyzer                        |  |
|  | - Batches frames (3/sec)                              |  |
|  | - Merges YOLO data with frames                        |  |
|  | - Orchestrates parallel requests                      |  |
|  +-----------------------+-------------------------------+  |
|                          |                                  |
|                          v                                  |
|  +-------------------------------------------------------+  |
|  |                 VLMClient                             |  |
|  | - Handles API requests to OpenRouter (Qwen-VL etc.)   |  |
|  | - Implements connection pooling and retries           |  |
|  +-------------------------------------------------------+  |
+-------------------------------------------------------------+
           |                                     |
           v                                     v
+-----------------------+               +---------------------+
|                       |               |                     |
|    MongoDB Database   |               | External API (VLM)  |
|  (Stores jobs, frames,|               |    (OpenRouter)     |
|   detections, results)|               |                     |
+-----------------------+               +---------------------+
```

## 2. Process Flow Diagram

```text
User / Client                      Backend Services                     External Systems
      |                                   |                                   |
      | 1. Upload Video or Start Stream   |                                   |
      |---------------------------------->|                                   |
      |                                   |                                   |
      | 2. Connect to WebSocket           |                                   |
      |---------------------------------->|                                   |
      |                                   | 3. Extract Frames                 |
      |                                   | (FrameSampler/StreamExtractor)    |
      |                                   |------------------+                |
      |                                   |                  v                |
      |                                   | 4. Run YOLO Detection             |
      |                                   | (Identifies vehicles & bounds)    |
      |                                   |------------------+                |
      |                                   |                  v                |
      |                                   | 5. Group Frames + YOLO Context    |
      |                                   | (BehaviorAnalyzer)                |
      |                                   |------------------+                |
      |                                   |                  |                |
      |                                   | 6. Parallel VLM API Calls         |
      |                                   |---------------------------------->|
      |                                   |                                   |
      |                                   | 7. Return Risk & Behaviors        |
      |                                   |<----------------------------------|
      |                                   |                                   |
      | 8. Send WS Progress/Results       |                                   |
      |<----------------------------------|                                   |
      |                                   | 9. Save to MongoDB                |
      |                                   |------------------+                |
      |                                   |                  v                |
      | 10. Fetch Final Report/Summary    |                                   |
      |<----------------------------------|                                   |
      |                                   |                                   |
```

## 3. Detailed Component Documentation

### 3.1. Client Applications
- **Frontend (React/Vite)**: A web-based application (TypeScript, Tailwind) found in the `frontend/` directory. Provides users with an interface to upload videos, view real-time analyses via WebSockets, and check historical reports.
- **Mobile (Flutter)**: A cross-platform mobile application found in the `mobile/` directory, allowing users to access the same analysis features from their smartphones.

### 3.2. Core Backend (FastAPI)
- **`server.py`**: The primary entry point. Defines REST endpoints (for upload, status checks) and WebSocket routes (for real-time progress updates). Manages connection states for both mobile devices and web clients.
- **`config.py`**: Centralizes configuration, reading from `.env` (MongoDB URIs, API keys, YOLO confidence thresholds, VLM concurrency settings).

### 3.3. Video & Stream Processing
- **`frame_sampler.py` / `stream_processor.py`**: Responsible for taking a static video file or a live stream URL (like YouTube) and extracting frames at a specific interval (e.g., 3 frames per second) for analysis.
- **`video_analyzer.py`**: The main orchestrator for static videos. It uses the `YOLODetector` class to run local object detection (using `ultralytics` models) on the extracted frames, drawing bounding boxes and identifying vehicle types (car, truck, etc.).

### 3.4. AI Behavior Analysis
- **`behavior_analyzer.py`**: Operates on batches of frames (typically 1 second of video = 3 frames). It aggregates YOLO bounding box data and sends this context, along with base64 encoded frames, to to the VLM via parallel execution.
- **`vlm_client.py` & `hybrid_vlm_client.py`**: Handles external API interactions (mostly OpenRouter, but potentially local Ollama as a fallback). It batches API requests with an optimal concurrency limit to achieve 2x-4x speed improvements over sequential processing, while handling timeouts and retries.

### 3.5. Data Storage
- **`mongodb_handler.py`**: Manages all persistence. It stores job metadata, sampled frame references, YOLO detections, and final AI assessments to allow historical querying and reporting.

## 4. Summary of the Pipeline
1. **Ingestion**: Video is uploaded or stream URL is provided.
2. **Decoding**: Video is split into a set of frames.
3. **Local AI**: YOLO detects vehicles and generates bounding boxes locally to save time and API costs.
4. **Cloud AI**: Frames combined with YOLO metadata are sent concurrently to a Vision-Language Model.
5. **Aggregation**: Results are stitched together chronologically to assess behavioral risk levels over time.
6. **Reporting**: Real-time progress is streamed via WebSocket to the frontend/mobile apps, while final data is written to MongoDB.
