"""시퀀스 다이어그램 정적 자료 제공.

CoreServer 의 동일 기능을 SimulationState 의 라이브 모니터 페이지에서
바로 fetch 할 수 있도록 옮겨왔습니다. 데이터는 ``app/web/data/`` 안의
정적 JSON 파일.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import Response

from ..config import WEB_DIR

router = APIRouter(prefix="/api", tags=["📊 서버 상태"])

_DATA_DIR = WEB_DIR / "data"


@router.get(
    "/sequence-diagram",
    summary="시퀀스 다이어그램 JSON",
    description="라이브 모니터의 lane/arrow 렌더링용 정적 시퀀스 데이터.",
)
async def get_sequence_diagram(lang: str = "ko") -> Response:
    suffix = "_en" if lang.lower().startswith("e") else "_ko"
    path = _DATA_DIR / f"sequence_diagram{suffix}.json"
    if not path.is_file():
        path = _DATA_DIR / "sequence_diagram.json"
    if not path.is_file():
        return Response(
            content=json.dumps({"actors": [], "messages": []}),
            media_type="application/json",
        )
    return Response(content=path.read_text(encoding="utf-8"), media_type="application/json")
