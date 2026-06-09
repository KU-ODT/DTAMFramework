"""External DTAM plug-in process launcher.

The built-in DTAM modules are owned by IntegrationHub/CoreServer.  Plug-ins are
intentionally launched as separate local instances so their UI/runtime can live
outside the main DTAM stack.
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

from app.core.settings import settings


@dataclass(frozen=True)
class PluginDefinition:
    id: str
    title: str
    script_relative_path: Path
    preferred_frontend_port: int
    preferred_api_port: int | None = None
    preferred_tile_port: int | None = None
    host: str = "127.0.0.1"
    command_profile: str = "traffic-sim"


@dataclass
class PluginRuntime:
    process: subprocess.Popen
    url: str
    ports: dict[str, int]
    log_path: Path


PLUGIN_DEFINITIONS: dict[str, PluginDefinition] = {
    "uam-traffics": PluginDefinition(
        id="uam-traffics",
        title="UAM TrafficS",
        script_relative_path=Path("PlugIn") / "TrafficSim" / "TS_main.py",
        preferred_api_port=18102,
        preferred_tile_port=18101,
        preferred_frontend_port=18173,
    ),
    "uam-scheduler": PluginDefinition(
        id="uam-scheduler",
        title="UAM Flight Scheduler",
        script_relative_path=Path("PlugIn") / "FlightScheduler" / "FS_main.py",
        preferred_frontend_port=18174,
        command_profile="simple-web",
    ),
    "situation-awareness": PluginDefinition(
        id="situation-awareness",
        title="AI Model - 1 : Detection and Prediction",
        script_relative_path=Path("PlugIn") / "SituationAwareness" / "SA_main.py",
        preferred_frontend_port=18210,
        command_profile="simple-web",
    ),
    "teststream": PluginDefinition(
        id="teststream",
        title="DTAM TestStream",
        script_relative_path=Path("PlugIn") / "TestStream" / "TestStream_main.py",
        preferred_frontend_port=18175,
        command_profile="simple-web",
    ),
    "stakeholder-vpo": PluginDefinition(
        id="stakeholder-vpo",
        title="VPO",
        script_relative_path=Path("ExtenstionModule") / "VPOModule" / "VPO_main.py",
        preferred_frontend_port=8110,
        command_profile="vpo-module",
    ),
    "stakeholder-psu": PluginDefinition(
        id="stakeholder-psu",
        title="PSU",
        script_relative_path=Path("ExtenstionModule") / "PSUModule" / "PSU_main.py",
        preferred_frontend_port=8120,
        command_profile="vpo-module",
    ),
}

_plugin_runtimes: dict[str, PluginRuntime] = {}


def launch_plugin(plugin_id: str, timeout_s: float = 25.0) -> dict[str, Any]:
    """Launch a supported plug-in and open its GUI in a separate browser window."""
    definition = _get_definition(plugin_id)
    existing = _plugin_runtimes.get(definition.id)
    if existing and existing.process.poll() is None:
        if _http_ready(existing.url):
            webbrowser.open_new(existing.url)
            return _runtime_payload(definition, existing, reused=True)
        # Process is alive but GUI is not responding; leave it to be replaced.
        _terminate_process_tree(existing.process)
        _plugin_runtimes.pop(definition.id, None)

    preferred_url = f"http://{definition.host}:{definition.preferred_frontend_port}/"
    if _http_ready(preferred_url):
        webbrowser.open_new(preferred_url)
        return {
            "ok": True,
            "id": definition.id,
            "title": definition.title,
            "url": preferred_url,
            "pid": None,
            "ports": _definition_ports(definition, definition.preferred_frontend_port),
            "log": None,
            "reused": True,
            "external": True,
        }

    script_path = _framework_root() / definition.script_relative_path
    if not script_path.is_file():
        raise HTTPException(status_code=500, detail=f"Plugin script not found: {script_path}")

    used_ports: set[int] = set()
    if definition.preferred_api_port is not None:
        api_port = _find_available_tcp_port(definition.preferred_api_port, definition.host, used_ports)
        used_ports.add(api_port)
    else:
        api_port = None
    if definition.preferred_tile_port is not None:
        tile_port = _find_available_tcp_port(definition.preferred_tile_port, definition.host, used_ports)
        used_ports.add(tile_port)
    else:
        tile_port = None
    frontend_port = _find_available_tcp_port(definition.preferred_frontend_port, definition.host, used_ports)

    log_dir = _framework_root() / ".dtam_runtime" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"plugin_{definition.id}.log"

    command = _build_launch_command(definition, script_path, frontend_port, api_port, tile_port)
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env["UATM_OPEN_BROWSER"] = "0"

    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Launching {definition.title}\n")
        log_file.write(" ".join(command) + "\n")
        process = subprocess.Popen(
            command,
            cwd=str(script_path.parent),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=_creation_flags(),
        )

    runtime = PluginRuntime(
        process=process,
        url=f"http://{definition.host}:{frontend_port}/",
        ports=_runtime_ports(frontend_port, api_port, tile_port),
        log_path=log_path,
    )
    _plugin_runtimes[definition.id] = runtime

    deadline = time.time() + max(timeout_s, 1.0)
    while time.time() < deadline:
        if process.poll() is not None:
            _plugin_runtimes.pop(definition.id, None)
            raise HTTPException(
                status_code=502,
                detail=(
                    f"{definition.title} exited early with code {process.returncode}. "
                    f"Check log: {log_path}"
                ),
            )
        if _http_ready(runtime.url):
            webbrowser.open_new(runtime.url)
            return _runtime_payload(definition, runtime, reused=False)
        time.sleep(0.25)

    raise HTTPException(
        status_code=504,
        detail=f"{definition.title} GUI did not become ready in time. Check log: {log_path}",
    )


def plugin_status(plugin_id: str) -> dict[str, Any]:
    """Return whether a supported plug-in is currently reachable/running."""
    definition = _get_definition(plugin_id)
    existing = _plugin_runtimes.get(definition.id)
    if existing and existing.process.poll() is None:
        ready = _http_ready(existing.url)
        return {
            "ok": True,
            "id": definition.id,
            "title": definition.title,
            "running": ready,
            "reachable": ready,
            "url": existing.url,
            "pid": existing.process.pid,
            "ports": existing.ports,
            "tracked": True,
            "external": False,
        }
    if existing:
        _plugin_runtimes.pop(definition.id, None)

    preferred_url = f"http://{definition.host}:{definition.preferred_frontend_port}/"
    ready = _http_ready(preferred_url)
    return {
        "ok": True,
        "id": definition.id,
        "title": definition.title,
        "running": ready,
        "reachable": ready,
        "url": preferred_url if ready else None,
        "pid": None,
        "ports": _definition_ports(definition, definition.preferred_frontend_port),
        "tracked": False,
        "external": ready,
    }


def stop_plugin(plugin_id: str) -> dict[str, Any]:
    """Stop a supported plug-in launched by OperationModule or left on known ports."""
    definition = _get_definition(plugin_id)
    stopped: dict[str, Any] = {"tracked": None, "scripts": {}, "ports": {}}

    existing = _plugin_runtimes.pop(definition.id, None)
    if existing and existing.process.poll() is None:
        _terminate_process_tree(existing.process)
        stopped["tracked"] = existing.process.pid

    script_kills = _force_stop_known_plugin_scripts(plugin_ids={definition.id})
    if script_kills:
        stopped["scripts"] = script_kills

    port_kills = _force_stop_plugin_ports(plugin_ids={definition.id})
    if port_kills:
        stopped["ports"] = port_kills

    status = plugin_status(definition.id)
    status["stopped"] = stopped
    return status


def shutdown_plugins_for_console_exit() -> dict[str, Any]:
    """Best-effort shutdown for plug-ins launched from OperationModule."""
    stopped: dict[str, Any] = {"tracked": {}, "scripts": {}, "ports": {}}
    for plugin_id, runtime in list(_plugin_runtimes.items()):
        if runtime.process.poll() is None:
            _terminate_process_tree(runtime.process)
            stopped["tracked"][plugin_id] = runtime.process.pid
        _plugin_runtimes.pop(plugin_id, None)

    script_kills = _force_stop_known_plugin_scripts()
    if script_kills:
        stopped["scripts"] = script_kills

    port_kills = _force_stop_plugin_ports()
    if port_kills:
        stopped["ports"] = port_kills
    return stopped


def _runtime_payload(definition: PluginDefinition, runtime: PluginRuntime, *, reused: bool) -> dict[str, Any]:
    return {
        "ok": True,
        "id": definition.id,
        "title": definition.title,
        "url": runtime.url,
        "pid": runtime.process.pid,
        "ports": runtime.ports,
        "log": str(runtime.log_path),
        "reused": reused,
    }


def _build_launch_command(
    definition: PluginDefinition,
    script_path: Path,
    frontend_port: int,
    api_port: int | None,
    tile_port: int | None,
) -> list[str]:
    if definition.command_profile in {"vpo-module", "simple-web"}:
        return [
            sys.executable,
            str(script_path),
            "--host",
            definition.host,
            "--port",
            str(frontend_port),
            "--no-browser",
        ]

    if api_port is None or tile_port is None:
        raise HTTPException(status_code=500, detail=f"Plugin ports are not configured: {definition.id}")

    return [
        sys.executable,
        str(script_path),
        "all",
        "--host",
        definition.host,
        "--api-port",
        str(api_port),
        "--tile-port",
        str(tile_port),
        "--frontend-port",
        str(frontend_port),
    ]


def _runtime_ports(frontend_port: int, api_port: int | None = None, tile_port: int | None = None) -> dict[str, int]:
    ports = {"frontend": int(frontend_port)}
    if api_port is not None:
        ports["api"] = int(api_port)
    if tile_port is not None:
        ports["tiles"] = int(tile_port)
    return ports


def _definition_ports(definition: PluginDefinition, frontend_port: int) -> dict[str, int]:
    return _runtime_ports(frontend_port, definition.preferred_api_port, definition.preferred_tile_port)


def _get_definition(plugin_id: str) -> PluginDefinition:
    normalized = str(plugin_id or "").strip().lower()
    try:
        return PLUGIN_DEFINITIONS[normalized]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown or unbound plug-in: {plugin_id}") from exc


def _framework_root() -> Path:
    return settings.project_root.parent


def _creation_flags() -> int:
    if sys.platform != "win32":
        return 0
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _find_available_tcp_port(preferred: int, host: str, used: set[int]) -> int:
    if preferred not in used and _can_bind(host, preferred):
        return preferred
    bind_host = "127.0.0.1" if host in ("", "0.0.0.0", "::") else host
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((bind_host, 0))
            port = int(sock.getsockname()[1])
        if port not in used:
            return port


def _can_bind(host: str, port: int) -> bool:
    bind_host = "127.0.0.1" if host in ("", "0.0.0.0", "::") else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((bind_host, int(port)))
            return True
        except OSError:
            return False


def _http_ready(url: str) -> bool:
    req = UrlRequest(url, headers={"Accept": "text/html,application/json;q=0.8,*/*;q=0.1"})
    try:
        with urlopen(req, timeout=0.8) as response:
            return 200 <= int(response.status) < 500
    except (OSError, URLError, TimeoutError):
        return False


def _terminate_process_tree(process: subprocess.Popen, timeout_s: float = 4.0) -> None:
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        try:
            process.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            pass
        return
    process.terminate()
    try:
        process.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        process.kill()


def _force_stop_known_plugin_scripts(plugin_ids: set[str] | None = None) -> dict[str, list[int]]:
    if sys.platform != "win32":
        return {}
    targets = {
        _normalized_abs_path(_framework_root() / definition.script_relative_path): definition.id
        for definition in PLUGIN_DEFINITIONS.values()
        if plugin_ids is None or definition.id in plugin_ids
    }
    killed: dict[str, list[int]] = {}
    own_pid = os.getpid()
    for process in _windows_processes():
        try:
            pid = int(process.get("ProcessId") or 0)
        except (TypeError, ValueError):
            continue
        if pid <= 0 or pid == own_pid:
            continue
        command_line = _normalized_process_text(process.get("CommandLine"))
        if not command_line:
            continue
        for absolute_script, plugin_id in targets.items():
            if absolute_script and absolute_script in command_line:
                if _terminate_pid(pid):
                    killed.setdefault(plugin_id, []).append(pid)
                break
    return killed


def _force_stop_plugin_ports(plugin_ids: set[str] | None = None) -> dict[int, list[int]]:
    ports: set[int] = set()
    for definition in PLUGIN_DEFINITIONS.values():
        if plugin_ids is not None and definition.id not in plugin_ids:
            continue
        ports.add(int(definition.preferred_frontend_port))
        if definition.preferred_api_port is not None:
            ports.add(int(definition.preferred_api_port))
        if definition.preferred_tile_port is not None:
            ports.add(int(definition.preferred_tile_port))
    killed: dict[int, list[int]] = {}
    for port, pids in _listening_pids_by_port(tuple(sorted(ports))).items():
        for pid in pids:
            if _terminate_pid(pid):
                killed.setdefault(port, []).append(pid)
    return killed


def _windows_processes() -> list[dict[str, Any]]:
    command = (
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,ExecutablePath,CommandLine | "
        "ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
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


def _listening_pids_by_port(ports: tuple[int, ...]) -> dict[int, list[int]]:
    if sys.platform != "win32" or not ports:
        return {}
    try:
        completed = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=5.0,
            check=False,
            creationflags=_creation_flags(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}

    wanted = {int(port) for port in ports}
    found: dict[int, set[int]] = {port: set() for port in wanted}
    own_pid = os.getpid()
    for raw_line in completed.stdout.splitlines():
        parts = raw_line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP" or parts[3].upper() != "LISTENING":
            continue
        try:
            port = int(parts[1].rsplit(":", 1)[-1])
            pid = int(parts[-1])
        except ValueError:
            continue
        if port in wanted and pid > 0 and pid != own_pid:
            found.setdefault(port, set()).add(pid)
    return {port: sorted(pids) for port, pids in found.items() if pids}


def _terminate_pid(pid: int) -> bool:
    if pid <= 0 or pid == os.getpid():
        return False
    if sys.platform == "win32":
        try:
            completed = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8.0,
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


def _normalized_abs_path(path: Path) -> str:
    try:
        resolved = path.resolve(strict=False)
    except OSError:
        resolved = path
    return str(resolved).lower().replace("/", "\\")


def _normalized_process_text(value: Any) -> str:
    return str(value or "").lower().replace("/", "\\")
