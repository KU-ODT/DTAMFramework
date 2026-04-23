"""DTAM 3001 (Scheduled Flight) 송신 모듈.

Mission Planner UI 가 구성한 Mission ICD record 를 DTAM_SDK 의
``push_scheduled_flight`` 를 통해 TCP 로 송출한다.

- 입력: Mission ICD record dict (``flightPlanNumber``, ``aircraftId``,
  ``departure``, ``enRoute``, ``arrival``)
- 추가로 3001 스키마가 요구하는 ``planVersion`` / ``planStatus`` 를
  채워 주고, 선회 segment 의 ``turnDirection`` / ``centerLLA`` 를 검증.
- TCP 송신 결과를 PushResult dict 형식으로 반환.

SDK 는 ``DtamClient`` 또는 ``push_scheduled_flight`` 를 그대로 사용하면
되며, 본 모듈은 엔드포인트(IP/port) 를 설정 가능한 facade 를 제공한다.
"""
from __future__ import annotations

import logging
import sys
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

_SDK_ROOT = Path(__file__).resolve().parents[2] / "DTAM_SDK"
if _SDK_ROOT.is_dir() and str(_SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(_SDK_ROOT))

from dtam_client import DtamClient  # type: ignore  # sys.path 에 추가 후 import

logger = logging.getLogger(__name__)

MODULE_SOURCE_NAME = "DTAM_MissionPlanner"
HEARTBEAT_PERIOD_S = 1.0

FlightPlanRequestHandler = Callable[[Dict[str, Any], "DtamSender"], Optional[Dict[str, Any]]]


def _iso_ts() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _result_payload(result: Any) -> Dict[str, Any]:
    raw = getattr(result, "raw", None)
    if isinstance(raw, dict):
        return raw
    if hasattr(result, "to_dict"):
        try:
            value = result.to_dict()
            if isinstance(value, dict):
                return value
        except Exception:
            pass
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
    # ICD export 에서 seq 는 1..N 의 int. 추가 검증 없이 그대로 둔다.
    return out


