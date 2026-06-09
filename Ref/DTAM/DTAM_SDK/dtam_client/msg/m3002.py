"""MSG 3002 — Strategic Separation Command (TCP)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from ..schema.msg_3002 import validate_message
from .._config import get_config
from .._result import PushResult
from .._transport import send_tcp


def push_strategic_separation(
    data: Dict[str, Any],
    *,
    target_ip: Optional[str] = None,
    target_port: Optional[int] = None,
) -> PushResult:
    """전략 분리 명령을 서버로 전송한다 (TCP)."""
    cfg = get_config()
    ip   = target_ip   or cfg.server_ip
    port = target_port or cfg.tcp_port
    result = PushResult(target=f"{ip}:{port}", payload=data)

    ok, errors, _ = validate_message(data)
    if not ok:
        result.errors.extend(errors)
        return result

    return send_tcp(ip, port, data)
