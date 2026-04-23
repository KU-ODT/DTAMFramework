from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Dict
import urllib.error
import urllib.request

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - runtime fallback path
    httpx = None

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
import uvicorn

from app.config import (
    APP_TITLE,
    FRONTEND_HOST,
    FRONTEND_PORT,
    RESOURCES_DIR,
    SERVER_HOST,
    SERVER_PORT,
    TILE_SERVER_HOST,
    TILE_SERVER_PORT,
    WEB_DIR,
)


API_BASE = f"http://{SERVER_HOST}:{SERVER_PORT}"
TILE_BASE = f"http://{TILE_SERVER_HOST}:{TILE_SERVER_PORT}"
PROXY_TIMEOUT_S = 30.0

_REQUEST_BLOCKED_HEADERS = {
    "host",
    "content-length",
    "connection",
    "accept-encoding",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}
_RESPONSE_BLOCKED_HEADERS = {
    "content-length",
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def _filter_request_headers(headers: Dict[str, str]) -> Dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in _REQUEST_BLOCKED_HEADERS
    }


def _filter_response_headers(headers: Dict[str, str]) -> Dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in _RESPONSE_BLOCKED_HEADERS
    }


def _split_content_type(headers: Dict[str, str]) -> tuple[Dict[str, str], str | None]:
    content_type = None
    filtered: Dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() == "content-type":
            content_type = value
            continue
        filtered[key] = value
    return filtered, content_type


def _drop_content_encoding(headers: Dict[str, str]) -> Dict[str, str]:
    filtered: Dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() == "content-encoding":
            continue
        filtered[key] = value
    return filtered


def _proxy_with_urllib_sync(
    method: str,
    url: str,
    data: bytes | None,
    headers: Dict[str, str],
) -> tuple[int, bytes, Dict[str, str]]:
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=PROXY_TIMEOUT_S) as resp:
            return resp.getcode(), resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as err:
        return err.code, err.read(), dict(err.headers)


async def _proxy_with_urllib(
    request: Request,
    url: str,
    data: bytes | None,
    headers: Dict[str, str],
) -> Response:
    try:
        status_code, payload, raw_headers = await asyncio.to_thread(
            _proxy_with_urllib_sync,
            request.method,
            url,
            data,
            headers,
        )
    except urllib.error.URLError as err:
        reason = str(err.reason) if getattr(err, "reason", None) else str(err)
        raise HTTPException(status_code=502, detail=reason) from err

    resp_headers = _filter_response_headers(raw_headers)
    resp_headers, content_type = _split_content_type(resp_headers)
    return Response(
        content=payload,
        status_code=status_code,
        headers=resp_headers,
        media_type=content_type,
    )


async def _proxy_with_httpx(
    request: Request,
    client,
    url: str,
    data: bytes | None,
    headers: Dict[str, str],
) -> Response:
    try:
        upstream = await client.request(
            request.method,
            url,
            content=data,
            headers=headers,
        )
    except httpx.RequestError as err:
        reason = str(err) or err.__class__.__name__
        raise HTTPException(status_code=502, detail=reason) from err

    resp_headers = _filter_response_headers(dict(upstream.headers))
    # httpx auto-decodes compressed payloads while the original header may remain.
    # Drop Content-Encoding to keep body/header consistent for downstream clients.
    resp_headers = _drop_content_encoding(resp_headers)
    resp_headers, content_type = _split_content_type(resp_headers)
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=resp_headers,
        media_type=content_type,
    )


async def _proxy_request(
    request: Request,
    base: str,
    path: str,
) -> Response:
    query = request.url.query
    url = f"{base}/{path.lstrip('/')}"
    if query:
        url = f"{url}?{query}"
    body = await request.body()
    data = body if body else None
    headers = _filter_request_headers(dict(request.headers))

    client = getattr(request.app.state, "proxy_client", None)
    if httpx is not None and client is not None:
        return await _proxy_with_httpx(request, client, url, data, headers)
    return await _proxy_with_urllib(request, url, data, headers)


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = None
    if httpx is not None:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(PROXY_TIMEOUT_S),
            follow_redirects=False,
        )
    app.state.proxy_client = client
    try:
        yield
    finally:
        if client is not None:
            await client.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title=f"{APP_TITLE} Frontend", lifespan=lifespan)

    @app.api_route(
        "/api/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )
    async def proxy_api(request: Request, path: str) -> Response:
        return await _proxy_request(request, API_BASE, f"api/{path}")

    @app.api_route("/tiles/{path:path}", methods=["GET"])
    async def proxy_tiles(request: Request, path: str) -> Response:
        return await _proxy_request(request, TILE_BASE, f"tiles/{path}")

    @app.api_route("/dem/{path:path}", methods=["GET"])
    async def proxy_dem(request: Request, path: str) -> Response:
        return await _proxy_request(request, TILE_BASE, f"dem/{path}")

    app.mount("/resources", StaticFiles(directory=RESOURCES_DIR), name="resources")
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="static")
    return app


app = create_app()


def main() -> int:
    url = f"http://{FRONTEND_HOST}:{FRONTEND_PORT}/"
    print(f"{APP_TITLE} frontend server running at {url}")
    uvicorn.run(app, host=FRONTEND_HOST, port=FRONTEND_PORT, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
