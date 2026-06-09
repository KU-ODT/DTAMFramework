"""
VFDS Dynamics Dispatch System — Schema Validator

Pydantic v2 모델을 사용하여 ICD v1 JSON의 구조적 유효성을 검증한다.
단건/복수건 JSON을 모두 처리한다.
"""

from __future__ import annotations

import json
from typing import Union

from pydantic import ValidationError as PydanticValidationError

from .errors import SchemaValidationError, ValidationReport
from .models import MissionPlan


class SchemaValidator:
    """
    ICD v1 §4 구조 기반 Schema 검증기.

    Pydantic 모델 파싱을 통해 필드 존재/타입/범위를 자동 검증한다.
    """

    def validate_single(self, data: dict) -> tuple[MissionPlan | None, ValidationReport]:
        """
        단건 Mission JSON을 검증한다.

        Returns:
            (MissionPlan | None, ValidationReport)
            - 성공 시: (MissionPlan, report.is_valid=True)
            - 실패 시: (None, report with errors)
        """
        report = ValidationReport(
            flight_plan_number=data.get("flightPlanNumber")
        )

        try:
            mission = MissionPlan.model_validate(data)
            return mission, report
        except PydanticValidationError as e:
            for err in e.errors():
                field_path = self._format_field_path(err.get("loc", ()))
                report.add_error(
                    SchemaValidationError(
                        rule="SCHEMA",
                        field_path=field_path,
                        message=err.get("msg", "Unknown schema error"),
                        pydantic_error_type=err.get("type"),
                    )
                )
            return None, report

    def validate_batch(
        self, data: Union[dict, list]
    ) -> list[tuple[MissionPlan | None, ValidationReport]]:
        """
        단건 또는 복수건 Mission JSON을 검증한다.

        - dict → 단건 처리
        - list → 각 원소를 개별 검증
        """
        if isinstance(data, dict):
            return [self.validate_single(data)]

        if not isinstance(data, list):
            report = ValidationReport()
            report.add_error(
                SchemaValidationError(
                    rule="SCHEMA",
                    field_path="(root)",
                    message="Payload must be a JSON object or array of objects.",
                )
            )
            return [(None, report)]

        results = []
        for idx, item in enumerate(data):
            if not isinstance(item, dict):
                report = ValidationReport()
                report.add_error(
                    SchemaValidationError(
                        rule="SCHEMA",
                        field_path=f"[{idx}]",
                        message=f"Array element [{idx}] must be a JSON object.",
                    )
                )
                results.append((None, report))
            else:
                results.append(self.validate_single(item))
        return results

    def validate_json_string(
        self, raw: str
    ) -> list[tuple[MissionPlan | None, ValidationReport]]:
        """
        JSON 문자열을 파싱 후 검증한다.
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            report = ValidationReport()
            report.add_error(
                SchemaValidationError(
                    rule="JSON_PARSE",
                    field_path="(root)",
                    message=f"Invalid JSON: {e.msg} at line {e.lineno} col {e.colno}",
                )
            )
            return [(None, report)]

        return self.validate_batch(data)

    @staticmethod
    def _format_field_path(loc: tuple) -> str:
        """Pydantic loc tuple → 사람이 읽기 쉬운 필드 경로 문자열"""
        parts = []
        for segment in loc:
            if isinstance(segment, int):
                parts.append(f"[{segment}]")
            else:
                if parts:
                    parts.append(f".{segment}")
                else:
                    parts.append(str(segment))
        return "".join(parts) if parts else "(root)"
