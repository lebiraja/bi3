#!/usr/bin/env python3
"""
Quick test script to verify streaming components are working.
Tests StreamExtractor and StreamManager initialization.
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_imports():
    """Test that all streaming modules can be imported."""
    logger.info("Testing imports...")
    
    try:
        from stream_processor import StreamExtractor, StreamManager, StreamState
        logger.info("✓ stream_processor imports successful")
        
        from stream_analyzer import StreamAnalyzer
        logger.info("✓ stream_analyzer imports successful")
        
        from config import Config
        logger.info("✓ Config imports successful")
        
        return True
    except Exception as e:
        logger.error(f"✗ Import failed: {e}")
        return False

def test_stream_manager():
    """Test StreamManager initialization."""
    logger.info("\nTesting StreamManager...")
    
    try:
        from stream_processor import StreamManager
        from config import Config
        
        manager = StreamManager(max_concurrent=Config.STREAM_MAX_CONCURRENT)
        logger.info(f"✓ StreamManager initialized (max concurrent: {Config.STREAM_MAX_CONCURRENT})")
        
        # Test listing streams (should be empty)
        streams = manager.list_streams()
        assert streams == [], "Expected empty stream list"
        logger.info("✓ Stream list is empty (as expected)")
        
        return True
    except Exception as e:
        logger.error(f"✗ StreamManager test failed: {e}")
        return False

def test_config():
    """Test streaming configuration."""
    logger.info("\nTesting streaming configuration...")
    
    try:
        from config import Config
        
        assert hasattr(Config, 'STREAM_BATCH_DURATION'), "Missing STREAM_BATCH_DURATION"
        assert hasattr(Config, 'STREAM_WAIT_DURATION'), "Missing STREAM_WAIT_DURATION"
        assert hasattr(Config, 'STREAM_INIT_DURATION'), "Missing STREAM_INIT_DURATION"
        assert hasattr(Config, 'STREAM_MAX_CONCURRENT'), "Missing STREAM_MAX_CONCURRENT"
        assert hasattr(Config, 'STREAM_QUALITY'), "Missing STREAM_QUALITY"
        
        logger.info(f"✓ STREAM_BATCH_DURATION: {Config.STREAM_BATCH_DURATION}s")
        logger.info(f"✓ STREAM_WAIT_DURATION: {Config.STREAM_WAIT_DURATION}s")
        logger.info(f"✓ STREAM_INIT_DURATION: {Config.STREAM_INIT_DURATION}s")
        logger.info(f"✓ STREAM_MAX_CONCURRENT: {Config.STREAM_MAX_CONCURRENT}")
        logger.info(f"✓ STREAM_QUALITY: {Config.STREAM_QUALITY}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Config test failed: {e}")
        return False

def test_dependencies():
    """Test that required dependencies are installed."""
    logger.info("\nTesting dependencies...")
    
    try:
        import yt_dlp
        logger.info(f"✓ yt-dlp installed: {yt_dlp.version.__version__}")
        
        import streamlink
        logger.info(f"✓ streamlink installed: {streamlink.__version__}")
        
        import cv2
        logger.info(f"✓ opencv-python installed: {cv2.__version__}")
        
        return True
    except ImportError as e:
        logger.error(f"✗ Dependency missing: {e}")
        return False

def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("Live Stream Processing - Component Verification")
    logger.info("=" * 60)
    
    results = {
        "Imports": test_imports(),
        "Dependencies": test_dependencies(),
        "Configuration": test_config(),
        "StreamManager": test_stream_manager(),
    }
    
    logger.info("\n" + "=" * 60)
    logger.info("Test Results Summary")
    logger.info("=" * 60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{test_name:20s}: {status}")
    
    all_passed = all(results.values())
    
    logger.info("=" * 60)
    if all_passed:
        logger.info("✓ All tests passed! Backend is ready for streaming.")
        return 0
    else:
        logger.error("✗ Some tests failed. Please review errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
