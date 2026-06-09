"""Operations Console module lifecycle facade.

ServerRevision moves process ownership to `CoreServerModule`. This keeps the
existing Operations Console API shape while delegating start/stop to CoreServer.
"""

from __future__ import annotations

import os
import json
import socket
import subprocess
import sys
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import HTTPException

from app import comm
from app.core.settings import settings


CORE_HOST = os.environ.get("DTAM_TARGET_IP") or "127.0.0.1"
CORE_PORT = 8095
STATE_HOST = os.environ.get("DTAM_TARGET_IP") or "127.0.0.1"
STATE_PORT = int(os.environ.get("DTAM_WS_PORT") or 8096)
VFDS_HOST = os.environ.get("DTAM_VFDS_GUI_HOST") or "127.0.0.1"
VFDS_PORT = int(os.environ.get("DTAM_VFDS_PORT") or 8098)


@dataclass(frozen=True)
class ModuleDefinition:
    id: str
    name: str
    role: str
    display_role: str
    accent: str
    gui_host: str
    gui_port: int

    @property
    def endpoint(self) -> str:
        if self.id == "server":
            return f"{CORE_HOST}:{CORE_PORT} / {STATE_HOST}:{STATE_PORT}"
        return f"ws://{STATE_HOST}:{STATE_PORT}/ws/dtam"

    @property
    def gui_url(self) -> str:
        return f"http://{self.gui_host}:{self.gui_port}"

    @property
    def transport(self) -> str:
        if self.id == "server":
            return f"HTTP {CORE_PORT} / WS {STATE_PORT}"
        return f"WS {STATE_PORT}"


MODULES: dict[str, ModuleDefinition] = {
    "mission": ModuleDefinition("mission", "MissionModule", "mission", "MISSION", "purple", "127.0.0.1", 8090),
    "airmobility": ModuleDefinition("airmobility", "VehicleModule", "vehicle", "VEHICLE", "green", "127.0.0.1", 8100),
    "vfds": ModuleDefinition("vfds", "VFDS/KP2A Dynamics", "vfds", "VFDS/KP2A", "blue", VFDS_HOST, VFDS_PORT),
    "server": ModuleDefinition("server", "IntegrationHub", "server", "SERVER", "cyan", "127.0.0.1", CORE_PORT),
    "visualization": ModuleDefinition("visualization", "VisualizationModule", "visual", "VISUAL", "amber", "127.0.0.1", 8097),
}

ROLE_TO_ID = {definition.role: module_id for module_id, definition in MODULES.items()}
ID_TO_PROCESS_ROLE = {
    "mission": "mission",
    "airmobility": "vehicle",
    "visualization": "visual",
}
START_ORDER = ("server", "mission", "airmobility", "vfds", "visualization")
DISPLAY_ORDER = ("mission", "airmobility", "vfds", "server", "visualization")
LOCAL_MODULE_PORTS = tuple(
    definition.gui_port for module_id, definition in MODULES.items() if module_id != "server"
)
LOCAL_STACK_PORTS = (*LOCAL_MODULE_PORTS, CORE_PORT, STATE_PORT)
LOCAL_MODULE_SCRIPT_RELATIVE_PATHS: dict[str, Path] = {
    "mission": Path("MissionModule") / "MP_main.py",
    "airmobility": Path("VehicleModule") / "AM_main.py",
    "visualization": Path("VisualizationModule") / "VM_main.py",
}
LOCAL_STACK_SCRIPT_RELATIVE_PATHS = (
    Path("IntegrationHub") / "CoreServerModule" / "DSE_main.py",
    Path("IntegrationHub") / "StateServerModule" / "SS_main.py",
    *LOCAL_MODULE_SCRIPT_RELATIVE_PATHS.values(),
)
LOCAL_UNREAL_EXE_RELATIVE_PATHS = (
    Path("VisualizationModule")
    / "runtime"
    / "Unreal"
    / "Environments"
    / "DTAMVisualization"
    / "Saved"
    / "StagedBuilds"
    / "Windows"
    / "DTAMVisualization.exe",
    Path("VisualizationModule")
    / "runtime"
    / "Unreal"
    / "Environments"
    / "DTAMVisualization"
    / "Binaries"
    / "Win64"
    / "DTAMVisualization.exe",
)

