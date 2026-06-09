from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
DTAMSDK_ROOT = REPO_ROOT / "DTAMSDK"
for _path in (str(REPO_ROOT), str(DTAMSDK_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from VehicleModule.app.domain.dynamics.core.types import (  # noqa: E402
    Arrival,
    Departure,
    EnRouteSegment,
    FlightPlan,
    FlightTrajectoryPoint,
    LLA,
    Phase,
    SimulationConfig,
)
from VehicleModule.app.services.integrated_service import (  # noqa: E402
    ControlMode,
    IntegratedAirMobilityService,
    VehicleSession,
    _MockKp2AProvider,
)


ETOT_S = 6 * 60 * 60 + 30 * 60


def _plan(aircraft_id: str, fpn: int, *, lon_offset: float = 0.0) -> FlightPlan:
    start = LLA(37.50, 127.00 + lon_offset, 50.0)
    end = LLA(37.51, 127.01 + lon_offset, 120.0)
    return FlightPlan(
        flight_plan_number=fpn,
        aircraft_id=aircraft_id,
        departure=Departure(
            vertiport="DEP",
            std="06:30:00",
            dep_gate_number="G1",
            eobt="06:30:00",
            dep_fato_number="F1",
            etot="06:30:00",
        ),
        en_route=[
            EnRouteSegment(
                seq=1,
                phase=Phase.A,
                start_lla=start,
                end_lla=end,
                target_speed=20.0,
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


def _session(aircraft_id: str, fpn: int, *, lon_offset: float = 0.0) -> VehicleSession:
    session = VehicleSession(_plan(aircraft_id, fpn, lon_offset=lon_offset), config=SimulationConfig())
    session.trajectory = [
        FlightTrajectoryPoint(
            time_s=0.0,
            clock="06:30:00",
            phase="A",
            mode="gate_taxi",
            lat=37.50,
            lon=127.00 + lon_offset,
            alt_m=50.0,
            speed_mps=0.0,
            heading_deg=90.0,
            track_heading_deg=90.0,
            battery_pct=99.0,
        ),
        FlightTrajectoryPoint(
            time_s=10.0,
            clock="06:30:10",
            phase="B",
            mode="vertical_climb",
            lat=37.5001,
            lon=127.0001 + lon_offset,
            alt_m=60.0,
            speed_mps=12.0,
            heading_deg=90.0,
            track_heading_deg=90.0,
            battery_pct=98.8,
        ),
    ]
    session.trajectory_time_offset_s = 0.0
    session.project_point_to_pose_frame = lambda point, heading: None  # type: ignore[method-assign]
    return session


def _service() -> IntegratedAirMobilityService:
    service = IntegratedAirMobilityService.__new__(IntegratedAirMobilityService)
    service._lock = threading.RLock()
    service._sessions = {}
    service._control_mode = ControlMode.MISSION
    service._vehicle_control_modes = {}
    service._vehicle_dynamics_models = {}
    service._vehicle_provider_modes = {}
    service._manual_configs = {}
    service._manual_last_tick_wall = 0.0
    service._collision_responses_by_vehicle = {}
    service._collision_hold_payloads = {}
    service._mock_kp2a_provider = _MockKp2AProvider()
    return service


def test_control_modes_store_dynamics_and_provider_routing() -> None:
    service = _service()

    applied = service.set_vehicle_control_modes(
        default_mode=ControlMode.MISSION,
        vehicle_modes={"UAM0001": "mission", "UAM0002": "mission"},
        dynamics_by_aircraft={"UAM0001": "simple", "UAM0002": "highFidelity"},
        provider_by_aircraft={"UAM0002": "vfds-kp2a"},
    )

    assert applied["vehicleModes"] == {"UAM0001": "mission", "UAM0002": "mission"}
    assert applied["dynamicsByAircraft"]["UAM0001"] == "simple"
    assert applied["dynamicsByAircraft"]["UAM0002"] == "highFidelity"
    assert applied["providerByAircraft"]["UAM0001"] == "simple"
    assert applied["providerByAircraft"]["UAM0002"] == "vfds-kp2a"


def test_high_fidelity_rejects_non_autopilot_mode_and_rolls_back() -> None:
    service = _service()
    service.set_vehicle_control_modes(
        default_mode=ControlMode.MISSION,
        vehicle_modes={"UAM0002": "mission"},
        dynamics_by_aircraft={"UAM0002": "highFidelity"},
        provider_by_aircraft={"UAM0002": "vfds-kp2a"},
    )

    with pytest.raises(ValueError, match="highFidelity"):
        service.set_vehicle_control_modes(
            default_mode=ControlMode.MISSION,
            vehicle_modes={"UAM0002": "keyboard"},
            dynamics_by_aircraft={"UAM0002": "highFidelity"},
            provider_by_aircraft={"UAM0002": "vfds-kp2a"},
        )

    assert service._vehicle_control_modes["UAM0002"] == ControlMode.MISSION
    assert service._vehicle_dynamics_models["UAM0002"] == "highFidelity"


def test_run_tick_merges_simple_and_mock_high_fidelity_without_duplicate_source() -> None:
    simple = _session("UAM0001", 5151001)
    high = _session("UAM0002", 5151002, lon_offset=0.01)
    service = _service()
    service._sessions = {"UAM0001": simple, "UAM0002": high}
    service.set_vehicle_control_modes(
        default_mode=ControlMode.MISSION,
        vehicle_modes={"UAM0001": "mission", "UAM0002": "mission"},
        dynamics_by_aircraft={"UAM0001": "simple", "UAM0002": "highFidelity"},
        provider_by_aircraft={"UAM0002": "vfds-kp2a"},
    )

    message = service._run_tick(ETOT_S + 1.0, publish=False)

    assert set(message) == {"timestamp", "UAM0001", "UAM0002"}
    assert service._mock_kp2a_provider.frames == {"UAM0002": 1}
    assert "_provider" not in message["UAM0002"]
    assert high.last_payload is not None
    assert high.last_payload["_provider"] == "vfds-kp2a"
    assert simple.last_payload is not None
    assert "_provider" not in simple.last_payload
