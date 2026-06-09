"""
VFDS Dynamics Dispatch System — Dispatch Queue

asyncio 기반 비동기 디스패치 큐.
다중 기체 운용 시 병목을 방지하기 위해 Aircraft ID 단위로 개별 Queue와 워커를 관리한다.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable, Optional

from .models import DispatchResult, DispatchStatus
from .scheduler import schedule_for_mission, schedule_seconds_for_mission
from .sim_time import SimulationClock, format_hhmmss

logger = logging.getLogger(__name__)


class DispatchQueue:
    """
    비동기 미션 디스패치 큐 (Multi-Aircraft 지원).

    Aircraft ID별로 Queue를 동적으로 생성하여 병렬 처리를 지원하면서,
    동일 기체에 대해서는 순차 처리(FIFO)를 보장한다.
    """

    def __init__(
        self,
        *,
        schedule_enabled: bool = True,
        schedule_timezone: str = "Asia/Seoul",
        schedule_time_field: str = "departure.std",
        schedule_lead_sec: float = 300.0,
        simulation_clock: SimulationClock | None = None,
    ):
        # aircraft_id -> Queue mapping
        self._queues: dict[str, asyncio.Queue[DispatchResult]] = {}
        # aircraft_id -> Task mapping
        self._workers: dict[str, asyncio.Task] = {}
        # mission_id -> DispatchResult mapping (for status lookups)
        self._results_by_mission: dict[str, DispatchResult] = {}
        # FPN -> DispatchResult mapping (legacy lookup support)
        self._results_by_fpn: dict[int, DispatchResult] = {}
        
        self._on_dispatch: Optional[Callable[[DispatchResult], Awaitable[None]]] = None
        self._schedule_enabled = schedule_enabled
        self._schedule_timezone = schedule_timezone
        self._schedule_time_field = schedule_time_field
        self._schedule_lead_sec = max(0.0, schedule_lead_sec)
        self._simulation_clock = simulation_clock

    async def put(self, result: DispatchResult) -> None:
        """미션을 적절한 기체 큐에 적재하고 필요 시 워커를 구동한다."""
        self._register_result(result)
        queue = self._get_or_create_queue(result.aircraft_id)
        await queue.put(result)
        logger.info(
            "Queued mission FP%d (MissionId: %s) for aircraft %s",
            result.flight_plan_number,
            result.mission_id,
            result.aircraft_id,
        )

    def put_nowait(self, result: DispatchResult) -> None:
        """동기적으로 큐에 적재한다."""
        self._register_result(result)
        queue = self._get_or_create_queue(result.aircraft_id)
        queue.put_nowait(result)
        
    def _register_result(self, result: DispatchResult) -> None:
        self._results_by_mission[result.mission_id] = result
        self._results_by_fpn[result.flight_plan_number] = result

    def _get_or_create_queue(self, aircraft_id: str) -> asyncio.Queue[DispatchResult]:
        if aircraft_id not in self._queues:
            self._queues[aircraft_id] = asyncio.Queue()
            if self._on_dispatch is not None:
                self._workers[aircraft_id] = asyncio.create_task(self._worker_loop(aircraft_id))
                logger.info("Started dedicated worker for aircraft %s", aircraft_id)
        return self._queues[aircraft_id]

    def get_status(self, mission_id: str) -> Optional[DispatchResult]:
        """Mission ID 기반 조회"""
        return self._results_by_mission.get(mission_id)

    def get_status_by_fpn(self, flight_plan_number: int) -> Optional[DispatchResult]:
        """FPN 기반 조회 (이전 버전 호환용)"""
        return self._results_by_fpn.get(flight_plan_number)

    def list_all(self) -> list[DispatchResult]:
        """모든 디스패치 결과를 반환한다."""
        return list(self._results_by_mission.values())

    @property
    def pending_count(self) -> int:
        """전체 처리 대기 중인 미션 수"""
        return sum(q.qsize() for q in self._queues.values())

    def set_handler(self, handler: Callable[[DispatchResult], Awaitable[None]]) -> None:
        """핸들러 등록"""
        self._on_dispatch = handler
        # 이미 큐는 만들어졌는데 워커가 안 뜬 경우 일괄 시작
        for aircraft_id in self._queues.keys():
            if aircraft_id not in self._workers:
                self._workers[aircraft_id] = asyncio.create_task(self._worker_loop(aircraft_id))

    async def start_worker(self) -> None:
        """(하위 호환) 워커 시작. 실제 워커는 put 호출 시 동적 생성됨"""
        pass

    async def stop_worker(self) -> None:
        """모든 기체 워커를 중지한다."""
        for aircraft_id, task in self._workers.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._workers.clear()
        logger.info("All dispatch queue workers stopped")

    async def _worker_loop(self, aircraft_id: str) -> None:
        """기체 전용 워커 메인 루프"""
        queue = self._queues[aircraft_id]
        while True:
            result = await queue.get()
            try:
                if self._on_dispatch:
                    self._record_schedule_metadata(result)
                    result.status = DispatchStatus.COMPILING
                    await self._on_dispatch(result)
                else:
                    logger.warning(
                        "No dispatch handler registered. Mission FP%d skipped.", 
                        result.flight_plan_number
                    )
            except Exception as e:
                result.status = DispatchStatus.FAILED
                result.error_message = str(e)
                logger.error(
                    "Dispatch failed for FP%d: %s",
                    result.flight_plan_number, e
                )
            finally:
                queue.task_done()

    def _record_schedule_metadata(self, result: DispatchResult) -> None:
        if not self._schedule_enabled:
            return

        if self._simulation_clock is not None:
            scheduled_sec, dispatch_sec, scheduled_value = schedule_seconds_for_mission(
                result.mission,
                time_field=self._schedule_time_field,
                lead_sec=self._schedule_lead_sec,
            )
            result.scheduled_start_at = format_hhmmss(scheduled_sec)
            result.scheduled_arm_at = format_hhmmss(dispatch_sec)
            result.schedule_field = self._schedule_time_field
            result.schedule_lead_sec = self._schedule_lead_sec
            logger.info(
                "Mission FP%d schedule recorded: arm at %s before mission start %s (%s=%s). "
                "Pipeline starts now so VFDS/PX4 telemetry can be received while the mission script waits.",
                result.flight_plan_number,
                format_hhmmss(dispatch_sec),
                format_hhmmss(scheduled_sec),
                self._schedule_time_field,
                scheduled_value,
            )
            return

        schedule = schedule_for_mission(
            result.mission,
            timezone_name=self._schedule_timezone,
            time_field=self._schedule_time_field,
            lead_sec=self._schedule_lead_sec,
        )
        result.scheduled_start_at = schedule.scheduled_at.isoformat()
        result.scheduled_arm_at = schedule.dispatch_at.isoformat()
        result.schedule_field = schedule.source_field
        result.schedule_lead_sec = schedule.lead_sec
        logger.info(
            "Mission FP%d schedule recorded: arm at %s before start %s (%s, %.1fs from now). "
            "Pipeline starts now so telemetry can be received while the mission script waits.",
            result.flight_plan_number,
            schedule.dispatch_at.isoformat(),
            schedule.scheduled_at.isoformat(),
            schedule.source_field,
            schedule.delay_sec,
        )
