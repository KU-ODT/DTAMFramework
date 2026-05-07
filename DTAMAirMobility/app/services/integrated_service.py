"""통합 AirMobility 서비스.

한 대 이상의 UAM 에 비행 계획(FlightPlan) 을 등록해두면, 외부 또는 내부(wall)
시계에서 주입되는 현재 시각을 따라 각 비행체의 궤적을 30 Hz 로 생성하고
DTAM 4001 메시지로 송출한다.

흐름 요약::

    service = IntegratedAirMobilityService(publisher_cfg={...})
    service.add_plan(plan_uam0001)
    service.add_plan(plan_uam0002)
    service.start()                       # 송신 스레드 기동

    # (a) 외부 시계 구동
    service.feed_time_hhmmss("09:10:00")  # 또는
    service.feed_time_seconds(33000.0)

    # (b) 내부 wall-clock 구동
    service.enable_wall_clock(True)
"""
from __future__ import annotations

import logging
import math
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..domain.dynamics.core.types import (
    DEFAULT_SIMULATION_HZ,
    DEFAULT_SIMULATION_TICK_S,
    FlightPlan,
    FlightTrajectoryPoint,
    SimulationConfig,
)
from ..domain.dynamics.io.icd_parser import parse_flight_plans, parse_flight_plan
from ..domain.dynamics.simulator import UAMFlightSimulator

from .msg4001 import (
    VehiclePublishContext,
    build_4001_message,
    build_vehicle_payload,
    iso_timestamp,
)
from dtam_client import VehicleModule
from dtam_client.schema import parse_payload
from ..domain.manual_dynamics import (
    build_manual_waypoint_id,
    ManualControlInput,
    ManualVehicleConfig,
    create_operator_dynamics,
)
from ..domain.transform.coord_transform import LocalNEDFrame
from ..domain.transform.odt_pose_frame import (
    OdtPoseFrameState,
    load_spawn_pose_for_aircraft,
    trim_airsim_sync_trajectory,
)

logger = logging.getLogger(__name__)


PUBLISH_HZ = DEFAULT_SIMULATION_HZ
PUBLISH_PERIOD_S = DEFAULT_SIMULATION_TICK_S
MISSION_CORNER_SMOOTHING_RADIUS_M = 400.0


