"""DTAM Execute (MSG 2002) ?쒕뜡 ?앹꽦湲?"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dtam_client.schema.msg_2002 import validate_message


def _now_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def generate(
    sim_mode_file_name: Optional[str] = None,
    simulation_setup_file_name: Optional[str] = None,
    scenario_file_name: Optional[str] = None,
    flight_plan_folder_name: Optional[str] = None,
    validate: bool = True,
    **_ignored: Any,
) -> Dict[str, Any]:
    ts = _now_iso()
    file_ts = ts.replace("-", "").replace(":", "").replace(".", "")

    msg: Dict[str, Any] = {
        "timestamp": ts,
        "simModeFileName": sim_mode_file_name or f"simModeSetup_{file_ts}.json",
        "simulationSetupFileName": simulation_setup_file_name or f"simulationSetup_{file_ts}.json",
        "scenarioFileName": scenario_file_name or f"scenarioSetup_{file_ts}.json",
        "flightPlanFolderName": flight_plan_folder_name or f"FlightPlan_{file_ts}",
    }

    if validate:
        ok, errs, _ = validate_message(msg)
        if not ok:
            raise RuntimeError("2002 generator self-check ?ㅽ뙣: " + "; ".join(errs))
    return msg


if __name__ == "__main__":
    import json
    print(json.dumps(generate(), ensure_ascii=False, indent=2))

