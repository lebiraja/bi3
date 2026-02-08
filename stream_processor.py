"""
Stream Processor Module.
Handles live stream ingestion from YouTube and other video URLs.
Extracts frames in real-time for YOLO and VLM analysis.
"""

import cv2
import logging
import subprocess
import threading
import time
import queue
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import yt_dlp

logger = logging.getLogger(__name__)


class StreamState(Enum):
    """Stream processing states."""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class StreamInfo:
    """Stream metadata."""
    stream_id: str
    url: str
    title: str
    duration: Optional[float]  # None for live streams
    fps: float
    width: int
    height: int
    is_live: bool
    format_id: str


class StreamExtractor:
    """
    Extracts frames from YouTube/stream URLs using yt-dlp and OpenCV.
    Handles both recorded videos and live streams.
    """
    
    def __init__(self, url: str, quality: str = "720p", timeout: int = 30):
        """
        Initialize stream extractor.
        
        Args:
            url: YouTube or stream URL
            quality: Preferred quality (720p, 480p, 360p)
            timeout: Connection timeout in seconds
        """
        self.url = url
        self.quality = quality
        self.timeout = timeout
        
        self.stream_url: Optional[str] = None
        self.stream_info: Optional[StreamInfo] = None
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running = False
        
        # Frame buffer for smooth extraction
        self.frame_buffer = queue.Queue(maxsize=90)  # ~3 seconds at 30fps
        self.buffer_thread: Optional[threading.Thread] = None
        
        logger.info(f"StreamExtractor initialized for URL: {url}")
    
    def _get_stream_url(self) -> Dict[str, Any]:
        """
        Extract direct stream URL using yt-dlp.
        
        Returns:
            Dictionary with stream URL and metadata
        """
        ydl_opts = {
            'format': f'best[height<={self.quality[:-1]}]/best',  # 720p -> height<=720
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'socket_timeout': self.timeout,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info(f"Extracting stream info from: {self.url}")
                info = ydl.extract_info(self.url, download=False)
                
                # Get the best format URL
                if 'url' in info:
                    stream_url = info['url']
                elif 'formats' in info and len(info['formats']) > 0:
                    # Get the best format
                    stream_url = info['formats'][-1]['url']
                else:
                    raise ValueError("No stream URL found in video info")
                
                return {
                    'url': stream_url,
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration'),
                    'is_live': info.get('is_live', False),
                    'fps': info.get('fps', 30),
                    'width': info.get('width', 1280),
                    'height': info.get('height', 720),
                    'format_id': info.get('format_id', 'unknown'),
                }
        except Exception as e:
            logger.error(f"Failed to extract stream URL: {e}")
            raise
    
    def start_stream(self, stream_id: str) -> StreamInfo:
        """
        Initialize stream connection and start frame buffering.
        
        Args:
            stream_id: Unique identifier for this stream
            
        Returns:
            StreamInfo object with metadata
        """
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Get stream URL and metadata
                stream_data = self._get_stream_url()
                self.stream_url = stream_data['url']
                
                # Open video capture with retry logic
                logger.info(f"Opening video capture for stream: {stream_id} (attempt {retry_count + 1}/{max_retries})")
                self.cap = cv2.VideoCapture(self.stream_url)
                
                if not self.cap.isOpened():
                    retry_count += 1
                    if retry_count < max_retries:
                        logger.warning(f"Failed to open stream, retrying in 2s...")
                        time.sleep(2)
                        continue
                    raise RuntimeError("Failed to open video stream after retries")
                
                # Get actual stream properties
                actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
                actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                # Create stream info
                self.stream_info = StreamInfo(
                    stream_id=stream_id,
                    url=self.url,
                    title=stream_data['title'],
                    duration=stream_data['duration'],
                    fps=actual_fps if actual_fps > 0 else stream_data['fps'],
                    width=actual_width if actual_width > 0 else stream_data['width'],
                    height=actual_height if actual_height > 0 else stream_data['height'],
                    is_live=stream_data['is_live'],
                    format_id=stream_data['format_id'],
                )
                
                # Start frame buffering thread
                self.is_running = True
                self.buffer_thread = threading.Thread(target=self._buffer_frames, daemon=True)
                self.buffer_thread.start()
                
                logger.info(f"Stream started successfully: {self.stream_info.title} ({self.stream_info.width}x{self.stream_info.height} @ {self.stream_info.fps}fps)")
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
    
    def _buffer_frames(self):
        """Background thread to continuously read frames into buffer."""
        frame_count = 0
        error_count = 0
        max_errors = 15
        consecutive_timeouts = 0
        max_consecutive_timeouts = 5
        
        while self.is_running and self.cap is not None:
            try:
                ret, frame = self.cap.read()
                
                if not ret:
                    error_count += 1
                    consecutive_timeouts += 1
                    
                    if consecutive_timeouts > max_consecutive_timeouts:
                        logger.warning(f"Too many consecutive timeouts ({consecutive_timeouts}), reconnecting...")
                        consecutive_timeouts = 0
                        # Try to reconnect
                        self.cap.release()
                        try:
                            self.cap = cv2.VideoCapture(self.stream_url)
                            if self.cap.isOpened():
                                logger.info("Successfully reconnected to stream")
                                error_count = 0
                                continue
                        except Exception as reconnect_error:
                            logger.error(f"Failed to reconnect: {reconnect_error}")
                    
                    if error_count >= max_errors:
                        logger.error("Too many frame read errors, stopping buffer")
                        self.is_running = False
                        break
                    
                    time.sleep(0.05)
                    continue
                
                # Reset error counts on successful read
                error_count = 0
                consecutive_timeouts = 0
                frame_count += 1
                
                # Add to buffer with adaptive timeout
                try:
                    # Use shorter timeout to prevent blocking
                    timeout = 0.5 if self.frame_buffer.qsize() > 60 else 1.0
                    self.frame_buffer.put((frame_count, frame), timeout=timeout)
                except queue.Full:
                    # Skip frame if buffer is full (normal under high load)
                    if frame_count % 30 == 0:  # Log every 30 frames
                        logger.debug(f"Frame buffer full (size: {self.frame_buffer.qsize()}/90), skipping frame {frame_count}")
                    
            except Exception as e:
                logger.error(f"Error in frame buffer thread: {e}")
                error_count += 1
                if error_count >= max_errors:
                    self.is_running = False
                    break
        
        logger.info(f"Frame buffering stopped. Total frames buffered: {frame_count}, Final queue size: {self.frame_buffer.qsize()}")
    
    def get_next_frame(self) -> Optional[tuple]:
        """
        Get next frame from buffer.

        Returns:
            Tuple of (frame_number, frame) or None if no frame available
        """
        try:
            return self.frame_buffer.get(timeout=2.0)
        except queue.Empty:
            if not self.is_running:
                return None
            logger.warning("Frame buffer empty, waiting for frames...")
            return None

    def get_frame(self) -> Optional[tuple]:
        """
        Get next frame from buffer with timestamp.
        Non-blocking version for continuous processing.

        Returns:
            Tuple of (frame_number, frame, timestamp_ms) or None if no frame available
        """
        try:
            frame_data = self.frame_buffer.get_nowait()
            if frame_data:
                frame_number, frame = frame_data
                # Calculate timestamp based on frame number and fps
                fps = self.stream_info.fps if self.stream_info else 30
                timestamp_ms = (frame_number / fps) * 1000
                return (frame_number, frame, timestamp_ms)
            return None
        except queue.Empty:
            return None
    
    def get_batch_frames(self, duration: int = 15, target_fps: int = 3) -> List[tuple]:
        """
        Extract a batch of frames for the specified duration.
        
        Args:
            duration: Duration in seconds (default 15)
            target_fps: Target frames per second (default 3)
            
        Returns:
            List of (frame_number, frame, timestamp) tuples
        """
        if not self.stream_info:
            raise RuntimeError("Stream not started")
        
        total_frames_needed = duration * target_fps
        frames = []
        
        # Calculate frame skip interval
        # If stream is 30fps and we want 3fps, we need to skip every 10 frames
        source_fps = self.stream_info.fps
        skip_interval = max(1, int(source_fps / target_fps))
        
        logger.info(f"Extracting {total_frames_needed} frames over {duration}s (1 every {skip_interval} frames)")
        
        frame_counter = 0
        extracted_count = 0
        start_time = time.time()
        timeout_duration = duration * 3  # Increased timeout buffer
        consecutive_empty = 0
        max_consecutive_empty = 10
        
        while extracted_count < total_frames_needed and self.is_running:
            frame_data = self.get_next_frame()
            
            if frame_data is None:
                consecutive_empty += 1
                
                # Check if we've timed out
                elapsed = time.time() - start_time
                if elapsed > timeout_duration:
                    logger.warning(f"Timeout while extracting batch after {elapsed:.2f}s. Got {extracted_count}/{total_frames_needed} frames")
                    break
                
                # If buffer is empty for too long, might be a connection issue
                if consecutive_empty >= max_consecutive_empty:
                    logger.warning(f"Buffer empty for {consecutive_empty} attempts, retrying...")
                    consecutive_empty = 0
                
                # Adaptive wait time
                time.sleep(0.05)
                continue
            
            consecutive_empty = 0
            frame_number, frame = frame_data
            frame_counter += 1
            
            # Only keep frames at the target interval
            if frame_counter % skip_interval == 0:
                timestamp_ms = (frame_number / source_fps) * 1000
                frames.append((frame_number, frame, timestamp_ms))
                extracted_count += 1
        
        elapsed = time.time() - start_time
        logger.info(f"Extracted {len(frames)}/{total_frames_needed} frames in {elapsed:.2f}s (efficiency: {len(frames)/total_frames_needed*100:.1f}%)")
        return frames
    
    def stop_stream(self):
        """Stop stream and clean up resources."""
        logger.info("Stopping stream...")
        self.is_running = False
        
        # Wait for buffer thread to finish
        if self.buffer_thread and self.buffer_thread.is_alive():
            self.buffer_thread.join(timeout=2.0)
        
        # Release video capture
        if self.cap:
            self.cap.release()
            self.cap = None
        
        # Clear buffer
        while not self.frame_buffer.empty():
            try:
                self.frame_buffer.get_nowait()
            except queue.Empty:
                break
        
        logger.info("Stream stopped and resources cleaned up")


class StreamManager:
    """
    Manages multiple active streams and their lifecycle.
    Coordinates batch processing cycles (15s + 5s).
    """
    
    def __init__(self, max_concurrent: int = 3):
        """
        Initialize stream manager.
        
        Args:
            max_concurrent: Maximum number of concurrent streams
        """
        self.max_concurrent = max_concurrent
        self.active_streams: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        
        logger.info(f"StreamManager initialized (max concurrent: {max_concurrent})")
    
    def create_stream(self, stream_id: str, url: str, quality: str = "720p") -> StreamExtractor:
        """
        Create a new stream.
        
        Args:
            stream_id: Unique stream identifier
            url: Stream URL
            quality: Preferred quality
            
        Returns:
            StreamExtractor instance
        """
        with self.lock:
            if len(self.active_streams) >= self.max_concurrent:
                raise RuntimeError(f"Maximum concurrent streams ({self.max_concurrent}) reached")
            
            if stream_id in self.active_streams:
                raise ValueError(f"Stream {stream_id} already exists")
            
            extractor = StreamExtractor(url, quality)
            
            self.active_streams[stream_id] = {
                'extractor': extractor,
                'state': StreamState.INITIALIZING,
                'created_at': datetime.utcnow(),
                'batch_count': 0,
                'total_frames': 0,
                'error': None,
            }
            
            logger.info(f"Created stream: {stream_id}")
            return extractor
    
    def get_stream(self, stream_id: str) -> Optional[StreamExtractor]:
        """Get stream extractor by ID."""
        with self.lock:
            stream_data = self.active_streams.get(stream_id)
            return stream_data['extractor'] if stream_data else None
    
    def update_state(self, stream_id: str, state: StreamState, error: Optional[str] = None):
        """Update stream state."""
        with self.lock:
            if stream_id in self.active_streams:
                self.active_streams[stream_id]['state'] = state
                if error:
                    self.active_streams[stream_id]['error'] = error
                logger.info(f"Stream {stream_id} state: {state.value}")
    
    def increment_batch(self, stream_id: str, frame_count: int):
        """Increment batch counter and frame count."""
        with self.lock:
            if stream_id in self.active_streams:
                self.active_streams[stream_id]['batch_count'] += 1
                self.active_streams[stream_id]['total_frames'] += frame_count
    
    def get_status(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """Get stream status."""
        with self.lock:
            if stream_id not in self.active_streams:
                return None
            
            stream_data = self.active_streams[stream_id]
            extractor = stream_data['extractor']
            
            return {
                'stream_id': stream_id,
                'state': stream_data['state'].value,
                'created_at': stream_data['created_at'].isoformat() + 'Z',
                'batch_count': stream_data['batch_count'],
                'total_frames': stream_data['total_frames'],
                'error': stream_data['error'],
                'stream_info': {
                    'title': extractor.stream_info.title if extractor.stream_info else None,
                    'is_live': extractor.stream_info.is_live if extractor.stream_info else None,
                    'fps': extractor.stream_info.fps if extractor.stream_info else None,
                    'resolution': f"{extractor.stream_info.width}x{extractor.stream_info.height}" if extractor.stream_info else None,
                } if extractor.stream_info else None,
            }
    
    def remove_stream(self, stream_id: str):
        """Remove stream and clean up."""
        with self.lock:
            if stream_id in self.active_streams:
                stream_data = self.active_streams[stream_id]
                extractor = stream_data['extractor']
                
                # Stop the stream
                extractor.stop_stream()
                
                # Remove from active streams
                del self.active_streams[stream_id]
                logger.info(f"Removed stream: {stream_id}")
    
    def list_streams(self) -> List[Dict[str, Any]]:
        """List all active streams."""
        with self.lock:
            return [self.get_status(sid) for sid in self.active_streams.keys()]
    
    def cleanup_all(self):
        """Stop and remove all streams."""
        with self.lock:
            stream_ids = list(self.active_streams.keys())
            for stream_id in stream_ids:
                self.remove_stream(stream_id)
            logger.info("All streams cleaned up")


if __name__ == "__main__":
    # Test stream extraction
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) < 2:
        print("Usage: python stream_processor.py <youtube_url>")
        sys.exit(1)
    
    url = sys.argv[1]
    
    # Create manager and stream
    manager = StreamManager()
    stream_id = "test_stream"
    
    try:
        extractor = manager.create_stream(stream_id, url)
        stream_info = extractor.start_stream(stream_id)
        manager.update_state(stream_id, StreamState.ACTIVE)
        
        print(f"\nStream Info:")
        print(f"  Title: {stream_info.title}")
        print(f"  Resolution: {stream_info.width}x{stream_info.height}")
        print(f"  FPS: {stream_info.fps}")
        print(f"  Is Live: {stream_info.is_live}")
        
        # Extract one batch
        print(f"\nExtracting 15-second batch...")
        frames = extractor.get_batch_frames(duration=15, target_fps=3)
        print(f"Extracted {len(frames)} frames")
        
        # Display first frame
        if frames:
            _, first_frame, _ = frames[0]
            cv2.imshow("First Frame", first_frame)
            cv2.waitKey(2000)
            cv2.destroyAllWindows()
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        manager.remove_stream(stream_id)
        print("\nStream stopped")
