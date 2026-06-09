"""Scheduled Flight Modification Command (MSG 3002) ?쒕뜡 ?앹꽦湲?"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dtam_client.schema.msg_3002 import (
    MODIFICATION_TYPES,
    MODIFY_SCOPES,
    REASON_CODES,
    validate_message,
)


def _now_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"



def generate(
    command_id: Optional[str] = None,
    flight_plan_number: Optional[int] = None,
    plan_version: Optional[int] = None,
    aircraft_id: Optional[str] = None,
    modification_type: Optional[str] = None,
    reason_code: Optional[str] = None,
    modify_scope: Optional[str] = None,
    validate: bool = True,
    **_ignored: Any,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    date_tag = now.strftime("%Y%m%d")

    msg: Dict[str, Any] = {
        "timestamp": _now_iso(),
        "commandId": command_id or f"SMP-{date_tag}-{random.randint(1, 999):03d}",
        "flightPlanNumber": int(flight_plan_number) if flight_plan_number else random.randint(1000, 9999),
        "planVersion": int(plan_version) if plan_version else random.randint(2, 5),
        "aircraftId": aircraft_id or f"UAM{random.randint(1, 9999):04d}",
        "modificationType": modification_type or random.choice(MODIFICATION_TYPES),
        "reasonCode": reason_code or random.choice(REASON_CODES),
        "modifyScope": modify_scope or random.choice(MODIFY_SCOPES),
    }

    if validate:
        ok, errs, _ = validate_message(msg)
        if not ok:
            raise RuntimeError("3002 generator self-check ?ㅽ뙣: " + "; ".join(errs))
    return msg


if __name__ == "__main__":
    import json
    print(json.dumps(generate(), ensure_ascii=False, indent=2))

