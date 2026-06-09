'use strict';

/* Two-style strategy:
 *  - mbtilesStyle()  : vector tiles served by our backend at /tiles/{z}/{x}/{y}.pbf
 *  - fallbackStyle() : public CartoDB Dark Matter raster tiles (used when no
 *                      .mbtiles file is present, so the frame still shows a map
 *                      during development)
 *
 * Rendering split (mirrors odt_preflight_demand reference):
 *   layer            | source kind          | rendered as
 *   ─────────────────┼──────────────────────┼────────────────────────────────
 *   basemap          | vector or raster     | style layers from this file
 *   corridor lines   | geojson (LineString) | MapLibre line layer (color by type)
 *   waypoint dots    | geojson (Point)      | MapLibre circle layer
 *   computed routes  | geojson (LineString) | MapLibre line layer
 *   vertiports       | -                    | HTML Marker (DOM, app.js)
 *   waypoint labels  | -                    | HTML Marker (DOM, app.js)
 */

window.MAP_STYLES = {
  mbtiles: mbtilesStyle,
  fallback: fallbackStyle,
};

const GLYPHS_URL = 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf';

const OVERLAY_SOURCES = () => ({
  'overlay-corridors': { type: 'geojson', data: emptyFc() },
  'overlay-waypoints': { type: 'geojson', data: emptyFc() },
  'overlay-route': { type: 'geojson', data: emptyFc() },
  'overlay-sim-routes': { type: 'geojson', data: emptyFc() },
  'overlay-sim-aircraft': { type: 'geojson', data: emptyFc() },
});

const OVERLAY_LAYERS = [
  /* corridor segments — colored by type:
   *   vertiport-link : vertiport ↔ waypoint (blue)
   *   corridor       : waypoint ↔ waypoint (amber/orange) */
  {
    id: 'corridor-line',
    type: 'line',
    source: 'overlay-corridors',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': [
        'match', ['get', 'type'],
        'vertiport-link', '#60a5fa',
        '#f59e0b',
      ],
      'line-width': 1.55,
      'line-dasharray': [3.5, 3.5],
      'line-opacity': 0.55,
    },
  },

  /* waypoint dots */
  {
    id: 'waypoint-circle',
    type: 'circle',
    source: 'overlay-waypoints',
    paint: {
      'circle-radius': 4.5,
      'circle-color': '#f59e0b',
      'circle-stroke-color': '#141824',
      'circle-stroke-width': 1.5,
      'circle-opacity': 0.85,
    },
  },

  /* placeholder for a computed route (filled by /api/route later) */
  {
    id: 'route-line',
    type: 'line',
    source: 'overlay-route',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': '#34c77a',
      'line-width': 3,
      'line-opacity': 0.9,
    },
  },

  {
    id: 'sim-route-line',
    type: 'line',
    source: 'overlay-sim-routes',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': '#22d3ee',
      'line-width': [
        'interpolate', ['linear'], ['get', 'flightCount'],
        1, 1.5,
        20, 3.5,
        80, 6,
      ],
      'line-opacity': 0.5,
    },
  },

  {
    id: 'sim-aircraft-circle',
    type: 'circle',
    source: 'overlay-sim-aircraft',
    paint: {
      'circle-radius': [
        'match', ['get', 'typeId'],
        'a2', 6,
        'a4', 7,
        'a6', 8,
        'a8', 9,
        7,
      ],
      'circle-color': [
        'match', ['get', 'typeId'],
        'a2', '#94a3b8',
        'a4', '#38bdf8',
        'a6', '#34d399',
        'a8', '#f59e0b',
        '#e5e7eb',
      ],
      'circle-stroke-color': '#e6edf5',
      'circle-stroke-width': 1.4,
      'circle-opacity': 0.9,
    },
  },
];

function mbtilesStyle() {
  return {
    version: 8,
    glyphs: GLYPHS_URL,
    sources: {
      basemap: {
        type: 'vector',
        tiles: [`${location.origin}/tiles/{z}/{x}/{y}.pbf`],
        minzoom: 0,
        maxzoom: 14,
      },
      ...OVERLAY_SOURCES(),
    },
    layers: [
      { id: 'background', type: 'background', paint: { 'background-color': '#0a1018' } },
      { id: 'landcover', type: 'fill', source: 'basemap', 'source-layer': 'landcover',
        paint: { 'fill-color': '#101a26', 'fill-opacity': 0.7 } },
      { id: 'landuse', type: 'fill', source: 'basemap', 'source-layer': 'landuse',
        paint: { 'fill-color': '#0f1822', 'fill-opacity': 0.7 } },
      { id: 'park', type: 'fill', source: 'basemap', 'source-layer': 'park',
        paint: { 'fill-color': '#0f2018', 'fill-opacity': 0.85 } },
      { id: 'water', type: 'fill', source: 'basemap', 'source-layer': 'water',
        paint: { 'fill-color': '#0c1a2c' } },
      { id: 'waterway', type: 'line', source: 'basemap', 'source-layer': 'waterway',
        paint: { 'line-color': '#1a3a5a', 'line-width': 1 } },
      { id: 'boundary', type: 'line', source: 'basemap', 'source-layer': 'boundary',
        paint: { 'line-color': '#2a3850', 'line-width': 0.6, 'line-dasharray': [2, 2] } },
      { id: 'transportation', type: 'line', source: 'basemap', 'source-layer': 'transportation',
        paint: { 'line-color': '#2a3a52',
                 'line-width': ['interpolate', ['linear'], ['zoom'], 5, 0.4, 10, 1, 14, 2.5] } },
      { id: 'building', type: 'fill', source: 'basemap', 'source-layer': 'building', minzoom: 13,
        paint: { 'fill-color': '#1a2738', 'fill-opacity': 0.6 } },
      ...OVERLAY_LAYERS,
    ],
  };
}

function fallbackStyle() {
  return {
    version: 8,
    glyphs: GLYPHS_URL,
    sources: {
      'fallback-raster': {
        type: 'raster',
        tiles: [
          'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
          'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
          'https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
        ],
        tileSize: 256,
        attribution: '© OpenStreetMap contributors © CARTO',
      },
      ...OVERLAY_SOURCES(),
    },
    layers: [
      { id: 'background', type: 'background', paint: { 'background-color': '#0a1018' } },
      { id: 'fallback-tiles', type: 'raster', source: 'fallback-raster',
        paint: { 'raster-opacity': 0.92, 'raster-saturation': -0.15 } },
      ...OVERLAY_LAYERS,
    ],
  };
}

function emptyFc() {
  return { type: 'FeatureCollection', features: [] };
}
