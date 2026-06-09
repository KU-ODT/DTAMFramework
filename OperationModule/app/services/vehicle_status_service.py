"""Latest DTAM 4001 vehicle status cache for the Operations Console."""

from __future__ import annotations

import logging
import math
import os
import re
import sys
import threading
import time
import json
import dataclasses
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from app.core.settings import settings

logger = logging.getLogger(__name__)

STALE_AFTER_S = 3.0
DROP_AFTER_S = 30.0
AIRMOBILITY_URL_ENV = "DTAM_AIRMOBILITY_URL"
DEFAULT_AIRMOBILITY_URL = "http://127.0.0.1:8100"

_lock = threading.RLock()
_client: Any = None
_vehicles: dict[str, dict[str, Any]] = {}
_collisions_by_vehicle: dict[str, dict[str, Any]] = {}
_cleared_collision_events: dict[str, str] = {}
_rx_count = 0
_collision_rx_count = 0
_last_message_ts = ""
_last_received_epoch = 0.0
_last_collision_event: dict[str, Any] = {}
_last_error = ""
_listening = False


def _ensure_sdk_on_path() -> None:
    sdk_root = settings.project_root.parent / "DTAMSDK"
    if not sdk_root.exists():
        raise RuntimeError(f"DTAMSDK not found at {sdk_root}")
    sdk_path = str(sdk_root)
    if sdk_path not in sys.path:
        sys.path.insert(0, sdk_path)


def _iso_from_epoch(epoch_s: float) -> str:
    try:
        value = float(epoch_s)
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(value) or value <= 0:
        return ""
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        try:
            converted = value.to_dict()
            return dict(converted) if isinstance(converted, dict) else {}
        except Exception:
            return {}
    return {}


