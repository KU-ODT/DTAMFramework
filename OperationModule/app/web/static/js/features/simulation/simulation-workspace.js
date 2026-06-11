import { getJSON, postJSON } from "../../api/client.js";
import { WEATHER_MAX_POINTS, WEATHER_STEP_METERS, WeatherLayer, WindModel, latToY, lonToX, normalizeWindPreset } from "./wind-layer.js";

const SPEEDS = [1, 2, 4, 8];
const PLAY_STATES = ["play", "pause", "reset"];
const PRECIPITATION_TYPES = ["none", "rainy", "snow"];
const WIND_GRADES = ["normal", "warning", "serious"];
// 1002 wind.grade → Vehicle 바람 모델 (uamodt) preset 매핑
const WIND_GRADE_TO_WEATHER_PRESET = { normal: "good", warning: "fair", serious: "bad" };
const MAP_THEME_KEYS = ["dark", "light"];
const PANEL_MODES = ["environment", "mission"];
const ENVIRONMENT_TOOLS = ["select", "vertiport", "route", "link"];
const OPERATION_MODES = ["single", "traffic"];
const TRAFFIC_DENSITIES = ["low", "middle", "high", "customed"];
const DYNAMICS_MODELS = ["simple", "highFidelity"];
const CONTROLLER_MODES = ["Joystick", "Keyboard", "Autopilot"];
const DEFAULT_SIMULATION_START_TIME = "06:30:00";
const DEFAULT_SIMULATION_START_SECONDS = 6 * 60 * 60 + 30 * 60;
const SECONDS_PER_DAY = 24 * 60 * 60;
const SEOUL_CENTER = [126.978, 37.566];
const INITIAL_ZOOM = 10.85;
const MAX_MAP_ZOOM = 18;
const TILE_METADATA_URL = "/api/v1/tiles/metadata";
const SERVER_TIME_REFRESH_MS = 1000;
const ICD_SEND_DEBOUNCE_MS = 300;
const WEATHER_ICD_SEND_DEBOUNCE_MS = 120;
const COMMERCIAL_TRAFFIC_URL = "/api/v1/traffic/commercial?region=korea";
const FLIGHT_SCHEDULER_LAUNCH_URL = "/api/v1/plugins/uam-scheduler/launch";
const TRAFFIC_FPL_FOLDERS_URL = "/api/v1/traffic/fpl-folders";
const COMMERCIAL_TRAFFIC_REFRESH_MS = 5000;
const COMMERCIAL_AIRCRAFT_SOURCE_ID = "commercial-aircraft";
const COMMERCIAL_AIRCRAFT_LAYER_ID = "commercial-aircraft-symbol";
const COMMERCIAL_AIRCRAFT_SELECTED_LAYER_ID = "commercial-aircraft-selected";
const COMMERCIAL_AIRCRAFT_ICON_ID = "commercial-aircraft-yellow";
const COMMERCIAL_TRACK_SOURCE_ID = "commercial-aircraft-track";
const COMMERCIAL_TRACK_LAYER_IDS = ["commercial-aircraft-track-casing", "commercial-aircraft-track-line"];
const COMMERCIAL_TRAIL_STEPS = 8;
const COMMERCIAL_TRAIL_SECONDS = 210;
const COMMERCIAL_TRAIL_MIN_METERS = 12000;
const COMMERCIAL_TRAIL_MAX_METERS = 52000;
const VEHICLE_STATUS_URL = "/api/v1/simulation/vehicle-status";
const VEHICLE_COLLISION_CLEAR_URL = "/api/v1/simulation/collision";
const UAM_VEHICLE_REFRESH_MS = 1000;
const UAM_VEHICLE_SOURCE_ID = "uam-vehicles";
const UAM_VEHICLE_TRACK_SOURCE_ID = "uam-vehicle-track";
const UAM_VEHICLE_ICON_ID = "uam-plane-map-icon";
const UAM_VEHICLE_ICON_URL = "/resource/plane.png?v=20260516-map-symbol9";
const UAM_VEHICLE_SELECTION_LAYER_ID = "uam-vehicle-selection-ring";
const UAM_VEHICLE_ICON_LAYER_ID = "uam-vehicle-symbol";
const UAM_VEHICLE_LABEL_LAYER_ID = "uam-vehicle-label";
const UAM_VEHICLE_TRACK_LAYER_IDS = ["uam-vehicle-track-casing", "uam-vehicle-track-line"];
const UAM_VEHICLE_POINT_LAYER_IDS = ["uam-vehicle-selected", "uam-vehicle-halo", "uam-vehicle-dot"];
const UAM_VEHICLE_CLICK_LAYER_IDS = ["uam-vehicle-hit-area"];
const UAM_VEHICLE_LAYER_IDS = [
  "uam-vehicle-track-casing",
  "uam-vehicle-track-line",
  UAM_VEHICLE_SELECTION_LAYER_ID,
  UAM_VEHICLE_ICON_LAYER_ID,
  UAM_VEHICLE_LABEL_LAYER_ID,
  "uam-vehicle-hit-area",
];
const UAM_VEHICLE_TRACK_LIMIT = 720;
// 4001 heading/trackHeadingDeg uses GPS bearing: 0=N, 90=E.
// Keep the map icon on the same bearing; the asset orientation is handled in the asset/style.
const UAM_VEHICLE_ICON_HEADING_OFFSET_DEG = 0;
const OPERATIONAL_ENVIRONMENT_URL = "/api/v1/simulation/operational-environment";
const MISSION_ROUTE_URL = "/api/v1/simulation/mission-route";
const LATEST_MISSION_PLANS_URL = "/api/v1/simulation/latest-mission-plans";
const STATE_SERVER_LATEST_MISSION_PLANS_URL = (() => {
  const fallbackUrl = "http://127.0.0.1:8096/api/db/messages/1001/latest";
  try {
    const locationObject = globalThis?.location;
    const protocol = locationObject?.protocol === "https:" ? "https:" : "http:";
    const hostname = locationObject?.hostname || "127.0.0.1";
    return `${protocol}//${hostname}:8096/api/db/messages/1001/latest`;
  } catch {
    return fallbackUrl;
  }
})();
const DTAM_PREPARE_URL = "/api/v1/system/dtam/prepare-execution";
const DTAM_LAUNCH_URL = "/api/v1/system/dtam/launch-world";
const DTAM_APPLY_CONTROL_URL = "/api/v1/system/dtam/apply-control";
const DTAM_RUNTIME_STATUS_URL = "/api/v1/system/dtam/runtime-status";
const DTAM_VFDS_ENSURE_URL = "/api/v1/system/dtam/vfds/ensure";
const DTAM_VFDS_GUI_URL = "http://127.0.0.1:8098/";
const DTAM_RUNTIME_STATUS_REFRESH_MS = 2000;
const DTAM_WORLD_SETTLE_MS = 6000;
const SCHEDULED_FLIGHT_WAIT_MS = 10000;
const SCHEDULED_FLIGHT_POLL_MS = 300;
const DTAM_EXECUTE_READY_WAIT_MS = 5000;
const FLIGHT_PLAN_REQUEST_URL = "/api/v1/icd/2001/send";
const DTAM_EXECUTE_URL = "/api/v1/icd/2002/send";
// 데모 시나리오 → Mission 데모 플랜 팩 (MissionModule/data/demo_plans/<stem>/) 매핑
const DEMO_SCENARIO_FILES = {
  S1: "S1_nominal.json",
  S2: "S2_psu_replan.json",
  S3: "S3_uao_battery_alt_vertiport.json",
};
const ABNORMAL_SITUATION_URL = "/api/v1/icd/5003/send";
const ENV_LINK_SOURCE_ID = "operational-environment-links";
const ENV_VERTIPORT_SOURCE_ID = "operational-environment-vertiports";
const ENV_CORRIDOR_SOURCE_ID = "operational-environment-corridors";
const ENV_LINK_LAYER_IDS = ["operational-vertiport-links", "operational-corridor-spare-links", "operational-corridor-links"];
const ENV_POINT_LAYER_IDS = ["operational-corridor-points"];
const ABNORMAL_ZONE_SOURCE_ID = "abnormal-situation-zone";
const ABNORMAL_ZONE_LAYER_ID = "abnormal-situation-zone";
const ABNORMAL_ZONE_MIN_RADIUS_M = 100;
const ABNORMAL_ZONE_MAX_RADIUS_M = 5000;
const ABNORMAL_ZONE_RADIUS_STEP_M = 100;
const MISSION_ROUTE_SOURCE_ID = "mission-route-preview";
const MISSION_ROUTE_POINT_SOURCE_ID = "mission-route-points";
const MISSION_ROUTE_LAYER_IDS = [
  "mission-route-line-shadow",
  "mission-route-line-halo",
  "mission-route-line",
  "mission-route-points",
];
// DTAM route preview는 SVG overlay를 함께 사용한다.
// 일부 환경에서 MapLibre line layer가 갱신 타이밍/레이어 순서 영향으로 보이지 않는 경우가 있어
// SVG를 표시 보강용으로 쓰고, UAM 주변은 mask cutout으로 비워 비행체가 경로보다 위에 보이게 한다.
const MISSION_ROUTE_SVG_OVERLAY_ENABLED = true;
const ODT_CORRIDOR_DARK = "#f59e0b";
const ODT_CORRIDOR_LIGHT = "#2c6dff";
const ODT_VERTIPORT_LINK = "#60a5fa";
const ODT_VERTIPORT_MARKER = "#10b981";
const ODT_VERTIPORT_SELECTED = "#3b82f6";
const ODT_CORRIDOR_STROKE_DARK = "#141824";
const ODT_WAYPOINT_LABEL = "#fbbf24";
const ODT_HOVER_OUTLINE = "#ffe600";
const DEFAULT_TILE_METADATA = {
  min_zoom: 0,
  max_zoom: 14,
  tile_format: "pbf",
  bounds: [[124.3188, 32.36076], [132.3386, 38.64966]],
  start_view: { lat: 35.50521, lon: 128.3287, zoom: 7 },
  tile_url: "/api/v1/tiles/{z}/{x}/{y}.pbf",
};

const DEFAULT_STATE = {
  playbackSpeed: 1,
  playState: "pause",
  simulationStartTime: DEFAULT_SIMULATION_START_TIME,
  simulationTime: DEFAULT_SIMULATION_START_TIME,
  precipitationType: "none",
  precipitationIntensity: 0,
  fogIntensity: 0,
  weatherVisualizationEnabled: false,
  windGrade: "normal",
  demoScenarioId: null,
  operationMode: "single",
  dynamics: "simple",
  mainVehicleController: "Autopilot",
  connectionStatus: "disconnected",
  modeSaveStatus: "idle",
  modeSaveMessage: "",
  gustEnabled: false,
  gustApplyMode: false,
  gustLat: 37.56,
  gustLon: 126.98,
  gustRadius: 1200,
  mapTheme: "dark",
  activePanel: "environment",
  panelOpen: false,
  commercialTrafficEnabled: false,
  commercialTrafficLoading: false,
  commercialTrafficCount: 0,
  commercialTrafficError: "",
  commercialTrafficSource: "",
  weatherDockOpen: false,
  abnormalDashboardOpen: false,
  abnormalPickMode: false,
  abnormalZoneVisible: false,
  abnormalType: "bird_flock",
  abnormalLat: 37.56,
  abnormalLon: 126.98,
  abnormalAltitudeM: 120,
  abnormalRadiusM: 800,
  abnormalCount: 9,
  abnormalSpeedMps: 12,
  abnormalStatus: "",
  abnormalStatusLevel: "info",
  trafficCustomMissionFolderName: "",
  trafficCustomMissionAction: "",
  trafficSchedulerLaunching: false,
  environmentTool: "select",
  environmentLoading: false,
  environmentStatus: "",
  environmentStatusLevel: "info",
};

const COPY = {
  en: {
    back: "Back",
    title: "DTAM Mission & Operation",
    mapLoading: "Loading map",
    mapLoadingSub: "Connecting Korea MBTiles...",
    syncReady: "1002 Ready",
    syncSending: "1002 Sending",
    syncOk: "1002 Confirmed",
    syncError: "1002 Error",
    play: "Play",
    pause: "Pause",
    reset: "Reset",
    connect: "Connect",
    dtamExecute: "DT World Execute",
    dtamLaunching: "Launching DT World",
    dtamWorldLaunchOk: "DT World launched",
    planning: "Planning",
    execute: "Execute",
    dtamFlowOk: "DTAM execution started",
    dtamPreparing: "Preparing DTAM modules",
    vehicleReady: "VehicleModule ready",
    vfdsReady: "VFDS/KP2A server ready",
    vfdsSkipped: "VFDS skipped: no high-fidelity vehicle",
    vfdsGuiOpening: "Opening VFDS/KP2A GUI",
    vfdsGuiBlocked: "VFDS GUI popup was blocked; open http://127.0.0.1:8098 manually",
    flightPlanWaiting: "Waiting for 3001 ScheduledFlight",
    flightPlanReady: "3001 ScheduledFlight registered",
    flightPlanFallback: "3001 did not arrive; sending 2001 fallback",
    executeReady: "2002 Execute accepted",
    missionIncomplete: "Complete mission planning first.",
    missionSaveRequired: "Complete mission planning and save settings first.",
    modeSaveRequiresMission: "Complete mission planning before saving settings.",
    connectionConnected: "Connected",
    connectionDisconnected: "Disconnected",
    connectionConnecting: "Connecting",
    playback: "Playback",
    playbackPlaying: "Playing",
    speed: "Speed",
    controlPanel: "Control",
    modePanel: "Mode",
    weatherPanel: "Weather",
    windPanel: "Wind",
    close: "X",
    windGrade: "Wind grade",
    visualization: "Visualization",
    visualizationOn: "Visualization ON",
    visualizationOff: "Visualization OFF",
    weatherEffect: "Weather effect",
    precipitation: "Precipitation",
    intensity: "Intensity",
    fog: "Fog",
    localWind: "Local wind",
    applyOn: "Apply mode: ON",
    applyOff: "Apply mode: OFF",
    resetLocal: "Reset local",
    radius: "Radius",
    clickMap: "Enable apply mode, then click a map point.",
    normal: "Normal",
    warning: "Warning",
    serious: "Serious",
    none: "None",
    rainy: "Rain",
    snow: "Snow",
    totalFlights: "Total flights",
    inFlight: "In flight",
    completed: "Completed",
    statusBoard: "Situation Board",
    operationLog: "Operation Log",
    operationAlert: "Operation Alert",
    noTrafficData: "Waiting for traffic data",
    serverTime: "Server time",
    resetView: "Reset view",
    mapTheme: "Map theme",
    dark: "Dark",
    light: "White",
    autoSend: "Auto send",
    sourceMap: "korea.mbtiles",
    rawSource: "OSM PBF",
    gustPoint: "Gust point",
    modeSetup: "Operation Mode",
    modeHint: "Save sends the selected mode settings.",
    single: "Single Flight",
    traffic: "Traffic Sim",
    singleDescription: "Each aircraft can use its own dynamics model.",
    trafficDescription: "Traffic Sim runs without additional Mode Setup fields.",
    vehicleSimulation: "Vehicle Simulation",
    dynamicsModel: "Dynamics model",
    aircraftController: "Aircraft controller",
    simple: "Simple Dynamics",
    highFidelity: "High Fidelity : KP-2A",
    aircraftDynamics: "Dynamics model",
    low: "Low",
    middle: "Middle",
    high: "High",
    customed: "Custom",
    saveSettings: "Save Settings",
    modeSaveIdle: "Ready to save",
    modeSaveSending: "Saving...",
    modeSaveOk: "Mode saved",
    modeSaveError: "Save failed",
    environmentPanel: "Operational Environment",
    environment: "Environment",
    environmentToolSelect: "Select",
    environmentToolVertiport: "V-Port",
    environmentToolRoute: "Route",
    environmentToolLink: "Link",
    environmentSummary: "Vertiports {vertiports} / Routes {routes} / Links {links}",
    environmentLoading: "Loading environment data",
    environmentReady: "DB environment is active",
    environmentHint: "Map click adds data. Point click edits, moves, links, or deletes.",
    environmentRefresh: "Refresh",
    environmentReset: "Reset",
    environmentVertiports: "Vertiports",
    environmentRoutes: "Routes",
    environmentNoItems: "No data",
    environmentSelectTarget: "Select a route node to link.",
    environmentMoveTarget: "Click the map to move the selected item.",
    environmentSaved: "Saved",
    environmentDeleted: "Deleted",
    environmentLinkSaved: "Link saved",
    environmentLinkRemoved: "Link removed",
    environmentLoadError: "Environment load failed",
  },
  ko: {
    back: "돌아가기",
    title: "DTAM 임무&운용",
    mapLoading: "지도 로딩 중",
    mapLoadingSub: "korea.mbtiles 타일 연결 중...",
    syncReady: "1002 대기",
    syncSending: "1002 전송 중",
    syncOk: "1002 확정",
    syncError: "1002 오류",
    play: "재생",
    pause: "정지",
    reset: "DT World 실행",
    playback: "재생 제어",
    playbackPlaying: "재생 중",
    speed: "배속",
    controlPanel: "통제",
    modePanel: "모드",
    weatherPanel: "기상",
    windPanel: "바람",
    close: "X",
    windGrade: "바람 등급",
    visualization: "시각화",
    visualizationOn: "시각화 ON",
    visualizationOff: "시각화 OFF",
    weatherEffect: "기상 효과",
    precipitation: "강수",
    intensity: "강도",
    fog: "안개",
    localWind: "국소 바람",
    applyOn: "적용 모드: ON",
    applyOff: "적용 모드: OFF",
    resetLocal: "국소 초기화",
    radius: "반경",
    clickMap: "적용 모드를 켠 뒤 지도 지점을 클릭하세요.",
    normal: "정상",
    warning: "주의",
    serious: "심각",
    none: "없음",
    rainy: "비",
    snow: "눈",
    totalFlights: "전체 비행",
    inFlight: "비행 중",
    completed: "완료",
    statusBoard: "상황판",
    noTrafficData: "교통 데이터 수신 대기",
    serverTime: "서버 시간",
    resetView: "시점 초기화",
    mapTheme: "지도 테마",
    dark: "다크",
    light: "화이트",
    autoSend: "자동 전송",
    sourceMap: "korea.mbtiles",
    rawSource: "OSM PBF",
    gustPoint: "돌풍 지점",
    modeSetup: "운용 모드",
    modeHint: "설정 저장 시 선택한 모드 데이터가 송신됩니다.",
    single: "단일 비행",
    traffic: "Traffic Sim",
    singleDescription: "비행체별로 동역학 모델을 선택해 운용합니다.",
    trafficDescription: "Traffic Sim은 Mode Setup에서 추가 입력값 없이 운용합니다.",
    vehicleSimulation: "비행체 시뮬레이션",
    dynamicsModel: "동역학 모델",
    aircraftController: "비행체 제어방식",
    simple: "Simple Dynamics",
    highFidelity: "High Fidelity : KP-2A",
    aircraftDynamics: "동역학 모델",
    low: "낮음",
    middle: "보통",
    high: "높음",
    customed: "사용자 정의",
    saveSettings: "설정 저장",
    modeSaveIdle: "저장 대기",
    modeSaveSending: "저장 중...",
    modeSaveOk: "모드 저장 완료",
    modeSaveError: "저장 실패",
    environmentPanel: "운용환경",
    environment: "운용환경",
    environmentToolSelect: "선택",
    environmentToolVertiport: "V-Port",
    environmentToolRoute: "항로",
    environmentToolLink: "Link",
    environmentSummary: "버티포트 {vertiports} / 항로 {routes} / Link {links}",
    environmentLoading: "운용환경 데이터 로딩 중",
    environmentReady: "DB 운용환경 활성화",
    environmentHint: "지도 클릭은 추가, 점 클릭은 수정·이동·링크·삭제입니다.",
    environmentRefresh: "새로고침",
    environmentReset: "기본값",
    environmentVertiports: "버티포트",
    environmentRoutes: "항로",
    environmentNoItems: "데이터 없음",
    environmentSelectTarget: "연결할 항로 노드를 선택하세요.",
    environmentMoveTarget: "지도에서 새 위치를 클릭하세요.",
    environmentSaved: "저장 완료",
    environmentDeleted: "삭제 완료",
    environmentLinkSaved: "Link 저장 완료",
    environmentLinkRemoved: "Link 삭제 완료",
    environmentLoadError: "운용환경 로딩 실패",
  },
};

Object.assign(COPY.en, {
  commercialAircraft: "Commercial aircraft",
  commercialOn: "ON",
  commercialOff: "OFF",
  commercialLoading: "Receiving",
  commercialEmpty: "No aircraft",
  commercialError: "Feed error",
  commercialTracked: "tracked",
  callsign: "Callsign",
  icao24: "ICAO24",
  originCountry: "Origin",
  altitude: "Altitude",
  speed: "Speed",
  heading: "Heading",
  lastContact: "Last contact",
  missionPanel: "Mission Planning",
  missionPlanning: "Mission Planning",
  missionAddAircraft: "Add Aircraft",
  missionDeleteAircraft: "Delete aircraft",
  missionEditing: "Editing",
  demoScenarioLockNotice: "Demo scenario mode ({scenarioId}) — manual vehicle/mission editing is disabled. The mission plan is published in bulk by Mission's demo plan pack. To unlock, select [없음] under 데모 시나리오.",
  missionAircraft: "Aircraft",
  departureTime: "Departure time (STD)",
  timeHour: "Hour",
  timeMinute: "Minute",
  timeSecond: "Second",
  missionFrom: "From",
  missionTo: "To",
  missionRouteInfo: "Route Info",
  missionDistance: "Distance",
  missionWaypoints: "Waypoints",
  missionPath: "Path",
  missionAwaitDeparture: "Select a departure vertiport on the map.",
  missionAwaitArrival: "Select an arrival vertiport on the map.",
  missionReadyHint: "Select an aircraft card, then click departure and arrival on the map.",
  missionRoutePending: "Route pending",
  missionRouteReady: "Route ready",
  missionRouteFailed: "Route compute failed",
  missionRouteComputing: "Computing route...",
  missionSelectVertiport: "Select a vertiport marker on the map.",
  missionSameVertiport: "Departure and arrival must be different.",
  missionNoAircraft: "No aircraft mission is configured.",
  missionResetRoute: "Click the selected aircraft card to pick a new departure and arrival.",
  commonController: "Common",
  inheritController: "Use common",
  trafficDensity: "Traffic density",
  trafficDensityHint: "Select the traffic density preset used by Traffic Sim.",
  trafficCustomMissionHint: "Choose a mission planning folder for custom traffic.",
  trafficRegularFlightGenerate: "Generate Schedule",
  trafficMissionLoad: "Load",
  trafficCustomFolderSelected: "Mission folder selected: {name}",
  trafficCustomFolderGenerateSelected: "Generate folder selected: {name}",
  trafficCustomFolderLoadSelected: "Loaded folder: {name}",
  trafficFplListLoading: "Loading FPL folders...",
  trafficFplListFallback: "FPL folder list unavailable — pick a folder manually.",
  trafficFplFlightCount: "{count} flights",
  trafficSchedulerLaunchStarting: "Opening UAM Flight Scheduler...",
  trafficSchedulerLaunchOk: "UAM Flight Scheduler opened.",
  trafficSchedulerLaunchError: "Failed to open UAM Flight Scheduler.",
  singleDescription: "Select an aircraft card, then plan departure and arrival on the map.",
  trafficDescription: "Choose the traffic density preset used by Traffic Sim.",
});

Object.assign(COPY.en, {
  uamVehicles: "UAM vehicles",
  vehicleStatusWaiting: "Waiting for UAM 4001 data",
  vehicleStatusOffline: "4001 listener offline",
  vehicleDetails: "Vehicle Details",
  currentWaypoint: "Current WP",
  nedPosition: "NED position",
  gpsPosition: "GPS position",
  attitude: "Attitude",
  lastUpdate: "Last update",
  collisionActive: "Collision active",
  collisionStatus: "Collision",
  collisionDetails: "Collision details",
  collisionClearResume: "Clear / Resume",
  collisionClearing: "Clearing...",
  collisionClearOk: "Collision cleared",
  collisionClearError: "Collision clear failed",
});

Object.assign(COPY.ko, {
  commercialAircraft: "상용 항공기",
  commercialOn: "ON",
  commercialOff: "OFF",
  commercialLoading: "수신 중",
  commercialEmpty: "항공기 없음",
  commercialError: "수신 오류",
  commercialTracked: "대 수신",
  callsign: "콜사인",
  icao24: "ICAO24",
  originCountry: "출발 국가",
  altitude: "고도",
  speed: "속도",
  heading: "방위",
  lastContact: "수신 시각",
});

Object.assign(COPY.ko, {
  missionPanel: "임무계획",
  missionPlanning: "임무계획",
  missionAddAircraft: "비행기 추가",
  missionDeleteAircraft: "비행체 삭제",
  missionEditing: "편집 중",
  demoScenarioLockNotice: "데모 시나리오 모드 ({scenarioId}) — 비행체/임무 수동 편집이 비활성화됩니다. 임무 계획은 Mission 의 데모 플랜 팩이 일괄 발행합니다. 해제하려면 데모 시나리오에서 [없음] 선택.",
  missionAircraft: "비행체",
  departureTime: "출발시간(STD)",
  missionFrom: "출발",
  missionTo: "도착",
  missionRouteInfo: "경로 정보",
  missionDistance: "거리",
  missionWaypoints: "경유점",
  missionPath: "경로",
  missionAwaitDeparture: "지도에서 출발 버티포트를 선택하세요.",
  missionAwaitArrival: "지도에서 도착 버티포트를 선택하세요.",
  missionReadyHint: "비행체 박스를 선택한 뒤 지도에서 출발지와 도착지를 눌러주세요.",
  missionRoutePending: "경로 대기",
  missionRouteReady: "경로 생성 완료",
  missionRouteFailed: "경로 계산 실패",
  missionRouteComputing: "경로 계산 중...",
  missionSelectVertiport: "지도에서 버티포트 마커를 선택하세요.",
  missionSameVertiport: "출발지와 도착지는 달라야 합니다.",
  missionNoAircraft: "설정된 비행 임무가 없습니다.",
  missionResetRoute: "선택된 비행체 박스를 누르면 새 출발지와 도착지를 선택합니다.",
  commonController: "공통",
  inheritController: "공통 사용",
  trafficDensity: "교통 밀도",
  trafficDensityHint: "Traffic Sim에서 사용할 교통 밀도를 선택하세요.",
  trafficCustomMissionHint: "사용자 정의 Traffic Sim용 임무계획 폴더를 선택하세요.",
  trafficRegularFlightGenerate: "정기편 생성",
  trafficMissionLoad: "불러오기",
  trafficCustomFolderSelected: "임무계획 폴더 선택: {name}",
  trafficCustomFolderGenerateSelected: "정기편 생성 폴더 선택: {name}",
  trafficCustomFolderLoadSelected: "임무계획 폴더 불러오기: {name}",
  trafficFplListLoading: "FPL 폴더 목록을 불러오는 중...",
  trafficFplListFallback: "FPL 폴더 목록을 가져오지 못해 직접 폴더를 선택합니다.",
  trafficFplFlightCount: "{count}편",
  trafficSchedulerLaunchStarting: "UAM Flight Scheduler를 여는 중입니다...",
  trafficSchedulerLaunchOk: "UAM Flight Scheduler를 열었습니다.",
  trafficSchedulerLaunchError: "UAM Flight Scheduler를 열지 못했습니다.",
  singleDescription: "비행체 박스를 선택한 뒤 지도에서 출발지와 도착지를 계획합니다.",
  trafficDescription: "Traffic Sim에서 사용할 교통 밀도 프리셋을 선택합니다.",
});

Object.assign(COPY.ko, {
  dtamExecute: "DT World 실행",
  dtamLaunching: "DT World 실행 중",
  dtamWorldLaunchOk: "DT World 실행 완료",
  dtamPreparing: "DTAM 모듈 준비 중",
  vehicleReady: "VehicleModule 준비 완료",
  vfdsReady: "VFDS/KP2A 서버 준비 완료",
  vfdsSkipped: "VFDS 생략: 고신뢰도 비행체 없음",
  vfdsGuiOpening: "VFDS/KP2A GUI 여는 중",
  vfdsGuiBlocked: "VFDS GUI 팝업이 차단됨: http://127.0.0.1:8098 을 직접 열어주세요",
  flightPlanWaiting: "3001 ScheduledFlight 수신 대기",
  flightPlanReady: "3001 ScheduledFlight 등록 완료",
  flightPlanFallback: "3001 미수신: 2001 재전송",
  executeReady: "2002 Execute 수신 확인",
  missionIncomplete: "임무계획을 완료해 주세요",
  missionSaveRequired: "임무계획을 완료하고 설정 저장을 먼저 눌러주세요",
  modeSaveRequiresMission: "임무계획을 완료한 뒤 설정 저장을 눌러주세요",
  operationLog: "운용 로그",
  operationAlert: "운용 확인",
  connectionConnected: "연결됨",
  connectionDisconnected: "연결 안 됨",
  connectionConnecting: "연결 중",
  collisionActive: "충돌 활성",
  collisionStatus: "충돌",
  collisionDetails: "충돌 정보",
  collisionClearResume: "해제 / 재개",
  collisionClearing: "해제 중...",
  collisionClearOk: "충돌 해제 완료",
  collisionClearError: "충돌 해제 실패",
});

Object.assign(COPY.ko, {
  uamVehicles: "UAM 비행체",
  vehicleStatusWaiting: "UAM 4001 데이터 수신 대기",
  vehicleStatusOffline: "4001 리스너 오프라인",
  vehicleDetails: "비행체 상세",
  currentWaypoint: "현재 WP",
  nedPosition: "NED 위치",
  gpsPosition: "GPS 위치",
  attitude: "자세",
  lastUpdate: "최근 수신",
});

Object.assign(COPY.en, {
  abnormalDashboard: "Abnormal Situation",
  abnormalDashboardTitle: "Abnormal Situation Dashboard",
  abnormalDashboardMeta: "Bird flock / obstacle",
  birdFlockSpawn: "Bird flock",
  birdFlockDescription: "Select an outbreak area on the map, adjust radius with the mouse wheel, then apply once.",
  abnormalPickArea: "Pick area",
  abnormalPicking: "Picking...",
  abnormalApply: "Apply once",
  abnormalClear: "Clear zone",
  abnormalRadius: "Radius",
  abnormalCount: "Count",
  abnormalSpeed: "Speed",
  abnormalCenter: "Center",
  abnormalNoCenter: "No center selected",
  abnormalWheelHint: "Map click sets the center. Mouse wheel changes the circle radius.",
  abnormalSpawnOk: "Bird flock command sent.",
  abnormalSpawnError: "Failed to send abnormal situation command",
});

Object.assign(COPY.ko, {
  abnormalDashboard: "비정상 상황",
  abnormalDashboardTitle: "비정상 상황 대시보드",
  abnormalDashboardMeta: "새떼 / 장애물",
  birdFlockSpawn: "새떼 출현",
  birdFlockDescription: "지도에서 출몰 구역을 지정하고, 마우스 휠로 반경을 조정한 뒤 1회 적용합니다.",
  abnormalPickArea: "출몰 구역 지정",
  abnormalPicking: "구역 지정 중",
  abnormalApply: "1회 적용",
  abnormalClear: "구역 초기화",
  abnormalRadius: "반경",
  abnormalCount: "개체 수",
  abnormalSpeed: "속도",
  abnormalCenter: "중심",
  abnormalNoCenter: "중심 미선택",
  abnormalWheelHint: "지도 클릭으로 중심을 지정하고, 마우스 휠로 원 반경을 조정합니다.",
  abnormalSpawnOk: "새떼 출현 명령을 전송했습니다.",
  abnormalSpawnError: "비정상 상황 명령 전송 실패",
});

const MAP_PALETTES = {
  dark: {
    background: "#223447",
    sky: "#304761",
    tileLand: "#223447",
    landcover: "#182522",
    landuse: "#1b2320",
    park: "#1d3024",
    water: "#142a3e",
    waterLine: "#1f425e",
    boundary: "#5e6872",
    roadCasing: "#4a453a",
    road: "#4a453a",
    roadMajor: "#4a453a",
    building: "#2f2c2a",
    label: "#7c8b9a",
    labelHalo: "#223447",
  },
  light: {
    background: "#6bbbe6",
    tileLand: "#e5efd9",
    landcover: "#cce2c4",
    landuse: "#d7e8cb",
    park: "#afd3a4",
    water: "#4faee0",
    waterLine: "#328fc2",
    boundary: "#7a8172",
    roadCasing: "#f5efe3",
    road: "#b9aa92",
    roadMajor: "#836f55",
    building: "#c8c0b4",
    label: "#24301f",
    labelHalo: "#f8f4ea",
  },
};

let mapLibrePromise = null;

function normalizeLanguage(language) {
  return language === "ko" ? "ko" : "en";
}

function ensureMapLibre() {
  if (window.maplibregl) {
    return Promise.resolve(window.maplibregl);
  }
  if (mapLibrePromise) {
    return mapLibrePromise;
  }
  mapLibrePromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "/static/vendor/maplibre-gl.js";
    script.async = true;
    script.onload = () => (window.maplibregl ? resolve(window.maplibregl) : reject(new Error("MapLibre unavailable")));
    script.onerror = () => reject(new Error("MapLibre script load failed"));
    document.head.append(script);
  });
  return mapLibrePromise;
}

function normalizeNumber(value, min, max, fallback) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, numeric));
}

function normalizeDegrees(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return 0;
  }
  return ((numeric % 360) + 360) % 360;
}

function step01(value) {
  return Math.round(Number(value) * 10) / 10;
}

function pct(value) {
  return `${Math.round(Number(value) * 100)}%`;
}

function normalizeDynamicsModel(value) {
  return DYNAMICS_MODELS.includes(value) ? value : "simple";
}

function defaultMissionDepartureTime() {
  return DEFAULT_SIMULATION_START_TIME;
}

function normalizeMissionDepartureTime(value, fallback = defaultMissionDepartureTime()) {
  let text = String(value || "").trim();
  if (/^\d{4}$/.test(text) || /^\d{6}$/.test(text)) {
    const compact = text;
    text = `${compact.slice(0, 2)}:${compact.slice(2, 4)}:${compact.length === 6 ? compact.slice(4, 6) : "00"}`;
  }
  const match = text.match(/^(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?$/);
  if (!match) {
    return fallback;
  }
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  const seconds = Number(match[3] || 0);
  if (
    !Number.isInteger(hours) || hours < 0 || hours > 23
    || !Number.isInteger(minutes) || minutes < 0 || minutes > 59
    || !Number.isInteger(seconds) || seconds < 0 || seconds > 59
  ) {
    return fallback;
  }
  const pad = (number) => String(number).padStart(2, "0");
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
}

function missionTimeToSeconds(value, fallbackSeconds = DEFAULT_SIMULATION_START_SECONDS) {
  const hms = normalizeMissionDepartureTime(value, "");
  if (!hms) {
    return fallbackSeconds;
  }
  const [hours, minutes, seconds] = hms.split(":").map(Number);
  return hours * 3600 + minutes * 60 + seconds;
}

function secondsToMissionTime(value) {
  const total = Math.floor(normalizeNumber(value, 0, Number.MAX_SAFE_INTEGER, DEFAULT_SIMULATION_START_SECONDS)) % SECONDS_PER_DAY;
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  const pad = (number) => String(number).padStart(2, "0");
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
}

function seoulDatePart(date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value || "00";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function createMissionAircraftEntry(index = 1, dynamics = "simple") {
  const label = `UAM ${index}`;
  const departureTime = defaultMissionDepartureTime();
  return {
    id: `mission-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    aircraftName: label,
    departureTime,
    std: departureTime,
    departureName: "",
    arrivalName: "",
    routeData: null,
    dynamics: normalizeDynamicsModel(dynamics),
    controllerOverride: "",
  };
}

function isFiniteNumber(value) {
  return Number.isFinite(Number(value));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function simIcon(name) {
  const icons = {
    mode: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 5h16" />
        <path d="M4 12h16" />
        <path d="M4 19h16" />
        <circle cx="8" cy="5" r="2" />
        <circle cx="15" cy="12" r="2" />
        <circle cx="11" cy="19" r="2" />
      </svg>
    `,
    singleMode: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3 17.5 15H6.5L12 3Z" />
        <path d="M12 15v6" />
        <path d="M9 18h6" />
      </svg>
    `,
    trafficMode: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M5 7h14" />
        <path d="M5 17h14" />
        <circle cx="8" cy="7" r="2.2" />
        <circle cx="16" cy="17" r="2.2" />
        <path d="M8 9.2v5.6" />
        <path d="M16 9.2v5.6" />
      </svg>
    `,
    weather: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7.2 15.8h9.4a3.5 3.5 0 0 0 .4-7 5.1 5.1 0 0 0-9.6-1.3A4.2 4.2 0 0 0 7.2 15.8Z" />
        <path d="M8 19h.01M12 19h.01M16 19h.01" />
      </svg>
    `,
    environment: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="6" cy="7" r="2.2" />
        <circle cx="18" cy="6" r="2.2" />
        <circle cx="9" cy="18" r="2.2" />
        <path d="M8.1 7.8 15.9 6.4" />
        <path d="M7 9 8.4 15.8" />
        <path d="M10.8 16.5 16.5 8" />
      </svg>
    `,
    vertiport: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3v18" />
        <path d="M5 6h14" />
        <path d="M7 18h10" />
        <circle cx="12" cy="12" r="4" />
      </svg>
    `,
    route: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M5 18 10 6l4 12 5-12" />
        <circle cx="5" cy="18" r="2" />
        <circle cx="10" cy="6" r="2" />
        <circle cx="14" cy="18" r="2" />
        <circle cx="19" cy="6" r="2" />
      </svg>
    `,
    link: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M9.5 7.5 7.8 5.8a4 4 0 0 0-5.7 5.7l2.4 2.4a4 4 0 0 0 5.7 0" />
        <path d="m14.5 16.5 1.7 1.7a4 4 0 0 0 5.7-5.7l-2.4-2.4a4 4 0 0 0-5.7 0" />
        <path d="M8 16 16 8" />
      </svg>
    `,
    mission: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3.5 11.5 20 4l-6.2 16.1-2.2-6.4-6.4-2.2Z" />
        <path d="M11.6 13.7 20 4" />
      </svg>
    `,
    playback: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M5 5v14" />
        <path d="m9 7 8 5-8 5V7Z" />
        <path d="M19 7v10" />
      </svg>
    `,
    dark: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M18.5 15.4A7.5 7.5 0 0 1 8.6 5.5 7.5 7.5 0 1 0 18.5 15.4Z" />
      </svg>
    `,
    light: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
      </svg>
    `,
    zoomIn: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="11" cy="11" r="6" />
        <path d="M11 8v6M8 11h6M16 16l4 4" />
      </svg>
    `,
    zoomOut: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="11" cy="11" r="6" />
        <path d="M8 11h6M16 16l4 4" />
      </svg>
    `,
    resetView: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
        <circle cx="12" cy="12" r="5" />
        <circle cx="12" cy="12" r="1.2" />
      </svg>
    `,
    aircraft: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 2.2 9.6 10 3 14.1v2.1l7.4-2.1-.5 4.1-2.3 1.7v1.5l4.4-.9 4.4.9v-1.5l-2.3-1.7-.5-4.1 7.4 2.1v-2.1L14.4 10 12 2.2Z" />
      </svg>
    `,
    abnormal: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3 20 18H4L12 3Z" />
        <path d="M12 8v5" />
        <circle cx="12" cy="16.5" r="1" />
      </svg>
    `,
    bird: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3 12.8c3.4-3.5 6.8-3.4 9.4.2 2.4-3.5 5.4-4.2 8.6-1.5" />
        <path d="M6.2 13.3c2.4-1.2 4.2-.7 5.8 1.7" />
        <path d="M12.2 15c1.6-2.4 3.6-3 5.8-1.6" />
      </svg>
    `,
    trash: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 7h16" />
        <path d="M9 7V4h6v3" />
        <path d="M8 10v8" />
        <path d="M12 10v8" />
        <path d="M16 10v8" />
        <path d="M6 7l1 13h10l1-13" />
      </svg>
    `,
  };
  return icons[name] || "";
}

function tileBounds(metadata) {
  const bounds = metadata?.bounds;
  if (Array.isArray(bounds) && bounds.length === 2) {
    return bounds;
  }
  return DEFAULT_TILE_METADATA.bounds;
}

function tileLandBase(metadata) {
  const [[west, south], [east, north]] = tileBounds(metadata);
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: {},
        geometry: {
          type: "Polygon",
          coordinates: [
            [
              [west, south],
              [east, south],
              [east, north],
              [west, north],
              [west, south],
            ],
          ],
        },
      },
    ],
  };
}

