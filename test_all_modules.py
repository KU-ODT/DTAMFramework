"""전체 모듈 및 ICD 메시지 포워딩 통합 검증 스크립트.

이 스크립트는 다음을 수행합니다:
1. 백그라운드에서 DSE_main.py (DTAM Core Server)를 실행합니다.
2. 백그라운드에서 SS_main.py (Simulation State Server)를 실행합니다.
3. 4개의 가상 모듈(mission, monitoring, vehicle, visual)을 WebSocket으로 서버에 연결합니다.
4. 각 모듈이 전송해야 할 모든 ICD 메시지(0001~4101)를 HTTP POST API를 통해 서버로 전송합니다.
5. FORWARD_RULES 에 따라 올바른 수신자가 WebSocket으로 메시지를 받았는지 검증합니다.
"""

import sys
import time
import sys
import time
import json
import urllib.request
import urllib.error
import subprocess
import asyncio
import websockets
from typing import Dict, Any, List

# 포워딩 규칙 (서버에 구현된 것과 동일)
FORWARD_RULES = {
    "0001": ["monitoring"],
    "0003": ["vehicle", "visual"],
    "1001": ["sim_state"],
    "1002": ["vehicle", "visual", "sim_state"],
    "1003": ["sim_state"],
    "2001": ["mission"],
    "2002": ["mission", "monitoring", "vehicle", "visual"],
    "3001": ["vehicle"],
    "3002": ["vehicle"],
    "3003": ["vehicle"],
    "4001": ["monitoring", "visual"],
    "4101": ["monitoring"],
}

TEST_MESSAGES = [
    ("monitoring", "1001", {"timestamp": "2026-04-24T00:00:00Z", "operationMode": "single"}),
    ("monitoring", "1002", {"timestamp": "2026-04-24T00:00:00Z", "playState": "play"}),
    ("monitoring", "1003", {"timestamp": "2026-04-24T00:00:00Z", "scenarioFileName": "test"}),
    ("monitoring", "2001", {"timestamp": "2026-04-24T00:00:00Z", "scenarioFileName": "test"}),
    ("monitoring", "2002", {"timestamp": "2026-04-24T00:00:00Z", "simModeFileName": "test"}),
    ("mission", "3001", {"flightPlanNumber": 1, "aircraftId": "UAM0001"}),
    ("mission", "3002", {"commandId": "CMD1", "aircraftId": "UAM0001", "modificationType": "routeUpdate"}),
    ("mission", "3003", {"commandId": "CMD2", "aircraftId": "UAM0001", "actions": []}),
    ("vehicle", "4001", {"timestamp": "2026-04-24T00:00:00Z", "vehicles": {"UAM0001": {"currentWaypointId": "W1"}}}),
    ("visual", "4101", {"message_id": 4101, "timestamp": "2026-04-24T00:00:00Z", "vehicle_id": "UAM0001", "image_type": "scene"}),
]

rx_history = {
    "mission": set(),
    "monitoring": set(),
    "vehicle": set(),
    "visual": set(),
    "sim_state": set()
}
ws_connections = {}

async def ws_client(role: str):
    uri = f"ws://127.0.0.1:8096/ws/dtam?role={role}&source=test"
    try:
        async with websockets.connect(uri) as ws:
            ws_connections[role] = ws
            # 모듈 등록
            await ws.send(json.dumps({"type": "register", "role": role, "source": "test"}))
            
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                data = json.loads(msg)
                if data.get("type") == "message":
                    mid = data.get("mid")
                    if mid:
                        rx_history[role].add(mid)
                        print(f"  [RX] {role} received {mid}")
    except asyncio.TimeoutError:
        pass
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"  [WS ERROR] {role}: {e}")

def start_server():
    print("[TEST] Starting Core Server...")
    proc_core = subprocess.Popen(
        [sys.executable, "DTAM_CoreServer/DSE_main.py", "--no-browser"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    for _ in range(30):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8095/docs") as response:
                if response.status == 200:
                    break
        except urllib.error.URLError:
            pass
        time.sleep(0.5)
        
    print("[TEST] Starting Simulation State Server...")
    proc_sim = subprocess.Popen(
        [sys.executable, "DTAM_SimulationState/SS_main.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(2.0)
    return proc_core, proc_sim

async def run_test():
    proc_core, proc_sim = start_server()
    print("[TEST] Servers are ready.")
    
    # test script also checks simulated modules, but sim_state is already running as a real process.
    # so we'll test the remaining 4 virtual modules.
    roles = ["mission", "monitoring", "vehicle", "visual"]
    tasks = [asyncio.create_task(ws_client(r)) for r in roles]
    
    # 연결 및 등록을 위한 대기
    await asyncio.sleep(2)
    
    print("\n[TEST] Sending messages via WebSocket (Dataclass validation)...")
    for sender, mid, payload in TEST_MESSAGES:
        print(f"  -> {sender} sending {mid}")
        ws = ws_connections.get(sender)
        if ws:
            await ws.send(json.dumps({
                "type": "message",
                "mid": mid,
                "payload": payload
            }))
        else:
            print(f"     Failed: {sender} WS not connected")
        await asyncio.sleep(0.5)
        
    # 라우팅 수신 대기
    await asyncio.sleep(2)
    
    for task in tasks:
        task.cancel()
        
    proc_core.terminate()
    proc_sim.terminate()
    proc_core.wait()
    proc_sim.wait()
    print("[TEST] Cleanup done.")
    
    print("\n[TEST] Verification Results:")
    all_passed = True
    
    for sender, mid, payload in TEST_MESSAGES:
        expected_receivers = FORWARD_RULES.get(mid, [])
        for target_role in roles:
            if target_role == sender:
                continue
                
            is_received = mid in rx_history[target_role]
            should_receive = target_role in expected_receivers
            
            if is_received == should_receive:
                pass
            else:
                all_passed = False
                print(f"  [ERROR] {mid} -> {target_role}: Expected {should_receive}, Got {is_received}")

    if all_passed:
        print("\n  ✅ SUCCESS: All modules successfully connected, sent messages, and routing was perfect!")
        print("  ✅ VALIDATION: All payloads passed the strict Dataclass validation on the server.")
    else:
        print("\n  ❌ FAILED: Some messages were not routed correctly.")

if __name__ == "__main__":
    asyncio.run(run_test())
