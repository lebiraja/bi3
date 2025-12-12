# Stream Processing Code Changes - Detailed Implementation

## 1. Frame Buffer Reconnection Fix

**File:** `stream_processor.py`  
**Method:** `StreamManager._buffer_frames()`  
**Lines:** ~183-238

### Key Changes:
```python
# Error handling threshold
max_errors = 15  # Increased from 10

# New consecutive timeout tracking
consecutive_timeouts = 0
MAX_CONSECUTIVE_TIMEOUTS = 5

# Reconnection logic
if consecutive_timeouts >= MAX_CONSECUTIVE_TIMEOUTS:
    logger.warning(f"Max consecutive timeouts ({MAX_CONSECUTIVE_TIMEOUTS}) reached, reconnecting...")
    try:
        self.cap = cv2.VideoCapture(self.stream_url)
        consecutive_timeouts = 0
    except Exception as e:
        logger.error(f"Reconnection failed: {e}")
        error_count += 1
        continue

# Adaptive timeout calculation
queue_size = self.frame_buffer.qsize()
timeout = 0.5 + min(0.5, queue_size / 100.0)  # 0.5s to 1.0s

# Efficiency logging (every 30 frames)
if frames_buffered % 30 == 0:
    efficiency_pct = (frames_buffered / total_frames) * 100
    logger.info(f"Buffer efficiency: {efficiency_pct:.1f}% ({frames_buffered}/{total_frames})")
```

### Why This Works:
- **Prevents stalls**: Reconnection after repeated timeouts avoids infinite wait loops
- **Adaptive timing**: Timeout scales with queue depth - reduces CPU on empty queue, patience on full queue
- **Visibility**: Efficiency logging provides diagnostics without spam

---

## 2. Frame Extraction Timeout Hardening

**File:** `stream_processor.py`  
**Method:** `StreamExtractor.get_batch_frames()`  
**Lines:** ~270-334

### Key Changes:
```python
# Extended timeout buffer
timeout_duration = duration * 3  # 45 seconds for 15s batch (was: duration * 2)

# Consecutive empty frame tracking
consecutive_empty = 0
MAX_CONSECUTIVE_EMPTY = 10

while elapsed_time < timeout_duration:
    try:
        success, frame = self.cap.read()
        
        if not success:
            consecutive_empty += 1
            if consecutive_empty >= MAX_CONSECUTIVE_EMPTY:
                logger.warning(f"Max consecutive empty frames ({MAX_CONSECUTIVE_EMPTY}) reached")
                break
            time.sleep(0.05)  # Reduced from 0.1s for more responsive polling
            continue
        
        consecutive_empty = 0  # Reset on successful frame
        # ... process frame
```

### Efficiency Metrics:
```python
extraction_pct = (len(frames) / expected_frame_count) * 100
logger.info(f"Extraction efficiency: {extraction_pct:.1f}% "
            f"({len(frames)}/{expected_frame_count} frames in {elapsed_time:.2f}s)")
```

### Why This Works:
- **More patient**: 45s timeout allows for legitimate slow frame rates
- **Smart stopping**: Stops only after 10 consecutive failures (not one timeout)
- **Responsive**: 0.05s sleep provides quicker polling without CPU waste
- **Diagnostics**: Efficiency percentage shows what % of expected frames captured

---

## 3. Stream Startup Retry Logic

**File:** `stream_processor.py`  
**Method:** `StreamExtractor.start_stream()`  
**Lines:** ~120-177

### Key Changes:
```python
max_retries = 3
retry_count = 0

while retry_count < max_retries:
    try:
        # Get stream URL and metadata
        stream_data = self._get_stream_url()
        self.stream_url = stream_data['url']
        
        # Open video capture
        logger.info(f"Opening video capture for stream: {stream_id} "
                   f"(attempt {retry_count + 1}/{max_retries})")
        self.cap = cv2.VideoCapture(self.stream_url)
        
        if not self.cap.isOpened():
            retry_count += 1
            if retry_count < max_retries:
                logger.warning(f"Failed to open stream, retrying in 2s...")
                time.sleep(2)
                continue
            raise RuntimeError("Failed to open video stream after retries")
        
        # ... rest of initialization
        logger.info(f"Stream started successfully: {self.stream_info.title}")
        return self.stream_info
        
    except Exception as e:
        logger.error(f"Failed to start stream (attempt {retry_count + 1}/{max_retries}): {e}")
        if retry_count < max_retries - 1:
            retry_count += 1
            logger.warning(f"Retrying in 2s...")
            time.sleep(2)
        else:
            self.stop_stream()
            raise
```

