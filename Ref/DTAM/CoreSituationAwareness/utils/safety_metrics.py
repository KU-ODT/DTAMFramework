"""
Safety Metrics Calculation Module for UAM Operations System

This module calculates safety performance metrics including distance,
time-to-collision, relative velocity, and uncertainty measures.
"""

import numpy as np
import math
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import logging

from ..detection.object_detector import DetectedObject
from ..prediction.gaussian_predictor import TrajectoryPoint

@dataclass
class SafetyMetrics:
    """Container for safety performance metrics"""
    distance: float  # Distance to object (meters)
    time_to_collision: Optional[float]  # TTC in seconds (None if no collision)
    relative_velocity: float  # Relative velocity magnitude (m/s)
    approach_rate: float  # Rate of approach (m/s, positive if approaching)
    uncertainty: float  # Positional uncertainty metric
    bearing_rate: float  # Rate of bearing change (rad/s)
    normalized_distance: float  # Distance normalized to [0, 1]
    normalized_ttc: float  # TTC normalized to [0, 1]
    normalized_velocity: float  # Velocity normalized to [0, 1]
    normalized_uncertainty: float  # Uncertainty normalized to [0, 1]
    composite_risk: float  # Combined risk metric [0, 1]

class SafetyMetricsCalculator:
    """Calculator for UAM safety performance metrics"""
    
    def __init__(self, uav_position: Tuple[float, float] = (0, 0),
                 uav_velocity: Tuple[float, float] = (0, 0),
                 safety_radius: float = 10.0,
                 pixel_to_meter_ratio: float = 0.1):
        self.logger = logging.getLogger(__name__)
        
        # UAV state
        self.uav_position = np.array(uav_position)
        self.uav_velocity = np.array(uav_velocity)
        
        # Safety parameters
        self.safety_radius = safety_radius  # meters
        self.pixel_to_meter_ratio = pixel_to_meter_ratio  # meters per pixel
        
        # Normalization parameters
        self.max_detection_range = 100.0  # meters
        self.max_velocity = 30.0  # m/s
        self.max_ttc = 60.0  # seconds
        self.max_uncertainty = 10.0  # meters
        
    def update_uav_state(self, position: Tuple[float, float], 
                        velocity: Tuple[float, float]):
        """Update UAV position and velocity"""
        self.uav_position = np.array(position)
        self.uav_velocity = np.array(velocity)
        
    def calculate_metrics(self, detected_object: DetectedObject,
                         trajectory: Optional[List[TrajectoryPoint]] = None) -> SafetyMetrics:
        """Calculate comprehensive safety metrics for a detected object"""
        
        # Convert pixel coordinates to meters
        obj_position = np.array([
            detected_object.centroid[0] * self.pixel_to_meter_ratio,
            detected_object.centroid[1] * self.pixel_to_meter_ratio
        ])
        
        obj_velocity = np.array([
            detected_object.velocity[0] * self.pixel_to_meter_ratio,
            detected_object.velocity[1] * self.pixel_to_meter_ratio
        ])
        
        # Basic distance calculation
        distance = self._calculate_distance(obj_position)
        
        # Relative velocity
        relative_velocity = self._calculate_relative_velocity(obj_velocity)
        
        # Approach rate (positive if approaching)
        approach_rate = self._calculate_approach_rate(obj_position, obj_velocity)
        
        # Time to collision
        ttc = self._calculate_time_to_collision(obj_position, obj_velocity)
        
        # Bearing rate
        bearing_rate = self._calculate_bearing_rate(obj_position, obj_velocity)
        
        # Uncertainty (use trajectory if available)
        uncertainty = self._calculate_uncertainty(detected_object, trajectory)
        
        # Normalize metrics
        norm_distance = self._normalize_distance(distance)
        norm_ttc = self._normalize_ttc(ttc)
        norm_velocity = self._normalize_velocity(np.linalg.norm(relative_velocity))
        norm_uncertainty = self._normalize_uncertainty(uncertainty)
        
        # Calculate composite risk
        composite_risk = self._calculate_composite_risk(
            norm_distance, norm_ttc, norm_velocity, norm_uncertainty)
        
        return SafetyMetrics(
            distance=distance,
            time_to_collision=ttc,
            relative_velocity=np.linalg.norm(relative_velocity),
            approach_rate=approach_rate,
            uncertainty=uncertainty,
            bearing_rate=bearing_rate,
            normalized_distance=norm_distance,
            normalized_ttc=norm_ttc,
            normalized_velocity=norm_velocity,
            normalized_uncertainty=norm_uncertainty,
            composite_risk=composite_risk
        )
        
    def _calculate_distance(self, obj_position: np.ndarray) -> float:
        """Calculate Euclidean distance to object"""
        return np.linalg.norm(obj_position - self.uav_position)
        
    def _calculate_relative_velocity(self, obj_velocity: np.ndarray) -> np.ndarray:
        """Calculate relative velocity vector"""
        return obj_velocity - self.uav_velocity
        
    def _calculate_approach_rate(self, obj_position: np.ndarray, 
                                obj_velocity: np.ndarray) -> float:
        """Calculate rate of approach (positive if approaching)"""
        relative_position = obj_position - self.uav_position
        relative_velocity = obj_velocity - self.uav_velocity
        
        if np.linalg.norm(relative_position) == 0:
            return 0.0
            
        # Project relative velocity onto relative position vector
        unit_position = relative_position / np.linalg.norm(relative_position)
        approach_rate = -np.dot(relative_velocity, unit_position)
        
        return approach_rate
        
    def _calculate_time_to_collision(self, obj_position: np.ndarray,
                                   obj_velocity: np.ndarray) -> Optional[float]:
        """Calculate time to collision using closest point of approach"""
        relative_position = obj_position - self.uav_position
        relative_velocity = obj_velocity - self.uav_velocity
        
        # If no relative velocity, no collision
        rel_speed_squared = np.dot(relative_velocity, relative_velocity)
        if rel_speed_squared < 1e-6:
            return None
            
        # Time to closest point of approach
        t_cpa = -np.dot(relative_position, relative_velocity) / rel_speed_squared
        
        # If CPA is in the past, no future collision
        if t_cpa < 0:
            return None
            
        # Distance at closest point of approach
        pos_at_cpa = relative_position + relative_velocity * t_cpa
        distance_at_cpa = np.linalg.norm(pos_at_cpa)
        
        # Check if collision occurs within safety radius
        if distance_at_cpa <= self.safety_radius:
            # Calculate exact collision time
            # Solve: |relative_position + relative_velocity * t| = safety_radius
            a = rel_speed_squared
            b = 2 * np.dot(relative_position, relative_velocity)
            c = np.dot(relative_position, relative_position) - self.safety_radius**2
            
            discriminant = b**2 - 4*a*c
            if discriminant >= 0:
                t1 = (-b - np.sqrt(discriminant)) / (2*a)
                t2 = (-b + np.sqrt(discriminant)) / (2*a)
                
                # Return the smaller positive time
                if t1 > 0:
                    return t1
                elif t2 > 0:
                    return t2
                    
        return None
        
    def _calculate_bearing_rate(self, obj_position: np.ndarray,
                               obj_velocity: np.ndarray) -> float:
        """Calculate rate of bearing change"""
        relative_position = obj_position - self.uav_position
        relative_velocity = obj_velocity - self.uav_velocity
        
        distance = np.linalg.norm(relative_position)
        if distance < 1e-6:
            return 0.0
            
        # Cross product gives bearing rate
        bearing_rate = np.cross(relative_position, relative_velocity) / (distance**2)
        
        return abs(bearing_rate)
        
    def _calculate_uncertainty(self, detected_object: DetectedObject,
                              trajectory: Optional[List[TrajectoryPoint]]) -> float:
        """Calculate positional uncertainty metric"""
        if trajectory and len(trajectory) > 0:
            # Use trajectory uncertainty if available
            future_point = trajectory[min(10, len(trajectory)-1)]  # ~0.33 seconds ahead
            uncertainty = np.trace(future_point.covariance)
            return np.sqrt(uncertainty) * self.pixel_to_meter_ratio
        else:
            # Estimate uncertainty from detection confidence and velocity
            base_uncertainty = (1.0 - detected_object.confidence) * 2.0  # meters
            velocity_uncertainty = detected_object.get_speed() * self.pixel_to_meter_ratio * 0.1
            return base_uncertainty + velocity_uncertainty
            
    def _normalize_distance(self, distance: float) -> float:
        """Normalize distance to [0, 1] where 0 is far, 1 is close"""
        normalized = 1.0 - min(distance / self.max_detection_range, 1.0)
        return max(0.0, normalized)
        
    def _normalize_ttc(self, ttc: Optional[float]) -> float:
        """Normalize TTC to [0, 1] where 0 is safe, 1 is imminent collision"""
        if ttc is None:
            return 0.0
        normalized = 1.0 - min(ttc / self.max_ttc, 1.0)
        return max(0.0, normalized)
        
    def _normalize_velocity(self, velocity: float) -> float:
        """Normalize velocity to [0, 1]"""
        normalized = min(velocity / self.max_velocity, 1.0)
        return max(0.0, normalized)
        
    def _normalize_uncertainty(self, uncertainty: float) -> float:
        """Normalize uncertainty to [0, 1]"""
        normalized = min(uncertainty / self.max_uncertainty, 1.0)
        return max(0.0, normalized)
        
    def _calculate_composite_risk(self, norm_distance: float, norm_ttc: float,
                                 norm_velocity: float, norm_uncertainty: float) -> float:
        """Calculate composite risk score using weighted combination"""
        # Simple weighted average (will be replaced by AHP)
        weights = {
            'distance': 0.4,
            'ttc': 0.3,
            'velocity': 0.2,
            'uncertainty': 0.1
        }
        
        composite = (weights['distance'] * norm_distance +
                    weights['ttc'] * norm_ttc +
                    weights['velocity'] * norm_velocity +
                    weights['uncertainty'] * norm_uncertainty)
        
        return min(1.0, max(0.0, composite))
        
    def calculate_multiple_objects_risk(self, objects_metrics: List[SafetyMetrics]) -> Dict:
        """Calculate aggregate risk metrics for multiple objects"""
        if not objects_metrics:
            return {
                'max_risk': 0.0,
                'average_risk': 0.0,
                'critical_objects': 0,
                'total_objects': 0,
                'closest_distance': float('inf'),
                'shortest_ttc': None
            }
            
        risks = [m.composite_risk for m in objects_metrics]
        distances = [m.distance for m in objects_metrics]
        ttcs = [m.time_to_collision for m in objects_metrics if m.time_to_collision is not None]
        
        return {
            'max_risk': max(risks),
            'average_risk': np.mean(risks),
            'critical_objects': sum(1 for r in risks if r > 0.6),
            'total_objects': len(objects_metrics),
            'closest_distance': min(distances),
            'shortest_ttc': min(ttcs) if ttcs else None
        }
        
    def get_risk_category(self, composite_risk: float) -> Tuple[str, str]:
        """Get risk category and color for visualization"""
        if composite_risk <= 0.3:
            return "SAFE", "#00AA00"
        elif composite_risk <= 0.6:
            return "CAUTION", "#FFAA00"
        else:
            return "EMERGENCY", "#FF0000"
            
    def generate_safety_report(self, metrics: SafetyMetrics) -> Dict:
        """Generate comprehensive safety report"""
        category, color = self.get_risk_category(metrics.composite_risk)
        
        return {
            'risk_level': metrics.composite_risk,
            'category': category,
            'color': color,
            'distance_m': metrics.distance,
            'ttc_s': metrics.time_to_collision,
            'relative_speed_ms': metrics.relative_velocity,
            'approach_rate_ms': metrics.approach_rate,
            'uncertainty_m': metrics.uncertainty,
            'bearing_rate_rads': metrics.bearing_rate,
            'is_approaching': metrics.approach_rate > 0.1,
            'is_critical': metrics.composite_risk > 0.6,
            'requires_action': metrics.time_to_collision is not None and metrics.time_to_collision < 10.0
        }