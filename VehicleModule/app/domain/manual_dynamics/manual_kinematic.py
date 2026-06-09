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


def _zero_small(value: float, threshold: float) -> float:
    threshold = max(0.0, float(threshold))
    return 0.0 if abs(float(value)) < threshold else float(value)


def _rate_limit_scalar(current: float, target: float, max_rate: float, dt: float) -> float:
    limit = max(0.0, float(max_rate)) * max(0.0, float(dt))
    delta = float(target) - float(current)
    if abs(delta) <= limit or limit <= 1e-12:
        return float(target) if limit > 1e-12 else float(current)
    return float(current) + math.copysign(limit, delta)


def _rate_limit_vector(
    current_n: float,
    current_e: float,
    target_n: float,
    target_e: float,
    max_rate: float,
    dt: float,
) -> Tuple[float, float]:
    limit = max(0.0, float(max_rate)) * max(0.0, float(dt))
    dn = float(target_n) - float(current_n)
    de = float(target_e) - float(current_e)
    delta_mag = math.hypot(dn, de)
    if delta_mag <= limit or limit <= 1e-12:
        return (float(target_n), float(target_e)) if limit > 1e-12 else (float(current_n), float(current_e))
    scale = limit / max(delta_mag, 1e-12)
    return float(current_n) + dn * scale, float(current_e) + de * scale


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


def _gps_lla(config: ManualVehicleConfig, north_m: float, east_m: float, down_m: float) -> Tuple[float, float, float]:
    """Convert manual sim position to GPS, optionally using a separate GPS anchor.

    ``north/east/down`` may be an Unreal/AirSim replay pose.  When a mission
    launch supplies ``gps_origin_*`` and ``gps_reference_*``, GPS starts at the
    mission departure point while the replay pose remains in the AirSim frame.
    """
    origin_lat = config.gps_origin_lat if config.gps_origin_lat is not None else config.origin_lat
    origin_lon = config.gps_origin_lon if config.gps_origin_lon is not None else config.origin_lon
    origin_alt = config.gps_origin_alt_m if config.gps_origin_alt_m is not None else config.origin_alt_m
    ref_north = config.gps_reference_north_m if config.gps_reference_north_m is not None else 0.0
    ref_east = config.gps_reference_east_m if config.gps_reference_east_m is not None else 0.0
    ref_down = config.gps_reference_down_m if config.gps_reference_down_m is not None else 0.0
    return _ned_to_lla(
        float(origin_lat),
        float(origin_lon),
        float(origin_alt),
        float(north_m) - float(ref_north),
        float(east_m) - float(ref_east),
        float(down_m) - float(ref_down),
    )


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


