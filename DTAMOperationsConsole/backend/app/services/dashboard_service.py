"""Service module that provides dashboard cards and overview placeholder data."""

from fastapi import HTTPException

from backend.app.schemas.module import ActionItem, MetricItem, ModuleCard, ModuleOverview


MODULES: list[ModuleCard] = [
    ModuleCard(
        slug="dtam-modules",
        title="DTAM Module Management",
        subtitle="Module process and links",
        description="Review DTAM module connection state and prepare module start or stop commands.",
        icon="dtam-modules",
        accent="#78c8ff",
        endpoint="/api/v1/system/overview",
    ),
    ModuleCard(
        slug="mission",
        title="Simulation Ops",
        subtitle="Mode, playback, and monitoring",
        description="Select operation mode, control playback, weather, wind, and live simulation state.",
        icon="mission",
        accent="#53e0c7",
        endpoint="/api/v1/mission/overview",
    ),
    ModuleCard(
        slug="operations",
        title="Operations Hub",
        subtitle="Fleet and sortie control",
        description="Coordinate fleet status, launch windows, and mission readiness.",
        icon="operations",
        accent="#ffcc6e",
        endpoint="/api/v1/operations/overview",
    ),
    ModuleCard(
        slug="fleet",
        title="Fleet Monitor",
        subtitle="Aircraft status board",
        description="Track vehicle readiness, battery state, maintenance flags, and assigned sorties.",
        icon="fleet",
        accent="#7dd7ff",
        endpoint="/api/v1/fleet/overview",
    ),
    ModuleCard(
        slug="airspace",
        title="Airspace Control",
        subtitle="Corridors and constraints",
        description="Review corridor availability, no-fly zones, altitude bands, and active restrictions.",
        icon="airspace",
        accent="#ff9f7d",
        endpoint="/api/v1/airspace/overview",
    ),
    ModuleCard(
        slug="data",
        title="Data Console",
        subtitle="Logs and data feeds",
        description="Inspect telemetry streams, mission exports, resource files, and replay datasets.",
        icon="data",
        accent="#b8e86d",
        endpoint="/api/v1/data/overview",
    ),
    ModuleCard(
        slug="system",
        title="System Setting",
        subtitle="Platform and service controls",
        description="Handle users, integrations, logs, alarms, and backend services.",
        icon="system",
        accent="#c1b5ff",
        endpoint="/api/v1/system/overview",
    ),
]

