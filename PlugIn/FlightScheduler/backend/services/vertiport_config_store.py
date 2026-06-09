from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from ..config import DATA_DIR

CONFIG_DIR = DATA_DIR / "vertiport_configs"

_INVALID = re.compile(r"[/\\]|\.\.")
_lock = Lock()


def _safe_id(vertiport_id: str) -> str:
    text = (vertiport_id or "").strip()
    if not text or _INVALID.search(text):
        raise ValueError(f"Invalid vertiport id: {vertiport_id!r}")
    return text


def _path(vertiport_id: str) -> Path:
    return CONFIG_DIR / f"{_safe_id(vertiport_id)}.json"


def list_configs() -> list[dict]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    items: list[dict] = []
    for path in sorted(CONFIG_DIR.glob("*.json")):
        try:
            items.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return items


def get_config(vertiport_id: str) -> dict | None:
    path = _path(vertiport_id)
    if not path.is_file():
        return None
    with _lock:
        return json.loads(path.read_text(encoding="utf-8"))


def put_config(vertiport_id: str, payload: dict) -> dict:
    safe = _safe_id(vertiport_id)
    path = CONFIG_DIR / f"{safe}.json"
    fleet = payload.get("fleet") or {}
    gate_assignments = fleet.get("gateAssignments") or {}
    config = {
        "vertiportId": safe,
        "layoutName": payload.get("layoutName") or None,
        "fleet": {"gateAssignments": dict(gate_assignments)},
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with _lock:
        path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return config


def delete_config(vertiport_id: str) -> None:
    path = _path(vertiport_id)
    with _lock:
        if path.is_file():
            path.unlink()
