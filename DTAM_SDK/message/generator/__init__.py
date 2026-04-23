"""User-friendly access to payload generators.

Generator source files keep the ICD message ID in their filename, so they are
loaded by path and exposed here with normal Python names.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Dict


_ROOT = Path(__file__).resolve().parent

_TAGS: Dict[str, str] = {
    "module_setting_info": "0001_moduleSettingInfo",
    "module_status": "0002_moduleStatus",
    "common_time_info": "0003_commonTimeInfo",
    "sim_mode_setup": "1001_simModeSetup",
    "simulation_setup": "1002_simulationSetup",
    "scenario_setup": "1003_scenarioSetup",
    "flight_plan_request": "2001_flightPlanRequest",
    "dtam_execute": "2002_dtamExecute",
    "scheduled_flight": "3001_scheduledFlight",
    "strategic_separation": "3002_scheduledFlightModification",
    "tactical_separation": "3003_tacticalActionCommand",
    "vehicle_status": "4001_vehicleStatus",
    "camera_image_frame": "4101_cameraImageFrame",
}


def _load(tag: str) -> ModuleType:
    path = _ROOT / f"{tag}.py"
    if not path.is_file():
        raise FileNotFoundError(path)
    module_name = f"message.generator.{tag}"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_generator(name: str) -> ModuleType:
    key = name.strip().lower().replace("-", "_").replace(" ", "_")
    tag = _TAGS.get(key, name)
    return _load(tag)


module_setting_info = _load(_TAGS["module_setting_info"])
module_status = _load(_TAGS["module_status"])
common_time_info = _load(_TAGS["common_time_info"])
sim_mode_setup = _load(_TAGS["sim_mode_setup"])
simulation_setup = _load(_TAGS["simulation_setup"])
scenario_setup = _load(_TAGS["scenario_setup"])
flight_plan_request = _load(_TAGS["flight_plan_request"])
dtam_execute = _load(_TAGS["dtam_execute"])
scheduled_flight = _load(_TAGS["scheduled_flight"])
strategic_separation = _load(_TAGS["strategic_separation"])
tactical_separation = _load(_TAGS["tactical_separation"])
vehicle_status = _load(_TAGS["vehicle_status"])
camera_image_frame = _load(_TAGS["camera_image_frame"])


__all__ = [
    "load_generator",
    "module_setting_info",
    "module_status",
    "common_time_info",
    "sim_mode_setup",
    "simulation_setup",
    "scenario_setup",
    "flight_plan_request",
    "dtam_execute",
    "scheduled_flight",
    "strategic_separation",
    "tactical_separation",
    "vehicle_status",
    "camera_image_frame",
]
