"""HTML index 라우트 (`/`)."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from ..config import WEB_DIR

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(content=(WEB_DIR / "index.html").read_text(encoding="utf-8"))
