from __future__ import annotations

import csv
from functools import lru_cache

from ..config import VERTIPORT_CSV


def _split_links(value: str | None) -> list[str]:
    if not value:
        return []
    return [token.strip() for token in str(value).split(",") if token and token.strip()]


def _parse_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


@lru_cache(maxsize=1)
def load_vertiports() -> list[dict]:
    items: list[dict] = []
    with VERTIPORT_CSV.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            name = (row.get("Vertiport 명") or "").strip()
            if not name:
                continue
            try:
                lat = float(row["위도"])
                lon = float(row["경도"])
            except (KeyError, TypeError, ValueError):
                continue

            items.append(
                {
                    "id": name,
                    "name": name,
                    "class": (row.get("Class") or "").strip() or "port",
                    "lat": lat,
                    "lon": lon,
                    "inrKm": _parse_float(row.get("INR(km)")),
                    "otrKm": _parse_float(row.get("OTR(km)")),
                    "mtrKm": _parse_float(row.get("MTR(km)")),
                    "inrDeg": _parse_float(row.get("INR_Deg")),
                    "otrDeg": _parse_float(row.get("OTR_Deg")),
                    "turnDir": (row.get("Circle Turn") or "").strip(),
                    "links": _split_links(row.get("Link")),
                }
            )
    return items
