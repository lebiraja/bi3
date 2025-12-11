from ultralytics import YOLO

# Load pretrained model
# Using yolo11n.pt (nano model) since we have the yolo11n folder
model = YOLO("yolo11n.pt")

# Detect and track vehicles in video
results = model.track(
    source="realtimetest-1.mp4",  # Using the video in your workspace
    classes=[2, 3, 5, 7],  # Filter for vehicles only (car, motorcycle, bus, truck)
    tracker="bytetrack.yaml",  # ByteTrack tracker
    show=True,  # Display results in real-time
    save=True,  # Save tracked video
    conf=0.3,  # Confidence threshold
    iou=0.5,  # IOU threshold for NMS
)

# Optional: Process results
for frame_idx, result in enumerate(results):
    # Get tracking IDs and bounding boxes
    if result.boxes.id is not None:
        track_ids = result.boxes.id.cpu().numpy().astype(int)
        boxes = result.boxes.xyxy.cpu().numpy()
        classes = result.boxes.cls.cpu().numpy().astype(int)
        
        print(f"Frame {frame_idx}: Detected {len(track_ids)} vehicles")
        for track_id, box, cls in zip(track_ids, boxes, classes):
            print(f"  ID {track_id}: Class {cls}, Box: {box}")
