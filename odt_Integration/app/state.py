"""런타임 상태 + config.json 영속화.

구조:
  - self_rx : 이 프로그램의 수신 바인딩 (단일)
  - targets : 송신 대상 목록 (연결 확인 없이 그냥 보냄)
  - messages: 메시지 템플릿 목록
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional

from .messages import DEFAULT_MESSAGES

_env_cfg = os.environ.get("DTAM_CONFIG")
CONFIG_PATH = Path(_env_cfg) if _env_cfg else (Path(__file__).resolve().parent.parent / "config.json")

DEFAULT_RX_IP = "127.0.0.1"
DEFAULT_RX_PORT = 17000
DEFAULT_TX_IP = "127.0.0.1"
DEFAULT_TX_PORT = 17000


class SelfReceiver:
    """이 프로그램이 수신 대기하는 단일 소켓."""
    def __init__(self, bind_ip: str = DEFAULT_RX_IP, bind_port: int = DEFAULT_RX_PORT):
        self.bind_ip = bind_ip
        self.bind_port = int(bind_port)
        self.enabled = False
        self.rx_count = 0
        self.rx_last_ts = 0.0
        self.rx_last_payload: bytes = b""

    def to_config(self) -> Dict[str, Any]:
        return {"bind_ip": self.bind_ip, "bind_port": self.bind_port}

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.to_config(),
            "enabled": self.enabled,
            "rx_count": self.rx_count,
            "rx_last_ts": self.rx_last_ts,
            "rx_age": (time.time() - self.rx_last_ts) if self.rx_last_ts else None,
        }


class Target:
    """송신 대상. UDP와 TCP 포트를 분리 관리."""
    def __init__(self, name: str, ip: str = DEFAULT_TX_IP, port: int = DEFAULT_TX_PORT,
                 tcp_port: Optional[int] = None, protocol: str = "udp", **_ignored):
        self.name = name
        self.ip = ip
        self.port = int(port)                                          # UDP port
        self.tcp_port = int(tcp_port) if tcp_port is not None else self.port + 1  # TCP port
        self.protocol = protocol if protocol in ("udp", "tcp") else "udp"
        self.last_ping_ok: Optional[bool] = None
        self.last_ping_rtt_ms: Optional[float] = None
        self.last_ping_msg: str = ""
        self.tx_count = 0
        self.tx_last_ts = 0.0

    def to_config(self) -> Dict[str, Any]:
        return {"name": self.name, "ip": self.ip, "port": self.port,
                "tcp_port": self.tcp_port, "protocol": self.protocol}

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.to_config(),
            "tx_count": self.tx_count,
            "tx_last_ts": self.tx_last_ts,
            "ping": {
                "ok": self.last_ping_ok,
                "rtt_ms": self.last_ping_rtt_ms,
                "msg": self.last_ping_msg,
            },
            "udp_port": self.port,   # 프론트엔드 편의용 alias
        }


class Message:
    def __init__(
        self,
        id: str,
        name: str,
        name_en: str = "",
        payload: Optional[Dict[str, Any]] = None,
        target: Optional[str] = None,
        protocol: str = "udp",
        **_ignored,
    ):
        self.id = id
        self.name = name
        self.name_en = name_en
        self.payload: Dict[str, Any] = payload or {}
        self.target = target  # 명시 시 해당 이름의 Target 으로 송신, 없으면 첫 번째
        self.protocol = protocol if protocol in ("udp", "tcp") else "udp"
        self.tx_count = 0
        self.tx_last_ts = 0.0
        self.tx_last_bytes: bytes = b""
        self.tx_last_protocol: str = "udp"
        self.rx_count = 0
        self.rx_last_ts = 0.0
        self.rx_last_payload: Dict[str, Any] = {}

    def to_config(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "name_en": self.name_en,
            "payload": self.payload,
            "target": self.target,
            "protocol": self.protocol,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.to_config(),
            "tx_count": self.tx_count,
            "tx_last_ts": self.tx_last_ts,
            "rx_count": self.rx_count,
            "rx_last_ts": self.rx_last_ts,
            "rx_last_payload": self.rx_last_payload,
        }


class AppState:
    def __init__(self):
        self.lock = RLock()
        self.self_rx: SelfReceiver = SelfReceiver()
        self.targets: List[Target] = []
        self.messages: List[Message] = []
        self.load()

    # ----- persistence -----
    def load(self):
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                sr = data.get("self_rx") or {}
                self.self_rx = SelfReceiver(
                    bind_ip=sr.get("bind_ip", DEFAULT_RX_IP),
                    bind_port=sr.get("bind_port", DEFAULT_RX_PORT),
                )
                self.targets = [Target(**t) for t in data.get("targets", [])]
                self.messages = [Message(**m) for m in data.get("messages", [])]
                self._fill_missing_defaults()
                return
            except Exception as e:
                print(f"[state] config 로드 실패 - 기본값 사용: {e}")
        self.self_rx = SelfReceiver()
        self.targets = []
        self.messages = [Message(**m) for m in DEFAULT_MESSAGES]
        self._fill_missing_defaults()

    def save(self):
        data = {
            "self_rx": self.self_rx.to_config(),
            "targets": [t.to_config() for t in self.targets],
            "messages": [m.to_config() for m in self.messages],
        }
        CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _fill_missing_defaults(self):
        """DEFAULT_MESSAGES / registry 에서 name/name_en 동기화. 신규 항목 자동 추가."""
        from . import registry
        defaults = {m["id"]: m for m in DEFAULT_MESSAGES}
        existing_ids = {m.id for m in self.messages}
        for msg in self.messages:
            d = defaults.get(msg.id, {})
            if d:
                msg.name = d.get("name", msg.name)
            reg = registry.REGISTRY.get(msg.id)
            msg.name_en = (d.get("name_en") or (reg.name_en if reg else "") or msg.name_en)
            if d.get("protocol"):
                msg.protocol = d["protocol"]
        for d in DEFAULT_MESSAGES:
            if d["id"] not in existing_ids:
                self.messages.append(Message(**d))
        self.save()

    # ----- target -----
    def get_target(self, name: str) -> Optional[Target]:
        for t in self.targets:
            if t.name == name:
                return t
        return None

    def add_target(self, target: Target) -> bool:
        if self.get_target(target.name):
            return False
        self.targets.append(target)
        self.save()
        return True

    def remove_target(self, name: str) -> bool:
        t = self.get_target(name)
        if not t:
            return False
        self.targets.remove(t)
        self.save()
        return True

    # ----- message -----
    def get_message(self, mid: str) -> Optional[Message]:
        for m in self.messages:
            if m.id == mid:
                return m
        return None


STATE = AppState()
