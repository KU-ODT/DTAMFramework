"""MSG 0002 — Module Status (UDP, 1 Hz 주기)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from ..schema.msg_0002 import validate_message
from .._config import get_config
from .._result import PushResult
from .._transport import send_udp


def push_module_status(
    data: Dict[str, Any],
    *,
    target_ip: Optional[str] = None,
    target_port: Optional[int] = None,
) -> PushResult:
    """모듈 상태를 서버로 전송한다 (UDP).

    Args:
        data:        MSG 0002 ICD에 맞는 dict.
        target_ip:   전송 대상 IP (생략 시 configure()로 설정한 값 사용).
        target_port: 전송 대상 Port (생략 시 configure()로 설정한 udp_port 사용).

    Example::

        from dtam_client import configure, push_module_status

        configure("192.168.1.100")
        push_module_status({
            "timestamp": "2026-04-16T10:00:00.000Z",
            "source": "VehicleDynamics",
            "status": 1,
        })
    """
    cfg = get_config()
    ip   = target_ip   or cfg.server_ip
    port = target_port or cfg.udp_port
    result = PushResult(target=f"{ip}:{port}", payload=data)

    ok, errors, _ = validate_message(data)
    if not ok:
        result.errors.extend(errors)
        return result

    return send_udp(ip, port, data)
