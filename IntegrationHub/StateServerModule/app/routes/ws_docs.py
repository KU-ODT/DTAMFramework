"""Internal DTAM helper."""
from __future__ import annotations
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["WebSocket Docs"])

WS_DOC_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>DTAM WebSocket Protocol</title>
<style>
body{font-family:'Segoe UI',sans-serif;max-width:980px;margin:40px auto;padding:0 20px;background:#0d1117;color:#c9d1d9}
h1{color:#58a6ff}h2{color:#79c0ff;border-bottom:1px solid #21262d;padding-bottom:8px;margin-top:36px}
code{background:#161b22;padding:2px 6px;border-radius:4px;color:#f0883e}
pre{background:#161b22;padding:16px;border-radius:8px;overflow-x:auto;border:1px solid #30363d}
pre code{background:none;padding:0;color:#c9d1d9}
table{border-collapse:collapse;width:100%;margin:8px 0 16px}th,td{border:1px solid #30363d;padding:8px 12px;text-align:left;font-size:14px;vertical-align:top}th{background:#161b22;color:#58a6ff}.note{color:#8b949e;font-size:13px}.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600;margin-right:6px}.tx{background:#1f6feb;color:#fff}.rx{background:#238636;color:#fff}.warn{background:#5a1e02;border-left:3px solid #f0883e;padding:10px 14px;margin:12px 0;border-radius:4px}
</style></head><body>
<h1>DTAM WebSocket Protocol</h1>
<p class="note">All DTAM ICD messages use a single WebSocket channel: <code>/ws/dtam</code>. Modules connect once, register their role/source, and then exchange message envelopes.</p>
<h2>1. Connection</h2><pre><code>ws://&lt;server-ip&gt;:8096/ws/dtam</code></pre>
<p class="note">StateServerModule hosts the data-plane WebSocket endpoint on port 8096. CoreServer on port 8095 is the REST control plane.</p>
<h2>2. Registration handshake</h2>
<p><span class="badge tx">TX to server</span></p><pre><code>{"type":"register","role":"vehicle","source":"VehicleModule"}</code></pre>
<p><span class="badge rx">RX from server</span> The server returns the registered role and subscribed message IDs.</p>
<pre><code>{"type":"registered","role":"vehicle","source":"VehicleModule","subscriptions":["0003","1002","2002","3001","3002","3003","5001"]}</code></pre>
<h2>3. Send a message</h2>
<pre><code>{"type":"message","mid":"4001","payload":{"timestamp":"2026-04-28T03:01:00.123Z","UAM0001":{"position":{"north":0,"east":0,"down":-100}}}}</code></pre>
<h2>4. Receive a message</h2>
<pre><code>{"type":"message","mid":"0003","from_role":"server","payload":{"timestamp":"2026-04-28T12:00:01.000Z","simTime":"2026-04-28T09:30:15.000Z"}}</code></pre>
<h2>5. Camera image frame (4101)</h2>
<p>Image bytes are embedded as base64 in the <code>image_b64</code> field of the same message envelope.</p>
<h2>6. ping/pong</h2><p>Clients may send <code>{"type":"ping"}</code>; the server replies with <code>{"type":"pong"}</code>.</p>
<h2>7. Role subscriptions</h2>
<table><tr><th>Role</th><th>SDK base</th><th>Module</th><th>Incoming mids</th></tr>
<tr><td><code>mission</code></td><td><code>MissionModule</code></td><td>MissionModule</td><td>2001, 2002</td></tr>
<tr><td><code>vehicle</code></td><td><code>VehicleModule</code></td><td>VehicleModule</td><td>0003, 1002, 2002, 3001, 3002, 3003, 5001</td></tr>
<tr><td><code>monitoring</code></td><td><code>OperationModule</code></td><td>OperationModule</td><td>0001, 0002, 2002, 4001, 4101</td></tr>
<tr><td><code>visual</code></td><td><code>VisualizationModule</code></td><td>VisualizationModule</td><td>0003, 1002, 1003, 2002, 3001, 4001, 5002</td></tr>
<tr><td><code>sim_state</code></td><td>-</td><td>State server DB sink</td><td>1001, 1002, 1003</td></tr></table>
<h2>8. Recommended SDK pattern</h2>
<pre><code>from dtam_client import VehicleModule, on_receive
from dtam_client.schema import Msg3001_ScheduledFlight, Msg4001_VehicleStatus

class MyVehicleService(VehicleModule):
    @on_receive("3001")
    def on_scheduled_flight(self, plan: Msg3001_ScheduledFlight):
        ...

    def push_status(self, vehicles: dict):
        return self.send(Msg4001_VehicleStatus(timestamp="...", vehicles=vehicles))</code></pre>
<h2>9. REST helper endpoints</h2>
<table><tr><th>Endpoint</th><th>Purpose</th></tr>
<tr><td><code>POST /api/msg/{mid}</code></td><td>Send one ICD message from scripts or Swagger UI.</td></tr>
<tr><td><code>GET /api/state</code></td><td>Inspect server, module, traffic, and DB state.</td></tr>
<tr><td><code>GET /api/modules</code></td><td>List registered modules and latest heartbeat.</td></tr>
<tr><td><code>POST /api/heartbeat</code></td><td>Inject a heartbeat for debugging or tests.</td></tr>
<tr><td><code>GET /api/db/messages/{mid}/latest</code></td><td>Read the latest payload for one message ID.</td></tr>
<tr><td><code>GET /api/cameras/{vehicle_id}</code></td><td>Read the latest 4101 camera frame as MJPEG.</td></tr></table>
<div class="warn"><strong>Note:</strong> A message is forwarded only when <code>FORWARD_RULES</code> allows the sender/receiver role combination.</div>
</body></html>"""


@router.get(
    "/docs/websocket",
    summary="WebSocket protocol documentation",
    description="DTAM WebSocket protocol guide as an HTML page.",
    response_class=HTMLResponse,
)
async def ws_docs_page() -> HTMLResponse:
    return HTMLResponse(content=WS_DOC_HTML)
