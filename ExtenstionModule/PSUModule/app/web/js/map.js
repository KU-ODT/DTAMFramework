const BASE_MAP_PALETTES = {
  // OperationModule simulation workspace palette. Keep PSU map visually aligned
  // with OperationModule/DOC_main.py instead of using a separate demo look.
  light: {
    background: "#6bbbe6",
    tileLand: "#e5efd9",
    landcover: "#cce2c4",
    landuse: "#d7e8cb",
    park: "#afd3a4",
    water: "#4faee0",
    waterway: "#328fc2",
    boundary: "#7a8172",
    roadCasing: "#f5efe3",
    transportation: "#b9aa92",
    roadMajor: "#836f55",
    building: "#c8c0b4",
    label: "#24301f",
    labelHalo: "#f8f4ea",
  },
  dark: {
    background: "#223447",
    tileLand: "#223447",
    landcover: "#182522",
    landuse: "#1b2320",
    park: "#1d3024",
    water: "#142a3e",
    waterway: "#1f425e",
    boundary: "#5e6872",
    roadCasing: "#4a453a",
    transportation: "#4a453a",
    roadMajor: "#4a453a",
    building: "#2f2c2a",
    label: "#7c8b9a",
    labelHalo: "#223447",
  },
};

const ODT_CORRIDOR_DARK = "#f59e0b";
const ODT_CORRIDOR_LIGHT = "#2c6dff";
const ODT_VERTIPORT_LINK = "#60a5fa";
const ODT_VERTIPORT_MARKER = "#10b981";
const ODT_CORRIDOR_STROKE_DARK = "#141824";
const ODT_WAYPOINT_LABEL = "#fbbf24";

let psuMapInstance = null;
let latestScenarioLayers = null;

function normalizeMapTheme(theme) {
  return theme === "light" ? "light" : "dark";
}

function currentMapTheme() {
  return normalizeMapTheme(document.documentElement?.dataset?.theme);
}

function applyBaseMapPalette(map, theme) {
  if (!map) return false;
  const normalizedTheme = normalizeMapTheme(theme);
  const pal = BASE_MAP_PALETTES[normalizedTheme] || BASE_MAP_PALETTES.dark;
  const setPaint = (layerId, property, value) => {
    if (map.getLayer(layerId)) {
      map.setPaintProperty(layerId, property, value);
    }
  };

  setPaint("background", "background-color", pal.background);
  setPaint("tile-land-base", "fill-color", pal.tileLand || pal.background);
  setPaint("landcover", "fill-color", pal.landcover);
  setPaint("landuse", "fill-color", pal.landuse);
  setPaint("park", "fill-color", pal.park);
  setPaint("water", "fill-color", pal.water);
  setPaint("waterway", "line-color", pal.waterway);
  setPaint("boundary", "line-color", pal.boundary);
  setPaint("transportation", "line-color", pal.transportation);
  for (const layerId of ["transportation-casing-minor", "transportation-casing-medium", "transportation-casing-major"]) {
    setPaint(layerId, "line-color", pal.roadCasing || pal.transportation);
  }
  for (const layerId of ["transportation-minor", "transportation-medium"]) {
    setPaint(layerId, "line-color", pal.transportation);
  }
  setPaint("transportation-major", "line-color", pal.roadMajor || pal.transportation);
  setPaint("building", "fill-color", pal.building);
  setPaint("place-label-city", "text-color", pal.label);
  setPaint("place-label-city", "text-halo-color", pal.labelHalo);
  setPaint("place-label-district", "text-color", pal.label);
  setPaint("place-label-district", "text-halo-color", pal.labelHalo);
  setPaint("transportation-label", "text-color", pal.label);
  setPaint("transportation-label", "text-halo-color", pal.labelHalo);
  if (map.getLayer("osm")) {
    const lightMode = normalizedTheme === "light";
    map.setPaintProperty("osm", "raster-opacity", lightMode ? 0.9 : 0.62);
    map.setPaintProperty("osm", "raster-saturation", lightMode ? -0.08 : -0.55);
    map.setPaintProperty("osm", "raster-brightness-min", lightMode ? 0.08 : 0);
    map.setPaintProperty("osm", "raster-brightness-max", lightMode ? 0.98 : 1);
  }
  applyPsuOverlayTheme(map, normalizedTheme);
  return true;
}

