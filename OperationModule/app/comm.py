"""Operations Console REST facade for the ServerRevision DTAM stack."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.core.settings import settings
from app.schemas.icd import IcdSendResponse


CORE_HTTP_PORT = 8095
STATE_HTTP_PORT = int(os.environ.get("DTAM_WS_PORT") or 8096)


def _sdk_root() -> Path:
    return settings.project_root.parent / "DTAMSDK"


def _ensure_sdk_on_path() -> Path:
    sdk_root = _sdk_root()
    if not sdk_root.exists():
        raise HTTPException(status_code=500, detail=f"DTAMSDK not found at {sdk_root}")
    sdk_path = str(sdk_root)
    if sdk_path not in sys.path:
        sys.path.insert(0, sdk_path)
    return sdk_root


def _server_ip() -> str:
    return os.environ.get("DTAM_TARGET_IP") or "127.0.0.1"


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
    """Send one ICD payload through SimulationState REST."""

    normalized_id = str(message_id).strip()
    ip = target_ip or _server_ip()
    target = f"{ip}:{STATE_HTTP_PORT}"

    _ensure_sdk_on_path()
    from dtam_client import DtamRest, DtamRestError  # type: ignore

    sent = False
    errors: list[str] = []
    try:
        res = DtamRest(f"http://{ip}:{STATE_HTTP_PORT}").push(normalized_id, payload, role="")
        sent = bool(res.get("ok"))
        if not sent:
            details = res.get("details") or {}
            for role, detail in details.items():
                if isinstance(detail, dict) and not detail.get("ok"):
                    errors.extend(f"[{role}] {error}" for error in (detail.get("errors") or []))
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
    try:
        return _state_rest().snapshot()
    except Exception:
        return {"registry": {"modules": []}}


def control_module_process(role: str, action: str) -> dict[str, Any]:
    rest = _core_rest()
    try:
        if action == "start":
            return rest.process_start(role)
        if action == "stop":
            return rest.process_stop(role)
        return {"ok": False, "error": f"unknown action: {action}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