_core_process: subprocess.Popen | None = None


def list_module_status() -> dict[str, Any]:
    registry = _fetch_state_registry()
    modules = [_module_status(MODULES[module_id], registry) for module_id in DISPLAY_ORDER]
    running_count = sum(1 for item in modules if item["status"] == "connected")
    return {
        "modules": modules,
        "running_count": running_count,
        "total_count": len(modules),
        "server_registry_available": bool(registry),
        "generated_at": time.time(),
    }


def start_all_modules() -> dict[str, Any]:
    for module_id in START_ORDER:
        start_module(module_id)
    return _wait_for_connected(START_ORDER, timeout_s=15.0)


def stop_all_modules() -> dict[str, Any]:
    for module_id in reversed(START_ORDER):
        stop_module(module_id)
    _force_stop_known_processes(
        ports=LOCAL_STACK_PORTS,
        script_paths=LOCAL_STACK_SCRIPT_RELATIVE_PATHS,
        include_unreal=True,
    )
    return list_module_status()


def shutdown_modules_for_console_exit() -> None:
    """Best-effort shutdown for the local DTAM stack when the console exits."""
    try:
        stop_all_modules()
    except Exception:
        pass
    _force_stop_known_processes(
        ports=LOCAL_STACK_PORTS,
        script_paths=LOCAL_STACK_SCRIPT_RELATIVE_PATHS,
        include_unreal=True,
    )


def cleanup_stale_module_processes_for_console_start() -> None:
    """Clear stale module GUI processes without touching a running Unreal session.

    Opening the Operations Console must not close Unreal that was launched from
    the Visualization module or the editor. Explicit module stop/DTAM relaunch
    paths still own Unreal shutdown.
    """
    _force_stop_known_processes(
        ports=LOCAL_MODULE_PORTS,
        script_paths=tuple(LOCAL_MODULE_SCRIPT_RELATIVE_PATHS.values()),
        include_unreal=False,
    )


def cleanup_stale_visualization_processes() -> dict[str, Any]:
    """Clear VM/Unreal leftovers before writing AirSim settings and relaunching."""
    result = _force_stop_known_processes(
        ports=(MODULES["visualization"].gui_port,),
        script_paths=(LOCAL_MODULE_SCRIPT_RELATIVE_PATHS["visualization"],),
        include_unreal=True,
    )
    _wait_for_port_closed(MODULES["visualization"].gui_host, MODULES["visualization"].gui_port, timeout_s=4.0)
    return result


def start_module(module_id: str) -> dict[str, Any]:
    definition = _get_definition(module_id)
    if definition.id == "server":
        _ensure_core_server()
        return list_module_status()
    if definition.id == "vfds":
        _ensure_vfds_runtime()
        return list_module_status()
    if _is_module_http_ready(definition):
        return list_module_status()
    _ensure_core_server()
    process_role = ID_TO_PROCESS_ROLE.get(definition.id)
    if process_role is None:
        return list_module_status()
    result = comm.control_module_process(process_role, "start")
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("error") or result.get("detail") or result)
    # CoreServer can still hold a stale Popen handle when a user manually closes
    # Unreal/VM or when Operations Console force-cleans a previous launch.  In
    # that case CoreServer may reply "already running" without opening the fixed
    # backend port; force a clean restart so VM does not fall back to 8098+ and
    # the console keeps waiting on 8097 forever.
    message = str(result.get("message") or "").lower()
    if "already running" in message and not _is_module_http_ready(definition):
        _restart_local_module_process(definition)
    return list_module_status()