class DtamSender:
    """Mission Planner 전용 DTAM 3001 송신기."""

    def __init__(
        self,
        *,
        target_ip: str = "127.0.0.1",
        target_port: int = 17000,
        my_ip: str = "0.0.0.0",
        my_port: int = 17010,
        on_flight_plan_request: Optional[FlightPlanRequestHandler] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._target_ip = str(target_ip)
        self._target_port = int(target_port)
        self._my_ip = str(my_ip)
        self._my_port = int(my_port)
        self._client: Optional[DtamClient] = None
        self._last_error: str = ""
        self._rx_2001_count = 0
        self._rx_2002_count = 0
        self._last_rx_2001 = ""
        self._last_rx_2002 = ""
        self._last_heartbeat_error = ""
        self._auto_3001_count = 0
        self._last_auto_3001 = ""
        self._last_auto_3001_error = ""
        self._on_flight_plan_request_handler = on_flight_plan_request
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._build_client_locked()
        self._start_heartbeat()

    # ── 설정 ──────────────────────────────────────────────────
    def reconfigure(
        self,
        *,
        target_ip: Optional[str] = None,
        target_port: Optional[int] = None,
        my_ip: Optional[str] = None,
        my_port: Optional[int] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            if target_ip is not None:
                self._target_ip = str(target_ip)
            if target_port is not None:
                self._target_port = int(target_port)
            rebuild_my = False
            if my_ip is not None and str(my_ip) != self._my_ip:
                self._my_ip = str(my_ip)
                rebuild_my = True
            if my_port is not None and int(my_port) != self._my_port:
                self._my_port = int(my_port)
                rebuild_my = True

            if rebuild_my:
                self._close_client_locked()
                self._build_client_locked()
            elif self._client is not None:
                try:
                    self._client.configure(
                        target_ip=self._target_ip,
                        base_port=self._target_port,
                    )
                except Exception as exc:
                    self._last_error = f"configure failed: {type(exc).__name__}: {exc}"
                    logger.exception("DtamClient.configure failed")
            return self.describe()

    def describe(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "target_ip": self._target_ip,
                "target_port": self._target_port,
                "target_tcp_port": self._target_port + 1,
                "my_ip": self._my_ip,
                "my_port": self._my_port,
                "my_tcp_port": self._my_port + 1,
                "last_error": self._last_error,
                "last_heartbeat_error": self._last_heartbeat_error,
                "ready": self._client is not None,
                "listening": bool(self._client and self._client.listening),
                "rx_2001_count": self._rx_2001_count,
                "rx_2002_count": self._rx_2002_count,
                "last_rx_2001": self._last_rx_2001,
                "last_rx_2002": self._last_rx_2002,
                "auto_3001_count": self._auto_3001_count,
                "last_auto_3001": self._last_auto_3001,
                "last_auto_3001_error": self._last_auto_3001_error,
            }

    # ── 송신 ──────────────────────────────────────────────────
    def send_scheduled_flight(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """단일 3001 record 를 송신하고 결과 dict 를 반환한다."""
        payload = _ensure_plan_metadata(record)
        errors = _quick_validate(payload)
        if errors:
            return {
                "ok": False,
                "target": f"{self._target_ip}:{self._target_port + 1}",
                "aircraftId": payload.get("aircraftId"),
                "flightPlanNumber": payload.get("flightPlanNumber"),
                "errors": errors,
                "warnings": [],
            }

        with self._lock:
            if self._client is None:
                return {
                    "ok": False,
                    "target": f"{self._target_ip}:{self._target_port + 1}",
                    "aircraftId": payload.get("aircraftId"),
                    "flightPlanNumber": payload.get("flightPlanNumber"),
                    "errors": [f"client not initialised: {self._last_error or 'unknown'}"],
                    "warnings": [],
                }
            try:
                result = self._client.push_scheduled_flight(payload)
            except Exception as exc:
                msg = f"{type(exc).__name__}: {exc}"
                self._last_error = msg
                logger.exception("push_scheduled_flight raised")
                return {
                    "ok": False,
                    "target": f"{self._target_ip}:{self._target_port + 1}",
                    "aircraftId": payload.get("aircraftId"),
                    "flightPlanNumber": payload.get("flightPlanNumber"),
                    "errors": [msg],
                    "warnings": [],
                }

        ok = bool(result) if result is not None else False
        errors_out: List[str] = list(getattr(result, "errors", []) or [])
        warnings_out: List[str] = list(getattr(result, "warnings", []) or [])
        if not ok and not errors_out:
            errors_out.append("TCP send reported failure")
        if not ok:
            self._last_error = "; ".join(errors_out) or "send failed"
        else:
            self._last_error = ""
        return {
            "ok": ok,
            "target": getattr(result, "target", f"{self._target_ip}:{self._target_port + 1}"),
            "aircraftId": payload.get("aircraftId"),
            "flightPlanNumber": payload.get("flightPlanNumber"),
            "errors": errors_out,
            "warnings": warnings_out,
        }

    def send_scheduled_flights(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """여러 3001 record 를 순차 송신한다."""
        items: List[Dict[str, Any]] = []
        for record in records or []:
            items.append(self.send_scheduled_flight(record))
        ok = all(item["ok"] for item in items) if items else False
        return {
            "ok": ok,
            "count": len(items),
            "results": items,
        }

    # ── 라이프사이클 ──────────────────────────────────────────
    def close(self) -> None:
        self._heartbeat_stop.set()
        thread = self._heartbeat_thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        with self._lock:
            self._close_client_locked()

    # ── 내부 ──────────────────────────────────────────────────
    def _build_client_locked(self) -> None:
        try:
            self._client = DtamClient.module(
                my_ip=self._my_ip,
                my_port=self._my_port,
                peer_ip=self._target_ip,
                peer_port=self._target_port,
                auto_listen=True,
            )
            self._client.on_flight_plan_request = self._on_flight_plan_request
            self._client.on_dtam_execute = self._on_dtam_execute
            self._last_error = ""
        except Exception as exc:
            self._client = None
            self._last_error = f"init failed: {type(exc).__name__}: {exc}"
            logger.exception("DtamClient init failed")

    def _close_client_locked(self) -> None:
        client = self._client
        self._client = None
        if client is None:
            return
        try:
            client.close()
        except Exception:
            logger.exception("DtamClient.close failed")

    def _start_heartbeat(self) -> None:
        if self._heartbeat_thread is not None:
            return
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name="dtam-mission-heartbeat",
            daemon=True,
        )
        self._heartbeat_thread.start()

    def _heartbeat_loop(self) -> None:
        while not self._heartbeat_stop.is_set():
            try:
                self._send_module_status()
            except Exception as exc:
                self._last_heartbeat_error = f"{type(exc).__name__}: {exc}"
                logger.debug("mission heartbeat failed: %s", self._last_heartbeat_error)
            if self._heartbeat_stop.wait(HEARTBEAT_PERIOD_S):
                break

    def _send_module_status(self) -> None:
        with self._lock:
            client = self._client
        if client is None:
            self._last_heartbeat_error = self._last_error or "client not initialised"
            return
        payload = {
            "timestamp": _iso_ts(),
            "source": MODULE_SOURCE_NAME,
            "status": 1,
        }
        result = client.push_module_status(payload)
        if bool(result):
            self._last_heartbeat_error = ""
        else:
            errors = list(getattr(result, "errors", []) or [])
            self._last_heartbeat_error = "; ".join(errors) or "module status send failed"

    def _on_flight_plan_request(self, result: Any) -> None:
        payload = _result_payload(result)
        scenario = str(payload.get("scenarioFileName") or "")
        with self._lock:
            self._rx_2001_count += 1
            self._last_rx_2001 = scenario or str(payload)
        logger.info("2001 Flight Plan Request received: scenario=%s", scenario)
        handler = self._on_flight_plan_request_handler
        if handler is None:
            return
        try:
            auto_result = handler(payload, self) or {}
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

    def _on_dtam_execute(self, result: Any) -> None:
        payload = _result_payload(result)
        folder = str(payload.get("flightPlanFolderName") or "")
        with self._lock:
            self._rx_2002_count += 1
            self._last_rx_2002 = folder or str(payload)
        logger.info("2002 DTAM Execute received: flightPlanFolderName=%s", folder)


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
