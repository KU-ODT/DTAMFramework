"""DTAM 서버 이벤트를 파일 DB 로 남기는 writer.

구조::

    <db_root>/
      ServerStart_<UTC-timestamp>/
        ScheduledFlight/
          1201_UAM0001.json
          1202_UAM0002.json
        ScheduledFlightModification/
          ...
        TacticalActionCommand/
          ...
        VehicleStatus/
          20260420T103501100Z_UAM0001.json
        SimModeSetup/
          20260420T103500200Z.json
        ...

파일명 규칙:
- **3001 ScheduledFlight**: ``{flightPlanNumber}_{aircraftId}.json`` (ICD 기준)
- **3002 Modification / 3003 Tactical**: ``{commandId}.json`` (commandId 없으면 timestamp)
- **4001 VehicleStatus**: 메시지 안의 ``timestamp`` 와 함께 등장하는 각 UAM 별로
  ``{iso_compact}_{vehicleId}.json`` 로 샘플 저장
- 그 외: ``{iso_compact}.json`` 로 이벤트 단위 저장
"""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from DTAM_CoreServer.app.model.message import DB_FOLDER_FOR_MID


def _utc_stamp(dt: Optional[datetime] = None) -> str:
    """``YYYYMMDDTHHMMSSmmmZ`` — 파일명 친화적인 UTC 타임스탬프."""
    now = dt or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    return now.strftime("%Y%m%dT%H%M%S") + f"{now.microsecond // 1000:03d}Z"


_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize(value: Any, default: str = "x") -> str:
    text = str(value or default).strip()
    text = _SAFE_CHARS.sub("_", text)
    return text or default


class DtamFileDb:
    """Thread-safe 파일 DB.

    서버 시작 시점의 timestamp 를 루트로 고정하고, 이벤트마다 해당 메시지
    타입 폴더 아래에 JSON 을 쌓는다. 4001 과 같은 고빈도 메시지를 고려해
    파일명이 충돌하지 않게 밀리초 단위 타임스탬프를 사용한다.
    """

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

    # ── 내부 유틸 ─────────────────────────────────────────────
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

    # ── 공개 API ──────────────────────────────────────────────
    def write_event(
        self,
        mid: str,
        payload: Dict[str, Any],
        *,
        extra_bytes: bytes = b"",
    ) -> List[Path]:
        """메시지 ID 와 payload 를 받아 하나 이상의 JSON 파일을 쓴다.

        4001 은 여러 UAM 의 샘플을 포함할 수 있어 UAM 별로 분해된다.
        """
        mid = str(mid)
        if not isinstance(payload, dict):
            return []

        with self._lock:
            self._record_meta(mid)
            folder = self._folder_for(mid)

            # ── 주기성 상태 메시지는 파일을 쌓지 않고 latest 하나에 덮어쓴다 ──
            if mid == "0003":
                # Common Time Info — 1 Hz 주기. 매 tick 쌓으면 초당 1 파일이 되므로
                # 단일 파일(latest.json)에 갱신만 수행한다.
                path = folder / "latest.json"
                return [self._write(path, payload)]

            if mid == "0002":
                # Module Status — 1 Hz 주기. 모듈별로 단일 파일 유지.
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
                ts = _sanitize(payload.get("timestamp") or _utc_stamp()).replace(":", "")
                written: List[Path] = []
                single_aircraft_id = payload.get("aircraftId") or payload.get("vehicleId") or payload.get("vehicle_id")
                if single_aircraft_id:
                    acid = _sanitize(single_aircraft_id, "UAM0000")
                    path = folder / f"{ts}_{acid}.json"
                    return [self._write(path, payload)]
                for key, value in payload.items():
                    if key == "timestamp" or not isinstance(value, dict):
                        continue
                    acid = _sanitize(key, "UAM0000")
                    path = folder / f"{ts}_{acid}.json"
                    written.append(self._write(path, {
                        "timestamp": payload.get("timestamp"),
                        "aircraftId": key,
                        **value,
                    }))
                return written

            if mid == "4101":
                ts = _sanitize(payload.get("timestamp") or _utc_stamp()).replace(":", "")
                vid = _sanitize(payload.get("vehicle_id") or "UAM0000")
                cam = _sanitize(payload.get("camera_name") or "cam")
                seq = _sanitize(payload.get("sequence") or "0")
                base = folder / f"{ts}_{vid}_{cam}_{seq}"
                written = [self._write(base.with_suffix(".json"), payload)]
                if extra_bytes:
                    bin_path = base.with_suffix(".bin")
                    bin_path.write_bytes(extra_bytes)
                    written.append(bin_path)
                return written

            # 기본: 이벤트 단위 타임스탬프
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
