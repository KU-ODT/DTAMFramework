from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from ..config import DATA_DIR

LAYOUT_DIR = DATA_DIR / "layouts"

_INVALID_NAME = re.compile(r"[/\\]|\.\.")
_lock = Lock()


def _safe_name(name: str) -> str:
    text = (name or "").strip()
    if not text or _INVALID_NAME.search(text):
        raise ValueError(f"Invalid layout name: {name!r}")
    return text


def _path(name: str) -> Path:
    return LAYOUT_DIR / f"{_safe_name(name)}.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _summary(name: str, data: dict, mtime: float) -> dict:
    meta = data.get("meta") or {}
    updated = meta.get("updatedAt") or datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    return {
        "name": name,
        "displayName": meta.get("name") or name,
        "entityCount": len(data.get("entities") or []),
        "linkCount": len(data.get("links") or []),
        "updatedAt": updated,
    }


def list_layouts() -> list[dict]:
    LAYOUT_DIR.mkdir(parents=True, exist_ok=True)
    items: list[dict] = []
    for path in sorted(LAYOUT_DIR.glob("*.json")):
        try:
            data = _read(path)
        except (OSError, json.JSONDecodeError):
            continue
        items.append(_summary(path.stem, data, path.stat().st_mtime))
    return items


def get_layout(name: str) -> dict:
    path = _path(name)
    if not path.is_file():
        raise KeyError(f"Layout not found: {name}")
    with _lock:
        return _read(path)


def save_layout(name: str, layout: dict) -> dict:
    safe = _safe_name(name)
    path = LAYOUT_DIR / f"{safe}.json"
    payload = dict(layout or {})
    meta = dict(payload.get("meta") or {})
    meta.setdefault("name", safe)
    meta["updatedAt"] = datetime.now(timezone.utc).isoformat()
    payload["meta"] = meta
    payload.setdefault("entities", [])
    payload.setdefault("links", [])
    LAYOUT_DIR.mkdir(parents=True, exist_ok=True)
    with _lock:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return payload


def delete_layout(name: str) -> None:
    path = _path(name)
    with _lock:
        if not path.is_file():
            raise KeyError(f"Layout not found: {name}")
        path.unlink()
