from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (str(REPO_ROOT),):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from VisualizationModule.app.adapters.airsim import (  # noqa: E402
    _normalize_4001_payload,
    _telemetry_args_from_4001,
)


def test_4001_energy_is_preserved_and_forwarded_as_battery_fraction() -> None:
    message = {
        "timestamp": "2026-05-21T00:00:00.000Z",
        "UAM0001": {
            "currentWaypointId": "5200001-1",
            "position": {"north": 1.0, "east": 2.0, "down": -3.0},
            "attitude": {"roll": 0.0, "pitch": 0.0, "yaw": 1.57},
            "gps": {
                "latitude": 37.5,
                "longitude": 127.0,
                "altitude": 55.0,
                "velocity_north": 10.0,
                "velocity_east": 0.0,
                "velocity_down": 0.0,
            },
            "barometer": {"altitude": 55.0, "pressure": 101325.0, "qnh": 1013.25},
            "energy": {"battery_pct": 73.25, "state_of_charge_pct": 73.25},
        },
    }

    vehicle_payload = _normalize_4001_payload(message)["UAM0001"]
    args = _telemetry_args_from_4001("UAM0001", vehicle_payload, "Drone1")

    assert args is not None
    assert vehicle_payload["energy"]["battery_pct"] == 73.25
    assert args[-2] == "Drone1"
    assert args[-1] == 0.7325