def _manual_battery_power_kw(
    cfg: ManualVehicleConfig,
    *,
    horizontal_speed_mps: float,
    climb_rate_mps: float,
    horizontal_accel_mps2: float,
    mean_motor_rpm: float,
) -> float:
    """Estimate electrical power draw for the manual kinematic model.

    The previous implementation subtracted a tiny fixed percent per second
    from the battery.  This model converts a simple power estimate to kWh and
    never regenerates charge, so the state of charge is monotonically
    decreasing during operation.
    """
    speed = max(0.0, float(horizontal_speed_mps))
    climb = float(climb_rate_mps)
    accel = max(0.0, float(horizontal_accel_mps2))
    rpm_frac = _clamp(float(mean_motor_rpm) / 6000.0, 0.0, 1.0)

    aux_kw = max(0.0, float(cfg.battery_aux_power_kw))
    hover_kw = max(0.0, float(cfg.battery_hover_power_kw))
    cruise_kw = max(0.0, float(cfg.battery_cruise_power_kw))
    speed_drag_kw = max(0.0, float(cfg.battery_speed_power_kw_per_mps2)) * speed * speed

    transition_speed = max(1.0, float(cfg.max_lateral_speed_mps) * 0.45)
    cruise_blend = _clamp(speed / transition_speed, 0.0, 1.0)
    # Keep hover power significant at low speed; scale slightly with RPM so
    # throttle/attitude inputs are reflected without making SOC bounce back.
    hover_component = hover_kw * (0.65 + 0.35 * rpm_frac)
    cruise_component = cruise_kw + speed_drag_kw
    base_kw = hover_component * (1.0 - cruise_blend) + cruise_component * cruise_blend

    vertical_kw = 0.0
    if climb > 0.0:
        vertical_kw += max(0.0, float(cfg.battery_climb_power_kw_per_mps)) * climb
    else:
        # Descent still costs control/propulsion power; do not model regen here
        # because the simulator battery must not recover during flight.
        vertical_kw += max(0.0, float(cfg.battery_descent_power_kw_per_mps)) * abs(climb)
    accel_kw = max(0.0, float(cfg.battery_accel_power_kw_per_mps2)) * accel
    return max(0.0, aux_kw + base_kw + vertical_kw + accel_kw)


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
        self.yaw_rate_deg_s = 0.0
        self.battery_pct = _clamp(float(config.battery_initial_pct), 0.0, 100.0)
        self.last_input = ManualControlInput()
        self._shaped_input = ManualControlInput()
        self._command_input = ManualControlInput()
        self._last_actuator = ActuatorState()
        self._last_propulsion = PropulsionState([float(config.hover_motor_rpm)] * 4)
        lat, lon, alt = _gps_lla(config, self.north_m, self.east_m, self.down_m)
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
        cmd = ManualControlInput(
            roll=_zero_small(cmd.roll, cfg.input_deadband),
            pitch=_zero_small(cmd.pitch, cfg.input_deadband),
            yaw=_zero_small(cmd.yaw, cfg.input_deadband),
            throttle=_zero_small(cmd.throttle, cfg.input_deadband),
        )
        self._command_input = cmd

        prev_vn = self.vn_mps
        prev_ve = self.ve_mps
        prev_vd = self.vd_mps
        prev_heading_deg = self.heading_deg
        prev_roll_rad = self.roll_rad
        prev_pitch_rad = self.pitch_rad

        speed_for_yaw = math.hypot(self.vn_mps, self.ve_mps)
        speed_over_free = max(0.0, speed_for_yaw - max(0.0, cfg.yaw_rate_free_speed_mps))
        speed_scale = max(1e-6, cfg.yaw_rate_speed_scale_mps)
        yaw_cap_deg_s = cfg.min_yaw_rate_deg_s + (
            (cfg.max_yaw_rate_deg_s - cfg.min_yaw_rate_deg_s)
            / (1.0 + (speed_over_free / speed_scale) ** 2)
        )
        yaw_cap_deg_s = _clamp(yaw_cap_deg_s, 0.0, cfg.max_yaw_rate_deg_s)
        target_yaw_rate_deg_s = cmd.yaw * yaw_cap_deg_s
        self.yaw_rate_deg_s = _rate_limit_scalar(
            self.yaw_rate_deg_s,
            target_yaw_rate_deg_s,
            cfg.max_yaw_accel_deg_s2,
            dt,
        )
        if abs(target_yaw_rate_deg_s) < cfg.yaw_rate_stop_deadband_deg_s and abs(self.yaw_rate_deg_s) < cfg.yaw_rate_stop_deadband_deg_s:
            self.yaw_rate_deg_s = 0.0
        yaw_rate_deg_s = self.yaw_rate_deg_s
        self.heading_deg = _wrap_deg(self.heading_deg + yaw_rate_deg_s * dt)
        yaw_rad = math.radians(self.heading_deg)

        max_horizontal_speed = max(0.0, float(cfg.max_lateral_speed_mps))
        horizontal_cmd_mag = math.hypot(cmd.pitch, cmd.roll)
        horizontal_scale = 1.0
        if horizontal_cmd_mag > 1.0:
            horizontal_scale = 1.0 / horizontal_cmd_mag
        forward_speed = cmd.pitch * horizontal_scale * max_horizontal_speed
        right_speed = cmd.roll * horizontal_scale * max_horizontal_speed
        target_vn = forward_speed * math.cos(yaw_rad) - right_speed * math.sin(yaw_rad)
        target_ve = forward_speed * math.sin(yaw_rad) + right_speed * math.cos(yaw_rad)
        target_vd = -cmd.throttle * cfg.max_vertical_speed_mps

        desired_vn = _exp_smooth(self.vn_mps, target_vn, dt, cfg.velocity_tau_s)
        desired_ve = _exp_smooth(self.ve_mps, target_ve, dt, cfg.velocity_tau_s)
        desired_vd = _exp_smooth(self.vd_mps, target_vd, dt, cfg.velocity_tau_s)
        current_horizontal_speed = math.hypot(self.vn_mps, self.ve_mps)
        desired_horizontal_speed = math.hypot(desired_vn, desired_ve)
        dot = self.vn_mps * desired_vn + self.ve_mps * desired_ve
        accel_limit = (
            cfg.max_horizontal_decel_mps2
            if desired_horizontal_speed < current_horizontal_speed or dot < 0.0
            else cfg.max_horizontal_accel_mps2
        )
        self.vn_mps, self.ve_mps = _rate_limit_vector(
            self.vn_mps,
            self.ve_mps,
            desired_vn,
            desired_ve,
            accel_limit,
            dt,
        )
        self.vd_mps = _rate_limit_scalar(self.vd_mps, desired_vd, cfg.max_vertical_accel_mps2, dt)
        if math.hypot(target_vn, target_ve) < cfg.velocity_stop_deadband_mps and math.hypot(self.vn_mps, self.ve_mps) < cfg.velocity_stop_deadband_mps:
            self.vn_mps = 0.0
            self.ve_mps = 0.0
        if abs(target_vd) < cfg.velocity_stop_deadband_mps and abs(self.vd_mps) < cfg.velocity_stop_deadband_mps:
            self.vd_mps = 0.0

        north_accel = (self.vn_mps - prev_vn) / dt
        east_accel = (self.ve_mps - prev_ve) / dt
        down_accel = (self.vd_mps - prev_vd) / dt
        horizontal_speed = math.hypot(self.vn_mps, self.ve_mps)

        body_forward_speed = self.vn_mps * math.cos(yaw_rad) + self.ve_mps * math.sin(yaw_rad)
        forward_accel = north_accel * math.cos(yaw_rad) + east_accel * math.sin(yaw_rad)
        right_accel = -north_accel * math.sin(yaw_rad) + east_accel * math.cos(yaw_rad)
        speed_fraction = (
            _clamp(body_forward_speed / max_horizontal_speed, -1.0, 1.0)
            if max_horizontal_speed > 1e-6
            else 0.0
        )
        accel_gain = max(0.0, float(cfg.attitude_accel_gain))
        command_gain = max(0.0, float(cfg.attitude_command_gain))
        target_roll_deg = _clamp(
            math.degrees(math.atan2(right_accel, GRAVITY_MPS2)) * accel_gain
            + cmd.roll * cfg.visual_tilt_max_deg * command_gain,
            -cfg.visual_tilt_max_deg,
            cfg.visual_tilt_max_deg,
        )
        target_pitch_deg = _clamp(
            -math.degrees(math.atan2(forward_accel, GRAVITY_MPS2)) * accel_gain
            - float(cfg.cruise_pitch_max_deg) * speed_fraction
            - cmd.pitch * cfg.visual_tilt_max_deg * command_gain * 0.6,
            -cfg.visual_tilt_max_deg,
            cfg.visual_tilt_max_deg,
        )
        self.roll_rad = _exp_smooth(self.roll_rad, math.radians(target_roll_deg), dt, cfg.attitude_tau_s)
        self.pitch_rad = _exp_smooth(self.pitch_rad, math.radians(target_pitch_deg), dt, cfg.attitude_tau_s)
        roll_rate = (self.roll_rad - prev_roll_rad) / dt
        pitch_rate = (self.pitch_rad - prev_pitch_rad) / dt
        yaw_rate = math.radians(_wrap_delta_deg(self.heading_deg - prev_heading_deg)) / dt

        self.north_m += self.vn_mps * dt
        self.east_m += self.ve_mps * dt
        self.down_m += self.vd_mps * dt

        track_heading_deg = self.heading_deg
        if horizontal_speed > 0.05:
            track_heading_deg = _wrap_deg(math.degrees(math.atan2(self.ve_mps, self.vn_mps)))

        lat, lon, alt = _gps_lla(cfg, self.north_m, self.east_m, self.down_m)

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
        # MSG 4001 / AirSim QuadX order:
        #   1 front-right, 2 rear-left, 3 front-left, 4 rear-right.
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
        capacity_kwh = max(0.0, float(cfg.battery_capacity_kwh))
        if capacity_kwh > 1e-6:
            power_kw = _manual_battery_power_kw(
                cfg,
                horizontal_speed_mps=horizontal_speed,
                climb_rate_mps=-self.vd_mps,
                horizontal_accel_mps2=math.hypot(north_accel, east_accel),
                mean_motor_rpm=mean_motor_rpm,
            )
            consumed_pct = (power_kw * dt / 3600.0) / capacity_kwh * 100.0
        else:
            consumed_pct = 0.0
        self.battery_pct = max(0.0, min(self.battery_pct, self.battery_pct - max(0.0, consumed_pct)))

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
            "input": self._command_input.to_dict(),
            "input_shaped": self._shaped_input.to_dict(),
            "input_raw": self.last_input.to_dict(),
            "actuator": self._last_actuator.to_dict(),
            "propulsion": self._last_propulsion.to_dict(),
            "gps": self._last_gps.to_dict(),
            "imu": self._last_imu.to_dict(),
            "barometer": self._last_barometer.to_dict(),
        }
