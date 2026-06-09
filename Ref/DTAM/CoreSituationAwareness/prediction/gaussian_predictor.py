"""
Gaussian Trajectory Prediction Module for UAM Operations System

This module implements trajectory prediction using Gaussian distributions,
Kalman filtering, and uncertainty quantification.
"""

import numpy as np
from scipy.stats import multivariate_normal
from typing import List, Tuple, Optional, Dict
import logging
from dataclasses import dataclass

@dataclass
class TrajectoryPoint:
    """Represents a point in predicted trajectory with uncertainty"""
    position: Tuple[float, float]  # (x, y)
    velocity: Tuple[float, float]  # (vx, vy)
    covariance: np.ndarray  # 2x2 covariance matrix
    timestamp: float
    confidence: float

class KalmanFilter:
    """Kalman filter for object state estimation"""
    
    def __init__(self, dt: float = 1/30):  # 30 FPS default
        self.dt = dt
        
        # State vector: [x, y, vx, vy]
        self.state = np.zeros(4)
        
        # State transition matrix (constant velocity model)
        self.F = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ])
        
        # Observation matrix (we observe position only)
        self.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ])
        
        # Process noise covariance
        self.Q = np.array([
            [0.1, 0, 0.05, 0],
            [0, 0.1, 0, 0.05],
            [0.05, 0, 0.1, 0],
            [0, 0.05, 0, 0.1]
        ])
        
        # Measurement noise covariance
        self.R = np.array([
            [1.0, 0],
            [0, 1.0]
        ])
        
        # State covariance
        self.P = np.eye(4) * 10
        
        self.initialized = False
        
    def initialize(self, position: Tuple[float, float], velocity: Tuple[float, float] = (0, 0)):
        """Initialize filter with first measurement"""
        self.state = np.array([position[0], position[1], velocity[0], velocity[1]])
        self.initialized = True
        
    def predict(self) -> Tuple[np.ndarray, np.ndarray]:
        """Predict next state"""
        # Predict state
        self.state = self.F @ self.state
        
        # Predict covariance
        self.P = self.F @ self.P @ self.F.T + self.Q
        
        return self.state.copy(), self.P.copy()
        
    def update(self, measurement: Tuple[float, float]):
        """Update with new measurement"""
        z = np.array([measurement[0], measurement[1]])
        
        # Innovation
        y = z - self.H @ self.state
        
        # Innovation covariance
        S = self.H @ self.P @ self.H.T + self.R
        
        # Kalman gain
        K = self.P @ self.H.T @ np.linalg.inv(S)
        
        # Update state and covariance
        self.state = self.state + K @ y
        self.P = (np.eye(4) - K @ self.H) @ self.P
        
    def get_position_covariance(self) -> np.ndarray:
        """Get position covariance (2x2 matrix)"""
        return self.P[:2, :2]
        
    def get_velocity_covariance(self) -> np.ndarray:
        """Get velocity covariance (2x2 matrix)"""
        return self.P[2:, 2:]

