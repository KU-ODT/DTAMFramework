"""Operations Console REST facade for DTAM.

WebSocket lifecycle (``MonitoringService``) lives in ``app.lifespan`` —
attached to ``app.state.monitoring_service`` and accessed via
``app.deps.get_monitoring_service`` (FastAPI ``Depends``). 이 파일은 REST
facade 만 담당:

- ``send_icd_command``        — POST /api/msg/{mid} (State Server)
- ``get_registry_snapshot``   — GET  /api/state    (State Server)
- ``control_module_process``  — POST /api/v1/process/{role}/{action} (Core)

DTAM 자체는 WebSocket 단일 채널. REST 는 운영자가 Swagger UI 에서 단발
명령을 보낼 때 쓰는 facade 일 뿐이다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.config import settings
from app.schemas.icd import IcdSendResponse


CORE_HTTP_PORT = 8095
STATE_HTTP_PORT = 8096


def _sdk_root() -> Path:
    return settings.project_root.parent / "DTAM_SDK"


def _ensure_sdk_on_path() -> Path:
    sdk_root = _sdk_root()
    if not sdk_root.exists():
        raise HTTPException(status_code=500, detail=f"DTAM_SDK not found at {sdk_root}")
    sdk_path = str(sdk_root)
    if sdk_path not in sys.path:
        sys.path.insert(0, sdk_path)
    return sdk_root


def _server_ip() -> str:
    return os.environ.get("DTAM_TARGET_IP") or "127.0.0.1"


# ── REST facade (Swagger UI 에서 운영자가 직접 호출) ──────────
def _state_rest():
    _ensure_sdk_on_path()
    from dtam_client import DtamRest  # type: ignore
    return DtamRest(f"http://{_server_ip()}:{STATE_HTTP_PORT}")


def _core_rest():
    _ensure_sdk_on_path()
    from dtam_client import DtamRest  # type: ignore
    return DtamRest(f"http://{_server_ip()}:{CORE_HTTP_PORT}")


def send_icd_command(
    message_id: str,
    payload: dict[str, Any],
    *,
    target_ip: str | None = None,
) -> IcdSendResponse:
    """ICD 메시지를 State Server REST(``POST /api/msg/{mid}``) 로 송신.

    State 서버 포트는 ``STATE_HTTP_PORT`` 로 고정. ``target_ip`` 만 환경별로
    오버라이드 가능 (예: 클라우드 배포 시 외부 IP).
    """
    normalized_id = str(message_id).strip()
    ip = target_ip or _server_ip()
    target = f"{ip}:{STATE_HTTP_PORT}"

    _ensure_sdk_on_path()
    from dtam_client import DtamRest, DtamRestError  # type: ignore

    rest = DtamRest(f"http://{ip}:{STATE_HTTP_PORT}")
    sent = False
    errors: list[str] = []
    try:
        res = rest.push(normalized_id, payload, role="")
        sent = bool(res.get("ok"))
        if not sent:
            details = res.get("details") or {}
            for role, d in details.items():
                if isinstance(d, dict) and not d.get("ok"):
                    for e in (d.get("errors") or []):
                        errors.append(f"[{role}] {e}")
            if "error" in res:
                errors.append(str(res["error"]))
            if not errors:
                errors = ["Unknown REST validation error"]
    except DtamRestError as exc:
        errors = [str(exc)]
    except Exception as exc:
        errors = [f"{type(exc).__name__}: {exc}"]

    return IcdSendResponse(
        message_id=normalized_id,
        protocol="ws",
        sent=sent,
        bytes_sent=0,
        target=target,
        errors=errors,
        payload=payload,
    )


def get_registry_snapshot() -> dict[str, Any]:
    """State Server 의 ``GET /api/state`` 결과를 반환."""
    try:
        return _state_rest().snapshot()
    except Exception:
        return {"registry": {"modules": []}}


def control_module_process(role: str, action: str) -> dict[str, Any]:
    """Core Server 의 ``POST /api/v1/process/{role}/{start|stop}`` 호출."""
    rest = _core_rest()
    try:
        if action == "start":
            return rest.process_start(role)
        if action == "stop":
            return rest.process_stop(role)
        return {"ok": False, "error": f"unknown action: {action}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
