"""Message ID to generator / receiver / push function mapping.

The ``message`` package is intentionally user-side: it owns payload generators.
Protocol parsing, schema validation, and send functions live in ``dtam_client``.

File names start with digits, so modules are loaded by path.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .sdk_import import SDK_ROOT, ensure_sdk_path

ensure_sdk_path()
import dtam_client

ROOT = Path(__file__).resolve().parent.parent
MESSAGE_ROOT = SDK_ROOT / "message"
DTAM_CLIENT_ROOT = SDK_ROOT / "dtam_client"


def _load(mod_path: Path, unique_name: str):
    """Load a Python module from a path using a synthetic module name."""
    if not mod_path.is_file():
        raise FileNotFoundError(mod_path)
    spec = importlib.util.spec_from_file_location(unique_name, mod_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@dataclass
class MessageHandler:
    generator: Callable[..., Dict[str, Any]]
    receiver: Callable[..., Any]
    push_fn: Callable[..., Any]
    tag: str = ""
    name_en: str = ""


def _tag_to_name_en(tag: str) -> str:
    """Convert ``4001_vehicleStatus`` to ``Vehicle Status``."""
    import re

    part = tag.split("_", 1)[1] if "_" in tag else tag
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", part)
    return spaced[:1].upper() + spaced[1:] if spaced else ""


def _build(tag: str, push_fn: Callable[..., Any]) -> MessageHandler:
    gen_mod = _load(MESSAGE_ROOT / "generator" / f"{tag}.py", f"_msg_{tag}_generator")
    recv_mod = _load(DTAM_CLIENT_ROOT / "receiver" / f"{tag}.py", f"_dtam_{tag}_receiver")
    return MessageHandler(
        generator=gen_mod.generate,
        receiver=recv_mod.parse,
        push_fn=push_fn,
        tag=tag,
        name_en=_tag_to_name_en(tag),
    )


REGISTRY: Dict[str, MessageHandler] = {
    "0001": _build("0001_moduleSettingInfo", dtam_client.push_module_setting_info),
    "0002": _build("0002_moduleStatus", dtam_client.push_module_status),
    "0003": _build("0003_commonTimeInfo", dtam_client.push_common_time_info),
    "1001": _build("1001_simModeSetup", dtam_client.push_sim_mode_setup),
    "1002": _build("1002_simulationSetup", dtam_client.push_simulation_setup),
    "1003": _build("1003_scenarioSetup", dtam_client.push_scenario_setup),
    "2001": _build("2001_flightPlanRequest", dtam_client.push_flight_plan_request),
    "2002": _build("2002_dtamExecute", dtam_client.push_dtam_execute),
    "3001": _build("3001_scheduledFlight", dtam_client.push_scheduled_flight),
    "3002": _build("3002_scheduledFlightModification", dtam_client.push_strategic_separation),
    "3003": _build("3003_tacticalActionCommand", dtam_client.push_tactical_separation),
    "4001": _build("4001_vehicleStatus", dtam_client.push_vehicle_status),
    "4101": _build("4101_cameraImageFrame", dtam_client.push_camera_image),
}


def get(mid: str) -> Optional[MessageHandler]:
    return REGISTRY.get(mid)
