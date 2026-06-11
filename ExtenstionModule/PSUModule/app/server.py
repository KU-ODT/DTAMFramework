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

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from .services.dtam_live import get_live_gateway
from .services.mbtiles import MBTiles
from .services.operational_environment import (
    load_operational_environment,
    operational_environment_map_layers,
)
from .services.psu_icd_gateway import (
    build_3002_draft,
    build_3003_draft,
    dispatch_3002_command,
    dispatch_3003_command,
    load_scheduled_flights,
    summarize_vehicle_snapshot,
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

REMOVED_DEMO_SECTIONS: dict[str, dict[str, str]] = {
    "scenario": {
        "title": "Scenario demo dataset removed",
        "previous": "static waypoints, corridors, vertiports, flight plans, tracks, conflicts, capacity metrics, events, and trend demo data",
        "replacement": "Only live integrated data and real map/environment resources are displayed.",
    },
    "flight_plans": {
        "title": "Flight plan demo removed",
        "previous": "static sample flight plans from the demo JSON",
        "replacement": "The console displays only received flight plan data from the StateServer.",
    },
    "vertiport_status": {
        "title": "Vertiport status demo removed",
        "previous": "static FATO, gate, queue, delay, and status values from the demo JSON",
        "replacement": "Dedicated live vertiport state is not generated until a real source is connected.",
    },
    "corridor_status": {
        "title": "Corridor status demo removed",
        "previous": "static corridor capacity, occupancy, density, and status values from the demo JSON",
        "replacement": "Only node and link geometry from the operational environment is displayed.",
    },
    "conflicts": {
        "title": "Conflict demo removed",
        "previous": "static predicted conflict, severity, and suggested action demo values",
        "replacement": "Live collision/event consumption is not generated until a real event source is connected.",
    },
    "capacity": {
        "title": "Capacity analysis demo removed",
        "previous": "static demand-capacity, bottleneck, and delay propagation demo analysis",
        "replacement": "Capacity analysis results are hidden until a real analysis engine is connected.",
    },
    "decision": {
        "title": "Decision support demo removed",
        "previous": "static rulebook recommendations, before/after comparison, and preview package",
        "replacement": "Recommended actions are not generated until a real decision engine and dispatch path are connected.",
    },
    "replay_report": {
        "title": "Replay and report demo removed",
        "previous": "stored scenario timeline, replay frames, report, and final validation demo output",
        "replacement": "Replay and reports are not generated until real execution logs or analysis output are connected.",
    },
    "events": {
        "title": "Priority event demo removed",
        "previous": "static priority event and operator focus values from the demo JSON",
        "replacement": "Event lists stay empty until a real event stream is connected.",
    },
    "traffic_trend": {
        "title": "Traffic trend demo removed",
        "previous": "static active, delay, and conflict trend values from the demo JSON",
        "replacement": "Trend charts stay empty until real-time trend aggregation is connected.",
    },
}


def _server_time() -> dict[str, str]:
    now = datetime.now(tz=KST)
    return {
        "timezone": "Asia/Seoul",
        "iso": now.isoformat(),
        "display": now.strftime("%Y-%m-%d %H:%M:%S KST"),
    }


def _removed_notice(section_id: str) -> dict[str, str]:
    section = REMOVED_DEMO_SECTIONS[section_id]
    previous = section["previous"]
    return {
        "id": section_id,
        "status": "removed",
        "title": section["title"],
        "previous": previous,
        "message": f"Previously this used {previous}; it has been removed.",
        "replacement": section["replacement"],
    }


def _removed_not_found(section_id: str, item_id: str) -> HTTPException:
    notice = _removed_notice(section_id)
    return HTTPException(
        status_code=404,
        detail={
            "id": item_id,
            "message": notice["message"],
            "replacement": notice["replacement"],
        },
    )


def _live_tracks() -> list[dict[str, object]]:
    return get_live_gateway().live_tracks(include_stale=False)


def _removed_sections(*section_ids: str) -> list[dict[str, str]]:
    return [_removed_notice(section_id) for section_id in section_ids]


def _live_metadata() -> dict[str, object]:
    tracks = _live_tracks()
    return {
        "scenario_id": "LIVE-DTAM-PSU",
        "name": "Live DTAM PSU Console",
        "description": "Demo scenario data removed. PSU displays only live tracks and real map/environment resources.",
        "schema_version": "live-only",
        "created_at": "",
        "current_time": _server_time()["iso"],
        "counts": {
            "waypoints": 0,
            "corridors": 0,
            "vertiports": 0,
            "flight_plans": 0,
            "track_states": len(tracks),
            "conflict_events": 0,
            "capacity_metrics": 0,
            "event_logs": 0,
            "traffic_trend": 0,
        },
        "removed_demo": _removed_sections("scenario"),
    }


def _live_flights() -> list[dict[str, object]]:
    flights: list[dict[str, object]] = []
    for track in _live_tracks():
        aircraft_id = str(track.get("aircraft_id") or track.get("aircraftId") or "").strip()
        if not aircraft_id:
            continue
        flights.append(
            {
                "flight_plan_id": track.get("flight_plan_id") or f"LIVE-{aircraft_id}",
                "aircraft_id": aircraft_id,
                "operator_id": track.get("operator_id") or "DTAM",
                "route_id": track.get("route_id") or "",
                "current_corridor_id": track.get("current_corridor_id") or "",
                "current_corridor_name": track.get("current_corridor_name") or "Live track",
                "origin_vertiport": track.get("origin_vertiport") or "",
                "origin_name": None,
                "destination_vertiport": track.get("destination_vertiport") or "",
                "destination_name": None,
                "waypoints": [],
                "planned_departure_time": None,
                "planned_arrival_time": None,
                "eta": track.get("timestamp") or track.get("received_at"),
                "delay_sec": 0,
                "planned_altitude": track.get("altitude"),
                "planned_speed": track.get("ground_speed"),
                "status": track.get("flight_status") or track.get("status") or "ACTIVE",
                "track": track,
                "is_active": str(track.get("flight_status") or track.get("status") or "").upper() in {"ACTIVE", "CONNECTED"},
                "conflict_count": 0,
                "severity": "NORMAL",
                "related_conflicts": [],
                "source": track.get("source") or "Live Feed",
            }
        )
    return flights


def _overview_payload() -> dict[str, object]:
    env = load_operational_environment()
    tracks = _live_tracks()
    return {
        "scenario": _live_metadata(),
        "kpis": {
            "active_uam": len(tracks),
            "pending_intent": 0,
            "conflict_alert": 0,
            "capacity_alert": 0,
            "average_delay_sec": 0,
            "max_delay_sec": 0,
            "off_nominal_event": 0,
            "data_link_health": _live_data_link_label(),
        },
        "status_summary": {
            "event_severity": {},
            "vertiport_status": {},
            "corridor_status": {},
            "flight_plan_status": {},
            "track_status": {"ACTIVE": len(tracks)} if tracks else {},
        },
        "traffic_summary": {
            "peak_active_flights": len(tracks),
            "peak_conflict_count": 0,
            "peak_average_delay_sec": 0,
            "trend_points": 0,
        },
        "map_summary": {
            "track_count": len(tracks),
            "route_count": 0,
            "vertiport_count": len(env.get("vertiports") or []),
            "corridor_count": len(env.get("corridors") or []),
            "conflict_count": 0,
            "actual_track_count": len(tracks),
            "warning_corridors": 0,
        },
        "top_priority_event": None,
        "capacity_hotspots": [],
        "critical_vertiports": [],
        "priority_events": [],
        "vertiport_summary": [],
        "traffic_trend": [],
        "removed_demo": _removed_sections(
            "events",
            "vertiport_status",
            "traffic_trend",
            "flight_plans",
            "conflicts",
            "capacity",
        ),
        "generated_at": _server_time()["iso"],
    }


def _traffic_payload() -> dict[str, object]:
    flights = _live_flights()
    tracks = [flight["track"] for flight in flights]
    return {
        "scenario": _live_metadata(),
        "flights": flights,
        "tracks": tracks,
        "conflicts": [],
        "timeline": [],
        "summary": {
            "flight_count": len(flights),
            "active_track_count": len(tracks),
            "active_flight_count": sum(1 for item in flights if item.get("is_active")),
            "conflict_count": 0,
            "warning_count": 0,
            "caution_count": 0,
        },
        "data_link": get_live_gateway().status(),
        "live_mode": "icd-4001",
        "removed_demo": _removed_sections("flight_plans", "conflicts"),
        "generated_at": _server_time()["iso"],
    }


def _tactical_vehicle_payload() -> dict[str, object]:
    snapshot = get_live_gateway().vehicle_snapshot(include_stale=True)
    vehicles = snapshot.get("vehicles") if isinstance(snapshot.get("vehicles"), list) else []
    return {
        "message_id": "4001",
        "vehicles": vehicles,
        "tracks": _live_tracks(),
        "summary": summarize_vehicle_snapshot(snapshot),
        "data_link": get_live_gateway().status(),
        "snapshot": {
            "source": snapshot.get("source"),
            "transport": snapshot.get("transport"),
            "last_received_at": snapshot.get("last_received_at"),
            "state_server": snapshot.get("state_server"),
            "operation_status": snapshot.get("operation_status"),
        },
        "generated_at": _server_time()["iso"],
    }


def _capacity_removed_payload() -> dict[str, object]:
    return {
        "removed": True,
        "scenario": _live_metadata(),
        "analysis_condition": {
            "time_window_start": "",
            "time_window_end": "",
            "interval_min": 0,
            "target_scope": "Removed demo data",
            "scenario_mode": "removed-demo-data",
            "generated_at": _server_time()["iso"],
        },
        "summary": {
            "total_demand": 0,
            "total_capacity": 0,
            "network_utilization": 0,
            "warning_count": 0,
            "caution_count": 0,
            "max_utilization": 0,
            "main_bottleneck_id": None,
            "main_bottleneck_type": None,
            "main_bottleneck_cause": None,
            "delay_event_count": 0,
        },
        "demand_capacity_series": [],
        "corridor_density": [],
        "vertiport_throughput": [],
        "delay_propagation": [],
        "bottleneck_diagnosis": None,
        "capacity_events": [],
        "removed_demo": _removed_sections("capacity", "corridor_status", "vertiport_status"),
        "generated_at": _server_time()["iso"],
    }


def _decision_removed_payload() -> dict[str, object]:
    return {
        "removed": True,
        "scenario": _live_metadata(),
        "analysis_mode": {
            "phase": "live-only",
            "layer": "decision-support",
            "automation_level": "removed-demo-data",
            "operator_authority": "not-generated",
            "optimization_engine": "not-connected",
            "generated_at": _server_time()["iso"],
        },
        "baseline": {},
        "recommendations": [],
        "comparison": [],
        "operation_handoff": None,
        "report": None,
        "removed_demo": _removed_sections("decision"),
        "generated_at": _server_time()["iso"],
    }


def _replay_removed_payload() -> dict[str, object]:
    return {
        "removed": True,
        "scenario": _live_metadata(),
        "playback": {
            "mode": "removed-demo-data",
            "start_time": "",
            "end_time": "",
            "frame_count": 0,
            "default_interval_ms": 1600,
            "speed_options": [],
            "operator_controls": [],
        },
        "summary": {
            "initial_active_flights": len(_live_tracks()),
            "conflict_events": 0,
            "capacity_events": 0,
            "decision_candidates": 0,
            "recommended_scenario": None,
            "report_id": None,
        },
        "frames": [],
        "removed_demo": _removed_sections("replay_report"),
        "generated_at": _server_time()["iso"],
    }


def _validation_removed_payload() -> dict[str, object]:
    return {
        "removed": True,
        "scenario": _live_metadata(),
        "phase": "live-only",
        "completion": {
            "passed": 0,
            "warnings": 0,
            "total": 0,
            "percentage": 0,
        },
        "checks": [],
        "known_limits": [notice["message"] for notice in _removed_sections("replay_report", "decision", "capacity")],
        "removed_demo": _removed_sections("replay_report"),
        "generated_at": _server_time()["iso"],
    }


def _report_removed_payload() -> dict[str, object]:
    notice = _removed_notice("replay_report")
    markdown = f"# PSU Report Removed\n\n{notice['message']}\n\n{notice['replacement']}\n"
    html = (
        "<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\"><title>PSU Report Removed</title></head>"
        f"<body><h1>PSU Report Removed</h1><p>{notice['message']}</p><p>{notice['replacement']}</p></body></html>"
    )
    return {
        "removed": True,
        "report_id": None,
        "title": "PSU Report Removed",
        "summary": notice["message"],
        "format": "removed-demo-data",
        "exports": {},
        "replay_summary": _replay_removed_payload()["summary"],
        "validation_summary": _validation_removed_payload()["completion"],
        "markdown": markdown,
        "html": html,
        "removed_demo": [notice],
        "generated_at": _server_time()["iso"],
    }

def _live_data_link_label() -> str:
    status = get_live_gateway().status()
    stream = status.get("vehicle_stream") if isinstance(status.get("vehicle_stream"), dict) else {}
    if stream.get("fresh_vehicle_count"):
        return "LIVE"
    if status.get("state_server", {}).get("connected"):
        return "WAITING"
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

    @app.middleware("http")
    async def no_cache_web_assets(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path == "/" or path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(
            WEB_DIR / "index.html",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

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
            "phase": "live-only demo-data-removed",
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
            "scenario": _live_metadata(),
            "removed_demo": _removed_sections("scenario"),
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
                "phase": "live-only demo-data-removed",
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
                "overview_shell": True,
                "overview_view_integrated": False,
                "traffic_map_shell": True,
                "traffic_conflict_view_integrated": False,
                "flow_capacity_shell": True,
                "flow_capacity_view_integrated": False,
                "decision_support_integrated": False,
                "mitigation_evaluation_integrated": False,
                "operation_module_preview_integrated": False,
                "scenario_report_integrated": False,
                "replay_report_view_integrated": False,
                "report_export_integrated": False,
                "final_validation_integrated": False,
                "mission_map_assets_integrated": True,
                "analysis_engine_integrated": False,
                "scenario_data_integrated": False,
                "operation_module_launch_integrated": False,
                "strategic_3001_view_integrated": True,
                "strategic_3002_dispatch_integrated": True,
                "live_4001_data_integrated": True,
                "tactical_3003_dispatch_integrated": True,
                "dt_world_status_integrated": True,
            },
            "map": _map_config_payload(app),
            "scenario": _live_metadata(),
            "connected": live_status.get("connected"),
            "dt_world": live_status.get("dt_world"),
            "state_server": live_status.get("state_server"),
            "operation_status": live_status.get("operation_status"),
            "vehicle_stream": live_status.get("vehicle_stream"),
            "data_link_health": live_status.get("data_link_health"),
            "message": live_status.get("message"),
            "removed_demo": list(_removed_sections(*REMOVED_DEMO_SECTIONS.keys())),
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
                    "id": "strategic-plans",
                    "label": "Strategic Planning",
                    "status": "flight-planning",
                    "description_live": "Received flight plans and strategic modification command dispatch.",
                },
                {
                    "id": "tactical-monitoring",
                    "label": "Operations Monitoring",
                    "status": "live-operations",
                    "description_live": "Live aircraft status and tactical command dispatch.",
                },
                {
                    "id": "replay-report",
                    "label": "Replay / Report",
                    "status": "removed-demo",
                    "description_live": "Static replay, report, and validation demo removed. Placeholder retained.",
                },
            ]
        }

    @app.get("/api/psu/console-flow")
    async def psu_console_flow() -> dict[str, object]:
        return {
            "flow": [
                "Scheduled flight plan",
                "receive/store/validate/display",
                "strategic conflict or capacity issue",
                "strategic modification command dispatch",
                "new flight plan version updates active plan",
                "live aircraft status",
                "live position/status/conformance/event detection",
                "tactical event",
                "action command dispatch",
                "execution monitoring/log",
            ],
            "dispatch": {"strategic_modification": "StateServer /api/msg/3002 accept/store", "action_command": "StateServer /api/msg/3003 -> vehicle"},
        }

    @app.get("/api/strategic/plans")
    async def strategic_plans() -> dict[str, object]:
        return load_scheduled_flights()

    @app.post("/api/strategic/modification/draft")
    async def strategic_modification_draft(request: Request) -> dict[str, object]:
        payload = await request.json()
        return build_3002_draft(payload if isinstance(payload, dict) else {})

    @app.post("/api/strategic/modification/dispatch")
    async def strategic_modification_dispatch(request: Request) -> dict[str, object]:
        payload = await request.json()
        return dispatch_3002_command(payload if isinstance(payload, dict) else {})

    @app.get("/api/tactical/vehicles")
    async def tactical_vehicles() -> dict[str, object]:
        return _tactical_vehicle_payload()

    @app.post("/api/test/4001")
    async def test_4001_live_track(request: Request) -> dict[str, object]:
        body = await request.json()
        payload = body.get("payload") if isinstance(body, dict) and isinstance(body.get("payload"), dict) else body
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="payload must be a MSG 4001 JSON object")
        source = str(body.get("source") or "PSUTestEmulator/4001") if isinstance(body, dict) else "PSUTestEmulator/4001"
        result = get_live_gateway().inject_4001_payload(payload, source=source)
        if not result.get("ok"):
            raise HTTPException(status_code=422, detail="No valid aircraft found in MSG 4001 payload")
        return {
            "ok": True,
            "message_id": "4001",
            "mode": "psu-local-test",
            **result,
        }

    @app.post("/api/tactical/command/draft")
    async def tactical_command_draft(request: Request) -> dict[str, object]:
        payload = await request.json()
        return build_3003_draft(payload if isinstance(payload, dict) else {})

    @app.post("/api/tactical/command/dispatch")
    async def tactical_command_dispatch(request: Request) -> dict[str, object]:
        payload = await request.json()
        return dispatch_3003_command(payload if isinstance(payload, dict) else {})

    @app.get("/api/scenarios")
    async def scenarios() -> dict[str, object]:
        return {"scenarios": [], "removed_demo": _removed_sections("scenario")}

    @app.get("/api/scenario")
    async def scenario() -> dict[str, object]:
        return {
            "removed": True,
            "scenario": _live_metadata(),
            "removed_demo": list(_removed_sections(*REMOVED_DEMO_SECTIONS.keys())),
        }

    @app.get("/api/scenario/metadata")
    async def scenario_meta() -> dict[str, object]:
        return _live_metadata()

    @app.get("/api/overview")
    async def overview() -> dict[str, object]:
        return _overview_payload()

    @app.get("/api/overview/dashboard")
    async def overview_dashboard() -> dict[str, object]:
        return _overview_payload()

    @app.get("/api/flight-plans")
    async def flight_plans() -> list[dict[str, object]]:
        return list(load_scheduled_flights().get("plans") or [])

    @app.get("/api/flight-plans/{flight_plan_id}")
    async def flight_plan_detail(flight_plan_id: str) -> dict[str, object]:
        for plan in load_scheduled_flights().get("plans") or []:
            if str(plan.get("key")) == flight_plan_id or str(plan.get("flightPlanNumber")) == flight_plan_id:
                return plan
        raise HTTPException(status_code=404, detail=f"Unknown flight_plan_id: {flight_plan_id}")

    @app.get("/api/tracks/current")
    async def current_tracks() -> list[dict[str, object]]:
        return _live_tracks()

    @app.get("/api/tracks/{aircraft_id}")
    async def track_detail(aircraft_id: str) -> dict[str, object]:
        for item in _live_tracks():
            if item.get("aircraft_id") == aircraft_id:
                return item
        raise HTTPException(status_code=404, detail=f"Unknown aircraft_id: {aircraft_id}")

    @app.get("/api/vertiports")
    async def vertiports() -> list[dict[str, object]]:
        return []

    @app.get("/api/vertiports/state")
    async def vertiport_state() -> list[dict[str, object]]:
        return []

    @app.get("/api/vertiports/{vertiport_id}")
    async def vertiport_detail(vertiport_id: str) -> dict[str, object]:
        raise _removed_not_found("vertiport_status", vertiport_id)

    @app.get("/api/corridors")
    async def corridors() -> list[dict[str, object]]:
        return []

    @app.get("/api/conflicts")
    async def conflicts() -> list[dict[str, object]]:
        return []

    @app.get("/api/conflicts/{conflict_id}")
    async def conflict_detail(conflict_id: str) -> dict[str, object]:
        raise _removed_not_found("conflicts", conflict_id)

    @app.get("/api/traffic/conflict-view")
    async def traffic_conflict_view() -> dict[str, object]:
        return _traffic_payload()

    @app.get("/api/traffic-map/summary")
    async def traffic_map_summary() -> dict[str, object]:
        return _traffic_payload()

    @app.get("/api/capacity/summary")
    async def capacity() -> dict[str, object]:
        return _capacity_removed_payload()

    @app.get("/api/capacity/flow-view")
    async def capacity_flow_view() -> dict[str, object]:
        return _capacity_removed_payload()

    @app.get("/api/flow-capacity/summary")
    async def flow_capacity_summary() -> dict[str, object]:
        return _capacity_removed_payload()

    @app.get("/api/capacity/bottlenecks")
    async def capacity_bottlenecks() -> dict[str, object]:
        return {"removed": True, "removed_demo": _removed_sections("capacity")}

    @app.get("/api/capacity/delay-propagation")
    async def capacity_delay_propagation() -> list[dict[str, object]]:
        return []

    @app.post("/api/capacity/run")
    async def capacity_run() -> dict[str, object]:
        payload = _capacity_removed_payload()
        payload["run_mode"] = "removed-demo-data"
        return payload

    @app.get("/api/decision-support")
    async def decision_support() -> dict[str, object]:
        return _decision_removed_payload()

    @app.get("/api/decision-support/summary")
    async def decision_support_summary() -> dict[str, object]:
        payload = _decision_removed_payload()
        return {
            "scenario": payload.get("scenario"),
            "analysis_mode": payload.get("analysis_mode"),
            "baseline": payload.get("baseline"),
            "recommendation_count": len(payload.get("recommendations", [])),
            "recommended_scenario": None,
            "removed_demo": payload.get("removed_demo"),
            "generated_at": payload.get("generated_at"),
        }

    @app.get("/api/decision-support/actions")
    async def decision_support_actions() -> list[dict[str, object]]:
        return []

    @app.get("/api/decision-support/actions/{recommendation_id}")
    async def decision_support_action_detail(recommendation_id: str) -> dict[str, object]:
        raise _removed_not_found("decision", recommendation_id)

    @app.post("/api/decision-support/actions/{recommendation_id}/evaluate")
    async def decision_support_action_evaluate(recommendation_id: str) -> dict[str, object]:
        return {
            "run_mode": "removed-demo-data",
            "recommendation_id": recommendation_id,
            "removed_demo": _removed_sections("decision"),
        }

    @app.get("/api/decision-support/comparison")
    async def decision_support_comparison() -> list[dict[str, object]]:
        return []

    @app.post("/api/operation-module/replan/preview")
    async def operation_module_replan_preview() -> dict[str, object]:
        notice = _removed_notice("decision")
        return {
            "run_mode": "removed-demo-data",
            "execution": "not-dispatched",
            "reason": notice["message"],
            "operation_handoff": None,
            "removed_demo": [notice],
        }

    @app.post("/api/operation-module/replan/dispatch")
    async def operation_module_replan_dispatch() -> dict[str, object]:
        notice = _removed_notice("decision")
        return {
            "run_mode": "removed-demo-data",
            "execution": "blocked-by-design",
            "reason": notice["message"],
            "operation_handoff": None,
            "removed_demo": [notice],
        }

    @app.get("/api/replay")
    async def replay() -> dict[str, object]:
        return _replay_removed_payload()

    @app.get("/api/replay/timeline")
    async def replay_timeline() -> list[dict[str, object]]:
        return []

    @app.get("/api/replay/frame/{step}")
    async def replay_frame(step: int) -> dict[str, object]:
        raise _removed_not_found("replay_report", str(step))

    @app.get("/api/reports/scenario-result")
    async def scenario_result_report() -> dict[str, object]:
        return _report_removed_payload()

    @app.get("/api/reports/scenario-result.md")
    async def scenario_result_report_markdown() -> Response:
        report = _report_removed_payload()
        return Response(
            content=str(report.get("markdown") or ""),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": 'inline; filename="psu_scenario_result.md"'},
        )

    @app.get("/api/reports/scenario-result.html")
    async def scenario_result_report_html() -> HTMLResponse:
        report = _report_removed_payload()
        return HTMLResponse(content=str(report.get("html") or ""))

    @app.get("/api/final-validation")
    async def final_validation() -> dict[str, object]:
        return _validation_removed_payload()

    @app.get("/api/capacity/vertiports")
    async def capacity_vertiports() -> list[dict[str, object]]:
        return []

    @app.get("/api/capacity/corridors")
    async def capacity_corridors() -> list[dict[str, object]]:
        return []

    @app.get("/api/capacity/corridors/{corridor_id}")
    async def capacity_corridor_detail(corridor_id: str) -> dict[str, object]:
        raise _removed_not_found("corridor_status", corridor_id)

    @app.get("/api/capacity/vertiports/{vertiport_id}")
    async def capacity_vertiport_detail(vertiport_id: str) -> dict[str, object]:
        raise _removed_not_found("vertiport_status", vertiport_id)

    @app.get("/api/events")
    async def events() -> list[dict[str, object]]:
        return []

    @app.get("/api/events/priority")
    async def events_priority() -> list[dict[str, object]]:
        return []

    @app.get("/api/map/operational-environment")
    async def map_operational_environment() -> dict[str, object]:
        return load_operational_environment()

    @app.get("/api/map/layers")
    async def scenario_map_layers() -> dict[str, object]:
        return operational_environment_map_layers(
            live_tracks=_live_tracks(),
            generated_at=_server_time()["iso"],
        )

    return app
