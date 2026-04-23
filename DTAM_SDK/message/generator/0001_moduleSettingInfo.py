"""Module Setting Info (MSG 0001) payload generator."""
from __future__ import annotations

import socket
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dtam_client.schema.msg_0001 import validate_message


def _now_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _detect_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def generate(
    ModuleName: Optional[str] = None,
    IP: Optional[str] = None,
    UDPPort: Optional[int] = None,
    TCPPort: Optional[int] = None,
    Timestamp: Optional[str] = None,
    module_name: Optional[str] = None,
    ip: Optional[str] = None,
    udp_port: Optional[int] = None,
    tcp_port: Optional[int] = None,
    validate: bool = True,
    **_ignored: Any,
) -> Dict[str, Any]:
    udp = UDPPort if UDPPort is not None else (udp_port if udp_port is not None else 17000)
    tcp = TCPPort if TCPPort is not None else (tcp_port if tcp_port is not None else int(udp) + 1)
    msg: Dict[str, Any] = {
        "Timestamp": Timestamp or _now_iso(),
        "ModuleName": ModuleName or module_name or "DTAMModule",
        "IP": IP or ip or _detect_ip(),
        "UDPPort": int(udp),
        "TCPPort": int(tcp),
    }

    if validate:
        ok, errs, _ = validate_message(msg)
        if not ok:
            raise RuntimeError("0001 generator self-check failed: " + "; ".join(errs))
    return msg


if __name__ == "__main__":
    import json

    print(json.dumps(generate(), ensure_ascii=False, indent=2))
