from __future__ import annotations

import asyncio
import subprocess
import sys
import requests
import concurrent.futures
import traceback
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="", tags=["🚀 프로세스 관리"])

# 모듈별 실행 스크립트 맵
MODULE_MAP = {
    "mission": {"name": "DTAM Mission Planner", "path": "DTAM_MissionPlanner/MP_main.py", "type": "python"},
    "vehicle": {"name": "DTAM Air Mobility", "path": "DTAMAirMobility/AM_main.py", "type": "python"},
    "visual": {"name": "DTAM Visualization", "path": "DTAMVisualizationModule/run.bat", "type": "bat"},
}

active_processes: Dict[str, subprocess.Popen] = {}
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)

def _send_heartbeat_sync(role: str):
    """상태 서버에 하트비트를 보내는 동기 함수"""
    try:
        requests.post(
            "http://127.0.0.1:8096/api/heartbeat",
            json={"source": f"DTAM_{role.upper()}"},
            timeout=1.0
        )
    except Exception:
        pass

async def _process_heartbeat_loop():
    """백그라운드에서 실행 중인 프로세스의 하트비트를 주기적으로 갱신"""
    loop = asyncio.get_event_loop()
    while True:
        try:
            for role, proc in list(active_processes.items()):
                if proc.poll() is None:
                    await loop.run_in_executor(_executor, _send_heartbeat_sync, role)
                else:
                    active_processes.pop(role, None)
        except Exception:
            traceback.print_exc()
        await asyncio.sleep(2.0)

@router.post("/{role}/start")
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
                [sys.executable, str(script_path)],
                cwd=str(script_path.parent),
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
            )
        else:  # bat
            new_proc = subprocess.Popen(
                [str(script_path)],
                cwd=str(script_path.parent),
                shell=True,
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
            )
        
        active_processes[role] = new_proc
        
        # 즉시 하트비트 전송
        loop = asyncio.get_event_loop()
        loop.run_in_executor(_executor, _send_heartbeat_sync, role)

        return {"ok": True, "message": f"{info['name']} started (PID: {new_proc.pid})"}
    except Exception as e:
        print(f"[DTAM Core] Error starting {role}:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{role}/stop")
async def stop_module(role: str):
    if role not in active_processes:
        return {"ok": True, "message": "Module is not running."}
    
    proc = active_processes.pop(role)
    if proc.poll() is None:
        proc.terminate()
    return {"ok": True, "message": f"Stopped {role}"}
