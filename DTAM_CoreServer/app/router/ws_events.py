"""WebSocket — GUI 실시간 이벤트 (/ws/events)."""
from __future__ import annotations
import json, logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()
gui_clients: set = set()

@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
    hub = websocket.app.state.hub
    await websocket.accept()
    gui_clients.add(websocket)
    try:
        await websocket.send_json({"type": "snapshot", **hub.snapshot()})
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg.get("type") == "snapshot":
                await websocket.send_json({"type": "snapshot", **hub.snapshot()})
    except WebSocketDisconnect:
        pass
    finally:
        gui_clients.discard(websocket)
