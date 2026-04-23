"""MSG 4101 — Camera Image Frame (TCP, 바이너리 프레이밍)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from ..schema.msg_4101 import validate_header
from .._config import get_config
from .._result import PushResult
from .._transport import send_tcp


def push_camera_image(
    header: Dict[str, Any],
    image_bytes: bytes = b"",
    *,
    target_ip: Optional[str] = None,
    target_port: Optional[int] = None,
) -> PushResult:
    """카메라 이미지 프레임을 서버로 전송한다 (TCP, 바이너리 프레이밍).

    프레임 구조: [u32le header_len][header_json][image_bytes]

    Args:
        header:      MSG 4101 ICD에 맞는 헤더 dict.
                     payload_size 는 len(image_bytes)와 일치해야 함.
        image_bytes: 실제 이미지 바이너리. 없으면 b"" 전달 가능.
        target_ip:   전송 대상 IP (생략 시 configure() 값 사용).
        target_port: 전송 대상 Port (생략 시 configure() tcp_port 사용).
    """
    cfg = get_config()
    ip   = target_ip   or cfg.server_ip
    port = target_port or cfg.tcp_port
    result = PushResult(target=f"{ip}:{port}", payload=header)

    declared = header.get("payload_size", 0)
    actual   = len(image_bytes)
    if declared != actual:
        result.errors.append(
            f"payload_size 불일치: header={declared}, 실제 bytes={actual}"
        )
        return result

    ok, errors, _ = validate_header(header)
    if not ok:
        result.errors.extend(errors)
        return result

    return send_tcp(ip, port, header, image_bytes)