def stop_module(module_id: str) -> dict[str, Any]:
    definition = _get_definition(module_id)
    if definition.id == "server":
        _stop_core_server_if_owned()
        return list_module_status()
    if definition.id == "vfds":
        _force_stop_ports((VFDS_PORT,))
        _wait_for_port_closed(VFDS_HOST, VFDS_PORT, timeout_s=4.0)
        return list_module_status()
    if not _is_port_open(CORE_HOST, CORE_PORT):
        return list_module_status()
    process_role = ID_TO_PROCESS_ROLE.get(definition.id)
    if process_role is None:
        return list_module_status()
    result = comm.control_module_process(process_role, "stop")
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("error") or result.get("detail") or result)
    if definition.id == "visualization":
        cleanup_stale_visualization_processes()
    return list_module_status()


def open_module_gui(module_id: str) -> dict[str, Any]:
    definition = _get_definition(module_id)
    if definition.id == "vfds" and not _is_port_open(definition.gui_host, definition.gui_port):
        _ensure_vfds_runtime()
    if not _is_port_open(definition.gui_host, definition.gui_port):
        raise HTTPException(
            status_code=409,
            detail=f"{definition.name} backend is not running. Run modules first.",
        )
    webbrowser.open_new(definition.gui_url)
    status = list_module_status()
    status["opened"] = {"id": definition.id, "url": definition.gui_url}
    return status


def start_module_and_open_gui(module_id: str, timeout_s: float = 6.0) -> dict[str, Any]:
    definition = _get_definition(module_id)
    start_module(module_id)
    deadline = time.time() + max(timeout_s, 0.5)
    while time.time() < deadline:
        if _is_port_open(definition.gui_host, definition.gui_port):
            return open_module_gui(module_id)
        time.sleep(0.15)
    raise HTTPException(status_code=504, detail=f"{definition.name} GUI did not become ready in time.")


def open_state_monitor_gui(timeout_s: float = 15.0) -> dict[str, Any]:
    """Open the Simulation State live monitor instead of the CoreServer page."""
    _ensure_core_server(timeout_s=timeout_s)
    monitor_url = f"http://{STATE_HOST}:{STATE_PORT}/"
    if not _is_port_open(STATE_HOST, STATE_PORT):
        raise HTTPException(
            status_code=504,
            detail=f"StateServer live monitor did not become ready on {STATE_HOST}:{STATE_PORT}.",
        )
    webbrowser.open_new(monitor_url)
    status = list_module_status()
    status["opened"] = {"id": "sim_state", "url": monitor_url}
    return status


def ensure_module_backend(module_id: str, timeout_s: float = 8.0) -> str:
    definition = _get_definition(module_id)
    if definition.id == "server":
        _ensure_core_server(timeout_s=timeout_s)
    elif definition.id == "vfds":
        _ensure_vfds_runtime(timeout_s=timeout_s)
    elif not _is_module_http_ready(definition):
        start_module(module_id)
    if _wait_for_module_http_ready(definition, timeout_s=max(timeout_s, 0.5)):
        return definition.gui_url
    if definition.id != "server":
        _restart_local_module_process(definition)
        if _wait_for_module_http_ready(definition, timeout_s=max(timeout_s, 0.5)):
            return definition.gui_url
    raise HTTPException(status_code=504, detail=f"{definition.name} backend did not become ready in time.")


def _ensure_vfds_runtime(timeout_s: float = 25.0) -> dict[str, Any]:
    """Start/keep the embedded VFDS/KP2A server through VehicleModule.

    The VFDS dashboard is only a browser view.  The runtime itself is owned by
    VehicleModule and must already be alive from the moment the user enters UAM
    mode, so Operation never waits until DT World/Play to spawn it.
    """

    airmobility_url = ensure_module_backend("airmobility", timeout_s=max(timeout_s, 8.0)).rstrip("/")
    payload = _request_json_url(
        f"{airmobility_url}/api/vfds/ensure",
        method="POST",
        body={"timeout_s": max(timeout_s, 20.0)},
        timeout_s=max(timeout_s, 20.0) + 5.0,
    )
    if not bool(payload.get("ok")):
        detail = payload.get("runtime", {}).get("error") if isinstance(payload.get("runtime"), dict) else ""
        raise HTTPException(status_code=502, detail=detail or "VFDS/KP2A runtime is not ready")
    if not _wait_for_module_http_ready(MODULES["vfds"], timeout_s=max(timeout_s, 5.0)):
        raise HTTPException(status_code=504, detail=f"VFDS/KP2A GUI backend did not become ready on {VFDS_PORT}.")
    return payload