def _message_to_wire(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_wire"):
        converted = value.to_wire()
        return dict(converted) if isinstance(converted, dict) else {}
    if hasattr(value, "to_dict"):
        converted = value.to_dict()
        return dict(converted) if isinstance(converted, dict) else {}
    if dataclass_is_instance(value):
        from dataclasses import asdict

        return asdict(value)
    return {}


def dataclass_is_instance(value: Any) -> bool:
    from dataclasses import is_dataclass

    return bool(is_dataclass(value) and not isinstance(value, type))


class _CompatReceiveResult:
    """Small adapter for legacy handler methods after the WebSocket SDK switch."""

    def __init__(self, message: Any) -> None:
        raw = _message_to_wire(message)
        self.raw = raw
        self.ok = True
        self.errors: list[str] = []
        self.sim_time = raw.get("simTime") or raw.get("sim_time") or ""
        self.playback_speed = raw.get("playbackSpeed")
        self.play_state = raw.get("playState")


class _VehicleModulePublisherAdapter:
    """Expose the publisher surface on top of ``VehicleModule``."""

    def __init__(
        self,
        owner: "IntegratedAirMobilityService",
        *,
        target_ip: str,
        ws_port: int,
    ) -> None:
        self._owner = owner
        self.target_ip = str(target_ip)
        self.ws_port = int(ws_port)

    @property
    def connected(self) -> bool:
        return bool(self._owner.connected)

    @property
    def last_error(self) -> str:
        return self._owner.stats.last_error

    def reconfigure(
        self,
        *,
        target_ip: Optional[str] = None,
        ws_port: Optional[int] = None,
    ) -> None:
        if target_ip is not None:
            self.target_ip = str(target_ip)
        if ws_port is not None:
            self.ws_port = int(ws_port)
        self._owner.target_ip = self.target_ip
        self._owner.ws_port = self.ws_port
        self._owner.reconfigure(server_url=f"ws://{self.target_ip}:{self.ws_port}/ws/dtam")

    def push_module_status(self, *, source: str, status: int) -> bool:
        return bool(self._owner.connected)

    def push(self, message: Dict[str, Any]) -> bool:
        return self._owner.send(parse_payload("4001", message))

    def close(self) -> None:
        pass


class ClockMode(str, Enum):
    EXTERNAL = "external"   # 외부에서 feed_time_* 호출
    WALL = "wall"           # 내부 실시간 시계
    MANUAL = "manual"       # step_once(t) 를 직접 호출


class ControlMode(str, Enum):
    MISSION = "mission"
    KEYBOARD = "keyboard"
    JOYSTICK = "joystick"


class VehicleState(str, Enum):
    WAITING = "waiting"     # etot 이전 (또는 plan 방금 등록)
    ACTIVE = "active"       # engine 실행 중, 4001 송출 중
    COMPLETED = "completed" # 궤적 끝
    ERROR = "error"


@dataclass
class VehicleStatus:
    vehicle_id: str
    flight_plan_number: int
    state: VehicleState
    etot_s: float
    elapsed_s: float
    total_duration_s: float
    last_point: Optional[Dict[str, Any]] = None
    last_error: str = ""


@dataclass
class FleetStatus:
    control_mode: str
    dynamics_model: str
    clock_mode: str
    running: bool
    play_state: str
    playback_speed_x: float
    publisher_connected: bool
    publisher_error: str
    sim_time_s: float
    sim_time_hms: str
    vehicles: List[VehicleStatus] = field(default_factory=list)
    rx_3001_count: int = 0      # 수신한 3001 메시지 누적
    rx_0003_count: int = 0      # 수신한 0003 메시지 누적
    last_rx_3001: str = ""       # 가장 최근 3001 간략 정보
    last_rx_0003: str = ""       # 가장 최근 0003 simTime
    rx_2002_count: int = 0
    rx_3002_count: int = 0
    rx_3003_count: int = 0
    rx_5001_count: int = 0
    last_rx_2002: str = ""
    last_rx_3002: str = ""
    last_rx_3003: str = ""
    last_rx_5001: str = ""
    last_heartbeat_error: str = ""
    manual: Dict[str, Any] = field(default_factory=dict)


def _parse_hhmmss_to_s(text: str) -> float:
    parts = str(text).split(":")
    if len(parts) != 3:
        raise ValueError(f"expected HH:MM:SS, got {text!r}")
    h, m, s = parts
    return float(int(h) * 3600 + int(m) * 60 + float(s))


def _s_to_hhmmss(total_s: float) -> str:
    total = max(0.0, float(total_s))
    h = int(total // 3600) % 24
    m = int((total % 3600) // 60)
    s = int(total) % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _truthy(value: Any, default: bool = True) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "y", "on", "active", "start"):
        return True
    if text in ("0", "false", "no", "n", "off", "inactive", "stop"):
        return False
    return bool(default)


def _lerp_float(a: float, b: float, ratio: float) -> float:
    return float(a) + (float(b) - float(a)) * float(ratio)


def _signed_angle_delta_deg(target_deg: float, current_deg: float) -> float:
    return ((float(target_deg) - float(current_deg) + 180.0) % 360.0) - 180.0


def _lerp_heading_deg(a: float, b: float, ratio: float) -> float:
    return (float(a) + _signed_angle_delta_deg(b, a) * float(ratio)) % 360.0


def _interpolate_trajectory_point(
    a: FlightTrajectoryPoint,
    b: FlightTrajectoryPoint,
    target_time_s: float,
) -> FlightTrajectoryPoint:
    a_time = float(getattr(a, "time_s", 0.0) or 0.0)
    b_time = float(getattr(b, "time_s", a_time) or a_time)
    if b_time <= a_time + 1e-9:
        return a

    ratio = max(0.0, min(1.0, (float(target_time_s) - a_time) / (b_time - a_time)))
    phase_source = a if ratio < 1.0 else b
    clock_source = a if ratio < 0.5 else b
    return FlightTrajectoryPoint(
        time_s=round(float(target_time_s), 3),
        clock=str(getattr(clock_source, "clock", "")),
        phase=str(getattr(phase_source, "phase", "")),
        mode=str(getattr(phase_source, "mode", "")),
        lat=_lerp_float(a.lat, b.lat, ratio),
        lon=_lerp_float(a.lon, b.lon, ratio),
        alt_m=round(_lerp_float(a.alt_m, b.alt_m, ratio), 2),
        speed_mps=round(_lerp_float(a.speed_mps, b.speed_mps, ratio), 2),
        heading_deg=round(_lerp_heading_deg(a.heading_deg, b.heading_deg, ratio), 2),
        track_heading_deg=round(_lerp_heading_deg(a.track_heading_deg, b.track_heading_deg, ratio), 2),
        wind_e_mps=round(_lerp_float(a.wind_e_mps, b.wind_e_mps, ratio), 3),
        wind_n_mps=round(_lerp_float(a.wind_n_mps, b.wind_n_mps, ratio), 3),
        lateral_dev_m=round(_lerp_float(a.lateral_dev_m, b.lateral_dev_m, ratio), 3),
        battery_pct=round(_lerp_float(a.battery_pct, b.battery_pct, ratio), 2),
    )


def _trajectory_distance_m(a: FlightTrajectoryPoint, b: FlightTrajectoryPoint) -> float:
    mean_lat_rad = math.radians((float(a.lat) + float(b.lat)) * 0.5)
    meters_per_lat = 111_132.92
    meters_per_lon = 111_412.84 * math.cos(mean_lat_rad)
    north_m = (float(b.lat) - float(a.lat)) * meters_per_lat
    east_m = (float(b.lon) - float(a.lon)) * meters_per_lon
    up_m = float(b.alt_m) - float(a.alt_m)
    return math.sqrt(north_m * north_m + east_m * east_m + up_m * up_m)


def _limit_trajectory_step(
    previous: FlightTrajectoryPoint,
    target: FlightTrajectoryPoint,
    max_distance_m: float,
) -> FlightTrajectoryPoint:
    distance_m = _trajectory_distance_m(previous, target)
    if distance_m <= max(0.0, float(max_distance_m)) or distance_m <= 1e-6:
        return target

    ratio = max(0.0, min(1.0, float(max_distance_m) / distance_m))
    return FlightTrajectoryPoint(
        time_s=float(target.time_s),
        clock=str(target.clock),
        phase=str(target.phase),
        mode=str(target.mode),
        lat=_lerp_float(previous.lat, target.lat, ratio),
        lon=_lerp_float(previous.lon, target.lon, ratio),
        alt_m=round(_lerp_float(previous.alt_m, target.alt_m, ratio), 2),
        speed_mps=round(_lerp_float(previous.speed_mps, target.speed_mps, ratio), 2),
        heading_deg=round(_lerp_heading_deg(previous.heading_deg, target.heading_deg, ratio), 2),
        track_heading_deg=round(_lerp_heading_deg(previous.track_heading_deg, target.track_heading_deg, ratio), 2),
        wind_e_mps=round(_lerp_float(previous.wind_e_mps, target.wind_e_mps, ratio), 3),
        wind_n_mps=round(_lerp_float(previous.wind_n_mps, target.wind_n_mps, ratio), 3),
        lateral_dev_m=round(_lerp_float(previous.lateral_dev_m, target.lateral_dev_m, ratio), 3),
        battery_pct=round(_lerp_float(previous.battery_pct, target.battery_pct, ratio), 2),
    )


def _departure_origin_frame(plan: FlightPlan) -> LocalNEDFrame:
    """첫 세그먼트의 start_lla 를 NED 원점으로 사용."""
    if plan.en_route:
        start = plan.en_route[0].start_lla
        return LocalNEDFrame(origin_lat=start.lat, origin_lon=start.lon, origin_alt_m=start.alt)
    return LocalNEDFrame(origin_lat=0.0, origin_lon=0.0, origin_alt_m=0.0)


class VehicleSession:
    """한 비행체의 엔진 + 컨텍스트 + 상태를 관리."""

    def __init__(
        self,
        plan: FlightPlan,
        *,
        config: SimulationConfig,
        wind_seed: int = 20260121,
        month: int = 4,
    ) -> None:
        self.plan = plan
        self.config = config
        self.wind_seed = int(wind_seed)
        self.month = int(month)

        self.state: VehicleState = VehicleState.WAITING
        self.last_error: str = ""
        self.last_point: Optional[FlightTrajectoryPoint] = None
        self.last_payload: Optional[Dict[str, Any]] = None
        self.elapsed_s: float = 0.0
        self.trajectory: List[FlightTrajectoryPoint] = []
        self.trajectory_index: int = 0
        self.trajectory_time_offset_s: float = 0.0
        self.last_emit_target_time_s: Optional[float] = None
        self.pose_frame: Optional[OdtPoseFrameState] = None
        self.start_sim_time_s: Optional[float] = None
        self._final_emitted: bool = False
        self.origin_frame: LocalNEDFrame = _departure_origin_frame(plan)
        self.context: VehiclePublishContext = VehiclePublishContext(
            vehicle_id=plan.aircraft_id,
            flight_plan_number=int(plan.flight_plan_number),
            origin_frame=self.origin_frame,
            departure_vertiport=str(plan.departure.vertiport),
            departure_gate=str(plan.departure.dep_gate_number),
            arrival_vertiport=str(plan.arrival.vertiport),
            arrival_gate=str(plan.arrival.arr_gate_number),
        )

        try:
            self.etot_s: float = _parse_hhmmss_to_s(plan.departure.etot)
        except Exception as exc:
            self.etot_s = 0.0
            self.last_error = f"etot parse failed: {exc}"
            self.state = VehicleState.ERROR

    def reset(self) -> None:
        self.state = VehicleState.WAITING
        self.last_error = ""
        self.last_point = None
        self.last_payload = None
        self.elapsed_s = 0.0
        self.trajectory_index = 0
        self.last_emit_target_time_s = None
        self.pose_frame = None
        self.start_sim_time_s = None
        self._final_emitted = False
        for attr in ("_prev_alt_m", "_prev_point_time_s", "_seq_cursor"):
            if hasattr(self, attr):
                delattr(self, attr)

    @property
    def aircraft_id(self) -> str:
        return self.plan.aircraft_id

    @property
    def flight_plan_number(self) -> int:
        return int(self.plan.flight_plan_number)

    def _ensure_trajectory(self) -> None:
        if self.trajectory:
            return
        try:
            simulator = UAMFlightSimulator(
                config=self.config,
                wind_seed=self.wind_seed,
                month=self.month,
            )
            result = simulator.simulate_plan(self.plan)
            self.trajectory = trim_airsim_sync_trajectory(list(result.trajectory))
            self.trajectory_index = 0
            self.trajectory_time_offset_s = (
                float(self.trajectory[0].time_s) if self.trajectory else 0.0
            )
            self.pose_frame = None
            self._final_emitted = False
            if not self.trajectory:
                raise RuntimeError("simpleDynamics returned an empty trajectory")
        except Exception as exc:
            self.state = VehicleState.ERROR
            self.last_error = f"trajectory init failed: {type(exc).__name__}: {exc}"
            logger.exception("trajectory init failed for %s", self.aircraft_id)

    def _ensure_pose_frame(self) -> Optional[OdtPoseFrameState]:
        self._ensure_trajectory()
        if self.pose_frame is not None:
            return self.pose_frame
        if not self.trajectory:
            return None
        first = self.trajectory[0]
        self.pose_frame = OdtPoseFrameState(
            origin_lat=float(first.lat),
            origin_lon=float(first.lon),
            origin_alt_m=float(first.alt_m),
            spawn_pose=load_spawn_pose_for_aircraft(self.aircraft_id),
            yaw_rate_deg_s=float(getattr(self.config, "turn_rate_deg_s", 12.0) or 12.0),
        )
        return self.pose_frame

    def project_point_to_pose_frame(
        self,
        point: FlightTrajectoryPoint,
        heading_deg: float,
    ) -> Optional[Dict[str, Any]]:
        pose_frame = self._ensure_pose_frame()
        if pose_frame is None:
            return None
        return pose_frame.project(
            lat=float(point.lat),
            lon=float(point.lon),
            alt_m=float(point.alt_m),
            heading_deg=float(heading_deg),
            time_s=float(getattr(point, "time_s", 0.0) or 0.0),
        )

    def advance(self, sim_time_s: float) -> Optional[FlightTrajectoryPoint]:
        """sim_time_s 가 etot 이상이면 engine.tick() 을 1회 전진시킨다."""
        if self.state == VehicleState.COMPLETED:
            return None
        if self.state == VehicleState.ERROR:
            return None

        self._ensure_trajectory()
        if not self.trajectory:
            return None

        if self.state == VehicleState.WAITING:
            self.state = VehicleState.ACTIVE

        if self.start_sim_time_s is None:
            self.start_sim_time_s = float(sim_time_s)
        target_elapsed_s = max(0.0, float(sim_time_s) - float(self.start_sim_time_s))
        target_time_s = target_elapsed_s + float(self.trajectory_time_offset_s)
        last_index = len(self.trajectory) - 1
        last_time_s = float(self.trajectory[last_index].time_s)

        if target_time_s >= last_time_s - 1e-6:
            if self._final_emitted:
                self.state = VehicleState.COMPLETED
                return None
            self.trajectory_index = last_index
            point = self.trajectory[last_index]
            self._final_emitted = True
        else:
            while (
                self.trajectory_index + 1 < last_index
                and float(self.trajectory[self.trajectory_index + 1].time_s)
                <= target_time_s + 1e-9
            ):
                self.trajectory_index += 1
            while (
                self.trajectory_index > 0
                and float(self.trajectory[self.trajectory_index].time_s)
                > target_time_s + 1e-9
            ):
                self.trajectory_index -= 1
            current = self.trajectory[self.trajectory_index]
            next_point = (
                self.trajectory[self.trajectory_index + 1]
                if self.trajectory_index + 1 <= last_index
                else current
            )
            point = (
                current
                if next_point is current
                else _interpolate_trajectory_point(current, next_point, target_time_s)
            )

        if point is None:
            self.state = VehicleState.COMPLETED
            return None
        if self.last_point is not None and self.last_emit_target_time_s is not None:
            dt_s = float(target_time_s) - float(self.last_emit_target_time_s)
            if dt_s >= -1e-6:
                dt_s = max(PUBLISH_PERIOD_S, dt_s)
                speed_hint = max(
                    abs(float(getattr(self.last_point, "speed_mps", 0.0) or 0.0)),
                    abs(float(getattr(point, "speed_mps", 0.0) or 0.0)),
                )
                max_step_m = max(0.75, speed_hint * dt_s * 1.5 + 0.25)
                point = _limit_trajectory_step(self.last_point, point, max_step_m)
        self.last_point = point
        self.last_emit_target_time_s = float(target_time_s)
        total_s = max(0.0, last_time_s - float(self.trajectory_time_offset_s))
        self.elapsed_s = min(target_elapsed_s, total_s)
        return point

    def status(self) -> VehicleStatus:
        total = 0.0
        if self.trajectory:
            total = max(0.0, float(self.trajectory[-1].time_s) - float(self.trajectory_time_offset_s))
        last_pt_dict: Optional[Dict[str, Any]] = None
        if self.last_payload is not None:
            pos = self.last_payload.get("position") or {}
            gps = self.last_payload.get("gps") or {}
            last_pt_dict = {
                "lat": gps.get("latitude"),
                "lon": gps.get("longitude"),
                "alt_m": gps.get("altitude"),
                "north": pos.get("north"),
                "east": pos.get("east"),
                "down": pos.get("down"),
                "waypoint_id": self.last_payload.get("currentWaypointId"),
            }
        return VehicleStatus(
            vehicle_id=self.aircraft_id,
            flight_plan_number=self.flight_plan_number,
            state=self.state,
            etot_s=float(self.etot_s),
            elapsed_s=float(self.elapsed_s),
            total_duration_s=float(total),
            last_point=last_pt_dict,
            last_error=self.last_error,
        )


class IntegratedAirMobilityService(VehicleModule):
    """Top-level 서비스.

    - 비행계획들을 등록
    - clock 모드 설정 (external / wall / manual)
    - 30 Hz 로 tick → 각 session.advance() → 4001 묶어서 publish
    """

    def __init__(
        self,
        *,
        target_ip: str = "127.0.0.1",
        ws_port: int = 8096,
        async_send: bool = True,
        config: Optional[SimulationConfig] = None,
        wind_seed: int = 20260121,
        month: int = 4,
    ) -> None:
        self.config = config or SimulationConfig(tick_s=PUBLISH_PERIOD_S)
        # 30 Hz 로 고정
        self.config.tick_s = PUBLISH_PERIOD_S
        self.config.wind_enabled = False
        self.config.trajectory_turn_smoothing_radius_m = MISSION_CORNER_SMOOTHING_RADIUS_M
        self.config.vehicle_dynamics_enabled = True

        self.wind_seed = int(wind_seed)
        self.month = int(month)
        self._lock = threading.RLock()

        self.target_ip = str(target_ip)
        self.ws_port = int(ws_port)
        self._async_send = bool(async_send)
        super().__init__(
            server_url=f"ws://{self.target_ip}:{self.ws_port}/ws/dtam",
            heartbeat=True,
        )
        self.publisher = _VehicleModulePublisherAdapter(
            self,
            target_ip=self.target_ip,
            ws_port=self.ws_port,
        )

        self._sessions: Dict[str, VehicleSession] = {}
        self._clock_mode: ClockMode = ClockMode.EXTERNAL
        self._control_mode: ControlMode = ControlMode.MISSION
        self._manual_config = ManualVehicleConfig()
        self._manual_dynamics = create_operator_dynamics("manual_kinematic", self._manual_config)
        self._manual_context = VehiclePublishContext(
            vehicle_id=self._manual_config.vehicle_id,
            flight_plan_number=int(self._manual_config.flight_plan_number),
            origin_frame=self._manual_config.origin_frame,
            current_waypoint_id=build_manual_waypoint_id(self._manual_config.flight_plan_number),
        )
        self._manual_input = ManualControlInput()
        self._manual_last_payload: Optional[Dict[str, Any]] = None
        self._manual_last_tick_wall = time.monotonic()
        self._running = False
        self._sim_time_s: float = 0.0
        self._wall_origin_wall: float = 0.0   # 실시간 기준점(모노토닉)
        self._wall_origin_sim: float = 0.0    # 해당 시점의 sim 시각
        self._pending_ext_time: Optional[float] = None
        self._ext_event = threading.Event()
        self._last_external_tick_wall = time.monotonic()
        self._external_time_initialized = False
        self._play_state = "pause"
        self._playback_speed_x = 1.0
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.on_publish: Optional[Callable[[Dict[str, Any]], None]] = None

        # 수신 통계/기록
        self._rx_3001_count: int = 0
        self._rx_0003_count: int = 0
        self._rx_2002_count: int = 0
        self._rx_3002_count: int = 0
        self._rx_3003_count: int = 0
        self._rx_5001_count: int = 0
        self._last_rx_3001: str = ""
        self._last_rx_0003: str = ""
        self._last_rx_2002: str = ""
        self._last_rx_3002: str = ""
        self._last_rx_3003: str = ""
        self._last_rx_5001: str = ""
        self._last_heartbeat_error: str = ""
        # 계획 버전 추적 (planVersion 이 낮으면 무시)
        self._plan_versions: Dict[str, int] = {}

    # ── 비행계획 관리 ──────────────────────────────────────────

    def add_plan(self, plan_or_dict: Any) -> str:
        if isinstance(plan_or_dict, FlightPlan):
            plan = plan_or_dict
        elif isinstance(plan_or_dict, dict):
            plan = parse_flight_plan(plan_or_dict)
        else:
            raise TypeError("plan must be FlightPlan or dict")

        session = VehicleSession(
            plan,
            config=self.config,
            wind_seed=self.wind_seed,
            month=self.month,
        )
        session._ensure_trajectory()
        if session.state == VehicleState.ERROR:
            raise RuntimeError(session.last_error or f"trajectory init failed for {plan.aircraft_id}")
        with self._lock:
            self._sessions[plan.aircraft_id] = session
        logger.info(
            "registered plan: %s (etot=%s, fpn=%d)",
            plan.aircraft_id, plan.departure.etot, plan.flight_plan_number,
        )
        return plan.aircraft_id

    def add_plans_from_json(self, data: Any) -> List[str]:
        plans = parse_flight_plans(data)
        ids: List[str] = []
        for p in plans:
            ids.append(self.add_plan(p))
        return ids

    def remove_plan(self, vehicle_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(vehicle_id, None) is not None

    def clear_plans(self) -> None:
        with self._lock:
            self._sessions.clear()

    def reset_sessions(self) -> None:
        with self._lock:
            for session in self._sessions.values():
                session.reset()
            self._sim_time_s = 0.0
            self._pending_ext_time = None
            self._last_external_tick_wall = time.monotonic()
            self._external_time_initialized = False

    # ── 송신기 재설정 ──────────────────────────────────────────

    def reconfigure_publisher(
        self,
        *,
        target_ip: Optional[str] = None,
        ws_port: Optional[int] = None,
    ) -> None:
        self.publisher.reconfigure(
            target_ip=target_ip,
            ws_port=ws_port,
        )

    # ── 시계 제어 ──────────────────────────────────────────────

    def _start_heartbeat(self) -> None:
        super()._start_heartbeat()

    def _stop_heartbeat(self) -> None:
        # DtamModule.close() owns the WebSocket heartbeat shutdown.
        return

    def _heartbeat_loop(self) -> None:
        super()._heartbeat_loop()

    def set_clock_mode(self, mode: ClockMode | str) -> None:
        mode = ClockMode(mode) if isinstance(mode, str) else mode
        with self._lock:
            self._clock_mode = mode
            if mode == ClockMode.WALL:
                self._wall_origin_wall = time.monotonic()
                self._wall_origin_sim = float(self._sim_time_s)
            if mode == ClockMode.EXTERNAL:
                self._last_external_tick_wall = time.monotonic()
                self._external_time_initialized = False

    def set_control_mode(self, mode: ControlMode | str) -> None:
        mode = ControlMode(mode) if isinstance(mode, str) else mode
        with self._lock:
            self._control_mode = mode
            self._manual_last_tick_wall = time.monotonic()
            if mode != ControlMode.MISSION:
                self._clock_mode = ClockMode.WALL

    def configure_manual_vehicle(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            self._manual_config = ManualVehicleConfig.from_dict(data, self._manual_config)
            self._manual_dynamics.configure(self._manual_config)
            self._manual_context = VehiclePublishContext(
                vehicle_id=self._manual_config.vehicle_id,
                flight_plan_number=int(self._manual_config.flight_plan_number),
                origin_frame=self._manual_config.origin_frame,
                current_waypoint_id=build_manual_waypoint_id(self._manual_config.flight_plan_number),
            )
            self._manual_last_payload = None
            self._manual_last_tick_wall = time.monotonic()
            return self._manual_dynamics.snapshot()

    def set_manual_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        command = ManualControlInput.from_dict(data)
        with self._lock:
            self._manual_input = command
            self._manual_dynamics.set_input(command)
            if self._control_mode == ControlMode.MISSION:
                self._control_mode = ControlMode.KEYBOARD
                self._clock_mode = ClockMode.WALL
            return self._manual_dynamics.snapshot()

    def submit_operator_control_input(
        self,
        data: Dict[str, Any],
        *,
        source: str = "api",
        control_mode: str = "",
        send_via_server: bool = True,
    ) -> Dict[str, Any]:
        """Apply manual input locally and also publish MSG 5001 through the server."""
        payload = self._build_operator_control_payload(
            data,
            source=source,
            control_mode=control_mode,
        )
        manual = self._apply_operator_control_payload(payload, count_rx=False)
        sent = False
        send_error = ""
        if send_via_server:
            try:
                sent = bool(self.send(parse_payload("5001", payload)))
            except Exception as exc:
                send_error = f"{type(exc).__name__}: {exc}"
                logger.debug("5001 publish failed, local input already applied: %s", send_error)
        return {
            "ok": True,
            "sent": sent,
            "send_error": send_error,
            "payload": payload,
            "manual": manual,
        }

    def _build_operator_control_payload(
        self,
        data: Dict[str, Any],
        *,
        source: str,
        control_mode: str,
    ) -> Dict[str, Any]:
        raw = dict(data or {})
        axes = raw.get("axes") if isinstance(raw.get("axes"), dict) else raw
        with self._lock:
            vehicle_id = str(raw.get("aircraftId") or raw.get("vehicleId") or self._manual_config.vehicle_id).strip()
        source_text = str(raw.get("source") or source or "api").strip().lower()
        mode_text = str(raw.get("controlMode") or raw.get("mode") or control_mode or source_text or "keyboard").strip().lower()
        return {
            "timestamp": iso_timestamp(datetime.now(timezone.utc)),
            "aircraftId": vehicle_id or "UAM0001",
            "source": source_text,
            "controlMode": mode_text,
            "sequence": int(time.time() * 1000) & 0x7FFFFFFF,
            "active": _truthy(raw.get("active"), True),
            "axes": ManualControlInput.from_dict(axes).to_dict(),
            "buttons": list(raw.get("buttons") or []),
            "hats": list(raw.get("hats") or []),
            "rawAxes": dict(raw.get("rawAxes") or {}),
        }

    def _apply_operator_control_payload(
        self,
        raw: Dict[str, Any],
        *,
        count_rx: bool = True,
    ) -> Dict[str, Any]:
        axes = raw.get("axes") if isinstance(raw.get("axes"), dict) else raw
        active = _truthy(raw.get("active"), True)
        command = ManualControlInput.from_dict(axes if active else {})
        mode_text = str(raw.get("controlMode") or raw.get("mode") or raw.get("source") or "").strip().lower()
        vehicle_id = str(raw.get("aircraftId") or raw.get("vehicleId") or "").strip()
        should_start_manual_stream = False

        with self._lock:
            if vehicle_id and vehicle_id != self._manual_config.vehicle_id:
                self._manual_config = ManualVehicleConfig.from_dict(
                    {"vehicle_id": vehicle_id},
                    self._manual_config,
                )
                self._manual_dynamics.configure(self._manual_config)
                self._manual_context = VehiclePublishContext(
                    vehicle_id=self._manual_config.vehicle_id,
                    flight_plan_number=int(self._manual_config.flight_plan_number),
                    origin_frame=self._manual_config.origin_frame,
                    current_waypoint_id=build_manual_waypoint_id(self._manual_config.flight_plan_number),
                )
                self._manual_last_payload = None

            self._manual_input = command
            self._manual_dynamics.set_input(command)

            if mode_text in ("mission", "auto", "autopilot"):
                self._control_mode = ControlMode.MISSION
            elif mode_text in ("joystick", "stick"):
                self._control_mode = ControlMode.JOYSTICK
                self._clock_mode = ClockMode.WALL
            elif mode_text in ("keyboard", "manual", "api", "operator", ""):
                if self._control_mode == ControlMode.MISSION or mode_text in ("keyboard", "manual", "api", "operator"):
                    self._control_mode = ControlMode.KEYBOARD
                self._clock_mode = ClockMode.WALL
            else:
                if self._control_mode == ControlMode.MISSION:
                    self._control_mode = ControlMode.KEYBOARD
                    self._clock_mode = ClockMode.WALL

            if active and self._control_mode != ControlMode.MISSION:
                self._clock_mode = ClockMode.WALL
                self._play_state = "play"
                if self._playback_speed_x <= 0.0:
                    self._playback_speed_x = 1.0
                should_start_manual_stream = True

            self._manual_last_tick_wall = time.monotonic()
            if count_rx:
                self._rx_5001_count += 1
                self._last_rx_5001 = (
                    f"{raw.get('source') or ''}/{self._control_mode.value} "
                    f"{self._manual_config.vehicle_id} "
                    f"r={command.roll:.2f} p={command.pitch:.2f} y={command.yaw:.2f} t={command.throttle:.2f}"
                ).strip()
            snapshot = self._manual_dynamics.snapshot()
        if should_start_manual_stream:
            self.start()
        return snapshot

    def manual_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return self._manual_dynamics.snapshot()

    def feed_time_seconds(self, sim_time_s: float) -> None:
        with self._lock:
            self._pending_ext_time = float(sim_time_s)
        self._ext_event.set()

    def feed_time_hhmmss(self, hhmmss: str) -> None:
        self.feed_time_seconds(_parse_hhmmss_to_s(hhmmss))

    def set_sim_time(self, sim_time_s: float) -> None:
        """현재 sim 시간을 강제 설정(재시작/되감기용)."""
        with self._lock:
            self._sim_time_s = float(sim_time_s)
            self._external_time_initialized = True
            if self._clock_mode == ClockMode.WALL:
                self._wall_origin_wall = time.monotonic()
                self._wall_origin_sim = float(sim_time_s)

    def step_once(self, sim_time_s: float) -> Dict[str, Any]:
        """한 tick 만 실행 (MANUAL 모드). 전송된 4001 메시지 반환 (비어있을 수 있음)."""
        with self._lock:
            self._sim_time_s = float(sim_time_s)
        return self._run_tick(self._sim_time_s)

    def apply_simulation_setup(
        self,
        data: Optional[Dict[str, Any]] = None,
        *,
        playback_speed: Optional[float] = None,
        play_state: Optional[str] = None,
    ) -> Dict[str, Any]:
        raw = dict(data or {})
        speed_value = playback_speed
        if speed_value is None:
            speed_value = raw.get("playbackSpeed")
        state_value = str(play_state or raw.get("playState") or "pause").strip().lower()
        if state_value not in {"play", "pause", "reset"}:
            state_value = "pause"
        try:
            speed_x = float(speed_value if speed_value is not None else 1.0)
        except (TypeError, ValueError):
            speed_x = 1.0
        speed_x = max(0.0, speed_x)

        if state_value == "reset":
            self.reset_sessions()
            state_value = "pause"

        now = time.monotonic()
        with self._lock:
            self._playback_speed_x = speed_x
            self._play_state = state_value
            self._last_external_tick_wall = now
            sim_time_s = float(self._sim_time_s)

        if state_value == "play":
            self.start()
        return {
            "play_state": state_value,
            "playback_speed_x": speed_x,
            "sim_time_s": sim_time_s,
            "running": self.status().running,
        }

    # ── 생명주기 ──────────────────────────────────────────────

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._loop,
                name="dtam-airmobility",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False
        self._stop_event.set()
        self._ext_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        self._thread = None

    def close(self) -> None:
        self._stop_heartbeat()
        self.stop()
        self.publisher.close()
        VehicleModule.close(self)

    # ── 내부 ──────────────────────────────────────────────────

    def _loop(self) -> None:
        next_deadline = time.monotonic()
        while not self._stop_event.is_set():
            with self._lock:
                mode = self._clock_mode
                control_mode = self._control_mode

            if control_mode != ControlMode.MISSION:
                now = time.monotonic()
                with self._lock:
                    dt = now - self._manual_last_tick_wall
                    self._manual_last_tick_wall = now
                    play_state = self._play_state
                    speed = max(0.0, float(self._playback_speed_x))
                    if play_state == "play":
                        self._sim_time_s += max(0.0, dt) * speed
                    sim_t = self._sim_time_s
                if play_state == "play":
                    self._run_manual_tick(dt * speed, sim_t)
                next_deadline += PUBLISH_PERIOD_S
                delay = next_deadline - time.monotonic()
                if delay > 0:
                    if self._stop_event.wait(delay):
                        break
                else:
                    next_deadline = time.monotonic()
                continue

            if mode == ClockMode.WALL:
                now = time.monotonic()
                with self._lock:
                    dt = max(0.0, now - self._last_external_tick_wall)
                    self._last_external_tick_wall = now
                    play_state = self._play_state
                    speed = max(0.0, float(self._playback_speed_x))
                    if play_state == "play":
                        self._sim_time_s += dt * speed
                    sim_t = float(self._sim_time_s)
                if play_state != "play":
                    next_deadline += PUBLISH_PERIOD_S
                    delay = next_deadline - time.monotonic()
                    if delay > 0:
                        if self._stop_event.wait(delay):
                            break
                    else:
                        next_deadline = time.monotonic()
                    continue
                self._run_tick(sim_t)
                next_deadline += PUBLISH_PERIOD_S
                delay = next_deadline - time.monotonic()
                if delay > 0:
                    if self._stop_event.wait(delay):
                        break
                else:
                    # 드리프트 방지
                    next_deadline = time.monotonic()
            elif mode == ClockMode.EXTERNAL:
                # 외부 공통시간은 동기 기준으로만 쓰고, 4001은 내부 30 Hz 주기로 진행한다.
                got = self._ext_event.wait(timeout=PUBLISH_PERIOD_S)
                if self._stop_event.is_set():
                    break
                now = time.monotonic()
                with self._lock:
                    if got:
                        self._ext_event.clear()
                    pending = self._pending_ext_time
                    self._pending_ext_time = None
                    if pending is not None:
                        self._sim_time_s = float(pending)
                        self._external_time_initialized = True
                    dt = max(0.0, now - self._last_external_tick_wall)
                    self._last_external_tick_wall = now
                    play_state = self._play_state
                    speed = max(0.0, float(self._playback_speed_x))
                    if play_state == "play":
                        self._sim_time_s += dt * speed
                    sim_t = float(self._sim_time_s)
                if play_state != "play":
                    continue
                self._run_tick(sim_t)
            else:
                # MANUAL — 루프는 idle. stop 이 올 때까지 대기.
                if self._stop_event.wait(timeout=0.25):
                    break

    def _run_manual_tick(self, dt: float, sim_time_s: float) -> Dict[str, Any]:
        """Advance manual dynamics once and publish the resulting 4001 message."""
        with self._lock:
            sample = self._manual_dynamics.tick(dt)
            context = self._manual_context
            context.current_waypoint_id = sample.waypoint_id
            context.battery_pct = sample.battery_pct

        payload = build_vehicle_payload(
            context=context,
            lat=sample.lat,
            lon=sample.lon,
            alt_m=sample.alt_m,
            speed_mps=sample.speed_mps,
            heading_deg=sample.heading_deg,
            track_heading_deg=sample.track_heading_deg,
            pitch_rad=sample.pitch_rad,
            roll_rad=sample.roll_rad,
            climb_rate_mps=sample.climb_rate_mps,
            phase="MANUAL",
            seq=0,
            battery_pct=sample.battery_pct,
            actuator=sample.actuator.to_dict(),
            propulsion=sample.propulsion.to_dict(),
            gps=sample.gps.to_dict(),
            imu=sample.imu.to_dict(),
            barometer=sample.barometer.to_dict(),
        )
        payload["position"] = {
            "north": float(sample.north_m),
            "east": float(sample.east_m),
            "down": float(sample.down_m),
        }
        self._manual_last_payload = payload

        message = build_4001_message({sample.vehicle_id: payload}, timestamp=_sim_time_to_iso(sim_time_s))
        try:
            self.publisher.push(message)
        except Exception:
            logger.exception("manual publisher push failed")
        if self.on_publish is not None:
            try:
                self.on_publish(message)
            except Exception:
                pass
        return message

    def _run_tick(self, sim_time_s: float) -> Dict[str, Any]:
        """현재 sim 시간에 맞춰 1 tick 진행하고 4001 을 송출."""
        with self._lock:
            sessions = list(self._sessions.values())

        vehicle_payloads: Dict[str, Dict[str, Any]] = {}
        for session in sessions:
            try:
                point = session.advance(sim_time_s)
            except Exception as exc:
                session.state = VehicleState.ERROR
                session.last_error = f"advance failed: {type(exc).__name__}: {exc}"
                logger.exception("advance failed for %s", session.aircraft_id)
                continue
            if point is None:
                continue

            heading = float(getattr(point, "heading_deg", 0.0) or 0.0)
            track = getattr(point, "track_heading_deg", None)
            alt_m = float(getattr(point, "alt_m", 0.0) or 0.0)
            point_time_s = float(getattr(point, "time_s", 0.0) or 0.0)
            prev_alt = getattr(session, "_prev_alt_m", alt_m)
            prev_point_time_s = getattr(session, "_prev_point_time_s", point_time_s)
            point_dt_s = max(0.0, point_time_s - float(prev_point_time_s))
            climb_rate = (alt_m - prev_alt) / point_dt_s if point_dt_s > 1e-6 else 0.0
            session._prev_alt_m = alt_m  # type: ignore[attr-defined]
            session._prev_point_time_s = point_time_s  # type: ignore[attr-defined]

            # phase + seq 기반 waypoint id
            phase = str(getattr(point, "phase", "") or "")
            seq = _find_seq_for_phase(session.plan, phase, getattr(session, "_seq_cursor", 0))
            session._seq_cursor = seq  # type: ignore[attr-defined]

            # waypoint id 결정
            if session.state == VehicleState.ACTIVE:
                if seq >= 1:
                    session.context.current_waypoint_id = (
                        f"{session.flight_plan_number}-{seq}"
                    )
                elif phase and phase in ("A",):
                    session.context.current_waypoint_id = (
                        f"{session.flight_plan_number}-"
                        f"{session.plan.departure.vertiport}-"
                        f"{session.plan.departure.dep_gate_number}"
                    )
            session.context.battery_pct = float(getattr(point, "battery_pct", 100.0))
            pose_projection = session.project_point_to_pose_frame(point, heading)
            pose_position = None
            pose_yaw_deg = None
            pose_frame = None
            if isinstance(pose_projection, dict):
                # 4001 position is mission-relative NED. The AirSim settings
                # spawn pose is kept only as diagnostic poseFrame metadata;
                # adding it here makes MP-only play reuse stale settings and
                # causes the aircraft to jump to an unrelated world location.
                pose_position = pose_projection.get("relative_position")
                pose_yaw_deg = pose_projection.get("yaw_deg")
                pose_frame = pose_projection.get("pose_frame")

            payload = build_vehicle_payload(
                context=session.context,
                lat=float(getattr(point, "lat", 0.0)),
                lon=float(getattr(point, "lon", 0.0)),
                alt_m=alt_m,
                speed_mps=float(getattr(point, "speed_mps", 0.0)),
                heading_deg=heading,
                track_heading_deg=float(track) if track is not None else None,
                pitch_rad=0.0,
                roll_rad=0.0,
                climb_rate_mps=float(climb_rate),
                phase=phase,
                seq=seq,
                battery_pct=float(getattr(point, "battery_pct", 100.0)),
                position_ned=pose_position if isinstance(pose_position, dict) else None,
                attitude_yaw_deg=float(pose_yaw_deg) if pose_yaw_deg is not None else None,
                pose_frame=pose_frame if isinstance(pose_frame, dict) else None,
            )
            session.last_payload = payload
            vehicle_payloads[session.aircraft_id] = payload

        if not vehicle_payloads:
            return {}

        # 시뮬레이션 sim_time_s 를 UTC ISO 타임스탬프로 — 오늘 자정 기준으로 매핑
        ts = _sim_time_to_iso(sim_time_s)
        message = build_4001_message(vehicle_payloads, timestamp=ts)
        try:
            self.publisher.push(message)
        except Exception:
            logger.exception("publisher push failed")
        if self.on_publish is not None:
            try:
                self.on_publish(message)
            except Exception:
                pass
        return message

    # ── 상태 질의 ──────────────────────────────────────────────

    def status(self) -> FleetStatus:
        with self._lock:
            sessions = list(self._sessions.values())
            clock_mode = self._clock_mode.value
            control_mode = self._control_mode.value
            dynamics_model = "mission_profile" if self._control_mode == ControlMode.MISSION else "manual_kinematic"
            running = self._running
            play_state = self._play_state
            playback_speed_x = float(self._playback_speed_x)
            sim_t = float(self._sim_time_s)
            rx3 = self._rx_3001_count
            rx0 = self._rx_0003_count
            rx_exec = self._rx_2002_count
            rx_strategic = self._rx_3002_count
            rx_tactical = self._rx_3003_count
            rx_manual = self._rx_5001_count
            last3 = self._last_rx_3001
            last0 = self._last_rx_0003
            last_exec = self._last_rx_2002
            last_strategic = self._last_rx_3002
            last_tactical = self._last_rx_3003
            last_manual = self._last_rx_5001
            heartbeat_error = self._last_heartbeat_error
            manual = self._manual_dynamics.snapshot()
        return FleetStatus(
            control_mode=control_mode,
            dynamics_model=dynamics_model,
            clock_mode=clock_mode,
            running=running,
            play_state=play_state,
            playback_speed_x=playback_speed_x,
            publisher_connected=self.publisher.connected,
            publisher_error=self.publisher.last_error or "",
            sim_time_s=sim_t,
            sim_time_hms=_s_to_hhmmss(sim_t),
            vehicles=[s.status() for s in sessions],
            rx_3001_count=rx3,
            rx_0003_count=rx0,
            rx_2002_count=rx_exec,
            rx_3002_count=rx_strategic,
            rx_3003_count=rx_tactical,
            rx_5001_count=rx_manual,
            last_rx_3001=last3,
            last_rx_0003=last0,
            last_rx_2002=last_exec,
            last_rx_3002=last_strategic,
            last_rx_3003=last_tactical,
            last_rx_5001=last_manual,
            last_heartbeat_error=heartbeat_error,
            manual=manual,
        )

    # ── DTAM 수신 핸들러 ──────────────────────────────────────

    def on_scheduled_flight(self, msg: Any) -> None:
        self._on_scheduled_flight(_CompatReceiveResult(msg))

    def on_common_time_info(self, msg: Any) -> None:
        self._on_common_time_info(_CompatReceiveResult(msg))

    def on_simulation_setup(self, msg: Any) -> None:
        self._on_simulation_setup(_CompatReceiveResult(msg))

    def on_dtam_execute(self, msg: Any) -> None:
        self._on_dtam_execute(_CompatReceiveResult(msg))

    def on_strategic_separation(self, msg: Any) -> None:
        self._on_strategic_separation(_CompatReceiveResult(msg))

    def on_tactical_separation(self, msg: Any) -> None:
        self._on_tactical_separation(_CompatReceiveResult(msg))

    def on_operator_control_input(self, msg: Any) -> None:
        self._on_operator_control_input(_CompatReceiveResult(msg))

    def _on_scheduled_flight(self, result: Any) -> None:
        """MSG 3001 수신 → 해당 비행체의 계획을 자동 등록/갱신.

        ``result`` 는 dtam_client 의 ReceiveResult (raw dict 포함).
        planStatus == 'discarded' 면 해당 비행체 계획 제거.
        planStatus == 'superseded' 면 무시 (더 신선한 active 가 올 것).
        planVersion 이 기존보다 낮으면 무시.
        """
        try:
            raw = getattr(result, "raw", None) or {}
            ok = bool(getattr(result, "ok", True))
            if not ok:
                logger.warning("3001 수신 무효: %s", getattr(result, "errors", None))
                return
            vehicle_id = str(raw.get("aircraftId") or "").strip()
            fpn = raw.get("flightPlanNumber")
            version = int(raw.get("planVersion") or 0)
            status_text = str(raw.get("planStatus") or "active").lower()
            brief = f"fpn={fpn} v={version} {status_text} {vehicle_id}"
            with self._lock:
                self._rx_3001_count += 1
                self._last_rx_3001 = brief

            if status_text == "discarded":
                removed = self.remove_plan(vehicle_id)
                logger.info("3001 discarded → remove %s (removed=%s)", vehicle_id, removed)
                self._plan_versions.pop(vehicle_id, None)
                return
            if status_text == "superseded":
                logger.info("3001 superseded → ignore %s", vehicle_id)
                return

            prev_version = self._plan_versions.get(vehicle_id, -1)
            if version > 0 and version < prev_version:
                logger.info(
                    "3001 older version → ignore (%s v=%s < v=%s)",
                    vehicle_id, version, prev_version,
                )
                return

            # 기존 계획이 있으면 교체
            if vehicle_id and vehicle_id in self._sessions:
                self.remove_plan(vehicle_id)
            added = self.add_plan(raw)
            self._plan_versions[vehicle_id or added] = version
            logger.info("3001 → plan updated: %s", brief)
        except Exception:
            logger.exception("_on_scheduled_flight failed")

    def _on_common_time_info(self, result: Any) -> None:
        """MSG 0003 수신 → simTime 을 시계로 주입.

        - 공통 시간은 권위 있는 시간 원천이므로 모드에 상관없이 ``_sim_time_s`` 갱신.
        - EXTERNAL 모드인 경우 추가로 ``feed_time_seconds`` 를 호출해
          서비스 루프가 1 tick 진행하고 4001 을 송출하도록 유도.
        """
        try:
            sim_iso = getattr(result, "sim_time", None) or ""
            if not sim_iso:
                raw = getattr(result, "raw", None) or {}
                sim_iso = raw.get("simTime") or ""
            if not sim_iso:
                return
            sim_s = _iso_to_seconds_of_day(str(sim_iso))
            with self._lock:
                self._rx_0003_count += 1
                self._last_rx_0003 = str(sim_iso)
                mode = self._clock_mode
                should_apply_time = not self._external_time_initialized
                if should_apply_time:
                    self._sim_time_s = float(sim_s)
                    self._last_external_tick_wall = time.monotonic()
                    self._external_time_initialized = True
            if mode == ClockMode.EXTERNAL and should_apply_time:
                self.feed_time_seconds(sim_s)
        except Exception:
            logger.exception("_on_common_time_info failed")

    def _on_simulation_setup(self, result: Any) -> None:
        try:
            raw = getattr(result, "raw", None) or {}
            speed = getattr(result, "playback_speed", None)
            if speed is None:
                speed = raw.get("playbackSpeed")
            play_state = str(getattr(result, "play_state", None) or raw.get("playState") or "pause").strip().lower()
            applied = self.apply_simulation_setup(raw, playback_speed=speed, play_state=play_state)
            logger.info(
                "1002 Simulation Control received: playState=%s speed=%sx",
                applied["play_state"],
                applied["playback_speed_x"],
            )
        except Exception:
            logger.exception("_on_simulation_setup failed")

    def _on_dtam_execute(self, result: Any) -> None:
        try:
            raw = getattr(result, "raw", None) or {}
            folder = str(raw.get("flightPlanFolderName") or "")
            self.reset_sessions()
            with self._lock:
                self._rx_2002_count += 1
                self._last_rx_2002 = folder or str(raw)
                self._control_mode = ControlMode.MISSION
                self._play_state = "pause"
                self._last_external_tick_wall = time.monotonic()
            logger.info("2002 DTAM Execute received: flightPlanFolderName=%s (armed, waiting for 1002 play)", folder)
        except Exception:
            logger.exception("_on_dtam_execute failed")

    def _on_strategic_separation(self, result: Any) -> None:
        try:
            raw = getattr(result, "raw", None) or {}
            command_id = str(raw.get("commandId") or "")
            aircraft_id = str(raw.get("aircraftId") or "").strip()
            modification = str(raw.get("modificationType") or "")
            brief = f"{command_id} {modification} {aircraft_id}".strip()
            with self._lock:
                self._rx_3002_count += 1
                self._last_rx_3002 = brief or str(raw)
            if modification == "cancelPlan" and aircraft_id:
                removed = self.remove_plan(aircraft_id)
                logger.info("3002 cancelPlan received: aircraftId=%s removed=%s", aircraft_id, removed)
            else:
                logger.info("3002 Strategic Separation received: %s", brief)
        except Exception:
            logger.exception("_on_strategic_separation failed")

    def _on_tactical_separation(self, result: Any) -> None:
        try:
            raw = getattr(result, "raw", None) or {}
            command_id = str(raw.get("commandId") or "")
            aircraft_id = str(raw.get("aircraftId") or "").strip()
            actions = raw.get("actions") if isinstance(raw, dict) else None
            action_types = []
            if isinstance(actions, list):
                action_types = [str(a.get("type")) for a in actions if isinstance(a, dict) and a.get("type")]
            brief = f"{command_id} {aircraft_id} actions={','.join(action_types)}".strip()
            with self._lock:
                self._rx_3003_count += 1
                self._last_rx_3003 = brief or str(raw)
            logger.info("3003 Tactical Separation received: %s", brief)
        except Exception:
            logger.exception("_on_tactical_separation failed")

    def _on_operator_control_input(self, result: Any) -> None:
        try:
            raw = getattr(result, "raw", None) or {}
            if not isinstance(raw, dict):
                return
            manual = self._apply_operator_control_payload(raw, count_rx=True)
            logger.debug(
                "5001 Operator Control received: aircraftId=%s source=%s mode=%s manual=%s",
                raw.get("aircraftId") or raw.get("vehicleId"),
                raw.get("source"),
                raw.get("controlMode"),
                manual,
            )
        except Exception:
            logger.exception("_on_operator_control_input failed")


def _find_seq_for_phase(plan: FlightPlan, phase: str, cursor: int) -> int:
    """현재 phase 코드가 맞는 segment seq 를 찾는다. 없으면 cursor 유지."""
    if not phase:
        return cursor
    for seg in plan.en_route[cursor:] if cursor > 0 else plan.en_route:
        seg_phase = getattr(seg.phase, "value", str(seg.phase))
        if str(seg_phase) == str(phase):
            return int(seg.seq)
    for seg in plan.en_route:
        seg_phase = getattr(seg.phase, "value", str(seg.phase))
        if str(seg_phase) == str(phase):
            return int(seg.seq)
    return cursor


_ISO_RE = re.compile(
    r"^(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})T"
    r"(?P<H>\d{2}):(?P<M>\d{2}):(?P<S>\d{2})(?:\.(?P<ms>\d{1,6}))?Z?"
)


def _iso_to_seconds_of_day(iso_text: str) -> float:
    """``2026-04-16T09:30:15.250Z`` → 34215.25 (정각 대비 초).

    우리 sim_time_s 관습에 맞추기 위해 UTC 기준 시/분/초/밀리초 만 추출한다.
    datetime.fromisoformat 보다 ``Z`` 접미사를 관대하게 처리.
    """
    m = _ISO_RE.match(iso_text.strip())
    if not m:
        # datetime 으로 한 번 더 시도
        try:
            text = iso_text.strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(text)
            return float(
                dt.hour * 3600 + dt.minute * 60 + dt.second
                + dt.microsecond / 1_000_000.0
            )
        except Exception:
            raise ValueError(f"unrecognized ISO-8601 time: {iso_text!r}")
    H = int(m.group("H"))
    M = int(m.group("M"))
    S = int(m.group("S"))
    ms = m.group("ms") or ""
    frac = float("0." + ms) if ms else 0.0
    return float(H * 3600 + M * 60 + S) + frac


def _sim_time_to_iso(sim_time_s: float) -> str:
    """sim_time_s (초, HH:MM:SS 해석) → 오늘 UTC ISO 문자열.

    주의: sim_time_s 는 일 단위 "벽시계" 로 취급 (simpleDynamics 관습).
    """
    today = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    ts = today.timestamp() + max(0.0, float(sim_time_s))
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return iso_timestamp(dt)