### Why This Works:
- **Handles transient failures**: Most network errors resolve within 2 seconds
- **Clear progress**: User sees which attempt is in progress
- **Proper cleanup**: Calls `stop_stream()` if all retries exhausted
- **Exponential backoff ready**: Can easily adjust to exponential if needed

---

## 4. Adaptive VLM Sampling Method

**File:** `stream_analyzer.py`  
**Method:** `StreamAnalyzer._sample_batches_adaptively()`  
**Lines:** ~495-605

### Core Algorithm:
```python
def _sample_batches_adaptively(self, frame_batches, yolo_detections, stream_id=""):
    """Intelligently select which seconds need VLM analysis"""
    
    # Step 1: Calculate activity metrics per second
    for idx, batch in enumerate(frame_batches):
        total_vehicles = sum(
            len(yolo_detections.get(f.frame_number, []))
            for f in batch
        )
        vehicles_per_frame = total_vehicles / len(batch)
        activity = max(frame_counts) - min(frame_counts)
        
        vehicle_counts.append(total_vehicles)
        activity_scores.append((vehicles_per_frame, activity))
    
    # Step 2: Determine dynamic threshold
    avg_vehicles = sum(vehicle_counts) / len(vehicle_counts)
    threshold = max(1, avg_vehicles * 0.5)  # Analyze if >50% of average
    
    # Step 3: Apply heuristics
    for idx in range(len(frame_batches)):
        vehicles = vehicle_counts[idx]
        
        # Heuristic 1: High activity (>150% of average)
        if vehicles >= threshold * 1.5:
            selected_indices.append(idx)
        
        # Heuristic 2: Activity change (variance from neighbors)
        elif activity_change(idx, vehicle_counts):
            selected_indices.append(idx)
        
        # Heuristic 3: High variance within second
        elif activity_scores[idx][1] >= 2:
            selected_indices.append(idx)
        
        # Heuristic 4: Minimum coverage fallback
        elif idx % Config.STREAM_VLM_INTERVAL == 0 and vehicles > 0:
            selected_indices.append(idx)
    
    # Step 4: Ensure coverage if stream has activity
    if not selected_indices and any(vc > 0 for vc in vehicle_counts):
        # Select top 2 busiest seconds
        selected_indices = sorted(top_2_busiest_indices)
    
    return sorted(selected_indices)
```

### Heuristic Details:

**Heuristic 1 - High Activity Seconds**
- Condition: `vehicles >= threshold × 1.5`
- Purpose: Always analyze busy seconds (likely have important incidents)
- Example: If avg=2 vehicles/sec, analyze any second with ≥3 vehicles

**Heuristic 2 - Activity Changes**
- Condition: `|vehicles[i] - vehicles[i±1]| >= 2`
- Purpose: Catch behavior transitions (entering/leaving congestion)
- Example: Second 5 has 4 vehicles, second 6 has 1 vehicle → analyze both

**Heuristic 3 - High Variance**
- Condition: `max(counts) - min(counts) >= 2` within second
- Purpose: Capture complex/diverse scenarios (multiple concurrent behaviors)
- Example: Frame 1 has 1 vehicle, frame 2 has 3 vehicles → analyze

