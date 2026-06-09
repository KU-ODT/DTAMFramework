"""트래픽 이벤트 데이터 모델."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class TrafficEvent:
    ts: float
    mid: str
    name: str
    kind: str              # "rx" | "tx"
    proto: str             # "ws"
    peer_role: Optional[str]
    peer_ip: str
    peer_port: int
    ok: bool
    note: str = ""
    payload_preview: Any = None
    full_payload: Any = None
    extra_bytes: bytes = b""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "mid": self.mid,
            "name": self.name,
            "kind": self.kind,
            "proto": self.proto,
            "peer_role": self.peer_role,
            "peer_ip": self.peer_ip,
            "peer_port": self.peer_port,
            "ok": self.ok,
            "note": self.note,
            "payload_preview": self.payload_preview,
            # full_payload is intentionally excluded from to_dict for GUI bandwidth
        }