def _wait_for_module_http_ready(definition: ModuleDefinition, *, timeout_s: float) -> bool:
    deadline = time.time() + max(timeout_s, 0.5)
    while time.time() < deadline:
        if _is_module_http_ready(definition):
            return True
        time.sleep(0.15)
    return _is_module_http_ready(definition)


def _restart_local_module_process(definition: ModuleDefinition) -> None:
    if definition.id == "server":
        return
    process_role = ID_TO_PROCESS_ROLE.get(definition.id)
    script_path = LOCAL_MODULE_SCRIPT_RELATIVE_PATHS.get(definition.id)
    if process_role is None or script_path is None:
        return

    _ensure_core_server()
    try:
        comm.control_module_process(process_role, "stop")
    except Exception:
        pass

    _force_stop_known_processes(
        ports=(definition.gui_port,),
        script_paths=(script_path,),
        include_unreal=definition.id == "visualization",
    )
    _wait_for_port_closed(definition.gui_host, definition.gui_port, timeout_s=4.0)

    result = comm.control_module_process(process_role, "start")
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("error") or result.get("detail") or result)


def _module_status(definition: ModuleDefinition, registry: dict[str, Any]) -> dict[str, Any]:
    if definition.id == "server":
        core_open = _is_port_open(CORE_HOST, CORE_PORT)
        state_open = _is_port_open(STATE_HOST, STATE_PORT)
        connected = core_open or state_open
        return {
            "id": definition.id,
            "name": definition.name,
            "role": definition.display_role,
            "endpoint": definition.endpoint,
            "transport": definition.transport,
            "gui_url": definition.gui_url,
            "status": "connected" if connected else "waiting",
            "process_state": "running" if connected else "stopped",
            "pid": None,
            "rx": "-",
            "tx": "-",
            "heartbeat": "core/state" if connected else "-",
            "tag": "8095/8096" if connected else "idle",
            "accent": definition.accent,
            "gui_available": core_open,
            "last_heartbeat_ts": 0,
        }

    if definition.id == "vfds":
        health = _try_request_json_url(f"{definition.gui_url}/api/v1/health", timeout_s=0.6)
        gui_available = _is_port_open(definition.gui_host, definition.gui_port)
        connected = bool(health.get("status") == "ok") or gui_available
        time_value = health.get("time") or "-"
        mission_rx = health.get("missionRxCount", 0)
        time_rx = health.get("timeRxCount", 0)
        return {
            "id": definition.id,
            "name": definition.name,
            "role": definition.display_role,
            "endpoint": f"{definition.gui_url}/api/v1/missions/realtime",
            "transport": f"HTTP {definition.gui_port}",
            "gui_url": definition.gui_url,
            "status": "connected" if connected else "waiting",
            "process_state": "running" if gui_available else "stopped",
            "pid": None,
            "rx": str(mission_rx),
            "tx": str(time_rx),
            "heartbeat": str(time_value),
            "tag": "VFDS" if connected else "idle",
            "accent": definition.accent,
            "gui_available": gui_available,
            "last_heartbeat_ts": time.time() if connected else 0,
        }

    registry_module = _registry_module(registry, definition.role)
    registry_connected = bool(registry_module.get("connected")) if registry_module else False
    gui_available = _is_port_open(definition.gui_host, definition.gui_port)
    connected = registry_connected or gui_available
    last_heartbeat = float(registry_module.get("last_heartbeat_ts") or 0.0) if registry_module else 0.0
    inbound_count = int(registry_module.get("tx_count") or 0) if registry_module else 0
    outbound_count = int(registry_module.get("rx_count") or 0) if registry_module else 0

    return {
        "id": definition.id,
        "name": definition.name,
        "role": definition.display_role,
        "endpoint": definition.endpoint,
        "transport": definition.transport,
        "gui_url": definition.gui_url,
        "status": "connected" if connected else "waiting",
        "process_state": "running" if gui_available or registry_connected else "stopped",
        "pid": None,
        "rx": str(inbound_count),
        "tx": str(outbound_count),
        "heartbeat": _format_heartbeat(last_heartbeat, registry_connected),
        "tag": _last_message_tag(registry_module) or ("ws" if registry_connected else "idle"),
        "accent": definition.accent,
        "gui_available": gui_available,
        "last_heartbeat_ts": last_heartbeat,
    }