function applyPsuOverlayTheme(map, theme = currentMapTheme()) {
  if (!map) return false;
  const normalizedTheme = normalizeMapTheme(theme);
  const setPaint = (layerId, property, value) => {
    if (map.getLayer(layerId)) {
      map.setPaintProperty(layerId, property, value);
    }
  };
  const cColor = corridorColor(normalizedTheme);
  setPaint("psu-corridor-links", "line-color", cColor);
  setPaint("psu-corridor-spare-links", "line-color", cColor);
  setPaint("psu-nodes-circle", "circle-color", cColor);
  setPaint("psu-nodes-circle", "circle-stroke-color", corridorStrokeColor(normalizedTheme));
  setPaint("psu-node-labels", "text-halo-color", normalizedTheme === "dark" ? "rgba(8, 12, 16, 0.85)" : "rgba(248, 244, 234, 0.85)");
  setPaint("psu-vertiport-labels", "text-halo-color", normalizedTheme === "dark" ? "rgba(8, 12, 16, 0.85)" : "rgba(248, 244, 234, 0.85)");
  return true;
}

function emptyFeatureCollection() {
  return { type: "FeatureCollection", features: [] };
}

function tileUrl(url) {
  if (!url) {
    return null;
  }
  if (/^https?:\/\//i.test(url)) {
    return url;
  }
  return `${window.location.origin}${url.startsWith("/") ? "" : "/"}${url}`;
}

function tileBoundsFromConfig(config) {
  const bounds = config?.metadata?.bounds || config?.bounds;
  if (Array.isArray(bounds) && bounds.length === 4) {
    return [[Number(bounds[0]), Number(bounds[1])], [Number(bounds[2]), Number(bounds[3])]];
  }
  if (Array.isArray(bounds) && bounds.length === 2) {
    return bounds;
  }
  return [[124.0, 33.0], [132.0, 39.5]];
}

function tileLandBase(config) {
  const [[west, south], [east, north]] = tileBoundsFromConfig(config);
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: {},
        geometry: {
          type: "Polygon",
          coordinates: [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
        },
      },
    ],
  };
}

function corridorColor(theme = currentMapTheme()) {
  return normalizeMapTheme(theme) === "light" ? ODT_CORRIDOR_LIGHT : ODT_CORRIDOR_DARK;
}

function corridorStrokeColor(theme = currentMapTheme()) {
  return normalizeMapTheme(theme) === "dark" ? ODT_CORRIDOR_STROKE_DARK : "#ffffff";
}

