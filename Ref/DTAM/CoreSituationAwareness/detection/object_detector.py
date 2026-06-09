"""
Object Detection Module for UAM Operations System

This module implements YOLO-based object detection with tracking capabilities.
It detects obstacles like birds, drones, buildings, and unknown objects.
"""

import cv2
import numpy as np
from ultralytics import YOLO
import logging
from typing import List, Dict, Tuple, Optional
import time
import os

from ..utils.config import get_config

class DetectedObject:
    """Represents a detected object with tracking information"""
    
    def __init__(self, obj_id: int, bbox: Tuple[int, int, int, int], 
                 confidence: float, class_name: str, frame_time: float):
        self.obj_id = obj_id
        self.bbox = bbox  # (x1, y1, x2, y2)
        self.confidence = confidence
        self.class_name = class_name
        self.frame_time = frame_time
        
        # Calculate centroid
        self.centroid = ((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2)
        
        # Tracking history
        self.position_history = [self.centroid]
        self.time_history = [frame_time]
        
        # Motion properties
        self.velocity = (0.0, 0.0)  # (vx, vy) in pixels/second
        self.distance = 0.0  # Estimated distance in meters
        
    def update_position(self, new_bbox: Tuple[int, int, int, int], 
                       frame_time: float, confidence: float):
        """Update object position and calculate velocity"""
        self.bbox = new_bbox
        self.confidence = confidence
        self.frame_time = frame_time
        
        new_centroid = ((new_bbox[0] + new_bbox[2]) // 2, (new_bbox[1] + new_bbox[3]) // 2)
        
        # Calculate velocity if we have previous position
        if len(self.position_history) > 0:
            dt = frame_time - self.time_history[-1]
            if dt > 0:
                dx = new_centroid[0] - self.centroid[0]
                dy = new_centroid[1] - self.centroid[1]
                self.velocity = (dx / dt, dy / dt)
        
        # Update tracking history
        self.centroid = new_centroid
        self.position_history.append(self.centroid)
        self.time_history.append(frame_time)
        
        # Keep only recent history (last 10 positions)
        if len(self.position_history) > 10:
            self.position_history.pop(0)
            self.time_history.pop(0)
            
    def estimate_distance(self, focal_length: float = 800, real_height: float = 1.0):
        """Estimate distance based on object size (simple approximation)"""
        bbox_height = self.bbox[3] - self.bbox[1]
        if bbox_height > 0:
            # Distance = (Real Height * Focal Length) / Pixel Height
            self.distance = (real_height * focal_length) / bbox_height
        return self.distance
        
    def get_speed(self) -> float:
        """Get object speed in pixels/second"""
        return np.sqrt(self.velocity[0]**2 + self.velocity[1]**2)

class ObjectDetector:
    """YOLO-based object detector with tracking capabilities"""
    
    def __init__(self, model_path: str = None):
        self.logger = logging.getLogger(__name__)
        self.model = None
        
        # Load configuration
        config = get_config()
        detection_config = config.get_detection_config()
        
        # Set model path from config if not provided
        if model_path is None:
            model_path = detection_config.get('model_path', 'models/yolo11n.pt')
            
        self.model_path = model_path
        self.confidence_threshold = detection_config.get('confidence_threshold', 0.5)
        self.tracked_objects = {}  # Dictionary of tracked objects
        self.next_id = 1
        self.max_disappeared = 30  # Maximum frames an object can disappear
        self.max_distance = 100  # Maximum distance for object matching
        
        # UAM-specific classes we're interested in
        self.target_classes = {
            'person': 0, 'bicycle': 1, 'car': 2, 'motorbike': 3, 'aeroplane': 4,
            'bus': 5, 'train': 6, 'truck': 7, 'bird': 14, 'cat': 15, 'dog': 16
        }
        
        self.initialize_model()
        
    def initialize_model(self):
        """Initialize YOLO model"""
        import os
        
        # Get the project root directory (two levels up from this file)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        
        # Try multiple model options
        model_options = []
        
        if self.model_path:
            # If it's a relative path, make it relative to project root
            if not os.path.isabs(self.model_path):
                full_path = os.path.join(project_root, self.model_path)
                model_options.append(full_path)
            model_options.append(self.model_path)
            
        # Add models in the current directory 
        model_options.extend([
            os.path.join(current_dir, "yolo11n.pt"),
            os.path.join(current_dir, "yolov8n.pt"),
        ])
        
        # Add models in project models directory
        models_dir = os.path.join(project_root, "models")
        model_options.extend([
            os.path.join(models_dir, "yolo11n.pt"),
            os.path.join(models_dir, "yolov8n.pt"),
            os.path.join(models_dir, "yolov8s.pt"),
        ])
        
        # Add common model names to try
        model_options.extend([
            "yolo11n.pt",
            "yolov8n.pt",
            "yolov8s.pt", 
            "yolov5n.pt",
            "yolov5s.pt",
            "models/yolov8s.pt"
        ])
        
        for model_path in model_options:
            try:
                self.logger.info(f"Trying to load YOLO model: {model_path}")
                self.model = YOLO(model_path)
                self.model_path = model_path
                self.logger.info(f"YOLO model loaded successfully: {model_path}")
                return
            except Exception as e:
                self.logger.debug(f"Failed to load {model_path}: {e}")
                continue
                
        # If no model could be loaded, create a dummy detector
        self.logger.warning("No YOLO model could be loaded. Using dummy detector for testing.")
        self.model = None
            
    def detect_objects(self, frame: np.ndarray) -> List[DetectedObject]:
        """Detect objects in frame and return tracked objects"""
        if self.model is None:
            # Generate dummy detections for testing
            return self._generate_dummy_detections(frame)
            
        try:
            frame_time = time.time()
            
            # Run YOLO detection
            results = self.model(frame, verbose=False)
            
            # Extract detections
            detections = []
            if results and len(results) > 0:
                result = results[0]
                if result.boxes is not None:
                    boxes = result.boxes.xyxy.cpu().numpy()
                    confidences = result.boxes.conf.cpu().numpy()
                    classes = result.boxes.cls.cpu().numpy()
                    
                    for i, (box, conf, cls) in enumerate(zip(boxes, confidences, classes)):
                        if conf > 0.5:  # Confidence threshold
                            class_name = self.model.names[int(cls)]
                            detections.append({
                                'bbox': tuple(map(int, box)),
                                'confidence': float(conf),
                                'class_name': class_name,
                                'frame_time': frame_time
                            })
            
            # Update tracking
            tracked_objects = self.update_tracking(detections, frame_time)
            
            return tracked_objects
            
        except Exception as e:
            self.logger.error(f"Error in object detection: {e}")
            return []
            
    def update_tracking(self, detections: List[Dict], frame_time: float) -> List[DetectedObject]:
        """Update object tracking with new detections"""
        # Convert current tracked objects to list for distance calculation
        existing_objects = list(self.tracked_objects.values())
        
        # Match detections to existing objects
        matched_pairs = []
        unmatched_detections = list(range(len(detections)))
        unmatched_objects = list(self.tracked_objects.keys())
        
        if len(existing_objects) > 0 and len(detections) > 0:
            # Calculate distances between detections and existing objects
            distances = np.zeros((len(detections), len(existing_objects)))
            
            for i, detection in enumerate(detections):
                det_centroid = ((detection['bbox'][0] + detection['bbox'][2]) // 2,
                              (detection['bbox'][1] + detection['bbox'][3]) // 2)
                
                for j, obj in enumerate(existing_objects):
                    obj_centroid = obj.centroid
                    distance = np.sqrt((det_centroid[0] - obj_centroid[0])**2 + 
                                     (det_centroid[1] - obj_centroid[1])**2)
                    distances[i, j] = distance
            
            # Find best matches using Hungarian algorithm (simplified)
            for _ in range(min(len(detections), len(existing_objects))):
                if distances.size == 0:
                    break
                    
                min_idx = np.unravel_index(np.argmin(distances), distances.shape)
                det_idx, obj_idx = min_idx
                
                if distances[det_idx, obj_idx] < self.max_distance:
                    # Match found
                    obj_id = existing_objects[obj_idx].obj_id
                    matched_pairs.append((det_idx, obj_id))
                    unmatched_detections.remove(det_idx)
                    if obj_id in unmatched_objects:
                        unmatched_objects.remove(obj_id)
                
                # Remove matched row and column
                distances = np.delete(distances, det_idx, axis=0)
                distances = np.delete(distances, obj_idx, axis=1)
                existing_objects.pop(obj_idx)
        
        # Update matched objects
        for det_idx, obj_id in matched_pairs:
            detection = detections[det_idx]
            self.tracked_objects[obj_id].update_position(
                detection['bbox'], frame_time, detection['confidence'])
        
        # Create new objects for unmatched detections
        for det_idx in unmatched_detections:
            detection = detections[det_idx]
            new_obj = DetectedObject(
                self.next_id, detection['bbox'], detection['confidence'],
                detection['class_name'], frame_time)
            new_obj.estimate_distance()
            self.tracked_objects[self.next_id] = new_obj
            self.next_id += 1
        
        # Remove objects that haven't been seen for too long
        current_time = time.time()
        to_remove = []
        for obj_id, obj in self.tracked_objects.items():
            if current_time - obj.frame_time > 2.0:  # 2 seconds timeout
                to_remove.append(obj_id)
        
        for obj_id in to_remove:
            del self.tracked_objects[obj_id]
        
        return list(self.tracked_objects.values())
    
    def draw_detections(self, frame: np.ndarray, objects: List[DetectedObject]) -> np.ndarray:
        """Draw bounding boxes and tracking information on frame"""
        annotated_frame = frame.copy()
        
        for obj in objects:
            # Draw bounding box
            x1, y1, x2, y2 = obj.bbox
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Draw centroid
            cv2.circle(annotated_frame, obj.centroid, 5, (0, 0, 255), -1)
            
            # Draw trajectory trail
            if len(obj.position_history) > 1:
                points = np.array(obj.position_history, dtype=np.int32)
                cv2.polylines(annotated_frame, [points], False, (255, 255, 0), 2)
            
            # Draw velocity vector
            if obj.get_speed() > 5:  # Only draw if moving significantly
                end_x = int(obj.centroid[0] + obj.velocity[0] * 0.1)
                end_y = int(obj.centroid[1] + obj.velocity[1] * 0.1)
                cv2.arrowedLine(annotated_frame, obj.centroid, (end_x, end_y), 
                              (255, 0, 255), 2)
            
            # Draw text info
            info_text = f"ID:{obj.obj_id} {obj.class_name} {obj.confidence:.2f}"
            distance_text = f"Dist: {obj.distance:.1f}m"
            speed_text = f"Speed: {obj.get_speed():.1f}px/s"
            
            cv2.putText(annotated_frame, info_text, (x1, y1-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(annotated_frame, distance_text, (x1, y1-25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
            cv2.putText(annotated_frame, speed_text, (x1, y1-40),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        return annotated_frame
    
    def get_detection_summary(self, objects: List[DetectedObject]) -> Dict:
        """Get summary of current detections"""
        summary = {
            'total_objects': len(objects),
            'objects_by_class': {},
            'closest_object': None,
            'average_distance': 0.0,
            'moving_objects': 0
        }
        
        if not objects:
            return summary
        
        # Count objects by class
        for obj in objects:
            if obj.class_name not in summary['objects_by_class']:
                summary['objects_by_class'][obj.class_name] = 0
            summary['objects_by_class'][obj.class_name] += 1
        
        # Find closest object
        closest_dist = float('inf')
        for obj in objects:
            if obj.distance < closest_dist:
                closest_dist = obj.distance
                summary['closest_object'] = obj
        
        # Calculate average distance
        summary['average_distance'] = np.mean([obj.distance for obj in objects])
        
        # Count moving objects
        summary['moving_objects'] = sum(1 for obj in objects if obj.get_speed() > 5)
        
        return summary
        
    def _generate_dummy_detections(self, frame: np.ndarray) -> List[DetectedObject]:
        """Generate dummy detections for testing when no YOLO model is available"""
        frame_time = time.time()
        detections = []
        
        # Create a few dummy moving objects for testing
        import math
        
        # Moving object 1 (simulates a bird)
        t = frame_time * 0.5
        x1 = int(200 + 150 * math.sin(t))
        y1 = int(150 + 50 * math.cos(t))
        bbox1 = (x1-15, y1-15, x1+15, y1+15)
        
        detection1 = {
            'bbox': bbox1,
            'confidence': 0.85,
            'class_name': 'bird',
            'frame_time': frame_time
        }
        detections.append(detection1)
        
        # Moving object 2 (simulates a person)
        x2 = int(400 + 100 * math.sin(t * 0.3))
        y2 = int(300 + 80 * math.cos(t * 0.7))
        bbox2 = (x2-25, y2-40, x2+25, y2+40)
        
        detection2 = {
            'bbox': bbox2,
            'confidence': 0.92,
            'class_name': 'person',
            'frame_time': frame_time
        }
        detections.append(detection2)
        
        # Update tracking with dummy detections
        tracked_objects = self.update_tracking(detections, frame_time)
        
        return tracked_objects