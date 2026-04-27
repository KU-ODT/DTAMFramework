"""Operations Console ↔ DTAM 서버 통합 서비스.

- 0002 모듈 상태 heartbeat 는 ``DtamModule`` (WebSocket /ws/dtam) 가 자동 송신.
- ICD 송신은 운영자/외부 트리거 호환을 위해 REST 그대로 (`DtamRest.push`).
- 서버 스냅샷 / 모듈 프로세스 start-stop 도 REST.

이전(legacy):
  · DtamClient 기반 UDP heartbeat thread + urllib 직접 호출.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from backend.app.core.settings import settings
from backend.app.schemas.icd import IcdSendResponse


SUPPORTED_UDP_MESSAGES = {"1001", "1002", "1003"}
MODULE_SOURCE_NAME = "DTAMOperationsConsole"

CORE_HTTP_PORT = 8095
STATE_HTTP_PORT = 8096
STATE_WS_PORT = 8096


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


# ── DtamModule heartbeat (WebSocket) ─────────────────────────
_module: Any = None  # DtamModule


def start_module_status_heartbeat() -> None:
    """0002 module status 1Hz 자동 송신을 시작."""
    global _module
    if _module is not None:
        return
    _ensure_sdk_on_path()
    from dtam_client import DtamModule, Role  # type: ignore

    server_url = f"ws://{_server_ip()}:{STATE_WS_PORT}/ws/dtam"
    _module = DtamModule.start(
        role=Role.MONITORING,
        server_url=server_url,
        heartbeat=True,
    )


def stop_module_status_heartbeat() -> None:
    global _module
    mod = _module
    _module = None
    if mod is None:
        return
    try:
        mod.close()
    except Exception:
        pass


# ── REST 기반 ICD 송신 / 서버 조회 / 프로세스 제어 ──────────
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
    target_port: int | None = None,
) -> IcdSendResponse:
    """ICD 메시지를 State Server REST(``POST /api/msg/{mid}``) 로 송신."""
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
        protocol="HTTP",
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