function buildVectorLayers(pal, theme = currentMapTheme()) {
  if (normalizeMapTheme(theme) === "dark") {
    return [
      { id: "landcover", type: "fill", source: "mbtiles", "source-layer": "landcover", paint: { "fill-color": pal.landcover, "fill-opacity": 0.7 } },
      { id: "landuse", type: "fill", source: "mbtiles", "source-layer": "landuse", paint: { "fill-color": pal.landuse, "fill-opacity": 0.7 } },
      { id: "park", type: "fill", source: "mbtiles", "source-layer": "park", paint: { "fill-color": pal.park, "fill-opacity": 0.85 } },
      { id: "water", type: "fill", source: "mbtiles", "source-layer": "water", paint: { "fill-color": pal.water } },
      { id: "waterway", type: "line", source: "mbtiles", "source-layer": "waterway", paint: { "line-color": pal.waterway, "line-width": 1 } },
      {
        id: "boundary",
        type: "line",
        source: "mbtiles",
        "source-layer": "boundary",
        paint: { "line-color": pal.boundary, "line-width": 1, "line-dasharray": [2, 2], "line-opacity": 0.58 },
      },
      {
        id: "transportation",
        type: "line",
        source: "mbtiles",
        "source-layer": "transportation",
        paint: { "line-color": pal.transportation, "line-width": ["interpolate", ["linear"], ["zoom"], 5, 0.4, 10, 1, 14, 2.5], "line-opacity": 0.78 },
      },
      { id: "building", type: "fill", source: "mbtiles", "source-layer": "building", minzoom: 13, paint: { "fill-color": pal.building, "fill-opacity": 0.6 } },
    ];
  }

  return [
    { id: "tile-land-base", type: "fill", source: "tileLandBase", paint: { "fill-color": pal.tileLand, "fill-opacity": 1 } },
    { id: "landcover", type: "fill", source: "mbtiles", "source-layer": "landcover", paint: { "fill-color": pal.landcover, "fill-opacity": 0.9 } },
    { id: "landuse", type: "fill", source: "mbtiles", "source-layer": "landuse", paint: { "fill-color": pal.landuse, "fill-opacity": 0.88 } },
    { id: "park", type: "fill", source: "mbtiles", "source-layer": "park", paint: { "fill-color": pal.park, "fill-opacity": 0.8 } },
    { id: "water", type: "fill", source: "mbtiles", "source-layer": "water", paint: { "fill-color": pal.water, "fill-opacity": 0.92 } },
    { id: "waterway", type: "line", source: "mbtiles", "source-layer": "waterway", paint: { "line-color": pal.waterway, "line-opacity": 0.75, "line-width": ["interpolate", ["linear"], ["zoom"], 7, 0.5, 13, 2.2] } },
    { id: "boundary", type: "line", source: "mbtiles", "source-layer": "boundary", paint: { "line-color": pal.boundary, "line-opacity": 0.48, "line-width": ["interpolate", ["linear"], ["zoom"], 5, 0.5, 12, 1.4] } },
    {
      id: "transportation-casing-minor",
      type: "line",
      source: "mbtiles",
      "source-layer": "transportation",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": pal.roadCasing, "line-opacity": 0.24, "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.25, 12, 1.05, 14, 2] },
    },
    {
      id: "transportation-casing-medium",
      type: "line",
      source: "mbtiles",
      "source-layer": "transportation",
      filter: ["in", ["get", "class"], ["literal", ["secondary", "tertiary"]]],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": pal.roadCasing, "line-opacity": 0.42, "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.7, 12, 2.4, 14, 4.4] },
    },
    {
      id: "transportation-casing-major",
      type: "line",
      source: "mbtiles",
      "source-layer": "transportation",
      filter: ["in", ["get", "class"], ["literal", ["motorway", "trunk", "primary"]]],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": pal.roadCasing, "line-opacity": 0.58, "line-width": ["interpolate", ["linear"], ["zoom"], 8, 1, 12, 4.2, 14, 8] },
    },
    {
      id: "transportation-minor",
      type: "line",
      source: "mbtiles",
      "source-layer": "transportation",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": pal.transportation, "line-opacity": ["interpolate", ["linear"], ["zoom"], 8, 0.28, 13, 0.58], "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.22, 12, 0.65, 14, 1.25] },
    },
    {
      id: "transportation-medium",
      type: "line",
      source: "mbtiles",
      "source-layer": "transportation",
      filter: ["in", ["get", "class"], ["literal", ["secondary", "tertiary"]]],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": pal.transportation, "line-opacity": ["interpolate", ["linear"], ["zoom"], 8, 0.42, 13, 0.78], "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.45, 12, 1.35, 14, 2.4] },
    },
    {
      id: "transportation-major",
      type: "line",
      source: "mbtiles",
      "source-layer": "transportation",
      filter: ["in", ["get", "class"], ["literal", ["motorway", "trunk", "primary"]]],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": pal.roadMajor, "line-opacity": ["interpolate", ["linear"], ["zoom"], 8, 0.5, 13, 0.88], "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.75, 12, 2.6, 14, 5] },
    },
    { id: "aeroway", type: "line", source: "mbtiles", "source-layer": "aeroway", minzoom: 10, paint: { "line-color": "#396f8b", "line-opacity": 0.75, "line-width": 1.6 } },
    { id: "building", type: "fill", source: "mbtiles", "source-layer": "building", minzoom: 12, paint: { "fill-color": pal.building, "fill-opacity": ["interpolate", ["linear"], ["zoom"], 12, 0.28, 14, 0.68] } },
  ];
}

