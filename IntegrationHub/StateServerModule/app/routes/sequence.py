"""시퀀스 다이어그램 — JSON 데이터 + 시각화 페이지.

- ``GET /api/sequence-diagram`` — Phase별 메시지 흐름을 담은 정적 JSON
- ``GET /docs/sequence``        — 위 JSON 을 SVG 로 그려주는 HTML 페이지

데이터 파일은 ``app/web/data/sequence_diagram{_ko,_en}.json``.
페이지와 JSON 이 같은 origin (SimulationState, port 8096) 위에 있어야
브라우저 fetch 가 막히지 않는다.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from ..config import WEB_DIR

router = APIRouter(tags=["📊 서버 상태"])

_DATA_DIR = WEB_DIR / "data"


@router.get(
    "/api/sequence-diagram",
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


# ── 시각화 페이지 ───────────────────────────────────────────────────────
SEQ_HTML = r"""Internal DTAM helper."""


@router.get(
    "/docs/sequence",
    summary="시퀀스 다이어그램",
    description="Phase별 메시지 흐름 시퀀스 다이어그램 (SVG 기반 시각화)",
    response_class=HTMLResponse,
)
async def sequence_diagram_page() -> HTMLResponse:
    return HTMLResponse(content=SEQ_HTML)
