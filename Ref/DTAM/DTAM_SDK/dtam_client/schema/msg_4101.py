"""Camera Image Frame (MSG 4101) 스키마 — 헤더 JSON 검증."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .common import (
    VEHICLE_ID_PATTERN,
    VEHICLE_ID_REGEX,
    Field,
    ISO_DATETIME_PATTERN,
    validate_field,
)


IMAGE_TYPES = [
    "scene", "depth_planar", "depth_perspective", "depth_vis",
    "segmentation", "surface_normals", "infrared",
    "optical_flow", "optical_flow_vis",
]

PIXEL_FORMATS = ["rgb8", "rgba8", "gray8", "gray16", "float32", "vector2_float32"]

ENCODINGS = ["jpeg", "png", "raw", "depth_png"]

CAMERA_NAMES = [
    "front_center", "front_left", "front_right",
    "bottom_center", "back_center",
]

TOP_FIELDS: Dict[str, Field] = {
    "message_id":   Field("int", "",    "메시지 ID",       "Message ID",        range=(4101, 4101)),
    "message_name": Field("str", "",    "메시지 이름",     "Message name",      choices=["Camera Image Frame"]),
    "timestamp":    Field("iso_datetime", "UTC", "촬영 시각", "Capture time",  pattern=ISO_DATETIME_PATTERN),
    "vehicle_id":   Field("str", "",    "비행체 ID",       "Vehicle ID",        pattern=VEHICLE_ID_PATTERN),
    "camera_name":  Field("str", "",    "카메라 이름",     "Camera name"),
    "image_type":   Field("str", "",    "이미지 유형",     "Image type",        choices=IMAGE_TYPES),
    "sequence":     Field("int", "",    "프레임 번호",     "Frame sequence",    range=(0, 4_294_967_295)),
    "width":        Field("int", "px",  "이미지 너비",     "Image width",       range=(1, 65535)),
    "height":       Field("int", "px",  "이미지 높이",     "Image height",      range=(1, 65535)),
    "channels":     Field("int", "",    "채널 수",         "Channel count",     range=(1, 255)),
    "pixel_format": Field("str", "",    "픽셀 형식",       "Pixel format",      choices=PIXEL_FORMATS),
    "encoding":     Field("str", "",    "인코딩 방식",     "Encoding",          choices=ENCODINGS),
    "payload_size": Field("int", "B",   "바이너리 크기",   "Payload byte size", range=(0, 4_294_967_295)),
}

OPTIONAL_FIELDS: Dict[str, Field] = {
    "checksum": Field("str", "", "체크섬", "Checksum"),
    "unit":     Field("str", "", "단위",   "Physical unit"),
    "frame_id": Field("str", "", "프레임 ID", "Frame identifier"),
}


def validate_header(obj: Any) -> Tuple[bool, List[str], Dict[str, Any]]:
    """헤더 JSON 검증. _image_base64 등 내부 필드는 무시."""
    errors: List[str] = []
    if not isinstance(obj, dict):
        return False, ["root: dict 필요"], {}

    for name, fspec in TOP_FIELDS.items():
        if name not in obj:
            errors.append(f"{name}: 누락")
            continue
        validate_field(obj[name], fspec, name, errors)

    # optional fields — 있으면 타입만 검사
    for name, fspec in OPTIONAL_FIELDS.items():
        if name in obj:
            validate_field(obj[name], fspec, name, errors)

    # vehicle_id regex
    vid = obj.get("vehicle_id", "")
    if isinstance(vid, str) and vid and not VEHICLE_ID_REGEX.match(vid):
        errors.append(f"vehicle_id: 패턴 불일치 ({VEHICLE_ID_PATTERN})")

    return (len(errors) == 0), errors, obj


# validate_message alias (registry 호환)
validate_message = validate_header
