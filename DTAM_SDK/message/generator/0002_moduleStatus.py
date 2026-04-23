"""Module Status (MSG 0002) ?쒕뜡 ?앹꽦湲?"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dtam_client.schema.msg_0002 import validate_message

MODULE_NAMES = [
    "FlightDynamics", "TrafficManager", "WeatherEngine",
    "SensorFusion", "PathPlanner", "CommRelay",
]


def _now_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def generate(
    source: Optional[str] = None,
    status: Optional[int] = None,
    validate: bool = True,
    **_ignored: Any,
) -> Dict[str, Any]:
    msg: Dict[str, Any] = {
        "timestamp": _now_iso(),
        "source": source or random.choice(MODULE_NAMES),
        "status": status if status is not None else 1,
    }

    if validate:
        ok, errs, _ = validate_message(msg)
        if not ok:
            raise RuntimeError("0002 generator self-check ?ㅽ뙣: " + "; ".join(errs))
    return msg


if __name__ == "__main__":
    import json
    print(json.dumps(generate(), ensure_ascii=False, indent=2))

