from __future__ import annotations

import sys
import threading
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DTAMSDK_ROOT = REPO_ROOT / "DTAMSDK"
for _path in (str(REPO_ROOT), str(DTAMSDK_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from VehicleModule.app.domain.dynamics.core.types import (
    Arrival,
    Departure,
    EnRouteSegment,
    FlightPlan,
    FlightTrajectoryPoint,
    LLA,
    Phase,
    SimulationConfig,
)
from VehicleModule.app.services.integrated_service import (
    IntegratedAirMobilityService,
    VehicleSession,
    VehicleState,
)


ETOT_S = 6 * 60 * 60 + 35 * 60


def _plan() -> FlightPlan:
    start = LLA(37.50, 127.00, 50.0)
    end = LLA(37.51, 127.01, 120.0)
    return FlightPlan(
        flight_plan_number=5151552,
        aircraft_id="UAM0001",
        departure=Departure(
            vertiport="DEP",
            std="06:35:00",
            dep_gate_number="G1",
            eobt="06:35:00",
            dep_fato_number="F1",
            etot="06:35:00",
        ),
        en_route=[
            EnRouteSegment(
                seq=1,
                phase=Phase.A,
                start_lla=start,
                end_lla=end,
                target_speed=10.0,
            )
        ],
        arrival=Arrival(
            vertiport="ARR",
            sta="06:45:00",
            arr_gate_number="G2",
            eibt="06:45:00",
            arr_fato_number="F2",
            eldt="06:45:00",
        ),
    )


def _session() -> VehicleSession:
    session = VehicleSession(_plan(), config=SimulationConfig())
    session.trajectory = [
        FlightTrajectoryPoint(
            time_s=0.0,
            clock="06:35:00",
            phase="A",
            mode="gate_taxi",
            lat=37.50,
            lon=127.00,
            alt_m=50.0,
            speed_mps=3.0,
            heading_deg=90.0,
            track_heading_deg=90.0,
            battery_pct=99.0,
        ),
        FlightTrajectoryPoint(
            time_s=10.0,
            clock="06:35:10",
            phase="B",
            mode="vertical_climb",
            lat=37.5001,
            lon=127.0001,
            alt_m=60.0,
            speed_mps=8.0,
            heading_deg=90.0,
            track_heading_deg=90.0,
            battery_pct=98.8,
        ),
    ]
    session.trajectory_time_offset_s = 0.0
    session.project_point_to_pose_frame = lambda point, heading: None  # type: ignore[method-assign]
    return session


def _service_with_sessions(*sessions: VehicleSession) -> IntegratedAirMobilityService:
    service = IntegratedAirMobilityService.__new__(IntegratedAirMobilityService)
    service._lock = threading.RLock()
    service._sessions = {session.aircraft_id: session for session in sessions}
    service._collision_responses_by_vehicle = {}
    service._collision_hold_payloads = {}
    return service


def test_waiting_before_etot_returns_zero_speed_hold_point() -> None:
    session = _session()

    point = session.advance(ETOT_S - 60.0)

    assert point is not None
    assert session.state == VehicleState.WAITING
    assert session.elapsed_s == 0.0
    assert session.start_sim_time_s is None
    assert session.last_emit_target_time_s is None
    assert session.last_point is None
    assert point.speed_mps == 0.0
    assert point.mode == "WAITING"
    assert point.lat == session.trajectory[0].lat
    assert point.lon == session.trajectory[0].lon


def test_run_tick_includes_waiting_aircraft_hold_4001_payload() -> None:
    session = _session()
    service = _service_with_sessions(session)

    message = service._run_tick(ETOT_S - 60.0, publish=False)

    assert "UAM0001" in message
    payload = message["UAM0001"]
    assert session.state == VehicleState.WAITING
    assert session.start_sim_time_s is None
    assert session.last_payload is not None
    assert session.last_payload["gps"] == payload["gps"]
    assert payload["gps"]["velocity_north"] == 0.0
    assert payload["gps"]["velocity_east"] == 0.0
    assert payload["gps"]["velocity_down"] == 0.0
    assert payload["energy"]["battery_pct"] == 99.0


def test_etot_first_tick_starts_at_elapsed_zero() -> None:
    session = _session()
    session.advance(ETOT_S - 1.0)

    point = session.advance(ETOT_S)

    assert point is not None
    assert session.state == VehicleState.ACTIVE
    assert session.start_sim_time_s == ETOT_S
    assert session.elapsed_s == 0.0
    assert session.last_emit_target_time_s == 0.0
    assert point.time_s == 0.0


def test_rewind_before_etot_resets_runtime_state_to_waiting() -> None:
    session = _session()
    session.advance(ETOT_S)
    session.advance(ETOT_S + 1.0)

    hold = session.advance(ETOT_S - 0.5)

    assert hold is not None
    assert hold.speed_mps == 0.0
    assert session.state == VehicleState.WAITING
    assert session.start_sim_time_s is None
    assert session.last_emit_target_time_s is None
    assert session.trajectory_index == 0
    assert session.elapsed_s == 0.0


def test_completed_session_rewinds_when_time_moves_back_inside_flight() -> None:
    session = _session()
    session.state = VehicleState.COMPLETED
    session.start_sim_time_s = float(ETOT_S)
    session.trajectory_index = len(session.trajectory) - 1
    session.last_emit_target_time_s = session.trajectory[-1].time_s

    point = session.advance(ETOT_S + 2.0)

    assert point is not None
    assert session.state == VehicleState.ACTIVE
    assert session.elapsed_s >= 0.0
