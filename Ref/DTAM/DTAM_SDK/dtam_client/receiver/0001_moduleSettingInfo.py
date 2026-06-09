"""Module Setting Info (MSG 0001) receiver/parser."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from dtam_client.schema.msg_0001 import validate_message


@dataclass
class ReceiveResult:
    ok: bool = False
    Timestamp: Optional[str] = None
    ModuleName: Optional[str] = None
    IP: Optional[str] = None
    UDPPort: Optional[int] = None
    TCPPort: Optional[int] = None
    errors: List[str] = field(default_factory=list)
    raw: Optional[Dict[str, Any]] = None

    @property
    def timestamp(self) -> Optional[str]:
        return self.Timestamp

    @property
    def module_name(self) -> Optional[str]:
        return self.ModuleName

    @property
    def ip(self) -> Optional[str]:
        return self.IP

    @property
    def udp_port(self) -> Optional[int]:
        return self.UDPPort

    @property
    def tcp_port(self) -> Optional[int]:
        return self.TCPPort

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "Timestamp": self.Timestamp,
            "ModuleName": self.ModuleName,
            "IP": self.IP,
            "UDPPort": self.UDPPort,
            "TCPPort": self.TCPPort,
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
        return None, f"unsupported input type: {type(data).__name__}"
    except UnicodeDecodeError as e:
        return None, f"UTF-8 decode failed: {e}"
    except json.JSONDecodeError as e:
        return None, f"JSON parse failed: {e}"


def parse(data: Union[bytes, str, Dict[str, Any]]) -> ReceiveResult:
    result = ReceiveResult()
    try:
        obj, err = _coerce_dict(data)
        if err:
            result.errors.append(err)
            return result
        result.raw = obj

        ok, errors, normalized = validate_message(obj)
        result.ok = ok
        result.errors.extend(errors)
        if not ok:
            return result

        result.Timestamp = normalized.get("Timestamp")
        result.ModuleName = normalized.get("ModuleName")
        result.IP = normalized.get("IP")
        result.UDPPort = normalized.get("UDPPort")
        result.TCPPort = normalized.get("TCPPort")
        return result
    except Exception as e:
        result.ok = False
        result.errors.append(f"internal exception: {type(e).__name__}: {e}")
        return result


def extract(data: Union[bytes, str, Dict[str, Any]]) -> Dict[str, Any]:
    return parse(data).to_dict()
