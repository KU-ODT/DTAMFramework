"""Server forwarding policy mirrored in the SDK for subscription calculation.
"""
from __future__ import annotations

from typing import Dict, List

from .identity import Role


# Registration handling
# Registration handling
FORWARD_RULES: Dict[str, List[Role]] = {
    "0001": [Role.MONITORING],                                                           # Phase 0
    "0002": [Role.MONITORING],                                                           # Phase 0
    "0003": [Role.VEHICLE, Role.VISUAL],                                                 # Phase 5 (1Hz)
    "1001": [Role.SIM_STATE],                                                            # Phase 1
    "1002": [Role.VEHICLE, Role.VISUAL, Role.SIM_STATE],                                 # Phase 4
    "1003": [Role.SIM_STATE, Role.VISUAL],                                                # Phase 1
    "2001": [Role.MISSION],                                                              # Phase 2
    "2002": [Role.MISSION, Role.MONITORING, Role.VEHICLE, Role.VISUAL, Role.SITUATION_AWARENESS],  # Phase 3
    "3001": [Role.VEHICLE, Role.VISUAL],                                                 # Phase 2
    "3002": [Role.VEHICLE],                                                              # Phase 6
    "3003": [Role.VEHICLE, Role.MISSION],                                                # Phase 6 (PSU 발행분을 Mission 도 수신 — plan 정합성 추적)
    "4001": [Role.MONITORING, Role.VISUAL, Role.SITUATION_AWARENESS, Role.PSU],          # Phase 5
    "4002": [Role.MONITORING, Role.SITUATION_AWARENESS, Role.PSU],                       # Phase 5
    "4101": [Role.MONITORING, Role.SITUATION_AWARENESS],                                 # Phase 5
    "4102": [Role.MONITORING, Role.SITUATION_AWARENESS],                                 # Phase 5
    "4103": [Role.VEHICLE, Role.MONITORING, Role.SITUATION_AWARENESS],                    # Phase 5
    "5001": [Role.VEHICLE],                                                              # Phase 7
    "5002": [Role.VISUAL],                                                               # Phase 7
    "5003": [Role.VISUAL],                                                               # Phase 7
    "5004": [Role.VEHICLE, Role.VISUAL, Role.PSU, Role.MISSION, Role.MONITORING, Role.SITUATION_AWARENESS],  # Phase 7 (데모 날씨 — 전 모듈 바람 영향 공유)
}


def subscriptions_for(role: Role | str) -> List[str]:
    """Internal helper."""
    target = Role(role) if isinstance(role, str) else role
    return sorted({
        mid for mid, targets in FORWARD_RULES.items()
        if target in targets
    })


__all__ = ["FORWARD_RULES", "subscriptions_for"]
