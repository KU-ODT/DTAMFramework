"""FastAPI server for the PSU Monitoring SW extension module.

1회차 범위:
- 독립 실행 가능한 FastAPI 앱 골격 제공
- 정적 웹 셸 제공
- 헬스체크/상태 API 제공

8회차 최종 범위까지 Overview, Traffic Map, Flow & Capacity,
Decision Support, Replay / Report API와 정적 웹 UI를 통합한다.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from .services.dtam_live import get_live_gateway
from .services.mbtiles import MBTiles
from .services.operational_environment import (
    load_operational_environment,
    operational_environment_map_layers,
)
from .services.scenario_data import (
    capacity_summary,
    decision_support_payload,
    flow_capacity_payload,
    list_scenarios,
    load_scenario,
    overview_payload,
    priority_events,
    final_validation_payload,
    replay_payload,
    scenario_result_report_payload,
    scenario_metadata,
    traffic_conflict_payload,
)


APP_DIR = Path(__file__).resolve().parent
MODULE_ROOT = APP_DIR.parent
EXTENSION_ROOT = MODULE_ROOT.parent
FRAMEWORK_ROOT = EXTENSION_ROOT.parent
MISSION_MODULE_ROOT = FRAMEWORK_ROOT / "MissionModule"
OPERATION_MODULE_ROOT = FRAMEWORK_ROOT / "OperationModule"
WEB_DIR = APP_DIR / "web"
CHECKLIST_PATH = MODULE_ROOT / "psu_monitoring_sw_master_checklist.md"
MISSION_RESOURCES_DIR = MISSION_MODULE_ROOT / "resources"
OPERATION_RESOURCES_DIR = OPERATION_MODULE_ROOT / "resource"
MBTILES_PATH = (OPERATION_RESOURCES_DIR / "korea.mbtiles") if (OPERATION_RESOURCES_DIR / "korea.mbtiles").is_file() else (MISSION_RESOURCES_DIR / "korea.mbtiles")
DEFAULT_CENTER_LON = 126.978
DEFAULT_CENTER_LAT = 37.5665
DEFAULT_START_ZOOM = 10.85
KST = ZoneInfo("Asia/Seoul")


def _server_time() -> dict[str, str]:
    now = datetime.now(tz=KST)
    return {
        "timezone": "Asia/Seoul",
        "iso": now.isoformat(),
        "display": now.strftime("%Y-%m-%d %H:%M:%S KST"),
    }


def _scenario_with_live_tracks() -> dict[str, object]:
    """Return scenario context with live ICD 4001 tracks only.

    Static demo track positions are intentionally removed so the PSU console does
    not display fake aircraft when DT World/StateServer has not delivered fresh
    4001 data.  Scenario analytics can still use their static datasets through
    routes that call ``load_scenario()`` directly.
    """
    scenario = load_scenario()
    live_tracks = get_live_gateway().live_tracks(include_stale=False)

    flight_plans = scenario.get("flight_plans", [])
    plan_by_aircraft = {
        str(item.get("aircraft_id") or item.get("aircraftId") or ""): item
        for item in flight_plans
        if isinstance(item, dict)
    }

    merged_tracks: list[dict[str, object]] = []
    for live in live_tracks:
        aircraft_id = str(live.get("aircraft_id") or live.get("aircraftId") or "")
        if not aircraft_id:
            continue
        base = dict(live)
        plan = plan_by_aircraft.get(aircraft_id) or {}
        base.setdefault("aircraft_id", aircraft_id)
        base.setdefault("flight_status", "ACTIVE")
        base.setdefault("status", "ACTIVE")
        base.setdefault("severity", "NORMAL")
        if not base.get("flight_plan_id") and plan:
            base["flight_plan_id"] = plan.get("flight_plan_id")
        if not base.get("route_id") and plan:
            base["route_id"] = plan.get("route_id")
        if not base.get("origin_vertiport") and plan:
            base["origin_vertiport"] = plan.get("origin_vertiport")
        if not base.get("destination_vertiport") and plan:
            base["destination_vertiport"] = plan.get("destination_vertiport")
        merged_tracks.append(base)

    scenario["track_states"] = merged_tracks
    scenario["live_4001"] = get_live_gateway().vehicle_snapshot(include_stale=True)
    notes = list(scenario.get("source_notes") or [])
    if merged_tracks:
        notes.append("Live ICD 4001 vehicle positions merged from DTAM StateServer/OperationModule cache.")
    else:
        notes.append("No fresh ICD 4001 vehicle positions; static demo aircraft suppressed on PSU map.")
    scenario["source_notes"] = notes
    return scenario




def _traffic_live_scenario() -> dict[str, object]:
    """Traffic Map tab payload: live aircraft/conflicts only.

    If no fresh 4001 aircraft exists, suppress demo flight plans and demo
    conflicts so the traffic tab does not imply real-time data is present.
    """
    scenario = _scenario_with_live_tracks()
    if not scenario.get("track_states"):
        scenario["flight_plans"] = []
        scenario["conflict_events"] = []
    return scenario

def _live_data_link_label() -> str:
    status = get_live_gateway().status()
    stream = status.get("vehicle_stream") if isinstance(status.get("vehicle_stream"), dict) else {}
    if stream.get("fresh_vehicle_count"):
        return "LIVE 4001"
    if status.get("state_server", {}).get("connected"):
        return "WAIT 4001"
    return "OFFLINE"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load map assets and start the live DTAM 4001 adapter for this PSU process."""
    app.state.mbtiles = MBTiles(MBTILES_PATH) if MBTILES_PATH.is_file() else None
    live_gateway = get_live_gateway()
    live_gateway.start()
    try:
        yield
    finally:
        live_gateway.stop()
        mbtiles = getattr(app.state, "mbtiles", None)
        if mbtiles is not None:
            mbtiles.close()
        app.state.mbtiles = None


