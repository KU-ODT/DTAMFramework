"""Scheduled Flight (MSG 3001) ?쒕뜡 ?곗씠???앹꽦湲?"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from dtam_client.schema.msg_3001 import PLAN_STATUSES, validate_message

# ?섑뵆 ??踰꾪떚?ы듃 醫뚰몴 (?ъ쓽?????좎떎 異?洹쇰갑)
_VERTIPORTS = [
    {"name": "Yeouido", "lat": 37.52545, "lon": 126.92142, "alt": 0.0},
    {"name": "Jamsil",  "lat": 37.51402, "lon": 127.10395, "alt": 0.0},
    {"name": "Gimpo",   "lat": 37.55830, "lon": 126.79060, "alt": 0.0},
    {"name": "Incheon", "lat": 37.46910, "lon": 126.45060, "alt": 0.0},
    {"name": "Gangnam", "lat": 37.49790, "lon": 127.02760, "alt": 0.0},
]


def _time_hms(total_sec: int) -> str:
    h = (total_sec // 3600) % 24
    m = (total_sec // 60) % 60
    s = total_sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _pick_two(items: List[Dict[str, Any]]) -> (Dict[str, Any], Dict[str, Any]):
    a, b = random.sample(items, 2)
    return a, b


def _lla(lat: float, lon: float, alt: float) -> Dict[str, float]:
    return {"lat": round(lat, 6), "lon": round(lon, 6), "alt": round(alt, 1)}


def _interp(a: Dict[str, float], b: Dict[str, float], t: float, alt: float) -> Dict[str, float]:
    return _lla(a["lat"] + (b["lat"] - a["lat"]) * t,
                a["lon"] + (b["lon"] - a["lon"]) * t,
                alt)


def _gen_enroute(dep: Dict[str, Any], arr: Dict[str, Any],
                 num_segments: int) -> List[Dict[str, Any]]:
    """?⑥닚 10-援ш컙 鍮꾪뻾 ?꾨줈?? 吏?곹솢二쇄넂?대쪠?믪긽?밟넂?쒗빆(?좏쉶1???믫븯媛뺚넂?묎렐?믪갑瑜쇺넂?쒖＜."""
    if num_segments < 2:
        num_segments = 2
    if num_segments > 20:
        num_segments = 20

    cruise_alt = round(random.uniform(150.0, 350.0), 1)
    segs: List[Dict[str, Any]] = []
    dep_pt = _lla(dep["lat"], dep["lon"], 0.0)
    arr_pt = _lla(arr["lat"], arr["lon"], 0.0)

    phases = [chr(ord("A") + i) for i in range(num_segments)]
    # ?좏쉶 援ш컙? 以묎컙易??섎굹
    turn_idx = num_segments // 2

    prev_end = dep_pt
    for i in range(num_segments):
        t0 = i / num_segments
        t1 = (i + 1) / num_segments
        # ?⑥닚 怨좊룄 ?꾨줈??
        if i == 0:
            alt_end = 0.0         # 吏?곹솢二?
        elif i == 1:
            alt_end = round(cruise_alt * 0.2, 1)  # ?대쪠
        elif i < turn_idx:
            alt_end = round(cruise_alt * min(1.0, 0.2 + 0.3 * (i - 1)), 1)  # ?곸듅
        elif i == turn_idx:
            alt_end = cruise_alt  # ?좏쉶 怨좊룄 ?좎?
        elif i < num_segments - 2:
            alt_end = round(cruise_alt * max(0.0, 1.0 - 0.3 * (i - turn_idx)), 1)  # ?섍컯
        elif i == num_segments - 2:
            alt_end = round(cruise_alt * 0.1, 1)  # ?묎렐
        else:
            alt_end = 0.0         # 李⑸쪠/?쒖＜

        end_pt = _interp(dep_pt, arr_pt, t1, alt_end)
        seg: Dict[str, Any] = {
            "seq": i + 1,
            "phase": phases[i],
            "startLLA": prev_end,
            "endLLA": end_pt,
            "targetSpeed": round(random.uniform(5.0, 80.0), 1),
        }
        if i == turn_idx:
            mid = _interp(dep_pt, arr_pt, (t0 + t1) / 2, cruise_alt)
            seg["turnDirection"] = random.choice(["CW", "CCW"])
            seg["centerLLA"] = mid
        segs.append(seg)
        prev_end = end_pt
    return segs


def generate(
    flight_plan_number: Optional[int] = None,
    plan_version: Optional[int] = None,
    plan_status: Optional[str] = None,
    aircraft_id: Optional[str] = None,
    num_segments: int = 11,
    validate: bool = True,
    **_ignored: Any,
) -> Dict[str, Any]:
    """?쒕뜡 3001 硫붿떆吏 ?앹꽦."""
    fpn = int(flight_plan_number) if flight_plan_number else random.randint(1000, 9999)
    pver = int(plan_version) if plan_version else random.randint(1, 5)
    pstat = plan_status if plan_status in PLAN_STATUSES else "active"
    acid = aircraft_id or f"UAM{random.randint(1, 9999):04d}"

    dep_port, arr_port = _pick_two(_VERTIPORTS)

    # ?쒓컖 ?????異쒕컻 09:00 ?꾪썑
    base = 9 * 3600
    std = base + random.randint(-1800, 1800)
    eobt = std + random.randint(60, 300)
    etot = eobt + random.randint(120, 600)
    sta = std + random.randint(1800, 4200)
    eldt = sta - random.randint(300, 900)
    eibt = sta - random.randint(60, 300)

    msg: Dict[str, Any] = {
        "flightPlanNumber": fpn,
        "planVersion": pver,
        "planStatus": pstat,
        "aircraftId": acid,
        "departure": {
            "vertiport": dep_port["name"],
            "std": _time_hms(std),
            "depGateNumber": f"G{random.randint(1, 9)}",
            "eobt": _time_hms(eobt),
            "depFatoNumber": f"F{random.randint(1, 4)}",
            "etot": _time_hms(etot),
        },
        "enRoute": _gen_enroute(dep_port, arr_port, num_segments),
        "arrival": {
            "vertiport": arr_port["name"],
            "sta": _time_hms(sta),
            "arrGateNumber": f"G{random.randint(1, 9)}",
            "eibt": _time_hms(eibt),
            "arrFatoNumber": f"F{random.randint(1, 4)}",
            "eldt": _time_hms(eldt),
        },
    }

    if validate:
        ok, errs, _ = validate_message(msg)
        if not ok:
            raise RuntimeError("3001 generator self-check ?ㅽ뙣: " + "; ".join(errs))
    return msg


if __name__ == "__main__":
    import json
    print(json.dumps(generate(), ensure_ascii=False, indent=2))

