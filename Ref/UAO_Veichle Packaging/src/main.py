"""
Mission Dispatch System — 진입점 (main.py)

모든 레이어를 조합하여 서버를 실행한다.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import uvicorn
import yaml

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.dispatcher.aircraft_registry import AircraftRegistry
from src.dispatcher.dispatch_queue import DispatchQueue
from src.dispatcher.dispatcher import Dispatcher
from src.dispatcher.sim_time import SimulationClock
from src.receiver.http_server import create_app
from src.receiver.file_watcher import FileWatcher
from src.compiler.assembler import Assembler
from src.pipeline import MissionPipeline
from src.uploader.uploader import Uploader
from src.status.normalizer import register_home


def load_config(config_path: str | Path) -> dict:
    """서버 설정 YAML 로드"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    # ── 로깅 설정 ──
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("mission_dispatch")

    # ── Config 로드 ──
    config_dir = PROJECT_ROOT / "config"
    config = load_config(config_dir / "server_config.yaml")

    server_cfg = config.get("server", {})
    fw_cfg = config.get("file_watcher", {})
    scheduler_cfg = config.get("mission_scheduler", {})

    # ── Aircraft Registry 로드 ──
    registry = AircraftRegistry.from_yaml(config_dir / "aircraft_registry.yaml")
    logger.info("Aircraft registry loaded: %d aircraft", registry.count)

    # ── NED→LLA 변환용 HOME 좌표 등록 ──
    for target in registry.list_all():
        register_home(target.aircraft_id, target.home_lat, target.home_lon, target.home_alt)
        logger.info(
            "HOME registered: %s (%.6f, %.6f, %.1f)",
            target.aircraft_id, target.home_lat, target.home_lon, target.home_alt,
        )

    # ── Dispatcher & Pipeline 초기화 ──
    simulation_clock = SimulationClock()
    queue = DispatchQueue(
        schedule_enabled=bool(scheduler_cfg.get("enabled", True)),
        schedule_timezone=str(scheduler_cfg.get("timezone", "Asia/Seoul")),
        schedule_time_field=str(scheduler_cfg.get("time_field", "departure.std")),
        schedule_lead_sec=float(scheduler_cfg.get("arming_lead_sec", 300)),
        simulation_clock=simulation_clock,
    )
    dispatcher = Dispatcher(registry=registry, queue=queue)

    script_dir = config.get("output", {}).get("script_dir", "./output")
    assembler = Assembler(output_dir=Path(script_dir))
    uploader = Uploader(auto_execute=True, auto_launch_sitl=True)
    pipeline = MissionPipeline(
        assembler=assembler,
        uploader=uploader,
        mission_start_field=str(scheduler_cfg.get("time_field", "departure.std")),
        arming_lead_sec=float(scheduler_cfg.get("arming_lead_sec", 300)),
    )

    queue.set_handler(pipeline.handle)

    # ── [IMPORTANT] 서버 시작 시 원격지 잔류 프로세스 강제 클린업 ──
    unique_hosts = {}
    for target in registry.list_all():
        if target.send_host not in unique_hosts:
            unique_hosts[target.send_host] = target
    
    for hostname, target in unique_hosts.items():
        if hostname not in ["localhost", "127.0.0.1"]:
            pipeline.cleanup_remote_host(target)
    
    # ── File Watcher 시작 (선택적) ──
    file_watcher = None
    if fw_cfg.get("enabled", False):
        inbox_path = fw_cfg.get("inbox_path", "./inbox")
        file_watcher = FileWatcher(inbox_path=inbox_path, dispatcher=dispatcher)
        file_watcher.start()
        logger.info("File watcher enabled: %s", inbox_path)

    # ── FastAPI 서버 실행 ──
    app = create_app(dispatcher, pipeline=pipeline, simulation_clock=simulation_clock)
    host = server_cfg.get("host", "0.0.0.0")
    port = server_cfg.get("port", 8000)

    logger.info("Starting HTTP server on %s:%d", host, port)

    # 종료 시 원격 SITL 클린업을 보장하는 함수
    def _shutdown_cleanup():
        logger.info("=== Shutdown cleanup: stopping all remote SITL sessions ===")
        pipeline.stop_all_active_sitls()
        # 추적 리스트에 없더라도 등록된 모든 원격 호스트를 한 번 더 청소
        for hostname, target in unique_hosts.items():
            if hostname not in ["localhost", "127.0.0.1"]:
                try:
                    pipeline.cleanup_remote_host(target)
                except Exception as e:
                    logger.warning("Shutdown cleanup failed for %s: %s", hostname, e)

    # 시그널 핸들러 등록 (Ctrl+C, IDE 종료 등)
    import signal
    import atexit
    atexit.register(_shutdown_cleanup)

    try:
        uvicorn.run(app, host=host, port=port)
    finally:
        _shutdown_cleanup()
        if file_watcher:
            file_watcher.stop()


if __name__ == "__main__":
    main()
