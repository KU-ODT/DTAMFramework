"""Example VehicleModule using DtamModule and @on_receive.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# Registration handling
_SDK_ROOT = Path(__file__).resolve().parents[1]
if str(_SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(_SDK_ROOT))

from dtam_client import DtamModule, Role, on_receive


class ExampleVehicle(DtamModule):
    """Internal helper."""

    role = Role.VEHICLE

    @on_receive("3001")
    def on_scheduled_flight(self, plan) -> None:
        # Registration handling
        print(f"[3001] aircraftId={plan.aircraftId} fpn={plan.flightPlanNumber}")

    @on_receive("0003")
    def on_common_time_info(self, clock) -> None:
        print(f"[0003] simTime={clock.simTime}")

    @on_receive("2002")
    def on_dtam_execute(self, execute) -> None:
        print(f"[2002] folder={execute.flightPlanFolderName}")


def main() -> None:
    veh = ExampleVehicle(
        server_url="ws://127.0.0.1:8096/ws/dtam",
        heartbeat=True,
    )

    # Registration handling
    payload = {
        "timestamp": "2026-04-27T11:00:00.000Z",
        "UAM0001": {
            "currentWaypointId": "1-1",
            "position": {"north": 0, "east": 0, "down": 0},
            # Registration handling
        },
    }
    veh.send("vehicle_status", payload)

    print(f"connected={veh.connected} subscriptions={veh.subscriptions}")
    try:
        # Registration handling
        time.sleep(5.0)
    finally:
        veh.close()


if __name__ == "__main__":
    main()