def _get_definition(module_id: str) -> ModuleDefinition:
    normalized = str(module_id).strip().lower()
    if normalized in ROLE_TO_ID:
        normalized = ROLE_TO_ID[normalized]
    try:
        return MODULES[normalized]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown module: {module_id}") from exc


def _framework_root() -> Path:
    return settings.project_root.parent


def _creation_flags() -> int:
    if sys.platform != "win32":
        return 0
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _ensure_core_server(timeout_s: float = 15.0) -> None:
    """Start CoreServer first so the console can delegate module lifecycle calls."""
    global _core_process

    if _is_port_open(CORE_HOST, CORE_PORT) and _is_port_open(STATE_HOST, STATE_PORT):
        return

    if _core_process is None or _core_process.poll() is not None:
        script_path = _framework_root() / "IntegrationHub" / "CoreServerModule" / "DSE_main.py"
        if not script_path.exists():
            raise HTTPException(status_code=500, detail=f"CoreServer script not found: {script_path}")

        log_dir = _framework_root() / ".dtam_runtime" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "operations_console_core_server.log"

        env = os.environ.copy()
        env["DTAM_TARGET_IP"] = CORE_HOST
        env["DTAM_WS_PORT"] = str(STATE_PORT)
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting CoreServer from Operations Console\n")
            _core_process = subprocess.Popen(
                [sys.executable, str(script_path), "--no-browser"],
                cwd=str(script_path.parent),
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=_creation_flags(),
            )

    deadline = time.time() + max(timeout_s, 1.0)
    while time.time() < deadline:
        if _core_process is not None and _core_process.poll() is not None:
            raise HTTPException(
                status_code=502,
                detail=f"CoreServer exited early with code {_core_process.returncode}. "
                       "See .dtam_runtime/logs/operations_console_core_server.log",
            )
        if _is_port_open(CORE_HOST, CORE_PORT) and _is_port_open(STATE_HOST, STATE_PORT):
            return
        time.sleep(0.2)

    raise HTTPException(
        status_code=504,
        detail=f"Core/State Server did not become ready on {CORE_PORT}/{STATE_PORT}. "
               "See .dtam_runtime/logs/operations_console_core_server.log",
    )


def _stop_core_server_if_owned(timeout_s: float = 4.0) -> None:
    global _core_process
    proc = _core_process
    _core_process = None
    if proc is None or proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        try:
            proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            pass
        return
    proc.terminate()
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2.0)


def _force_stop_ports(ports: tuple[int, ...]) -> dict[int, list[int]]:
    """Kill local processes listening on known DTAM ports.

    This is intentionally limited to fixed DTAM module/server ports so the
    console can clean up orphaned children even when CoreServer ownership was
    lost during a previous run.
    """
    killed: dict[int, list[int]] = {}
    own_pid = os.getpid()
    for port in ports:
        pids = [pid for pid in _listening_pids(port) if pid and pid != own_pid]
        for pid in sorted(set(pids)):
            if _terminate_pid_tree(pid):
                killed.setdefault(int(port), []).append(pid)
    return killed


def _force_stop_known_processes(
    *,
    ports: tuple[int, ...],
    script_paths: tuple[Path, ...],
    include_unreal: bool,
) -> dict[str, Any]:
    killed: dict[str, Any] = {
        "scripts": {},
        "executables": {},
        "ports": {},
    }
    script_kills = _force_stop_script_processes(script_paths)
    if script_kills:
        killed["scripts"] = script_kills
    if include_unreal:
        exe_kills = _force_stop_executables(LOCAL_UNREAL_EXE_RELATIVE_PATHS)
        if exe_kills:
            killed["executables"] = exe_kills
    port_kills = _force_stop_ports(ports)
    if port_kills:
        killed["ports"] = port_kills
    return killed


