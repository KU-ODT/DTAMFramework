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
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..domain.dynamics.core.types import (
    DEFAULT_SIMULATION_HZ,
    DEFAULT_SIMULATION_TICK_S,
    FlightPlan,
    FlightTrajectoryPoint,
    LLA,
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
from .vfds_client import VfdsHttpResult, VfdsMissionClient
from .vfds_telemetry import VfdsTelemetryReceiver
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
DEFAULT_SIMULATION_START_S = 6 * 60 * 60 + 30 * 60  # 06:30:00
MISSION_CORNER_SMOOTHING_RADIUS_M = 400.0
MAX_TRAJECTORY_TIME_STEP_S = 0.5
COLLISION_ACTIVE_RESPONSE_MODES = {"hold", "emergency_stop", "abort"}
DEFAULT_DYNAMICS_MODEL = "simple"
HIGH_FIDELITY_DYNAMICS_MODEL = "highFidelity"
SIMPLE_PROVIDER = "simple"
KP2A_PROVIDER = "vfds-kp2a"
MOCK_KP2A_PROVIDER = "mock-vfds-kp2a"
KP2A_PROVIDER_ALIASES = {KP2A_PROVIDER, MOCK_KP2A_PROVIDER, "mock-kp2a"}
VFDS_TIME_FEED_PERIOD_S = 0.2
# VFDS/KP2A AircraftStatus yaw is treated as the same geographic/NED yaw
# convention as DTAM 4001.  Do not add the ODT visual-frame -90/+90 correction
# here; if the remote yaw is noisy or provider-specific, the bridge below
# prefers velocity/LLA motion track for the published heading.
KP2A_TELEMETRY_YAW_TO_GEO_DEG = 0.0


def _normalize_dynamics_model(value: Any, *, default: str = DEFAULT_DYNAMICS_MODEL) -> str:
    text = str(value or default or DEFAULT_DYNAMICS_MODEL).strip()
    key = text.replace("-", "").replace("_", "").lower()
    if key in {"highfidelity", "kp2a", "kp2ahighfidelity"}:
        return HIGH_FIDELITY_DYNAMICS_MODEL
    return DEFAULT_DYNAMICS_MODEL


def _default_provider_for_dynamics(dynamics_model: str) -> str:
    if _normalize_dynamics_model(dynamics_model) == HIGH_FIDELITY_DYNAMICS_MODEL:
        return KP2A_PROVIDER
    return SIMPLE_PROVIDER


def _normalize_provider_name(value: Any, *, dynamics_model: str = DEFAULT_DYNAMICS_MODEL) -> str:
    text = str(value or "").strip()
    if not text:
        return _default_provider_for_dynamics(dynamics_model)
    key = text.replace("_", "-").lower()
    if key in {"vfds", "vfds-kp2a", "vehicle", "vehicle-kp2a", "kp2a", "kp-2a", "kp2a-vfds"}:
        return KP2A_PROVIDER
    if key in {"mock", "mock-vfds-kp2a", "mock-kp2a", "kp2a-mock"}:
        return MOCK_KP2A_PROVIDER
    if key in {"simple", "mission", "simple-dynamics", "mission-profile"}:
        return SIMPLE_PROVIDER
    return key


def _normalize_collision_response_mode(event: Dict[str, Any]) -> str:
    """Return the VehicleModule response mode for a 4103 event.

    ``none`` means "record only"; ``clear`` explicitly releases an active
    collision response.  Active response modes are listed in
    ``COLLISION_ACTIVE_RESPONSE_MODES``.
    """
    if not isinstance(event, dict):
        return "none"

    has_collided = _truthy(event.get("hasCollided"), True)
    action = str(event.get("recommendedAction") or event.get("action") or "").strip().lower()
    action = action.replace("-", "_").replace(" ", "_")
    severity = str(event.get("severity") or "").strip().lower()

    if not has_collided or action in {"clear", "cleared", "release", "resume", "reset"}:
        return "clear"
    if action in {"none", "noop", "no_op", "monitor", "record", "log"}:
        return "none"
    if action in {"hold", "pause", "brake"}:
        return "hold"
    if action in {"stop", "emergency", "emergency_stop", "emergency_hold"}:
        return "emergency_stop"
    if action in {"abort", "terminate", "fatal", "emergency_abort", "emergency_land"}:
        return "abort"

    if severity == "fatal":
        return "abort"
    if severity == "critical":
        return "emergency_stop"
    if severity == "warning":
        return "hold"
    # 4103의 recommendedAction/severity는 문서상 선택 필드다. 실제 충돌이
    # 감지됐는데 두 필드가 비어 있으면 기록만 하고 지나가는 것보다 안전한
    # 기본 동작인 hold를 적용한다.
    return "hold"


def _collision_snapshot_from_event(
    event: Dict[str, Any],
    *,
    response_mode: str,
    active: bool,
) -> Dict[str, Any]:
    """Build the compact 4001/status collision snapshot from a 4103 payload."""
    if not isinstance(event, dict):
        event = {}
    event_id = str(event.get("eventId") or "").strip()
    timestamp = str(event.get("timestamp") or iso_timestamp(datetime.now(timezone.utc))).strip()
    return {
        "active": bool(active),
        "lastEventId": event_id,
        "eventId": event_id,
        "aircraftId": str(event.get("aircraftId") or event.get("vehicleId") or "").strip(),
        "airsimVehicleName": str(event.get("airsimVehicleName") or "").strip(),
        "objectName": str(event.get("objectName") or "").strip(),
        "objectId": event.get("objectId", -1),
        "severity": str(event.get("severity") or "").strip().lower() or "info",
        "recommendedAction": str(event.get("recommendedAction") or "").strip().lower() or "none",
        "responseMode": str(response_mode or "none"),
        "timestamp": timestamp,
        "impactSpeedMps": float(event.get("impactSpeedMps") or 0.0),
        "source": "4103",
    }


def _zero_motion_payload(
    payload: Dict[str, Any],
    *,
    collision: Dict[str, Any],
    response_mode: str,
) -> Dict[str, Any]:
    """Return a 4001 sub-payload frozen in place with motion-related fields zeroed."""
    frozen = deepcopy(payload) if isinstance(payload, dict) else {}
    frozen["collision"] = deepcopy(collision)

    gps = frozen.get("gps")
    if isinstance(gps, dict):
        gps["velocity_north"] = 0.0
        gps["velocity_east"] = 0.0
        gps["velocity_down"] = 0.0

    imu = frozen.get("imu")
    if isinstance(imu, dict):
        angular = imu.get("angular_velocity")
        if isinstance(angular, dict):
            angular["x"] = 0.0
            angular["y"] = 0.0
            angular["z"] = 0.0
        linear = imu.get("linear_acceleration")
        if isinstance(linear, dict):
            linear["x"] = 0.0
            linear["y"] = 0.0
            linear["z"] = 0.0

    for key in ("speed", "speed_mps", "groundspeed", "groundSpeedMps", "vertical_speed"):
        if key in frozen:
            frozen[key] = 0.0

    barometer = frozen.get("barometer")
    if isinstance(barometer, dict) and "vertical_speed" in barometer:
        barometer["vertical_speed"] = 0.0

    if str(response_mode or "").lower() in {"emergency_stop", "abort"}:
        propulsion = frozen.get("propulsion")
        if isinstance(propulsion, dict) and isinstance(propulsion.get("motor_rpm"), list):
            propulsion["motor_rpm"] = [0.0 for _ in propulsion["motor_rpm"]]
        actuator = frozen.get("actuator")
        if isinstance(actuator, dict):
            for key in ("aileron", "rudder_left", "rudder_right"):
                if key in actuator:
                    actuator[key] = 0.0

    return frozen


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
        self.sim_time_of_day = raw.get("simTimeOfDay") or raw.get("sim_time_of_day") or ""
        self.sim_seconds_of_day = raw.get("simSecondsOfDay") or raw.get("sim_seconds_of_day")
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
        return self._owner._send_4001_sync(message)

    def close(self) -> None:
        pass


class _Latest4001Publisher:
    """Send only the latest 4001 frame from a background worker.

    Telemetry frames are time-sensitive.  If WebSocket send stalls, sending old
    queued frames later is worse than skipping them, so this worker keeps only
    one pending frame and overwrites it with newer data.
    """

    def __init__(
        self,
        send_fn: Callable[[Dict[str, Any]], bool],
        *,
        name: str = "dtam-4001-publisher",
    ) -> None:
        self._send_fn = send_fn
        self._name = str(name)
        self._condition = threading.Condition()
        self._thread: Optional[threading.Thread] = None
        self._stop_requested = False
        self._latest: Optional[Dict[str, Any]] = None
        self._submitted_count = 0
        self._sent_count = 0
        self._dropped_count = 0
        self._error_count = 0
        self._last_error = ""
        self._last_send_ms = 0.0

    def start(self) -> None:
        with self._condition:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_requested = False
            self._thread = threading.Thread(
                target=self._loop,
                name=self._name,
                daemon=True,
            )
            self._thread.start()

    def submit(self, message: Dict[str, Any]) -> bool:
        self.start()
        with self._condition:
            if self._stop_requested:
                return False
            if self._latest is not None:
                self._dropped_count += 1
            self._latest = message
            self._submitted_count += 1
            self._condition.notify()
            return True

    def stop(self, timeout: float = 2.0) -> None:
        with self._condition:
            self._stop_requested = True
            self._latest = None
            self._condition.notify_all()
            thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(0.0, float(timeout)))
        with self._condition:
            if self._thread is thread:
                self._thread = None

    def stats(self) -> Dict[str, Any]:
        with self._condition:
            thread = self._thread
            return {
                "active": bool(thread is not None and thread.is_alive()),
                "pending": self._latest is not None,
                "submitted": int(self._submitted_count),
                "sent": int(self._sent_count),
                "dropped": int(self._dropped_count),
                "errors": int(self._error_count),
                "lastSendMs": float(self._last_send_ms),
                "lastError": self._last_error,
            }

    def _loop(self) -> None:
        while True:
            with self._condition:
                while not self._stop_requested and self._latest is None:
                    self._condition.wait()
                if self._stop_requested:
                    return
                message = self._latest
                self._latest = None

            if message is None:
                continue

            started = time.monotonic()
            ok = False
            error_text = ""
            try:
                ok = bool(self._send_fn(message))
                if not ok:
                    error_text = "send returned False"
            except Exception as exc:
                error_text = f"{type(exc).__name__}: {exc}"
                ok = False
            elapsed_ms = (time.monotonic() - started) * 1000.0

            with self._condition:
                self._last_send_ms = elapsed_ms
                if ok:
                    self._sent_count += 1
                    self._last_error = ""
                else:
                    self._error_count += 1
                    if error_text and error_text != self._last_error:
                        logger.warning("4001 async publish failed: %s", error_text)
                    self._last_error = error_text


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
    publisher_queue: Dict[str, Any] = field(default_factory=dict)
    rx_3001_count: int = 0      # 수신한 3001 메시지 누적
    rx_0003_count: int = 0      # 수신한 0003 메시지 누적
    last_rx_3001: str = ""       # 가장 최근 3001 간략 정보
    last_rx_0003: str = ""       # 가장 최근 0003 simTime
    rx_2002_count: int = 0
    rx_3002_count: int = 0
    rx_3003_count: int = 0
    rx_4103_count: int = 0
    rx_5001_count: int = 0
    last_rx_2002: str = ""
    last_rx_3002: str = ""
    last_rx_3003: str = ""
    last_rx_4103: str = ""
    last_rx_5001: str = ""
    last_heartbeat_error: str = ""
    last_collision_event: Dict[str, Any] = field(default_factory=dict)
    collisions_by_vehicle: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    collision_responses_by_vehicle: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    manual: Dict[str, Any] = field(default_factory=dict)
    vehicle_control_modes: Dict[str, str] = field(default_factory=dict)
    vehicle_dynamics: Dict[str, str] = field(default_factory=dict)
    vehicle_providers: Dict[str, str] = field(default_factory=dict)
    provider_statuses: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    manual_by_vehicle: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    manual_source_targets: Dict[str, str] = field(default_factory=dict)


def _parse_hhmmss_to_s(text: str) -> float:
    parts = str(text).split(":")
    if len(parts) != 3:
        raise ValueError(f"expected HH:MM:SS, got {text!r}")
    h, m, s = parts
    return float(int(h) * 3600 + int(m) * 60 + float(s))


def _coerce_sim_seconds_of_day(value: Any) -> Optional[float]:
    """Return a numeric seconds-of-day value when ``value`` is present."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(seconds):
        return None
    return max(0.0, seconds)


def _parse_sim_time_text_to_s(value: Any) -> Optional[float]:
    """Parse HH:MM:SS(.sss), numeric seconds, or ISO time into seconds of day."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return _coerce_sim_seconds_of_day(value)
    text = str(value).strip()
    if not text:
        return None
    numeric = _coerce_sim_seconds_of_day(text)
    if numeric is not None:
        return numeric
    try:
        if "T" in text or "-" in text:
            return _iso_to_seconds_of_day(text)
        return _parse_hhmmss_to_s(text)
    except Exception:
        return None


def _extract_sim_time_from_payload(
    raw: Dict[str, Any],
    *,
    seconds_keys: Tuple[str, ...],
    time_of_day_keys: Tuple[str, ...],
    iso_keys: Tuple[str, ...],
) -> Tuple[Optional[float], str, Any]:
    """Extract simulation time with explicit-field priority.

    Priority is numeric seconds-of-day, then HH:MM:SS-style time-of-day,
    then legacy ISO ``simTime``.  The third return value is the raw field
    value used, for diagnostics/status.
    """
    if not isinstance(raw, dict):
        return None, "", None

    for key in seconds_keys:
        if key in raw:
            seconds = _coerce_sim_seconds_of_day(raw.get(key))
            if seconds is not None:
                return seconds, key, raw.get(key)

    for key in time_of_day_keys:
        if key in raw:
            seconds = _parse_sim_time_text_to_s(raw.get(key))
            if seconds is not None:
                return seconds, key, raw.get(key)

    for key in iso_keys:
        if key in raw:
            seconds = _parse_sim_time_text_to_s(raw.get(key))
            if seconds is not None:
                return seconds, key, raw.get(key)

    return None, "", None


def _extract_common_time_seconds(raw: Dict[str, Any]) -> Tuple[Optional[float], str, Any]:
    return _extract_sim_time_from_payload(
        raw,
        seconds_keys=("simSecondsOfDay", "sim_seconds_of_day"),
        time_of_day_keys=("simTimeOfDay", "sim_time_of_day"),
        iso_keys=("simTime", "sim_time"),
    )


def _extract_simulation_setup_time_seconds(raw: Dict[str, Any]) -> Tuple[Optional[float], str, Any]:
    return _extract_sim_time_from_payload(
        raw,
        seconds_keys=("simSecondsOfDay", "sim_seconds_of_day"),
        time_of_day_keys=(
            "simulationTime",
            "simulation_time",
            "simTimeOfDay",
            "sim_time_of_day",
            "simulationStartTime",
            "simulation_start_time",
        ),
        iso_keys=("simTime", "sim_time"),
    )


