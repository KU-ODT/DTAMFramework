"""Phase 7 messages for operator/manual control."""
from __future__ import annotations

import dataclasses as _dc
from dataclasses import dataclass, field
from typing import Any, Dict, List


def _clamp_axis(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return max(-1.0, min(1.0, number))


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _as_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "y", "on", "active", "start"):
        return True
    if text in ("0", "false", "no", "n", "off", "inactive", "stop"):
        return False
    return bool(default)


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


@dataclass
class OperatorControlAxes:
    """Normalized four-axis manual control command."""

    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    throttle: float = 0.0

    @classmethod
    def from_wire(cls, data: Dict[str, Any] | None) -> "OperatorControlAxes":
        raw = data or {}
        return cls(
            roll=_clamp_axis(raw.get("roll")),
            pitch=_clamp_axis(raw.get("pitch")),
            yaw=_clamp_axis(raw.get("yaw")),
            throttle=_clamp_axis(raw.get("throttle")),
        )


@dataclass
class Msg5001_OperatorControlInput:
    """MSG 5001: operator keyboard/joystick/manual control input."""

    timestamp: str = ""
    aircraftId: str = "UAM0001"
    source: str = "api"          # keyboard | joystick | api | script
    controlMode: str = "keyboard"  # keyboard | joystick | manual | mission
    sequence: int = 0
    active: bool = True
    axes: OperatorControlAxes = field(default_factory=OperatorControlAxes)
    buttons: List[int] = field(default_factory=list)
    hats: List[List[int]] = field(default_factory=list)
    rawAxes: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_wire(cls, data: Dict[str, Any]) -> "Msg5001_OperatorControlInput":
        raw = data or {}
        axes_raw = raw.get("axes") if isinstance(raw.get("axes"), dict) else raw
        buttons_raw = raw.get("buttons") if isinstance(raw.get("buttons"), list) else []
        hats_raw = raw.get("hats") if isinstance(raw.get("hats"), list) else []
        raw_axes = raw.get("rawAxes") if isinstance(raw.get("rawAxes"), dict) else {}
        try:
            sequence = int(raw.get("sequence") or 0)
        except (TypeError, ValueError):
            sequence = 0
        buttons: List[int] = []
        for item in buttons_raw:
            try:
                buttons.append(int(item))
            except (TypeError, ValueError):
                continue

        hats: List[List[int]] = []
        for pair in hats_raw:
            if not isinstance(pair, (list, tuple)) or len(pair) < 2:
                continue
            try:
                hats.append([int(pair[0]), int(pair[1])])
            except (TypeError, ValueError):
                continue

        return cls(
            timestamp=str(raw.get("timestamp") or ""),
            aircraftId=str(raw.get("aircraftId") or raw.get("vehicleId") or "UAM0001"),
            source=str(raw.get("source") or "api"),
            controlMode=str(raw.get("controlMode") or raw.get("mode") or raw.get("source") or "keyboard"),
            sequence=sequence,
            active=_as_bool(raw.get("active"), True),
            axes=OperatorControlAxes.from_wire(axes_raw),
            buttons=buttons,
            hats=hats,
            rawAxes={str(k): _as_float(v) for k, v in raw_axes.items() if _is_number(v)},
        )

    def to_wire(self) -> Dict[str, Any]:
        return _dc.asdict(self)


@dataclass
class Msg5002_CameraControlCommand:
    """MSG 5002: visualization camera control command."""

    timestamp: str = ""
    aircraftId: str = "UAM0001"
    vehicleName: str = ""
    cameraName: str = "front_center"
    source: str = "joystick"
    action: str = "adjust"       # adjust | reset
    sequence: int = 0
    yawDeltaDeg: float = 0.0
    pitchDeltaDeg: float = 0.0
    focalLengthDelta: float = 0.0

    @classmethod
    def from_wire(cls, data: Dict[str, Any]) -> "Msg5002_CameraControlCommand":
        raw = data or {}
        try:
            sequence = int(raw.get("sequence") or 0)
        except (TypeError, ValueError):
            sequence = 0
        return cls(
            timestamp=str(raw.get("timestamp") or ""),
            aircraftId=str(raw.get("aircraftId") or raw.get("vehicleId") or "UAM0001"),
            vehicleName=str(raw.get("vehicleName") or raw.get("airsimVehicleName") or ""),
            cameraName=str(raw.get("cameraName") or raw.get("camera_name") or "front_center"),
            source=str(raw.get("source") or "joystick"),
            action=str(raw.get("action") or "adjust"),
            sequence=sequence,
            yawDeltaDeg=_as_float(raw.get("yawDeltaDeg") or raw.get("yaw_delta_deg")),
            pitchDeltaDeg=_as_float(raw.get("pitchDeltaDeg") or raw.get("pitch_delta_deg")),
            focalLengthDelta=_as_float(raw.get("focalLengthDelta") or raw.get("focal_length_delta")),
        )

    def to_wire(self) -> Dict[str, Any]:
        return _dc.asdict(self)


