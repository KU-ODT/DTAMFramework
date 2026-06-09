"""FastAPI web server for the Situation Awareness plug-in."""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.core.utils.thread_manager import ProcessingResult, ThreadManager
from app.services.dtam_bridge import SituationAwarenessIcdBridge


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

app = FastAPI(title="Situation Awareness")
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

latest_frame: np.ndarray | None = None
latest_data: dict[str, Any] = {
    "risk_score": 0.0,
    "risk_level": "SAFE",
    "object_count": 0,
    "distance": "--",
    "ttc": "--",
    "uncertainty": "--",
    "advisory": "Waiting for ICD stream...",
}

thread_manager = ThreadManager(gui_callback=None)
icd_bridge: SituationAwarenessIcdBridge | None = None


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/status")
async def status() -> dict[str, Any]:
    return {
        "ok": True,
        "input_mode": os.environ.get("DTAM_SA_INPUT_MODE", "icd").lower(),
        "latest": latest_data,
        "threads": thread_manager.get_thread_states(),
        "icd": icd_bridge.status() if icd_bridge else None,
    }


def gui_callback(result: ProcessingResult | np.ndarray) -> None:
    """Accept direct ICD frames and reference ThreadManager processing results."""

    global latest_frame
    try:
        if isinstance(result, np.ndarray):
            latest_frame = result.copy()
            return

        if result.frame is not None:
            latest_frame = result.frame.copy()

        object_count = len(result.detected_objects or [])
        risk_score = 0.0
        risk_level = "SAFE"

        if result.ahp_result:
            risk_score = float(getattr(result.ahp_result, "risk_score", 0.0))
            if risk_score <= 0.3:
                risk_level = "SAFE"
            elif risk_score <= 0.6:
                risk_level = "CAUTION"
            else:
                risk_level = "EMERGENCY"

        distance = "--"
        ttc = "--"
        uncertainty = "--"
        if result.safety_metrics:
            closest = min(result.safety_metrics, key=lambda m: m.distance)
            distance = f"{closest.distance:.1f}"
            ttc = (
                f"{closest.time_to_collision:.1f}"
                if closest.time_to_collision is not None
                else "0"
            )
            uncertainty = f"{closest.uncertainty:.2f}"

        latest_data.update(
            {
                "risk_score": round(risk_score, 2),
                "risk_level": risk_level,
                "object_count": object_count,
                "distance": distance,
                "ttc": ttc,
                "uncertainty": uncertainty,
                "advisory": f"{risk_level} monitoring active",
            }
        )
    except Exception as exc:
        print("[SituationAwareness] callback error:", exc)


@app.get("/video_feed")
def video_feed() -> StreamingResponse:
    def generate():
        global latest_frame
        while True:
            if latest_frame is None:
                time.sleep(0.05)
                continue
            ok, buffer = cv2.imencode(".jpg", latest_frame)
            if not ok:
                time.sleep(0.05)
                continue
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + buffer.tobytes()
                + b"\r\n"
            )
            time.sleep(0.03)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.on_event("startup")
async def startup_event() -> None:
    global thread_manager, icd_bridge
    input_mode = os.environ.get("DTAM_SA_INPUT_MODE", "icd").strip().lower()
    thread_manager.gui_callback = gui_callback
    if input_mode == "airsim":
        thread_manager.start_all(enable_camera=True, enable_airsim=True)
        latest_data["advisory"] = "AirSim direct monitoring active"
    else:
        thread_manager.start_all(enable_camera=False, enable_airsim=False)
        latest_data["advisory"] = "Waiting for DTAM ICD 4001/4101 stream..."

    icd_bridge = SituationAwarenessIcdBridge(
        frame_queue=thread_manager.frame_queue,
        sensor_queue=thread_manager.sensor_queue,
        frame_callback=gui_callback,
    )


@app.on_event("shutdown")
async def shutdown_event() -> None:
    global icd_bridge
    if icd_bridge is not None:
        icd_bridge.close()
        icd_bridge = None
    thread_manager.stop_all()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    while True:
        await websocket.send_text(json.dumps(latest_data, ensure_ascii=False))
        await asyncio.sleep(1)
