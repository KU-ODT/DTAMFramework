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
import urllib.request
import json


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


def send_icd_command(
    message_id: str,
    payload: dict[str, Any],
    *,
    target_ip: str | None = None,
    target_port: int | None = None,
) -> IcdSendResponse:
    """Validate and send one supported ICD payload over HTTP REST to the State Server."""
    normalized_id = str(message_id).strip()
    
    # State Server HTTP 포트는 8096으로 기본 설정
    http_port = 8096
    ip = target_ip or os.environ.get("DTAM_TARGET_IP") or "127.0.0.1"
    
    url = f"http://{ip}:{http_port}/api/msg/{normalized_id}"
    
    body = json.dumps({"role": "", "payload": payload}).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
    
    try:
        with urllib.request.urlopen(req, timeout=5.0) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            sent = res_data.get("ok", False)
            if sent:
                errors = []
            else:
                errors = [res_data.get("error")] if "error" in res_data else []
                if "details" in res_data:
                    for role, d in res_data["details"].items():
                        if not d.get("ok") and "errors" in d:
                            errors.extend([f"[{role}] {e}" for e in d["errors"]])
                if not errors:
                    errors = ["Unknown REST validation error"]
    except Exception as e:
        sent = False
        errors = [str(e)]

    return IcdSendResponse(
        message_id=normalized_id,
        protocol="HTTP",
        sent=sent,
        bytes_sent=len(body) if sent else 0,
        target=f"{ip}:{http_port}",
        errors=errors,
        payload=payload,
    )

def get_registry_snapshot() -> dict[str, Any]:
    """Fetch module registry snapshot from the State Server (8096)."""
    http_port = 8096
    ip = os.environ.get("DTAM_TARGET_IP") or "127.0.0.1"
    url = f"http://{ip}:{http_port}/api/state"
    
    try:
        with urllib.request.urlopen(url, timeout=3.0) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception:
        return {"registry": {"modules": []}}

def control_module_process(role: str, action: str) -> dict[str, Any]:
    """Send start/stop command to the Core Server (8095)."""
    # Core Server HTTP 포트는 8095
    http_port = 8095
    ip = os.environ.get("DTAM_TARGET_IP") or "127.0.0.1"
    
    # action: "start" or "stop"
    url = f"http://{ip}:{http_port}/api/v1/process/{role}/{action}"
    
    try:
        req = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(req, timeout=5.0) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return {"ok": False, "error": str(e)}
