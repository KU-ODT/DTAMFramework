"""
Threading Architecture for UAM Operations System

This module implements thread-safe communication between vision processing,
sensor data acquisition, risk assessment, and GUI rendering threads.
"""
import sys
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(CORE_DIR / "external"))
import cosysairsim as airsim

import threading
import queue
import time
import cv2
import numpy as np
from typing import Dict, Any, Optional, Callable
import logging
from dataclasses import dataclass
from enum import Enum

from ..detection.object_detector import ObjectDetector, DetectedObject
from ..prediction.gaussian_predictor import GaussianTrajectoryPredictor
from ..utils.safety_metrics import SafetyMetricsCalculator, SafetyMetrics
from ..ahp.ahp_processor import AHPProcessor, AHPCriteria
# from ..airsim_integration.airsim_connector import AirSimConnector
from ..utils.config import get_config

class ThreadState(Enum):
    """Thread execution states"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"

@dataclass
class ProcessingResult:
    """Container for processing results"""
    timestamp: float
    frame: Optional[np.ndarray] = None
    detected_objects: Optional[list] = None
    trajectories: Optional[Dict] = None
    safety_metrics: Optional[list] = None
    ahp_result: Optional[Any] = None
    uav_state: Optional[Any] = None
    error: Optional[str] = None

class CameraThread(threading.Thread):
    """Thread for camera capture and video processing"""
    
    def __init__(self, frame_queue: queue.Queue, camera_index: int = 0, use_airsim: bool = False, airsim_connector=None, frame_callback=None):
        super().__init__(name="CameraThread")
        self.frame_queue = frame_queue
        self.camera_index = camera_index
        self.use_airsim = use_airsim
        self.airsim_connector = airsim_connector
        self.frame_callback = frame_callback  # Direct callback for GUI display
        self.state = ThreadState.STOPPED
        self.running = False
        self.camera = None
        self.airsim_client = None
        self.vehicle_name = "Drone1"
        self.camera_name = "front_center"
        self.logger = logging.getLogger(__name__)
        
    def start_camera(self) -> bool:
        """Start camera capture"""
        # If AirSim is available and connected, use it exclusively
        if self.use_airsim:
            try:
                self.airsim_client = airsim.MultirotorClient(ip="127.0.0.1")
                self.airsim_client.confirmConnection()

                self.logger.info("Connected to Cosys-AirSim UE")
                self.camera = None
                return True

            except Exception as e:
                self.logger.error(f"Could not connect to Cosys-AirSim UE: {e}")
                return False
                        
        # Only try local cameras if NOT in AirSim mode
        if not self.use_airsim:
            # Try multiple camera indices for local cameras
            camera_indices = [self.camera_index, 0, 1, 2]
            
            for idx in camera_indices:
                try:
                    self.logger.info(f"Trying camera index {idx}...")
                    self.camera = cv2.VideoCapture(idx)
                    
                    if self.camera.isOpened():
                        # Test if we can read a frame
                        ret, frame = self.camera.read()
                        if ret and frame is not None:
                            self.camera_index = idx
                            
                            # Set camera properties
                            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                            self.camera.set(cv2.CAP_PROP_FPS, 30)
                            
                            self.logger.info(f"Camera {idx} opened successfully")
                            return True
                        else:
                            self.camera.release()
                            
                except Exception as e:
                    self.logger.debug(f"Camera {idx} failed: {e}")
                    if self.camera:
                        self.camera.release()
                        
            # No local camera found
            self.logger.warning("No local camera found")
            self.camera = None
            return False
        
        return True
            
    def stop_camera(self):
        """Stop camera capture"""
        if self.camera:
            self.camera.release()
            self.camera = None
            
    def run(self):
        """Main camera thread loop"""
        self.state = ThreadState.STARTING
        self.running = True
        
        if not self.start_camera():
            self.state = ThreadState.ERROR
            return
            
        self.state = ThreadState.RUNNING
        self.logger.info("Camera thread started")
        
        frame_count = 0
        start_time = time.time()
        
        try:
            while self.running:
                frame = None
                ret = False
                
                # Try AirSim camera first if available
                if self.use_airsim and self.airsim_client:
                    try:
                        raw_image = self.airsim_client.simGetImage(
                            self.camera_name,
                            airsim.ImageType.Scene,
                            vehicle_name=self.vehicle_name
                        )

                        if raw_image:
                            img_1d = np.frombuffer(raw_image, dtype=np.uint8)
                            frame = cv2.imdecode(img_1d, cv2.IMREAD_COLOR)
                            ret = frame is not None
                        if frame is not None and frame.size > 0:
                            ret = True
                            if frame_count % 100 == 0:  # Log success occasionally
                                self.logger.debug("AirSim camera working")
                        else:
                            self.logger.debug("AirSim camera returned empty frame")
                    except Exception as e:
                        self.logger.debug(f"AirSim camera error: {e}")
                        
                # Fallback to local camera if AirSim failed
                if not ret and self.camera is not None:
                    try:
                        ret, frame = self.camera.read()
                        if not ret:
                            self.logger.debug("Local camera failed to read frame")
                    except Exception as e:
                        self.logger.debug(f"Local camera error: {e}")
                        
                # Final fallback - skip frame if no cameras available
                if not ret or frame is None:
                    if frame_count % 100 == 0:  # Log occasionally
                        self.logger.debug("No camera sources available, skipping frame")
                    time.sleep(0.1)
                    continue
                
                # Ensure frame is valid
                if frame is None or frame.size == 0:
                    self.logger.warning("All frame sources failed, skipping frame")
                    time.sleep(0.1)
                    continue
                    
                # Put frame in queue (non-blocking)
                try:
                    self.frame_queue.put(frame, block=False)
                except queue.Full:
                    # Remove oldest frame if queue is full
                    try:
                        self.frame_queue.get_nowait()
                        self.frame_queue.put(frame, block=False)
                    except queue.Empty:
                        pass
                
                # Send frame directly to GUI for immediate display
                if self.frame_callback:
                    try:
                        # Create a simple result for immediate display
                        display_result = ProcessingResult(
                            timestamp=time.time(),
                            frame=frame
                        )
                        self.frame_callback(display_result)
                    except Exception as e:
                        self.logger.debug(f"Error in frame callback: {e}")
                        
                frame_count += 1
                
                # Log FPS every 100 frames
                if frame_count % 100 == 0:
                    elapsed = time.time() - start_time
                    fps = frame_count / elapsed
                    self.logger.debug(f"Camera FPS: {fps:.1f}")
                    
                time.sleep(1/30)  # Target 30 FPS
                
        except Exception as e:
            self.logger.error(f"Error in camera thread: {e}")
            self.state = ThreadState.ERROR
        finally:
            self.stop_camera()
            self.state = ThreadState.STOPPED
            self.logger.info("Camera thread stopped")
            
    def stop(self):
        """Stop the camera thread"""
        self.running = False
        
    # Test frame generation disabled - no longer used
    # def _generate_test_frame(self, frame_count: int) -> np.ndarray:
    #     """Generate a test frame when no camera is available"""
    #     # Test pattern generation removed - frames are skipped instead
    #     pass

class VisionProcessingThread(threading.Thread):
    """Thread for object detection and tracking"""
    
    def __init__(self, frame_queue: queue.Queue, result_queue: queue.Queue):
        super().__init__(name="VisionProcessingThread")
        self.frame_queue = frame_queue
        self.result_queue = result_queue
        self.state = ThreadState.STOPPED
        self.running = False
        self.detector = None
        self.predictor = None
        self.logger = logging.getLogger(__name__)
        
    def initialize(self):
        """Initialize detection and prediction components"""
        try:
            self.detector = ObjectDetector()
            self.predictor = GaussianTrajectoryPredictor()
            return True
        except Exception as e:
            self.logger.error(f"Error initializing vision components: {e}")
            return False
            
    def run(self):
        """Main vision processing loop"""
        self.state = ThreadState.STARTING
        self.running = True
        
        if not self.initialize():
            self.state = ThreadState.ERROR
            return
            
        self.state = ThreadState.RUNNING
        self.logger.info("Vision processing thread started")
        
        try:
            while self.running:
                try:
                    # Get frame from queue
                    frame = self.frame_queue.get(timeout=1.0)
                    
                    # Detect objects
                    detected_objects = self.detector.detect_objects(frame)
                    
                    # Update trajectory predictions
                    trajectories = {}
                    for obj in detected_objects:
                        self.predictor.update_object_state(
                            obj.obj_id, obj.centroid, obj.velocity)
                        trajectory = self.predictor.predict_trajectory(obj.obj_id)
                        trajectories[obj.obj_id] = trajectory
                        
                    # Clean up old objects
                    active_ids = [obj.obj_id for obj in detected_objects]
                    self.predictor.cleanup_old_objects(active_ids)
                    
                    # Draw annotations
                    annotated_frame = self.detector.draw_detections(frame, detected_objects)
                    
                    # Create result
                    result = ProcessingResult(
                        timestamp=time.time(),
                        frame=annotated_frame,
                        detected_objects=detected_objects,
                        trajectories=trajectories
                    )
                    
                    # Put result in queue
                    try:
                        self.result_queue.put(result, block=False)
                    except queue.Full:
                        # Remove oldest result
                        try:
                            self.result_queue.get_nowait()
                            self.result_queue.put(result, block=False)
                        except queue.Empty:
                            pass
                            
                except queue.Empty:
                    continue
                except Exception as e:
                    self.logger.error(f"Error in vision processing: {e}")
                    
        except Exception as e:
            self.logger.error(f"Fatal error in vision thread: {e}")
            self.state = ThreadState.ERROR
        finally:
            self.state = ThreadState.STOPPED
            self.logger.info("Vision processing thread stopped")
            
    def stop(self):
        """Stop the vision processing thread"""
        self.running = False

class AirSimThread(threading.Thread):
    """Thread for AirSim sensor data acquisition"""
    
    def __init__(self, sensor_queue: queue.Queue, ip_address: str = None):
        super().__init__(name="AirSimThread")
        self.sensor_queue = sensor_queue
        self.state = ThreadState.STOPPED
        self.running = False
        self.airsim_connector = None
        self.logger = logging.getLogger(__name__)
        self.custom_ip = ip_address  # Allow override of config IP
        self.client = None
        self.vehicle_name = "Drone1"
        self.camera_name = "front_center"
        
    def connect_airsim(self) -> bool:
        """Connect directly to Cosys-AirSim"""

        try:

            config = get_config()
            airsim_config = config.get_airsim_config()

            ip_address = (
                self.custom_ip
                if self.custom_ip
                else airsim_config.get('ip_address', '127.0.0.1')
            )

            self.client = airsim.MultirotorClient(ip=ip_address)

            self.client.confirmConnection()

            self.logger.info(
                f"Connected to Cosys-AirSim at {ip_address}"
            )

            return True

        except Exception as e:

            self.logger.error(
                f"Error connecting to Cosys-AirSim: {e}"
            )

            return False
            
    def run(self):
        """Main AirSim sensor acquisition loop"""
        self.state = ThreadState.STARTING
        self.running = True
        
        if not self.connect_airsim():
            self.state = ThreadState.ERROR
            return
            
        self.state = ThreadState.RUNNING
        self.logger.info("AirSim thread started")
        
        try:
            while self.running:

                if self.client is not None:

                    try:

                        state = self.client.getMultirotorState(
                            vehicle_name=self.vehicle_name
                        )

                        try:
                            self.sensor_queue.put(state, block=False)
                        except queue.Full:
                            pass

                    except Exception as e:
                        self.logger.debug(f"AirSim state error: {e}")

                    time.sleep(0.1)

                else:

                    self.logger.warning(
                        "Cosys-AirSim connection lost, reconnecting..."
                    )

                    time.sleep(5.0)

                    self.connect_airsim()
                    
        except Exception as e:
            self.logger.error(f"Error in AirSim thread: {e}")
            self.state = ThreadState.ERROR
        finally:
            if self.airsim_connector:
                self.airsim_connector.disconnect()
            self.state = ThreadState.STOPPED
            self.logger.info("AirSim thread stopped")
            
    def stop(self):
        """Stop the AirSim thread"""
        self.running = False

class RiskAssessmentThread(threading.Thread):
    """Thread for risk assessment and AHP processing"""
    
    def __init__(self, result_queue: queue.Queue, sensor_queue: queue.Queue, 
                 assessment_queue: queue.Queue):
        super().__init__(name="RiskAssessmentThread")
        self.result_queue = result_queue
        self.sensor_queue = sensor_queue
        self.assessment_queue = assessment_queue
        self.state = ThreadState.STOPPED
        self.running = False
        
        # Processing components
        self.safety_calculator = None
        self.ahp_processor = None
        
        # Current data
        self.current_uav_state = None
        self.logger = logging.getLogger(__name__)
        
    def initialize(self):
        """Initialize risk assessment components"""
        try:
            self.safety_calculator = SafetyMetricsCalculator()
            self.ahp_processor = AHPProcessor()
            return True
        except Exception as e:
            self.logger.error(f"Error initializing risk assessment: {e}")
            return False
            
    def run(self):
        """Main risk assessment loop"""
        self.state = ThreadState.STARTING
        self.running = True

        if not self.initialize():
            self.state = ThreadState.ERROR
            return

        self.state = ThreadState.RUNNING
        self.logger.info("Risk assessment thread started")

        try:
            while self.running:

                # --------------------------------------------------
                # Get latest UAV state from Cosys-AirSim
                # --------------------------------------------------
                try:
                    uav_state = self.sensor_queue.get_nowait()
                    self.current_uav_state = uav_state

                    try:
                        pos = uav_state.kinematics_estimated.position
                        vel = uav_state.kinematics_estimated.linear_velocity

                        self.safety_calculator.update_uav_state(
                            (pos.x_val, pos.y_val),
                            (vel.x_val, vel.y_val)
                        )

                    except AttributeError:
                        self.logger.debug(
                            "UAV state format not recognized. Skipping UAV state update."
                        )

                except queue.Empty:
                    pass

                # --------------------------------------------------
                # Get latest vision results
                # --------------------------------------------------
                try:
                    vision_result = self.result_queue.get(timeout=1.0)

                    if vision_result.detected_objects:

                        all_metrics = []
                        all_criteria = []

                        for obj in vision_result.detected_objects:
                            trajectory = vision_result.trajectories.get(obj.obj_id)

                            metrics = self.safety_calculator.calculate_metrics(
                                obj,
                                trajectory
                            )

                            all_metrics.append(metrics)

                            criteria = AHPCriteria(
                                distance=metrics.normalized_distance,
                                time_to_collision=metrics.normalized_ttc,
                                uncertainty=metrics.normalized_uncertainty,
                                velocity=metrics.normalized_velocity
                            )

                            all_criteria.append(criteria)

                        ahp_result = self.ahp_processor.analyze_multiple_objects(
                            all_criteria
                        )

                        assessment = ProcessingResult(
                            timestamp=time.time(),
                            frame=vision_result.frame,
                            detected_objects=vision_result.detected_objects,
                            trajectories=vision_result.trajectories,
                            safety_metrics=all_metrics,
                            ahp_result=ahp_result,
                            uav_state=self.current_uav_state
                        )

                        try:
                            self.assessment_queue.put(assessment, block=False)
                        except queue.Full:
                            try:
                                self.assessment_queue.get_nowait()
                                self.assessment_queue.put(assessment, block=False)
                            except queue.Empty:
                                pass

                except queue.Empty:
                    continue

                except Exception as e:
                    self.logger.error(f"Error in risk assessment: {e}")

        except Exception as e:
            self.logger.error(f"Fatal error in risk assessment thread: {e}")
            self.state = ThreadState.ERROR

        finally:
            self.state = ThreadState.STOPPED
            self.logger.info("Risk assessment thread stopped")
            
    def stop(self):
        """Stop the risk assessment thread"""
        self.running = False

class ThreadManager:
    """Manager for all processing threads"""
    
    def __init__(self, gui_callback: Optional[Callable] = None):
        self.logger = logging.getLogger(__name__)
        self.gui_callback = gui_callback
        
        # Queues
        self.frame_queue = queue.Queue(maxsize=5)
        self.result_queue = queue.Queue(maxsize=5)
        self.sensor_queue = queue.Queue(maxsize=10)
        self.assessment_queue = queue.Queue(maxsize=5)
        
        # Threads
        self.camera_thread = None
        self.vision_thread = None
        self.airsim_thread = None
        self.risk_thread = None
        
        # State
        self.running = False
        
    def start_all(self, enable_camera: bool = True, enable_airsim: bool = False, airsim_ip: str = None):
        """Start all processing threads"""
        try:
            self.running = True
            
            # Start AirSim if enabled (before camera so camera can use it)
            if enable_airsim:
                self.airsim_thread = AirSimThread(self.sensor_queue, ip_address=airsim_ip)
                self.airsim_thread.start()
                # Give AirSim time to connect
                import time
                time.sleep(2)
            
            # Start vision processing
            self.vision_thread = VisionProcessingThread(self.frame_queue, self.result_queue)
            self.vision_thread.start()
            
            # Start camera if enabled
            if enable_camera:
                # Pass AirSim connector to camera thread if available
                airsim_connector = None
                if self.airsim_thread and self.airsim_thread.airsim_connector:
                    airsim_connector = self.airsim_thread.airsim_connector
                    
                self.camera_thread = CameraThread(
                    self.frame_queue, 
                    use_airsim=enable_airsim,
                    airsim_connector=airsim_connector,
                    frame_callback=self.gui_callback  # Pass GUI callback for direct frame display
                )
                self.camera_thread.start()
                
            # Start risk assessment
            self.risk_thread = RiskAssessmentThread(
                self.result_queue, self.sensor_queue, self.assessment_queue)
            self.risk_thread.start()
            
            self.logger.info("All threads started successfully")
            
            # Start GUI update loop
            if self.gui_callback:
                self._start_gui_updates()
                
        except Exception as e:
            self.logger.error(f"Error starting threads: {e}")
            self.stop_all()
            
    def stop_all(self):
        """Stop all processing threads"""
        self.running = False
        
        threads = [self.camera_thread, self.vision_thread, 
                  self.airsim_thread, self.risk_thread]
        
        # Stop all threads
        for thread in threads:
            if thread and thread.is_alive():
                thread.stop()
                
        # Wait for threads to finish
        for thread in threads:
            if thread and thread.is_alive():
                thread.join(timeout=5.0)
                
        self.logger.info("All threads stopped")
        
    def _start_gui_updates(self):
        """Start GUI update timer"""
        def update_gui():
            if not self.running:
                return
                
            try:
                # Get latest assessment
                assessment = self.assessment_queue.get_nowait()
                if self.gui_callback:
                    self.gui_callback(assessment)
            except queue.Empty:
                pass
            except Exception as e:
                self.logger.error(f"Error in GUI update: {e}")
                
            # Schedule next update
            if self.running:
                threading.Timer(0.1, update_gui).start()
                
        # Start the update loop
        threading.Timer(0.1, update_gui).start()
        
    def get_thread_states(self) -> Dict[str, str]:
        """Get current state of all threads"""
        states = {}
        
        if self.camera_thread:
            states['camera'] = self.camera_thread.state.value
        if self.vision_thread:
            states['vision'] = self.vision_thread.state.value
        if self.airsim_thread:
            states['airsim'] = self.airsim_thread.state.value
        if self.risk_thread:
            states['risk_assessment'] = self.risk_thread.state.value
            
        return states