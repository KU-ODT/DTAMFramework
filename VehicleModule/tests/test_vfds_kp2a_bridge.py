from __future__ import annotations

import sys
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DTAMSDK_ROOT = REPO_ROOT / "DTAMSDK"
for _path in (str(REPO_ROOT), str(DTAMSDK_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from VehicleModule.app.domain.dynamics.core.types import SimulationConfig  # noqa: E402
from VehicleModule.app.services.integrated_service import (  # noqa: E402
    ClockMode,
    ControlMode,
    DEFAULT_SIMULATION_START_S,
    IntegratedAirMobilityService,
    _MockKp2AProvider,
    _s_to_hhmmss,
)
from VehicleModule.app.services.vfds_client import VfdsHttpResult  # noqa: E402
from VehicleModule.app.services.vfds_telemetry import VfdsTelemetryReceiver  # noqa: E402
from dtam_client.schema import parse_payload  # noqa: E402


def _raw_plan(
    aircraft_id: str = "UAM0001",
    fpn: int = 5151552,
    *,
    std: str = "06:35:00",
    etot: str = "06:40:00",
) -> Dict[str, Any]:
    return {
        "flightPlanNumber": fpn,
        "aircraftId": aircraft_id,
        "planVersion": 7,
        "planStatus": "active",
        "departure": {
            "vertiport": "DEP",
            "std": std,
            "depGateNumber": "G1",
            "eobt": std,
            "depFatoNumber": "F1",
            "etot": etot,
        },
        "enRoute": [
            {
                "seq": 1,
                "phase": "A",
                "startLLA": {"lat": 37.50, "lon": 127.00, "alt": 50.0},
                "endLLA": {"lat": 37.501, "lon": 127.001, "alt": 80.0},
                "targetSpeed": 18.0,
            }
        ],
        "arrival": {
            "vertiport": "ARR",
            "sta": "06:50:00",
            "arrGateNumber": "G2",
            "eibt": "06:50:00",
            "arrFatoNumber": "F2",
            "eldt": "06:49:00",
        },
    }


class FakeVfdsClient:
    def __init__(self) -> None:
        self.health_calls = 0
        self.submitted_payloads: List[Dict[str, Any]] = []
        self.deleted_fpns: List[int] = []
        self.time_posts: List[Tuple[str, str]] = []

    def health(self) -> VfdsHttpResult:
        self.health_calls += 1
        return VfdsHttpResult(True, "GET", "http://fake/health", 200, {"status": "ok"})

    def submit_mission(self, payload: Dict[str, Any]) -> VfdsHttpResult:
        self.submitted_payloads.append(deepcopy(payload))
        return VfdsHttpResult(True, "POST", "http://fake/api/v1/missions/realtime", 202, {"status": "QUEUED"})

    def delete_mission(self, flight_plan_number: int) -> VfdsHttpResult:
        self.deleted_fpns.append(int(flight_plan_number))
        return VfdsHttpResult(True, "DELETE", f"http://fake/api/v1/missions/{int(flight_plan_number)}", 200, {"status": "success"})

    def post_time_hhmmss(self, hhmmss: str, *, source: str = "VehicleModule") -> VfdsHttpResult:
        self.time_posts.append((str(hhmmss), str(source)))
        return VfdsHttpResult(True, "POST", "http://fake/api/v1/time", 202, {"status": "ok", "time": hhmmss})

    def get_telemetry_snapshot(self) -> VfdsHttpResult:
        return VfdsHttpResult(True, "GET", "http://fake/api/v1/telemetry", 200, {"total": 0, "aircraft": []})

    def websocket_url(self, path: str = "/api/v1/ws/live") -> str:
        return f"ws://fake{path}"


def _service(fake: FakeVfdsClient) -> IntegratedAirMobilityService:
    service = IntegratedAirMobilityService.__new__(IntegratedAirMobilityService)
    service.config = SimulationConfig(tick_s=1.0 / 30.0)
    service.wind_seed = 20260121
    service.month = 4
    service._lock = threading.RLock()
    service._sessions = {}
    service._clock_mode = ClockMode.EXTERNAL
    service._control_mode = ControlMode.MISSION
    service._vehicle_control_modes = {}
    service._vehicle_dynamics_models = {}
    service._vehicle_provider_modes = {}
    service._manual_configs = {}
    service._manual_last_tick_wall = 0.0
    service._collision_responses_by_vehicle = {}
    service._collision_hold_payloads = {}
    service._collisions_by_vehicle = {}
    service._last_collision_event = {}
    service._manual_last_payloads = {}
    receiver = VfdsTelemetryReceiver(fake, prefer_websocket=False, poll_period_s=3600.0)
    service._mock_kp2a_provider = _MockKp2AProvider(
        client=fake,
        async_time_feed=False,
        telemetry_receiver=receiver,
    )
    service._sim_time_s = float(DEFAULT_SIMULATION_START_S)
    service._pending_ext_time = None
    service._last_external_tick_wall = 0.0
    service._external_time_initialized = True
    service._play_state = "pause"
    service._playback_speed_x = 1.0
    service._running = False
    service._rx_2002_count = 0
    service._rx_4103_count = 0
    service._last_rx_2002 = ""
    service._last_rx_4103 = ""
    return service


def _register_high_fidelity_plan(service: IntegratedAirMobilityService, raw: Dict[str, Any]) -> None:
    service.add_plan(raw)
    service.set_vehicle_control_modes(
        default_mode=ControlMode.MISSION,
        vehicle_modes={raw["aircraftId"]: "mission"},
        dynamics_by_aircraft={raw["aircraftId"]: "highFidelity"},
        provider_by_aircraft={raw["aircraftId"]: "vfds-kp2a"},
    )


def test_2002_submit_uses_sanitized_3001_payload_and_preserves_std_etot() -> None:
    fake = FakeVfdsClient()
    service = _service(fake)
    raw = _raw_plan(std="06:35:00", etot="06:40:00")
    _register_high_fidelity_plan(service, raw)

    results = service._submit_high_fidelity_missions(reason="unit")

    assert results["UAM0001"]["ok"] is True
    assert fake.health_calls == 1
    assert len(fake.submitted_payloads) == 1
    payload = fake.submitted_payloads[0]
    assert payload["flightPlanNumber"] == 5151552
    assert payload["aircraftId"] == "UAM0001"
    assert payload["departure"]["std"] == "06:35:00"
    assert payload["departure"]["etot"] == "06:40:00"
    assert "planVersion" not in payload
    assert "planStatus" not in payload
    assert service._mock_kp2a_provider.submitted == {"UAM0001": 5151552}


def test_high_fidelity_time_feed_posts_hhmmss_to_vfds() -> None:
    fake = FakeVfdsClient()
    service = _service(fake)
    raw = _raw_plan()
    _register_high_fidelity_plan(service, raw)

    service._feed_high_fidelity_time(DEFAULT_SIMULATION_START_S, force=True, source="unit-test")

    assert fake.time_posts == [(_s_to_hhmmss(DEFAULT_SIMULATION_START_S), "unit-test")]
    assert service._mock_kp2a_provider.last_time_hms == "06:30:00"


def test_simple_autopilot_starts_at_std_even_when_etot_is_later() -> None:
    fake = FakeVfdsClient()
    service = _service(fake)
    raw = _raw_plan(std="06:31:00", etot="06:32:00")
    service.add_plan(raw)

    before = service._run_tick(DEFAULT_SIMULATION_START_S + 59.0, publish=False)
    state_before = service._sessions["UAM0001"].state
    at_std = service._run_tick(DEFAULT_SIMULATION_START_S + 61.0, publish=False)
    state_after = service._sessions["UAM0001"].state

    assert before["UAM0001"]["speedMps"] == pytest.approx(0.0)
    assert state_before.value == "waiting"
    assert service._sessions["UAM0001"].start_gate_s == pytest.approx(DEFAULT_SIMULATION_START_S + 60.0)
    assert state_after.value == "active"
    assert at_std["UAM0001"]["currentWaypointId"]


def test_remove_plan_deletes_vfds_mission_by_flight_plan_number() -> None:
    fake = FakeVfdsClient()
    service = _service(fake)
    raw = _raw_plan(fpn=5151666)
    _register_high_fidelity_plan(service, raw)

    assert service.remove_plan("UAM0001") is True

    assert fake.deleted_fpns == [5151666]
    assert "UAM0001" not in service._sessions


def test_2002_cleanup_resubmit_and_holds_time_at_0630_until_play() -> None:
    fake = FakeVfdsClient()
    service = _service(fake)
    raw = _raw_plan(fpn=5151777)
    _register_high_fidelity_plan(service, raw)
    service._mock_kp2a_provider.submitted["UAM0001"] = 5151777
    service._sim_time_s = 7 * 60 * 60
    service._play_state = "play"

    service.on_dtam_execute({"flightPlanFolderName": "session4"})

    assert fake.deleted_fpns == [5151777]
    assert len(fake.submitted_payloads) == 1
    assert fake.time_posts[-1] == ("06:30:00", "VehicleModule:2002")
    assert service._play_state == "pause"
    assert service._sim_time_s == float(DEFAULT_SIMULATION_START_S)


def test_fresh_vfds_telemetry_maps_to_4001_payload_units_and_origin() -> None:
    fake = FakeVfdsClient()
    service = _service(fake)
    raw = _raw_plan(etot="06:30:00")
    _register_high_fidelity_plan(service, raw)
    session = service._sessions["UAM0001"]

    service._mock_kp2a_provider.telemetry.ingest(
        {
            "aircraftId": "UAM0001",
            "flightPlanNumber": 5151552,
            "ts": "2026-05-19T06:30:01.000Z",
            "missionState": "EXECUTING",
            "phase": "A",
            "seq": 1,
            "position": {
                "lat": 37.5005,
                "lon": 127.0005,
                "alt": 75.0,
                # VFDS NED can use a mission HOME origin that differs from
                # DTAM's session origin.  Valid LLA should win over this value.
                "north": 9999.0,
                "east": 9999.0,
                "down": -9999.0,
            },
            "attitude": {"roll": 10.0, "pitch": -5.0, "yaw": 90.0},
            "actuator": {
                "tilt_left": 0.95,
                "tilt_right": 0.9,
                "aileron": 3.2,
                "rudder_left": -5.1,
                "rudder_right": 2.8,
            },
            "motorRpm": [1000.0, 1100.0, 1200.0, 1300.0],
            "velocityNed": {"north": 10.0, "east": 0.0, "down": 0.0},
        },
        source="unit",
    )

    message = service._run_tick(DEFAULT_SIMULATION_START_S + 1.0, publish=False)

    parse_payload("4001", message)
    payload = message["UAM0001"]
    session._ensure_trajectory()
    first = session.trajectory[0]
    vfds_point = deepcopy(first)
    # KP2A GPS is kept as WGS84 truth, but the 4001 position sent to Unreal
    # must use the same DT World/ODT visual pose frame as simple/autopilot.
    from dataclasses import replace
    vfds_point = replace(first, lat=37.5005, lon=127.0005, alt_m=75.0, time_s=DEFAULT_SIMULATION_START_S + 1.0)
    pose_projection = session.project_point_to_pose_frame(vfds_point, 0.0)
    assert isinstance(pose_projection, dict)
    expected_position = pose_projection["relative_position"]
    assert payload["position"]["north"] == pytest.approx(expected_position["north"], abs=0.2)
    assert payload["position"]["east"] == pytest.approx(expected_position["east"], abs=0.2)
    assert payload["position"]["down"] == pytest.approx(expected_position["down"], abs=0.2)
    assert payload["position"]["north"] != pytest.approx(9999.0)
    assert payload["headingDeg"] == pytest.approx(0.0, abs=1e-6)
    assert payload["attitude"]["roll"] == pytest.approx(0.1745329, rel=1e-5)
    assert payload["attitude"]["pitch"] == pytest.approx(-0.0872665, rel=1e-5)
    assert payload["actuator"]["tilt_left"] == pytest.approx(0.95)
    assert payload["actuator"]["rudder_left"] == pytest.approx(-5.1)
    assert payload["propulsion"]["motor_rpm"] == [1000.0, 1100.0, 1200.0, 1300.0]
    assert payload["navigation"]["missionState"] == "EXECUTING"
    assert payload["navigation"]["positionSource"] == "lla-odt-pose-frame"
    assert "vfds" not in payload
    assert service._mock_kp2a_provider.telemetry_used == {"UAM0001": 1}
    assert session.last_payload is not None
    assert session.last_payload["_provider_mode"] == "vfds-telemetry"
    assert session.last_payload["_vfds"]["positionSource"] == "lla-odt-pose-frame"
    assert session.last_payload["_vfds"]["rawYawDeg"] == pytest.approx(90.0)
    assert session.last_payload["_vfds"]["headingDeg"] == pytest.approx(0.0)


def test_vfds_track_heading_prefers_lla_motion_and_holds_previous_over_raw_yaw() -> None:
    fake = FakeVfdsClient()
    service = _service(fake)
    raw = _raw_plan(etot="06:30:00")
    _register_high_fidelity_plan(service, raw)
    receiver = service._mock_kp2a_provider.telemetry

    receiver.ingest(
        {
            "aircraftId": "UAM0001",
            "flightPlanNumber": 5151552,
            "ts": "2026-05-19T06:30:01.000Z",
            "missionState": "EXECUTING",
            "phase": "A",
            "seq": 1,
            "position": {"lat": 37.5000, "lon": 127.0000, "alt": 75.0},
            # Raw provider yaw can be 90 deg off from GPS track.
            "attitude": {"roll": 0.0, "pitch": 0.0, "yaw": 90.0},
        },
        source="unit",
    )
    service._run_tick(DEFAULT_SIMULATION_START_S + 1.0, publish=False)

    receiver.ingest(
        {
            "aircraftId": "UAM0001",
            "flightPlanNumber": 5151552,
            "ts": "2026-05-19T06:30:02.000Z",
            "missionState": "EXECUTING",
            "phase": "A",
            "seq": 1,
            "position": {"lat": 37.5010, "lon": 127.0000, "alt": 75.0},
            "attitude": {"roll": 0.0, "pitch": 0.0, "yaw": 90.0},
        },
        source="unit",
    )
    northbound = service._run_tick(DEFAULT_SIMULATION_START_S + 2.0, publish=False)["UAM0001"]
    assert min(abs(northbound["trackHeadingDeg"]), abs(northbound["trackHeadingDeg"] - 360.0)) <= 1.0
    assert min(abs(northbound["headingDeg"]), abs(northbound["headingDeg"] - 360.0)) <= 1.0
    northbound_debug = service._sessions["UAM0001"].last_payload["_vfds"]
    assert min(abs(northbound_debug["motionTrackHeadingDeg"]), abs(northbound_debug["motionTrackHeadingDeg"] - 360.0)) <= 1.0

    # Duplicate/no-motion frame should not fall back to raw yaw or provider-frame
    # velocity.  VFDS velocity can be 90 deg off from GPS track, so holding the
    # last GPS-motion track prevents Operation icon flicker.
    receiver.ingest(
        {
            "aircraftId": "UAM0001",
            "flightPlanNumber": 5151552,
            "ts": "2026-05-19T06:30:03.000Z",
            "missionState": "EXECUTING",
            "phase": "A",
            "seq": 1,
            "position": {"lat": 37.5010, "lon": 127.0000, "alt": 75.0},
            "attitude": {"roll": 0.0, "pitch": 0.0, "yaw": 90.0},
            "velocityNed": {"north": 0.0, "east": 10.0, "down": 0.0},
        },
        source="unit",
    )
    held = service._run_tick(DEFAULT_SIMULATION_START_S + 3.0, publish=False)["UAM0001"]
    assert min(abs(held["trackHeadingDeg"]), abs(held["trackHeadingDeg"] - 360.0)) <= 1.0
    assert min(abs(held["headingDeg"]), abs(held["headingDeg"] - 360.0)) <= 1.0
    held_debug = service._sessions["UAM0001"].last_payload["_vfds"]
    assert min(abs(held_debug["heldTrackHeadingDeg"]), abs(held_debug["heldTrackHeadingDeg"] - 360.0)) <= 1.0
    assert held_debug["velocityTrackHeadingDeg"] == pytest.approx(90.0)
    assert held_debug["ignoredVelocityTrackHeadingDeg"] == pytest.approx(90.0)


def test_stale_vfds_telemetry_holds_last_frame_before_fallback() -> None:
    fake = FakeVfdsClient()
    service = _service(fake)
    raw = _raw_plan(etot="06:30:00")
    _register_high_fidelity_plan(service, raw)
    receiver = service._mock_kp2a_provider.telemetry
    receiver.stale_after_s = 0.25
    receiver.ingest(
        {
            "aircraftId": "UAM0001",
            "flightPlanNumber": 5151552,
            "ts": "2026-05-19T06:30:01.000Z",
            "missionState": "EXECUTING",
            "phase": "A",
            "seq": 1,
            "position": {"lat": 37.5005, "lon": 127.0005, "alt": 75.0},
            "attitude": {"roll": 0.0, "pitch": 0.0, "yaw": 45.0},
            "actuator": {},
            "motorRpm": [1000.0, 1000.0, 1000.0, 1000.0],
        },
        source="unit",
    )

    first = service._run_tick(DEFAULT_SIMULATION_START_S + 1.0, publish=False)
    with receiver._lock:  # test-only fast-forward to stale age
        receiver._latest["UAM0001"]["_received_wall_s"] = time.monotonic() - 10.0

    second = service._run_tick(DEFAULT_SIMULATION_START_S + 2.0, publish=False)

    assert second["UAM0001"]["position"] == first["UAM0001"]["position"]
    assert second["UAM0001"]["attitude"] == first["UAM0001"]["attitude"]
    assert service._mock_kp2a_provider.telemetry_stale_holds == {"UAM0001": 1}
    assert service._sessions["UAM0001"].last_payload["_provider_mode"] == "vfds-stale-hold"


def test_out_of_order_vfds_telemetry_is_dropped() -> None:
    fake = FakeVfdsClient()
    receiver = VfdsTelemetryReceiver(fake, prefer_websocket=False)

    assert receiver.ingest(
        {
            "aircraftId": "UAM0001",
            "ts": "2026-05-19T06:30:05.000Z",
            "position": {"lat": 37.5, "lon": 127.0, "alt": 50.0},
        },
        source="unit",
    ) == 1
    assert receiver.ingest(
        {
            "aircraftId": "UAM0001",
            "ts": "2026-05-19T06:30:01.000Z",
            "position": {"lat": 38.0, "lon": 128.0, "alt": 999.0},
        },
        source="unit",
    ) == 0

    latest = receiver.latest("UAM0001")
    assert latest is not None
    assert latest["position"]["lat"] == pytest.approx(37.5)
    assert receiver.snapshot()["dropped_count"] == 1


def test_reset_marker_drops_pre_reset_remote_telemetry_snapshot() -> None:
    fake = FakeVfdsClient()
    receiver = VfdsTelemetryReceiver(fake, prefer_websocket=False)
    reset_epoch_s = datetime(2026, 5, 20, 6, 31, 0, tzinfo=timezone.utc).timestamp()

    receiver.mark_reset("UAM0001", source_epoch_s=reset_epoch_s)

    assert receiver.ingest(
        {
            "aircraftId": "UAM0001",
            "ts": "2026-05-20T06:30:59.000Z",
            "position": {"lat": 37.5, "lon": 127.0, "alt": 50.0},
        },
        source="poll",
    ) == 0
    assert receiver.ingest(
        {
            "aircraftId": "UAM0001",
            "ts": "2026-05-20T06:31:01.000Z",
            "position": {"lat": 37.6, "lon": 127.1, "alt": 60.0},
        },
        source="poll",
    ) == 1

    latest = receiver.latest("UAM0001")
    assert latest is not None
    assert latest["position"]["lat"] == pytest.approx(37.6)
    assert receiver.snapshot()["dropped_count"] == 1


def test_high_fidelity_collision_abort_holds_payload_and_deletes_vfds_mission() -> None:
    fake = FakeVfdsClient()
    service = _service(fake)
    raw = _raw_plan(fpn=5151888, etot="06:30:00")
    _register_high_fidelity_plan(service, raw)
    service._mock_kp2a_provider.submitted["UAM0001"] = 5151888
    receiver = service._mock_kp2a_provider.telemetry
    receiver.ingest(
        {
            "aircraftId": "UAM0001",
            "flightPlanNumber": 5151888,
            "ts": "2026-05-20T06:30:01.000Z",
            "missionState": "EXECUTING",
            "phase": "A",
            "seq": 1,
            "position": {"lat": 37.5005, "lon": 127.0005, "alt": 75.0},
            "attitude": {"roll": 0.0, "pitch": 0.0, "yaw": 45.0},
            "actuator": {},
            "motorRpm": [1500.0, 1500.0, 1500.0, 1500.0],
        },
        source="unit",
    )
    first = service._run_tick(DEFAULT_SIMULATION_START_S + 1.0, publish=False)

    service.on_vehicle_collision_event(
        {
            "eventId": "COLLISION-1",
            "aircraftId": "UAM0001",
            "objectName": "building",
            "hasCollided": True,
            "severity": "fatal",
            "recommendedAction": "abort",
            "impactSpeedMps": 12.0,
        }
    )
    receiver.ingest(
        {
            "aircraftId": "UAM0001",
            "flightPlanNumber": 5151888,
            "ts": "2026-05-20T06:30:02.000Z",
            "missionState": "EXECUTING",
            "phase": "A",
            "seq": 1,
            "position": {"lat": 37.7000, "lon": 127.2000, "alt": 150.0},
            "attitude": {"roll": 0.0, "pitch": 0.0, "yaw": 90.0},
            "actuator": {},
            "motorRpm": [2000.0, 2000.0, 2000.0, 2000.0],
        },
        source="unit",
    )

    second = service._run_tick(DEFAULT_SIMULATION_START_S + 2.0, publish=False)

    assert fake.deleted_fpns == [5151888]
    assert "UAM0001" not in service._mock_kp2a_provider.submitted
    assert second["UAM0001"]["position"] == first["UAM0001"]["position"]
    assert second["UAM0001"]["collision"]["responseMode"] == "abort"
    assert second["UAM0001"]["propulsion"]["motor_rpm"] == [0.0, 0.0, 0.0, 0.0]
    assert service._sessions["UAM0001"].last_error.startswith("collision abort")


def test_vfds_poll_failure_is_captured_with_backoff_instead_of_raising() -> None:
    class FailingTelemetryClient(FakeVfdsClient):
        def get_telemetry_snapshot(self) -> VfdsHttpResult:
            raise RuntimeError("VFDS offline")

    receiver = VfdsTelemetryReceiver(FailingTelemetryClient(), prefer_websocket=False)

    receiver._poll_once()

    snapshot = receiver.snapshot()
    assert snapshot["error_count"] == 1
    assert "VFDS offline" in snapshot["last_error"]
    assert snapshot["next_poll_attempt_in_s"] > 0.0


def test_vfds_result_redacts_url_credentials_and_tokens() -> None:
    result = VfdsHttpResult(
        True,
        "GET",
        "http://user:secret@example.com:8000/api/v1/telemetry?access_token=abc123&ok=1",
        200,
        {
            "status": "ok",
            "password": "body-secret",
            "nested": {"token": "nested-token", "url": "http://u:p@example.com/path?api_key=key123"},
        },
        "failed http://u:p@example.com/path?token=errtoken",
    )

    wire = result.to_dict()

    assert "user" not in wire["url"]
    assert "secret" not in wire["url"]
    assert "abc123" not in wire["url"]
    assert "access_token=%2A%2A%2A" in wire["url"] or "access_token=***" in wire["url"]
    assert "ok=1" in wire["url"]
    assert wire["body"]["password"] == "***"
    assert wire["body"]["nested"]["token"] == "***"
    assert "key123" not in wire["body"]["nested"]["url"]
    assert "errtoken" not in wire["error"]
