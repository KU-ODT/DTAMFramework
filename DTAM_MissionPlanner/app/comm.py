"""DTAM 3001 (Scheduled Flight) 송신 모듈.

DtamModule (WebSocket /ws/dtam) 기반. Mission Planner UI 가 구성한
Mission ICD record 를 검증한 뒤 DtamModule.send("scheduled_flight", ...) 로 송출.

- 입력: Mission ICD record dict (``flightPlanNumber``, ``aircraftId``,
  ``departure``, ``enRoute``, ``arrival``)
- 추가로 3001 스키마가 요구하는 ``planVersion`` / ``planStatus`` 를 채워줌.
- 송신 결과를 PushResult 호환 dict 형식으로 반환.

외부 인터페이스 (server.py 가 사용):
  - DtamSender(target_ip, ws_port, on_flight_plan_request)
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

_SDK_ROOT = Path(__file__).resolve().parents[2] / "DTAM_SDK"
if _SDK_ROOT.is_dir() and str(_SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(_SDK_ROOT))

from dtam_client import DtamModule, Role  # type: ignore

logger = logging.getLogger(__name__)

FlightPlanRequestHandler = Callable[[Dict[str, Any], "DtamSender"], Optional[Dict[str, Any]]]


def _result_raw(result: Any) -> Dict[str, Any]:
    """수신 콜백 인자를 dict 으로 정규화.

    DtamModule 이 ICD dataclass 인스턴스를 넘기면 ``asdict`` 로 풀고,
    이미 dict 형태로 들어온 경우엔 그대로 반환한다.
    """
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
    """스키마 세부는 SDK 가 하지만, 흔한 사전오류만 먼저 잡는다."""
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


class DtamSender:
    """Mission Planner 전용 DTAM 3001 송신기 (DtamModule 위 얇은 wrapper)."""

    def __init__(
        self,
        *,
        target_ip: str = "127.0.0.1",
        ws_port: int = 8096,             # SimulationState HTTP/WS 포트
        on_flight_plan_request: Optional[FlightPlanRequestHandler] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._target_ip = str(target_ip)
        self._ws_port = int(ws_port)
        self._module: Optional[DtamModule] = None
        self._last_error: str = ""
        self._rx_2001_count = 0
        self._rx_2002_count = 0
        self._last_rx_2001 = ""
        self._last_rx_2002 = ""
        self._auto_3001_count = 0
        self._last_auto_3001 = ""
        self._last_auto_3001_error = ""
        self._on_flight_plan_request_handler = on_flight_plan_request
        self._build_module_locked()

    # ── 내부: DtamModule 생성/콜백 등록 ────────────────────────
    def _build_module_locked(self) -> None:
        url = f"ws://{self._target_ip}:{self._ws_port}/ws/dtam"
        try:
            self._module = DtamModule.start(
                role=Role.MISSION,
                server_url=url,
                heartbeat=True,
            )
            self._module.on("flight_plan_request", self._on_flight_plan_request_cb)
            self._module.on("dtam_execute",        self._on_dtam_execute_cb)
            self._last_error = ""
        except Exception as exc:
            self._module = None
            self._last_error = f"init failed: {type(exc).__name__}: {exc}"
            logger.exception("DtamModule init failed")

    def _close_module_locked(self) -> None:
        mod = self._module
        self._module = None
        if mod is None:
            return
        try:
            mod.close()
        except Exception:
            logger.exception("DtamModule.close failed")

    # ── 설정 ──────────────────────────────────────────────────
    def reconfigure(
        self,
        *,
        target_ip: Optional[str] = None,
        ws_port: Optional[int] = None,
    ) -> Dict[str, Any]:
        """WS 서버 endpoint 재설정."""
        with self._lock:
            rebuild = False
            if target_ip is not None and str(target_ip) != self._target_ip:
                self._target_ip = str(target_ip)
                rebuild = True
            if ws_port is not None and int(ws_port) != self._ws_port:
                self._ws_port = int(ws_port)
                rebuild = True

            if rebuild:
                self._close_module_locked()
                self._build_module_locked()
            return self.describe()

    def describe(self) -> Dict[str, Any]:
        with self._lock:
            mod = self._module
            stats = mod.stats.to_dict() if mod is not None else {}
            return {
                "target_ip": self._target_ip,
                "ws_port": self._ws_port,
                "server_url": f"ws://{self._target_ip}:{self._ws_port}/ws/dtam",
                "last_error": self._last_error,
                "ready": mod is not None,
                "connected": bool(mod and mod.connected),
                "registered": bool(mod and mod.registered),
                "rx_2001_count": self._rx_2001_count,
                "rx_2002_count": self._rx_2002_count,
                "last_rx_2001": self._last_rx_2001,
                "last_rx_2002": self._last_rx_2002,
                "auto_3001_count": self._auto_3001_count,
                "last_auto_3001": self._last_auto_3001,
                "last_auto_3001_error": self._last_auto_3001_error,
                "stats": stats,
            }

    # ── 송신 ──────────────────────────────────────────────────
    def send_scheduled_flight(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """단일 3001 record 를 송신하고 결과 dict 를 반환한다."""
        payload = _ensure_plan_metadata(record)
        target = f"ws://{self._target_ip}:{self._ws_port}/ws/dtam"
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

        with self._lock:
            mod = self._module
            if mod is None:
                return {
                    "ok": False,
                    "target": target,
                    "aircraftId": payload.get("aircraftId"),
                    "flightPlanNumber": payload.get("flightPlanNumber"),
                    "errors": [f"module not initialised: {self._last_error or 'unknown'}"],
                    "warnings": [],
                }
        try:
            ok = mod.send("scheduled_flight", payload)
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            with self._lock:
                self._last_error = msg
            logger.exception("scheduled_flight send raised")
            return {
                "ok": False, "target": target,
                "aircraftId": payload.get("aircraftId"),
                "flightPlanNumber": payload.get("flightPlanNumber"),
                "errors": [msg], "warnings": [],
            }

        errors_out: List[str] = []
        if not ok:
            errors_out.append("WebSocket send failed (not connected or registered)")
            self._last_error = "; ".join(errors_out)
        else:
            self._last_error = ""
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

    # ── 라이프사이클 ──────────────────────────────────────────
    def close(self) -> None:
        with self._lock:
            self._close_module_locked()

    # ── 내부 콜백 ─────────────────────────────────────────────
    def _on_flight_plan_request_cb(self, payload: Any) -> None:
        raw = _result_raw(payload)
        scenario = str(raw.get("scenarioFileName") or "")
        with self._lock:
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
            with self._lock:
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
            msg = f"{type(exc).__name__}: {exc}"
            with self._lock:
                self._last_auto_3001_error = msg
            logger.exception("2001 auto 3001 handler failed")

    def _on_dtam_execute_cb(self, payload: Any) -> None:
        raw = _result_raw(payload)
        folder = str(raw.get("flightPlanFolderName") or "")
        with self._lock:
            self._rx_2002_count += 1
            self._last_rx_2002 = folder or str(raw)
        logger.info("2002 DTAM Execute received: flightPlanFolderName=%s", folder)
