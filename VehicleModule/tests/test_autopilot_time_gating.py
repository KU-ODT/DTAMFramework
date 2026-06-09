"""Regression coverage for simple Autopilot ETOT time gating.

Run directly with:
    python -m unittest discover -s VehicleModule/tests -p test_autopilot_time_gating.py

The test injects a tiny precomputed trajectory into ``VehicleSession`` so it
validates the Autopilot session gate without running the full simpleDynamics
simulator.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DTAMSDK_ROOT = REPO_ROOT / "DTAMSDK"
for path in (str(REPO_ROOT), str(DTAMSDK_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


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
    PUBLISH_PERIOD_S,
    VehicleSession,
    VehicleState,
)


ETOT_TEXT = "09:10:00"
ETOT_S = 9 * 3600 + 10 * 60
TRAJECTORY_OFFSET_S = 100.0


def _point(time_s: float, *, lat: float = 37.0, lon: float = 127.0) -> FlightTrajectoryPoint:
    return FlightTrajectoryPoint(
        time_s=time_s,
        clock="00:00:00",
        phase="B",
        mode="vertical_climb",
        lat=lat,
        lon=lon,
        alt_m=10.0,
        speed_mps=5.0,
        heading_deg=90.0,
        track_heading_deg=90.0,
    )


def _session_with_precomputed_trajectory() -> VehicleSession:
    start = LLA(37.0, 127.0, 10.0)
    end = LLA(37.0001, 127.0001, 10.0)
    plan = FlightPlan(
        flight_plan_number=42,
        aircraft_id="UAM_TEST_ETOT",
        departure=Departure(
            vertiport="DEP",
            std=ETOT_TEXT,
            dep_gate_number="G1",
            eobt=ETOT_TEXT,
            dep_fato_number="F1",
            etot=ETOT_TEXT,
        ),
        en_route=[
            EnRouteSegment(
                seq=1,
                phase=Phase.B,
                start_lla=start,
                end_lla=end,
                target_speed=5.0,
            )
        ],
        arrival=Arrival(
            vertiport="ARR",
            sta="09:20:00",
            arr_gate_number="G2",
            eibt="09:20:00",
            arr_fato_number="F2",
            eldt="09:20:00",
        ),
    )
    session = VehicleSession(plan, config=SimulationConfig(tick_s=PUBLISH_PERIOD_S))
    session.trajectory = [
        _point(TRAJECTORY_OFFSET_S, lat=start.lat, lon=start.lon),
        _point(TRAJECTORY_OFFSET_S + 1.0, lat=end.lat, lon=end.lon),
    ]
    session.trajectory_time_offset_s = TRAJECTORY_OFFSET_S
    return session


class AutopilotTimeGatingTest(unittest.TestCase):
    def test_waits_until_etot_starts_at_zero_and_resets_to_waiting(self) -> None:
        session = _session_with_precomputed_trajectory()

        before_etot_point = session.advance(ETOT_S - 0.1)

        self.assertIsNotNone(before_etot_point)
        self.assertEqual(before_etot_point.mode, "WAITING")
        self.assertEqual(before_etot_point.speed_mps, 0.0)
        self.assertEqual(before_etot_point.time_s, TRAJECTORY_OFFSET_S)
        self.assertEqual(session.state, VehicleState.WAITING)
        self.assertEqual(session.elapsed_s, 0.0)
        self.assertIsNone(session.last_point)
        self.assertIsNone(session.start_sim_time_s)
        self.assertIsNone(session.last_emit_target_time_s)

        etot_point = session.advance(ETOT_S)

        self.assertIsNotNone(etot_point)
        self.assertEqual(session.state, VehicleState.ACTIVE)
        self.assertEqual(session.start_sim_time_s, float(ETOT_S))
        self.assertEqual(session.elapsed_s, 0.0)
        self.assertEqual(session.last_emit_target_time_s, TRAJECTORY_OFFSET_S)
        self.assertAlmostEqual(etot_point.time_s, TRAJECTORY_OFFSET_S)

        session.reset()

        self.assertEqual(session.state, VehicleState.WAITING)
        self.assertEqual(session.elapsed_s, 0.0)
        self.assertIsNone(session.last_point)
        self.assertIsNone(session.start_sim_time_s)
        self.assertIsNone(session.last_emit_target_time_s)

        after_reset_before_etot_point = session.advance(ETOT_S - 0.1)

        self.assertIsNotNone(after_reset_before_etot_point)
        self.assertEqual(after_reset_before_etot_point.mode, "WAITING")
        self.assertEqual(after_reset_before_etot_point.speed_mps, 0.0)
        self.assertEqual(after_reset_before_etot_point.time_s, TRAJECTORY_OFFSET_S)
        self.assertEqual(session.state, VehicleState.WAITING)
        self.assertEqual(session.elapsed_s, 0.0)
        self.assertIsNone(session.start_sim_time_s)


if __name__ == "__main__":
    unittest.main()
