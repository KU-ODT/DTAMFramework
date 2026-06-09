"""ICD 공통 타입 — 모든 메시지 dataclass에서 재사용."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class LLA:
    """위도/경도/고도 좌표."""
    lat: float = 0.0
    lon: float = 0.0
    alt: float = 0.0


@dataclass
class Vec3:
    """3축 벡터."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class Quaternion:
    """쿼터니언."""
    w: float = 1.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
