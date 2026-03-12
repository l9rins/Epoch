from ultralytics import YOLO
import supervision as sv
import numpy as np

class PlayerTracker:
    def __init__(self):
        # Using yolov8x.pt for maximum accuracy, will auto-download on first use
        self.model = YOLO("yolov8x.pt")  
        self.tracker = sv.ByteTrack()
    
    def process_frame(self, frame: np.ndarray) -> sv.Detections:
        """
        Detect and track players (persons) in a frame.
        """
        results = self.model(frame)[0]
        detections = sv.Detections.from_ultralytics(results)
        
        # Filter to person class only (class_id == 0 in COCO)
        detections = detections[detections.class_id == 0]
        
        # Link detections across frames
        detections = self.tracker.update_with_detections(detections)
        
        return detections
