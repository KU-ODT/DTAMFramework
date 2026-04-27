"""WebSocket 모듈 통신 테스트 스크립트.

1. 서버를 먼저 실행해둔 상태에서 이 스크립트를 실행합니다.
2. "vehicle" 역할로 서버에 WebSocket 연결합니다.
3. 등록 응답을 확인합니다.
4. 테스트 메시지(4001)를 전송합니다.
5. 서버로부터 메시지 수신을 기다립니다 (0003 Common Time 등).

사용법:
    python test_ws_client.py
"""
import sys
import time
from pathlib import Path

# DTAM_SDK 경로 추가
ROOT = Path(__file__).resolve().parent
SDK_ROOT = ROOT / "DTAM_SDK"
if str(SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(SDK_ROOT))

from dtam_client import DtamWsClient


def main():
    SERVER_URL = "ws://127.0.0.1:8095/ws/dtam"

    print(f"[TEST] 서버에 연결합니다: {SERVER_URL}")
    dtam = DtamWsClient(
        url=SERVER_URL,
        role="vehicle",
        source="TestVehicle",
    )

    # 0003 Common Time Info 수신 콜백
    @dtam.on("0003")
    def on_common_time(payload):
        print(f"  [RX] 0003 Common Time: {payload.get('simTime', '?')}")

    # 3001 Scheduled Flight 수신 콜백
    @dtam.on("3001")
    def on_flight(payload):
        print(f"  [RX] 3001 Scheduled Flight: {payload.get('aircraftId', '?')}")

    # 2002 DTAM Execute 수신 콜백
    @dtam.on("2002")
    def on_execute(payload):
        print(f"  [RX] 2002 DTAM Execute: {payload}")

    dtam.connect()
    time.sleep(2.0)  # 연결 대기

    if not dtam.connected:
        print("[TEST] 연결 실패! 서버가 실행 중인지 확인하세요.")
        print("       서버 실행: python DTAM_CoreServer/DSE_main.py")
        dtam.close()
        return

    print(f"[TEST] 연결 성공! registered={dtam.registered}")
    print(f"[TEST] subscriptions={dtam.subscriptions}")

    # 테스트 메시지 전송
    print("[TEST] 4001 Vehicle Status 전송 중...")
    ok = dtam.send("4001", {
        "UAM0001": {
            "position": {"north": 0, "east": 0, "down": 0},
            "gps": {"latitude": 37.5, "longitude": 127.0, "altitude": 100},
            "speed": 50.0,
        }
    })
    print(f"  [TX] 4001 전송 결과: {ok}")

    # 10초간 수신 대기 (0003 이 1Hz로 올 것)
    print("[TEST] 10초간 메시지 수신 대기 중... (Ctrl+C로 종료)")
    try:
        time.sleep(10)
    except KeyboardInterrupt:
        pass

    print("[TEST] 종료")
    dtam.close()


if __name__ == "__main__":
    main()
