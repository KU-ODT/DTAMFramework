import { postJSON } from "../../api/client.js";
import { WEATHER_MAX_POINTS, WEATHER_STEP_METERS, WeatherLayer, WindModel, latToY, lonToX, normalizeWindPreset } from "./wind-layer.js";

const SPEEDS = [1, 2, 4, 8];
const PLAY_STATES = ["play", "pause", "reset"];
const PRECIPITATION_TYPES = ["none", "rainy", "snow"];
const WIND_GRADES = ["normal", "warning", "serious"];
const MAP_THEME_KEYS = ["dark", "light"];
const PANEL_MODES = ["mode", "weather"];
const OPERATION_MODES = ["single", "traffic", "integrated"];
const DYNAMICS_MODELS = ["simple", "multirotor", "highFidelity"];
const CONTROLLER_MODES = ["Joystick", "Keyboard", "Autopilot"];
const TRAFFIC_SCENARIOS = ["low", "middle", "high", "customed"];
const SEOUL_CENTER = [126.978, 37.566];
const INITIAL_ZOOM = 10.85;
const MAX_MAP_ZOOM = 18;
const TILE_METADATA_URL = "/api/v1/tiles/metadata";
const SERVER_TIME_URL = "/api/v1/system/time";
const COMMERCIAL_TRAFFIC_URL = "/api/v1/traffic/commercial?region=korea";
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
  precipitationType: "none",
  precipitationIntensity: 0,
  fogIntensity: 0,
  weatherVisualizationEnabled: false,
  windGrade: "normal",
  operationMode: "integrated",
  dynamics: "simple",
  mainVehicleController: "Autopilot",
  trafficScenario: "middle",
  modeSaveStatus: "idle",
  modeSaveMessage: "",
  gustEnabled: false,
  gustApplyMode: false,
  gustLat: 37.56,
  gustLon: 126.98,
  gustRadius: 1200,
  mapTheme: "dark",
  activePanel: "weather",
  panelOpen: false,
  commercialTrafficEnabled: false,
  commercialTrafficLoading: false,
  commercialTrafficCount: 0,
  commercialTrafficError: "",
  commercialTrafficSource: "",
};

