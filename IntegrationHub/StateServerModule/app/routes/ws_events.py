"""WebSocket — GUI 실시간 이벤트 (/ws/events)."""
from __future__ import annotations
import json, logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()
gui_clients: set = set()


def _full_snapshot(app) -> dict:
    """hub.snapshot() + DB 세션 정보를 합쳐 모니터 UI 가 한 번에 받게 한다."""
    hub = app.state.hub
    snap = hub.snapshot()
    db = getattr(app.state, "db", None)
    if db is not None:
        try:
            snap["db"] = db.stats()
        except Exception:
            snap["db"] = {"session_id": "(error)", "session_dir": ""}
    return snap


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
    await websocket.accept()
    gui_clients.add(websocket)
    try:
        await websocket.send_json({"type": "snapshot", **_full_snapshot(websocket.app)})
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg.get("type") == "snapshot":
                await websocket.send_json({"type": "snapshot", **_full_snapshot(websocket.app)})
    except WebSocketDisconnect:
        pass
    finally:
        gui_clients.discard(websocket)
