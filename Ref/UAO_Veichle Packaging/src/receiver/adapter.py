"""
Mission Dispatch System — JSON Adapter Layer

상위 시스템(Operator, Traffic Sim 등)에서 전송하는 Mission JSON 형식을
내부 Canonical 포맷(Mission ICD v1)으로 변환하는 어댑터.
"""
import copy
from typing import Any

class OperatorPayloadAdapter:
    @staticmethod
    def adapt(payload: dict[str, Any]) -> dict[str, Any]:
        """
        Operator JSON을 Canonical ICD v1 JSON으로 변환합니다.
        
        지금은 Operator JSON이 이미 Canonical Format을 준수한다고 가정하고
        Passthrough 구조로 작성되어 있습니다. 상위 시스템 인터페이스가
        변경될 경우 이 메서드에서 LLA, Time, Speed 등을 추출하여
        {"flightPlanNumber": ..., "departure": {...}, ...} 로 재조립합니다.
        """
        # 만약 payload가 이미 ICD v1과 호환된다면 변경 없이 반환
        if "flightPlanNumber" in payload and "departure" in payload and "enRoute" in payload:
            return copy.deepcopy(payload)
            
        # TODO: "LLA", "Time", "Speed", "Phase" 등의 플랫한 구조로 들어올 경우
        # departure, enRoute, arrival 객체로 조립하는 로직 구현
        # 현재는 들어온 payload를 그대로 반환하여 SchemaValidator 단계로 넘깁니다.
        return copy.deepcopy(payload)

    @staticmethod
    def adapt_batch(payload_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [OperatorPayloadAdapter.adapt(p) for p in payload_list]