function buildStyle(config, theme = currentMapTheme()) {
  const normalizedTheme = normalizeMapTheme(theme);
  const pal = BASE_MAP_PALETTES[normalizedTheme] || BASE_MAP_PALETTES.dark;
  const layers = [{ id: "background", type: "background", paint: { "background-color": pal.background } }];
  const sources = {};
  const vectorTileUrl = tileUrl(config.tileUrl);
  if (config.available && vectorTileUrl) {
    if (normalizedTheme === "light") {
      sources.tileLandBase = { type: "geojson", data: tileLandBase(config) };
    }
    sources.mbtiles = {
      type: "vector",
      tiles: [vectorTileUrl],
      minzoom: Number(config.minZoom ?? 0),
      maxzoom: Number(config.maxZoom ?? 14),
      bounds: tileBoundsFromConfig(config).flat(),
    };
    layers.push(...buildVectorLayers(pal, normalizedTheme));
  } else {
    sources.osm = {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      minzoom: 0,
      maxzoom: 19,
    };
    layers.push({ id: "osm", type: "raster", source: "osm", paint: { "raster-opacity": normalizedTheme === "light" ? 0.9 : 0.62, "raster-saturation": normalizedTheme === "light" ? -0.08 : -0.55 } });
  }
  return {
    version: 8,
    name: `PSU DTAM Korea ${normalizedTheme}`,
    glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
    sources,
    layers,
  };
}

function createResetControl(map, initialView) {
  return {
    onAdd() {
      const container = document.createElement("div");
      container.className = "maplibregl-ctrl maplibregl-ctrl-group";
      const button = document.createElement("button");
      button.type = "button";
      button.title = "초기 지도 위치로 이동";
      button.setAttribute("aria-label", "초기 지도 위치로 이동");
      button.textContent = "⌂";
      button.addEventListener("click", () => {
        map.flyTo({ ...initialView, duration: 900 });
      });
      container.appendChild(button);
      return container;
    },
    onRemove() {},
  };
}

function statusColorExpression(defaultColor = "#7dd3fc") {
  return [
    "match",
    ["get", "status"],
    "WARNING",
    "#ef4444",
    "CAUTION",
    "#f59e0b",
    "NORMAL",
    "#34d399",
    "ACTIVE",
    "#7dd3fc",
    "ACCEPTED",
    "#38bdf8",
    "PENDING_REVIEW",
    "#f59e0b",
    defaultColor,
  ];
}

function addOrUpdateSource(map, sourceId, data) {
  const source = map.getSource(sourceId);
  if (source?.setData) {
    source.setData(data);
    return;
  }
  map.addSource(sourceId, { type: "geojson", data });
}

function addLayerIfMissing(map, layer) {
  if (map.getLayer(layer.id)) {
    return;
  }
  map.addLayer(layer);
}

function loadMapImage(map, id, url) {
  if (!map || map.hasImage?.(id)) {
    return Promise.resolve(true);
  }
  return new Promise((resolve) => {
    const finish = (image) => {
      if (!map || !image) {
        resolve(false);
        return;
      }
      try {
        if (!map.hasImage?.(id)) {
          map.addImage(id, image);
        }
        resolve(true);
      } catch (_) {
        resolve(false);
      }
    };

    if (typeof map.loadImage === "function") {
      map.loadImage(url, (error, image) => {
        if (error || !image) {
          resolve(false);
          return;
        }
        finish(image);
      });
      return;
    }

    const image = new Image();
    image.onload = () => finish(image);
    image.onerror = () => resolve(false);
    image.src = url;
  });
}

async function loadPsuMapIcons(map) {
  const plane = await loadMapImage(map, "psu-plane-icon", "/static/assets/plane.png");
  map.__psuIconState = { plane };
  return map.__psuIconState;
}

