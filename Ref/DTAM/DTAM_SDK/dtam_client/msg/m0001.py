"""MSG 0001 - Module Setting Info (UDP)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from .._config import get_config
from .._result import PushResult
from .._transport import send_udp
from ..schema.msg_0001 import validate_message


def push_module_setting_info(
    data: Dict[str, Any],
    *,
    target_ip: Optional[str] = None,
    target_port: Optional[int] = None,
) -> PushResult:
    """Send module receive endpoint information to the DTAM server."""
    cfg = get_config()
    ip = target_ip or cfg.server_ip
    port = target_port or cfg.udp_port
    result = PushResult(target=f"{ip}:{port}", payload=data)

    ok, errors, normalized = validate_message(data)
    if not ok:
        result.errors.extend(errors)
        return result

    return send_udp(ip, port, normalized)