function absolutizeUrl(url) {
  if (/^https?:\/\//i.test(url)) {
    return url;
  }
  if (url.startsWith("/")) {
    return `${window.location.origin}${url}`;
  }
  return `${window.location.origin}/${url.replace(/^\.?\//, "")}`;
}

function tileUrl(metadata) {
  return absolutizeUrl(metadata?.tile_url || DEFAULT_TILE_METADATA.tile_url);
}

function buildOdtDarkMapLayers(palette) {
  return [
    { id: "background", type: "background", paint: { "background-color": palette.background } },
    {
      id: "landcover",
      type: "fill",
      source: "mbtiles",
      "source-layer": "landcover",
      paint: { "fill-color": palette.landcover, "fill-opacity": 0.7, "fill-opacity-transition": { duration: 300 } },
    },
    {
      id: "landuse",
      type: "fill",
      source: "mbtiles",
      "source-layer": "landuse",
      paint: { "fill-color": palette.landuse, "fill-opacity": 0.7, "fill-opacity-transition": { duration: 300 } },
    },
    {
      id: "park",
      type: "fill",
      source: "mbtiles",
      "source-layer": "park",
      paint: { "fill-color": palette.park, "fill-opacity": 0.85, "fill-opacity-transition": { duration: 300 } },
    },
    {
      id: "water",
      type: "fill",
      source: "mbtiles",
      "source-layer": "water",
      paint: { "fill-color": palette.water, "fill-color-transition": { duration: 300 } },
    },
    {
      id: "waterway",
      type: "line",
      source: "mbtiles",
      "source-layer": "waterway",
      paint: { "line-color": palette.waterLine, "line-width": 1, "line-color-transition": { duration: 300 } },
    },
    {
      id: "boundary",
      type: "line",
      source: "mbtiles",
      "source-layer": "boundary",
      paint: {
        "line-color": palette.boundary,
        "line-width": 1,
        "line-dasharray": [2, 2],
        "line-color-transition": { duration: 300 },
      },
    },
    {
      id: "transportation",
      type: "line",
      source: "mbtiles",
      "source-layer": "transportation",
      paint: {
        "line-color": palette.road,
        "line-width": ["interpolate", ["linear"], ["zoom"], 5, 0.4, 10, 1, 14, 2.5],
        "line-color-transition": { duration: 300 },
      },
    },
    {
      id: "building",
      type: "fill",
      source: "mbtiles",
      "source-layer": "building",
      minzoom: 13,
      paint: { "fill-color": palette.building, "fill-opacity": 0.6, "fill-opacity-transition": { duration: 300 } },
    },
  ];
}

function buildMapStyle(theme, metadata = DEFAULT_TILE_METADATA) {
  const palette = MAP_PALETTES[theme] || MAP_PALETTES.dark;
  const maxZoom = Number(metadata?.max_zoom ?? DEFAULT_TILE_METADATA.max_zoom);
  const minZoom = Number(metadata?.min_zoom ?? DEFAULT_TILE_METADATA.min_zoom);

  return {
    version: 8,
    name: `DTAM Korea ${theme}`,
    glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
    sources: {
      tileLandBase: {
        type: "geojson",
        data: tileLandBase(metadata),
      },
      mbtiles: {
        type: "vector",
        tiles: [tileUrl(metadata)],
        minzoom: minZoom,
        maxzoom: maxZoom,
        bounds: tileBounds(metadata).flat(),
      },
    },
    layers: theme === "dark" ? buildOdtDarkMapLayers(palette) : [
      { id: "background", type: "background", paint: { "background-color": palette.background } },
      {
        id: "tile-land-base",
        type: "fill",
        source: "tileLandBase",
        paint: { "fill-color": palette.tileLand, "fill-opacity": 1 },
      },
      {
        id: "landcover",
        type: "fill",
        source: "mbtiles",
        "source-layer": "landcover",
        paint: { "fill-color": palette.landcover, "fill-opacity": 0.9 },
      },
      {
        id: "landuse",
        type: "fill",
        source: "mbtiles",
        "source-layer": "landuse",
        paint: { "fill-color": palette.landuse, "fill-opacity": 0.88 },
      },
      {
        id: "park",
        type: "fill",
        source: "mbtiles",
        "source-layer": "park",
        paint: { "fill-color": palette.park, "fill-opacity": 0.8 },
      },
      {
        id: "water",
        type: "fill",
        source: "mbtiles",
        "source-layer": "water",
        paint: { "fill-color": palette.water, "fill-opacity": 0.92 },
      },
      {
        id: "waterway",
        type: "line",
        source: "mbtiles",
        "source-layer": "waterway",
        paint: {
          "line-color": palette.waterLine,
          "line-opacity": 0.75,
          "line-width": ["interpolate", ["linear"], ["zoom"], 7, 0.5, 13, 2.2],
        },
      },
      {
        id: "boundary",
        type: "line",
        source: "mbtiles",
        "source-layer": "boundary",
        paint: {
          "line-color": palette.boundary,
          "line-opacity": 0.48,
          "line-width": ["interpolate", ["linear"], ["zoom"], 5, 0.5, 12, 1.4],
        },
      },
      {
        id: "transportation-casing-minor",
        type: "line",
        source: "mbtiles",
        "source-layer": "transportation",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": palette.roadCasing,
          "line-opacity": 0.24,
          "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.25, 12, 1.05, 14, 2],
        },
      },
      {
        id: "transportation-casing-medium",
        type: "line",
        source: "mbtiles",
        "source-layer": "transportation",
        filter: ["in", ["get", "class"], ["literal", ["secondary", "tertiary"]]],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": palette.roadCasing,
          "line-opacity": 0.42,
          "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.7, 12, 2.4, 14, 4.4],
        },
      },
      {
        id: "transportation-casing-major",
        type: "line",
        source: "mbtiles",
        "source-layer": "transportation",
        filter: ["in", ["get", "class"], ["literal", ["motorway", "trunk", "primary"]]],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": palette.roadCasing,
          "line-opacity": 0.58,
          "line-width": ["interpolate", ["linear"], ["zoom"], 8, 1, 12, 4.2, 14, 8],
        },
      },
      {
        id: "transportation-minor",
        type: "line",
        source: "mbtiles",
        "source-layer": "transportation",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": palette.road,
          "line-opacity": ["interpolate", ["linear"], ["zoom"], 8, 0.28, 13, 0.58],
          "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.22, 12, 0.65, 14, 1.25],
        },
      },
      {
        id: "transportation-medium",
        type: "line",
        source: "mbtiles",
        "source-layer": "transportation",
        filter: ["in", ["get", "class"], ["literal", ["secondary", "tertiary"]]],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": palette.road,
          "line-opacity": ["interpolate", ["linear"], ["zoom"], 8, 0.42, 13, 0.78],
          "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.45, 12, 1.35, 14, 2.4],
        },
      },
      {
        id: "transportation-major",
        type: "line",
        source: "mbtiles",
        "source-layer": "transportation",
        filter: ["in", ["get", "class"], ["literal", ["motorway", "trunk", "primary"]]],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": palette.roadMajor,
          "line-opacity": ["interpolate", ["linear"], ["zoom"], 8, 0.5, 13, 0.88],
          "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.75, 12, 2.6, 14, 5],
        },
      },
      {
        id: "aeroway",
        type: "line",
        source: "mbtiles",
        "source-layer": "aeroway",
        minzoom: 10,
        paint: {
          "line-color": theme === "dark" ? "#76d8ff" : "#396f8b",
          "line-opacity": 0.75,
          "line-width": 1.6,
        },
      },
      {
        id: "building",
        type: "fill",
        source: "mbtiles",
        "source-layer": "building",
        minzoom: 12,
        paint: {
          "fill-color": palette.building,
          "fill-opacity": ["interpolate", ["linear"], ["zoom"], 12, 0.28, 14, 0.68],
        },
      },
      {
        id: "place-label-city",
        type: "symbol",
        source: "mbtiles",
        "source-layer": "place",
        minzoom: 7,
        filter: ["in", ["get", "class"], ["literal", ["city", "town"]]],
        layout: {
          "text-field": ["coalesce", ["get", "name:latin"], ["get", "name:en"], ["get", "name"]],
          "text-font": ["Open Sans Regular", "Arial Unicode MS Regular"],
          "text-size": ["interpolate", ["linear"], ["zoom"], 7, 11, 12, 15],
          "text-anchor": "center",
          "text-allow-overlap": false,
        },
        paint: {
          "text-color": palette.label,
          "text-halo-color": palette.labelHalo,
          "text-halo-width": 1.4,
        },
      },
      {
        id: "place-label-district",
        type: "symbol",
        source: "mbtiles",
        "source-layer": "place",
        minzoom: 9,
        filter: [
          "in",
          ["get", "class"],
          ["literal", ["suburb", "borough", "district", "county", "municipality", "locality", "village"]],
        ],
        layout: {
          "text-field": ["coalesce", ["get", "name:latin"], ["get", "name:en"], ["get", "name"]],
          "text-font": ["Open Sans Regular", "Arial Unicode MS Regular"],
          "text-size": ["interpolate", ["linear"], ["zoom"], 9, 9, 12, 11, 14, 13],
          "text-anchor": "center",
          "text-allow-overlap": false,
        },
        paint: {
          "text-color": palette.label,
          "text-halo-color": palette.labelHalo,
          "text-halo-width": 1.2,
        },
      },
      {
        id: "transportation-label",
        type: "symbol",
        source: "mbtiles",
        "source-layer": "transportation_name",
        minzoom: 12,
        layout: {
          "symbol-placement": "line",
          "text-field": ["coalesce", ["get", "name:latin"], ["get", "name:en"], ["get", "name"], ["get", "ref"]],
          "text-font": ["Open Sans Regular", "Arial Unicode MS Regular"],
          "text-size": 10,
        },
        paint: {
          "text-color": palette.label,
          "text-halo-color": palette.labelHalo,
          "text-halo-width": 1,
        },
      },
    ],
  };
}

class SimulationWorkspace {
  constructor(container, options = {}) {
    this.container = container;
    this.language = normalizeLanguage(options.language);
    this.onBack = typeof options.onBack === "function" ? options.onBack : () => {};
    const initialMission = createMissionAircraftEntry(1);
    this.state = {
      ...DEFAULT_STATE,
      missionEntries: [initialMission],
      activeMissionId: initialMission.id,
      missionInputMode: false,
      missionInputTarget: "departure",
      missionStatusLevel: "info",
      missionStatusMessage: "",
      operationLogs: [],
      trafficDensity: "middle",
    };
    this.tileMetadata = null;
    this.map = null;
    this.windModel = null;
    this.windLayer = null;
    this.sendTimer = null;
    this.operationLogTimer = null;
    this.serverTimeTimer = null;
    this.dtamRuntimeStatusTimer = null;
    this.dtamRuntimeStatusLoading = false;
    this.dtamRuntimeStatus = null;
    this.uamVehicleTimer = null;
    this.uamVehicleSeq = 0;
    this.uamVehicleStatusLoading = false;
    this.uamVehicles = [];
    this.uamVehicleMarkerPositions = new Map();
    this.uamVehicleTracks = new Map();
    this.uamVehiclePopup = null;
    this.selectedUamVehicleId = null;
    this.uamVehicleAutoCentered = false;
    this.uamVehicleMapEventsBound = false;
    this.uamVehicleIconLoading = false;
    this.vehicleStatusListening = false;
    this.vehicleStatusError = "";
    this.commercialTrafficTimer = null;
    this.commercialTrafficSeq = 0;
    this.commercialAircraft = [];
    this.commercialAircraftMarkers = new Map();
    this.commercialAircraftMarkerPositions = new Map();
    this.commercialAircraftMarkerAnimations = new Map();
    this.commercialAircraftPopup = null;
    this.commercialTrackAnimation = null;
    this.selectedCommercialAircraftId = null;
    this.commercialAircraftMapEventsBound = false;
    this.operationalEnvironment = { vertiports: [], corridors: [], basestations: [], links: [] };
    this.environmentDataLoaded = false;
    this.environmentLoadPromise = null;
    this.environmentPopup = null;
    this.environmentSelection = null;
    this.environmentMoveTarget = null;
    this.environmentLinkSource = null;
    this.environmentMapEventsBound = false;
    this.environmentVertiportMarkers = new Map();
    this.overlayRestoreTimer = null;
    this.missionRouteOverlay = null;
    this.missionRouteOverlayFrame = 0;
    this.missionRouteOverlayUpdateHandler = null;
    this.latestMissionPlanLoading = false;
    this.latestMissionPlanPromise = null;
    this.missionRouteRequestSeq = 0;
    this.missionEntryCount = 1;
    this.sendSeq = 0;
    this.executionPreparationKey = "";
    this.executionArmKey = "";
    this.savedModeSettingsKey = "";
    this.vfdsGuiWindow = null;
    this.vfdsGuiOpenWarned = false;
    this.destroyed = false;
    this.status = "ready";
    this.statusMessage = "";
    this.serverTimeText = "-";
    this.simulationClockAnchorSeconds = DEFAULT_SIMULATION_START_SECONDS;
    this.simulationClockAnchorWallMs = Date.now();
    this.simulationClockDatePart = seoulDatePart();
  }

  mount() {
    this.destroyed = false;
    this.render();
    this.bindControls();
    this.loadOperationalEnvironment();
    this.initMap();
    this.startServerTime();
    this.startDtamRuntimeStatusPolling();
    this.startUamVehiclePolling();
    this.scheduleSend({ immediate: true });
    return {
      updateLanguage: (language) => this.updateLanguage(language),
      show: () => this.show(),
      destroy: () => this.destroy(),
    };
  }

  show() {
    if (this.destroyed) {
      return;
    }
    window.setTimeout(() => {
      if (this.destroyed) {
        return;
      }
      this.map?.resize();
      this.restoreMapOverlayLayers();
      this.updateMissionRouteOverlay();
      this.renderUamVehicles();
      this.renderCommercialAircraft();
      this.updateUamVehicleDetailPanel();
      this.refreshDtamRuntimeStatus();
      this.refreshUamVehicleStatus();
    }, 0);
  }

  updateLanguage(language) {
    this.language = normalizeLanguage(language);
    this.windLayer?.stop();
    this.windLayer = null;
    this.windModel = null;
    this.clearUamVehicleOverlay();
    this.clearCommercialAircraftOverlay();
    this.clearEnvironmentVertiportMarkers();
    this.environmentPopup?.remove();
    this.environmentPopup = null;
    window.clearTimeout(this.overlayRestoreTimer);
    this.overlayRestoreTimer = null;
    this.clearMissionRouteSvgOverlay();
    if (this.map) {
      this.map.remove();
      this.map = null;
    }
    this.commercialAircraftMapEventsBound = false;
    this.uamVehicleMapEventsBound = false;
    this.environmentMapEventsBound = false;
    this.render();
    this.bindControls();
    this.initMap();
    this.updateStatus();
  }

  destroy() {
    this.destroyed = true;
    window.clearTimeout(this.sendTimer);
    window.clearTimeout(this.operationLogTimer);
    window.clearTimeout(this.overlayRestoreTimer);
    window.clearInterval(this.serverTimeTimer);
    window.clearInterval(this.dtamRuntimeStatusTimer);
    window.clearInterval(this.uamVehicleTimer);
    window.clearInterval(this.commercialTrafficTimer);
    this.clearUamVehicleOverlay();
    this.clearCommercialAircraftOverlay();
    this.clearEnvironmentVertiportMarkers();
    this.environmentPopup?.remove();
    this.environmentPopup = null;
    this.clearMissionRouteSvgOverlay();
    this.windLayer?.stop();
    this.windLayer = null;
    this.windModel = null;
    if (this.map) {
      this.map.remove();
      this.map = null;
    }
    this.uamVehicleMapEventsBound = false;
    this.environmentMapEventsBound = false;
    this.overlayRestoreTimer = null;
    this.operationLogTimer = null;
    this.container.replaceChildren();
  }

  t(key) {
    return COPY[this.language][key] || COPY.en[key] || key;
  }

  tf(key, replacements = {}) {
    return Object.entries(replacements).reduce(
      (text, [name, value]) => text.replaceAll(`{${name}}`, String(value)),
      this.t(key),
    );
  }

  async loadTileMetadata() {
    if (this.tileMetadata) {
      return this.tileMetadata;
    }
    try {
      const response = await fetch(TILE_METADATA_URL, { headers: { Accept: "application/json" } });
      if (!response.ok) {
        throw new Error(`tile metadata ${response.status}`);
      }
      this.tileMetadata = await response.json();
    } catch (error) {
      this.tileMetadata = DEFAULT_TILE_METADATA;
      this.status = "error";
      this.statusMessage = error.message;
      this.updateStatus();
    }
    return this.tileMetadata;
  }

  currentSimulationSeconds() {
    const anchor = Number.isFinite(Number(this.simulationClockAnchorSeconds))
      ? Number(this.simulationClockAnchorSeconds)
      : missionTimeToSeconds(this.state.simulationTime, DEFAULT_SIMULATION_START_SECONDS);
    if (this.state.playState !== "play") {
      return anchor;
    }
    const elapsedS = Math.max(0, (Date.now() - Number(this.simulationClockAnchorWallMs || Date.now())) / 1000);
    const speed = SPEEDS.includes(Number(this.state.playbackSpeed)) ? Number(this.state.playbackSpeed) : 1;
    return anchor + elapsedS * speed;
  }

  syncSimulationClockToState() {
    const currentSeconds = this.currentSimulationSeconds();
    this.state.simulationTime = secondsToMissionTime(currentSeconds);
    return currentSeconds;
  }

  formatSimulationServerTime() {
    const seconds = this.syncSimulationClockToState();
    const dayOffset = Math.floor(seconds / SECONDS_PER_DAY);
    let datePart = this.simulationClockDatePart || seoulDatePart();
    if (dayOffset > 0) {
      const [year, month, day] = datePart.split("-").map(Number);
      const date = new Date(Date.UTC(year, month - 1, day + dayOffset));
      datePart = date.toISOString().slice(0, 10);
    }
    return `${datePart} ${secondsToMissionTime(seconds)} KST`;
  }

  captureSimulationClock() {
    this.simulationClockAnchorSeconds = this.syncSimulationClockToState();
    this.simulationClockAnchorWallMs = Date.now();
  }

  setPlayState(nextState) {
    const normalized = PLAY_STATES.includes(nextState) ? nextState : "pause";
    this.captureSimulationClock();
    if (normalized === "reset") {
      const startTime = normalizeMissionDepartureTime(this.state.simulationStartTime, DEFAULT_SIMULATION_START_TIME);
      this.state.simulationStartTime = startTime;
      this.state.simulationTime = startTime;
      this.simulationClockAnchorSeconds = missionTimeToSeconds(startTime, DEFAULT_SIMULATION_START_SECONDS);
      this.state.playState = "pause";
    } else {
      this.state.playState = normalized;
    }
    this.simulationClockAnchorWallMs = Date.now();
    this.refreshServerTime();
  }

  setPlaybackSpeed(speed) {
    this.captureSimulationClock();
    this.state.playbackSpeed = SPEEDS.includes(speed) ? speed : 1;
    this.simulationClockAnchorWallMs = Date.now();
    this.refreshServerTime();
  }

  async refreshServerTime() {
    this.syncSimulationClockToState();
    this.serverTimeText = this.formatSimulationServerTime();
    this.container.querySelector("[data-server-time]")?.replaceChildren(document.createTextNode(this.serverTimeText));
  }

  startServerTime() {
    window.clearInterval(this.serverTimeTimer);
    this.refreshServerTime();
    this.serverTimeTimer = window.setInterval(() => this.refreshServerTime(), SERVER_TIME_REFRESH_MS);
  }

  startDtamRuntimeStatusPolling() {
    window.clearInterval(this.dtamRuntimeStatusTimer);
    this.refreshDtamRuntimeStatus();
    this.dtamRuntimeStatusTimer = window.setInterval(
      () => this.refreshDtamRuntimeStatus(),
      DTAM_RUNTIME_STATUS_REFRESH_MS,
    );
  }

  async refreshDtamRuntimeStatus() {
    if (this.destroyed || this.dtamRuntimeStatusLoading) {
      return;
    }
    this.dtamRuntimeStatusLoading = true;
    try {
      const data = await this.fetchDtamRuntimeStatus();
      if (this.destroyed) {
        return;
      }
      const nextStatus = data?.running || data?.airmobility_ready
        ? "connected"
        : (this.status === "sending" || this.state.connectionStatus === "connecting" ? "connecting" : "disconnected");
      this.applyDtamConnectionStatus(nextStatus);
    } catch {
      if (this.destroyed) {
        return;
      }
      if (this.status !== "sending" && this.state.connectionStatus !== "connecting") {
        this.applyDtamConnectionStatus("disconnected");
      }
    } finally {
      this.dtamRuntimeStatusLoading = false;
    }
  }

  async fetchDtamRuntimeStatus() {
    const data = await getJSON(`${DTAM_RUNTIME_STATUS_URL}?t=${Date.now()}`);
    this.dtamRuntimeStatus = data || null;
    return data || {};
  }

  applyDtamConnectionStatus(status) {
    const nextStatus = ["connected", "connecting"].includes(status) ? status : "disconnected";
    if (this.state.connectionStatus === nextStatus) {
      return;
    }
    this.state.connectionStatus = nextStatus;
    this.syncUi();
  }

  panelTitle() {
    if (this.state.activePanel === "environment") {
      return this.t("environmentPanel");
    }
    return this.t("missionPanel");
  }

  commercialTrafficMeta() {
    if (!this.state.commercialTrafficEnabled) {
      return this.t("commercialOff");
    }
    if (this.state.commercialTrafficLoading) {
      return this.t("commercialLoading");
    }
    if (this.state.commercialTrafficError) {
      return this.t("commercialError");
    }
    if (this.state.commercialTrafficCount > 0) {
      const count = this.state.commercialTrafficCount.toLocaleString(this.language === "ko" ? "ko-KR" : "en-US");
      return this.language === "ko" ? `${count}${this.t("commercialTracked")}` : `${count} ${this.t("commercialTracked")}`;
    }
    return this.t("commercialEmpty");
  }

  render() {
    this.container.hidden = false;
    this.container.innerHTML = `
      <section class="uatm-sim" aria-label="${this.t("title")}">
        <div id="dtam-simulation-map" class="uatm-map theme-${this.state.mapTheme}"></div>

        <div class="uatm-loading" data-map-loading>
          <div class="uatm-loading-card">
            <div class="uatm-spinner" aria-hidden="true"></div>
            <div class="uatm-loading-title">${this.t("mapLoading")}</div>
            <div class="uatm-loading-subtitle">${this.t("mapLoadingSub")}</div>
          </div>
        </div>

        <button type="button" class="uatm-back" data-action="back">
          <span aria-hidden="true">&larr;</span>
          <strong>${this.t("back")}</strong>
        </button>

        <div class="uatm-title-block">
          <strong>${this.t("title")}</strong>
          <small>${this.t("serverTime")} <b data-server-time>${this.serverTimeText}</b></small>
        </div>

        ${this.renderOperationLogPanel()}

        <div id="sim-status-board" class="sim-status-board">
          <strong>${this.t("statusBoard")}</strong>
          <span>${this.t("noTrafficData")}</span>
        </div>

        <div id="left-controls" class="panel panel-left">
          <button type="button" class="ui-btn ui-btn-icon" title="${this.t("environmentPanel")}" data-panel-toggle="environment">
            ${simIcon("environment")}
          </button>
          <button type="button" class="ui-btn ui-btn-icon" title="${this.t("missionPanel")}" data-panel-toggle="mission">
            ${simIcon("mission")}
          </button>
        </div>

        <div id="bottom-controls" class="panel panel-bottom-left">
          <div id="playback-panel" class="playback-panel playback-panel-odt is-open" aria-hidden="false">
            ${this.renderPlaybackButtons()}
          </div>
        </div>

        <div id="theme-controls" class="panel panel-right theme-panel is-open">
          <div class="theme-row">
            <div id="theme-list" class="theme-list">
              ${MAP_THEME_KEYS.map((theme) => `
                <button type="button" class="theme-card ${this.state.mapTheme === theme ? "is-active" : ""}" data-map-theme="${theme}" title="${this.t(theme)}">
                  <span class="theme-icon theme-icon--${theme}">${simIcon(theme)}</span>
                  <span class="base-card-label">${this.t(theme)}</span>
                </button>
              `).join("")}
            </div>
          </div>
        </div>

        ${this.renderRightDock()}

        <div class="map-zoom-controls" aria-label="${this.t("mapTheme")}">
          <button type="button" data-map-zoom="in" aria-label="Zoom in">${simIcon("zoomIn")}</button>
          <button type="button" data-map-zoom="out" aria-label="Zoom out">${simIcon("zoomOut")}</button>
          <button type="button" data-map-zoom="reset" aria-label="${this.t("resetView")}">${simIcon("resetView")}</button>
        </div>

        ${this.renderScenarioPanel()}
      </section>
    `;
    this.syncUi();
  }

  renderPlaybackButtons() {
    const connectionStatus = ["connected", "connecting"].includes(this.state.connectionStatus)
      ? this.state.connectionStatus
      : "disconnected";
    const connectionTitle = this.t(`connection${connectionStatus.charAt(0).toUpperCase()}${connectionStatus.slice(1)}`);
    const isPlaying = this.state.playState === "play";
    return `
      <div class="playback-bar-group playback-bar-group--primary ${isPlaying ? "is-playing" : ""}">
        <span
          class="dtam-link-indicator dtam-link-indicator--${connectionStatus}"
          title="${connectionTitle}"
          aria-label="${connectionTitle}"
          data-connection-indicator
        ></span>
        <button type="button" class="playback-text-btn" title="${this.t("dtamExecute")}" data-action="dtam-execute">
          ${this.t("dtamExecute")}
        </button>
        <button type="button" class="playback-round-btn playback-round-btn--play ${isPlaying ? "is-active" : ""}" title="${this.t("play")}" aria-label="${this.t("play")}" aria-pressed="${isPlaying ? "true" : "false"}" data-play-state="play">
          <span class="playback-round-icon playback-round-icon--play" aria-hidden="true"></span>
        </button>
        <span class="playback-state-pill ${isPlaying ? "is-visible" : ""}" data-playback-state-pill aria-live="polite" ${isPlaying ? "" : "aria-hidden=\"true\""}>
          <span class="playback-state-dot" aria-hidden="true"></span>
          <span data-playback-state-text>${this.t("playbackPlaying")}</span>
        </span>
        <button type="button" class="playback-round-btn playback-round-btn--stop ${this.state.playState === "pause" ? "is-active" : ""}" title="${this.t("pause")}" aria-label="${this.t("pause")}" aria-pressed="${this.state.playState === "pause" ? "true" : "false"}" data-play-state="pause">
          <span class="playback-round-icon playback-round-icon--stop" aria-hidden="true"></span>
        </button>
        <button
          type="button"
          class="playback-speed-pill ${this.state.playbackSpeed > 1 ? "is-active" : ""}"
          title="${this.t("speed")} ${this.state.playbackSpeed}x"
          aria-label="${this.t("speed")} ${this.state.playbackSpeed}x"
          data-action="cycle-speed"
          data-speed-display="true"
        >${this.state.playbackSpeed}x</button>
      </div>
    `;
  }

  renderOperationLogPanel() {
    const logs = Array.isArray(this.state.operationLogs) ? this.state.operationLogs : [];
    return `
      <section class="operation-log-panel ${logs.length ? "is-visible" : ""}" data-operation-log-panel aria-live="polite">
        <div class="operation-log-heading">
          <strong>${this.t("operationLog")}</strong>
          <button type="button" class="operation-log-close" title="${this.t("close")}" aria-label="${this.t("close")}" data-action="clear-operation-log">
            ${this.t("close")}
          </button>
        </div>
        <div class="operation-log-list" data-operation-log-list>
          ${this.renderOperationLogEntries()}
        </div>
      </section>
    `;
  }

  renderOperationLogEntries() {
    const logs = Array.isArray(this.state.operationLogs) ? this.state.operationLogs : [];
    return logs.map((log) => `
      <article class="operation-log-entry" data-log-level="${escapeHtml(log.level || "info")}">
        <span class="operation-log-dot" aria-hidden="true"></span>
        <div class="operation-log-copy">
          <strong>${escapeHtml(log.title || this.t("operationAlert"))}</strong>
          <small>${escapeHtml(log.message || "")}</small>
        </div>
        <time>${escapeHtml(log.time || "")}</time>
      </article>
    `).join("");
  }

  renderRightDock() {
    return `
      <div class="right-sidebar-stack">
        ${this.renderAbnormalDashboardPanel()}
        ${this.renderCommercialTrafficPanel()}
        ${this.renderWeatherDockPanel()}
      </div>
    `;
  }

  renderUamVehicleDetailPanel() {
    return `
      <aside class="uam-vehicle-detail-panel" data-uam-vehicle-detail hidden>
        <div class="uam-vehicle-detail-header">
          <span>${simIcon("aircraft")}</span>
          <div>
            <strong data-uam-detail-title>${this.t("vehicleDetails")}</strong>
            <small data-uam-detail-subtitle>${this.t("vehicleStatusWaiting")}</small>
          </div>
          <button type="button" class="uam-vehicle-detail-close" title="${this.t("close")}" aria-label="${this.t("close")}" data-action="close-uam-detail">${this.t("close")}</button>
        </div>
        <div class="uam-vehicle-detail-body" data-uam-detail-body></div>
      </aside>
    `;
  }

  renderCommercialTrafficPanel() {
    return `
      <div id="commercial-traffic-panel" class="commercial-traffic-panel">
        <button type="button" class="traffic-toggle ${this.state.commercialTrafficEnabled ? "is-active" : ""}" data-action="toggle-commercial-traffic" aria-pressed="${this.state.commercialTrafficEnabled ? "true" : "false"}">
          <span class="traffic-toggle-icon">${simIcon("aircraft")}</span>
          <span class="traffic-toggle-title">${this.t("commercialAircraft")}</span>
          <small data-commercial-traffic-meta>${this.commercialTrafficMeta()}</small>
        </button>
      </div>
    `;
  }

  renderAbnormalDashboardPanel() {
    const radiusKm = (Number(this.state.abnormalRadiusM || 0) / 1000).toFixed(2);
    const centerText = Number.isFinite(Number(this.state.abnormalLat)) && Number.isFinite(Number(this.state.abnormalLon))
      ? `${Number(this.state.abnormalLat).toFixed(5)}, ${Number(this.state.abnormalLon).toFixed(5)}`
      : this.t("abnormalNoCenter");
    return `
      <div class="abnormal-dock-wrap">
        <button
          type="button"
          class="traffic-toggle abnormal-dock-toggle ${this.state.abnormalDashboardOpen ? "is-active" : ""}"
          data-action="toggle-abnormal-dashboard"
          aria-pressed="${this.state.abnormalDashboardOpen ? "true" : "false"}"
          aria-controls="abnormal-dashboard-panel"
        >
          <span class="traffic-toggle-icon">${simIcon("abnormal")}</span>
          <span class="traffic-toggle-title">${this.t("abnormalDashboard")}</span>
          <small data-abnormal-dashboard-meta>${this.t("abnormalDashboardMeta")}</small>
        </button>
        <aside id="abnormal-dashboard-panel" class="abnormal-dashboard-panel ${this.state.abnormalDashboardOpen ? "is-open" : ""}" ${this.state.abnormalDashboardOpen ? "" : "hidden"}>
          <div class="abnormal-dashboard-header">
            <strong>${this.t("abnormalDashboardTitle")}</strong>
          </div>
          <div class="abnormal-dashboard-body">
            <button type="button" class="abnormal-type-card is-active" data-action="select-bird-flock">
              <span>${simIcon("bird")}</span>
              <strong>${this.t("birdFlockSpawn")}</strong>
              <small>${this.t("birdFlockDescription")}</small>
            </button>
            <div class="abnormal-control-row">
              <button type="button" class="scenario-btn scenario-toggle-btn ${this.state.abnormalPickMode ? "is-active" : ""}" data-action="toggle-abnormal-pick">
                ${this.state.abnormalPickMode ? this.t("abnormalPicking") : this.t("abnormalPickArea")}
              </button>
              <button type="button" class="scenario-btn scenario-btn-ghost" data-action="clear-abnormal-zone">${this.t("abnormalClear")}</button>
            </div>
            <label class="scenario-field">
              <span>${this.t("abnormalRadius")} <strong data-abnormal-radius-value>${radiusKm} km</strong></span>
              <input type="range" min="${ABNORMAL_ZONE_MIN_RADIUS_M}" max="${ABNORMAL_ZONE_MAX_RADIUS_M}" step="50" value="${this.state.abnormalRadiusM}" data-abnormal-radius />
            </label>
            <div class="abnormal-metrics">
              <span><b>${this.t("abnormalCenter")}</b><i data-abnormal-center>${centerText}</i></span>
              <span><b>${this.t("abnormalCount")}</b><i data-abnormal-count>${Number(this.state.abnormalCount || 0)}</i></span>
              <span><b>${this.t("abnormalSpeed")}</b><i data-abnormal-speed>${Number(this.state.abnormalSpeedMps || 0).toFixed(1)} m/s</i></span>
            </div>
            <div class="scenario-hint">${this.t("abnormalWheelHint")}</div>
            <button type="button" class="scenario-btn abnormal-apply-btn" data-action="apply-abnormal-event">
              ${this.t("abnormalApply")}
            </button>
            <div class="abnormal-status" data-abnormal-status data-status-level="${escapeHtml(this.state.abnormalStatusLevel || "info")}">
              ${escapeHtml(this.state.abnormalStatus || "")}
            </div>
          </div>
        </aside>
      </div>
    `;
  }

  weatherDockMeta() {
    const precipitation = this.t(this.state.precipitationType);
    const wind = this.t(this.state.windGrade);
    if (this.language === "ko") {
      return `강수 ${precipitation} · 바람 ${wind}`;
    }
    return `${this.t("precipitation")} ${precipitation} · ${this.t("windGrade")} ${wind}`;
  }

  renderWeatherDockPanel() {
    return `
      <div class="weather-dock-wrap">
        <button
          type="button"
          class="traffic-toggle weather-dock-toggle ${this.state.weatherDockOpen ? "is-active" : ""}"
          data-action="toggle-weather-dock"
          aria-pressed="${this.state.weatherDockOpen ? "true" : "false"}"
          aria-controls="weather-dock-panel"
        >
          <span class="traffic-toggle-icon">${simIcon("weather")}</span>
          <span class="traffic-toggle-title">${this.t("weatherPanel")}</span>
          <small data-weather-dock-meta>${this.weatherDockMeta()}</small>
        </button>
        <aside id="weather-dock-panel" class="weather-dock-panel ${this.state.weatherDockOpen ? "is-open" : ""}" ${this.state.weatherDockOpen ? "" : "hidden"}>
          <div class="weather-dock-header">
            <strong>${this.t("weatherPanel")}</strong>
          </div>
          <div class="weather-dock-body">
            ${this.renderWeatherControls()}
          </div>
        </aside>
      </div>
    `;
  }

  renderWeatherControls() {
    return `
      <div class="scenario-title">${this.t("weatherEffect")}</div>
      <label class="scenario-field">
        <span>${this.t("precipitation")}</span>
        <select data-precipitation-type>
          ${PRECIPITATION_TYPES.map((type) => `
            <option value="${type}" ${this.state.precipitationType === type ? "selected" : ""}>${this.t(type)}</option>
          `).join("")}
        </select>
      </label>
      <div class="scenario-row scenario-row-single">
        <button type="button" class="scenario-btn scenario-toggle-btn ${this.state.weatherVisualizationEnabled ? "is-active" : ""}" data-action="toggle-weather-visualization">
          ${this.state.weatherVisualizationEnabled ? this.t("visualizationOn") : this.t("visualizationOff")}
        </button>
      </div>
      <label class="scenario-field">
        <span>${this.t("intensity")} <strong data-precipitation-value>${pct(this.state.precipitationIntensity)}</strong></span>
        <input type="range" min="0" max="1" step="0.1" value="${this.state.precipitationIntensity}" data-precipitation-intensity />
      </label>
      <label class="scenario-field">
        <span>${this.t("fog")} <strong data-fog-value>${pct(this.state.fogIntensity)}</strong></span>
        <input type="range" min="0" max="1" step="0.1" value="${this.state.fogIntensity}" data-fog-intensity />
      </label>

      <div class="scenario-title">${this.t("windGrade")}</div>
      <div class="scenario-grid">
        ${WIND_GRADES.map((grade) => `
          <button type="button" class="scenario-btn scenario-preset-btn ${this.state.windGrade === grade ? "is-active" : ""}" data-wind-grade="${grade}">
            ${this.t(grade)}
          </button>
        `).join("")}
      </div>
      <div class="scenario-title">${this.t("localWind")}</div>
      <div class="scenario-row">
        <button type="button" class="scenario-btn scenario-toggle-btn ${this.state.gustApplyMode ? "is-active" : ""}" data-action="toggle-gust-apply">
          ${this.state.gustApplyMode ? this.t("applyOn") : this.t("applyOff")}
        </button>
        <button type="button" class="scenario-btn scenario-btn-ghost" data-action="reset-gust">${this.t("resetLocal")}</button>
      </div>
      <div class="scenario-row scenario-row-inline">
        <label class="scenario-label" for="scenario-wind-radius">${this.t("radius")}</label>
        <input id="scenario-wind-radius" class="scenario-range" type="range" min="400" max="4000" step="100" value="${this.state.gustRadius}" data-gust-radius />
        <span class="scenario-value" data-gust-radius-value>${(this.state.gustRadius / 1000).toFixed(1)} km</span>
      </div>
      <div class="scenario-hint">${this.t("clickMap")}</div>
    `;
  }

