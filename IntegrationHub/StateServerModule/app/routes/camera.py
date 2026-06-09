"""Camera-related StateServer routes.

- GET /stream/camera/{vehicle_id}: low-rate MJPEG stream reconstructed from MSG 4101.
- GET /api/camera/list: vehicle IDs with a recent 4101 frame.
- GET /api/camera-streams: latest MSG 4102 stream descriptors.

High-rate real-time video should use the direct media URL announced by 4102
instead of proxying frames through IntegrationHub.
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

router = APIRouter(tags=["Camera"])


@router.get(
    "/stream/camera/{vehicle_id}",
    summary="Low-rate MJPEG stream from MSG 4101",
    description=(
        "Replays the latest ICD 4101 frame as an MJPEG stream. "
        "Use only for low-rate monitoring; high-rate video should open the "
        "direct media-plane URL announced by MSG 4102."
    ),
)
async def camera_stream(vehicle_id: str, request: Request) -> StreamingResponse:
    hub = request.app.state.hub

    async def generate():
        last_frame_obj = None
        while True:
            if await request.is_disconnected():
                break
            frame = hub.camera_frames.get(vehicle_id)
            if frame and frame is not last_frame_obj:
                last_frame_obj = frame
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Cache-Control: no-cache\r\n"
                    + f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii")
                    + frame + b"\r\n"
                )
            await asyncio.sleep(0.2)  # 5 FPS max from cached 4101 frames.

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get(
    "/api/camera/list",
    summary="Vehicle IDs with recent MSG 4101 frames",
    description="Returns vehicle IDs currently cached from MSG 4101 Camera Image Frame messages.",
)
async def camera_list(request: Request) -> JSONResponse:
    hub = request.app.state.hub
    return JSONResponse(sorted(hub.camera_frames.keys()))


@router.get(
    "/api/camera-streams",
    summary="Latest MSG 4102 camera stream descriptors",
    description="Returns the latest Camera Stream Descriptor messages cached by stream_id.",
)
async def camera_stream_descriptors(request: Request) -> JSONResponse:
    hub = request.app.state.hub
    streams: dict[str, Any] = getattr(hub, "camera_streams", {})
    return JSONResponse({"streams": streams, "count": len(streams)})


@router.get(
    "/api/camera-streams/{stream_id}",
    summary="MSG 4102 descriptor by stream ID",
)
async def camera_stream_descriptor(stream_id: str, request: Request) -> JSONResponse:
    hub = request.app.state.hub
    streams: dict[str, Any] = getattr(hub, "camera_streams", {})
    descriptor = streams.get(stream_id)
    if descriptor is None:
        raise HTTPException(status_code=404, detail=f"Unknown camera stream: {stream_id}")
    return JSONResponse(descriptor)