def _message_to_wire(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_wire"):
        try:
            converted = value.to_wire()
            return dict(converted) if isinstance(converted, dict) else {}
        except Exception:
            return {}
    if hasattr(value, "to_dict"):
        try:
            converted = value.to_dict()
            return dict(converted) if isinstance(converted, dict) else {}
        except Exception:
            return {}
    if dataclasses.is_dataclass(value):
        try:
            raw = dataclasses.asdict(value)
            if "vehicles" in raw and isinstance(raw["vehicles"], dict):
                out = {"timestamp": raw.get("timestamp", "")}
                out.update(raw["vehicles"])
                return out
            return raw
        except Exception:
            return {}
    return {}


def _canonical_vehicle_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = re.fullmatch(r"([A-Za-z]+)[\s_-]*0*(\d+)", text)
    if not match:
        return text
    return f"{match.group(1).upper()}{match.group(2).zfill(4)}"


def _json_safe(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _first_number(*values: Any) -> float | None:
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(number):
            continue
        return number
    return None


def _safe_epoch(value: Any) -> float:
    number = _first_number(value)
    return number if number is not None and number > 0 else 0.0


def _airmobility_base_url() -> str:
    return str(os.environ.get(AIRMOBILITY_URL_ENV) or DEFAULT_AIRMOBILITY_URL).strip().rstrip("/")


def _fetch_airmobility_status() -> dict[str, Any]:
    request = urllib_request.Request(
        f"{_airmobility_base_url()}/api/status",
        headers={"Accept": "application/json"},
        method="GET",
    )
    with urllib_request.urlopen(request, timeout=0.45) as response:
        return json.loads(response.read().decode("utf-8"))


def _truthy(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if not text:
        return default
    if text in {"1", "true", "yes", "y", "on", "collided", "active"}:
        return True
    if text in {"0", "false", "no", "n", "off", "none", "clear", "cleared", "inactive"}:
        return False
    return default


def _normalize_collision_response_mode(event: dict[str, Any]) -> str:
    if not isinstance(event, dict):
        return "none"
    has_collided = _truthy(event.get("hasCollided"), True)
    action = str(event.get("recommendedAction") or event.get("action") or "").strip().lower()
    action = action.replace("-", "_").replace(" ", "_")
    severity = str(event.get("severity") or "").strip().lower()

    if not has_collided or action in {"clear", "cleared", "release", "resume", "reset"}:
        return "clear"
    if action in {"none", "noop", "no_op", "monitor", "record", "log"}:
        return "none"
    if action in {"hold", "pause", "brake"}:
        return "hold"
    if action in {"stop", "emergency", "emergency_stop", "emergency_hold"}:
        return "emergency_stop"
    if action in {"abort", "terminate", "fatal", "emergency_abort", "emergency_land"}:
        return "abort"
    if severity == "fatal":
        return "abort"
    if severity == "critical":
        return "emergency_stop"
    if severity == "warning":
        return "hold"
    return "none"


def _collision_snapshot_from_event(event: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(event, dict):
        event = {}
    response_mode = _normalize_collision_response_mode(event)
    event_id = str(event.get("eventId") or event.get("event_id") or "").strip()
    timestamp = str(event.get("timestamp") or _iso_from_epoch(time.time())).strip()
    has_collided = _truthy(event.get("hasCollided"), True)
    active = bool(has_collided and response_mode not in {"clear", "none"})
    aircraft_id = _canonical_vehicle_id(
        event.get("aircraftId")
        or event.get("vehicleId")
        or event.get("vehicle_id")
        or ""
    )
    return {
        "active": active,
        "responseActive": response_mode in {"hold", "emergency_stop", "abort"},
        "lastEventId": event_id,
        "eventId": event_id,
        "aircraftId": aircraft_id,
        "airsimVehicleName": str(event.get("airsimVehicleName") or "").strip(),
        "objectName": str(event.get("objectName") or "").strip(),
        "objectId": event.get("objectId", -1),
        "severity": str(event.get("severity") or "").strip().lower() or "info",
        "recommendedAction": str(event.get("recommendedAction") or "").strip().lower() or "none",
        "responseMode": response_mode,
        "timestamp": timestamp,
        "impactSpeedMps": _first_number(event.get("impactSpeedMps"), 0.0) or 0.0,
        "source": str(event.get("source") or "4103").strip() or "4103",
    }


def _collision_event_id_from_payload(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    collision = payload.get("collision") if isinstance(payload.get("collision"), dict) else payload
    return str(
        collision.get("eventId")
        or collision.get("lastEventId")
        or collision.get("event_id")
        or ""
    ).strip()


def _drop_cleared_collision_from_vehicle_locked(vehicle_id: str, vehicle: dict[str, Any]) -> None:
    """Remove stale 4001 collision snapshots that were already cleared locally.

    VehicleModule can briefly keep publishing the previous 4001 sub-payload
    while a high-fidelity telemetry source is stale.  If that old payload still
    contains the cleared collision snapshot, OperationModule should not revive
    the red collision badge.
    """
    if not vehicle_id or not isinstance(vehicle, dict):
        return
    cleared_event_id = _cleared_collision_events.get(vehicle_id)
    if not cleared_event_id:
        return
    current_event_id = _collision_event_id_from_payload(vehicle.get("collision"))
    if current_event_id and current_event_id == cleared_event_id:
        vehicle.pop("collision", None)


def _vehicles_from_airmobility_status(now: float) -> dict[str, dict[str, Any]]:
    try:
        status = _fetch_airmobility_status()
    except (OSError, TimeoutError, urllib_error.URLError, json.JSONDecodeError):
        return {}
    except Exception as exc:
        logger.debug("Air Mobility status fallback unavailable: %s", exc)
        return {}

    if not isinstance(status, dict) or not status.get("running"):
        return {}

    responses = (
        status.get("collision_responses_by_vehicle")
        if isinstance(status.get("collision_responses_by_vehicle"), dict)
        else {}
    )
    result: dict[str, dict[str, Any]] = {}
    for item in status.get("vehicles") or []:
        vehicle = item if isinstance(item, dict) else {}
        vehicle_id = _canonical_vehicle_id(vehicle.get("vehicle_id") or vehicle.get("aircraftId") or "")
        point = vehicle.get("last_point") if isinstance(vehicle.get("last_point"), dict) else {}
        lat = _first_number(point.get("lat"), point.get("latitude"))
        lon = _first_number(point.get("lon"), point.get("longitude"))
        if not vehicle_id or lat is None or lon is None:
            continue
        alt = _first_number(point.get("alt_m"), point.get("altitude"), 0.0) or 0.0
        north = _first_number(point.get("north"), 0.0) or 0.0
        east = _first_number(point.get("east"), 0.0) or 0.0
        down = _first_number(point.get("down"), -alt) or -alt
        speed_mps = _first_number(
            point.get("speed_mps"),
            point.get("speedMps"),
            vehicle.get("speedMps"),
            0.0,
        ) or 0.0
        heading_deg = (_first_number(
            point.get("heading_deg"),
            point.get("headingDeg"),
            vehicle.get("headingDeg"),
            0.0,
        ) or 0.0) % 360.0
        track_heading_deg = (_first_number(
            point.get("track_heading_deg"),
            point.get("trackHeadingDeg"),
            vehicle.get("trackHeadingDeg"),
            heading_deg,
        ) or heading_deg) % 360.0
        track_rad = math.radians(track_heading_deg)
        velocity_north = float(speed_mps) * math.cos(track_rad)
        velocity_east = float(speed_mps) * math.sin(track_rad)
        payload = {
            "id": vehicle_id,
            "aircraftId": vehicle_id,
            "vehicle_id": vehicle_id,
            "currentWaypointId": str(point.get("waypoint_id") or vehicle.get("currentWaypointId") or ""),
            "messageTimestamp": _iso_from_epoch(now),
            "receivedAt": _iso_from_epoch(now),
            "receivedAtEpoch": now,
            "source": "airmobility-status",
            "state": vehicle.get("state") or "",
            "flightPlanNumber": vehicle.get("flight_plan_number"),
            "speedMps": float(speed_mps),
            "groundSpeedMps": float(abs(speed_mps)),
            "headingDeg": float(heading_deg),
            "trackHeadingDeg": float(track_heading_deg),
            "position": {
                "north": north,
                "east": east,
                "down": down,
            },
            "gps": {
                "is_valid": True,
                "fix_type": 3,
                "latitude": lat,
                "longitude": lon,
                "altitude": alt,
                "velocity_north": velocity_north,
                "velocity_east": velocity_east,
                "velocity_down": 0.0,
                "eph": 0.8,
                "epv": 1.2,
            },
            "attitude": {"roll": 0.0, "pitch": 0.0, "yaw": math.radians(heading_deg)},
        }
        collision = None
        # VehicleModule keeps ``collisions_by_vehicle`` as event history even after
        # clear/resume.  The OperationModule vehicle marker should reflect the
        # currently active response, so the fallback snapshot only projects
        # ``collision_responses_by_vehicle`` (plus explicit per-vehicle collision
        # fields already included in a 4001-like payload).
        candidate = responses.get(vehicle_id) or responses.get(vehicle.get("vehicle_id") or "")
        if isinstance(candidate, dict):
            collision = dict(candidate)
        if collision is None and isinstance(vehicle.get("collision"), dict):
            collision = dict(vehicle.get("collision") or {})
        if collision:
            payload["collision"] = collision
        result[vehicle_id] = payload
    return result


def _clear_local_collision(vehicle_id: str = "") -> list[str]:
    vehicle_key = _canonical_vehicle_id(vehicle_id)
    if not vehicle_key or vehicle_key.lower() in {"all", "*"}:
        affected = sorted(set(_collisions_by_vehicle.keys()) | set(_vehicles.keys()))
        for key in affected:
            event_id = _collision_event_id_from_payload(
                _collisions_by_vehicle.get(key)
                or (_vehicles.get(key) or {}).get("collision")
            )
            if event_id:
                _cleared_collision_events[key] = event_id
        _collisions_by_vehicle.clear()
        for vehicle in _vehicles.values():
            if isinstance(vehicle, dict):
                vehicle.pop("collision", None)
        return affected
    affected = [vehicle_key] if vehicle_key in _collisions_by_vehicle else []
    event_id = _collision_event_id_from_payload(
        _collisions_by_vehicle.get(vehicle_key)
        or (_vehicles.get(vehicle_key) or {}).get("collision")
    )
    if event_id:
        _cleared_collision_events[vehicle_key] = event_id
    _collisions_by_vehicle.pop(vehicle_key, None)
    vehicle = _vehicles.get(vehicle_key)
    if isinstance(vehicle, dict):
        vehicle.pop("collision", None)
        if vehicle_key not in affected:
            affected.append(vehicle_key)
    return affected


def _handle_vehicle_status(result: Any) -> None:
    global _rx_count, _last_message_ts, _last_received_epoch, _last_error
    now = time.time()
    try:
        raw = getattr(result, "raw", None) or {}
        timestamp = str(getattr(result, "timestamp", None) or raw.get("timestamp") or "")
        samples = list(getattr(result, "vehicles", None) or [])
        normalized: dict[str, dict[str, Any]] = {}
        for sample in samples:
            vehicle = _to_dict(sample)
            vehicle_id = _canonical_vehicle_id(
                vehicle.get("vehicle_id")
                or vehicle.get("aircraftId")
                or getattr(sample, "vehicle_id", "")
                or ""
            )
            if not vehicle_id:
                continue
            vehicle["id"] = vehicle_id
            vehicle["aircraftId"] = vehicle_id
            vehicle["messageTimestamp"] = timestamp
            vehicle["receivedAt"] = _iso_from_epoch(now)
            vehicle["receivedAtEpoch"] = now
            normalized[vehicle_id] = vehicle

        with _lock:
            for vehicle_id, vehicle in normalized.items():
                _drop_cleared_collision_from_vehicle_locked(vehicle_id, vehicle)
            _vehicles.update(normalized)
            _rx_count += 1
            _last_message_ts = timestamp
            _last_received_epoch = now
            _last_error = ""
    except Exception as exc:
        with _lock:
            _last_error = f"{type(exc).__name__}: {exc}"
        logger.exception("4001 vehicle status handling failed")


def record_vehicle_status(message: Any) -> None:
    """Record a 4001 message received by MonitoringService over WebSocket."""

    global _rx_count, _last_message_ts, _last_received_epoch, _last_error
    now = time.time()
    try:
        raw = _message_to_wire(message)
        timestamp = str(raw.get("timestamp") or "")
        vehicles_source = raw.get("vehicles") if isinstance(raw.get("vehicles"), dict) else raw
        normalized: dict[str, dict[str, Any]] = {}
        for vehicle_id, payload in vehicles_source.items():
            if vehicle_id in ("timestamp", "vehicles") or not isinstance(payload, dict):
                continue
            canonical_id = _canonical_vehicle_id(vehicle_id)
            if not canonical_id:
                continue
            vehicle = dict(payload)
            vehicle["id"] = canonical_id
            vehicle["aircraftId"] = canonical_id
            vehicle["vehicle_id"] = canonical_id
            vehicle["messageTimestamp"] = timestamp
            vehicle["receivedAt"] = _iso_from_epoch(now)
            vehicle["receivedAtEpoch"] = now
            vehicle["source"] = "simulation-state-ws"
            normalized[canonical_id] = vehicle

        with _lock:
            for vehicle_id, vehicle in normalized.items():
                _drop_cleared_collision_from_vehicle_locked(vehicle_id, vehicle)
            _vehicles.update(normalized)
            _rx_count += 1
            _last_message_ts = timestamp
            _last_received_epoch = now
            _last_error = ""
    except Exception as exc:
        with _lock:
            _last_error = f"{type(exc).__name__}: {exc}"
        logger.exception("4001 vehicle status recording failed")


def record_collision_event(message: Any) -> None:
    """Record a 4103 collision event received by MonitoringService over WebSocket."""

    global _collision_rx_count, _last_collision_event, _last_error
    now = time.time()
    try:
        raw = _message_to_wire(message)
        if not isinstance(raw, dict) or not raw:
            return
        vehicle_id = _canonical_vehicle_id(
            raw.get("aircraftId")
            or raw.get("vehicleId")
            or raw.get("vehicle_id")
            or ""
        )
        snapshot = _collision_snapshot_from_event(raw)
        if vehicle_id:
            snapshot["aircraftId"] = vehicle_id
        response_mode = str(snapshot.get("responseMode") or "").lower()
        should_clear = response_mode == "clear" or not bool(snapshot.get("active"))

        with _lock:
            _collision_rx_count += 1
            event_payload = dict(raw)
            event_payload["receivedAt"] = _iso_from_epoch(now)
            event_payload["receivedAtEpoch"] = now
            event_payload["collision"] = dict(snapshot)
            _last_collision_event = event_payload
            if vehicle_id:
                if should_clear:
                    _clear_local_collision(vehicle_id)
                else:
                    _cleared_collision_events.pop(vehicle_id, None)
                    _collisions_by_vehicle[vehicle_id] = dict(snapshot)
                    existing = _vehicles.get(vehicle_id)
                    if isinstance(existing, dict):
                        existing["collision"] = dict(snapshot)
            _last_error = ""
    except Exception as exc:
        with _lock:
            _last_error = f"{type(exc).__name__}: {exc}"
        logger.exception("4103 collision event recording failed")


def clear_collision_response(vehicle_id: str = "", *, clear_history: bool = False) -> dict[str, Any]:
    """Proxy collision clear/resume to VehicleModule and mirror the local UI cache."""

    vehicle_key = _canonical_vehicle_id(vehicle_id)
    if vehicle_key:
        url = f"{_airmobility_base_url()}/api/collision/{urllib_parse.quote(vehicle_key, safe='')}/clear"
        body: dict[str, Any] = {"aircraftId": vehicle_key}
    else:
        url = f"{_airmobility_base_url()}/api/collision/clear"
        body = {"all": True}
    if clear_history:
        body["clearHistory"] = True

    request = urllib_request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(request, timeout=2.0) as response:
            payload = json.loads(response.read().decode("utf-8") or "{}")
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"VehicleModule collision clear failed ({exc.code}): {detail}") from exc
    except (OSError, TimeoutError, urllib_error.URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"VehicleModule collision clear unavailable: {exc}") from exc

    with _lock:
        affected = _clear_local_collision(vehicle_key)
    if isinstance(payload, dict):
        payload.setdefault("local_cleared", affected)
        return payload
    return {"ok": True, "local_cleared": affected}


def start_vehicle_status_listener() -> None:
    """Compatibility hook; 4001 now arrives via MonitoringService WebSocket."""

    global _listening, _last_error
    with _lock:
        _listening = True
        _last_error = ""
    logger.info("4001 vehicle status listener using SimulationState WebSocket")


def stop_vehicle_status_listener() -> None:
    global _listening
    with _lock:
        _listening = False


def vehicle_status_snapshot(*, include_stale: bool = True) -> dict[str, Any]:
    now = time.time()
    am_live_vehicles = _vehicles_from_airmobility_status(now)
    with _lock:
        merged = dict(_vehicles)
        for vehicle_id, vehicle in am_live_vehicles.items():
            existing = merged.get(vehicle_id) or {}
            existing_epoch = _safe_epoch(existing.get("receivedAtEpoch"))
            existing_age = max(0.0, now - existing_epoch) if existing_epoch else None
            if existing_age is None or existing_age > 1.25:
                merged[vehicle_id] = vehicle

        items = []
        for vehicle in merged.values():
            if not isinstance(vehicle, dict):
                continue
            received_epoch = _safe_epoch(vehicle.get("receivedAtEpoch"))
            age_s = max(0.0, now - received_epoch) if received_epoch else None
            if age_s is not None and age_s > DROP_AFTER_S and not include_stale:
                continue
            item = _json_safe(dict(vehicle))
            vehicle_id = _canonical_vehicle_id(item.get("aircraftId") or item.get("id") or item.get("vehicle_id") or "")
            if vehicle_id and not isinstance(item.get("collision"), dict):
                collision = _collisions_by_vehicle.get(vehicle_id)
                if isinstance(collision, dict):
                    item["collision"] = _json_safe(dict(collision))
            item["age_s"] = round(age_s, 3) if age_s is not None else None
            item["stale"] = bool(age_s is not None and age_s > STALE_AFTER_S)
            items.append(item)

        items.sort(key=lambda item: str(item.get("aircraftId") or item.get("id") or ""))
        received_epochs = [_safe_epoch(_last_received_epoch)]
        received_epochs.extend(_safe_epoch(v.get("receivedAtEpoch")) for v in am_live_vehicles.values())
        last_received_epoch = max(received_epochs) if received_epochs else 0.0

        return {
            "listening": _listening,
            "transport": "ws",
            "ws_role": "monitoring",
            "rx_count": _rx_count,
            "last_message_timestamp": _last_message_ts,
            "last_received_at": _iso_from_epoch(last_received_epoch) if last_received_epoch else "",
            "last_error": _last_error,
            "collision_rx_count": _collision_rx_count,
            "last_collision_event": _json_safe(dict(_last_collision_event)),
            "collisions_by_vehicle": _json_safe(dict(_collisions_by_vehicle)),
            "vehicles": items,
        }
