"""Keyboard-focused kinematic dynamics with synthetic sensors and actuators."""

from __future__ import annotations

import math
from typing import Dict, Tuple

from .base import (
    ActuatorState,
    BarometerState,
    GpsState,
    ImuState,
    build_manual_waypoint_id,
    ManualControlInput,
    ManualVehicleConfig,
    ManualVehicleSample,
    OperatorDynamicsModel,
    PropulsionState,
)


GRAVITY_MPS2 = 9.80665
STANDARD_QNH_HPA = 1013.25
STANDARD_PRESSURE_PA = 101325.0


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def _exp_smooth(current: float, target: float, dt: float, tau: float) -> float:
    if tau <= 0.0001:
        return target
    alpha = 1.0 - math.exp(-max(0.0, dt) / tau)
    return current + (target - current) * alpha


def _smooth_axis(current: float, target: float, dt: float, rise_tau: float, release_tau: float) -> float:
    tau = rise_tau if abs(target) > abs(current) else release_tau
    return _exp_smooth(current, target, dt, tau)


def _wrap_deg(value: float) -> float:
    wrapped = float(value) % 360.0
    return wrapped if wrapped >= 0.0 else wrapped + 360.0


def _wrap_delta_deg(value: float) -> float:
    wrapped = (float(value) + 180.0) % 360.0 - 180.0
    return wrapped


def _ned_to_lla(origin_lat: float, origin_lon: float, origin_alt_m: float, north_m: float, east_m: float, down_m: float) -> Tuple[float, float, float]:
    lat0 = math.radians(float(origin_lat))
    meters_per_lat = 111_132.92 - 559.82 * math.cos(2 * lat0) + 1.175 * math.cos(4 * lat0)
    meters_per_lon = 111_412.84 * math.cos(lat0) - 93.5 * math.cos(3 * lat0)
    if abs(meters_per_lon) < 1e-6:
        meters_per_lon = 1e-6
    lat = float(origin_lat) + float(north_m) / meters_per_lat
    lon = float(origin_lon) + float(east_m) / meters_per_lon
    alt = float(origin_alt_m) - float(down_m)
    return lat, lon, alt


def _euler_to_quaternion(roll: float, pitch: float, yaw: float) -> Dict[str, float]:
    cr = math.cos(roll * 0.5)
    sr = math.sin(roll * 0.5)
    cp = math.cos(pitch * 0.5)
    sp = math.sin(pitch * 0.5)
    cy = math.cos(yaw * 0.5)
    sy = math.sin(yaw * 0.5)
    return {
        "w": cr * cp * cy + sr * sp * sy,
        "x": sr * cp * cy - cr * sp * sy,
        "y": cr * sp * cy + sr * cp * sy,
        "z": cr * cp * sy - sr * sp * cy,
    }


def _rotation_body_to_ned(roll: float, pitch: float, yaw: float) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]:
    cr = math.cos(roll)
    sr = math.sin(roll)
    cp = math.cos(pitch)
    sp = math.sin(pitch)
    cy = math.cos(yaw)
    sy = math.sin(yaw)
    return (
        (cp * cy, cp * sy, -sp),
        (sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, sr * cp),
        (cr * sp * cy + sr * sy, cr * sp * sy - sr * cy, cr * cp),
    )


def _ned_to_body_vector(roll: float, pitch: float, yaw: float, north: float, east: float, down: float) -> Tuple[float, float, float]:
    r_bn = _rotation_body_to_ned(roll, pitch, yaw)
    return (
        r_bn[0][0] * north + r_bn[1][0] * east + r_bn[2][0] * down,
        r_bn[0][1] * north + r_bn[1][1] * east + r_bn[2][1] * down,
        r_bn[0][2] * north + r_bn[1][2] * east + r_bn[2][2] * down,
    )


def _pressure_from_altitude(altitude_m: float) -> float:
    capped_altitude = _clamp(altitude_m, -1000.0, 20000.0)
    ratio = 1.0 - 2.25577e-5 * capped_altitude
    ratio = max(ratio, 0.05)
    return STANDARD_PRESSURE_PA * math.pow(ratio, 5.25588)