MODULE_OVERVIEWS: dict[str, ModuleOverview] = {
    "simulation": ModuleOverview(
        slug="simulation",
        headline="Simulation workspace",
        summary="Tune the digital aircraft model before you start route or control logic work. This folder should eventually own vehicle parameters, sensor models, and scenario presets.",
        status="Ready for configuration",
        metrics=[
            MetricItem(label="Vehicle Profiles", value="12", hint="Primary aircraft and payload variants"),
            MetricItem(label="Scenario Presets", value="08", hint="Reusable startup conditions"),
            MetricItem(label="Physics Fidelity", value="High", hint="Current dynamics solver profile"),
        ],
        actions=[
            ActionItem(id="vehicle-profile", label="Vehicle Profile", description="Airframe, propulsion, payload, and sensor definitions."),
            ActionItem(id="scenario-library", label="Scenario Library", description="Takeoff, cruise, hover, and contingency presets."),
            ActionItem(id="sim-io", label="Simulation I/O", description="Input feeds, replay files, and test output handlers."),
        ],
    ),
    "mission": ModuleOverview(
        slug="mission",
        headline="Mission planning deck",
        summary="Split route generation, waypoint editing, and mission approval into their own submodules. Mission planners should be able to find objectives, paths, and fallback logic here without checking system code.",
        status="Route model loaded",
        metrics=[
            MetricItem(label="Draft Missions", value="05", hint="Missions waiting for review"),
            MetricItem(label="Waypoints", value="143", hint="Points across active mission templates"),
            MetricItem(label="Conflicts", value="02", hint="Airspace or terrain warnings"),
        ],
        actions=[
            ActionItem(id="route-editor", label="Route Editor", description="Waypoint graph, corridor, and leg timing management."),
            ActionItem(id="objective-board", label="Objective Board", description="Mission goals, payload tasks, and constraints."),
            ActionItem(id="recovery-plan", label="Recovery Plan", description="Diversion routes and abort conditions."),
        ],
    ),
    "environment": ModuleOverview(
        slug="environment",
        headline="Environment model",
        summary="Keep geospatial, weather, and terrain sources grouped under one feature so operators can update the world state without touching simulation or system internals.",
        status="Live terrain package online",
        metrics=[
            MetricItem(label="Map Layers", value="21", hint="Terrain, zoning, and airspace overlays"),
            MetricItem(label="Weather Cells", value="14", hint="Tracked weather volumes"),
            MetricItem(label="No-Fly Zones", value="07", hint="Restricted operating regions"),
        ],
        actions=[
            ActionItem(id="terrain-stack", label="Terrain Stack", description="DEM, urban geometry, and obstacle sources."),
            ActionItem(id="weather-model", label="Weather Model", description="Wind, visibility, and turbulence inputs."),
            ActionItem(id="airspace-rules", label="Airspace Rules", description="Corridors, altitude bands, and exclusions."),
        ],
    ),
    "operations": ModuleOverview(
        slug="operations",
        headline="Operations control",
        summary="Use this area for everything tied to live execution: fleet readiness, sortie sequencing, and operator-facing checklists. It keeps launch logic separate from backend settings and from engineering simulation tools.",
        status="2 sorties armed",
        metrics=[
            MetricItem(label="Fleet Ready", value="06 / 08", hint="Vehicles cleared for dispatch"),
            MetricItem(label="Launch Window", value="27m", hint="Time left in current slot"),
            MetricItem(label="Operators", value="04", hint="Console sessions online"),
        ],
        actions=[
            ActionItem(id="fleet-board", label="Fleet Board", description="Vehicle health, charge state, and crew assignment."),
            ActionItem(id="sortie-timeline", label="Sortie Timeline", description="Launch order, staging, and recovery sequence."),
            ActionItem(id="ops-checklist", label="Ops Checklist", description="Preflight and mission execution steps."),
        ],
    ),
    "fleet": ModuleOverview(
        slug="fleet",
        headline="Fleet monitoring",
        summary="Use this module as the live aircraft board for readiness, battery state, maintenance state, and sortie assignment. It should become the operator view for deciding which aircraft can fly next.",
        status="Fleet board online",
        metrics=[
            MetricItem(label="Available Aircraft", value="08", hint="Vehicles visible to the console"),
            MetricItem(label="Ready", value="06", hint="Aircraft cleared for dispatch"),
            MetricItem(label="Maintenance", value="02", hint="Vehicles requiring review"),
        ],
        actions=[
            ActionItem(id="readiness-board", label="Readiness Board", description="Vehicle availability, battery, payload, and comms state."),
            ActionItem(id="assignment-map", label="Assignment Map", description="Match aircraft to active mission legs and staging pads."),
            ActionItem(id="maintenance-queue", label="Maintenance Queue", description="Track faults, service notes, and release status."),
        ],
    ),
    "airspace": ModuleOverview(
        slug="airspace",
        headline="Airspace control",
        summary="Keep corridor state, route constraints, and restricted areas in one operator-facing module. This is where live airspace availability should be reviewed before dispatch.",
        status="Corridor constraints loaded",
        metrics=[
            MetricItem(label="Open Corridors", value="11", hint="Routes available for assignment"),
            MetricItem(label="Restrictions", value="04", hint="Active no-fly or altitude constraints"),
            MetricItem(label="Conflict Alerts", value="01", hint="Items requiring operator review"),
        ],
        actions=[
            ActionItem(id="corridor-state", label="Corridor State", description="Availability, congestion, and route reservations."),
            ActionItem(id="restriction-editor", label="Restriction Editor", description="No-fly areas, temporary holds, and altitude limits."),
            ActionItem(id="conflict-review", label="Conflict Review", description="Airspace warnings and route intersection checks."),
        ],
    ),
    "data": ModuleOverview(
        slug="data",
        headline="Data console",
        summary="Centralize telemetry feeds, replay inputs, mission exports, and static resource files. This module should make data provenance and operator downloads easier to manage.",
        status="Feeds synchronized",
        metrics=[
            MetricItem(label="Live Feeds", value="07", hint="Telemetry and system streams online"),
            MetricItem(label="Mission Exports", value="02", hint="Available export packages"),
            MetricItem(label="Replay Sets", value="05", hint="Recorded datasets ready for review"),
        ],
        actions=[
            ActionItem(id="telemetry-feeds", label="Telemetry Feeds", description="Vehicle, environment, and platform event streams."),
            ActionItem(id="mission-exports", label="Mission Exports", description="Exported flight and operation packages."),
            ActionItem(id="replay-library", label="Replay Library", description="Scenario replays, operator logs, and test datasets."),
        ],
    ),
    "system": ModuleOverview(
        slug="system",
        headline="System configuration",
        summary="Put cross-cutting concerns here: accounts, storage, service orchestration, alarms, and audit logs. Teams should immediately understand that this folder is platform-wide, not mission-specific.",
        status="Core services stable",
        metrics=[
            MetricItem(label="Services", value="09", hint="Backend workers and API processes"),
            MetricItem(label="Alerts", value="01", hint="Items requiring review"),
            MetricItem(label="Connected Clients", value="18", hint="Active browser or operator sessions"),
        ],
        actions=[
            ActionItem(id="access-control", label="Access Control", description="Users, roles, and permission matrices."),
            ActionItem(id="service-health", label="Service Health", description="API health, task workers, and message brokers."),
            ActionItem(id="audit-log", label="Audit Log", description="Operator events, changes, and security records."),
        ],
    ),
}


def list_modules() -> list[ModuleCard]:
    return MODULES


def get_module_overview(slug: str) -> ModuleOverview:
    try:
        return MODULE_OVERVIEWS[slug]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown module: {slug}") from exc
