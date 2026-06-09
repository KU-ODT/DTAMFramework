"""Common Time Info (MSG 0003) ?쒕뜡 ?앹꽦湲?"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from dtam_client.schema.msg_0003 import validate_message


def _now_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _dt_iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def generate(
    sim_time: Optional[str] = None,
    validate: bool = True,
    **_ignored: Any,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    if sim_time is None:
        # ?쒕??덉씠???쒓컙? ?ㅼ젣 ?쒓컙怨??ㅻ? ???덉쓬 (?? ?쒕굹由ъ삤 ?쒖옉 ?쒓컖 湲곗?)
        sim_dt = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(seconds=int(now.timestamp()) % 3600)
        sim_time = sim_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    msg: Dict[str, Any] = {
        "timestamp": _now_iso(),
        "simTime": sim_time,
    }

    if validate:
        ok, errs, _ = validate_message(msg)
        if not ok:
            raise RuntimeError("0003 generator self-check ?ㅽ뙣: " + "; ".join(errs))
    return msg


if __name__ == "__main__":
    import json
    print(json.dumps(generate(), ensure_ascii=False, indent=2))