class ManualKinematicDynamics(OperatorDynamicsModel):
    """Simple 4-axis kinematics plus synthetic actuator and sensor outputs."""

    def __init__(self, config: ManualVehicleConfig | None = None) -> None:
        self.configure(config or ManualVehicleConfig())

    def configure(self, config: ManualVehicleConfig) -> None:
        self.config = config
        self.north_m = float(config.initial_north_m)
        self.east_m = float(config.initial_east_m)
        self.down_m = float(config.initial_down_m)
        self.heading_deg = _wrap_deg(config.initial_heading_deg)
        self.roll_rad = 0.0
        self.pitch_rad = 0.0
        self.vn_mps = 0.0
        self.ve_mps = 0.0
        self.vd_mps = 0.0
        self.battery_pct = 100.0
        self.last_input = ManualControlInput()
        self._shaped_input = ManualControlInput()
        self._last_actuator = ActuatorState()
        self._last_propulsion = PropulsionState([float(config.hover_motor_rpm)] * 4)
        lat, lon, alt = _ned_to_lla(
            config.origin_lat,
            config.origin_lon,
            config.origin_alt_m,
            self.north_m,
            self.east_m,
            self.down_m,
        )
        self._last_gps = GpsState(
            is_valid=True,
            fix_type=3,
            latitude=lat,
            longitude=lon,
            altitude=alt,
            velocity_north=0.0,
            velocity_east=0.0,
            velocity_down=0.0,
            eph=float(config.gps_eph_m),
            epv=float(config.gps_epv_m),
        )
        self._last_imu = ImuState(
            orientation=_euler_to_quaternion(self.roll_rad, self.pitch_rad, math.radians(self.heading_deg)),
            angular_velocity={"x": 0.0, "y": 0.0, "z": 0.0},
            linear_acceleration={"x": 0.0, "y": 0.0, "z": -GRAVITY_MPS2},
        )
        self._last_barometer = BarometerState(
            altitude=alt,
            pressure=_pressure_from_altitude(alt),
            qnh=STANDARD_QNH_HPA,
        )

    def set_input(self, command: ManualControlInput) -> None:
        self.last_input = command

    def tick(self, dt: float) -> ManualVehicleSample:
        dt = max(1e-3, min(0.25, float(dt)))
        cfg = self.config
        raw_cmd = self.last_input

        self._shaped_input = ManualControlInput(
            roll=_smooth_axis(
                self._shaped_input.roll,
                raw_cmd.roll,
                dt,
                cfg.input_rise_tau_s,
                cfg.input_release_tau_s,
            ),
            pitch=_smooth_axis(
                self._shaped_input.pitch,
                raw_cmd.pitch,
                dt,
                cfg.input_rise_tau_s,
                cfg.input_release_tau_s,
            ),
            yaw=_exp_smooth(
                self._shaped_input.yaw,
                raw_cmd.yaw,
                dt,
                cfg.yaw_input_tau_s,
            ),
            throttle=_smooth_axis(
                self._shaped_input.throttle,
                raw_cmd.throttle,
                dt,
                cfg.input_rise_tau_s,
                cfg.input_release_tau_s,
            ),
        )
        cmd = self._shaped_input

        prev_vn = self.vn_mps
        prev_ve = self.ve_mps
        prev_vd = self.vd_mps
        prev_heading_deg = self.heading_deg
        prev_roll_rad = self.roll_rad
        prev_pitch_rad = self.pitch_rad

        yaw_rate_deg_s = cmd.yaw * cfg.max_yaw_rate_deg_s
        self.heading_deg = _wrap_deg(self.heading_deg + yaw_rate_deg_s * dt)
        yaw_rad = math.radians(self.heading_deg)

        forward_speed = cmd.pitch * cfg.max_lateral_speed_mps
        right_speed = cmd.roll * cfg.max_lateral_speed_mps
        target_vn = forward_speed * math.cos(yaw_rad) - right_speed * math.sin(yaw_rad)
        target_ve = forward_speed * math.sin(yaw_rad) + right_speed * math.cos(yaw_rad)
        target_vd = -cmd.throttle * cfg.max_vertical_speed_mps

        self.vn_mps = _exp_smooth(self.vn_mps, target_vn, dt, cfg.velocity_tau_s)
        self.ve_mps = _exp_smooth(self.ve_mps, target_ve, dt, cfg.velocity_tau_s)
        self.vd_mps = _exp_smooth(self.vd_mps, target_vd, dt, cfg.velocity_tau_s)

        target_roll_rad = math.radians(cmd.roll * cfg.visual_tilt_max_deg)
        target_pitch_rad = math.radians(-cmd.pitch * cfg.visual_tilt_max_deg * 0.8)
        self.roll_rad = _exp_smooth(self.roll_rad, target_roll_rad, dt, cfg.attitude_tau_s)
        self.pitch_rad = _exp_smooth(self.pitch_rad, target_pitch_rad, dt, cfg.attitude_tau_s)

        self.north_m += self.vn_mps * dt
        self.east_m += self.ve_mps * dt
        self.down_m += self.vd_mps * dt

        north_accel = (self.vn_mps - prev_vn) / dt
        east_accel = (self.ve_mps - prev_ve) / dt
        down_accel = (self.vd_mps - prev_vd) / dt
        roll_rate = (self.roll_rad - prev_roll_rad) / dt
        pitch_rate = (self.pitch_rad - prev_pitch_rad) / dt
        yaw_rate = math.radians(_wrap_delta_deg(self.heading_deg - prev_heading_deg)) / dt

        horizontal_speed = math.hypot(self.vn_mps, self.ve_mps)
        track_heading_deg = self.heading_deg
        if horizontal_speed > 0.05:
            track_heading_deg = _wrap_deg(math.degrees(math.atan2(self.ve_mps, self.vn_mps)))

        lat, lon, alt = _ned_to_lla(
            cfg.origin_lat,
            cfg.origin_lon,
            cfg.origin_alt_m,
            self.north_m,
            self.east_m,
            self.down_m,
        )

        pitch_surface = _clamp(-cmd.pitch * cfg.max_rudder_deg * 0.75, -cfg.max_rudder_deg, cfg.max_rudder_deg)
        yaw_surface = _clamp(cmd.yaw * cfg.max_rudder_deg * 0.55, -cfg.max_rudder_deg, cfg.max_rudder_deg)
        tilt_center = 0.5 + cfg.tilt_pitch_gain * cmd.pitch
        actuator = ActuatorState(
            tilt_left=_clamp(tilt_center - cfg.tilt_roll_gain * cmd.roll, 0.0, 1.0),
            tilt_right=_clamp(tilt_center + cfg.tilt_roll_gain * cmd.roll, 0.0, 1.0),
            aileron=_clamp(cmd.roll * cfg.max_aileron_deg, -30.0, 30.0),
            rudder_left=_clamp(pitch_surface - yaw_surface, -30.0, 30.0),
            rudder_right=_clamp(pitch_surface + yaw_surface, -30.0, 30.0),
        )

        base_rpm = cfg.hover_motor_rpm + cmd.throttle * cfg.max_motor_rpm_delta
        base_rpm += horizontal_speed * 45.0 + abs(self.vd_mps) * 60.0
        pitch_mix = -cmd.pitch * 120.0
        roll_mix = cmd.roll * 95.0
        yaw_mix = cmd.yaw * 70.0
        propulsion = PropulsionState([
            _clamp(base_rpm - pitch_mix - roll_mix - yaw_mix, 0.0, 6000.0),
            _clamp(base_rpm - pitch_mix + roll_mix + yaw_mix, 0.0, 6000.0),
            _clamp(base_rpm + pitch_mix - roll_mix + yaw_mix, 0.0, 6000.0),
            _clamp(base_rpm + pitch_mix + roll_mix - yaw_mix, 0.0, 6000.0),
        ])

        gps = GpsState(
            is_valid=True,
            fix_type=3,
            latitude=lat,
            longitude=lon,
            altitude=alt,
            velocity_north=self.vn_mps,
            velocity_east=self.ve_mps,
            velocity_down=self.vd_mps,
            eph=_clamp(cfg.gps_eph_m + 0.02 * horizontal_speed, 0.0, 100.0),
            epv=_clamp(cfg.gps_epv_m + 0.04 * abs(self.vd_mps), 0.0, 100.0),
        )

        specific_force_ned = (north_accel, east_accel, down_accel - GRAVITY_MPS2)
        body_ax, body_ay, body_az = _ned_to_body_vector(
            self.roll_rad,
            self.pitch_rad,
            yaw_rad,
            specific_force_ned[0],
            specific_force_ned[1],
            specific_force_ned[2],
        )
        imu = ImuState(
            orientation=_euler_to_quaternion(self.roll_rad, self.pitch_rad, yaw_rad),
            angular_velocity={
                "x": _clamp(roll_rate, -100.0, 100.0),
                "y": _clamp(pitch_rate, -100.0, 100.0),
                "z": _clamp(yaw_rate, -100.0, 100.0),
            },
            linear_acceleration={
                "x": _clamp(body_ax, -200.0, 200.0),
                "y": _clamp(body_ay, -200.0, 200.0),
                "z": _clamp(body_az, -200.0, 200.0),
            },
        )

        barometer = BarometerState(
            altitude=alt,
            pressure=_clamp(_pressure_from_altitude(alt), 10000.0, 120000.0),
            qnh=STANDARD_QNH_HPA,
        )

        mean_motor_rpm = sum(propulsion.motor_rpm) / max(1, len(propulsion.motor_rpm))
        discharge_rate = 0.002 + 0.004 * (mean_motor_rpm / 6000.0)
        self.battery_pct = max(0.0, self.battery_pct - dt * discharge_rate)

        sample = ManualVehicleSample(
            vehicle_id=cfg.vehicle_id,
            flight_plan_number=int(cfg.flight_plan_number),
            lat=lat,
            lon=lon,
            alt_m=alt,
            north_m=self.north_m,
            east_m=self.east_m,
            down_m=self.down_m,
            speed_mps=horizontal_speed,
            climb_rate_mps=-self.vd_mps,
            heading_deg=self.heading_deg,
            track_heading_deg=track_heading_deg,
            pitch_rad=self.pitch_rad,
            roll_rad=self.roll_rad,
            battery_pct=self.battery_pct,
            waypoint_id=build_manual_waypoint_id(cfg.flight_plan_number),
            actuator=actuator,
            propulsion=propulsion,
            gps=gps,
            imu=imu,
            barometer=barometer,
        )
        self._last_actuator = actuator
        self._last_propulsion = propulsion
        self._last_gps = gps
        self._last_imu = imu
        self._last_barometer = barometer
        return sample

    def snapshot(self) -> Dict[str, object]:
        return {
            "vehicle_id": self.config.vehicle_id,
            "flight_plan_number": self.config.flight_plan_number,
            "origin": self.config.origin_frame.as_dict(),
            "position": {
                "north": self.north_m,
                "east": self.east_m,
                "down": self.down_m,
            },
            "velocity": {
                "north": self.vn_mps,
                "east": self.ve_mps,
                "down": self.vd_mps,
            },
            "heading_deg": self.heading_deg,
            "battery_pct": self.battery_pct,
            "input": self._shaped_input.to_dict(),
            "input_raw": self.last_input.to_dict(),
            "actuator": self._last_actuator.to_dict(),
            "propulsion": self._last_propulsion.to_dict(),
            "gps": self._last_gps.to_dict(),
            "imu": self._last_imu.to_dict(),
            "barometer": self._last_barometer.to_dict(),
        }
