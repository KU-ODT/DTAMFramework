"""ICD 문서 제공 라우터.

- GET /api/icd           — 전체 ICD 목록
- GET /api/icd/{mid}     — 특정 메시지 ICD 마크다운 원문
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse, PlainTextResponse

from ..model.config import ICD_DIR
from ..model.message import MESSAGE_TABLE, PHASE_INFO, phase_tag

router = APIRouter(prefix="/api/icd", tags=["📋 ICD 문서"])


@router.get(
    "",
    summary="전체 ICD 목록",
    description="정의된 모든 메시지의 ICD 요약 정보를 반환합니다.",
)
async def icd_list() -> JSONResponse:
    result = []
    for mid, info in sorted(MESSAGE_TABLE.items()):
        phase = info.get("phase", -1)
        result.append({
            "mid": mid,
            "name": info["name"],
            "name_ko": info.get("name_ko", info["name"]),
            "proto": info.get("proto", "ws"),
            "direction": info.get("direction", ""),
            "rate_hz": info.get("rate_hz", 0.0),
            "phase": phase,
            "phase_name": PHASE_INFO.get(phase, {}).get("name", ""),
            "phase_tag": phase_tag(phase),
        })
    return JSONResponse(result)


@router.get(
    "/{mid}",
    summary="ICD 마크다운 원문",
    description="특정 메시지의 ICD 문서(마크다운)를 반환합니다.\n\n"
                "한국어(`?lang=ko`, 기본) 또는 영문(`?lang=en`) 선택 가능.",
)
async def icd_detail(mid: str, lang: str = "ko") -> PlainTextResponse:
    info = MESSAGE_TABLE.get(mid)
    if info is None:
        return PlainTextResponse(f"Unknown message ID: {mid}", status_code=404)

    lang_dir = "KOR" if lang.lower().startswith("k") else "ENG"
    icd_dir = ICD_DIR / lang_dir

    # 파일명 패턴: 0001_moduleSettingInfo.md, 4001_vehicleStatus.md 등
    candidates = list(icd_dir.glob(f"{mid}_*.md"))
    if not candidates:
        return PlainTextResponse(
            f"ICD document not found for {mid} ({lang_dir})",
            status_code=404,
        )

    content = candidates[0].read_text(encoding="utf-8")
    return PlainTextResponse(content, media_type="text/markdown; charset=utf-8")


@router.get(
    "/phases",
    summary="Phase 목록",
    description="시퀀스 다이어그램 기준 Phase 정의를 반환합니다.",
)
async def phase_list() -> JSONResponse:
    result = []
    for phase_num, info in sorted(PHASE_INFO.items()):
        # 이 phase에 속하는 메시지 목록
        messages = [
            {"mid": mid, "name": m["name"], "name_ko": m.get("name_ko", m["name"])}
            for mid, m in sorted(MESSAGE_TABLE.items())
            if m.get("phase") == phase_num
        ]
        result.append({
            "phase": phase_num,
            "name": info["name"],
            "name_en": info.get("name_en", ""),
            "description": info.get("description", ""),
            "messages": messages,
        })
    return JSONResponse(result)