def _force_stop_script_processes(script_paths: tuple[Path, ...]) -> dict[str, list[int]]:
    if sys.platform != "win32" or not script_paths:
        return {}
    stop_priority = {
        "VM_main.py": 10,
        "AM_main.py": 20,
        "MP_main.py": 30,
        "DOC_main.py": 40,
        "SS_main.py": 50,
        "DSE_main.py": 60,
    }
    ordered_paths = sorted(
        script_paths,
        key=lambda path: (stop_priority.get(path.name, 100), str(path).casefold()),
    )
    targets = [
        (_normalized_abs_path(_framework_root() / relative_path), str(relative_path), relative_path.name.casefold())
        for relative_path in ordered_paths
    ]
    killed: dict[str, list[int]] = {}
    own_pid = os.getpid()
    processes = _windows_processes()
    killed_pids: set[int] = set()
    for absolute_script, label, script_name in targets:
        for process in processes:
            pid = _process_pid(process)
            if pid <= 0 or pid == own_pid or pid in killed_pids:
                continue
            command_line = _normalized_process_text(process.get("CommandLine"))
            if not command_line:
                continue
            if (absolute_script and absolute_script in command_line) or script_name in command_line:
                if _terminate_pid_tree(pid):
                    killed.setdefault(label, []).append(pid)
                    killed_pids.add(pid)
    return killed


def _force_stop_executables(executable_paths: tuple[Path, ...]) -> dict[str, list[int]]:
    if sys.platform != "win32" or not executable_paths:
        return {}
    targets = {
        _normalized_abs_path(_framework_root() / relative_path): str(relative_path)
        for relative_path in executable_paths
    }
    killed: dict[str, list[int]] = {}
    own_pid = os.getpid()
    for process in _windows_processes():
        pid = _process_pid(process)
        if pid <= 0 or pid == own_pid:
            continue
        executable = _normalized_process_text(process.get("ExecutablePath"))
        command_line = _normalized_process_text(process.get("CommandLine"))
        for absolute_executable, label in targets.items():
            if not absolute_executable:
                continue
            if executable == absolute_executable or absolute_executable in command_line:
                if _terminate_pid_tree(pid):
                    killed.setdefault(label, []).append(pid)
                break
    return killed


