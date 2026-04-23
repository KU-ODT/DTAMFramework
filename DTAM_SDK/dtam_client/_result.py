"""Shared dtam_client result types."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PushResult:
    ok: bool = False
    bytes_sent: int = 0
    payload: Optional[Dict[str, Any]] = None
    target: Optional[str] = None
    errors: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.ok

    def __str__(self) -> str:
        if self.ok:
            return f"OK {self.bytes_sent}B -> {self.target}"
        return f"FAIL {self.target}: {'; '.join(self.errors)}"
