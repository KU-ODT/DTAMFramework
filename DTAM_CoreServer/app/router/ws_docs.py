"""WebSocket 프로토콜 문서 페이지."""
from __future__ import annotations
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["📡 WebSocket 문서"])

WS_DOC_HTML = """<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<title>DTAM WebSocket Protocol</title>
<style>
body{font-family:'Segoe UI',sans-serif;max-width:900px;margin:40px auto;padding:0 20px;background:#0d1117;color:#c9d1d9}
h1{color:#58a6ff}h2{color:#79c0ff;border-bottom:1px solid #21262d;padding-bottom:8px}
code{background:#161b22;padding:2px 6px;border-radius:4px;color:#f0883e}
pre{background:#161b22;padding:16px;border-radius:8px;overflow-x:auto;border:1px solid #30363d}
pre code{background:none;padding:0;color:#c9d1d9}
table{border-collapse:collapse;width:100%}th,td{border:1px solid #30363d;padding:8px 12px;text-align:left}
th{background:#161b22;color:#58a6ff}.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600}
.rx{background:#238636;color:#fff}.tx{background:#1f6feb;color:#fff}
</style></head><body>
<h1>🔌 DTAM WebSocket Protocol</h1>
<p>모듈이 서버에 WebSocket으로 연결하여 메시지를 송수신하는 프로토콜입니다.</p>

<h2>1. 연결</h2>
<pre><code>ws://&lt;서버IP&gt;:8095/ws/dtam</code></pre>

<h2>2. 등록 (connect 후 첫 메시지)</h2>
<p><span class="badge tx">TX → 서버</span></p>
<pre><code>{
  "type": "register",
  "role": "vehicle",
  "source": "DTAMAirMobility"
}</code></pre>
<p><span class="badge rx">RX ← 서버</span></p>
<pre><code>{
  "type": "registered",
  "role": "vehicle",
  "source": "DTAMAirMobility",
  "subscriptions": ["0003", "2002", "3001", "3002", "3003"]
}</code></pre>

<h2>3. 메시지 전송</h2>
<p><span class="badge tx">TX → 서버</span></p>
<pre><code>{
  "type": "message",
  "mid": "4001",
  "payload": {
    "timestamp": "2026-04-15T03:01:00.123Z",
    "UAM0001": { "position": {"north": 0, "east": 0, "down": 0} }
  }
}</code></pre>

<h2>4. 메시지 수신</h2>
<p><span class="badge rx">RX ← 서버</span> (서버가 포워딩하거나 주기 전송하는 메시지)</p>
<pre><code>{
  "type": "message",
  "mid": "0003",
  "from_role": "server",
  "payload": {
    "timestamp": "2026-04-16T12:00:01.000Z",
    "simTime": "2026-04-16T09:30:15.000Z"
  }
}</code></pre>

<h2>5. 역할 (role) 목록</h2>
<table><tr><th>Role</th><th>설명</th><th>수신 메시지 예</th></tr>
<tr><td><code>mission</code></td><td>임무 계획 모듈</td><td>2001, 2002</td></tr>
<tr><td><code>monitoring</code></td><td>운용 콘솔</td><td>2002, 4001, 4101</td></tr>
<tr><td><code>vehicle</code></td><td>비행체 모듈</td><td>0003, 2002, 3001, 3002, 3003</td></tr>
<tr><td><code>visual</code></td><td>시각화 모듈</td><td>0003, 2002, 4001</td></tr>
</table>

<h2>6. SDK 사용 예</h2>
<pre><code>from dtam_client import DtamWsClient

dtam = DtamWsClient(
    url="ws://127.0.0.1:8095/ws/dtam",
    role="vehicle",
    source="DTAMAirMobility",
)

@dtam.on("3001")
def on_flight(payload):
    print("비행계획 수신:", payload)

dtam.connect()
dtam.send("4001", my_vehicle_data)
dtam.disconnect()
</code></pre>
</body></html>"""


@router.get(
    "/docs/websocket",
    summary="WebSocket 프로토콜 문서",
    description="DTAM WebSocket 프로토콜 사용법 (HTML)",
    response_class=HTMLResponse,
)
async def ws_docs_page() -> HTMLResponse:
    return HTMLResponse(content=WS_DOC_HTML)