  operationModeDescription(mode = this.state.operationMode) {
    if (mode === "single") {
      return this.t("singleDescription");
    }
    return this.t("trafficDescription");
  }

  modeStatusText() {
    if (this.state.modeSaveStatus === "sending") {
      return this.t("modeSaveSending");
    }
    if (this.state.modeSaveStatus === "ok") {
      return this.t("modeSaveOk");
    }
    if (this.state.modeSaveStatus === "error") {
      return this.state.modeSaveMessage || this.t("modeSaveError");
    }
    return this.t("modeSaveIdle");
  }

  isDemoScenarioLocked() {
    return Boolean(this.state.demoScenarioId);
  }

  demoScenarioLockNoticeText() {
    return this.tf("demoScenarioLockNotice", { scenarioId: this.state.demoScenarioId || "-" });
  }

  activeMissionEntry() {
    return (this.state.missionEntries || []).find((entry) => entry.id === this.state.activeMissionId) || this.state.missionEntries?.[0] || null;
  }

  trafficCustomMissionText() {
    const folderName = String(this.state.trafficCustomMissionFolderName || "").trim();
    if (!folderName) {
      return this.t("trafficCustomMissionHint");
    }
    if (this.state.trafficCustomMissionAction === "generate") {
      return this.tf("trafficCustomFolderGenerateSelected", { name: folderName });
    }
    if (this.state.trafficCustomMissionAction === "load") {
      return this.tf("trafficCustomFolderLoadSelected", { name: folderName });
    }
    return this.tf("trafficCustomFolderSelected", { name: folderName });
  }

  missionStatusText() {
    if (this.state.missionStatusMessage) {
      return this.state.missionStatusMessage;
    }
    if (this.state.operationMode === "traffic") {
      return this.state.trafficDensity === "customed"
        ? this.trafficCustomMissionText()
        : this.t("trafficDensityHint");
    }
    const entry = this.activeMissionEntry();
    if (!entry) {
      return this.t("missionNoAircraft");
    }
    if (this.state.missionInputMode) {
      return this.state.missionInputTarget === "arrival"
        ? this.t("missionAwaitArrival")
        : this.t("missionAwaitDeparture");
    }
    if (entry.routeData) {
      return `${this.t("missionRouteReady")} · ${entry.departureName || "--"} -> ${entry.arrivalName || "--"}`;
    }
    if (entry.departureName || entry.arrivalName) {
      return `${this.t("missionRoutePending")} · ${entry.departureName || "--"} -> ${entry.arrivalName || "--"}`;
    }
    return this.t("missionReadyHint");
  }

  missionStatusLevel() {
    if (this.state.missionStatusMessage) {
      return this.state.missionStatusLevel || "info";
    }
    if (this.state.operationMode === "traffic" && this.state.trafficDensity === "customed" && this.state.trafficCustomMissionFolderName) {
      return "success";
    }
    return this.activeMissionEntry()?.routeData ? "success" : "info";
  }

  formatMissionDistance(distanceKm) {
    const value = Number(distanceKm || 0);
    return `${value.toFixed(value >= 10 ? 1 : 2)} km`;
  }

  missionDistanceKm(route) {
    return this.firstFiniteNumber(
      route?.distance_km,
      route?.distanceKm,
      route?.distance,
      route?.length_km,
      route?.lengthKm,
    ) || 0;
  }

  missionSummaryText(entry) {
    if (entry?.routeData) {
      return `${this.t("missionRouteReady")} · ${entry.departureName || "--"} -> ${entry.arrivalName || "--"}`;
    }
    if (entry?.departureName || entry?.arrivalName) {
      return `${this.t("missionRoutePending")} · ${entry.departureName || "--"} -> ${entry.arrivalName || "--"}`;
    }
    return this.t("missionReadyHint");
  }

  missionControllerLabel(entry) {
    const override = CONTROLLER_MODES.includes(entry?.controllerOverride) ? entry.controllerOverride : "";
    return override || `${this.t("commonController")} ${this.state.mainVehicleController || "-"}`;
  }

  missionDynamicsLabel(entry) {
    return this.t(normalizeDynamicsModel(entry?.dynamics));
  }

  missionDepartureTime(entry) {
    const value = entry?.departureTime || entry?.std || "";
    const normalized = normalizeMissionDepartureTime(value);
    if (entry && entry.departureTime !== normalized) {
      entry.departureTime = normalized;
      entry.std = normalized;
    }
    return normalized;
  }

  missionDepartureTimeParts(entry) {
    return this.missionDepartureTime(entry).split(":");
  }

  timePartMax(part) {
    return part === "hours" ? 23 : 59;
  }

  sanitizeMissionTimePartInput(input) {
    if (!input) {
      return;
    }
    const sanitized = String(input.value || "").replace(/\D/g, "").slice(0, 2);
    if (input.value !== sanitized) {
      input.value = sanitized;
    }
  }

  missionTimeValueFromGroup(group, id) {
    const entry = (this.state.missionEntries || []).find((item) => item.id === id);
    const fallbackParts = this.missionDepartureTime(entry).split(":");
    const parts = ["hours", "minutes", "seconds"].map((part, index) => {
      const input = group?.querySelector(`[data-mission-time-part="${part}"]`);
      const raw = String(input?.value || "").replace(/\D/g, "");
      if (!raw) {
        return null;
      }
      const max = this.timePartMax(part);
      const fallback = Number(fallbackParts[index] || 0);
      const numeric = Number(raw);
      if (!Number.isFinite(numeric)) {
        return fallback;
      }
      return Math.max(0, Math.min(max, Math.floor(numeric)));
    });
    if (parts.some((part) => part === null)) {
      return "";
    }
    return parts.map((part) => String(part).padStart(2, "0")).join(":");
  }

  updateMissionTimeGroupDisplay(group, value) {
    const normalized = normalizeMissionDepartureTime(value);
    const [hours, minutes, seconds] = normalized.split(":");
    [
      ["hours", hours],
      ["minutes", minutes],
      ["seconds", seconds],
    ].forEach(([part, partValue]) => {
      const input = group?.querySelector(`[data-mission-time-part="${part}"]`);
      if (input) {
        input.value = partValue;
      }
    });
  }

  commitMissionDepartureTimeInput(target, options = {}) {
    const input = target?.closest?.("[data-mission-departure-time-id]");
    if (!input) {
      return;
    }
    const id = input.dataset.missionDepartureTimeId;
    const group = input.closest("[data-mission-time-group]");
    const value = group ? this.missionTimeValueFromGroup(group, id) : String(input.value || "").trim();
    if (!id || !value) {
      if (id && group && options.normalizeDisplay !== false) {
        const entry = (this.state.missionEntries || []).find((item) => item.id === id);
        this.updateMissionTimeGroupDisplay(group, this.missionDepartureTime(entry));
      }
      return;
    }
    this.setMissionDepartureTime(id, value, { refresh: false });
    if (group && options.normalizeDisplay !== false) {
      this.updateMissionTimeGroupDisplay(group, value);
    }
  }

  adjustMissionDepartureTimePart(input, direction) {
    if (!input?.matches?.("[data-mission-time-part]")) {
      return;
    }
    const part = input.dataset.missionTimePart || "minutes";
    const max = this.timePartMax(part);
    const min = 0;
    const range = max - min + 1;
    const group = input.closest("[data-mission-time-group]");
    const id = input.dataset.missionDepartureTimeId;
    const entry = (this.state.missionEntries || []).find((item) => item.id === id);
    const partIndex = part === "hours" ? 0 : part === "minutes" ? 1 : 2;
    const fallback = Number(this.missionDepartureTime(entry).split(":")[partIndex] || 0);
    const current = Number(String(input.value || "").replace(/\D/g, ""));
    const base = Number.isFinite(current) ? current : fallback;
    const next = ((Math.max(min, Math.min(max, base)) - min + direction + range) % range) + min;
    input.value = String(next).padStart(2, "0");
    this.commitMissionDepartureTimeInput(input, { normalizeDisplay: true });
    if (group) {
      this.updateMissionTimeGroupDisplay(group, this.missionTimeValueFromGroup(group, id) || this.missionDepartureTime(entry));
    }
  }

  renderMissionCards() {
    const entries = Array.isArray(this.state.missionEntries) ? this.state.missionEntries : [];
    if (!entries.length) {
      return `<div class="mission-card-empty">${this.t("missionNoAircraft")}</div>`;
    }
    const lockedAttr = this.isDemoScenarioLocked() ? "disabled" : "";
    return entries.map((entry, index) => {
      const [departureHour, departureMinute, departureSecond] = this.missionDepartureTimeParts(entry);
      return `
      <article class="mission-aircraft-card ${entry.id === this.state.activeMissionId ? "is-active" : ""}" data-mission-card="${entry.id}" tabindex="0" role="button" aria-pressed="${entry.id === this.state.activeMissionId ? "true" : "false"}" aria-disabled="${lockedAttr ? "true" : "false"}">
        <span class="mission-aircraft-media">
          <img src="/resource/simulation_sign.png" alt="" loading="lazy" />
        </span>
        <span class="mission-aircraft-content">
          <span class="mission-aircraft-heading">
            <strong>${escapeHtml(entry.aircraftName || `UAM ${index + 1}`)}</strong>
          </span>
          <span class="mission-aircraft-route">
            <span><b>${this.t("missionFrom")}</b><i>${escapeHtml(entry.departureName || "--")}</i></span>
            <span><b>${this.t("missionTo")}</b><i>${escapeHtml(entry.arrivalName || "--")}</i></span>
          </span>
          <label class="mission-aircraft-controller mission-aircraft-setting mission-aircraft-time">
            <b>${this.t("departureTime")}</b>
            <span class="mission-time-input-group" data-mission-time-group="${escapeHtml(entry.id)}" role="group" aria-label="${this.t("departureTime")}">
              <input type="text" inputmode="numeric" autocomplete="off" spellcheck="false" maxlength="2" value="${escapeHtml(departureHour)}" data-mission-departure-time-id="${entry.id}" data-mission-time-part="hours" aria-label="${this.t("timeHour")}" title="${this.t("timeHour")}" ${lockedAttr} />
              <span class="mission-time-separator" aria-hidden="true">:</span>
              <input type="text" inputmode="numeric" autocomplete="off" spellcheck="false" maxlength="2" value="${escapeHtml(departureMinute)}" data-mission-departure-time-id="${entry.id}" data-mission-time-part="minutes" aria-label="${this.t("timeMinute")}" title="${this.t("timeMinute")}" ${lockedAttr} />
              <span class="mission-time-separator" aria-hidden="true">:</span>
              <input type="text" inputmode="numeric" autocomplete="off" spellcheck="false" maxlength="2" value="${escapeHtml(departureSecond)}" data-mission-departure-time-id="${entry.id}" data-mission-time-part="seconds" aria-label="${this.t("timeSecond")}" title="${this.t("timeSecond")}" ${lockedAttr} />
            </span>
          </label>
          <span class="mission-aircraft-controller mission-aircraft-setting">
            <b>${this.t("aircraftDynamics")}</b>
            <i>${escapeHtml(this.missionDynamicsLabel(entry))}</i>
          </span>
          <span class="mission-dynamics-options" data-mission-dynamics-row="${entry.id}">
            ${DYNAMICS_MODELS.map((model) => `
              <button type="button" class="scenario-btn ${normalizeDynamicsModel(entry.dynamics) === model ? "is-active" : ""}" data-mission-dynamics-model="${model}" data-mission-dynamics-id="${entry.id}" ${lockedAttr}>
                ${this.t(model)}
              </button>
            `).join("")}
          </span>
          <span class="mission-aircraft-controller mission-aircraft-setting">
            <b>${this.t("aircraftController")}</b>
            <i>${escapeHtml(this.missionControllerLabel(entry))}</i>
          </span>
          <span class="mission-controller-override" data-mission-controller-row="${entry.id}">
            <button type="button" class="scenario-btn ${!entry.controllerOverride ? "is-active" : ""}" data-mission-controller-mode="" data-mission-controller-id="${entry.id}" ${lockedAttr}>
              ${this.t("inheritController")}
            </button>
            ${CONTROLLER_MODES.map((controller) => `
              <button type="button" class="scenario-btn ${entry.controllerOverride === controller ? "is-active" : ""}" data-mission-controller-mode="${controller}" data-mission-controller-id="${entry.id}" ${lockedAttr}>
                ${controller}
              </button>
            `).join("")}
          </span>
          <span class="mission-aircraft-summary">${escapeHtml(this.missionSummaryText(entry))}</span>
        </span>
        <span class="mission-card-actions">
          <small>UAM ${index + 1}</small>
          <button type="button" class="mission-card-delete" data-mission-delete="${entry.id}" title="${this.t("missionDeleteAircraft")}" aria-label="${this.t("missionDeleteAircraft")}" ${lockedAttr}>
            ${simIcon("trash")}
          </button>
        </span>
      </article>
    `;
    }).join("");
  }

  renderMissionRouteInfo() {
    const entry = this.activeMissionEntry();
    if (!entry) {
      return `
        <div class="mission-route-empty">
          <strong>${this.t("missionRouteInfo")}</strong>
          <span>${this.t("missionNoAircraft")}</span>
        </div>
      `;
    }
    if (!entry?.routeData) {
      return `
        <div class="mission-route-empty">
          <strong>${this.t("missionRouteInfo")}</strong>
          <span>${this.t("missionResetRoute")}</span>
        </div>
      `;
    }
    const route = entry.routeData;
    return `
      <div class="mission-route-card">
        <div class="mission-route-title-row">
          <strong>${this.t("missionRouteInfo")}</strong>
          <span>${escapeHtml(entry.departureName || "--")} -> ${escapeHtml(entry.arrivalName || "--")}</span>
        </div>
        <div class="mission-route-grid">
          <div class="mission-route-metric">
            <span>${this.t("missionDistance")}</span>
            <b>${this.formatMissionDistance(this.missionDistanceKm(route))}</b>
          </div>
          <div class="mission-route-metric">
            <span>${this.t("missionWaypoints")}</span>
            <b>${Array.isArray(route.path) ? route.path.length : 0}</b>
          </div>
        </div>
        <div class="mission-route-path">
          <span>${this.t("missionPath")}</span>
          <b>${escapeHtml(Array.isArray(route.path) ? route.path.join(" -> ") : "--")}</b>
        </div>
      </div>
    `;
  }

  renderMissionPlanningSection() {
    const activeMission = this.activeMissionEntry();
    return `
      <div class="scenario-section scenario-section-tab mission-planning-section" data-panel-section="mission">
        <div class="scenario-title">${this.t("missionPlanning")}</div>
        <div class="scenario-title">데모 시나리오</div>
        <div class="scenario-grid">
          ${["", "S1", "S2", "S3"].map((id) => `
            <button type="button" class="scenario-btn scenario-preset-btn ${(this.state.demoScenarioId || "") === id ? "is-active" : ""}" data-demo-scenario="${id}">
              ${id || "없음"}
            </button>
          `).join("")}
        </div>
        <div class="scenario-hint">데모 시나리오 선택 시 2002 DtamExecute 에 scenarioId 가 포함되고, 아래 비행체/임무 수동 편집이 잠깁니다. 임무 계획은 Mission 의 데모 플랜 팩이 일괄 발행합니다.</div>
        <div class="mode-option-grid">
          ${OPERATION_MODES.map((mode) => `
            <button type="button" class="mode-option-card ${this.state.operationMode === mode ? "is-active" : ""}" data-operation-mode="${mode}">
              <span class="mode-option-icon">${simIcon(`${mode}Mode`)}</span>
              <strong>${this.t(mode)}</strong>
              <small>${this.operationModeDescription(mode)}</small>
            </button>
          `).join("")}
        </div>

        <div class="mode-detail-card mission-detail-card">
          <div class="mode-detail-heading">
            <strong data-mode-detail-title>${this.t(this.state.operationMode)}</strong>
            <span data-mode-detail-description>${this.operationModeDescription()}</span>
          </div>

          <div class="mission-single-layout" data-single-mission-layout>
            <div class="mission-toolbar">
              <div class="mission-toolbar-copy">
                <span>${this.t("missionEditing")}</span>
                <strong data-mission-active-label>${escapeHtml(activeMission?.aircraftName || "-")}</strong>
              </div>
              <button type="button" class="scenario-btn mission-add-btn" data-mission-action="add" ${this.isDemoScenarioLocked() ? "disabled" : ""}>${this.t("missionAddAircraft")}</button>
            </div>
            <div class="scenario-hint mission-demo-lock-notice" data-demo-lock-notice ${this.isDemoScenarioLocked() ? "" : "hidden"}>${escapeHtml(this.demoScenarioLockNoticeText())}</div>
            <div class="mission-card-list" data-mission-list>${this.renderMissionCards()}</div>
            <div class="mission-status" data-mission-status-level="${this.missionStatusLevel()}" data-mission-status>${this.missionStatusText()}</div>
            <div class="mission-route-info-wrap" data-mission-route-info>${this.renderMissionRouteInfo()}</div>

            <div class="mode-config-block mission-config-block" data-vehicle-mode-section>
              <div class="scenario-title">${this.t("vehicleSimulation")}</div>
              <label class="scenario-field">
                <span>${this.t("dynamicsModel")}</span>
                <select data-dynamics-model>
                  ${DYNAMICS_MODELS.map((model) => `
                    <option value="${model}" ${this.state.dynamics === model ? "selected" : ""}>${this.t(model)}</option>
                  `).join("")}
                </select>
              </label>
              <div class="scenario-title">${this.t("aircraftController")}</div>
              <div class="scenario-grid scenario-grid--controller">
                ${CONTROLLER_MODES.map((controller) => `
                  <button type="button" class="scenario-btn ${this.state.mainVehicleController === controller ? "is-active" : ""}" data-controller-mode="${controller}">
                    ${controller}
                  </button>
                `).join("")}
              </div>
            </div>
          </div>

          <div class="traffic-density-section" data-traffic-density-section hidden>
            <label class="scenario-field">
              <span>${this.t("trafficDensity")}</span>
              <select data-traffic-density>
                ${TRAFFIC_DENSITIES.map((density) => `
                  <option value="${density}" ${this.state.trafficDensity === density ? "selected" : ""}>${this.t(density)}</option>
                `).join("")}
              </select>
            </label>
            <div class="scenario-hint">${this.t("trafficDensityHint")}</div>
            <div class="traffic-custom-block" data-traffic-custom-block ${this.state.trafficDensity === "customed" ? "" : "hidden"}>
              <div class="traffic-custom-heading">
                <strong>${this.t("customed")}</strong>
                <span>${this.t("trafficCustomMissionHint")}</span>
              </div>
              <div class="traffic-custom-actions">
                <button type="button" class="scenario-btn" data-traffic-custom-action="generate">${this.t("trafficRegularFlightGenerate")}</button>
                <button type="button" class="scenario-btn" data-traffic-custom-action="load">${this.t("trafficMissionLoad")}</button>
              </div>
              <div class="traffic-fpl-list" data-traffic-fpl-list hidden></div>
              <div class="scenario-hint traffic-custom-status" data-traffic-custom-status>${this.trafficCustomMissionText()}</div>
              <input type="file" data-traffic-folder-input="generate" webkitdirectory directory multiple hidden />
              <input type="file" data-traffic-folder-input="load" webkitdirectory directory multiple hidden />
            </div>
          </div>

          <div class="mode-save-row">
            <button type="button" class="scenario-btn mode-save-btn" data-action="save-mode-settings">
              ${this.t("saveSettings")}
            </button>
            <span class="mode-save-status" data-mode-save-status="${this.state.modeSaveStatus}">${this.modeStatusText()}</span>
          </div>
          <div class="scenario-hint" data-mission-bottom-hint>${this.state.operationMode === "single" ? (activeMission ? this.t("missionResetRoute") : this.t("missionNoAircraft")) : (this.state.trafficDensity === "customed" ? this.trafficCustomMissionText() : this.t("modeHint"))}</div>
        </div>
      </div>
    `;
  }

  environmentSummaryText() {
    const vertiports = this.operationalEnvironment?.vertiports?.length || 0;
    const routes = this.operationalEnvironment?.corridors?.length || 0;
    const links = this.operationalEnvironment?.links?.length || 0;
    return this.tf("environmentSummary", { vertiports, routes, links });
  }

  environmentStatusText() {
    if (this.state.environmentLoading) {
      return this.t("environmentLoading");
    }
    return this.state.environmentStatus || this.t("environmentReady");
  }

  environmentToolLabel(tool) {
    const labels = {
      select: this.t("environmentToolSelect"),
      vertiport: this.t("environmentToolVertiport"),
      route: this.t("environmentToolRoute"),
      link: this.t("environmentToolLink"),
    };
    return labels[tool] || tool;
  }

