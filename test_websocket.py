#!/usr/bin/env python3
"""
WebSocket test client to verify stream events are being sent correctly.
"""

import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8000/ws/stream_263c5c43"
    
    print(f"Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✓ Connected to WebSocket")
            
            # Listen for messages
            message_count = 0
            async for message in websocket:
                message_count += 1
                data = json.loads(message)
                event_type = data.get('type', 'unknown')
                
                print(f"\n[Message #{message_count}] Type: {event_type}")
                
                if event_type == 'yolo_detection':
                    has_frame = 'frame' in data
                    frame_length = len(data.get('frame', '')) if has_frame else 0
                    detections_count = len(data.get('detections', []))
                    print(f"  - Has frame: {has_frame}")
                    print(f"  - Frame data length: {frame_length} chars")
                    print(f"  - Detections: {detections_count}")
                    
                    if has_frame and frame_length > 0:
                        print("  ✓ Frame data looks good!")
                    else:
                        print("  ✗ Frame data missing or empty!")
                
                elif event_type == 'vlm_summary':
                    print(f"  - Analysis: {data.get('analysis', {}).get('summary', 'N/A')[:50]}...")
                
                elif event_type == 'batch_complete':
                    print(f"  - Batch: {data.get('batch_index')}")
                    print(f"  - Frames: {data.get('frame_count')}")
                    print(f"  - Risk: {data.get('avg_risk_score')}")
                
                else:
                    print(f"  - Data keys: {list(data.keys())}")
                
                # Stop after 20 messages for testing
                if message_count >= 20:
                    print("\n✓ Test complete (received 20 messages)")
                    break
                    
    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == "__main__":
    print("WebSocket Stream Test")
    print("=" * 60)
    asyncio.run(test_websocket())
