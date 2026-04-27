"""서버 라우팅·포워딩 정책.

서버(DTAM_SimulationState) 가 권위적으로 사용하지만, 클라이언트도 자기
``subscriptions`` 를 미리 계산할 수 있도록 SDK 안에 같이 둡니다.

이전에 ``DTAM_CoreServer/app/model/message.py:FORWARD_RULES`` 에 있던 표를
SDK 단일 표로 옮긴 것입니다.
"""
from __future__ import annotations

from typing import Dict, List

from .identity import Role


# 메시지 ID → 서버가 forwarding 할 역할 목록.
# 시퀀스 다이어그램(`DTAM_CoreServer/app/web/data/sequence_diagram.json`) 기준.
FORWARD_RULES: Dict[str, List[Role]] = {
    "0001": [Role.MONITORING],                                                           # Phase 0
    "0002": [Role.MONITORING],                                                           # Phase 0
    "0003": [Role.VEHICLE, Role.VISUAL],                                                 # Phase 5 (1Hz)
    "1001": [Role.SIM_STATE],                                                            # Phase 1
    "1002": [Role.VEHICLE, Role.VISUAL, Role.SIM_STATE],                                 # Phase 4
    "1003": [Role.SIM_STATE],                                                            # Phase 1
    "2001": [Role.MISSION],                                                              # Phase 2
    "2002": [Role.MISSION, Role.MONITORING, Role.VEHICLE, Role.VISUAL],                  # Phase 3
    "3001": [Role.VEHICLE],                                                              # Phase 2
    "3002": [Role.VEHICLE],                                                              # Phase 6
    "3003": [Role.VEHICLE],                                                              # Phase 6
    "4001": [Role.MONITORING, Role.VISUAL],                                              # Phase 5
    "4101": [Role.MONITORING],                                                           # Phase 5
}


def subscriptions_for(role: Role | str) -> List[str]:
    """주어진 역할이 서버로부터 forwarding 받을 메시지 mid 목록."""
    target = Role(role) if isinstance(role, str) else role
    return sorted({
        mid for mid, targets in FORWARD_RULES.items()
        if target in targets
    })


__all__ = ["FORWARD_RULES", "subscriptions_for"]
