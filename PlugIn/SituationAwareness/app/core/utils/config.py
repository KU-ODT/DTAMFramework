"""
Configuration loader for UAM Operations System
"""

try:
    import yaml
except Exception:  # pragma: no cover - optional dependency fallback
    yaml = None
import os
from typing import Dict, Any

class ConfigLoader:
    """Load and manage system configuration"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Try multiple possible locations
            # base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            # possible_paths = [
            #     os.path.join(base_dir, "config", "system_config.yaml"),  # User's location
            #     os.path.join(base_dir, "src", "config", "system_config.yaml"),  # Original location
            # ]
            core_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

            possible_paths = [
                os.path.join(core_dir, "config", "system_config.yaml"),
            ]
            
            config_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    config_path = path
                    break
                    
            if config_path is None:
                config_path = possible_paths[0]  # Default to first option
            
        self.config_path = config_path
        self.config = self.load_config()
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if yaml is None:
            print("Warning: PyYAML is not installed; using default Situation Awareness config")
            return self.get_default_config()
        try:
            with open(self.config_path, 'r') as file:
                config = yaml.safe_load(file)
                return config
        except Exception as e:
            print(f"Warning: Could not load config from {self.config_path}: {e}")
            return self.get_default_config()
            
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration if file loading fails"""
        return {
            'detection': {
                'model_path': 'models/yolo11n.pt',
                'confidence_threshold': 0.5,
                'nms_threshold': 0.4,
                'max_objects': 20
            },
            'camera': {
                'device_index': 0,
                'width': 640,
                'height': 480,
                'fps': 30
            },
            'safety': {
                'safety_radius_m': 10.0,
                'max_detection_range_m': 100.0,
                'max_velocity_ms': 30.0,
                'max_ttc_s': 60.0,
                'pixel_to_meter_ratio': 0.1
            },
            'ahp': {
                'safe_threshold': 0.3,
                'emergency_threshold': 0.6
            },
            'airsim': {
                'ip_address': '127.0.0.1',
                'vehicle_name': 'Drone1',
                'enable_lidar': True
            }
        }
        
    def get(self, key_path: str, default=None):
        """Get configuration value using dot notation (e.g., 'detection.model_path')"""
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
            
    def get_detection_config(self) -> Dict[str, Any]:
        """Get detection-specific configuration"""
        return self.config.get('detection', {})
        
    def get_camera_config(self) -> Dict[str, Any]:
        """Get camera-specific configuration"""
        return self.config.get('camera', {})
        
    def get_safety_config(self) -> Dict[str, Any]:
        """Get safety-specific configuration"""
        return self.config.get('safety', {})
        
    def get_ahp_config(self) -> Dict[str, Any]:
        """Get AHP-specific configuration"""
        return self.config.get('ahp', {})
        
    def get_airsim_config(self) -> Dict[str, Any]:
        """Get AirSim-specific configuration"""
        return self.config.get('airsim', {})

# Global config instance
_config = None

def get_config() -> ConfigLoader:
    """Get global configuration instance"""
    global _config
    if _config is None:
        _config = ConfigLoader()
    return _config
