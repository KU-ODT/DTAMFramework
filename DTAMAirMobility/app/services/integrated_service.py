"""통합 AirMobility 서비스.

한 대 이상의 UAM 에 비행 계획(FlightPlan) 을 등록해두면, 외부 또는 내부(wall)
시계에서 주입되는 현재 시각을 따라 각 비행체의 궤적을 10 Hz 로 생성하고
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
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from ..domain.dynamics.core.types import FlightPlan, SimulationConfig
from ..domain.dynamics.io.icd_parser import parse_flight_plans, parse_flight_plan

from dtam_client import VehicleModule, on_receive  # type: ignore  # SDK 가 sys.path 에 있어야 함

from .msg4001 import (
    build_4001_message,
    build_vehicle_payload,
    iso_timestamp,
)
from .types import (
    ClockMode,
    FleetStatus,
    VehicleState,
    VehicleStatus,  # IntegratedAirMobilityService.status() 의 반환 typing 위해 노출
    parse_hhmmss_to_s as _parse_hhmmss_to_s,
    s_to_hhmmss as _s_to_hhmmss,
)
from .vehicle_session import VehicleSession

logger = logging.getLogger(__name__)


PUBLISH_HZ = 10.0
PUBLISH_PERIOD_S = 1.0 / PUBLISH_HZ


# ClockMode / VehicleState / VehicleStatus / FleetStatus → services/types.py
# VehicleSession (+ _departure_origin_frame, parse_hhmmss_to_s, s_to_hhmmss) →
#   services/vehicle_session.py 및 services/types.py


class IntegratedAirMobilityService(VehicleModule):
    """Top-level 서비스 — 통신 + 도메인 한 클래스에 통합.

    ``VehicleModule`` 베이스가 6개 mid 의 빈 ``@on_receive`` stub 을 제공.
    이 클래스는 도메인 로직 (시계, 세션, 10Hz tick) 을 채우고 5개 핸들러를
    override 한다 (1002 SimulationSetup 은 베이스 stub 그대로).

    - 비행계획들을 등록
    - clock 모드 설정 (external / wall / manual)
    - 10 Hz 로 tick → 각 session.advance() → 4001 묶어서 publish (self.send)
    - 0002 heartbeat 1Hz: 부모 클래스가 자동
    """

    def __init__(
        self,
        *,
        target_ip: str = "127.0.0.1",
        ws_port: int = 8096,                 # SimulationState HTTP/WS 포트
        async_send: bool = True,
        config: Optional[SimulationConfig] = None,
        wind_seed: int = 20260121,
        month: int = 4,
    ) -> None:
        self.config = config or SimulationConfig(tick_s=PUBLISH_PERIOD_S)
        # 10 Hz 로 고정
        self.config.tick_s = PUBLISH_PERIOD_S

        self.wind_seed = int(wind_seed)
        self.month = int(month)
        self._lock = threading.RLock()

        # ── 통신 (VehicleModule 부모가 처리) ──────────────────────
        self.target_ip = str(target_ip)
        self.ws_port = int(ws_port)
        self._async_send = bool(async_send)
        super().__init__(
            server_url=f"ws://{self.target_ip}:{self.ws_port}/ws/dtam",
            heartbeat=True,
        )

        self._sessions: Dict[str, VehicleSession] = {}
        self._clock_mode: ClockMode = ClockMode.EXTERNAL
        self._running = False
        self._sim_time_s: float = 0.0
        self._wall_origin_wall: float = 0.0   # 실시간 기준점(모노토닉)
        self._wall_origin_sim: float = 0.0    # 해당 시점의 sim 시각
        self._pending_ext_time: Optional[float] = None
        self._ext_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.on_publish: Optional[Callable[[Dict[str, Any]], None]] = None

        # 수신 통계/기록
        self._rx_3001_count: int = 0
        self._rx_0003_count: int = 0
        self._rx_2002_count: int = 0
        self._rx_3002_count: int = 0
        self._rx_3003_count: int = 0
        self._last_rx_3001: str = ""
        self._last_rx_0003: str = ""
        self._last_rx_2002: str = ""
        self._last_rx_3002: str = ""
        self._last_rx_3003: str = ""
        # heartbeat 는 DtamModule(heartbeat=True) 가 자동 송신.
        # _last_heartbeat_error 는 호환을 위해 보존하되 DtamModule.stats 에서 채움.
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

    # ── 송신기 재설정 ──────────────────────────────────────────

    def reconfigure_publisher(
        self,
        *,
        target_ip: Optional[str] = None,
        ws_port: Optional[int] = None,
    ) -> None:
        """WebSocket 서버 endpoint 재설정."""
        if target_ip is not None:
            self.target_ip = str(target_ip)
        if ws_port is not None:
            self.ws_port = int(ws_port)
        # comm 이 콜백 등록까지 모두 보존한 채로 WS 만 재접속.
        self.comm.reconfigure_endpoint(target_ip=self.target_ip, ws_port=self.ws_port)

    # ── 시계 제어 ──────────────────────────────────────────────

    def set_clock_mode(self, mode: ClockMode | str) -> None:
        mode = ClockMode(mode) if isinstance(mode, str) else mode
        with self._lock:
            self._clock_mode = mode
            if mode == ClockMode.WALL:
                self._wall_origin_wall = time.monotonic()
                self._wall_origin_sim = float(self._sim_time_s)

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
            if self._clock_mode == ClockMode.WALL:
                self._wall_origin_wall = time.monotonic()
                self._wall_origin_sim = float(sim_time_s)

    def step_once(self, sim_time_s: float) -> Dict[str, Any]:
        """한 tick 만 실행 (MANUAL 모드). 전송된 4001 메시지 반환 (비어있을 수 있음)."""
        with self._lock:
            self._sim_time_s = float(sim_time_s)
        return self._run_tick(self._sim_time_s)

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
        self.stop()
        try:
            super().close()      # 부모 (DtamModule) — WS + heartbeat 정리
        except Exception:
            pass

    # ── 내부 ──────────────────────────────────────────────────

    def _loop(self) -> None:
        next_deadline = time.monotonic()
        while not self._stop_event.is_set():
            with self._lock:
                mode = self._clock_mode

            if mode == ClockMode.WALL:
                now = time.monotonic()
                sim_t = self._wall_origin_sim + (now - self._wall_origin_wall)
                with self._lock:
                    self._sim_time_s = float(sim_t)
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
                # 외부 시각 입력을 기다렸다가 tick 1회. 10 Hz 이상 들어와도 최대 10Hz 로 clamp.
                got = self._ext_event.wait(timeout=0.5)
                if self._stop_event.is_set():
                    break
                if not got:
                    continue
                self._ext_event.clear()
                with self._lock:
                    pending = self._pending_ext_time
                    self._pending_ext_time = None
                if pending is None:
                    continue
                with self._lock:
                    self._sim_time_s = float(pending)
                self._run_tick(float(pending))
            else:
                # MANUAL — 루프는 idle. stop 이 올 때까지 대기.
                if self._stop_event.wait(timeout=0.25):
                    break

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
            prev_alt = getattr(session, "_prev_alt_m", alt_m)
            climb_rate = (alt_m - prev_alt) / max(PUBLISH_PERIOD_S, 1e-6)
            session._prev_alt_m = alt_m  # type: ignore[attr-defined]

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
            )
            session.last_payload = payload
            vehicle_payloads[session.aircraft_id] = payload

        if not vehicle_payloads:
            return {}

        # 시뮬레이션 sim_time_s 를 UTC ISO 타임스탬프로 — 오늘 자정 기준으로 매핑
        ts = _sim_time_to_iso(sim_time_s)
        message = build_4001_message(vehicle_payloads, timestamp=ts)
        try:
            self.send("vehicle_status", message)     # 부모 DtamModule.send
        except Exception:
            logger.exception("vehicle_status send failed")
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
            running = self._running
            sim_t = float(self._sim_time_s)
            rx3 = self._rx_3001_count
            rx0 = self._rx_0003_count
            rx_exec = self._rx_2002_count
            rx_strategic = self._rx_3002_count
            rx_tactical = self._rx_3003_count
            last3 = self._last_rx_3001
            last0 = self._last_rx_0003
            last_exec = self._last_rx_2002
            last_strategic = self._last_rx_3002
            last_tactical = self._last_rx_3003
            heartbeat_error = self._last_heartbeat_error
        return FleetStatus(
            clock_mode=clock_mode,
            running=running,
            publisher_connected=self.connected,                  # DtamModule property
            publisher_error=self.stats.last_error or "",
            sim_time_s=sim_t,
            sim_time_hms=_s_to_hhmmss(sim_t),
            vehicles=[s.status() for s in sessions],
            rx_3001_count=rx3,
            rx_0003_count=rx0,
            rx_2002_count=rx_exec,
            rx_3002_count=rx_strategic,
            rx_3003_count=rx_tactical,
            last_rx_3001=last3,
            last_rx_0003=last0,
            last_rx_2002=last_exec,
            last_rx_3002=last_strategic,
            last_rx_3003=last_tactical,
            last_heartbeat_error=heartbeat_error,
        )

    # ── DTAM 수신 핸들러 ──────────────────────────────────────
    # 데코레이터는 가독성용 — base ``VehicleModule`` 이 이미 mid 매핑 보유.
    # mid 가 다르면 SDK 가 import 시점에 ``TypeError`` 로 잡아준다.
    # 1002 (SimulationSetup) 은 base 의 빈 stub 그대로 사용 (override 불필요).

    @on_receive("3001")
    def on_scheduled_flight(self, result: Any) -> None:
        """MSG 3001 수신 → 해당 비행체의 계획을 자동 등록/갱신.

        VehicleModule 의 빈 stub 을 override.
        planStatus == 'discarded' 면 해당 비행체 계획 제거.
        planStatus == 'superseded' 면 무시 (더 신선한 active 가 올 것).
        planVersion 이 기존보다 낮으면 무시.
        """
        try:
            raw = _result_raw(result)
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

    @on_receive("0003")
    def on_common_time_info(self, result: Any) -> None:
        """MSG 0003 수신 → simTime 을 시계로 주입.

        - 공통 시간은 권위 있는 시간 원천이므로 모드에 상관없이 ``_sim_time_s`` 갱신.
        - EXTERNAL 모드인 경우 추가로 ``feed_time_seconds`` 를 호출해
          서비스 루프가 1 tick 진행하고 4001 을 송출하도록 유도.
        """
        try:
            raw = _result_raw(result)
            sim_iso = raw.get("simTime") or getattr(result, "sim_time", "") or ""
            if not sim_iso:
                return
            sim_s = _iso_to_seconds_of_day(str(sim_iso))
            with self._lock:
                self._rx_0003_count += 1
                self._last_rx_0003 = str(sim_iso)
                self._sim_time_s = float(sim_s)
                mode = self._clock_mode
            if mode == ClockMode.EXTERNAL:
                self.feed_time_seconds(sim_s)
        except Exception:
            logger.exception("_on_common_time_info failed")

    @on_receive("2002")
    def on_dtam_execute(self, result: Any) -> None:
        try:
            raw = _result_raw(result)
            folder = str(raw.get("flightPlanFolderName") or "")
            with self._lock:
                self._rx_2002_count += 1
                self._last_rx_2002 = folder or str(raw)
            self.start()
            logger.info("2002 DTAM Execute received: flightPlanFolderName=%s", folder)
        except Exception:
            logger.exception("_on_dtam_execute failed")

    @on_receive("3002")
    def on_strategic_separation(self, result: Any) -> None:
        try:
            raw = _result_raw(result)
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

    @on_receive("3003")
    def on_tactical_separation(self, result: Any) -> None:
        try:
            raw = _result_raw(result)
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


def _result_raw(result: Any) -> Dict[str, Any]:
    """수신 콜백 인자를 raw dict 으로 정규화.

    DtamModule 은 ICD dataclass 인스턴스를 넘긴다 (parse_payload 결과).
    legacy 경로 (dict 직접, 또는 ``ReceiveResult.raw``) 와도 호환.
    """
    if isinstance(result, dict):
        return result
    raw = getattr(result, "raw", None)
    if isinstance(raw, dict):
        return raw
    # dataclass 인스턴스 → dict (재귀적으로 sub-dataclass 도 포함)
    import dataclasses as _dc
    if _dc.is_dataclass(result) and not isinstance(result, type):
        return _dc.asdict(result)
    return {}


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
