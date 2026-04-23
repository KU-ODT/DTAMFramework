/* settings.js - settings management and toggles */
window.ODT = window.ODT || {};

ODT.Settings = (function () {
  function init() {
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
      themeToggle.addEventListener('click', () => {
        themeToggle.classList.toggle('active');
        ODT.toggleTheme();
        ODT.MapManager.updateTheme(ODT.getTheme());
      });
    }

    const themeBtn = document.getElementById('theme-btn');
    if (themeBtn) {
      themeBtn.addEventListener('click', () => {
        ODT.toggleTheme();
        ODT.MapManager.updateTheme(ODT.getTheme());
        if (themeToggle) {
          themeToggle.classList.toggle('active', ODT.getTheme() === 'light');
        }
      });
    }

    const corridorToggle = document.getElementById('corridor-toggle');
    if (corridorToggle) {
      corridorToggle.addEventListener('click', () => {
        corridorToggle.classList.toggle('active');
        ODT.Mission.setCorridorVisibility(corridorToggle.classList.contains('active'));
      });
    }

    const buildingToggle = document.getElementById('building-toggle');
    if (buildingToggle) {
      buildingToggle.addEventListener('click', () => {
        buildingToggle.classList.toggle('active');
        ODT.Mission.setBuildingVisibility(buildingToggle.classList.contains('active'));
      });
    }

    const saveBtn = document.getElementById('settings-save');
    if (saveBtn) {
      saveBtn.addEventListener('click', saveSettings);
    }
  }

  async function saveSettings() {
    const host = document.getElementById('settings-host')?.value || '127.0.0.1';
    const port = parseInt(document.getElementById('settings-port')?.value, 10) || 41451;
    const speed = parseFloat(document.getElementById('settings-speed')?.value) || 30;
    const alt = parseFloat(document.getElementById('settings-altitude')?.value) || 300;

    try {
      await ODT.putJSON('/api/settings', {
        airsim_host: host,
        airsim_port: port,
        default_speed_mps: speed,
        default_altitude_m: alt,
      });
      console.log('Settings saved');
      ODT.OperatorLog?.success(
        ODT.t('log_settings_saved_title'),
        ODT.t('log_settings_saved_message', { host, port, speed, alt })
      );
    } catch (e) {
      console.error('Settings save failed:', e);
      ODT.OperatorLog?.error(
        ODT.t('log_settings_save_failed_title'),
        ODT.humanizeError(e, ODT.t('log_settings_save_failed_message'))
      );
    }
  }

  async function loadSettings() {
    try {
      const s = await ODT.api('/api/settings');
      const hostInput = document.getElementById('settings-host');
      const portInput = document.getElementById('settings-port');
      const speedInput = document.getElementById('settings-speed');
      const altInput = document.getElementById('settings-altitude');
      if (hostInput) hostInput.value = s.airsim_host || '127.0.0.1';
      if (portInput) portInput.value = s.airsim_port || 41451;
      if (speedInput) speedInput.value = s.default_speed_mps || 30;
      if (altInput) altInput.value = s.default_altitude_m || 300;
    } catch (e) {
      console.error('Failed to load settings:', e);
      ODT.OperatorLog?.warn(
        ODT.t('log_settings_unavailable_title'),
        ODT.t('log_settings_unavailable_message')
      );
    }
  }

  return { init, saveSettings, loadSettings };
})();
