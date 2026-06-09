"""메시지 push 요청/응답 Pydantic 모델."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PushRequest(BaseModel):
    """메시지 push 요청 본문."""
    role: Optional[str] = Field(
        default="",
        description="전송 대상 역할 (mission, monitoring, vehicle, visual). 빈 값이면 기본 대상에 전송.",
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="메시지 payload (JSON)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "role": "vehicle",
                "payload": {"timestamp": "2026-04-15T03:01:00.123Z"},
            }
        }


class PushResponse(BaseModel):
    """메시지 push 응답."""
    ok: bool
    errors: List[str] = Field(default_factory=list)
    target: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = None
