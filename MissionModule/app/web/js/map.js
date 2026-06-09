/* map.js — MapLibre GL initialisation and style management */
window.ODT = window.ODT || {};

ODT.MapManager = (function () {
  let map = null;
  let config = null;
  let initialView = null;
  let terrainEnabled = false;
  let sceneUpdateHandle = 0;
  const scenePrefs = {
    buildingsVisible: true,
  };

  function getDemConfig() {
    return {
      enabled: config?.dem?.enabled !== false,
      tileUrl: config?.dem?.tileUrl || config?.demUrl || '/dem/{z}/{x}/{y}.png',
      tileSize: config?.dem?.tileSize || 256,
      maxZoom: config?.dem?.maxZoom || 12,
      encoding: config?.dem?.encoding || 'terrarium',
      exaggeration: config?.dem?.exaggeration || 1.15,
      pitchThreshold: config?.dem?.pitchThreshold ?? 18,
      terrainZoomThreshold: config?.dem?.terrainZoomThreshold ?? 9,
      hillshadeMinZoom: config?.dem?.hillshadeMinZoom ?? 8,
      buildingPitchThreshold: config?.dem?.buildingPitchThreshold ?? 28,
      buildingZoomThreshold: config?.dem?.buildingZoomThreshold ?? 13.5,
    };
  }

  function setLayerVisibility(id, visible) {
    if (!map || !map.getLayer(id)) return;
    const next = visible ? 'visible' : 'none';
    if (map.getLayoutProperty(id, 'visibility') === next) return;
    map.setLayoutProperty(id, 'visibility', next);
  }

  function applyBackdrop(theme) {
    if (!map) return;
    const pal = ODT.BASE_MAP_PALETTES[theme] || ODT.BASE_MAP_PALETTES.dark;
    const mapEl = document.getElementById('map');
    const canvas = map.getCanvas();
    const canvasContainer = map.getCanvasContainer();

    if (mapEl) mapEl.style.background = pal.sky;
    if (canvas) canvas.style.backgroundColor = pal.sky;
    if (canvasContainer) canvasContainer.style.background = pal.sky;
  }

  function buildStyle(theme) {
    const pal = ODT.BASE_MAP_PALETTES[theme] || ODT.BASE_MAP_PALETTES.dark;
    const sourceMaxZoom = config.maxZoom || 14;
    const dem = getDemConfig();
    const sources = {
      mbtiles: {
        type: 'vector',
        tiles: [window.location.origin + '/tiles/{z}/{x}/{y}.pbf'],
        minzoom: config.minZoom || 0,
        maxzoom: sourceMaxZoom,
      },
      osm: {
        type: 'raster',
        tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
        tileSize: 256,
        minzoom: 0,
        maxzoom: 19,
      },
    };

    if (dem.enabled) {
      sources.dem = {
        type: 'raster-dem',
        tiles: [dem.tileUrl],
        tileSize: dem.tileSize,
        maxzoom: dem.maxZoom,
        encoding: dem.encoding,
      };
    }

    return {
      version: 8,
      sources,
      layers: [
        {
          id: 'background',
          type: 'background',
          paint: { 'background-color': pal.background },
        },
        {
          id: 'landcover',
          type: 'fill',
          source: 'mbtiles',
          'source-layer': 'landcover',
          paint: {
            'fill-color': pal.landcover,
            'fill-opacity': 0.7,
            'fill-opacity-transition': { duration: 300 },
          },
        },
        {
          id: 'landuse',
          type: 'fill',
          source: 'mbtiles',
          'source-layer': 'landuse',
          paint: {
            'fill-color': pal.landuse,
            'fill-opacity': 0.7,
            'fill-opacity-transition': { duration: 300 },
          },
        },
        {
          id: 'park',
          type: 'fill',
          source: 'mbtiles',
          'source-layer': 'park',
          paint: {
            'fill-color': pal.park,
            'fill-opacity': 0.85,
            'fill-opacity-transition': { duration: 300 },
          },
        },
        {
          id: 'water',
          type: 'fill',
          source: 'mbtiles',
          'source-layer': 'water',
          paint: {
            'fill-color': pal.water,
            'fill-color-transition': { duration: 300 },
          },
        },
        ...(dem.enabled
          ? [
              {
                id: 'hillshade',
                type: 'hillshade',
                source: 'dem',
                layout: { visibility: 'none' },
                paint: {
                  'hillshade-illumination-anchor': 'viewport',
                  'hillshade-exaggeration': theme === 'dark' ? 0.28 : 0.22,
                  'hillshade-highlight-color':
                    theme === 'dark' ? 'rgba(255,255,255,0.08)' : 'rgba(255,255,255,0.42)',
                  'hillshade-shadow-color':
                    theme === 'dark' ? 'rgba(5,10,18,0.34)' : 'rgba(70,96,124,0.18)',
                  'hillshade-accent-color':
                    theme === 'dark' ? 'rgba(109,143,179,0.12)' : 'rgba(125,173,214,0.18)',
                },
              },
            ]
          : []),
        {
          id: 'waterway',
          type: 'line',
          source: 'mbtiles',
          'source-layer': 'waterway',
          paint: {
            'line-color': pal.waterway,
            'line-width': 1,
            'line-color-transition': { duration: 300 },
          },
        },
        {
          id: 'boundary',
          type: 'line',
          source: 'mbtiles',
          'source-layer': 'boundary',
          paint: {
            'line-color': pal.boundary,
            'line-width': 1,
            'line-dasharray': [2, 2],
            'line-color-transition': { duration: 300 },
          },
        },
        {
          id: 'transportation',
          type: 'line',
          source: 'mbtiles',
          'source-layer': 'transportation',
          paint: {
            'line-color': pal.transportation,
            'line-width': ['interpolate', ['linear'], ['zoom'], 5, 0.4, 10, 1, 14, 2.5],
            'line-color-transition': { duration: 300 },
          },
        },
        {
          id: 'building',
          type: 'fill',
          source: 'mbtiles',
          'source-layer': 'building',
          minzoom: 13,
          paint: {
            'fill-color': pal.building,
            'fill-opacity': 0.6,
            'fill-opacity-transition': { duration: 300 },
          },
        },
        {
          id: 'building-3d',
          type: 'fill-extrusion',
          source: 'mbtiles',
          'source-layer': 'building',
          minzoom: 14,
          layout: { visibility: 'none' },
          paint: {
            'fill-extrusion-color': pal.building,
            'fill-extrusion-height': ['interpolate', ['linear'], ['zoom'], 14, 0, 16, 12],
            'fill-extrusion-base': 0,
            'fill-extrusion-opacity': 0.5,
            'fill-extrusion-opacity-transition': { duration: 500 },
          },
        },
        {
          id: 'osm-raster',
          type: 'raster',
          source: 'osm',
          layout: { visibility: 'none' },
          paint: {
            'raster-opacity': 1,
            'raster-fade-duration': 0,
          },
        },
      ],
    };
  }

  function updateTheme(theme) {
    if (!map) return;
    const pal = ODT.BASE_MAP_PALETTES[theme] || ODT.BASE_MAP_PALETTES.dark;
    const layerMap = {
      background: { 'background-color': pal.background },
      hillshade: {
        'hillshade-exaggeration': theme === 'dark' ? 0.28 : 0.22,
        'hillshade-highlight-color':
          theme === 'dark' ? 'rgba(255,255,255,0.08)' : 'rgba(255,255,255,0.42)',
        'hillshade-shadow-color':
          theme === 'dark' ? 'rgba(5,10,18,0.34)' : 'rgba(70,96,124,0.18)',
        'hillshade-accent-color':
          theme === 'dark' ? 'rgba(109,143,179,0.12)' : 'rgba(125,173,214,0.18)',
      },
      landcover: { 'fill-color': pal.landcover },
      landuse: { 'fill-color': pal.landuse },
      park: { 'fill-color': pal.park },
      water: { 'fill-color': pal.water },
      waterway: { 'line-color': pal.waterway },
      boundary: { 'line-color': pal.boundary },
      transportation: { 'line-color': pal.transportation },
      building: { 'fill-color': pal.building },
      'building-3d': { 'fill-extrusion-color': pal.building },
    };
    for (const [id, props] of Object.entries(layerMap)) {
      if (!map.getLayer(id)) continue;
      for (const [prop, val] of Object.entries(props)) {
        try {
          map.setPaintProperty(id, prop, val);
        } catch (_) {}
      }
    }
    applyBackdrop(theme);
    scheduleSceneUpdate();
  }

  function syncSceneState() {
    if (!map) return;
    const dem = getDemConfig();
    const pitch = map.getPitch();
    const zoom = map.getZoom();

    const shouldEnableTerrain =
      dem.enabled &&
      zoom >= dem.terrainZoomThreshold &&
      pitch >= dem.pitchThreshold &&
      !!map.getSource('dem');

    if (shouldEnableTerrain !== terrainEnabled) {
      map.setTerrain(
        shouldEnableTerrain
          ? {
              source: 'dem',
              exaggeration: dem.exaggeration,
            }
          : null
      );
      terrainEnabled = shouldEnableTerrain;
    }

    const hillshadeVisible =
      dem.enabled && zoom >= dem.hillshadeMinZoom && !terrainEnabled;
    setLayerVisibility('hillshade', hillshadeVisible);

    const building3dVisible =
      scenePrefs.buildingsVisible &&
      zoom >= dem.buildingZoomThreshold &&
      pitch >= dem.buildingPitchThreshold;
    setLayerVisibility('building-3d', building3dVisible);
    setLayerVisibility('building', scenePrefs.buildingsVisible && !building3dVisible);
  }

  function scheduleSceneUpdate() {
    if (!map || sceneUpdateHandle) return;
    sceneUpdateHandle = window.requestAnimationFrame(() => {
      sceneUpdateHandle = 0;
      syncSceneState();
    });
  }

  function createResetViewControl() {
    return {
      onAdd() {
        const container = document.createElement('div');
        container.className = 'maplibregl-ctrl maplibregl-ctrl-group map-reset-control';

        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'map-reset-button';
        button.innerHTML = `
          <svg class="map-reset-icon" viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="12" r="7.25"></circle>
          </svg>
        `;

        const applyLabel = () => {
          const label = ODT.t ? ODT.t('reset_view') : 'Reset view';
          button.title = label;
          button.setAttribute('aria-label', label);
        };

        button.addEventListener('click', () => {
          resetView();
        });

        this.languageHandler = applyLabel;
        document.addEventListener('odt:languagechange', this.languageHandler);
        applyLabel();

        container.appendChild(button);
        this.container = container;
        return container;
      },
      onRemove() {
        if (this.languageHandler) {
          document.removeEventListener('odt:languagechange', this.languageHandler);
        }
        this.container?.remove();
      },
    };
  }

  function init(cfg) {
    config = cfg;
    initialView = {
      center: Array.isArray(config.center) ? [...config.center] : [126.978, 37.5665],
      zoom: config.zoom || 11.5,
      pitch: config.pitch || 0,
      bearing: config.bearing || 0,
    };
    const theme = ODT.getTheme();
    const style = buildStyle(theme);
    const sourceMaxZoom = config.maxZoom || 14;
    const viewMaxZoom = Math.max(sourceMaxZoom + 5, 18);

    map = new maplibregl.Map({
      container: 'map',
      style: style,
      center: initialView.center,
      zoom: initialView.zoom,
      pitch: initialView.pitch,
      bearing: initialView.bearing,
      minZoom: config.minZoom || 0,
      maxZoom: viewMaxZoom,
      maxPitch: 85,
      attributionControl: false,
    });

    map.addControl(createResetViewControl(), 'bottom-right');
    map.addControl(
      new maplibregl.NavigationControl({ showCompass: true, visualizePitch: true }),
      'bottom-right'
    );

    map.once('load', () => {
      applyBackdrop(ODT.getTheme());
      scheduleSceneUpdate();
      map.on('pitch', scheduleSceneUpdate);
      map.on('zoom', scheduleSceneUpdate);
    });

    return map;
  }

  function getMap() {
    return map;
  }

  function flyTo(center, zoom) {
    if (!map) return;
    map.flyTo({ center: center, zoom: zoom || 14, duration: 1200 });
  }

  function resetView() {
    if (!map || !initialView) return;
    map.flyTo({
      center: initialView.center,
      zoom: initialView.zoom,
      pitch: initialView.pitch,
      bearing: initialView.bearing,
      duration: 1200,
    });
  }

  function setBuildingsVisible(visible) {
    scenePrefs.buildingsVisible = !!visible;
    scheduleSceneUpdate();
  }

  function setOsmBaseVisible(visible) {
    setLayerVisibility('osm-raster', !!visible);
  }

  return {
    init,
    getMap,
    buildStyle,
    updateTheme,
    flyTo,
    resetView,
    setBuildingsVisible,
    setOsmBaseVisible,
  };
})();
