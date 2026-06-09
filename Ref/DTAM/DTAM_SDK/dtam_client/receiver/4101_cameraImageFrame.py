"""Camera Image Frame (MSG 4101) 수신/파싱기.

바이너리 프레이밍과 JSON 헤더 파싱을 모두 지원.
dict 입력 시 헤더만 검증 (이미지 바이너리는 별도).
bytes 입력 시 [header_length][header_json][payload] 프레이밍 파싱.
"""
from __future__ import annotations

import base64
import json
import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from dtam_client.schema.msg_4101 import validate_header


@dataclass
class ReceiveResult:
    ok: bool = False
    timestamp: Optional[str] = None
    vehicle_id: Optional[str] = None
    camera_name: Optional[str] = None
    image_type: Optional[str] = None
    sequence: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    encoding: Optional[str] = None
    payload_size: Optional[int] = None
    image_bytes: Optional[bytes] = None
    errors: List[str] = field(default_factory=list)
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "ok": self.ok,
            "timestamp": self.timestamp,
            "vehicle_id": self.vehicle_id,
            "camera_name": self.camera_name,
            "image_type": self.image_type,
            "sequence": self.sequence,
            "width": self.width,
            "height": self.height,
            "encoding": self.encoding,
            "payload_size": self.payload_size,
            "errors": self.errors,
        }
        if self.image_bytes is not None:
            d["_image_base64"] = base64.b64encode(self.image_bytes).decode("ascii")
            if self.encoding in ("jpeg", "png"):
                d["_image_mime"] = f"image/{self.encoding}"
        return d


def _parse_binary_frame(data: bytes) -> Tuple[Optional[Dict[str, Any]], Optional[bytes], Optional[str]]:
    """바이너리 프레이밍 파싱."""
    if len(data) < 4:
        return None, None, "프레임 너무 짧음 (< 4 bytes)"
    header_len = struct.unpack("<I", data[:4])[0]
    if len(data) < 4 + header_len:
        return None, None, f"헤더 길이 부족 (need {4 + header_len}, got {len(data)})"
    try:
        header_json = data[4:4 + header_len].decode("utf-8")
        header = json.loads(header_json)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return None, None, f"헤더 파싱 실패: {e}"
    payload = data[4 + header_len:]
    return header, payload, None


def parse(data: Union[bytes, str, Dict[str, Any]]) -> ReceiveResult:
    result = ReceiveResult()
    try:
        image_bytes: Optional[bytes] = None

        if isinstance(data, dict):
            obj = data
            # dict 내 _image_base64 가 있으면 디코드
            if "_image_base64" in data:
                try:
                    image_bytes = base64.b64decode(data["_image_base64"])
                except Exception:
                    pass
        elif isinstance(data, (bytes, bytearray)):
            obj, image_bytes, err = _parse_binary_frame(bytes(data))
            if err:
                result.errors.append(err)
                return result
        elif isinstance(data, str):
            try:
                obj = json.loads(data)
            except json.JSONDecodeError as e:
                result.errors.append(f"JSON 파싱 실패: {e}")
                return result
        else:
            result.errors.append(f"지원하지 않는 입력 타입: {type(data).__name__}")
            return result

        result.raw = obj
        ok, errors, _ = validate_header(obj)
        result.ok = ok
        result.errors.extend(errors)
        if not ok:
            return result

        result.timestamp = obj.get("timestamp")
        result.vehicle_id = obj.get("vehicle_id")
        result.camera_name = obj.get("camera_name")
        result.image_type = obj.get("image_type")
        result.sequence = obj.get("sequence")
        result.width = obj.get("width")
        result.height = obj.get("height")
        result.encoding = obj.get("encoding")
        result.payload_size = obj.get("payload_size")
        result.image_bytes = image_bytes
        return result
    except Exception as e:
        result.ok = False
        result.errors.append(f"내부 예외: {type(e).__name__}: {e}")
        return result


def extract(data: Union[bytes, str, Dict[str, Any]]) -> Dict[str, Any]:
    return parse(data).to_dict()