@dataclass
class AbnormalSituationPosition:
    """LLA center point for an abnormal situation / obstacle command."""

    lat: float = 37.56
    lon: float = 126.98
    alt: float = 120.0

    @classmethod
    def from_wire(cls, data: Dict[str, Any] | None) -> "AbnormalSituationPosition":
        raw = data or {}
        return cls(
            lat=_as_float(_first_present(raw.get("lat"), raw.get("latitude")), 37.56),
            lon=_as_float(_first_present(raw.get("lon"), raw.get("lng"), raw.get("longitude")), 126.98),
            alt=_as_float(_first_present(raw.get("alt"), raw.get("altitude"), raw.get("height")), 120.0),
        )


@dataclass
class Msg5003_AbnormalSituationCommand:
    """MSG 5003: operator abnormal situation / obstacle spawn command.

    The payload is intentionally generic so future abnormal types can share the
    same ICD.  Current first implementation uses ``abnormalType='bird_flock'``.
    """

    timestamp: str = ""
    commandId: str = "OBS-0001"
    action: str = "create"          # create | update | remove | clear
    abnormalType: str = "bird_flock"
    obstacleId: str = "bird_flock_001"
    position: AbnormalSituationPosition = field(default_factory=AbnormalSituationPosition)
    radiusM: float = 800.0
    count: int = 9
    headingDeg: float = 0.0
    speedMps: float = 12.0
    durationSec: float = 0.0
    severity: str = "warning"
    affectedAircraftIds: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_wire(cls, data: Dict[str, Any]) -> "Msg5003_AbnormalSituationCommand":
        raw = data or {}
        entity = raw.get("entity") if isinstance(raw.get("entity"), dict) else {}
        position_raw = raw.get("position")
        if not isinstance(position_raw, dict):
            position_raw = raw.get("center") if isinstance(raw.get("center"), dict) else {}
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        affected_raw = raw.get("affectedAircraftIds")
        if not isinstance(affected_raw, list):
            affected_raw = raw.get("affectedAircraft") if isinstance(raw.get("affectedAircraft"), list) else []
        try:
            count = int(raw.get("count") if raw.get("count") is not None else entity.get("count", 9))
        except (TypeError, ValueError):
            count = 9
        return cls(
            timestamp=str(raw.get("timestamp") or ""),
            commandId=str(raw.get("commandId") or raw.get("eventId") or raw.get("id") or "OBS-0001"),
            action=str(raw.get("action") or "create"),
            abnormalType=str(
                raw.get("abnormalType")
                or raw.get("obstacleType")
                or raw.get("eventType")
                or entity.get("type")
                or "bird_flock"
            ),
            obstacleId=str(raw.get("obstacleId") or raw.get("eventId") or raw.get("commandId") or "bird_flock_001"),
            position=AbnormalSituationPosition.from_wire(position_raw),
            radiusM=max(1.0, _as_float(_first_present(raw.get("radiusM"), raw.get("radius"), raw.get("radius_m")), 800.0)),
            count=max(1, count),
            headingDeg=_as_float(_first_present(raw.get("headingDeg"), raw.get("heading"), raw.get("heading_deg")), 0.0),
            speedMps=max(0.1, _as_float(_first_present(raw.get("speedMps"), raw.get("speed_mps"), entity.get("speedMps")), 12.0)),
            durationSec=max(0.0, _as_float(_first_present(raw.get("durationSec"), raw.get("duration_s"), raw.get("duration")), 0.0)),
            severity=str(raw.get("severity") or "warning"),
            affectedAircraftIds=[str(item) for item in affected_raw if str(item).strip()],
            metadata=metadata,
        )

    def to_wire(self) -> Dict[str, Any]:
        return _dc.asdict(self)


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False
