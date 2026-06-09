"""Simulation Setup (MSG 1002) 스키마."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .common import (
    Field,
    ISO_DATETIME_PATTERN,
    validate_field,
)


# ===== 열거형 =====
PLAYBACK_SPEEDS = [1, 2, 4, 8]
PLAY_STATES = ["play", "pause", "reset"]
PRECIPITATION_TYPES = ["none", "rainy", "snow"]
WIND_GRADES = ["normal", "warning", "serious"]


# ===== 필드 정의 =====

TOP_FIELDS: Dict[str, Field] = {
    "timestamp":     Field("iso_datetime", "UTC", "송신 시각",     "Send time",       pattern=ISO_DATETIME_PATTERN),
    "playbackSpeed": Field("int", "x",            "재생 배속",     "Playback speed",  choices=PLAYBACK_SPEEDS),
    "playState":     Field("str", "",             "재생 상태",     "Play state",      choices=PLAY_STATES),
}

PRECIPITATION_FIELDS: Dict[str, Field] = {
    "type":      Field("str",   "",      "강수 유형", "Precipitation type", choices=PRECIPITATION_TYPES),
    "intensity": Field("float", "0..1",  "강수 세기", "Precipitation intensity (0.1 step)", range=(0.0, 1.0)),
}

FOG_FIELDS: Dict[str, Field] = {
    "intensity": Field("float", "0..1", "안개 세기 (0=자동비활)", "Fog intensity (0=off, 0.1 step)", range=(0.0, 1.0)),
}

WIND_TOP_FIELDS: Dict[str, Field] = {
    "grade": Field("str", "", "바람 등급", "Wind grade", choices=WIND_GRADES),
}

GUST_FIELDS: Dict[str, Field] = {
    "lat":    Field("float", "deg", "위도",        "Latitude",  range=(-90.0, 90.0)),
    "lon":    Field("float", "deg", "경도",        "Longitude", range=(-180.0, 180.0)),
    "radius": Field("float", "m",   "돌풍 반경",   "Gust radius", range=(0.0, 50000.0)),
}


# ===== 내부 헬퍼 =====

def _check_step_01(val: Any, path: str, errors: List[str]) -> None:
    """0.1 스텝 검증 (float 오차 1e-6 허용)."""
    if not isinstance(val, (int, float)) or isinstance(val, bool):
        return  # 타입 검증은 validate_field 가 별도로
    scaled = val * 10.0
    if abs(scaled - round(scaled)) > 1e-6:
        errors.append(f"{path}: 0.1 단위 필요 (got {val})")


def _validate_dict_section(obj: Dict[str, Any], key: str, fields: Dict[str, Field],
                           errors: List[str], root: str) -> bool:
    sec = obj.get(key)
    if sec is None:
        errors.append(f"{root}: 누락")
        return False
    if not isinstance(sec, dict):
        errors.append(f"{root}: dict 필요")
        return False
    for fname, fspec in fields.items():
        if fname not in sec:
            errors.append(f"{root}.{fname}: 누락")
            continue
        validate_field(sec[fname], fspec, f"{root}.{fname}", errors)
    return True


def _validate_weather(obj: Dict[str, Any], errors: List[str]) -> None:
    we = obj.get("weatherEffect")
    if we is None:
        errors.append("weatherEffect: 누락")
        return
    if not isinstance(we, dict):
        errors.append("weatherEffect: dict 필요")
        return
    # precipitation
    if _validate_dict_section(we, "precipitation", PRECIPITATION_FIELDS, errors, "weatherEffect.precipitation"):
        prec = we["precipitation"]
        _check_step_01(prec.get("intensity"), "weatherEffect.precipitation.intensity", errors)
        # type=none 이면 intensity=0 이어야 함
        if prec.get("type") == "none" and prec.get("intensity", 0) != 0:
            errors.append("weatherEffect.precipitation: type=none 은 intensity=0 이어야 함")
    # fog
    if _validate_dict_section(we, "fog", FOG_FIELDS, errors, "weatherEffect.fog"):
        _check_step_01(we["fog"].get("intensity"), "weatherEffect.fog.intensity", errors)


def _validate_wind(obj: Dict[str, Any], errors: List[str]) -> None:
    wind = obj.get("wind")
    if wind is None:
        errors.append("wind: 누락")
        return
    if not isinstance(wind, dict):
        errors.append("wind: dict 필요")
        return
    for fname, fspec in WIND_TOP_FIELDS.items():
        if fname not in wind:
            errors.append(f"wind.{fname}: 누락")
            continue
        validate_field(wind[fname], fspec, f"wind.{fname}", errors)
    # gust 는 optional — 있으면 필드 전부 검증
    if "gust" in wind:
        gust = wind["gust"]
        if not isinstance(gust, dict):
            errors.append("wind.gust: dict 필요")
            return
        for fname, fspec in GUST_FIELDS.items():
            if fname not in gust:
                errors.append(f"wind.gust.{fname}: 누락 (gust 존재 시 필수)")
                continue
            validate_field(gust[fname], fspec, f"wind.gust.{fname}", errors)


def validate_message(obj: Any) -> Tuple[bool, List[str], Dict[str, Any]]:
    errors: List[str] = []
    if not isinstance(obj, dict):
        return False, ["root: dict 필요"], {}

    if "mainVehicleController" in obj:
        errors.append("mainVehicleController: MSG 1002에서 허용되지 않음")

    for name, fspec in TOP_FIELDS.items():
        if name not in obj:
            errors.append(f"{name}: 누락")
            continue
        validate_field(obj[name], fspec, name, errors)

    _validate_weather(obj, errors)
    _validate_wind(obj, errors)

    return (len(errors) == 0), errors, obj