async function addScenarioLayers(map, statusEl) {
  const response = await fetch("/api/map/layers", { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`시나리오 지도 레이어 로드 실패: HTTP ${response.status}`);
  }
  const layers = await response.json();
  latestScenarioLayers = layers;
  const iconState = await loadPsuMapIcons(map);

  addOrUpdateSource(map, "psu-links", layers.links || emptyFeatureCollection());
  addOrUpdateSource(map, "psu-corridors", layers.corridors || emptyFeatureCollection());
  addOrUpdateSource(map, "psu-routes", layers.routes || emptyFeatureCollection());
  addOrUpdateSource(map, "psu-actual-tracks", layers.actual_tracks || emptyFeatureCollection());
  addOrUpdateSource(map, "psu-nodes", layers.nodes || emptyFeatureCollection());
  addOrUpdateSource(map, "psu-waypoints", layers.waypoints || emptyFeatureCollection());
  addOrUpdateSource(map, "psu-vertiports", layers.vertiports || emptyFeatureCollection());
  addOrUpdateSource(map, "psu-tracks", layers.tracks || emptyFeatureCollection());
  addOrUpdateSource(map, "psu-conflicts", layers.conflicts || emptyFeatureCollection());
  if (!map.getSource("psu-selected-conflict")) {
    addOrUpdateSource(map, "psu-selected-conflict", emptyFeatureCollection());
  }
  if (!map.getSource("psu-selected-track")) {
    addOrUpdateSource(map, "psu-selected-track", emptyFeatureCollection());
  }

  addLayerIfMissing(map, {
    id: "psu-corridor-links",
    type: "line",
    source: "psu-links",
    filter: ["all", ["==", ["get", "linkKind"], "corridor"], ["==", ["get", "spare"], false]],
    layout: { "line-cap": "round", "line-join": "round" },
    paint: {
      "line-color": corridorColor(),
      "line-width": ["case", ["==", ["get", "selected"], true], 2.2, 1.55],
      "line-dasharray": [3.5, 3.5],
      "line-opacity": 0.5,
    },
  });
  addLayerIfMissing(map, {
    id: "psu-corridor-spare-links",
    type: "line",
    source: "psu-links",
    filter: ["all", ["==", ["get", "linkKind"], "corridor"], ["==", ["get", "spare"], true]],
    layout: { "line-cap": "round", "line-join": "round" },
    paint: {
      "line-color": corridorColor(),
      "line-width": 1.55,
      "line-dasharray": [3.5, 3.5],
      "line-opacity": 0.5,
    },
  });
  addLayerIfMissing(map, {
    id: "psu-vertiport-links",
    type: "line",
    source: "psu-links",
    filter: ["==", ["get", "linkKind"], "vertiport"],
    layout: { "line-cap": "round", "line-join": "round" },
    paint: {
      "line-color": ODT_VERTIPORT_LINK,
      "line-width": ["case", ["==", ["get", "selected"], true], 2.2, 1.55],
      "line-dasharray": [3.5, 3.5],
      "line-opacity": 0.5,
    },
  });
  // These sources are intentionally empty unless a real analysis engine/live
  // route history provides them. Keeping the layers registered allows future
  // updates without showing static demo lines.
  addLayerIfMissing(map, {
    id: "psu-routes-line",
    type: "line",
    source: "psu-routes",
    layout: { "line-cap": "round", "line-join": "round" },
    paint: {
      "line-color": statusColorExpression("#7dd3fc"),
      "line-width": ["interpolate", ["linear"], ["zoom"], 9, 1, 12, 2, 15, 4],
      "line-dasharray": [1.5, 1.2],
      "line-opacity": 0.88,
    },
  });
  addLayerIfMissing(map, {
    id: "psu-actual-tracks-line",
    type: "line",
    source: "psu-actual-tracks",
    layout: { "line-cap": "round", "line-join": "round" },
    paint: {
      "line-color": "#f8fafc",
      "line-width": ["interpolate", ["linear"], ["zoom"], 9, 1.6, 12, 3.2, 15, 5],
      "line-opacity": 0.76,
    },
  });
  addLayerIfMissing(map, {
    id: "psu-nodes-circle",
    type: "circle",
    source: "psu-nodes",
    paint: {
      "circle-radius": ["case", ["==", ["get", "selected"], true], 6, 4.5],
      "circle-color": corridorColor(),
      "circle-stroke-width": 1.5,
      "circle-stroke-color": corridorStrokeColor(),
      "circle-opacity": 0.78,
    },
  });
  addLayerIfMissing(map, {
    id: "psu-node-labels",
    type: "symbol",
    source: "psu-nodes",
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
  addLayerIfMissing(map, {
    id: "psu-vertiports-circle",
    type: "circle",
    source: "psu-vertiports",
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 8, 9, 12, 12, 16, 16],
      "circle-color": ODT_VERTIPORT_MARKER,
      "circle-stroke-color": "rgba(255, 255, 255, 0.92)",
      "circle-stroke-width": 2,
      "circle-opacity": 0.96,
    },
  });
  addLayerIfMissing(map, {
    id: "psu-vertiports-v-label",
    type: "symbol",
    source: "psu-vertiports",
    layout: {
      "text-field": "V",
      "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"],
      "text-size": ["interpolate", ["linear"], ["zoom"], 8, 8, 12, 10, 16, 13],
      "text-anchor": "center",
      "text-allow-overlap": true,
      "text-ignore-placement": true,
    },
    paint: {
      "text-color": "#ffffff",
      "text-halo-color": "rgba(0,0,0,0.12)",
      "text-halo-width": 0.5,
    },
  });
  addLayerIfMissing(map, {
    id: "psu-vertiport-labels",
    type: "symbol",
    source: "psu-vertiports",
    minzoom: 10.5,
    layout: {
      "text-field": ["get", "name"],
      "text-font": ["Open Sans Regular", "Arial Unicode MS Regular"],
      "text-size": 10,
      "text-offset": [0, 1.65],
      "text-anchor": "top",
      "text-allow-overlap": false,
    },
    paint: {
      "text-color": "#ffffff",
      "text-halo-color": "rgba(8, 12, 16, 0.88)",
      "text-halo-width": 2.2,
    },
  });
  addLayerIfMissing(map, {
    id: "psu-tracks-circle",
    type: "circle",
    source: "psu-tracks",
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 9, 6, 13, 11, 16, 16],
      "circle-color": "#22d3ee",
      "circle-stroke-color": "#22d3ee",
      "circle-stroke-width": 0,
      "circle-opacity": 0,
    },
  });
  addLayerIfMissing(map, {
    id: "psu-tracks-neon-outer",
    type: "circle",
    source: "psu-tracks",
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 9, 12, 13, 20, 16, 28],
      "circle-color": statusColorExpression("#22d3ee"),
      "circle-opacity": ["case", ["==", ["get", "stale"], true], 0.08, 0.18],
      "circle-blur": 0.72,
      "circle-stroke-width": 0,
    },
  });
  addLayerIfMissing(map, {
    id: "psu-tracks-neon-inner",
    type: "circle",
    source: "psu-tracks",
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 9, 5, 13, 8, 16, 11],
      "circle-color": statusColorExpression("#67e8f9"),
      "circle-opacity": ["case", ["==", ["get", "stale"], true], 0.1, 0.24],
      "circle-blur": 0.38,
      "circle-stroke-width": 0,
    },
  });
  if (iconState.plane) {
    addLayerIfMissing(map, {
      id: "psu-tracks-icon",
      type: "symbol",
      source: "psu-tracks",
      layout: {
        "icon-image": "psu-plane-icon",
        "icon-size": 0.122,
        "icon-rotate": ["+", ["coalesce", ["get", "heading"], ["get", "heading_deg"], 0], 90],
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
  addLayerIfMissing(map, {
    id: "psu-conflicts-halo",
    type: "circle",
    source: "psu-conflicts",
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 9, 10, 13, 18, 16, 26],
      "circle-color": statusColorExpression("#f97316"),
      "circle-opacity": 0.22,
      "circle-stroke-color": statusColorExpression("#f97316"),
      "circle-stroke-width": 1,
      "circle-stroke-opacity": 0.72,
    },
  });
  addLayerIfMissing(map, {
    id: "psu-conflicts-circle",
    type: "circle",
    source: "psu-conflicts",
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 9, 5, 13, 8.5, 16, 12],
      "circle-color": statusColorExpression("#f97316"),
      "circle-stroke-color": "#ffffff",
      "circle-stroke-width": 2,
      "circle-opacity": 0.96,
    },
  });
  addLayerIfMissing(map, {
    id: "psu-selected-conflict-halo",
    type: "circle",
    source: "psu-selected-conflict",
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 9, 18, 13, 32, 16, 46],
      "circle-color": "#facc15",
      "circle-opacity": 0.18,
      "circle-stroke-color": "#fde68a",
      "circle-stroke-width": 3,
      "circle-stroke-opacity": 0.9,
    },
  });
  addLayerIfMissing(map, {
    id: "psu-selected-conflict-core",
    type: "circle",
    source: "psu-selected-conflict",
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 9, 7, 13, 12, 16, 16],
      "circle-color": "#fde047",
      "circle-stroke-color": "#111827",
      "circle-stroke-width": 2,
      "circle-opacity": 0.98,
    },
  });
  addLayerIfMissing(map, {
    id: "psu-selected-track-halo",
    type: "circle",
    source: "psu-selected-track",
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 9, 14, 13, 24, 16, 32],
      "circle-color": "#22d3ee",
      "circle-opacity": 0.18,
      "circle-blur": 0.58,
      "circle-stroke-color": "#22d3ee",
      "circle-stroke-width": 0,
    },
  });

  attachScenarioInteractions(map);

  if (statusEl) {
    const count =
      (layers.tracks?.features?.length || 0) +
      (layers.vertiports?.features?.length || 0) +
      (layers.corridors?.features?.length || 0) +
      (layers.conflicts?.features?.length || 0);
    statusEl.textContent = `MissionModule 지도 + PSU Traffic/Conflict 레이어 연결 완료 · ${count}개 객체`;
  }
}

