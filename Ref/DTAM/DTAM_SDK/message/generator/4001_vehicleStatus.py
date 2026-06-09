"""User-side sample generator for Vehicle Status (MSG 4001)."""
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dtam_client.schema.msg_4001 import (
    Field,
    TOP_SCHEMA,
    VEHICLE_SCHEMA,
    validate_message,
)


def _rand_field(f: Field) -> Any:
    if f.ftype == "float":
        lo, hi = f.range if f.range else (0.0, 1.0)
        return round(random.uniform(lo, hi), 4)
    if f.ftype == "int":
        lo, hi = f.range if f.range else (0, 100)
        return random.randint(int(lo), int(hi))
    if f.ftype == "list[float]":
        n = f.length or 1
        lo, hi = f.item_range if f.item_range else (0.0, 1.0)
        return [round(random.uniform(lo, hi), 2) for _ in range(n)]
    if f.ftype == "list[int]":
        n = f.length or 1
        lo, hi = f.item_range if f.item_range else (0, 100)
        return [random.randint(int(lo), int(hi)) for _ in range(n)]
    if f.ftype == "str":
        if f.choices:
            return random.choice(f.choices)
        return ""
    if f.ftype == "iso_datetime":
        return _now_iso()
    return None


def _now_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _rand_quaternion() -> Dict[str, float]:
    """?뺢퇋?붾맂 ?쒕뜡 荑쇳꽣?덉뼵."""
    import math
    w, x, y, z = [random.gauss(0, 1) for _ in range(4)]
    norm = math.sqrt(w*w + x*x + y*y + z*z) or 1.0
    return {
        "w": round(w / norm, 4),
        "x": round(x / norm, 4),
        "y": round(y / norm, 4),
        "z": round(z / norm, 4),
    }


def _rand_vec3(lo: float, hi: float) -> Dict[str, float]:
    return {
        "x": round(random.uniform(lo, hi), 4),
        "y": round(random.uniform(lo, hi), 4),
        "z": round(random.uniform(lo, hi), 4),
    }


_VERTIPORTS = ["Yeouido", "Jamsil", "Gimpo", "Incheon", "Gangnam"]


def _rand_waypoint_id() -> str:
    fpn = random.randint(1000, 9999)
    if random.random() < 0.7:
        # en-route: flightPlanNumber-seq
        return f"{fpn}-{random.randint(1, 15)}"
    else:
        # vertiport: flightPlanNumber-Vertiport-Gate
        vp = random.choice(_VERTIPORTS)
        gate = f"G{random.randint(1, 9)}"
        return f"{fpn}-{vp}-{gate}"


def generate_vehicle() -> Dict[str, Any]:
    out: Dict[str, Any] = {"currentWaypointId": _rand_waypoint_id()}
    for group, fields in VEHICLE_SCHEMA.items():
        if group == "imu":
            out["imu"] = {
                "orientation": _rand_quaternion(),
                "angular_velocity": _rand_vec3(-100.0, 100.0),
                "linear_acceleration": _rand_vec3(-200.0, 200.0),
            }
        elif group == "gps":
            out["gps"] = {
                "is_valid": random.choice([True, False]),
                "fix_type": random.randint(0, 3),
                **{name: _rand_field(f) for name, f in fields.items()
                   if name not in ("is_valid", "fix_type")},
            }
        else:
            out[group] = {name: _rand_field(f) for name, f in fields.items()}
    return out


def generate(
    num_vehicles: int = 1,
    vehicle_id_prefix: str = "UAM",
    vehicle_ids: Optional[List[str]] = None,
    validate: bool = True,
    **_ignored: Any,
) -> Dict[str, Any]:
    """?쒕뜡 硫붿떆吏 ?앹꽦. ?덉쇅 ?놁씠 ?좏슚 ?곗씠??諛섑솚."""
    try:
        n = max(1, int(num_vehicles))
    except (TypeError, ValueError):
        n = 1

    if vehicle_ids:
        ids = [str(v).strip() for v in vehicle_ids if str(v).strip()]
    else:
        prefix = (vehicle_id_prefix or "UAM").strip().upper()[:8] or "UAM"
        ids = [f"{prefix}{i:04d}" for i in range(1, n + 1)]

    msg: Dict[str, Any] = {"timestamp": _rand_field(TOP_SCHEMA["timestamp"])}
    for vid in ids:
        msg[vid] = generate_vehicle()

    if validate:
        ok, errors, _ = validate_message(msg)
        if not ok:
            raise RuntimeError("generator self-check ?ㅽ뙣: " + "; ".join(errors))
    return msg


if __name__ == "__main__":
    import json
    print(json.dumps(generate(num_vehicles=2), ensure_ascii=False, indent=2))


