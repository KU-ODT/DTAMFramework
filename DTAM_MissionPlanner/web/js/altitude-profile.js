/* altitude-profile.js - SVG altitude profile chart */
window.ODT = window.ODT || {};

ODT.AltitudeProfile = (function () {
  const NS = 'http://www.w3.org/2000/svg';
  const REF_ALTS = [0, 150, 300, 500, 1000];
  const CHART_SPECS = [
    { id: 'altitude-canvas', width: 308, height: 120, modal: false },
    { id: 'altitude-canvas-modal', width: 760, height: 340, modal: true },
  ];

  let charts = [];
  let modalEl = null;
  let waypoints = [];
  let dragIndex = -1;
  let dragChartId = null;

  function init() {
    charts = CHART_SPECS.map(bindChart).filter(Boolean);
    modalEl = document.getElementById('altitude-profile-modal');

    const expandBtn = document.getElementById('altitude-profile-expand');
    if (expandBtn) {
      expandBtn.addEventListener('click', openModal);
    }

    const container = document.getElementById('altitude-profile');
    if (container) {
      container.addEventListener('click', (evt) => {
        if (evt.target.closest('#altitude-profile-expand')) return;
        if (evt.target.tagName && evt.target.tagName.toLowerCase() === 'circle') return;
        openModal();
      });
    }

    const closeBtn = document.getElementById('altitude-profile-modal-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', closeModal);
    }

    const backdrop = document.getElementById('altitude-profile-modal-backdrop');
    if (backdrop) {
      backdrop.addEventListener('click', closeModal);
    }

    document.addEventListener('keydown', (evt) => {
      if (evt.key === 'Escape') {
        closeModal();
      }
    });
  }

  function bindChart(spec) {
    const svg = document.getElementById(spec.id);
    if (!svg) return null;

    const chart = { ...spec, svg };
    svg.addEventListener('mousedown', (evt) => onMouseDown(evt, chart));
    svg.addEventListener('mousemove', (evt) => onMouseMove(evt, chart));
    svg.addEventListener('mouseup', onMouseUp);
    svg.addEventListener('mouseleave', onMouseUp);
    return chart;
  }

  function show(wps) {
    waypoints = wps || [];
    const container = document.getElementById('altitude-profile');
    if (!container) return;
    if (waypoints.length < 2) {
      container.classList.remove('visible');
      closeModal();
      clearCharts();
      return;
    }
    container.classList.add('visible');
    render();
  }

  function hide() {
    const container = document.getElementById('altitude-profile');
    if (container) container.classList.remove('visible');
    waypoints = [];
    closeModal();
    clearCharts();
  }

  function openModal() {
    if (!modalEl || waypoints.length < 2) return;
    modalEl.classList.add('visible');
    modalEl.setAttribute('aria-hidden', 'false');
    render();
  }

  function closeModal() {
    if (!modalEl) return;
    modalEl.classList.remove('visible');
    modalEl.setAttribute('aria-hidden', 'true');
    onMouseUp();
  }

  function clearCharts() {
    charts.forEach((chart) => {
      while (chart.svg.firstChild) chart.svg.removeChild(chart.svg.firstChild);
    });
  }

  function render() {
    charts.forEach((chart) => renderChart(chart));
  }

  function renderChart(chart) {
    const { svg, width, height, modal } = chart;

    while (svg.firstChild) svg.removeChild(svg.firstChild);
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    if (waypoints.length < 2) return;

    const padding = getPadding(modal);
    const plotW = width - padding.left - padding.right;
    const plotH = height - padding.top - padding.bottom;

    const distances = [0];
    for (let i = 1; i < waypoints.length; i += 1) {
      const prev = waypoints[i - 1];
      const curr = waypoints[i];
      distances.push(distances[i - 1] + ODT.haversineKm(prev.lat, prev.lon, curr.lat, curr.lon));
    }

    const totalDist = distances[distances.length - 1] || 1;
    const maxAlt = Math.max(500, ...waypoints.map((w) => w.alt_m || 0)) * 1.1;
    const refColor = ODT.getTheme() === 'dark' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)';
    const textColor = ODT.getTheme() === 'dark' ? '#5c6478' : '#8890a4';
    const markerStroke = ODT.getTheme() === 'dark' ? '#141824' : '#ffffff';
    const labelFont = modal ? 10 : 7;
    const refFont = modal ? 10 : 8;
    const markerRadius = modal ? 6 : 4;
    const labelAngle = -45;
    const labelOffsetY = modal ? 18 : 12;

    const xPos = (d) => padding.left + (d / totalDist) * plotW;
    const yPos = (alt) => padding.top + plotH - (alt / maxAlt) * plotH;

    for (const alt of REF_ALTS) {
      if (alt > maxAlt) continue;
      const y = yPos(alt);
      const line = document.createElementNS(NS, 'line');
      line.setAttribute('x1', padding.left);
      line.setAttribute('y1', y);
      line.setAttribute('x2', width - padding.right);
      line.setAttribute('y2', y);
      line.setAttribute('stroke', refColor);
      line.setAttribute('stroke-dasharray', modal ? '4 4' : '3 3');
      svg.appendChild(line);

      const label = document.createElementNS(NS, 'text');
      label.setAttribute('x', padding.left - (modal ? 6 : 4));
      label.setAttribute('y', y + (modal ? 4 : 3));
      label.setAttribute('text-anchor', 'end');
      label.setAttribute('fill', textColor);
      label.setAttribute('font-size', String(refFont));
      label.setAttribute('font-family', 'JetBrains Mono, monospace');
      label.textContent = `${alt}m`;
      svg.appendChild(label);
    }

    const defs = document.createElementNS(NS, 'defs');
    const grad = document.createElementNS(NS, 'linearGradient');
    const gradId = modal ? 'alt-grad-modal' : 'alt-grad';
    grad.setAttribute('id', gradId);
    grad.setAttribute('x1', '0');
    grad.setAttribute('y1', '0');
    grad.setAttribute('x2', '0');
    grad.setAttribute('y2', '1');

    const s1 = document.createElementNS(NS, 'stop');
    s1.setAttribute('offset', '0%');
    s1.setAttribute('stop-color', '#3b82f6');
    s1.setAttribute('stop-opacity', modal ? '0.36' : '0.3');
    grad.appendChild(s1);

    const s2 = document.createElementNS(NS, 'stop');
    s2.setAttribute('offset', '100%');
    s2.setAttribute('stop-color', '#3b82f6');
    s2.setAttribute('stop-opacity', '0.02');
    grad.appendChild(s2);

    defs.appendChild(grad);
    svg.appendChild(defs);

    let areaPath = `M ${xPos(0)} ${yPos(0)}`;
    for (let i = 0; i < waypoints.length; i += 1) {
      areaPath += ` L ${xPos(distances[i])} ${yPos(waypoints[i].alt_m || 0)}`;
    }
    areaPath += ` L ${xPos(totalDist)} ${yPos(0)} Z`;

    const area = document.createElementNS(NS, 'path');
    area.setAttribute('d', areaPath);
    area.setAttribute('fill', `url(#${gradId})`);
    svg.appendChild(area);

    let linePath = '';
    for (let i = 0; i < waypoints.length; i += 1) {
      const x = xPos(distances[i]);
      const y = yPos(waypoints[i].alt_m || 0);
      linePath += `${i === 0 ? 'M' : 'L'} ${x} ${y} `;
    }

    const polyline = document.createElementNS(NS, 'path');
    polyline.setAttribute('d', linePath.trim());
    polyline.setAttribute('fill', 'none');
    polyline.setAttribute('stroke', '#3b82f6');
    polyline.setAttribute('stroke-width', modal ? '3' : '2');
    polyline.setAttribute('stroke-linejoin', 'round');
    polyline.setAttribute('stroke-linecap', 'round');
    svg.appendChild(polyline);

    for (let i = 0; i < waypoints.length; i += 1) {
      const x = xPos(distances[i]);
      const y = yPos(waypoints[i].alt_m || 0);

      const circle = document.createElementNS(NS, 'circle');
      circle.setAttribute('cx', x);
      circle.setAttribute('cy', y);
      circle.setAttribute('r', String(markerRadius));
      circle.setAttribute('fill', waypoints[i].type === 'vertiport' ? '#10b981' : '#3b82f6');
      circle.setAttribute('stroke', markerStroke);
      circle.setAttribute('stroke-width', modal ? '2' : '1.5');
      circle.setAttribute('data-idx', i);
      circle.style.cursor = 'ns-resize';
      svg.appendChild(circle);

      if (waypoints[i].name) {
        const text = document.createElementNS(NS, 'text');
        const labelX = x + (modal ? 5 : 3);
        const labelY = y - labelOffsetY;
        text.setAttribute('x', labelX);
        text.setAttribute('y', labelY);
        text.setAttribute('text-anchor', 'start');
        text.setAttribute('fill', textColor);
        text.setAttribute('font-size', String(labelFont));
        text.setAttribute('font-family', 'Inter, sans-serif');
        text.setAttribute('transform', `rotate(${labelAngle} ${labelX} ${labelY})`);
        const name = waypoints[i].name;
        const maxLabel = modal ? 14 : 8;
        text.textContent = name.length > maxLabel ? `${name.slice(0, maxLabel - 1)}..` : name;
        svg.appendChild(text);
      }
    }

    const distLabel = document.createElementNS(NS, 'text');
    distLabel.setAttribute('x', width / 2);
    distLabel.setAttribute('y', height - (modal ? 8 : 2));
    distLabel.setAttribute('text-anchor', 'middle');
    distLabel.setAttribute('fill', textColor);
    distLabel.setAttribute('font-size', String(modal ? 10 : 8));
    distLabel.setAttribute('font-family', 'JetBrains Mono, monospace');
    distLabel.textContent = `${totalDist.toFixed(1)} km`;
    svg.appendChild(distLabel);
  }

  function getPadding(modal) {
    if (modal) {
      return { top: 44, right: 18, bottom: 30, left: 52 };
    }
    return { top: 26, right: 10, bottom: 20, left: 35 };
  }

  function onMouseDown(evt, chart) {
    const target = evt.target;
    if (target.tagName === 'circle' && target.hasAttribute('data-idx')) {
      dragIndex = parseInt(target.getAttribute('data-idx'), 10);
      dragChartId = chart.id;
    }
  }

  function onMouseMove(evt, chart) {
    if (dragIndex < 0 || dragChartId !== chart.id) return;

    const rect = chart.svg.getBoundingClientRect();
    const viewBox = chart.svg.viewBox.baseVal;
    const padding = getPadding(chart.modal);
    const scaleY = viewBox.height / rect.height;
    const mouseY = (evt.clientY - rect.top) * scaleY;
    const plotH = viewBox.height - padding.top - padding.bottom;
    const maxAlt = Math.max(500, ...waypoints.map((w) => w.alt_m || 0)) * 1.1;
    const alt = Math.max(0, ((padding.top + plotH - mouseY) / plotH) * maxAlt);

    waypoints[dragIndex].alt_m = Math.round(alt);
    render();

    if (ODT.Mission && ODT.Mission.onAltitudeChange) {
      ODT.Mission.onAltitudeChange(dragIndex, waypoints[dragIndex].alt_m);
    }
  }

  function onMouseUp() {
    dragIndex = -1;
    dragChartId = null;
  }

  return { init, show, hide, render, openModal, closeModal };
})();
