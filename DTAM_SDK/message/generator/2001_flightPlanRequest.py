"""Flight Plan Request (MSG 2001) ?쒕뜡 ?앹꽦湲?"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dtam_client.schema.msg_2001 import validate_message


def _now_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def generate(
    scenario_file_name: Optional[str] = None,
    validate: bool = True,
    **_ignored: Any,
) -> Dict[str, Any]:
    ts = _now_iso()
    if not scenario_file_name:
        file_ts = ts.replace("-", "").replace(":", "").replace(".", "")
        scenario_file_name = f"scenarioSetup_{file_ts}.json"

    msg: Dict[str, Any] = {
        "timestamp": ts,
        "scenarioFileName": scenario_file_name,
    }

    if validate:
        ok, errs, _ = validate_message(msg)
        if not ok:
            raise RuntimeError("2001 generator self-check ?ㅽ뙣: " + "; ".join(errs))
    return msg


if __name__ == "__main__":
    import json
    print(json.dumps(generate(), ensure_ascii=False, indent=2))

