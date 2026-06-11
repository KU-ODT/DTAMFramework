"""ICD-backed data helpers for the PSU console.

This module intentionally reads existing StateServer DB/session data instead of
opening a new DTAM WebSocket role. PSU is a monitoring/coordination UI, and the
StateServer role slots are already used by the runtime modules.
"""
from __future__ import annotations

import json
import math
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

APP_DIR = Path(__file__).resolve().parents[1]
MODULE_ROOT = APP_DIR.parent
EXTENSION_ROOT = MODULE_ROOT.parent
FRAMEWORK_ROOT = EXTENSION_ROOT.parent
STATE_DB_ROOT = FRAMEWORK_ROOT / "IntegrationHub" / "StateServerModule" / "data" / "DB"

DEFAULT_STATE_PORT = 8096
AIRCRAFT_ID_RE = re.compile(r"^[A-Z]{2,8}\d{4}$")
_COMMAND_COUNTERS: dict[tuple[str, str], int] = {}
MODIFICATION_TYPES = {
    "scheduleResourceUpdate",
    "routeUpdate",
    "aircraftSwap",
    "delayOnly",
    "cancelPlan",
}
STRATEGIC_REASONS = {
    "VERTIPORT_CAPACITY",
    "CORRIDOR_CLOSED",
    "WEATHER",
    "VEHICLE_UNAVAILABLE",
    "OPERATOR_REQUEST",
}
MODIFY_SCOPES = {
    "departureOnly",
    "arrivalOnly",
    "departureAndArrival",
    "enRouteOnly",
    "aircraftOnly",
    "fullPlan",
}
TACTICAL_REASONS = {
    "LOSS_OF_SEPARATION_RISK",
    "LOCAL_CORRIDOR_BLOCKED",
    "LOW_BATTERY",
    "WEATHER_AVOIDANCE",
    "OPERATOR_OVERRIDE",
    "EMERGENCY_LANDING",
}
TACTICAL_ACTION_TYPES = {"setSpeed", "directTo", "hold", "rejoinPlan", "land"}
WARNING_SEVERITIES = {"info", "warning", "critical", "fatal"}
WARNING_FILE_LIMIT = 20


def _state_base_url() -> str:
    host = str(os.environ.get("DTAM_TARGET_IP") or "127.0.0.1")
    port = int(os.environ.get("DTAM_WS_PORT") or DEFAULT_STATE_PORT)
    return f"http://{host}:{port}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(now: datetime | None = None) -> str:
    value = now or _utc_now()
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _command_id(prefix: str, now: datetime | None = None) -> str:
    value = now or _utc_now()
    date = value.strftime("%Y%m%d")
    key = (prefix, date)
    _COMMAND_COUNTERS[key] = _COMMAND_COUNTERS.get(key, 0) + 1
    return f"{prefix}-{date}-{_COMMAND_COUNTERS[key]:03d}"


def _fetch_json(url: str, timeout_s: float = 0.45) -> dict[str, Any]:
    req = urllib_request.Request(url, headers={"Accept": "application/json"}, method="GET")
    with urllib_request.urlopen(req, timeout=timeout_s) as response:
        data = response.read().decode("utf-8")
    parsed = json.loads(data)
    return parsed if isinstance(parsed, dict) else {}