def _s_to_hhmmss(total_s: float) -> str:
    total = max(0.0, float(total_s))
    h = int(total // 3600) % 24
    m = int((total % 3600) // 60)
    s = int(total) % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(result):
        return float(default)
    return result


def _wrap_heading_deg(value: Any, default: float = 0.0) -> float:
    return float(_safe_float(value, default) % 360.0)


def _kp2a_yaw_to_geo_heading_deg(yaw_deg: Any) -> float:
    # "???? 90?" ??: VFDS/PX4 yaw -> DTAM geographic heading.
    return _wrap_heading_deg(_safe_float(yaw_deg, 0.0) + KP2A_TELEMETRY_YAW_TO_GEO_DEG)


def _first_present_numeric(*values: Any) -> Optional[float]:
    for value in values:
        if value is None:
            continue
        try:
            result = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(result):
            return float(result)
    return None


def _extract_vfds_speed_mps(telemetry: Dict[str, Any], position: Dict[str, Any]) -> Optional[float]:
    """Best-effort speed extraction from VFDS/PX4 telemetry payloads."""
    direct = _first_present_numeric(
        telemetry.get("speedMps"),
        telemetry.get("speed_mps"),
        telemetry.get("groundSpeedMps"),
        telemetry.get("ground_speed_mps"),
        telemetry.get("groundspeed_mps"),
        telemetry.get("groundspeed"),
        telemetry.get("speed"),
        telemetry.get("airspeed_mps"),
        telemetry.get("airspeed"),
        position.get("speedMps"),
        position.get("speed_mps"),
    )
    if direct is not None:
        return max(0.0, min(250.0, float(direct)))

    velocity = telemetry.get("velocityNed") or telemetry.get("velocity_ned") or telemetry.get("velocity")
    if isinstance(velocity, dict):
        vn = _first_present_numeric(velocity.get("north"), velocity.get("n"), velocity.get("vn"), velocity.get("x"))
        ve = _first_present_numeric(velocity.get("east"), velocity.get("e"), velocity.get("ve"), velocity.get("y"))
        vd = _first_present_numeric(velocity.get("down"), velocity.get("d"), velocity.get("vd"), velocity.get("z"))
        if vn is not None or ve is not None or vd is not None:
            return max(0.0, min(250.0, math.sqrt((vn or 0.0) ** 2 + (ve or 0.0) ** 2 + (vd or 0.0) ** 2)))
    return None


def _extract_vfds_track_heading_deg(telemetry: Dict[str, Any], position: Dict[str, Any]) -> Optional[float]:
    """Best-effort geographic track heading from VFDS NED velocity."""

    velocity = telemetry.get("velocityNed") or telemetry.get("velocity_ned") or telemetry.get("velocity")
    if not isinstance(velocity, dict):
        velocity = position.get("velocityNed") or position.get("velocity_ned") or position.get("velocity")
    if not isinstance(velocity, dict):
        return None
    vn = _first_present_numeric(velocity.get("north"), velocity.get("n"), velocity.get("vn"), velocity.get("x"))
    ve = _first_present_numeric(velocity.get("east"), velocity.get("e"), velocity.get("ve"), velocity.get("y"))
    if vn is None or ve is None:
        return None
    if math.hypot(float(vn), float(ve)) <= 0.05:
        return None
    return float(math.degrees(math.atan2(float(ve), float(vn))) % 360.0)


def _telemetry_ts_to_epoch(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return float(dt.timestamp())
    except Exception:
        return None


def _lla_to_vfds_dict(lla: LLA) -> Dict[str, float]:
    return {"lat": float(lla.lat), "lon": float(lla.lon), "alt": float(lla.alt)}


def _copy_lla_like(value: Any) -> Dict[str, float]:
    if not isinstance(value, dict):
        raise ValueError("LLA must be a dict")
    return {
        "lat": float(value["lat"]),
        "lon": float(value["lon"]),
        "alt": float(value["alt"]),
    }


def _flight_plan_to_vfds_payload(plan: FlightPlan) -> Dict[str, Any]:
    en_route: List[Dict[str, Any]] = []
    for segment in plan.en_route:
        item: Dict[str, Any] = {
            "seq": int(segment.seq),
            "phase": str(segment.phase.value if hasattr(segment.phase, "value") else segment.phase),
            "startLLA": _lla_to_vfds_dict(segment.start_lla),
            "endLLA": _lla_to_vfds_dict(segment.end_lla),
            "targetSpeed": float(segment.target_speed),
        }
        if segment.turn_direction:
            item["turnDirection"] = str(segment.turn_direction)
        if segment.center_lla is not None:
            item["centerLLA"] = _lla_to_vfds_dict(segment.center_lla)
        en_route.append(item)
    return {
        "flightPlanNumber": int(plan.flight_plan_number),
        "aircraftId": str(plan.aircraft_id),
        "departure": {
            "vertiport": str(plan.departure.vertiport),
            "std": str(plan.departure.std),
            "depGateNumber": str(plan.departure.dep_gate_number),
            "eobt": str(plan.departure.eobt),
            "depFatoNumber": str(plan.departure.dep_fato_number),
            "etot": str(plan.departure.etot),
        },
        "enRoute": en_route,
        "arrival": {
            "vertiport": str(plan.arrival.vertiport),
            "sta": str(plan.arrival.sta),
            "arrGateNumber": str(plan.arrival.arr_gate_number),
            "eibt": str(plan.arrival.eibt),
            "arrFatoNumber": str(plan.arrival.arr_fato_number),
            "eldt": str(plan.arrival.eldt),
        },
    }


def _build_vfds_mission_payload(plan: FlightPlan, raw_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return the VFDS Mission ICD payload for one VehicleSession.

    Prefer the received DTAM 3001 JSON so aircraft-specific STD/ETOT values and
    route shape remain identical to Operation/MissionModule output.  Only fields
    accepted by VFDS MissionPlan are whitelisted to avoid leaking DTAM-only
    metadata such as planVersion/planStatus.
    """

    if not isinstance(raw_payload, dict):
        return _flight_plan_to_vfds_payload(plan)

    try:
        departure_raw = raw_payload.get("departure") if isinstance(raw_payload.get("departure"), dict) else {}
        arrival_raw = raw_payload.get("arrival") if isinstance(raw_payload.get("arrival"), dict) else {}
        en_route_raw = raw_payload.get("enRoute") if isinstance(raw_payload.get("enRoute"), list) else []
        en_route: List[Dict[str, Any]] = []
        for idx, segment in enumerate(en_route_raw):
            if not isinstance(segment, dict):
                continue
            phase = str(segment.get("phase") or "")
            item: Dict[str, Any] = {
                "seq": int(segment.get("seq", idx + 1)),
                "phase": phase,
                "startLLA": _copy_lla_like(segment.get("startLLA")),
                "endLLA": _copy_lla_like(segment.get("endLLA")),
                "targetSpeed": float(segment.get("targetSpeed")),
            }
            if phase in {"D", "H"}:
                if segment.get("turnDirection") is not None:
                    item["turnDirection"] = str(segment.get("turnDirection"))
                if segment.get("centerLLA") is not None:
                    item["centerLLA"] = _copy_lla_like(segment.get("centerLLA"))
            en_route.append(item)
        if not en_route:
            raise ValueError("empty enRoute")
        return {
            "flightPlanNumber": int(raw_payload.get("flightPlanNumber", plan.flight_plan_number)),
            "aircraftId": str(raw_payload.get("aircraftId") or plan.aircraft_id),
            "departure": {
                "vertiport": str(departure_raw.get("vertiport", plan.departure.vertiport)),
                "std": str(departure_raw.get("std", plan.departure.std)),
                "depGateNumber": str(departure_raw.get("depGateNumber", plan.departure.dep_gate_number)),
                "eobt": str(departure_raw.get("eobt", plan.departure.eobt)),
                "depFatoNumber": str(departure_raw.get("depFatoNumber", plan.departure.dep_fato_number)),
                "etot": str(departure_raw.get("etot", plan.departure.etot)),
            },
            "enRoute": en_route,
            "arrival": {
                "vertiport": str(arrival_raw.get("vertiport", plan.arrival.vertiport)),
                "sta": str(arrival_raw.get("sta", plan.arrival.sta)),
                "arrGateNumber": str(arrival_raw.get("arrGateNumber", plan.arrival.arr_gate_number)),
                "eibt": str(arrival_raw.get("eibt", plan.arrival.eibt)),
                "arrFatoNumber": str(arrival_raw.get("arrFatoNumber", plan.arrival.arr_fato_number)),
                "eldt": str(arrival_raw.get("eldt", plan.arrival.eldt)),
            },
        }
    except Exception as exc:
        logger.warning(
            "falling back to FlightPlan serializer for VFDS payload: aircraft=%s fpn=%s error=%s",
            plan.aircraft_id,
            plan.flight_plan_number,
            exc,
        )
        return _flight_plan_to_vfds_payload(plan)


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


def _lla_horizontal_components_m(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> Tuple[float, float]:
    """Return north/east metres from A to B using a local flat-earth frame."""
    mean_lat_rad = math.radians((float(lat_a) + float(lat_b)) * 0.5)
    meters_per_lat = 111_132.92
    meters_per_lon = 111_412.84 * math.cos(mean_lat_rad)
    north_m = (float(lat_b) - float(lat_a)) * meters_per_lat
    east_m = (float(lon_b) - float(lon_a)) * meters_per_lon
    return north_m, east_m


def _bearing_distance_to_lla(lat: float, lon: float, alt_m: float, target: LLA) -> Tuple[float, float, float]:
    north_m, east_m = _lla_horizontal_components_m(lat, lon, target.lat, target.lon)
    bearing_deg = math.degrees(math.atan2(east_m, north_m)) % 360.0
    horizontal_distance_m = math.hypot(north_m, east_m)
    vertical_delta_m = float(target.alt) - float(alt_m)
    return bearing_deg, horizontal_distance_m, vertical_delta_m


def _same_lla(a: LLA, b: LLA) -> bool:
    return (
        abs(float(a.lat) - float(b.lat)) < 1.0e-8
        and abs(float(a.lon) - float(b.lon)) < 1.0e-8
        and abs(float(a.alt) - float(b.alt)) < 0.05
    )


def _flight_plan_route_points(plan: FlightPlan) -> List[Tuple[int, LLA]]:
    """Return de-duplicated start/end LLA points tagged by segment seq."""
    points: List[Tuple[int, LLA]] = []
    for seg in plan.en_route:
        seq = int(getattr(seg, "seq", len(points) + 1) or len(points) + 1)
        for lla in (seg.start_lla, seg.end_lla):
            if not points or not _same_lla(points[-1][1], lla):
                points.append((seq, lla))
    return points


def _select_navigation_target_by_seq(
    plan: FlightPlan,
    *,
    seq: Optional[int],
    lat: float,
    lon: float,
    alt_m: float,
) -> Tuple[Optional[int], Optional[LLA]]:
    if seq is None or int(seq) < 1:
        return None, None
    segments = list(plan.en_route or [])
    for index, seg in enumerate(segments):
        if int(getattr(seg, "seq", -1) or -1) != int(seq):
            continue
        target_seq = int(seg.seq)
        target_lla = seg.end_lla
        _bearing, distance_m, _vertical = _bearing_distance_to_lla(lat, lon, alt_m, target_lla)
        if distance_m < 25.0 and index + 1 < len(segments):
            next_seg = segments[index + 1]
            return int(next_seg.seq), next_seg.end_lla
        return target_seq, target_lla
    return None, None


def _select_navigation_target_from_route(plan: FlightPlan, *, lat: float, lon: float, alt_m: float) -> Tuple[Optional[int], Optional[LLA]]:
    points = _flight_plan_route_points(plan)
    if len(points) < 2:
        return None, None

    # Find the closest route segment to the current position, then guide toward
    # that segment's end.  This keeps manual Keyboard/Joystick vehicles tied to
    # the planned route without forcing autopilot motion.
    best_index = 0
    best_error_m = float("inf")
    for index in range(len(points) - 1):
        a = points[index][1]
        b = points[index + 1][1]
        ab_n, ab_e = _lla_horizontal_components_m(a.lat, a.lon, b.lat, b.lon)
        ac_n, ac_e = _lla_horizontal_components_m(a.lat, a.lon, lat, lon)
        ab_len2 = ab_n * ab_n + ab_e * ab_e
        if ab_len2 <= 1.0e-6:
            t = 0.0
            proj_n = 0.0
            proj_e = 0.0
        else:
            t = max(0.0, min(1.0, (ac_n * ab_n + ac_e * ab_e) / ab_len2))
            proj_n = ab_n * t
            proj_e = ab_e * t
        err_n = ac_n - proj_n
        err_e = ac_e - proj_e
        error_m = math.hypot(err_n, err_e)
        if error_m < best_error_m:
            best_error_m = error_m
            best_index = index

    target_index = min(best_index + 1, len(points) - 1)
    target_seq, target_lla = points[target_index]
    _bearing, distance_m, _vertical = _bearing_distance_to_lla(lat, lon, alt_m, target_lla)
    if distance_m < 25.0 and target_index + 1 < len(points):
        target_seq, target_lla = points[target_index + 1]
    return int(target_seq), target_lla


def _build_navigation_payload(
    plan: Optional[FlightPlan],
    *,
    lat: float,
    lon: float,
    alt_m: float,
    current_waypoint_id: str = "",
    seq: Optional[int] = None,
    source: str = "3001",
) -> Optional[Dict[str, Any]]:
    """Build optional 4001.navigation guidance for the Unreal I-key HUD."""
    if plan is None or not getattr(plan, "en_route", None):
        return None

    target_seq, target_lla = _select_navigation_target_by_seq(
        plan,
        seq=seq,
        lat=lat,
        lon=lon,
        alt_m=alt_m,
    )
    if target_lla is None:
        target_seq, target_lla = _select_navigation_target_from_route(plan, lat=lat, lon=lon, alt_m=alt_m)
    if target_lla is None or target_seq is None:
        return None

    bearing_deg, distance_m, vertical_delta_m = _bearing_distance_to_lla(lat, lon, alt_m, target_lla)
    next_waypoint_id = f"{int(plan.flight_plan_number)}-{int(target_seq)}"
    return {
        "flightPlanNumber": int(plan.flight_plan_number),
        "currentWaypointId": str(current_waypoint_id or ""),
        "nextWaypointId": next_waypoint_id,
        "targetLLA": {
            "lat": round(float(target_lla.lat), 8),
            "lon": round(float(target_lla.lon), 8),
            "alt": round(float(target_lla.alt), 3),
        },
        "bearingToTargetDeg": round(float(bearing_deg), 2),
        "distanceToTargetM": round(float(distance_m), 1),
        "verticalDeltaM": round(float(vertical_delta_m), 1),
        "source": str(source or "3001"),
    }


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
        # Operation?? ???? ??? ????(STD)? ???/?? ?????
        # ????. MissionModule? ETOT? taxi/hold ???? ??? ?? ???
        # Vehicle autopilot? STD? ???? ?? ??? ????.
        std_s = _parse_sim_time_text_to_s(getattr(plan.departure, "std", ""))
        self.start_gate_s: float = float(std_s) if std_s is not None else float(self.etot_s)

    def reset(self) -> None:
        self.state = VehicleState.WAITING
        self.last_error = ""
        self._reset_runtime_state()

    def _reset_runtime_state(self, *, clear_payload: bool = True) -> None:
        """Reset only runtime progress derived from the simulation clock."""
        self.last_point = None
        if clear_payload:
            self.last_payload = None
        self.elapsed_s = 0.0
        self.trajectory_index = 0
        self.last_emit_target_time_s = None
        self.pose_frame = None
        self.start_sim_time_s = None
        self._final_emitted = False
        for attr in (
            "_prev_alt_m",
            "_prev_point_time_s",
            "_seq_cursor",
            "_last_battery_pct",
            "_vfds_prev_motion",
            "_vfds_prev_battery_time",
            "_vfds_last_track_heading_deg",
        ):
            if hasattr(self, attr):
                delattr(self, attr)

    def waiting_hold_point(self) -> Optional[FlightTrajectoryPoint]:
        """Return a zero-speed copy of the first trajectory point for pre-start hold."""
        self._ensure_trajectory()
        if not self.trajectory:
            return None
        first = self.trajectory[0]
        self.elapsed_s = 0.0
        self.trajectory_index = 0
        return replace(
            first,
            time_s=float(self.trajectory_time_offset_s),
            speed_mps=0.0,
            mode="WAITING",
        )

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
        """sim_time_s ? ?? ???(STD ??, fallback ETOT) ???? ????."""
        if self.state == VehicleState.ERROR:
            return None

        self._ensure_trajectory()
        if not self.trajectory:
            return None

        current_sim_time_s = float(sim_time_s)
        start_gate_s = float(getattr(self, "start_gate_s", self.etot_s))
        if current_sim_time_s + 1e-6 < start_gate_s:
            # ????? STD(??? ????) ??? Autopilot ??? ???? ???.
            # Play? ?? ??? 0003/1002 ??? ?? ???? ??? ???
            # WAITING ??? ???? ?? ???? staggered departure? ????.
            if (
                self.state != VehicleState.WAITING
                or self.start_sim_time_s is not None
                or self.last_emit_target_time_s is not None
                or self.trajectory_index != 0
                or self._final_emitted
            ):
                self.state = VehicleState.WAITING
                self._reset_runtime_state()
            return self.waiting_hold_point()

        last_index = len(self.trajectory) - 1
        last_time_s = float(self.trajectory[last_index].time_s)
        total_s = max(0.0, last_time_s - float(self.trajectory_time_offset_s))
        if self.state == VehicleState.COMPLETED:
            end_sim_time_s = (
                float(self.start_sim_time_s) + total_s
                if self.start_sim_time_s is not None
                else float(getattr(self, "start_gate_s", self.etot_s)) + total_s
            )
            if current_sim_time_s >= end_sim_time_s - 1e-6:
                return None
            # Simulation time was rewound after completion.  Rewind this
            # vehicle session instead of keeping it terminal until global reset.
            self.state = VehicleState.WAITING
            self._reset_runtime_state()

        if self.state == VehicleState.WAITING:
            self.state = VehicleState.ACTIVE

        if self.start_sim_time_s is None:
            self.start_sim_time_s = max(current_sim_time_s, float(getattr(self, "start_gate_s", self.etot_s)))
        target_elapsed_s = max(0.0, current_sim_time_s - float(self.start_sim_time_s))
        target_time_s = target_elapsed_s + float(self.trajectory_time_offset_s)

        if (
            self.last_emit_target_time_s is not None
            and target_time_s + 1e-6 < float(self.last_emit_target_time_s)
        ):
            # Rewind within the active trajectory.  Clear smoothing anchors so
            # the new frame is generated at the requested time, not constrained
            # by the previous forward-only step limiter.
            self.last_point = None
            self.last_emit_target_time_s = None
            self._final_emitted = False

        if self.last_emit_target_time_s is not None:
            max_step_s = max(PUBLISH_PERIOD_S, MAX_TRAJECTORY_TIME_STEP_S)
            allowed_target_time_s = float(self.last_emit_target_time_s) + max_step_s
            if target_time_s > allowed_target_time_s:
                target_time_s = allowed_target_time_s
                target_elapsed_s = max(0.0, target_time_s - float(self.trajectory_time_offset_s))
                self.start_sim_time_s = current_sim_time_s - target_elapsed_s

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


class _LatestVfdsTimePublisher:
    """Last-value-only worker for VFDS `/api/v1/time`.

    It prevents HTTP latency from becoming a 30 Hz simulation-loop stutter.  If
    multiple time updates arrive while one request is in flight, only the latest
    HH:MM:SS value is sent next.
    """

    def __init__(self, client: VfdsMissionClient) -> None:
        self.client = client
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._pending: Optional[Tuple[str, str]] = None
        self._stopped = False
        self._thread: Optional[threading.Thread] = None
        self.last_result: Optional[Dict[str, Any]] = None
        self.last_payload: Dict[str, str] = {}
        self.submitted_count = 0
        self.dropped_count = 0

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stopped = False
            self._thread = threading.Thread(target=self._loop, name="dtam-vfds-time", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._condition:
            self._stopped = True
            self._condition.notify_all()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=1.0)
        self._thread = None

    def submit(self, hhmmss: str, *, source: str) -> None:
        with self._condition:
            if self._pending is not None:
                self.dropped_count += 1
            self._pending = (str(hhmmss), str(source or "VehicleModule"))
            self._condition.notify()

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "submitted_count": int(self.submitted_count),
                "dropped_count": int(self.dropped_count),
                "pending": self._pending[0] if self._pending else None,
                "last_payload": dict(self.last_payload),
                "last_result": dict(self.last_result or {}),
            }

    def _loop(self) -> None:
        while True:
            with self._condition:
                while self._pending is None and not self._stopped:
                    self._condition.wait(timeout=0.5)
                if self._stopped:
                    return
                hhmmss, source = self._pending
                self._pending = None
            result = self.client.post_time_hhmmss(hhmmss, source=source)
            with self._lock:
                self.submitted_count += 1
                self.last_payload = {"time": hhmmss, "source": source}
                self.last_result = result.to_dict()


class _MockKp2AProvider:
    """VFDS/KP2A bridge with live telemetry priority and deterministic fallback.

    Mission submit/delete/time feed are sent to the external VFDS dispatch
    server.  If fresh KP2A telemetry is available, it is converted into DTAM
    4001; otherwise the validated local trajectory remains the safe fallback.
    """

    def __init__(
        self,
        name: str = KP2A_PROVIDER,
        *,
        client: Optional[VfdsMissionClient] = None,
        async_time_feed: bool = True,
        time_feed_period_s: float = VFDS_TIME_FEED_PERIOD_S,
        telemetry_receiver: Optional[VfdsTelemetryReceiver] = None,
    ) -> None:
        self.name = str(name or KP2A_PROVIDER)
        self.client = client or VfdsMissionClient()
        self.async_time_feed = bool(async_time_feed)
        self.time_feed_period_s = max(0.05, float(time_feed_period_s))
        self.frames: Dict[str, int] = {}
        self.last_sim_time_s: Dict[str, float] = {}
        self.last_error: Dict[str, str] = {}
        self.mission_payloads: Dict[str, Dict[str, Any]] = {}
        self.submitted: Dict[str, int] = {}
        self.submit_results: Dict[str, Dict[str, Any]] = {}
        self.delete_results: Dict[str, Dict[str, Any]] = {}
        self.last_health: Dict[str, Any] = {}
        self.last_time_hms: str = ""
        self.last_time_source: str = ""
        self.last_time_result: Dict[str, Any] = {}
        self.time_feed_count = 0
        self.time_feed_enabled = False
        self.telemetry = telemetry_receiver or VfdsTelemetryReceiver(self.client)
        self.telemetry_used: Dict[str, int] = {}
        self.telemetry_seen: Dict[str, bool] = {}
        self.telemetry_stale_holds: Dict[str, int] = {}
        self._last_time_feed_wall_s = 0.0
        self._time_worker: Optional[_LatestVfdsTimePublisher] = (
            _LatestVfdsTimePublisher(self.client) if self.async_time_feed else None
        )
        if self._time_worker is not None:
            self._time_worker.start()

    def close(self) -> None:
        if self._time_worker is not None:
            self._time_worker.stop()
        self.telemetry.stop()

    def reset(self, vehicle_id: str = "") -> None:
        """Clear local telemetry/runtime counters, preserving submitted missions."""
        vehicle_key = str(vehicle_id or "").strip()
        if not vehicle_key or vehicle_key.lower() in {"all", "*"}:
            self.frames.clear()
            self.last_sim_time_s.clear()
            self.last_error.clear()
            self.time_feed_enabled = False
            self._last_time_feed_wall_s = 0.0
            self.telemetry.mark_reset()
            self.telemetry_used.clear()
            self.telemetry_seen.clear()
            self.telemetry_stale_holds.clear()
            return
        self.frames.pop(vehicle_key, None)
        self.last_sim_time_s.pop(vehicle_key, None)
        self.last_error.pop(vehicle_key, None)
        self.telemetry.mark_reset(vehicle_key)
        self.telemetry_used.pop(vehicle_key, None)
        self.telemetry_seen.pop(vehicle_key, None)
        self.telemetry_stale_holds.pop(vehicle_key, None)

    def clear_all(self) -> None:
        self.reset("")
        self.mission_payloads.clear()
        self.submitted.clear()
        self.submit_results.clear()
        self.delete_results.clear()
        self.last_health.clear()
        self.last_time_hms = ""
        self.last_time_source = ""
        self.last_time_result = {}
        self.time_feed_count = 0
        self.telemetry.clear()
        self.telemetry_used.clear()
        self.telemetry_seen.clear()
        self.telemetry_stale_holds.clear()

    def register_session_payload(self, session: VehicleSession, payload: Dict[str, Any]) -> None:
        self.mission_payloads[session.aircraft_id] = deepcopy(payload)

    def ensure_ready(self, *, timeout_s: float = 20.0) -> Dict[str, Any]:
        """Make sure the VFDS/KP2A runtime is reachable before mission submit."""
        self.telemetry.start()
        ensure_fn = getattr(self.client, "ensure_ready", None)
        if callable(ensure_fn):
            runtime = ensure_fn(timeout_s=timeout_s)
        else:
            health = self.client.health()
            runtime = {
                "ok": bool(health.ok),
                "started": False,
                "health": health.to_dict(),
            }
        if not isinstance(runtime, dict):
            runtime = {"ok": False, "error": f"invalid VFDS runtime response: {runtime!r}"}
        health_obj = runtime.get("health")
        self.last_health = dict(health_obj) if isinstance(health_obj, dict) else dict(runtime)
        return dict(runtime)

    def submit_session(self, session: VehicleSession, *, reason: str = "") -> VfdsHttpResult:
        vehicle_key = session.aircraft_id
        payload = deepcopy(
            self.mission_payloads.get(vehicle_key)
            or getattr(session, "vfds_mission_payload", None)
            or _flight_plan_to_vfds_payload(session.plan)
        )
        self.mission_payloads[vehicle_key] = deepcopy(payload)
        runtime = self.ensure_ready(timeout_s=20.0)
        result = self.client.submit_mission(payload)
        result_dict = result.to_dict()
        result_dict["reason"] = str(reason or "")
        result_dict["flightPlanNumber"] = int(session.flight_plan_number)
        result_dict["runtime"] = deepcopy(runtime)
        self.submit_results[vehicle_key] = result_dict
        if result.ok:
            self.submitted[vehicle_key] = int(session.flight_plan_number)
            self.last_error.pop(vehicle_key, None)
        else:
            self.last_error[vehicle_key] = f"VFDS submit failed: {result.error or result.status_code}"
        return result

    def delete_session(
        self,
        session_or_vehicle_id: VehicleSession | str,
        *,
        flight_plan_number: Optional[int] = None,
        reason: str = "",
    ) -> Optional[VfdsHttpResult]:
        if isinstance(session_or_vehicle_id, VehicleSession):
            vehicle_key = session_or_vehicle_id.aircraft_id
            fpn = int(flight_plan_number or session_or_vehicle_id.flight_plan_number)
        else:
            vehicle_key = str(session_or_vehicle_id or "").strip()
            fpn = int(flight_plan_number or self.submitted.get(vehicle_key, 0) or 0)
        if not fpn:
            return None
        result = self.client.delete_mission(fpn)
        result_dict = result.to_dict()
        result_dict["reason"] = str(reason or "")
        result_dict["flightPlanNumber"] = int(fpn)
        if vehicle_key:
            self.delete_results[vehicle_key] = result_dict
            self.submitted.pop(vehicle_key, None)
            self.mission_payloads.pop(vehicle_key, None)
            if result.ok or int(result.status_code or 0) == 404:
                self.last_error.pop(vehicle_key, None)
                self.telemetry.mark_reset(vehicle_key)
            else:
                self.last_error[vehicle_key] = f"VFDS delete failed: {result.error or result.status_code}"
        return result

    def feed_time(self, sim_time_s: float, *, force: bool = False, source: str = "VehicleModule") -> Optional[VfdsHttpResult]:
        self.telemetry.start()
        now = time.monotonic()
        if not force and (now - self._last_time_feed_wall_s) < self.time_feed_period_s:
            return None
        self._last_time_feed_wall_s = now
        hhmmss = _s_to_hhmmss(sim_time_s)
        self.last_time_hms = hhmmss
        self.last_time_source = str(source or "VehicleModule")
        self.time_feed_enabled = True
        if self._time_worker is not None:
            self._time_worker.submit(hhmmss, source=self.last_time_source)
            self.time_feed_count += 1
            self.last_time_result = {
                "ok": True,
                "queued": True,
                "time": hhmmss,
                "source": self.last_time_source,
            }
            return None
        result = self.client.post_time_hhmmss(hhmmss, source=self.last_time_source)
        self.time_feed_count += 1
        self.last_time_result = result.to_dict()
        return result

    def pause_time_feed(self) -> None:
        self.time_feed_enabled = False

    def build_payload(
        self,
        service: "IntegratedAirMobilityService",
        session: VehicleSession,
        sim_time_s: float,
        *,
        previous_payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            telemetry = self.telemetry.latest(session.aircraft_id)
            if isinstance(telemetry, dict):
                payload = service._build_session_payload_from_vfds_telemetry(
                    session,
                    telemetry,
                    previous_payload=previous_payload,
                )
                if payload is not None:
                    vehicle_key = session.aircraft_id
                    self.frames[vehicle_key] = int(self.frames.get(vehicle_key, 0)) + 1
                    self.last_sim_time_s[vehicle_key] = float(sim_time_s)
                    self.telemetry_used[vehicle_key] = int(self.telemetry_used.get(vehicle_key, 0)) + 1
                    self.telemetry_seen[vehicle_key] = True
                    self.last_error.pop(vehicle_key, None)
                    payload["_provider"] = self.name
                    payload["_dynamics"] = HIGH_FIDELITY_DYNAMICS_MODEL
                    payload["_provider_mode"] = "vfds-telemetry"
                    return payload
            if self.telemetry_seen.get(session.aircraft_id) and isinstance(previous_payload, dict):
                vehicle_key = session.aircraft_id
                self.telemetry_stale_holds[vehicle_key] = (
                    int(self.telemetry_stale_holds.get(vehicle_key, 0)) + 1
                )
                payload = deepcopy(previous_payload)
                self.frames[vehicle_key] = int(self.frames.get(vehicle_key, 0)) + 1
                self.last_sim_time_s[vehicle_key] = float(sim_time_s)
                payload["_provider"] = self.name
                payload["_dynamics"] = HIGH_FIDELITY_DYNAMICS_MODEL
                payload["_provider_mode"] = "vfds-stale-hold"
                session.last_payload = payload
                return payload

            point = session.advance(sim_time_s)
            if point is None:
                return None
            payload = service._build_session_payload_from_point(
                session,
                point,
                previous_payload=previous_payload,
            )
            vehicle_key = session.aircraft_id
            self.frames[vehicle_key] = int(self.frames.get(vehicle_key, 0)) + 1
            self.last_sim_time_s[vehicle_key] = float(sim_time_s)
            self.last_error.pop(vehicle_key, None)
            payload["_provider"] = self.name
            payload["_dynamics"] = HIGH_FIDELITY_DYNAMICS_MODEL
            payload["_provider_mode"] = "trajectory-fallback"
            return payload
        except Exception as exc:
            self.last_error[session.aircraft_id] = f"{type(exc).__name__}: {exc}"
            raise

    def status(self) -> Dict[str, Any]:
        worker_status = self._time_worker.snapshot() if self._time_worker is not None else {}
        return {
            "name": self.name,
            "mode": "vfds-bridge-telemetry",
            "runtime_ready": bool(self.last_health.get("ok") or self.last_health.get("status") == "ok"),
            "time_feed_period_s": float(self.time_feed_period_s),
            "time_feed_enabled": bool(self.time_feed_enabled),
            "frames": dict(self.frames),
            "last_sim_time_s": dict(self.last_sim_time_s),
            "last_error": dict(self.last_error),
            "submitted": dict(self.submitted),
            "submit_results": dict(self.submit_results),
            "delete_results": dict(self.delete_results),
            "last_health": dict(self.last_health),
            "last_time_hms": self.last_time_hms,
            "last_time_source": self.last_time_source,
            "last_time_result": dict(self.last_time_result),
            "time_feed_count": int(self.time_feed_count),
            "time_worker": worker_status,
            "telemetry": self.telemetry.snapshot(),
            "telemetry_used": dict(self.telemetry_used),
            "telemetry_seen": dict(self.telemetry_seen),
            "telemetry_stale_holds": dict(self.telemetry_stale_holds),
        }


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
        self._latest_4001_publisher = _Latest4001Publisher(self._send_4001_sync)
        if self._async_send:
            self._latest_4001_publisher.start()

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
        self._manual_configs: Dict[str, ManualVehicleConfig] = {
            self._manual_config.vehicle_id: self._manual_config,
        }
        self._manual_dynamics_by_vehicle: Dict[str, Any] = {
            self._manual_config.vehicle_id: self._manual_dynamics,
        }
        self._manual_contexts: Dict[str, VehiclePublishContext] = {
            self._manual_config.vehicle_id: self._manual_context,
        }
        self._manual_inputs: Dict[str, ManualControlInput] = {
            self._manual_config.vehicle_id: self._manual_input,
        }
        self._manual_last_payloads: Dict[str, Dict[str, Any]] = {}
        self._vehicle_control_modes: Dict[str, ControlMode] = {}
        self._vehicle_dynamics_models: Dict[str, str] = {}
        self._vehicle_provider_modes: Dict[str, str] = {}
        self._mock_kp2a_provider = _MockKp2AProvider()
        self._manual_source_targets: Dict[str, str] = {}
        self._running = False
        self._sim_time_s: float = float(DEFAULT_SIMULATION_START_S)
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
        self._rx_4103_count: int = 0
        self._rx_5001_count: int = 0
        self._last_rx_3001: str = ""
        self._last_rx_0003: str = ""
        self._last_rx_2002: str = ""
        self._last_rx_3002: str = ""
        self._last_rx_3003: str = ""
        self._last_rx_4103: str = ""
        self._last_rx_5001: str = ""
        self._last_heartbeat_error: str = ""
        self._last_collision_event: Dict[str, Any] = {}
        self._collisions_by_vehicle: Dict[str, Dict[str, Any]] = {}
        self._collision_responses_by_vehicle: Dict[str, Dict[str, Any]] = {}
        self._collision_hold_payloads: Dict[str, Dict[str, Any]] = {}
        # 계획 버전 추적 (planVersion 이 낮으면 무시)
        self._plan_versions: Dict[str, int] = {}

    # ── 비행계획 관리 ──────────────────────────────────────────

    def add_plan(self, plan_or_dict: Any) -> str:
        raw_payload = deepcopy(plan_or_dict) if isinstance(plan_or_dict, dict) else None
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
        vfds_payload = _build_vfds_mission_payload(plan, raw_payload)
        session.vfds_mission_payload = vfds_payload  # type: ignore[attr-defined]
        with self._lock:
            self._clear_collision_response_locked(plan.aircraft_id)
            self._sessions[plan.aircraft_id] = session
            self._mock_kp2a_provider.register_session_payload(session, vfds_payload)
        logger.info(
            "registered plan: %s (etot=%s, fpn=%d)",
            plan.aircraft_id, plan.departure.etot, plan.flight_plan_number,
        )
        return plan.aircraft_id

    def add_plans_from_json(self, data: Any) -> List[str]:
        ids: List[str] = []
        if isinstance(data, dict):
            ids.append(self.add_plan(data))
            return ids
        if isinstance(data, list):
            for item in data:
                ids.append(self.add_plan(item))
            return ids
        plans = parse_flight_plans(data)
        for plan in plans:
            ids.append(self.add_plan(plan))
        return ids

    def remove_plan(self, vehicle_id: str) -> bool:
        session_to_delete: Optional[VehicleSession] = None
        with self._lock:
            vehicle_key = str(vehicle_id or "").strip()
            session = self._sessions.get(vehicle_key)
            submitted_fpn = int(self._mock_kp2a_provider.submitted.get(vehicle_key, 0) or 0)
            should_delete = bool(
                session is not None
                and (self._session_uses_kp2a_locked(session) or submitted_fpn)
            )
            removed = self._sessions.pop(vehicle_key, None) is not None
            if removed and session is not None and should_delete:
                session_to_delete = session
            if removed:
                self._clear_collision_response_locked(vehicle_key)
                self._mock_kp2a_provider.reset(vehicle_key)
        if session_to_delete is not None:
            self._mock_kp2a_provider.delete_session(session_to_delete, reason="remove_plan")
            return removed
        return removed

    def clear_plans(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
            self._clear_collision_response_locked("")
        self._delete_high_fidelity_sessions(sessions, reason="clear_plans")
        for vehicle_key, fpn in list(self._mock_kp2a_provider.submitted.items()):
            self._mock_kp2a_provider.delete_session(
                vehicle_key,
                flight_plan_number=int(fpn),
                reason="clear_plans_leftover",
            )
        with self._lock:
            self._mock_kp2a_provider.reset()
            self._mock_kp2a_provider.clear_all()

    def reset_sessions(self, *, cleanup_high_fidelity: bool = False, cleanup_reason: str = "reset_sessions") -> None:
        sessions_to_cleanup: List[VehicleSession] = []
        with self._lock:
            if cleanup_high_fidelity:
                sessions_to_cleanup = list(self._sessions.values())
            for session in self._sessions.values():
                session.reset()
            self._sim_time_s = float(DEFAULT_SIMULATION_START_S)
            self._pending_ext_time = None
            self._last_external_tick_wall = time.monotonic()
            self._external_time_initialized = False
            self._clear_collision_response_locked("")
            self._mock_kp2a_provider.reset()
        if sessions_to_cleanup:
            self._delete_high_fidelity_sessions(sessions_to_cleanup, reason=cleanup_reason)

    # ── 충돌 반응 상태 관리 ────────────────────────────────────

    def _clear_collision_response_locked(self, vehicle_id: str = "") -> List[str]:
        """Clear active collision response/hold anchors.

        ``vehicle_id``가 비어 있거나 ``all``/``*``이면 전체를 해제한다.
        호출자는 ``self._lock``을 이미 잡고 있어야 한다.
        """
        vehicle_key = str(vehicle_id or "").strip()
        if not vehicle_key or vehicle_key.lower() in {"all", "*"}:
            affected = sorted(
                set(self._collision_responses_by_vehicle.keys())
                | set(self._collision_hold_payloads.keys())
            )
            self._collision_responses_by_vehicle.clear()
            self._collision_hold_payloads.clear()
            return affected

        affected = []
        if vehicle_key in self._collision_responses_by_vehicle:
            affected.append(vehicle_key)
        if vehicle_key in self._collision_hold_payloads and vehicle_key not in affected:
            affected.append(vehicle_key)
        self._collision_responses_by_vehicle.pop(vehicle_key, None)
        self._collision_hold_payloads.pop(vehicle_key, None)
        return affected

    def clear_collision_response(
        self,
        vehicle_id: str = "",
        *,
        clear_history: bool = False,
    ) -> Dict[str, Any]:
        """Public clear/resume hook for collision hold/emergency state."""
        with self._lock:
            affected = self._clear_collision_response_locked(vehicle_id)
            if clear_history:
                vehicle_key = str(vehicle_id or "").strip()
                if not vehicle_key or vehicle_key.lower() in {"all", "*"}:
                    self._collisions_by_vehicle.clear()
                    self._last_collision_event = {}
                else:
                    self._collisions_by_vehicle.pop(vehicle_key, None)
            return {
                "cleared": affected,
                "active": {
                    key: dict(value)
                    for key, value in self._collision_responses_by_vehicle.items()
                },
            }

    def _collision_response_active_locked(self, vehicle_id: str) -> bool:
        response = self._collision_responses_by_vehicle.get(str(vehicle_id or "").strip()) or {}
        return bool(response.get("active")) and str(response.get("responseMode") or "") in COLLISION_ACTIVE_RESPONSE_MODES

    def _collision_response_for_vehicle(self, vehicle_id: str) -> Dict[str, Any]:
        with self._lock:
            return dict(self._collision_responses_by_vehicle.get(str(vehicle_id or "").strip()) or {})

    def _apply_collision_response_to_payload(
        self,
        vehicle_id: str,
        payload: Dict[str, Any],
        *,
        previous_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Apply active collision response to a 4001 sub-payload.

        The first payload observed after the collision becomes the hold anchor.
        If a pre-collision payload is available, it is preferred so the vehicle
        freezes at the last displayed position instead of advancing one tick.
        """
        vehicle_key = str(vehicle_id or "").strip()
        if not vehicle_key or not isinstance(payload, dict):
            return payload
        with self._lock:
            response = dict(self._collision_responses_by_vehicle.get(vehicle_key) or {})
            active = bool(response.get("active")) and str(response.get("responseMode") or "") in COLLISION_ACTIVE_RESPONSE_MODES
            if not active:
                self._collision_hold_payloads.pop(vehicle_key, None)
                # ``payload`` can be a stale-hold/previous payload that already
                # contains the old 4103 collision snapshot.  Once the active
                # response is cleared, never re-publish that stale marker in
                # 4001; otherwise OperationModule keeps showing "collision
                # active" even though VehicleModule has resumed.
                if "collision" in payload:
                    cleaned = deepcopy(payload)
                    cleaned.pop("collision", None)
                    return cleaned
                return payload

            anchor = self._collision_hold_payloads.get(vehicle_key)
            if not isinstance(anchor, dict):
                source = previous_payload if isinstance(previous_payload, dict) else payload
                anchor = deepcopy(source)
                self._collision_hold_payloads[vehicle_key] = deepcopy(anchor)

        return _zero_motion_payload(
            anchor,
            collision=response,
            response_mode=str(response.get("responseMode") or "hold"),
        )

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
            if mode == ControlMode.MISSION:
                self._vehicle_control_modes.clear()
                self._vehicle_dynamics_models.clear()
                self._vehicle_provider_modes.clear()
            self._manual_last_tick_wall = time.monotonic()
            if mode != ControlMode.MISSION:
                self._clock_mode = ClockMode.WALL

    def set_vehicle_control_mode(self, vehicle_id: str, mode: ControlMode | str) -> None:
        vehicle_id = str(vehicle_id or "").strip()
        if not vehicle_id:
            return
        mode = ControlMode(mode) if isinstance(mode, str) else mode
        with self._lock:
            self._assert_vehicle_allows_control_mode_locked(vehicle_id, mode)
            self._vehicle_control_modes[vehicle_id] = mode
            self._manual_last_tick_wall = time.monotonic()
            if mode != ControlMode.MISSION:
                self._clock_mode = ClockMode.WALL
                self._ensure_manual_vehicle_locked(vehicle_id)

    def _routing_vehicle_ids_locked(self) -> set[str]:
        return (
            set(getattr(self, "_sessions", {}).keys())
            | set(getattr(self, "_manual_configs", {}).keys())
            | set(getattr(self, "_vehicle_control_modes", {}).keys())
            | set(getattr(self, "_vehicle_dynamics_models", {}).keys())
            | set(getattr(self, "_vehicle_provider_modes", {}).keys())
        )

    def _resolve_dynamics_model_locked(self, vehicle_id: str) -> str:
        vehicle_key = str(vehicle_id or "").strip()
        dynamics_models = getattr(self, "_vehicle_dynamics_models", {})
        return _normalize_dynamics_model(dynamics_models.get(vehicle_key))

    def _resolve_provider_locked(self, vehicle_id: str) -> str:
        dynamics_model = self._resolve_dynamics_model_locked(vehicle_id)
        vehicle_key = str(vehicle_id or "").strip()
        provider_modes = getattr(self, "_vehicle_provider_modes", {})
        raw_provider = provider_modes.get(vehicle_key)
        return _normalize_provider_name(raw_provider, dynamics_model=dynamics_model)

    def _session_uses_kp2a_locked(self, session: VehicleSession) -> bool:
        return (
            self._resolve_dynamics_model_locked(session.aircraft_id) == HIGH_FIDELITY_DYNAMICS_MODEL
            and self._resolve_provider_locked(session.aircraft_id) in KP2A_PROVIDER_ALIASES
        )

    def _high_fidelity_sessions_snapshot(self) -> List[VehicleSession]:
        with self._lock:
            return [
                session
                for session in self._sessions.values()
                if self._session_uses_kp2a_locked(session)
            ]

    def _delete_high_fidelity_sessions(self, sessions: List[VehicleSession], *, reason: str) -> None:
        selected: List[VehicleSession] = []
        with self._lock:
            for session in sessions:
                if self._session_uses_kp2a_locked(session):
                    selected.append(session)
        for session in selected:
            try:
                self._mock_kp2a_provider.delete_session(session, reason=reason)
            except Exception:
                logger.exception(
                    "VFDS mission delete failed: aircraft=%s fpn=%s reason=%s",
                    session.aircraft_id,
                    session.flight_plan_number,
                    reason,
                )

    def _submit_high_fidelity_missions(self, *, reason: str) -> Dict[str, Any]:
        submitted: Dict[str, Any] = {}
        for session in self._high_fidelity_sessions_snapshot():
            try:
                result = self._mock_kp2a_provider.submit_session(session, reason=reason)
                submitted[session.aircraft_id] = result.to_dict()
                if not result.ok:
                    session.last_error = self._mock_kp2a_provider.last_error.get(session.aircraft_id, "")
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                session.last_error = f"VFDS submit failed: {error}"
                self._mock_kp2a_provider.last_error[session.aircraft_id] = session.last_error
                submitted[session.aircraft_id] = {"ok": False, "error": error}
                logger.exception(
                    "VFDS mission submit failed: aircraft=%s fpn=%s reason=%s",
                    session.aircraft_id,
                    session.flight_plan_number,
                    reason,
                )
        return submitted

    def _feed_high_fidelity_time(
        self,
        sim_time_s: float,
        *,
        force: bool = False,
        source: str = "VehicleModule",
    ) -> None:
        if not self._high_fidelity_sessions_snapshot():
            return
        try:
            self._mock_kp2a_provider.feed_time(sim_time_s, force=force, source=source)
        except Exception:
            logger.exception("VFDS time feed failed: sim_time_s=%s source=%s", sim_time_s, source)

    def ensure_vfds_runtime(self, *, timeout_s: float = 20.0) -> Dict[str, Any]:
        """Public API hook used by OperationModule before arming high-fidelity missions."""
        return self._mock_kp2a_provider.ensure_ready(timeout_s=float(timeout_s))

    def vfds_status(self) -> Dict[str, Any]:
        return self._mock_kp2a_provider.status()

    def _assert_vehicle_allows_control_mode_locked(self, vehicle_id: str, mode: ControlMode) -> None:
        vehicle_key = str(vehicle_id or "").strip()
        if (
            vehicle_key
            and self._resolve_dynamics_model_locked(vehicle_key) == HIGH_FIDELITY_DYNAMICS_MODEL
            and mode != ControlMode.MISSION
        ):
            raise ValueError(
                "highFidelity dynamics currently supports Autopilot/mission mode only "
                f"(vehicle={vehicle_key}, mode={mode.value})"
            )

    def _validate_provider_routing_locked(self) -> None:
        for vehicle_id in sorted(self._routing_vehicle_ids_locked()):
            dynamics_model = self._resolve_dynamics_model_locked(vehicle_id)
            control_mode = self._resolve_control_mode_locked(vehicle_id)
            if dynamics_model == HIGH_FIDELITY_DYNAMICS_MODEL:
                self._assert_vehicle_allows_control_mode_locked(vehicle_id, control_mode)

    def set_vehicle_control_modes(
        self,
        *,
        default_mode: ControlMode | str | None = None,
        vehicle_modes: Optional[Dict[str, ControlMode | str]] = None,
        dynamics_by_aircraft: Optional[Dict[str, Any]] = None,
        provider_by_aircraft: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            previous_control_mode = self._control_mode
            previous_vehicle_modes = dict(self._vehicle_control_modes)
            previous_dynamics = dict(self._vehicle_dynamics_models)
            previous_providers = dict(self._vehicle_provider_modes)
            try:
                if default_mode is not None:
                    self._control_mode = ControlMode(default_mode) if isinstance(default_mode, str) else default_mode
                self._vehicle_control_modes.clear()
                for vehicle_id, raw_mode in dict(vehicle_modes or {}).items():
                    vehicle_key = str(vehicle_id or "").strip()
                    if not vehicle_key:
                        continue
                    mode = ControlMode(raw_mode) if isinstance(raw_mode, str) else raw_mode
                    self._vehicle_control_modes[vehicle_key] = mode
                self._vehicle_dynamics_models.clear()
                for vehicle_id, raw_dynamics in dict(dynamics_by_aircraft or {}).items():
                    vehicle_key = str(vehicle_id or "").strip()
                    if not vehicle_key:
                        continue
                    self._vehicle_dynamics_models[vehicle_key] = _normalize_dynamics_model(raw_dynamics)
                self._vehicle_provider_modes.clear()
                for vehicle_id, raw_provider in dict(provider_by_aircraft or {}).items():
                    vehicle_key = str(vehicle_id or "").strip()
                    if not vehicle_key:
                        continue
                    dynamics_model = self._vehicle_dynamics_models.get(vehicle_key, DEFAULT_DYNAMICS_MODEL)
                    self._vehicle_provider_modes[vehicle_key] = _normalize_provider_name(
                        raw_provider,
                        dynamics_model=dynamics_model,
                    )
                # If a highFidelity vehicle did not provide a provider explicitly,
                # select the VFDS/KP2A route.  Session 3 backs it by a mock provider;
                # Session 4/5 will replace the internals without changing routing.
                for vehicle_id, dynamics_model in list(self._vehicle_dynamics_models.items()):
                    self._vehicle_provider_modes.setdefault(
                        vehicle_id,
                        _default_provider_for_dynamics(dynamics_model),
                    )
                self._validate_provider_routing_locked()
                for vehicle_key, mode in self._vehicle_control_modes.items():
                    if mode != ControlMode.MISSION:
                        self._ensure_manual_vehicle_locked(vehicle_key)
            except Exception:
                self._control_mode = previous_control_mode
                self._vehicle_control_modes = previous_vehicle_modes
                self._vehicle_dynamics_models = previous_dynamics
                self._vehicle_provider_modes = previous_providers
                raise
            if self._control_mode != ControlMode.MISSION or any(
                mode != ControlMode.MISSION for mode in self._vehicle_control_modes.values()
            ):
                self._clock_mode = ClockMode.WALL
            self._manual_last_tick_wall = time.monotonic()
            vehicle_ids = sorted(self._routing_vehicle_ids_locked())
            return {
                "defaultMode": self._control_mode.value,
                "vehicleModes": {
                    vehicle_id: mode.value for vehicle_id, mode in self._vehicle_control_modes.items()
                },
                "dynamicsByAircraft": {
                    vehicle_id: self._resolve_dynamics_model_locked(vehicle_id)
                    for vehicle_id in vehicle_ids
                },
                "providerByAircraft": {
                    vehicle_id: self._resolve_provider_locked(vehicle_id)
                    for vehicle_id in vehicle_ids
                },
            }

    def set_manual_source_target(self, source: str, vehicle_id: str) -> None:
        source_key = str(source or "").strip().lower()
        vehicle_key = str(vehicle_id or "").strip()
        if not source_key or not vehicle_key:
            return
        with self._lock:
            self._manual_source_targets[source_key] = vehicle_key
            self._ensure_manual_vehicle_locked(vehicle_key)

    def get_manual_source_target(self, source: str) -> str:
        with self._lock:
            return self._source_target_locked(source)

    def _resolve_control_mode_locked(self, vehicle_id: str) -> ControlMode:
        vehicle_key = str(vehicle_id or "").strip()
        return self._vehicle_control_modes.get(vehicle_key, self._control_mode)

    def control_mode_info(self, vehicle_id: str) -> Dict[str, Any]:
        """Return resolved + explicit control mode state for one aircraft.

        The public status payload intentionally reports resolved modes for UI,
        but input routing needs to know whether a mode was explicitly assigned
        to the aircraft or merely inherited from the common/default mode.
        """
        vehicle_key = str(vehicle_id or "").strip()
        with self._lock:
            explicit_mode = self._vehicle_control_modes.get(vehicle_key)
            resolved = explicit_mode or self._control_mode
            return {
                "vehicle_id": vehicle_key,
                "mode": resolved.value,
                "explicit": explicit_mode is not None,
                "defaultMode": self._control_mode.value,
                "dynamics": self._resolve_dynamics_model_locked(vehicle_key),
                "provider": self._resolve_provider_locked(vehicle_key),
            }

    def _has_manual_control_locked(self) -> bool:
        if self._control_mode != ControlMode.MISSION:
            return True
        return any(mode != ControlMode.MISSION for mode in self._vehicle_control_modes.values())

    def _source_target_locked(self, source: str) -> str:
        source_key = str(source or "").strip().lower()
        if source_key and self._manual_source_targets.get(source_key):
            return self._manual_source_targets[source_key]
        return self._manual_config.vehicle_id

    def _known_vehicle_ids_locked(self) -> set[str]:
        return self._routing_vehicle_ids_locked()

    def _operator_target_ids_locked(
        self,
        raw: Dict[str, Any],
        *,
        source_text: str,
        mode_text: str,
    ) -> List[str]:
        explicit = str(raw.get("aircraftId") or raw.get("vehicleId") or "").strip()
        if explicit:
            return [explicit]

        requested_mode: Optional[ControlMode] = None
        source_key = str(source_text or "").strip().lower()
        mode_key = str(mode_text or "").strip().lower()
        if source_key == "joystick" or mode_key in ("joystick", "stick"):
            requested_mode = ControlMode.JOYSTICK
        elif source_key == "keyboard" or mode_key in ("keyboard", "manual", "operator"):
            requested_mode = ControlMode.KEYBOARD

        if requested_mode is not None:
            targets = [
                vehicle_id
                for vehicle_id in sorted(self._known_vehicle_ids_locked())
                if self._resolve_control_mode_locked(vehicle_id) == requested_mode
            ]
            if targets:
                return targets

        return [self._source_target_locked(source_key or mode_key)]

    def _ensure_manual_vehicle_locked(
        self,
        vehicle_id: str,
        config_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        vehicle_key = str(vehicle_id or "").strip() or self._manual_config.vehicle_id
        base = self._manual_configs.get(vehicle_key) or self._manual_config
        dynamics = self._manual_dynamics_by_vehicle.get(vehicle_key)
        context = self._manual_contexts.get(vehicle_key)

        # 중요:
        # 이 함수는 "없으면 만들기"뿐 아니라, 매 tick 현재 수동 대상 차량을
        # 선택하기 위해서도 호출된다. 기존 구현은 config_data가 없어도
        # dynamics.configure()를 매번 호출해서 위치/속도/last_input을 초기화했다.
        # 그 결과 키보드/조이스틱 입력은 들어와도 다음 4001 tick에서 바로
        # 초기 상태로 리셋되어 Unreal에서는 비행체가 전혀 움직이지 않았다.
        #
        # 명시적 config 요청(/api/control/manual/config, capture start)일 때만
        # 재설정하고, 일반 입력/발행 tick에서는 기존 dynamics 상태를 보존한다.
        should_configure = dynamics is None or config_data is not None
        if should_configure:
            raw_config = dict(config_data or {})
            raw_config["vehicle_id"] = vehicle_key
            config = ManualVehicleConfig.from_dict(raw_config, base)
            if dynamics is None:
                dynamics = create_operator_dynamics("manual_kinematic", config)
            else:
                dynamics.configure(config)
            context = VehiclePublishContext(
                vehicle_id=config.vehicle_id,
                flight_plan_number=int(config.flight_plan_number),
                origin_frame=config.origin_frame,
                current_waypoint_id=build_manual_waypoint_id(config.flight_plan_number),
            )
            self._manual_configs[vehicle_key] = config
            self._manual_dynamics_by_vehicle[vehicle_key] = dynamics
            self._manual_contexts[vehicle_key] = context
        else:
            config = base
            if context is None:
                context = VehiclePublishContext(
                    vehicle_id=config.vehicle_id,
                    flight_plan_number=int(config.flight_plan_number),
                    origin_frame=config.origin_frame,
                    current_waypoint_id=build_manual_waypoint_id(config.flight_plan_number),
                )
                self._manual_contexts[vehicle_key] = context

        self._manual_inputs.setdefault(vehicle_key, ManualControlInput())

        # Backward-compatible "current manual vehicle" snapshot.
        self._manual_config = config
        self._manual_dynamics = dynamics
        self._manual_context = context
        self._manual_input = self._manual_inputs[vehicle_key]
        self._manual_last_payload = self._manual_last_payloads.get(vehicle_key)
        return dynamics.snapshot()

    def configure_manual_vehicle(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            vehicle_id = str((data or {}).get("vehicle_id") or self._manual_config.vehicle_id).strip()
            snapshot = self._ensure_manual_vehicle_locked(vehicle_id, data)
            self._manual_last_payloads.pop(vehicle_id, None)
            self._manual_last_payload = None
            self._manual_last_tick_wall = time.monotonic()
            return snapshot

    def set_manual_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        command = ManualControlInput.from_dict(data)
        with self._lock:
            vehicle_id = self._manual_config.vehicle_id
            self._ensure_manual_vehicle_locked(vehicle_id)
            self._manual_input = command
            self._manual_inputs[vehicle_id] = command
            self._manual_dynamics.set_input(command)
            if self._resolve_control_mode_locked(vehicle_id) == ControlMode.MISSION:
                self._assert_vehicle_allows_control_mode_locked(vehicle_id, ControlMode.KEYBOARD)
                self._vehicle_control_modes[vehicle_id] = ControlMode.KEYBOARD
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
        raw = dict(data or {})
        source_text = str(raw.get("source") or source or "api").strip().lower()
        mode_text = str(raw.get("controlMode") or raw.get("mode") or control_mode or source_text or "keyboard").strip().lower()
        with self._lock:
            target_ids = self._operator_target_ids_locked(
                raw,
                source_text=source_text,
                mode_text=mode_text,
            )

        payloads: List[Dict[str, Any]] = []
        manuals: Dict[str, Dict[str, Any]] = {}
        sent = False
        errors: List[str] = []
        for target_id in target_ids:
            target_raw = dict(raw)
            target_raw["aircraftId"] = target_id
            payload = self._build_operator_control_payload(
                target_raw,
                source=source,
                control_mode=control_mode,
            )
            payloads.append(payload)
            manual = self._apply_operator_control_payload(payload, count_rx=False)
            manuals[target_id] = manual
            if send_via_server:
                try:
                    sent = bool(self.send(parse_payload("5001", payload))) or sent
                except Exception as exc:
                    err = f"{type(exc).__name__}: {exc}"
                    errors.append(err)
                    logger.debug("5001 publish failed, local input already applied: %s", err)
        payload = payloads[0] if payloads else self._build_operator_control_payload(
            raw,
            source=source,
            control_mode=control_mode,
        )
        send_error = "; ".join(errors)
        manual = manuals.get(str(payload.get("aircraftId") or ""), {})
        return {
            "ok": True,
            "sent": sent,
            "send_error": send_error,
            "payload": payload,
            "payloads": payloads,
            "manual": manual,
            "manuals": manuals,
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
        source_text = str(raw.get("source") or source or "api").strip().lower()
        with self._lock:
            vehicle_id = str(
                raw.get("aircraftId")
                or raw.get("vehicleId")
                or self._source_target_locked(source_text)
                or self._manual_config.vehicle_id
            ).strip()
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
            if not vehicle_id:
                vehicle_id = self._source_target_locked(raw.get("source") or mode_text)
            self._ensure_manual_vehicle_locked(vehicle_id)
            dynamics = self._manual_dynamics_by_vehicle[self._manual_config.vehicle_id]

            collision_response = dict(
                self._collision_responses_by_vehicle.get(self._manual_config.vehicle_id) or {}
            )
            if bool(collision_response.get("active")):
                # Collision response owns the vehicle state until an explicit
                # clear/resume arrives.  Keep the selected control mode intact,
                # but damp any keyboard/joystick command to neutral so the
                # held vehicle does not keep drifting underneath the frozen
                # 4001 output.
                neutral = ManualControlInput()
                self._manual_input = neutral
                self._manual_inputs[self._manual_config.vehicle_id] = neutral
                dynamics.set_input(neutral)
                if count_rx:
                    self._rx_5001_count += 1
                    self._last_rx_5001 = (
                        f"{raw.get('source') or ''}/blocked "
                        f"{self._manual_config.vehicle_id} "
                        f"collision={collision_response.get('responseMode') or 'hold'}"
                    ).strip()
                snapshot = dynamics.snapshot()
                snapshot["collision"] = collision_response
                return snapshot

            self._manual_input = command
            self._manual_inputs[self._manual_config.vehicle_id] = command
            dynamics.set_input(command)

            explicit_mode = self._manual_config.vehicle_id in self._vehicle_control_modes
            requested_mode: Optional[ControlMode] = None
            if mode_text in ("mission", "auto", "autopilot"):
                requested_mode = ControlMode.MISSION
            elif mode_text in ("joystick", "stick"):
                requested_mode = ControlMode.JOYSTICK
            elif mode_text in ("keyboard", "manual", "api", "operator", ""):
                requested_mode = ControlMode.KEYBOARD

            # MSG 5001 is an operator input message, not the owner of the
            # control-mode table.  Let /api/control/modes and start endpoints
            # decide explicit per-aircraft modes.  Only bootstrap a mode for
            # legacy/direct 5001 inputs when the aircraft has no explicit mode;
            # never let neutral(active=False) inputs rewrite modes.
            if active and requested_mode is not None and not explicit_mode:
                self._assert_vehicle_allows_control_mode_locked(
                    self._manual_config.vehicle_id,
                    requested_mode,
                )
                self._vehicle_control_modes[self._manual_config.vehicle_id] = requested_mode

            active_mode = self._resolve_control_mode_locked(self._manual_config.vehicle_id)
            if active_mode != ControlMode.MISSION:
                self._clock_mode = ClockMode.WALL

            if active and active_mode != ControlMode.MISSION:
                # MSG 5001 is an input sample, not a simulation transport
                # command.  Previously this path forced ``_play_state="play"``
                # and started the 4001 loop as soon as a joystick/keyboard axis
                # moved.  That made aircraft move during Execute/Arm even when
                # the operator had not pressed Play.  Keep the command buffered
                # here; actual motion is gated exclusively by 1002 Play via
                # ``apply_simulation_setup``.
                if self._play_state == "play":
                    if not self._running:
                        self._manual_last_tick_wall = time.monotonic()
                    should_start_manual_stream = True

            if count_rx:
                self._rx_5001_count += 1
                self._last_rx_5001 = (
                    f"{raw.get('source') or ''}/{active_mode.value} "
                    f"{self._manual_config.vehicle_id} "
                    f"r={command.roll:.2f} p={command.pitch:.2f} y={command.yaw:.2f} t={command.throttle:.2f}"
                ).strip()
            snapshot = dynamics.snapshot()
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

    def _set_sim_time_locked(self, sim_time_s: float) -> None:
        sim_time = float(sim_time_s)
        self._sim_time_s = sim_time
        self._external_time_initialized = True
        self._last_external_tick_wall = time.monotonic()
        if self._clock_mode == ClockMode.WALL:
            self._wall_origin_wall = time.monotonic()
            self._wall_origin_sim = sim_time

    def set_sim_time(self, sim_time_s: float) -> None:
        """현재 sim 시간을 강제 설정(재시작/되감기용)."""
        with self._lock:
            self._set_sim_time_locked(float(sim_time_s))

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
        initial_sim_time_s, initial_time_source, initial_time_value = _extract_simulation_setup_time_seconds(raw)
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

        if state_value == "play":
            with self._lock:
                should_restart_completed = bool(self._sessions) and all(
                    session.state == VehicleState.COMPLETED
                    for session in self._sessions.values()
                )
            if should_restart_completed:
                logger.info("1002 Play received after all mission sessions completed; restarting sessions")
                self.reset_sessions()

        was_reset = state_value == "reset"
        if was_reset:
            self.reset_sessions(cleanup_high_fidelity=True, cleanup_reason="1002_reset")
            state_value = "pause"

        now = time.monotonic()
        should_start = False
        initialized_from_1002 = False
        with self._lock:
            if (
                initial_sim_time_s is not None
                and self._clock_mode == ClockMode.EXTERNAL
                and not self._external_time_initialized
            ):
                self._set_sim_time_locked(initial_sim_time_s)
                self._pending_ext_time = None
                initialized_from_1002 = True
            self._playback_speed_x = speed_x
            self._play_state = state_value
            self._last_external_tick_wall = now
            sim_time_s = float(self._sim_time_s)
            should_start = (
                state_value == "play"
                and (
                    self._clock_mode != ClockMode.EXTERNAL
                    or self._external_time_initialized
                )
            )

        if should_start:
            self.start()
        self._feed_high_fidelity_time(
            sim_time_s,
            force=True,
            source=f"VehicleModule:1002:{'reset' if was_reset else state_value}",
        )
        if state_value != "play":
            self._mock_kp2a_provider.pause_time_feed()
        return {
            "play_state": state_value,
            "playback_speed_x": speed_x,
            "sim_time_s": sim_time_s,
            "running": self.status().running,
            "sim_time_initialized_from_1002": initialized_from_1002,
            "sim_time_source": initial_time_source if initialized_from_1002 else "",
            "sim_time_value": initial_time_value if initialized_from_1002 else None,
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
        self._mock_kp2a_provider.close()
        self._latest_4001_publisher.stop()
        self.publisher.close()
        VehicleModule.close(self)

    # ── 내부 ──────────────────────────────────────────────────

    def _send_4001_sync(self, message: Dict[str, Any]) -> bool:
        """Serialize and send one 4001 message on the caller's thread."""
        return bool(self.send(parse_payload("4001", message)))

    def _publish_4001_message(self, message: Dict[str, Any], *, source: str) -> bool:
        """Publish 4001 without letting WebSocket send block the sim tick."""
        ok = False
        if self._async_send:
            ok = self._latest_4001_publisher.submit(message)
            if not ok:
                logger.warning("4001 async publish queue is stopped; source=%s", source)
        else:
            try:
                ok = self.publisher.push(message)
            except Exception:
                logger.exception("%s publisher push failed", source)
                ok = False

        if self.on_publish is not None:
            try:
                self.on_publish(message)
            except Exception:
                pass
        return bool(ok)

    def _loop(self) -> None:
        next_deadline = time.monotonic()
        while not self._stop_event.is_set():
            with self._lock:
                mode = self._clock_mode
                has_manual_control = self._has_manual_control_locked()

            if has_manual_control:
                now = time.monotonic()
                with self._lock:
                    self._manual_last_tick_wall = now
                    play_state = self._play_state
                    speed = max(0.0, float(self._playback_speed_x))
                    fixed_dt = PUBLISH_PERIOD_S * speed
                    if play_state == "play":
                        self._sim_time_s += fixed_dt
                    sim_t = self._sim_time_s
                if play_state == "play":
                    # Manual dynamics is integrated with a fixed publish step.
                    # Wall-clock jitter from WebSocket/UI work should not become
                    # a physics dt spike, otherwise the aircraft appears to
                    # stutter even when inputs are smooth.
                    self._feed_high_fidelity_time(sim_t, source="VehicleModule:loop:manual")
                    self._run_mixed_tick(fixed_dt, sim_t)
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
                self._feed_high_fidelity_time(sim_t, source="VehicleModule:loop:wall")
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
                    external_ready = self._external_time_initialized
                    if play_state == "play":
                        self._sim_time_s += dt * speed
                    sim_t = float(self._sim_time_s)
                if play_state != "play" or not external_ready:
                    continue
                self._feed_high_fidelity_time(sim_t, source="VehicleModule:loop:external")
                self._run_tick(sim_t)
            else:
                # MANUAL — 루프는 idle. stop 이 올 때까지 대기.
                if self._stop_event.wait(timeout=0.25):
                    break

    def _run_mixed_tick(self, dt: float, sim_time_s: float) -> Dict[str, Any]:
        """Publish one 4001 frame where manual vehicles override mission vehicles."""
        with self._lock:
            manual_vehicle_ids = {
                vehicle_id
                for vehicle_id in self._manual_configs
                if self._resolve_control_mode_locked(vehicle_id) != ControlMode.MISSION
            }
            manual_vehicle_ids.update(
                vehicle_id
                for vehicle_id, mode in self._vehicle_control_modes.items()
                if mode != ControlMode.MISSION
            )

        mission_message = self._run_tick(
            sim_time_s,
            skip_vehicle_ids=manual_vehicle_ids,
            publish=False,
        )
        vehicle_payloads: Dict[str, Dict[str, Any]] = {
            str(vehicle_id): dict(payload)
            for vehicle_id, payload in mission_message.items()
            if vehicle_id != "timestamp" and isinstance(payload, dict)
        }

        for vehicle_id in sorted(manual_vehicle_ids):
            payload = self._run_manual_vehicle_payload(vehicle_id, dt)
            if payload:
                vehicle_payloads[vehicle_id] = payload

        if not vehicle_payloads:
            return {}

        message = build_4001_message(vehicle_payloads, timestamp=_sim_time_to_iso(sim_time_s))
        self._publish_4001_message(message, source="mixed")
        return message

    def _run_manual_vehicle_payload(self, vehicle_id: str, dt: float) -> Dict[str, Any]:
        """Advance one manual vehicle and return its 4001 sub-payload."""
        with self._lock:
            vehicle_key = str(vehicle_id or "").strip() or self._manual_config.vehicle_id
            self._ensure_manual_vehicle_locked(vehicle_key)
            dynamics = self._manual_dynamics_by_vehicle[vehicle_key]
            previous_payload = self._manual_last_payloads.get(vehicle_key)
            collision_active = self._collision_response_active_locked(vehicle_key)
            if collision_active and isinstance(previous_payload, dict):
                payload = self._apply_collision_response_to_payload(
                    vehicle_key,
                    previous_payload,
                    previous_payload=previous_payload,
                )
                self._manual_last_payloads[vehicle_key] = payload
                self._manual_last_payload = payload
                return payload
            if collision_active:
                dynamics.set_input(ManualControlInput())
            sample = dynamics.tick(0.0 if collision_active else dt)
            context = self._manual_contexts[vehicle_key]
            context.current_waypoint_id = sample.waypoint_id
            context.battery_pct = sample.battery_pct
            navigation_session = self._sessions.get(vehicle_key)
            navigation_plan = navigation_session.plan if navigation_session is not None else None
            if navigation_plan is None:
                manual_config = self._manual_configs.get(vehicle_key)
                manual_fpn = int(getattr(manual_config, "flight_plan_number", 0) or 0) if manual_config is not None else 0
                if manual_fpn:
                    for candidate in self._sessions.values():
                        if int(getattr(candidate.plan, "flight_plan_number", 0) or 0) == manual_fpn:
                            navigation_plan = candidate.plan
                            break
            if navigation_plan is None and len(self._sessions) == 1:
                # Last-resort compatibility fallback for legacy single-aircraft
                # manual flows where the manual vehicle key was not identical to
                # the 3001 aircraftId.  Multi-aircraft flows still require an
                # exact vehicle/flight-plan match to avoid drawing a wrong route.
                navigation_plan = next(iter(self._sessions.values())).plan

        navigation = _build_navigation_payload(
            navigation_plan,
            lat=sample.lat,
            lon=sample.lon,
            alt_m=sample.alt_m,
            current_waypoint_id=context.current_waypoint_id,
            seq=None,
            source="manual-route",
        )

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
            position_ned={
                "north": float(sample.north_m),
                "east": float(sample.east_m),
                "down": float(sample.down_m),
            },
            navigation=navigation,
        )
        payload = self._apply_collision_response_to_payload(
            sample.vehicle_id,
            payload,
            previous_payload=previous_payload,
        )
        self._manual_last_payloads[sample.vehicle_id] = payload
        self._manual_last_payload = payload
        return payload

    def _build_session_payload_from_point(
        self,
        session: VehicleSession,
        point: FlightTrajectoryPoint,
        *,
        previous_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build one 4001 sub-payload for an Autopilot mission session.

        Both the built-in simple provider and the Session 3 mock KP2A provider
        use this helper.  Keeping the payload builder centralized prevents
        simple/highFidelity mixed frames from diverging in NED, battery,
        navigation, or collision-hold semantics.
        """
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
        if session.state in (VehicleState.WAITING, VehicleState.ACTIVE):
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
        raw_battery_pct = max(0.0, min(100.0, float(getattr(point, "battery_pct", 100.0))))
        prev_battery_pct = getattr(session, "_last_battery_pct", raw_battery_pct)
        battery_pct = min(float(prev_battery_pct), raw_battery_pct)
        session._last_battery_pct = battery_pct  # type: ignore[attr-defined]
        session.context.battery_pct = battery_pct
        pose_projection = session.project_point_to_pose_frame(point, heading)
        pose_position = None
        pose_yaw_deg = None
        pose_frame = None
        if isinstance(pose_projection, dict):
            # 4001 position is mission-start relative in the DT World/ODT
            # visual pose frame.  The AirSim settings spawn pose is applied by
            # Unreal at startup; adding it again here would double-offset the
            # pawn away from the vertiport.
            pose_position = pose_projection.get("relative_position")
            pose_yaw_deg = pose_projection.get("yaw_deg")
            pose_frame = pose_projection.get("pose_frame")

        navigation = _build_navigation_payload(
            session.plan,
            lat=float(getattr(point, "lat", 0.0)),
            lon=float(getattr(point, "lon", 0.0)),
            alt_m=alt_m,
            current_waypoint_id=session.context.current_waypoint_id,
            seq=seq,
            source="3001",
        )

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
            battery_pct=battery_pct,
            position_ned=pose_position if isinstance(pose_position, dict) else None,
            attitude_yaw_deg=float(pose_yaw_deg) if pose_yaw_deg is not None else None,
            pose_frame=pose_frame if isinstance(pose_frame, dict) else None,
            navigation=navigation,
        )
        payload = self._apply_collision_response_to_payload(
            session.aircraft_id,
            payload,
            previous_payload=previous_payload,
        )
        if str(payload.get("collision", {}).get("responseMode") or "") in {"emergency_stop", "abort"}:
            session.last_error = (
                f"collision {payload.get('collision', {}).get('responseMode')}: "
                f"{payload.get('collision', {}).get('objectName') or '-'}"
            )
        session.last_payload = payload
        return payload

    def _build_session_payload_from_vfds_telemetry(
        self,
        session: VehicleSession,
        telemetry: Dict[str, Any],
        *,
        previous_payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Map one VFDS AircraftStatus sample to a DTAM 4001 sub-payload.

        KP2A/VFDS arrives as LLA plus provider yaw/velocity.  Keep the public
        LLA/geographic heading for Operation, and publish true local NED for
        Visualization/AirSim.  Do not apply the ODT custom visual-frame
        rotation to high-fidelity telemetry.
        """
        if not isinstance(telemetry, dict):
            return None
        position = telemetry.get("position") if isinstance(telemetry.get("position"), dict) else {}
        attitude = telemetry.get("attitude") if isinstance(telemetry.get("attitude"), dict) else {}
        actuator_raw = telemetry.get("actuator") if isinstance(telemetry.get("actuator"), dict) else {}

        first_point: Optional[FlightTrajectoryPoint] = None
        try:
            session._ensure_trajectory()
            first_point = session.trajectory[0] if session.trajectory else None
        except Exception:
            first_point = None

        raw_lat = _safe_float(position.get("lat"), 0.0)
        raw_lon = _safe_float(position.get("lon"), 0.0)
        raw_alt_m = _safe_float(position.get("alt"), getattr(first_point, "alt_m", 0.0) if first_point else 0.0)
        lla_valid = abs(raw_lat) >= 0.1 and abs(raw_lon) >= 0.1
        if lla_valid:
            lat = raw_lat
            lon = raw_lon
            alt_m = raw_alt_m
        elif first_point is not None:
            lat = float(first_point.lat)
            lon = float(first_point.lon)
            alt_m = float(first_point.alt_m)
        else:
            return None

        raw_yaw_deg = _safe_float(
            attitude.get("yaw"),
            getattr(first_point, "heading_deg", 0.0) if first_point else 0.0,
        )
        # Treat VFDS yaw as DTAM geographic/NED yaw.  When the provider gives a
        # usable velocity vector or consecutive LLA samples, prefer the motion
        # track so KP2A and simple dynamics show the same route-facing heading.
        heading_deg = _kp2a_yaw_to_geo_heading_deg(raw_yaw_deg)
        roll_rad = math.radians(_safe_float(attitude.get("roll"), 0.0))
        pitch_rad = math.radians(_safe_float(attitude.get("pitch"), 0.0))

        ts_epoch = _telemetry_ts_to_epoch(telemetry.get("ts"))
        received_wall = _safe_float(telemetry.get("_received_wall_s"), time.monotonic())
        time_key = ts_epoch if ts_epoch is not None else received_wall

        vfds_ned_available = any(key in position for key in ("north", "east", "down"))
        vfds_position_ned = None
        if vfds_ned_available:
            vfds_position_ned = {
                "north": _safe_float(position.get("north"), 0.0),
                "east": _safe_float(position.get("east"), 0.0),
                "down": _safe_float(position.get("down"), 0.0),
            }

        motion_ned: Optional[Dict[str, float]] = None
        if lla_valid:
            dtam_north, dtam_east, dtam_down = session.origin_frame.to_ned(lat, lon, alt_m)
            motion_ned = {"north": float(dtam_north), "east": float(dtam_east), "down": float(dtam_down)}
        elif isinstance(vfds_position_ned, dict) and any(
            abs(float(vfds_position_ned[key])) > 1e-6 for key in ("north", "east", "down")
        ):
            motion_ned = {k: float(vfds_position_ned[k]) for k in ("north", "east", "down")}
        else:
            # `/api/v1/events` can create zero-position AircraftStatus before
            # real telemetry arrives. Ignore it and let trajectory fallback keep
            # the previous sane frame.
            return None

        prev_motion = getattr(session, "_vfds_prev_motion", None)
        north = float(motion_ned["north"])
        east = float(motion_ned["east"])
        down = float(motion_ned["down"])

        explicit_speed_mps = _extract_vfds_speed_mps(telemetry, position)
        speed_mps = float(explicit_speed_mps) if explicit_speed_mps is not None else 0.0
        track_heading_deg = heading_deg
        climb_rate_mps = 0.0
        motion_track_heading_deg: Optional[float] = None
        if isinstance(prev_motion, dict):
            prev_time = _safe_float(prev_motion.get("time"), time_key)
            dt_s = max(0.0, float(time_key) - prev_time)
            if dt_s > 1e-3:
                dn = north - _safe_float(prev_motion.get("north"), north)
                de = east - _safe_float(prev_motion.get("east"), east)
                dd = down - _safe_float(prev_motion.get("down"), down)
                horizontal_speed = math.hypot(dn, de) / dt_s
                if explicit_speed_mps is None or horizontal_speed > 0.05:
                    speed_mps = min(120.0, max(0.0, horizontal_speed))
                if horizontal_speed > 0.05:
                    motion_track_heading_deg = math.degrees(math.atan2(de, dn)) % 360.0
                climb_rate_mps = max(-60.0, min(60.0, -dd / dt_s))

        velocity_track_heading_deg = _extract_vfds_track_heading_deg(telemetry, position)
        previous_track_heading_deg: Optional[float] = None
        previous_track_raw = getattr(session, "_vfds_last_track_heading_deg", None)
        if previous_track_raw is not None:
            previous_track_heading_deg = _wrap_heading_deg(previous_track_raw)

        # For Operation/Unreal direction, GPS/LLA motion is the most stable truth.
        # Some VFDS frames report velocity in the provider/body frame while LLA is
        # already geographic truth.  If a low-motion/stale GPS frame falls back to
        # that velocity heading, the Operation icon can flicker by exactly 90 deg.
        #
        # So: trust consecutive-LLA motion first, then keep the last accepted
        # geographic track.  VFDS velocity is only allowed as an initial hint, or
        # when it is close enough to the last accepted track to be plausible.
        ignored_velocity_track_heading_deg: Optional[float] = None
        accepted_velocity_track_heading_deg = velocity_track_heading_deg
        if velocity_track_heading_deg is not None and previous_track_heading_deg is not None:
            velocity_delta = abs(_signed_angle_delta_deg(velocity_track_heading_deg, previous_track_heading_deg))
            if velocity_delta > 45.0:
                ignored_velocity_track_heading_deg = velocity_track_heading_deg
                accepted_velocity_track_heading_deg = None

        preferred_track_heading_deg = (
            motion_track_heading_deg
            if motion_track_heading_deg is not None
            else previous_track_heading_deg
            if previous_track_heading_deg is not None
            else accepted_velocity_track_heading_deg
        )
        if preferred_track_heading_deg is not None:
            track_heading_deg = float(preferred_track_heading_deg) % 360.0
            heading_deg = track_heading_deg
            session._vfds_last_track_heading_deg = track_heading_deg  # type: ignore[attr-defined]

        session._vfds_prev_motion = {  # type: ignore[attr-defined]
            "time": float(time_key),
            "north": float(north),
            "east": float(east),
            "down": float(down),
        }

        # VFDS/KP2A LLA is GPS truth, but Visualization/AirSim consumes 4001
        # ``position`` as true vehicle-spawn-relative AirSim NED.  Keep GPS
        # fields untouched and convert only the visual pose position/yaw so
        # KP2A and simple autopilot share exactly the same Unreal pose frame.
        position_ned: Dict[str, float] = dict(motion_ned)
        position_source = "lla-dtam-ned" if lla_valid else "vfds-ned-fallback"
        pose_frame = None
        pose_yaw_deg: Optional[float] = heading_deg
        if lla_valid and first_point is not None:
            try:
                pose_time_s = _parse_sim_time_text_to_s(telemetry.get("simTime") or telemetry.get("sim_time"))
                if pose_time_s is None:
                    pose_time_s = max(0.0, received_wall)
                vfds_point = replace(
                    first_point,
                    time_s=float(pose_time_s),
                    lat=float(lat),
                    lon=float(lon),
                    alt_m=float(alt_m),
                    speed_mps=float(speed_mps),
                    heading_deg=float(heading_deg),
                    track_heading_deg=float(track_heading_deg),
                    phase=str(telemetry.get("phase") or getattr(first_point, "phase", "") or ""),
                )
                pose_projection = session.project_point_to_pose_frame(vfds_point, heading_deg)
            except Exception:
                pose_projection = None
            if isinstance(pose_projection, dict):
                pose_position = pose_projection.get("relative_position")
                if isinstance(pose_position, dict):
                    position_ned = {
                        "north": _safe_float(pose_position.get("north"), 0.0),
                        "east": _safe_float(pose_position.get("east"), 0.0),
                        "down": _safe_float(pose_position.get("down"), 0.0),
                    }
                    position_source = "lla-odt-pose-frame"
                pose_yaw_raw = pose_projection.get("yaw_deg")
                if pose_yaw_raw is not None:
                    pose_yaw_deg = _safe_float(pose_yaw_raw, heading_deg)
                pose_frame_raw = pose_projection.get("pose_frame")
                if isinstance(pose_frame_raw, dict):
                    pose_frame = pose_frame_raw

        phase = str(telemetry.get("phase") or "")
        if not phase or phase == "N/A":
            phase = str(getattr(first_point, "phase", "") or "")
        seq = int(_safe_float(telemetry.get("seq"), 0.0))
        if seq <= 0 and phase:
            seq = _find_seq_for_phase(session.plan, phase, getattr(session, "_seq_cursor", 0))
        session._seq_cursor = seq  # type: ignore[attr-defined]
        if seq >= 1:
            session.context.current_waypoint_id = f"{session.flight_plan_number}-{seq}"
        elif phase == "A":
            session.context.current_waypoint_id = (
                f"{session.flight_plan_number}-"
                f"{session.plan.departure.vertiport}-"
                f"{session.plan.departure.dep_gate_number}"
            )

        mission_state = str(telemetry.get("missionState") or "").upper()
        if mission_state in {"EXECUTING", "ACTIVE", "START"}:
            session.state = VehicleState.ACTIVE
        elif mission_state == "COMPLETED":
            session.state = VehicleState.COMPLETED
        elif mission_state == "FAILED":
            session.state = VehicleState.ERROR
            session.last_error = f"VFDS mission failed: phase={phase or '-'}"
        elif session.state == VehicleState.ERROR:
            pass
        else:
            session.state = VehicleState.WAITING

        motor_rpm_raw = telemetry.get("motorRpm") or telemetry.get("motor_rpm") or []
        motor_rpm = []
        if isinstance(motor_rpm_raw, list):
            for value in motor_rpm_raw[:4]:
                motor_rpm.append(max(0.0, min(20000.0, _safe_float(value, 0.0))))
        while len(motor_rpm) < 4:
            motor_rpm.append(0.0)
        propulsion = {"motor_rpm": motor_rpm}

        actuator = {
            "tilt_left": _safe_float(actuator_raw.get("tilt_left"), 0.0),
            "tilt_right": _safe_float(actuator_raw.get("tilt_right"), 0.0),
            "aileron": _safe_float(actuator_raw.get("aileron"), 0.0),
            "rudder_left": _safe_float(actuator_raw.get("rudder_left"), 0.0),
            "rudder_right": _safe_float(actuator_raw.get("rudder_right"), 0.0),
        }

        prev_battery_pct = _safe_float(getattr(session, "_last_battery_pct", 100.0), 100.0)
        avg_rpm = sum(motor_rpm) / max(1, len(motor_rpm))
        prev_battery_time = getattr(session, "_vfds_prev_battery_time", None)
        if prev_battery_time is None:
            battery_pct = prev_battery_pct
        else:
            dt_batt = max(0.0, float(time_key) - float(prev_battery_time))
            drain_pct = dt_batt * (0.002 + min(avg_rpm / 10000.0, 1.0) * 0.012)
            battery_pct = max(0.0, prev_battery_pct - drain_pct)
        session._vfds_prev_battery_time = float(time_key)  # type: ignore[attr-defined]
        session._last_battery_pct = battery_pct  # type: ignore[attr-defined]
        session.context.battery_pct = battery_pct

        navigation = _build_navigation_payload(
            session.plan,
            lat=lat,
            lon=lon,
            alt_m=alt_m,
            current_waypoint_id=session.context.current_waypoint_id,
            seq=seq,
            source="vfds-kp2a",
        )
        if not isinstance(navigation, dict):
            navigation = {}
        navigation["missionState"] = mission_state or ""
        navigation["phase"] = phase
        navigation["positionSource"] = position_source

        payload = build_vehicle_payload(
            context=session.context,
            lat=lat,
            lon=lon,
            alt_m=alt_m,
            speed_mps=speed_mps,
            heading_deg=heading_deg,
            track_heading_deg=track_heading_deg,
            pitch_rad=pitch_rad,
            roll_rad=roll_rad,
            climb_rate_mps=climb_rate_mps,
            phase=phase,
            seq=seq,
            battery_pct=battery_pct,
            actuator=actuator,
            propulsion=propulsion,
            energy={"battery_pct": battery_pct, "state_of_charge_pct": battery_pct},
            position_ned=position_ned,
            attitude_yaw_deg=float(pose_yaw_deg) if pose_yaw_deg is not None else heading_deg,
            pose_frame=pose_frame if isinstance(pose_frame, dict) else None,
            navigation=navigation,
        )
        payload["_vfds"] = {
            "missionState": mission_state or "",
            "phase": phase,
            "seq": seq,
            "ts": str(telemetry.get("ts") or ""),
            "source": str(telemetry.get("_source") or ""),
            "age_s": _safe_float(telemetry.get("_age_s"), 0.0),
            "positionSource": position_source,
            "rawYawDeg": float(raw_yaw_deg),
            "headingDeg": float(heading_deg),
            "poseYawDeg": float(pose_yaw_deg) if pose_yaw_deg is not None else float(heading_deg),
            "speedMps": float(speed_mps),
            "motionTrackHeadingDeg": float(motion_track_heading_deg) if motion_track_heading_deg is not None else None,
            "velocityTrackHeadingDeg": float(velocity_track_heading_deg) if velocity_track_heading_deg is not None else None,
            "ignoredVelocityTrackHeadingDeg": float(ignored_velocity_track_heading_deg)
            if ignored_velocity_track_heading_deg is not None
            else None,
            "heldTrackHeadingDeg": float(previous_track_heading_deg) if previous_track_heading_deg is not None else None,
            "motionNed": dict(motion_ned),
            "visualNed": dict(position_ned),
            "sourceNed": deepcopy(vfds_position_ned) if isinstance(vfds_position_ned, dict) else None,
        }
        payload = self._apply_collision_response_to_payload(
            session.aircraft_id,
            payload,
            previous_payload=previous_payload,
        )
        if str(payload.get("collision", {}).get("responseMode") or "") in {"emergency_stop", "abort"}:
            session.last_error = (
                f"collision {payload.get('collision', {}).get('responseMode')}: "
                f"{payload.get('collision', {}).get('objectName') or '-'}"
            )
        session.last_payload = payload
        return payload

    def _run_provider_vehicle_payload(
        self,
        session: VehicleSession,
        sim_time_s: float,
        *,
        previous_payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            dynamics_model = self._resolve_dynamics_model_locked(session.aircraft_id)
            provider_name = self._resolve_provider_locked(session.aircraft_id)
        if dynamics_model != HIGH_FIDELITY_DYNAMICS_MODEL:
            return None
        if provider_name not in KP2A_PROVIDER_ALIASES:
            session.state = VehicleState.ERROR
            session.last_error = f"unsupported highFidelity provider: {provider_name}"
            return None
        return self._mock_kp2a_provider.build_payload(
            self,
            session,
            sim_time_s,
            previous_payload=previous_payload,
        )

    def _run_manual_tick(self, dt: float, sim_time_s: float) -> Dict[str, Any]:
        """Advance the current manual vehicle and publish the resulting 4001 message."""
        payload = self._run_manual_vehicle_payload(self._manual_config.vehicle_id, dt)
        if not payload:
            return {}
        message = build_4001_message({self._manual_config.vehicle_id: payload}, timestamp=_sim_time_to_iso(sim_time_s))
        self._publish_4001_message(message, source="manual")
        return message

    def _run_tick(
        self,
        sim_time_s: float,
        *,
        skip_vehicle_ids: Optional[set[str]] = None,
        publish: bool = True,
    ) -> Dict[str, Any]:
        """현재 sim 시간에 맞춰 1 tick 진행하고 4001 을 송출."""
        with self._lock:
            sessions = list(self._sessions.values())

        skip_vehicle_ids = set(skip_vehicle_ids or set())
        vehicle_payloads: Dict[str, Dict[str, Any]] = {}
        for session in sessions:
            if session.aircraft_id in skip_vehicle_ids:
                continue
            previous_payload = session.last_payload if isinstance(session.last_payload, dict) else None
            with self._lock:
                collision_active = self._collision_response_active_locked(session.aircraft_id)
            if collision_active and isinstance(previous_payload, dict):
                payload = self._apply_collision_response_to_payload(
                    session.aircraft_id,
                    previous_payload,
                    previous_payload=previous_payload,
                )
                session.last_payload = payload
                if str(payload.get("collision", {}).get("responseMode") or "") in {"emergency_stop", "abort"}:
                    session.last_error = (
                        f"collision {payload.get('collision', {}).get('responseMode')}: "
                        f"{payload.get('collision', {}).get('objectName') or '-'}"
                    )
                vehicle_payloads[session.aircraft_id] = payload
                continue
            with self._lock:
                dynamics_model = self._resolve_dynamics_model_locked(session.aircraft_id)
            if dynamics_model == HIGH_FIDELITY_DYNAMICS_MODEL:
                try:
                    payload = self._run_provider_vehicle_payload(
                        session,
                        sim_time_s,
                        previous_payload=previous_payload,
                    )
                except Exception as exc:
                    session.state = VehicleState.ERROR
                    session.last_error = f"provider advance failed: {type(exc).__name__}: {exc}"
                    logger.exception("provider advance failed for %s", session.aircraft_id)
                    continue
                if payload is not None:
                    vehicle_payloads[session.aircraft_id] = payload
                continue

            try:
                point = session.advance(sim_time_s)
            except Exception as exc:
                session.state = VehicleState.ERROR
                session.last_error = f"advance failed: {type(exc).__name__}: {exc}"
                logger.exception("advance failed for %s", session.aircraft_id)
                continue
            if point is None:
                continue
            payload = self._build_session_payload_from_point(
                session,
                point,
                previous_payload=previous_payload,
            )
            vehicle_payloads[session.aircraft_id] = payload

        if not vehicle_payloads:
            return {}

        # 시뮬레이션 sim_time_s 를 UTC ISO 타임스탬프로 — 오늘 자정 기준으로 매핑
        ts = _sim_time_to_iso(sim_time_s)
        message = build_4001_message(vehicle_payloads, timestamp=ts)
        if not publish:
            return message
        self._publish_4001_message(message, source="mission")
        return message

    # ── 상태 질의 ──────────────────────────────────────────────

    def status(self) -> FleetStatus:
        with self._lock:
            sessions = list(self._sessions.values())
            clock_mode = self._clock_mode.value
            control_mode = self._control_mode.value
            has_manual = self._has_manual_control_locked()
            vehicle_ids = sorted(self._routing_vehicle_ids_locked())
            vehicle_dynamics = {
                vehicle_id: self._resolve_dynamics_model_locked(vehicle_id)
                for vehicle_id in vehicle_ids
            }
            vehicle_providers = {
                vehicle_id: self._resolve_provider_locked(vehicle_id)
                for vehicle_id in vehicle_ids
            }
            active_dynamics = {
                model
                for vehicle_id, model in vehicle_dynamics.items()
                if vehicle_id in self._sessions or model != DEFAULT_DYNAMICS_MODEL
            }
            if has_manual and (sessions or active_dynamics):
                dynamics_model = "mixed"
            elif has_manual:
                dynamics_model = "manual_kinematic"
            elif not active_dynamics:
                dynamics_model = "mission_profile"
            elif len(active_dynamics) == 1:
                dynamics_model = next(iter(active_dynamics))
            else:
                dynamics_model = "mixed"
            running = self._running
            play_state = self._play_state
            playback_speed_x = float(self._playback_speed_x)
            sim_t = float(self._sim_time_s)
            rx3 = self._rx_3001_count
            rx0 = self._rx_0003_count
            rx_exec = self._rx_2002_count
            rx_strategic = self._rx_3002_count
            rx_tactical = self._rx_3003_count
            rx_collision = self._rx_4103_count
            rx_manual = self._rx_5001_count
            last3 = self._last_rx_3001
            last0 = self._last_rx_0003
            last_exec = self._last_rx_2002
            last_strategic = self._last_rx_3002
            last_tactical = self._last_rx_3003
            last_collision = self._last_rx_4103
            last_manual = self._last_rx_5001
            heartbeat_error = self._last_heartbeat_error
            last_collision_event = dict(self._last_collision_event)
            collisions_by_vehicle = {
                vehicle_id: dict(event)
                for vehicle_id, event in self._collisions_by_vehicle.items()
            }
            collision_responses_by_vehicle = {
                vehicle_id: dict(response)
                for vehicle_id, response in self._collision_responses_by_vehicle.items()
            }
            manual = self._manual_dynamics.snapshot()
            manual_by_vehicle = {
                vehicle_id: dynamics.snapshot()
                for vehicle_id, dynamics in self._manual_dynamics_by_vehicle.items()
            }
            vehicle_control_modes = {
                vehicle_id: self._resolve_control_mode_locked(vehicle_id).value
                for vehicle_id in vehicle_ids
            }
            provider_statuses = {
                KP2A_PROVIDER: self._mock_kp2a_provider.status(),
            }
            source_targets = dict(self._manual_source_targets)
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
            publisher_queue=self._latest_4001_publisher.stats(),
            rx_3001_count=rx3,
            rx_0003_count=rx0,
            rx_2002_count=rx_exec,
            rx_3002_count=rx_strategic,
            rx_3003_count=rx_tactical,
            rx_4103_count=rx_collision,
            rx_5001_count=rx_manual,
            last_rx_3001=last3,
            last_rx_0003=last0,
            last_rx_2002=last_exec,
            last_rx_3002=last_strategic,
            last_rx_3003=last_tactical,
            last_rx_4103=last_collision,
            last_rx_5001=last_manual,
            last_heartbeat_error=heartbeat_error,
            last_collision_event=last_collision_event,
            collisions_by_vehicle=collisions_by_vehicle,
            collision_responses_by_vehicle=collision_responses_by_vehicle,
            manual=manual,
            manual_by_vehicle=manual_by_vehicle,
            vehicle_control_modes=vehicle_control_modes,
            vehicle_dynamics=vehicle_dynamics,
            vehicle_providers=vehicle_providers,
            provider_statuses=provider_statuses,
            manual_source_targets=source_targets,
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

    def on_vehicle_collision_event(self, msg: Any) -> None:
        self._on_vehicle_collision_event(_CompatReceiveResult(msg))

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
        """MSG 0003 수신 → simulation time 을 시계로 주입.

        - 기존 동작과 같이 아직 외부 시간이 초기화되지 않았을 때 ``_sim_time_s``에
          초기 주입한다.
        - ``simSecondsOfDay``/``simTimeOfDay``가 있으면 우선 사용하고,
          없으면 기존 ``simTime`` ISO 파싱을 유지.
        - EXTERNAL 모드인 경우 추가로 ``feed_time_seconds`` 를 호출해
          서비스 루프가 1 tick 진행하고 4001 을 송출하도록 유도.
        """
        try:
            raw = getattr(result, "raw", None) or {}
            if not isinstance(raw, dict):
                raw = {}
            if getattr(result, "sim_seconds_of_day", None) is not None and "simSecondsOfDay" not in raw:
                raw["simSecondsOfDay"] = getattr(result, "sim_seconds_of_day")
            if getattr(result, "sim_time_of_day", None) and "simTimeOfDay" not in raw:
                raw["simTimeOfDay"] = getattr(result, "sim_time_of_day")
            if getattr(result, "sim_time", None) and "simTime" not in raw:
                raw["simTime"] = getattr(result, "sim_time")

            sim_s, sim_source, sim_value = _extract_common_time_seconds(raw)
            if sim_s is None:
                return
            with self._lock:
                self._rx_0003_count += 1
                self._last_rx_0003 = f"{sim_source}={sim_value}"
                mode = self._clock_mode
                should_apply_time = not self._external_time_initialized
                play_state = self._play_state
                if should_apply_time:
                    self._set_sim_time_locked(float(sim_s))
            if mode == ClockMode.EXTERNAL:
                self.feed_time_seconds(sim_s)
                if play_state == "play":
                    self.start()
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
                "1002 Simulation Control received: playState=%s speed=%sx simTime=%s source=%s initialized=%s",
                applied["play_state"],
                applied["playback_speed_x"],
                applied["sim_time_s"],
                applied.get("sim_time_source") or "",
                applied.get("sim_time_initialized_from_1002"),
            )
        except Exception:
            logger.exception("_on_simulation_setup failed")

    def _on_dtam_execute(self, result: Any) -> None:
        try:
            raw = getattr(result, "raw", None) or {}
            folder = str(raw.get("flightPlanFolderName") or "")
            with self._lock:
                previous_control_mode = self._control_mode
            self.reset_sessions(cleanup_high_fidelity=True, cleanup_reason="2002_execute")
            with self._lock:
                self._rx_2002_count += 1
                self._last_rx_2002 = folder or str(raw)
                # 2002 means "arm/reset the DTAM execution flow"; it must not
                # override the controller selected in 1001 / prepare-execution.
                # Operation Console prepares Keyboard/Joystick via REST before
                # sending 2002, so preserving the current manual mode is what
                # makes the subsequent 1002 Play drive manual dynamics instead
                # of the mission autopilot.
                self._control_mode = previous_control_mode
                has_manual_mode = self._control_mode != ControlMode.MISSION or any(
                    mode != ControlMode.MISSION for mode in self._vehicle_control_modes.values()
                )
                if has_manual_mode:
                    self._clock_mode = ClockMode.WALL
                    self._manual_last_tick_wall = time.monotonic()
                self._play_state = "pause"
                self._last_external_tick_wall = time.monotonic()
            submit_results = self._submit_high_fidelity_missions(reason="2002_execute")
            self._feed_high_fidelity_time(
                DEFAULT_SIMULATION_START_S,
                force=True,
                source="VehicleModule:2002",
            )
            self._mock_kp2a_provider.pause_time_feed()
            logger.info(
                "2002 DTAM Execute received: flightPlanFolderName=%s control=%s vehicleModes=%s highFidelitySubmit=%s (armed, waiting for 1002 play)",
                folder,
                self._control_mode.value,
                {vehicle_id: mode.value for vehicle_id, mode in self._vehicle_control_modes.items()},
                submit_results,
            )
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

    def _on_vehicle_collision_event(self, result: Any) -> None:
        """MSG 4103 수신 → 충돌 이벤트 기록 및 비행 상태 반응 활성화."""
        try:
            raw = getattr(result, "raw", None) or {}
            if not isinstance(raw, dict):
                return
            ok = bool(getattr(result, "ok", True))
            if not ok:
                logger.warning("4103 수신 무효: %s", getattr(result, "errors", None))
                return

            aircraft_id = str(raw.get("aircraftId") or raw.get("vehicleId") or "").strip()
            event_id = str(raw.get("eventId") or "").strip()
            object_name = str(raw.get("objectName") or raw.get("objectId") or "").strip()
            severity = str(raw.get("severity") or "").strip()
            action = str(raw.get("recommendedAction") or "").strip()
            response_mode = _normalize_collision_response_mode(raw)
            brief = (
                f"{event_id or 'collision'} {aircraft_id or '-'} "
                f"object={object_name or '-'} severity={severity or '-'} "
                f"action={action or '-'} response={response_mode}"
            ).strip()

            event_payload = dict(raw)
            active = response_mode in COLLISION_ACTIVE_RESPONSE_MODES
            response_snapshot = _collision_snapshot_from_event(
                event_payload,
                response_mode=response_mode,
                active=active,
            )
            abort_sessions: List[VehicleSession] = []
            with self._lock:
                self._rx_4103_count += 1
                self._last_rx_4103 = brief
                self._last_collision_event = event_payload
                if aircraft_id:
                    self._collisions_by_vehicle[aircraft_id] = event_payload
                    if response_mode == "clear":
                        self._clear_collision_response_locked(aircraft_id)
                    elif active:
                        self._collision_responses_by_vehicle[aircraft_id] = response_snapshot
                        # A fresh collision event should freeze at the most
                        # recent visible payload.  If none exists, the next
                        # tick will establish the anchor.
                        anchor = None
                        session = self._sessions.get(aircraft_id)
                        manual_payloads = getattr(self, "_manual_last_payloads", {})
                        if isinstance(manual_payloads.get(aircraft_id), dict):
                            anchor = manual_payloads.get(aircraft_id)
                        elif session is not None and isinstance(session.last_payload, dict):
                            anchor = session.last_payload
                        if isinstance(anchor, dict):
                            self._collision_hold_payloads[aircraft_id] = deepcopy(anchor)
                        if response_mode in {"emergency_stop", "abort"} and session is not None:
                            session.last_error = f"collision {response_mode}: {object_name or '-'}"
                        if (
                            response_mode == "abort"
                            and session is not None
                            and self._session_uses_kp2a_locked(session)
                        ):
                            abort_sessions.append(session)
                    elif response_mode == "none":
                        # Record-only event: leave any existing active response
                        # untouched until an explicit clear/resume arrives.
                        pass

            for session in abort_sessions:
                try:
                    self._mock_kp2a_provider.delete_session(session, reason="collision_abort")
                except Exception:
                    logger.exception(
                        "VFDS mission abort cleanup failed: aircraft=%s fpn=%s event=%s",
                        session.aircraft_id,
                        session.flight_plan_number,
                        event_id,
                    )

            logger.info("4103 Vehicle Collision Event received: %s", brief)
        except Exception:
            logger.exception("_on_vehicle_collision_event failed")

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
