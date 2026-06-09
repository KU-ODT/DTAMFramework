"""API route for loading system module overview data."""

import os
import threading
import time

from fastapi import APIRouter, HTTPException

from app.schemas.module import ModuleOverview
from app.services.dashboard_service import get_module_overview
from app.services.dtam_execution_service import (
    apply_dtam_control_modes,
    ensure_vfds_runtime,
    get_dtam_runtime_status,
    launch_dtam_world,
    prepare_dtam_execution,
)
from app.services.module_process_service import (
    list_module_status,
    open_module_gui,
    start_all_modules,
    start_module,
    stop_all_modules,
    stop_module,
    shutdown_modules_for_console_exit,
)
from app.services.simulation_time_service import get_operation_server_time

router = APIRouter()
_console_close_lock = threading.Lock()
_console_close_started = False


def _shutdown_stack_and_exit(reason: str) -> None:
    print(f"[OperationModule] managed console closed ({reason}); shutting down DTAM stack.")
    try:
        shutdown_modules_for_console_exit()
    except Exception as exc:
        print(f"[OperationModule] stack shutdown on console close failed: {type(exc).__name__}: {exc}")
    finally:
        # Give the beacon/HTTP response a moment to flush before terminating
        # the OperationModule process. Start_DTAM.py will then run its final
        # cleanup pass as well.
        time.sleep(0.5)
        os._exit(0)


@router.get("/overview", response_model=ModuleOverview)
async def get_system_overview() -> ModuleOverview:
    return get_module_overview("system")


@router.get("/time")
async def get_server_time() -> dict:
    return get_operation_server_time()


@router.get("/modules")
async def get_dtam_modules() -> dict:
    return list_module_status()


@router.post("/modules/run")
def run_dtam_modules() -> dict:
    return start_all_modules()


@router.post("/modules/start")
def start_dtam_modules() -> dict:
    return start_all_modules()


@router.post("/dtam/prepare-execution")
def prepare_dtam_execution_route(payload: dict) -> dict:
    return prepare_dtam_execution(payload)


@router.post("/dtam/launch-world")
def launch_dtam_world_route() -> dict:
    return launch_dtam_world()


@router.post("/dtam/apply-control")
def apply_dtam_control_modes_route(payload: dict) -> dict:
    return apply_dtam_control_modes(payload)


@router.post("/dtam/vfds/ensure")
def ensure_vfds_runtime_route(payload: dict) -> dict:
    return ensure_vfds_runtime(payload)


@router.get("/dtam/runtime-status")
def get_dtam_runtime_status_route() -> dict:
    return get_dtam_runtime_status()


@router.post("/modules/stop")
def stop_dtam_modules() -> dict:
    return stop_all_modules()


@router.post("/modules/{module_id}/run")
def run_dtam_module(module_id: str) -> dict:
    return start_module(module_id)


@router.post("/modules/{module_id}/stop")
def stop_dtam_module(module_id: str) -> dict:
    return stop_module(module_id)


@router.post("/modules/{module_id}/open-gui")
def open_dtam_module_gui(module_id: str) -> dict:
    return open_module_gui(module_id)


@router.post("/console/closed")
async def managed_console_closed(payload: dict | None = None) -> dict:
    expected_token = os.environ.get("DTAM_OPERATION_CONSOLE_MANAGED_TOKEN") or ""
    supplied_token = str((payload or {}).get("token") or "")
    if not expected_token or supplied_token != expected_token:
        raise HTTPException(status_code=403, detail="Invalid managed console close token")

    reason = str((payload or {}).get("reason") or "browser-window-closed")[:80]
    global _console_close_started
    with _console_close_lock:
        if not _console_close_started:
            _console_close_started = True
            threading.Thread(
                target=_shutdown_stack_and_exit,
                args=(reason,),
                name="dtam-console-close-shutdown",
                daemon=True,
            ).start()
    return {"ok": True, "shutdown_started": True}