function findFeature(collection, predicate) {
  return (collection?.features || []).find(predicate);
}

function updateGeoJsonSource(map, sourceId, feature) {
  const source = map?.getSource?.(sourceId);
  if (!source?.setData) {
    return false;
  }
  source.setData(feature ? { type: "FeatureCollection", features: [feature] } : emptyFeatureCollection());
  return Boolean(feature);
}

function attachScenarioInteractions(map) {
  if (map.__psuScenarioInteractionsAttached) {
    return;
  }
  map.__psuScenarioInteractionsAttached = true;

  const interactiveLayers = ["psu-conflicts-circle", "psu-tracks-circle", "psu-tracks-icon", "psu-vertiports-circle"];
  for (const layerId of interactiveLayers) {
    if (!map.getLayer(layerId)) continue;
    map.on("mouseenter", layerId, () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", layerId, () => {
      map.getCanvas().style.cursor = "";
    });
  }

  map.on("click", "psu-conflicts-circle", (event) => {
    const feature = event.features?.[0];
    const conflictId = feature?.properties?.conflict_id || feature?.id;
    if (!conflictId) {
      return;
    }
    selectConflictOnMap(conflictId);
    window.dispatchEvent(new CustomEvent("psu:conflict-selected", { detail: { conflictId } }));
  });

  for (const trackLayerId of ["psu-tracks-circle", "psu-tracks-icon"]) {
    if (!map.getLayer(trackLayerId)) continue;
    map.on("click", trackLayerId, (event) => {
      const feature = event.features?.[0];
      const aircraftId = feature?.properties?.aircraft_id || feature?.properties?.aircraftId || feature?.id;
      if (!aircraftId) {
        return;
      }
      selectAircraftOnMap(aircraftId);
      window.dispatchEvent(new CustomEvent("psu:aircraft-selected", { detail: { aircraftId } }));
    });
  }
}

