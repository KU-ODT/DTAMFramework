"""DtamModule 서브클래스 + ``@on_receive`` 패턴 예제.

vehicle 역할로 접속해 3001/0003/2002 수신 + 4001 송신.

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

from dtam_client import DtamModule, Role, on_receive


class ExampleVehicle(DtamModule):
    """예제용 vehicle 모듈 — 핵심 3개 mid 만 받고 4001 한 번 송신."""

    role = Role.VEHICLE

    @on_receive("3001")
    def on_scheduled_flight(self, plan) -> None:
        # ``plan`` 은 ``Msg3001_ScheduledFlight`` dataclass 인스턴스.
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

    # 4001 송신 예시 (lenient 호환 경로 — strict 모드면 dataclass 필요).
    payload = {
        "timestamp": "2026-04-27T11:00:00.000Z",
        "UAM0001": {
            "currentWaypointId": "1-1",
            "position": {"north": 0, "east": 0, "down": 0},
            # ... 4001 ICD 의 나머지 필드 ...
        },
    }
    veh.send("vehicle_status", payload)

    print(f"connected={veh.connected} subscriptions={veh.subscriptions}")
    try:
        # 5초간 0003 / 3001 등 forwarding 메시지 수신
        time.sleep(5.0)
    finally:
        veh.close()


if __name__ == "__main__":
    main()
