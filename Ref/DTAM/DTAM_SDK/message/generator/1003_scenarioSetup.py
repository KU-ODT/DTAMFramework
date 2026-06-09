"""User-side sample generator for Scenario Setup (MSG 1003)."""
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dtam_client.schema.msg_1003 import (
    VEHICLE_TYPES,
    VERTIPORT_CLASSES,
    validate_message,
)


_VERTIPORTS = [
    {"name": "Yeouido", "lat": 37.526513, "lon": 126.922845, "angle": 322.0},
    {"name": "Jamsil", "lat": 37.514368, "lon": 127.069068, "angle": 83.0},
    {"name": "Sangam", "lat": 37.562282, "lon": 126.890156, "angle": 38.0},
    {"name": "Gimpo", "lat": 37.558300, "lon": 126.790600, "angle": 270.0},
    {"name": "Gangnam", "lat": 37.497900, "lon": 127.027600, "angle": 155.0},
]

_WAYPOINTS = [
    {"id": "WP001", "name": "Gaehwa", "lat": 37.569391, "lon": 126.861026, "alt": 1000.0, "links": ["WP002", "WP003"]},
    {"id": "WP002", "name": "Deungchon", "lat": 37.553824, "lon": 126.875819, "alt": 1000.0, "links": ["WP001", "WP003"]},
    {"id": "WP003", "name": "Mokdong", "lat": 37.530667, "lon": 126.888262, "alt": 1000.0, "links": ["WP002", "WP004"]},
    {"id": "WP004", "name": "YeouidoEntry", "lat": 37.527100, "lon": 126.910500, "alt": 800.0, "links": ["WP003", "WP005"]},
    {"id": "WP005", "name": "YeouidoPark", "lat": 37.525500, "lon": 126.921400, "alt": 600.0, "links": ["WP004"]},
]


def _now_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def generate(
    total_aircraft_count: Optional[int] = None,
    main_vehicle_type: Optional[str] = None,
    validate: bool = True,
    **_ignored: Any,
) -> Dict[str, Any]:
    start_h = random.randint(6, 10)
    end_h = min(23, start_h + random.randint(4, 12))

    num_vp = random.randint(2, len(_VERTIPORTS))
    vps = random.sample(_VERTIPORTS, num_vp)

    ts = _now_iso()
    file_ts = ts.replace("-", "").replace(":", "").replace(".", "")

    msg: Dict[str, Any] = {
        "timestamp": ts,
        "scenarioFileName": f"scenarioSetup_{file_ts}.json",
        "operationTime": {
            "startTime": f"{start_h:02d}:00:00",
            "endTime": f"{end_h:02d}:00:00",
        },
        "vertiports": [
            {
                "name": vp["name"],
                "class": random.choice(VERTIPORT_CLASSES),
                "lat": vp["lat"],
                "lon": vp["lon"],
                "angleDegrees": vp["angle"],
            }
            for vp in vps
        ],
        "routeNetwork": {
            "waypoints": [
                {
                    "waypointId": wp["id"],
                    "waypointName": wp["name"],
                    "lat": wp["lat"],
                    "lon": wp["lon"],
                    "altFt": wp["alt"],
                    "links": wp["links"],
                }
                for wp in _WAYPOINTS
            ],
        },
        "totalAircraftCount": int(total_aircraft_count) if total_aircraft_count else random.randint(5, 50),
        "mainVehicleType": main_vehicle_type or random.choice(VEHICLE_TYPES),
    }

    if validate:
        ok, errors, _ = validate_message(msg)
        if not ok:
            raise RuntimeError("1003 generator self-check failed: " + "; ".join(errors))
    return msg


if __name__ == "__main__":
    import json

    print(json.dumps(generate(), ensure_ascii=False, indent=2))
