"""
VFDS Dynamics Dispatch System — 검증 에러 정의

Schema 검증과 Semantic 검증에서 발생하는 에러 타입 및
검증 결과를 집계하는 ValidationReport를 제공한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ValidationError:
    """개별 검증 에러 1건"""
    rule: str                       # 위반 규칙 ID (예: "ICD-6.2")
    field_path: str                 # 위반 필드 경로 (예: "enRoute[3].seq")
    message: str                    # 사람이 읽을 수 있는 에러 메시지
    severity: str = "error"         # "error" | "warning"


@dataclass
class SchemaValidationError(ValidationError):
    """Pydantic 모델 파싱 단계에서 발생하는 구조적 에러"""
    pydantic_error_type: Optional[str] = None   # Pydantic 내부 에러 타입


@dataclass
class SemanticValidationError(ValidationError):
    """비즈니스 로직 검증에서 발생하는 의미적 에러"""
    expected: Optional[str] = None  # 기대값
    actual: Optional[str] = None    # 실제값


@dataclass
class ValidationReport:
    """
    검증 결과 집계 보고서.

    하나의 MissionPlan (또는 배치)에 대한 모든 에러를 수집한다.
    """
    flight_plan_number: Optional[int] = None
    errors: list[ValidationError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """에러가 없으면 유효"""
        return not any(e.severity == "error" for e in self.errors)

    @property
    def error_count(self) -> int:
        return sum(1 for e in self.errors if e.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for e in self.errors if e.severity == "warning")

    def add_error(self, error: ValidationError) -> None:
        self.errors.append(error)

    def to_dict(self) -> dict:
        """API 응답용 직렬화"""
        return {
            "status": "valid" if self.is_valid else "error",
            "flightPlanNumber": self.flight_plan_number,
            "errorCount": self.error_count,
            "warningCount": self.warning_count,
            "errors": [
                {
                    "rule": e.rule,
                    "field": e.field_path,
                    "message": e.message,
                    "severity": e.severity,
                }
                for e in self.errors
            ],
        }
