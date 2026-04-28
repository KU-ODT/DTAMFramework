"""카메라 스트리밍 라우터.

- GET /stream/camera/{vehicle_id} — MJPEG 스트림
- GET /api/camera/list            — 활성 카메라 목록
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

router = APIRouter(tags=["📹 카메라"])


@router.get(
    "/stream/camera/{vehicle_id}",
    summary="MJPEG 카메라 스트림",
    description="브라우저에서 `<img src=\"/stream/camera/UAM0001\">` 형태로 사용합니다.\n\n"
                "vehicle 모듈이 4101 Camera Image Frame 을 전송하면 실시간으로 스트리밍됩니다.",
)
async def camera_stream(vehicle_id: str, request: Request) -> StreamingResponse:
    hub = request.app.state.hub

    async def generate():
        while True:
            frame = hub.camera_frames.get(vehicle_id)
            if frame:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                )
            await asyncio.sleep(0.2)  # 5 FPS

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get(
    "/api/camera/list",
    summary="활성 카메라 목록",
    description="현재 프레임이 수신된 vehicle_id 목록을 반환합니다.",
)
async def camera_list(request: Request) -> JSONResponse:
    hub = request.app.state.hub
    return JSONResponse(sorted(hub.camera_frames.keys()))
