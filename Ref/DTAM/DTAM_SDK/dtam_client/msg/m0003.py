"""MSG 0003 — Common Time Info (UDP, 1 Hz 주기)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from ..schema.msg_0003 import validate_message
from .._config import get_config
from .._result import PushResult
from .._transport import send_udp


def push_common_time_info(
    data: Dict[str, Any],
    *,
    target_ip: Optional[str] = None,
    target_port: Optional[int] = None,
) -> PushResult:
    """공통 시간 정보를 서버로 전송한다 (UDP)."""
    cfg = get_config()
    ip   = target_ip   or cfg.server_ip
    port = target_port or cfg.udp_port
    result = PushResult(target=f"{ip}:{port}", payload=data)

    ok, errors, _ = validate_message(data)
    if not ok:
        result.errors.extend(errors)
        return result

    return send_udp(ip, port, data)
