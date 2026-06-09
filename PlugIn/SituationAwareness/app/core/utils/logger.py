"""
Logging and Data Export Module for UAM Operations System

This module provides comprehensive logging capabilities and CSV export functionality
for system events, object detections, safety metrics, and advisory decisions.
"""

from __future__ import annotations

import logging
import csv
import json
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import os

from ..detection.object_detector import DetectedObject
from ..utils.safety_metrics import SafetyMetrics
from ..ahp.ahp_processor import AHPResult

class UAMLogger:
    """Comprehensive logging system for UAM operations"""
    
    def __init__(self, log_directory: str = "logs", enable_file_logging: bool = False):
        self.enable_file_logging = enable_file_logging
        
        if not self.enable_file_logging:
            # Disable all file logging - only console logging
            self.logger = logging.getLogger(__name__)
            self.logger.info("File logging disabled")
            return
            
        self.log_directory = Path(log_directory)
        self.log_directory.mkdir(exist_ok=True)
        
        # Create timestamped session directory
        self.session_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.log_directory / f"session_{self.session_time}"
        self.session_dir.mkdir(exist_ok=True)
        
        # Initialize logging files
        self.setup_loggers()
        self.setup_csv_files()
        
        # Data buffers
        self.detection_buffer = []
        self.metrics_buffer = []
        self.advisory_buffer = []
        self.system_events_buffer = []
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"UAM Logger initialized for session {self.session_time}")
        
    def setup_loggers(self):
        """Setup different loggers for different components"""
        if not self.enable_file_logging:
            return
            
        # Main system logger
        main_logger = logging.getLogger('uam_system')
        main_handler = logging.FileHandler(self.session_dir / 'system.log')
        main_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        main_handler.setFormatter(main_formatter)
        main_logger.addHandler(main_handler)
        main_logger.setLevel(logging.INFO)
        
        # Detection logger
        detection_logger = logging.getLogger('detection')
        detection_handler = logging.FileHandler(self.session_dir / 'detection.log')
        detection_handler.setFormatter(main_formatter)
        detection_logger.addHandler(detection_handler)
        detection_logger.setLevel(logging.DEBUG)
        
        # Safety logger
        safety_logger = logging.getLogger('safety')
        safety_handler = logging.FileHandler(self.session_dir / 'safety.log')
        safety_handler.setFormatter(main_formatter)
        safety_logger.addHandler(safety_handler)
        safety_logger.setLevel(logging.INFO)
        
        # AHP logger
        ahp_logger = logging.getLogger('ahp')
        ahp_handler = logging.FileHandler(self.session_dir / 'ahp_decisions.log')
        ahp_handler.setFormatter(main_formatter)
        ahp_logger.addHandler(ahp_handler)
        ahp_logger.setLevel(logging.INFO)
        
    def setup_csv_files(self):
        """Setup CSV files for data export"""
        if not self.enable_file_logging:
            return
            
        # Object detections CSV
        self.detections_csv = self.session_dir / 'object_detections.csv'
        self.detections_fieldnames = [
            'timestamp', 'session_id', 'object_id', 'class_name', 'confidence',
            'bbox_x1', 'bbox_y1', 'bbox_x2', 'bbox_y2', 'centroid_x', 'centroid_y',
            'velocity_x', 'velocity_y', 'estimated_distance', 'speed'
        ]
        
        # Safety metrics CSV
        self.metrics_csv = self.session_dir / 'safety_metrics.csv'
        self.metrics_fieldnames = [
            'timestamp', 'session_id', 'object_id', 'distance', 'time_to_collision',
            'relative_velocity', 'approach_rate', 'uncertainty', 'bearing_rate',
            'normalized_distance', 'normalized_ttc', 'normalized_velocity',
            'normalized_uncertainty', 'composite_risk'
        ]
        
        # Advisory decisions CSV
        self.advisory_csv = self.session_dir / 'advisory_decisions.csv'
        self.advisory_fieldnames = [
            'timestamp', 'session_id', 'risk_score', 'risk_level', 'recommended_action',
            'confidence', 'num_objects', 'closest_distance', 'shortest_ttc',
            'criteria_distance', 'criteria_ttc', 'criteria_uncertainty', 'criteria_velocity'
        ]
        
        # System events CSV
        self.events_csv = self.session_dir / 'system_events.csv'
        self.events_fieldnames = [
            'timestamp', 'session_id', 'event_type', 'component', 'description', 'data'
        ]
        
        # Initialize CSV files with headers
        for csv_file, fieldnames in [
            (self.detections_csv, self.detections_fieldnames),
            (self.metrics_csv, self.metrics_fieldnames),
            (self.advisory_csv, self.advisory_fieldnames),
            (self.events_csv, self.events_fieldnames)
        ]:
            with open(csv_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
    def log_detection(self, detected_object: DetectedObject):
        """Log object detection data"""
        if not self.enable_file_logging:
            return
            
        timestamp = datetime.now().isoformat()
        
        detection_data = {
            'timestamp': timestamp,
            'session_id': self.session_time,
            'object_id': detected_object.obj_id,
            'class_name': detected_object.class_name,
            'confidence': detected_object.confidence,
            'bbox_x1': detected_object.bbox[0],
            'bbox_y1': detected_object.bbox[1],
            'bbox_x2': detected_object.bbox[2],
            'bbox_y2': detected_object.bbox[3],
            'centroid_x': detected_object.centroid[0],
            'centroid_y': detected_object.centroid[1],
            'velocity_x': detected_object.velocity[0],
            'velocity_y': detected_object.velocity[1],
            'estimated_distance': detected_object.distance,
            'speed': detected_object.get_speed()
        }
        
        self.detection_buffer.append(detection_data)
        
        # Log to detection logger
        detection_logger = logging.getLogger('detection')
        detection_logger.info(
            f"Object detected: ID={detected_object.obj_id}, "
            f"Class={detected_object.class_name}, "
            f"Confidence={detected_object.confidence:.3f}, "
            f"Distance={detected_object.distance:.1f}m"
        )
        
    def log_safety_metrics(self, object_id: int, metrics: SafetyMetrics):
        """Log safety metrics data"""
        if not self.enable_file_logging:
            return
            
        timestamp = datetime.now().isoformat()
        
        metrics_data = {
            'timestamp': timestamp,
            'session_id': self.session_time,
            'object_id': object_id,
            'distance': metrics.distance,
            'time_to_collision': metrics.time_to_collision,
            'relative_velocity': metrics.relative_velocity,
            'approach_rate': metrics.approach_rate,
            'uncertainty': metrics.uncertainty,
            'bearing_rate': metrics.bearing_rate,
            'normalized_distance': metrics.normalized_distance,
            'normalized_ttc': metrics.normalized_ttc,
            'normalized_velocity': metrics.normalized_velocity,
            'normalized_uncertainty': metrics.normalized_uncertainty,
            'composite_risk': metrics.composite_risk
        }
        
        self.metrics_buffer.append(metrics_data)
        
        # Log to safety logger
        safety_logger = logging.getLogger('safety')
        safety_logger.info(
            f"Safety metrics calculated: ID={object_id}, "
            f"Distance={metrics.distance:.1f}m, "
            f"TTC={metrics.time_to_collision}, "
            f"Risk={metrics.composite_risk:.3f}"
        )
        
    def log_advisory_decision(self, ahp_result: AHPResult, context: Optional[Dict] = None):
        """Log AHP advisory decision"""
        if not self.enable_file_logging:
            return
            
        timestamp = datetime.now().isoformat()
        
        advisory_data = {
            'timestamp': timestamp,
            'session_id': self.session_time,
            'risk_score': ahp_result.risk_score,
            'risk_level': ahp_result.risk_level.value,
            'recommended_action': ahp_result.recommended_action.value,
            'confidence': ahp_result.confidence,
            'num_objects': context.get('num_objects', 0) if context else 0,
            'closest_distance': context.get('closest_distance', None) if context else None,
            'shortest_ttc': context.get('shortest_ttc', None) if context else None,
            'criteria_distance': ahp_result.criteria_scores.get('distance', 0),
            'criteria_ttc': ahp_result.criteria_scores.get('time_to_collision', 0),
            'criteria_uncertainty': ahp_result.criteria_scores.get('uncertainty', 0),
            'criteria_velocity': ahp_result.criteria_scores.get('velocity', 0)
        }
        
        self.advisory_buffer.append(advisory_data)
        
        # Log to AHP logger
        ahp_logger = logging.getLogger('ahp')
        ahp_logger.info(
            f"Advisory decision: Risk={ahp_result.risk_score:.3f}, "
            f"Level={ahp_result.risk_level.value}, "
            f"Action={ahp_result.recommended_action.value}, "
            f"Confidence={ahp_result.confidence:.3f}"
        )
        
    def log_system_event(self, event_type: str, component: str, description: str, data: Optional[Dict] = None):
        """Log system events"""
        if not self.enable_file_logging:
            return
            
        timestamp = datetime.now().isoformat()
        
        event_data = {
            'timestamp': timestamp,
            'session_id': self.session_time,
            'event_type': event_type,
            'component': component,
            'description': description,
            'data': json.dumps(data) if data else None
        }
        
        self.system_events_buffer.append(event_data)
        
        # Log to main system logger
        main_logger = logging.getLogger('uam_system')
        if event_type == 'ERROR':
            main_logger.error(f"{component}: {description}")
        elif event_type == 'WARNING':
            main_logger.warning(f"{component}: {description}")
        else:
            main_logger.info(f"{component}: {description}")
            
    def log_uav_state(self, uav_state: UAVState):
        """Log UAV state information"""
        if not self.enable_file_logging:
            return
            
        state_data = {
            'position': uav_state.position,
            'velocity': uav_state.velocity,
            'altitude_agl': uav_state.altitude_agl,
            'heading': uav_state.heading,
            'collision_detected': uav_state.collision_detected
        }
        
        self.log_system_event('UAV_STATE', 'AirSim', 'UAV state update', state_data)
        
    def flush_buffers(self):
        """Write buffered data to CSV files"""
        try:
            # Write detections
            if self.detection_buffer:
                with open(self.detections_csv, 'a', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=self.detections_fieldnames)
                    writer.writerows(self.detection_buffer)
                self.detection_buffer.clear()
                
            # Write metrics
            if self.metrics_buffer:
                with open(self.metrics_csv, 'a', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=self.metrics_fieldnames)
                    writer.writerows(self.metrics_buffer)
                self.metrics_buffer.clear()
                
            # Write advisory decisions
            if self.advisory_buffer:
                with open(self.advisory_csv, 'a', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=self.advisory_fieldnames)
                    writer.writerows(self.advisory_buffer)
                self.advisory_buffer.clear()
                
            # Write system events
            if self.system_events_buffer:
                with open(self.events_csv, 'a', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=self.events_fieldnames)
                    writer.writerows(self.system_events_buffer)
                self.system_events_buffer.clear()
                
        except Exception as e:
            self.logger.error(f"Error flushing buffers: {e}")
            
    def export_session_summary(self) -> Dict:
        """Export session summary statistics"""
        if not self.enable_file_logging:
            return {}
            
        try:
            summary = {
                'session_id': self.session_time,
                'start_time': self.session_time,
                'end_time': datetime.now().isoformat(),
                'total_detections': 0,
                'total_advisories': 0,
                'risk_level_counts': {},
                'object_class_counts': {},
                'average_risk_score': 0.0,
                'max_risk_score': 0.0,
                'emergency_events': 0
            }
            
            # Analyze detections
            if self.detections_csv.exists():
                df_detections = pd.read_csv(self.detections_csv)
                summary['total_detections'] = len(df_detections)
                summary['object_class_counts'] = df_detections['class_name'].value_counts().to_dict()
                
            # Analyze advisory decisions
            if self.advisory_csv.exists():
                df_advisory = pd.read_csv(self.advisory_csv)
                summary['total_advisories'] = len(df_advisory)
                summary['risk_level_counts'] = df_advisory['risk_level'].value_counts().to_dict()
                summary['average_risk_score'] = df_advisory['risk_score'].mean()
                summary['max_risk_score'] = df_advisory['risk_score'].max()
                summary['emergency_events'] = len(df_advisory[df_advisory['risk_level'] == 'EMERGENCY'])
                
            # Save summary
            summary_file = self.session_dir / 'session_summary.json'
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
                
            return summary
            
        except Exception as e:
            self.logger.error(f"Error creating session summary: {e}")
            return {}
            
    def create_data_visualization(self):
        """Create basic data visualizations"""
        try:
            import matplotlib.pyplot as plt
            
            # Risk score over time
            if self.advisory_csv.exists():
                df = pd.read_csv(self.advisory_csv)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                
                fig, axes = plt.subplots(2, 2, figsize=(15, 10))
                
                # Risk score timeline
                axes[0, 0].plot(df['timestamp'], df['risk_score'])
                axes[0, 0].set_title('Risk Score Over Time')
                axes[0, 0].set_ylabel('Risk Score')
                axes[0, 0].tick_params(axis='x', rotation=45)
                
                # Risk level distribution
                risk_counts = df['risk_level'].value_counts()
                axes[0, 1].pie(risk_counts.values, labels=risk_counts.index, autopct='%1.1f%%')
                axes[0, 1].set_title('Risk Level Distribution')
                
                # Advisory actions
                action_counts = df['recommended_action'].value_counts()
                axes[1, 0].bar(range(len(action_counts)), action_counts.values)
                axes[1, 0].set_xticks(range(len(action_counts)))
                axes[1, 0].set_xticklabels(action_counts.index, rotation=45, ha='right')
                axes[1, 0].set_title('Advisory Actions')
                
                # Confidence over time
                axes[1, 1].plot(df['timestamp'], df['confidence'])
                axes[1, 1].set_title('Decision Confidence Over Time')
                axes[1, 1].set_ylabel('Confidence')
                axes[1, 1].tick_params(axis='x', rotation=45)
                
                plt.tight_layout()
                plt.savefig(self.session_dir / 'risk_analysis.png', dpi=300, bbox_inches='tight')
                plt.close()
                
        except ImportError:
            self.logger.warning("Matplotlib not available for visualization")
        except Exception as e:
            self.logger.error(f"Error creating visualizations: {e}")
            
    def close_session(self):
        """Close logging session and finalize data"""
        self.flush_buffers()
        summary = self.export_session_summary()
        self.create_data_visualization()
        
        self.logger.info(f"Session {self.session_time} closed. Summary: {summary}")
        
        return summary
