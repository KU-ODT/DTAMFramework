"""DTAM Mission Planner 서비스 (WebSocket /ws/dtam + 도메인 통합).

``MissionModule`` (SDK 베이스) 를 상속한 ``MissionService`` — 통신과 ICD
빌드 도메인을 한 클래스에 묶었다. 다른 클라이언트 모듈
(``IntegratedAirMobilityService(VehicleModule)``,
``MonitoringService(MonitoringModule)``) 과 동일한 패턴.

책임:
  - 2001 / 2002 수신 (베이스 stub override)
  - 2001 받으면 자동으로 ICD bundle 만들어 3001 송신 (auto-3001 트리거)
  - ICD bundle 빌드 helpers (build_mission_icd_bundle 등) — routes 도 호출
  - 3001 송신 wrapper (send_scheduled_flight*)
  - reconfigure / describe

생성자에 주입되는 deps:
  - route_planner    : RoutePlanner (find_route, list_ports 등)
  - settings         : dict (mutable 공유 — default_speed_mps, dtam_target_ip 등)
  - resource_csv     : Path (mission_icd_export 가 사용하는 vertiport CSV)
  - route_response_fn: Callable[[str, str, RouteResult], Dict] — server.py
                       의 _route_payload_response (routes/route.py 와 공유)
  - server_http_get_fn: Callable[[str, Optional[Dict]], Dict] — server.py
                       의 _server_get_json (CoreServer DB API)
"""
from __future__ import annotations

import datetime
import logging
import sys
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_SDK_ROOT = Path(__file__).resolve().parents[3] / "DTAM_SDK"
if _SDK_ROOT.is_dir() and str(_SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(_SDK_ROOT))

from dtam_client import MissionModule, on_receive  # type: ignore
from dtam_client.schema import parse_payload  # type: ignore

from .mission_icd_export import build_mission_icd_export, validate_mission_icd_record
from .route_planner import RoutePlanner

logger = logging.getLogger(__name__)


def _result_raw(result: Any) -> Dict[str, Any]:
    if isinstance(result, dict):
        return result
    raw = getattr(result, "raw", None)
    if isinstance(raw, dict):
        return raw
    import dataclasses as _dc
    if _dc.is_dataclass(result) and not isinstance(result, type):
        return _dc.asdict(result)
    return {}