export function selectConflictOnMap(conflictId, { fly = true } = {}) {
  if (!psuMapInstance || !latestScenarioLayers) {
    return false;
  }
  const feature = findFeature(
    latestScenarioLayers.conflicts,
    (item) => String(item?.properties?.conflict_id || item?.id) === String(conflictId),
  );
  updateGeoJsonSource(psuMapInstance, "psu-selected-conflict", feature);
  if (feature && fly) {
    psuMapInstance.flyTo({
      center: feature.geometry.coordinates,
      zoom: Math.max(psuMapInstance.getZoom(), 13.4),
      duration: 800,
      essential: true,
    });
  }
  return Boolean(feature);
}

export function selectAircraftOnMap(aircraftId, { fly = true } = {}) {
  if (!psuMapInstance || !latestScenarioLayers) {
    return false;
  }
  const feature = findFeature(
    latestScenarioLayers.tracks,
    (item) => String(item?.properties?.aircraft_id || item?.id) === String(aircraftId),
  );
  updateGeoJsonSource(psuMapInstance, "psu-selected-track", feature);
  if (feature && fly) {
    psuMapInstance.flyTo({
      center: feature.geometry.coordinates,
      zoom: Math.max(psuMapInstance.getZoom(), 13.2),
      duration: 700,
      essential: true,
    });
  }
  return Boolean(feature);
}