class GaussianTrajectoryPredictor:
    """Gaussian-based trajectory predictor with uncertainty quantification"""
    
    def __init__(self, prediction_horizon: float = 5.0, dt: float = 1/30):
        self.logger = logging.getLogger(__name__)
        self.prediction_horizon = prediction_horizon  # seconds
        self.dt = dt
        self.kalman_filters = {}  # One filter per tracked object
        
    def update_object_state(self, obj_id: int, position: Tuple[float, float], 
                           velocity: Optional[Tuple[float, float]] = None):
        """Update object state with new observation"""
        if obj_id not in self.kalman_filters:
            # Initialize new Kalman filter
            self.kalman_filters[obj_id] = KalmanFilter(self.dt)
            self.kalman_filters[obj_id].initialize(position, velocity or (0, 0))
        else:
            # Predict and update existing filter
            kf = self.kalman_filters[obj_id]
            kf.predict()
            kf.update(position)
            
    def predict_trajectory(self, obj_id: int, num_points: int = None) -> List[TrajectoryPoint]:
        """Predict future trajectory points with uncertainty"""
        if obj_id not in self.kalman_filters:
            return []
            
        if num_points is None:
            num_points = int(self.prediction_horizon / self.dt)
            
        kf = self.kalman_filters[obj_id]
        trajectory = []
        
        # Current state
        current_state = kf.state.copy()
        current_P = kf.P.copy()
        
        for i in range(num_points):
            # Predict forward in time
            current_state = kf.F @ current_state
            current_P = kf.F @ current_P @ kf.F.T + kf.Q
            
            # Extract position and velocity
            position = (current_state[0], current_state[1])
            velocity = (current_state[2], current_state[3])
            
            # Extract position covariance
            pos_cov = current_P[:2, :2]
            
            # Calculate confidence based on trace of covariance
            uncertainty = np.trace(pos_cov)
            confidence = 1.0 / (1.0 + uncertainty)
            
            # Create trajectory point
            point = TrajectoryPoint(
                position=position,
                velocity=velocity,
                covariance=pos_cov,
                timestamp=i * self.dt,
                confidence=confidence
            )
            
            trajectory.append(point)
            
        return trajectory
        
    def get_uncertainty_ellipse(self, point: TrajectoryPoint, 
                               confidence_level: float = 0.95) -> Tuple[Tuple[float, float], float, float, float]:
        """Get uncertainty ellipse parameters for visualization"""
        # Chi-square value for confidence level
        if confidence_level == 0.95:
            chi2_val = 5.991  # 95% confidence for 2D
        elif confidence_level == 0.68:
            chi2_val = 2.296  # 68% confidence
        else:
            chi2_val = 5.991  # Default to 95%
            
        # Eigenvalue decomposition of covariance matrix
        eigenvals, eigenvecs = np.linalg.eigh(point.covariance)
        
        # Sort eigenvalues and eigenvectors
        order = eigenvals.argsort()[::-1]
        eigenvals = eigenvals[order]
        eigenvecs = eigenvecs[:, order]
        
        # Calculate ellipse parameters
        width = 2 * np.sqrt(chi2_val * eigenvals[0])
        height = 2 * np.sqrt(chi2_val * eigenvals[1])
        angle = np.degrees(np.arctan2(eigenvecs[1, 0], eigenvecs[0, 0]))
        
        return point.position, width, height, angle
        
    def calculate_collision_probability(self, obj1_trajectory: List[TrajectoryPoint],
                                      obj2_trajectory: List[TrajectoryPoint],
                                      safety_radius: float = 5.0) -> List[float]:
        """Calculate collision probability over time between two trajectories"""
        min_length = min(len(obj1_trajectory), len(obj2_trajectory))
        probabilities = []
        
        for i in range(min_length):
            p1 = obj1_trajectory[i]
            p2 = obj2_trajectory[i]
            
            # Relative position and combined covariance
            rel_pos = np.array([p1.position[0] - p2.position[0], 
                               p1.position[1] - p2.position[1]])
            combined_cov = p1.covariance + p2.covariance
            
            # Add safety radius to covariance
            combined_cov += np.eye(2) * (safety_radius ** 2)
            
            # Calculate probability that relative distance < safety_radius
            try:
                prob = multivariate_normal.cdf([safety_radius, safety_radius], 
                                             mean=rel_pos, cov=combined_cov)
                probabilities.append(prob)
            except:
                probabilities.append(0.0)
                
        return probabilities
        
    def estimate_time_to_collision(self, trajectory: List[TrajectoryPoint],
                                  target_position: Tuple[float, float],
                                  safety_radius: float = 5.0) -> Optional[float]:
        """Estimate time to collision with a target position"""
        for i, point in enumerate(trajectory):
            distance = np.sqrt((point.position[0] - target_position[0])**2 + 
                             (point.position[1] - target_position[1])**2)
            
            if distance <= safety_radius:
                return point.timestamp
                
        return None
        
    def get_prediction_uncertainty(self, trajectory: List[TrajectoryPoint]) -> Dict:
        """Get uncertainty metrics for trajectory prediction"""
        if not trajectory:
            return {}
            
        uncertainties = [np.trace(point.covariance) for point in trajectory]
        confidences = [point.confidence for point in trajectory]
        
        return {
            'mean_uncertainty': np.mean(uncertainties),
            'max_uncertainty': np.max(uncertainties),
            'min_confidence': np.min(confidences),
            'uncertainty_growth_rate': (uncertainties[-1] - uncertainties[0]) / len(uncertainties) if len(uncertainties) > 1 else 0,
            'final_uncertainty': uncertainties[-1] if uncertainties else 0
        }
        
    def cleanup_old_objects(self, active_object_ids: List[int]):
        """Remove Kalman filters for objects no longer being tracked"""
        to_remove = []
        for obj_id in self.kalman_filters:
            if obj_id not in active_object_ids:
                to_remove.append(obj_id)
                
        for obj_id in to_remove:
            del self.kalman_filters[obj_id]
            
    def get_trajectory_envelope(self, trajectory: List[TrajectoryPoint],
                               confidence_level: float = 0.95) -> Tuple[List[Tuple[float, float]], 
                                                                        List[Tuple[float, float]]]:
        """Get upper and lower bounds of trajectory uncertainty envelope"""
        upper_bound = []
        lower_bound = []
        
        for point in trajectory:
            # Get uncertainty ellipse
            center, width, height, angle = self.get_uncertainty_ellipse(point, confidence_level)
            
            # Simple approximation: use major axis as uncertainty bound
            uncertainty_radius = max(width, height) / 2
            
            upper_bound.append((center[0] + uncertainty_radius, center[1] + uncertainty_radius))
            lower_bound.append((center[0] - uncertainty_radius, center[1] - uncertainty_radius))
            
        return upper_bound, lower_bound