def _post_json(url: str, body: dict[str, Any], timeout_s: float = 2.0) -> dict[str, Any]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib_request.Request(
        url,
        data=data,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib_request.urlopen(req, timeout=timeout_s) as response:
        raw = response.read().decode("utf-8", errors="replace")
    parsed = json.loads(raw) if raw else {}
    return parsed if isinstance(parsed, dict) else {}


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _repair_text(value: str) -> str:
    text = str(value)
    if not any(marker in text for marker in ("ì", "ë", "ê", "í")):
        return text
    try:
        repaired = text.encode("latin1").decode("utf-8")
    except Exception:
        return text
    if any("\uac00" <= char <= "\ud7a3" for char in repaired):
        return repaired
    return text


def _repair_value(value: Any) -> Any:
    if isinstance(value, str):
        return _repair_text(value)
    if isinstance(value, list):
        return [_repair_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _repair_value(item) for key, item in value.items()}
    return value


def _as_int(value: Any, default: int = 0) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number


def _as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _valid_aircraft_id(value: Any) -> bool:
    return bool(AIRCRAFT_ID_RE.fullmatch(str(value or "").strip()))


def _session_dir_from_state() -> tuple[Path | None, dict[str, Any]]:
    state_url = f"{_state_base_url()}/api/state"
    try:
        state = _fetch_json(state_url, timeout_s=0.45)
    except (OSError, TimeoutError, urllib_error.URLError, json.JSONDecodeError) as exc:
        return None, {"connected": False, "url": state_url, "error": str(exc)}
    except Exception as exc:
        return None, {"connected": False, "url": state_url, "error": f"{type(exc).__name__}: {exc}"}

    db = state.get("db") if isinstance(state.get("db"), dict) else {}
    session_dir = str(db.get("session_dir") or "").strip()
    path = Path(session_dir) if session_dir else None
    return path, {
        "connected": True,
        "url": state_url,
        "session_dir": str(path or ""),
        "session_exists": bool(path and path.is_dir()),
    }


def _fallback_session_dirs(limit: int = 5) -> list[Path]:
    if not STATE_DB_ROOT.is_dir():
        return []
    try:
        return sorted(
            (path for path in STATE_DB_ROOT.iterdir() if path.is_dir() and path.name.startswith("ServerStart_")),
            key=lambda item: item.name,
            reverse=True,
        )[:limit]
    except Exception:
        return []


def _scheduled_flight_files() -> tuple[list[Path], dict[str, Any]]:
    session_dir, state_status = _session_dir_from_state()
    search_dirs: list[Path] = []
    if session_dir and session_dir.is_dir():
        search_dirs.append(session_dir)
    else:
        search_dirs.extend(_fallback_session_dirs())

    files: list[Path] = []
    for root in search_dirs:
        folder = root / "ScheduledFlight"
        if not folder.is_dir():
            continue
        try:
            files.extend(path for path in folder.glob("*.json") if path.is_file())
        except Exception:
            continue
    files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    state_status["searched_session_dirs"] = [str(path) for path in search_dirs]
    return files, state_status


def _latest_3001_payload() -> tuple[dict[str, Any] | None, dict[str, Any]]:
    url = f"{_state_base_url()}/api/db/messages/3001/latest"
    try:
        latest = _fetch_json(url, timeout_s=0.45)
    except Exception as exc:
        return None, {"connected": False, "url": url, "error": str(exc)}
    payload = latest.get("payload") if isinstance(latest.get("payload"), dict) else None
    return payload, {
        "connected": True,
        "url": url,
        "ok": bool(latest.get("ok")),
        "path": str(latest.get("path") or ""),
        "modified_at": str(latest.get("modified_at") or ""),
    }


def _plan_departure(plan: dict[str, Any]) -> dict[str, Any]:
    return plan.get("departure") if isinstance(plan.get("departure"), dict) else {}


def _plan_arrival(plan: dict[str, Any]) -> dict[str, Any]:
    return plan.get("arrival") if isinstance(plan.get("arrival"), dict) else {}


def _plan_enroute(plan: dict[str, Any]) -> list[Any]:
    route = plan.get("enRoute")
    return route if isinstance(route, list) else []


def _time_value(plan: dict[str, Any]) -> str:
    dep = _plan_departure(plan)
    return str(dep.get("etot") or dep.get("std") or "")


def _time_bucket(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "No time"
    match = re.search(r"(\d{2}):(\d{2})", text)
    if not match:
        return "Time text"
    hour = int(match.group(1))
    return f"{hour:02d}:00-{hour:02d}:59"


def _validate_3001(plan: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    flight_plan_number = _as_int(plan.get("flightPlanNumber"))
    plan_version = _as_int(plan.get("planVersion"), 1)
    aircraft_id = str(plan.get("aircraftId") or "").strip()
    dep = _plan_departure(plan)
    arr = _plan_arrival(plan)

    if flight_plan_number < 1 or flight_plan_number > 9_999_999:
        issues.append("flightPlanNumber range")
    if plan_version < 1:
        issues.append("planVersion range")
    if not _valid_aircraft_id(aircraft_id):
        issues.append("aircraftId pattern")
    if not str(dep.get("vertiport") or "").strip():
        issues.append("departure.vertiport missing")
    if not str(arr.get("vertiport") or "").strip():
        issues.append("arrival.vertiport missing")
    if not str(dep.get("std") or dep.get("etot") or "").strip():
        issues.append("departure time missing")
    if not str(arr.get("sta") or arr.get("eldt") or "").strip():
        issues.append("arrival time missing")
    route = _plan_enroute(plan)
    if not route:
        issues.append("enRoute required")
    last_seq = 0
    for index, item in enumerate(route):
        if not isinstance(item, dict):
            issues.append(f"enRoute[{index}] object")
            continue
        seq = _as_int(item.get("seq"))
        phase = str(item.get("phase") or "").strip()
        speed = _as_float(item.get("targetSpeed"))
        if seq < 1 or seq > 9999:
            issues.append(f"enRoute[{index}].seq range")
        if seq <= last_seq:
            issues.append(f"enRoute[{index}].seq order")
        last_seq = seq
        if not re.fullmatch(r"[A-Z]", phase):
            issues.append(f"enRoute[{index}].phase pattern")
        _validate_lla(item.get("startLLA") if isinstance(item.get("startLLA"), dict) else None, f"enRoute[{index}].startLLA", issues)
        _validate_lla(item.get("endLLA") if isinstance(item.get("endLLA"), dict) else None, f"enRoute[{index}].endLLA", issues)
        if speed is None or speed < 0 or speed > 200:
            issues.append(f"enRoute[{index}].targetSpeed range")
        if "turnDirection" in item:
            turn = str(item.get("turnDirection") or "").strip()
            if turn not in {"CW", "CCW"}:
                issues.append(f"enRoute[{index}].turnDirection enum")
            _validate_lla(item.get("centerLLA") if isinstance(item.get("centerLLA"), dict) else None, f"enRoute[{index}].centerLLA", issues)
    return issues


def _normalize_3001(raw: dict[str, Any], *, source: str, modified_at: str = "") -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    raw = _repair_value(raw)
    if not any(key in raw for key in ("flightPlanNumber", "aircraftId", "departure", "arrival", "enRoute")):
        return None

    dep = _plan_departure(raw)
    arr = _plan_arrival(raw)
    route = _plan_enroute(raw)
    issues = _validate_3001(raw)
    plan_version = _as_int(raw.get("planVersion"), 1)
    plan_status = str(raw.get("planStatus") or "pending").strip() or "pending"
    flight_plan_number = _as_int(raw.get("flightPlanNumber"))
    aircraft_id = str(raw.get("aircraftId") or "").strip()
    key = f"{flight_plan_number}:{aircraft_id}:v{plan_version}"

    return {
        "key": key,
        "flightPlanNumber": flight_plan_number,
        "planVersion": plan_version,
        "planStatus": plan_status,
        "aircraftId": aircraft_id,
        "departure": dep,
        "arrival": arr,
        "enRoute": route,
        "departureVertiport": str(dep.get("vertiport") or ""),
        "departureGate": str(dep.get("depGateNumber") or ""),
        "departureFato": str(dep.get("depFatoNumber") or ""),
        "std": str(dep.get("std") or ""),
        "eobt": str(dep.get("eobt") or ""),
        "etot": str(dep.get("etot") or ""),
        "arrivalVertiport": str(arr.get("vertiport") or ""),
        "arrivalGate": str(arr.get("arrGateNumber") or ""),
        "arrivalFato": str(arr.get("arrFatoNumber") or ""),
        "sta": str(arr.get("sta") or ""),
        "eibt": str(arr.get("eibt") or ""),
        "eldt": str(arr.get("eldt") or ""),
        "routeSeqCount": len(route),
        "validationIssues": issues,
        "reviewStatus": "NEED_REVIEW" if issues else "OK",
        "isModification": plan_version > 1,
        "timeBucket": _time_bucket(_time_value(raw)),
        "source": source,
        "modifiedAt": modified_at,
        "raw": raw,
    }


def _dedupe_plans(plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for plan in plans:
        key = str(plan.get("key") or "")
        if not key:
            continue
        current = deduped.get(key)
        if current is None:
            deduped[key] = plan
            continue
        current_mtime = str(current.get("modifiedAt") or "")
        next_mtime = str(plan.get("modifiedAt") or "")
        if next_mtime >= current_mtime:
            deduped[key] = plan
    return sorted(
        deduped.values(),
        key=lambda item: (
            str(item.get("departureVertiport") or ""),
            str(item.get("arrivalVertiport") or ""),
            str(item.get("etot") or item.get("std") or ""),
            int(item.get("flightPlanNumber") or 0),
        ),
    )


def _group_count(plans: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for plan in plans:
        key = str(plan.get(field) or "Unspecified")
        counts[key] = counts.get(key, 0) + 1
    return [{"key": key, "count": count} for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


def _plan_summary(plans: list[dict[str, Any]]) -> dict[str, int]:
    active = 0
    pending = 0
    need_review = 0
    modification = 0
    for plan in plans:
        status = str(plan.get("planStatus") or "").lower()
        if status == "active":
            active += 1
        elif status in {"superseded", "discarded"}:
            pass
        else:
            pending += 1
        if plan.get("validationIssues"):
            need_review += 1
        if plan.get("isModification"):
            modification += 1
    return {
        "pending": pending,
        "active": active,
        "need_review": need_review,
        "modification": modification,
        "total": len(plans),
    }


def load_scheduled_flights() -> dict[str, Any]:
    plans: list[dict[str, Any]] = []
    latest_payload, latest_status = _latest_3001_payload()
    if latest_payload:
        normalized = _normalize_3001(
            latest_payload,
            source="StateServerREST/3001",
            modified_at=str(latest_status.get("modified_at") or ""),
        )
        if normalized:
            plans.append(normalized)

    files, state_status = _scheduled_flight_files()
    for path in files[:1000]:
        payload = _read_json_file(path)
        normalized = _normalize_3001(
            payload,
            source="StateServerDB/3001",
            modified_at=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
        )
        if normalized:
            plans.append(normalized)

    plans = _dedupe_plans(plans)
    return {
        "message_id": "3001",
        "plans": plans,
        "summary": _plan_summary(plans),
        "groups": {
            "byDestination": _group_count(plans, "arrivalVertiport"),
            "byOrigin": _group_count(plans, "departureVertiport"),
            "byTimeBucket": _group_count(plans, "timeBucket"),
            "byStatus": _group_count(plans, "planStatus"),
        },
        "data_link": {
            "state_server": state_status,
            "latest_rest": latest_status,
            "file_count": len(files),
            "using_only_received_3001": True,
        },
        "generated_at": _utc_iso(),
    }


def _warning_event_files(limit: int = WARNING_FILE_LIMIT) -> tuple[list[Path], dict[str, Any]]:
    session_dir, state_status = _session_dir_from_state()
    search_dirs: list[Path] = []
    if session_dir and session_dir.is_dir():
        search_dirs.append(session_dir)
    else:
        search_dirs.extend(_fallback_session_dirs())

    files: list[Path] = []
    for root in search_dirs:
        folder = root / "VehicleWarningEvent"
        if not folder.is_dir():
            continue
        try:
            files.extend(path for path in folder.glob("*.json") if path.is_file())
        except Exception:
            continue
    files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    state_status["searched_session_dirs"] = [str(path) for path in search_dirs]
    return files[:limit], state_status


def _latest_4002_payload() -> tuple[dict[str, Any] | None, dict[str, Any]]:
    url = f"{_state_base_url()}/api/db/messages/4002/latest"
    try:
        latest = _fetch_json(url, timeout_s=0.45)
    except Exception as exc:
        return None, {"connected": False, "url": url, "error": str(exc)}
    payload = latest.get("payload") if isinstance(latest.get("payload"), dict) else None
    return payload, {
        "connected": True,
        "url": url,
        "ok": bool(latest.get("ok")),
        "path": str(latest.get("path") or ""),
        "modified_at": str(latest.get("modified_at") or ""),
    }


def _warning_battery_pct(raw: dict[str, Any]) -> float | None:
    detected = raw.get("detectedValue") if isinstance(raw.get("detectedValue"), dict) else {}
    return _as_float(
        detected.get("battery_pct")
        or detected.get("batteryPct")
        or detected.get("state_of_charge_pct")
        or raw.get("battery_pct")
    )


def _normalize_4002(raw: dict[str, Any], *, source: str, modified_at: str = "") -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    raw = _repair_value(raw)
    if not any(key in raw for key in ("eventId", "vehicleId", "eventType", "severity")):
        return None

    vehicle_id = str(raw.get("vehicleId") or raw.get("aircraftId") or "").strip()
    severity = str(raw.get("severity") or "").strip().lower()
    if not vehicle_id or severity not in WARNING_SEVERITIES:
        return None
    event_id = str(raw.get("eventId") or "").strip() or f"WARN-{vehicle_id}"

    return {
        "eventId": event_id,
        "vehicleId": vehicle_id,
        "severity": severity,
        "eventType": str(raw.get("eventType") or "").strip(),
        "status": str(raw.get("status") or "").strip(),
        "battery_pct": _warning_battery_pct(raw),
        "recommendedAction": str(raw.get("recommendedAction") or "").strip(),
        "availableDistance": _as_float(raw.get("availableDistance")),
        "timestamp": str(raw.get("timestamp") or ""),
        "description": str(raw.get("description") or ""),
        "isCritical": severity in {"critical", "fatal"},
        "source": source,
        "modifiedAt": modified_at,
        "raw": raw,
    }


def _dedupe_warning_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for event in events:
        key = str(event.get("eventId") or "")
        if not key:
            continue
        current = deduped.get(key)
        if current is None or str(event.get("modifiedAt") or "") >= str(current.get("modifiedAt") or ""):
            deduped[key] = event
    return sorted(
        deduped.values(),
        key=lambda item: (str(item.get("timestamp") or ""), str(item.get("modifiedAt") or "")),
        reverse=True,
    )


def load_warning_events() -> dict[str, Any]:
    """Load received MSG 4002 vehicle warning events.

    Reads the StateServer REST latest payload first and falls back to the
    session DB VehicleWarningEvent folder, mirroring load_scheduled_flights.
    Malformed payloads are skipped silently by the normalizer.
    """
    events: list[dict[str, Any]] = []
    latest_payload, latest_status = _latest_4002_payload()
    if latest_payload:
        normalized = _normalize_4002(
            latest_payload,
            source="StateServerREST/4002",
            modified_at=str(latest_status.get("modified_at") or ""),
        )
        if normalized:
            events.append(normalized)

    files, state_status = _warning_event_files()
    for path in files:
        payload = _read_json_file(path)
        normalized = _normalize_4002(
            payload,
            source="StateServerDB/4002",
            modified_at=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
        )
        if normalized:
            events.append(normalized)

    events = _dedupe_warning_events(events)
    critical_count = sum(1 for event in events if event.get("isCritical"))
    return {
        "ok": True,
        "message_id": "4002",
        "events": events,
        "critical_count": critical_count,
        "summary": {
            "total": len(events),
            "critical": critical_count,
            "active": sum(1 for event in events if str(event.get("status") or "").lower() == "active"),
        },
        "data_link": {
            "state_server": state_status,
            "latest_rest": latest_status,
            "file_count": len(files),
            "using_only_received_4002": True,
        },
        "generated_at": _utc_iso(),
    }


def build_3002_draft(data: dict[str, Any]) -> dict[str, Any]:
    now = _utc_now()
    payload = {
        "timestamp": str(data.get("timestamp") or _utc_iso(now)),
        "commandId": str(data.get("commandId") or _command_id("SMP", now)).strip(),
        "flightPlanNumber": _as_int(data.get("flightPlanNumber")),
        "planVersion": _as_int(data.get("planVersion"), 1),
        "aircraftId": str(data.get("aircraftId") or "").strip(),
        "modificationType": str(data.get("modificationType") or "").strip(),
        "reasonCode": str(data.get("reasonCode") or "").strip(),
        "modifyScope": str(data.get("modifyScope") or "").strip(),
    }
    issues: list[str] = []
    if not payload["commandId"]:
        issues.append("commandId required")
    if payload["flightPlanNumber"] < 1 or payload["flightPlanNumber"] > 9_999_999:
        issues.append("flightPlanNumber range")
    if payload["planVersion"] < 1:
        issues.append("planVersion range")
    if not _valid_aircraft_id(payload["aircraftId"]):
        issues.append("aircraftId pattern")
    if payload["modificationType"] not in MODIFICATION_TYPES:
        issues.append("modificationType enum")
    if payload["reasonCode"] not in STRATEGIC_REASONS:
        issues.append("reasonCode enum")
    if payload["modifyScope"] not in MODIFY_SCOPES:
        issues.append("modifyScope enum")
    return {
        "ok": not issues,
        "validation_ok": not issues,
        "message_id": "3002",
        "dispatch": {
            "attempted": False,
            "ok": False,
            "status": "draft_only",
            "targetRole": "",
            "target": "state_server",
            "stateServerUrl": _state_base_url(),
            "message": "Draft only. No DTAM dispatch was attempted.",
        },
        "dispatch_note": "Draft only. No DTAM dispatch was attempted.",
        "validationIssues": issues,
        "payload": payload,
        "icd_fields": [
            "timestamp",
            "commandId",
            "flightPlanNumber",
            "planVersion",
            "aircraftId",
            "modificationType",
            "reasonCode",
            "modifyScope",
        ],
    }


def _lla(data: dict[str, Any], lat_key: str = "lat", lon_key: str = "lon", alt_key: str = "alt") -> dict[str, float] | None:
    lat = _as_float(data.get(lat_key))
    lon = _as_float(data.get(lon_key))
    alt = _as_float(data.get(alt_key))
    if lat is None or lon is None or alt is None:
        return None
    return {"lat": lat, "lon": lon, "alt": alt}


def _validate_lla(value: dict[str, Any] | None, label: str, issues: list[str]) -> None:
    if not isinstance(value, dict):
        issues.append(f"{label} required")
        return
    lat = _as_float(value.get("lat"))
    lon = _as_float(value.get("lon"))
    alt = _as_float(value.get("alt"))
    if lat is None or lat < -90 or lat > 90:
        issues.append(f"{label}.lat range")
    if lon is None or lon < -180 or lon > 180:
        issues.append(f"{label}.lon range")
    if alt is None or alt < -500 or alt > 20000:
        issues.append(f"{label}.alt range")


def _clean_tactical_action(raw: dict[str, Any], issues: list[str], index: int) -> dict[str, Any] | None:
    action_type = str(raw.get("type") or "").strip()
    label = f"actions[{index}]"
    if action_type not in TACTICAL_ACTION_TYPES:
        issues.append(f"{label}.type enum")
        return None

    action: dict[str, Any] = {"type": action_type}
    if action_type == "setSpeed":
        speed = _as_float(raw.get("targetSpeed"))
        if speed is None or speed < 0 or speed > 200:
            issues.append(f"{label}.targetSpeed range")
        action["targetSpeed"] = speed
    elif action_type == "directTo":
        targets = raw.get("targetLLAs") if isinstance(raw.get("targetLLAs"), list) else []
        cleaned_targets: list[dict[str, float]] = []
        if not targets:
            issues.append(f"{label}.targetLLAs required")
        for target_index, target in enumerate(targets):
            target_dict = target if isinstance(target, dict) else {}
            _validate_lla(target_dict, f"{label}.targetLLAs[{target_index}]", issues)
            speed = _as_float(target_dict.get("targetSpeed"))
            if speed is None or speed < 0 or speed > 200:
                issues.append(f"{label}.targetLLAs[{target_index}].targetSpeed range")
            cleaned_targets.append(
                {
                    "lat": _as_float(target_dict.get("lat")) or 0.0,
                    "lon": _as_float(target_dict.get("lon")) or 0.0,
                    "alt": _as_float(target_dict.get("alt")) or 0.0,
                    "targetSpeed": speed or 0.0,
                }
            )
        action["targetLLAs"] = cleaned_targets
    elif action_type == "hold":
        hold_lla = raw.get("holdLLA") if isinstance(raw.get("holdLLA"), dict) else None
        _validate_lla(hold_lla, f"{label}.holdLLA", issues)
        turn = str(raw.get("turnDirection") or "").strip()
        radius = _as_float(raw.get("holdingRadiusM"))
        count = _as_int(raw.get("maxHoldingCount"), -1)
        if turn not in {"CW", "CCW"}:
            issues.append(f"{label}.turnDirection enum")
        if radius is None or radius < 1 or radius > 5000:
            issues.append(f"{label}.holdingRadiusM range")
        if count < 0 or count > 9999:
            issues.append(f"{label}.maxHoldingCount range")
        action.update(
            {
                "holdLLA": hold_lla or {"lat": 0.0, "lon": 0.0, "alt": 0.0},
                "turnDirection": turn or "CW",
                "holdingRadiusM": radius or 0.0,
                "maxHoldingCount": max(0, count),
            }
        )
    elif action_type == "rejoinPlan":
        at_seq = _as_int(raw.get("atSeq"))
        if at_seq < 1 or at_seq > 9999:
            issues.append(f"{label}.atSeq range")
        action["atSeq"] = at_seq
    elif action_type == "land":
        target_lla = raw.get("targetLLA") if isinstance(raw.get("targetLLA"), dict) else None
        vertiport = str(raw.get("vertiport") or "").strip()
        fato_number = str(raw.get("fatoNumber") or "").strip()
        if not target_lla and not vertiport:
            issues.append(f"{label}.targetLLA or vertiport required")
        if target_lla:
            _validate_lla(target_lla, f"{label}.targetLLA", issues)
            action["targetLLA"] = target_lla
        if vertiport:
            action["vertiport"] = vertiport
        if fato_number:
            action["fatoNumber"] = fato_number
    return action


def build_3003_draft(data: dict[str, Any]) -> dict[str, Any]:
    now = _utc_now()
    raw_actions = data.get("actions") if isinstance(data.get("actions"), list) else []
    issues: list[str] = []
    actions: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_actions):
        if not isinstance(raw, dict):
            issues.append(f"actions[{index}] object")
            continue
        action = _clean_tactical_action(raw, issues, index)
        if action:
            actions.append(action)

    payload = {
        "timestamp": str(data.get("timestamp") or _utc_iso(now)),
        "commandId": str(data.get("commandId") or _command_id("TMP", now)).strip(),
        "aircraftId": str(data.get("aircraftId") or "").strip(),
        "reasonCode": str(data.get("reasonCode") or "").strip(),
        "actions": actions,
    }
    if not payload["commandId"]:
        issues.append("commandId required")
    if not _valid_aircraft_id(payload["aircraftId"]):
        issues.append("aircraftId pattern")
    if payload["reasonCode"] not in TACTICAL_REASONS:
        issues.append("reasonCode enum")
    if not actions:
        issues.append("actions length")
    return {
        "ok": not issues,
        "validation_ok": not issues,
        "message_id": "3003",
        "dispatch": {
            "attempted": False,
            "ok": False,
            "status": "draft_only",
            "targetRole": "vehicle",
            "stateServerUrl": _state_base_url(),
            "message": "Draft only. No DTAM dispatch was attempted.",
        },
        "dispatch_note": "Draft only. No DTAM dispatch was attempted.",
        "validationIssues": issues,
        "payload": payload,
        "icd_fields": ["timestamp", "commandId", "aircraftId", "reasonCode", "actions"],
    }


def build_3003_land_draft_from_warning(event: dict[str, Any]) -> dict[str, Any]:
    """Build a prefilled 3003 land draft from a normalized 4002 warning event.

    The vertiport/FATO landing target is intentionally left for the operator,
    so the draft keeps a validation issue until the target is selected.
    """
    event = event if isinstance(event, dict) else {}
    draft = build_3003_draft(
        {
            "aircraftId": str(event.get("vehicleId") or "").strip(),
            "reasonCode": "LOW_BATTERY",
            "actions": [{"type": "land"}],
        }
    )
    draft["draft_source"] = "4002-warning-event"
    draft["warning_event"] = {
        "eventId": event.get("eventId"),
        "vehicleId": event.get("vehicleId"),
        "severity": event.get("severity"),
        "eventType": event.get("eventType"),
        "battery_pct": event.get("battery_pct"),
        "recommendedAction": event.get("recommendedAction"),
    }
    return draft


def _dispatch_payload(mid: str, payload: dict[str, Any], *, target_role: str = "") -> dict[str, Any]:
    base_url = _state_base_url()
    endpoint = f"{base_url}/api/msg/{mid}"
    role = str(target_role or "").strip().lower()
    target_label = role or "state_server"
    try:
        response = _post_json(
            endpoint,
            {"role": role, "payload": payload},
            timeout_s=2.0,
        )
    except Exception as exc:
        return {
            "attempted": True,
            "ok": False,
            "status": "state_server_unreachable",
            "targetRole": role,
            "target": target_label,
            "stateServerUrl": base_url,
            "endpoint": endpoint,
            "message": f"StateServer is not reachable at {base_url}. Start the DTAM stack before sending.",
            "error": f"{type(exc).__name__}: {exc}",
        }

    errors = response.get("errors") if isinstance(response.get("errors"), list) else []
    ok = bool(response.get("ok"))
    if ok:
        if role:
            status = "sent"
            message = f"Sent to {role} through StateServer."
        else:
            status = "accepted_by_state_server"
            message = "Accepted by StateServer and stored in the StateServer DB."
    elif role and any("not connected" in str(item).lower() for item in errors):
        status = "target_not_connected"
        message = f"StateServer is reachable, but {role} is not connected."
    else:
        status = "send_failed"
        message = "; ".join(str(item) for item in errors) or "StateServer rejected or failed the dispatch."

    return {
        "attempted": True,
        "ok": ok,
        "status": status,
        "targetRole": role,
        "target": target_label,
        "stateServerUrl": base_url,
        "endpoint": endpoint,
        "message": message,
        "response": response,
    }


def _with_dispatch_result(draft: dict[str, Any], mid: str, *, target_role: str = "") -> dict[str, Any]:
    result = dict(draft)
    role = str(target_role or "").strip().lower()
    validation_ok = bool(result.get("validation_ok", result.get("ok")))
    if not validation_ok:
        result["ok"] = False
        result["dispatch"] = {
            "attempted": False,
            "ok": False,
            "status": "validation_failed",
            "targetRole": role,
            "target": role or "state_server",
            "stateServerUrl": _state_base_url(),
            "message": "Command was not sent because ICD validation failed.",
        }
        result["dispatch_note"] = result["dispatch"]["message"]
        return result

    dispatch = _dispatch_payload(mid, result.get("payload") if isinstance(result.get("payload"), dict) else {}, target_role=role)
    result["dispatch"] = dispatch
    result["dispatch_note"] = str(dispatch.get("message") or "")
    result["sent"] = bool(dispatch.get("ok"))
    result["ok"] = bool(dispatch.get("ok"))
    return result


def dispatch_3002_command(data: dict[str, Any]) -> dict[str, Any]:
    return _with_dispatch_result(build_3002_draft(data), "3002", target_role="")


def dispatch_3003_command(data: dict[str, Any]) -> dict[str, Any]:
    return _with_dispatch_result(build_3003_draft(data), "3003", target_role="vehicle")


def summarize_vehicle_snapshot(snapshot: dict[str, Any]) -> dict[str, int]:
    vehicles = snapshot.get("vehicles") if isinstance(snapshot.get("vehicles"), list) else []
    live = sum(1 for vehicle in vehicles if not vehicle.get("stale"))
    stale = sum(1 for vehicle in vehicles if vehicle.get("stale"))
    low_battery = 0
    collision = 0
    for vehicle in vehicles:
        energy = vehicle.get("energy") if isinstance(vehicle.get("energy"), dict) else {}
        battery = _as_float(
            vehicle.get("batteryPct")
            or vehicle.get("battery_pct")
            or vehicle.get("batteryRemainingPct")
            or energy.get("batteryRemainingPct")
            or energy.get("batteryPct")
            or energy.get("battery_pct")
            or energy.get("state_of_charge_pct")
        )
        if battery is not None and battery <= 20:
            low_battery += 1
        collision_data = vehicle.get("collision") if isinstance(vehicle.get("collision"), dict) else {}
        if bool(vehicle.get("collisionActive") or collision_data.get("active") or collision_data.get("hasCollision")):
            collision += 1
    return {
        "total": len(vehicles),
        "live": live,
        "stale": stale,
        "low_battery": low_battery,
        "collision": collision,
    }


__all__ = [
    "build_3002_draft",
    "build_3003_draft",
    "build_3003_land_draft_from_warning",
    "dispatch_3002_command",
    "dispatch_3003_command",
    "load_scheduled_flights",
    "load_warning_events",
    "summarize_vehicle_snapshot",
]
