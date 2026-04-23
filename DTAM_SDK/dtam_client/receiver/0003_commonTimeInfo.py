"""Common Time Info (MSG 0003) 수신/파싱기."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from dtam_client.schema.msg_0003 import validate_message


@dataclass
class ReceiveResult:
    ok: bool = False
    timestamp: Optional[str] = None
    sim_time: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "timestamp": self.timestamp,
            "simTime": self.sim_time,
            "errors": self.errors,
        }


def _coerce_dict(data: Union[bytes, str, Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if isinstance(data, dict):
        return data, None
    try:
        if isinstance(data, (bytes, bytearray)):
            data = data.decode("utf-8")
        if isinstance(data, str):
            return json.loads(data), None
        return None, f"지원하지 않는 입력 타입: {type(data).__name__}"
    except UnicodeDecodeError as e:
        return None, f"UTF-8 디코드 실패: {e}"
    except json.JSONDecodeError as e:
        return None, f"JSON 파싱 실패: {e}"


def parse(data: Union[bytes, str, Dict[str, Any]]) -> ReceiveResult:
    result = ReceiveResult()
    try:
        obj, err = _coerce_dict(data)
        if err:
            result.errors.append(err)
            return result
        result.raw = obj
        ok, errors, _ = validate_message(obj)
        result.ok = ok
        result.errors.extend(errors)
        if not ok:
            return result
        result.timestamp = obj.get("timestamp")
        result.sim_time = obj.get("simTime")
        return result
    except Exception as e:
        result.ok = False
        result.errors.append(f"내부 예외: {type(e).__name__}: {e}")
        return result


def extract(data: Union[bytes, str, Dict[str, Any]]) -> Dict[str, Any]:
    return parse(data).to_dict()
