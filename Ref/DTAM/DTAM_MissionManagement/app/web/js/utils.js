/* utils.js — shared constants and utility functions */
window.ODT = window.ODT || {};

ODT.FT_TO_M = 0.3048;

ODT.BASE_MAP_PALETTES = {
  light: {
    background: '#dbeefe',
    sky: '#bfe3ff',
    landcover: '#dfe8d8',
    landuse: '#e8e6d8',
    park: '#cfe8c5',
    water: '#a8c8e6',
    waterway: '#90b7dd',
    boundary: '#9a9a9a',
    transportation: '#c2b59b',
    building: '#d0c7c2',
  },
  dark: {
    background: '#223447',
    sky: '#304761',
    landcover: '#182522',
    landuse: '#1b2320',
    park: '#1d3024',
    water: '#142a3e',
    waterway: '#1f425e',
    boundary: '#5e6872',
    transportation: '#4a453a',
    building: '#2f2c2a',
  },
};

ODT.getTheme = function () {
  return document.documentElement.getAttribute('data-theme') || 'dark';
};

ODT.setTheme = function (theme) {
  document.documentElement.classList.add('theme-transitioning');
  document.documentElement.setAttribute('data-theme', theme);
  setTimeout(() => document.documentElement.classList.remove('theme-transitioning'), 650);
};

ODT.toggleTheme = function () {
  const current = ODT.getTheme();
  ODT.setTheme(current === 'dark' ? 'light' : 'dark');
};

ODT.formatCoord = function (v, decimals) {
  if (v == null || !isFinite(v)) return '--';
  return v.toFixed(decimals || 6);
};

ODT.formatAlt = function (m) {
  if (m == null || !isFinite(m)) return '--';
  return m.toFixed(1) + ' m';
};

ODT.formatDist = function (km) {
  if (km == null || !isFinite(km)) return '--';
  return km.toFixed(2) + ' km';
};

ODT.haversineKm = function (lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
};

ODT.api = async function (url, options) {
  const resp = await fetch(url, options);
  if (!resp.ok) {
    const body = await resp.text().catch(() => '');
    throw new Error(`API ${resp.status}: ${body}`);
  }
  return resp.json();
};

ODT.postJSON = function (url, data) {
  return ODT.api(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
};

ODT.putJSON = function (url, data) {
  return ODT.api(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
};

ODT.humanizeError = function (error, fallback) {
  if (error == null) return fallback || 'The request could not be completed.';
  let text = '';
  if (typeof error === 'string') {
    text = error;
  } else if (error && typeof error.message === 'string') {
    text = error.message;
  } else {
    text = String(error);
  }
  text = text.replace(/^Error:\s*/i, '');
  text = text.replace(/^API\s+\d+:\s*/i, '');
  text = text.replace(/\s+/g, ' ').trim();
  return text || fallback || 'The request could not be completed.';
};
