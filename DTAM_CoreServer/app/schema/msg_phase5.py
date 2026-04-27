"""Phase 5 메시지 — 4001 Vehicle Status, 4101 Camera Image Frame."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .icd_common import Vec3, Quaternion


# ── MSG 4001 ─────────────────────────────────────────────

@dataclass
class Position:
    north: float = 0.0                 # m, NED
    east: float = 0.0
    down: float = 0.0


@dataclass
class Attitude:
    roll: float = 0.0                  # rad
    pitch: float = 0.0
    yaw: float = 0.0


@dataclass
class Actuator:
    tilt_left: float = 0.0            # 0..1
    tilt_right: float = 0.0
    aileron: float = 0.0              # deg
    rudder_left: float = 0.0
    rudder_right: float = 0.0


@dataclass
class Propulsion:
    motor_rpm: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])


@dataclass
class GPS:
    is_valid: bool = False
    fix_type: int = 0
    latitude: float = 0.0
    longitude: float = 0.0
    altitude: float = 0.0
    velocity_north: float = 0.0
    velocity_east: float = 0.0
    velocity_down: float = 0.0
    eph: float = 0.0
    epv: float = 0.0


@dataclass
class IMU:
    orientation: Quaternion = field(default_factory=Quaternion)
    angular_velocity: Vec3 = field(default_factory=Vec3)
    linear_acceleration: Vec3 = field(default_factory=Vec3)


@dataclass
class Barometer:
    altitude: float = 0.0
    pressure: float = 101325.0
    qnh: float = 1013.25


@dataclass
class VehicleData:
    """단일 비행체 상태 (4001 payload 내 UAM0001 등의 값)."""
    currentWaypointId: str = ""
    position: Position = field(default_factory=Position)
    attitude: Attitude = field(default_factory=Attitude)
    actuator: Actuator = field(default_factory=Actuator)
    propulsion: Propulsion = field(default_factory=Propulsion)
    gps: GPS = field(default_factory=GPS)
    imu: IMU = field(default_factory=IMU)
    barometer: Barometer = field(default_factory=Barometer)


@dataclass
class Msg4001_VehicleStatus:
    """MSG 4001: 비행체 상태 정보 — 주기 송신.

    payload 구조: {"timestamp": "...", "UAM0001": {...}, "UAM0002": {...}}
    vehicles 필드에 aircraftId → VehicleData 매핑.
    """
    timestamp: str = ""
    vehicles: Dict[str, VehicleData] = field(default_factory=dict)


# ── MSG 4101 ─────────────────────────────────────────────

@dataclass
class Msg4101_CameraImageFrame:
    """MSG 4101: 카메라 이미지 프레임 — 헤더 JSON."""
    message_id: int = 4101
    message_name: str = "Camera Image Frame"
    timestamp: str = ""
    vehicle_id: str = ""
    camera_name: str = "front_center"
    image_type: str = "scene"          # scene|depth_planar|depth_perspective|...
    sequence: int = 0
    width: int = 0
    height: int = 0
    channels: int = 3
    pixel_format: str = "rgb8"
    encoding: str = "jpeg"
    payload_size: int = 0
    checksum: Optional[str] = None
    unit: Optional[str] = None
    frame_id: Optional[str] = None
