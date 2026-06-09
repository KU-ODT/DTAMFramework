"""CSV-backed operational environment data used by the simulation workspace."""

from __future__ import annotations

import csv
import io
import shutil
from pathlib import Path
from typing import Any

from app.core.settings import settings


FRAMEWORK_ROOT = settings.project_root.parent
ENV_DIR = FRAMEWORK_ROOT / "DB" / "operational_environment"
DEFAULT_DIR = ENV_DIR / "default"
ACTIVE_DIR = ENV_DIR / "active"
REFERENCE_DEFAULT_DIR = FRAMEWORK_ROOT / "reference" / "uatm_sample" / "data" / "default"

VERTIPORT_FILE = "vertiport_default.csv"
CORRIDOR_FILE = "corridor_default.csv"
BASESTATION_FILE = "basestation_default.csv"

VERTIPORT_HEADER = [
    "Vertiport name",
    "Class",
    "Latitude",
    "Longitude",
    "INR(km)",
    "OTR(km)",
    "MTR(km)",
    "INR_Deg",
    "OTR_Deg",
    "Circle Turn",
    "Link",
]
CORRIDOR_HEADER = [
    "Waypoint name",
    "Latitude",
    "Longitude",
    "Altitude(ft)",
    "Link",
    "spare_link",
]
BASESTATION_HEADER = ["name", "lat", "lon"]


class OperationalEnvironmentError(ValueError):
    """Raised when a requested environment update cannot be applied."""


def ensure_operational_environment_files() -> None:
    """Create the DB folder and active CSV files from the default dataset."""

    DEFAULT_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVE_DIR.mkdir(parents=True, exist_ok=True)
    for file_name in (VERTIPORT_FILE, CORRIDOR_FILE, BASESTATION_FILE):
        default_path = DEFAULT_DIR / file_name
        reference_path = REFERENCE_DEFAULT_DIR / file_name
        if not default_path.exists() and reference_path.exists():
            shutil.copy2(reference_path, default_path)
        active_path = ACTIVE_DIR / file_name
        if not active_path.exists() and default_path.exists():
            shutil.copy2(default_path, active_path)


def reset_operational_environment_files() -> None:
    """Replace active CSV files with DB defaults."""

    ensure_operational_environment_files()
    for file_name in (VERTIPORT_FILE, CORRIDOR_FILE, BASESTATION_FILE):
        source = DEFAULT_DIR / file_name
        target = ACTIVE_DIR / file_name
        if source.exists():
            shutil.copy2(source, target)


