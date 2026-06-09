"""VFDS Dynamics Mission Dispatch entrypoint.

Assembles the mission receive, validate, compile, upload, and status pipeline,
then runs the FastAPI server.
"""

from __future__ import annotations

import atexit
import logging
import os
from pathlib import Path

import uvicorn
import yaml

from .compiler.assembler import Assembler
from .dispatcher.aircraft_registry import AircraftRegistry
from .dispatcher.dispatch_queue import DispatchQueue
from .dispatcher.dispatcher import Dispatcher
from .dispatcher.sim_time import SimulationClock
from .pipeline import MissionPipeline
from .receiver.file_watcher import FileWatcher
from .receiver.http_server import create_app
from .status.normalizer import register_home
from .uploader.uploader import Uploader


# VehicleModule.app.domain.vfds_dynamics package root.
PACKAGE_ROOT = Path(__file__).resolve().parent


def load_config(config_path: str | Path) -> dict:
    """Load the server configuration YAML."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _resolve_package_path(path_value: str | Path) -> Path:
    """Resolve relative config paths from the vfds_dynamics package root."""
    path = Path(path_value)
    return path if path.is_absolute() else PACKAGE_ROOT / path


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("vfds_dynamics")

    config_dir = Path(os.environ.get("DTAM_VFDS_DYNAMICS_CONFIG_DIR", PACKAGE_ROOT / "config"))
    config = load_config(config_dir / "server_config.yaml")

    server_cfg = config.get("server", {})
    fw_cfg = config.get("file_watcher", {})
    scheduler_cfg = config.get("mission_scheduler", {})

    registry = AircraftRegistry.from_yaml(config_dir / "aircraft_registry.yaml")
    logger.info("Aircraft registry loaded: %d aircraft", registry.count)

    for target in registry.list_all():
        register_home(target.aircraft_id, target.home_lat, target.home_lon, target.home_alt)
        logger.info(
            "HOME registered: %s (%.6f, %.6f, %.1f)",
            target.aircraft_id,
            target.home_lat,
            target.home_lon,
            target.home_alt,
        )

    simulation_clock = SimulationClock()
    queue = DispatchQueue(
        schedule_enabled=bool(scheduler_cfg.get("enabled", True)),
        schedule_timezone=str(scheduler_cfg.get("timezone", "Asia/Seoul")),
        schedule_time_field=str(scheduler_cfg.get("time_field", "departure.std")),
        schedule_lead_sec=float(scheduler_cfg.get("arming_lead_sec", 300)),
        simulation_clock=simulation_clock,
    )
    dispatcher = Dispatcher(registry=registry, queue=queue)

    script_dir = _resolve_package_path(config.get("output", {}).get("script_dir", "./output"))
    assembler = Assembler(output_dir=script_dir)
    uploader = Uploader(auto_execute=True, auto_launch_sitl=True)
    pipeline = MissionPipeline(
        assembler=assembler,
        uploader=uploader,
        mission_start_field=str(scheduler_cfg.get("time_field", "departure.std")),
        arming_lead_sec=float(scheduler_cfg.get("arming_lead_sec", 300)),
    )

    queue.set_handler(pipeline.handle)

    # Clean up stale remote processes before accepting new missions.
    unique_hosts = {}
    for target in registry.list_all():
        if target.send_host not in unique_hosts:
            unique_hosts[target.send_host] = target

    for hostname, target in unique_hosts.items():
        if hostname not in ["localhost", "127.0.0.1"]:
            pipeline.cleanup_remote_host(target)

    file_watcher = None
    if fw_cfg.get("enabled", False):
        inbox_path = _resolve_package_path(fw_cfg.get("inbox_path", "./inbox"))
        file_watcher = FileWatcher(inbox_path=inbox_path, dispatcher=dispatcher)
        file_watcher.start()
        logger.info("File watcher enabled: %s", inbox_path)

    app = create_app(dispatcher, pipeline=pipeline, simulation_clock=simulation_clock)
    host = os.environ.get("DTAM_VFDS_HOST") or server_cfg.get("host", "0.0.0.0")
    port = int(os.environ.get("DTAM_VFDS_PORT") or server_cfg.get("port", 8098))

    logger.info("Starting HTTP server on %s:%d", host, port)

    def _shutdown_cleanup() -> None:
        logger.info("=== Shutdown cleanup: stopping all remote SITL sessions ===")
        pipeline.stop_all_active_sitls()
        for hostname, target in unique_hosts.items():
            if hostname not in ["localhost", "127.0.0.1"]:
                try:
                    pipeline.cleanup_remote_host(target)
                except Exception as exc:
                    logger.warning("Shutdown cleanup failed for %s: %s", hostname, exc)

    atexit.register(_shutdown_cleanup)

    try:
        uvicorn.run(app, host=host, port=port)
    finally:
        _shutdown_cleanup()
        if file_watcher:
            file_watcher.stop()


if __name__ == "__main__":
    main()
