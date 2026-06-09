"""Route received DTAM message dictionaries to their receiver parser."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_RECV_ROOT = Path(__file__).resolve().parent / "receiver"
_cache: Dict[str, Any] = {}


def _load(tag: str):
    """Load receiver modules whose filenames start with message IDs."""
    if tag in _cache:
        return _cache[tag]
    path = _RECV_ROOT / f"{tag}.py"
    unique = f"_dtam_recv_{tag}"
    spec = importlib.util.spec_from_file_location(unique, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[unique] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    _cache[tag] = mod
    return mod


_ROUTES: List[Tuple[str, str, Optional[str]]] = [
    ("4101", "4101_cameraImageFrame", "message_id"),
    ("2002", "2002_dtamExecute", "flightPlanFolderName"),
    ("3001", "3001_scheduledFlight", "enRoute"),
    ("3002", "3002_scheduledFlightModification", "modificationType"),
    ("3003", "3003_tacticalActionCommand", "actions"),
    ("0001", "0001_moduleSettingInfo", "ModuleName"),
    ("0002", "0002_moduleStatus", "source"),
    ("0003", "0003_commonTimeInfo", "simTime"),
    ("1001", "1001_simModeSetup", "operationMode"),
    ("1002", "1002_simulationSetup", "playbackSpeed"),
    ("1003", "1003_scenarioSetup", "totalAircraftCount"),
    ("2001", "2001_flightPlanRequest", "scenarioFileName"),
    ("4001", "4001_vehicleStatus", None),
]


def route(obj: Dict[str, Any]) -> Optional[Tuple[str, Any]]:
    """Return ``(message_id, ReceiveResult)`` for a received payload."""
    tried: set[str] = set()

    for mid, tag, hint in _ROUTES:
        if hint and hint in obj:
            tried.add(tag)
            try:
                result = _load(tag).parse(obj)
                if result.ok:
                    return mid, result
            except Exception:
                pass

    for mid, tag, _hint in _ROUTES:
        if tag in tried:
            continue
        try:
            result = _load(tag).parse(obj)
            if result.ok:
                return mid, result
        except Exception:
            pass

    return None
