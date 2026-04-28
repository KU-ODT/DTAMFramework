"""DTAM Mission Planner 통신 layer (WebSocket /ws/dtam).

``DtamModule`` 서브클래스 + ``@on_receive("MID")`` 데코레이터 패턴.
2001 (Flight Plan Request) / 2002 (DTAM Execute) 수신 핸들러를 데코레이터로
자동 등록하고, 3001 (Scheduled Flight) 송신은 도메인 메서드로 노출한다.

외부 인터페이스 (server.py / routes/* 가 사용):
  - MissionService(target_ip, ws_port, on_flight_plan_request)
  - .describe() → dict
  - .send_scheduled_flight(record) → dict
  - .send_scheduled_flights(records) → dict
  - .reconfigure(target_ip=..., ws_port=...) → dict
  - .close()
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

FlightPlanRequestHandler = Callable[[Dict[str, Any], "MissionService"], Optional[Dict[str, Any]]]


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
        on_flight_plan_request: Optional[FlightPlanRequestHandler] = None,
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
        self._on_flight_plan_request_handler = on_flight_plan_request

        super().__init__(
            server_url=f"ws://{target_ip}:{ws_port}/ws/dtam",
            heartbeat=True,
        )

    # ── 수신 핸들러 (MissionModule 의 빈 stub 을 override) ──────
    def on_flight_plan_request(self, msg: Any) -> None:
        raw = _result_raw(msg)
        scenario = str(raw.get("scenarioFileName") or "")
        with self._mc_lock:
            self._rx_2001_count += 1
            self._last_rx_2001 = scenario or str(raw)
        logger.info("2001 Flight Plan Request received: scenario=%s", scenario)
        handler = self._on_flight_plan_request_handler
        if handler is None:
            return
        try:
            auto_result = handler(raw, self) or {}
            count = int(auto_result.get("count") or 0)
            ok = bool(auto_result.get("ok", False))
            summary = str(auto_result.get("summary") or "")
            with self._mc_lock:
                if ok:
                    self._auto_3001_count += count
                    self._last_auto_3001 = summary or f"sent {count} scheduled flight(s)"
                    self._last_auto_3001_error = ""
                else:
                    self._last_auto_3001_error = summary or str(auto_result)
            if ok:
                logger.info("2001 auto 3001 completed: %s", summary)
            else:
                logger.warning("2001 auto 3001 failed: %s", summary)
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            with self._mc_lock:
                self._last_auto_3001_error = err
            logger.exception("2001 auto 3001 handler failed")

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


__all__ = ["MissionService", "FlightPlanRequestHandler"]
