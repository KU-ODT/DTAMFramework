"""Web route for rendering the main dashboard page."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from backend.app.core.settings import settings

web_router = APIRouter()
templates = Jinja2Templates(directory=str(settings.templates_dir))


@web_router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "page_title": "DTAM GUI",
            "app_name": "Digital Twin Air Mobility",
        },
    )


@web_router.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)
