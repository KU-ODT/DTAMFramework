"""Tactical Action Command (MSG 3003) ?쒕뜡 ?앹꽦湲?"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dtam_client.schema.msg_3003 import REASON_CODES, validate_message


def _now_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _rand_lla() -> Dict[str, float]:
    return {
        "lat": round(random.uniform(37.48, 37.56), 5),
        "lon": round(random.uniform(126.90, 127.05), 5),
        "alt": round(random.uniform(0.0, 500.0), 1),
    }


def _gen_set_speed() -> Dict[str, Any]:
    return {
        "type": "setSpeed",
        "targetSpeed": round(random.uniform(5.0, 80.0), 1),
    }


def _gen_direct_to(num_points: int = 0) -> Dict[str, Any]:
    n = num_points or random.randint(1, 3)
    return {
        "type": "directTo",
        "targetLLAs": [
            {**_rand_lla(), "targetSpeed": round(random.uniform(10.0, 60.0), 1)}
            for _ in range(n)
        ],
    }


def _gen_hold() -> Dict[str, Any]:
    return {
        "type": "hold",
        "holdLLA": _rand_lla(),
        "turnDirection": random.choice(["CW", "CCW"]),
        "holdingRadiusM": round(random.uniform(50.0, 500.0), 1),
        "maxHoldingCount": random.randint(0, 5),
    }


def _gen_rejoin_plan(seq: int = 0) -> Dict[str, Any]:
    return {
        "type": "rejoinPlan",
        "atSeq": seq or random.randint(3, 15),
    }


def _gen_land() -> Dict[str, Any]:
    vertiports = ["Yeouido", "Jamsil", "Gimpo", "Gangnam", "SeoulStation-Alt"]
    use_target = random.random() < 0.5
    use_vertiport = random.random() < 0.7
    if not use_target and not use_vertiport:
        use_vertiport = True

    action: Dict[str, Any] = {"type": "land"}
    if use_target:
        action["targetLLA"] = _rand_lla()
    if use_vertiport:
        action["vertiport"] = random.choice(vertiports)
        action["fatoNumber"] = f"F{random.randint(1, 4)}"
    return action


_SCENARIOS: List = [
    lambda: [_gen_set_speed(), _gen_hold(), _gen_rejoin_plan()],
    lambda: [_gen_set_speed(), _gen_direct_to(), _gen_rejoin_plan()],
    lambda: [_gen_direct_to(), _gen_land()],
    lambda: [_gen_set_speed(), _gen_direct_to(), _gen_land()],
    lambda: [_gen_hold(), _gen_rejoin_plan()],
]


def generate(
    command_id: Optional[str] = None,
    aircraft_id: Optional[str] = None,
    reason_code: Optional[str] = None,
    actions: Optional[List[Dict[str, Any]]] = None,
    validate: bool = True,
    **_ignored: Any,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    date_tag = now.strftime("%Y%m%d")

    msg: Dict[str, Any] = {
        "timestamp": _now_iso(),
        "commandId": command_id or f"TMP-{date_tag}-{random.randint(1, 999):03d}",
        "aircraftId": aircraft_id or f"UAM{random.randint(1, 9999):04d}",
        "reasonCode": reason_code or random.choice(REASON_CODES),
        "actions": actions or random.choice(_SCENARIOS)(),
    }

    if validate:
        ok, errs, _ = validate_message(msg)
        if not ok:
            raise RuntimeError("3003 generator self-check ?ㅽ뙣: " + "; ".join(errs))
    return msg


if __name__ == "__main__":
    import json
    print(json.dumps(generate(), ensure_ascii=False, indent=2))

