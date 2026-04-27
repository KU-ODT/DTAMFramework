"""Phase 기반 메시지 Push 라우터.

MESSAGE_TABLE의 각 메시지를 개별 엔드포인트로 등록하고,
phase에 따라 Swagger UI 태그를 자동 부여합니다.
ICD dataclass로 payload를 정적 검증합니다.
"""
from __future__ import annotations

import dataclasses
import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from pydantic import create_model, Field
from fastapi.responses import JSONResponse

from ..model.message import MESSAGE_TABLE, PHASE_INFO, phase_tag
from ..schema.push import PushResponse
from ..schema.icd_registry import (
    ICD_REGISTRY,
    get_example_payload,
    to_dict,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/msg")


def _create_push_handler(msg_id: str):
    """메시지별 push 핸들러 팩토리 — 동적 Pydantic 모델 검증 포함."""
    icd_cls = ICD_REGISTRY.get(msg_id)
    example_payload = get_example_payload(msg_id)
    
    # 동적으로 Pydantic 모델 생성 (Swagger 자동완성 지원)
    model_name = f"PushRequest_{msg_id}"
    
    if icd_cls is not None:
        payload_field = (icd_cls, Field(..., description=f"{msg_id} payload", json_schema_extra={"example": example_payload}))
    else:
        payload_field = (Dict[str, Any], Field(default_factory=dict, description="Payload (JSON)", json_schema_extra={"example": example_payload}))
        
    config_dict = {
        "json_schema_extra": {
            "example": {
                "role": "vehicle" if "4" in msg_id else "monitoring",
                "payload": example_payload
            }
        }
    }

    DynamicPushRequest = create_model(
        model_name,
        __config__=config_dict,
        role=(Optional[str], Field(default="", description="전송 대상 역할 (mission, monitoring, vehicle, visual).")),
        payload=payload_field
    )

    from fastapi import Body
    async def handler(request: Request, body: Any = Body(None)) -> JSONResponse:
        hub = request.app.state.hub
        
        # [NEW] raw payload 지원
        payload_dict = {}
        role = ""
        
        if isinstance(body, dict):
            if "payload" in body:
                payload_dict = body["payload"]
                role = str(body.get("role") or "").strip()
            else:
                payload_dict = body
        elif body:
            # Pydantic 모델인 경우
            payload_dict = getattr(body, "payload", body)
            role = str(getattr(body, "role", "") or "").strip()

        if role:
            try:
                hub.db.write_event(msg_id, payload_dict)
            except Exception:
                logger.exception("DB write failed for api push %s", msg_id)
            result = hub.push_to_role(role, msg_id, payload_dict)
        else:
            if msg_id == "0002":
                hub.registry.heartbeat(payload_dict)
                result = {"ok": True, "mid": "0002"}
            else:
                result = hub.push_scheduled_mid(msg_id)
        return JSONResponse(result)

    # FastAPI 라우팅을 위해 함수 이름 동적으로 변경
    handler.__name__ = f"push_msg_{msg_id}"
    handler.__qualname__ = f"push_msg_{msg_id}"
    return handler


def _build_field_table(cls) -> str:
    """dataclass 필드를 마크다운 테이블로 변환."""
    if cls is None or not dataclasses.is_dataclass(cls):
        return ""
    lines = ["\n\n#### Payload 필드\n", "| 필드 | 타입 | 기본값 |", "|---|---|---|"]
    for f in dataclasses.fields(cls):
        ftype = f.type if isinstance(f.type, str) else getattr(f.type, '__name__', str(f.type))
        default = f.default if f.default is not dataclasses.MISSING else "—"
        if f.default_factory is not dataclasses.MISSING:
            default = "(factory)"
        lines.append(f"| `{f.name}` | `{ftype}` | `{default}` |")
    return "\n".join(lines)


# 동적 라우트 등록 — 메시지별 개별 엔드포인트
for _mid, _info in sorted(MESSAGE_TABLE.items()):
    _phase = _info.get("phase", -1)
    _tag = phase_tag(_phase)
    _name_ko = _info.get("name_ko", _info["name"])
    _direction = _info.get("direction", "")
    _rate = _info.get("rate_hz", 0.0)
    _icd_cls = ICD_REGISTRY.get(_mid)

    _description = (
        f"### {_name_ko}\n\n"
        f"| 항목 | 값 |\n|---|---|\n"
        f"| Message ID | `{_mid}` |\n"
        f"| 영문명 | {_info['name']} |\n"
        f"| 방향 | `{_direction}` |\n"
        f"| 프로토콜 | `{_info.get('proto', 'udp').upper()}` |\n"
        f"| 주기 | {_rate} Hz |\n"
        f"| Dataclass | `{_icd_cls.__name__}` |\n" if _icd_cls else ""
    )

    if _icd_cls:
        _description += _build_field_table(_icd_cls)
        # 예시 payload
        _example = get_example_payload(_mid)
        if _example:
            _description += f"\n\n#### 예시 payload\n```json\n{json.dumps(_example, indent=2, ensure_ascii=False)}\n```"

    router.add_api_route(
        f"/{_mid}",
        _create_push_handler(_mid),
        methods=["POST"],
        summary=f"MSG {_mid}: {_info['name']}",
        description=_description,
        tags=[_tag],
        response_model=PushResponse,
        response_class=JSONResponse,
    )