export function setTrafficMapFilter(filter) {
  if (!psuMapInstance) {
    return;
  }
  const normalized = String(filter || "ALL").toUpperCase();
  const severityFilter = normalized === "WARNING" || normalized === "CAUTION" ? ["==", ["get", "severity"], normalized] : null;
  const trackFilter = normalized === "WARNING" || normalized === "CAUTION"
    ? ["==", ["get", "severity"], normalized]
    : normalized === "ACTIVE"
      ? ["in", ["get", "flight_status"], ["literal", ["ACTIVE", "CONNECTED"]]]
      : null;
  for (const layerId of ["psu-conflicts-halo", "psu-conflicts-circle"]) {
    if (psuMapInstance.getLayer(layerId)) {
      psuMapInstance.setFilter(layerId, severityFilter);
    }
  }
  for (const layerId of ["psu-tracks-circle", "psu-tracks-neon-outer", "psu-tracks-neon-inner", "psu-tracks-icon"]) {
    if (psuMapInstance.getLayer(layerId)) {
      psuMapInstance.setFilter(layerId, trackFilter);
    }
  }
}

export function setPsuMapTheme(theme) {
  const applied = applyBaseMapPalette(psuMapInstance, theme);
  window.setTimeout(() => applyBaseMapPalette(psuMapInstance, theme), 180);
  return applied;
}

if (!window.__PSU_MAP_THEME_LISTENER__) {
  window.__PSU_MAP_THEME_LISTENER__ = true;
  window.addEventListener("psu:theme-changed", (event) => {
    setPsuMapTheme(event.detail?.theme || currentMapTheme());
  });
}

export async function initPsuMap({ containerId = "psu-map", statusEl } = {}) {
  const container = document.getElementById(containerId);
  if (!container) {
    return null;
  }
  if (!window.maplibregl) {
    if (statusEl) {
      statusEl.textContent = "MapLibre 라이브러리를 찾을 수 없습니다.";
    }
    return null;
  }

  const response = await fetch("/api/map/config", { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`지도 설정 로드 실패: HTTP ${response.status}`);
  }
  const config = await response.json();
  const center = Array.isArray(config.center) ? config.center : [126.978, 37.5665];
  const initialView = {
    center,
    zoom: Number(config.zoom ?? 11.5),
    pitch: Number(config.pitch ?? 0),
    bearing: Number(config.bearing ?? 0),
  };

  const map = new window.maplibregl.Map({
    container,
    style: buildStyle(config, currentMapTheme()),
    ...initialView,
    minZoom: Number(config.minZoom ?? 0),
    maxZoom: Math.max(Number(config.maxZoom ?? 14) + 4, 18),
    attributionControl: false,
  });

  map.addControl(new window.maplibregl.NavigationControl({ showCompass: true, visualizePitch: true }), "top-right");
  map.addControl(new window.maplibregl.AttributionControl({ compact: true }), "bottom-right");
  map.addControl(createResetControl(map, initialView), "top-right");

  map.once("load", async () => {
    if (statusEl) {
      const name = config?.metadata?.name || "korea.mbtiles";
      statusEl.textContent = config.available
        ? `MissionModule 지도 연결 완료 · ${name} · z${config.minZoom}-${config.maxZoom}`
        : "MissionModule 지도 파일 없음 · OSM fallback";
    }
    try {
      applyBaseMapPalette(map, currentMapTheme());
      await addScenarioLayers(map, statusEl);
      window.clearInterval(map.__psuLiveRefreshTimer);
      map.__psuLiveRefreshTimer = window.setInterval(() => {
        if (document.hidden || !map.isStyleLoaded?.()) {
          return;
        }
        addScenarioLayers(map, null).catch((error) => {
          if (statusEl) {
            statusEl.textContent = error instanceof Error ? error.message : String(error);
          }
        });
      }, 1500);
    } catch (error) {
      if (statusEl) {
        statusEl.textContent = error instanceof Error ? error.message : String(error);
      }
    }
  });

  map.on("error", (event) => {
    const message = event?.error?.message || "지도 렌더링 경고";
    if (statusEl) {
      statusEl.textContent = message;
    }
  });

  psuMapInstance = map;
  window.__PSU_MAP__ = map;
  applyBaseMapPalette(map, currentMapTheme());
  return map;
}
