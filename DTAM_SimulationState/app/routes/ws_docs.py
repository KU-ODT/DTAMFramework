"""WebSocket 프로토콜 문서 페이지 (`/docs/websocket`).

Swagger UI 가 WebSocket 을 1급으로 다루지 못하기 때문에, ``/ws/dtam`` 의
프로토콜은 별도 HTML 페이지로 정리한다. SimulationState (port 8096) 에
마운트되어 ``http://<host>:8096/docs/websocket`` 으로 접근 가능.
"""
from __future__ import annotations
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["📡 WebSocket 문서"])

WS_DOC_HTML = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8">
<title>DTAM WebSocket Protocol</title>
<style>
body{font-family:'Segoe UI',sans-serif;max-width:960px;margin:40px auto;padding:0 20px;background:#0d1117;color:#c9d1d9}
h1{color:#58a6ff}h2{color:#79c0ff;border-bottom:1px solid #21262d;padding-bottom:8px;margin-top:36px}
h3{color:#8b949e;margin-top:24px}
code{background:#161b22;padding:2px 6px;border-radius:4px;color:#f0883e}
pre{background:#161b22;padding:16px;border-radius:8px;overflow-x:auto;border:1px solid #30363d}
pre code{background:none;padding:0;color:#c9d1d9}
table{border-collapse:collapse;width:100%;margin:8px 0 16px}th,td{border:1px solid #30363d;padding:8px 12px;text-align:left;font-size:14px}
th{background:#161b22;color:#58a6ff}.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600;margin-right:6px}
.rx{background:#238636;color:#fff}.tx{background:#1f6feb;color:#fff}.note{color:#8b949e;font-size:13px}
ul li{margin-bottom:4px}
</style></head><body>
<h1>🔌 DTAM WebSocket Protocol</h1>
<p class="note">DTAM 의 모든 ICD 메시지는 이 단일 채널로 송수신됩니다.
모듈은 서버에 한 번 connect 하고, register 후에는 메시지가 양방향으로 흐릅니다.</p>

<h2>1. 연결</h2>
<pre><code>ws://&lt;서버IP&gt;:8096/ws/dtam</code></pre>
<p class="note">서버는 <code>DTAM_SimulationState</code> (port 8096). CoreServer (port 8095)
는 control plane 이라 WS endpoint 가 없습니다.</p>

<h2>2. 등록 핸드셰이크</h2>
<p>connect 후 <em>첫 메시지</em>로 자기 정체를 알립니다.</p>
<p><span class="badge tx">TX → 서버</span></p>
<pre><code>{
  "type": "register",
  "role": "vehicle",
  "source": "DTAMAirMobility"
}</code></pre>
<p><span class="badge rx">RX ← 서버</span> 서버가 forward 정책 (이 모듈이 받게 될 mid 목록) 을 응답.</p>
<pre><code>{
  "type": "registered",
  "role": "vehicle",
  "source": "DTAMAirMobility",
  "subscriptions": ["0003", "1002", "2002", "3001", "3002", "3003"]
}</code></pre>

<h2>3. 메시지 송신 (모듈 → 서버)</h2>
<p><span class="badge tx">TX → 서버</span></p>
<pre><code>{
  "type": "message",
  "mid": "4001",
  "payload": {
    "timestamp": "2026-04-28T03:01:00.123Z",
    "UAM0001": { "currentWaypointId": "1201-3", "position": {"north": 0, "east": 0, "down": -100} }
  }
}</code></pre>

<h2>4. 메시지 수신 (서버 → 모듈)</h2>
<p><span class="badge rx">RX ← 서버</span> 서버가 forwarding 또는 주기 푸시 (예: 0003 1Hz) 하는 메시지.</p>
<pre><code>{
  "type": "message",
  "mid": "0003",
  "from_role": "server",
  "payload": {
    "timestamp": "2026-04-28T12:00:01.000Z",
    "simTime": "2026-04-28T09:30:15.000Z"
  }
}</code></pre>

<h2>5. 카메라 프레임 (4101) — binary tail</h2>
<p>이미지 바이너리는 <code>image_b64</code> 필드에 base64 로 인코딩되어 같은 message 안에 동봉됩니다.</p>
<pre><code>{
  "type": "message",
  "mid": "4101",
  "payload": { "vehicle_id": "UAM0001", "camera_name": "front_center", ... },
  "image_b64": "iVBORw0KGgoAAAA..."
}</code></pre>

<h2>6. 역할 (role) 별 subscriptions</h2>
<p>FORWARD_RULES 에서 자동 계산. <code>register</code> 응답의 <code>subscriptions</code> 필드와 동일.</p>
<table>
<tr><th>Role</th><th>설명</th><th>수신 메시지</th></tr>
<tr><td><code>mission</code></td><td>임무 계획 (DTAM_MissionPlanner)</td><td>2001, 2002</td></tr>
<tr><td><code>monitoring</code></td><td>운용 콘솔 (DTAMOperationsConsole)</td><td>0001, 0002, 2002, 4001, 4101</td></tr>
<tr><td><code>vehicle</code></td><td>비행체 (DTAMAirMobility)</td><td>0003, 1002, 2002, 3001, 3002, 3003</td></tr>
<tr><td><code>visual</code></td><td>시각화 (DTAMVisualization)</td><td>0003, 1002, 2002, 4001</td></tr>
<tr><td><code>sim_state</code></td><td>시뮬레이션 상태 서버 (자기 자신, DB sink)</td><td>1001, 1002, 1003</td></tr>
</table>

<h2>7. SDK 사용 예 (권장)</h2>

<h3>(a) 서브클래스 + 데코레이터 패턴</h3>
<pre><code>from dtam_client import DtamModule, Role, on_receive
from dtam_client.schema import (
    Msg3001_ScheduledFlight,
    Msg0003_CommonTimeInfo,
    Msg4001_VehicleStatus,
    VehicleData,
)

class VehicleService(DtamModule):
    role = Role.VEHICLE                        # 클래스 속성으로 한 번 선언

    def __init__(self):
        super().__init__(server_url="ws://127.0.0.1:8096/ws/dtam")
        self._plans = {}

    @on_receive("3001")
    def handle_plan(self, plan: Msg3001_ScheduledFlight):
        self._plans[plan.aircraftId] = plan

    @on_receive("0003")
    def handle_time(self, msg: Msg0003_CommonTimeInfo):
        ...

    def push_status(self, vehicles: dict):
        # SDK 가 to_wire() 자동 호출 → ICD wire format 으로 직렬화
        msg = Msg4001_VehicleStatus(timestamp="...", vehicles=vehicles)
        return self.send(msg)
</code></pre>

<h3>(b) Composition 패턴 (런타임 등록)</h3>
<pre><code>from dtam_client import DtamModule, Role

mod = DtamModule.start(
    role=Role.VEHICLE,
    server_url="ws://127.0.0.1:8096/ws/dtam",
    heartbeat=True,            # 0002 1 Hz 자동 송신
)
mod.on("scheduled_flight", on_3001)
mod.on("common_time_info", on_0003)
mod.send(Msg4001_VehicleStatus(...))
</code></pre>

<h3>(c) 저수준 — DtamWsClient (advanced only)</h3>
<pre><code>from dtam_client import DtamWsClient

ws = DtamWsClient(
    url="ws://127.0.0.1:8096/ws/dtam",
    role="vehicle",
    source="DTAMAirMobility",
)
ws.on("3001")(lambda payload: print(payload))
ws.connect()
ws.send("4001", {"timestamp": "...", "UAM0001": {...}})
</code></pre>

<h2>8. 운영 / 테스트 트리거 (REST 보조 채널)</h2>
<p>WS 가 아니라 단발성 REST 로 메시지를 송신하고 싶을 때:</p>
<table>
<tr><th>Endpoint</th><th>용도</th></tr>
<tr><td><code>POST /api/msg/{mid}</code></td><td>운영자/스크립트 단발 ICD 송신</td></tr>
<tr><td><code>GET  /api/state</code></td><td>모듈 / 트래픽 / DB 스냅샷 조회</td></tr>
<tr><td><code>POST /api/heartbeat</code></td><td>강제 heartbeat 주입 (디버그용)</td></tr>
</table>
<p>위 endpoint 들은 <a href="/docs" style="color:#58a6ff">Swagger (/docs)</a> 에서 직접 테스트 가능.</p>

<h2>9. 라이브 모니터</h2>
<p><a href="/" style="color:#58a6ff">SimulationState 라이브 모니터</a> — 시퀀스 다이어그램 위로
TrafficEvent 가 실시간 화살표로 표시.</p>

</body></html>"""


@router.get(
    "/docs/websocket",
    summary="WebSocket 프로토콜 문서",
    description=(
        "DTAM WebSocket 프로토콜 사용법 (HTML 페이지). "
        "Swagger UI 는 WS 를 직접 테스트하지 못하므로 여기에 별도 정리."
    ),
    response_class=HTMLResponse,
)
async def ws_docs_page() -> HTMLResponse:
    return HTMLResponse(content=WS_DOC_HTML)
