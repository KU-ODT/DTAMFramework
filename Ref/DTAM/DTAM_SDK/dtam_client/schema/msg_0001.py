"""Module Setting Info (MSG 0001) schema."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from .common import Field, ISO_DATETIME_PATTERN, validate_field


IPV4_PATTERN = r"^(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)$"

TOP_FIELDS: Dict[str, Field] = {
    "Timestamp": Field("iso_datetime", "UTC", "보고 시각", "Report time", pattern=ISO_DATETIME_PATTERN),
    "ModuleName": Field("str", "", "모듈 이름", "Module name"),
    "IP": Field("str", "", "모듈이 보고한 컴퓨터 IP", "Module computer IP", pattern=IPV4_PATTERN),
    "UDPPort": Field("int", "", "모듈 수신 UDP 포트", "Module receive UDP port", range=(1, 65535)),
    "TCPPort": Field("int", "", "모듈 수신 TCP 포트", "Module receive TCP port", range=(1, 65535)),
}

ALIASES = {
    "timestamp": "Timestamp",
    "moduleName": "ModuleName",
    "module_name": "ModuleName",
    "ip": "IP",
    "udpPort": "UDPPort",
    "udp_port": "UDPPort",
    "tcpPort": "TCPPort",
    "tcp_port": "TCPPort",
}


def normalize_message(obj: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(obj)
    for src, dst in ALIASES.items():
        if src in normalized and dst not in normalized:
            normalized[dst] = normalized[src]
    return normalized


def validate_message(obj: Any) -> Tuple[bool, List[str], Dict[str, Any]]:
    errors: List[str] = []
    if not isinstance(obj, dict):
        return False, ["root: dict required"], {}

    normalized = normalize_message(obj)

    for name, fspec in TOP_FIELDS.items():
        if name not in normalized:
            errors.append(f"{name}: missing")
            continue
        validate_field(normalized[name], fspec, name, errors)

    module_name = normalized.get("ModuleName")
    if isinstance(module_name, str) and not module_name.strip():
        errors.append("ModuleName: empty string is not allowed")

    ip = normalized.get("IP")
    if isinstance(ip, str) and not re.match(IPV4_PATTERN, ip):
        errors.append("IP: invalid IPv4 address")

    return (len(errors) == 0), errors, normalized