def _map_config_payload(app: FastAPI) -> dict[str, object]:
    mbtiles: MBTiles | None = getattr(app.state, "mbtiles", None)
    if mbtiles is not None:
        metadata = mbtiles.metadata_payload()
        max_zoom = int(metadata.get("maxZoom") or 14)
        return {
            "provider": "OperationModule MBTiles",
            "available": True,
            "tileUrl": "/tiles/{z}/{x}/{y}.pbf",
            "center": [DEFAULT_CENTER_LON, DEFAULT_CENTER_LAT],
            "zoom": DEFAULT_START_ZOOM,
            "minZoom": int(metadata.get("minZoom") or 0),
            "maxZoom": max_zoom,
            "pitch": 0,
            "bearing": 0,
            "metadata": metadata,
        }
    return {
        "provider": "OperationModule MBTiles",
        "available": False,
        "tileUrl": None,
        "center": [DEFAULT_CENTER_LON, DEFAULT_CENTER_LAT],
        "zoom": DEFAULT_START_ZOOM,
        "minZoom": 0,
        "maxZoom": 14,
        "pitch": 0,
        "bearing": 0,
        "metadata": {
            "path": str(MBTILES_PATH),
            "missing": True,
        },
    }


def create_app() -> FastAPI:
    """Create the PSU Monitoring SW FastAPI app."""
    app = FastAPI(
        title="PSU Monitoring SW",
        description="Provider of Services for UAM monitoring console extension module.",
        version="0.1.0",
        lifespan=lifespan,
    )

    if WEB_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/api/health")
    async def health() -> dict[str, object]:
        return {
            "ok": True,
            "status": "ok",
            "module": "PSU",
            "name": "PSU Monitoring SW",
            "phase": "8/8 final replay report integration",
            "time": _server_time(),
        }

    @app.get("/api/config")
    async def config() -> dict[str, object]:
        return {
            "module": "PSU",
            "title": "PSU Monitoring SW",
            "version": "0.1.0",
            "default_port": 8120,
            "static_root": str(WEB_DIR),
            "map": _map_config_payload(app),
            "scenario": scenario_metadata(load_scenario()),
        }

    @app.get("/api/map/config")
    async def map_config() -> dict[str, object]:
        return _map_config_payload(app)

    @app.get("/tiles/{z}/{x}/{y}.pbf")
    async def get_tile(z: int, x: int, y: int) -> Response:
        mbtiles: MBTiles | None = getattr(app.state, "mbtiles", None)
        if mbtiles is None:
            raise HTTPException(status_code=404, detail=f"MBTiles not found: {MBTILES_PATH}")
        data = mbtiles.get_tile(z, x, y)
        if data is None:
            return Response(status_code=204)
        headers = {
            "Content-Type": "application/vnd.mapbox-vector-tile",
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=86400",
        }
        if len(data) >= 2 and data[0] == 0x1F and data[1] == 0x8B:
            headers["Content-Encoding"] = "gzip"
        return Response(content=data, headers=headers)

    @app.get("/api/status")
    async def status() -> dict[str, object]:
        live_status = get_live_gateway().status()
        return {
            "ok": True,
            "module": {
                "id": "stakeholder-psu",
                "name": "PSU Monitoring SW",
                "role": "Provider of Services for UAM",
                "version": "0.1.0",
                "phase": "8/8 final replay report integration",
            },
            "paths": {
                "module_root": str(MODULE_ROOT),
                "web_dir": str(WEB_DIR),
                "checklist": str(CHECKLIST_PATH),
                "checklist_exists": CHECKLIST_PATH.is_file(),
                "mission_resources": str(MISSION_RESOURCES_DIR),
                "operation_resources": str(OPERATION_RESOURCES_DIR),
                "mbtiles": str(MBTILES_PATH),
                "mbtiles_exists": MBTILES_PATH.is_file(),
            },
            "capabilities": {
                "overview_shell": False,
                "overview_view_integrated": True,
                "traffic_map_shell": False,
                "traffic_conflict_view_integrated": True,
                "flow_capacity_shell": False,
                "flow_capacity_view_integrated": True,
                "decision_support_integrated": True,
                "mitigation_evaluation_integrated": True,
                "operation_module_preview_integrated": True,
                "scenario_report_integrated": True,
                "replay_report_view_integrated": True,
                "report_export_integrated": True,
                "final_validation_integrated": True,
                "mission_map_assets_integrated": True,
                "analysis_engine_integrated": False,
                "scenario_data_integrated": True,
                "operation_module_launch_integrated": True,
                "live_4001_data_integrated": True,
                "dt_world_status_integrated": True,
            },
            "map": _map_config_payload(app),
            "scenario": scenario_metadata(_scenario_with_live_tracks()),
            "connected": live_status.get("connected"),
            "dt_world": live_status.get("dt_world"),
            "state_server": live_status.get("state_server"),
            "operation_status": live_status.get("operation_status"),
            "vehicle_stream": live_status.get("vehicle_stream"),
            "data_link_health": live_status.get("data_link_health"),
            "message": live_status.get("message"),
            "time": _server_time(),
        }

    @app.get("/api/dtworld/status")
    async def dtworld_status() -> dict[str, object]:
        return get_live_gateway().status()

    @app.get("/api/dtworld/vehicles")
    async def dtworld_vehicles() -> dict[str, object]:
        return get_live_gateway().vehicle_snapshot(include_stale=True)

    @app.get("/api/navigation")
    async def navigation() -> dict[str, object]:
        return {
            "tabs": [
                {
                    "id": "overview",
                    "label": "Overview",
                    "status": "integrated",
                    "description": "전체 운항 상황, KPI, 우선 이벤트를 표시하는 메인 화면",
                },
                {
                    "id": "traffic-map",
                    "label": "Traffic Map / Conflict",
                    "status": "integrated",
                    "description": "지도 기반 실시간 위치, 경로, 전략적 예측 충돌 분석 화면",
                },
                {
                    "id": "flow-capacity",
                    "label": "Flow & Capacity",
                    "status": "integrated",
                    "description": "수요-수용량, 회랑 밀도, 버티포트 병목 분석 화면",
                },
                {
                    "id": "decision-support",
                    "label": "Decision Support",
                    "status": "integrated",
                    "description": "조치 후보 생성, 전후 효과 비교, 리포트 및 OperationModule preview",
                },
                {
                    "id": "replay-report",
                    "label": "Replay / Report",
                    "status": "integrated",
                    "description": "시연용 시나리오 리플레이, 최종 리포트 출력, 통합 검증 결과",
                },
            ]
        }

    @app.get("/api/scenarios")
    async def scenarios() -> dict[str, object]:
        return {"scenarios": list_scenarios()}

    @app.get("/api/scenario")
    async def scenario() -> dict[str, object]:
        return load_scenario()

    @app.get("/api/scenario/metadata")
    async def scenario_meta() -> dict[str, object]:
        return scenario_metadata(_scenario_with_live_tracks())

    @app.get("/api/overview")
    async def overview() -> dict[str, object]:
        payload = overview_payload(_scenario_with_live_tracks())
        payload.setdefault("kpis", {})["data_link_health"] = _live_data_link_label()
        return payload

    @app.get("/api/overview/dashboard")
    async def overview_dashboard() -> dict[str, object]:
        payload = overview_payload(_scenario_with_live_tracks())
        payload.setdefault("kpis", {})["data_link_health"] = _live_data_link_label()
        return payload

    @app.get("/api/flight-plans")
    async def flight_plans() -> list[dict[str, object]]:
        return load_scenario().get("flight_plans", [])

    @app.get("/api/flight-plans/{flight_plan_id}")
    async def flight_plan_detail(flight_plan_id: str) -> dict[str, object]:
        for item in load_scenario().get("flight_plans", []):
            if item.get("flight_plan_id") == flight_plan_id:
                return item
        raise HTTPException(status_code=404, detail=f"Unknown flight_plan_id: {flight_plan_id}")

    @app.get("/api/tracks/current")
    async def current_tracks() -> list[dict[str, object]]:
        return _scenario_with_live_tracks().get("track_states", [])

    @app.get("/api/tracks/{aircraft_id}")
    async def track_detail(aircraft_id: str) -> dict[str, object]:
        for item in _scenario_with_live_tracks().get("track_states", []):
            if item.get("aircraft_id") == aircraft_id:
                return item
        raise HTTPException(status_code=404, detail=f"Unknown aircraft_id: {aircraft_id}")

    @app.get("/api/vertiports")
    async def vertiports() -> list[dict[str, object]]:
        return load_scenario().get("vertiports", [])

    @app.get("/api/vertiports/state")
    async def vertiport_state() -> list[dict[str, object]]:
        return load_scenario().get("vertiports", [])

    @app.get("/api/vertiports/{vertiport_id}")
    async def vertiport_detail(vertiport_id: str) -> dict[str, object]:
        for item in load_scenario().get("vertiports", []):
            if item.get("vertiport_id") == vertiport_id:
                return item
        raise HTTPException(status_code=404, detail=f"Unknown vertiport_id: {vertiport_id}")

    @app.get("/api/corridors")
    async def corridors() -> list[dict[str, object]]:
        return load_scenario().get("corridors", [])

    @app.get("/api/conflicts")
    async def conflicts() -> list[dict[str, object]]:
        return load_scenario().get("conflict_events", [])

    @app.get("/api/conflicts/{conflict_id}")
    async def conflict_detail(conflict_id: str) -> dict[str, object]:
        for item in load_scenario().get("conflict_events", []):
            if item.get("conflict_id") == conflict_id:
                return item
        raise HTTPException(status_code=404, detail=f"Unknown conflict_id: {conflict_id}")

    @app.get("/api/traffic/conflict-view")
    async def traffic_conflict_view() -> dict[str, object]:
        payload = traffic_conflict_payload(_traffic_live_scenario())
        payload["data_link"] = get_live_gateway().status()
        payload["live_mode"] = "icd-4001"
        return payload

    @app.get("/api/traffic-map/summary")
    async def traffic_map_summary() -> dict[str, object]:
        payload = traffic_conflict_payload(_traffic_live_scenario())
        payload["data_link"] = get_live_gateway().status()
        payload["live_mode"] = "icd-4001"
        return payload

    @app.get("/api/capacity/summary")
    async def capacity() -> dict[str, object]:
        return capacity_summary(load_scenario())

    @app.get("/api/capacity/flow-view")
    async def capacity_flow_view() -> dict[str, object]:
        return flow_capacity_payload(load_scenario())

    @app.get("/api/flow-capacity/summary")
    async def flow_capacity_summary() -> dict[str, object]:
        return flow_capacity_payload(load_scenario())

    @app.get("/api/capacity/bottlenecks")
    async def capacity_bottlenecks() -> dict[str, object]:
        payload = flow_capacity_payload(load_scenario())
        return payload.get("bottleneck_diagnosis", {})

    @app.get("/api/capacity/delay-propagation")
    async def capacity_delay_propagation() -> list[dict[str, object]]:
        payload = flow_capacity_payload(load_scenario())
        return payload.get("delay_propagation", [])

    @app.post("/api/capacity/run")
    async def capacity_run() -> dict[str, object]:
        payload = flow_capacity_payload(load_scenario())
        payload["run_mode"] = "static-demo"
        return payload

    @app.get("/api/decision-support")
    async def decision_support() -> dict[str, object]:
        return decision_support_payload(load_scenario())

    @app.get("/api/decision-support/summary")
    async def decision_support_summary() -> dict[str, object]:
        payload = decision_support_payload(load_scenario())
        return {
            "scenario": payload.get("scenario"),
            "analysis_mode": payload.get("analysis_mode"),
            "baseline": payload.get("baseline"),
            "recommendation_count": len(payload.get("recommendations", [])),
            "recommended_scenario": next(
                (item for item in payload.get("comparison", []) if item.get("recommended")),
                None,
            ),
            "generated_at": payload.get("generated_at"),
        }

    @app.get("/api/decision-support/actions")
    async def decision_support_actions() -> list[dict[str, object]]:
        return decision_support_payload(load_scenario()).get("recommendations", [])

    @app.get("/api/decision-support/actions/{recommendation_id}")
    async def decision_support_action_detail(recommendation_id: str) -> dict[str, object]:
        for item in decision_support_payload(load_scenario()).get("recommendations", []):
            if str(item.get("recommendation_id")) == recommendation_id:
                return item
        raise HTTPException(status_code=404, detail=f"Unknown recommendation_id: {recommendation_id}")

    @app.post("/api/decision-support/actions/{recommendation_id}/evaluate")
    async def decision_support_action_evaluate(recommendation_id: str) -> dict[str, object]:
        payload = decision_support_payload(load_scenario())
        for item in payload.get("recommendations", []):
            if str(item.get("recommendation_id")) == recommendation_id:
                return {
                    "run_mode": "static-demo-dry-run",
                    "recommendation": item,
                    "comparison": {
                        "before": item.get("before"),
                        "after": item.get("after"),
                        "expected_effect": item.get("expected_effect"),
                    },
                    "operation_handoff": payload.get("operation_handoff"),
                }
        raise HTTPException(status_code=404, detail=f"Unknown recommendation_id: {recommendation_id}")

    @app.get("/api/decision-support/comparison")
    async def decision_support_comparison() -> list[dict[str, object]]:
        return decision_support_payload(load_scenario()).get("comparison", [])

    @app.post("/api/operation-module/replan/preview")
    async def operation_module_replan_preview() -> dict[str, object]:
        payload = decision_support_payload(load_scenario())
        return {
            "run_mode": "dry-run",
            "execution": "not-dispatched",
            "operation_handoff": payload.get("operation_handoff"),
        }

    @app.post("/api/operation-module/replan/dispatch")
    async def operation_module_replan_dispatch() -> dict[str, object]:
        payload = decision_support_payload(load_scenario())
        return {
            "run_mode": "dry-run-disabled-dispatch",
            "execution": "blocked-by-design",
            "reason": "초기 연구용 PSU 콘솔은 자동 운항 재계획 실행을 하지 않고 preview 패키지만 제공합니다.",
            "operation_handoff": payload.get("operation_handoff"),
        }

    @app.get("/api/replay")
    async def replay() -> dict[str, object]:
        return replay_payload(load_scenario())

    @app.get("/api/replay/timeline")
    async def replay_timeline() -> list[dict[str, object]]:
        return replay_payload(load_scenario()).get("frames", [])

    @app.get("/api/replay/frame/{step}")
    async def replay_frame(step: int) -> dict[str, object]:
        for item in replay_payload(load_scenario()).get("frames", []):
            if int(item.get("step") or 0) == step:
                return item
        raise HTTPException(status_code=404, detail=f"Unknown replay step: {step}")

    @app.get("/api/reports/scenario-result")
    async def scenario_result_report() -> dict[str, object]:
        return scenario_result_report_payload(load_scenario())

    @app.get("/api/reports/scenario-result.md")
    async def scenario_result_report_markdown() -> Response:
        report = scenario_result_report_payload(load_scenario())
        return Response(
            content=str(report.get("markdown") or ""),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": 'inline; filename="psu_scenario_result.md"'},
        )

    @app.get("/api/reports/scenario-result.html")
    async def scenario_result_report_html() -> HTMLResponse:
        report = scenario_result_report_payload(load_scenario())
        return HTMLResponse(content=str(report.get("html") or ""))

    @app.get("/api/final-validation")
    async def final_validation() -> dict[str, object]:
        return final_validation_payload(load_scenario())

    @app.get("/api/capacity/vertiports")
    async def capacity_vertiports() -> list[dict[str, object]]:
        return [
            item
            for item in load_scenario().get("capacity_metrics", [])
            if str(item.get("target_type", "")).upper() == "VERTIPORT"
        ]

    @app.get("/api/capacity/corridors")
    async def capacity_corridors() -> list[dict[str, object]]:
        return [
            item
            for item in load_scenario().get("capacity_metrics", [])
            if str(item.get("target_type", "")).upper() == "CORRIDOR"
        ]

    @app.get("/api/capacity/corridors/{corridor_id}")
    async def capacity_corridor_detail(corridor_id: str) -> dict[str, object]:
        payload = flow_capacity_payload(load_scenario())
        for item in payload.get("corridor_density", []):
            if str(item.get("target_id")) == corridor_id:
                return item
        raise HTTPException(status_code=404, detail=f"Unknown corridor_id: {corridor_id}")

    @app.get("/api/capacity/vertiports/{vertiport_id}")
    async def capacity_vertiport_detail(vertiport_id: str) -> dict[str, object]:
        payload = flow_capacity_payload(load_scenario())
        for item in payload.get("vertiport_throughput", []):
            if str(item.get("target_id")) == vertiport_id:
                return item
        raise HTTPException(status_code=404, detail=f"Unknown vertiport_id: {vertiport_id}")

    @app.get("/api/events")
    async def events() -> list[dict[str, object]]:
        return load_scenario().get("event_logs", [])

    @app.get("/api/events/priority")
    async def events_priority() -> list[dict[str, object]]:
        return priority_events(load_scenario())

    @app.get("/api/map/operational-environment")
    async def map_operational_environment() -> dict[str, object]:
        return load_operational_environment()

    @app.get("/api/map/layers")
    async def scenario_map_layers() -> dict[str, object]:
        scenario = _scenario_with_live_tracks()
        return operational_environment_map_layers(
            live_tracks=scenario.get("track_states", []),
            generated_at=str(scenario.get("current_time") or ""),
        )

    return app
