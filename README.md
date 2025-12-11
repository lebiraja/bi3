# YOLO Vehicle Tracking Setup

## Files in this workspace:
- `yolo11n/` - YOLO11 nano model files
- `vid1.mp4` - Input video for tracking
- `vehicle_tracking.py` - Main tracking script

## Installation

```bash
pip install ultralytics
```

## Usage

Run the vehicle tracking script:
```bash
python vehicle_tracking.py
```

## Vehicle Classes (COCO dataset):
- Class 2: car
- Class 3: motorcycle
- Class 5: bus
- Class 7: truck

## Tracker Options:
- `bytetrack.yaml` - ByteTrack (default, good for crowded scenes)
- `botsort.yaml` - BoT-SORT (better for camera motion)

## Output:
- Tracked video will be saved in `runs/track/exp/`
- Console will show frame-by-frame detection counts and IDs

## Customization:
Modify parameters in `vehicle_tracking.py`:
- `conf`: Confidence threshold (0.0-1.0)
- `iou`: IOU threshold for non-max suppression
- `classes`: List of class IDs to detect
- `tracker`: Tracking algorithm configuration
