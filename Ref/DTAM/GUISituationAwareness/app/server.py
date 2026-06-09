import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT_DIR))
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

import asyncio
import json
from fastapi.responses import StreamingResponse
import cv2
from CoreSituationAwareness.utils.thread_manager import ThreadManager

app = FastAPI(title="Situation Awareness")
latest_frame = None

BASE_DIR = Path(__file__).resolve().parent.parent

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "web"),
    name="static"
)

@app.get("/")
async def root():
    return FileResponse(BASE_DIR / "web" / "index.html")

# --------------------------------------------------
# GLOBAL STATE
# --------------------------------------------------

latest_data = {
    "risk_score": 0.0,
    "risk_level": "SAFE",
    "object_count": 0,
    "distance": "--",
    "ttc": "--",
    "uncertainty": "--",
    "advisory": "Waiting for backend..."
}

# --------------------------------------------------
# CALLBACK FROM THREAD MANAGER
# --------------------------------------------------

def gui_callback(result):

    global latest_frame

    try:

        if result.frame is not None:
            latest_frame = result.frame.copy()

        object_count = 0

        if result.detected_objects:
            object_count = len(result.detected_objects)

        risk_score = 0.0
        risk_level = "SAFE"

        if result.ahp_result:

            risk_score = float(
                getattr(result.ahp_result, "risk_score", 0.0)
            )

            if risk_score <= 0.3:
                risk_level = "SAFE"
            elif risk_score <= 0.6:
                risk_level = "CAUTION"
            else:
                risk_level = "EMERGENCY"

        distance = "0"
        ttc = "0"
        uncertainty = "0"

        if result.safety_metrics:
            closest = min(result.safety_metrics, key=lambda m: m.distance)

            distance = f"{closest.distance:.1f}"
            ttc = f"{closest.time_to_collision:.1f}" if closest.time_to_collision is not None else "0"
            uncertainty = f"{closest.uncertainty:.2f}"

        latest_data.update({
            "risk_score": round(risk_score, 2),
            "risk_level": risk_level,
            "object_count": object_count,
            "distance": distance,
            "ttc": ttc,
            "uncertainty": uncertainty,
            "advisory": f"{risk_level} monitoring active"
        })

    except Exception as e:
        print("Callback error:", e)
        

@app.get("/video_feed")
def video_feed():

    def generate():

        global latest_frame

        while True:

            if latest_frame is not None:

                _, buffer = cv2.imencode('.jpg', latest_frame)

                frame_bytes = buffer.tobytes()

                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n'
                    + frame_bytes +
                    b'\r\n'
                )

    return StreamingResponse(
        generate(),
        media_type='multipart/x-mixed-replace; boundary=frame'
    )

# --------------------------------------------------
# THREAD MANAGER
# --------------------------------------------------

thread_manager = ThreadManager(gui_callback=gui_callback)

@app.on_event("startup")
async def startup_event():

    print("Starting Thread Manager...")

    thread_manager.start_all(
        enable_camera=True,
        enable_airsim=True
    )

# --------------------------------------------------
# WEBSOCKET
# --------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    await websocket.accept()

    while True:

        await websocket.send_text(
            json.dumps(latest_data)
        )

        await asyncio.sleep(1)