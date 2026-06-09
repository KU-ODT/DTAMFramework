"""
Mission Dispatch System Pipeline

Dispatcher Queue, Compiler, Uploader를 연결하는 파이프라인 핸들러.
DispatchQueue.set_handler()에 등록되어 자동 처리를 담당한다.
"""

from __future__ import annotations

import asyncio
import logging
import socket

from src.compiler.mission_to_ir import mission_to_ir
from src.compiler.assembler import Assembler
from src.dispatcher.models import DispatchResult, DispatchStatus
from src.status.normalizer import register_home
from src.uploader.uploader import Uploader

logger = logging.getLogger(__name__)


class MissionPipeline:
    """
    전체 미션 처리 파이프라인.

    DispatchResult를 받아서
    1. MissionPlan -> IR 변환
    2. IR -> Python 스크립트 컴파일
    3. 스크립트를 대상 항공기에 업로드/실행

    upload()는 동기 블로킹 호출(WSL subprocess 등)이므로
    run_in_executor()로 감싸서 이벤트 루프를 차단하지 않는다.
    """

    def __init__(
        self,
        assembler: Assembler,
        uploader: Uploader,
        arc_points: int = 12,
        mission_start_field: str = "departure.std",
        arming_lead_sec: float = 300.0,
    ):
        self._assembler = assembler
        self._uploader = uploader
        self._arc_points = arc_points
        self._mission_start_field = mission_start_field
        self._arming_lead_sec = arming_lead_sec
        self._uao_host = self._detect_local_ip()
        self._active_results: list[DispatchResult] = []  # set 대신 list 사용

    def _detect_local_ip(self) -> str:
        """현재 서버의 외부 연결 가능한 IP를 감지한다."""
        try:
            # 더미 소켓을 열어 라우팅 테이블에서 사용 중인 로컬 IP 확인
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    async def handle(self, result: DispatchResult) -> None:
        """DispatchQueue worker가 호출하는 비동기 핸들러."""
        try:
            result.status = DispatchStatus.COMPILING
            logger.info(
                "Compiling FP%d for %s...",
                result.flight_plan_number,
                result.aircraft_id,
            )

            ir = mission_to_ir(
                result.mission,
                connection_string=result.target.connection_string,
                arc_points=self._arc_points,
                uao_host=self._uao_host,
                mission_start_field=self._mission_start_field,
                arming_lead_sec=self._arming_lead_sec,
            )
            register_home(result.aircraft_id, ir.home_lat, ir.home_lon, ir.home_alt)
            logger.info(
                "HOME updated from mission: %s (%.6f, %.6f, %.1f)",
                result.aircraft_id,
                ir.home_lat,
                ir.home_lon,
                ir.home_alt,
            )
            script_path = self._assembler.compile(ir)
            result.compiled_script_path = script_path
            result.status = DispatchStatus.COMPILED

            logger.info(
                "Compiled: %s -> %s",
                result.aircraft_id,
                script_path.name,
            )

            result.status = DispatchStatus.UPLOADING
            logger.info(
                "Uploading FP%d to %s (protocol: %s, mode: %s)...",
                result.flight_plan_number,
                result.aircraft_id,
                result.target.send_protocol,
                result.target.execution_mode,
            )

            # 동기 블로킹 upload()를 executor에서 실행하여 이벤트 루프를 보호한다.
            loop = asyncio.get_running_loop()
            upload_result = await loop.run_in_executor(
                None,
                self._uploader.upload,
                script_path,
                result.target,
                result.flight_plan_number,
                (ir.home_lat, ir.home_lon, ir.home_alt),
            )

            if upload_result.success:
                if upload_result.execution_result and upload_result.execution_result.success:
                    result.status = DispatchStatus.EXECUTING
                    logger.info(
                        "Executing: FP%d -> %s (PID: %s)",
                        result.flight_plan_number,
                        upload_result.deployed_path,
                        upload_result.execution_result.pid,
                    )
                    # 추적 리스트에 추가
                    if result not in self._active_results:
                        self._active_results.append(result)
                    # 원격 SITL이 기동된 경우 미션 완료 후 자동 종료한다.
                    if upload_result.sitl_result and upload_result.sitl_result.success:
                        asyncio.create_task(self._watch_and_stop_sitl(result))
                else:
                    result.status = DispatchStatus.UPLOADED
                    logger.info(
                        "Uploaded: FP%d -> %s",
                        result.flight_plan_number,
                        upload_result.deployed_path,
                    )
            else:
                result.status = DispatchStatus.FAILED
                result.error_message = upload_result.message
                logger.error(
                    "Upload failed: FP%d -> %s",
                    result.flight_plan_number,
                    upload_result.message,
                )

        except Exception as e:
            result.status = DispatchStatus.FAILED
            result.error_message = str(e)
            logger.error(
                "Pipeline failed for FP%d: %s",
                result.flight_plan_number,
                e,
                exc_info=True,
            )

    async def _watch_and_stop_sitl(self, result: DispatchResult) -> None:
        """미션이 COMPLETED 또는 FAILED 상태가 되면 원격 SITL을 종료한다."""
        _TERMINAL = {DispatchStatus.COMPLETED, DispatchStatus.FAILED}
        _POLL_SEC = 5.0
        _TIMEOUT_SEC = 1800  # 30분 초과 시 포기

        elapsed = 0.0
        while result.status not in _TERMINAL and elapsed < _TIMEOUT_SEC:
            await asyncio.sleep(_POLL_SEC)
            elapsed += _POLL_SEC

        if elapsed >= _TIMEOUT_SEC:
            logger.warning(
                "FP%d SITL cleanup timed out after %.0fs — stopping anyway.",
                result.flight_plan_number,
                _TIMEOUT_SEC,
            )

        logger.info(
            "FP%d mission ended (%s) — stopping remote SITL for %s.",
            result.flight_plan_number,
            result.status.value,
            result.aircraft_id,
        )
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, lambda: self._uploader.stop_sitl_remote(result.target))
        finally:
            # 작업이 끝났으므로 추적 리스트에서 제거
            if result in self._active_results:
                self._active_results.remove(result)

    def stop_all_active_sitls(self):
        """현재 실행 중인 모든 원격 SITL을 강제로 종료한다. (서버 종료 시 호출)"""
        if not self._active_results:
            return

        logger.info("Shutting down %d active SITL sessions...", len(self._active_results))
        for result in list(self._active_results):
            try:
                logger.info("Emergency stop: %s (FP%d)", result.aircraft_id, result.flight_plan_number)
                self._uploader.stop_sitl_remote(result.target)
            except Exception as e:
                logger.error("Failed to stop SITL for %s: %s", result.aircraft_id, e)
        self._active_results.clear()

    def cleanup_remote_host(self, target):
        """특정 원격 호스트의 모든 잔류 시뮬레이션 및 미션 프로세스를 강제 종료한다."""
        logger.info("Performing nuclear cleanup on remote host: %s", target.send_host)
        # 미션 스크립트, PX4, VFDS 모두 정리
        patterns = [
            ".*UAM.*.py",
            "px4",
            "run_vehicle_multi.py",
            "vfds",
            "mavsdk_server",
            "mission_dispatch_mavlink_forwarder_14550",
        ]
        for pattern in patterns:
            try:
                self._uploader.stop_sitl_remote(target, stop_pattern=pattern)
            except Exception as e:
                logger.warning("Cleanup failed for pattern %s on %s: %s", pattern, target.send_host, e)
