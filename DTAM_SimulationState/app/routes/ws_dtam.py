"""WebSocket — 모듈 통신 (/ws/dtam).

SDK의 DtamWsClient가 이 엔드포인트에 접속하여 메시지를 송수신합니다.

프로토콜:
  1. 모듈이 connect
  2. {"type": "register", "role": "vehicle", "source": "DTAMAirMobility"} 전송
  3. 서버가 {"type": "registered", ...} 응답
  4. 이후 {"type": "message", "mid": "...", "payload": {...}} 로 송수신
"""
from __future__ import annotations

import base64
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from DTAM_CoreServer.app.model.message import FORWARD_RULES, MODULE_ROLES

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/dtam")
async def ws_dtam(websocket: WebSocket) -> None:
    hub = websocket.app.state.hub
    await websocket.accept()
    role: Optional[str] = None
    source: str = ""
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                await websocket.send_json({"type": "error", "error": "invalid JSON"})
                continue

            msg_type = str(msg.get("type") or "").strip()

            # ── 등록 ──────────────────────────────────
            if msg_type == "register":
                req_role = str(msg.get("role") or "").strip().lower()
                source = str(msg.get("source") or "").strip()
                if req_role not in MODULE_ROLES:
                    await websocket.send_json({
                        "type": "error",
                        "error": f"unknown role: {req_role}",
                        "allowed": MODULE_ROLES,
                    })
                    continue
                role = req_role
                hub.register_ws_module(role, websocket, source)
                # 이 role이 받을 메시지 목록 계산
                subscriptions = sorted(set(
                    mid for mid, targets in FORWARD_RULES.items() if role in targets
                ))
                await websocket.send_json({
                    "type": "registered",
                    "role": role,
                    "source": source,
                    "subscriptions": subscriptions,
                })
                continue

            # ── 메시지 전송 ─────────────────────────────
            if msg_type == "message":
                if role is None:
                    await websocket.send_json({"type": "error", "error": "not registered"})
                    continue
                mid = str(msg.get("mid") or "").strip()
                payload = msg.get("payload") or {}
                image_b64 = msg.get("image_b64") or ""
                image_bytes = base64.b64decode(image_b64) if image_b64 else b""
                hub.on_ws_message(role, mid, payload, image_bytes)
                continue

            # ── ping/pong ────────────────────────────────
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("ws_dtam error")
    finally:
        if role:
            hub.unregister_ws_module(role)