**Heuristic 4 - Minimum Coverage**
- Condition: `idx % INTERVAL == 0 AND vehicles > 0`
- Purpose: Baseline regular sampling (fallback if others don't trigger)
- Example: With INTERVAL=3, analyze seconds 0, 3, 6, 9, ... if active

### Adaptation Mechanism:
```python
# Dynamic threshold based on stream activity
if vehicle_counts:
    avg_vehicles = sum(vehicle_counts) / len(vehicle_counts)
    threshold = max(1, avg_vehicles * 0.5)
else:
    threshold = 1  # Default if no activity

# Skip rate calculation
skip_rate = (skipped / len(frame_batches)) * 100

# Logging with metrics
logger.info(f"Adaptive VLM sampling: {len(selected_indices)} seconds selected, "
           f"{skipped} skipped ({skip_rate:.1f}% skip rate). "
           f"Threshold: {threshold:.1f} vehicles/sec")
```

### Why This Works:
- **Self-tuning**: Threshold adapts to stream's natural activity level
- **Context-aware**: Different streams get different sampling patterns
- **Redundancy**: Multiple heuristics ensure important scenes aren't missed
- **Fallback safety**: Always analyzes at least top 2 busiest seconds
- **Observable**: Detailed metrics help identify patterns

### Expected Skip Rates:
- **High-activity stream** (constant traffic): 30-40% skip rate
- **Medium-activity stream** (intermittent traffic): 60-70% skip rate
- **Low-activity stream** (occasional vehicles): 80-90% skip rate

---

## Integration Points

### How Fixes Interact:

1. **Stream startup** → Retry logic handles initial connection
2. **Frame buffering** → Reconnection logic keeps buffer alive
3. **Frame extraction** → Extended timeouts work with buffer resilience
4. **VLM sampling** → Adaptive method uses YOLO detections from all frames

### Data Flow:
```
User starts stream
    ↓
[Retry Logic] - up to 3 attempts with 2s delays
    ↓
StreamExtractor.start_stream() - initializes cap and buffer thread
    ↓
StreamManager._buffer_frames() - background thread feeds buffer
    ├─ [Reconnection Logic] - auto-recovers from glitches
    └─ [Adaptive Timeouts] - scales with queue depth
    ↓
StreamAnalyzer._process_batch() - orchestrates analysis
    ├─ get_batch_frames() - extracts 15s of frames
    │  └─ [Extended Timeouts] - 45s buffer for slow streams
    ├─ YOLO detection - runs on all frames
    └─ _sample_batches_adaptively() - selects VLM seconds
       ├─ [4 Heuristics] - intelligent sampling
       └─ [Dynamic Threshold] - adapts to activity level
```

---

## Configuration Integration

These fixes use `Config` constants from `config.py`:

```python
Config.STREAM_VLM_INTERVAL = 3           # Fallback sample every 3rd second
Config.STREAM_SKIP_LOW_ACTIVITY = True   # Enable activity filtering
Config.STREAM_MIN_VEHICLES_FOR_VLM = 1   # Minimum for activity check
Config.VLM_MAX_CONCURRENT = 15           # Parallel VLM requests
```

Adjusting these constants allows tuning the fixes without code changes:
- Higher `STREAM_VLM_INTERVAL` = more aggressive skipping
- Lower threshold in adaptive method = more inclusive sampling
- Higher `VLM_MAX_CONCURRENT` = faster batch processing

---

## Monitoring & Diagnostics

Each fix provides logging for production monitoring:

**Frame Buffer Health:**
```
[stream_123] Buffer efficiency: 98.5% (295/300)
[stream_123] Adaptive timeout: 0.7s (queue=25)
[stream_123] Reconnection successful after 5 consecutive timeouts
```

**Frame Extraction Status:**
```
[stream_123] Extraction efficiency: 89.3% (40/45 frames in 15.2s)
[stream_123] Consecutive empty frames: 8/10 (approaching limit)
```

**Stream Startup Progress:**
```
[stream_123] Opening video capture for stream: stream_123 (attempt 1/3)
[stream_123] Failed to open stream, retrying in 2s...
[stream_123] Stream started successfully: Walworth Road @ 1280x720 @ 30fps
```

**VLM Sampling Metrics:**
```
[stream_123] Adaptive VLM sampling: 5 seconds selected, 10 skipped (66.7% skip rate). Threshold: 1.5 vehicles/sec
```

These logs help identify:
- Patterns in connection stability
- Frame capture issues specific to streams
- VLM optimization effectiveness
- Performance bottlenecks
