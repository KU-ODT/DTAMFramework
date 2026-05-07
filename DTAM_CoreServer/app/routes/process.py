from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="", tags=["🚀 프로세스 관리"])

DTAM_TARGET_IP = os.environ.get("DTAM_TARGET_IP") or "127.0.0.1"
DTAM_WS_PORT = os.environ.get("DTAM_WS_PORT") or "8096"


def _creation_flags() -> int:
    if sys.platform != "win32":
        return 0
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))

# 모듈별 실행 스크립트 맵
MODULE_MAP = {
    "mission": {
        "name": "DTAM Mission Planner",
        "path": "DTAM_MissionPlanner/MP_main.py",
        "type": "python",
        "args": ["--target-ip", DTAM_TARGET_IP, "--ws-port", DTAM_WS_PORT, "--port", "8090", "--no-browser"],
    },
    "vehicle": {
        "name": "DTAM Air Mobility",
        "path": "DTAMAirMobility/AM_main.py",
        "type": "python",
        "args": ["--target-ip", DTAM_TARGET_IP, "--ws-port", DTAM_WS_PORT, "--port", "8100", "--no-browser"],
    },
    "visual": {
        "name": "DTAM Visualization",
        "path": "DTAMVisualization/VM_main.py",
        "type": "python",
        "args": ["--gui-port", "8097", "--server-ip", DTAM_TARGET_IP, "--ws-port", DTAM_WS_PORT, "--no-browser"],
    },
}

active_processes: Dict[str, subprocess.Popen] = {}


async def _process_heartbeat_loop():
    """Track child process liveness without faking module WebSocket heartbeats."""
    while True:
        try:
            for role, proc in list(active_processes.items()):
                if proc.poll() is not None:
                    active_processes.pop(role, None)
        except Exception:
            traceback.print_exc()
        await asyncio.sleep(2.0)

@router.post(
    "/{role}/start",
    summary="모듈 실행",
    description="지정된 역할(mission, vehicle, visual)의 프로세스를 새로운 콘솔 창에서 실행합니다."
)
async def start_module(role: str):
    try:
        if role not in MODULE_MAP:
            raise HTTPException(status_code=404, detail=f"Unknown module: {role}")
        
        if role in active_processes and active_processes[role].poll() is None:
            return {"ok": True, "message": f"{MODULE_MAP[role]['name']} is already running."}

        info = MODULE_MAP[role]
        # 프로젝트 루트(DTAMFramework) 절대 경로 계산 (app/router/process.py 기준 4단계 위)
        BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
        script_path = BASE_DIR / info["path"]

        print(f"[DTAM Core] Attempting to start {role} at {script_path}")

        if not script_path.exists():
            raise FileNotFoundError(f"Script not found at {script_path}")

        if info["type"] == "python":
            new_proc = subprocess.Popen(
                [sys.executable, str(script_path), *list(info.get("args", []))],
                cwd=str(script_path.parent),
                creationflags=_creation_flags(),
            )
        else:  # bat
            new_proc = subprocess.Popen(
                [str(script_path), *list(info.get("args", []))],
                cwd=str(script_path.parent),
                shell=True,
                creationflags=_creation_flags(),
            )
        
        active_processes[role] = new_proc
        return {"ok": True, "message": f"{info['name']} started (PID: {new_proc.pid})"}
    except Exception as e:
        print(f"[DTAM Core] Error starting {role}:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/{role}/stop",
    summary="모듈 종료",
    description="실행 중인 모듈 프로세스를 강제 종료합니다."
)
async def stop_module(role: str):
    if role not in active_processes:
        return {"ok": True, "message": "Module is not running."}
    
    proc = active_processes.pop(role)
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                pass
    return {"ok": True, "message": f"Stopped {role}"}

