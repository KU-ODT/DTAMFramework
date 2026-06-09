"""Phase 5 메시지 — 4001 Vehicle Status, 4101/4102 Camera, 4103 Collision."""
from __future__ import annotations
import dataclasses as _dc
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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
class Energy:
    battery_pct: float = 100.0
    state_of_charge_pct: float = 100.0


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
    energy: Energy = field(default_factory=Energy)
    navigation: Dict[str, Any] = field(default_factory=dict)
    collision: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Msg4001_VehicleStatus:
    """MSG 4001: 비행체 상태 정보 — 주기 송신.

    Wire format (ICD 명세, ``4001_vehicleStatus.md``)::

        {
          "timestamp": "<ISO-8601 UTC>",
          "<VEHICLE_ID_1>": { ...VehicleData... },
          "<VEHICLE_ID_2>": { ...VehicleData... }
        }

    Python 코드에서는 동적 vehicleId 키를 ``vehicles: Dict[str, VehicleData]``
    로 묶어 다루지만, ``to_wire()`` / ``from_wire()`` 가 wrapper 를 풀고/씌워
    ICD 명세와 정확히 일치하는 flat dict 로 변환한다. SDK 의 ``to_dict`` /
    ``parse_payload`` 가 이 메서드들을 자동으로 호출한다.
    """
    timestamp: str = ""
    vehicles: Dict[str, "VehicleData"] = field(default_factory=dict)

    def to_wire(self) -> Dict[str, Any]:
        """dataclass → ICD wire dict (flat).

        ``vehicles`` wrapper 를 풀어 vehicleId 키를 top-level 로 직접 노출.
        """
        out: Dict[str, Any] = {"timestamp": self.timestamp}
        for vid, vdata in self.vehicles.items():
            if _dc.is_dataclass(vdata) and not isinstance(vdata, type):
                item = _dc.asdict(vdata)
                if not item.get("navigation"):
                    item.pop("navigation", None)
                if not item.get("collision"):
                    item.pop("collision", None)
                out[str(vid)] = item
            elif isinstance(vdata, dict):
                item = dict(vdata)
                if not item.get("navigation"):
                    item.pop("navigation", None)
                if not item.get("collision"):
                    item.pop("collision", None)
                out[str(vid)] = item
            else:
                out[str(vid)] = vdata
        return out

    @classmethod
    def from_wire(cls, data: Dict[str, Any]) -> "Msg4001_VehicleStatus":
        """ICD wire dict (flat) → dataclass 인스턴스.

        ``timestamp`` 외의 top-level 키는 모두 vehicleId 로 보고 ``VehicleData``
        로 변환해 ``vehicles`` 딕셔너리에 채워 넣는다. dict 가 아니거나 alias
        가 ``timestamp`` 인 항목은 무시.
        """
        # 순환 import 방지를 위한 deferred import — icd_registry 가 본 모듈을 import 함.
        from .icd_registry import _dict_to_dataclass

        if not isinstance(data, dict):
            return cls()
        ts = str(data.get("timestamp", "") or "")
        vehicles: Dict[str, VehicleData] = {}
        for key, value in data.items():
            if key == "timestamp" or not isinstance(value, dict):
                continue
            vehicles[str(key)] = _dict_to_dataclass(VehicleData, value)
        return cls(timestamp=ts, vehicles=vehicles)


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
    image_b64: Optional[str] = None


@dataclass
class Msg4102_CameraStreamDescriptor:
    """MSG 4102: camera stream metadata descriptor.

    This message does not carry image bytes. It announces an on-demand
    media-plane endpoint such as VisualizationModule's direct MJPEG URL while
    keeping stream discovery, auditing, and subscriptions inside DTAM ICD.
    """
    message_id: int = 4102
    message_name: str = "Camera Stream Descriptor"
    timestamp: str = ""
    stream_id: str = "default-front-center"
    vehicle_id: str = "UAM0001"
    airsim_vehicle_name: str = ""
    camera_name: str = "front_center"
    stream_type: str = "mjpeg"         # mjpeg|webrtc|rtsp|snapshot
    transport: str = "http"
    codec: str = "mjpeg"
    encoding: str = "jpeg"
    url: str = ""
    control_mid: str = "5002"
    fps: float = 2.0
    quality: int = 70
    width: int = 0
    height: int = 0
    status: str = "available"          # available|disabled|error
    expires_at: Optional[str] = None
    note: Optional[str] = None


@dataclass
class Msg4103_VehicleCollisionEvent:
    """MSG 4103: Vehicle collision event detected by Visualization/AirSim.

    This is an event-driven status message. VisualizationModule reads
    AirSim/Unreal collision data and sends the normalized event through DTAM so
    VehicleModule can decide the actual flight-state response.
    """
    message_id: int = 4103
    message_name: str = "Vehicle Collision Event"
    timestamp: str = ""
    eventId: str = ""
    aircraftId: str = "UAM0001"
    airsimVehicleName: str = ""
    hasCollided: bool = True
    objectName: str = ""
    objectId: int = -1
    positionNed: Position = field(default_factory=Position)
    impactPointNed: Position = field(default_factory=Position)
    normalNed: Position = field(default_factory=Position)
    penetrationDepth: float = 0.0
    collisionTimeNanos: int = 0
    impactSpeedMps: float = 0.0
    severity: str = "warning"           # info|warning|critical|fatal
    recommendedAction: str = "hold"     # none|hold|emergency_stop|abort
    source: str = "airsim.simGetCollisionInfo"
    metadata: Dict[str, Any] = field(default_factory=dict)
