"""Simulation Setup (MSG 1002) 수신/파싱기."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from dtam_client.schema.msg_1002 import validate_message


@dataclass
class ReceiveResult:
    ok: bool = False
    timestamp: Optional[str] = None
    playback_speed: Optional[int] = None
    play_state: Optional[str] = None
    precipitation: Dict[str, Any] = field(default_factory=dict)
    fog: Dict[str, Any] = field(default_factory=dict)
    wind_grade: Optional[str] = None
    gust: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "ok": self.ok,
            "timestamp": self.timestamp,
            "playbackSpeed": self.playback_speed,
            "playState": self.play_state,
            "precipitation": self.precipitation,
            "fog": self.fog,
            "windGrade": self.wind_grade,
            "errors": self.errors,
        }
        if self.gust is not None:
            d["gust"] = self.gust
        return d


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
        result.playback_speed = obj.get("playbackSpeed")
        result.play_state = obj.get("playState")
        we = obj.get("weatherEffect", {})
        result.precipitation = dict(we.get("precipitation", {}))
        result.fog = dict(we.get("fog", {}))
        wind = obj.get("wind", {})
        result.wind_grade = wind.get("grade")
        if isinstance(wind.get("gust"), dict):
            result.gust = dict(wind["gust"])
        return result
    except Exception as e:
        result.ok = False
        result.errors.append(f"내부 예외: {type(e).__name__}: {e}")
        return result


def extract(data: Union[bytes, str, Dict[str, Any]]) -> Dict[str, Any]:
    return parse(data).to_dict()