const COPY = {
  en: {
    back: "Back",
    title: "Simulation Monitoring",
    mapLoading: "Loading map",
    mapLoadingSub: "Connecting Korea MBTiles...",
    syncReady: "1002 Ready",
    syncSending: "1002 Sending",
    syncOk: "1002 Confirmed",
    syncError: "1002 Error",
    play: "Play",
    pause: "Pause",
    reset: "Reset",
    playback: "Playback",
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
    integrated: "Integrated",
    singleDescription: "One primary aircraft uses the selected dynamics model.",
    trafficDescription: "Multiple UAM flights are simulated as traffic flow.",
    integratedDescription: "One primary aircraft runs with surrounding simulated traffic.",
    vehicleSimulation: "Vehicle Simulation",
    dynamicsModel: "Dynamics model",
    aircraftController: "Aircraft controller",
    trafficScenario: "Traffic density",
    simple: "Simple",
    multirotor: "Multirotor",
    highFidelity: "High Fidelity",
    low: "Low",
    middle: "Middle",
    high: "High",
    customed: "Custom",
    saveSettings: "Save Settings",
    modeSaveIdle: "Ready to save",
    modeSaveSending: "Saving...",
    modeSaveOk: "Mode saved",
    modeSaveError: "Save failed",
  },
  ko: {
    back: "돌아가기",
    title: "시뮬레이션 모니터링",
    mapLoading: "지도 로딩 중",
    mapLoadingSub: "korea.mbtiles 타일 연결 중...",
    syncReady: "1002 대기",
    syncSending: "1002 전송 중",
    syncOk: "1002 확정",
    syncError: "1002 오류",
    play: "재생",
    pause: "정지",
    reset: "초기화",
    playback: "재생 제어",
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
    integrated: "통합 비행",
    singleDescription: "주 비행체 1대를 선택한 동역학 모델로 운용합니다.",
    trafficDescription: "다수 UAM 비행을 항공 교통 흐름으로 모사합니다.",
    integratedDescription: "주 비행체 1대와 주변 교통 흐름을 함께 모사합니다.",
    vehicleSimulation: "비행체 시뮬레이션",
    dynamicsModel: "동역학 모델",
    aircraftController: "비행체 제어방식",
    trafficScenario: "교통 밀도",
    simple: "기본",
    multirotor: "멀티로터",
    highFidelity: "고정밀",
    low: "낮음",
    middle: "보통",
    high: "높음",
    customed: "사용자 정의",
    saveSettings: "설정 저장",
    modeSaveIdle: "저장 대기",
    modeSaveSending: "저장 중...",
    modeSaveOk: "모드 저장 완료",
    modeSaveError: "저장 실패",
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

const MAP_PALETTES = {
  dark: {
    background: "#04466c",
    tileLand: "#071b27",
    landcover: "#0f2b32",
    landuse: "#12332e",
    park: "#184a39",
    water: "#0a5a82",
    waterLine: "#1789bd",
    boundary: "#5f7187",
    roadCasing: "#121a25",
    road: "#607285",
    roadMajor: "#9bb4c9",
    building: "#2a3748",
    label: "#d9e5ef",
    labelHalo: "#07111c",
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

function step01(value) {
  return Math.round(Number(value) * 10) / 10;
}

function pct(value) {
  return `${Math.round(Number(value) * 100)}%`;
}

function isFiniteNumber(value) {
  return Number.isFinite(Number(value));
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
    integratedMode: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3 18 8.5 12 14 6 8.5 12 3Z" />
        <path d="M6 12.5 12 18 18 12.5" />
        <circle cx="12" cy="8.5" r="1.6" />
      </svg>
    `,
    weather: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7.2 15.8h9.4a3.5 3.5 0 0 0 .4-7 5.1 5.1 0 0 0-9.6-1.3A4.2 4.2 0 0 0 7.2 15.8Z" />
        <path d="M8 19h.01M12 19h.01M16 19h.01" />
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
    layers: [
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
    this.state = { ...DEFAULT_STATE };
    this.tileMetadata = null;
    this.map = null;
    this.windModel = null;
    this.windLayer = null;
    this.sendTimer = null;
    this.serverTimeTimer = null;
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
    this.sendSeq = 0;
    this.destroyed = false;
    this.status = "ready";
    this.statusMessage = "";
    this.serverTimeText = "-";
  }

  mount() {
    this.destroyed = false;
    this.render();
    this.bindControls();
    this.initMap();
    this.startServerTime();
    this.scheduleSend({ immediate: true });
    return {
      updateLanguage: (language) => this.updateLanguage(language),
      destroy: () => this.destroy(),
    };
  }

  updateLanguage(language) {
    this.language = normalizeLanguage(language);
    this.windLayer?.stop();
    this.windLayer = null;
    this.windModel = null;
    this.clearCommercialAircraftOverlay();
    if (this.map) {
      this.map.remove();
      this.map = null;
    }
    this.commercialAircraftMapEventsBound = false;
    this.render();
    this.bindControls();
    this.initMap();
    this.updateStatus();
  }

  destroy() {
    this.destroyed = true;
    window.clearTimeout(this.sendTimer);
    window.clearInterval(this.serverTimeTimer);
    window.clearInterval(this.commercialTrafficTimer);
    this.clearCommercialAircraftOverlay();
    this.windLayer?.stop();
    this.windLayer = null;
    this.windModel = null;
    if (this.map) {
      this.map.remove();
      this.map = null;
    }
    this.container.replaceChildren();
  }

  t(key) {
    return COPY[this.language][key] || COPY.en[key] || key;
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

  async refreshServerTime() {
    try {
      const response = await fetch(SERVER_TIME_URL, { headers: { Accept: "application/json" }, cache: "no-store" });
      if (!response.ok) {
        throw new Error(`server time ${response.status}`);
      }
      const data = await response.json();
      this.serverTimeText = data.display || data.iso || "-";
    } catch {
      this.serverTimeText = "-";
    }
    this.container.querySelector("[data-server-time]")?.replaceChildren(document.createTextNode(this.serverTimeText));
  }

  startServerTime() {
    window.clearInterval(this.serverTimeTimer);
    this.refreshServerTime();
    this.serverTimeTimer = window.setInterval(() => this.refreshServerTime(), 5000);
  }

  panelTitle() {
    if (this.state.activePanel === "mode") {
      return this.t("modePanel");
    }
    return this.t("weatherPanel");
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

        <div id="sim-status-board" class="sim-status-board">
          <strong>${this.t("statusBoard")}</strong>
          <span>${this.t("noTrafficData")}</span>
        </div>

        <div id="left-controls" class="panel panel-left">
          <button type="button" class="ui-btn ui-btn-icon" title="${this.t("modePanel")}" data-panel-toggle="mode">
            ${simIcon("mode")}
          </button>
          <button type="button" class="ui-btn ui-btn-icon" title="${this.t("weatherPanel")}" data-panel-toggle="weather">
            ${simIcon("weather")}
          </button>
        </div>

        <div id="bottom-controls" class="panel panel-bottom-left">
          <button id="playback-toggle" type="button" class="ui-btn ui-btn-icon" title="${this.t("playback")}" data-action="toggle-playback">
            ${simIcon("playback")}
          </button>
          <div id="playback-panel" class="playback-panel is-open" aria-hidden="false">
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

        ${this.renderCommercialTrafficPanel()}

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
    return `
      <button type="button" class="playback-btn playback-btn-play ${this.state.playState === "play" ? "is-active" : ""}" title="${this.t("play")}" data-play-state="play"></button>
      <div class="playback-speed-group">
        <button type="button" class="playback-btn playback-btn-fast" title="${this.t("speed")}" data-action="toggle-speed"></button>
        <div class="playback-speed-menu" role="menu" aria-hidden="true">
          ${SPEEDS.map((speed) => `
            <button type="button" class="playback-speed-option ${this.state.playbackSpeed === speed ? "is-active" : ""}" data-speed="${speed}" role="menuitem">x${speed}</button>
          `).join("")}
        </div>
      </div>
      <button type="button" class="playback-btn playback-btn-pause ${this.state.playState === "pause" ? "is-active" : ""}" title="${this.t("pause")}" data-play-state="pause"></button>
      <button type="button" class="playback-btn playback-btn-reset ${this.state.playState === "reset" ? "is-active" : ""}" title="${this.t("reset")}" data-play-state="reset"></button>
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

  operationModeDescription(mode = this.state.operationMode) {
    if (mode === "single") {
      return this.t("singleDescription");
    }
    if (mode === "traffic") {
      return this.t("trafficDescription");
    }
    return this.t("integratedDescription");
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

  renderOperationModeSection() {
    return `
      <div class="scenario-section scenario-section-tab mode-setup-section" data-panel-section="mode">
        <div class="scenario-title">${this.t("modeSetup")}</div>
        <div class="mode-option-grid">
          ${OPERATION_MODES.map((mode) => `
            <button type="button" class="mode-option-card ${this.state.operationMode === mode ? "is-active" : ""}" data-operation-mode="${mode}">
              <span class="mode-option-icon">${simIcon(`${mode}Mode`)}</span>
              <strong>${this.t(mode)}</strong>
              <small>${this.operationModeDescription(mode)}</small>
            </button>
          `).join("")}
        </div>

        <div class="mode-detail-card">
          <div class="mode-detail-heading">
            <strong data-mode-detail-title>${this.t(this.state.operationMode)}</strong>
            <span data-mode-detail-description>${this.operationModeDescription()}</span>
          </div>

          <div class="mode-config-block" data-vehicle-mode-section>
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

          <div class="mode-config-block" data-traffic-mode-section>
            <label class="scenario-field">
              <span>${this.t("trafficScenario")}</span>
              <select data-traffic-scenario>
                ${TRAFFIC_SCENARIOS.map((scenario) => `
                  <option value="${scenario}" ${this.state.trafficScenario === scenario ? "selected" : ""}>${this.t(scenario)}</option>
                `).join("")}
              </select>
            </label>
          </div>

          <div class="mode-save-row">
            <button type="button" class="scenario-btn mode-save-btn" data-action="save-mode-settings">
              ${this.t("saveSettings")}
            </button>
            <span class="mode-save-status" data-mode-save-status="${this.state.modeSaveStatus}">${this.modeStatusText()}</span>
          </div>
          <div class="scenario-hint">${this.t("modeHint")}</div>
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
          ${this.renderOperationModeSection()}

          <div class="scenario-section scenario-section-tab" data-panel-section="weather">
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
          </div>
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
          return;
        }
        this.setActivePanel(PANEL_MODES.includes(mode) ? mode : "weather");
        this.state.panelOpen = true;
        this.syncUi();
      });
    });

    this.container.querySelectorAll("[data-panel-tab]").forEach((button) => {
      button.addEventListener("click", () => {
        this.setActivePanel(button.dataset.panelTab);
        this.state.panelOpen = true;
        this.syncUi();
      });
    });

    this.container.querySelectorAll("[data-operation-mode]").forEach((button) => {
      button.addEventListener("click", () => {
        this.state.operationMode = OPERATION_MODES.includes(button.dataset.operationMode) ? button.dataset.operationMode : "integrated";
        this.state.modeSaveStatus = "idle";
        this.state.modeSaveMessage = "";
        this.syncUi();
      });
    });

    this.container.querySelector("[data-dynamics-model]")?.addEventListener("change", (event) => {
      this.state.dynamics = DYNAMICS_MODELS.includes(event.target.value) ? event.target.value : "simple";
      this.state.modeSaveStatus = "idle";
      this.state.modeSaveMessage = "";
      this.syncUi();
    });

    this.container.querySelectorAll("[data-controller-mode]").forEach((button) => {
      button.addEventListener("click", () => {
        this.state.mainVehicleController = CONTROLLER_MODES.includes(button.dataset.controllerMode) ? button.dataset.controllerMode : "Autopilot";
        this.state.modeSaveStatus = "idle";
        this.state.modeSaveMessage = "";
        this.syncUi();
      });
    });

    this.container.querySelector("[data-traffic-scenario]")?.addEventListener("change", (event) => {
      this.state.trafficScenario = TRAFFIC_SCENARIOS.includes(event.target.value) ? event.target.value : "middle";
      this.state.modeSaveStatus = "idle";
      this.state.modeSaveMessage = "";
      this.syncUi();
    });

    this.container.querySelector("[data-action='save-mode-settings']")?.addEventListener("click", () => {
      this.sendModeSettings();
    });

    this.container.querySelector("[data-action='toggle-playback']")?.addEventListener("click", (event) => {
      const panel = this.container.querySelector("#playback-panel");
      const isOpen = !panel?.classList.contains("is-open");
      panel?.classList.toggle("is-open", isOpen);
      panel?.setAttribute("aria-hidden", isOpen ? "false" : "true");
      event.currentTarget.classList.toggle("is-active", isOpen);
    });

    this.container.querySelectorAll("[data-action='toggle-speed']").forEach((button) => {
      button.addEventListener("click", () => {
        const menu = button.parentElement?.querySelector(".playback-speed-menu");
        const isOpen = !menu?.classList.contains("is-open");
        menu?.classList.toggle("is-open", isOpen);
        menu?.setAttribute("aria-hidden", isOpen ? "false" : "true");
      });
    });

    this.container.querySelector("[data-action='collapse-scenario']")?.addEventListener("click", () => {
      const panel = this.container.querySelector("#scenario-panel");
      this.state.panelOpen = false;
      this.syncUi();
    });

    this.container.querySelectorAll("[data-map-zoom]").forEach((button) => {
      button.addEventListener("click", () => this.handleMapControl(button.dataset.mapZoom));
    });

    this.container.querySelector("[data-action='toggle-commercial-traffic']")?.addEventListener("click", () => {
      this.toggleCommercialTraffic();
    });

    this.container.querySelector("[data-action='toggle-weather-visualization']")?.addEventListener("click", () => {
      this.state.weatherVisualizationEnabled = !this.state.weatherVisualizationEnabled;
      this.refresh();
      this.updateWindVisualization();
    });

    this.container.querySelectorAll("[data-play-state]").forEach((button) => {
      button.addEventListener("click", () => {
        this.state.playState = PLAY_STATES.includes(button.dataset.playState) ? button.dataset.playState : "pause";
        this.refresh();
        this.updateWindVisualization();
        this.scheduleSend({ immediate: true });
      });
    });

    this.container.querySelectorAll("[data-speed]").forEach((button) => {
      button.addEventListener("click", () => {
        const speed = Number(button.dataset.speed);
        this.state.playbackSpeed = SPEEDS.includes(speed) ? speed : 1;
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
        this.scheduleSend({ immediate: true });
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
      this.scheduleSend();
    });

    this.container.querySelector("[data-precipitation-intensity]")?.addEventListener("input", (event) => {
      this.state.precipitationIntensity =
        this.state.precipitationType === "none" ? 0 : step01(normalizeNumber(event.target.value, 0, 1, 0));
      this.updateRangeLabels();
      this.updateOperationalLayers();
      this.updateWindVisualization();
      this.scheduleSend();
    });

    this.container.querySelector("[data-fog-intensity]")?.addEventListener("input", (event) => {
      this.state.fogIntensity = step01(normalizeNumber(event.target.value, 0, 1, 0));
      this.updateRangeLabels();
      this.updateOperationalLayers();
      this.updateWindVisualization();
      this.scheduleSend();
    });

    this.container.querySelector("[data-action='toggle-gust-apply']")?.addEventListener("click", () => {
      this.state.gustApplyMode = !this.state.gustApplyMode;
      this.refresh();
      this.updateWindVisualization();
      this.scheduleSend({ immediate: true });
    });

    this.container.querySelector("[data-action='reset-gust']")?.addEventListener("click", () => {
      this.state.gustApplyMode = false;
      this.state.gustEnabled = false;
      this.state.gustLat = DEFAULT_STATE.gustLat;
      this.state.gustLon = DEFAULT_STATE.gustLon;
      this.state.gustRadius = DEFAULT_STATE.gustRadius;
      this.refresh();
      this.updateWindVisualization();
      this.scheduleSend({ immediate: true });
    });

    this.container.querySelector("[data-gust-radius]")?.addEventListener("input", (event) => {
      this.state.gustRadius = normalizeNumber(event.target.value, 400, 4000, DEFAULT_STATE.gustRadius);
      this.updateRangeLabels();
      this.updateOperationalLayers();
      this.updateWindVisualization();
      this.scheduleSend();
    });
  }

  setActivePanel(mode) {
    if (!PANEL_MODES.includes(mode)) {
      return;
    }
    this.state.activePanel = mode;
    this.syncUi();
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
    this.scheduleSend({ immediate: true });
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
    const trafficSection = this.container.querySelector("[data-traffic-mode-section]");
    if (trafficSection) {
      trafficSection.hidden = this.state.operationMode === "single";
    }
    const dynamicsModel = this.container.querySelector("[data-dynamics-model]");
    if (dynamicsModel) {
      dynamicsModel.value = this.state.dynamics;
    }
    const trafficScenario = this.container.querySelector("[data-traffic-scenario]");
    if (trafficScenario) {
      trafficScenario.value = this.state.trafficScenario;
    }
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

    this.container.querySelectorAll("[data-play-state]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.playState === this.state.playState);
    });
    this.container.querySelectorAll("[data-speed]").forEach((button) => {
      button.classList.toggle("is-active", Number(button.dataset.speed) === this.state.playbackSpeed);
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

    this.container.querySelectorAll(".scenario-status-row strong").forEach((element) => {
      if (element.previousElementSibling?.textContent === this.t("autoSend")) {
        element.textContent = this.statusLabel();
      }
    });

    this.updateCommercialTrafficControl();
    this.updateRangeLabels();
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
    if (!this.state.commercialTrafficEnabled) {
      statusBoard.textContent = this.t("noTrafficData");
      return;
    }
    statusBoard.textContent = `${this.t("commercialAircraft")} ${this.commercialTrafficMeta()}`;
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

      this.map.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: "metric" }), "bottom-right");

      this.map.once("load", () => {
        this.container.querySelector("[data-map-loading]")?.classList.add("is-hidden");
        this.addOperationalLayers();
        this.bindCommercialAircraftMapEvents();
        this.updateOperationalLayers();
        this.updateWindVisualization();
        this.renderCommercialAircraft();
      });

      this.map.on("click", (event) => {
        const aircraftFeature = this.map.getLayer(COMMERCIAL_AIRCRAFT_LAYER_ID)
          ? this.map.queryRenderedFeatures(event.point, { layers: [COMMERCIAL_AIRCRAFT_LAYER_ID] })[0]
          : null;
        const aircraftId = aircraftFeature?.properties?.id;
        if (aircraftId) {
          this.selectCommercialAircraft(aircraftId);
          return;
        }
        this.closeCommercialAircraftPopup();
        if (!this.state.gustApplyMode) {
          return;
        }
        this.applyLocalWind(event.lngLat);
      });

      ["movestart", "zoomstart", "dragstart", "rotatestart", "pitchstart"].forEach((eventName) => {
        this.map.on(eventName, () => this.snapCommercialAircraftMarkers());
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

    this.ensureCommercialAircraftTrackLayer();
  }

  setMapTheme() {
    if (!this.map) {
      return;
    }
    this.map.getContainer().className = `uatm-map theme-${this.state.mapTheme} maplibregl-map`;
    this.map.setStyle(buildMapStyle(this.state.mapTheme, this.tileMetadata || DEFAULT_TILE_METADATA));
    this.map.once("style.load", () => {
      this.addOperationalLayers();
      this.updateOperationalLayers();
      this.updateWindVisualization();
      this.renderCommercialAircraft();
    });
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

  buildModePayload() {
    const operationMode = OPERATION_MODES.includes(this.state.operationMode) ? this.state.operationMode : "integrated";
    const payload = {
      timestamp: new Date().toISOString(),
      operationMode,
    };

    if (operationMode !== "traffic") {
      payload.singleFlight = {
        vehicleSimType: {
          dynamics: DYNAMICS_MODELS.includes(this.state.dynamics) ? this.state.dynamics : "simple",
          mainVehicleController: CONTROLLER_MODES.includes(this.state.mainVehicleController)
            ? this.state.mainVehicleController
            : "Autopilot",
        },
      };
    }

    if (operationMode !== "single") {
      payload.traffic = {
        trafficScenario: TRAFFIC_SCENARIOS.includes(this.state.trafficScenario) ? this.state.trafficScenario : "middle",
      };
    }

    return payload;
  }

  async sendModeSettings() {
    this.state.modeSaveStatus = "sending";
    this.state.modeSaveMessage = "";
    this.syncUi();

    try {
      const result = await postJSON("/api/v1/icd/1001/send", { payload: this.buildModePayload() });
      if (result?.sent === false || (Array.isArray(result?.errors) && result.errors.length > 0)) {
        throw new Error(result.errors?.join(", ") || "1001 send rejected");
      }
      if (this.destroyed) {
        return;
      }
      this.state.modeSaveStatus = "ok";
      this.state.modeSaveMessage = "";
      this.syncUi();
    } catch (error) {
      if (this.destroyed) {
        return;
      }
      this.state.modeSaveStatus = "error";
      this.state.modeSaveMessage = error.message;
      this.syncUi();
    }
  }

  buildPayload() {
    const precipitationType = PRECIPITATION_TYPES.includes(this.state.precipitationType) ? this.state.precipitationType : "none";
    const payload = {
      timestamp: new Date().toISOString(),
      playbackSpeed: SPEEDS.includes(this.state.playbackSpeed) ? this.state.playbackSpeed : 1,
      playState: PLAY_STATES.includes(this.state.playState) ? this.state.playState : "pause",
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
    return payload;
  }

  scheduleSend(options = {}) {
    window.clearTimeout(this.sendTimer);
    const delay = options.immediate ? 0 : 300;
    this.status = "ready";
    this.updateStatus();
    this.sendTimer = window.setTimeout(() => this.sendCurrentPayload(), delay);
  }

  async sendCurrentPayload() {
    const seq = ++this.sendSeq;
    this.status = "sending";
    this.statusMessage = "";
    this.updateStatus();
    try {
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
    } catch (error) {
      if (this.destroyed || seq !== this.sendSeq) {
        return;
      }
      this.status = "error";
      this.statusMessage = error.message;
      this.updateStatus();
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
