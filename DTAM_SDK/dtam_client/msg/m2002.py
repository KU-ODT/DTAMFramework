"""MSG 2002 — DTAM Execute (TCP)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from ..schema.msg_2002 import validate_message
from .._config import get_config
from .._result import PushResult
from .._transport import send_tcp


def push_dtam_execute(
    data: Dict[str, Any],
    *,
    target_ip: Optional[str] = None,
    target_port: Optional[int] = None,
) -> PushResult:
    """DTAM 실행 명령을 서버로 전송한다 (TCP)."""
    cfg = get_config()
    ip   = target_ip   or cfg.server_ip
    port = target_port or cfg.tcp_port
    result = PushResult(target=f"{ip}:{port}", payload=data)

    ok, errors, _ = validate_message(data)
    if not ok:
        result.errors.extend(errors)
        return result

    return send_tcp(ip, port, data)
