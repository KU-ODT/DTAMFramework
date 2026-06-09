"""Network configuration helpers for the DTAM SDK.

The user-facing rule is intentionally small:

* ``port`` is the UDP port.
* TCP uses ``port + 1`` unless ``tcp_port`` is explicitly provided.
* ``my`` is where this module receives data.
* ``peer`` is where this module sends data.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


DEFAULT_BASE_PORT = 17000
DEFAULT_UDP_PORT = DEFAULT_BASE_PORT
DEFAULT_TCP_PORT = DEFAULT_BASE_PORT + 1


@dataclass
class DtamConfig:
    server_ip: str = "127.0.0.1"
    udp_port: int = DEFAULT_UDP_PORT
    tcp_port: int = DEFAULT_TCP_PORT

    @property
    def base_port(self) -> int:
        return self.udp_port


@dataclass(frozen=True)
class Endpoint:
    """One DTAM network endpoint.

    ``port`` means UDP. TCP is automatically ``port + 1`` unless ``tcp_port``
    is set for an unusual integration environment.
    """

    ip: str = "127.0.0.1"
    port: int = DEFAULT_BASE_PORT
    tcp_port: int | None = None
    name: str = ""

    @property
    def udp_port(self) -> int:
        return int(self.port)

    @property
    def resolved_tcp_port(self) -> int:
        return int(self.tcp_port) if self.tcp_port is not None else self.udp_port + 1

    @property
    def base_port(self) -> int:
        return self.udp_port

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"ip": self.ip, "port": self.udp_port}
        if self.name:
            data["name"] = self.name
        if self.tcp_port is not None:
            data["tcp_port"] = self.resolved_tcp_port
        return data


@dataclass(frozen=True)
class DtamNetworkConfig:
    """Simple SDK config loaded from ``dtam_config.json``."""

    my: Endpoint
    peer: Endpoint

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DtamNetworkConfig":
        my_raw = _as_mapping(data.get("my") or data.get("module") or {})
        peer_raw = _as_mapping(data.get("peer") or data.get("target") or {})
        return cls(
            my=_endpoint_from_mapping(
                my_raw,
                default_ip="0.0.0.0",
                default_port=DEFAULT_BASE_PORT,
                default_name="my_module",
            ),
            peer=_endpoint_from_mapping(
                peer_raw,
                default_ip="127.0.0.1",
                default_port=DEFAULT_BASE_PORT,
                default_name="peer_module",
            ),
        )

    @classmethod
    def from_file(cls, path: str | Path = "dtam_config.json") -> "DtamNetworkConfig":
        return load_network_config(path)

    def to_dict(self) -> dict[str, Any]:
        return {"my": self.my.to_dict(), "peer": self.peer.to_dict()}


_CONFIG = DtamConfig()


def configure(
    server_ip: str = "127.0.0.1",
    udp_port: int = DEFAULT_UDP_PORT,
    tcp_port: int | None = None,
    *,
    base_port: int | None = None,
) -> None:
    """Set the default remote endpoint for module-level push functions.

    Args:
        server_ip: Remote module IP address.
        udp_port: UDP receive port. Usually omit this.
        tcp_port: TCP receive port. Defaults to ``udp_port + 1``.
        base_port: Convenience alias for ``udp_port``.
    """
    if base_port is not None:
        udp_port = base_port
    if tcp_port is None:
        tcp_port = int(udp_port) + 1

    _CONFIG.server_ip = server_ip
    _CONFIG.udp_port = int(udp_port)
    _CONFIG.tcp_port = int(tcp_port)


def get_config() -> DtamConfig:
    return _CONFIG


def load_network_config(path: str | Path = "dtam_config.json") -> DtamNetworkConfig:
    """Load the short SDK JSON config file.

    Expected shape:

    .. code-block:: json

        {
          "my": {"ip": "0.0.0.0", "port": 17000},
          "peer": {"ip": "192.168.0.43", "port": 17000}
        }
    """
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as fp:
        raw = json.load(fp)
    if not isinstance(raw, Mapping):
        raise ValueError(f"{config_path} must contain a JSON object")
    return DtamNetworkConfig.from_dict(raw)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _endpoint_from_mapping(
    data: Mapping[str, Any],
    *,
    default_ip: str,
    default_port: int,
    default_name: str,
) -> Endpoint:
    ip = str(data.get("ip") or data.get("bind_ip") or data.get("host") or default_ip)
    name = str(data.get("name") or default_name)
    port_raw = (
        data.get("port")
        if data.get("port") is not None
        else data.get("base_port")
        if data.get("base_port") is not None
        else data.get("udp_port")
        if data.get("udp_port") is not None
        else default_port
    )
    tcp_raw = data.get("tcp_port")
    return Endpoint(
        ip=ip,
        port=int(port_raw),
        tcp_port=int(tcp_raw) if tcp_raw is not None else None,
        name=name,
    )
