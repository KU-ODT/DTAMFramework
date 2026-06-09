"""Simulation Setup (MSG 1002) ?쒕뜡 ?앹꽦湲?"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dtam_client.schema.msg_1002 import (
    PLAY_STATES,
    PLAYBACK_SPEEDS,
    PRECIPITATION_TYPES,
    WIND_GRADES,
    validate_message,
)


def _now_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _rand_step01(lo: float = 0.0, hi: float = 1.0) -> float:
    """0.1 ?ㅽ뀦 ?쒕뜡 媛?"""
    steps = int(round((hi - lo) * 10))
    return round(lo + random.randint(0, steps) / 10.0, 1)


def generate(
    playback_speed: Optional[int] = None,
    play_state: Optional[str] = None,
    precipitation_type: Optional[str] = None,
    precipitation_intensity: Optional[float] = None,
    fog_intensity: Optional[float] = None,
    wind_grade: Optional[str] = None,
    include_gust: Optional[bool] = None,
    gust_lat: Optional[float] = None,
    gust_lon: Optional[float] = None,
    gust_radius: Optional[float] = None,
    validate: bool = True,
    **_ignored: Any,
) -> Dict[str, Any]:
    # 媛뺤닔
    ptype = precipitation_type or random.choice(PRECIPITATION_TYPES)
    if ptype == "none":
        pint = 0.0
    else:
        pint = precipitation_intensity if precipitation_intensity is not None else _rand_step01(0.1, 1.0)

    # ?덇컻
    fint = fog_intensity if fog_intensity is not None else _rand_step01(0.0, 1.0)

    # 諛붾엺
    wgrade = wind_grade or random.choice(WIND_GRADES)
    if include_gust is None:
        include_gust = random.random() < 0.5

    msg: Dict[str, Any] = {
        "timestamp": _now_iso(),
        "playbackSpeed": playback_speed if playback_speed in PLAYBACK_SPEEDS
                         else random.choice(PLAYBACK_SPEEDS),
        "playState": play_state or random.choice(PLAY_STATES),
        "weatherEffect": {
            "precipitation": {"type": ptype, "intensity": round(pint, 1)},
            "fog":           {"intensity": round(fint, 1)},
        },
        "wind": {"grade": wgrade},
    }

    if include_gust:
        msg["wind"]["gust"] = {
            "lat":    round(gust_lat    if gust_lat    is not None else random.uniform(37.4, 37.6), 4),
            "lon":    round(gust_lon    if gust_lon    is not None else random.uniform(126.9, 127.1), 4),
            "radius": round(gust_radius if gust_radius is not None else random.uniform(100.0, 3000.0), 1),
        }

    if validate:
        ok, errs, _ = validate_message(msg)
        if not ok:
            raise RuntimeError("1002 generator self-check ?ㅽ뙣: " + "; ".join(errs))
    return msg


if __name__ == "__main__":
    import json
    print(json.dumps(generate(include_gust=True), ensure_ascii=False, indent=2))

