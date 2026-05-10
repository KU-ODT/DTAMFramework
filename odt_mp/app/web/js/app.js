/* app.js - main application initialization */
window.ODT = window.ODT || {};

(async function () {
  'use strict';

  ODT.I18n?.init();
  ODT.OperatorLog?.init();

  let config;
  try {
    config = await ODT.api('/api/config');
  } catch (e) {
    console.error('Failed to load config:', e);
    ODT.OperatorLog?.warn(
      ODT.t('log_using_fallback_title'),
      ODT.t('log_using_fallback_message')
    );
    config = {
      center: [126.978, 37.5665],
      zoom: 11.5,
      minZoom: 0,
      maxZoom: 14,
      dem: {
        enabled: true,
        tileUrl: '/dem/{z}/{x}/{y}.png',
        tileSize: 256,
        maxZoom: 12,
        encoding: 'terrarium',
        exaggeration: 1.15,
        pitchThreshold: 18,
        terrainZoomThreshold: 9,
        hillshadeMinZoom: 8,
        buildingPitchThreshold: 28,
        buildingZoomThreshold: 13.5,
      },
    };
  }

  const map = ODT.MapManager.init(config);

  ODT.Sidebar.init();
  ODT.AltitudeProfile.init();
  ODT.Settings.init();

  map.once('load', () => {
    ODT.Mission.init();
    ODT.Simulator?.init();
    ODT.Converter?.init();
    ODT.Settings.loadSettings();
    ODT.OperatorLog?.info(
      ODT.t('log_ready_title'),
      ODT.t('log_ready_message')
    );
  });

  const connectBtn = document.getElementById('connect-btn');
  if (connectBtn) {
    connectBtn.addEventListener('click', async () => {
      await ODT.Simulator?.toggleConnection?.();
    });
  }

  const playBtn = document.getElementById('play-btn');
  if (playBtn) {
    playBtn.addEventListener('click', () => {
      ODT.Mission.executeMission();
    });
  }

  const stopBtn = document.getElementById('stop-btn');
  if (stopBtn) {
    stopBtn.addEventListener('click', async () => {
      await ODT.Simulator?.stopSimulation?.();
    });
  }

  console.log('[ODT Mission Planner] Initialized');
})();