def _detect_encoding(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    for encoding in ("utf-8", "cp949", "euc-kr"):
        try:
            raw.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "utf-8"


def _read_csv_table(path: Path, fallback_header: list[str], min_columns: int) -> tuple[list[str], list[list[str]]]:
    ensure_operational_environment_files()
    if not path.exists():
        return fallback_header[:], []
    raw = path.read_bytes()
    if not raw:
        return fallback_header[:], []
    encoding = _detect_encoding(raw)
    text = raw.decode(encoding, errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return fallback_header[:], []
    header = rows[0] or fallback_header[:]
    data_rows: list[list[str]] = []
    for row in rows[1:]:
        if not row or not any(str(cell).strip() for cell in row):
            continue
        padded = [str(cell).strip() for cell in row]
        if len(padded) < min_columns:
            padded.extend([""] * (min_columns - len(padded)))
        if len(padded) > min_columns:
            padded = padded[: min_columns - 1] + [", ".join(cell for cell in padded[min_columns - 1 :] if cell)]
        data_rows.append(padded)
    return header, data_rows


def _write_csv_table(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def _parse_float(value: Any, default: float | None = None) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed


def _fmt_number(value: Any, decimals: int = 6) -> str:
    parsed = _parse_float(value)
    if parsed is None:
        return ""
    if abs(parsed) < 1e-9:
        return "0"
    text = f"{parsed:.{decimals}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def _split_links(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    normalized = text.replace(";", ",")
    return [part.strip() for part in normalized.split(",") if part.strip()]


def _join_links(values: list[str]) -> str:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return ", ".join(cleaned)


def _find_row(rows: list[list[str]], name: str) -> int:
    target = str(name or "").strip()
    if not target:
        return -1
    for index, row in enumerate(rows):
        if row and row[0].strip() == target:
            return index
    return -1


def _require_name(value: Any, label: str) -> str:
    name = str(value or "").strip()
    if not name:
        raise OperationalEnvironmentError(f"{label} name is required.")
    return name


def _vertiport_defaults(class_name: str) -> dict[str, Any]:
    if class_name == "hub":
        return {
            "inr_km": 1.4,
            "otr_km": 2.7,
            "mtr_km": 3.7,
            "inr_deg": 45,
            "otr_deg": 255,
            "circle_turn": "Left",
        }
    return {
        "inr_km": 1.4,
        "otr_km": 0,
        "mtr_km": 2.7,
        "inr_deg": 165,
        "otr_deg": 0,
        "circle_turn": "Left",
    }


def _read_vertiport_table() -> tuple[list[str], list[list[str]]]:
    return _read_csv_table(ACTIVE_DIR / VERTIPORT_FILE, VERTIPORT_HEADER, 11)


def _write_vertiport_table(header: list[str], rows: list[list[str]]) -> None:
    _write_csv_table(ACTIVE_DIR / VERTIPORT_FILE, header or VERTIPORT_HEADER, rows)


def _read_corridor_table() -> tuple[list[str], list[list[str]]]:
    return _read_csv_table(ACTIVE_DIR / CORRIDOR_FILE, CORRIDOR_HEADER, 6)


def _write_corridor_table(header: list[str], rows: list[list[str]]) -> None:
    _write_csv_table(ACTIVE_DIR / CORRIDOR_FILE, header or CORRIDOR_HEADER, rows)


def _read_basestation_table() -> tuple[list[str], list[list[str]]]:
    return _read_csv_table(ACTIVE_DIR / BASESTATION_FILE, BASESTATION_HEADER, 3)


def _row_to_vertiport(row: list[str]) -> dict[str, Any]:
    links = _split_links(row[10] if len(row) > 10 else "")
    return {
        "name": row[0],
        "class": (row[1] or "port").lower(),
        "lat": _parse_float(row[2]),
        "lon": _parse_float(row[3]),
        "inr_km": _parse_float(row[4], 0),
        "otr_km": _parse_float(row[5], 0),
        "mtr_km": _parse_float(row[6], 0),
        "inr_deg": _parse_float(row[7], 0),
        "otr_deg": _parse_float(row[8], 0),
        "circle_turn": row[9] or "Left",
        "links": links,
    }


def _row_to_corridor(row: list[str]) -> dict[str, Any]:
    links = _split_links(row[4] if len(row) > 4 else "")
    spare_links = _split_links(row[5] if len(row) > 5 else "")
    return {
        "name": row[0],
        "lat": _parse_float(row[1]),
        "lon": _parse_float(row[2]),
        "altitude_ft": _parse_float(row[3], 1000),
        "links": links,
        "spare_links": spare_links,
    }


def _row_to_basestation(row: list[str]) -> dict[str, Any]:
    return {
        "name": row[0],
        "lat": _parse_float(row[1]),
        "lon": _parse_float(row[2]),
    }


def load_operational_environment() -> dict[str, Any]:
    ensure_operational_environment_files()
    _, vertiport_rows = _read_vertiport_table()
    _, corridor_rows = _read_corridor_table()
    _, basestation_rows = _read_basestation_table()
    vertiports = [
        entry
        for entry in (_row_to_vertiport(row) for row in vertiport_rows)
        if entry["name"] and entry["lat"] is not None and entry["lon"] is not None
    ]
    corridors = [
        entry
        for entry in (_row_to_corridor(row) for row in corridor_rows)
        if entry["name"] and entry["lat"] is not None and entry["lon"] is not None
    ]
    basestations = [
        entry
        for entry in (_row_to_basestation(row) for row in basestation_rows)
        if entry["name"] and entry["lat"] is not None and entry["lon"] is not None
    ]

    corridor_names = {entry["name"] for entry in corridors}
    links: list[dict[str, Any]] = []
    seen_corridor_links: set[tuple[str, str, bool]] = set()
    for corridor in corridors:
        for target in corridor["links"]:
            if target not in corridor_names:
                continue
            key = tuple(sorted((corridor["name"], target))) + (False,)
            if key in seen_corridor_links:
                continue
            seen_corridor_links.add(key)
            links.append({"kind": "corridor", "from": corridor["name"], "to": target, "spare": False})
        for target in corridor["spare_links"]:
            if target not in corridor_names:
                continue
            key = tuple(sorted((corridor["name"], target))) + (True,)
            if key in seen_corridor_links:
                continue
            seen_corridor_links.add(key)
            links.append({"kind": "corridor", "from": corridor["name"], "to": target, "spare": True})

    for vertiport in vertiports:
        for target in vertiport["links"]:
            if target in corridor_names:
                links.append({"kind": "vertiport", "from": vertiport["name"], "to": target, "spare": False})

    return {
        "files": {
            "default_dir": str(DEFAULT_DIR),
            "active_dir": str(ACTIVE_DIR),
            "vertiport": VERTIPORT_FILE,
            "corridor": CORRIDOR_FILE,
            "basestation": BASESTATION_FILE,
        },
        "vertiports": vertiports,
        "corridors": corridors,
        "basestations": basestations,
        "links": links,
    }


def update_vertiport(payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or "").strip().lower()
    header, rows = _read_vertiport_table()
    if action == "add":
        entry = payload.get("entry") if isinstance(payload.get("entry"), dict) else {}
        name = _require_name(entry.get("name"), "Vertiport")
        if _find_row(rows, name) >= 0:
            raise OperationalEnvironmentError("Vertiport name already exists.")
        class_name = str(entry.get("class") or "port").strip().lower()
        if class_name not in {"port", "hub"}:
            raise OperationalEnvironmentError("Vertiport class must be port or hub.")
        lat = _parse_float(entry.get("lat"))
        lon = _parse_float(entry.get("lon"))
        if lat is None or lon is None:
            raise OperationalEnvironmentError("Valid latitude and longitude are required.")
        defaults = _vertiport_defaults(class_name)
        row = [
            name,
            class_name,
            _fmt_number(lat),
            _fmt_number(lon),
            _fmt_number(entry.get("inr_km", defaults["inr_km"]), 1),
            _fmt_number(entry.get("otr_km", defaults["otr_km"]), 1),
            _fmt_number(entry.get("mtr_km", defaults["mtr_km"]), 1),
            _fmt_number(entry.get("inr_deg", defaults["inr_deg"]), 0),
            _fmt_number(entry.get("otr_deg", defaults["otr_deg"]), 0),
            str(entry.get("circle_turn") or defaults["circle_turn"]),
            _join_links(_split_links(entry.get("link") or entry.get("links") or "")),
        ]
        rows.append(row)
    elif action == "update":
        target = _require_name(payload.get("target"), "Vertiport")
        index = _find_row(rows, target)
        if index < 0:
            raise OperationalEnvironmentError("Vertiport not found.")
        updates = payload.get("updates") if isinstance(payload.get("updates"), dict) else {}
        row = rows[index]
        if "name" in updates:
            next_name = _require_name(updates.get("name"), "Vertiport")
            existing = _find_row(rows, next_name)
            if existing >= 0 and existing != index:
                raise OperationalEnvironmentError("Vertiport name already exists.")
            row[0] = next_name
        if "class" in updates:
            class_name = str(updates.get("class") or "").strip().lower()
            if class_name not in {"port", "hub"}:
                raise OperationalEnvironmentError("Vertiport class must be port or hub.")
            row[1] = class_name
        if "lat" in updates:
            lat = _parse_float(updates.get("lat"))
            if lat is None:
                raise OperationalEnvironmentError("Valid latitude is required.")
            row[2] = _fmt_number(lat)
        if "lon" in updates:
            lon = _parse_float(updates.get("lon"))
            if lon is None:
                raise OperationalEnvironmentError("Valid longitude is required.")
            row[3] = _fmt_number(lon)
        for field, column, decimals in (
            ("inr_km", 4, 1),
            ("otr_km", 5, 1),
            ("mtr_km", 6, 1),
            ("inr_deg", 7, 0),
            ("otr_deg", 8, 0),
        ):
            if field in updates:
                row[column] = _fmt_number(updates.get(field), decimals)
        if "circle_turn" in updates:
            row[9] = str(updates.get("circle_turn") or "Left")
        if "link" in updates or "links" in updates:
            row[10] = _join_links(_split_links(updates.get("link", updates.get("links"))))
        links = _split_links(row[10])
        if "link_append" in updates:
            links.extend(_split_links(updates.get("link_append")))
        if "link_remove" in updates:
            remove = set(_split_links(updates.get("link_remove")))
            links = [link for link in links if link not in remove]
        row[10] = _join_links(links)
    elif action == "delete":
        target = _require_name(payload.get("target"), "Vertiport")
        index = _find_row(rows, target)
        if index < 0:
            raise OperationalEnvironmentError("Vertiport not found.")
        del rows[index]
    else:
        raise OperationalEnvironmentError("Unsupported vertiport action.")
    _write_vertiport_table(header, rows)
    return load_operational_environment()


def update_corridor(payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or "").strip().lower()
    header, rows = _read_corridor_table()
    if action == "add":
        entry = payload.get("entry") if isinstance(payload.get("entry"), dict) else {}
        name = _require_name(entry.get("name"), "Route")
        if _find_row(rows, name) >= 0:
            raise OperationalEnvironmentError("Route node name already exists.")
        lat = _parse_float(entry.get("lat"))
        lon = _parse_float(entry.get("lon"))
        if lat is None or lon is None:
            raise OperationalEnvironmentError("Valid latitude and longitude are required.")
        row = [
            name,
            _fmt_number(lat),
            _fmt_number(lon),
            _fmt_number(entry.get("altitude_ft", 1000), 0),
            _join_links(_split_links(entry.get("link") or entry.get("links") or "")),
            _join_links(_split_links(entry.get("spare_link") or entry.get("spare_links") or "")),
        ]
        rows.append(row)
    elif action == "update":
        target = _require_name(payload.get("target"), "Route")
        index = _find_row(rows, target)
        if index < 0:
            raise OperationalEnvironmentError("Route node not found.")
        updates = payload.get("updates") if isinstance(payload.get("updates"), dict) else {}
        row = rows[index]
        old_name = row[0]
        if "name" in updates:
            next_name = _require_name(updates.get("name"), "Route")
            existing = _find_row(rows, next_name)
            if existing >= 0 and existing != index:
                raise OperationalEnvironmentError("Route node name already exists.")
            row[0] = next_name
            for corridor_row in rows:
                for column in (4, 5):
                    corridor_row[column] = _join_links(
                        [next_name if link == old_name else link for link in _split_links(corridor_row[column])]
                    )
            _replace_vertiport_references(old_name, next_name)
        if "lat" in updates:
            lat = _parse_float(updates.get("lat"))
            if lat is None:
                raise OperationalEnvironmentError("Valid latitude is required.")
            row[1] = _fmt_number(lat)
        if "lon" in updates:
            lon = _parse_float(updates.get("lon"))
            if lon is None:
                raise OperationalEnvironmentError("Valid longitude is required.")
            row[2] = _fmt_number(lon)
        if "altitude_ft" in updates:
            row[3] = _fmt_number(updates.get("altitude_ft"), 0)
        if "link" in updates or "links" in updates:
            row[4] = _join_links(_split_links(updates.get("link", updates.get("links"))))
        if "spare_link" in updates or "spare_links" in updates:
            row[5] = _join_links(_split_links(updates.get("spare_link", updates.get("spare_links"))))
        primary_links = _split_links(row[4])
        spare_links = _split_links(row[5])
        link_field = spare_links if bool(updates.get("spare")) else primary_links
        if "link_append" in updates:
            link_field.extend(_split_links(updates.get("link_append")))
        if "link_remove" in updates:
            remove = set(_split_links(updates.get("link_remove")))
            primary_links = [link for link in primary_links if link not in remove]
            spare_links = [link for link in spare_links if link not in remove]
        if bool(updates.get("spare")):
            spare_links = link_field
        else:
            primary_links = link_field
        row[4] = _join_links(primary_links)
        row[5] = _join_links(spare_links)
    elif action == "delete":
        target = _require_name(payload.get("target"), "Route")
        index = _find_row(rows, target)
        if index < 0:
            raise OperationalEnvironmentError("Route node not found.")
        del rows[index]
        for corridor_row in rows:
            for column in (4, 5):
                corridor_row[column] = _join_links([link for link in _split_links(corridor_row[column]) if link != target])
        _remove_vertiport_references(target)
    else:
        raise OperationalEnvironmentError("Unsupported route action.")
    _write_corridor_table(header, rows)
    return load_operational_environment()


def _replace_vertiport_references(old_name: str, next_name: str) -> None:
    vertiport_header, vertiport_rows = _read_vertiport_table()
    for row in vertiport_rows:
        row[10] = _join_links([next_name if link == old_name else link for link in _split_links(row[10])])
    _write_vertiport_table(vertiport_header, vertiport_rows)


def _remove_vertiport_references(name: str) -> None:
    vertiport_header, vertiport_rows = _read_vertiport_table()
    for row in vertiport_rows:
        row[10] = _join_links([link for link in _split_links(row[10]) if link != name])
    _write_vertiport_table(vertiport_header, vertiport_rows)
