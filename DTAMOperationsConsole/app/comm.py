"""Operations Console DTAM 통신 layer.

WebSocket (heartbeat / 수신) 은 ``MonitoringComm(DtamModule)`` 클래스로,
ICD 단발 송신 / 서버 조회 / 프로세스 제어는 REST facade 함수들로 분리.

- WS: ``MonitoringComm`` — 0002 heartbeat 자동 + 향후 @on_receive 핸들러 자리
- REST: ``send_icd_command`` (POST /api/msg/{mid}), ``get_registry_snapshot``,
  ``control_module_process``

DTAM 자체는 WebSocket 단일 채널. REST 는 운영자가 Swagger UI 에서 단발
명령을 보낼 때 쓰는 facade 일 뿐.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException

from app.config import settings
from app.schemas.icd import IcdSendResponse


# OpsConsole 이 REST 로 직접 송신 가능한 ICD 메시지.
# (시뮬레이션 모드 / 통제 / 시나리오 — 모두 user→server 방향 명령)
SUPPORTED_ICD_MESSAGES = {"1001", "1002", "1003"}
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


# ── WebSocket 통신 layer (DtamModule 서브클래스) ─────────────
def _import_dtam_sdk():
    _ensure_sdk_on_path()
    from dtam_client import DtamModule, Role  # type: ignore
    return DtamModule, Role


class MonitoringComm:
    """OpsConsole DTAM 통신 layer (lazy DtamModule 서브클래스).

    DtamModule 은 SDK path 가 sys.path 에 들어간 뒤에야 import 가능하므로,
    실제 서브클래스 정의는 :func:`_build_class` 안에서 처리. ``MonitoringComm()``
    호출 시 lazily 생성·반환.
    """

    def __new__(cls, **kwargs):
        impl = _build_class()
        return impl(**kwargs)


def _build_class():
    """SDK 가 sys.path 에 올라간 뒤 정의되는 실제 DtamModule 서브클래스."""
    DtamModule, Role = _import_dtam_sdk()
    from dtam_client import on_receive  # noqa: F401 — 향후 핸들러용

    class _MonitoringComm(DtamModule):
        role = Role.MONITORING

        def __init__(self, *, target_ip: Optional[str] = None,
                     ws_port: int = STATE_WS_PORT) -> None:
            ip = target_ip or _server_ip()
            super().__init__(
                server_url=f"ws://{ip}:{ws_port}/ws/dtam",
                heartbeat=True,
            )

        # 향후 monitoring 이 받기로 한 forwarding (FORWARD_RULES 상 2002/4001/4101 도
        # 가능) 핸들러 자리 — 현재는 heartbeat 전용.

    return _MonitoringComm


# ── 모듈 레벨 lifecycle (server.py 가 호출) ──────────────────
_module: Any = None  # MonitoringComm 인스턴스


def start_module_status_heartbeat() -> None:
    """0002 module status 1Hz 자동 송신을 시작."""
    global _module
    if _module is not None:
        return
    _module = MonitoringComm()


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
