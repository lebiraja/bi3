# Video Analysis Pipeline - YOLO + Vision-Language Model

Real-time video behavior analysis system using YOLO object detection and Vision-Language Models (VLM) for intelligent vehicle behavior assessment.

## 🚀 Features

- **YOLO Vehicle Detection**: Real-time vehicle tracking (cars, motorcycles, buses, trucks)
- **VLM Behavior Analysis**: AI-powered behavioral analysis using Vision-Language Models
- **Parallel Processing**: Optimized concurrent VLM requests for 2-4x faster processing
- **Real-time WebSocket Updates**: Live progress tracking and frame previews
- **MongoDB Storage**: Persistent storage for analysis results
- **React Frontend**: Modern web interface with video playback and visualizations

## ⚡ Performance

| VLM Concurrency | Processing Time (7s video) | Speed Improvement |
|-----------------|----------------------------|-------------------|
| 4 requests (old) | ~21 seconds | Baseline |
| **10 requests (new default)** | **~9 seconds** | **2.3x faster** |
| 20 requests | ~5 seconds | 4.2x faster |

*Configure via `VLM_MAX_CONCURRENT` in `.env`*

## 📁 Files in this workspace:
- `server.py` - FastAPI backend with WebSocket support
- `video_analyzer.py` - YOLO detection pipeline
- `behavior_analyzer.py` - Parallel VLM analysis orchestrator
- `vlm_client.py` - OpenRouter API client with connection pooling
- `frame_sampler.py` - Video frame extraction
- `video_processor.py` - YOLO annotation and encoding
- `config.py` - Configuration management
- `frontend/` - React + TypeScript web interface

## 🛠️ Installation

### Backend

```bash
# Install Python dependencies
pip install ultralytics fastapi uvicorn aiohttp pymongo python-dotenv pillow

# Or use requirements.txt if available
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

## ⚙️ Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` with your settings:
```env
# Required: OpenRouter API Key
OPENROUTER_API_KEY=sk-or-v1-your-api-key-here

# Optional: Performance tuning
VLM_MAX_CONCURRENT=10        # Concurrent VLM requests (higher = faster)
VLM_REQUEST_TIMEOUT=60       # Timeout per request in seconds
VLM_RETRY_ATTEMPTS=2         # Retry failed requests

# MongoDB (optional)
MONGODB_URI=mongodb://localhost:27017
```

### Performance Tuning Guidelines

**VLM_MAX_CONCURRENT** - Balance speed vs API limits:
- **Conservative (4-6)**: Safer for rate limits, slower processing
- **Balanced (8-10)**: Recommended default, 2-3x faster
- **Aggressive (15-20)**: Maximum speed, requires high API limits

## 🚀 Usage

### Start Backend Server

```bash
python server.py
```

### Start Frontend Development Server

```bash
cd frontend
npm run dev
```

Access the web interface at `http://localhost:5173`

### API Endpoints

- `POST /api/upload` - Upload video and start analysis
- `GET /api/jobs` - List all analysis jobs
- `GET /api/jobs/{id}` - Get job status
- `GET /api/jobs/{id}/video` - Stream annotated video
- `WS /ws/{job_id}` - Real-time progress updates

## 🏗️ Architecture

```
Frontend (React) → FastAPI → YOLO Detector → VLM Client (parallel) → OpenRouter API
                      ↓                           ↓
                  WebSocket                    MongoDB
```

See `ARCHITECTURE.md` for detailed system design.

## 🎯 Vehicle Classes (COCO dataset)
- Class 2: car
- Class 3: motorcycle
- Class 5: bus
- Class 7: truck

## 🔧 Tracker Options
- `bytetrack.yaml` - ByteTrack (default, good for crowded scenes)
- `botsort.yaml` - BoT-SORT (better for camera motion)

## 📊 Output
- Annotated videos saved in `processed/`
- Analysis results in MongoDB
- Real-time frame previews via WebSocket

## 🎨 Customization

### YOLO Parameters (`config.py`):
- `YOLO_CONFIDENCE`: Detection confidence threshold (default: 0.3)
- `YOLO_IOU`: IOU threshold for non-max suppression (default: 0.5)
- `FRAMES_PER_SECOND`: Frame sampling rate (default: 3)

### VLM Parameters:
- `VLM_MODEL`: Vision-Language model (default: qwen/qwen3-vl-8b-instruct)
- `VLM_MAX_CONCURRENT`: Parallel requests (default: 10)
- `VLM_REQUEST_TIMEOUT`: Request timeout (default: 60s)

## 📝 License

See LICENSE file for details.