def _coerce_int(value: Any, default: Optional[int] = None) -> Optional[int]:
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
    """Mission Planner DTAM service — 통신 + ICD 빌드 도메인 통합."""

    def __init__(
        self,
        *,
        target_ip: str = "127.0.0.1",
        ws_port: int = 8096,
        route_planner: Optional[RoutePlanner] = None,
        settings: Optional[Dict[str, Any]] = None,
        resource_csv: Optional[Path] = None,
        route_response_fn: Optional[Callable[[str, str, Any], Dict[str, Any]]] = None,
        server_http_get_fn: Optional[Callable[[str, Optional[Dict[str, str]]], Dict[str, Any]]] = None,
    ) -> None:
        # 도메인 deps + 통계 (super().__init__ 보다 먼저)
        self._mc_lock = threading.RLock()
        self._target_ip = str(target_ip)
        self._ws_port = int(ws_port)
        self.route_planner = route_planner
        self.settings = settings if settings is not None else {}
        self._resource_csv = resource_csv
        self._route_response_fn = route_response_fn
        self._server_http_get_fn = server_http_get_fn

        self._rx_2001_count = 0
        self._rx_2002_count = 0
        self._last_rx_2001 = ""
        self._last_rx_2002 = ""
        self._auto_3001_count = 0
        self._last_auto_3001 = ""
        self._last_auto_3001_error = ""

        super().__init__(
            server_url=f"ws://{target_ip}:{ws_port}/ws/dtam",
            heartbeat=True,
        )

    # ──────────────────────────────────────────────────────────
    # 수신 핸들러 (MissionModule 의 빈 stub 을 override)
    # 데코레이터는 가독성용 — base 가 이미 mid 매핑을 보유. mid 가 다르면
    # SDK 가 import 시점에 ``TypeError`` 로 잡아준다.
    # ──────────────────────────────────────────────────────────
    @on_receive("2001")
    def on_flight_plan_request(self, msg: Any) -> None:
        """MSG 2001 수신 → 자동 3001 트리거.

        흐름: 통계 → scenario lookup → mission payload 빌드 → ICD bundle →
        records 추출 → send_scheduled_flights → 결과 통계 갱신.
        """
        raw = _result_raw(msg)
        scenario_file_name = str(raw.get("scenarioFileName") or "")
        with self._mc_lock:
            self._rx_2001_count += 1
            self._last_rx_2001 = scenario_file_name or str(raw)
        logger.info("2001 received: scenario=%s", scenario_file_name)

        # Auto-3001 pipeline (helpers 가 self.route_planner 등을 사용)
        try:
            scenario: Dict[str, Any] = {}
            scenario_path: Optional[str] = None
            scenario_error: Optional[Exception] = None
            try:
                scenario, scenario_path = self._find_scenario_setup_payload(scenario_file_name)
            except Exception as exc:
                scenario_error = exc
            sim_mode, sim_mode_path = self._find_latest_sim_mode_payload()
            mission_payload = (
                self._build_mission_payload_from_sim_mode(sim_mode, scenario)
                if sim_mode is not None
                else None
            )
            source_label = str(sim_mode_path) if mission_payload is not None and sim_mode_path else ""
            if mission_payload is None:
                if scenario_error is not None:
                    raise scenario_error
                mission_payload = self._build_auto_mission_payload_from_scenario(scenario)
                source_label = str(scenario_path) if scenario_path else "latest ScenarioSetup"
            export = self.build_mission_icd_bundle(mission_payload)
        except Exception as exc:
            err = f"pipeline raised: {type(exc).__name__}: {exc}"
            with self._mc_lock:
                self._last_auto_3001_error = err
            logger.exception("auto_3001 pipeline failed")
            return

        validation = export.get("validation") if isinstance(export, dict) else None
        if not (isinstance(validation, dict) and validation.get("valid")):
            errs = "; ".join(str(e) for e in (validation or {}).get("errors", []))
            summary = f"Auto 3001 validation failed: {errs}" if errs else "Auto 3001 validation failed"
            with self._mc_lock:
                self._last_auto_3001_error = summary
            logger.warning(summary)
            return

        records = self.extract_records_from_export(export)
        if not records:
            with self._mc_lock:
                self._last_auto_3001_error = "Auto 3001 generated no records"
            logger.warning("auto_3001: no records")
            return

        send_result = self.send_scheduled_flights(records)
        ok = bool(send_result.get("ok"))
        count = int(send_result.get("count") or 0)
        with self._mc_lock:
            if ok:
                self._auto_3001_count += count
                display_source = source_label or "latest SimModeSetup"
                self._last_auto_3001 = (
                    f"scenario={Path(scenario_file_name).name or display_source}, "
                    f"source={display_source}, sent {count} scheduled flight(s)"
                )
                self._last_auto_3001_error = ""
                logger.info("auto_3001 sent: count=%d", count)
            else:
                errors_out: List[str] = []
                for item in send_result.get("results", []) or []:
                    if isinstance(item, dict):
                        errors_out.extend(str(e) for e in (item.get("errors") or []))
                self._last_auto_3001_error = "; ".join(errors_out) or "send failed"
                logger.warning("auto_3001 failed: %s", self._last_auto_3001_error)

    @on_receive("2002")
    def on_dtam_execute(self, msg: Any) -> None:
        raw = _result_raw(msg)
        folder = str(raw.get("flightPlanFolderName") or "")
        with self._mc_lock:
            self._rx_2002_count += 1
            self._last_rx_2002 = folder or str(raw)
        logger.info("2002 DTAM Execute received: flightPlanFolderName=%s", folder)

    # ──────────────────────────────────────────────────────────
    # 설정/상태
    # ──────────────────────────────────────────────────────────
    def reconfigure(
        self,
        *,
        target_ip: Optional[str] = None,
        ws_port: Optional[int] = None,
    ) -> Dict[str, Any]:
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

    # ──────────────────────────────────────────────────────────
    # 송신 (3001)
    # ──────────────────────────────────────────────────────────
    def send_scheduled_flight(self, record: Dict[str, Any]) -> Dict[str, Any]:
        payload = _ensure_plan_metadata(record)
        target = self.server_url
        errors = _quick_validate(payload)
        if errors:
            return {
                "ok": False, "target": target,
                "aircraftId": payload.get("aircraftId"),
                "flightPlanNumber": payload.get("flightPlanNumber"),
                "errors": errors, "warnings": [],
            }
        try:
            ok = self.send(parse_payload("3001", payload))
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
            "ok": ok, "target": target,
            "aircraftId": payload.get("aircraftId"),
            "flightPlanNumber": payload.get("flightPlanNumber"),
            "errors": errors_out, "warnings": [],
        }

    def send_scheduled_flights(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        items: List[Dict[str, Any]] = []
        for record in records or []:
            items.append(self.send_scheduled_flight(record))
        ok = all(item["ok"] for item in items) if items else False
        return {"ok": ok, "count": len(items), "results": items}

    # ──────────────────────────────────────────────────────────
    # ICD bundle helpers (routes 도 호출)
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def looks_like_icd_record(payload: Dict[str, Any]) -> bool:
        required = {"flightPlanNumber", "aircraftId", "departure", "enRoute", "arrival"}
        return isinstance(payload, dict) and required.issubset(payload.keys())

    @staticmethod
    def looks_like_icd_record_list(payload: Any) -> bool:
        return isinstance(payload, list) and bool(payload) and all(
            MissionService.looks_like_icd_record(item) for item in payload
        )

    @staticmethod
    def extract_records_from_export(result: Dict[str, Any]) -> List[Dict[str, Any]]:
        records = result.get("records") if isinstance(result, dict) else None
        if isinstance(records, list) and records:
            return [item for item in records if isinstance(item, dict)]
        record = result.get("record") if isinstance(result, dict) else None
        if isinstance(record, list):
            return [item for item in record if isinstance(item, dict)]
        if isinstance(record, dict):
            return [record]
        return []

    def _normalize_simulation_fleet(
        self,
        mission_payload: Dict[str, Any],
        default_vehicle_name: str = "UAM1",
    ) -> List[Dict[str, Any]]:
        options = mission_payload.get("options") or {}
        base_aircraft_id = str(options.get("aircraftId") or "UAM0001").strip() or "UAM0001"
        base_flight_plan = _coerce_int(options.get("flightPlanNumber"))
        if base_flight_plan is None:
            base_flight_plan = int(datetime.datetime.now().strftime("%m%d%H%M"))

        raw_fleet = mission_payload.get("fleet") or []
        normalized: List[Dict[str, Any]] = []
        if isinstance(raw_fleet, list):
            for index, item in enumerate(raw_fleet):
                if not isinstance(item, dict):
                    continue
                aircraft_id = (
                    str(item.get("aircraftId") or base_aircraft_id or f"UAM{index + 1:04d}").strip()
                    or f"UAM{index + 1:04d}"
                )
                vehicle_name = (
                    str(item.get("vehicleName") or item.get("vehicle_name") or "").strip()
                    or (default_vehicle_name if index == 0 else f"UAM{index + 1}")
                )
                flight_plan_number = _coerce_int(item.get("flightPlanNumber"))
                if flight_plan_number is None:
                    flight_plan_number = base_flight_plan + index
                normalized.append({
                    "aircraftId": aircraft_id,
                    "vehicleName": vehicle_name,
                    "flightPlanNumber": flight_plan_number,
                })
        if normalized:
            return normalized
        return [{
            "aircraftId": base_aircraft_id,
            "vehicleName": str(default_vehicle_name or "UAM1").strip() or "UAM1",
            "flightPlanNumber": base_flight_plan,
        }]

    def build_existing_icd_export_bundle(
        self,
        mission_payload: Any,
        fleet: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        records = mission_payload if isinstance(mission_payload, list) else [mission_payload]
        normalized_records = [item for item in records if isinstance(item, dict)]
        if not normalized_records:
            raise ValueError("No ICD records were provided.")

        normalized_fleet = list(fleet or [])
        if not normalized_fleet:
            base_number = int(datetime.datetime.now().strftime("%m%d%H%M"))
            for index, record in enumerate(normalized_records):
                normalized_fleet.append({
                    "aircraftId": str(record.get("aircraftId") or f"UAM{index + 1:04d}"),
                    "vehicleName": f"UAM{index + 1}",
                    "flightPlanNumber": _coerce_int(record.get("flightPlanNumber")) or (base_number + index),
                })

        errors: List[str] = []
        for fleet_entry, record in zip(normalized_fleet, normalized_records):
            prefix = f"{fleet_entry['aircraftId']} ({fleet_entry['vehicleName']})"
            for message in validate_mission_icd_record(record):
                errors.append(f"{prefix}: {message}")

        first_record = normalized_records[0]
        filename = (
            f"mission_icd_v1_{first_record.get('flightPlanNumber', 'fleet')}_{first_record.get('aircraftId', 'UAM0001')}.json"
            if len(normalized_records) == 1
            else f"mission_icd_v1_fleet_{normalized_fleet[0]['flightPlanNumber']}_{len(normalized_records)}ac.json"
        )
        return {
            "mode": "icd",
            "filename": filename,
            "record": normalized_records[0] if len(normalized_records) == 1 else normalized_records,
            "records": normalized_records,
            "fleet": normalized_fleet,
            "validation": {"valid": not errors, "errors": errors},
            "warnings": [],
        }

    def build_mission_icd_bundle(
        self,
        payload: Dict[str, Any],
        fleet: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        if self.route_planner is None:
            raise RuntimeError("Route planner not loaded.")
        if self._resource_csv is None:
            raise RuntimeError("Mission ICD resource CSV path not configured.")

        normalized_fleet = list(fleet or self._normalize_simulation_fleet(payload))
        raw_missions = payload.get("missions")
        missions = (
            [item for item in raw_missions if isinstance(item, dict)]
            if isinstance(raw_missions, list)
            else [payload]
        )
        if not missions:
            raise ValueError("No mission payloads were provided.")
        if len(missions) != len(normalized_fleet):
            raise ValueError(
                f"Mission count ({len(missions)}) does not match fleet count ({len(normalized_fleet)})."
            )

        base_options = dict(payload.get("options") or {})
        exports: List[Dict[str, Any]] = []
        for mission_payload, fleet_entry in zip(missions, normalized_fleet):
            item_payload = dict(mission_payload)
            item_payload.pop("fleet", None)
            item_payload.pop("missions", None)
            item_payload["options"] = {
                **base_options,
                **dict(item_payload.get("options") or {}),
                "aircraftId": fleet_entry["aircraftId"],
                "flightPlanNumber": fleet_entry["flightPlanNumber"],
            }
            exports.append(
                build_mission_icd_export(
                    item_payload,
                    self.route_planner,
                    self._resource_csv,
                    float(self.settings.get("default_altitude_m", 300.0)),
                )
            )

        if len(exports) == 1:
            result = dict(exports[0])
            result["records"] = [exports[0]["record"]]
            result["fleet"] = normalized_fleet
            return result

        warnings: List[str] = []
        errors: List[str] = []
        records: List[Dict[str, Any]] = []
        for fleet_entry, export in zip(normalized_fleet, exports):
            prefix = f"{fleet_entry['aircraftId']} ({fleet_entry['vehicleName']})"
            records.append(export["record"])
            for warning in export.get("warnings", []):
                warnings.append(f"{prefix}: {warning}")
            for message in export.get("validation", {}).get("errors", []):
                errors.append(f"{prefix}: {message}")

        return {
            "mode": str(payload.get("mode") or "route"),
            "filename": f"mission_icd_v1_fleet_{normalized_fleet[0]['flightPlanNumber']}_{len(records)}ac.json",
            "record": records,
            "records": records,
            "fleet": normalized_fleet,
            "validation": {"valid": not errors, "errors": errors},
            "warnings": warnings,
        }

    # ──────────────────────────────────────────────────────────
    # Auto-3001 내부 helpers (on_flight_plan_request 가 사용)
    # ──────────────────────────────────────────────────────────
    def _find_scenario_setup_payload(
        self, scenario_file_name: str
    ) -> tuple[Dict[str, Any], Optional[str]]:
        if self._server_http_get_fn is None:
            raise RuntimeError("server_http_get_fn not configured.")
        requested = Path(str(scenario_file_name or "")).name
        query = {"field": "scenarioFileName", "value": requested} if requested else None
        try:
            data = self._server_http_get_fn("/api/db/messages/1003/latest", query)
        except Exception:
            if not query:
                raise
            data = self._server_http_get_fn("/api/db/messages/1003/latest", None)
        payload = data.get("payload")
        if not isinstance(payload, dict):
            raise FileNotFoundError("No ScenarioSetup payload exists on DTAM server.")
        return payload, str(data.get("path") or "") or None

    def _find_latest_sim_mode_payload(self) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        if self._server_http_get_fn is None:
            return None, None
        try:
            data = self._server_http_get_fn("/api/db/messages/1001/latest", None)
        except Exception:
            return None, None
        payload = data.get("payload")
        if not isinstance(payload, dict):
            return None, str(data.get("path") or "") or None
        return payload, str(data.get("path") or "") or None

    @staticmethod
    def _aircraft_id_from_name(name: Any, index: int) -> str:
        text = str(name or "").strip()
        import re

        match = re.search(r"(\d+)$", text)
        if match:
            return f"UAM{int(match.group(1)):04d}"
        return f"UAM{index + 1:04d}"

    def _build_mission_payload_from_sim_mode(
        self,
        sim_mode: Dict[str, Any],
        scenario: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        single = sim_mode.get("singleFlight") if isinstance(sim_mode.get("singleFlight"), dict) else {}
        planning = single.get("missionPlanning") if isinstance(single.get("missionPlanning"), dict) else {}
        entries = planning.get("missions") if isinstance(planning.get("missions"), list) else []
        valid_entries = [
            entry for entry in entries
            if isinstance(entry, dict) and isinstance(entry.get("routeData"), dict)
        ]
        if not valid_entries:
            return None

        operation_time = (
            scenario.get("operationTime")
            if isinstance(scenario, dict) and isinstance(scenario.get("operationTime"), dict)
            else {}
        )
        std = str(operation_time.get("startTime") or datetime.datetime.now().strftime("%H:%M:%S"))
        base_number = int(datetime.datetime.now().strftime("%m%d%H%M"))
        missions: List[Dict[str, Any]] = []
        fleet: List[Dict[str, Any]] = []

        for index, entry in enumerate(valid_entries):
            route_data = dict(entry.get("routeData") or {})
            path = route_data.get("path") if isinstance(route_data.get("path"), list) else []
            departure = str(entry.get("departureName") or (path[0] if path else "")).strip()
            arrival = str(entry.get("arrivalName") or (path[-1] if path else "")).strip()
            if not departure or not arrival:
                continue
            aircraft_name = str(entry.get("aircraftName") or f"UAM {index + 1}").strip()
            aircraft_id = self._aircraft_id_from_name(aircraft_name, index)
            flight_plan_number = base_number + index
            fleet.append({
                "aircraftId": aircraft_id,
                "vehicleName": aircraft_name,
                "flightPlanNumber": flight_plan_number,
            })
            missions.append({
                "mode": "route",
                "departureName": departure,
                "arrivalName": arrival,
                "routeData": route_data,
                "options": {
                    "std": std,
                    "cruiseSpeedMps": float(self.settings.get("default_speed_mps", 30.0)),
                },
            })

        if not missions:
            return None
        return {
            "mode": "route",
            "missions": missions,
            "fleet": fleet,
            "options": {
                "std": std,
                "cruiseSpeedMps": float(self.settings.get("default_speed_mps", 30.0)),
            },
        }

    def _scenario_vertiport_names(self, scenario: Dict[str, Any]) -> List[str]:
        names: List[str] = []
        for item in scenario.get("vertiports") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if name and name not in names:
                names.append(name)
        if self.route_planner is not None:
            names = [name for name in names if name in self.route_planner.ports]
            if len(names) < 2:
                for name in self.route_planner.list_ports():
                    if name not in names:
                        names.append(name)
                    if len(names) >= 2:
                        break
        return names

    def _auto_plan_count(self, scenario: Dict[str, Any]) -> int:
        requested = _coerce_int(scenario.get("totalAircraftCount")) or 1
        max_count = _coerce_int(self.settings.get("auto_plan_max_aircraft")) or 1
        return max(1, min(int(requested), int(max_count)))

    def _build_auto_mission_payload_from_scenario(
        self, scenario: Dict[str, Any]
    ) -> Dict[str, Any]:
        if self.route_planner is None:
            raise RuntimeError("Route planner not loaded.")
        if self._route_response_fn is None:
            raise RuntimeError("route_response_fn not configured.")

        vertiports = self._scenario_vertiport_names(scenario)
        if len(vertiports) < 2:
            raise RuntimeError("At least two vertiports are required to auto-generate 3001.")

        operation_time = scenario.get("operationTime") if isinstance(scenario.get("operationTime"), dict) else {}
        std = str(operation_time.get("startTime") or datetime.datetime.now().strftime("%H:%M:%S"))
        base_number = int(datetime.datetime.now().strftime("%m%d%H%M"))
        count = self._auto_plan_count(scenario)
        missions: List[Dict[str, Any]] = []
        fleet: List[Dict[str, Any]] = []

        for index in range(count):
            departure = vertiports[index % len(vertiports)]
            arrival = vertiports[(index + 1) % len(vertiports)]
            if departure == arrival:
                arrival = vertiports[-1] if departure != vertiports[-1] else vertiports[0]

            route = self.route_planner.find_route(departure, arrival, include_turn_arcs=False)
            route_data = self._route_response_fn(departure, arrival, route, include_turn_arcs=False)
            aircraft_id = f"UAM{index + 1:04d}"
            flight_plan_number = base_number + index
            fleet.append({
                "aircraftId": aircraft_id,
                "vehicleName": f"UAM{index + 1}",
                "flightPlanNumber": flight_plan_number,
            })
            missions.append({
                "mode": "route",
                "departureName": departure,
                "arrivalName": arrival,
                "routeData": route_data,
                "options": {
                    "std": std,
                    "cruiseSpeedMps": float(self.settings.get("default_speed_mps", 30.0)),
                },
            })

        return {
            "mode": "route",
            "missions": missions,
            "fleet": fleet,
            "options": {
                "std": std,
                "cruiseSpeedMps": float(self.settings.get("default_speed_mps", 30.0)),
            },
        }


__all__ = ["MissionService"]
