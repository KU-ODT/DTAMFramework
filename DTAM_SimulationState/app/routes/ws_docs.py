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
body{font-family:'Segoe UI',sans-serif;max-width:980px;margin:40px auto;padding:0 20px;background:#0d1117;color:#c9d1d9}
h1{color:#58a6ff}h2{color:#79c0ff;border-bottom:1px solid #21262d;padding-bottom:8px;margin-top:36px}
h3{color:#8b949e;margin-top:24px}
code{background:#161b22;padding:2px 6px;border-radius:4px;color:#f0883e}
pre{background:#161b22;padding:16px;border-radius:8px;overflow-x:auto;border:1px solid #30363d}
pre code{background:none;padding:0;color:#c9d1d9}
table{border-collapse:collapse;width:100%;margin:8px 0 16px}
th,td{border:1px solid #30363d;padding:8px 12px;text-align:left;font-size:14px;vertical-align:top}
th{background:#161b22;color:#58a6ff}
.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600;margin-right:6px}
.rx{background:#238636;color:#fff}.tx{background:#1f6feb;color:#fff}.note{color:#8b949e;font-size:13px}
.tip{background:#0a3069;border-left:3px solid #58a6ff;padding:10px 14px;margin:12px 0;border-radius:4px}
.warn{background:#5a1e02;border-left:3px solid #f0883e;padding:10px 14px;margin:12px 0;border-radius:4px}
ul li{margin-bottom:4px}
</style></head><body>
<h1>🔌 DTAM WebSocket Protocol</h1>
<p class="note">DTAM 의 모든 ICD 메시지는 이 단일 채널 (<code>/ws/dtam</code>) 으로 송수신됩니다.
모듈은 서버에 한 번 connect 하고, register 후에는 메시지가 양방향으로 흐릅니다.
SDK (<code>dtam_client</code>) 가 핸드셰이크 / 재연결 / heartbeat / dataclass 직렬화를 모두 처리하므로,
모듈 작성자는 <em>역할별 베이스 클래스를 상속해 핸들러만 override</em> 하면 됩니다.</p>

<h2>1. 연결</h2>
<pre><code>ws://&lt;서버IP&gt;:8096/ws/dtam</code></pre>
<p class="note">서버는 <code>DTAM_SimulationState</code> (port 8096). CoreServer (port 8095)
는 control plane (REST 만) 이라 WS endpoint 가 없습니다.</p>

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
<p>알 수 없는 role 이면 <code>{"type":"error","error":"unknown role: ...","allowed":[...]}</code> 응답 후 연결은 유지됩니다 (재시도 가능).</p>

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
<p class="note">등록 전에 <code>type:"message"</code> 를 보내면 <code>{"type":"error","error":"not registered"}</code> 응답.</p>

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

<h2>6. ping/pong (선택)</h2>
<p>WebSocket 자체의 keepalive 외에, 응용 레벨에서도 <code>{"type":"ping"}</code> 송신 시 서버가
<code>{"type":"pong"}</code> 으로 즉시 응답합니다.</p>

<h2>7. 역할 (role) 별 subscriptions</h2>
<p>SDK <code>dtam_client.policy.FORWARD_RULES</code> 가 권위. <code>register</code> 응답의
<code>subscriptions</code> 필드가 동일 값입니다.</p>
<table>
<tr><th>Role</th><th>SDK 베이스</th><th>모듈</th><th>수신 mid</th></tr>
<tr><td><code>mission</code></td><td><code>MissionModule</code></td><td>DTAM_MissionPlanner</td><td>2001, 2002</td></tr>
<tr><td><code>vehicle</code></td><td><code>VehicleModule</code></td><td>DTAMAirMobility</td><td>0003, 1002, 2002, 3001, 3002, 3003</td></tr>
<tr><td><code>monitoring</code></td><td><code>MonitoringModule</code></td><td>DTAMOperationsConsole</td><td>0001, 0002, 2002, 4001, 4101</td></tr>
<tr><td><code>visual</code></td><td><code>VisualModule</code></td><td>DTAMVisualization (Unreal)</td><td>0003, 1002, 2002, 4001</td></tr>
<tr><td><code>sim_state</code></td><td>—</td><td>이 서버 자체 (DB sink)</td><td>1001, 1002, 1003</td></tr>
</table>
<p class="note">각 베이스 클래스의 ``@on_receive`` stub 집합이 <code>FORWARD_RULES</code> 와 일치하는지 import 시점에
자동 검증 (<code>_validate_role_base</code>). drift 있으면 <code>AssertionError</code>.</p>

<h2>8. SDK 사용 예 (권장)</h2>

<h3>(a) 역할 베이스 + 핸들러 override — ★ 표준</h3>
<p>5개 모듈 모두 이 패턴을 사용합니다. 베이스가 mid → method 매핑·구독·heartbeat 를 모두 처리하므로,
서브클래스는 <em>처리할 핸들러만 override</em> 하면 됩니다.</p>
<pre><code>from dtam_client import VehicleModule, on_receive
from dtam_client.schema import (
    Msg3001_ScheduledFlight,
    Msg0003_CommonTimeInfo,
    Msg4001_VehicleStatus,
)

class MyVehicleService(VehicleModule):
    def __init__(self, *, target_ip="127.0.0.1", ws_port=8096):
        # 도메인 상태 초기화 (super 보다 먼저)
        self._plans = {}
        super().__init__(server_url=f"ws://{target_ip}:{ws_port}/ws/dtam",
                         heartbeat=True)              # 0002 1Hz 자동 송신

    # ─── 베이스 stub override ───
    @on_receive("3001")                                # ← 가독성용, 생략 가능
    def on_scheduled_flight(self, plan: Msg3001_ScheduledFlight):
        self._plans[plan.aircraftId] = plan

    @on_receive("0003")
    def on_common_time_info(self, msg: Msg0003_CommonTimeInfo):
        ...

    # 1002 SimulationSetup 처리 안 함 → 베이스 빈 stub 이 silent drop

    # ─── 송신 ───
    def push_status(self, vehicles: dict):
        return self.send(Msg4001_VehicleStatus(timestamp="...", vehicles=vehicles))
</code></pre>

<div class="tip">
<strong>핸들러 작성 — 3가지 방식 모두 지원</strong>
<ul>
<li><strong>A. 같은 이름 + 데코레이터 생략</strong> — 베이스 매핑 그대로 적용. 가장 짧음.</li>
<li><strong>B. 같은 이름 + <code>@on_receive("MID")</code></strong> — 가독성용 (베이스와 mid 일치 검증됨). ★ 권장.</li>
<li><strong>C. 자유 이름 + <code>@on_receive("MID")</code></strong> — 도메인 친화 이름. 베이스 stub 은 dormant.</li>
</ul>
mid 가 베이스와 다르면 인스턴스화 시점에 <code>TypeError</code> (footgun 방지).
</div>

<h3>(b) Composition — 런타임 등록 (간단한 스크립트용)</h3>
<p>클래스 상속 없이 한 번에 띄우고 콜백을 런타임에 붙이고 싶을 때.</p>
<pre><code>from dtam_client import DtamModule, Role
from dtam_client.schema import Msg4001_VehicleStatus

mod = DtamModule.start(
    role=Role.VEHICLE,
    server_url="ws://127.0.0.1:8096/ws/dtam",
    heartbeat=True,
)
mod.on("scheduled_flight", lambda plan: print("got 3001:", plan.aircraftId))
mod.on("common_time_info", lambda msg: ...)
mod.send(Msg4001_VehicleStatus(timestamp="...", vehicles={...}))
</code></pre>
<p class="note">베이스의 stub 검증을 받지 않는 <em>raw role</em> 모드. 임시 스크립트·테스트용으로 사용.
프로덕션 모듈은 (a) 패턴을 사용합니다.</p>

<h3>(c) 저수준 — <code>DtamWsClient</code> (advanced only)</h3>
<pre><code>from dtam_client import DtamWsClient

ws = DtamWsClient(
    url="ws://127.0.0.1:8096/ws/dtam",
    role="vehicle",
    source="DTAMAirMobility",
)
ws.on("3001", lambda payload: print(payload))
ws.connect()
ws.send("4001", {"timestamp": "...", "UAM0001": {...}})
</code></pre>
<p class="note">데코레이터로도 사용 가능: <code>@ws.on("3001")</code>. dataclass 직렬화·통계·재연결 보호는
<code>DtamModule</code> 이 추가로 제공하는 기능이라 직접 처리해야 합니다.</p>

<h2>9. 운영 / 테스트 트리거 (REST 보조 채널)</h2>
<p>WS 가 아니라 단발성 REST 로 메시지를 송신하거나 상태를 조회하고 싶을 때:</p>
<table>
<tr><th>Endpoint</th><th>용도</th></tr>
<tr><td><code>POST /api/msg/{mid}</code></td><td>운영자/스크립트 단발 ICD 송신 (Swagger UI 에서 직접 테스트 가능)</td></tr>
<tr><td><code>GET  /api/state</code></td><td>모듈 / 트래픽 / DB 세션 등 전체 상태 스냅샷</td></tr>
<tr><td><code>GET  /api/modules</code></td><td>등록된 모든 모듈 + 마지막 heartbeat</td></tr>
<tr><td><code>PATCH /api/modules/{role}</code></td><td>특정 모듈의 expected_source 수정 (운영용)</td></tr>
<tr><td><code>POST /api/heartbeat</code></td><td>강제 heartbeat 주입 (디버그·테스트)</td></tr>
<tr><td><code>GET  /api/db/stats</code></td><td>현재 세션 파일 DB 통계 (mid별 누적·마지막 쓰기 시각)</td></tr>
<tr><td><code>POST /api/db/open-folder</code></td><td>OS 파일 탐색기로 세션 DB 폴더 열기</td></tr>
<tr><td><code>GET  /api/db/messages/{mid}/latest</code></td><td>특정 mid 의 최근 페이로드 1건 (필터링 가능)</td></tr>
<tr><td><code>GET  /api/cameras/{vehicle_id}</code></td><td>4101 이 적재한 차량 카메라 프레임 (MJPEG 스트림)</td></tr>
</table>
<p>위 endpoint 들은 <a href="/docs" style="color:#58a6ff">Swagger (/docs)</a> 에서 직접 테스트 가능.</p>

<h2>10. 라이브 모니터 / 시퀀스 다이어그램</h2>
<p><a href="/" style="color:#58a6ff">/</a> — 시퀀스 다이어그램 위로 TrafficEvent 가 실시간 화살표로 표시.</p>
<p><a href="/docs/sequence" style="color:#58a6ff">/docs/sequence</a> — Phase 별 시퀀스 다이어그램 (정적 SVG).</p>

<div class="warn">
<strong>주의:</strong> WebSocket 으로 보낼 수 있는 mid 라도, <code>FORWARD_RULES</code> 가 forward 해주지 않는
role 조합이면 메시지가 도달하지 않습니다. 예: <code>monitoring</code> role 에서 4001 을 송신해도 서버는
forward 하지 않음 (4001 은 vehicle 만 송신 가능).
</div>

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
