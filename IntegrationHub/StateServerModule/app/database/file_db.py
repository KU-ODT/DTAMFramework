"""Thread-safe file DB writer for DTAM server events.
"""
from __future__ import annotations

import json
import re
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from IntegrationHub.CoreServerModule.app.model.message import DB_FOLDER_FOR_MID


def _utc_stamp(dt: Optional[datetime] = None) -> str:
    """Internal helper."""
    now = dt or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    return now.strftime("%Y%m%dT%H%M%S") + f"{now.microsecond // 1000:03d}Z"


_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_SESSION_DIR_PREFIX = "ServerStart_"
MAX_SESSION_DIRS = 5


def _sanitize(value: Any, default: str = "x") -> str:
    text = str(value or default).strip()
    text = _SAFE_CHARS.sub("_", text)
    return text or default


class DtamFileDb:
    """Internal DTAM helper."""

    def __init__(self, db_root: Path) -> None:
        self.db_root = Path(db_root)
        self.session_id: str = _utc_stamp()
        self.session_dir: Path = self.db_root / f"ServerStart_{self.session_id}"
        self._lock = threading.Lock()
        self._counts: Dict[str, int] = {}
        self._last_write_ts: Dict[str, str] = {}
        self.session_dir.mkdir(parents=True, exist_ok=True)
        (self.session_dir / "_session.json").write_text(
            json.dumps({
                "session_id": self.session_id,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.prune_old_sessions(MAX_SESSION_DIRS)

    def prune_old_sessions(self, max_sessions: int = MAX_SESSION_DIRS) -> List[Path]:
        """Keep only the newest server DB session directories.

        This is intentionally conservative: only direct child directories named
        ``ServerStart_*`` under ``db_root`` are removed, and symlinks/reparse
        points are skipped.
        """
        if max_sessions <= 0 or not self.db_root.is_dir():
            return []

        root = self.db_root.resolve()
        session_dirs = sorted(
            (
                path
                for path in self.db_root.iterdir()
                if path.is_dir()
                and not path.is_symlink()
                and path.name.startswith(_SESSION_DIR_PREFIX)
            ),
            key=lambda path: path.name,
            reverse=True,
        )
        stale_dirs = session_dirs[max_sessions:]
        removed: List[Path] = []

        for path in stale_dirs:
            try:
                resolved = path.resolve()
                if resolved.parent != root or not path.name.startswith(_SESSION_DIR_PREFIX):
                    continue
                shutil.rmtree(path)
                removed.append(path)
            except Exception:
                # DB pruning must never prevent the server from starting.
                continue
        return removed

    # Registration handling
    def _folder_for(self, mid: str) -> Path:
        folder_name = DB_FOLDER_FOR_MID.get(mid, f"Msg_{mid}")
        path = self.session_dir / folder_name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _record_meta(self, mid: str) -> None:
        self._counts[mid] = int(self._counts.get(mid, 0)) + 1
        self._last_write_ts[mid] = _utc_stamp()

    def _write(self, path: Path, payload: Any) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    # Registration handling
    def write_event(
        self,
        mid: str,
        payload: Dict[str, Any],
        *,
        extra_bytes: bytes = b"",
    ) -> List[Path]:
        """Internal DTAM helper."""
        mid = str(mid)
        if not isinstance(payload, dict):
            return []

        with self._lock:
            self._record_meta(mid)
            folder = self._folder_for(mid)

            # Registration handling
            if mid == "0003":
                # Registration handling
                path = folder / "latest.json"
                return [self._write(path, payload)]

            if mid == "0002":
                # Registration handling
                source = _sanitize(payload.get("source") or "", "")
                name = f"{source}.json" if source else "unknown.json"
                return [self._write(folder / name, payload)]

            if mid == "3001":
                fpn = _sanitize(payload.get("flightPlanNumber"), "000")
                acid = _sanitize(payload.get("aircraftId"), "UAM0000")
                path = folder / f"{fpn}_{acid}.json"
                return [self._write(path, payload)]

            if mid in ("3002", "3003"):
                cmd_id = _sanitize(payload.get("commandId") or "", "")
                if not cmd_id:
                    cmd_id = _utc_stamp()
                acid = _sanitize(payload.get("aircraftId") or "", "")
                name = f"{cmd_id}_{acid}.json" if acid else f"{cmd_id}.json"
                return [self._write(folder / name, payload)]

            if mid == "4001":
                written: List[Path] = []
                single_aircraft_id = payload.get("aircraftId") or payload.get("vehicleId") or payload.get("vehicle_id")
                if single_aircraft_id:
                    acid = _sanitize(single_aircraft_id, "UAM0000")
                    latest_payload = dict(payload)
                    written.append(self._write(folder / "latest.json", latest_payload))
                    written.append(self._write(folder / f"latest_{acid}.json", latest_payload))
                    return written
                written.append(self._write(folder / "latest.json", payload))
                for key, value in payload.items():
                    if key == "timestamp" or not isinstance(value, dict):
                        continue
                    acid = _sanitize(key, "UAM0000")
                    written.append(self._write(folder / f"latest_{acid}.json", {
                        "timestamp": payload.get("timestamp"),
                        "aircraftId": key,
                        **value,
                    }))
                return written

            if mid == "4101":
                vid = _sanitize(payload.get("vehicle_id") or "UAM0000")
                cam = _sanitize(payload.get("camera_name") or "cam")
                base = folder / f"latest_{vid}_{cam}"
                latest_payload = dict(payload)
                written = [
                    self._write(folder / "latest.json", latest_payload),
                    self._write(base.with_suffix(".json"), latest_payload),
                ]
                if extra_bytes:
                    bin_path = base.with_suffix(".bin")
                    bin_path.write_bytes(extra_bytes)
                    written.append(bin_path)
                return written

            if mid == "4103":
                event_id = _sanitize(payload.get("eventId") or payload.get("event_id") or "", "")
                if not event_id:
                    event_id = _utc_stamp()
                acid = _sanitize(payload.get("aircraftId") or payload.get("vehicleId") or "", "")
                latest_payload = dict(payload)
                written = [self._write(folder / "latest.json", latest_payload)]
                if acid:
                    written.append(self._write(folder / f"latest_{acid}.json", latest_payload))
                    written.append(self._write(folder / f"{event_id}_{acid}.json", latest_payload))
                else:
                    written.append(self._write(folder / f"{event_id}.json", latest_payload))
                return written

            # Registration handling
            ts = _sanitize(payload.get("timestamp") or _utc_stamp()).replace(":", "")
            source = _sanitize(payload.get("source") or "", "")
            name = f"{ts}_{source}.json" if source else f"{ts}.json"
            return [self._write(folder / name, payload)]

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "session_id": self.session_id,
                "session_dir": str(self.session_dir),
                "counts": dict(self._counts),
                "last_write_ts": dict(self._last_write_ts),
            }

    def find_latest_event(
        self,
        mid: str,
        *,
        field: Optional[str] = None,
        value: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return the newest saved JSON payload for a message id.

        Optional field/value filtering is used by modules that need a central
        server lookup without reading the DB folder directly.
        """
        mid = str(mid)
        folder_name = DB_FOLDER_FOR_MID.get(mid, f"Msg_{mid}")
        folder = self.session_dir / folder_name
        if not folder.is_dir():
            return None

        target_value = str(value or "").strip()
        target_basename = Path(target_value).name if target_value else ""
        candidates = sorted(
            (path for path in folder.glob("*.json") if path.is_file()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

        for path in candidates:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if field and target_value:
                payload_value = str((payload or {}).get(field) or "").strip()
                if payload_value != target_value and Path(payload_value).name != target_basename:
                    continue
            return {
                "mid": mid,
                "path": str(path),
                "payload": payload,
                "modified_at": datetime.fromtimestamp(
                    path.stat().st_mtime,
                    timezone.utc,
                ).isoformat(),
            }
        return None

    def list_session_dirs(self) -> List[str]:
        if not self.db_root.is_dir():
            return []
        return sorted(p.name for p in self.db_root.iterdir() if p.is_dir())


__all__ = ["DtamFileDb"]
