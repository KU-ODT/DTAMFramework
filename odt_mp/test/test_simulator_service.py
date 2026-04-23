from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.simulator_service import _trim_airsim_sync_trajectory
from modules.simpleDynamics.core.types import FlightTrajectoryPoint


def _point(phase: str, index: int) -> FlightTrajectoryPoint:
    return FlightTrajectoryPoint(
        time_s=float(index),
        clock=f"00:00:{index:02d}",
        phase=phase,
        mode="test",
        lat=37.0 + (index * 0.001),
        lon=127.0 + (index * 0.001),
        alt_m=50.0 + index,
        speed_mps=10.0,
        heading_deg=90.0,
        track_heading_deg=90.0,
    )


class SimulatorServiceTests(unittest.TestCase):
    def test_trim_airsim_sync_trajectory_skips_ground_taxi_segments(self) -> None:
        trajectory = [
            _point("A", 0),
            _point("A", 1),
            _point("B", 2),
            _point("F", 3),
            _point("J", 4),
            _point("K", 5),
            _point("K", 6),
        ]

        trimmed = _trim_airsim_sync_trajectory(trajectory)

        self.assertEqual([point.phase for point in trimmed], ["B", "F", "J"])

    def test_trim_airsim_sync_trajectory_preserves_airborne_only_route(self) -> None:
        trajectory = [_point("B", 0), _point("F", 1), _point("J", 2)]

        trimmed = _trim_airsim_sync_trajectory(trajectory)

        self.assertEqual([point.phase for point in trimmed], ["B", "F", "J"])


if __name__ == "__main__":
    unittest.main()
