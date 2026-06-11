"""Live aircraft traffic API for the simulation workspace."""

from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Query

from app.services.commercial_traffic import get_commercial_traffic

logger = logging.getLogger(__name__)

router = APIRouter()

FRAMEWORK_ROOT = Path(__file__).resolve().parents[4]
FPL_FOLDERS_DIR = FRAMEWORK_ROOT / "PlugIn" / "FlightScheduler" / "FPL"


@router.get("/commercial")
async def commercial_traffic(region: str = Query(default="korea", pattern="^[a-zA-Z0-9_-]{1,32}$")):
    return get_commercial_traffic(region=region)


@router.get("/fpl-folders")
async def fpl_folders():
    """List FlightScheduler FPL output folders that contain an FPL_all.csv."""
    folders: list[dict] = []
    if FPL_FOLDERS_DIR.is_dir():
        for csv_path in FPL_FOLDERS_DIR.glob("*/FPL_all.csv"):
            try:
                stat = csv_path.stat()
                with csv_path.open(encoding="utf-8-sig", newline="") as fh:
                    reader = csv.reader(fh)
                    next(reader, None)  # header
                    flight_count = sum(
                        1 for row in reader if any(str(cell).strip() for cell in row)
                    )
            except OSError as exc:
                logger.warning("Skipping unreadable FPL folder %s: %s", csv_path.parent, exc)
                continue
            folders.append(
                {
                    "name": csv_path.parent.name,
                    "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    "flightCount": flight_count,
                }
            )
    folders.sort(key=lambda item: item["modified"], reverse=True)
    return {"ok": True, "folders": folders}
