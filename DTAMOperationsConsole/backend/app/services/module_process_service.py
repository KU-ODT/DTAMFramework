"""Operations Console module lifecycle facade.

ServerRevision moves process ownership to `DTAM_CoreServer`. This keeps the
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

from backend.app import comm
from backend.app.core.settings import settings


CORE_HOST = os.environ.get("DTAM_TARGET_IP") or "127.0.0.1"
CORE_PORT = 8095
STATE_HOST = os.environ.get("DTAM_TARGET_IP") or "127.0.0.1"
STATE_PORT = int(os.environ.get("DTAM_WS_PORT") or 8096)


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
    "mission": ModuleDefinition("mission", "DTAM Mission Planner", "mission", "MISSION", "purple", "127.0.0.1", 8090),
    "airmobility": ModuleDefinition("airmobility", "DTAM Air Mobility", "vehicle", "VEHICLE", "green", "127.0.0.1", 8100),
    "server": ModuleDefinition("server", "DTAM Core/State Server", "server", "SERVER", "cyan", "127.0.0.1", CORE_PORT),
    "visualization": ModuleDefinition("visualization", "DTAM Visualization", "visual", "VISUAL", "amber", "127.0.0.1", 8097),
}

ROLE_TO_ID = {definition.role: module_id for module_id, definition in MODULES.items()}
ID_TO_PROCESS_ROLE = {
    "mission": "mission",
    "airmobility": "vehicle",
    "visualization": "visual",
}
START_ORDER = ("server", "mission", "airmobility", "visualization")
DISPLAY_ORDER = ("mission", "airmobility", "server", "visualization")
LOCAL_MODULE_PORTS = tuple(
    definition.gui_port for module_id, definition in MODULES.items() if module_id != "server"
)
LOCAL_STACK_PORTS = (*LOCAL_MODULE_PORTS, CORE_PORT, STATE_PORT)
LOCAL_MODULE_SCRIPT_RELATIVE_PATHS: dict[str, Path] = {
    "mission": Path("DTAM_MissionPlanner") / "MP_main.py",
    "airmobility": Path("DTAMAirMobility") / "AM_main.py",
    "visualization": Path("DTAMVisualization") / "VM_main.py",
}
LOCAL_STACK_SCRIPT_RELATIVE_PATHS = (
    Path("DTAM_CoreServer") / "DSE_main.py",
    Path("DTAM_SimulationState") / "SS_main.py",
    *LOCAL_MODULE_SCRIPT_RELATIVE_PATHS.values(),
)
LOCAL_UNREAL_EXE_RELATIVE_PATHS = (
    Path("DTAMVisualization")
    / "Unreal"
    / "Environments"
    / "DTAMVisualization"
    / "Binaries"
    / "Win64"
    / "DTAMVisualization.exe",
    Path("DTAMVisualization")
    / "Unreal"
    / "Environments"
    / "DTAMVisualization"
    / "Saved"
    / "StagedBuilds"
    / "Windows"
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


def cleanup_stale_visualization_processes() -> None:
    """Clear VM/Unreal leftovers before writing AirSim settings and relaunching."""
    _force_stop_known_processes(
        ports=(MODULES["visualization"].gui_port,),
        script_paths=(LOCAL_MODULE_SCRIPT_RELATIVE_PATHS["visualization"],),
        include_unreal=True,
    )


def start_module(module_id: str) -> dict[str, Any]:
    definition = _get_definition(module_id)
    if definition.id == "server":
        _ensure_core_server()
        return list_module_status()
    if _is_module_already_running(definition):
        return list_module_status()
    _ensure_core_server()
    process_role = ID_TO_PROCESS_ROLE.get(definition.id)
    if process_role is None:
        return list_module_status()
    result = comm.control_module_process(process_role, "start")
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("error") or result.get("detail") or result)
    return list_module_status()


def stop_module(module_id: str) -> dict[str, Any]:
    definition = _get_definition(module_id)
    if definition.id == "server":
        _stop_core_server_if_owned()
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


def ensure_module_backend(module_id: str, timeout_s: float = 8.0) -> str:
    definition = _get_definition(module_id)
    if definition.id == "server":
        _ensure_core_server(timeout_s=timeout_s)
    elif not _is_port_open(definition.gui_host, definition.gui_port):
        start_module(module_id)
    deadline = time.time() + max(timeout_s, 0.5)
    while time.time() < deadline:
        if definition.id == "server" and _is_module_http_ready(definition):
            return definition.gui_url
        if definition.id != "server" and _is_module_http_ready(definition):
            return definition.gui_url
        time.sleep(0.15)
    raise HTTPException(status_code=504, detail=f"{definition.name} backend did not become ready in time.")


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
        script_path = _framework_root() / "DTAM_CoreServer" / "DSE_main.py"
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
    targets = {
        _normalized_abs_path(_framework_root() / relative_path): str(relative_path)
        for relative_path in script_paths
    }
    killed: dict[str, list[int]] = {}
    own_pid = os.getpid()
    for process in _windows_processes():
        pid = _process_pid(process)
        if pid <= 0 or pid == own_pid:
            continue
        command_line = _normalized_process_text(process.get("CommandLine"))
        if not command_line:
            continue
        for absolute_script, label in targets.items():
            if absolute_script and absolute_script in command_line:
                if _terminate_pid_tree(pid):
                    killed.setdefault(label, []).append(pid)
                break
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


def _is_module_http_ready(definition: ModuleDefinition) -> bool:
    if definition.id == "server":
        return _http_ready(f"http://{CORE_HOST}:{CORE_PORT}/") and _http_ready(f"http://{STATE_HOST}:{STATE_PORT}/api/state")
    readiness_paths = {
        "mission": "/api/dtam/status",
        "airmobility": "/api/status",
        "visualization": "/api/state",
    }
    path = readiness_paths.get(definition.id, "/")
    return _http_ready(f"{definition.gui_url}{path}")


def _http_ready(url: str) -> bool:
    req = UrlRequest(url, headers={"Accept": "application/json,text/html;q=0.8,*/*;q=0.1"})
    try:
        with urlopen(req, timeout=0.6) as response:
            return 200 <= int(response.status) < 500
    except (OSError, URLError, TimeoutError):
        return False
