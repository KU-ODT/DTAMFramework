import { initPsuMap, selectAircraftOnMap, selectConflictOnMap, setPsuMapTheme, setTrafficMapFilter } from "./map.js?v=psu-live-4001-20260519-reactive";

const healthStatus = document.querySelector("[data-health-status]");
const themeToggle = document.querySelector("[data-theme-toggle]");
const serverTime = document.querySelector("[data-server-time]");
const mapStatus = document.querySelector("[data-map-status]");
const tabs = Array.from(document.querySelectorAll("[data-tab]"));
const panels = Array.from(document.querySelectorAll("[data-panel]"));
const THEME_STORAGE_KEY = "psu-theme";

let mapReady = false;
let trafficPayload = null;
let trafficFilter = "ALL";
let selectedConflictId = null;
let selectedAircraftId = null;
let flowPayload = null;
let selectedCapacityTarget = null;
let decisionPayload = null;
let selectedRecommendationId = null;
let reportPayload = null;
let replayPayload = null;
let validationPayload = null;
let selectedReplayStep = 1;
let replayTimer = null;
let replayIntervalMs = 1600;

function formatDelay(seconds) {
  const value = Number(seconds || 0);
  const min = Math.floor(Math.abs(value) / 60);
  const sec = Math.round(Math.abs(value) % 60);
  return `${String(min).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

function formatSignedDelay(seconds) {
  const value = Number(seconds || 0);
  if (value === 0) {
    return "00:00";
  }
  return `${value > 0 ? "+" : "-"}${formatDelay(value)}`;
}

function formatTime(value) {
  if (!value) return "--";
  const match = String(value).match(/T(\d{2}:\d{2})/);
  return match ? match[1] : String(value);
}

function formatPercent(value) {
  return `${(Number(value || 0) * 100).toFixed(0)}%`;
}

function formatCoordinate(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric.toFixed(5) : "--";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function setText(selector, text) {
  const element = document.querySelector(selector);
  if (element) {
    element.textContent = text;
  }
}


function normalizedTheme(value) {
  return value === "light" ? "light" : "dark";
}

function applyTheme(theme, { persist = false } = {}) {
  const nextTheme = normalizedTheme(theme);
  document.documentElement.dataset.theme = nextTheme;
  if (themeToggle) {
    const label = nextTheme === "light" ? "\uc5b4\ub450\uc6b4 \ud14c\ub9c8\ub85c \uc804\ud658" : "\ubc1d\uc740 \ud14c\ub9c8\ub85c \uc804\ud658";
    themeToggle.dataset.theme = nextTheme;
    themeToggle.setAttribute("aria-label", label);
    themeToggle.title = label;
  }
  setPsuMapTheme(nextTheme);
  window.dispatchEvent(new CustomEvent("psu:theme-changed", { detail: { theme: nextTheme } }));
  window.setTimeout(() => window.__PSU_MAP__?.resize?.(), 60);
  if (persist) {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
    } catch (_) {
      // localStorage may be unavailable in restricted browser contexts.
    }
  }
}

function initTheme() {
  let theme = normalizedTheme(document.documentElement.dataset.theme);
  try {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    if (saved === "light" || saved === "dark") {
      theme = saved;
    }
  } catch (_) {
    // Keep the theme selected by the early inline bootstrap.
  }
  applyTheme(theme);
}


function setConnectionState(isOnline, label) {
  if (!healthStatus) return;
  healthStatus.classList.remove("is-checking", "is-online", "is-offline");
  healthStatus.classList.add(isOnline ? "is-online" : "is-offline");
  healthStatus.dataset.state = isOnline ? "online" : "offline";
  healthStatus.title = label;
  healthStatus.setAttribute("aria-label", label);
}

function statusClass(value) {
  return `status-badge--${String(value || "NORMAL").toUpperCase()}`;
}

function severityRank(value) {
  const rank = { WARNING: 3, CAUTION: 2, NORMAL: 1 };
  return rank[String(value || "NORMAL").toUpperCase()] || 0;
}


function tabIdFromHash() {
  const value = String(window.location.hash || "").replace(/^#/, "");
  return panels.some((panel) => panel.dataset.panel === value) ? value : "overview";
}

function setActiveTab(tabId, shouldScroll = false) {
  const targetTabId = panels.some((panel) => panel.dataset.panel === tabId) ? tabId : "overview";

  for (const tab of tabs) {
    tab.classList.toggle("is-active", tab.dataset.tab === targetTabId);
    tab.setAttribute("aria-selected", tab.dataset.tab === targetTabId ? "true" : "false");
  }

  for (const panel of panels) {
    const active = panel.dataset.panel === targetTabId;
    panel.hidden = !active;
    panel.classList.toggle("is-active-panel", active);
    panel.style.outline = "";
    panel.style.opacity = "";
  }

  if (shouldScroll) {
    document.querySelector(`[data-panel="${targetTabId}"]`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  if (targetTabId === "traffic-map") {
    window.setTimeout(() => window.__PSU_MAP__?.resize?.(), 80);
  }
}

function screenToTabId(screen) {
  const normalized = String(screen || "").toLowerCase();
  if (normalized.includes("replay") || normalized.includes("report")) {
    return "replay-report";
  }
  if (
    normalized.includes("decision") ||
    normalized.includes("support") ||
    normalized.includes("mitigation")
  ) {
    return "decision-support";
  }
  if (normalized.includes("flow") || normalized.includes("capacity")) {
    return "flow-capacity";
  }
  if (normalized.includes("traffic") || normalized.includes("conflict")) {
    return "traffic-map";
  }
  return "overview";
}

async function refreshStatus() {
  try {
    const response = await fetch("/api/status", { headers: { Accept: "application/json" } });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const payload = await response.json();
    const stateServer = payload?.state_server || {};
    const operationStatus = payload?.operation_status || {};
    const vehicleStream = payload?.vehicle_stream || {};
    const streamCount = Number(vehicleStream.fresh_vehicle_count || 0);
    const serverReady = Boolean(payload?.connected || vehicleStream.server_connected || stateServer.connected || operationStatus.connected);
    const sourceLabel = operationStatus.connected
      ? "OperationModule 4001 API"
      : stateServer.connected
        ? "StateServer 4001 DB"
        : "4001 서버";
    const detail = streamCount
      ? ` · 4001 ${streamCount} UAM 수신`
      : serverReady
        ? " · 4001 연결됨 / 비행체 대기"
        : " · 4001 연결 대기";
    setConnectionState(serverReady, `${sourceLabel}${detail}`);
    if (serverTime) {
      serverTime.textContent = payload?.time?.display || "서버 시간 수신 완료";
    }
  } catch (error) {
    setConnectionState(false, "4001 서버 연결 끊김");
    if (serverTime) {
      serverTime.textContent = error instanceof Error ? error.message : String(error);
    }
  }
}

function updateKpiCards(kpis) {
  setText("[data-kpi='active_uam']", kpis.active_uam ?? "--");
  setText("[data-kpi='pending_intent']", kpis.pending_intent ?? "--");
  setText("[data-kpi='conflict_alert']", kpis.conflict_alert ?? "--");
  setText("[data-kpi='capacity_alert']", kpis.capacity_alert ?? "--");
  setText("[data-kpi='average_delay']", formatDelay(kpis.average_delay_sec));
  setText("[data-kpi='data_link_health']", kpis.data_link_health || "--");
  setText("[data-kpi='max_delay']", formatDelay(kpis.max_delay_sec));
  setText("[data-kpi='off_nominal_event']", kpis.off_nominal_event ?? "--");

  for (const element of document.querySelectorAll("[data-kpi]")) {
    const card = element.closest(".kpi-card");
    if (!card) continue;
    card.classList.remove("kpi-card--warning", "kpi-card--caution", "kpi-card--normal");
  }
  const warningKeys = ["conflict_alert", "capacity_alert", "off_nominal_event"];
  for (const key of warningKeys) {
    const value = Number(kpis[key] || 0);
    const card = document.querySelector(`[data-kpi='${key}']`)?.closest(".kpi-card");
    if (card) {
      card.classList.add(value >= 2 ? "kpi-card--warning" : value === 1 ? "kpi-card--caution" : "kpi-card--normal");
    }
  }
}

function renderPriorityEvents(events) {
  const eventList = document.querySelector("[data-priority-events]");
  setText("[data-event-count]", `${events.length} OPEN`);
  if (!eventList) return;
  eventList.innerHTML = events.length
    ? events
        .slice(0, 5)
        .map((event) => {
          const relatedTargets = (event.related_targets || []).join(",");
          return `
            <li class="event-item" data-recommended-screen="${escapeHtml(event.recommended_screen)}" data-related-targets="${escapeHtml(relatedTargets)}" data-event-id="${escapeHtml(event.event_id)}" tabindex="0" role="button">
              <span class="status-badge ${statusClass(event.severity)}">${escapeHtml(event.severity)}</span>
              ${escapeHtml(event.title)}
              <span class="event-meta">
                ${escapeHtml(formatTime(event.expected_time))} · ${escapeHtml(event.recommended_screen)} · Score ${escapeHtml(event.priority_score)}
              </span>
            </li>
          `;
        })
        .join("")
    : "<li>열린 우선 이벤트가 없습니다.</li>";
}

function resourceOccupancy(available, total) {
  const totalValue = Number(total || 0);
  if (!totalValue) return 0;
  return Math.max(0, Math.min(1, 1 - Number(available || 0) / totalValue));
}

function renderVertiports(vertiports) {
  const vertiportList = document.querySelector("[data-vertiport-summary]");
  setText("[data-vertiport-count]", `${vertiports.length} VP`);
  if (!vertiportList) return;
  vertiportList.innerHTML = vertiports
    .slice()
    .sort((a, b) => severityRank(b.status) - severityRank(a.status) || Number(b.average_delay_sec || 0) - Number(a.average_delay_sec || 0))
    .slice(0, 5)
    .map((vp) => {
      const fatoOcc = resourceOccupancy(vp.fato_available, vp.fato_total);
      const gateOcc = resourceOccupancy(vp.gate_available, vp.gate_total);
      return `
        <li class="vertiport-row">
          <div>
            <span class="status-badge ${statusClass(vp.status)}">${escapeHtml(vp.status)}</span>
            <strong>${escapeHtml(vp.vertiport_id)}</strong> · ${escapeHtml(vp.name)}
          </div>
          <div class="event-meta">
            Arr Q ${escapeHtml(vp.arrival_queue)} · Dep Q ${escapeHtml(vp.departure_queue)} · Delay ${formatDelay(vp.average_delay_sec)}
          </div>
          <div class="resource-bar" title="FATO occupancy"><span style="width:${(fatoOcc * 100).toFixed(0)}%"></span></div>
          <div class="resource-bar" title="Gate occupancy"><span style="width:${(gateOcc * 100).toFixed(0)}%"></span></div>
        </li>
      `;
    })
    .join("");
}

function renderTrafficTrend(trend, summary) {
  const container = document.querySelector("[data-traffic-trend]");
  if (!container) return;
  const peakActive = Math.max(Number(summary?.peak_active_flights || 1), 1);
  const peakDelay = Math.max(Number(summary?.peak_average_delay_sec || 1), 1);
  const peakConflict = Math.max(Number(summary?.peak_conflict_count || 1), 1);
  container.innerHTML = trend.length
    ? trend
        .map((point) => {
          const activePct = Math.min(100, (Number(point.active_flights || 0) / peakActive) * 100);
          const delayPct = Math.min(100, (Number(point.average_delay_sec || 0) / peakDelay) * 100);
          const conflictPct = Math.min(100, (Number(point.conflict_count || 0) / peakConflict) * 100);
          return `
            <div class="trend-row">
              <span>${escapeHtml(point.time)}</span>
              <div class="trend-bars">
                <div class="trend-bar trend-bar--active"><span style="width:${activePct.toFixed(0)}%"></span></div>
                <div class="trend-bar trend-bar--delay"><span style="width:${delayPct.toFixed(0)}%"></span></div>
                <div class="trend-bar trend-bar--conflict"><span style="width:${conflictPct.toFixed(0)}%"></span></div>
              </div>
              <span>${escapeHtml(point.active_flights)} AC</span>
            </div>
          `;
        })
        .join("")
    : "<p>교통 추세 데이터가 없습니다.</p>";
}

function renderOperationalSnapshot(overview) {
  const container = document.querySelector("[data-operational-snapshot]");
  if (!container) return;
  const status = overview.status_summary || {};
  const map = overview.map_summary || {};
  const hotspot = overview.capacity_hotspots?.[0];
  const topEvent = overview.top_priority_event;
  container.innerHTML = `
    <div class="snapshot-card">
      <span>Event Severity</span>
      <strong>W${status.event_severity?.WARNING || 0} / C${status.event_severity?.CAUTION || 0}</strong>
    </div>
    <div class="snapshot-card">
      <span>Vertiport Warning</span>
      <strong>${status.vertiport_status?.WARNING || 0}</strong>
    </div>
    <div class="snapshot-card">
      <span>Map Objects</span>
      <strong>${map.track_count || 0}+${map.route_count || 0}+${map.vertiport_count || 0}</strong>
    </div>
    <div class="snapshot-card">
      <span>Top Hotspot</span>
      <strong>${hotspot ? `${escapeHtml(hotspot.target_id)} ${(Number(hotspot.utilization || 0) * 100).toFixed(0)}%` : "--"}</strong>
    </div>
    <div class="snapshot-card snapshot-card--wide">
      <span>Next Operator Focus</span>
      <strong>${topEvent ? escapeHtml(topEvent.recommended_screen) : "--"}</strong>
    </div>
  `;
}

function renderMiniMapSummary(mapSummary) {
  const container = document.querySelector("[data-mini-map-summary]");
  if (!container) return;
  container.innerHTML = `
    <span>UAM ${escapeHtml(mapSummary.track_count || 0)}</span>
    <span>Routes ${escapeHtml(mapSummary.route_count || 0)}</span>
    <span>Corridors ${escapeHtml(mapSummary.corridor_count || 0)}</span>
    <span>Conflicts ${escapeHtml(mapSummary.conflict_count || 0)}</span>
  `;
}

function currentActiveAircraftSet() {
  return new Set((trafficPayload?.flights || []).filter((flight) => flight.is_active).map((flight) => String(flight.aircraft_id)));
}

function findFlightByAircraftId(aircraftId) {
  const normalized = String(aircraftId || "");
  if (!normalized) return null;
  return (trafficPayload?.flights || []).find((flight) => String(flight.aircraft_id) === normalized) || null;
}

function trafficDataLinkState() {
  const dataLink = trafficPayload?.data_link || {};
  const stream = dataLink.vehicle_stream || {};
  const stateServer = dataLink.state_server || {};
  const operationStatus = dataLink.operation_status || {};
  const freshCount = Number(stream.fresh_vehicle_count || 0);
  const totalCount = Number(stream.total_vehicle_count || 0);
  const serverReady = Boolean(dataLink.connected || stream.server_connected || stateServer.connected || operationStatus.connected);
  const sourceLabel = operationStatus.connected
    ? "OperationModule 4001 API"
    : stateServer.connected
      ? "StateServer 4001 DB"
      : "ICD 4001";
  return {
    serverReady,
    freshCount,
    totalCount,
    sourceLabel,
    health: dataLink.data_link_health || (freshCount ? "LIVE_4001" : serverReady ? "WAITING_4001" : "OFFLINE"),
    message: dataLink.message || "",
  };
}

function trafficEmptyStateMarkup(kind, { filtered = false } = {}) {
  const link = trafficDataLinkState();
  if (filtered) {
    return `
      <div class="traffic-empty-state">
        <strong>현재 필터에 해당하는 ${kind} 데이터가 없습니다.</strong>
        <small>${escapeHtml(link.sourceLabel)} · ${escapeHtml(link.health)}</small>
      </div>
    `;
  }
  const title = link.serverReady
    ? "4001 서버는 연결되어 있으나 수신된 실시간 비행체가 없습니다."
    : "4001 서버 연결을 기다리는 중입니다.";
  const detail = link.serverReady
    ? (link.message || "OperationModule/StateServer에서 4001 비행체 데이터가 들어오면 자동으로 목록과 맵이 갱신됩니다.")
    : "OperationModule 또는 StateServer 4001 스트림을 실행하면 비행체/충돌 패널이 자동으로 채워집니다.";
  return `
    <div class="traffic-empty-state">
      <strong>${escapeHtml(title)}</strong>
      <small>${escapeHtml(detail)}</small>
      <span>${escapeHtml(link.sourceLabel)} · fresh ${escapeHtml(link.freshCount)} / total ${escapeHtml(link.totalCount)}</span>
    </div>
  `;
}

function filteredFlights() {
  const flights = trafficPayload?.flights || [];
  const normalized = trafficFilter.toUpperCase();
  const filtered = flights.filter((flight) => {
    if (normalized === "ALL") return true;
    if (normalized === "ACTIVE") return Boolean(flight.is_active);
    return String(flight.severity || "").toUpperCase() === normalized;
  });
  return filtered.sort((a, b) => severityRank(b.severity) - severityRank(a.severity) || String(a.aircraft_id).localeCompare(String(b.aircraft_id)));
}

function filteredConflicts() {
  const conflicts = trafficPayload?.timeline || [];
  const normalized = trafficFilter.toUpperCase();
  if (normalized === "ALL") return conflicts;
  if (normalized === "ACTIVE") {
    const activeAircraft = currentActiveAircraftSet();
    return conflicts.filter((conflict) => (conflict.related_aircraft || []).some((aircraftId) => activeAircraft.has(String(aircraftId))));
  }
  return conflicts.filter((conflict) => String(conflict.severity || "").toUpperCase() === normalized);
}

function renderFlightList() {
  const list = document.querySelector("[data-flight-list]");
  const flights = filteredFlights();
  const total = trafficPayload?.flights?.length || 0;
  setText("[data-traffic-count]", `${flights.length}/${total} FLT`);
  if (!list) return;
  if (!flights.length) {
    list.innerHTML = trafficEmptyStateMarkup("운항", { filtered: total > 0 });
    return;
  }
  list.innerHTML = flights
    .map((flight) => {
      const track = flight.track || {};
      const status = flight.is_active ? track.flight_status || "ACTIVE" : flight.status;
      return `
        <button type="button" class="flight-item ${String(flight.aircraft_id) === String(selectedAircraftId) ? "is-selected" : ""}" data-aircraft-id="${escapeHtml(flight.aircraft_id)}">
          <span class="status-badge ${statusClass(flight.severity)}">${escapeHtml(flight.severity)}</span>
          <strong>${escapeHtml(flight.aircraft_id)}</strong>
          <span>${escapeHtml(flight.flight_plan_id)} · ${escapeHtml(status)}</span>
          <span>${escapeHtml(flight.origin_vertiport)} → ${escapeHtml(flight.destination_vertiport)} · ${escapeHtml(flight.route_id)} / ${escapeHtml(flight.current_corridor_id || "--")}</span>
          <small>ETA ${escapeHtml(formatTime(flight.eta))} · Delay ${escapeHtml(formatSignedDelay(flight.delay_sec))} · Alt ${escapeHtml(track.altitude ?? flight.planned_altitude)}m · GS ${escapeHtml(track.ground_speed ?? flight.planned_speed)}kt · CF ${escapeHtml(flight.conflict_count)}</small>
        </button>
      `;
    })
    .join("");
}

function renderConflictTimeline() {
  const list = document.querySelector("[data-conflict-timeline]");
  const conflicts = filteredConflicts();
  const total = trafficPayload?.timeline?.length || 0;
  setText("[data-conflict-count]", `${conflicts.length}/${total} CF`);
  if (!conflicts.some((conflict) => String(conflict.conflict_id) === String(selectedConflictId))) {
    const aircraftRelated = selectedAircraftId
      ? conflicts.find((conflict) => (conflict.related_aircraft || []).some((aircraftId) => String(aircraftId) === String(selectedAircraftId)))
      : null;
    selectedConflictId = aircraftRelated?.conflict_id || (selectedAircraftId ? null : conflicts[0]?.conflict_id || null);
  }
  if (!list) return;
  if (!conflicts.length) {
    list.innerHTML = trafficEmptyStateMarkup("충돌", { filtered: total > 0 });
    return;
  }
  list.innerHTML = conflicts
    .map((conflict) => `
      <button type="button" class="timeline-item ${String(conflict.conflict_id) === String(selectedConflictId) ? "is-selected" : ""}" data-conflict-id="${escapeHtml(conflict.conflict_id)}">
        <span class="status-badge ${statusClass(conflict.severity)}">${escapeHtml(conflict.severity)}</span>
        <strong>${escapeHtml(formatTime(conflict.predicted_time))}</strong>
        <span>${escapeHtml(conflict.conflict_type)}</span>
        <small>${escapeHtml(conflict.location_id)} · ${escapeHtml((conflict.related_aircraft || []).join(" / "))} · T-${escapeHtml(conflict.time_to_event_label)}</small>
      </button>
    `)
    .join("");
}

function renderConflictDetail({ fly = false } = {}) {
  const detail = document.querySelector("[data-conflict-detail]");
  const actions = document.querySelector("[data-suggested-actions]");
  const conflict = (trafficPayload?.conflicts || []).find((item) => String(item.conflict_id) === String(selectedConflictId));
  const selectedFlight = selectedAircraftId ? findFlightByAircraftId(selectedAircraftId) : null;
  setText("[data-conflict-selected]", conflict ? conflict.conflict_id : selectedFlight ? selectedFlight.aircraft_id : "--");
  if (!detail || !actions) return;
  if (!conflict) {
    if (selectedFlight) {
      const track = selectedFlight.track || {};
      const liveAge = Number.isFinite(Number(track.age_s)) ? `${Number(track.age_s).toFixed(1)} sec` : "--";
      detail.innerHTML = `
        <div class="conflict-title-row">
          <span class="status-badge ${statusClass(selectedFlight.severity || track.severity || "NORMAL")}">${escapeHtml(track.flight_status || selectedFlight.status || "ACTIVE")}</span>
          <strong>${escapeHtml(selectedFlight.aircraft_id)}</strong>
        </div>
        <div class="detail-grid">
          <div class="detail-metric"><span>Source</span><strong>${escapeHtml(selectedFlight.source || track.source || "ICD-4001")}</strong><small>4001 live vehicle stream</small></div>
          <div class="detail-metric"><span>Flight Plan</span><strong>${escapeHtml(selectedFlight.flight_plan_id || "--")}</strong><small>${escapeHtml(selectedFlight.route_id || "route pending")}</small></div>
          <div class="detail-metric"><span>Position</span><strong>${escapeHtml(formatCoordinate(track.latitude))}, ${escapeHtml(formatCoordinate(track.longitude))}</strong><small>lat / lon</small></div>
          <div class="detail-metric"><span>Altitude / Speed</span><strong>${escapeHtml(track.altitude ?? selectedFlight.planned_altitude ?? "--")} m · ${escapeHtml(track.ground_speed ?? selectedFlight.planned_speed ?? "--")}</strong><small>ground speed m/s 또는 kt</small></div>
          <div class="detail-metric detail-metric--wide"><span>Last Update</span><strong>${escapeHtml(formatTime(track.timestamp || track.received_at || selectedFlight.eta))}</strong><small>age ${escapeHtml(liveAge)} · 관련 충돌 ${escapeHtml(selectedFlight.conflict_count || 0)}건</small></div>
        </div>
      `;
      actions.innerHTML = `
        <h5>Live Data Link</h5>
        <ol class="action-list">
          <li>선택한 비행체는 4001 수신 데이터 기준으로 맵과 목록에 동시 반영됩니다.</li>
          <li>관련 충돌 후보가 생기면 Conflict Timeline과 Detail Panel이 자동으로 전환됩니다.</li>
        </ol>
      `;
      return;
    }
    detail.innerHTML = "<p>충돌 이벤트 또는 실시간 비행체를 선택하면 상세 분석이 표시됩니다.</p>";
    actions.innerHTML = trafficEmptyStateMarkup("상세 분석");
    return;
  }
  const margin = Number(conflict.separation_margin_sec || 0);
  detail.innerHTML = `
    <div class="conflict-title-row">
      <span class="status-badge ${statusClass(conflict.severity)}">${escapeHtml(conflict.severity)}</span>
      <strong>${escapeHtml(conflict.conflict_type)}</strong>
    </div>
    <div class="detail-grid">
      <div class="detail-metric"><span>Location</span><strong>${escapeHtml(conflict.location_id)}</strong><small>${escapeHtml(conflict.location_name || "--")}</small></div>
      <div class="detail-metric"><span>Aircraft</span><strong>${escapeHtml((conflict.related_aircraft || []).join(" / "))}</strong><small>관련 UAM</small></div>
      <div class="detail-metric"><span>Predicted</span><strong>${escapeHtml(formatTime(conflict.predicted_time))}</strong><small>T-${escapeHtml(conflict.time_to_event_label)}</small></div>
      <div class="detail-metric"><span>ETA Gap</span><strong>${escapeHtml(conflict.eta_gap_sec)} sec</strong><small>Required ${escapeHtml(conflict.required_gap_sec)} sec</small></div>
      <div class="detail-metric detail-metric--wide ${margin < 0 ? "margin-negative" : ""}"><span>Separation Margin</span><strong>${margin > 0 ? "+" : ""}${escapeHtml(margin)} sec</strong><small>음수이면 전략적 분리 기준 미달</small></div>
    </div>
  `;
  actions.innerHTML = `
    <h5>Suggested Actions</h5>
    <ol class="action-list">
      ${(conflict.suggested_actions || []).map((action) => `<li>${escapeHtml(action)}</li>`).join("") || "<li>등록된 조치 후보가 없습니다.</li>"}
    </ol>
  `;
  if (mapReady) {
    selectConflictOnMap(conflict.conflict_id, { fly });
  }
}

function renderTrafficWorkspace({ preserveSelection = true } = {}) {
  if (!trafficPayload) return;
  const timeline = trafficPayload.timeline || [];
  if (selectedAircraftId && !findFlightByAircraftId(selectedAircraftId)) {
    selectedAircraftId = null;
  }
  if (!selectedAircraftId && (!preserveSelection || !timeline.some((conflict) => String(conflict.conflict_id) === String(selectedConflictId)))) {
    selectedConflictId = timeline[0]?.conflict_id || null;
  }
  renderFlightList();
  renderConflictTimeline();
  renderConflictDetail({ fly: false });
}

function selectConflict(conflictId, { fly = true } = {}) {
  selectedAircraftId = null;
  selectedConflictId = conflictId;
  renderFlightList();
  renderConflictTimeline();
  renderConflictDetail({ fly });
}

function selectAircraft(aircraftId, { fly = true } = {}) {
  if (!aircraftId) return;
  selectedAircraftId = String(aircraftId);
  const related = (trafficPayload?.conflicts || []).find((conflict) =>
    (conflict.related_aircraft || []).some((item) => String(item) === String(aircraftId)),
  );
  selectedConflictId = related?.conflict_id || null;
  renderFlightList();
  renderConflictTimeline();
  renderConflictDetail({ fly: false });
  if (fly) {
    selectAircraftOnMap(aircraftId);
  }
}

function selectRelatedConflictFromTargets(targets, { fly = true } = {}) {
  if (!trafficPayload || !targets.length) return false;
  const targetSet = new Set(targets.map(String));
  const conflict = (trafficPayload.conflicts || []).find((item) => {
    if (targetSet.has(String(item.location_id)) || targetSet.has(String(item.conflict_id))) return true;
    return (item.related_aircraft || []).some((aircraftId) => targetSet.has(String(aircraftId)));
  });
  if (!conflict) return false;
  selectConflict(conflict.conflict_id, { fly });
  return true;
}

async function refreshTrafficData() {
  try {
    const response = await fetch("/api/traffic/conflict-view", { headers: { Accept: "application/json" } });
    if (!response.ok) {
      throw new Error(`Traffic API HTTP ${response.status}`);
    }
    trafficPayload = await response.json();
    renderTrafficWorkspace({ preserveSelection: true });
  } catch (error) {
    console.error(error);
    const list = document.querySelector("[data-flight-list]");
    const timeline = document.querySelector("[data-conflict-timeline]");
    if (list) list.innerHTML = "<p>운항 목록을 불러오지 못했습니다.</p>";
    if (timeline) timeline.innerHTML = "<p>충돌 타임라인을 불러오지 못했습니다.</p>";
  }
}

function renderFlowSummary(summary) {
  setText("[data-flow-summary='network_utilization']", formatPercent(summary.network_utilization));
  setText("[data-flow-summary='warning_count']", `${summary.warning_count ?? 0}`);
  setText("[data-flow-summary='main_bottleneck']", summary.main_bottleneck_id || "--");
  setText("[data-flow-summary='delay_event_count']", `${summary.delay_event_count ?? 0}`);
}

function renderFlowCondition(condition) {
  const container = document.querySelector("[data-flow-condition]");
  setText("[data-flow-generated]", formatTime(condition.generated_at));
  if (!container) return;
  container.innerHTML = `
    <div><span>Time Window</span><strong>${escapeHtml(formatTime(condition.time_window_start))} - ${escapeHtml(formatTime(condition.time_window_end))}</strong></div>
    <div><span>Interval</span><strong>${escapeHtml(condition.interval_min)} min</strong></div>
    <div><span>Target</span><strong>${escapeHtml(condition.target_scope)}</strong></div>
    <div><span>Scenario</span><strong>${escapeHtml(condition.scenario_mode)}</strong></div>
  `;
}

function renderDcbChart(series) {
  const container = document.querySelector("[data-dcb-chart]");
  setText("[data-dcb-count]", `${series.length} Windows`);
  if (!container) return;
  if (!series.length) {
    container.innerHTML = "<p>수요-수용량 분석 데이터가 없습니다.</p>";
    return;
  }
  const maxValue = Math.max(...series.map((item) => Math.max(Number(item.demand || 0), Number(item.capacity || 0))), 1);
  container.innerHTML = series
    .map((item) => {
      const demandPct = Math.min(100, (Number(item.demand || 0) / maxValue) * 100);
      const capacityPct = Math.min(100, (Number(item.capacity || 0) / maxValue) * 100);
      return `
        <button type="button" class="dcb-row" data-capacity-target="${escapeHtml(item.target_id)}" data-capacity-type="${escapeHtml(item.target_type)}">
          <div class="dcb-row__label">
            <span class="status-badge ${statusClass(item.status)}">${escapeHtml(item.status)}</span>
            <strong>${escapeHtml(item.target_id)}</strong>
            <small>${escapeHtml(item.time_label)} · ${escapeHtml(item.target_type)}</small>
          </div>
          <div class="dcb-bars">
            <div class="dcb-bar dcb-bar--demand"><span style="width:${demandPct.toFixed(0)}%"></span></div>
            <div class="dcb-bar dcb-bar--capacity"><span style="width:${capacityPct.toFixed(0)}%"></span></div>
          </div>
          <div class="dcb-row__metric">
            <strong>${escapeHtml(item.demand)} / ${escapeHtml(item.capacity)}</strong>
            <small>Over ${escapeHtml(item.overload)} · ${formatPercent(item.utilization)}</small>
          </div>
        </button>
      `;
    })
    .join("");
}

function renderCorridorDensity(items) {
  const container = document.querySelector("[data-corridor-density]");
  setText("[data-corridor-density-count]", `${items.length} COR`);
  if (!container) return;
  container.innerHTML = items
    .slice()
    .sort((a, b) => severityRank(b.status) - severityRank(a.status) || Number(b.utilization || 0) - Number(a.utilization || 0))
    .map((item) => `
      <button type="button" class="capacity-item ${String(selectedCapacityTarget?.id) === String(item.target_id) ? "is-selected" : ""}" data-capacity-target="${escapeHtml(item.target_id)}" data-capacity-type="CORRIDOR">
        <div>
          <span class="status-badge ${statusClass(item.status)}">${escapeHtml(item.status)}</span>
          <strong>${escapeHtml(item.target_id)}</strong> · ${escapeHtml(item.name)}
        </div>
        <div class="capacity-meter capacity-meter--${escapeHtml(item.status)}"><span style="width:${Math.min(100, Number(item.utilization || 0) * 100).toFixed(0)}%"></span></div>
        <small>Density ${formatPercent(item.density_ratio)} · Occupied ${escapeHtml(item.occupied_aircraft)}/${escapeHtml(item.capacity)} · Flights ${escapeHtml(item.flight_count)}</small>
      </button>
    `)
    .join("");
}

function renderVertiportThroughput(items) {
  const container = document.querySelector("[data-vertiport-throughput]");
  setText("[data-vertiport-throughput-count]", `${items.length} VP`);
  if (!container) return;
  container.innerHTML = items
    .slice()
    .sort((a, b) => severityRank(b.status) - severityRank(a.status) || Number(b.utilization || 0) - Number(a.utilization || 0))
    .map((item) => `
      <button type="button" class="capacity-item ${String(selectedCapacityTarget?.id) === String(item.target_id) ? "is-selected" : ""}" data-capacity-target="${escapeHtml(item.target_id)}" data-capacity-type="VERTIPORT">
        <div>
          <span class="status-badge ${statusClass(item.status)}">${escapeHtml(item.status)}</span>
          <strong>${escapeHtml(item.target_id)}</strong> · ${escapeHtml(item.name)}
        </div>
        <div class="throughput-grid">
          <span>Arr ${escapeHtml(item.arrival_demand)}</span>
          <span>Dep ${escapeHtml(item.departure_demand)}</span>
          <span>Delay ${formatDelay(item.average_delay_sec)}</span>
        </div>
        <div class="capacity-meter"><span style="width:${Math.min(100, Number(item.fato_occupancy || 0) * 100).toFixed(0)}%"></span></div>
        <small>FATO ${formatPercent(item.fato_occupancy)} · Gate ${formatPercent(item.gate_occupancy)} · ${escapeHtml(item.bottleneck_cause)}</small>
      </button>
    `)
    .join("");
}

function renderDelayPropagation(items) {
  const container = document.querySelector("[data-delay-propagation]");
  setText("[data-delay-count]", `${items.length} Steps`);
  if (!container) return;
  container.innerHTML = items.length
    ? items
        .map((item) => `
          <div class="delay-step">
            <span class="delay-step__index">${escapeHtml(item.step)}</span>
            <div>
              <span class="status-badge ${statusClass(item.status)}">${escapeHtml(item.status)}</span>
              <strong>${escapeHtml(item.time)} · ${escapeHtml(item.title)}</strong>
              <small>${escapeHtml(item.description)} · Delay ${formatSignedDelay(item.delay_sec)}</small>
            </div>
          </div>
        `)
        .join("")
    : "<p>지연 전파 이벤트가 없습니다.</p>";
}

function renderBottleneckDiagnosis(diagnosis) {
  const container = document.querySelector("[data-bottleneck-diagnosis]");
  setText("[data-bottleneck-status]", diagnosis?.status || "--");
  if (!container) return;
  if (!diagnosis) {
    container.innerHTML = "<p>병목 진단 데이터가 없습니다.</p>";
    return;
  }
  container.innerHTML = `
    <div class="bottleneck-head">
      <span class="status-badge ${statusClass(diagnosis.status)}">${escapeHtml(diagnosis.status)}</span>
      <strong>${escapeHtml(diagnosis.target_id)} · ${escapeHtml(diagnosis.cause)}</strong>
      <small>${escapeHtml(diagnosis.impact)} · ${escapeHtml(diagnosis.expected_duration_min)} min</small>
    </div>
    <div class="bottleneck-columns">
      <div>
        <h5>Root Causes</h5>
        <ul>${(diagnosis.root_causes || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </div>
      <div>
        <h5>Mitigation</h5>
        <ul>${(diagnosis.mitigations || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </div>
    </div>
  `;
}

function findCapacityTarget(targetId, targetType) {
  if (!flowPayload) return null;
  const lists = [
    ...(flowPayload.corridor_density || []),
    ...(flowPayload.vertiport_throughput || []),
  ];
  return lists.find(
    (item) =>
      String(item.target_id) === String(targetId) &&
      (!targetType || String(item.target_type).toUpperCase() === String(targetType).toUpperCase()),
  );
}

function renderCapacityDetail() {
  const container = document.querySelector("[data-capacity-detail]");
  const target = selectedCapacityTarget ? findCapacityTarget(selectedCapacityTarget.id, selectedCapacityTarget.type) : null;
  setText("[data-capacity-selected]", target ? `${target.target_type} ${target.target_id}` : "--");
  if (!container) return;
  if (!target) {
    container.innerHTML = "<p>회랑 또는 버티포트를 선택하면 상세 분석이 표시됩니다.</p>";
    return;
  }
  const aircraft = target.affected_aircraft || [];
  const isVertiport = String(target.target_type).toUpperCase() === "VERTIPORT";
  container.innerHTML = `
    <div class="capacity-detail-grid">
      <div class="detail-metric"><span>Target</span><strong>${escapeHtml(target.target_id)}</strong><small>${escapeHtml(target.name || target.target_type)}</small></div>
      <div class="detail-metric"><span>Status</span><strong>${escapeHtml(target.status)}</strong><small>${formatPercent(target.utilization)} utilization</small></div>
      <div class="detail-metric"><span>Demand / Capacity</span><strong>${escapeHtml(target.demand)} / ${escapeHtml(target.capacity)}</strong><small>Overload ${escapeHtml(target.overload || 0)}</small></div>
      <div class="detail-metric"><span>Affected UAM</span><strong>${escapeHtml(aircraft.length)}</strong><small>${escapeHtml(aircraft.join(" / ") || "--")}</small></div>
      <div class="detail-metric detail-metric--wide"><span>Diagnosis</span><strong>${escapeHtml(isVertiport ? target.bottleneck_cause : target.diagnosis)}</strong><small>${escapeHtml(target.time_window || "--")}</small></div>
    </div>
  `;
}

function renderFlowCapacity() {
  if (!flowPayload) return;
  const summary = flowPayload.summary || {};
  if (!selectedCapacityTarget && summary.main_bottleneck_id) {
    selectedCapacityTarget = { id: summary.main_bottleneck_id, type: summary.main_bottleneck_type };
  }
  renderFlowSummary(summary);
  renderFlowCondition(flowPayload.analysis_condition || {});
  renderDcbChart(flowPayload.demand_capacity_series || []);
  renderCorridorDensity(flowPayload.corridor_density || []);
  renderVertiportThroughput(flowPayload.vertiport_throughput || []);
  renderDelayPropagation(flowPayload.delay_propagation || []);
  renderBottleneckDiagnosis(flowPayload.bottleneck_diagnosis);
  renderCapacityDetail();
}

function selectCapacityTarget(targetId, targetType) {
  selectedCapacityTarget = { id: targetId, type: targetType };
  renderFlowCapacity();
}

async function refreshFlowCapacityData() {
  try {
    const response = await fetch("/api/capacity/flow-view", { headers: { Accept: "application/json" } });
    if (!response.ok) {
      throw new Error(`Flow Capacity API HTTP ${response.status}`);
    }
    flowPayload = await response.json();
    renderFlowCapacity();
  } catch (error) {
    console.error(error);
    const container = document.querySelector("[data-capacity-detail]");
    if (container) container.innerHTML = "<p>Flow & Capacity 데이터를 불러오지 못했습니다.</p>";
  }
}

function findRecommendation(recommendationId) {
  if (!decisionPayload) return null;
  return (decisionPayload.recommendations || []).find(
    (item) => String(item.recommendation_id) === String(recommendationId),
  );
}

function renderDecisionSummary() {
  if (!decisionPayload) return;
  const baseline = decisionPayload.baseline || {};
  const recommended = (decisionPayload.comparison || []).find((item) => item.recommended) || {};
  const recommendedMetrics = recommended.metrics || {};
  const handoff = decisionPayload.operation_handoff || {};
  setText("[data-decision-summary='candidate_count']", `${decisionPayload.recommendations?.length || 0}`);
  setText("[data-decision-summary='baseline_conflict']", `${baseline.conflict_count ?? "--"} CF`);
  setText("[data-decision-summary='recommended_conflict']", `${recommendedMetrics.conflict_count ?? "--"} CF`);
  setText("[data-decision-summary='handoff_status']", handoff.handoff_status || "--");
}

function renderRecommendationList() {
  const list = document.querySelector("[data-recommendation-list]");
  const recommendations = decisionPayload?.recommendations || [];
  setText("[data-recommendation-count]", `${recommendations.length} Actions`);
  if (!recommendations.some((item) => String(item.recommendation_id) === String(selectedRecommendationId))) {
    selectedRecommendationId = recommendations[0]?.recommendation_id || null;
  }
  if (!list) return;
  if (!recommendations.length) {
    list.innerHTML = "<p>생성된 조치 후보가 없습니다.</p>";
    return;
  }
  list.innerHTML = recommendations
    .map((item) => {
      const effect = item.expected_effect || {};
      return `
        <button type="button" class="recommendation-item ${String(item.recommendation_id) === String(selectedRecommendationId) ? "is-selected" : ""}" data-recommendation-id="${escapeHtml(item.recommendation_id)}">
          <span class="status-badge ${statusClass(item.severity)}">${escapeHtml(item.severity)}</span>
          <strong>${escapeHtml(item.title)}</strong>
          <span>${escapeHtml(item.category)} · ${escapeHtml(item.target_type)} ${escapeHtml(item.target_id)}</span>
          <small>${escapeHtml(effect.summary || "--")} · Score ${escapeHtml(effect.priority_score ?? "--")} · T-${escapeHtml(item.time_to_event_label || "--")}</small>
        </button>
      `;
    })
    .join("");
}

function renderEffectComparison() {
  const container = document.querySelector("[data-effect-comparison]");
  const scenarios = decisionPayload?.comparison || [];
  setText("[data-comparison-count]", `${scenarios.length} Scenarios`);
  if (!container) return;
  if (!scenarios.length) {
    container.innerHTML = "<p>비교 가능한 완화 시나리오가 없습니다.</p>";
    return;
  }
  const maxConflict = Math.max(...scenarios.map((item) => Number(item.metrics?.conflict_count || 0)), 1);
  const maxCapacity = Math.max(...scenarios.map((item) => Number(item.metrics?.capacity_warning_count || 0)), 1);
  const maxDelay = Math.max(...scenarios.map((item) => Number(item.metrics?.average_delay_sec || 0)), 1);
  container.innerHTML = scenarios
    .map((item) => {
      const metrics = item.metrics || {};
      const conflictPct = Math.min(100, (Number(metrics.conflict_count || 0) / maxConflict) * 100);
      const capacityPct = Math.min(100, (Number(metrics.capacity_warning_count || 0) / maxCapacity) * 100);
      const delayPct = Math.min(100, (Number(metrics.average_delay_sec || 0) / maxDelay) * 100);
      return `
        <div class="comparison-row ${item.recommended ? "is-recommended" : ""}" data-comparison-scenario="${escapeHtml(item.scenario_id)}">
          <div class="comparison-row__label">
            <strong>${escapeHtml(item.label)}</strong>
            <small>${escapeHtml(item.description)}</small>
          </div>
          <div class="comparison-bars" aria-label="Conflict Capacity Delay bars">
            <div class="comparison-bar comparison-bar--conflict"><span style="width:${conflictPct.toFixed(0)}%"></span></div>
            <div class="comparison-bar comparison-bar--capacity"><span style="width:${capacityPct.toFixed(0)}%"></span></div>
            <div class="comparison-bar comparison-bar--delay"><span style="width:${delayPct.toFixed(0)}%"></span></div>
          </div>
          <div class="comparison-row__metrics">
            <span>CF ${escapeHtml(metrics.conflict_count ?? "--")}</span>
            <span>CAP-W ${escapeHtml(metrics.capacity_warning_count ?? "--")}</span>
            <span>Avg ${formatDelay(metrics.average_delay_sec)}</span>
            <span>Over ${escapeHtml(metrics.over_capacity_minutes ?? "--")}m</span>
          </div>
        </div>
      `;
    })
    .join("");
}

function renderRecommendationDetail() {
  const container = document.querySelector("[data-recommendation-detail]");
  const item = findRecommendation(selectedRecommendationId);
  setText("[data-recommendation-selected]", item ? item.recommendation_id : "--");
  if (!container) return;
  if (!item) {
    container.innerHTML = "<p>조치 후보를 선택하면 예상 효과와 실행 단계가 표시됩니다.</p>";
    return;
  }
  const before = item.before || {};
  const after = item.after || {};
  const effect = item.expected_effect || {};
  const metricCards = [
    ["Conflict", before.conflict_count, after.conflict_count, ""],
    ["Capacity W", before.capacity_warning_count, after.capacity_warning_count, ""],
    ["Avg Delay", formatDelay(before.average_delay_sec), formatDelay(after.average_delay_sec), formatSignedDelay(effect.average_delay_delta_sec)],
    ["Max Delay", formatDelay(before.max_delay_sec), formatDelay(after.max_delay_sec), formatSignedDelay(effect.max_delay_delta_sec)],
    ["Over Cap", `${before.over_capacity_minutes ?? "--"}m`, `${after.over_capacity_minutes ?? "--"}m`, `${effect.over_capacity_minutes_delta > 0 ? "+" : ""}${effect.over_capacity_minutes_delta ?? 0}m`],
    ["Network D/C", formatPercent(before.network_utilization), formatPercent(after.network_utilization), `${effect.network_utilization_delta > 0 ? "+" : ""}${formatPercent(effect.network_utilization_delta)}`],
  ];
  container.innerHTML = `
    <div class="recommendation-head">
      <span class="status-badge ${statusClass(item.severity)}">${escapeHtml(item.severity)}</span>
      <strong>${escapeHtml(item.title)}</strong>
      <small>${escapeHtml(item.rationale)}</small>
    </div>
    <div class="effect-grid">
      ${metricCards
        .map(
          ([label, beforeValue, afterValue, deltaValue]) => `
            <div class="effect-metric">
              <span>${escapeHtml(label)}</span>
              <strong>${escapeHtml(beforeValue)} → ${escapeHtml(afterValue)}</strong>
              <small>${escapeHtml(deltaValue || "change included")}</small>
            </div>
          `,
        )
        .join("")}
    </div>
    <div class="decision-columns">
      <div>
        <h5>Action Steps</h5>
        <ol>${(item.action_steps || []).map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ol>
      </div>
      <div>
        <h5>Risk Notes</h5>
        <ul>${(item.risk_notes || []).map((note) => `<li>${escapeHtml(note)}</li>`).join("")}</ul>
      </div>
    </div>
    <div class="intent-preview">
      <h5>Operation Intent Preview</h5>
      <pre>${escapeHtml(JSON.stringify(item.operation_intent || {}, null, 2))}</pre>
    </div>
  `;
}

function renderOperationHandoff() {
  const container = document.querySelector("[data-operation-handoff]");
  const handoff = decisionPayload?.operation_handoff;
  setText("[data-operation-handoff-status]", handoff?.handoff_status || "--");
  if (!container) return;
  if (!handoff) {
    container.innerHTML = "<p>OperationModule preview 정보를 불러오지 못했습니다.</p>";
    return;
  }
  const actions = handoff.command_package?.actions || [];
  container.innerHTML = `
    <div class="handoff-status">
      <span class="status-badge ${handoff.available ? "status-badge--NORMAL" : "status-badge--CAUTION"}">${escapeHtml(handoff.handoff_status)}</span>
      <strong>${escapeHtml(handoff.package_id)}</strong>
      <small>${escapeHtml(handoff.handoff_mode)} · operator confirmation required</small>
    </div>
    <div class="operation-package">
      <div><span>Target</span><strong>${escapeHtml(handoff.target_module)}</strong></div>
      <div><span>Available</span><strong>${handoff.available ? "YES" : "NO"}</strong></div>
      <div><span>Actions</span><strong>${escapeHtml(actions.length)}</strong></div>
      <div><span>Recommended</span><strong>${escapeHtml(handoff.recommended_scenario_id || "--")}</strong></div>
    </div>
    <p class="handoff-path">${escapeHtml(handoff.module_root)}</p>
    <ul class="handoff-notes">
      ${(handoff.notes || []).map((note) => `<li>${escapeHtml(note)}</li>`).join("")}
    </ul>
  `;
}

function renderReportPreview() {
  const container = document.querySelector("[data-report-preview]");
  const report = decisionPayload?.report;
  setText("[data-report-id]", report?.report_id || "--");
  if (!container) return;
  if (!report) {
    container.innerHTML = "<p>시나리오 결과 리포트가 없습니다.</p>";
    return;
  }
  container.innerHTML = `
    <div class="report-head">
      <strong>${escapeHtml(report.title)}</strong>
      <small>${escapeHtml(report.report_id)} · ${escapeHtml(formatTime(report.generated_at))}</small>
    </div>
    <p>${escapeHtml(report.summary)}</p>
    <div class="report-sections">
      ${(report.sections || [])
        .map(
          (section) => `
            <section>
              <h5>${escapeHtml(section.heading)}</h5>
              <ul>${(section.items || []).map((line) => `<li>${escapeHtml(line)}</li>`).join("")}</ul>
            </section>
          `,
        )
        .join("")}
    </div>
  `;
}

function syncRecommendationRelatedTargets(item, { fly = true } = {}) {
  if (!item) return;
  if (item.related_conflict_id && trafficPayload) {
    selectConflict(item.related_conflict_id, { fly });
  } else if (String(item.target_type || "").toUpperCase() === "AIRCRAFT" && item.target_id) {
    selectAircraftOnMap(item.target_id);
  }
  if ((item.target_type === "CORRIDOR" || item.target_type === "VERTIPORT") && flowPayload) {
    const target = findCapacityTarget(item.target_id, item.target_type);
    if (target) {
      selectCapacityTarget(target.target_id, target.target_type);
    }
  }
}

function selectRelatedRecommendationFromTargets(targets, { syncRelated = false } = {}) {
  if (!decisionPayload || !targets.length) return false;
  const targetSet = new Set(targets.map(String));
  const recommendation = (decisionPayload.recommendations || []).find((item) => {
    if (targetSet.has(String(item.target_id)) || targetSet.has(String(item.related_conflict_id))) return true;
    return (item.affected_aircraft || []).some((aircraftId) => targetSet.has(String(aircraftId)));
  });
  if (!recommendation) return false;
  selectRecommendation(recommendation.recommendation_id, { syncRelated });
  return true;
}

function renderDecisionSupport({ syncRelated = false } = {}) {
  if (!decisionPayload) return;
  renderDecisionSummary();
  renderRecommendationList();
  renderEffectComparison();
  renderRecommendationDetail();
  renderOperationHandoff();
  renderReportPreview();
  if (syncRelated) {
    syncRecommendationRelatedTargets(findRecommendation(selectedRecommendationId), { fly: true });
  }
}

function selectRecommendation(recommendationId, { syncRelated = true } = {}) {
  selectedRecommendationId = recommendationId;
  renderDecisionSupport({ syncRelated });
}

async function refreshDecisionSupportData() {
  try {
    const response = await fetch("/api/decision-support", { headers: { Accept: "application/json" } });
    if (!response.ok) {
      throw new Error(`Decision Support API HTTP ${response.status}`);
    }
    decisionPayload = await response.json();
    if (!selectedRecommendationId) {
      selectedRecommendationId = decisionPayload.recommendations?.[0]?.recommendation_id || null;
    }
    renderDecisionSupport({ syncRelated: false });
  } catch (error) {
    console.error(error);
    const list = document.querySelector("[data-recommendation-list]");
    if (list) list.innerHTML = "<p>Decision Support 데이터를 불러오지 못했습니다.</p>";
  }
}

function replayFrames() {
  return replayPayload?.frames || [];
}

function findReplayFrame(step) {
  return replayFrames().find((frame) => Number(frame.step) === Number(step));
}

function replayProgressPct() {
  const frames = replayFrames();
  if (!frames.length) return 0;
  const index = frames.findIndex((frame) => Number(frame.step) === Number(selectedReplayStep));
  if (frames.length === 1) return 100;
  return Math.max(0, Math.min(100, (index / (frames.length - 1)) * 100));
}

function renderReplaySummary() {
  const summary = replayPayload?.summary || {};
  const playback = replayPayload?.playback || {};
  const validation = validationPayload?.completion || {};
  setText("[data-replay-summary='frame_count']", `${playback.frame_count ?? replayFrames().length}`);
  setText("[data-replay-summary='candidate_count']", `${summary.decision_candidates ?? "--"}`);
  setText("[data-replay-summary='report_id']", summary.report_id || "--");
  setText("[data-replay-summary='validation']", validation.percentage != null ? `${validation.percentage}%` : "--");
  const progress = document.querySelector("[data-replay-progress]");
  if (progress) {
    progress.style.width = `${replayProgressPct().toFixed(0)}%`;
  }
}

function renderReplayTimeline() {
  const container = document.querySelector("[data-replay-timeline]");
  const frames = replayFrames();
  setText("[data-replay-count]", `${frames.length} Frames`);
  if (!container) return;
  if (!frames.length) {
    container.innerHTML = "<p>리플레이 프레임이 없습니다.</p>";
    return;
  }
  container.innerHTML = frames
    .map(
      (frame) => `
        <button type="button" class="replay-step ${Number(frame.step) === Number(selectedReplayStep) ? "is-selected" : ""}" data-replay-step="${escapeHtml(frame.step)}">
          <span class="replay-step__index">${escapeHtml(frame.step)}</span>
          <span class="status-badge ${statusClass(frame.severity)}">${escapeHtml(frame.severity)}</span>
          <strong>${escapeHtml(frame.time_label)} · ${escapeHtml(frame.title)}</strong>
          <small>${escapeHtml(frame.screen)} · ${escapeHtml(frame.operator_focus)}</small>
        </button>
      `,
    )
    .join("");
}

function renderReplayDetail() {
  const container = document.querySelector("[data-replay-detail]");
  const frame = findReplayFrame(selectedReplayStep);
  setText("[data-replay-selected]", frame ? `Step ${frame.step} / ${frame.screen}` : "--");
  if (!container) return;
  if (!frame) {
    container.innerHTML = "<p>리플레이 프레임을 선택하거나 Play를 누르면 상세 설명이 표시됩니다.</p>";
    return;
  }
  const metrics = frame.metrics || {};
  const targets = frame.related_targets || [];
  container.innerHTML = `
    <div class="replay-frame-head">
      <span class="status-badge ${statusClass(frame.severity)}">${escapeHtml(frame.severity)}</span>
      <strong>${escapeHtml(frame.title)}</strong>
      <small>${escapeHtml(formatTime(frame.timestamp))} · ${escapeHtml(frame.screen)} · ${escapeHtml(frame.operator_focus)}</small>
    </div>
    <p>${escapeHtml(frame.description)}</p>
    <div class="replay-metric-grid">
      <div><span>Active</span><strong>${escapeHtml(metrics.active_flights ?? "--")}</strong></div>
      <div><span>Conflict</span><strong>${escapeHtml(metrics.conflict_count ?? "--")}</strong></div>
      <div><span>Avg Delay</span><strong>${formatDelay(metrics.average_delay_sec)}</strong></div>
      <div><span>Capacity W</span><strong>${escapeHtml(metrics.capacity_warning_count ?? "--")}</strong></div>
      <div><span>Network D/C</span><strong>${metrics.network_utilization != null ? formatPercent(metrics.network_utilization) : "--"}</strong></div>
      <div><span>Over Cap</span><strong>${metrics.over_capacity_minutes != null ? `${escapeHtml(metrics.over_capacity_minutes)}m` : "--"}</strong></div>
    </div>
    <div class="replay-targets">
      <h5>Related Targets</h5>
      <p>${targets.map((target) => `<span>${escapeHtml(target)}</span>`).join("") || "<span>--</span>"}</p>
    </div>
  `;
}

function renderReportExport() {
  const container = document.querySelector("[data-report-export]");
  const report = reportPayload || decisionPayload?.report || {};
  setText("[data-report-export-status]", report.report_id || replayPayload?.summary?.report_id || "--");
  if (!container) return;
  const exports = {
    json: "/api/reports/scenario-result",
    markdown: "/api/reports/scenario-result.md",
    html: "/api/reports/scenario-result.html",
  };
  container.innerHTML = `
    <div class="report-export-head">
      <strong>${escapeHtml(report.title || "PSU Scenario Result Report")}</strong>
      <small>${escapeHtml(report.report_id || replayPayload?.summary?.report_id || "--")}</small>
    </div>
    <div class="report-links">
      <a href="${exports.json}" target="_blank" rel="noreferrer">JSON</a>
      <a href="${exports.markdown}" target="_blank" rel="noreferrer">Markdown</a>
      <a href="${exports.html}" target="_blank" rel="noreferrer">HTML</a>
    </div>
    <p>운영자 승인 전 자동 실행 없이 시나리오 결과와 Decision Support 비교를 출력합니다.</p>
  `;
}

function renderValidationBoard() {
  const container = document.querySelector("[data-validation-board]");
  const sections = validationPayload?.checks || [];
  const completion = validationPayload?.completion || {};
  setText("[data-validation-count]", `${completion.passed ?? 0}/${completion.total ?? 0} PASS`);
  if (!container) return;
  if (!sections.length) {
    container.innerHTML = "<p>최종 검증 결과가 없습니다.</p>";
    return;
  }
  container.innerHTML = `
    <div class="validation-summary">
      <strong>${escapeHtml(completion.percentage ?? 0)}%</strong>
      <span>PASS ${escapeHtml(completion.passed ?? 0)} · WARN ${escapeHtml(completion.warnings ?? 0)} · TOTAL ${escapeHtml(completion.total ?? 0)}</span>
    </div>
    <div class="validation-sections">
      ${sections
        .map(
          (section) => `
            <section>
              <h5>${escapeHtml(section.section)}</h5>
              <ul>
                ${(section.items || [])
                  .map(
                    (item) => `
                      <li>
                        <span class="status-badge ${item.status === "PASS" ? "status-badge--NORMAL" : "status-badge--CAUTION"}">${escapeHtml(item.status)}</span>
                        <strong>${escapeHtml(item.name)}</strong>
                        <small>${escapeHtml(item.detail)}</small>
                      </li>
                    `,
                  )
                  .join("")}
              </ul>
            </section>
          `,
        )
        .join("")}
    </div>
    <div class="known-limits">
      <h5>Known Limits</h5>
      <ul>${(validationPayload.known_limits || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    </div>
  `;
}

function renderReplayReport() {
  renderReplaySummary();
  renderReplayTimeline();
  renderReplayDetail();
  renderReportExport();
  renderValidationBoard();
}

function applyReplayFrameNavigation(frame) {
  if (!frame) return;
  const tabId = frame.recommended_tab || screenToTabId(frame.screen);
  setActiveTab(tabId, true);
  if (tabId === "traffic-map" && frame.conflict_id) {
    selectConflict(frame.conflict_id, { fly: true });
    window.setTimeout(() => window.__PSU_MAP__?.resize?.(), 80);
  }
  if (tabId === "flow-capacity") {
    const focus = frame.map_focus || {};
    const target = findCapacityTarget(focus.id) || (frame.related_targets || []).map((target) => findCapacityTarget(target)).find(Boolean);
    if (target) {
      selectCapacityTarget(target.target_id, target.target_type);
    }
  }
  if (tabId === "decision-support") {
    const recommendationId = (frame.related_targets || []).find((target) => String(target).startsWith("DS-"));
    if (recommendationId) {
      selectRecommendation(recommendationId, { syncRelated: false });
    }
  }
}

function selectReplayStep(step, { navigate = false } = {}) {
  const frames = replayFrames();
  if (!frames.length) return;
  const first = frames[0].step;
  const last = frames[frames.length - 1].step;
  selectedReplayStep = Math.max(Number(first), Math.min(Number(last), Number(step)));
  renderReplayReport();
  if (navigate) {
    applyReplayFrameNavigation(findReplayFrame(selectedReplayStep));
  }
}

function stopReplay() {
  if (replayTimer) {
    window.clearInterval(replayTimer);
    replayTimer = null;
  }
}

function startReplay() {
  stopReplay();
  const frames = replayFrames();
  if (!frames.length) return;
  applyReplayFrameNavigation(findReplayFrame(selectedReplayStep));
  replayTimer = window.setInterval(() => {
    const currentIndex = frames.findIndex((frame) => Number(frame.step) === Number(selectedReplayStep));
    if (currentIndex >= frames.length - 1) {
      stopReplay();
      setActiveTab("replay-report", true);
      return;
    }
    selectReplayStep(frames[currentIndex + 1].step, { navigate: true });
  }, replayIntervalMs);
}

function handleReplayControl(control) {
  const frames = replayFrames();
  if (!frames.length) return;
  const currentIndex = frames.findIndex((frame) => Number(frame.step) === Number(selectedReplayStep));
  if (control === "play") {
    startReplay();
    return;
  }
  if (control === "pause") {
    stopReplay();
    return;
  }
  if (control === "reset") {
    stopReplay();
    selectedReplayStep = frames[0].step;
    renderReplayReport();
    setActiveTab("replay-report", true);
    return;
  }
  if (control === "next") {
    stopReplay();
    const next = frames[Math.min(frames.length - 1, currentIndex + 1)] || frames[0];
    selectReplayStep(next.step, { navigate: true });
    return;
  }
  if (control === "prev") {
    stopReplay();
    const prev = frames[Math.max(0, currentIndex - 1)] || frames[0];
    selectReplayStep(prev.step, { navigate: true });
  }
}

async function refreshReplayReportData() {
  try {
    const [replayResponse, validationResponse, reportResponse] = await Promise.all([
      fetch("/api/replay", { headers: { Accept: "application/json" } }),
      fetch("/api/final-validation", { headers: { Accept: "application/json" } }),
      fetch("/api/reports/scenario-result", { headers: { Accept: "application/json" } }),
    ]);
    if (!replayResponse.ok || !validationResponse.ok || !reportResponse.ok) {
      throw new Error("Replay/Validation API 응답 실패");
    }
    replayPayload = await replayResponse.json();
    validationPayload = await validationResponse.json();
    reportPayload = await reportResponse.json();
    if (!findReplayFrame(selectedReplayStep)) {
      selectedReplayStep = replayFrames()[0]?.step || 1;
    }
    renderReplayReport();
  } catch (error) {
    console.error(error);
    const timeline = document.querySelector("[data-replay-timeline]");
    if (timeline) timeline.innerHTML = "<p>Replay / Report 데이터를 불러오지 못했습니다.</p>";
  }
}

async function refreshScenarioData() {
  try {
    const overviewResponse = await fetch("/api/overview/dashboard", { headers: { Accept: "application/json" } });
    if (!overviewResponse.ok) {
      throw new Error("시나리오 데이터 API 응답 실패");
    }
    const overview = await overviewResponse.json();
    const kpis = overview.kpis || {};

    setText("[data-scenario-name]", overview.scenario?.name || "--");
    setText("[data-scenario-time]", formatTime(overview.generated_at));
    setText("[data-top-priority]", overview.top_priority_event?.title || "--");
    updateKpiCards(kpis);
    renderPriorityEvents(overview.priority_events || []);
    renderVertiports(overview.vertiport_summary || []);
    renderTrafficTrend(overview.traffic_trend || [], overview.traffic_summary || {});
    renderOperationalSnapshot(overview);
    renderMiniMapSummary(overview.map_summary || {});
  } catch (error) {
    console.error(error);
  }
}

async function bootMap() {
  if (mapReady) {
    return;
  }
  try {
    const map = await initPsuMap({ statusEl: mapStatus });
    mapReady = Boolean(map);
    if (document.querySelector('[data-panel="traffic-map"]:not([hidden])')) {
      window.setTimeout(() => window.__PSU_MAP__?.resize?.(), 80);
    }
    window.setTimeout(() => {
      if (selectedConflictId) {
        selectConflictOnMap(selectedConflictId, { fly: false });
      }
    }, 1200);
  } catch (error) {
    if (mapStatus) {
      mapStatus.textContent = error instanceof Error ? error.message : String(error);
    }
  }
}

for (const tab of tabs) {
  tab.addEventListener("click", () => {
    const tabId = tab.dataset.tab || "overview";
    setActiveTab(tabId, true);
    if (window.location.hash !== `#${tabId}`) {
      window.history.replaceState(null, "", `#${tabId}`);
    }
    if (tabId === "traffic-map") {
      window.setTimeout(() => window.__PSU_MAP__?.resize?.(), 50);
    }
  });
}


if (themeToggle) {
  themeToggle.addEventListener("click", () => {
    const currentTheme = normalizedTheme(document.documentElement.dataset.theme);
    applyTheme(currentTheme === "light" ? "dark" : "light", { persist: true });
  });
}

document.addEventListener("click", (event) => {
  const filter = event.target.closest("[data-traffic-filter]");
  if (filter) {
    trafficFilter = filter.dataset.trafficFilter || "ALL";
    for (const chip of document.querySelectorAll("[data-traffic-filter]")) {
      chip.classList.toggle("is-active", chip === filter);
    }
    setTrafficMapFilter(trafficFilter);
    renderTrafficWorkspace({ preserveSelection: true });
    return;
  }

  const flightItem = event.target.closest("[data-aircraft-id]");
  if (flightItem) {
    selectAircraft(flightItem.dataset.aircraftId, { fly: true });
    return;
  }

  const timelineItem = event.target.closest("[data-conflict-id]");
  if (timelineItem) {
    selectConflict(timelineItem.dataset.conflictId, { fly: true });
    return;
  }

  const capacityItem = event.target.closest("[data-capacity-target]");
  if (capacityItem) {
    selectCapacityTarget(capacityItem.dataset.capacityTarget, capacityItem.dataset.capacityType);
    return;
  }

  const recommendationItem = event.target.closest("[data-recommendation-id]");
  if (recommendationItem) {
    selectRecommendation(recommendationItem.dataset.recommendationId, { syncRelated: true });
    return;
  }

  const replayStep = event.target.closest("[data-replay-step]");
  if (replayStep) {
    stopReplay();
    selectReplayStep(replayStep.dataset.replayStep, { navigate: false });
    return;
  }

  const replayControl = event.target.closest("[data-replay-control]");
  if (replayControl) {
    handleReplayControl(replayControl.dataset.replayControl);
    return;
  }

  const item = event.target.closest("[data-recommended-screen]");
  if (!item) return;
  const tabId = screenToTabId(item.dataset.recommendedScreen);
  setActiveTab(tabId, true);
  if (tabId === "traffic-map") {
    const targets = String(item.dataset.relatedTargets || "").split(",").filter(Boolean);
    selectRelatedConflictFromTargets(targets, { fly: true });
    window.setTimeout(() => window.__PSU_MAP__?.resize?.(), 80);
  }
  if (tabId === "flow-capacity") {
    const targets = String(item.dataset.relatedTargets || "").split(",").filter(Boolean);
    const selected = targets.find((target) => findCapacityTarget(target));
    if (selected) {
      const target = findCapacityTarget(selected);
      selectCapacityTarget(target.target_id, target.target_type);
    }
  }
  if (tabId === "decision-support") {
    const targets = String(item.dataset.relatedTargets || "").split(",").filter(Boolean);
    selectRelatedRecommendationFromTargets(targets, { syncRelated: true });
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") return;
  const item = event.target.closest("[data-recommended-screen], [data-conflict-id], [data-aircraft-id], [data-traffic-filter], [data-capacity-target], [data-recommendation-id], [data-replay-step], [data-replay-control]");
  if (!item) return;
  event.preventDefault();
  item.click();
});

document.addEventListener("change", (event) => {
  const speed = event.target.closest("[data-replay-speed]");
  if (!speed) return;
  replayIntervalMs = Number(speed.value || 1600);
  if (replayTimer) {
    startReplay();
  }
});

window.addEventListener("psu:conflict-selected", (event) => {
  const conflictId = event.detail?.conflictId;
  if (conflictId) {
    selectConflict(conflictId, { fly: false });
  }
});

window.addEventListener("psu:aircraft-selected", (event) => {
  const aircraftId = event.detail?.aircraftId;
  if (aircraftId) {
    selectAircraft(aircraftId, { fly: false });
  }
});

initTheme();
setActiveTab(tabIdFromHash());
window.addEventListener("hashchange", () => setActiveTab(tabIdFromHash()));
refreshStatus();
refreshScenarioData();
refreshTrafficData();
refreshFlowCapacityData();
refreshDecisionSupportData();
refreshReplayReportData();
bootMap();
window.setInterval(refreshStatus, 10_000);
window.setInterval(refreshScenarioData, 10_000);
window.setInterval(refreshTrafficData, 10_000);
window.setInterval(refreshFlowCapacityData, 10_000);
window.setInterval(refreshDecisionSupportData, 10_000);
window.setInterval(refreshReplayReportData, 10_000);
