"""Internal UDP/TCP transport helpers.

Module developers should not call this module directly. Use ``DtamClient`` or
the public ``push_*`` functions instead.
"""
from __future__ import annotations

import errno
import json
import socket
import struct
from typing import Any, Dict

from ._result import PushResult


DEFAULT_TCP_TIMEOUT = 1.0


def _serialize(data: Dict[str, Any]) -> tuple[bytes, PushResult | None]:
    try:
        return json.dumps(data, ensure_ascii=False).encode("utf-8"), None
    except Exception as exc:
        result = PushResult()
        result.errors.append(f"JSON serialization failed: {exc}")
        return b"", result


def _format_send_error(protocol: str, ip: str, port: int, exc: OSError) -> str:
    target = f"{ip}:{port}"
    code = getattr(exc, "errno", None)
    winerror = getattr(exc, "winerror", None)

    if isinstance(exc, ConnectionRefusedError) or code in (errno.ECONNREFUSED,) or winerror == 10061:
        return (
            f"{protocol} send failed ({target}): receiver is not listening. "
            "Check that the remote module called listen()/auto_listen and that the base_port matches."
        )
    if isinstance(exc, TimeoutError) or code in (errno.ETIMEDOUT,) or winerror == 10060:
        return (
            f"{protocol} send failed ({target}): connection timed out. "
            "Check IP address, network route, firewall, and base_port."
        )
    if code in (errno.EHOSTUNREACH, errno.ENETUNREACH) or winerror in (10051, 10065):
        return (
            f"{protocol} send failed ({target}): network or host is unreachable. "
            "Check the target IP address."
        )
    return f"{protocol} send failed ({target}): {exc}"


def send_udp(ip: str, port: int, data: Dict[str, Any]) -> PushResult:
    """Serialize a dict as JSON and send it over UDP."""
    port = int(port)
    result = PushResult(target=f"{ip}:{port}", payload=data)
    raw, err = _serialize(data)
    if err:
        result.errors.extend(err.errors)
        return result
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(raw, (ip, port))
        result.bytes_sent = len(raw)
        result.ok = True
    except OSError as exc:
        result.errors.append(_format_send_error("UDP", ip, port, exc))
    return result


def send_tcp(
    ip: str,
    port: int,
    data: Dict[str, Any],
    payload_bytes: bytes = b"",
    timeout: float = DEFAULT_TCP_TIMEOUT,
) -> PushResult:
    """Send a binary-framed TCP message.

    Frame format: ``[u32le header_len][header_json][payload_bytes]``.
    """
    port = int(port)
    result = PushResult(target=f"{ip}:{port}", payload=data)
    wire = {k: v for k, v in data.items() if not k.startswith("_")}
    header_json, err = _serialize(wire)
    if err:
        result.errors.extend(err.errors)
        return result
    frame = struct.pack("<I", len(header_json)) + header_json + payload_bytes
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(float(timeout))
            sock.connect((ip, port))
            sock.sendall(frame)
        result.bytes_sent = len(frame)
        result.ok = True
    except OSError as exc:
        result.errors.append(_format_send_error("TCP", ip, port, exc))
    return result
