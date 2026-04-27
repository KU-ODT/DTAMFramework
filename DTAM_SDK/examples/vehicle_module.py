"""DtamModule 사용 예제 — vehicle 역할로 접속해 4001 송신 + 콜백.

실행:
    python DTAM_SDK/examples/vehicle_module.py
    (사전에 DTAM_SimulationState 가 8096 포트에서 가동 중이어야 함)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# DTAM_SDK 루트를 sys.path 에 추가 (pip install -e . 했다면 불필요)
_SDK_ROOT = Path(__file__).resolve().parents[1]
if str(_SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(_SDK_ROOT))

from dtam_client import DtamModule, Role


def on_scheduled_flight(payload: dict) -> None:
    print(f"[3001] aircraftId={payload.get('aircraftId')} fpn={payload.get('flightPlanNumber')}")


def on_common_time_info(payload: dict) -> None:
    print(f"[0003] simTime={payload.get('simTime')}")


def on_dtam_execute(payload: dict) -> None:
    print(f"[2002] folder={payload.get('flightPlanFolderName')}")


def main() -> None:
    mod = DtamModule.start(
        role=Role.VEHICLE,
        server_url="ws://127.0.0.1:8096/ws/dtam",
        heartbeat=True,
    )
    mod.on("scheduled_flight",  on_scheduled_flight)
    mod.on("common_time_info",  on_common_time_info)
    mod.on("dtam_execute",      on_dtam_execute)

    # 4001 송신 예시
    payload = {
        "timestamp": "2026-04-27T11:00:00.000Z",
        "UAM0001": {
            "currentWaypointId": "1-1",
            "position": {"north": 0, "east": 0, "down": 0},
            # ...4001 ICD 의 나머지 필드...
        },
    }
    mod.send("vehicle_status", payload)

    print(f"connected={mod.connected} subscriptions={mod.subscriptions}")
    try:
        # 5초간 0003 / 3001 등 forwarding 메시지 수신
        time.sleep(5.0)
    finally:
        mod.close()


if __name__ == "__main__":
    main()
