"""Common types and interfaces for operator-driven air mobility dynamics."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List

from ..transform.coord_transform import LocalNEDFrame


def _clamp_axis(value: float) -> float:
    return max(-1.0, min(1.0, float(value)))


def build_manual_waypoint_id(flight_plan_number: int, label: str = "MANUAL", seq: int = 1) -> str:
    return f"{int(flight_plan_number)}-{str(label).strip() or 'MANUAL'}-{int(seq)}"
 

@dataclass
class ManualControlInput:
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    throttle: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, float] | None) -> "ManualControlInput":
        raw = data or {}
        return cls(
            roll=_clamp_axis(float(raw.get("roll", 0.0) or 0.0)),
            pitch=_clamp_axis(float(raw.get("pitch", 0.0) or 0.0)),
            yaw=_clamp_axis(float(raw.get("yaw", 0.0) or 0.0)),
            throttle=_clamp_axis(float(raw.get("throttle", 0.0) or 0.0)),
        )

    def to_dict(self) -> Dict[str, float]:
        return {
            "roll": float(self.roll),
            "pitch": float(self.pitch),
            "yaw": float(self.yaw),
            "throttle": float(self.throttle),
        }


@dataclass
class ManualVehicleConfig:
    vehicle_id: str = "UAM0001"
    flight_plan_number: int = 9001
    origin_lat: float = 37.5665
    origin_lon: float = 126.9780
    origin_alt_m: float = 0.0
    initial_north_m: float = 0.0
    initial_east_m: float = 0.0
    initial_down_m: float = -10.0
    initial_heading_deg: float = 0.0
    gps_origin_lat: float | None = None
    gps_origin_lon: float | None = None
    gps_origin_alt_m: float | None = None
    gps_reference_north_m: float | None = None
    gps_reference_east_m: float | None = None
    gps_reference_down_m: float | None = None
    max_lateral_speed_mps: float = 60.0
    max_vertical_speed_mps: float = 8.0
    max_yaw_rate_deg_s: float = 45.0
    min_yaw_rate_deg_s: float = 7.0
    yaw_rate_free_speed_mps: float = 5.0
    yaw_rate_speed_scale_mps: float = 15.0
    max_horizontal_accel_mps2: float = 3.2
    max_horizontal_decel_mps2: float = 4.2
    max_vertical_accel_mps2: float = 1.2
    max_yaw_accel_deg_s2: float = 55.0
    velocity_tau_s: float = 1.55
    attitude_tau_s: float = 0.55
    input_rise_tau_s: float = 0.65
    input_release_tau_s: float = 0.45
    yaw_input_tau_s: float = 0.85
    input_deadband: float = 0.015
    velocity_stop_deadband_mps: float = 0.03
    yaw_rate_stop_deadband_deg_s: float = 0.2
    visual_tilt_max_deg: float = 16.0
    attitude_accel_gain: float = 0.45
    attitude_command_gain: float = 0.18
    cruise_pitch_max_deg: float = 4.0
    max_aileron_deg: float = 18.0
    max_rudder_deg: float = 16.0
    tilt_pitch_gain: float = 0.22
    tilt_roll_gain: float = 0.08
    hover_motor_rpm: float = 2350.0
    max_motor_rpm_delta: float = 950.0
    gps_eph_m: float = 0.8
    gps_epv_m: float = 1.2
    battery_capacity_kwh: float = 120.0
    battery_initial_pct: float = 100.0
    battery_aux_power_kw: float = 6.0
    battery_hover_power_kw: float = 120.0
    battery_cruise_power_kw: float = 75.0
    battery_speed_power_kw_per_mps2: float = 0.020
    battery_climb_power_kw_per_mps: float = 10.0
    battery_descent_power_kw_per_mps: float = 1.5
    battery_accel_power_kw_per_mps2: float = 2.0

    @property
    def origin_frame(self) -> LocalNEDFrame:
        return LocalNEDFrame(
            origin_lat=float(self.origin_lat),
            origin_lon=float(self.origin_lon),
            origin_alt_m=float(self.origin_alt_m),
        )

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, object] | None,
        base: "ManualVehicleConfig | None" = None,
    ) -> "ManualVehicleConfig":
        cfg = base or cls()
        raw = data or {}
        values = cfg.__dict__.copy()
        for key in values:
            if key not in raw or raw[key] is None:
                continue
            if key == "vehicle_id":
                values[key] = str(raw[key]).strip() or values[key]
            elif key == "flight_plan_number":
                values[key] = int(raw[key])
            else:
                values[key] = float(raw[key])
        return cls(**values)


@dataclass
class ActuatorState:
    tilt_left: float = 0.5
    tilt_right: float = 0.5
    aileron: float = 0.0
    rudder_left: float = 0.0
    rudder_right: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "tilt_left": float(self.tilt_left),
            "tilt_right": float(self.tilt_right),
            "aileron": float(self.aileron),
            "rudder_left": float(self.rudder_left),
            "rudder_right": float(self.rudder_right),
        }


@dataclass
class PropulsionState:
    motor_rpm: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])

    def to_dict(self) -> Dict[str, List[float]]:
        return {"motor_rpm": [float(item) for item in self.motor_rpm]}


@dataclass
class GpsState:
    is_valid: bool
    fix_type: int
    latitude: float
    longitude: float
    altitude: float
    velocity_north: float
    velocity_east: float
    velocity_down: float
    eph: float
    epv: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": bool(self.is_valid),
            "fix_type": int(self.fix_type),
            "latitude": float(self.latitude),
            "longitude": float(self.longitude),
            "altitude": float(self.altitude),
            "velocity_north": float(self.velocity_north),
            "velocity_east": float(self.velocity_east),
            "velocity_down": float(self.velocity_down),
            "eph": float(self.eph),
            "epv": float(self.epv),
        }


@dataclass
class ImuState:
    orientation: Dict[str, float]
    angular_velocity: Dict[str, float]
    linear_acceleration: Dict[str, float]

    def to_dict(self) -> Dict[str, Dict[str, float]]:
        return {
            "orientation": {key: float(value) for key, value in self.orientation.items()},
            "angular_velocity": {key: float(value) for key, value in self.angular_velocity.items()},
            "linear_acceleration": {key: float(value) for key, value in self.linear_acceleration.items()},
        }


@dataclass
class BarometerState:
    altitude: float
    pressure: float
    qnh: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "altitude": float(self.altitude),
            "pressure": float(self.pressure),
            "qnh": float(self.qnh),
        }


@dataclass
class ManualVehicleSample:
    vehicle_id: str
    flight_plan_number: int
    lat: float
    lon: float
    alt_m: float
    north_m: float
    east_m: float
    down_m: float
    speed_mps: float
    climb_rate_mps: float
    heading_deg: float
    track_heading_deg: float
    pitch_rad: float
    roll_rad: float
    battery_pct: float
    waypoint_id: str
    actuator: ActuatorState
    propulsion: PropulsionState
    gps: GpsState
    imu: ImuState
    barometer: BarometerState

    def payload_groups(self) -> Dict[str, Any]:
        return {
            "actuator": self.actuator.to_dict(),
            "propulsion": self.propulsion.to_dict(),
            "gps": self.gps.to_dict(),
            "imu": self.imu.to_dict(),
            "barometer": self.barometer.to_dict(),
        }


class OperatorDynamicsModel(ABC):
    """Base class for future pluggable operator dynamics models."""

    @abstractmethod
    def configure(self, config: ManualVehicleConfig) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_input(self, command: ManualControlInput) -> None:
        raise NotImplementedError

    @abstractmethod
    def tick(self, dt: float) -> ManualVehicleSample:
        raise NotImplementedError

    @abstractmethod
    def snapshot(self) -> Dict[str, object]:
        raise NotImplementedError
