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
from urllib import request as urllib_request

from backend.app.core.settings import settings

logger = logging.getLogger(__name__)

STALE_AFTER_S = 3.0
DROP_AFTER_S = 30.0
AIRMOBILITY_URL_ENV = "DTAM_AIRMOBILITY_URL"
DEFAULT_AIRMOBILITY_URL = "http://127.0.0.1:8100"

_lock = threading.RLock()
_client: Any = None
_vehicles: dict[str, dict[str, Any]] = {}
_rx_count = 0
_last_message_ts = ""
_last_received_epoch = 0.0
_last_error = ""
_listening = False


def _ensure_sdk_on_path() -> None:
    sdk_root = settings.project_root.parent / "DTAM_SDK"
    if not sdk_root.exists():
        raise RuntimeError(f"DTAM_SDK not found at {sdk_root}")
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
        result[vehicle_id] = {
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
                "velocity_north": 0.0,
                "velocity_east": 0.0,
                "velocity_down": 0.0,
                "eph": 0.8,
                "epv": 1.2,
            },
            "attitude": {"roll": 0.0, "pitch": 0.0, "yaw": 0.0},
        }
    return result


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
            _vehicles.update(normalized)
            _rx_count += 1
            _last_message_ts = timestamp
            _last_received_epoch = now
            _last_error = ""
    except Exception as exc:
        with _lock:
            _last_error = f"{type(exc).__name__}: {exc}"
        logger.exception("4001 vehicle status recording failed")


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
            "vehicles": items,
        }
