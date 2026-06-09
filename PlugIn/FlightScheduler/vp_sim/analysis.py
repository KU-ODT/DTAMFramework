from __future__ import annotations

from typing import Any

from .simulation import get_simulation_snapshot

CHART_COLORS = {
    "preLanding": "#af52de",
    "landingFatoHold": "#ff9f0a",
    "landingGroundWait": "#c78100",
    "departureGroundWait": "#0a84ff",
    "otherWait": "#6f7b88",
}


def build_simulation_analysis(result: dict[str, Any], options: dict[str, Any] | None = None) -> dict[str, Any]:
    options = options or {}
    duration_seconds = float(result.get("durationSeconds") or 0)
    bucket_minutes = options.get("bucketMinutes") or choose_bucket_minutes(duration_seconds)
    bucket_seconds = bucket_minutes * 60
    bucket_count = max(1, int((duration_seconds + bucket_seconds - 1) // bucket_seconds))
    buckets = [
        {
            "start": index * bucket_seconds,
            "end": min((index + 1) * bucket_seconds, duration_seconds),
            "takeoff": 0,
            "landing": 0,
            "total": 0,
        }
        for index in range(bucket_count)
    ]

    fato_stats: dict[str, dict[str, Any]] = {}
    fato_usage_intervals: dict[str, list[tuple[float, float]]] = {}
    gate_stats: dict[str, dict[str, Any]] = {}
    wait_breakdown = create_wait_breakdown()
    completed_aircraft = 0
    completed_landings = 0
    total_wait_seconds = 0.0

    for item in result.get("aircraft", []):
        fato = ensure_fato_stats(fato_stats, item.get("fatoId"))
        gate = ensure_gate_stats(gate_stats, item.get("gateId"))
        wait_seconds = sum(
            max(0.0, segment["end"] - segment["start"])
            for segment in item.get("segments", [])
            if segment.get("state") == "waiting"
        )

        for segment in item.get("segments", []):
            add_fato_usage_interval(fato_usage_intervals, item.get("fatoId"), segment, duration_seconds)

        if item.get("completionTime", 0) <= duration_seconds:
            completed_aircraft += 1
            if item.get("kind") == "landing":
                completed_landings += 1
            total_wait_seconds += wait_seconds
            add_wait_breakdown(wait_breakdown, item)

            if item.get("kind") == "departure":
                fato["takeoff"] += 1
                gate["departure"] += 1
            if item.get("kind") == "landing":
                fato["landing"] += 1
                gate["landing"] += 1
            fato["waitSeconds"] += wait_seconds
            fato["completed"] += 1
            gate["waitSeconds"] += wait_seconds
            gate["completed"] += 1

            bucket_index = min(bucket_count - 1, int(item["completionTime"] // bucket_seconds))
            bucket = buckets[bucket_index]
            if item.get("kind") == "departure":
                bucket["takeoff"] += 1
            if item.get("kind") == "landing":
                bucket["landing"] += 1
            bucket["total"] += 1

    sample_step_seconds = choose_sample_step_seconds(duration_seconds)
    samples = []
    time_value = 0.0
    while time_value <= duration_seconds:
        snapshot = get_simulation_snapshot(result, time_value)
        samples.append({
            "time": time_value,
            "active": snapshot["stats"]["activeAircraft"],
            "queued": snapshot["stats"]["queuedAircraft"],
            "throughput": snapshot["stats"]["totalThroughput"],
        })
        time_value += sample_step_seconds
    if not samples or samples[-1]["time"] != duration_seconds:
        snapshot = get_simulation_snapshot(result, duration_seconds)
        samples.append({
            "time": duration_seconds,
            "active": snapshot["stats"]["activeAircraft"],
            "queued": snapshot["stats"]["queuedAircraft"],
            "throughput": snapshot["stats"]["totalThroughput"],
        })

    fato_busy_seconds = {
        fato_id: merged_duration_seconds(intervals)
        for fato_id, intervals in fato_usage_intervals.items()
    }
    facts = sorted([
        {
            **item,
            "total": item["takeoff"] + item["landing"],
            "averageWaitSeconds": item["waitSeconds"] / item["completed"] if item["completed"] else 0,
            "busySeconds": fato_busy_seconds.get(item["fatoId"], 0),
            "utilizationPercent": (fato_busy_seconds.get(item["fatoId"], 0) / duration_seconds * 100) if duration_seconds else 0,
        }
        for item in fato_stats.values()
    ], key=lambda item: (-item["total"], -item["averageWaitSeconds"]))
    gate_facts = sorted([
        {
            **item,
            "total": item["departure"] + item["landing"],
            "averageWaitSeconds": item["waitSeconds"] / item["completed"] if item["completed"] else 0,
        }
        for item in gate_stats.values()
    ], key=lambda item: (-item["total"], -item["averageWaitSeconds"]))

    peak_bucket = max(buckets, key=lambda bucket: bucket["total"])
    peak_active = max((sample["active"] for sample in samples), default=0)
    peak_queued = max((sample["queued"] for sample in samples), default=0)
    average_active = average([sample["active"] for sample in samples])
    average_queued = average([sample["queued"] for sample in samples])
    end_sample = samples[-1] if samples else {"active": 0, "queued": 0}
    bottleneck = max(facts, key=lambda item: (item["averageWaitSeconds"], item["total"]), default=None)
    max_utilization_fato = max(facts, key=lambda item: item["utilizationPercent"], default=None)
    total_throughput = sum(bucket["total"] for bucket in buckets)
    duration_hours = duration_seconds / 3600

    actual_slots = build_actual_slot_schedule(result)
    recommended_slots = build_recommended_slot_schedule(actual_slots)
    adjusted_landing_slots = [
        slot for slot in recommended_slots
        if slot.get("kind") == "landing" and slot.get("adjusted")
    ]
    recommended_saved_hold_seconds = sum(max(0.0, slot.get("savedHoldSeconds") or 0) for slot in adjusted_landing_slots)
    schedulable_landing_wait_seconds = wait_breakdown["preLandingSlot"] + recommended_saved_hold_seconds
    adjusted_wait_savings_seconds = min(total_wait_seconds, schedulable_landing_wait_seconds)
    adjusted_total_wait_seconds = max(0.0, total_wait_seconds - adjusted_wait_savings_seconds)
    landing_recommendations = build_landing_timing_recommendations(result)
    wait_breakdown_summary = build_wait_breakdown_summary(wait_breakdown, completed_aircraft, adjusted_total_wait_seconds)

    return {
        "durationSeconds": duration_seconds,
        "bucketMinutes": bucket_minutes,
        "buckets": buckets,
        "samples": samples,
        "fatoStats": facts,
        "gateStats": gate_facts,
        "actualSlots": actual_slots,
        "recommendedSlots": recommended_slots,
        "landingRecommendations": landing_recommendations,
        "waitBreakdown": wait_breakdown_summary,
        "summary": {
            "totalThroughput": total_throughput,
            "takeoffSuccess": sum(bucket["takeoff"] for bucket in buckets),
            "landingComplete": sum(bucket["landing"] for bucket in buckets),
            "peakHourlyRate": round((peak_bucket["total"] * 3600) / max(1, peak_bucket["end"] - peak_bucket["start"])),
            "averageHourlyRate": total_throughput / duration_hours if duration_hours else 0,
            "peakActive": peak_active,
            "peakQueued": peak_queued,
            "endActive": end_sample["active"],
            "endQueued": end_sample["queued"],
            "averageActive": average_active,
            "averageQueued": average_queued,
            "averageWaitMinutes": total_wait_seconds / completed_aircraft / 60 if completed_aircraft else 0,
            "adjustedAverageWaitMinutes": adjusted_total_wait_seconds / completed_aircraft / 60 if completed_aircraft else 0,
            "averageWaitReductionMinutes": adjusted_wait_savings_seconds / completed_aircraft / 60 if completed_aircraft else 0,
            "averagePreLandingSlotWaitMinutes": wait_breakdown["preLandingSlot"] / completed_landings / 60 if completed_landings else 0,
            "averageLandingFatoHoldMinutes": wait_breakdown["landingFatoHold"] / completed_landings / 60 if completed_landings else 0,
            "schedulableLandingWaitMinutes": schedulable_landing_wait_seconds / 60,
            "bottleneckFato": bottleneck,
            "maxUtilizationFato": max_utilization_fato,
            "avoidableFatoHoldMinutes": recommended_saved_hold_seconds / 60,
            "recommendedLandingCount": len(landing_recommendations),
            "adjustedLandingCount": len(adjusted_landing_slots),
            "adjustedSlotCount": len([slot for slot in recommended_slots if slot.get("adjusted")]),
        },
    }


def create_wait_breakdown() -> dict[str, float]:
    return {
        "preLandingSlot": 0.0,
        "landingFatoHold": 0.0,
        "landingGround": 0.0,
        "departureGround": 0.0,
        "other": 0.0,
    }


def add_wait_breakdown(target: dict[str, float], item: dict[str, Any]) -> None:
    for segment in item.get("segments", []):
        if segment.get("state") != "waiting":
            continue
        seconds = max(0.0, segment["end"] - segment["start"])
        if item.get("kind") == "landing" and not segment.get("at"):
            target["preLandingSlot"] += seconds
        elif item.get("kind") == "landing" and segment.get("at", {}).get("type") == "fato":
            target["landingFatoHold"] += seconds
        elif item.get("kind") == "landing":
            target["landingGround"] += seconds
        elif item.get("kind") == "departure":
            target["departureGround"] += seconds
        else:
            target["other"] += seconds


def build_wait_breakdown_summary(wait_breakdown: dict[str, float], completed_aircraft: int, adjusted_total_wait_seconds: float) -> dict[str, Any]:
    denominator = max(1, completed_aircraft)
    category_defs = [
        ("preLandingSlot", "착륙 전 슬롯 대기", "착륙전", CHART_COLORS["preLanding"], True),
        ("landingFatoHold", "착륙 후 FATO 대기", "FATO", CHART_COLORS["landingFatoHold"], True),
        ("landingGround", "착륙 지상 이동 대기", "착륙지상", CHART_COLORS["landingGroundWait"], False),
        ("departureGround", "이륙 지상 이동 대기", "이륙지상", CHART_COLORS["departureGroundWait"], False),
        ("other", "기타 대기", "기타", CHART_COLORS["otherWait"], False),
    ]
    categories = []
    for key, label, short_label, color, schedulable in category_defs:
        total_seconds = wait_breakdown.get(key, 0.0)
        if total_seconds <= 0 and key == "other":
            continue
        categories.append({
            "key": key,
            "label": label,
            "shortLabel": short_label,
            "color": color,
            "schedulable": schedulable,
            "totalSeconds": total_seconds,
            "totalMinutes": total_seconds / 60,
            "averageMinutes": total_seconds / denominator / 60,
        })
    total_seconds = sum(wait_breakdown.values())
    return {
        "totalSeconds": total_seconds,
        "adjustedTotalSeconds": adjusted_total_wait_seconds,
        "totalAverageMinutes": total_seconds / denominator / 60,
        "adjustedAverageMinutes": adjusted_total_wait_seconds / denominator / 60,
        "categories": categories,
    }


def build_actual_slot_schedule(result: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        [slot for slot in (build_fato_slot(item, result["durationSeconds"]) for item in result.get("aircraft", [])) if slot],
        key=lambda slot: (slot["start"], slot["end"]),
    )


def build_recommended_slot_schedule(actual_slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recommended = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for slot in actual_slots:
        hold_seconds = sum(
            max(0.0, interval["end"] - interval["start"])
            for interval in slot["intervals"]
            if interval.get("phase") == "hold"
        )
        operation_intervals = [interval for interval in slot["intervals"] if interval.get("phase") != "hold"]
        if not operation_intervals:
            continue
        operation_start = min(interval["start"] for interval in operation_intervals)
        desired_start = operation_start + hold_seconds if slot["kind"] == "landing" else operation_start
        grouped.setdefault(slot["fatoId"], []).append({
            "slot": slot,
            "holdSeconds": hold_seconds,
            "operationIntervals": operation_intervals,
            "operationStart": operation_start,
            "desiredStart": desired_start,
        })

    for candidates in grouped.values():
        fato_ready_time = 0.0
        ordered = sorted(candidates, key=lambda item: (item["desiredStart"], item["operationStart"], item["slot"]["end"]))
        for candidate in ordered:
            slot = candidate["slot"]
            recommended_start = max(candidate["desiredStart"], fato_ready_time)
            shift_seconds = recommended_start - candidate["operationStart"]
            intervals = [
                {**interval, "start": interval["start"] + shift_seconds, "end": interval["end"] + shift_seconds}
                for interval in candidate["operationIntervals"]
            ]
            start = min(interval["start"] for interval in intervals)
            end = max(interval["end"] for interval in intervals)
            fato_ready_time = end
            recommended.append({
                **slot,
                "start": start,
                "end": end,
                "eventTime": slot["eventTime"] + shift_seconds,
                "intervals": intervals,
                "adjusted": slot["kind"] == "landing" and shift_seconds > 0,
                "shiftSeconds": shift_seconds,
                "savedHoldSeconds": candidate["holdSeconds"] if slot["kind"] == "landing" else 0,
            })

    return sorted(recommended, key=lambda slot: (slot["start"], slot["end"]))


def build_fato_slot(item: dict[str, Any], duration_seconds: float) -> dict[str, Any] | None:
    fato_id = item.get("fatoId") or find_touched_fato_id(item.get("segments", []))
    if not fato_id:
        return None
    slot_segments = [
        segment for segment in item.get("segments", [])
        if is_fato_slot_segment(segment, fato_id, item.get("kind"))
    ]
    if not slot_segments:
        return None
    start = clamp(min(segment["start"] for segment in slot_segments), 0, duration_seconds)
    end = clamp(max(segment["end"] for segment in slot_segments), 0, duration_seconds)
    if end <= start:
        return None
    air_segment = next((segment for segment in slot_segments if segment.get("state") == "airborne"), None)
    event_time = (air_segment.get("start") if item.get("kind") == "departure" else air_segment.get("end")) if air_segment else start
    return {
        "id": item.get("id"),
        "kind": item.get("kind"),
        "fatoId": fato_id,
        "start": start,
        "end": end,
        "eventTime": clamp(event_time, start, end),
        "intervals": merge_slot_intervals([
            {
                "start": clamp(segment["start"], 0, duration_seconds),
                "end": clamp(segment["end"], 0, duration_seconds),
                "phase": "hold" if segment.get("state") == "waiting" and segment.get("at", {}).get("id") == fato_id else "operation",
            }
            for segment in slot_segments
        ]),
    }


def build_landing_timing_recommendations(result: dict[str, Any]) -> list[dict[str, Any]]:
    recommendations = []
    for item in result.get("aircraft", []):
        if item.get("kind") != "landing":
            continue
        fato_id = item.get("fatoId") or find_touched_fato_id(item.get("segments", []))
        if not fato_id:
            continue
        air_segment = next((
            segment for segment in item.get("segments", [])
            if segment.get("state") == "airborne" and segment.get("to", {}).get("id") == fato_id
        ), None)
        if not air_segment:
            continue
        hold_seconds = sum(
            max(0.0, segment["end"] - segment["start"])
            for segment in item.get("segments", [])
            if segment.get("state") == "waiting" and segment.get("at", {}).get("id") == fato_id
        )
        if hold_seconds < 60:
            continue
        current_touchdown = clamp(air_segment["end"], 0, result["durationSeconds"])
        recommended_touchdown = clamp(current_touchdown + hold_seconds, 0, result["durationSeconds"])
        if recommended_touchdown <= current_touchdown:
            continue
        recommendations.append({
            "aircraftId": item.get("id"),
            "gateId": item.get("gateId"),
            "fatoId": fato_id,
            "currentTouchdown": current_touchdown,
            "recommendedTouchdown": recommended_touchdown,
            "delaySeconds": recommended_touchdown - current_touchdown,
            "currentAirStart": clamp(air_segment["start"], 0, result["durationSeconds"]),
            "recommendedAirStart": clamp(air_segment["start"] + hold_seconds, 0, result["durationSeconds"]),
        })
    return sorted(recommendations, key=lambda item: (-item["delaySeconds"], item["currentTouchdown"]))


def is_fato_slot_segment(segment: dict[str, Any], fato_id: str, kind: str) -> bool:
    if segment.get("at", {}).get("id") == fato_id:
        return True
    if kind == "departure":
        return segment.get("state") == "airborne" and segment.get("from", {}).get("id") == fato_id
    if kind == "landing":
        return segment.get("state") == "airborne" and segment.get("to", {}).get("id") == fato_id
    return False


def merge_slot_intervals(intervals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sorted_intervals = sorted(
        [interval for interval in intervals if interval["end"] > interval["start"]],
        key=lambda interval: (interval["start"], interval["end"]),
    )
    merged = []
    for interval in sorted_intervals:
        last = merged[-1] if merged else None
        if last and last.get("phase") == interval.get("phase") and interval["start"] <= last["end"] + 0.001:
            last["end"] = max(last["end"], interval["end"])
            continue
        merged.append(dict(interval))
    return merged


def find_touched_fato_id(segments: list[dict[str, Any]]) -> str | None:
    for segment in segments:
        if segment.get("at", {}).get("type") == "fato":
            return segment["at"]["id"]
        if segment.get("from", {}).get("type") == "fato":
            return segment["from"]["id"]
        if segment.get("to", {}).get("type") == "fato":
            return segment["to"]["id"]
    return None


def add_fato_usage_interval(
    intervals_by_fato: dict[str, list[tuple[float, float]]],
    fallback_fato_id: str | None,
    segment: dict[str, Any],
    duration_seconds: float,
) -> None:
    fato_id = (
        segment.get("at", {}).get("id") if segment.get("at", {}).get("type") == "fato"
        else segment.get("from", {}).get("id") if segment.get("from", {}).get("type") == "fato"
        else segment.get("to", {}).get("id") if segment.get("to", {}).get("type") == "fato"
        else None
    )
    if not fato_id and not fallback_fato_id:
        return
    is_fato_stationary = segment.get("at", {}).get("type") == "fato"
    is_air_operation = segment.get("state") == "airborne" and (
        segment.get("from", {}).get("type") == "fato" or segment.get("to", {}).get("type") == "fato"
    )
    if not is_fato_stationary and not is_air_operation:
        return
    start = max(0.0, segment["start"])
    end = min(duration_seconds, segment["end"])
    if end <= start:
        return
    intervals_by_fato.setdefault(fato_id or fallback_fato_id, []).append((start, end))


def ensure_fato_stats(stats: dict[str, dict[str, Any]], fato_id: str | None) -> dict[str, Any]:
    key = fato_id or "unknown"
    if key not in stats:
        stats[key] = {"fatoId": key, "takeoff": 0, "landing": 0, "completed": 0, "waitSeconds": 0.0}
    return stats[key]


def ensure_gate_stats(stats: dict[str, dict[str, Any]], gate_id: str | None) -> dict[str, Any]:
    key = gate_id or "unknown"
    if key not in stats:
        stats[key] = {"gateId": key, "departure": 0, "landing": 0, "completed": 0, "waitSeconds": 0.0}
    return stats[key]


def merged_duration_seconds(intervals: list[tuple[float, float]]) -> float:
    sorted_intervals = sorted(
        [(max(0.0, start), max(0.0, end)) for start, end in intervals if end > start],
        key=lambda item: item[0],
    )
    if not sorted_intervals:
        return 0.0
    total = 0.0
    current_start, current_end = sorted_intervals[0]
    for start, end in sorted_intervals[1:]:
        if start <= current_end:
            current_end = max(current_end, end)
            continue
        total += current_end - current_start
        current_start, current_end = start, end
    total += current_end - current_start
    return total


def choose_bucket_minutes(duration_seconds: float) -> int:
    hours = duration_seconds / 3600
    if hours <= 2:
        return 10
    if hours <= 6:
        return 15
    return 30


def choose_sample_step_seconds(duration_seconds: float) -> int:
    target_samples = 72
    raw_step = duration_seconds / target_samples
    return max(60, int((raw_step + 59) // 60) * 60)


def average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))
