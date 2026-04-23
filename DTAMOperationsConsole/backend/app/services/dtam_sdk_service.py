"""Thin integration layer between the operations console and DTAM_SDK."""

from __future__ import annotations

import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from backend.app.core.settings import settings
from backend.app.schemas.icd import IcdSendResponse


SUPPORTED_UDP_MESSAGES = {"1001", "1002", "1003"}
MODULE_SOURCE_NAME = "DTAMOperationsConsole"
HEARTBEAT_PERIOD_S = 1.0

_heartbeat_stop = threading.Event()
_heartbeat_thread: threading.Thread | None = None


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


def _iso_ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _create_client():
    sdk_root = _ensure_sdk_on_path()
    from dtam_client import DtamClient

    target_ip = os.environ.get("DTAM_TARGET_IP")
    target_port = os.environ.get("DTAM_TARGET_PORT")
    if target_ip or target_port:
        return DtamClient(
            target_ip=target_ip or "127.0.0.1",
            target_udp_port=int(target_port or 17000),
            auto_listen=False,
        )

    config_path = sdk_root / "dtam_config.json"
    if config_path.exists():
        return DtamClient.from_config(str(config_path), auto_listen=False)
    return DtamClient(target_ip="127.0.0.1", target_udp_port=17000, auto_listen=False)


def start_module_status_heartbeat() -> None:
    global _heartbeat_thread
    if _heartbeat_thread is not None and _heartbeat_thread.is_alive():
        return
    _heartbeat_stop.clear()
    _heartbeat_thread = threading.Thread(
        target=_module_status_loop,
        name="dtam-operations-console-heartbeat",
        daemon=True,
    )
    _heartbeat_thread.start()


def stop_module_status_heartbeat() -> None:
    _heartbeat_stop.set()
    thread = _heartbeat_thread
    if thread is not None and thread.is_alive():
        thread.join(timeout=2.0)


def _module_status_loop() -> None:
    client = None
    try:
        while not _heartbeat_stop.is_set():
            try:
                if client is None:
                    client = _create_client()
                client.push_module_status(
                    {
                        "timestamp": _iso_ts(),
                        "source": MODULE_SOURCE_NAME,
                        "status": 1,
                    }
                )
            except Exception:
                if client is not None:
                    try:
                        client.close()
                    except Exception:
                        pass
                client = None
            if _heartbeat_stop.wait(HEARTBEAT_PERIOD_S):
                break
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def send_udp_message(
    message_id: str,
    payload: dict[str, Any],
    *,
    target_ip: str | None = None,
    target_port: int | None = None,
) -> IcdSendResponse:
    """Validate and send one supported ICD payload over UDP through DTAM_SDK."""
    normalized_id = str(message_id).strip()
    if normalized_id not in SUPPORTED_UDP_MESSAGES:
        raise HTTPException(status_code=404, detail=f"Unsupported UDP ICD message: {message_id}")

    client = _create_client()
    try:
        result = client.send(
            normalized_id,
            payload,
            target_ip=target_ip,
            udp_port=target_port,
        )
    finally:
        client.close()

    return IcdSendResponse(
        message_id=normalized_id,
        protocol="UDP",
        sent=bool(result),
        bytes_sent=result.bytes_sent,
        target=result.target,
        errors=list(result.errors),
        payload=payload,
    )
