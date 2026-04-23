"""Sim Mode Setup (MSG 1001) ?쒕뜡 ?앹꽦湲?"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dtam_client.schema.msg_1001 import (
    CONTROLLER_TYPES,
    DYNAMICS_CHOICES,
    OPERATION_MODES,
    TRAFFIC_SCENARIOS,
    validate_message,
)


def _now_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _gen_single_flight(
    dynamics: Optional[str] = None,
    main_vehicle_controller: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "vehicleSimType": {
            "dynamics": dynamics or random.choice(DYNAMICS_CHOICES),
            "mainVehicleController": main_vehicle_controller or random.choice(CONTROLLER_TYPES),
        }
    }


def _gen_traffic(traffic_scenario: Optional[str] = None) -> Dict[str, Any]:
    return {
        "trafficScenario": traffic_scenario or random.choice(TRAFFIC_SCENARIOS),
    }


def generate(
    operation_mode: Optional[str] = None,
    dynamics: Optional[str] = None,
    main_vehicle_controller: Optional[str] = None,
    traffic_scenario: Optional[str] = None,
    validate: bool = True,
    **_ignored: Any,
) -> Dict[str, Any]:
    mode = operation_mode or random.choice(OPERATION_MODES)
    msg: Dict[str, Any] = {
        "timestamp": _now_iso(),
        "operationMode": mode,
    }
    if mode == "single":
        msg["singleFlight"] = _gen_single_flight(dynamics, main_vehicle_controller)
    elif mode == "traffic":
        msg["traffic"] = _gen_traffic(traffic_scenario)
    elif mode == "integrated":
        msg["singleFlight"] = _gen_single_flight(dynamics, main_vehicle_controller)
        msg["traffic"] = _gen_traffic(traffic_scenario)

    if validate:
        ok, errs, _ = validate_message(msg)
        if not ok:
            raise RuntimeError("1001 generator self-check ?ㅽ뙣: " + "; ".join(errs))
    return msg


if __name__ == "__main__":
    import json
    for m in ("single", "traffic", "integrated"):
        print(f"--- {m} ---")
        print(json.dumps(generate(operation_mode=m), ensure_ascii=False, indent=2))

