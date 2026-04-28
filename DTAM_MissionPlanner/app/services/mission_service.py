"""DTAM Mission Planner 서비스 계층 (WebSocket /ws/dtam + 도메인 통합).

``MissionModule`` (SDK 베이스) 를 상속해 2001/2002 핸들러를 자체 처리.
2001 수신 시 자동 3001 트리거 — 검증·송신·통계 모두 핸들러 안에서 처리하고,
server.py 에서는 단일 callable (``auto_3001_pipeline``) 만 주입해 server.py
의 module-level helpers 와의 결합을 한 군데로 좁힌다.

외부 인터페이스 (server.py / routes/* 가 사용):
  - MissionService(target_ip, ws_port, auto_3001_pipeline=...)
  - .describe() → dict
  - .send_scheduled_flight(record) → dict
  - .send_scheduled_flights(records) → dict
  - .reconfigure(target_ip=..., ws_port=...) → dict
  - .close()

``auto_3001_pipeline`` 계약:
  Callable[[Dict], Dict]
  Input: 2001 raw payload dict (scenarioFileName 등)
  Output: ICD export bundle dict (validation, record/records, fleet, ...)
"""
from __future__ import annotations

import logging
import sys
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_SDK_ROOT = Path(__file__).resolve().parents[3] / "DTAM_SDK"
if _SDK_ROOT.is_dir() and str(_SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(_SDK_ROOT))

from dtam_client import MissionModule  # type: ignore

logger = logging.getLogger(__name__)

Auto3001Pipeline = Callable[[Dict[str, Any]], Dict[str, Any]]


def _result_raw(result: Any) -> Dict[str, Any]:
    """수신 콜백 인자(dataclass 또는 dict)를 dict 으로 정규화."""
    if isinstance(result, dict):
        return result
    raw = getattr(result, "raw", None)
    if isinstance(raw, dict):
        return raw
    import dataclasses as _dc
    if _dc.is_dataclass(result) and not isinstance(result, type):
        return _dc.asdict(result)
    return {}


def _coerce_int(value: Any, default: int) -> int:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _ensure_plan_metadata(record: Dict[str, Any]) -> Dict[str, Any]:
    """3001 스키마에 맞춰 ``planVersion`` / ``planStatus`` 를 채운다."""
    out = deepcopy(record)
    if "planVersion" not in out or not isinstance(out.get("planVersion"), int):
        out["planVersion"] = _coerce_int(out.get("planVersion"), 1)
    status = str(out.get("planStatus") or "").strip().lower()
    if status not in ("active", "superseded", "discarded"):
        out["planStatus"] = "active"
    return out


def _quick_validate(record: Dict[str, Any]) -> List[str]:
    """스키마 세부는 SDK 가 검증하지만 흔한 사전오류를 먼저 잡는다."""
    errors: List[str] = []
    if not isinstance(record, dict):
        return ["record is not a dict"]
    for key in ("flightPlanNumber", "aircraftId", "departure", "enRoute", "arrival"):
        if key not in record:
            errors.append(f"missing top-level field: {key}")
    enroute = record.get("enRoute")
    if not isinstance(enroute, list) or not enroute:
        errors.append("enRoute must be a non-empty list")
    return errors


