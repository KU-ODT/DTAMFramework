"""
Mission Dispatch System — Semantic Validator

Schema 검증(Pydantic) 통과 후, ICD v1 §6의 비즈니스 로직 규칙을 검증한다.
"""

from __future__ import annotations

import math
from typing import Optional

from .errors import SemanticValidationError, ValidationReport
from .models import MissionPlan, PhaseCode


# ──────────────────────────── 상수 ────────────────────────────

# 좌표 연속성 허용 오차 (ICD v1 §6.9)
COORD_TOLERANCE_LAT = 0.0001   # ~11m
COORD_TOLERANCE_LON = 0.0001   # ~8m (위도 37° 기준)
COORD_TOLERANCE_ALT = 1.0      # 1m

# 유효 Phase 코드
VALID_PHASES = frozenset(PhaseCode)


class SemanticValidator:
    """
    ICD v1 §6 기반 Semantic 검증기.

    Schema 검증이 통과된 MissionPlan 객체를 입력받아
    비즈니스 로직 위반 여부를 검사한다.
    """

    def validate(self, mission: MissionPlan) -> ValidationReport:
        """
        단건 MissionPlan에 대해 모든 Semantic 규칙을 검증한다.

        Returns:
            ValidationReport — 검증 결과 (errors가 비어있으면 유효)
        """
        report = ValidationReport(
            flight_plan_number=mission.flightPlanNumber
        )

        self._check_seq_continuity(mission, report)
        self._check_phase_validity(mission, report)
        self._check_coordinate_continuity(mission, report)
        self._check_time_ordering(mission, report)

        return report

    def validate_batch(self, missions: list[MissionPlan]) -> list[ValidationReport]:
        """
        복수 MissionPlan에 대해 개별 검증 + 배치 검증을 수행한다.
        """
        reports = []

        # 개별 검증
        for mission in missions:
            reports.append(self.validate(mission))

        # 배치 검증: flightPlanNumber 유일성 (ICD §6.1)
        self._check_batch_uniqueness(missions, reports)

        return reports

    # ────────────────── ICD §6.1: flightPlanNumber 유일성 ──────────────────

    def _check_batch_uniqueness(
        self, missions: list[MissionPlan], reports: list[ValidationReport]
    ) -> None:
        """배치 내 flightPlanNumber 중복 검사"""
        seen: dict[int, int] = {}
        for idx, mission in enumerate(missions):
            fpn = mission.flightPlanNumber
            if fpn in seen:
                reports[idx].add_error(
                    SemanticValidationError(
                        rule="ICD-6.1",
                        field_path="flightPlanNumber",
                        message=(
                            f"Duplicate flightPlanNumber {fpn} "
                            f"(first seen at index {seen[fpn]})"
                        ),
                        expected="unique within batch",
                        actual=str(fpn),
                    )
                )
            else:
                seen[fpn] = idx

    # ────────────────── ICD §6.2: seq 연속성 ──────────────────

    def _check_seq_continuity(
        self, mission: MissionPlan, report: ValidationReport
    ) -> None:
        """seq가 1부터 시작하는 연속 정수인지 검증"""
        for i, seg in enumerate(mission.enRoute):
            expected_seq = i + 1
            if seg.seq != expected_seq:
                report.add_error(
                    SemanticValidationError(
                        rule="ICD-6.2",
                        field_path=f"enRoute[{i}].seq",
                        message=(
                            f"seq must be consecutive starting from 1. "
                            f"Expected {expected_seq}, got {seg.seq}."
                        ),
                        expected=str(expected_seq),
                        actual=str(seg.seq),
                    )
                )

    # ────────────────── ICD §6.3: Phase 유효성 ──────────────────

    def _check_phase_validity(
        self, mission: MissionPlan, report: ValidationReport
    ) -> None:
        """phase 코드가 정의된 코드({A..K})에 포함되는지 검증"""
        # Pydantic의 PhaseCode enum이 이미 대부분 걸러주지만,
        # 방어적으로 다시 한번 확인
        for i, seg in enumerate(mission.enRoute):
            if seg.phase not in VALID_PHASES:
                report.add_error(
                    SemanticValidationError(
                        rule="ICD-6.3",
                        field_path=f"enRoute[{i}].phase",
                        message=(
                            f"Invalid phase code '{seg.phase}'. "
                            f"Must be one of {sorted(p.value for p in PhaseCode)}."
                        ),
                        expected="A~K",
                        actual=str(seg.phase),
                    )
                )

    # ────────────────── ICD §6.9: 좌표 연속성 ──────────────────

    def _check_coordinate_continuity(
        self, mission: MissionPlan, report: ValidationReport
    ) -> None:
        """
        이전 세그먼트의 endLLA와 다음 세그먼트의 startLLA가
        허용 오차 내에서 연속인지 검증한다.
        """
        segments = mission.enRoute
        for i in range(len(segments) - 1):
            prev_end = segments[i].endLLA
            next_start = segments[i + 1].startLLA

            gaps = []
            if abs(prev_end.lat - next_start.lat) > COORD_TOLERANCE_LAT:
                gaps.append(
                    f"lat gap={abs(prev_end.lat - next_start.lat):.6f}"
                )
            if abs(prev_end.lon - next_start.lon) > COORD_TOLERANCE_LON:
                gaps.append(
                    f"lon gap={abs(prev_end.lon - next_start.lon):.6f}"
                )
            if abs(prev_end.alt - next_start.alt) > COORD_TOLERANCE_ALT:
                gaps.append(
                    f"alt gap={abs(prev_end.alt - next_start.alt):.1f}m"
                )

            if gaps:
                report.add_error(
                    SemanticValidationError(
                        rule="ICD-6.9",
                        field_path=f"enRoute[{i}].endLLA → enRoute[{i+1}].startLLA",
                        message=(
                            f"Coordinate discontinuity between segment "
                            f"seq={segments[i].seq} and seq={segments[i+1].seq}: "
                            f"{', '.join(gaps)}"
                        ),
                        severity="warning",  # ICD에서 '원칙'이므로 warning
                    )
                )

    # ────────────────── ICD §6.6: 시간 순서 ──────────────────

    def _check_time_ordering(
        self, mission: MissionPlan, report: ValidationReport
    ) -> None:
        """
        시간 순서 권장 검증: std <= eobt <= etot <= eldt <= eibt <= sta
        ICD에서 '권장'이므로 severity는 warning으로 처리한다.
        """
        dep = mission.departure
        arr = mission.arrival

        time_chain = [
            ("departure.std",  dep.std),
            ("departure.eobt", dep.eobt),
            ("departure.etot", dep.etot),
            ("arrival.eldt",   arr.eldt),
            ("arrival.eibt",   arr.eibt),
            ("arrival.sta",    arr.sta),
        ]

        for i in range(len(time_chain) - 1):
            curr_name, curr_val = time_chain[i]
            next_name, next_val = time_chain[i + 1]

            if curr_val > next_val:
                report.add_error(
                    SemanticValidationError(
                        rule="ICD-6.6",
                        field_path=f"{curr_name} → {next_name}",
                        message=(
                            f"Time ordering violation: "
                            f"{curr_name}={curr_val} > {next_name}={next_val}. "
                            f"Expected {curr_name} <= {next_name}."
                        ),
                        severity="warning",
                        expected=f"{curr_val} <= {next_val}",
                        actual=f"{curr_val} > {next_val}",
                    )
                )
