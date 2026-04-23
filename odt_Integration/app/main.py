"""DTAM Data Emulator — FastAPI 엔트리."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .sdk_import import ensure_sdk_path

ensure_sdk_path()
from . import registry
from .comm import COMM
from .state import STATE, SelfReceiver, Target

BASE_DIR = Path(__file__).resolve().parent.parent
app = FastAPI(title="DTAM Data Emulator")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.on_event("startup")
async def _startup():
    COMM.attach_loop(asyncio.get_running_loop())
    # 저장된 self_rx 자동 시작
    await COMM.start_rx()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request, "index.html",
        {"title": "DTAM Data Emulator", "asset_v": int(time.time())},
    )


# ============ 상태 ============

@app.get("/api/state")
async def api_state():
    return {
        "self_rx": STATE.self_rx.to_dict(),
        "targets": [t.to_dict() for t in STATE.targets],
        "messages": [m.to_dict() for m in STATE.messages],
    }


# ============ 수신부 (self_rx) ============

class SelfRxConfig(BaseModel):
    bind_ip: Optional[str] = None
    bind_port: Optional[int] = None


@app.patch("/api/self_rx")
async def api_self_rx_update(cfg: SelfRxConfig):
    was_enabled = STATE.self_rx.enabled
    await COMM.stop_rx()
    if cfg.bind_ip is not None:
        STATE.self_rx.bind_ip = cfg.bind_ip.strip()
    if cfg.bind_port is not None:
        STATE.self_rx.bind_port = int(cfg.bind_port)
    STATE.save()
    msg = "설정 저장"
    if was_enabled:
        ok, m2 = await COMM.start_rx()
        msg += f" — {m2}"
    return {"ok": True, "msg": msg}


@app.post("/api/self_rx/start")
async def api_self_rx_start():
    ok, msg = await COMM.start_rx()
    return {"ok": ok, "msg": msg}


@app.post("/api/self_rx/stop")
async def api_self_rx_stop():
    await COMM.stop_rx()
    return {"ok": True, "msg": "수신부 중지"}


# ============ 송신 대상 ============

class TargetIn(BaseModel):
    name: str
    ip: str = "127.0.0.1"
    port: int = 17000       # UDP 수신 포트 (상대방)
    tcp_port: Optional[int] = None  # TCP 수신 포트 (생략 시 port+1)
    protocol: str = "udp"


@app.post("/api/targets")
async def api_target_add(t: TargetIn):
    name = t.name.strip()
    if not name:
        return JSONResponse({"ok": False, "msg": "이름 필수"}, status_code=400)
    target = Target(name=name, ip=t.ip.strip(), port=int(t.port),
                    tcp_port=t.tcp_port, protocol=t.protocol)
    if not STATE.add_target(target):
        return JSONResponse({"ok": False, "msg": "동일 이름 이미 존재"}, status_code=400)
    return {"ok": True, "msg": f"'{name}' 추가"}


class TargetUpdate(BaseModel):
    ip: Optional[str] = None
    port: Optional[int] = None      # UDP 포트
    tcp_port: Optional[int] = None  # TCP 포트


@app.patch("/api/targets/{name}")
async def api_target_update(name: str, u: TargetUpdate):
    t = STATE.get_target(name)
    if not t:
        return JSONResponse({"ok": False, "msg": "대상 없음"}, status_code=404)
    if u.ip is not None:
        t.ip = u.ip.strip()
    if u.port is not None:
        t.port = int(u.port)
    if u.tcp_port is not None:
        t.tcp_port = int(u.tcp_port)
    STATE.save()
    return {"ok": True, "msg": "저장"}


@app.delete("/api/targets/{name}")
async def api_target_delete(name: str):
    if not STATE.remove_target(name):
        return JSONResponse({"ok": False, "msg": "대상 없음"}, status_code=404)
    return {"ok": True, "msg": f"'{name}' 삭제"}


@app.post("/api/targets/{name}/ping")
async def api_target_ping(name: str):
    ok, msg = await COMM.ping_target(name)
    return {"ok": ok, "msg": msg}


# ============ 메시지 ============

class MessagePayload(BaseModel):
    payload: Dict[str, Any]


@app.patch("/api/messages/{mid}/payload")
async def api_message_payload(mid: str, body: MessagePayload):
    msg = STATE.get_message(mid)
    if not msg:
        return JSONResponse({"ok": False, "msg": "메시지 없음"}, status_code=404)
    msg.payload = body.payload
    STATE.save()
    return {"ok": True, "msg": "저장"}


class MessageTarget(BaseModel):
    target: Optional[str] = None


@app.patch("/api/messages/{mid}/target")
async def api_message_target(mid: str, body: MessageTarget):
    msg = STATE.get_message(mid)
    if not msg:
        return JSONResponse({"ok": False, "msg": "메시지 없음"}, status_code=404)
    msg.target = body.target
    STATE.save()
    return {"ok": True, "msg": "저장"}


class MessageProtocol(BaseModel):
    protocol: str = "udp"


@app.patch("/api/messages/{mid}/protocol")
async def api_message_protocol(mid: str, body: MessageProtocol):
    msg = STATE.get_message(mid)
    if not msg:
        return JSONResponse({"ok": False, "msg": "메시지 없음"}, status_code=404)
    if body.protocol not in ("udp", "tcp"):
        return JSONResponse({"ok": False, "msg": "udp 또는 tcp만 허용"}, status_code=400)
    msg.protocol = body.protocol
    STATE.save()
    return {"ok": True, "msg": f"{mid} → {body.protocol.upper()}"}


@app.post("/api/messages/{mid}/send")
async def api_message_send(mid: str):
    msg = STATE.get_message(mid)
    if not msg:
        return JSONResponse({"ok": False, "msg": "메시지 없음"}, status_code=404)
    has_channels = bool(COMM.channel_clients)
    if not STATE.targets and not has_channels:
        return JSONResponse({"ok": False, "msg": "송신 대상 없음 — 통신관리에서 추가하거나 DtamChannel로 연결"}, status_code=400)

    handler = registry.get(mid)
    if handler is None:
        return JSONResponse({"ok": False, "msg": "레지스트리 미등록 메시지"}, status_code=400)

    # 1) generator 로 데이터 생성
    opts = dict(msg.payload or {})
    image_bytes = b""
    try:
        if mid == "4101" and hasattr(handler.generator, "__module__"):
            gen_mod = __import__(handler.generator.__module__, fromlist=["generate_with_bytes"])
            if hasattr(gen_mod, "generate_with_bytes"):
                data, image_bytes = gen_mod.generate_with_bytes(**opts)
            else:
                data = handler.generator(**opts)
        else:
            data = handler.generator(**opts)
    except Exception as e:
        return {"ok": False, "msg": f"데이터 생성 실패: {type(e).__name__}: {e}", "sent": None}

    import base64
    if mid == "4101" and not image_bytes:
        image_bytes = base64.b64decode(data.get("_image_base64", "")) if data.get("_image_base64") else b""

    # 2) 연결된 DtamChannel 클라이언트에 자동 전송 (포트 설정 불필요)
    ch_count = COMM.send_to_channels(data, image_bytes)

    # 3) 설정된 target 으로도 전송 (기존 방식)
    result = None
    target = None
    if STATE.targets:
        target = STATE.get_target(msg.target) if msg.target else None
        if target is None:
            target = STATE.targets[0]
        result = COMM.send_message(mid, data, target, image_bytes=image_bytes)

    # 4) 통계 업데이트 및 응답
    now = time.time()
    sent_payload = data if result is None else result.payload
    target_ok = result is not None and result.ok

    if target_ok or ch_count:
        msg.tx_count += 1
        msg.tx_last_ts = now
        msg.tx_last_bytes = json.dumps(sent_payload, ensure_ascii=False).encode("utf-8") if sent_payload else b""
        msg.tx_last_protocol = msg.protocol
        if target_ok and target:
            target.tx_count += 1
            target.tx_last_ts = now
        parts = []
        if target_ok and target:
            parts.append(f"[{target.name}] {result.target} {result.bytes_sent}B")
        if ch_count:
            parts.append(f"채널 {ch_count}개")
        return {"ok": True, "msg": "송신 " + " + ".join(parts), "sent": sent_payload}

    errors = result.errors if result else []
    return {"ok": False, "msg": "; ".join(errors) or "송신 실패", "sent": sent_payload}


@app.get("/api/messages/{mid}/tx_last")
async def api_message_tx_last(mid: str):
    msg = STATE.get_message(mid)
    if not msg:
        return JSONResponse({"ok": False, "msg": "메시지 없음"}, status_code=404)
    try:
        parsed = json.loads(msg.tx_last_bytes.decode("utf-8")) if msg.tx_last_bytes else None
    except Exception:
        parsed = None
    return {
        "id": msg.id,
        "name": msg.name,
        "name_en": msg.name_en,
        "target": msg.target,
        "payload_template": msg.payload,
        "last_sent": parsed,
        "last_sent_bytes_len": len(msg.tx_last_bytes),
        "tx_count": msg.tx_count,
        "tx_last_ts": msg.tx_last_ts,
        "protocol": getattr(msg, "tx_last_protocol", "udp"),
    }


@app.get("/api/messages/{mid}/rx_last")
async def api_message_rx_last(mid: str):
    msg = STATE.get_message(mid)
    if not msg:
        return JSONResponse({"ok": False, "msg": "메시지 없음"}, status_code=404)
    return {
        "id": msg.id,
        "name": msg.name,
        "name_en": msg.name_en,
        "last_received": msg.rx_last_payload,
        "rx_count": msg.rx_count,
        "rx_last_ts": msg.rx_last_ts,
    }
