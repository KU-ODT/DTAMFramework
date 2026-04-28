"""Commercial aircraft traffic feed for the simulation workspace."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests


@dataclass(frozen=True)
class RegionBounds:
    lamin: float
    lomin: float
    lamax: float
    lomax: float


KOREA_BOUNDS = RegionBounds(lamin=31.5, lomin=123.0, lamax=39.5, lomax=132.8)
OPENSKY_STATES_URL = "https://opensky-network.org/api/states/all"
CACHE_TTL_SECONDS = 4.0
TRACK_TTL_SECONDS = 30 * 60
MAX_TRACK_POINTS = 36

_cache: dict[str, Any] = {"expires_at": 0.0, "payload": None}
_tracks: dict[str, list[dict[str, Any]]] = {}


def _iso_from_epoch(value: Any) -> str | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric) or numeric <= 0:
        return None
    return datetime.fromtimestamp(numeric, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _current_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _state_from_opensky_row(row: list[Any]) -> dict[str, Any] | None:
    if len(row) < 17:
        return None

    icao24 = _string(row[0]).lower()
    callsign = _string(row[1])
    lon = _number(row[5])
    lat = _number(row[6])
    if not icao24 or lat is None or lon is None:
        return None

    last_contact = row[4]
    altitude = _number(row[13])
    if altitude is None:
        altitude = _number(row[7])

    return {
        "id": icao24,
        "icao24": icao24,
        "callsign": callsign or icao24.upper(),
        "originCountry": _string(row[2]),
        "timePosition": _iso_from_epoch(row[3]),
        "lastContact": _iso_from_epoch(last_contact),
        "lastContactEpoch": _number(last_contact),
        "longitude": lon,
        "latitude": lat,
        "altitudeM": altitude,
        "baroAltitudeM": _number(row[7]),
        "geoAltitudeM": _number(row[13]),
        "onGround": bool(row[8]),
        "groundSpeedMps": _number(row[9]),
        "headingDeg": _number(row[10]),
        "verticalRateMps": _number(row[11]),
        "squawk": _string(row[14]),
        "spi": bool(row[15]),
        "positionSource": row[16],
    }


def _state_from_dataframe_record(record: dict[str, Any]) -> dict[str, Any] | None:
    icao24 = _string(record.get("icao24")).lower()
    lon = _number(record.get("longitude"))
    lat = _number(record.get("latitude"))
    if not icao24 or lat is None or lon is None:
        return None

    last_contact = record.get("last_contact")
    altitude = _number(record.get("geo_altitude"))
    if altitude is None:
        altitude = _number(record.get("baro_altitude"))

    return {
        "id": icao24,
        "icao24": icao24,
        "callsign": _string(record.get("callsign")) or icao24.upper(),
        "originCountry": _string(record.get("origin_country")),
        "timePosition": _iso_from_epoch(record.get("time_position")),
        "lastContact": _iso_from_epoch(last_contact),
        "lastContactEpoch": _number(last_contact),
        "longitude": lon,
        "latitude": lat,
        "altitudeM": altitude,
        "baroAltitudeM": _number(record.get("baro_altitude")),
        "geoAltitudeM": _number(record.get("geo_altitude")),
        "onGround": bool(record.get("on_ground")) if record.get("on_ground") is not None else False,
        "groundSpeedMps": _number(record.get("velocity")),
        "headingDeg": _number(record.get("true_track")),
        "verticalRateMps": _number(record.get("vertical_rate")),
        "squawk": _string(record.get("squawk")),
        "spi": bool(record.get("spi")) if record.get("spi") is not None else False,
        "positionSource": record.get("position_source"),
    }


def _fetch_with_pyopensky(bounds: RegionBounds) -> tuple[list[dict[str, Any]], str] | None:
    try:
        from pyopensky.rest import REST  # type: ignore
    except Exception:
        return None

    rest = REST()
    # pyopensky documents REST.states(bounds=tuple[float]) and returns a pandas DataFrame.
    dataframe = rest.states(bounds=(bounds.lomin, bounds.lamin, bounds.lomax, bounds.lamax))
    if dataframe is None:
        return [], "pyopensky"

    records = dataframe.to_dict("records")
    aircraft = []
    for record in records:
        item = _state_from_dataframe_record(record)
        if item is not None:
            aircraft.append(item)
    return aircraft, "pyopensky"


def _fetch_with_opensky_rest(bounds: RegionBounds) -> tuple[list[dict[str, Any]], str]:
    response = requests.get(
        OPENSKY_STATES_URL,
        params={
            "lamin": bounds.lamin,
            "lomin": bounds.lomin,
            "lamax": bounds.lamax,
            "lomax": bounds.lomax,
        },
        timeout=6,
    )
    response.raise_for_status()
    data = response.json()
    rows = data.get("states") or []
    aircraft = []
    for row in rows:
        if not isinstance(row, list):
            continue
        item = _state_from_opensky_row(row)
        if item is not None:
            aircraft.append(item)
    return aircraft, "opensky-rest"


def _is_commercial_like(item: dict[str, Any]) -> bool:
    if item.get("onGround"):
        return False
    callsign = _string(item.get("callsign"))
    return bool(callsign and callsign.lower() != _string(item.get("icao24")).lower())


def _track_point(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "longitude": item["longitude"],
        "latitude": item["latitude"],
        "altitudeM": item.get("altitudeM"),
        "timestamp": item.get("lastContact") or _current_iso(),
    }


def _update_tracks(aircraft: list[dict[str, Any]]) -> None:
    now = time.time()
    current_ids = set()
    for item in aircraft:
        aircraft_id = item["id"]
        current_ids.add(aircraft_id)
        track = _tracks.setdefault(aircraft_id, [])
        point = _track_point(item)
        if not track or track[-1]["longitude"] != point["longitude"] or track[-1]["latitude"] != point["latitude"]:
            track.append(point)
        del track[:-MAX_TRACK_POINTS]

    for aircraft_id in list(_tracks.keys()):
        if aircraft_id in current_ids:
            continue
        track = _tracks[aircraft_id]
        last_time = track[-1].get("timestamp") if track else None
        last_epoch = None
        if isinstance(last_time, str):
            try:
                last_epoch = datetime.fromisoformat(last_time.replace("Z", "+00:00")).timestamp()
            except ValueError:
                last_epoch = None
        if last_epoch is None or now - last_epoch > TRACK_TTL_SECONDS:
            _tracks.pop(aircraft_id, None)


def _attach_tracks(aircraft: list[dict[str, Any]]) -> None:
    for item in aircraft:
        item["track"] = list(_tracks.get(item["id"], []))


def get_commercial_traffic(region: str = "korea") -> dict[str, Any]:
    """Return live or near-live commercial-like aircraft states near Korea."""

    region_key = region.lower().strip() or "korea"
    bounds = KOREA_BOUNDS
    now = time.time()
    if _cache["payload"] is not None and now < _cache["expires_at"]:
        return dict(_cache["payload"])

    warnings: list[str] = []
    try:
        pyopensky_result = _fetch_with_pyopensky(bounds)
        if pyopensky_result is None:
            aircraft, source = _fetch_with_opensky_rest(bounds)
            warnings.append("pyopensky not installed; used OpenSky REST fallback")
        else:
            aircraft, source = pyopensky_result
    except Exception as exc:
        aircraft = []
        source = "opensky"
        warnings.append(str(exc))

    aircraft = [item for item in aircraft if _is_commercial_like(item)]
    aircraft.sort(key=lambda item: item.get("lastContactEpoch") or 0, reverse=True)
    aircraft = aircraft[:160]
    _update_tracks(aircraft)
    _attach_tracks(aircraft)

    payload = {
        "source": source,
        "postprocess": "traffic-compatible track cache",
        "region": region_key,
        "bounds": {
            "lamin": bounds.lamin,
            "lomin": bounds.lomin,
            "lamax": bounds.lamax,
            "lomax": bounds.lomax,
        },
        "timestamp": _current_iso(),
        "count": len(aircraft),
        "aircraft": aircraft,
        "warnings": warnings,
    }
    _cache["payload"] = payload
    _cache["expires_at"] = now + CACHE_TTL_SECONDS
    return dict(payload)
