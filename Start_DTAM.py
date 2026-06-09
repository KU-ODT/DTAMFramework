"""Start DTAM 2-Tier Architecture: Core Server + Operations Console.

Default behavior keeps the server control plane hidden:
1. Stop any previously running local DTAM stack.
2. Start IntegrationHub/CoreServerModule in the background.
3. CoreServerModule starts StateServerModule in the background.
4. Run OperationModule in the current console.

Use ``--show-server-windows`` only when the server console windows are needed
for debugging. Hidden server logs are written under ``.dtam_runtime/logs``.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / ".dtam_runtime" / "logs"

DTAM_PORTS = (
    8000, 8001, 8002, 8003, 8004, 8005,  # OperationModule fallback ports
    8090,  # MissionModule
    8095,  # CoreServerModule
    8096,  # StateServerModule
    8097,  # VisualizationModule
    8100,  # VehicleModule
    18101,  # TrafficS tile server
    18102,  # TrafficS API server
    18173,  # TrafficS frontend server
    18174,  # UAM Flight Scheduler frontend/API server
    18210,  # Situation Awareness frontend server
)

DTAM_SCRIPT_RELATIVE_PATHS = (
    Path("IntegrationHub") / "CoreServerModule" / "DSE_main.py",
    Path("IntegrationHub") / "StateServerModule" / "SS_main.py",
    Path("OperationModule") / "DOC_main.py",
    Path("MissionModule") / "MP_main.py",
    Path("VehicleModule") / "AM_main.py",
    Path("VisualizationModule") / "VM_main.py",
    Path("PlugIn") / "TrafficSim" / "TS_main.py",
    Path("PlugIn") / "FlightScheduler" / "FS_main.py",
    Path("PlugIn") / "SituationAwareness" / "SA_main.py",
)
DTAM_SCRIPT_STOP_ORDER = (
    Path("PlugIn") / "SituationAwareness" / "SA_main.py",
    Path("PlugIn") / "FlightScheduler" / "FS_main.py",
    Path("PlugIn") / "TrafficSim" / "TS_main.py",
    Path("VisualizationModule") / "VM_main.py",
    Path("VehicleModule") / "AM_main.py",
    Path("MissionModule") / "MP_main.py",
    Path("OperationModule") / "DOC_main.py",
    Path("IntegrationHub") / "StateServerModule" / "SS_main.py",
    Path("IntegrationHub") / "CoreServerModule" / "DSE_main.py",
)

DTAM_UNREAL_EXE_RELATIVE_PATHS = (
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

OPERATION_BROWSER_PROFILE_MARKER = str(ROOT / ".dtam_runtime" / "operations_console_browser").casefold()


def _normalize_path_for_match(path: Path | str) -> str:
    try:
        return str(Path(path).resolve()).replace("/", "\\").casefold()
    except Exception:
        return str(path).replace("/", "\\").casefold()


def _terminate_pid_tree(pid: int) -> bool:
    if pid <= 0 or pid == os.getpid():
        return False
    if os.name == "nt":
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


def _windows_processes() -> list[dict]:
    if os.name != "nt":
        return []
    command = (
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,ExecutablePath,CommandLine | "
        "ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    output = completed.stdout.strip()
    if not output:
        return []
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _force_stop_script_processes(processes: list[dict] | None = None) -> dict[str, list[int]]:
    if os.name != "nt":
        return {}
    processes = _windows_processes() if processes is None else processes
    targets = [
        (_normalize_path_for_match(ROOT / relative), str(relative), relative.name.casefold())
        for relative in DTAM_SCRIPT_STOP_ORDER
    ]
    killed: dict[str, list[int]] = {}
    killed_pids: set[int] = set()
    for absolute_script, label, script_name in targets:
        for process in processes:
            try:
                pid = int(process.get("ProcessId") or 0)
            except (TypeError, ValueError):
                continue
            if pid <= 0 or pid == os.getpid() or pid in killed_pids:
                continue
            command_line = str(process.get("CommandLine") or "").replace("/", "\\").casefold()
            if not command_line:
                continue
            # Newer launches use absolute paths; Start_DTAM itself starts some
            # entry points from cwd with a relative script name, so match both.
            if absolute_script in command_line or script_name in command_line:
                if _terminate_pid_tree(pid):
                    killed.setdefault(label, []).append(pid)
                    killed_pids.add(pid)
    return killed


def _force_stop_unreal_processes(processes: list[dict] | None = None) -> dict[str, list[int]]:
    if os.name != "nt":
        return {}
    processes = _windows_processes() if processes is None else processes
    targets = {
        _normalize_path_for_match(ROOT / relative): str(relative)
        for relative in DTAM_UNREAL_EXE_RELATIVE_PATHS
    }
    killed: dict[str, list[int]] = {}
    for process in processes:
        try:
            pid = int(process.get("ProcessId") or 0)
        except (TypeError, ValueError):
            continue
        if pid <= 0 or pid == os.getpid():
            continue
        executable = _normalize_path_for_match(process.get("ExecutablePath") or "")
        command_line = str(process.get("CommandLine") or "").replace("/", "\\").casefold()
        for absolute_exe, label in targets.items():
            if absolute_exe and (executable == absolute_exe or absolute_exe in command_line):
                if _terminate_pid_tree(pid):
                    killed.setdefault(label, []).append(pid)
                break
    return killed


def _force_stop_operation_browser_processes(processes: list[dict] | None = None) -> list[int]:
    if os.name != "nt":
        return []
    processes = _windows_processes() if processes is None else processes
    marker = OPERATION_BROWSER_PROFILE_MARKER.replace("/", "\\")
    killed: list[int] = []
    for process in processes:
        try:
            pid = int(process.get("ProcessId") or 0)
        except (TypeError, ValueError):
            continue
        if pid <= 0 or pid == os.getpid():
            continue
        command_line = str(process.get("CommandLine") or "").replace("/", "\\").casefold()
        if marker in command_line and _terminate_pid_tree(pid):
            killed.append(pid)
    return killed


def _listening_pids(port: int) -> list[int]:
    if os.name != "nt":
        return []
    try:
        completed = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=10.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    pids: list[int] = []
    suffix = f":{int(port)}"
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if "LISTENING" not in line.upper():
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        local_address = parts[1]
        if not local_address.endswith(suffix):
            continue
        try:
            pid = int(parts[-1])
        except ValueError:
            continue
        if pid > 0 and pid != os.getpid():
            pids.append(pid)
    return sorted(set(pids))


def _listening_pids_by_port(ports: tuple[int, ...]) -> dict[int, list[int]]:
    if os.name != "nt":
        return {}
    try:
        completed = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=10.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}

    wanted = {int(port) for port in ports}
    found: dict[int, set[int]] = {port: set() for port in wanted}
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if "LISTENING" not in line.upper():
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        local_address = parts[1]
        try:
            port = int(local_address.rsplit(":", 1)[-1])
            pid = int(parts[-1])
        except ValueError:
            continue
        if port in wanted and pid > 0 and pid != os.getpid():
            found.setdefault(port, set()).add(pid)
    return {port: sorted(pids) for port, pids in found.items() if pids}


def _force_stop_ports() -> dict[int, list[int]]:
    killed: dict[int, list[int]] = {}
    for port, pids in _listening_pids_by_port(DTAM_PORTS).items():
        for pid in pids:
            if _terminate_pid_tree(pid):
                killed.setdefault(port, []).append(pid)
    return killed


def cleanup_stale_stack(*, use_lifecycle: bool = True, settle_s: float = 0.35) -> dict[str, object]:
    """Stop any previously running local DTAM processes before a fresh start."""
    summary: dict[str, object] = {}

    # First use the OperationModule lifecycle service when available; it knows
    # how to stop child modules through the current IntegrationHub API.
    if use_lifecycle:
        console_root = ROOT / "OperationModule"
        if str(console_root) not in sys.path:
            sys.path.insert(0, str(console_root))
        try:
            from app.services.module_process_service import shutdown_modules_for_console_exit

            shutdown_modules_for_console_exit()
            summary["lifecycle_service"] = "ok"
        except Exception as exc:
            summary["lifecycle_service"] = f"skipped: {type(exc).__name__}: {exc}"
    else:
        summary["lifecycle_service"] = "skipped"

    processes = _windows_processes() if os.name == "nt" else []
    scripts = _force_stop_script_processes(processes)
    if scripts:
        summary["scripts"] = scripts
    unreal = _force_stop_unreal_processes(processes)
    if unreal:
        summary["unreal"] = unreal
    browsers = _force_stop_operation_browser_processes(processes)
    if browsers:
        summary["operation_browsers"] = browsers
    ports = _force_stop_ports()
    if ports:
        summary["ports"] = ports

    # Give Windows a short moment to release sockets and console handles.
    if settle_s > 0:
        time.sleep(settle_s)
    return summary


def _elapsed(start: float) -> str:
    return f"{time.perf_counter() - start:.2f}s"


def launch_console_window(
    name: str,
    cwd: Path,
    command: list[str],
    *,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.Popen:
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if env_overrides:
        env.update(env_overrides)
    if os.name == "nt":
        # Run the Python process directly. Avoid `cmd.exe /c ...` because that
        # creates a shell that appears to close/re-open while the stack starts.
        return subprocess.Popen(
            command,
            cwd=str(cwd),
            env=env,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
    return subprocess.Popen(command, cwd=str(cwd), env=env)


def launch_background_process(
    name: str,
    cwd: Path,
    command: list[str],
    log_name: str,
    *,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.Popen:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / log_name
    log_file = log_path.open("a", encoding="utf-8")
    log_file.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting {name}\n")
    log_file.flush()

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if env_overrides:
        env.update(env_overrides)
    creationflags = 0
    if os.name == "nt":
        creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )


def _is_port_open(host: str, port: int, timeout_s: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout_s):
            return True
    except OSError:
        return False


def wait_for_core_stack(proc: subprocess.Popen, timeout_s: float) -> bool:
    deadline = time.time() + max(float(timeout_s), 1.0)
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        if _is_port_open("127.0.0.1", 8095) and _is_port_open("127.0.0.1", 8096):
            return True
        time.sleep(0.25)
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start DTAM Core Server and Operations Console.")
    parser.add_argument("--python", default=sys.executable or "python", help="Python executable to use.")
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="Do not stop an already-running local DTAM stack before startup.",
    )
    parser.add_argument(
        "--new-windows",
        action="store_true",
        help="Launch CoreServer and OperationModule in separate console windows, then return.",
    )
    parser.add_argument(
        "--headless-server",
        action="store_true",
        help="Deprecated compatibility flag. Core/State server consoles are hidden by default.",
    )
    parser.add_argument(
        "--show-server-windows",
        action="store_true",
        help="Show Core/State server console windows for debugging.",
    )
    parser.add_argument("--core-timeout", type=float, default=30.0, help="Seconds to wait for Core/State startup.")
    return parser.parse_args()


def main() -> int:
    total_started_at = time.perf_counter()
    args = parse_args()
    python_exe = args.python

    print("[DTAM] Starting 2-Tier Architecture (WebSocket /ws/dtam)...")
    if not args.skip_cleanup:
        print("[DTAM] Stopping previous local DTAM stack...")
        stage_started_at = time.perf_counter()
        cleanup_summary = cleanup_stale_stack()
        print(f"[DTAM] Cleanup complete in {_elapsed(stage_started_at)}: {cleanup_summary}")

    # 1. Start Core Server (which auto-starts Simulation State)
    server_cmd = [
        python_exe,
        "DSE_main.py",
        "--no-browser",
    ]

    # 2. Start Operations Console
    console_cmd = [
        python_exe,
        "DOC_main.py",
        "--preserve-stack",
    ]

    if args.new_windows:
        launch_console_window(
            "DTAM Core Server",
            ROOT / "IntegrationHub" / "CoreServerModule",
            server_cmd,
            env_overrides={"DTAM_SHOW_SERVER_WINDOWS": "1"},
        )
        print("[DTAM] Waiting for Core/State ports before opening OperationModule...")
        stage_started_at = time.perf_counter()
        deadline = time.time() + max(float(args.core_timeout), 1.0)
        while time.time() < deadline:
            if _is_port_open("127.0.0.1", 8095) and _is_port_open("127.0.0.1", 8096):
                break
            time.sleep(0.25)
        print(f"[DTAM] Core/State wait finished in {_elapsed(stage_started_at)}.")
        launch_console_window(
            "DTAM Operations Console",
            ROOT / "OperationModule",
            console_cmd,
        )
        print("[DTAM] Launched Core Server and Operations Console in separate windows.")
        return 0

    server_headless = not args.show_server_windows
    if server_headless:
        print("[DTAM] Starting CoreServer in hidden background mode...")
        core_proc = launch_background_process(
            "DTAM Core Server",
            ROOT / "IntegrationHub" / "CoreServerModule",
            server_cmd,
            "start_dtam_core.log",
            env_overrides={"DTAM_SHOW_SERVER_WINDOWS": "0"},
        )
    else:
        print("[DTAM] Server console windows are visible (CoreServer + StateServer).")
        core_proc = launch_console_window(
            "DTAM Core Server",
            ROOT / "IntegrationHub" / "CoreServerModule",
            server_cmd,
            env_overrides={"DTAM_SHOW_SERVER_WINDOWS": "1"},
        )

    stage_started_at = time.perf_counter()
    if not wait_for_core_stack(core_proc, timeout_s=args.core_timeout):
        print(
            "[DTAM] Core/State startup failed or timed out. "
            f"Check log: {LOG_DIR / 'start_dtam_core.log'}"
            if server_headless
            else "[DTAM] Core/State startup failed or timed out. Check the visible server console windows."
        )
        cleanup_stale_stack(settle_s=0.2)
        return 1
    print(f"[DTAM] Core/State ready in {_elapsed(stage_started_at)}.")

    print("[DTAM] Core/State ready. Starting OperationModule in this console...")
    exit_code = 0
    interrupted = False
    try:
        exit_code = subprocess.call(console_cmd, cwd=str(ROOT / "OperationModule"))
    except KeyboardInterrupt:
        interrupted = True
        exit_code = 130
    finally:
        if interrupted:
            print("\n[DTAM] Interrupted. Cleaning up DTAM stack...")
        else:
            print("[DTAM] OperationModule exited. Cleaning up DTAM stack...")
        stage_started_at = time.perf_counter()
        cleanup_summary = cleanup_stale_stack(use_lifecycle=False, settle_s=0.15)
        print(f"[DTAM] Cleanup complete in {_elapsed(stage_started_at)}: {cleanup_summary}")
        print(f"[DTAM] Total Start_DTAM.py runtime: {_elapsed(total_started_at)}.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
