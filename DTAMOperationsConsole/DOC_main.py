"""Run the DTAM Operations Console web app."""
from __future__ import annotations

import argparse
import atexit
import _thread
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parent
FRAMEWORK_ROOT = ROOT.parent
DTAM_SDK_ROOT = FRAMEWORK_ROOT / "DTAM_SDK"
APP_IMPORT = "backend.app.main:app"

if str(DTAM_SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(DTAM_SDK_ROOT))

from dtam_client.ports import find_available_tcp_port  # noqa: E402


_shutdown_once = threading.Event()


def shutdown_modules_best_effort() -> None:
    if _shutdown_once.is_set():
        return
    _shutdown_once.set()
    try:
        from backend.app.services.module_process_service import shutdown_modules_for_console_exit

        shutdown_modules_for_console_exit()
    except Exception:
        pass


def register_shutdown_hooks() -> None:
    atexit.register(shutdown_modules_best_effort)

    def _handle_signal(signum, _frame) -> None:
        shutdown_modules_best_effort()
        raise KeyboardInterrupt

    for sig_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, _handle_signal)
        except Exception:
            pass


class ManagedBrowserSession:
    def __init__(
        self,
        process: subprocess.Popen[bytes],
        profile_dir: Path,
        *,
        cleanup_profile: bool = True,
        min_watch_seconds: float = 4.0,
        on_exit: Callable[[], None] | None = None,
    ) -> None:
        self._process = process
        self._profile_dir = profile_dir
        self._cleanup_profile = cleanup_profile
        self._min_watch_seconds = float(min_watch_seconds)
        self._started_at = time.monotonic()
        self._on_exit = on_exit
        self._closing = threading.Event()
        self._watcher = threading.Thread(target=self._watch, name="dtam-browser-watch", daemon=True)
        self._watcher.start()

    def _watch(self) -> None:
        try:
            self._process.wait()
        finally:
            lifetime_s = time.monotonic() - self._started_at
            self._cleanup_profile_dir()
            if lifetime_s < self._min_watch_seconds:
                print(
                    "[DTAMOperationsConsole] browser process exited immediately; "
                    "keeping the server running."
                )
                return
            if not self._closing.is_set() and self._on_exit is not None:
                self._on_exit()

    def close(self) -> None:
        if self._closing.is_set():
            return
        self._closing.set()
        _terminate_process_tree(self._process.pid)
        try:
            self._process.wait(timeout=5.0)
        except Exception:
            pass
        self._cleanup_profile_dir()

    def _cleanup_profile_dir(self) -> None:
        if self._cleanup_profile:
            shutil.rmtree(self._profile_dir, ignore_errors=True)


def _terminate_process_tree(pid: int) -> None:
    if pid <= 0:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10.0,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
        return

    try:
        os.kill(pid, 15)
    except OSError:
        return


def find_fullscreen_browser() -> Path | None:
    candidate_commands = ("msedge", "chrome", "chromium", "brave")
    for command in candidate_commands:
        resolved = shutil.which(command)
        if resolved:
            return Path(resolved)

    candidate_paths = (
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("LocalAppData", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("LocalAppData", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
    )
    for path in candidate_paths:
        if path.is_file():
            return path

    return None


def open_fullscreen_browser(url: str, *, on_exit: Callable[[], None] | None = None) -> ManagedBrowserSession | None:
    browser_path = find_fullscreen_browser()
    if browser_path:
        profile_root = FRAMEWORK_ROOT / ".dtam_runtime" / "operations_console_browser"
        profile_root.mkdir(parents=True, exist_ok=True)
        profile_dir = profile_root / f"profile-{os.getpid()}-{int(time.time() * 1000)}"
        profile_dir.mkdir(parents=True, exist_ok=True)
        process = subprocess.Popen(
            [
                str(browser_path),
                f"--user-data-dir={profile_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-session-crashed-bubble",
                "--disable-infobars",
                "--new-window",
                "--start-fullscreen",
                f"--app={url}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return ManagedBrowserSession(process, profile_dir, cleanup_profile=True, on_exit=on_exit)

    print("[DTAMOperationsConsole] fullscreen browser launch unavailable; close detection is disabled.")
    webbrowser.open(url)
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DTAM Operations Console")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind.")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on.")
    parser.add_argument("--target-ip", default="127.0.0.1", help="DTAM Core/State server target IP.")
    parser.add_argument("--ws-port", type=int, default=8096, help="DTAM SimulationState WebSocket/REST port.")
    parser.add_argument("--reload", action="store_true", help="Enable Uvicorn auto-reload.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser window.")
    parser.add_argument(
        "--preserve-stack",
        action="store_true",
        help="Do not clean an already-running local Core/State stack on startup.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    browser_session: ManagedBrowserSession | None = None

    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    os.environ["DTAM_TARGET_IP"] = str(args.target_ip)
    os.environ["DTAM_WS_PORT"] = str(args.ws_port)

    try:
        if args.preserve_stack:
            from backend.app.services.module_process_service import cleanup_stale_module_processes_for_console_start

            cleanup_stale_module_processes_for_console_start()
        else:
            shutdown_modules_best_effort()
            _shutdown_once.clear()
    except Exception:
        pass

    requested_port = int(args.port)
    args.port = find_available_tcp_port(args.host, requested_port)
    if args.port != requested_port:
        print(f"[DTAMOperationsConsole] port {requested_port} is busy; using {args.port}.")

    url = f"http://{args.host}:{args.port}"
    print(f"[DTAMOperationsConsole] GUI : {url}")
    print(f"[DTAMOperationsConsole] root: {ROOT}")

    if not args.no_browser:
        def launch_browser() -> None:
            nonlocal browser_session
            browser_session = open_fullscreen_browser(
                url,
                on_exit=lambda: (shutdown_modules_best_effort(), _thread.interrupt_main()),
            )

        threading.Timer(1.0, launch_browser).start()

    try:
        import uvicorn
        register_shutdown_hooks()

        uvicorn.run(
            APP_IMPORT,
            host=args.host,
            port=args.port,
            reload=args.reload,
            reload_dirs=[str(ROOT)] if args.reload else None,
        )
    finally:
        shutdown_modules_best_effort()
        if browser_session is not None:
            browser_session.close()


if __name__ == "__main__":
    main()
