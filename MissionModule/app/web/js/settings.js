/* settings.js — DTAM Mission Planner settings (DTAM target + map/mission defaults). */
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

  function fieldValue(id, fallback) {
    const el = document.getElementById(id);
    if (!el) return fallback;
    const text = String(el.value || '').trim();
    return text || fallback;
  }

  function fieldInt(id, fallback) {
    const el = document.getElementById(id);
    if (!el) return fallback;
    const n = parseInt(el.value, 10);
    return Number.isFinite(n) ? n : fallback;
  }

  function fieldFloat(id, fallback) {
    const el = document.getElementById(id);
    if (!el) return fallback;
    const n = parseFloat(el.value);
    return Number.isFinite(n) ? n : fallback;
  }

  async function saveSettings() {
    const payload = {
      dtam_target_ip: fieldValue('settings-dtam-target-ip', '127.0.0.1'),
      dtam_ws_port: fieldInt('settings-dtam-ws-port', 8096),
      default_speed_mps: fieldFloat('settings-speed', 30),
      default_altitude_m: fieldFloat('settings-altitude', 300),
    };

    try {
      await ODT.putJSON('/api/settings', payload);
      ODT.OperatorLog?.success(
        ODT.t('log_settings_saved_title'),
        `DTAM → ws://${payload.dtam_target_ip}:${payload.dtam_ws_port}/ws/dtam`
      );
      try {
        await ODT.Dtam?.refreshStatus?.(true);
      } catch (_) {}
    } catch (e) {
      ODT.OperatorLog?.error(
        ODT.t('log_settings_save_failed_title'),
        ODT.humanizeError(e, ODT.t('log_settings_save_failed_message'))
      );
    }
  }

  async function loadSettings() {
    try {
      const s = await ODT.api('/api/settings');
      setFieldValue('settings-dtam-target-ip', s.dtam_target_ip || '127.0.0.1');
      setFieldValue('settings-dtam-ws-port', s.dtam_ws_port || 8096);
      setFieldValue('settings-speed', s.default_speed_mps ?? 30);
      setFieldValue('settings-altitude', s.default_altitude_m ?? 300);
    } catch (e) {
      ODT.OperatorLog?.warn(
        ODT.t('log_settings_unavailable_title'),
        ODT.t('log_settings_unavailable_message')
      );
    }
  }

  function setFieldValue(id, value) {
    const el = document.getElementById(id);
    if (el) el.value = value;
  }

  return { init, saveSettings, loadSettings };
})();
