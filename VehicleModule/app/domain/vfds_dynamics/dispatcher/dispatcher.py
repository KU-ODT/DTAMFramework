"""
VFDS Dynamics Dispatch System — Dispatcher (메인 로직)

검증된 MissionPlan을 aircraftId 기준으로 분류하고,
Aircraft Registry에서 타겟을 resolve하여 디스패치 큐에 배정한다.
"""

from __future__ import annotations

import logging
from typing import Optional

from ..validator.models import MissionPlan
from ..validator.errors import SemanticValidationError, ValidationReport
from ..validator.schema_validator import SchemaValidator
from ..validator.semantic_validator import SemanticValidator

from .aircraft_registry import AircraftRegistry, UnknownAircraftError
from .dispatch_queue import DispatchQueue
from .models import AircraftStatus, DispatchResult, DispatchStatus

logger = logging.getLogger(__name__)


class DispatchError(Exception):
    """디스패치 과정에서 발생하는 에러"""
    pass


class Dispatcher:
    """
    Mission Dispatcher.

    전체 파이프라인을 조율한다:
    1. JSON 수신 → Schema Validator → Semantic Validator
    2. 검증 통과한 미션을 aircraftId로 레지스트리 조회
    3. DispatchResult 생성 → 큐에 적재
    """

    def __init__(
        self,
        registry: AircraftRegistry,
        queue: DispatchQueue,
    ):
        self._registry = registry
        self._queue = queue
        self._schema_validator = SchemaValidator()
        self._semantic_validator = SemanticValidator()

    def process_single(self, data: dict) -> DispatchResult | ValidationReport:
        """
        단건 미션 JSON을 수신하여 검증 → 디스패치한다.

        Returns:
            DispatchResult: 디스패치 성공
            ValidationReport: 검증 실패 시 에러 리포트
        """
        # 1) Schema 검증
        mission, schema_report = self._schema_validator.validate_single(data)
        if mission is None:
            return schema_report

        # 2) Semantic 검증
        semantic_report = self._semantic_validator.validate(mission)
        if not semantic_report.is_valid:
            return semantic_report

        # 3) 디스패치
        return self._dispatch(mission, semantic_report)

    def process_batch(self, data: list | dict) -> list[DispatchResult | ValidationReport]:
        """
        단건 또는 복수건 미션을 수신하여 검증 → 디스패치한다.
        """
        # Schema 검증 (단건/배치 자동 처리)
        schema_results = self._schema_validator.validate_batch(data)

        # 유효한 미션만 추출
        valid_missions: list[MissionPlan] = []
        output: list[DispatchResult | ValidationReport] = []
        valid_indices: list[int] = []

        for idx, (mission, report) in enumerate(schema_results):
            if mission is None:
                output.append(report)
            else:
                valid_missions.append(mission)
                output.append(None)  # placeholder
                valid_indices.append(idx)

        # Semantic 검증 (배치 유일성 포함)
        if valid_missions:
            semantic_reports = self._semantic_validator.validate_batch(valid_missions)

            for i, (mission, sem_report) in enumerate(zip(valid_missions, semantic_reports)):
                out_idx = valid_indices[i]
                if not sem_report.is_valid:
                    output[out_idx] = sem_report
                else:
                    result = self._dispatch(mission, sem_report)
                    output[out_idx] = result

        return output

    def _dispatch(
        self, mission: MissionPlan, report: ValidationReport
    ) -> DispatchResult | ValidationReport:
        """
        검증 통과한 미션을 항공기에 배정한다.

        1. aircraftId로 레지스트리 조회
        2. 항공기 가용 상태 확인
        3. DispatchResult 생성 → 큐에 적재
        """
        aircraft_id = mission.aircraftId

        # 레지스트리 조회
        try:
            target = self._registry.get(aircraft_id)
        except UnknownAircraftError as e:
            report.add_error(
                SemanticValidationError(
                    rule="DISPATCH",
                    field_path="aircraftId",
                    message=str(e),
                )
            )
            return report

        # 가용 상태 확인
        if target.status != AircraftStatus.AVAILABLE:
            logger.warning(
                "Aircraft %s is %s, queuing anyway.",
                aircraft_id, target.status.value
            )

        # DispatchResult 생성
        result = DispatchResult(
            aircraft_id=aircraft_id,
            mission=mission,
            target=target,
            status=DispatchStatus.QUEUED,
        )

        # 큐에 적재 (동기)
        self._queue.put_nowait(result)

        logger.info(
            "Dispatched FP%d → %s (%s:%d)",
            mission.flightPlanNumber,
            aircraft_id,
            target.connection_string,
            target.mavsdk_port,
        )

        return result

    @property
    def registry(self) -> AircraftRegistry:
        return self._registry

    @property
    def queue(self) -> DispatchQueue:
        return self._queue
