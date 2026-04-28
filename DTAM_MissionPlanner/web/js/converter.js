window.ODT = window.ODT || {};

ODT.Converter = (function () {
  const SEOUL_CENTER = [126.978, 37.5665];
  const SEOUL_ZOOM = 12.4;
  const AXIS_PREVIEW_LENGTH_M = 180;
  const DEFAULT_X_AXIS_HEADING = 90;
  const DEFAULT_Y_AXIS_HEADING = 180;

  let vertiports = [];
  let vertiportLookup = new Map();
  let settingsSummary = null;
  let targetSelection = null;
  let activeSpawnLayout = null;
  let spawnPointLookup = new Map();
  let spawnPointMarkers = [];
  let selectedSpawnPointId = '';
  let mapPickMode = '';
  let visualizationEnabled = false;
  let targetMarker = null;
  let playerStartMarker = null;
  let playerStartLabelMarker = null;
  let targetLabelMarker = null;
  let xAxisLabelMarker = null;
  let yAxisLabelMarker = null;
  let lastCopySnippet = '';

  function init() {
    bindUi();
    attachMapHandlers();
    updateMapPickUi();
    updateVisualizationUi();
    loadConverterData();
  }

  function bindUi() {
    document.getElementById('converter-open-osm-btn')?.addEventListener('click', () => {
      ODT.MapManager.setOsmBaseVisible(true);
      ODT.MapManager.flyTo(SEOUL_CENTER, SEOUL_ZOOM);
      setStatus('OSM base is active. Click the map or choose a vertiport.');
    });

    document.getElementById('converter-load-settings-btn')?.addEventListener('click', () => {
      loadSettingsSummary();
    });

    document.getElementById('converter-vertiport-select')?.addEventListener('change', () => {
      handleVertiportSelectionChange();
    });

    document.getElementById('converter-visual-toggle-btn')?.addEventListener('click', () => {
      visualizationEnabled = !visualizationEnabled;
      updateVisualizationUi();
      refreshVisualization();
    });

    document.getElementById('converter-copy-result-btn')?.addEventListener('click', async () => {
      await copyResultSnippet();
    });

    document.getElementById('converter-pick-toggle')?.addEventListener('click', () => {
      mapPickMode = mapPickMode === 'target' ? '' : 'target';
      updateMapPickUi();
    });

    document.getElementById('converter-pick-player-start-btn')?.addEventListener('click', () => {
      mapPickMode = mapPickMode === 'playerStart' ? '' : 'playerStart';
      updateMapPickUi();
    });

    document.getElementById('converter-use-origin-btn')?.addEventListener('click', () => {
      applyOriginToPlayerStart();
    });

    document.getElementById('converter-use-vertiport-btn')?.addEventListener('click', () => {
      const select = document.getElementById('converter-vertiport-select');
      const name = select?.value || '';
      if (!name || !vertiportLookup.has(name)) {
        setStatus('Select a vertiport first.');
        return;
      }
      const port = vertiportLookup.get(name);
      selectTarget({
        lat: Number(port.lat),
        lon: Number(port.lon),
        ground_m: Number(port.ground_m ?? 0),
        source: `vertiport:${port.name}`,
        label: port.name,
        alt_m: Number(port.ground_m ?? 0),
      });
      ODT.MapManager.flyTo([Number(port.lon), Number(port.lat)], 13.8);
    });

    document.getElementById('converter-spawn-point-select')?.addEventListener('change', () => {
      const value = document.getElementById('converter-spawn-point-select')?.value || '';
      if (!value) {
        selectedSpawnPointId = '';
        refreshVisualization();
        return;
      }
      useSelectedSpawnPoint(value);
    });

    document.getElementById('converter-use-spawn-btn')?.addEventListener('click', () => {
      useSelectedSpawnPoint();
    });

    [
      'converter-player-start-lat',
      'converter-player-start-lon',
      'converter-player-start-alt',
      'converter-x-axis-heading',
      'converter-y-axis-heading',
      'converter-target-alt',
    ].forEach((id) => {
      document.getElementById(id)?.addEventListener('input', () => {
        renderPlayerStartSummary();
        refreshVisualization();
        if (targetSelection) {
          refreshConversion();
        }
      });
    });
  }

  function attachMapHandlers() {
    const map = ODT.MapManager.getMap();
    if (!map) return;
    map.on('click', (event) => {
      if (!mapPickMode) return;
      const lat = Number(event.lngLat.lat);
      const lon = Number(event.lngLat.lng);
      if (mapPickMode === 'playerStart') {
        selectPlayerStartFromMap(lat, lon);
      } else {
        selectTarget({
          lat,
          lon,
          ground_m: null,
          source: 'map',
          label: 'Map pick',
        });
      }
      mapPickMode = '';
      updateMapPickUi();
    });
  }

  async function loadConverterData() {
    try {
      const ports = await ODT.api('/api/vertiports');
      vertiports = Array.isArray(ports) ? ports : [];
      vertiportLookup = new Map(vertiports.map((item) => [item.name, item]));
      populateVertiportSelect();
    } catch (error) {
      console.error('Failed to load converter vertiports:', error);
      setStatus(ODT.humanizeError(error, 'Failed to load vertiports.'));
    }

    try {
      await loadSettingsSummary();
    } catch (_) {
      // Converter still works with manual player-start input.
    }
  }

  async function loadSettingsSummary() {
    try {
      settingsSummary = await ODT.api('/api/converter/settings');
      renderSettingsSummary();
      return settingsSummary;
    } catch (error) {
      console.error('Failed to load AirSim settings summary:', error);
      setStatus(ODT.humanizeError(error, 'Failed to load settings.json.'));
      throw error;
    }
  }

  function renderSettingsSummary() {
    const pathInput = document.getElementById('converter-settings-path');
    const originView = document.getElementById('converter-origin-view');
    const vehicleView = document.getElementById('converter-vehicle-view');
    const rawPre = document.getElementById('converter-settings-preview');
    if (pathInput) {
      pathInput.value = settingsSummary?.path || '';
    }
    if (originView) {
      const origin = settingsSummary?.origin_geopoint;
      originView.textContent = origin
        ? `${formatNumber(origin.lat, 6)}, ${formatNumber(origin.lon, 6)}, ${formatNumber(origin.alt_m, 1)} m`
        : 'No OriginGeopoint';
    }
    if (vehicleView) {
      const vehicle = Array.isArray(settingsSummary?.vehicles) ? settingsSummary.vehicles[0] : null;
      vehicleView.textContent = vehicle
        ? `${vehicle.name}  X ${formatNumber(vehicle.x_m, 3)}  Y ${formatNumber(vehicle.y_m, 3)}  Z ${formatNumber(vehicle.z_m, 3)}  Yaw ${formatNumber(vehicle.yaw_deg, 1)}`
        : 'No vehicle block';
    }
    if (rawPre) {
      rawPre.textContent = settingsSummary?.raw
        ? JSON.stringify(settingsSummary.raw, null, 2)
        : 'settings.json not found.';
    }
    if (
      settingsSummary?.origin_geopoint &&
      !document.getElementById('converter-player-start-lat')?.value &&
      !document.getElementById('converter-player-start-lon')?.value
    ) {
      applyOriginToPlayerStart();
    }
    renderPlayerStartSummary();
    refreshVisualization();
    setStatus(settingsSummary?.exists ? 'settings.json loaded.' : 'settings.json not found.');
  }

  function populateVertiportSelect() {
    const select = document.getElementById('converter-vertiport-select');
    if (!select) return;
    select.innerHTML = '';
    const placeholder = new Option('Select vertiport...', '');
    select.appendChild(placeholder);
    [...vertiports]
      .sort((a, b) => String(a.name).localeCompare(String(b.name)))
      .forEach((item) => {
        select.appendChild(new Option(item.name, item.name));
      });
  }

  async function handleVertiportSelectionChange() {
    const name = document.getElementById('converter-vertiport-select')?.value || '';
    if (!name) {
      clearSpawnLayout();
      return;
    }
    await loadSpawnLayout(name);
  }

  async function loadSpawnLayout(name) {
    if (!name) {
      clearSpawnLayout();
      return;
    }
    try {
      const layout = await ODT.api(`/api/converter/vertiport-spawns?name=${encodeURIComponent(name)}`);
      activeSpawnLayout = layout;
      spawnPointLookup = new Map((layout?.points || []).map((point) => [point.id, point]));
      if (!spawnPointLookup.has(selectedSpawnPointId)) {
        selectedSpawnPointId = '';
      }
      populateSpawnPointSelect();
      renderSpawnLayoutSummary();
      refreshVisualization();
      setStatus(`${name} spawn layout loaded. Click a spawn point or choose one from the list.`);
    } catch (error) {
      console.error('Failed to load spawn layout:', error);
      clearSpawnLayout();
      setStatus(ODT.humanizeError(error, 'Failed to load spawn layout.'));
    }
  }

  function clearSpawnLayout() {
    activeSpawnLayout = null;
    spawnPointLookup = new Map();
    selectedSpawnPointId = '';
    populateSpawnPointSelect();
    renderSpawnLayoutSummary();
    refreshVisualization();
  }

  function populateSpawnPointSelect() {
    const select = document.getElementById('converter-spawn-point-select');
    const button = document.getElementById('converter-use-spawn-btn');
    if (!select) return;
    select.innerHTML = '';
    select.appendChild(new Option('Select spawn point...', ''));
    const points = Array.isArray(activeSpawnLayout?.points) ? activeSpawnLayout.points : [];
    points.forEach((point) => {
      const text = `${point.id}  ${point.label}  Yaw ${formatNumber(point.yaw_deg, 1)}`;
      select.appendChild(new Option(text, point.id));
    });
    select.disabled = !points.length;
    if (button) {
      button.disabled = !points.length;
    }
    select.value = selectedSpawnPointId && spawnPointLookup.has(selectedSpawnPointId) ? selectedSpawnPointId : '';
  }

  function renderSpawnLayoutSummary() {
    const view = document.getElementById('converter-spawn-layout-view');
    if (!view) return;
    if (!activeSpawnLayout) {
      view.textContent = '--';
      return;
    }
    const source = activeSpawnLayout.source_anchor || {};
    const count = Array.isArray(activeSpawnLayout.points) ? activeSpawnLayout.points.length : 0;
    view.textContent =
      `${activeSpawnLayout.vertiport_name}  ` +
      `Angle ${formatNumber(source.angle_deg, 1)} deg  ` +
      `X ${formatNumber(activeSpawnLayout.frame_heading_deg?.x, 1)} deg  ` +
      `Y ${formatNumber(activeSpawnLayout.frame_heading_deg?.y, 1)} deg  ` +
      `Points ${count}`;
  }

  function applyOriginToPlayerStart() {
    const origin = settingsSummary?.origin_geopoint;
    if (!origin) {
      setStatus('OriginGeopoint is not available in settings.json.');
      return;
    }
    setInputValue('converter-player-start-lat', origin.lat, 6);
    setInputValue('converter-player-start-lon', origin.lon, 6);
    setInputValue('converter-player-start-alt', origin.alt_m, 1);
    renderPlayerStartSummary();
    refreshVisualization();
    if (targetSelection) {
      refreshConversion();
    }
  }

  function setInputValue(id, value, decimals) {
    const input = document.getElementById(id);
    if (!input) return;
    if (value == null || !Number.isFinite(Number(value))) {
      input.value = '';
      return;
    }
    input.value = Number(value).toFixed(decimals);
  }

  async function selectPlayerStartFromMap(lat, lon) {
    setInputValue('converter-player-start-lat', lat, 6);
    setInputValue('converter-player-start-lon', lon, 6);
    try {
      const elevation = await ODT.api(`/api/elevation?lon=${encodeURIComponent(lon)}&lat=${encodeURIComponent(lat)}`);
      if (elevation?.ground_m != null) {
        setInputValue('converter-player-start-alt', elevation.ground_m, 1);
      }
    } catch (error) {
      console.warn('Failed to sample player start elevation:', error);
    }
    renderPlayerStartSummary();
    refreshVisualization();
    if (targetSelection) {
      refreshConversion();
    } else {
      setStatus('Player Start updated from the map.');
    }
  }

  function getCurrentPlayerStart() {
    const lat = parseNumberInput('converter-player-start-lat');
    const lon = parseNumberInput('converter-player-start-lon');
    const alt = parseNumberInput('converter-player-start-alt');
    const xHeading = parseNumberInput('converter-x-axis-heading');
    const yHeading = parseNumberInput('converter-y-axis-heading');
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      return null;
    }
    return {
      lat,
      lon,
      alt: Number.isFinite(alt) ? alt : 0,
      xHeading: Number.isFinite(xHeading) ? xHeading : DEFAULT_X_AXIS_HEADING,
      yHeading: Number.isFinite(yHeading) ? yHeading : DEFAULT_Y_AXIS_HEADING,
    };
  }

  function renderPlayerStartSummary() {
    const view = document.getElementById('converter-player-start-view');
    if (!view) return;
    const start = getCurrentPlayerStart();
    if (!start) {
      view.textContent = '--';
      return;
    }
    view.textContent =
      `${formatNumber(start.lat, 6)}, ${formatNumber(start.lon, 6)}  ` +
      `Alt ${formatNumber(start.alt, 1)} m  ` +
      `X ${formatNumber(start.xHeading, 1)} deg  ` +
      `Y ${formatNumber(start.yHeading, 1)} deg`;
  }

  function updateMapPickUi() {
    const targetBtn = document.getElementById('converter-pick-toggle');
    const playerStartBtn = document.getElementById('converter-pick-player-start-btn');
    const status = document.getElementById('converter-pick-status');
    if (targetBtn) {
      targetBtn.classList.toggle('active', mapPickMode === 'target');
      targetBtn.textContent = mapPickMode === 'target' ? 'Picking Target...' : 'Pick on Map';
    }
    if (playerStartBtn) {
      playerStartBtn.classList.toggle('active', mapPickMode === 'playerStart');
      playerStartBtn.textContent = mapPickMode === 'playerStart' ? 'Picking Start...' : 'Pick Player Start';
    }
    if (status) {
      status.textContent = mapPickMode
        ? mapPickMode === 'playerStart'
          ? 'Click a player-start point on the map.'
          : 'Click a target point on the map.'
        : targetSelection
          ? `${targetSelection.label || 'Target'} selected`
          : 'No target selected';
      status.classList.toggle('active', !!mapPickMode);
    }
    const map = ODT.MapManager.getMap();
    if (map) {
      map.getCanvas().style.cursor = mapPickMode ? 'crosshair' : '';
    }
  }

  function useSelectedSpawnPoint(preferredId) {
    const select = document.getElementById('converter-spawn-point-select');
    const id = preferredId || selectedSpawnPointId || select?.value || '';
    if (!activeSpawnLayout || !id || !spawnPointLookup.has(id)) {
      setStatus('Select a spawn point first.');
      return;
    }
    const point = spawnPointLookup.get(id);
    selectedSpawnPointId = id;
    selectTarget({
      lat: Number(point.lat),
      lon: Number(point.lon),
      ground_m: point.ground_m == null ? null : Number(point.ground_m),
      source: `spawn:${activeSpawnLayout.vertiport_name}:${point.id}`,
      label: `${activeSpawnLayout.vertiport_name} / ${point.id}`,
      alt_m: point.alt_m == null ? null : Number(point.alt_m),
      spawn_yaw_deg: point.yaw_deg == null ? null : Number(point.yaw_deg),
      spawn_point_id: point.id,
      spawn_point_label: point.label,
    });
    if (select) {
      select.value = id;
    }
    ODT.MapManager.flyTo([Number(point.lon), Number(point.lat)], 15.8);
  }

  function selectTarget(target) {
    selectedSpawnPointId = target.spawn_point_id || '';
    targetSelection = {
      lat: Number(target.lat),
      lon: Number(target.lon),
      ground_m: target.ground_m == null ? null : Number(target.ground_m),
      source: target.source || 'map',
      label: target.label || 'Target',
      alt_m: target.alt_m == null ? null : Number(target.alt_m),
      spawn_yaw_deg: target.spawn_yaw_deg == null ? null : Number(target.spawn_yaw_deg),
      spawn_point_id: target.spawn_point_id || '',
      spawn_point_label: target.spawn_point_label || '',
    };
    const spawnSelect = document.getElementById('converter-spawn-point-select');
    if (spawnSelect) {
      spawnSelect.value = selectedSpawnPointId && spawnPointLookup.has(selectedSpawnPointId) ? selectedSpawnPointId : '';
    }
    refreshVisualization();
    renderTargetSummary();
    refreshConversion();
  }

  function refreshVisualization() {
    updatePlayerStartOverlay();
    renderSpawnPointOverlay();
    renderTargetMarker();
  }

  function renderTargetMarker() {
    const map = ODT.MapManager.getMap();
    if (!map || !targetSelection || !visualizationEnabled) {
      targetMarker?.remove();
      targetLabelMarker?.remove();
      return;
    }
    if (!targetMarker) {
      const el = document.createElement('div');
      el.className = 'converter-target-marker';
      el.innerHTML = '<span></span>';
      targetMarker = new maplibregl.Marker({ element: el, anchor: 'center' });
    }
    targetMarker.setLngLat([targetSelection.lon, targetSelection.lat]).addTo(map);
    targetLabelMarker = upsertHtmlMarker(
      targetLabelMarker,
      buildVisualLabelElement(
        'Target',
        buildTargetLabelText(),
        'is-target'
      ),
      [targetSelection.lon, targetSelection.lat],
      'top-left',
      [18, -18]
    );
  }

  function renderTargetSummary() {
    const view = document.getElementById('converter-target-view');
    if (!view) return;
    if (!targetSelection) {
      view.textContent = '--';
      return;
    }
    view.textContent = buildTargetSummaryText();
  }

  function renderSpawnPointOverlay() {
    clearSpawnPointOverlay();
    const map = ODT.MapManager.getMap();
    const points = Array.isArray(activeSpawnLayout?.points) ? activeSpawnLayout.points : [];
    if (!map || !visualizationEnabled || !activeSpawnLayout || !points.length) {
      return;
    }

    points.forEach((point) => {
      const element = buildSpawnMarkerElement(point);
      element.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        useSelectedSpawnPoint(point.id);
      });
      const marker = new maplibregl.Marker({ element, anchor: 'center' })
        .setLngLat([Number(point.lon), Number(point.lat)])
        .addTo(map);
      spawnPointMarkers.push(marker);
    });
  }

  function clearSpawnPointOverlay() {
    spawnPointMarkers.forEach((marker) => marker.remove());
    spawnPointMarkers = [];
  }

  function updatePlayerStartOverlay() {
    const map = ODT.MapManager.getMap();
    const start = getCurrentPlayerStart();
    if (!map) return;

    if (!start || !visualizationEnabled) {
      playerStartMarker?.remove();
      playerStartLabelMarker?.remove();
      xAxisLabelMarker?.remove();
      yAxisLabelMarker?.remove();
      if (map.getSource('converter-frame')) {
        map.getSource('converter-frame').setData(emptyFeatureCollection());
      }
      return;
    }

    if (!playerStartMarker) {
      const el = document.createElement('div');
      el.className = 'converter-player-start-marker';
      el.innerHTML = '<span>S</span>';
      playerStartMarker = new maplibregl.Marker({ element: el, anchor: 'center' });
    }
    playerStartMarker.setLngLat([start.lon, start.lat]).addTo(map);
    ensureFrameLayer(map);
    const frame = buildFrameFeatureCollection(start);
    map.getSource('converter-frame').setData(frame.collection);
    playerStartLabelMarker = upsertHtmlMarker(
      playerStartLabelMarker,
      buildVisualLabelElement(
        'Player Start',
        [
          `${formatNumber(start.lat, 6)}, ${formatNumber(start.lon, 6)}`,
          `Alt ${formatNumber(start.alt, 1)} m`,
          `X ${formatNumber(start.xHeading, 1)} deg / Y ${formatNumber(start.yHeading, 1)} deg`,
        ].join('\n'),
        'is-player-start'
      ),
      [start.lon, start.lat],
      'bottom-left',
      [18, 18]
    );
    xAxisLabelMarker = upsertHtmlMarker(
      xAxisLabelMarker,
      buildAxisLabelElement(`X ${formatNumber(start.xHeading, 1)} deg`, 'is-x'),
      [frame.xEnd.lon, frame.xEnd.lat],
      'left',
      [10, 0]
    );
    yAxisLabelMarker = upsertHtmlMarker(
      yAxisLabelMarker,
      buildAxisLabelElement(`Y ${formatNumber(start.yHeading, 1)} deg`, 'is-y'),
      [frame.yEnd.lon, frame.yEnd.lat],
      'left',
      [10, 0]
    );
  }

  function ensureFrameLayer(map) {
    if (!map.getSource('converter-frame')) {
      map.addSource('converter-frame', {
        type: 'geojson',
        data: emptyFeatureCollection(),
      });
    }
    if (!map.getLayer('converter-frame-lines')) {
      map.addLayer({
        id: 'converter-frame-lines',
        type: 'line',
        source: 'converter-frame',
        layout: {
          'line-cap': 'round',
          'line-join': 'round',
        },
        paint: {
          'line-width': 4,
          'line-opacity': 0.95,
          'line-color': [
            'match',
            ['get', 'axis'],
            'x',
            '#3b82f6',
            'y',
            '#10b981',
            '#f59e0b',
          ],
        },
      });
    }
  }

  function buildFrameFeatureCollection(start) {
    const xEnd = projectHeading(start.lat, start.lon, start.xHeading, AXIS_PREVIEW_LENGTH_M);
    const yEnd = projectHeading(start.lat, start.lon, start.yHeading, AXIS_PREVIEW_LENGTH_M);
    return {
      xEnd,
      yEnd,
      collection: {
        type: 'FeatureCollection',
        features: [
          {
            type: 'Feature',
            properties: { axis: 'x' },
            geometry: {
              type: 'LineString',
              coordinates: [
                [start.lon, start.lat],
                [xEnd.lon, xEnd.lat],
              ],
            },
          },
          {
            type: 'Feature',
            properties: { axis: 'y' },
            geometry: {
              type: 'LineString',
              coordinates: [
                [start.lon, start.lat],
                [yEnd.lon, yEnd.lat],
              ],
            },
          },
        ],
      },
    };
  }

  function emptyFeatureCollection() {
    return {
      type: 'FeatureCollection',
      features: [],
    };
  }

  async function refreshConversion() {
    if (!targetSelection) return;
    const payload = buildRequestPayload();
    if (!payload) {
      clearResultViews('Player Start and axis headings are required.');
      return;
    }
    try {
      const result = await ODT.postJSON('/api/converter/convert', payload);
      applyConversionResult(result);
    } catch (error) {
      console.error('Coordinate conversion failed:', error);
      clearResultViews(ODT.humanizeError(error, 'Coordinate conversion failed.'));
    }
  }

  function buildRequestPayload() {
    const playerStartLat = parseNumberInput('converter-player-start-lat');
    const playerStartLon = parseNumberInput('converter-player-start-lon');
    const playerStartAlt = parseNumberInput('converter-player-start-alt');
    const xAxisHeading = parseNumberInput('converter-x-axis-heading');
    const yAxisHeading = parseNumberInput('converter-y-axis-heading');
    if (
      !Number.isFinite(playerStartLat) ||
      !Number.isFinite(playerStartLon) ||
      !Number.isFinite(playerStartAlt) ||
      !Number.isFinite(xAxisHeading) ||
      !Number.isFinite(yAxisHeading)
    ) {
      return null;
    }
    const targetAltOverride = parseOptionalNumberInput('converter-target-alt');
    const effectiveTargetAlt = targetAltOverride != null
      ? targetAltOverride
      : targetSelection?.alt_m != null
        ? Number(targetSelection.alt_m)
        : null;
    return {
      player_start_lat: playerStartLat,
      player_start_lon: playerStartLon,
      player_start_alt_m: playerStartAlt,
      x_axis_heading_deg: xAxisHeading,
      y_axis_heading_deg: yAxisHeading,
      target_lat: targetSelection.lat,
      target_lon: targetSelection.lon,
      target_alt_m: effectiveTargetAlt,
    };
  }

  function applyConversionResult(result) {
    const unrealView = document.getElementById('converter-unreal-view');
    const nedView = document.getElementById('converter-ned-view');
    const metaView = document.getElementById('converter-meta-view');
    const jsonView = document.getElementById('converter-result-preview');
    const targetAltInput = document.getElementById('converter-target-alt');

    if (targetAltInput && !String(targetAltInput.value || '').trim() && result?.target) {
      targetAltInput.placeholder = `${formatNumber(result.target.alt_m, 1)} m`;
    }
    if (unrealView) {
      unrealView.textContent =
        `X ${formatNumber(result.custom_unreal_m?.x, 3)}  ` +
        `Y ${formatNumber(result.custom_unreal_m?.y, 3)}  ` +
        `Z ${formatNumber(result.custom_unreal_m?.z, 3)}`;
    }
    if (nedView) {
      nedView.textContent =
        `N ${formatNumber(result.local_ned_m?.north, 3)}  ` +
        `E ${formatNumber(result.local_ned_m?.east, 3)}  ` +
        `D ${formatNumber(result.local_ned_m?.down, 3)}`;
    }
    if (metaView) {
      const metaParts = [
        `Dist ${formatNumber(result.distance_m, 1)} m  ` +
        `Bearing ${formatNumber(result.bearing_deg, 1)} deg  ` +
        `Axis err ${formatNumber(result.orthogonality_error_deg, 2)} deg`,
      ];
      if (targetSelection?.spawn_yaw_deg != null && Number.isFinite(Number(targetSelection.spawn_yaw_deg))) {
        metaParts.push(`Yaw ${formatNumber(targetSelection.spawn_yaw_deg, 1)} deg`);
      }
      metaView.textContent = metaParts.join('  ');
    }
    lastCopySnippet = buildCopySnippet(result);
    if (jsonView) {
      jsonView.textContent = lastCopySnippet;
    }
    if (result?.target?.ground_m != null && targetSelection) {
      targetSelection.ground_m = Number(result.target.ground_m);
      renderTargetSummary();
    }
    refreshVisualization();
    updateCopyButtonState();
      setStatus('Target converted to AirSim XYZ (NED, Z=Down) coordinates.');
  }

  function clearResultViews(message) {
    const unrealView = document.getElementById('converter-unreal-view');
    const nedView = document.getElementById('converter-ned-view');
    const metaView = document.getElementById('converter-meta-view');
    const jsonView = document.getElementById('converter-result-preview');
    if (unrealView) unrealView.textContent = '--';
    if (nedView) nedView.textContent = '--';
    if (metaView) metaView.textContent = '--';
    lastCopySnippet = '';
    if (jsonView) jsonView.textContent = message || '';
    updateCopyButtonState();
    setStatus(message || 'Converter is ready.');
  }

  function buildCopySnippet(result) {
    const x = formatNumber(result?.custom_unreal_m?.x, 3);
    const y = formatNumber(result?.custom_unreal_m?.y, 3);
    const z = formatNumber(result?.custom_unreal_m?.z, 3);
    const lines = [
      `      "X": ${x},`,
      `      "Y": ${y},`,
      `      "Z": ${z},`,
    ];
    if (targetSelection?.spawn_yaw_deg != null && Number.isFinite(Number(targetSelection.spawn_yaw_deg))) {
      lines.push(`      "Yaw": ${formatNumber(targetSelection.spawn_yaw_deg, 3)},`);
    }
    return lines.join('\n');
  }

  function updateCopyButtonState() {
    const button = document.getElementById('converter-copy-result-btn');
    if (!button) return;
    button.disabled = !lastCopySnippet;
  }

  async function copyResultSnippet() {
    if (!lastCopySnippet) return;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(lastCopySnippet);
      } else {
        const textArea = document.createElement('textarea');
        textArea.value = lastCopySnippet;
        textArea.style.position = 'fixed';
        textArea.style.opacity = '0';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        document.execCommand('copy');
        textArea.remove();
      }
      setStatus('Result snippet copied to clipboard.');
    } catch (error) {
      console.error('Failed to copy converter result:', error);
      setStatus(ODT.humanizeError(error, 'Failed to copy result snippet.'));
    }
  }

  function buildVisualLabelElement(title, body, extraClassName) {
    const wrapper = document.createElement('div');
    wrapper.className = `converter-visual-label ${extraClassName || ''}`.trim();

    const titleEl = document.createElement('div');
    titleEl.className = 'converter-visual-label-title';
    titleEl.textContent = title;

    const bodyEl = document.createElement('div');
    bodyEl.className = 'converter-visual-label-body';
    bodyEl.textContent = body;

    wrapper.appendChild(titleEl);
    wrapper.appendChild(bodyEl);
    return wrapper;
  }

  function buildTargetLabelText() {
    return buildTargetDetailLines().join('\n');
  }

  function buildTargetSummaryText() {
    return buildTargetDetailLines().join('  ');
  }

  function buildTargetDetailLines() {
    if (!targetSelection) {
      return ['--'];
    }
    const lines = [
      `${targetSelection.label}  ${formatNumber(targetSelection.lat, 6)}, ${formatNumber(targetSelection.lon, 6)}`,
      `DEM ${targetSelection.ground_m == null ? '--' : `${formatNumber(targetSelection.ground_m, 1)} m`}`,
    ];
    if (targetSelection.alt_m != null && Number.isFinite(Number(targetSelection.alt_m))) {
      lines.push(`Target Alt ${formatNumber(targetSelection.alt_m, 1)} m`);
    }
    if (targetSelection.spawn_yaw_deg != null && Number.isFinite(Number(targetSelection.spawn_yaw_deg))) {
      lines.push(`Spawn Yaw ${formatNumber(targetSelection.spawn_yaw_deg, 1)} deg`);
    }
    if (targetSelection.spawn_point_label) {
      lines.push(`Layout ${targetSelection.spawn_point_label}`);
    }
    return lines;
  }

  function buildSpawnMarkerElement(point) {
    const el = document.createElement('button');
    el.type = 'button';
    el.className = `converter-spawn-marker ${selectedSpawnPointId === point.id ? 'is-selected' : ''}`.trim();
    el.title = `${point.id} ${point.label} / yaw ${formatNumber(point.yaw_deg, 1)} deg`;
    el.textContent = String(point.id || '').replace(/^S/, '');
    return el;
  }

  function buildAxisLabelElement(text, extraClassName) {
    const el = document.createElement('div');
    el.className = `converter-axis-label ${extraClassName || ''}`.trim();
    el.textContent = text;
    return el;
  }

  function upsertHtmlMarker(marker, element, lngLat, anchor, offset) {
    const map = ODT.MapManager.getMap();
    if (!map) {
      marker?.remove();
      return null;
    }
    marker?.remove();
    marker = new maplibregl.Marker({
      element,
      anchor: anchor || 'center',
      offset: offset || [0, 0],
    });
    marker.setLngLat(lngLat).addTo(map);
    return marker;
  }

  function projectHeading(lat, lon, headingDeg, distanceM) {
    const headingRad = (Number(headingDeg) * Math.PI) / 180;
    const northM = Math.cos(headingRad) * distanceM;
    const eastM = Math.sin(headingRad) * distanceM;
    const metersPerDegLat = 111320;
    const metersPerDegLon = Math.max(1, Math.cos((lat * Math.PI) / 180) * 111320);
    return {
      lat: lat + (northM / metersPerDegLat),
      lon: lon + (eastM / metersPerDegLon),
    };
  }

  function parseNumberInput(id) {
    const value = document.getElementById(id)?.value;
    const number = Number(value);
    return Number.isFinite(number) ? number : NaN;
  }

  function parseOptionalNumberInput(id) {
    const value = String(document.getElementById(id)?.value || '').trim();
    if (!value) return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function formatNumber(value, decimals) {
    return value == null || !Number.isFinite(Number(value))
      ? '--'
      : Number(value).toFixed(decimals);
  }

  function setStatus(message) {
    const status = document.getElementById('converter-status');
    if (status) {
      status.textContent = message || '';
    }
  }

  function updateVisualizationUi() {
    const button = document.getElementById('converter-visual-toggle-btn');
    if (!button) return;
    button.classList.toggle('active', visualizationEnabled);
    button.textContent = visualizationEnabled ? 'Vis On' : 'Vis Off';
    button.title = visualizationEnabled ? 'Visualization On' : 'Visualization Off';
  }

  function isMapPickActive() {
    return !!mapPickMode;
  }

  return {
    init,
    isMapPickActive,
  };
})();