class MissionService(MissionModule):
    """Mission Planner DTAM 통신 layer.

    ``MissionModule`` 베이스가 ``role = Role.MISSION`` + 2001/2002 의 빈
    ``@on_receive`` stub 을 제공. 이 클래스는 그 위에 도메인 처리 (자동
    3001 트리거 + 통계) 를 얹는다.
    """

    def __init__(
        self,
        *,
        target_ip: str = "127.0.0.1",
        ws_port: int = 8096,
        auto_3001_pipeline: Optional[Auto3001Pipeline] = None,
    ) -> None:
        # 통계/상태 (super().__init__ 보다 먼저 — 데코레이터 핸들러가 곧 참조 가능)
        self._mc_lock = threading.RLock()
        self._target_ip = str(target_ip)
        self._ws_port = int(ws_port)
        self._rx_2001_count = 0
        self._rx_2002_count = 0
        self._last_rx_2001 = ""
        self._last_rx_2002 = ""
        self._auto_3001_count = 0
        self._last_auto_3001 = ""
        self._last_auto_3001_error = ""
        self._auto_3001_pipeline = auto_3001_pipeline

        super().__init__(
            server_url=f"ws://{target_ip}:{ws_port}/ws/dtam",
            heartbeat=True,
        )

    # ── 수신 핸들러 (MissionModule 의 빈 stub 을 override) ──────
    def on_flight_plan_request(self, msg: Any) -> None:
        """MSG 2001 수신 → 자동 3001 트리거.

        흐름:
          1. 통계 갱신
          2. ``auto_3001_pipeline(raw)`` 호출 — server.py 가 주입한 callable.
             scenario lookup + auto-mission 빌드 + ICD bundle 묶음을 한 번에
             돌려준다 (export dict). 이 단계가 실패하면 stats 에 기록 후 종료.
          3. ``export["validation"]`` 검증 — invalid 면 에러 통계 기록 후 종료.
          4. ``records`` 추출 → ``self.send_scheduled_flights(records)``
          5. 송신 결과를 통계에 반영 (auto_3001_count, last_auto_3001*).

        외부 (server.py) 는 단계 2 의 pipeline 함수만 책임 — 검증·송신·요약은
        모두 이 메서드 내부에서 처리.
        """
        raw = _result_raw(msg)
        scenario = str(raw.get("scenarioFileName") or "")
        with self._mc_lock:
            self._rx_2001_count += 1
            self._last_rx_2001 = scenario or str(raw)
        logger.info("2001 Flight Plan Request received: scenario=%s", scenario)

        pipeline = self._auto_3001_pipeline
        if pipeline is None:
            return

        # 1) Pipeline 호출 (scenario → mission payload → ICD bundle)
        try:
            export = pipeline(raw) or {}
        except Exception as exc:
            err = f"pipeline raised: {type(exc).__name__}: {exc}"
            with self._mc_lock:
                self._last_auto_3001_error = err
            logger.exception("auto_3001 pipeline failed")
            return

        # 2) Validation 확인
        validation = export.get("validation") if isinstance(export, dict) else None
        if not (isinstance(validation, dict) and validation.get("valid")):
            errs = "; ".join(str(e) for e in (validation or {}).get("errors", []))
            summary = f"Auto 3001 validation failed: {errs}" if errs else "Auto 3001 validation failed"
            with self._mc_lock:
                self._last_auto_3001_error = summary
            logger.warning(summary)
            return

        # 3) records 추출 (record/records 둘 다 허용)
        records: List[Dict[str, Any]] = []
        rec = export.get("record")
        if isinstance(rec, dict):
            records.append(rec)
        elif isinstance(rec, list):
            records.extend(item for item in rec if isinstance(item, dict))
        recs = export.get("records")
        if isinstance(recs, list):
            for item in recs:
                if isinstance(item, dict) and item not in records:
                    records.append(item)
        if not records:
            with self._mc_lock:
                self._last_auto_3001_error = "Auto 3001 generated no records"
            logger.warning("auto_3001: no records in export")
            return

        # 4) 송신
        send_result = self.send_scheduled_flights(records)
        ok = bool(send_result.get("ok"))
        count = int(send_result.get("count") or 0)

        # 5) 결과를 통계에 반영
        with self._mc_lock:
            if ok:
                self._auto_3001_count += count
                self._last_auto_3001 = f"sent {count} scheduled flight(s)"
                self._last_auto_3001_error = ""
                logger.info("auto_3001 sent: count=%d", count)
            else:
                errors_out: List[str] = []
                for item in send_result.get("results", []) or []:
                    if isinstance(item, dict):
                        errors_out.extend(str(e) for e in (item.get("errors") or []))
                self._last_auto_3001_error = "; ".join(errors_out) or "send failed"
                logger.warning("auto_3001 failed: %s", self._last_auto_3001_error)

    def on_dtam_execute(self, msg: Any) -> None:
        raw = _result_raw(msg)
        folder = str(raw.get("flightPlanFolderName") or "")
        with self._mc_lock:
            self._rx_2002_count += 1
            self._last_rx_2002 = folder or str(raw)
        logger.info("2002 DTAM Execute received: flightPlanFolderName=%s", folder)

    # ── 설정/상태 ─────────────────────────────────────────────
    def reconfigure(
        self,
        *,
        target_ip: Optional[str] = None,
        ws_port: Optional[int] = None,
    ) -> Dict[str, Any]:
        """target_ip/ws_port 변경 시 WS 끊고 재접속."""
        with self._mc_lock:
            changed = False
            if target_ip is not None and str(target_ip) != self._target_ip:
                self._target_ip = str(target_ip)
                changed = True
            if ws_port is not None and int(ws_port) != self._ws_port:
                self._ws_port = int(ws_port)
                changed = True
            new_url = f"ws://{self._target_ip}:{self._ws_port}/ws/dtam"
        if changed:
            super().reconfigure(server_url=new_url)
        return self.describe()

    def describe(self) -> Dict[str, Any]:
        with self._mc_lock:
            return {
                "target_ip": self._target_ip,
                "ws_port": self._ws_port,
                "server_url": self.server_url,
                "last_error": self.stats.last_error,
                "ready": True,
                "connected": self.connected,
                "registered": self.registered,
                "rx_2001_count": self._rx_2001_count,
                "rx_2002_count": self._rx_2002_count,
                "last_rx_2001": self._last_rx_2001,
                "last_rx_2002": self._last_rx_2002,
                "auto_3001_count": self._auto_3001_count,
                "last_auto_3001": self._last_auto_3001,
                "last_auto_3001_error": self._last_auto_3001_error,
                "stats": self.stats.to_dict(),
            }

    # ── 송신 ──────────────────────────────────────────────────
    def send_scheduled_flight(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """단일 3001 record 송신 결과 dict."""
        payload = _ensure_plan_metadata(record)
        target = self.server_url
        errors = _quick_validate(payload)
        if errors:
            return {
                "ok": False,
                "target": target,
                "aircraftId": payload.get("aircraftId"),
                "flightPlanNumber": payload.get("flightPlanNumber"),
                "errors": errors,
                "warnings": [],
            }
        try:
            ok = self.send("scheduled_flight", payload)
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            logger.exception("scheduled_flight send raised")
            return {
                "ok": False, "target": target,
                "aircraftId": payload.get("aircraftId"),
                "flightPlanNumber": payload.get("flightPlanNumber"),
                "errors": [err], "warnings": [],
            }
        errors_out: List[str] = []
        if not ok:
            errors_out.append("WebSocket send failed (not connected or registered)")
        return {
            "ok": ok,
            "target": target,
            "aircraftId": payload.get("aircraftId"),
            "flightPlanNumber": payload.get("flightPlanNumber"),
            "errors": errors_out,
            "warnings": [],
        }

    def send_scheduled_flights(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        items: List[Dict[str, Any]] = []
        for record in records or []:
            items.append(self.send_scheduled_flight(record))
        ok = all(item["ok"] for item in items) if items else False
        return {"ok": ok, "count": len(items), "results": items}


__all__ = ["MissionService", "Auto3001Pipeline"]
