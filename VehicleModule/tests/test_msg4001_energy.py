from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DTAMSDK_ROOT = REPO_ROOT / "DTAMSDK"
for _path in (str(REPO_ROOT), str(DTAMSDK_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from VehicleModule.app.domain.transform.coord_transform import LocalNEDFrame  # noqa: E402
from VehicleModule.app.services.msg4001 import VehiclePublishContext, build_vehicle_payload  # noqa: E402


def test_build_vehicle_payload_pins_energy_to_cumulative_battery_pct() -> None:
    context = VehiclePublishContext(
        vehicle_id="UAM0001",
        flight_plan_number=5200001,
        origin_frame=LocalNEDFrame(37.5, 127.0, 50.0),
        battery_pct=77.0,
    )

    payload = build_vehicle_payload(
        context=context,
        lat=37.5,
        lon=127.0,
        alt_m=50.0,
        speed_mps=15.0,
        heading_deg=90.0,
        battery_pct=76.5,
        energy={
            "battery_pct": 95.0,
            "state_of_charge_pct": 96.0,
            "source": "provider-instant-estimate",
        },
    )

    assert payload["energy"]["battery_pct"] == 76.5
    assert payload["energy"]["state_of_charge_pct"] == 76.5
    assert payload["energy"]["source"] == "provider-instant-estimate"
    assert payload["_battery_pct"] == 76.5