  renderEnvironmentTable(kind) {
    const isVertiport = kind === "vertiport";
    const items = isVertiport
      ? this.operationalEnvironment?.vertiports || []
      : this.operationalEnvironment?.corridors || [];
    if (!items.length) {
      return `<div class="environment-empty">${this.t("environmentNoItems")}</div>`;
    }
    const headers = isVertiport
      ? ["Name", "Class", "Link"]
      : ["Name", "Alt", "Link"];
    const rows = items
      .slice(0, 120)
      .map((item) => {
        const selected = this.environmentSelection?.kind === kind && this.environmentSelection?.name === item.name;
        const primary = isVertiport
          ? item.class || "port"
          : `${Math.round(Number(item.altitude_ft || 0)).toLocaleString(this.language === "ko" ? "ko-KR" : "en-US")} ft`;
        const linkCount = isVertiport
          ? (item.links || []).length
          : (item.links || []).length + (item.spare_links || []).length;
        return `
          <tr class="environment-list-item ${selected ? "is-active" : ""}" data-env-select-kind="${kind}" data-env-select-name="${escapeHtml(item.name)}" tabindex="0">
            <td title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</td>
            <td>${escapeHtml(primary)}</td>
            <td>${linkCount}</td>
          </tr>
        `;
      })
      .join("");
    return `
      <table class="environment-data-table">
        <thead>
          <tr>${headers.map((header) => `<th>${header}</th>`).join("")}</tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }

  renderEnvironmentList(kind) {
    return this.renderEnvironmentTable(kind);
  }

  renderEnvironmentPanelSection() {
    return `
      <div class="scenario-section scenario-section-tab environment-section" data-panel-section="environment">
        <div class="environment-settings-section">
          <div class="environment-title-row environment-title-row--summary">
            <b data-env-summary>${this.environmentSummaryText()}</b>
          </div>
          <div class="environment-tool-strip" aria-label="${this.t("environmentPanel")} tools">
            ${ENVIRONMENT_TOOLS.map((tool) => `
              <button type="button" class="environment-tool-btn ${this.state.environmentTool === tool ? "is-active" : ""}" data-env-tool="${tool}" title="${this.environmentToolLabel(tool)}">
                <span>${simIcon(tool === "select" ? "environment" : tool)}</span>
                <b>${this.environmentToolLabel(tool)}</b>
              </button>
            `).join("")}
          </div>
          <div class="environment-status" data-env-status-level="${this.state.environmentStatusLevel}" data-env-status>
            ${this.environmentStatusText()}
          </div>
          <div class="environment-hint">${this.t("environmentHint")}</div>
        </div>

        <div class="environment-list-grid">
          <section class="environment-settings-section environment-list-card">
            <div class="environment-title-row">
              <span>${this.t("environmentVertiports")}</span>
            </div>
            <div class="environment-table-wrap" data-env-list="vertiport">${this.renderEnvironmentList("vertiport")}</div>
          </section>
          <section class="environment-settings-section environment-list-card">
            <div class="environment-title-row">
              <span>${this.t("environmentRoutes")}</span>
            </div>
            <div class="environment-table-wrap" data-env-list="corridor">${this.renderEnvironmentList("corridor")}</div>
          </section>
        </div>
        <div class="environment-action-row">
          <button type="button" class="scenario-btn" data-env-action="refresh">${this.t("environmentRefresh")}</button>
          <button type="button" class="scenario-btn scenario-btn-ghost" data-env-action="reset">${this.t("environmentReset")}</button>
        </div>
      </div>
    `;
  }

  renderScenarioPanel() {
    return `
      <div id="scenario-panel" class="panel-window panel-window-scenario ${this.state.panelOpen ? "is-visible" : ""}" aria-hidden="${this.state.panelOpen ? "false" : "true"}">
        <div class="panel-header">
          <span class="panel-title" data-panel-title>${this.panelTitle()}</span>
          <button type="button" class="panel-close" data-action="collapse-scenario">${this.t("close")}</button>
        </div>
        <div class="scenario-tabs">
          ${PANEL_MODES.map((mode) => `
            <button type="button" class="scenario-tab" data-panel-tab="${mode}">${this.t(`${mode}Panel`)}</button>
          `).join("")}
        </div>
        <div class="panel-body scenario-body">
          ${this.renderMissionPlanningSection()}
          ${this.renderEnvironmentPanelSection()}
        </div>
      </div>
    `;
  }

  bindControls() {
    this.container.querySelector("[data-action='back']")?.addEventListener("click", () => this.onBack());

    this.container.querySelectorAll("[data-panel-toggle]").forEach((button) => {
      button.addEventListener("click", () => {
        const panel = this.container.querySelector("#scenario-panel");
        const mode = button.dataset.panelToggle;
        if (panel?.classList.contains("is-visible") && this.state.activePanel === mode) {
          this.state.panelOpen = false;
          this.syncUi();
          this.updateMissionRouteOverlay();
          return;
        }
        this.setActivePanel(PANEL_MODES.includes(mode) ? mode : "environment");
        this.state.panelOpen = true;
        this.syncUi();
        this.updateMissionRouteOverlay();
      });
    });

    this.container.querySelectorAll("[data-panel-tab]").forEach((button) => {
      button.addEventListener("click", () => {
        this.setActivePanel(button.dataset.panelTab);
        this.state.panelOpen = true;
        this.syncUi();
        this.updateMissionRouteOverlay();
      });
    });

    this.container.querySelectorAll("[data-operation-mode]").forEach((button) => {
      button.addEventListener("click", () => {
        this.state.operationMode = OPERATION_MODES.includes(button.dataset.operationMode) ? button.dataset.operationMode : "single";
        if (this.state.operationMode !== "single") {
          this.state.missionInputMode = false;
          this.state.missionInputTarget = "departure";
        }
        this.state.modeSaveStatus = "idle";
        this.state.modeSaveMessage = "";
        this.invalidateExecutionPlan();
        this.clearMissionStatus();
        this.syncUi();
        this.updateMissionRouteOverlay();
      });
    });

    this.container.querySelector("[data-dynamics-model]")?.addEventListener("change", (event) => {
      this.state.dynamics = normalizeDynamicsModel(event.target.value);
      this.invalidateExecutionPlan();
      this.state.modeSaveStatus = "idle";
      this.state.modeSaveMessage = "";
      this.syncUi();
    });

    this.container.querySelectorAll("[data-controller-mode]").forEach((button) => {
      button.addEventListener("click", () => {
        this.state.mainVehicleController = CONTROLLER_MODES.includes(button.dataset.controllerMode) ? button.dataset.controllerMode : "";
        this.invalidateExecutionPlan();
        this.state.modeSaveStatus = "idle";
        this.state.modeSaveMessage = "";
        this.syncUi();
      });
    });

    this.container.querySelector("[data-action='save-mode-settings']")?.addEventListener("click", () => {
      this.sendModeSettings();
    });

    this.container.querySelector("[data-action='dtam-execute']")?.addEventListener("click", () => {
      this.launchDtamWorldOnly();
    });

    this.container.querySelectorAll("[data-action='cycle-speed']").forEach((button) => {
      button.addEventListener("click", () => {
        const current = SPEEDS.includes(this.state.playbackSpeed) ? this.state.playbackSpeed : 1;
        const currentIndex = SPEEDS.indexOf(current);
        this.state.playbackSpeed = SPEEDS[(currentIndex + 1 + SPEEDS.length) % SPEEDS.length];
        this.refresh();
        this.updateWindVisualization();
        this.scheduleSend({ immediate: true });
      });
    });

    this.container.querySelector("[data-action='collapse-scenario']")?.addEventListener("click", () => {
      const panel = this.container.querySelector("#scenario-panel");
      this.state.panelOpen = false;
      this.syncUi();
      this.updateMissionRouteOverlay();
    });

    this.container.querySelector("[data-action='close-uam-detail']")?.addEventListener("click", () => {
      this.closeUamVehicleDetail();
    });

    this.container.querySelector("[data-uam-vehicle-detail]")?.addEventListener("click", (event) => {
      const button = event.target?.closest?.("[data-action='clear-uam-collision']");
      if (button) {
        this.clearUamVehicleCollision(button.dataset.vehicleId);
      }
    });

    this.container.querySelectorAll("[data-map-zoom]").forEach((button) => {
      button.addEventListener("click", () => this.handleMapControl(button.dataset.mapZoom));
    });

    this.container.querySelector("[data-action='toggle-commercial-traffic']")?.addEventListener("click", () => {
      this.toggleCommercialTraffic();
    });

    this.container.querySelector("[data-action='toggle-weather-dock']")?.addEventListener("click", () => {
      this.state.weatherDockOpen = !this.state.weatherDockOpen;
      this.syncUi();
    });

    this.container.querySelector("[data-action='toggle-abnormal-dashboard']")?.addEventListener("click", () => {
      this.state.abnormalDashboardOpen = !this.state.abnormalDashboardOpen;
      this.syncUi();
      this.updateOperationalLayers();
    });

    this.container.querySelector("[data-action='select-bird-flock']")?.addEventListener("click", () => {
      this.state.abnormalType = "bird_flock";
      this.state.abnormalDashboardOpen = true;
      this.syncUi();
    });

    this.container.querySelector("[data-action='toggle-abnormal-pick']")?.addEventListener("click", () => {
      this.setAbnormalPickMode(!this.state.abnormalPickMode);
    });

    this.container.querySelector("[data-action='clear-abnormal-zone']")?.addEventListener("click", () => {
      this.state.abnormalPickMode = false;
      this.state.abnormalZoneVisible = false;
      this.state.abnormalStatus = "";
      this.syncAbnormalDashboardUi();
      this.updateOperationalLayers();
      this.updateAbnormalScrollZoom();
    });

    this.container.querySelector("[data-action='apply-abnormal-event']")?.addEventListener("click", () => {
      void this.sendAbnormalSituationCommand();
    });

    this.container.querySelector("[data-abnormal-radius]")?.addEventListener("input", (event) => {
      this.state.abnormalRadiusM = normalizeNumber(
        event.target.value,
        ABNORMAL_ZONE_MIN_RADIUS_M,
        ABNORMAL_ZONE_MAX_RADIUS_M,
        DEFAULT_STATE.abnormalRadiusM,
      );
      this.state.abnormalZoneVisible = true;
      this.syncAbnormalDashboardUi();
      this.updateOperationalLayers();
    });

    this.container.querySelector("[data-action='toggle-weather-visualization']")?.addEventListener("click", () => {
      this.state.weatherVisualizationEnabled = !this.state.weatherVisualizationEnabled;
      this.refresh();
      this.updateWindVisualization();
    });

    this.container.querySelectorAll("[data-play-state]").forEach((button) => {
      button.addEventListener("click", () => {
        const nextPlayState = button.dataset.playState;
        this.setPlayState(nextPlayState);
        this.refresh();
        this.updateWindVisualization();
        this.scheduleSend({ immediate: true });
      });
    });

    this.container.querySelectorAll("[data-speed]").forEach((button) => {
      button.addEventListener("click", () => {
        const speed = Number(button.dataset.speed);
        this.setPlaybackSpeed(speed);
        this.refresh();
        this.updateWindVisualization();
        this.scheduleSend({ immediate: true });
      });
    });

    this.container.querySelectorAll("[data-wind-grade]").forEach((button) => {
      button.addEventListener("click", () => {
        this.state.windGrade = WIND_GRADES.includes(button.dataset.windGrade) ? button.dataset.windGrade : "normal";
        this.refresh();
        this.updateWindVisualization();
        this.scheduleWeatherIcdSend({ immediate: true });
      });
    });

    this.container.querySelectorAll("[data-demo-scenario]").forEach((button) => {
      button.addEventListener("click", () => {
        const id = button.dataset.demoScenario || "";
        this.state.demoScenarioId = ["S1", "S2", "S3"].includes(id) ? id : null;
        this.refresh();
      });
    });

    this.container.querySelectorAll("[data-map-theme]").forEach((button) => {
      button.addEventListener("click", () => {
        this.state.mapTheme = MAP_THEME_KEYS.includes(button.dataset.mapTheme) ? button.dataset.mapTheme : "dark";
        this.setMapTheme();
        this.refresh();
      });
    });

    this.container.querySelector("[data-precipitation-type]")?.addEventListener("change", (event) => {
      this.state.precipitationType = PRECIPITATION_TYPES.includes(event.target.value) ? event.target.value : "none";
      if (this.state.precipitationType === "none") {
        this.state.precipitationIntensity = 0;
      }
      this.refresh();
      this.updateWindVisualization();
      this.scheduleWeatherIcdSend({ immediate: true });
    });

    this.container.querySelector("[data-precipitation-intensity]")?.addEventListener("input", (event) => {
      this.state.precipitationIntensity =
        this.state.precipitationType === "none" ? 0 : step01(normalizeNumber(event.target.value, 0, 1, 0));
      this.updateRangeLabels();
      this.updateOperationalLayers();
      this.updateWindVisualization();
      this.scheduleWeatherIcdSend();
    });

    this.container.querySelector("[data-fog-intensity]")?.addEventListener("input", (event) => {
      this.state.fogIntensity = step01(normalizeNumber(event.target.value, 0, 1, 0));
      this.updateRangeLabels();
      this.updateOperationalLayers();
      this.updateWindVisualization();
      this.scheduleWeatherIcdSend();
    });

    this.container.querySelector("[data-action='toggle-gust-apply']")?.addEventListener("click", () => {
      this.state.gustApplyMode = !this.state.gustApplyMode;
      this.refresh();
      this.updateWindVisualization();
      this.scheduleWeatherIcdSend({ immediate: true });
    });

    this.container.querySelector("[data-action='reset-gust']")?.addEventListener("click", () => {
      this.state.gustApplyMode = false;
      this.state.gustEnabled = false;
      this.state.gustLat = DEFAULT_STATE.gustLat;
      this.state.gustLon = DEFAULT_STATE.gustLon;
      this.state.gustRadius = DEFAULT_STATE.gustRadius;
      this.refresh();
      this.updateWindVisualization();
      this.scheduleWeatherIcdSend({ immediate: true });
    });

    this.container.querySelector("[data-gust-radius]")?.addEventListener("input", (event) => {
      this.state.gustRadius = normalizeNumber(event.target.value, 400, 4000, DEFAULT_STATE.gustRadius);
      this.updateRangeLabels();
      this.updateOperationalLayers();
      this.updateWindVisualization();
      this.scheduleWeatherIcdSend();
    });

    this.container.querySelector(".uatm-sim")?.addEventListener("input", (event) => {
      if (event.target.matches("[data-mission-time-part]")) {
        this.sanitizeMissionTimePartInput(event.target);
        this.commitMissionDepartureTimeInput(event.target, { normalizeDisplay: false });
        return;
      }
      if (event.target.matches("[data-mission-departure-time-id]")) {
        const draftTime = String(event.target.value || "").trim();
        if (/^\d{1,2}:\d{2}(?::\d{2})?$/.test(draftTime) || /^\d{4}$/.test(draftTime) || /^\d{6}$/.test(draftTime)) {
          this.setMissionDepartureTime(
            event.target.dataset.missionDepartureTimeId,
            draftTime,
            { refresh: false },
          );
        }
      }
    });

    this.container.querySelector(".uatm-sim")?.addEventListener("focusin", (event) => {
      if (event.target.matches("[data-mission-time-part]")) {
        event.target.select();
      }
    });

    this.container.querySelector(".uatm-sim")?.addEventListener("wheel", (event) => {
      const timePartInput = event.target.closest("[data-mission-time-part]");
      if (!timePartInput) {
        return;
      }
      event.preventDefault();
      this.adjustMissionDepartureTimePart(timePartInput, event.deltaY < 0 ? 1 : -1);
    }, { passive: false });

    this.container.querySelector(".uatm-sim")?.addEventListener("click", (event) => {
      if (event.target.closest("[data-action='clear-operation-log']")) {
        this.clearOperationLogs();
        return;
      }

      const missionActionButton = event.target.closest("[data-mission-action]");
      if (missionActionButton?.dataset.missionAction === "add") {
        this.addMissionAircraft();
        return;
      }

      const trafficFplFolderButton = event.target.closest("[data-traffic-fpl-folder]");
      if (trafficFplFolderButton) {
        this.selectTrafficFplFolder(trafficFplFolderButton.dataset.trafficFplFolder);
        return;
      }

      const trafficCustomActionButton = event.target.closest("[data-traffic-custom-action]");
      if (trafficCustomActionButton?.dataset.trafficCustomAction) {
        if (trafficCustomActionButton.dataset.trafficCustomAction === "generate") {
          void this.launchTrafficScheduleGenerator();
        } else {
          void this.openTrafficFplFolderPicker();
        }
        return;
      }

      const missionDeleteButton = event.target.closest("[data-mission-delete]");
      if (missionDeleteButton?.dataset.missionDelete) {
        this.removeMissionAircraft(missionDeleteButton.dataset.missionDelete);
        return;
      }

      const missionDynamicsButton = event.target.closest("[data-mission-dynamics-id]");
      if (missionDynamicsButton) {
        this.setMissionDynamics(
          missionDynamicsButton.dataset.missionDynamicsId,
          missionDynamicsButton.dataset.missionDynamicsModel || "simple",
        );
        return;
      }

      const missionControllerButton = event.target.closest("[data-mission-controller-id]");
      if (missionControllerButton) {
        this.setMissionControllerOverride(
          missionControllerButton.dataset.missionControllerId,
          missionControllerButton.dataset.missionControllerMode || "",
        );
        return;
      }

      if (event.target.closest("[data-mission-departure-time-id]")) {
        return;
      }

      const missionCard = event.target.closest("[data-mission-card]");
      if (missionCard?.dataset.missionCard) {
        this.activateMissionEntry(missionCard.dataset.missionCard, { armInput: true });
        return;
      }

      const toolButton = event.target.closest("[data-env-tool]");
      if (toolButton) {
        this.setEnvironmentTool(toolButton.dataset.envTool);
        return;
      }

      const actionButton = event.target.closest("[data-env-action]");
      if (actionButton) {
        this.handleEnvironmentPanelAction(actionButton.dataset.envAction);
        return;
      }

      const listButton = event.target.closest("[data-env-select-kind][data-env-select-name]");
      if (listButton) {
        this.selectEnvironmentFeature(listButton.dataset.envSelectKind, listButton.dataset.envSelectName, { flyTo: true });
      }
    });

    this.container.querySelector(".uatm-sim")?.addEventListener("change", (event) => {
      if (event.target.matches("[data-mission-time-part]")) {
        this.sanitizeMissionTimePartInput(event.target);
        this.commitMissionDepartureTimeInput(event.target, { normalizeDisplay: true });
        return;
      }
      if (event.target.matches("[data-mission-departure-time-id]")) {
        this.setMissionDepartureTime(
          event.target.dataset.missionDepartureTimeId,
          event.target.value,
        );
        return;
      }
      if (event.target.matches("[data-traffic-density]")) {
        this.state.trafficDensity = TRAFFIC_DENSITIES.includes(event.target.value) ? event.target.value : "middle";
        this.state.modeSaveStatus = "idle";
        this.state.modeSaveMessage = "";
        this.clearMissionStatus();
        this.syncUi();
        return;
      }
      if (event.target.matches("[data-traffic-folder-input]")) {
        this.handleTrafficMissionFolderSelection(event.target.files, event.target.dataset.trafficFolderInput);
      }
    });

    this.container.querySelector(".uatm-sim")?.addEventListener("keydown", (event) => {
      const timePartInput = event.target.closest("[data-mission-time-part]");
      if (timePartInput) {
        if (event.key === "ArrowUp" || event.key === "ArrowDown") {
          event.preventDefault();
          this.adjustMissionDepartureTimePart(timePartInput, event.key === "ArrowUp" ? 1 : -1);
        }
        return;
      }
      if (
        event.target.closest("[data-mission-delete]")
        || event.target.closest("[data-mission-controller-id]")
        || event.target.closest("[data-mission-dynamics-id]")
        || event.target.closest("[data-mission-departure-time-id]")
      ) {
        return;
      }
      const missionCard = event.target.closest("[data-mission-card]");
      if (!missionCard?.dataset.missionCard) {
        return;
      }
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        this.activateMissionEntry(missionCard.dataset.missionCard, { armInput: true });
      }
    });
  }

  setEnvironmentTool(tool) {
    this.state.environmentTool = ENVIRONMENT_TOOLS.includes(tool) ? tool : "select";
    this.environmentMoveTarget = null;
    this.environmentLinkSource = null;
    if (this.state.environmentTool === "link") {
      this.setEnvironmentStatus(this.t("environmentSelectTarget"));
    } else if (this.state.environmentTool === "select") {
      this.setEnvironmentStatus(this.t("environmentReady"));
    } else {
      this.setEnvironmentStatus(this.t("environmentHint"));
    }
    this.syncUi();
  }

  handleEnvironmentPanelAction(action) {
    if (action === "refresh") {
      this.loadOperationalEnvironment({ force: true });
      return;
    }
    if (action === "reset") {
      this.resetOperationalEnvironment();
    }
  }

  setActivePanel(mode) {
    if (!PANEL_MODES.includes(mode)) {
      return;
    }
    this.state.activePanel = mode;
    this.syncUi();
  }

  invalidateExecutionPlan() {
    this.executionPreparationKey = "";
    this.executionArmKey = "";
    this.savedModeSettingsKey = "";
    this.state.connectionStatus = "disconnected";
  }

  clearMissionStatus() {
    this.state.missionStatusMessage = "";
    this.state.missionStatusLevel = "info";
  }

  setMissionStatus(message, level = "info") {
    this.state.missionStatusMessage = message || "";
    this.state.missionStatusLevel = level;
    this.syncMissionPlanningUi();
  }

  pushOperationLog(message, options = {}) {
    const time = new Date().toLocaleTimeString(this.language === "ko" ? "ko-KR" : "en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
    const nextLog = {
      id: `log-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`,
      title: options.title || this.t("operationAlert"),
      message: message || "",
      level: options.level || "info",
      time,
    };
    const logs = Array.isArray(this.state.operationLogs) ? this.state.operationLogs : [];
    this.state.operationLogs = [nextLog, ...logs].slice(0, 4);
    this.syncOperationLogUi();
    window.clearTimeout(this.operationLogTimer);
    this.operationLogTimer = window.setTimeout(() => this.clearOperationLogs(), Number(options.durationMs || 7000));
  }

  clearOperationLogs() {
    window.clearTimeout(this.operationLogTimer);
    this.operationLogTimer = null;
    this.state.operationLogs = [];
    this.syncOperationLogUi();
  }

  syncOperationLogUi() {
    const panel = this.container.querySelector("[data-operation-log-panel]");
    if (!panel) {
      return;
    }
    const logs = Array.isArray(this.state.operationLogs) ? this.state.operationLogs : [];
    panel.classList.toggle("is-visible", logs.length > 0);
    panel.querySelector("[data-operation-log-list]")?.replaceChildren();
    const list = panel.querySelector("[data-operation-log-list]");
    if (list) {
      list.innerHTML = this.renderOperationLogEntries();
    }
  }

  addMissionAircraft() {
    if (this.isDemoScenarioLocked()) {
      return;
    }
    this.missionEntryCount += 1;
    const nextEntry = createMissionAircraftEntry(this.missionEntryCount, normalizeDynamicsModel(this.state.dynamics));
    this.state.missionEntries = [...(this.state.missionEntries || []), nextEntry];
    this.state.activeMissionId = nextEntry.id;
    this.state.operationMode = "single";
    this.state.activePanel = "mission";
    this.state.panelOpen = true;
    this.state.modeSaveStatus = "idle";
    this.state.modeSaveMessage = "";
    this.invalidateExecutionPlan();
    this.clearMissionStatus();
    this.refresh();
  }

  async launchTrafficScheduleGenerator() {
    if (this.state.trafficSchedulerLaunching) {
      return;
    }
    this.state.trafficSchedulerLaunching = true;
    this.pushOperationLog(this.t("trafficSchedulerLaunchStarting"), {
      title: "UAM Flight Scheduler",
      level: "info",
      durationMs: 12000,
    });
    try {
      const payload = await postJSON(FLIGHT_SCHEDULER_LAUNCH_URL, {});
      const url = String(payload?.url || "").trim();
      this.pushOperationLog(url ? `${this.t("trafficSchedulerLaunchOk")} (${url})` : this.t("trafficSchedulerLaunchOk"), {
        title: "UAM Flight Scheduler",
        level: "success",
        durationMs: 12000,
      });
    } catch (error) {
      const message = error?.message ? `${this.t("trafficSchedulerLaunchError")} ${error.message}` : this.t("trafficSchedulerLaunchError");
      this.pushOperationLog(message, {
        title: "UAM Flight Scheduler",
        level: "error",
        durationMs: 12000,
      });
    } finally {
      this.state.trafficSchedulerLaunching = false;
    }
  }

  openTrafficMissionFolderInput(action) {
    const normalizedAction = action === "generate" ? "generate" : "load";
    const input = this.container.querySelector(`[data-traffic-folder-input='${normalizedAction}']`);
    if (!input) {
      return;
    }
    input.value = "";
    input.click();
  }

  async openTrafficFplFolderPicker() {
    // 불러오기: 서버에 있는 PlugIn/FlightScheduler/FPL 하위 폴더 목록을 받아
    // 인라인 리스트로 보여준다. 실패/빈 목록이면 기존 webkitdirectory 입력으로 폴백.
    const list = this.container.querySelector("[data-traffic-fpl-list]");
    if (!list) {
      this.openTrafficMissionFolderInput("load");
      return;
    }
    list.hidden = false;
    list.replaceChildren(document.createTextNode(this.t("trafficFplListLoading")));
    let folders = [];
    try {
      const response = await fetch(TRAFFIC_FPL_FOLDERS_URL, { headers: { Accept: "application/json" }, cache: "no-store" });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      folders = Array.isArray(data) ? data : (Array.isArray(data?.folders) ? data.folders : []);
    } catch (error) {
      folders = [];
    }
    if (!folders.length) {
      list.hidden = true;
      list.replaceChildren();
      this.setMissionStatus(this.t("trafficFplListFallback"), "info");
      this.openTrafficMissionFolderInput("load");
      return;
    }
    this.renderTrafficFplFolderList(folders);
  }

  renderTrafficFplFolderList(folders) {
    const list = this.container.querySelector("[data-traffic-fpl-list]");
    if (!list) {
      return;
    }
    const buttons = folders
      .map((folder) => {
        const name = String(folder?.name ?? folder ?? "").trim();
        if (!name) {
          return null;
        }
        const button = document.createElement("button");
        button.type = "button";
        button.className = "scenario-btn traffic-fpl-folder-btn";
        button.dataset.trafficFplFolder = name;
        const flightCount = Number(folder?.flightCount ?? folder?.flight_count);
        const modified = String(folder?.modified ?? folder?.modifiedAt ?? "").trim();
        const meta = [
          Number.isFinite(flightCount) ? this.tf("trafficFplFlightCount", { count: flightCount }) : "",
          modified,
        ].filter(Boolean).join(" · ");
        button.textContent = meta ? `${name} — ${meta}` : name;
        return button;
      })
      .filter(Boolean);
    list.hidden = false;
    list.replaceChildren(...buttons);
  }

  selectTrafficFplFolder(folderName) {
    const name = String(folderName || "").trim();
    if (!name) {
      return;
    }
    this.state.trafficCustomMissionAction = "load";
    this.state.trafficCustomMissionFolderName = name;
    this.state.modeSaveStatus = "idle";
    this.state.modeSaveMessage = "";
    const list = this.container.querySelector("[data-traffic-fpl-list]");
    if (list) {
      list.hidden = true;
      list.replaceChildren();
    }
    this.clearMissionStatus();
    this.syncUi();
  }

  handleTrafficMissionFolderSelection(fileList, action) {
    const files = Array.from(fileList || []);
    if (!files.length) {
      return;
    }
    const relativePath = String(files[0]?.webkitRelativePath || files[0]?.name || "").replaceAll("\\", "/");
    const folderName = relativePath.split("/").filter(Boolean)[0] || "";
    this.state.trafficCustomMissionAction = action === "generate" ? "generate" : "load";
    this.state.trafficCustomMissionFolderName = folderName;
    this.state.modeSaveStatus = "idle";
    this.state.modeSaveMessage = "";
    this.clearMissionStatus();
    this.syncUi();
  }

  removeMissionAircraft(id) {
    if (this.isDemoScenarioLocked()) {
      return;
    }
    const entries = Array.isArray(this.state.missionEntries) ? this.state.missionEntries : [];
    const removeIndex = entries.findIndex((entry) => entry.id === id);
    if (removeIndex < 0) {
      return;
    }

    const nextEntries = entries.filter((entry) => entry.id !== id);
    const fallbackEntry = nextEntries[removeIndex] || nextEntries[Math.max(0, removeIndex - 1)] || nextEntries[0] || null;

    this.state.missionEntries = nextEntries;
    this.state.activeMissionId = fallbackEntry?.id || "";
    this.state.missionInputMode = false;
    this.state.missionInputTarget = "departure";
    this.state.modeSaveStatus = "idle";
    this.state.modeSaveMessage = "";
    this.invalidateExecutionPlan();
    this.clearMissionStatus();
    this.refresh();
  }

  setMissionDynamics(id, dynamics) {
    if (this.isDemoScenarioLocked()) {
      return;
    }
    const entry = (this.state.missionEntries || []).find((item) => item.id === id);
    if (!entry) {
      return;
    }
    entry.dynamics = normalizeDynamicsModel(dynamics);
    this.invalidateExecutionPlan();
    this.state.modeSaveStatus = "idle";
    this.state.modeSaveMessage = "";
    this.syncMissionPlanningUi();
    this.syncUi();
  }

  setMissionDepartureTime(id, value, options = {}) {
    if (this.isDemoScenarioLocked()) {
      return;
    }
    const entry = (this.state.missionEntries || []).find((item) => item.id === id);
    if (!entry) {
      return;
    }
    const fallback = entry.departureTime || entry.std || defaultMissionDepartureTime();
    const departureTime = normalizeMissionDepartureTime(value, fallback);
    entry.departureTime = departureTime;
    entry.std = departureTime;
    this.invalidateExecutionPlan();
    this.state.modeSaveStatus = "idle";
    this.state.modeSaveMessage = "";
    if (options.refresh === false) {
      return;
    }
    this.syncMissionPlanningUi();
    this.syncUi();
  }

  setMissionControllerOverride(id, controller) {
    if (this.isDemoScenarioLocked()) {
      return;
    }
    const entry = (this.state.missionEntries || []).find((item) => item.id === id);
    if (!entry) {
      return;
    }
    entry.controllerOverride = CONTROLLER_MODES.includes(controller) ? controller : "";
    this.invalidateExecutionPlan();
    this.state.modeSaveStatus = "idle";
    this.state.modeSaveMessage = "";
    this.syncMissionPlanningUi();
    this.syncUi();
  }

  activateMissionEntry(id, options = {}) {
    if (this.isDemoScenarioLocked()) {
      return;
    }
    const entry = (this.state.missionEntries || []).find((item) => item.id === id);
    if (!entry) {
      return;
    }
    this.state.activeMissionId = id;
    if (options.armInput) {
      this.state.panelOpen = true;
      this.state.activePanel = "mission";
      this.state.missionInputMode = true;
      this.state.missionInputTarget = entry.routeData ? "departure" : (entry.departureName ? "arrival" : "departure");
      this.clearMissionStatus();
    }
    this.refresh();
  }

  missionEntryForUamVehicleId(vehicleId) {
    const canonicalId = this.canonicalUamVehicleId(vehicleId);
    if (!canonicalId) {
      return null;
    }
    const entries = Array.isArray(this.state.missionEntries) ? this.state.missionEntries : [];
    const matched = entries.find((entry) => (
      [
        entry?.aircraftName,
        entry?.aircraftId,
        entry?.vehicleId,
        entry?.vehicle_id,
      ].some((value) => this.canonicalUamVehicleId(value) === canonicalId)
    ));
    if (matched) {
      return matched;
    }

    const hasNamedEntries = entries.some((entry) => (
      entry?.aircraftName || entry?.aircraftId || entry?.vehicleId || entry?.vehicle_id
    ));
    if (hasNamedEntries) {
      return null;
    }
    const match = canonicalId.match(/^([A-Z]+)0*(\d+)$/);
    const sequence = match ? Number(match[2]) : NaN;
    return Number.isInteger(sequence) && sequence > 0 ? (entries[sequence - 1] || null) : null;
  }

  activateMissionEntryForUamVehicle(vehicleId) {
    const entry = this.missionEntryForUamVehicleId(vehicleId);
    if (!entry) {
      return null;
    }
    this.state.activeMissionId = entry.id;
    this.state.missionInputMode = false;
    this.state.missionInputTarget = entry.routeData ? "departure" : (entry.departureName ? "arrival" : "departure");
    this.syncMissionPlanningUi();
    this.syncMissionVertiportMarkerStates();
    return entry;
  }

  mergeLatestMissionPlans(missions) {
    if (!Array.isArray(missions) || missions.length < 1) {
      return false;
    }
    const entries = Array.isArray(this.state.missionEntries) ? [...this.state.missionEntries] : [];
    let changed = false;
    missions.forEach((mission, index) => {
      if (!mission || typeof mission !== "object") {
        return;
      }
      const aircraftName = mission.aircraftName || mission.aircraftId || mission.vehicleId || `UAM ${index + 1}`;
      const canonicalId = this.canonicalUamVehicleId(aircraftName);
      let entry = entries.find((item) => (
        this.canonicalUamVehicleId(item?.aircraftName || item?.aircraftId || item?.vehicleId || item?.vehicle_id) === canonicalId
      ));
      if (!entry) {
        entry = createMissionAircraftEntry(index + 1, normalizeDynamicsModel(mission.vehicleSimType?.dynamics || mission.dynamics));
        entry.aircraftName = aircraftName || entry.aircraftName;
        entries.push(entry);
        changed = true;
      }

      const nextDepartureName = mission.departureName || mission.departure?.vertiport || entry.departureName || "";
      const nextArrivalName = mission.arrivalName || mission.arrival?.vertiport || entry.arrivalName || "";
      const nextRouteData = mission.routeData && typeof mission.routeData === "object" ? mission.routeData : entry.routeData;
      const nextDepartureTime = normalizeMissionDepartureTime(
        mission.departureTime || mission.std || mission.departure?.std || entry.departureTime,
      );
      const nextDynamics = normalizeDynamicsModel(
        mission.vehicleSimType?.dynamics || mission.dynamics || entry.dynamics,
      );
      const nextController = CONTROLLER_MODES.includes(mission.vehicleSimType?.mainVehicleController)
        ? mission.vehicleSimType.mainVehicleController
        : entry.controllerOverride;

      if (
        entry.aircraftName !== aircraftName
        || entry.departureName !== nextDepartureName
        || entry.arrivalName !== nextArrivalName
        || entry.routeData !== nextRouteData
        || entry.departureTime !== nextDepartureTime
        || normalizeDynamicsModel(entry.dynamics) !== nextDynamics
        || entry.controllerOverride !== nextController
      ) {
        entry.aircraftName = aircraftName || entry.aircraftName;
        entry.departureName = nextDepartureName;
        entry.arrivalName = nextArrivalName;
        entry.routeData = nextRouteData || null;
        entry.departureTime = nextDepartureTime;
        entry.std = nextDepartureTime;
        entry.dynamics = nextDynamics;
        entry.controllerOverride = nextController;
        changed = true;
      }
    });
    if (changed) {
      this.state.missionEntries = entries;
    }
    return changed;
  }

  normalizeLatestMissionPlanResponse(data) {
    if (data?.ok && Array.isArray(data.missions)) {
      return data;
    }

    const payload = data?.payload && typeof data.payload === "object" ? data.payload : {};
    const singleFlight = payload.singleFlight && typeof payload.singleFlight === "object" ? payload.singleFlight : {};
    const missionPlanning = singleFlight.missionPlanning && typeof singleFlight.missionPlanning === "object"
      ? singleFlight.missionPlanning
      : {};
    const missions = Array.isArray(missionPlanning.missions) ? missionPlanning.missions : [];
    return {
      ok: missions.length > 0,
      source: data?.source || "StateServer",
      path: data?.path || "",
      modifiedAt: data?.modifiedAt || data?.modified_at || "",
      activeMissionId: missionPlanning.activeMissionId || "",
      missions,
    };
  }

  async fetchLatestMissionPlanData() {
    let proxyData = null;
    try {
      proxyData = this.normalizeLatestMissionPlanResponse(await getJSON(LATEST_MISSION_PLANS_URL));
      if (proxyData?.ok && proxyData.missions?.length) {
        return proxyData;
      }
    } catch {
      proxyData = null;
    }

    try {
      return this.normalizeLatestMissionPlanResponse(await getJSON(STATE_SERVER_LATEST_MISSION_PLANS_URL));
    } catch {
      return proxyData;
    }
  }

  async loadLatestMissionPlans(options = {}) {
    if (this.latestMissionPlanPromise) {
      return this.latestMissionPlanPromise;
    }
    this.latestMissionPlanLoading = true;
    this.latestMissionPlanPromise = this.fetchLatestMissionPlanData()
      .then((data) => {
        if (data?.ok && Array.isArray(data.missions)) {
          this.mergeLatestMissionPlans(data.missions);
          if (options.focusVehicleId) {
            this.activateMissionEntryForUamVehicle(options.focusVehicleId);
          }
          this.syncMissionPlanningUi();
          this.syncMissionVertiportMarkerStates();
          this.updateMissionRouteOverlay();
        }
        return data;
      })
      .catch(() => null)
      .finally(() => {
        this.latestMissionPlanLoading = false;
        this.latestMissionPlanPromise = null;
      });
    return this.latestMissionPlanPromise;
  }

  missionEntryHasVisibleRoute(entry) {
    if (!entry?.routeData) {
      return false;
    }
    return this.missionRouteLinePoints(entry.routeData).length > 1
      || this.missionRouteMarkerPoints(entry.routeData).length > 1;
  }

  async ensureMissionRouteForUamVehicle(vehicleId) {
    let entry = this.missionEntryForUamVehicleId(vehicleId);
    if (this.missionEntryHasVisibleRoute(entry)) {
      this.updateMissionRouteOverlay();
      return entry;
    }

    await this.loadLatestMissionPlans({ focusVehicleId: vehicleId });
    entry = this.missionEntryForUamVehicleId(vehicleId);
    if (this.missionEntryHasVisibleRoute(entry)) {
      this.updateMissionRouteOverlay();
      return entry;
    }

    if (!entry?.departureName || !entry?.arrivalName) {
      this.updateMissionRouteOverlay();
      return entry || null;
    }
    try {
      entry.routeData = await postJSON(MISSION_ROUTE_URL, {
        start: entry.departureName,
        end: entry.arrivalName,
        include_arcs: true,
      });
      this.activateMissionEntryForUamVehicle(vehicleId);
      this.syncMissionPlanningUi();
      this.updateMissionRouteOverlay();
    } catch {
      this.updateMissionRouteOverlay();
    }
    return entry;
  }

  isMissionMapInputActive() {
    return this.state.operationMode === "single"
      && this.state.panelOpen
      && this.state.activePanel === "mission"
      && this.state.missionInputMode;
  }

  handleMissionMapClick(event) {
    if (!this.isMissionMapInputActive()) {
      return false;
    }
    const picked = this.pickOperationalEnvironmentFeature(event?.point);
    if (picked?.type === "point" && picked.kind === "vertiport" && picked.name) {
      void this.handleMissionVertiportSelection(picked.name);
      return true;
    }
    this.setMissionStatus(this.t("missionSelectVertiport"), "info");
    return true;
  }

  handleMissionVertiportSelection(name) {
    if (!this.isMissionMapInputActive()) {
      return false;
    }
    const entry = this.activeMissionEntry();
    if (!entry || !name) {
      return true;
    }
    if (this.state.missionInputTarget !== "arrival") {
      entry.departureName = name;
      entry.arrivalName = "";
      entry.routeData = null;
      this.state.missionInputTarget = "arrival";
      this.invalidateExecutionPlan();
      this.clearMissionStatus();
      this.refresh();
      return true;
    }
    if (entry.departureName === name) {
      this.setMissionStatus(this.t("missionSameVertiport"), "error");
      return true;
    }

    entry.arrivalName = name;
    entry.routeData = null;
    this.state.missionInputMode = false;
    this.invalidateExecutionPlan();
    this.setMissionStatus(this.t("missionRouteComputing"), "info");
    this.refresh();
    void this.requestMissionRoute(entry.id, entry.departureName, entry.arrivalName);
    return true;
  }

  async requestMissionRoute(entryId, departureName, arrivalName) {
    const requestSeq = ++this.missionRouteRequestSeq;
    try {
      const routeData = await postJSON(MISSION_ROUTE_URL, {
        start: departureName,
        end: arrivalName,
        include_arcs: true,
      });
      if (this.destroyed || requestSeq !== this.missionRouteRequestSeq) {
        return;
      }
      const entry = (this.state.missionEntries || []).find((item) => item.id === entryId);
      if (!entry || entry.departureName !== departureName || entry.arrivalName !== arrivalName) {
        return;
      }
      entry.routeData = routeData;
      this.executionPreparationKey = "";
      this.executionArmKey = "";
      this.clearMissionStatus();
      this.refresh();
    } catch (error) {
      if (this.destroyed || requestSeq !== this.missionRouteRequestSeq) {
        return;
      }
      const entry = (this.state.missionEntries || []).find((item) => item.id === entryId);
      if (!entry || entry.departureName !== departureName || entry.arrivalName !== arrivalName) {
        return;
      }
      entry.routeData = null;
      this.setMissionStatus(`${this.t("missionRouteFailed")}: ${error.message}`, "error");
      this.refresh();
    }
  }

  async refreshMissionRoutesForExecution() {
    const entries = Array.isArray(this.state.missionEntries) ? this.state.missionEntries : [];
    await Promise.all(entries.map(async (entry) => {
      if (!entry?.departureName || !entry?.arrivalName) {
        return;
      }
      entry.routeData = await postJSON(MISSION_ROUTE_URL, {
        start: entry.departureName,
        end: entry.arrivalName,
        include_arcs: true,
      });
    }));
    this.clearMissionStatus();
    this.refresh();
  }

  windPreset() {
    const presetByGrade = {
      normal: "good",
      warning: "bad",
      serious: "serious",
    };
    return normalizeWindPreset(presetByGrade[this.state.windGrade] || "good");
  }

  ensureWindVisualization() {
    if (!this.map) {
      return;
    }
    const preset = this.windPreset();
    if (!this.windModel) {
      this.windModel = new WindModel({ preset });
    }
    this.windModel.setPreset(preset);
    this.windModel.setTimeSpeed(60 * (SPEEDS.includes(this.state.playbackSpeed) ? this.state.playbackSpeed : 1));
    if (!this.windLayer) {
      this.windLayer = new WeatherLayer(this.map, this.windModel, {
        stepMeters: WEATHER_STEP_METERS,
        maxPoints: WEATHER_MAX_POINTS,
      });
    }
    this.windLayer.start();
  }

  syncLocalWindZone() {
    if (!this.windModel) {
      return;
    }
    this.windModel.clearLocalZones(true);
    if (!this.state.gustEnabled) {
      return;
    }
    this.windModel.addLocalZone(
      lonToX(this.state.gustLon),
      latToY(this.state.gustLat),
      normalizeNumber(this.state.gustRadius, 0, 50000, DEFAULT_STATE.gustRadius),
      this.windPreset(),
    );
  }

  updateWindVisualization() {
    if (!this.state.weatherVisualizationEnabled) {
      this.windLayer?.stop();
      this.windLayer = null;
      this.windModel?.clearLocalZones(true);
      return;
    }
    this.ensureWindVisualization();
    this.syncLocalWindZone();
    this.windLayer?.refresh();
  }

  applyLocalWind(lngLat) {
    this.state.gustEnabled = true;
    this.state.gustLat = Number(lngLat.lat.toFixed(5));
    this.state.gustLon = Number(lngLat.lng.toFixed(5));
    this.updateOperationalLayers();
    this.updateWindVisualization();
    this.refresh();
    this.scheduleWeatherIcdSend({ immediate: true });
  }

  setAbnormalPickMode(enabled) {
    this.state.abnormalPickMode = Boolean(enabled);
    this.state.abnormalDashboardOpen = true;
    this.state.abnormalZoneVisible = true;
    if (this.map && (!Number.isFinite(Number(this.state.abnormalLat)) || !Number.isFinite(Number(this.state.abnormalLon)))) {
      const center = this.map.getCenter();
      this.state.abnormalLat = Number(center.lat.toFixed(6));
      this.state.abnormalLon = Number(center.lng.toFixed(6));
    }
    this.updateAbnormalScrollZoom();
    this.updateOperationalLayers();
    this.syncUi();
  }

  updateAbnormalScrollZoom() {
    if (!this.map?.scrollZoom) {
      return;
    }
    if (this.state.abnormalPickMode) {
      this.map.scrollZoom.disable();
    } else {
      this.map.scrollZoom.enable();
    }
  }

  handleAbnormalMapClick(event) {
    if (!this.state.abnormalPickMode) {
      return false;
    }
    const lngLat = event?.lngLat;
    if (!lngLat) {
      return true;
    }
    this.state.abnormalLat = Number(lngLat.lat.toFixed(6));
    this.state.abnormalLon = Number(lngLat.lng.toFixed(6));
    this.state.abnormalZoneVisible = true;
    this.state.abnormalStatus = "";
    this.syncAbnormalDashboardUi();
    this.updateOperationalLayers();
    return true;
  }

  handleAbnormalMapWheel(event) {
    if (!this.state.abnormalPickMode) {
      return false;
    }
    event.preventDefault();
    event.stopPropagation();
    const direction = Number(event.deltaY || 0) < 0 ? 1 : -1;
    this.state.abnormalRadiusM = normalizeNumber(
      Number(this.state.abnormalRadiusM || DEFAULT_STATE.abnormalRadiusM) + direction * ABNORMAL_ZONE_RADIUS_STEP_M,
      ABNORMAL_ZONE_MIN_RADIUS_M,
      ABNORMAL_ZONE_MAX_RADIUS_M,
      DEFAULT_STATE.abnormalRadiusM,
    );
    this.state.abnormalZoneVisible = true;
    this.syncAbnormalDashboardUi();
    this.updateOperationalLayers();
    return true;
  }

  buildAbnormalSituationPayload() {
    const now = new Date();
    const timestamp = now.toISOString();
    const stamp = timestamp.replaceAll(":", "").replaceAll("-", "").replace(/\.\d{3}Z$/, "Z");
    const obstacleId = `bird_flock_${stamp}`;
    return {
      timestamp,
      commandId: `OBS-${stamp}`,
      action: "create",
      abnormalType: this.state.abnormalType || "bird_flock",
      obstacleId,
      position: {
        lat: Number(this.state.abnormalLat),
        lon: Number(this.state.abnormalLon),
        alt: normalizeNumber(this.state.abnormalAltitudeM, 10, 1000, DEFAULT_STATE.abnormalAltitudeM),
      },
      radiusM: normalizeNumber(this.state.abnormalRadiusM, ABNORMAL_ZONE_MIN_RADIUS_M, ABNORMAL_ZONE_MAX_RADIUS_M, DEFAULT_STATE.abnormalRadiusM),
      count: Math.max(1, Math.round(normalizeNumber(this.state.abnormalCount, 1, 80, DEFAULT_STATE.abnormalCount))),
      headingDeg: 0,
      speedMps: normalizeNumber(this.state.abnormalSpeedMps, 0.1, 60, DEFAULT_STATE.abnormalSpeedMps),
      durationSec: 0,
      severity: "warning",
      affectedAircraftIds: [],
      metadata: {
        source: "OperationModule",
        assetKey: "birds_fab_fbx",
        radiusEditMode: "map-wheel",
      },
    };
  }

  async sendAbnormalSituationCommand() {
    if (!Number.isFinite(Number(this.state.abnormalLat)) || !Number.isFinite(Number(this.state.abnormalLon))) {
      const center = this.map?.getCenter();
      if (center) {
        this.state.abnormalLat = Number(center.lat.toFixed(6));
        this.state.abnormalLon = Number(center.lng.toFixed(6));
      }
    }
    const payload = this.buildAbnormalSituationPayload();
    this.state.abnormalStatus = `${this.t("abnormalApply")}...`;
    this.state.abnormalStatusLevel = "info";
    this.syncAbnormalDashboardUi();
    try {
      const result = await postJSON(ABNORMAL_SITUATION_URL, { payload });
      if (result?.sent === false || (Array.isArray(result?.errors) && result.errors.length > 0)) {
        throw new Error(result.errors?.join(", ") || result.error || "5003 send rejected");
      }
      this.state.abnormalStatus = this.t("abnormalSpawnOk");
      this.state.abnormalStatusLevel = "success";
      this.state.abnormalPickMode = false;
      this.state.abnormalZoneVisible = true;
      this.pushOperationLog(this.t("abnormalSpawnOk"), { title: this.t("abnormalDashboard"), level: "success" });
    } catch (error) {
      this.state.abnormalStatus = `${this.t("abnormalSpawnError")}: ${error.message}`;
      this.state.abnormalStatusLevel = "error";
      this.pushOperationLog(this.state.abnormalStatus, { title: this.t("abnormalDashboard"), level: "error" });
    } finally {
      this.updateAbnormalScrollZoom();
      this.syncAbnormalDashboardUi();
      this.updateOperationalLayers();
    }
  }

  handleMapControl(action) {
    if (!this.map) {
      return;
    }
    if (action === "in") {
      this.map.zoomIn({ duration: 220 });
      return;
    }
    if (action === "out") {
      this.map.zoomOut({ duration: 220 });
      return;
    }
    if (action === "reset") {
      this.resetView();
    }
  }

  resetView() {
    this.map?.easeTo({
      center: SEOUL_CENTER,
      zoom: INITIAL_ZOOM,
      pitch: 0,
      bearing: 0,
      duration: 450,
    });
  }

  refresh() {
    this.syncUi();
    this.updateOperationalLayers();
    this.updateMissionRouteOverlay();
    this.syncMissionVertiportMarkerStates();
    this.updateStatus();
  }

  syncUi() {
    this.container.querySelectorAll("[data-panel-toggle]").forEach((button) => {
      button.classList.toggle("is-active", this.state.panelOpen && button.dataset.panelToggle === this.state.activePanel);
    });
    this.container.querySelectorAll("[data-panel-tab]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.panelTab === this.state.activePanel);
    });
    this.container.querySelectorAll("[data-panel-section]").forEach((section) => {
      section.classList.toggle("is-active", section.dataset.panelSection === this.state.activePanel);
    });
    this.container.querySelector("[data-panel-title]")?.replaceChildren(document.createTextNode(this.panelTitle()));
    const panel = this.container.querySelector("#scenario-panel");
    panel?.classList.toggle("is-visible", this.state.panelOpen);
    panel?.classList.toggle("is-environment-panel", this.state.activePanel === "environment");
    panel?.classList.toggle("is-mission-panel", this.state.activePanel === "mission");
    panel?.setAttribute("aria-hidden", this.state.panelOpen ? "false" : "true");

    this.container.querySelectorAll("[data-operation-mode]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.operationMode === this.state.operationMode);
    });
    this.container.querySelectorAll("[data-controller-mode]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.controllerMode === this.state.mainVehicleController);
    });
    const vehicleSection = this.container.querySelector("[data-vehicle-mode-section]");
    if (vehicleSection) {
      vehicleSection.hidden = this.state.operationMode === "traffic";
    }
    const singleMissionLayout = this.container.querySelector("[data-single-mission-layout]");
    if (singleMissionLayout) {
      singleMissionLayout.hidden = this.state.operationMode !== "single";
    }
    const trafficDensitySection = this.container.querySelector("[data-traffic-density-section]");
    if (trafficDensitySection) {
      trafficDensitySection.hidden = this.state.operationMode !== "traffic";
    }
    const trafficCustomBlock = this.container.querySelector("[data-traffic-custom-block]");
    if (trafficCustomBlock) {
      trafficCustomBlock.hidden = !(this.state.operationMode === "traffic" && this.state.trafficDensity === "customed");
    }
    const dynamicsModel = this.container.querySelector("[data-dynamics-model]");
    if (dynamicsModel) {
      dynamicsModel.value = normalizeDynamicsModel(this.state.dynamics);
    }
    const trafficDensity = this.container.querySelector("[data-traffic-density]");
    if (trafficDensity) {
      trafficDensity.value = this.state.trafficDensity;
    }
    this.container.querySelector("[data-traffic-custom-status]")
      ?.replaceChildren(document.createTextNode(this.trafficCustomMissionText()));
    this.container.querySelector("[data-mode-detail-title]")?.replaceChildren(document.createTextNode(this.t(this.state.operationMode)));
    this.container
      .querySelector("[data-mode-detail-description]")
      ?.replaceChildren(document.createTextNode(this.operationModeDescription()));
    const modeStatus = this.container.querySelector("[data-mode-save-status]");
    if (modeStatus) {
      modeStatus.dataset.modeSaveStatus = this.state.modeSaveStatus;
      modeStatus.textContent = this.modeStatusText();
    }
    const modeSaveButton = this.container.querySelector("[data-action='save-mode-settings']");
    if (modeSaveButton) {
      modeSaveButton.disabled = this.state.modeSaveStatus === "sending";
    }
    const dtamExecuteButton = this.container.querySelector("[data-action='dtam-execute']");
    if (dtamExecuteButton) {
      dtamExecuteButton.disabled = this.status === "sending";
    }

    this.container.querySelectorAll("[data-play-state]").forEach((button) => {
      const active = button.dataset.playState === this.state.playState;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
    this.container.querySelectorAll("[data-playback-state-pill]").forEach((pill) => {
      const isPlaying = this.state.playState === "play";
      pill.classList.toggle("is-visible", isPlaying);
      pill.setAttribute("aria-hidden", isPlaying ? "false" : "true");
      pill.querySelector("[data-playback-state-text]")?.replaceChildren(document.createTextNode(this.t("playbackPlaying")));
    });
    this.container.querySelectorAll("[data-speed]").forEach((button) => {
      button.classList.toggle("is-active", Number(button.dataset.speed) === this.state.playbackSpeed);
    });
    this.container.querySelectorAll("[data-speed-display]").forEach((button) => {
      const speed = SPEEDS.includes(this.state.playbackSpeed) ? this.state.playbackSpeed : 1;
      button.textContent = `${speed}x`;
      button.title = `${this.t("speed")} ${speed}x`;
      button.setAttribute("aria-label", `${this.t("speed")} ${speed}x`);
      button.classList.toggle("is-active", speed > 1);
    });
    this.container.querySelectorAll("[data-connection-indicator]").forEach((indicator) => {
      const connectionStatus = ["connected", "connecting"].includes(this.state.connectionStatus)
        ? this.state.connectionStatus
        : "disconnected";
      const label = this.t(`connection${connectionStatus.charAt(0).toUpperCase()}${connectionStatus.slice(1)}`);
      indicator.classList.remove(
        "dtam-link-indicator--connected",
        "dtam-link-indicator--connecting",
        "dtam-link-indicator--disconnected",
      );
      indicator.classList.add(`dtam-link-indicator--${connectionStatus}`);
      indicator.title = label;
      indicator.setAttribute("aria-label", label);
    });
    this.container.querySelectorAll("[data-wind-grade]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.windGrade === this.state.windGrade);
    });
    this.container.querySelectorAll("[data-map-theme]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.mapTheme === this.state.mapTheme);
    });

    const precipitationType = this.container.querySelector("[data-precipitation-type]");
    if (precipitationType) {
      precipitationType.value = this.state.precipitationType;
    }
    const precipitationIntensity = this.container.querySelector("[data-precipitation-intensity]");
    if (precipitationIntensity) {
      precipitationIntensity.value = String(this.state.precipitationIntensity);
    }
    const fogIntensity = this.container.querySelector("[data-fog-intensity]");
    if (fogIntensity) {
      fogIntensity.value = String(this.state.fogIntensity);
    }
    const gustRadius = this.container.querySelector("[data-gust-radius]");
    if (gustRadius) {
      gustRadius.value = String(this.state.gustRadius);
    }

    const gustToggle = this.container.querySelector("[data-action='toggle-gust-apply']");
    if (gustToggle) {
      gustToggle.classList.toggle("is-active", this.state.gustApplyMode);
      gustToggle.textContent = this.state.gustApplyMode ? this.t("applyOn") : this.t("applyOff");
    }

    const weatherVisualizationToggle = this.container.querySelector("[data-action='toggle-weather-visualization']");
    if (weatherVisualizationToggle) {
      weatherVisualizationToggle.classList.toggle("is-active", this.state.weatherVisualizationEnabled);
      weatherVisualizationToggle.textContent = this.state.weatherVisualizationEnabled ? this.t("visualizationOn") : this.t("visualizationOff");
    }

    const weatherDockToggle = this.container.querySelector("[data-action='toggle-weather-dock']");
    if (weatherDockToggle) {
      weatherDockToggle.classList.toggle("is-active", this.state.weatherDockOpen);
      weatherDockToggle.setAttribute("aria-pressed", this.state.weatherDockOpen ? "true" : "false");
    }
    this.container.querySelector("[data-weather-dock-meta]")
      ?.replaceChildren(document.createTextNode(this.weatherDockMeta()));
    const weatherDockPanel = this.container.querySelector("#weather-dock-panel");
    if (weatherDockPanel) {
      weatherDockPanel.hidden = !this.state.weatherDockOpen;
      weatherDockPanel.classList.toggle("is-open", this.state.weatherDockOpen);
    }

    this.container.querySelectorAll(".scenario-status-row strong").forEach((element) => {
      if (element.previousElementSibling?.textContent === this.t("autoSend")) {
        element.textContent = this.statusLabel();
      }
    });

    this.updateCommercialTrafficControl();
    this.updateUamVehicleDetailPanel();
    this.syncMissionPlanningUi();
    this.syncOperationalEnvironmentUi();
    this.syncAbnormalDashboardUi();
    this.updateRangeLabels();
  }

  syncMissionPlanningUi() {
    const demoLocked = this.isDemoScenarioLocked();
    this.container.querySelectorAll("[data-demo-scenario]").forEach((button) => {
      button.classList.toggle("is-active", (this.state.demoScenarioId || "") === (button.dataset.demoScenario || ""));
    });
    const missionAddButton = this.container.querySelector("[data-mission-action='add']");
    if (missionAddButton) {
      missionAddButton.disabled = demoLocked;
    }
    const demoLockNotice = this.container.querySelector("[data-demo-lock-notice]");
    if (demoLockNotice) {
      demoLockNotice.hidden = !demoLocked;
      demoLockNotice.textContent = demoLocked ? this.demoScenarioLockNoticeText() : "";
    }
    const missionList = this.container.querySelector("[data-mission-list]");
    if (missionList) {
      missionList.innerHTML = this.renderMissionCards();
    }
    this.container.querySelector("[data-mission-active-label]")
      ?.replaceChildren(document.createTextNode(this.activeMissionEntry()?.aircraftName || "-"));
    const missionStatus = this.container.querySelector("[data-mission-status]");
    if (missionStatus) {
      missionStatus.dataset.missionStatusLevel = this.missionStatusLevel();
      missionStatus.textContent = this.missionStatusText();
    }
    const missionRouteInfo = this.container.querySelector("[data-mission-route-info]");
    if (missionRouteInfo) {
      missionRouteInfo.innerHTML = this.renderMissionRouteInfo();
    }
    this.container.querySelector("[data-mission-bottom-hint]")
      ?.replaceChildren(document.createTextNode(
        this.state.operationMode === "single"
          ? (this.activeMissionEntry() ? this.t("missionResetRoute") : this.t("missionNoAircraft"))
          : (this.state.trafficDensity === "customed" ? this.trafficCustomMissionText() : this.t("modeHint")),
      ));
  }

  syncOperationalEnvironmentUi() {
    this.container.querySelectorAll("[data-env-tool]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.envTool === this.state.environmentTool);
    });
    const status = this.container.querySelector("[data-env-status]");
    if (status) {
      status.dataset.envStatusLevel = this.state.environmentStatusLevel;
      status.textContent = this.environmentStatusText();
    }
    this.container.querySelector("[data-env-summary]")?.replaceChildren(document.createTextNode(this.environmentSummaryText()));
    const vertiportList = this.container.querySelector("[data-env-list='vertiport']");
    if (vertiportList) {
      vertiportList.innerHTML = this.renderEnvironmentList("vertiport");
    }
    const corridorList = this.container.querySelector("[data-env-list='corridor']");
    if (corridorList) {
      corridorList.innerHTML = this.renderEnvironmentList("corridor");
    }
  }

  syncAbnormalDashboardUi() {
    const toggle = this.container.querySelector("[data-action='toggle-abnormal-dashboard']");
    if (toggle) {
      toggle.classList.toggle("is-active", this.state.abnormalDashboardOpen);
      toggle.setAttribute("aria-pressed", this.state.abnormalDashboardOpen ? "true" : "false");
    }
    const panel = this.container.querySelector("#abnormal-dashboard-panel");
    if (panel) {
      panel.hidden = !this.state.abnormalDashboardOpen;
      panel.classList.toggle("is-open", this.state.abnormalDashboardOpen);
    }
    const pickButton = this.container.querySelector("[data-action='toggle-abnormal-pick']");
    if (pickButton) {
      pickButton.classList.toggle("is-active", this.state.abnormalPickMode);
      pickButton.textContent = this.state.abnormalPickMode ? this.t("abnormalPicking") : this.t("abnormalPickArea");
    }
    const radiusInput = this.container.querySelector("[data-abnormal-radius]");
    if (radiusInput) {
      radiusInput.value = String(this.state.abnormalRadiusM);
    }
    this.container.querySelector("[data-abnormal-radius-value]")
      ?.replaceChildren(document.createTextNode(`${(Number(this.state.abnormalRadiusM || 0) / 1000).toFixed(2)} km`));
    const centerText = Number.isFinite(Number(this.state.abnormalLat)) && Number.isFinite(Number(this.state.abnormalLon))
      ? `${Number(this.state.abnormalLat).toFixed(5)}, ${Number(this.state.abnormalLon).toFixed(5)}`
      : this.t("abnormalNoCenter");
    this.container.querySelector("[data-abnormal-center]")?.replaceChildren(document.createTextNode(centerText));
    this.container.querySelector("[data-abnormal-count]")?.replaceChildren(document.createTextNode(String(Number(this.state.abnormalCount || 0))));
    this.container.querySelector("[data-abnormal-speed]")
      ?.replaceChildren(document.createTextNode(`${Number(this.state.abnormalSpeedMps || 0).toFixed(1)} m/s`));
    const status = this.container.querySelector("[data-abnormal-status]");
    if (status) {
      status.dataset.statusLevel = this.state.abnormalStatusLevel || "info";
      status.textContent = this.state.abnormalStatus || "";
    }
  }

  updateCommercialTrafficControl() {
    const button = this.container.querySelector("[data-action='toggle-commercial-traffic']");
    if (button) {
      button.classList.toggle("is-active", this.state.commercialTrafficEnabled);
      button.classList.toggle("is-loading", this.state.commercialTrafficLoading);
      button.setAttribute("aria-pressed", this.state.commercialTrafficEnabled ? "true" : "false");
    }
    this.container.querySelector("[data-commercial-traffic-meta]")?.replaceChildren(document.createTextNode(this.commercialTrafficMeta()));

    const statusBoard = this.container.querySelector("#sim-status-board span");
    if (!statusBoard) {
      return;
    }
    if (this.uamVehicles.length > 0) {
      const latest = this.uamVehicles
        .slice()
        .sort((a, b) => new Date(b.receivedAt || b.messageTimestamp || 0).getTime() - new Date(a.receivedAt || a.messageTimestamp || 0).getTime())[0];
      const collisionCount = this.uamVehicles.filter((vehicle) => this.hasUamCollision(vehicle)).length;
      const collisionText = collisionCount > 0 ? ` / ${this.t("collisionStatus")} ${collisionCount}` : "";
      statusBoard.textContent = `${this.t("uamVehicles")} ${this.uamVehicles.length}${collisionText} / ${this.t("lastUpdate")} ${this.formatUamTime(latest?.receivedAt || latest?.messageTimestamp)}`;
      return;
    }
    if (this.vehicleStatusListening) {
      statusBoard.textContent = this.t("vehicleStatusWaiting");
      return;
    }
    if (!this.state.commercialTrafficEnabled) {
      statusBoard.textContent = this.t("noTrafficData");
      return;
    }
    statusBoard.textContent = `${this.t("commercialAircraft")} ${this.commercialTrafficMeta()}`;
  }

  setEnvironmentStatus(message, level = "info") {
    this.state.environmentStatus = message || "";
    this.state.environmentStatusLevel = level;
    this.syncOperationalEnvironmentUi();
  }

  normalizeOperationalEnvironmentData(data) {
    return {
      files: data?.files || {},
      vertiports: Array.isArray(data?.vertiports) ? data.vertiports : [],
      corridors: Array.isArray(data?.corridors) ? data.corridors : [],
      basestations: Array.isArray(data?.basestations) ? data.basestations : [],
      links: Array.isArray(data?.links) ? data.links : [],
    };
  }

  async loadOperationalEnvironment(options = {}) {
    if (this.environmentLoadPromise && !options.force) {
      return this.environmentLoadPromise;
    }
    if (this.environmentDataLoaded && !options.force) {
      this.updateOperationalEnvironmentLayers();
      this.syncOperationalEnvironmentUi();
      return this.operationalEnvironment;
    }
    this.state.environmentLoading = true;
    this.syncOperationalEnvironmentUi();
    const task = (async () => {
      const data = await getJSON(OPERATIONAL_ENVIRONMENT_URL);
      if (this.destroyed) {
        return this.operationalEnvironment;
      }
      this.operationalEnvironment = this.normalizeOperationalEnvironmentData(data);
      this.environmentDataLoaded = true;
      this.state.environmentLoading = false;
      this.setEnvironmentStatus(this.t("environmentReady"), "success");
      this.updateOperationalEnvironmentLayers();
      return this.operationalEnvironment;
    })();
    this.environmentLoadPromise = task;
    try {
      return await task;
    } catch (error) {
      if (this.destroyed) {
        return this.operationalEnvironment;
      }
      this.state.environmentLoading = false;
      this.setEnvironmentStatus(`${this.t("environmentLoadError")}: ${error.message}`, "error");
      return this.operationalEnvironment;
    } finally {
      if (this.environmentLoadPromise === task) {
        this.environmentLoadPromise = null;
      }
    }
  }

  async resetOperationalEnvironment() {
    this.state.environmentLoading = true;
    this.syncOperationalEnvironmentUi();
    try {
      const data = await postJSON(`${OPERATIONAL_ENVIRONMENT_URL}/reset`, {});
      if (this.destroyed) {
        return;
      }
      this.operationalEnvironment = this.normalizeOperationalEnvironmentData(data);
      this.environmentDataLoaded = true;
      this.environmentSelection = null;
      this.environmentMoveTarget = null;
      this.environmentLinkSource = null;
      this.state.environmentLoading = false;
      this.setEnvironmentStatus(this.t("environmentReady"), "success");
      this.updateOperationalEnvironmentLayers();
    } catch (error) {
      if (this.destroyed) {
        return;
      }
      this.state.environmentLoading = false;
      this.setEnvironmentStatus(error.message, "error");
    }
  }

  async updateOperationalEnvironment(kind, payload, successText = this.t("environmentSaved")) {
    const normalizedKind = kind === "route" ? "corridor" : kind;
    const url = normalizedKind === "vertiport"
      ? `${OPERATIONAL_ENVIRONMENT_URL}/vertiports`
      : `${OPERATIONAL_ENVIRONMENT_URL}/corridors`;
    this.state.environmentLoading = true;
    this.syncOperationalEnvironmentUi();
    try {
      const data = await postJSON(url, payload);
      if (this.destroyed) {
        return false;
      }
      this.operationalEnvironment = this.normalizeOperationalEnvironmentData(data);
      this.environmentDataLoaded = true;
      this.state.environmentLoading = false;
      this.setEnvironmentStatus(successText, "success");
      this.updateOperationalEnvironmentLayers();
      return true;
    } catch (error) {
      if (this.destroyed) {
        return false;
      }
      this.state.environmentLoading = false;
      this.setEnvironmentStatus(error.message, "error");
      return false;
    }
  }

  operationalEnvironmentLookups() {
    const vertiports = new Map();
    const corridors = new Map();
    (this.operationalEnvironment?.vertiports || []).forEach((entry) => {
      if (entry?.name) {
        vertiports.set(entry.name, entry);
      }
    });
    (this.operationalEnvironment?.corridors || []).forEach((entry) => {
      if (entry?.name) {
        corridors.set(entry.name, entry);
      }
    });
    return { vertiports, corridors };
  }

  ensureMissionRouteLayers() {
    if (!this.map || !this.map.isStyleLoaded()) {
      return false;
    }
    if (!this.map.getSource(MISSION_ROUTE_SOURCE_ID)) {
      this.map.addSource(MISSION_ROUTE_SOURCE_ID, {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
    }
    if (!this.map.getSource(MISSION_ROUTE_POINT_SOURCE_ID)) {
      this.map.addSource(MISSION_ROUTE_POINT_SOURCE_ID, {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
    }
    if (!this.map.getLayer("mission-route-line-shadow")) {
      this.map.addLayer({
        id: "mission-route-line-shadow",
        type: "line",
        source: MISSION_ROUTE_SOURCE_ID,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "rgba(2, 6, 23, 0.96)",
          "line-width": ["interpolate", ["linear"], ["zoom"], 6, 3, 8, 5, 10, 7.5, 12, 10, 15, 14],
          "line-opacity": 0.82,
        },
      });
    }
    if (!this.map.getLayer("mission-route-line-halo")) {
      this.map.addLayer({
        id: "mission-route-line-halo",
        type: "line",
        source: MISSION_ROUTE_SOURCE_ID,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "rgba(0, 234, 255, 0.62)",
          "line-width": ["interpolate", ["linear"], ["zoom"], 6, 5, 8, 7, 10, 10, 12, 13, 15, 17],
          "line-blur": 1.8,
          "line-opacity": 0.9,
        },
      });
    }
    if (!this.map.getLayer("mission-route-line")) {
      this.map.addLayer({
        id: "mission-route-line",
        type: "line",
        source: MISSION_ROUTE_SOURCE_ID,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "#00f0ff",
          "line-width": ["interpolate", ["linear"], ["zoom"], 6, 2, 8, 2.8, 10, 4, 12, 5.4, 15, 7.2],
          "line-opacity": 1,
        },
      });
    }
    if (!this.map.getLayer("mission-route-points")) {
      this.map.addLayer({
        id: "mission-route-points",
        type: "circle",
        source: MISSION_ROUTE_POINT_SOURCE_ID,
        paint: {
          "circle-radius": ["case", ["==", ["get", "terminal"], true], 10, 7],
          "circle-color": ["case", ["==", ["get", "terminal"], true], "#ffffff", "#00f0ff"],
          "circle-stroke-width": 4,
          "circle-stroke-color": "#0f172a",
          "circle-opacity": 1,
        },
      });
    }
    this.promoteMissionRouteLayers();
    return true;
  }

  promoteMissionRouteLayers() {
    if (!this.map) {
      return;
    }
    for (const layerId of MISSION_ROUTE_LAYER_IDS) {
      if (!this.map.getLayer(layerId)) {
        continue;
      }
      try {
        this.map.moveLayer(layerId);
      } catch (error) {
        // MapLibre throws if a style mutation is already in flight. The next
        // overlay restore/update pass will promote the route layer again.
      }
    }
    // Mission route를 위로 올린 직후에도 UAM 비행체 symbol/label이
    // 항상 최상단에 남도록 한 번 더 승격한다.
    this.raiseUamVehicleLayers();
  }

  clearMissionRouteSvgOverlay() {
    if (this.missionRouteOverlayFrame) {
      window.cancelAnimationFrame(this.missionRouteOverlayFrame);
      this.missionRouteOverlayFrame = 0;
    }
    if (this.map && this.missionRouteOverlayUpdateHandler) {
      ["move", "zoom", "rotate", "pitch", "resize"].forEach((eventName) => {
        this.map.off(eventName, this.missionRouteOverlayUpdateHandler);
      });
    }
    this.missionRouteOverlayUpdateHandler = null;
    this.missionRouteOverlay?.remove();
    this.missionRouteOverlay = null;
  }

  ensureMissionRouteSvgOverlay() {
    if (!MISSION_ROUTE_SVG_OVERLAY_ENABLED) {
      this.clearMissionRouteSvgOverlay();
      return null;
    }
    if (!this.map) {
      return null;
    }
    const container = this.map.getContainer();
    if (!this.missionRouteOverlay || !container.contains(this.missionRouteOverlay)) {
      this.missionRouteOverlay = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      this.missionRouteOverlay.classList.add("mission-route-svg-overlay");
      this.missionRouteOverlay.setAttribute("aria-hidden", "true");
      this.missionRouteOverlay.innerHTML = `
        <defs>
          <mask id="mission-route-uam-cutout" maskUnits="userSpaceOnUse">
            <rect data-mission-route-svg="mask-base" x="0" y="0" width="100%" height="100%" fill="white"></rect>
            <g data-mission-route-svg="uam-cutouts"></g>
          </mask>
        </defs>
        <g data-mission-route-svg="masked-lines" mask="url(#mission-route-uam-cutout)">
          <polyline class="mission-route-svg-line mission-route-svg-line--shadow" data-mission-route-svg="shadow"></polyline>
          <polyline class="mission-route-svg-line mission-route-svg-line--halo" data-mission-route-svg="halo"></polyline>
          <polyline class="mission-route-svg-line mission-route-svg-line--main" data-mission-route-svg="main"></polyline>
        </g>
        <g data-mission-route-svg="points"></g>
      `;
      container.append(this.missionRouteOverlay);
    }
    if (!this.missionRouteOverlayUpdateHandler) {
      this.missionRouteOverlayUpdateHandler = () => this.scheduleMissionRouteSvgOverlayUpdate();
      ["move", "zoom", "rotate", "pitch", "resize"].forEach((eventName) => {
        this.map.on(eventName, this.missionRouteOverlayUpdateHandler);
      });
    }
    return this.missionRouteOverlay;
  }

  scheduleMissionRouteSvgOverlayUpdate() {
    if (this.missionRouteOverlayFrame) {
      return;
    }
    this.missionRouteOverlayFrame = window.requestAnimationFrame(() => {
      this.missionRouteOverlayFrame = 0;
      this.updateMissionRouteSvgOverlay();
    });
  }

  updateMissionRouteSvgOverlay() {
    if (!MISSION_ROUTE_SVG_OVERLAY_ENABLED) {
      this.clearMissionRouteSvgOverlay();
      return;
    }
    if (!this.map) {
      return;
    }
    const routeData = this.missionRouteDisplayRouteData();
    const overlay = this.ensureMissionRouteSvgOverlay();
    if (!overlay) {
      return;
    }
    const width = this.map.getCanvas().clientWidth || this.map.getContainer().clientWidth || 0;
    const height = this.map.getCanvas().clientHeight || this.map.getContainer().clientHeight || 0;
    overlay.setAttribute("viewBox", `0 0 ${width} ${height}`);
    overlay.setAttribute("width", String(width));
    overlay.setAttribute("height", String(height));
    const maskBase = overlay.querySelector("[data-mission-route-svg='mask-base']");
    if (maskBase) {
      maskBase.setAttribute("width", String(width));
      maskBase.setAttribute("height", String(height));
    }
    const zoom = normalizeNumber(typeof this.map.getZoom === "function" ? this.map.getZoom() : INITIAL_ZOOM, 6, 16, INITIAL_ZOOM);
    const zoomScale = normalizeNumber((zoom - 9) / 6, 0, 1, 0.35);
    const mainWidth = 1.6 + zoomScale * 3.8;
    const haloWidth = mainWidth + 2.2 + zoomScale * 3.2;
    const shadowWidth = mainWidth + 1.8 + zoomScale * 2.2;
    const waypointRadius = 2.2 + zoomScale * 1.8;
    const terminalRadius = waypointRadius + 1.2;
    const pointStrokeWidth = 1.2 + zoomScale * 1.2;
    overlay.style.setProperty("--mission-route-main-width", `${mainWidth.toFixed(1)}px`);
    overlay.style.setProperty("--mission-route-halo-width", `${haloWidth.toFixed(1)}px`);
    overlay.style.setProperty("--mission-route-shadow-width", `${shadowWidth.toFixed(1)}px`);
    overlay.style.setProperty("--mission-route-point-stroke-width", `${pointStrokeWidth.toFixed(1)}px`);

    const routeLinePoints = this.missionRouteLinePoints(routeData);
    const projectedPoints = routeLinePoints
      .map((coordinates, index) => {
        const projected = this.map.project(coordinates);
        return Number.isFinite(projected.x) && Number.isFinite(projected.y)
          ? { x: projected.x, y: projected.y, index }
          : null;
      })
      .filter(Boolean);
    const routeMarkers = this.missionRouteMarkerPoints(routeData);
    const projectedMarkers = routeMarkers
      .map((point, index) => {
        const projected = this.map.project(point.coordinates);
        return Number.isFinite(projected.x) && Number.isFinite(projected.y)
          ? { x: projected.x, y: projected.y, index, terminal: index === 0 || index === routeMarkers.length - 1 }
          : null;
      })
      .filter(Boolean);

    const pointString = projectedPoints.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
    overlay.classList.toggle("is-visible", projectedPoints.length > 1);
    overlay.querySelectorAll("[data-mission-route-svg='shadow'], [data-mission-route-svg='halo'], [data-mission-route-svg='main']").forEach((line) => {
      line.setAttribute("points", pointString);
    });
    const pointGroup = overlay.querySelector("[data-mission-route-svg='points']");
    if (pointGroup) {
      pointGroup.innerHTML = projectedMarkers
        .map((point) => `<circle class="${point.terminal ? "is-terminal" : ""}" cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="${(point.terminal ? terminalRadius : waypointRadius).toFixed(1)}"></circle>`)
        .join("");
    }
    const cutoutGroup = overlay.querySelector("[data-mission-route-svg='uam-cutouts']");
    if (cutoutGroup) {
      cutoutGroup.innerHTML = this.missionRouteUamCutouts()
        .map((point) => `<circle cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="${point.radius.toFixed(1)}" fill="black"></circle>`)
        .join("");
    }
  }

  missionRouteUamCutouts() {
    if (!this.map || !Array.isArray(this.uamVehicles) || this.uamVehicles.length < 1) {
      return [];
    }
    const seen = new Set();
    return this.uamVehicles
      .map((vehicle) => {
        const id = this.uamVehicleId(vehicle);
        if (!id || seen.has(id)) {
          return null;
        }
        seen.add(id);
        const lngLat = this.uamVehicleMarkerPositions.get(id) || this.uamVehicleLngLat(vehicle);
        if (!lngLat) {
          return null;
        }
        const projected = this.map.project(lngLat);
        return Number.isFinite(projected.x) && Number.isFinite(projected.y)
          ? { x: projected.x, y: projected.y, radius: 34 }
          : null;
      })
      .filter(Boolean);
  }

  routePointLngLat(point) {
    if (typeof point === "string") {
      return this.routeNameLngLat(point);
    }
    if (Array.isArray(point)) {
      const lon = this.firstFiniteNumber(point[0]);
      const lat = this.firstFiniteNumber(point[1]);
      return lon === null || lat === null ? null : [lon, lat];
    }
    const lon = this.firstFiniteNumber(point?.lon, point?.lng, point?.longitude, point?.x);
    const lat = this.firstFiniteNumber(point?.lat, point?.latitude, point?.y);
    return lon === null || lat === null ? null : [lon, lat];
  }

  routeNameLngLat(name) {
    const value = String(name || "").trim();
    if (!value) {
      return null;
    }
    const entry = this.environmentEntry("vertiport", value) || this.environmentEntry("corridor", value);
    if (!entry || !isFiniteNumber(entry.lon) || !isFiniteNumber(entry.lat)) {
      return null;
    }
    return [Number(entry.lon), Number(entry.lat)];
  }

  routePointName(point, fallback = "") {
    return typeof point === "string"
      ? point
      : String(point?.name || point?.id || point?.label || fallback || "");
  }

  missionRouteLinePoints(routeData) {
    if (!routeData) {
      return [];
    }
    for (const key of ["points", "geometry", "routePoints", "route_points", "missionWaypoints", "mission_waypoints", "waypoints", "path"]) {
      const values = routeData[key];
      if (!Array.isArray(values) || values.length < 2) {
        continue;
      }
      const coordinates = values
        .map((point) => this.routePointLngLat(point))
        .filter(Boolean);
      if (coordinates.length > 1) {
        return coordinates;
      }
    }
    const enRoutePoints = this.missionRouteEnRoutePoints(routeData);
    if (enRoutePoints.length > 1) {
      return enRoutePoints;
    }
    return [];
  }

  missionRouteMarkerPoints(routeData) {
    if (!routeData) {
      return [];
    }
    for (const key of ["path", "waypoints", "missionWaypoints", "mission_waypoints", "routePoints", "route_points", "geometry", "points"]) {
      const values = routeData[key];
      if (!Array.isArray(values) || values.length < 1) {
        continue;
      }
      const markers = values
        .map((point, index) => {
          const coordinates = this.routePointLngLat(point);
          return coordinates
            ? { coordinates, name: this.routePointName(point, `WP ${index + 1}`) }
            : null;
        })
        .filter(Boolean);
      if (markers.length > 0) {
        return markers;
      }
    }
    const enRoutePoints = this.missionRouteEnRoutePoints(routeData);
    if (enRoutePoints.length > 0) {
      return enRoutePoints.map((coordinates, index) => ({
        coordinates,
        name: index === 0 ? "START" : `WP ${index}`,
      }));
    }
    return [];
  }

  missionRouteEnRoutePoints(routeData) {
    const segments = Array.isArray(routeData?.enRoute)
      ? routeData.enRoute
      : (Array.isArray(routeData?.en_route) ? routeData.en_route : []);
    const coordinates = [];
    segments.forEach((segment) => {
      if (!segment || typeof segment !== "object") {
        return;
      }
      ["startLLA", "start_lla", "start", "endLLA", "end_lla", "end"].forEach((key) => {
        const point = this.routePointLngLat(segment[key]);
        if (!point) {
          return;
        }
        const previous = coordinates[coordinates.length - 1];
        if (previous && Math.abs(previous[0] - point[0]) < 1e-9 && Math.abs(previous[1] - point[1]) < 1e-9) {
          return;
        }
        coordinates.push(point);
      });
    });
    return coordinates;
  }

  shouldDisplayMissionRoute() {
    return Boolean(this.missionRouteDisplayRouteData());
  }

  missionRouteDisplayEntry() {
    if (this.state.operationMode !== "single") {
      return null;
    }
    if (this.selectedUamVehicleId) {
      return this.missionEntryForUamVehicleId(this.selectedUamVehicleId);
    }
    if (this.state.panelOpen && this.state.activePanel === "mission") {
      return this.activeMissionEntry();
    }
    return null;
  }

  missionRouteDisplayRouteData() {
    const entry = this.missionRouteDisplayEntry();
    if (entry?.routeData) {
      return entry.routeData;
    }
    if (this.selectedUamVehicleId) {
      return this.liveUamVehicleRouteData(this.selectedUamVehicleId);
    }
    return null;
  }

  liveUamVehicleRouteData(vehicleId) {
    const selected = this.uamVehicles.find((vehicle) => this.uamVehicleId(vehicle) === vehicleId);
    if (!selected) {
      return null;
    }
    const current = this.uamVehicleMarkerPositions.get(vehicleId) || this.uamVehicleLngLat(selected);
    const target = this.routePointLngLat(
      selected.navigation?.targetLLA
      || selected.navigation?.target_lla
      || selected.targetLLA
      || selected.target_lla,
    );
    if (!current || !target) {
      return null;
    }
    return {
      path: [selected.currentWaypointId || vehicleId, selected.navigation?.nextWaypointId || "TARGET"],
      points: [
        { lon: current[0], lat: current[1] },
        { lon: target[0], lat: target[1] },
      ],
    };
  }

  updateMissionRouteOverlay() {
    if (!this.map) {
      return;
    }
    const routeData = this.missionRouteDisplayRouteData();
    this.updateMissionRouteSvgOverlay();
    if (!this.ensureMissionRouteLayers()) {
      return;
    }
    const routeLinePoints = this.missionRouteLinePoints(routeData);
    const lineFeatures = routeLinePoints.length > 1
      ? [{
        type: "Feature",
        properties: {},
        geometry: {
          type: "LineString",
          coordinates: routeLinePoints,
        },
      }]
      : [];
    const routeMarkers = this.missionRouteMarkerPoints(routeData);
    const pointFeatures = routeMarkers.length
      ? routeMarkers.map((point, index) => ({
        type: "Feature",
        properties: {
          name: point.name,
          terminal: index === 0 || index === routeMarkers.length - 1,
        },
        geometry: {
          type: "Point",
          coordinates: point.coordinates,
        },
      }))
      : [];
    this.map.getSource(MISSION_ROUTE_SOURCE_ID)?.setData({ type: "FeatureCollection", features: lineFeatures });
    this.map.getSource(MISSION_ROUTE_POINT_SOURCE_ID)?.setData({ type: "FeatureCollection", features: pointFeatures });
    this.promoteMissionRouteLayers();
    this.updateMissionRouteSvgOverlay();
  }

  isOperationalEnvironmentDataRendered() {
    if (!this.map) {
      return false;
    }
    const sourceFeatureCount = (sourceId) => {
      const features = this.map.getSource(sourceId)?._data?.features;
      return Array.isArray(features) ? features.length : null;
    };
    const { vertiports, corridors } = this.operationalEnvironmentLookups();
    const hasCoordinates = (entry) => isFiniteNumber(entry?.lon) && isFiniteNumber(entry?.lat);
    const expectedVertiports = Array.from(vertiports.values()).filter(hasCoordinates).length;
    const expectedCorridors = Array.from(corridors.values()).filter(hasCoordinates).length;
    const expectedLinks = (this.operationalEnvironment?.links || []).filter((link) => {
      const from = link.kind === "vertiport" ? vertiports.get(link.from) : corridors.get(link.from);
      const to = corridors.get(link.to);
      return hasCoordinates(from) && hasCoordinates(to);
    }).length;
    const renderedCounts = [
      [ENV_VERTIPORT_SOURCE_ID, expectedVertiports],
      [ENV_CORRIDOR_SOURCE_ID, expectedCorridors],
      [ENV_LINK_SOURCE_ID, expectedLinks],
    ];
    return renderedCounts.every(([sourceId, expectedCount]) => {
      const actualCount = sourceFeatureCount(sourceId);
      return actualCount === null || actualCount === expectedCount;
    });
  }

  environmentEntry(kind, name) {
    const normalizedKind = kind === "route" ? "corridor" : kind;
    const { vertiports, corridors } = this.operationalEnvironmentLookups();
    return normalizedKind === "vertiport" ? vertiports.get(name) : corridors.get(name);
  }

  environmentCoordinates(kind, name) {
    const entry = this.environmentEntry(kind, name);
    if (!entry || !isFiniteNumber(entry.lon) || !isFiniteNumber(entry.lat)) {
      return null;
    }
    return [Number(entry.lon), Number(entry.lat)];
  }

  selectEnvironmentFeature(kind, name, options = {}) {
    const normalizedKind = kind === "route" ? "corridor" : kind;
    const entry = this.environmentEntry(normalizedKind, name);
    if (!entry) {
      return;
    }
    this.environmentSelection = { kind: normalizedKind, name };
    this.updateOperationalEnvironmentLayers();
    this.syncOperationalEnvironmentUi();
    const coordinates = this.environmentCoordinates(normalizedKind, name);
    if (options.flyTo && this.map && coordinates) {
      this.map.easeTo({ center: coordinates, zoom: Math.max(12.5, this.map.getZoom()), duration: 360 });
    }
  }

  odtCorridorColor() {
    return this.state.mapTheme === "dark" ? ODT_CORRIDOR_DARK : ODT_CORRIDOR_LIGHT;
  }

  clearEnvironmentVertiportMarkers() {
    this.environmentVertiportMarkers.forEach((marker) => marker.remove());
    this.environmentVertiportMarkers.clear();
    this.map?.getContainer?.()?.querySelectorAll(".environment-vertiport-marker").forEach((element) => {
      element.closest(".maplibregl-marker")?.remove();
    });
  }

  syncMissionVertiportMarkerStates() {
    const activeMission = this.activeMissionEntry();
    this.environmentVertiportMarkers.forEach((marker, name) => {
      const element = marker.getElement?.();
      if (!element) {
        return;
      }
      element.classList.toggle("is-departure", activeMission?.departureName === name);
      element.classList.toggle("is-arrival", activeMission?.arrivalName === name);
    });
  }

  renderEnvironmentVertiportMarkers() {
    if (!this.map || !window.maplibregl) {
      return;
    }
    this.clearEnvironmentVertiportMarkers();
    const selected = this.environmentSelection;
    const activeMission = this.activeMissionEntry();
    (this.operationalEnvironment?.vertiports || []).forEach((entry) => {
      if (!entry?.name || !isFiniteNumber(entry.lon) || !isFiniteNumber(entry.lat)) {
        return;
      }
      const element = document.createElement("button");
      element.type = "button";
      element.className = "environment-vertiport-marker";
      if (selected?.kind === "vertiport" && selected.name === entry.name) {
        element.classList.add("is-selected");
      }
      if (activeMission?.departureName === entry.name) {
        element.classList.add("is-departure");
      }
      if (activeMission?.arrivalName === entry.name) {
        element.classList.add("is-arrival");
      }
      const pin = document.createElement("span");
      pin.className = "environment-vertiport-pin";
      pin.textContent = "V";
      const label = document.createElement("span");
      label.className = "environment-vertiport-name-label";
      label.textContent = entry.name;
      element.append(pin, label);
      element.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (this.handleMissionVertiportSelection(entry.name)) {
          return;
        }
        const point = { type: "point", kind: "vertiport", name: entry.name };
        if (this.environmentLinkSource || this.state.environmentTool === "link") {
          this.handleEnvironmentLinkPoint(point);
          return;
        }
        this.showExistingEnvironmentPopup("vertiport", entry.name, { lng: Number(entry.lon), lat: Number(entry.lat) });
      });
      const marker = new window.maplibregl.Marker({ element })
        .setLngLat([Number(entry.lon), Number(entry.lat)])
        .addTo(this.map);
      this.environmentVertiportMarkers.set(entry.name, marker);
    });
  }

  ensureOperationalEnvironmentLayers() {
    if (!this.map || !this.map.isStyleLoaded()) {
      return false;
    }
    if (!this.map.getSource(ENV_LINK_SOURCE_ID)) {
      this.map.addSource(ENV_LINK_SOURCE_ID, {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
    }
    if (!this.map.getSource(ENV_CORRIDOR_SOURCE_ID)) {
      this.map.addSource(ENV_CORRIDOR_SOURCE_ID, {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
    }
    if (!this.map.getSource(ENV_VERTIPORT_SOURCE_ID)) {
      this.map.addSource(ENV_VERTIPORT_SOURCE_ID, {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
    }

    ["operational-vertiport-points", "operational-vertiport-labels"].forEach((layerId) => {
      if (this.map.getLayer(layerId)) {
        this.map.removeLayer(layerId);
      }
    });

    if (!this.map.getLayer("operational-corridor-links")) {
      this.map.addLayer({
        id: "operational-corridor-links",
        type: "line",
        source: ENV_LINK_SOURCE_ID,
        filter: ["all", ["==", ["get", "linkKind"], "corridor"], ["==", ["get", "spare"], false]],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": ["case", ["==", ["get", "selected"], true], ODT_HOVER_OUTLINE, this.odtCorridorColor()],
          "line-width": ["case", ["==", ["get", "selected"], true], 2.2, 1.55],
          "line-dasharray": [3.5, 3.5],
          "line-opacity": 0.5,
          "line-opacity-transition": { duration: 300 },
        },
      });
    }
    if (!this.map.getLayer("operational-corridor-spare-links")) {
      this.map.addLayer({
        id: "operational-corridor-spare-links",
        type: "line",
        source: ENV_LINK_SOURCE_ID,
        filter: ["all", ["==", ["get", "linkKind"], "corridor"], ["==", ["get", "spare"], true]],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": this.odtCorridorColor(),
          "line-width": 1.55,
          "line-dasharray": [3.5, 3.5],
          "line-opacity": 0.5,
          "line-opacity-transition": { duration: 300 },
        },
      });
    }
    if (!this.map.getLayer("operational-vertiport-links")) {
      this.map.addLayer({
        id: "operational-vertiport-links",
        type: "line",
        source: ENV_LINK_SOURCE_ID,
        filter: ["==", ["get", "linkKind"], "vertiport"],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": ["case", ["==", ["get", "selected"], true], ODT_HOVER_OUTLINE, ODT_VERTIPORT_LINK],
          "line-width": ["case", ["==", ["get", "selected"], true], 2.2, 1.55],
          "line-dasharray": [3.5, 3.5],
          "line-opacity": 0.5,
          "line-opacity-transition": { duration: 300 },
        },
      });
    }
    if (!this.map.getLayer("operational-corridor-points")) {
      this.map.addLayer({
        id: "operational-corridor-points",
        type: "circle",
        source: ENV_CORRIDOR_SOURCE_ID,
        paint: {
          "circle-radius": ["case", ["==", ["get", "selected"], true], 6, 4.5],
          "circle-color": ["case", ["==", ["get", "selected"], true], ODT_HOVER_OUTLINE, this.odtCorridorColor()],
          "circle-stroke-width": 1.5,
          "circle-stroke-color": this.state.mapTheme === "dark" ? ODT_CORRIDOR_STROKE_DARK : "#ffffff",
          "circle-opacity": 0.78,
        },
      });
    }
    if (!this.map.getLayer("operational-corridor-labels")) {
      this.map.addLayer({
        id: "operational-corridor-labels",
        type: "symbol",
        source: ENV_CORRIDOR_SOURCE_ID,
        minzoom: 11,
        layout: {
          "text-field": ["get", "name"],
          "text-font": ["Open Sans Regular", "Arial Unicode MS Regular"],
          "text-size": 11,
          "text-offset": [0, 1.1],
          "text-anchor": "top",
          "text-allow-overlap": false,
        },
        paint: {
          "text-color": ODT_WAYPOINT_LABEL,
          "text-halo-color": "rgba(8, 12, 16, 0.85)",
          "text-halo-width": 2.4,
        },
      });
    }
    this.bindOperationalEnvironmentMapEvents();
    return true;
  }

  updateOperationalEnvironmentLayers() {
    if (!this.map || !this.ensureOperationalEnvironmentLayers()) {
      return;
    }
    const selected = this.environmentSelection;
    const selectedKey = selected ? `${selected.kind}:${selected.name}` : "";
    const { vertiports, corridors } = this.operationalEnvironmentLookups();
    const corridorFeatures = Array.from(corridors.values())
      .filter((entry) => isFiniteNumber(entry.lon) && isFiniteNumber(entry.lat))
      .map((entry) => ({
        type: "Feature",
        id: `corridor:${entry.name}`,
        properties: {
          kind: "corridor",
          name: entry.name,
          altitude_ft: Number(entry.altitude_ft || 0),
          selected: selectedKey === `corridor:${entry.name}`,
        },
        geometry: { type: "Point", coordinates: [Number(entry.lon), Number(entry.lat)] },
      }));
    const vertiportFeatures = Array.from(vertiports.values())
      .filter((entry) => isFiniteNumber(entry.lon) && isFiniteNumber(entry.lat))
      .map((entry) => ({
        type: "Feature",
        id: `vertiport:${entry.name}`,
        properties: {
          kind: "vertiport",
          name: entry.name,
          class: entry.class || "port",
          selected: selectedKey === `vertiport:${entry.name}`,
        },
        geometry: { type: "Point", coordinates: [Number(entry.lon), Number(entry.lat)] },
      }));

    const linkFeatures = (this.operationalEnvironment?.links || [])
      .map((link, index) => {
        const from = link.kind === "vertiport" ? vertiports.get(link.from) : corridors.get(link.from);
        const to = corridors.get(link.to);
        if (!from || !to || !isFiniteNumber(from.lon) || !isFiniteNumber(from.lat) || !isFiniteNumber(to.lon) || !isFiniteNumber(to.lat)) {
          return null;
        }
        const key = `${link.kind}:${link.from}:${link.to}:${Boolean(link.spare)}`;
        const selectedLink = selected?.kind === "link" && selected?.name === key;
        return {
          type: "Feature",
          id: `link:${index}`,
          properties: {
            kind: "link",
            linkKind: link.kind,
            from: link.from,
            to: link.to,
            spare: Boolean(link.spare),
            selected: selectedLink,
          },
          geometry: {
            type: "LineString",
            coordinates: [
              [Number(from.lon), Number(from.lat)],
              [Number(to.lon), Number(to.lat)],
            ],
          },
        };
      })
      .filter(Boolean);

    this.map.getSource(ENV_CORRIDOR_SOURCE_ID)?.setData({ type: "FeatureCollection", features: corridorFeatures });
    this.map.getSource(ENV_VERTIPORT_SOURCE_ID)?.setData({ type: "FeatureCollection", features: vertiportFeatures });
    this.map.getSource(ENV_LINK_SOURCE_ID)?.setData({ type: "FeatureCollection", features: linkFeatures });
    this.renderEnvironmentVertiportMarkers();
    this.updateMissionRouteOverlay();
  }

  bindOperationalEnvironmentMapEvents() {
    if (!this.map || this.environmentMapEventsBound) {
      return;
    }
    [...ENV_POINT_LAYER_IDS, ...ENV_LINK_LAYER_IDS].forEach((layerId) => {
      if (!this.map.getLayer(layerId)) {
        return;
      }
      this.map.on("mouseenter", layerId, () => {
        this.map.getCanvas().style.cursor = "pointer";
      });
      this.map.on("mouseleave", layerId, () => {
        if (!this.environmentMoveTarget && !this.environmentLinkSource) {
          this.map.getCanvas().style.cursor = "";
        }
      });
    });
    this.environmentMapEventsBound = true;
  }

  pickOperationalEnvironmentFeature(point) {
    if (!this.map || !point) {
      return null;
    }
    const pointLayers = ENV_POINT_LAYER_IDS.filter((layerId) => this.map.getLayer(layerId));
    const pointFeatures = pointLayers.length ? this.map.queryRenderedFeatures(point, { layers: pointLayers }) : [];
    if (pointFeatures.length) {
      const props = pointFeatures[0].properties || {};
      return { type: "point", kind: props.kind, name: props.name };
    }
    const linkLayers = ENV_LINK_LAYER_IDS.filter((layerId) => this.map.getLayer(layerId));
    const linkFeatures = linkLayers.length ? this.map.queryRenderedFeatures(point, { layers: linkLayers }) : [];
    if (linkFeatures.length) {
      const props = linkFeatures[0].properties || {};
      return {
        type: "link",
        kind: "link",
        linkKind: props.linkKind,
        from: props.from,
        to: props.to,
        spare: props.spare === true || props.spare === "true",
      };
    }
    return null;
  }

  handleOperationalEnvironmentMapClick(event) {
    const environmentActive = this.state.panelOpen && this.state.activePanel === "environment";
    if (!environmentActive && !this.environmentMoveTarget && !this.environmentLinkSource) {
      return false;
    }
    if (this.environmentMoveTarget) {
      this.moveOperationalEnvironmentTarget(event.lngLat);
      return true;
    }

    const picked = this.pickOperationalEnvironmentFeature(event.point);
    const tool = this.state.environmentTool;
    if (tool === "vertiport") {
      if (picked?.type === "point" && picked.kind === "vertiport") {
        this.showExistingEnvironmentPopup("vertiport", picked.name, event.lngLat);
      } else {
        this.showCreateEnvironmentPopup("vertiport", event.lngLat);
      }
      return true;
    }
    if (tool === "route") {
      if (picked?.type === "point" && picked.kind === "corridor") {
        this.showExistingEnvironmentPopup("corridor", picked.name, event.lngLat);
      } else {
        this.showCreateEnvironmentPopup("corridor", event.lngLat);
      }
      return true;
    }
    if (tool === "link") {
      if (picked?.type === "point") {
        this.handleEnvironmentLinkPoint(picked);
        return true;
      }
      if (picked?.type === "link") {
        this.showEnvironmentLinkPopup(picked, event.lngLat);
        return true;
      }
      return true;
    }
    if (environmentActive && picked?.type === "point") {
      this.showExistingEnvironmentPopup(picked.kind, picked.name, event.lngLat);
      return true;
    }
    if (environmentActive && picked?.type === "link") {
      this.showEnvironmentLinkPopup(picked, event.lngLat);
      return true;
    }
    return false;
  }

  ensureEnvironmentPopup() {
    if (!this.environmentPopup) {
      this.environmentPopup = new window.maplibregl.Popup({
        closeButton: false,
        closeOnClick: true,
        className: "environment-edit-popup",
        offset: [0, -10],
      });
    }
    return this.environmentPopup;
  }

  closeEnvironmentPopup() {
    this.environmentPopup?.remove();
  }

  buildEnvironmentButton(label, onClick, className = "") {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `environment-popup-btn ${className}`.trim();
    button.textContent = label;
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      onClick();
    });
    return button;
  }

  showCreateEnvironmentPopup(kind, lngLat) {
    if (!this.map || !lngLat) {
      return;
    }
    const normalizedKind = kind === "route" ? "corridor" : kind;
    const card = document.createElement("div");
    card.className = "environment-popup-card";
    const title = document.createElement("strong");
    title.textContent = normalizedKind === "vertiport" ? this.t("environmentToolVertiport") : this.t("environmentToolRoute");
    card.append(title);

    const nameInput = document.createElement("input");
    nameInput.className = "environment-popup-input";
    nameInput.placeholder = "Name";
    card.append(nameInput);

    let classSelect = null;
    let altitudeInput = null;
    if (normalizedKind === "vertiport") {
      classSelect = document.createElement("select");
      classSelect.className = "environment-popup-input";
      classSelect.innerHTML = "<option value=\"port\">port</option><option value=\"hub\">hub</option>";
      card.append(classSelect);
    } else {
      altitudeInput = document.createElement("input");
      altitudeInput.className = "environment-popup-input";
      altitudeInput.type = "number";
      altitudeInput.value = "1000";
      altitudeInput.placeholder = "Altitude(ft)";
      card.append(altitudeInput);
    }

    const actions = document.createElement("div");
    actions.className = "environment-popup-actions";
    actions.append(
      this.buildEnvironmentButton("Cancel", () => this.closeEnvironmentPopup()),
      this.buildEnvironmentButton("Save", async () => {
        const name = nameInput.value.trim();
        if (!name) {
          this.setEnvironmentStatus("Name is required.", "error");
          return;
        }
        const entry = {
          name,
          lat: Number(lngLat.lat.toFixed(6)),
          lon: Number(lngLat.lng.toFixed(6)),
        };
        if (normalizedKind === "vertiport") {
          entry.class = classSelect?.value || "port";
        } else {
          entry.altitude_ft = Number(altitudeInput?.value || 1000);
        }
        const ok = await this.updateOperationalEnvironment(normalizedKind, { action: "add", entry });
        if (ok) {
          this.closeEnvironmentPopup();
          this.selectEnvironmentFeature(normalizedKind, name);
        }
      }, "is-primary"),
    );
    card.append(actions);
    this.ensureEnvironmentPopup().setLngLat(lngLat).setDOMContent(card).addTo(this.map);
    nameInput.focus();
  }

  showExistingEnvironmentPopup(kind, name, lngLat) {
    const normalizedKind = kind === "route" ? "corridor" : kind;
    const entry = this.environmentEntry(normalizedKind, name);
    if (!this.map || !entry) {
      return;
    }
    this.selectEnvironmentFeature(normalizedKind, name);
    const coordinates = lngLat || this.environmentCoordinates(normalizedKind, name);
    const card = document.createElement("div");
    card.className = "environment-popup-card";
    const title = document.createElement("strong");
    title.textContent = entry.name;
    card.append(title);
    const meta = document.createElement("span");
    meta.className = "environment-popup-meta";
    meta.textContent = normalizedKind === "vertiport"
      ? `${entry.class || "port"} / ${(entry.links || []).length} link`
      : `${Math.round(Number(entry.altitude_ft || 0))} ft / ${(entry.links || []).length + (entry.spare_links || []).length} link`;
    card.append(meta);

    const actions = document.createElement("div");
    actions.className = "environment-popup-actions environment-popup-actions-wide";
    actions.append(
      this.buildEnvironmentButton("Move", () => {
        this.environmentMoveTarget = { kind: normalizedKind, name };
        this.closeEnvironmentPopup();
        this.setEnvironmentStatus(this.t("environmentMoveTarget"), "info");
        this.map.getCanvas().style.cursor = "crosshair";
      }),
      this.buildEnvironmentButton("Link", () => this.startEnvironmentLink(normalizedKind, name)),
      this.buildEnvironmentButton("Edit", () => this.showEditEnvironmentPopup(normalizedKind, name)),
      this.buildEnvironmentButton("Delete", () => this.deleteEnvironmentFeature(normalizedKind, name), "is-danger"),
    );
    card.append(actions);
    this.ensureEnvironmentPopup().setLngLat(coordinates).setDOMContent(card).addTo(this.map);
  }

  showEditEnvironmentPopup(kind, name) {
    const normalizedKind = kind === "route" ? "corridor" : kind;
    const entry = this.environmentEntry(normalizedKind, name);
    const coordinates = this.environmentCoordinates(normalizedKind, name);
    if (!this.map || !entry || !coordinates) {
      return;
    }
    const card = document.createElement("div");
    card.className = "environment-popup-card";
    const title = document.createElement("strong");
    title.textContent = "Edit";
    card.append(title);
    const nameInput = document.createElement("input");
    nameInput.className = "environment-popup-input";
    nameInput.value = entry.name;
    card.append(nameInput);

    let classSelect = null;
    let altitudeInput = null;
    if (normalizedKind === "vertiport") {
      classSelect = document.createElement("select");
      classSelect.className = "environment-popup-input";
      classSelect.innerHTML = "<option value=\"port\">port</option><option value=\"hub\">hub</option>";
      classSelect.value = entry.class === "hub" ? "hub" : "port";
      card.append(classSelect);
    } else {
      altitudeInput = document.createElement("input");
      altitudeInput.className = "environment-popup-input";
      altitudeInput.type = "number";
      altitudeInput.value = String(Math.round(Number(entry.altitude_ft || 1000)));
      card.append(altitudeInput);
    }

    const actions = document.createElement("div");
    actions.className = "environment-popup-actions";
    actions.append(
      this.buildEnvironmentButton("Cancel", () => this.closeEnvironmentPopup()),
      this.buildEnvironmentButton("Save", async () => {
        const updates = { name: nameInput.value.trim() };
        if (!updates.name) {
          this.setEnvironmentStatus("Name is required.", "error");
          return;
        }
        if (normalizedKind === "vertiport") {
          updates.class = classSelect?.value || "port";
        } else {
          updates.altitude_ft = Number(altitudeInput?.value || 1000);
        }
        const ok = await this.updateOperationalEnvironment(normalizedKind, { action: "update", target: name, updates });
        if (ok) {
          this.closeEnvironmentPopup();
          this.selectEnvironmentFeature(normalizedKind, updates.name);
        }
      }, "is-primary"),
    );
    card.append(actions);
    this.ensureEnvironmentPopup().setLngLat(coordinates).setDOMContent(card).addTo(this.map);
    nameInput.focus();
  }

  async deleteEnvironmentFeature(kind, name) {
    const normalizedKind = kind === "route" ? "corridor" : kind;
    const ok = await this.updateOperationalEnvironment(
      normalizedKind,
      { action: "delete", target: name },
      this.t("environmentDeleted"),
    );
    if (ok) {
      this.environmentSelection = null;
      this.closeEnvironmentPopup();
      this.updateOperationalEnvironmentLayers();
    }
  }

  async moveOperationalEnvironmentTarget(lngLat) {
    if (!this.environmentMoveTarget || !lngLat) {
      return;
    }
    const { kind, name } = this.environmentMoveTarget;
    const updates = {
      lat: Number(lngLat.lat.toFixed(6)),
      lon: Number(lngLat.lng.toFixed(6)),
    };
    const ok = await this.updateOperationalEnvironment(kind, { action: "update", target: name, updates });
    if (ok) {
      this.environmentMoveTarget = null;
      this.map.getCanvas().style.cursor = "";
      this.selectEnvironmentFeature(kind, name);
    }
  }

  startEnvironmentLink(kind, name) {
    const normalizedKind = kind === "route" ? "corridor" : kind;
    if (!this.environmentEntry(normalizedKind, name)) {
      return;
    }
    this.environmentLinkSource = { kind: normalizedKind, name };
    this.state.environmentTool = "link";
    this.closeEnvironmentPopup();
    this.selectEnvironmentFeature(normalizedKind, name);
    this.setEnvironmentStatus(this.t("environmentSelectTarget"), "info");
  }

  handleEnvironmentLinkPoint(picked) {
    if (!picked?.name) {
      return;
    }
    if (!this.environmentLinkSource) {
      this.startEnvironmentLink(picked.kind, picked.name);
      return;
    }
    if (picked.kind !== "corridor") {
      this.setEnvironmentStatus(this.t("environmentSelectTarget"), "error");
      return;
    }
    if (this.environmentLinkSource.kind === "corridor" && this.environmentLinkSource.name === picked.name) {
      this.setEnvironmentStatus("Select a different route node.", "error");
      return;
    }
    this.commitEnvironmentLink(this.environmentLinkSource, picked.name);
  }

  async commitEnvironmentLink(source, targetName) {
    const ok = await this.updateOperationalEnvironment(
      source.kind,
      { action: "update", target: source.name, updates: { link_append: targetName } },
      this.t("environmentLinkSaved"),
    );
    if (ok) {
      this.environmentLinkSource = null;
      this.state.environmentTool = "select";
      this.selectEnvironmentFeature(source.kind, source.name);
    }
  }

  showEnvironmentLinkPopup(link, lngLat) {
    if (!this.map || !link) {
      return;
    }
    const card = document.createElement("div");
    card.className = "environment-popup-card";
    const title = document.createElement("strong");
    title.textContent = "Link";
    card.append(title);
    const meta = document.createElement("span");
    meta.className = "environment-popup-meta";
    meta.textContent = `${link.from} -> ${link.to}${link.spare ? " / spare" : ""}`;
    card.append(meta);
    const actions = document.createElement("div");
    actions.className = "environment-popup-actions";
    actions.append(
      this.buildEnvironmentButton("Delete", () => this.removeEnvironmentLink(link), "is-danger"),
    );
    card.append(actions);
    this.environmentSelection = {
      kind: "link",
      name: `${link.linkKind}:${link.from}:${link.to}:${Boolean(link.spare)}`,
    };
    this.updateOperationalEnvironmentLayers();
    this.syncOperationalEnvironmentUi();
    this.ensureEnvironmentPopup().setLngLat(lngLat).setDOMContent(card).addTo(this.map);
  }

  async removeEnvironmentLink(link) {
    const kind = link.linkKind === "vertiport" ? "vertiport" : "corridor";
    const ok = await this.updateOperationalEnvironment(
      kind,
      { action: "update", target: link.from, updates: { link_remove: link.to } },
      this.t("environmentLinkRemoved"),
    );
    if (ok) {
      this.environmentSelection = null;
      this.closeEnvironmentPopup();
      this.updateOperationalEnvironmentLayers();
    }
  }

  toggleCommercialTraffic() {
    if (this.state.commercialTrafficEnabled) {
      this.stopCommercialTraffic();
      return;
    }
    this.startCommercialTraffic();
  }

  startCommercialTraffic() {
    this.state.commercialTrafficEnabled = true;
    this.state.commercialTrafficError = "";
    this.syncUi();
    window.clearInterval(this.commercialTrafficTimer);
    this.fetchCommercialTraffic();
    this.commercialTrafficTimer = window.setInterval(() => this.fetchCommercialTraffic(), COMMERCIAL_TRAFFIC_REFRESH_MS);
  }

  stopCommercialTraffic() {
    window.clearInterval(this.commercialTrafficTimer);
    this.commercialTrafficTimer = null;
    this.commercialTrafficSeq += 1;
    this.state.commercialTrafficEnabled = false;
    this.state.commercialTrafficLoading = false;
    this.state.commercialTrafficCount = 0;
    this.state.commercialTrafficError = "";
    this.state.commercialTrafficSource = "";
    this.commercialAircraft = [];
    this.clearCommercialAircraftOverlay();
    this.syncUi();
  }

  async fetchCommercialTraffic() {
    if (!this.state.commercialTrafficEnabled || this.destroyed) {
      return;
    }

    const seq = ++this.commercialTrafficSeq;
    this.state.commercialTrafficLoading = this.commercialAircraft.length === 0;
    this.state.commercialTrafficError = "";
    this.updateCommercialTrafficControl();

    try {
      const response = await fetch(COMMERCIAL_TRAFFIC_URL, { headers: { Accept: "application/json" }, cache: "no-store" });
      if (!response.ok) {
        throw new Error(`traffic ${response.status}`);
      }
      const data = await response.json();
      if (this.destroyed || !this.state.commercialTrafficEnabled || seq !== this.commercialTrafficSeq) {
        return;
      }
      this.commercialAircraft = Array.isArray(data.aircraft) ? data.aircraft : [];
      this.state.commercialTrafficCount = this.commercialAircraft.length;
      this.state.commercialTrafficSource = data.source || "";
      this.state.commercialTrafficLoading = false;
      this.state.commercialTrafficError = "";
      this.renderCommercialAircraft();
      this.updateCommercialTrafficControl();
    } catch (error) {
      if (this.destroyed || !this.state.commercialTrafficEnabled || seq !== this.commercialTrafficSeq) {
        return;
      }
      this.state.commercialTrafficLoading = false;
      this.state.commercialTrafficError = error.message;
      this.updateCommercialTrafficControl();
    }
  }

  startUamVehiclePolling() {
    window.clearInterval(this.uamVehicleTimer);
    this.refreshUamVehicleStatus();
    this.uamVehicleTimer = window.setInterval(() => this.refreshUamVehicleStatus(), UAM_VEHICLE_REFRESH_MS);
  }

  async refreshUamVehicleStatus() {
    if (this.destroyed || this.uamVehicleStatusLoading) {
      return;
    }
    this.uamVehicleStatusLoading = true;
    const seq = ++this.uamVehicleSeq;
    try {
      const response = await fetch(VEHICLE_STATUS_URL, { headers: { Accept: "application/json" }, cache: "no-store" });
      if (!response.ok) {
        throw new Error(`vehicle-status ${response.status}`);
      }
      const data = await response.json();
      if (this.destroyed || seq < this.uamVehicleSeq - 1) {
        return;
      }
      this.vehicleStatusListening = Boolean(data?.listening);
      this.vehicleStatusError = data?.last_error || "";
      this.uamVehicles = this.normalizeUamVehicleList(data?.vehicles);
      this.renderUamVehicles();
      this.updateUamVehicleDetailPanel();
      this.updateCommercialTrafficControl();
    } catch (error) {
      if (this.destroyed) {
        return;
      }
      this.vehicleStatusListening = false;
      this.vehicleStatusError = error.message || String(error);
      this.updateUamVehicleDetailPanel();
      this.updateCommercialTrafficControl();
    } finally {
      this.uamVehicleStatusLoading = false;
    }
  }

  firstFiniteNumber(...values) {
    for (const value of values) {
      if (value === null || value === undefined || value === "") {
        continue;
      }
      const numeric = Number(value);
      if (Number.isFinite(numeric)) {
        return numeric;
      }
    }
    return null;
  }

  canonicalUamVehicleId(value) {
    const text = String(value || "").trim();
    if (!text) {
      return "";
    }
    const match = text.match(/^([A-Za-z]+)[\s_-]*0*(\d+)$/);
    if (!match) {
      return text;
    }
    return `${match[1].toUpperCase()}${match[2].padStart(4, "0")}`;
  }

  uamVehicleFreshnessScore(vehicle) {
    const sourcePriority = vehicle?.source === "airmobility-status" ? 0 : 1_000_000_000;
    const receivedAtEpoch = Number(vehicle?.receivedAtEpoch);
    if (Number.isFinite(receivedAtEpoch) && receivedAtEpoch > 0) {
      return sourcePriority + (receivedAtEpoch * 1000);
    }
    const receivedAtMs = Date.parse(vehicle?.receivedAt || vehicle?.messageTimestamp || "");
    return sourcePriority + (Number.isFinite(receivedAtMs) ? receivedAtMs : 0);
  }

  normalizeUamVehicleList(rawVehicles) {
    if (!Array.isArray(rawVehicles)) {
      return [];
    }
    const vehiclesById = new Map();
    rawVehicles
      .map((vehicle) => this.normalizeUamVehicle(vehicle))
      .filter((vehicle) => vehicle && !vehicle.stale)
      .forEach((vehicle) => {
        const id = this.uamVehicleId(vehicle);
        if (!id) {
          return;
        }
        const current = vehiclesById.get(id);
        if (!current || this.uamVehicleFreshnessScore(vehicle) >= this.uamVehicleFreshnessScore(current)) {
          vehiclesById.set(id, vehicle);
        }
      });
    return Array.from(vehiclesById.values());
  }

  normalizeUamVehicle(raw) {
    if (!raw || typeof raw !== "object") {
      return null;
    }
    const gps = raw.gps && typeof raw.gps === "object" ? raw.gps : {};
    const position = raw.position && typeof raw.position === "object" ? raw.position : {};
    const attitude = raw.attitude && typeof raw.attitude === "object" ? raw.attitude : {};
    const aircraftId = this.canonicalUamVehicleId(raw.aircraftId || raw.id || raw.vehicle_id || raw.vehicleId || "");
    const latitude = this.firstFiniteNumber(gps.latitude, raw.latitude, raw.lat);
    const longitude = this.firstFiniteNumber(gps.longitude, raw.longitude, raw.lon, raw.lng);
    if (!aircraftId || latitude === null || longitude === null) {
      return null;
    }

    const altitudeM = this.firstFiniteNumber(gps.altitude, raw.altitudeM, raw.altitude, raw.altitude_m);
    const velocityNorth = this.firstFiniteNumber(gps.velocity_north, gps.velocityNorth, raw.velocity_north, raw.velocityNorth);
    const velocityEast = this.firstFiniteNumber(gps.velocity_east, gps.velocityEast, raw.velocity_east, raw.velocityEast);
    const velocityDown = this.firstFiniteNumber(gps.velocity_down, gps.velocityDown, raw.velocity_down, raw.velocityDown);
    let speedMps = this.firstFiniteNumber(raw.speedMps, raw.groundSpeedMps, raw.speed_mps);
    if (speedMps === null && [velocityNorth, velocityEast, velocityDown].some((value) => value !== null)) {
      speedMps = Math.hypot(velocityNorth || 0, velocityEast || 0, velocityDown || 0);
    }

    const yawRad = this.firstFiniteNumber(attitude.yaw, raw.yaw);
    const horizontalSpeedMps = Math.hypot(velocityNorth || 0, velocityEast || 0);
    const velocityTrackHeadingDeg =
      horizontalSpeedMps > 0.05
        ? normalizeDegrees((Math.atan2(velocityEast || 0, velocityNorth || 0) * 180) / Math.PI)
        : null;

    let bodyHeadingDeg = this.firstFiniteNumber(raw.headingDeg, raw.heading_deg, raw.heading);
    if (bodyHeadingDeg !== null) {
      bodyHeadingDeg = normalizeDegrees(bodyHeadingDeg);
    } else if (yawRad !== null) {
      // Some providers expose attitude.yaw in an AirSim/pose frame, so use it only as a last fallback.
      bodyHeadingDeg = normalizeDegrees((yawRad * 180) / Math.PI);
    }

    let trackHeadingDeg = this.firstFiniteNumber(
      raw.trackHeadingDeg,
      raw.track_heading_deg,
      raw.trackHeading,
      raw.track_heading,
    );
    if (trackHeadingDeg !== null) {
      trackHeadingDeg = normalizeDegrees(trackHeadingDeg);
    } else if (velocityTrackHeadingDeg !== null) {
      trackHeadingDeg = velocityTrackHeadingDeg;
    }

    const headingDeg = trackHeadingDeg ?? bodyHeadingDeg ?? velocityTrackHeadingDeg ?? 0;

    return {
      ...raw,
      id: aircraftId,
      aircraftId,
      latitude,
      longitude,
      altitudeM,
      speedMps,
      headingDeg,
      bodyHeadingDeg: bodyHeadingDeg === null ? headingDeg : bodyHeadingDeg,
      trackHeadingDeg: trackHeadingDeg === null ? headingDeg : trackHeadingDeg,
      velocityNorth,
      velocityEast,
      velocityDown,
      position,
      attitude,
      gps,
      stale: Boolean(raw.stale),
    };
  }

  clearUamVehicleOverlay() {
    this.clearUamVehicleTrack();
    this.uamVehicleMarkerPositions.clear();
    const source = this.map?.getSource(UAM_VEHICLE_SOURCE_ID);
    if (source) {
      source.setData({ type: "FeatureCollection", features: [] });
    }
    this.selectedUamVehicleId = null;
    this.updateUamVehicleDetailPanel();
  }

  ensureUamVehicleIconImage() {
    if (!this.map) {
      return false;
    }
    if (this.map.hasImage?.(UAM_VEHICLE_ICON_ID)) {
      return true;
    }
    if (this.uamVehicleIconLoading) {
      return false;
    }
    this.uamVehicleIconLoading = true;

    const finish = (image) => {
      this.uamVehicleIconLoading = false;
      if (!this.map || !image) {
        return;
      }
      try {
        if (!this.map.hasImage?.(UAM_VEHICLE_ICON_ID)) {
          this.map.addImage(UAM_VEHICLE_ICON_ID, image);
        }
        this.ensureUamVehicleTrackLayer();
        this.syncUamVehicleSource();
        this.setUamVehicleTrackData();
      } catch (error) {
        // Style reloads can invalidate addImage/addLayer briefly; the next poll retries.
      }
    };

    if (typeof this.map.loadImage === "function") {
      this.map.loadImage(UAM_VEHICLE_ICON_URL, (error, image) => {
        if (error || !image) {
          this.uamVehicleIconLoading = false;
          return;
        }
        finish(image);
      });
      return false;
    }

    const image = new Image();
    image.onload = () => finish(image);
    image.onerror = () => {
      this.uamVehicleIconLoading = false;
    };
    image.src = UAM_VEHICLE_ICON_URL;
    return false;
  }

  ensureUamVehicleTrackLayer() {
    if (!this.map || !this.map.isStyleLoaded()) {
      return false;
    }
    const hasUamIconImage = this.ensureUamVehicleIconImage();

    if (!this.map.getSource(UAM_VEHICLE_SOURCE_ID)) {
      this.map.addSource(UAM_VEHICLE_SOURCE_ID, {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
    }

    if (!this.map.getSource(UAM_VEHICLE_TRACK_SOURCE_ID)) {
      this.map.addSource(UAM_VEHICLE_TRACK_SOURCE_ID, {
        type: "geojson",
        lineMetrics: true,
        data: { type: "FeatureCollection", features: [] },
      });
    }

    UAM_VEHICLE_POINT_LAYER_IDS.forEach((layerId) => {
      if (this.map.getLayer(layerId)) {
        try {
          this.map.removeLayer(layerId);
        } catch (error) {
          // Style reloads can briefly invalidate layers; the next poll will retry.
        }
      }
    });

    if (!this.map.getLayer("uam-vehicle-track-casing")) {
      this.map.addLayer({
        id: "uam-vehicle-track-casing",
        type: "line",
        source: UAM_VEHICLE_TRACK_SOURCE_ID,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "rgba(3, 7, 18, 0.68)",
          "line-width": ["interpolate", ["linear"], ["zoom"], 7, 5, 12, 10],
          "line-opacity": 0,
        },
      });
    }

    if (!this.map.getLayer("uam-vehicle-track-line")) {
      this.map.addLayer({
        id: "uam-vehicle-track-line",
        type: "line",
        source: UAM_VEHICLE_TRACK_SOURCE_ID,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-gradient": ["interpolate", ["linear"], ["line-progress"], 0, "#13f5ff", 0.65, "#38bdf8", 1, "#ffffff"],
          "line-width": ["interpolate", ["linear"], ["zoom"], 7, 3, 12, 6],
          "line-opacity": 0,
        },
      });
    }

    if (!this.map.getLayer(UAM_VEHICLE_SELECTION_LAYER_ID)) {
      this.map.addLayer({
        id: UAM_VEHICLE_SELECTION_LAYER_ID,
        type: "circle",
        source: UAM_VEHICLE_SOURCE_ID,
        filter: ["==", ["get", "selected"], true],
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 6, 21, 12, 25, 18, 29],
          "circle-color": "rgba(34, 211, 238, 0.14)",
          "circle-opacity": ["case", ["==", ["get", "stale"], true], 0.35, 1],
          "circle-blur": 0.18,
          "circle-stroke-color": "#22d3ee",
          "circle-stroke-opacity": ["case", ["==", ["get", "stale"], true], 0.45, 0.92],
          "circle-stroke-width": 2.2,
        },
      });
    }

    if (hasUamIconImage && !this.map.getLayer(UAM_VEHICLE_ICON_LAYER_ID)) {
      this.map.addLayer({
        id: UAM_VEHICLE_ICON_LAYER_ID,
        type: "symbol",
        source: UAM_VEHICLE_SOURCE_ID,
        layout: {
          "icon-image": UAM_VEHICLE_ICON_ID,
          "icon-size": 0.105,
          "icon-rotate": ["coalesce", ["get", "heading"], 0],
          "icon-rotation-alignment": "map",
          "icon-pitch-alignment": "map",
          "icon-anchor": "center",
          "icon-allow-overlap": true,
          "icon-ignore-placement": true,
        },
        paint: {
          "icon-opacity": ["case", ["==", ["get", "stale"], true], 0.56, 1],
        },
      });
    }

    if (!this.map.getLayer(UAM_VEHICLE_LABEL_LAYER_ID)) {
      this.map.addLayer({
        id: UAM_VEHICLE_LABEL_LAYER_ID,
        type: "symbol",
        source: UAM_VEHICLE_SOURCE_ID,
        layout: {
          "text-field": ["get", "label"],
          "text-font": ["Open Sans Regular", "Arial Unicode MS Regular"],
          "text-size": 10,
          "text-offset": [0, 1.75],
          "text-anchor": "top",
          "text-allow-overlap": true,
          "text-ignore-placement": true,
        },
        paint: {
          "text-color": ["case", ["==", ["get", "collision"], true], "#fecaca", "#ffffff"],
          "text-halo-color": ["case", ["==", ["get", "collision"], true], "rgba(127, 29, 29, 0.98)", "rgba(8, 12, 16, 0.96)"],
          "text-halo-width": 2.4,
          "text-opacity": ["case", ["==", ["get", "stale"], true], 0.56, 1],
        },
      });
    }

    if (!this.map.getLayer("uam-vehicle-hit-area")) {
      this.map.addLayer({
        id: "uam-vehicle-hit-area",
        type: "circle",
        source: UAM_VEHICLE_SOURCE_ID,
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 7, 26, 12, 42],
          "circle-color": "#ffffff",
          "circle-opacity": 0,
          "circle-stroke-opacity": 0,
        },
      });
    }

    this.raiseUamVehicleLayers();
    this.bindUamVehicleMapEvents();
    return true;
  }

  raiseUamVehicleLayers() {
    if (!this.map || !this.map.isStyleLoaded()) {
      return;
    }
    UAM_VEHICLE_LAYER_IDS.forEach((layerId) => {
      if (!this.map.getLayer(layerId)) {
        return;
      }
      try {
        this.map.moveLayer(layerId);
      } catch (error) {
        // Style reloads can briefly invalidate layer ordering; the next poll will retry.
      }
    });
  }

  bindUamVehicleMapEvents() {
    if (!this.map || this.uamVehicleMapEventsBound) {
      return;
    }
    UAM_VEHICLE_CLICK_LAYER_IDS.forEach((layerId) => {
      if (!this.map.getLayer(layerId)) {
        return;
      }
      this.map.on("click", layerId, (event) => {
        const feature = event.features?.[0];
        const id = feature?.properties?.id;
        if (id) {
          this.selectUamVehicle(String(id));
        }
      });
      this.map.on("mouseenter", layerId, () => {
        this.map.getCanvas().style.cursor = "pointer";
      });
      this.map.on("mouseleave", layerId, () => {
        this.map.getCanvas().style.cursor = "";
      });
    });
    this.uamVehicleMapEventsBound = true;
  }

  uamVehicleId(vehicle) {
    return this.canonicalUamVehicleId(vehicle?.aircraftId || vehicle?.id || vehicle?.vehicle_id || "");
  }

  uamVehicleLngLat(vehicle) {
    const latitude = this.firstFiniteNumber(vehicle?.latitude, vehicle?.gps?.latitude);
    const longitude = this.firstFiniteNumber(vehicle?.longitude, vehicle?.gps?.longitude);
    if (latitude === null || longitude === null) {
      return null;
    }
    return [longitude, latitude];
  }

  uamVehicleHeading(vehicle) {
    const heading = this.firstFiniteNumber(vehicle?.headingDeg);
    return heading === null ? 0 : normalizeDegrees(heading);
  }

  formatUamVehicleLabel(id) {
    const value = String(id || "").trim();
    const match = value.match(/^([A-Za-z]+)[-_ ]?(\d+)$/);
    if (!match) {
      return value;
    }
    return `${match[1].toUpperCase()} ${match[2]}`;
  }

  renderUamVehicles() {
    if (!this.map || !window.maplibregl || !this.ensureUamVehicleTrackLayer()) {
      return;
    }

    // UAM positions are rendered as MapLibre symbol layers (like vertiports/WP),
    // not DOM markers. This keeps the icon anchored to the exact map
    // coordinate under every zoom/bearing change.
    const seen = new Set();
    this.uamVehicles.forEach((vehicle) => {
      const id = this.uamVehicleId(vehicle);
      const lngLat = this.uamVehicleLngLat(vehicle);
      if (!id || !lngLat) {
        return;
      }
      seen.add(id);
      this.uamVehicleMarkerPositions.set(id, lngLat);
      this.updateUamVehicleTrack(vehicle);
    });

    this.uamVehicleMarkerPositions.forEach((_, id) => {
      if (seen.has(id)) {
        return;
      }
      this.uamVehicleMarkerPositions.delete(id);
      this.uamVehicleTracks.delete(id);
    });

    if (this.selectedUamVehicleId && !seen.has(this.selectedUamVehicleId)) {
      this.selectedUamVehicleId = null;
      this.uamVehiclePopup?.remove();
      this.uamVehiclePopup = null;
      this.clearUamVehicleTrack();
    }

    this.syncUamVehicleSource();
    this.setUamVehicleTrackData();
    this.autoCenterLiveUamVehicle(seen);
    if (this.selectedUamVehicleId && this.uamVehiclePopup) {
      const selected = this.uamVehicles.find((vehicle) => this.uamVehicleId(vehicle) === this.selectedUamVehicleId);
      if (selected) {
        this.openUamVehiclePopup(selected);
      }
    }
    this.updateMissionRouteOverlay();
  }

  autoCenterLiveUamVehicle(seen) {
    if (this.uamVehicleAutoCentered || !this.map || !seen || seen.size < 1) {
      return;
    }
    const id = this.selectedUamVehicleId && seen.has(this.selectedUamVehicleId)
      ? this.selectedUamVehicleId
      : Array.from(seen)[0];
    const vehicle = this.uamVehicles.find((item) => this.uamVehicleId(item) === id);
    if (!vehicle || vehicle.stale) {
      return;
    }
    const lngLat = this.uamVehicleMarkerPositions.get(id) || this.uamVehicleLngLat(vehicle);
    if (!lngLat) {
      return;
    }
    this.uamVehicleAutoCentered = true;
    this.map.easeTo({
      center: lngLat,
      zoom: Math.max(this.map.getZoom(), 13.4),
      duration: 450,
      essential: true,
    });
  }

  snapUamVehicleMarkers() {
    this.uamVehicles.forEach((vehicle) => {
      const id = this.uamVehicleId(vehicle);
      const lngLat = this.uamVehicleLngLat(vehicle);
      if (!id || !lngLat) {
        return;
      }
      this.uamVehicleMarkerPositions.set(id, lngLat);
    });
    this.syncUamVehicleSource();
    this.setUamVehicleTrackData();
  }

  syncUamVehicleSource() {
    if (!this.map || !this.ensureUamVehicleTrackLayer()) {
      return;
    }
    const features = this.uamVehicles
      .map((vehicle) => {
        const id = this.uamVehicleId(vehicle);
        const lngLat = this.uamVehicleMarkerPositions.get(id) || this.uamVehicleLngLat(vehicle);
        if (!id || !lngLat) {
          return null;
        }
        return {
          type: "Feature",
          properties: {
            id,
            label: `${this.formatUamVehicleLabel(id)}${this.hasUamCollision(vehicle) ? " !" : ""}`,
            selected: id === this.selectedUamVehicleId,
            stale: Boolean(vehicle.stale),
            collision: this.hasUamCollision(vehicle),
            heading: normalizeDegrees(this.uamVehicleHeading(vehicle) + UAM_VEHICLE_ICON_HEADING_OFFSET_DEG),
          },
          geometry: { type: "Point", coordinates: lngLat },
        };
      })
      .filter(Boolean);

    this.map.getSource(UAM_VEHICLE_SOURCE_ID)?.setData({
      type: "FeatureCollection",
      features,
    });
    this.raiseUamVehicleLayers();
  }

  selectUamVehicle(id) {
    const selected = this.uamVehicles.find((vehicle) => this.uamVehicleId(vehicle) === id);
    if (!selected) {
      return;
    }
    this.selectedUamVehicleId = id;
    this.activateMissionEntryForUamVehicle(id);
    this.syncUamVehicleSource();
    this.setUamVehicleTrackData();
    this.openUamVehiclePopup(selected);
    this.updateUamVehicleDetailPanel();
    this.updateMissionRouteOverlay();
    void this.ensureMissionRouteForUamVehicle(id);
  }

  closeUamVehicleDetail() {
    this.selectedUamVehicleId = null;
    this.uamVehiclePopup?.remove();
    this.uamVehiclePopup = null;
    this.syncUamVehicleSource();
    this.clearUamVehicleTrack();
    this.updateUamVehicleDetailPanel();
    this.updateMissionRouteOverlay();
  }

  openUamVehiclePopup(vehicle) {
    const id = this.uamVehicleId(vehicle);
    const lngLat = this.uamVehicleMarkerPositions.get(id) || this.uamVehicleLngLat(vehicle);
    if (!this.map || !lngLat) {
      return;
    }
    if (!this.uamVehiclePopup) {
      this.uamVehiclePopup = new window.maplibregl.Popup({
        closeButton: true,
        closeOnClick: true,
        className: "uam-vehicle-popup",
        offset: [0, -22],
      });
      this.uamVehiclePopup.on("close", () => {
        this.uamVehiclePopup = null;
        this.selectedUamVehicleId = null;
        this.syncUamVehicleSource();
        this.clearUamVehicleTrack();
        this.updateUamVehicleDetailPanel();
        this.updateMissionRouteOverlay();
      });
    }
    this.uamVehiclePopup
      .setLngLat(lngLat)
      .setDOMContent(this.buildUamVehiclePopup(vehicle))
      .addTo(this.map);
  }

  buildUamVehiclePopup(vehicle) {
    const card = document.createElement("div");
    card.className = "commercial-popup-card uam-popup-card";

    const title = document.createElement("strong");
    title.textContent = vehicle.aircraftId || vehicle.id || this.t("vehicleDetails");
    card.append(title);

    if (this.hasUamCollision(vehicle)) {
      const badge = document.createElement("span");
      badge.className = "uam-collision-badge";
      badge.textContent = this.t("collisionActive");
      card.append(badge);
    }

    const rows = [
      [this.t("currentWaypoint"), vehicle.currentWaypointId || vehicle.current_waypoint_id || "-"],
      [this.t("gpsPosition"), this.formatUamGpsPosition(vehicle)],
      [this.t("altitude"), this.formatUamAltitude(vehicle.altitudeM)],
      [this.t("speed"), this.formatUamSpeed(vehicle.speedMps)],
      [this.t("heading"), this.formatUamHeading(vehicle.headingDeg)],
      [this.t("lastUpdate"), this.formatUamTime(vehicle.receivedAt || vehicle.messageTimestamp)],
    ];

    if (this.hasUamCollision(vehicle)) {
      rows.splice(1, 0, [this.t("collisionStatus"), this.formatUamCollision(vehicle.collision)]);
    }

    rows.forEach(([label, value]) => {
      const row = document.createElement("div");
      row.className = "commercial-popup-row";
      const labelElement = document.createElement("span");
      labelElement.textContent = label;
      const valueElement = document.createElement("b");
      valueElement.textContent = value;
      row.append(labelElement, valueElement);
      card.append(row);
    });

    if (this.hasUamCollision(vehicle)) {
      const actions = document.createElement("div");
      actions.className = "uam-collision-actions";
      const clearButton = document.createElement("button");
      clearButton.type = "button";
      clearButton.className = "uam-collision-button";
      clearButton.textContent = this.t("collisionClearResume");
      clearButton.addEventListener("click", () => this.clearUamVehicleCollision(id));
      actions.append(clearButton);
      card.append(actions);
    }

    return card;
  }

  updateUamVehicleTrack(vehicle) {
    const id = this.uamVehicleId(vehicle);
    const lngLat = this.uamVehicleLngLat(vehicle);
    if (!id || !lngLat) {
      return;
    }
    const track = this.uamVehicleTracks.get(id) || [];
    const last = track[track.length - 1];
    if (!last || Math.abs(last[0] - lngLat[0]) > 1e-7 || Math.abs(last[1] - lngLat[1]) > 1e-7) {
      track.push(lngLat);
      if (track.length > UAM_VEHICLE_TRACK_LIMIT) {
        track.splice(0, track.length - UAM_VEHICLE_TRACK_LIMIT);
      }
      this.uamVehicleTracks.set(id, track);
    }
  }

  setUamVehicleTrackData() {
    if (!this.map || !this.ensureUamVehicleTrackLayer()) {
      return;
    }
    const coordinates = this.selectedUamVehicleId ? (this.uamVehicleTracks.get(this.selectedUamVehicleId) || []) : [];
    const source = this.map.getSource(UAM_VEHICLE_TRACK_SOURCE_ID);
    if (source) {
      source.setData({
        type: "FeatureCollection",
        features: coordinates.length > 1
          ? [
              {
                type: "Feature",
                properties: {},
                geometry: { type: "LineString", coordinates },
              },
            ]
          : [],
      });
    }
    const visible = coordinates.length > 1;
    if (this.map.getLayer("uam-vehicle-track-casing")) {
      this.map.setPaintProperty("uam-vehicle-track-casing", "line-opacity", visible ? 0.56 : 0);
    }
    if (this.map.getLayer("uam-vehicle-track-line")) {
      this.map.setPaintProperty("uam-vehicle-track-line", "line-opacity", visible ? 0.94 : 0);
    }
    this.raiseUamVehicleLayers();
  }

  clearUamVehicleTrack() {
    if (!this.map || !this.map.isStyleLoaded()) {
      return;
    }
    const source = this.map.getSource(UAM_VEHICLE_TRACK_SOURCE_ID);
    if (source) {
      source.setData({ type: "FeatureCollection", features: [] });
    }
    UAM_VEHICLE_TRACK_LAYER_IDS.forEach((layerId) => {
      if (this.map?.getLayer(layerId)) {
        this.map.setPaintProperty(layerId, "line-opacity", 0);
      }
    });
  }

  updateUamVehicleDetailPanel() {
    const panel = this.container.querySelector("[data-uam-vehicle-detail]");
    if (!panel) {
      return;
    }
    const vehicle = this.selectedUamVehicleId
      ? this.uamVehicles.find((item) => this.uamVehicleId(item) === this.selectedUamVehicleId)
      : null;
    panel.hidden = !vehicle;
    panel.classList.toggle("has-collision", this.hasUamCollision(vehicle));
    if (!vehicle) {
      return;
    }
    panel.querySelector("[data-uam-detail-title]")?.replaceChildren(document.createTextNode(vehicle.aircraftId || vehicle.id || this.t("vehicleDetails")));
    const subtitle = `${this.t("lastUpdate")} ${this.formatUamTime(vehicle.receivedAt || vehicle.messageTimestamp)}${vehicle.stale ? " / stale" : ""}`;
    panel.querySelector("[data-uam-detail-subtitle]")?.replaceChildren(document.createTextNode(subtitle));
    const body = panel.querySelector("[data-uam-detail-body]");
    if (body) {
      body.innerHTML = this.renderUamVehicleDetailRows(vehicle);
    }
  }

  renderUamVehicleDetailRows(vehicle) {
    const rows = [
      [this.t("currentWaypoint"), vehicle.currentWaypointId || vehicle.current_waypoint_id || "-"],
      [this.t("gpsPosition"), this.formatUamGpsPosition(vehicle)],
      [this.t("nedPosition"), this.formatUamNedPosition(vehicle.position)],
      [this.t("altitude"), this.formatUamAltitude(vehicle.altitudeM)],
      [this.t("speed"), this.formatUamSpeed(vehicle.speedMps)],
      [this.t("heading"), this.formatUamHeading(vehicle.headingDeg)],
      [this.t("attitude"), this.formatUamAttitude(vehicle.attitude)],
    ];
    const collisionCard = this.hasUamCollision(vehicle) ? `
      <section class="uam-collision-card">
        <div class="uam-collision-card-title">
          <span class="uam-collision-badge">${escapeHtml(this.t("collisionActive"))}</span>
          <strong>${escapeHtml(this.t("collisionDetails"))}</strong>
        </div>
        <div class="uam-vehicle-detail-row">
          <span>${escapeHtml(this.t("collisionStatus"))}</span>
          <b>${escapeHtml(this.formatUamCollision(vehicle.collision))}</b>
        </div>
        <button type="button" class="uam-collision-button" data-action="clear-uam-collision" data-vehicle-id="${escapeHtml(this.uamVehicleId(vehicle))}">${escapeHtml(this.t("collisionClearResume"))}</button>
      </section>
    ` : "";
    return `${collisionCard}${rows.map(([label, value]) => `
      <div class="uam-vehicle-detail-row">
        <span>${escapeHtml(label)}</span>
        <b>${escapeHtml(value)}</b>
      </div>
    `).join("")}`;
  }

  hasUamCollision(vehicle) {
    const collision = vehicle && Object.prototype.hasOwnProperty.call(vehicle, "collision") ? vehicle.collision : null;
    if (!collision) {
      return false;
    }
    if (typeof collision !== "object") {
      return true;
    }
    const active = collision.active ?? collision.responseActive ?? collision.hasCollided;
    if (active === false || active === "false" || active === 0 || active === "0") {
      return false;
    }
    const response = String(collision.responseMode || collision.recommendedAction || "").toLowerCase();
    return !["clear", "cleared", "resume", "none", "noop", "no_op", "monitor", "record", "log"].includes(response);
  }

  formatUamCollision(collision) {
    if (!collision) {
      return "-";
    }
    if (typeof collision === "string") {
      return collision;
    }
    if (typeof collision !== "object") {
      return String(collision);
    }
    const target = collision.objectName
      || collision.targetId
      || collision.target_id
      || collision.otherVehicleId
      || collision.other_vehicle_id
      || collision.with
      || collision.objectId
      || collision.object_id
      || "-";
    const severity = collision.severity || collision.status || collision.state || "active";
    const response = collision.responseMode || collision.recommendedAction || collision.action || "";
    return response ? `${severity} / ${response} / ${target}` : `${severity} / ${target}`;
  }

  async clearUamVehicleCollision(vehicleId) {
    const id = this.canonicalUamVehicleId(vehicleId || this.selectedUamVehicleId);
    if (!id) {
      return null;
    }
    const buttons = Array.from(this.container.querySelectorAll("[data-action='clear-uam-collision']"))
      .filter((button) => this.canonicalUamVehicleId(button.dataset.vehicleId) === id);
    buttons.forEach((button) => {
      button.disabled = true;
      button.textContent = this.t("collisionClearing");
    });
    try {
      const result = await postJSON(`${VEHICLE_COLLISION_CLEAR_URL}/${encodeURIComponent(id)}/clear`, {});
      this.pushOperationLog(this.t("collisionClearOk"), {
        title: id,
        level: "success",
      });
      await this.refreshUamVehicleStatus();
      return result;
    } catch (error) {
      this.pushOperationLog(error.message || this.t("collisionClearError"), {
        title: this.t("collisionClearError"),
        level: "error",
      });
      buttons.forEach((button) => {
        button.disabled = false;
        button.textContent = this.t("collisionClearResume");
      });
      return null;
    }
  }

  formatUamGpsPosition(vehicle) {
    const latitude = this.firstFiniteNumber(vehicle?.latitude, vehicle?.gps?.latitude);
    const longitude = this.firstFiniteNumber(vehicle?.longitude, vehicle?.gps?.longitude);
    if (latitude === null || longitude === null) {
      return "-";
    }
    return `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`;
  }

  formatUamNedPosition(position) {
    const north = this.firstFiniteNumber(position?.north, position?.n);
    const east = this.firstFiniteNumber(position?.east, position?.e);
    const down = this.firstFiniteNumber(position?.down, position?.d);
    if (north === null && east === null && down === null) {
      return "-";
    }
    return `N ${this.formatMeters(north)} / E ${this.formatMeters(east)} / D ${this.formatMeters(down)}`;
  }

  formatUamAttitude(attitude) {
    const roll = this.firstFiniteNumber(attitude?.roll);
    const pitch = this.firstFiniteNumber(attitude?.pitch);
    const yaw = this.firstFiniteNumber(attitude?.yaw);
    const parts = [
      ["R", roll],
      ["P", pitch],
      ["Y", yaw],
    ]
      .filter(([, value]) => value !== null)
      .map(([label, value]) => `${label} ${this.formatDegrees((value * 180) / Math.PI)}`);
    return parts.length ? parts.join(" / ") : "-";
  }

  formatMeters(value) {
    if (value === null || value === undefined || value === "") {
      return "-";
    }
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      return "-";
    }
    return `${numeric.toFixed(1)} m`;
  }

  formatDegrees(value) {
    if (value === null || value === undefined || value === "") {
      return "-";
    }
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      return "-";
    }
    return `${numeric.toFixed(1)} deg`;
  }

  formatUamAltitude(value) {
    return this.formatMeters(value);
  }

  formatUamSpeed(value) {
    if (value === null || value === undefined || value === "") {
      return "-";
    }
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      return "-";
    }
    return `${(numeric * 3.6).toFixed(1)} km/h`;
  }

  formatUamHeading(value) {
    return this.formatDegrees(value);
  }

  formatUamTime(value) {
    if (!value) {
      return "-";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "-";
    }
    const formatted = new Intl.DateTimeFormat(this.language === "ko" ? "ko-KR" : "en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
      timeZone: "Asia/Seoul",
    }).format(date);
    return `${formatted} KST`;
  }

  clearCommercialAircraftOverlay() {
    this.clearCommercialAircraftTrack();
    this.commercialAircraftMarkerAnimations.forEach((animationId) => window.cancelAnimationFrame(animationId));
    this.commercialAircraftMarkerAnimations.clear();
    this.commercialAircraftMarkerPositions.clear();
    this.commercialAircraftMarkers.forEach((marker) => marker.remove());
    this.commercialAircraftMarkers.clear();
    const source = this.map?.getSource(COMMERCIAL_AIRCRAFT_SOURCE_ID);
    if (source) {
      source.setData({ type: "FeatureCollection", features: [] });
    }
    this.commercialAircraftPopup?.remove();
    this.commercialAircraftPopup = null;
    this.selectedCommercialAircraftId = null;
  }

  commercialAircraftId(aircraft) {
    return aircraft?.id || aircraft?.icao24 || `${aircraft?.longitude}:${aircraft?.latitude}`;
  }

  commercialAircraftLngLat(aircraft) {
    if (!isFiniteNumber(aircraft?.longitude) || !isFiniteNumber(aircraft?.latitude)) {
      return null;
    }
    return [Number(aircraft.longitude), Number(aircraft.latitude)];
  }

  createCommercialAircraftIcon() {
    const canvas = document.createElement("canvas");
    canvas.width = 64;
    canvas.height = 64;
    const context = canvas.getContext("2d");
    if (!context) {
      return { width: 1, height: 1, data: new Uint8Array(4) };
    }

    const scale = 2.25;
    const offset = 32 - 12 * scale;
    const path = new Path2D(
      "M12 2.2 9.6 10 3 14.1v2.1l7.4-2.1-.5 4.1-2.3 1.7v1.5l4.4-.9 4.4.9v-1.5l-2.3-1.7-.5-4.1 7.4 2.1v-2.1L14.4 10 12 2.2Z",
    );

    context.save();
    context.translate(offset + 2.5, offset + 3.2);
    context.scale(scale, scale);
    context.fillStyle = "rgba(0, 0, 0, 0.28)";
    context.fill(path);
    context.restore();

    context.save();
    context.translate(offset, offset);
    context.scale(scale, scale);
    context.lineJoin = "round";
    context.lineCap = "round";
    context.lineWidth = 0.95;
    context.strokeStyle = "#111111";
    context.fillStyle = "#ffd400";
    context.stroke(path);
    context.fill(path);
    context.restore();

    return context.getImageData(0, 0, canvas.width, canvas.height);
  }

  ensureCommercialAircraftLayer() {
    if (!this.map || !this.map.isStyleLoaded()) {
      return false;
    }

    if (!this.map.hasImage?.(COMMERCIAL_AIRCRAFT_ICON_ID)) {
      this.map.addImage(COMMERCIAL_AIRCRAFT_ICON_ID, this.createCommercialAircraftIcon(), { pixelRatio: 2 });
    }

    if (!this.map.getSource(COMMERCIAL_AIRCRAFT_SOURCE_ID)) {
      this.map.addSource(COMMERCIAL_AIRCRAFT_SOURCE_ID, {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
    }

    if (!this.map.getLayer(COMMERCIAL_AIRCRAFT_SELECTED_LAYER_ID)) {
      this.map.addLayer({
        id: COMMERCIAL_AIRCRAFT_SELECTED_LAYER_ID,
        type: "circle",
        source: COMMERCIAL_AIRCRAFT_SOURCE_ID,
        filter: ["==", ["get", "selected"], true],
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 7, 28, 12, 46],
          "circle-color": "#2dd4bf",
          "circle-opacity": 0.36,
          "circle-blur": 0.55,
          "circle-stroke-color": "#2563eb",
          "circle-stroke-opacity": 0.75,
          "circle-stroke-width": 1.2,
        },
      });
    }

    if (!this.map.getLayer(COMMERCIAL_AIRCRAFT_LAYER_ID)) {
      this.map.addLayer({
        id: COMMERCIAL_AIRCRAFT_LAYER_ID,
        type: "symbol",
        source: COMMERCIAL_AIRCRAFT_SOURCE_ID,
        layout: {
          "icon-image": COMMERCIAL_AIRCRAFT_ICON_ID,
          "icon-size": ["interpolate", ["linear"], ["zoom"], 6, 0.7, 10, 1.02, 14, 1.44],
          "icon-rotate": ["coalesce", ["get", "heading"], 0],
          "icon-rotation-alignment": "map",
          "icon-pitch-alignment": "map",
          "icon-anchor": "center",
          "icon-allow-overlap": true,
          "icon-ignore-placement": true,
        },
      });
    }

    this.bindCommercialAircraftMapEvents();
    return true;
  }

  syncCommercialAircraftSource() {
    if (!this.map || !this.ensureCommercialAircraftLayer()) {
      return;
    }

    const features = this.commercialAircraft
      .map((aircraft) => {
        const id = this.commercialAircraftId(aircraft);
        const lngLat = this.commercialAircraftMarkerPositions.get(id) || this.commercialAircraftLngLat(aircraft);
        if (!lngLat) {
          return null;
        }
        return {
          type: "Feature",
          properties: {
            id,
            heading: isFiniteNumber(aircraft.headingDeg) ? Number(aircraft.headingDeg) : 0,
            selected: id === this.selectedCommercialAircraftId,
          },
          geometry: { type: "Point", coordinates: lngLat },
        };
      })
      .filter(Boolean);

    this.map.getSource(COMMERCIAL_AIRCRAFT_SOURCE_ID)?.setData({
      type: "FeatureCollection",
      features,
    });
  }

  renderCommercialAircraft() {
    if (!this.map || !this.state.commercialTrafficEnabled) {
      this.clearCommercialAircraftOverlay();
      return;
    }

    if (!this.ensureCommercialAircraftLayer()) {
      return;
    }

    const seen = new Set();
    this.commercialAircraft.forEach((aircraft) => {
      if (!isFiniteNumber(aircraft.longitude) || !isFiniteNumber(aircraft.latitude)) {
        return;
      }

      const id = this.commercialAircraftId(aircraft);
      const lngLat = [Number(aircraft.longitude), Number(aircraft.latitude)];
      seen.add(id);

      if (!this.commercialAircraftMarkerPositions.has(id)) {
        this.commercialAircraftMarkerPositions.set(id, lngLat);
        return;
      }

      this.animateCommercialAircraftMarker(id, lngLat);
    });

    this.commercialAircraftMarkerPositions.forEach((_, id) => {
      if (!seen.has(id)) {
        const animationId = this.commercialAircraftMarkerAnimations.get(id);
        if (animationId) {
          window.cancelAnimationFrame(animationId);
        }
        this.commercialAircraftMarkerAnimations.delete(id);
        this.commercialAircraftMarkerPositions.delete(id);
      }
    });

    this.syncCommercialAircraftSource();

    if (this.selectedCommercialAircraftId) {
      const selected = this.commercialAircraft.find((aircraft) => this.commercialAircraftId(aircraft) === this.selectedCommercialAircraftId);
      if (selected) {
        this.openCommercialAircraftPopup(selected);
        this.updateCommercialAircraftTrack(selected);
      } else {
        this.closeCommercialAircraftPopup();
      }
    }
  }

  selectCommercialAircraft(id) {
    const selected = this.commercialAircraft.find((aircraft) => this.commercialAircraftId(aircraft) === id);
    if (!selected) {
      return;
    }
    this.selectedCommercialAircraftId = id;
    this.syncCommercialAircraftSource();
    this.openCommercialAircraftPopup(selected);
    this.updateCommercialAircraftTrack(selected);
  }

  animateCommercialAircraftMarker(id, targetLngLat) {
    const previous = this.commercialAircraftMarkerPositions.get(id);
    if (!previous) {
      this.commercialAircraftMarkerPositions.set(id, targetLngLat);
      this.syncCommercialAircraftSource();
      return;
    }

    if (previous[0] === targetLngLat[0] && previous[1] === targetLngLat[1]) {
      return;
    }

    const previousAnimation = this.commercialAircraftMarkerAnimations.get(id);
    if (previousAnimation) {
      window.cancelAnimationFrame(previousAnimation);
    }

    const start = performance.now();
    const duration = Math.min(1200, Math.max(700, COMMERCIAL_TRAFFIC_REFRESH_MS * 0.2));
    const [fromLng, fromLat] = previous;
    const [toLng, toLat] = targetLngLat;

    const tick = (now) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      const currentLngLat = [
        fromLng + (toLng - fromLng) * eased,
        fromLat + (toLat - fromLat) * eased,
      ];

      this.commercialAircraftMarkerPositions.set(id, currentLngLat);
      this.syncCommercialAircraftSource();
      if (id === this.selectedCommercialAircraftId && this.commercialAircraftPopup) {
        this.commercialAircraftPopup.setLngLat(currentLngLat);
      }

      if (progress < 1) {
        this.commercialAircraftMarkerAnimations.set(id, window.requestAnimationFrame(tick));
        return;
      }

      this.commercialAircraftMarkerPositions.set(id, targetLngLat);
      this.syncCommercialAircraftSource();
      this.commercialAircraftMarkerAnimations.delete(id);
      if (id === this.selectedCommercialAircraftId && this.commercialAircraftPopup) {
        this.commercialAircraftPopup.setLngLat(targetLngLat);
      }
    };

    this.commercialAircraftMarkerAnimations.set(id, window.requestAnimationFrame(tick));
  }

  snapCommercialAircraftMarkers() {
    this.commercialAircraft.forEach((aircraft) => {
      const id = this.commercialAircraftId(aircraft);
      const lngLat = this.commercialAircraftLngLat(aircraft);
      if (!lngLat) {
        return;
      }

      const animationId = this.commercialAircraftMarkerAnimations.get(id);
      if (animationId) {
        window.cancelAnimationFrame(animationId);
        this.commercialAircraftMarkerAnimations.delete(id);
      }

      this.commercialAircraftMarkerPositions.set(id, lngLat);
    });
    this.syncCommercialAircraftSource();

    if (this.selectedCommercialAircraftId && this.commercialAircraftPopup) {
      const selected = this.commercialAircraft.find((aircraft) => this.commercialAircraftId(aircraft) === this.selectedCommercialAircraftId);
      const lngLat = selected ? this.commercialAircraftLngLat(selected) : null;
      if (lngLat) {
        this.commercialAircraftPopup.setLngLat(lngLat);
      }
    }
  }

  closeCommercialAircraftPopup() {
    this.selectedCommercialAircraftId = null;
    this.commercialAircraftPopup?.remove();
    this.commercialAircraftPopup = null;
    this.syncCommercialAircraftSource();
    if (this.map?.getSource(COMMERCIAL_TRACK_SOURCE_ID)) {
      this.clearCommercialAircraftTrack();
    }
  }

  bindCommercialAircraftMapEvents() {
    if (!this.map || this.commercialAircraftMapEventsBound || !this.map.getLayer(COMMERCIAL_AIRCRAFT_LAYER_ID)) {
      return;
    }

    this.map.on("click", COMMERCIAL_AIRCRAFT_LAYER_ID, (event) => {
      const feature = event.features?.[0];
      const id = feature?.properties?.id;
      if (!id) {
        return;
      }
      event.preventDefault?.();
      this.selectCommercialAircraft(id);
    });

    this.map.on("mouseenter", COMMERCIAL_AIRCRAFT_LAYER_ID, () => {
      this.map.getCanvas().style.cursor = "pointer";
    });
    this.map.on("mouseleave", COMMERCIAL_AIRCRAFT_LAYER_ID, () => {
      this.map.getCanvas().style.cursor = "";
    });

    this.commercialAircraftMapEventsBound = true;
  }

  openCommercialAircraftPopup(aircraft) {
    const id = this.commercialAircraftId(aircraft);
    const lngLat = this.commercialAircraftMarkerPositions.get(id) || this.commercialAircraftLngLat(aircraft);
    if (!this.map || !lngLat) {
      return;
    }
    if (!this.commercialAircraftPopup) {
      this.commercialAircraftPopup = new window.maplibregl.Popup({
        closeButton: false,
        closeOnClick: false,
        className: "commercial-aircraft-popup",
        offset: [0, -18],
      });
    }
    this.commercialAircraftPopup
      .setLngLat(lngLat)
      .setDOMContent(this.buildCommercialAircraftPopup(aircraft))
      .addTo(this.map);
  }

  buildCommercialAircraftPopup(aircraft) {
    const card = document.createElement("div");
    card.className = "commercial-popup-card";

    const title = document.createElement("strong");
    title.textContent = aircraft.callsign || aircraft.icao24 || "-";
    card.append(title);

    const rows = [
      [this.t("icao24"), aircraft.icao24 || "-"],
      [this.t("originCountry"), aircraft.originCountry || "-"],
      [this.t("altitude"), this.formatCommercialAltitude(aircraft.altitudeM)],
      [this.t("speed"), this.formatCommercialSpeed(aircraft.groundSpeedMps)],
      [this.t("heading"), this.formatCommercialHeading(aircraft.headingDeg)],
      [this.t("lastContact"), this.formatCommercialTime(aircraft.lastContact)],
    ];

    rows.forEach(([label, value]) => {
      const row = document.createElement("div");
      row.className = "commercial-popup-row";
      const labelElement = document.createElement("span");
      labelElement.textContent = label;
      const valueElement = document.createElement("b");
      valueElement.textContent = value;
      row.append(labelElement, valueElement);
      card.append(row);
    });

    return card;
  }

  ensureCommercialAircraftTrackLayer() {
    if (!this.map || !this.map.isStyleLoaded()) {
      return false;
    }

    if (!this.map.getSource(COMMERCIAL_TRACK_SOURCE_ID)) {
      this.map.addSource(COMMERCIAL_TRACK_SOURCE_ID, {
        type: "geojson",
        lineMetrics: true,
        data: { type: "FeatureCollection", features: [] },
      });
    }

    if (!this.map.getLayer("commercial-aircraft-track-casing")) {
      this.map.addLayer({
        id: "commercial-aircraft-track-casing",
        type: "line",
        source: COMMERCIAL_TRACK_SOURCE_ID,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "rgba(8, 13, 20, 0.58)",
          "line-width": ["interpolate", ["linear"], ["zoom"], 7, 4.5, 12, 9],
          "line-opacity": 0,
        },
      });
    }

    if (!this.map.getLayer("commercial-aircraft-track-line")) {
      this.map.addLayer({
        id: "commercial-aircraft-track-line",
        type: "line",
        source: COMMERCIAL_TRACK_SOURCE_ID,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-gradient": ["interpolate", ["linear"], ["line-progress"], 0, "#18e7a5", 0.5, "#2bc9ff", 1, "#6675ff"],
          "line-width": ["interpolate", ["linear"], ["zoom"], 7, 2.6, 12, 5],
          "line-opacity": 0,
        },
      });
    }

    return true;
  }

  commercialAircraftTrackCoordinates(aircraft) {
    const coordinates = Array.isArray(aircraft.track)
      ? aircraft.track
          .filter((point) => isFiniteNumber(point.longitude) && isFiniteNumber(point.latitude))
          .slice()
          .sort((a, b) => new Date(a.timestamp || 0).getTime() - new Date(b.timestamp || 0).getTime())
          .map((point) => [Number(point.longitude), Number(point.latitude)])
      : [];

    if (isFiniteNumber(aircraft.longitude) && isFiniteNumber(aircraft.latitude)) {
      coordinates.push([Number(aircraft.longitude), Number(aircraft.latitude)]);
    }

    const deduped = coordinates.filter((coordinate, index) => {
      const previous = coordinates[index - 1];
      return !previous || previous[0] !== coordinate[0] || previous[1] !== coordinate[1];
    });

    if (deduped.length > 1) {
      return deduped;
    }

    return this.estimateCommercialAircraftTrail(aircraft);
  }

  estimateCommercialAircraftTrail(aircraft) {
    if (!isFiniteNumber(aircraft.longitude) || !isFiniteNumber(aircraft.latitude)) {
      return [];
    }

    const current = [Number(aircraft.longitude), Number(aircraft.latitude)];
    const heading = isFiniteNumber(aircraft.headingDeg) ? Number(aircraft.headingDeg) : 0;
    const speed = isFiniteNumber(aircraft.groundSpeedMps) ? Math.max(80, Number(aircraft.groundSpeedMps)) : 190;
    const trailMeters = Math.min(COMMERCIAL_TRAIL_MAX_METERS, Math.max(COMMERCIAL_TRAIL_MIN_METERS, speed * COMMERCIAL_TRAIL_SECONDS));
    const reverseBearing = (heading + 180) % 360;
    const coordinates = [];

    for (let step = COMMERCIAL_TRAIL_STEPS; step >= 1; step -= 1) {
      const distance = (trailMeters * step) / COMMERCIAL_TRAIL_STEPS;
      coordinates.push(this.destinationLngLat(current, reverseBearing, distance));
    }
    coordinates.push(current);
    return coordinates;
  }

  destinationLngLat(origin, bearingDeg, distanceMeters) {
    const earthRadius = 6371008.8;
    const angularDistance = distanceMeters / earthRadius;
    const bearing = (bearingDeg * Math.PI) / 180;
    const lat1 = (origin[1] * Math.PI) / 180;
    const lon1 = (origin[0] * Math.PI) / 180;
    const sinLat1 = Math.sin(lat1);
    const cosLat1 = Math.cos(lat1);
    const sinDistance = Math.sin(angularDistance);
    const cosDistance = Math.cos(angularDistance);
    const lat2 = Math.asin(sinLat1 * cosDistance + cosLat1 * sinDistance * Math.cos(bearing));
    const lon2 = lon1 + Math.atan2(Math.sin(bearing) * sinDistance * cosLat1, cosDistance - sinLat1 * Math.sin(lat2));
    return [((lon2 * 180) / Math.PI + 540) % 360 - 180, (lat2 * 180) / Math.PI];
  }

  updateCommercialAircraftTrack(aircraft) {
    if (!this.ensureCommercialAircraftTrackLayer()) {
      return;
    }

    const coordinates = this.commercialAircraftTrackCoordinates(aircraft);

    const source = this.map.getSource(COMMERCIAL_TRACK_SOURCE_ID);
    if (!source) {
      return;
    }

    source.setData({
      type: "FeatureCollection",
      features: coordinates.length > 1
        ? [
            {
              type: "Feature",
              properties: {},
              geometry: { type: "LineString", coordinates },
            },
          ]
        : [],
    });

    this.animateCommercialAircraftTrack(coordinates.length > 1);
  }

  animateCommercialAircraftTrack(visible) {
    if (!this.map) {
      return;
    }

    if (this.commercialTrackAnimation) {
      window.cancelAnimationFrame(this.commercialTrackAnimation);
      this.commercialTrackAnimation = null;
    }

    const duration = visible ? 240 : 120;
    const targetLineOpacity = visible ? 0.92 : 0;
    const targetCasingOpacity = visible ? 0.46 : 0;
    const start = performance.now();

    const tick = (now) => {
      if (!this.map || !this.map.getLayer("commercial-aircraft-track-line")) {
        return;
      }
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      this.map.setPaintProperty("commercial-aircraft-track-line", "line-opacity", eased * targetLineOpacity);
      this.map.setPaintProperty("commercial-aircraft-track-casing", "line-opacity", eased * targetCasingOpacity);
      if (progress < 1) {
        this.commercialTrackAnimation = window.requestAnimationFrame(tick);
      }
    };

    this.commercialTrackAnimation = window.requestAnimationFrame(tick);
  }

  clearCommercialAircraftTrack() {
    if (this.commercialTrackAnimation) {
      window.cancelAnimationFrame(this.commercialTrackAnimation);
      this.commercialTrackAnimation = null;
    }
    if (!this.map || !this.map.isStyleLoaded()) {
      return;
    }
    const source = this.map.getSource(COMMERCIAL_TRACK_SOURCE_ID);
    if (source) {
      source.setData({ type: "FeatureCollection", features: [] });
    }
    COMMERCIAL_TRACK_LAYER_IDS.forEach((layerId) => {
      if (this.map?.getLayer(layerId)) {
        this.map.setPaintProperty(layerId, "line-opacity", 0);
      }
    });
  }

  formatCommercialAltitude(value) {
    if (!isFiniteNumber(value)) {
      return "-";
    }
    return `${Math.round(Number(value)).toLocaleString(this.language === "ko" ? "ko-KR" : "en-US")} m`;
  }

  formatCommercialSpeed(value) {
    if (!isFiniteNumber(value)) {
      return "-";
    }
    return `${Math.round(Number(value) * 3.6).toLocaleString(this.language === "ko" ? "ko-KR" : "en-US")} km/h`;
  }

  formatCommercialHeading(value) {
    if (!isFiniteNumber(value)) {
      return "-";
    }
    return `${Math.round(Number(value))} deg`;
  }

  formatCommercialTime(value) {
    if (!value) {
      return "-";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "-";
    }
    const formatted = new Intl.DateTimeFormat(this.language === "ko" ? "ko-KR" : "en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
      timeZone: "Asia/Seoul",
    }).format(date);
    return `${formatted} KST`;
  }

  async initMap() {
    const mapElement = this.container.querySelector("#dtam-simulation-map");
    if (!mapElement) {
      return;
    }

    try {
      const [maplibregl, metadata] = await Promise.all([ensureMapLibre(), this.loadTileMetadata()]);
      if (this.destroyed || !this.container.contains(mapElement)) {
        return;
      }

      const bounds = tileBounds(metadata);
      this.commercialAircraftMapEventsBound = false;
      this.uamVehicleMapEventsBound = false;
      this.map = new maplibregl.Map({
        container: mapElement,
        style: buildMapStyle(this.state.mapTheme, metadata),
        center: SEOUL_CENTER,
        zoom: INITIAL_ZOOM,
        minZoom: 6,
        maxZoom: Math.max(MAX_MAP_ZOOM, Number(metadata?.max_zoom ?? 14)),
        maxBounds: bounds,
        pitch: 0,
        bearing: 0,
        attributionControl: false,
      });

      this.map.once("load", () => {
        this.container.querySelector("[data-map-loading]")?.classList.add("is-hidden");
        this.addOperationalLayers();
        this.updateOperationalEnvironmentLayers();
        this.loadOperationalEnvironment();
        this.bindCommercialAircraftMapEvents();
        this.updateOperationalLayers();
        this.updateWindVisualization();
        this.renderUamVehicles();
        this.renderCommercialAircraft();
        this.map.once("idle", () => {
          this.updateOperationalEnvironmentLayers();
          this.renderUamVehicles();
        });
      });

      this.map.getCanvas().addEventListener("wheel", (event) => {
        this.handleAbnormalMapWheel(event);
      }, { passive: false });

      this.map.on("click", (event) => {
        if (this.handleAbnormalMapClick(event)) {
          return;
        }
        if (this.handleMissionMapClick(event)) {
          return;
        }
        const uamFeature = this.map.getLayer("uam-vehicle-hit-area")
          ? this.map.queryRenderedFeatures(event.point, { layers: ["uam-vehicle-hit-area"] })[0]
          : null;
        const uamVehicleId = uamFeature?.properties?.id;
        if (uamVehicleId) {
          this.selectUamVehicle(uamVehicleId);
          return;
        }
        const aircraftFeature = this.map.getLayer(COMMERCIAL_AIRCRAFT_LAYER_ID)
          ? this.map.queryRenderedFeatures(event.point, { layers: [COMMERCIAL_AIRCRAFT_LAYER_ID] })[0]
          : null;
        const aircraftId = aircraftFeature?.properties?.id;
        if (aircraftId) {
          this.selectCommercialAircraft(aircraftId);
          return;
        }
        this.closeCommercialAircraftPopup();
        if (this.handleOperationalEnvironmentMapClick(event)) {
          return;
        }
        if (!this.state.gustApplyMode) {
          return;
        }
        this.applyLocalWind(event.lngLat);
      });

      ["movestart", "zoomstart", "dragstart", "rotatestart", "pitchstart"].forEach((eventName) => {
        this.map.on(eventName, () => {
          this.snapUamVehicleMarkers();
          this.snapCommercialAircraftMarkers();
        });
      });
    } catch (error) {
      this.container.querySelector("[data-map-loading]")?.classList.add("is-hidden");
      this.status = "error";
      this.statusMessage = error.message;
      this.updateStatus();
    }
  }

  addOperationalLayers() {
    if (!this.map || !this.map.isStyleLoaded()) {
      return;
    }

    if (!this.map.getSource("weather-zone")) {
      this.map.addSource("weather-zone", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      this.map.addLayer({
        id: "weather-zone",
        type: "circle",
        source: "weather-zone",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 8, 50, 12, 180],
          "circle-color": "#54b8e8",
          "circle-opacity": ["get", "opacity"],
          "circle-blur": 0.75,
        },
      });
    }

    if (!this.map.getSource("gust-zone")) {
      this.map.addSource("gust-zone", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      this.map.addLayer({
        id: "gust-zone",
        type: "circle",
        source: "gust-zone",
        paint: {
          "circle-radius": 72,
          "circle-color": "#d84a42",
          "circle-opacity": 0.28,
          "circle-stroke-width": 1.2,
          "circle-stroke-color": "#ffffff",
          "circle-stroke-opacity": 0.68,
          "circle-blur": 0.42,
        },
      });
    }

    if (!this.map.getSource(ABNORMAL_ZONE_SOURCE_ID)) {
      this.map.addSource(ABNORMAL_ZONE_SOURCE_ID, {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      this.map.addLayer({
        id: ABNORMAL_ZONE_LAYER_ID,
        type: "circle",
        source: ABNORMAL_ZONE_SOURCE_ID,
        paint: {
          "circle-radius": 72,
          "circle-color": "#facc15",
          "circle-opacity": 0.18,
          "circle-stroke-width": 2,
          "circle-stroke-color": "#fef3c7",
          "circle-stroke-opacity": 0.86,
          "circle-blur": 0.26,
        },
      });
    }

    this.ensureCommercialAircraftTrackLayer();
    this.ensureUamVehicleTrackLayer();
    this.ensureOperationalEnvironmentLayers();
    this.ensureMissionRouteLayers();
    this.updateOperationalEnvironmentLayers();
    this.updateMissionRouteOverlay();
    this.raiseUamVehicleLayers();
  }

  setMapTheme() {
    if (!this.map) {
      return;
    }
    this.map.getContainer().className = `uatm-map theme-${this.state.mapTheme} maplibregl-map`;
    window.clearTimeout(this.overlayRestoreTimer);
    this.map.setStyle(buildMapStyle(this.state.mapTheme, this.tileMetadata || DEFAULT_TILE_METADATA));
    this.map.once("style.load", () => this.scheduleOverlayLayerRestore());
    this.map.once("idle", () => this.scheduleOverlayLayerRestore());
    this.scheduleOverlayLayerRestore();
  }

  scheduleOverlayLayerRestore(attempt = 0) {
    window.clearTimeout(this.overlayRestoreTimer);
    const delay = attempt === 0 ? 0 : Math.min(700, 90 + attempt * 90);
    this.overlayRestoreTimer = window.setTimeout(() => {
      this.overlayRestoreTimer = null;
      if (this.destroyed || !this.map) {
        return;
      }
      if (this.restoreMapOverlayLayers()) {
        return;
      }
      if (attempt < 10) {
        this.scheduleOverlayLayerRestore(attempt + 1);
      }
    }, delay);
  }

  restoreMapOverlayLayers() {
    if (!this.map || !this.map.isStyleLoaded()) {
      return false;
    }
    try {
      this.addOperationalLayers();
      this.updateOperationalEnvironmentLayers();
      this.updateOperationalLayers();
      this.updateMissionRouteOverlay();
      this.updateWindVisualization();
      this.renderUamVehicles();
      this.renderCommercialAircraft();
      return Boolean(
        this.map.getSource(ENV_LINK_SOURCE_ID)
          && this.map.getSource(ENV_CORRIDOR_SOURCE_ID)
          && this.map.getSource(ENV_VERTIPORT_SOURCE_ID)
          && this.map.getSource(MISSION_ROUTE_SOURCE_ID)
          && this.map.getSource(MISSION_ROUTE_POINT_SOURCE_ID)
          && this.map.getSource(ABNORMAL_ZONE_SOURCE_ID)
          && this.map.getLayer(ABNORMAL_ZONE_LAYER_ID)
          && ENV_LINK_LAYER_IDS.every((layerId) => this.map.getLayer(layerId))
          && ENV_POINT_LAYER_IDS.every((layerId) => this.map.getLayer(layerId))
          && MISSION_ROUTE_LAYER_IDS.every((layerId) => this.map.getLayer(layerId))
          && this.isOperationalEnvironmentDataRendered(),
      );
    } catch (error) {
      console.warn("Failed to restore map overlay layers after style change.", error);
      return false;
    }
  }

  updateOperationalLayers() {
    if (!this.map || !this.map.isStyleLoaded()) {
      return;
    }
    this.addOperationalLayers();

    const visualizationEnabled = this.state.weatherVisualizationEnabled;
    const weatherStrength = visualizationEnabled ? Math.min(1, this.state.precipitationIntensity + this.state.fogIntensity) : 0;
    const weatherSource = this.map.getSource("weather-zone");
    if (weatherSource) {
      weatherSource.setData({
        type: "FeatureCollection",
        features:
          weatherStrength > 0
            ? [
                {
                  type: "Feature",
                  properties: { opacity: Math.max(0.12, weatherStrength * 0.38) },
                  geometry: { type: "Point", coordinates: [127.02, 37.55] },
                },
              ]
            : [],
      });
    }

    const gustSource = this.map.getSource("gust-zone");
    if (gustSource) {
      gustSource.setData({
        type: "FeatureCollection",
        features: visualizationEnabled && this.state.gustEnabled
          ? [
              {
                type: "Feature",
                properties: {},
                geometry: { type: "Point", coordinates: [this.state.gustLon, this.state.gustLat] },
              },
            ]
          : [],
      });
      this.map.setPaintProperty("gust-zone", "circle-radius", [
        "interpolate",
        ["linear"],
        ["zoom"],
        8,
        Math.max(20, this.state.gustRadius / 90),
        12,
        Math.max(64, this.state.gustRadius / 16),
      ]);
      this.map.setPaintProperty(
        "gust-zone",
        "circle-color",
        this.state.windGrade === "serious" ? "#d84a42" : this.state.windGrade === "warning" ? "#d48a16" : "#1b8a5a",
      );
    }

    const abnormalSource = this.map.getSource(ABNORMAL_ZONE_SOURCE_ID);
    if (abnormalSource) {
      const hasCenter = Number.isFinite(Number(this.state.abnormalLat)) && Number.isFinite(Number(this.state.abnormalLon));
      abnormalSource.setData({
        type: "FeatureCollection",
        features: this.state.abnormalZoneVisible && hasCenter
          ? [
              {
                type: "Feature",
                properties: {},
                geometry: { type: "Point", coordinates: [Number(this.state.abnormalLon), Number(this.state.abnormalLat)] },
              },
            ]
          : [],
      });
      this.map.setPaintProperty(ABNORMAL_ZONE_LAYER_ID, "circle-radius", [
        "interpolate",
        ["linear"],
        ["zoom"],
        8,
        Math.max(18, Number(this.state.abnormalRadiusM || DEFAULT_STATE.abnormalRadiusM) / 95),
        12,
        Math.max(54, Number(this.state.abnormalRadiusM || DEFAULT_STATE.abnormalRadiusM) / 17),
      ]);
      this.map.setPaintProperty(
        ABNORMAL_ZONE_LAYER_ID,
        "circle-color",
        this.state.abnormalPickMode ? "#facc15" : "#fb7185",
      );
    }
  }

  updateRangeLabels() {
    const precipitation = this.container.querySelector("[data-precipitation-value]");
    const fog = this.container.querySelector("[data-fog-value]");
    const radius = this.container.querySelector("[data-gust-radius-value]");
    if (precipitation) {
      precipitation.textContent = pct(this.state.precipitationIntensity);
    }
    if (fog) {
      fog.textContent = pct(this.state.fogIntensity);
    }
    if (radius) {
      radius.textContent = `${(this.state.gustRadius / 1000).toFixed(1)} km`;
    }
  }

  buildScenarioFileName() {
    // 데모 시나리오 모드: Mission 의 데모 플랜 팩 키와 일치해야
    // 2001 수신 시 사전 작성 3001 들이 발행된다 (data/demo_plans/<stem>/).
    const demoFile = DEMO_SCENARIO_FILES[this.state.demoScenarioId];
    if (demoFile) {
      return demoFile;
    }
    // 사용자 정의 traffic: 선택한 FPL 폴더명을 scenarioFileName 으로 사용
    // (Mission 이 stem 처리하여 PlugIn/FlightScheduler/FPL/<stem>/ 을 찾는다).
    const trafficFolderName = String(this.state.trafficCustomMissionFolderName || "").trim();
    if (this.state.operationMode === "traffic" && this.state.trafficDensity === "customed" && trafficFolderName) {
      return `${trafficFolderName}.json`;
    }
    const now = new Date();
    const stamp = now.toISOString().replaceAll(":", "").replaceAll("-", "").replace(/\.\d{3}Z$/, "Z");
    return `scenarioSetup_${stamp}.json`;
  }

  buildFlightPlanRequestPayload(scenarioFileName = this.buildScenarioFileName()) {
    return {
      timestamp: new Date().toISOString(),
      scenarioFileName,
    };
  }

  buildExecutePayload(scenarioFileName = this.buildScenarioFileName()) {
    const stamp = new Date().toISOString().replaceAll(":", "").replaceAll("-", "").replace(/\.\d{3}Z$/, "Z");
    return {
      timestamp: new Date().toISOString(),
      simModeFileName: `simModeSetup_${stamp}.json`,
      simulationSetupFileName: `simulationSetup_${stamp}.json`,
      scenarioFileName,
      flightPlanFolderName: "latest",
      ...(this.state.demoScenarioId ? { scenarioId: this.state.demoScenarioId } : {}),
    };
  }

  validateDtamExecutionInputs() {
    if (this.isDemoScenarioLocked()) {
      // 데모 시나리오 모드 — 임무계획은 Mission 의 데모 플랜 팩이 발행하므로
      // 수동 임무 entries (출발/도착/경로) 검증을 건너뛴다. 제어방식만 확인.
      if (!CONTROLLER_MODES.includes(this.state.mainVehicleController)) {
        return { ok: false, message: this.t("missionIncomplete") };
      }
      return { ok: true, message: "" };
    }
    if (this.state.operationMode === "traffic" && this.state.trafficDensity === "customed") {
      // 사용자 정의 traffic — 임무계획은 FPL 폴더(백엔드 브릿지가 spawn 합성)가
      // 제공하므로 수동 entries 검증을 건너뛴다. 폴더 선택 + 제어방식만 확인.
      const trafficFolderName = String(this.state.trafficCustomMissionFolderName || "").trim();
      if (trafficFolderName && CONTROLLER_MODES.includes(this.state.mainVehicleController)) {
        return { ok: true, message: "" };
      }
    }
    if (this.state.operationMode !== "single") {
      return { ok: false, message: this.t("missionIncomplete") };
    }
    if (!CONTROLLER_MODES.includes(this.state.mainVehicleController)) {
      return { ok: false, message: this.t("missionIncomplete") };
    }
    const entries = Array.isArray(this.state.missionEntries) ? this.state.missionEntries : [];
    if (!entries.length) {
      return { ok: false, message: this.t("missionIncomplete") };
    }
    const allReady = entries.every((entry) => (
      entry
      && String(entry.departureName || "").trim()
      && String(entry.arrivalName || "").trim()
      && this.routeDataHasStartPoint(entry.routeData)
    ));
    if (!allReady) {
      return { ok: false, message: this.t("missionIncomplete") };
    }
    return { ok: true, message: "" };
  }

  modeSettingsSavedForCurrentPlan() {
    return this.state.modeSaveStatus === "ok"
      && this.savedModeSettingsKey
      && this.savedModeSettingsKey === this.buildExecutionPreparationKey();
  }

  validateDtamExecutionReadiness() {
    const validation = this.validateDtamExecutionInputs();
    if (!validation.ok) {
      return validation;
    }
    if (!this.modeSettingsSavedForCurrentPlan()) {
      return { ok: false, reason: "settings", message: this.t("missionSaveRequired") };
    }
    return { ok: true, message: "" };
  }

  routeDataHasStartPoint(routeData) {
    if (!routeData || typeof routeData !== "object") {
      return false;
    }
    const directPoint = routeData.departureTakeoff || routeData.departure_takeoff;
    if (this.isRouteGeoPoint(directPoint)) {
      return true;
    }
    const enRoute = Array.isArray(routeData.enRoute) ? routeData.enRoute : (Array.isArray(routeData.en_route) ? routeData.en_route : []);
    if (enRoute.some((segment) => (
      this.isRouteGeoPoint(segment?.startLLA)
      || this.isRouteGeoPoint(segment?.start_lla)
      || this.isRouteGeoPoint(segment?.start)
      || this.isRouteGeoPoint(segment?.endLLA)
      || this.isRouteGeoPoint(segment?.end_lla)
      || this.isRouteGeoPoint(segment?.end)
    ))) {
      return true;
    }
    return ["missionWaypoints", "mission_waypoints", "waypoints", "points"].some((key) => (
      Array.isArray(routeData[key]) && routeData[key].some((point) => this.isRouteGeoPoint(point))
    ));
  }

  isRouteGeoPoint(point) {
    return !!point && Number.isFinite(Number(point.lat)) && Number.isFinite(Number(point.lon));
  }

  async prepareDtamExecution(options = {}) {
    const payload = this.buildModePayload();
    if (options.skipUnrealLaunch) {
      payload.skipUnrealLaunch = true;
    }
    const result = await postJSON(DTAM_PREPARE_URL, {
      payload,
      ...(this.state.demoScenarioId ? { demoScenarioId: this.state.demoScenarioId } : {}),
    });
    if (result?.ok === false) {
      throw new Error(result.message || "DTAM preparation failed");
    }
    return result;
  }

  async launchDtamWorld() {
    const result = await postJSON(DTAM_LAUNCH_URL, {});
    if (result?.ok === false) {
      throw new Error(result.message || "DT World launch failed");
    }
    return result;
  }

  runtimeAirmobilityStatus(data = this.dtamRuntimeStatus) {
    return data?.airmobility && typeof data.airmobility === "object" ? data.airmobility : {};
  }

  runtimeRxCount(data, key) {
    const value = this.runtimeAirmobilityStatus(data)?.[key];
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : 0;
  }

  hasHighFidelityMission() {
    return Array.isArray(this.state.missionEntries)
      && this.state.missionEntries.some((entry) => normalizeDynamicsModel(entry?.dynamics) === "highFidelity");
  }

  vfdsGuiUrlFromResult(result) {
    const runtime = result?.runtime && typeof result.runtime === "object" ? result.runtime : {};
    const candidate = String(runtime.base_url || DTAM_VFDS_GUI_URL || "").trim();
    if (!candidate) {
      return DTAM_VFDS_GUI_URL;
    }
    try {
      const url = new URL(candidate, window.location.href);
      url.pathname = url.pathname && url.pathname !== "/" ? url.pathname : "/";
      return url.toString();
    } catch {
      return DTAM_VFDS_GUI_URL;
    }
  }

  openVfdsGuiWindow(options = {}) {
    if (!this.hasHighFidelityMission() && !options.force) {
      return null;
    }
    const url = String(options.url || DTAM_VFDS_GUI_URL || "").trim() || DTAM_VFDS_GUI_URL;
    const features = "popup=yes,width=1420,height=920";
    let guiWindow = null;
    try {
      if (this.vfdsGuiWindow && !this.vfdsGuiWindow.closed) {
        guiWindow = this.vfdsGuiWindow;
      } else {
        guiWindow = window.open("about:blank", "dtam-vfds-kp2a", features);
        this.vfdsGuiWindow = guiWindow;
      }
      if (!guiWindow) {
        if (!this.vfdsGuiOpenWarned || options.warn) {
          this.vfdsGuiOpenWarned = true;
          this.pushOperationLog(this.t("vfdsGuiBlocked"), { title: "VFDS", level: "warning" });
        }
        return null;
      }
      if (options.placeholder) {
        try {
          guiWindow.document.open();
          guiWindow.document.write(`
            <!doctype html>
            <html><head><title>VFDS/KP2A</title></head>
            <body style="margin:0;background:#0a0e1a;color:#e2e8f0;font:16px system-ui;display:grid;place-items:center;height:100vh;">
              <div style="text-align:center;line-height:1.6;">
                <strong style="color:#3b82f6;font-size:22px;">VFDS/KP2A GUI 준비 중</strong><br>
                <span>Operation Play가 서버 기동, 임무 전달, 시간 수신 상태를 연결하고 있습니다.</span>
              </div>
            </body></html>
          `);
          guiWindow.document.close();
        } catch {
          // Cross-origin or already navigated; navigation below will still work.
        }
      }
      if (options.navigate) {
        guiWindow.location.href = url;
      }
      try {
        guiWindow.focus();
      } catch {
        // Ignore focus failures.
      }
      if (options.log) {
        this.pushOperationLog(`${this.t("vfdsGuiOpening")} (${url})`, { title: "VFDS", level: "info" });
      }
      return guiWindow;
    } catch (error) {
      this.pushOperationLog(error.message || this.t("vfdsGuiBlocked"), { title: "VFDS", level: "warning" });
      return null;
    }
  }

  sleep(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, Number(ms) || 0));
  }

  async ensureVfdsRuntimeForCurrentPlan(options = {}) {
    if (!this.hasHighFidelityMission()) {
      const skipped = { ok: true, skipped: true, reason: "no highFidelity vehicle" };
      if (options.log) {
        this.pushOperationLog(this.t("vfdsSkipped"), { title: "VFDS", level: "info" });
      }
      return skipped;
    }
    const result = await postJSON(DTAM_VFDS_ENSURE_URL, {
      payload: this.buildModePayload(),
      ...(this.state.demoScenarioId ? { demoScenarioId: this.state.demoScenarioId } : {}),
    });
    if (result?.ok === false) {
      throw new Error(result?.runtime?.error || "VFDS/KP2A server is not ready");
    }
    if (options.log) {
      const runtime = result.runtime || {};
      const suffix = runtime.pid ? ` (PID ${runtime.pid})` : "";
      this.pushOperationLog(`${this.t("vfdsReady")}${suffix}`, { title: "VFDS", level: "success" });
    }
    if (options.openGui === true) {
      this.openVfdsGuiWindow({
        url: this.vfdsGuiUrlFromResult(result),
        navigate: true,
        log: Boolean(options.log),
      });
    }
    return result;
  }

  async waitForScheduledFlightReady(options = {}) {
    const baselineRx3001 = Number(options.baselineRx3001 || 0);
    const timeoutMs = Number(options.timeoutMs || SCHEDULED_FLIGHT_WAIT_MS);
    const deadline = Date.now() + timeoutMs;
    let lastData = null;
    while (Date.now() <= deadline) {
      try {
        lastData = await this.fetchDtamRuntimeStatus();
        const rx = this.runtimeRxCount(lastData, "rx_3001_count");
        if (rx > baselineRx3001) {
          return { ok: true, data: lastData, rx };
        }
      } catch {
        // Keep polling; modules may still be starting.
      }
      await this.sleep(SCHEDULED_FLIGHT_POLL_MS);
    }
    return { ok: false, data: lastData, rx: this.runtimeRxCount(lastData, "rx_3001_count") };
  }

  async waitForExecuteReady(options = {}) {
    const baselineRx2002 = Number(options.baselineRx2002 || 0);
    const timeoutMs = Number(options.timeoutMs || DTAM_EXECUTE_READY_WAIT_MS);
    const deadline = Date.now() + timeoutMs;
    let lastData = null;
    while (Date.now() <= deadline) {
      try {
        lastData = await this.fetchDtamRuntimeStatus();
        const rx = this.runtimeRxCount(lastData, "rx_2002_count");
        if (rx > baselineRx2002) {
          return { ok: true, data: lastData, rx };
        }
      } catch {
        // Keep polling; 2002 may still be propagating through StateServer.
      }
      await this.sleep(SCHEDULED_FLIGHT_POLL_MS);
    }
    return { ok: false, data: lastData, rx: this.runtimeRxCount(lastData, "rx_2002_count") };
  }

  logDtamPreparationResult(prepareResult) {
    const preparedVehicleCount = Number(prepareResult?.vehicle_count || 0);
    if (preparedVehicleCount > 0) {
      const dynamicsSummary = Object.entries(prepareResult?.dynamics_by_aircraft || {})
        .map(([aircraftId, dynamics]) => `${aircraftId}:${dynamics}`)
        .join(", ");
      this.pushOperationLog(
        `Unreal spawn settings applied: ${preparedVehicleCount} vehicle(s)${dynamicsSummary ? ` (${dynamicsSummary})` : ""}`,
        { title: "DT World", level: "success" },
      );
    }
    this.pushOperationLog(this.t("vehicleReady"), { title: "Vehicle", level: "success" });
    if (prepareResult?.vfds?.skipped) {
      this.pushOperationLog(this.t("vfdsSkipped"), { title: "VFDS", level: "info" });
    } else if (prepareResult?.vfds?.ok) {
      this.pushOperationLog(this.t("vfdsReady"), { title: "VFDS", level: "success" });
    }
  }

  async launchDtamWorldOnly() {
    const seq = ++this.sendSeq;
    this.status = "sending";
    this.statusMessage = this.t("dtamLaunching");
    this.state.connectionStatus = "connecting";
    this.clearMissionStatus();
    this.syncUi();
    this.updateStatus();

    try {
      const validation = this.validateDtamExecutionInputs();
      if (validation.ok) {
        await this.refreshMissionRoutesForExecution();
        this.pushOperationLog(this.t("dtamPreparing"), { title: this.t("dtamExecute"), level: "info" });
        const prepareResult = await this.prepareDtamExecution({ skipUnrealLaunch: false });
        this.executionPreparationKey = this.buildExecutionPreparationKey();
        this.logDtamPreparationResult(prepareResult);
      } else {
        await this.launchDtamWorld();
        try {
          await this.ensureVfdsRuntimeForCurrentPlan({ log: true, optional: true });
        } catch (vfdsError) {
          this.pushOperationLog(vfdsError.message || "VFDS readiness check skipped", {
            title: "VFDS",
            level: "warning",
          });
        }
      }
      if (this.destroyed || seq !== this.sendSeq) {
        return;
      }
      this.state.connectionStatus = "connected";
      this.status = "ok";
      this.statusMessage = this.t("dtamWorldLaunchOk");
      this.refreshDtamRuntimeStatus();
      this.pushOperationLog(this.t("dtamWorldLaunchOk"), {
        title: this.t("dtamExecute"),
        level: "success",
      });
      this.syncUi();
      this.updateStatus();
    } catch (error) {
      if (this.destroyed || seq !== this.sendSeq) {
        return;
      }
      this.state.connectionStatus = "disconnected";
      this.status = "error";
      this.statusMessage = error.message;
      this.pushOperationLog(error.message, {
        title: this.t("operationAlert"),
        level: "error",
      });
      this.syncUi();
      this.updateStatus();
    }
  }

  async requestFlightPlan(scenarioFileName) {
    const result = await postJSON(FLIGHT_PLAN_REQUEST_URL, { payload: this.buildFlightPlanRequestPayload(scenarioFileName) });
    if (result?.sent === false || (Array.isArray(result?.errors) && result.errors.length > 0)) {
      throw new Error(result.errors?.join(", ") || "2001 send rejected");
    }
    return result;
  }

  async sendExecuteCommand(scenarioFileName) {
    const result = await postJSON(DTAM_EXECUTE_URL, { payload: this.buildExecutePayload(scenarioFileName) });
    if (result?.sent === false || (Array.isArray(result?.errors) && result.errors.length > 0)) {
      throw new Error(result.errors?.join(", ") || "2002 send rejected");
    }
    return result;
  }

  async prepareAndArmDtamExecution(options = {}) {
    const readiness = this.validateDtamExecutionReadiness();
    if (!readiness.ok) {
      throw new Error(readiness.message);
    }

    const preparationKey = this.buildExecutionPreparationKey();
    if (
      options.allowReuse
      && this.executionArmKey === preparationKey
      && this.state.connectionStatus === "connected"
    ) {
      return { reused: true, scenarioFileName: options.scenarioFileName || "" };
    }

    const scenarioFileName = options.scenarioFileName || this.buildScenarioFileName();
    const baselineStatus = await this.fetchDtamRuntimeStatus().catch(() => null);
    const runtimeAlreadyRunning = Boolean(
      baselineStatus?.running
      || baselineStatus?.airsim_rpc_open
      || baselineStatus?.unreal?.running
      || baselineStatus?.airsim?.connected
    );
    const baselineRx3001 = this.runtimeRxCount(baselineStatus, "rx_3001_count");
    const baselineRx2002 = this.runtimeRxCount(baselineStatus, "rx_2002_count");
    const worldAlreadyPrepared = (
      options.allowReuse
      && this.executionPreparationKey === preparationKey
      && (this.state.connectionStatus === "connected" || runtimeAlreadyRunning)
    );
    // If DT World was already prepared by the explicit DT World button, do not
    // run the route-refresh -> prepare-execution(false) path from Play.  That
    // path relaunches Unreal; Play should only arm 3001/2002 and start time.
    if (!worldAlreadyPrepared) {
      await this.refreshMissionRoutesForExecution();
    }
    const refreshedPreparationKey = this.buildExecutionPreparationKey();

    const alreadyPrepared = worldAlreadyPrepared || (
      options.allowReuse
      && this.executionPreparationKey === refreshedPreparationKey
      && (this.state.connectionStatus === "connected" || runtimeAlreadyRunning)
    );
    if (!alreadyPrepared) {
      // Playback must prepare the mission BEFORE launching/relaunching DT World.
      // AirSim only creates the Vehicles listed in settings.json at startup.  The
      // previous flow launched the Visualization baseline first and then wrote the
      // mission settings with skipUnrealLaunch=true, so Unreal kept the old single
      // baseline pawn and multi-vehicle/mixed-dynamics plans never appeared.
      this.pushOperationLog(this.t("dtamPreparing"), { title: this.t("dtamExecute"), level: "info" });
      const skipUnrealLaunch = Boolean(options.allowReuse && runtimeAlreadyRunning);
      if (skipUnrealLaunch) {
        this.pushOperationLog(
          "Existing DT World runtime detected; Play will not relaunch Unreal.",
          { title: "DT World", level: "info" },
        );
      }
      const prepareResult = await this.prepareDtamExecution({ skipUnrealLaunch });
      this.logDtamPreparationResult(prepareResult);
    } else {
      this.pushOperationLog("Using existing DT World mission spawn settings.", { title: "DT World", level: "info" });
    }
    this.executionPreparationKey = refreshedPreparationKey;
    this.state.connectionStatus = "connected";
    this.syncUi();

    await this.sendModeSettings({ throwOnError: true, applyControl: false });
    this.pushOperationLog(this.t("flightPlanWaiting"), { title: "3001", level: "info" });
    let scheduledReady;
    if (this.isDemoScenarioLocked()) {
      // 데모 시나리오: 2001 이 (fallback 이 아닌) 주 경로 — Mission 이
      // scenarioFileName 으로 데모 플랜 팩을 감지해 3001 을 일괄 발행한다.
      this.pushOperationLog(`데모 플랜 팩 요청 (${scenarioFileName})`, { title: "2001", level: "info" });
      await this.requestFlightPlan(scenarioFileName);
      scheduledReady = await this.waitForScheduledFlightReady({
        baselineRx3001,
        timeoutMs: SCHEDULED_FLIGHT_WAIT_MS,
      });
    } else {
      scheduledReady = await this.waitForScheduledFlightReady({ baselineRx3001 });
      if (!scheduledReady.ok) {
        this.pushOperationLog(this.t("flightPlanFallback"), { title: "2001", level: "warning" });
        await this.requestFlightPlan(scenarioFileName);
        scheduledReady = await this.waitForScheduledFlightReady({
          baselineRx3001,
          timeoutMs: SCHEDULED_FLIGHT_WAIT_MS,
        });
      }
    }
    if (!scheduledReady.ok) {
      throw new Error("3001 ScheduledFlight was not registered in VehicleModule");
    }
    this.pushOperationLog(this.t("flightPlanReady"), { title: "3001", level: "success" });
    await this.sendExecuteCommand(scenarioFileName);
    const executeReady = await this.waitForExecuteReady({ baselineRx2002 });
    if (executeReady.ok) {
      this.pushOperationLog(this.t("executeReady"), { title: "2002", level: "success" });
    }
    this.executionArmKey = this.buildExecutionPreparationKey();
    return { reused: false, scenarioFileName };
  }

  async startDtamExecutionFlow() {
    const readiness = this.validateDtamExecutionReadiness();
    if (!readiness.ok) {
      this.status = "error";
      this.statusMessage = readiness.message;
      this.state.connectionStatus = "disconnected";
      this.setMissionStatus(readiness.message, "error");
      if (readiness.reason === "settings") {
        this.state.modeSaveStatus = "error";
        this.state.modeSaveMessage = readiness.message;
      }
      this.pushOperationLog(readiness.message, {
        title: this.t("operationAlert"),
        level: "error",
      });
      this.syncUi();
      this.updateStatus();
      return;
    }

    const seq = ++this.sendSeq;
    this.status = "sending";
    this.statusMessage = this.t("planning");
    this.state.connectionStatus = "connecting";
    this.clearMissionStatus();
    this.syncUi();
    this.updateStatus();
    let prepared = false;
    try {
      const scenarioFileName = this.buildScenarioFileName();
      await this.prepareAndArmDtamExecution({ scenarioFileName, allowReuse: false });
      prepared = true;
      if (this.destroyed || seq !== this.sendSeq) {
        return;
      }
      this.state.connectionStatus = "connected";
      this.syncUi();
      this.refreshDtamRuntimeStatus();
      this.pushOperationLog(this.t("dtamFlowOk"), {
        title: this.t("dtamExecute"),
        level: "success",
      });
      this.status = "ok";
      this.statusMessage = this.t("dtamFlowOk");
      this.updateStatus();
    } catch (error) {
      if (this.destroyed || seq !== this.sendSeq) {
        return;
      }
      if (!prepared) {
        this.state.connectionStatus = "disconnected";
        this.syncUi();
      }
      this.pushOperationLog(error.message, {
        title: this.t("operationAlert"),
        level: "error",
      });
      this.status = "error";
      this.statusMessage = error.message;
      this.updateStatus();
    }
  }

  buildModePayload() {
    const operationMode = OPERATION_MODES.includes(this.state.operationMode) ? this.state.operationMode : "single";
    const payload = {
      timestamp: new Date().toISOString(),
      operationMode,
    };

    const missionEntries = (this.state.missionEntries || []).map((entry) => {
      const departureTime = this.missionDepartureTime(entry);
      const mission = {
        aircraftName: entry.aircraftName || "",
        departureTime,
        std: departureTime,
        departureName: entry.departureName || "",
        arrivalName: entry.arrivalName || "",
        routeData: entry.routeData || null,
        vehicleSimType: {
          dynamics: normalizeDynamicsModel(entry.dynamics),
          mainVehicleController: CONTROLLER_MODES.includes(entry.controllerOverride)
            ? entry.controllerOverride
            : (CONTROLLER_MODES.includes(this.state.mainVehicleController) ? this.state.mainVehicleController : "Autopilot"),
        },
      };
      return mission;
    });

    if (operationMode === "single") {
      payload.singleFlight = {
        vehicleSimType: {
          dynamics: normalizeDynamicsModel(this.state.dynamics),
          mainVehicleController: CONTROLLER_MODES.includes(this.state.mainVehicleController)
            ? this.state.mainVehicleController
            : "Autopilot",
        },
        missionPlanning: {
          activeMissionId: this.state.activeMissionId || "",
          missions: missionEntries,
        },
      };
    } else {
      const trafficDensity = TRAFFIC_DENSITIES.includes(this.state.trafficDensity) ? this.state.trafficDensity : "middle";
      payload.trafficSim = {
        density: trafficDensity,
        customMissionFolder: trafficDensity === "customed" ? (this.state.trafficCustomMissionFolderName || "") : "",
        customMissionAction: trafficDensity === "customed" ? (this.state.trafficCustomMissionAction || "") : "",
      };
    }

    return payload;
  }

  buildExecutionPreparationKey() {
    const missionEntries = (this.state.missionEntries || []).map((entry) => {
      const departureTime = this.missionDepartureTime(entry);
      return {
        aircraftName: entry.aircraftName || "",
        departureTime,
        std: departureTime,
        departureName: entry.departureName || "",
        arrivalName: entry.arrivalName || "",
        routeData: entry.routeData || null,
        dynamics: normalizeDynamicsModel(entry.dynamics),
        controllerOverride: CONTROLLER_MODES.includes(entry.controllerOverride) ? entry.controllerOverride : "",
      };
    });
    return JSON.stringify({
      operationMode: OPERATION_MODES.includes(this.state.operationMode) ? this.state.operationMode : "single",
      dynamics: normalizeDynamicsModel(this.state.dynamics),
      mainVehicleController: CONTROLLER_MODES.includes(this.state.mainVehicleController)
        ? this.state.mainVehicleController
        : "",
      activeMissionId: this.state.activeMissionId || "",
      demoScenarioId: this.state.demoScenarioId || "",
      missions: missionEntries,
    });
  }

  async ensureDtamExecutionArmedForPlayback() {
    if (this.state.playState !== "play") {
      return;
    }

    const readiness = this.validateDtamExecutionReadiness();
    if (!readiness.ok) {
      this.setMissionStatus(readiness.message, "error");
      if (readiness.reason === "settings") {
        this.state.modeSaveStatus = "error";
        this.state.modeSaveMessage = readiness.message;
      }
      this.syncUi();
      throw new Error(readiness.message);
    }

    const preparationKey = this.buildExecutionPreparationKey();
    if (this.executionArmKey === preparationKey && this.state.connectionStatus === "connected") {
      return;
    }

    this.statusMessage = this.t("planning");
    if (this.executionPreparationKey !== preparationKey || this.state.connectionStatus !== "connected") {
      this.state.connectionStatus = "connecting";
    }
    this.syncUi();
    this.updateStatus();

    try {
      await this.prepareAndArmDtamExecution({ allowReuse: true });
    } catch (error) {
      this.executionPreparationKey = "";
      this.executionArmKey = "";
      this.state.connectionStatus = "disconnected";
      this.syncUi();
      throw error;
    }
  }

  async sendModeSettings(options = {}) {
    this.state.modeSaveStatus = "sending";
    this.state.modeSaveMessage = "";
    this.syncUi();

    try {
      const validation = this.validateDtamExecutionInputs();
      if (!validation.ok) {
        const message = this.t("modeSaveRequiresMission");
        this.setMissionStatus(message, "error");
        throw new Error(message);
      }
      const result = await postJSON("/api/v1/icd/1001/send", { payload: this.buildModePayload() });
      if (result?.sent === false || (Array.isArray(result?.errors) && result.errors.length > 0)) {
        throw new Error(result.errors?.join(", ") || "1001 send rejected");
      }
      let controlResult = null;
      if (options.applyControl !== false) {
        controlResult = await postJSON(DTAM_APPLY_CONTROL_URL, {
          payload: this.buildModePayload(),
          ...(this.state.demoScenarioId ? { demoScenarioId: this.state.demoScenarioId } : {}),
        });
        if (controlResult?.ok === false) {
          throw new Error(controlResult.message || "controller apply failed");
        }
      }
      if (this.destroyed) {
        return;
      }
      this.state.modeSaveStatus = "ok";
      this.state.modeSaveMessage = "";
      this.savedModeSettingsKey = this.buildExecutionPreparationKey();
      this.clearMissionStatus();
      this.syncUi();
      return { icd: result, control: controlResult };
    } catch (error) {
      if (this.destroyed) {
        return;
      }
      this.state.modeSaveStatus = "error";
      this.state.modeSaveMessage = error.message;
      this.syncUi();
      if (options.throwOnError) {
        throw error;
      }
      return null;
    }
  }

  buildPayload() {
    this.syncSimulationClockToState();
    const precipitationType = PRECIPITATION_TYPES.includes(this.state.precipitationType) ? this.state.precipitationType : "none";
    const simulationStartTime = normalizeMissionDepartureTime(
      this.state.simulationStartTime,
      DEFAULT_SIMULATION_START_TIME,
    );
    const simulationTime = this.state.playState === "reset"
      ? simulationStartTime
      : normalizeMissionDepartureTime(this.state.simulationTime, simulationStartTime);
    const payload = {
      timestamp: new Date().toISOString(),
      playbackSpeed: SPEEDS.includes(this.state.playbackSpeed) ? this.state.playbackSpeed : 1,
      playState: PLAY_STATES.includes(this.state.playState) ? this.state.playState : "pause",
      simulationStartTime,
      simulationTime,
      simTimeOfDay: simulationTime,
      simSecondsOfDay: missionTimeToSeconds(simulationTime),
      timeSource: "operation-gui",
      weatherEffect: {
        precipitation: {
          type: precipitationType,
          intensity: precipitationType === "none" ? 0 : step01(normalizeNumber(this.state.precipitationIntensity, 0, 1, 0)),
        },
        fog: {
          intensity: step01(normalizeNumber(this.state.fogIntensity, 0, 1, 0)),
        },
      },
      wind: {
        grade: WIND_GRADES.includes(this.state.windGrade) ? this.state.windGrade : "normal",
      },
    };

    if (this.state.gustEnabled) {
      payload.wind.gust = {
        lat: normalizeNumber(this.state.gustLat, -90, 90, DEFAULT_STATE.gustLat),
        lon: normalizeNumber(this.state.gustLon, -180, 180, DEFAULT_STATE.gustLon),
        radius: normalizeNumber(this.state.gustRadius, 0, 50000, DEFAULT_STATE.gustRadius),
      };
    }

    // Vehicle 측 바람 모델 (uamodt standalone_weather) 파라미터 — 그쪽 wire 키와 1:1.
    // grade → preset 매핑: normal→good, warning→fair, serious→bad.
    const simSeconds = payload.simSecondsOfDay || 0;
    const month = new Date().getMonth() + 1;
    payload.wind.weather = {
      preset: WIND_GRADE_TO_WEATHER_PRESET[payload.wind.grade] || "good",
      season: month >= 3 && month <= 5 ? "spring" : month >= 6 && month <= 8 ? "summer" : month >= 9 && month <= 11 ? "autumn" : "winter",
      localHour: Math.min(23.999, Math.max(0, simSeconds / 3600)),
      seed: 0,
      includeGust: Boolean(this.state.gustEnabled),
      t: simSeconds,
    };
    return payload;
  }

  scheduleSend(options = {}) {
    window.clearTimeout(this.sendTimer);
    const delay = options.immediate ? 0 : normalizeNumber(options.delayMs, 0, 5000, ICD_SEND_DEBOUNCE_MS);
    this.status = "ready";
    this.updateStatus();
    const sendOptions = {
      skipExecutionArm: Boolean(options.skipExecutionArm),
    };
    this.sendTimer = window.setTimeout(() => this.sendCurrentPayload(sendOptions), delay);
  }

  scheduleWeatherIcdSend(options = {}) {
    this.scheduleSend({
      immediate: Boolean(options.immediate),
      delayMs: WEATHER_ICD_SEND_DEBOUNCE_MS,
      // Weather/wind changes are MSG 1002 runtime control and must not be
      // blocked by mission-planning/save guards.  The DTAM server will forward
      // the ICD to VisualizationModule whenever it is connected.
      skipExecutionArm: true,
    });
  }

  async sendCurrentPayload(options = {}) {
    const seq = options.keepSeq || ++this.sendSeq;
    this.status = "sending";
    this.statusMessage = "";
    this.updateStatus();
    try {
      if (!options.skipExecutionArm) {
        await this.ensureDtamExecutionArmedForPlayback();
      }
      const result = await postJSON("/api/v1/icd/1002/send", { payload: this.buildPayload() });
      if (result?.sent === false || (Array.isArray(result?.errors) && result.errors.length > 0)) {
        throw new Error(result.errors?.join(", ") || "1002 send rejected");
      }
      if (this.destroyed || seq !== this.sendSeq) {
        return;
      }
      this.status = "ok";
      this.statusMessage = "";
      this.updateStatus();
      return result;
    } catch (error) {
      if (this.destroyed || seq !== this.sendSeq) {
        return;
      }
      this.status = "error";
      this.statusMessage = error.message;
      this.updateStatus();
      if (options.throwOnError) {
        throw error;
      }
      return null;
    }
  }

  statusLabel() {
    if (this.status === "sending") {
      return this.t("syncSending");
    }
    if (this.status === "ok") {
      return this.t("syncOk");
    }
    if (this.status === "error") {
      return this.t("syncError");
    }
    return this.t("syncReady");
  }

  updateStatus() {
    const wrapper = this.container.querySelector("[data-sync-status]");
    const label = this.container.querySelector("[data-sync-label]");
    const detail = this.container.querySelector("[data-sync-detail]");
    if (wrapper) {
      wrapper.dataset.status = this.status;
    }
    if (label) {
      label.textContent = this.statusLabel();
    }
    if (detail) {
      detail.textContent = this.statusMessage || "";
    }
    this.container.querySelectorAll(".scenario-status-row strong").forEach((element) => {
      if (element.previousElementSibling?.textContent === this.t("autoSend")) {
        element.textContent = this.statusLabel();
      }
    });
  }
}

export function renderSimulationWorkspace(container, options = {}) {
  return new SimulationWorkspace(container, options).mount();
}