def _windows_processes() -> list[dict[str, Any]]:
    command = (
        "$own="
        + str(os.getpid())
        + "; Get-CimInstance Win32_Process | "
        "Where-Object { $_.ProcessId -ne $own } | "
        "Select-Object ProcessId,ExecutablePath,CommandLine | ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8.0,
            check=False,
            creationflags=_creation_flags(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode != 0 or not completed.stdout.strip():
        return []
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, dict):
        return [parsed]
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    return []


def _process_pid(process: dict[str, Any]) -> int:
    try:
        return int(process.get("ProcessId") or 0)
    except (TypeError, ValueError):
        return 0


def _normalized_abs_path(path: Path) -> str:
    try:
        resolved = path.resolve(strict=False)
    except OSError:
        resolved = path
    return str(resolved).lower().replace("/", "\\")


def _normalized_process_text(value: Any) -> str:
    return str(value or "").lower().replace("/", "\\")


def _listening_pids(port: int) -> list[int]:
    if sys.platform != "win32":
        return []
    try:
        completed = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5.0,
            check=False,
            creationflags=_creation_flags(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    pids: list[int] = []
    suffix = f":{int(port)}"
    for line in (completed.stdout or "").splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        if parts[0].upper() != "TCP":
            continue
        local_address = parts[1]
        state = parts[3].upper()
        if state != "LISTENING" or not local_address.endswith(suffix):
            continue
        try:
            pids.append(int(parts[-1]))
        except ValueError:
            continue
    return pids


def _terminate_pid_tree(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            completed = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10.0,
                check=False,
            )
            return completed.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False
    try:
        os.kill(pid, 15)
        return True
    except OSError:
        return False


def _is_module_already_running(definition: ModuleDefinition) -> bool:
    if definition.id == "server":
        return _is_port_open(CORE_HOST, CORE_PORT) or _is_port_open(STATE_HOST, STATE_PORT)
    return _is_port_open(definition.gui_host, definition.gui_port)


def _wait_for_connected(module_ids: tuple[str, ...], timeout_s: float) -> dict[str, Any]:
    requested = set(module_ids)
    deadline = time.time() + max(timeout_s, 0.5)
    latest = list_module_status()
    while time.time() < deadline:
        latest = list_module_status()
        by_id = {item.get("id"): item for item in latest.get("modules", [])}
        if all(by_id.get(module_id, {}).get("status") == "connected" for module_id in requested):
            return latest
        time.sleep(0.35)
    return latest


def _fetch_state_registry() -> dict[str, Any]:
    return comm.get_registry_snapshot()


def _registry_module(registry: dict[str, Any], role: str) -> dict[str, Any]:
    modules = registry.get("registry", {}).get("modules", []) if isinstance(registry, dict) else []
    if isinstance(modules, dict):
        modules = modules.values()
    for item in modules or []:
        if isinstance(item, dict) and str(item.get("role") or "").lower() == role:
            return item
    return {}


def _format_heartbeat(timestamp: float, connected: bool) -> str:
    if not connected:
        return "-"
    if not timestamp:
        return "connected"
    age_s = max(0.0, time.time() - timestamp)
    if age_s < 1:
        return "now"
    return f"{age_s:.0f}s ago"


def _last_message_tag(module: dict[str, Any]) -> str:
    if not module:
        return ""
    counts = module.get("rx_per_mid") or module.get("tx_per_mid") or {}
    if isinstance(counts, dict) and counts:
        return str(next(reversed(counts.keys())))
    return ""


def _is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=0.25):
            return True
    except OSError:
        return False


def _wait_for_port_closed(host: str, port: int, *, timeout_s: float) -> bool:
    deadline = time.time() + max(timeout_s, 0.5)
    while time.time() < deadline:
        if not _is_port_open(host, port):
            return True
        time.sleep(0.15)
    return not _is_port_open(host, port)


def _is_module_http_ready(definition: ModuleDefinition) -> bool:
    if definition.id == "server":
        return _http_ready(f"http://{CORE_HOST}:{CORE_PORT}/") and _http_ready(f"http://{STATE_HOST}:{STATE_PORT}/api/state")
    if definition.id == "vfds":
        return (
            _http_ready(f"{definition.gui_url}/api/v1/health", timeout_s=1.0)
            or _http_ready(f"{definition.gui_url}/health", timeout_s=1.0)
        )
    if definition.id == "visualization":
        return _http_ready(f"{definition.gui_url}/api/health", timeout_s=3.0)
    readiness_paths = {
        "mission": "/api/dtam/status",
        "airmobility": "/api/status",
    }
    path = readiness_paths.get(definition.id, "/")
    return _http_ready(f"{definition.gui_url}{path}")


def _http_ready(url: str, *, timeout_s: float = 0.6) -> bool:
    req = UrlRequest(url, headers={"Accept": "application/json,text/html;q=0.8,*/*;q=0.1"})
    try:
        with urlopen(req, timeout=timeout_s) as response:
            return 200 <= int(response.status) < 500
    except (OSError, URLError, TimeoutError):
        return False


def _request_json_url(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    timeout_s: float = 3.0,
) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = UrlRequest(url, data=data, headers=headers, method=str(method or "GET").upper())
    try:
        with urlopen(req, timeout=timeout_s) as response:
            raw = response.read()
            if not raw:
                return {"ok": 200 <= int(response.status) < 400}
            parsed = json.loads(raw.decode("utf-8", errors="replace"))
            return parsed if isinstance(parsed, dict) else {"ok": True, "body": parsed}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"{url} request failed: {exc}") from exc


def _try_request_json_url(url: str, *, timeout_s: float = 0.6) -> dict[str, Any]:
    try:
        return _request_json_url(url, timeout_s=timeout_s)
    except HTTPException:
        return {}
