import { initPsuMap, selectAircraftOnMap, setDraftRouteOnMap, setPsuMapTheme } from "./map.js?v=psu-console-v39";

const THEME_STORAGE_KEY = "psu-theme";
const PLAN_DRAFT_STORAGE_KEY = "psu-plan-modification-drafts";
const PLAN_COMMAND_COUNTER_STORAGE_KEY = "psu-plan-command-counter";
const ACTION_COMMAND_STORAGE_KEY = "psu-action-command-requests";
const ACTION_COMMAND_COUNTER_STORAGE_KEY = "psu-action-command-counter";

const state = {
  activeTab: "strategic-plans",
  planGroup: "byDestination",
  strategic: null,
  selectedPlanKey: null,
  savedPlanDrafts: [],
  planModificationCommandId: "",
  planModificationTimestamp: "",
  tactical: null,
  warnings: null,
  selectedAircraftId: null,
  aircraftPanelOpen: false,
  aircraftPanelMode: "status",
  modalActions: [],
  actionDraftForm: null,
  savedActionDrafts: [],
  actionCommandId: "",
  actionCommandTimestamp: "",
  mapPick: null,
  operationalLayers: null,
  replay: null,
  report: null,
  validation: null,
  selectedReplayStep: 1,
  replayTimer: null,
  replayIntervalMs: 1600,
  mapReady: false,
};

const ACTION_LABELS = {
  directTo: "Avoidance route",
  hold: "Holding pattern",
  land: "Alternate or emergency landing",
  setSpeed: "Speed adjustment",
  rejoinPlan: "Rejoin planned route",
};

const ACTION_KO = {
  directTo: "회피 경로",
  hold: "대기 선회",
  land: "대체/비상 착륙",
  setSpeed: "속도 조정",
  rejoinPlan: "계획 경로 복귀",
};

const FATO_OPTIONS = Array.from({ length: 8 }, (_, index) => {
  const value = `FATO-${index + 1}`;
  return [value, value];
});

const TACTICAL_REASON_LABELS = {
  LOSS_OF_SEPARATION_RISK: "Loss of separation risk",
  LOCAL_CORRIDOR_BLOCKED: "Local corridor blocked",
  LOW_BATTERY: "Low battery",
  WEATHER_AVOIDANCE: "Weather avoidance",
  OPERATOR_OVERRIDE: "Operator override",
  EMERGENCY_LANDING: "Emergency landing",
};

const TACTICAL_REASON_KO = {
  LOSS_OF_SEPARATION_RISK: "분리 거리 위험",
  LOCAL_CORRIDOR_BLOCKED: "국지 회랑 차단",
  LOW_BATTERY: "배터리 부족",
  WEATHER_AVOIDANCE: "기상 회피",
  OPERATOR_OVERRIDE: "운영자 개입",
  EMERGENCY_LANDING: "비상 착륙",
};

const TACTICAL_REASON_ACTIONS = {
  LOSS_OF_SEPARATION_RISK: ["directTo", "hold", "setSpeed"],
  LOCAL_CORRIDOR_BLOCKED: ["directTo", "hold", "rejoinPlan"],
  LOW_BATTERY: ["land", "directTo", "setSpeed"],
  WEATHER_AVOIDANCE: ["directTo", "hold"],
  OPERATOR_OVERRIDE: ["directTo", "hold", "setSpeed", "rejoinPlan", "land"],
  EMERGENCY_LANDING: ["land", "directTo"],
};

const TACTICAL_REASON_HINTS = {
  LOSS_OF_SEPARATION_RISK: "Prepare an avoidance route, temporary hold, or speed adjustment.",
  LOCAL_CORRIDOR_BLOCKED: "Route around the blocked segment, hold locally, or rejoin after the blockage.",
  LOW_BATTERY: "Prioritize alternate landing; speed reduction or direct routing can be added if needed.",
  WEATHER_AVOIDANCE: "Generate a weather avoidance route or hold clear of the affected area.",
  OPERATOR_OVERRIDE: "Manual override allows any available action type.",
  EMERGENCY_LANDING: "Prioritize emergency landing site or direct routing to a safe landing point.",
};

const STRATEGIC_MODIFICATION_TYPES = [
  ["scheduleResourceUpdate", "Schedule or resource update"],
  ["routeUpdate", "Route update"],
  ["aircraftSwap", "Aircraft swap"],
  ["delayOnly", "Delay only"],
  ["cancelPlan", "Cancel plan"],
];

const STRATEGIC_REASONS = [
  ["VERTIPORT_CAPACITY", "Vertiport capacity"],
  ["CORRIDOR_CLOSED", "Corridor closed"],
  ["WEATHER", "Weather"],
  ["VEHICLE_UNAVAILABLE", "Vehicle unavailable"],
  ["OPERATOR_REQUEST", "Operator request"],
];

const STRATEGIC_SCOPES = [
  ["departureAndArrival", "Departure and arrival"],
  ["departureOnly", "Departure only"],
  ["arrivalOnly", "Arrival only"],
  ["enRouteOnly", "En-route only"],
  ["aircraftOnly", "Aircraft only"],
  ["fullPlan", "Full plan"],
];

const STRATEGIC_MODIFICATION_KO = {
  scheduleResourceUpdate: "일정/자원 변경",
  routeUpdate: "경로 변경",
  aircraftSwap: "비행체 교체",
  delayOnly: "지연 반영",
  cancelPlan: "계획 취소",
};

const STRATEGIC_REASON_KO = {
  VERTIPORT_CAPACITY: "버티포트 용량",
  CORRIDOR_CLOSED: "회랑 폐쇄",
  WEATHER: "기상",
  VEHICLE_UNAVAILABLE: "비행체 사용 불가",
  OPERATOR_REQUEST: "운영자 요청",
};

const STRATEGIC_SCOPE_KO = {
  departureAndArrival: "출발/도착",
  departureOnly: "출발만",
  arrivalOnly: "도착만",
  enRouteOnly: "비행 경로만",
  aircraftOnly: "비행체만",
  fullPlan: "전체 계획",
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function asNumber(value, fallback = null) {
  if (value === "" || value == null) return fallback;
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function formatCoord(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(5) : "--";
}

function formatSpeed(value) {
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(1)} m/s` : "--";
}

function formatTime(value) {
  if (!value) return "--";
  const text = String(value);
  const match = text.match(/T?(\d{2}:\d{2})(?::\d{2})?/);
  return match ? match[1] : text;
}

function utcDateStamp(date = new Date()) {
  return date.toISOString().slice(0, 10).replace(/-/g, "");
}

function nextStrategicCommandId() {
  const date = utcDateStamp();
  let nextSeq = 1;
  try {
    const saved = JSON.parse(localStorage.getItem(PLAN_COMMAND_COUNTER_STORAGE_KEY) || "{}");
    if (saved?.date === date) {
      nextSeq = Math.max(1, Number(saved.seq || 0) + 1);
    }
    localStorage.setItem(PLAN_COMMAND_COUNTER_STORAGE_KEY, JSON.stringify({ date, seq: nextSeq }));
  } catch (_) {
    nextSeq = Math.floor(Date.now() / 1000) % 1000 || 1;
  }
  return `SMP-${date}-${String(nextSeq).padStart(3, "0")}`;
}

function nextTacticalCommandId() {
  const date = utcDateStamp();
  let nextSeq = 1;
  try {
    const saved = JSON.parse(localStorage.getItem(ACTION_COMMAND_COUNTER_STORAGE_KEY) || "{}");
    if (saved?.date === date) {
      nextSeq = Math.max(1, Number(saved.seq || 0) + 1);
    }
    localStorage.setItem(ACTION_COMMAND_COUNTER_STORAGE_KEY, JSON.stringify({ date, seq: nextSeq }));
  } catch (_) {
    nextSeq = Math.floor(Date.now() / 1000) % 1000 || 1;
  }
  return `TMP-${date}-${String(nextSeq).padStart(3, "0")}`;
}

function setText(selector, text) {
  const element = $(selector);
  if (element) element.textContent = text;
}

function optionMarkup(options, selectedValue = "") {
  return options
    .map(([value, label]) => `<option value="${escapeHtml(value)}" ${value === selectedValue ? "selected" : ""}>${escapeHtml(label)}</option>`)
    .join("");
}

function buttonCardMarkup(items, selectedValue, attrName, descriptions = {}) {
  return items
    .map(([value, label]) => `
      <button class="option-card ${value === selectedValue ? "is-selected" : ""}" type="button" ${attrName}="${escapeHtml(value)}">
        <strong>${escapeHtml(label)}</strong>
        ${descriptions[value] ? `<small>${escapeHtml(descriptions[value])}</small>` : ""}
      </button>
    `)
    .join("");
}

function planOptionCardMarkup(name, items, selectedValue, descriptions = {}) {
  return items
    .map(([value, label]) => `
      <button class="option-card ${value === selectedValue ? "is-selected" : ""}" type="button" data-plan-option-name="${escapeHtml(name)}" data-plan-option-value="${escapeHtml(value)}">
        <strong>${escapeHtml(label)}</strong>
        ${descriptions[value] ? `<small>${escapeHtml(descriptions[value])}</small>` : ""}
      </button>
    `)
    .join("");
}

function bilingualLabel(en, ko) {
  return `${escapeHtml(en)} <small>${escapeHtml(ko)}</small>`;
}

function setConnectionState(isOnline, label) {
  const element = $("[data-health-status]");
  if (!element) return;
  element.classList.remove("is-checking", "is-online", "is-offline");
  element.classList.add(isOnline ? "is-online" : "is-offline");
  element.title = label;
  element.setAttribute("aria-label", label);
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { Accept: "application/json", ...(options.headers || {}) },
    cache: "no-store",
    ...options,
  });
  if (!response.ok) {
    throw new Error(`${url} HTTP ${response.status}`);
  }
  return response.json();
}

async function postJson(url, payload) {
  return fetchJson(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

function normalizedTheme(value) {
  return value === "light" ? "light" : "dark";
}

function applyTheme(theme, { persist = false } = {}) {
  const nextTheme = normalizedTheme(theme);
  document.documentElement.dataset.theme = nextTheme;
  const toggle = $("[data-theme-toggle]");
  if (toggle) {
    toggle.dataset.theme = nextTheme;
    toggle.title = nextTheme === "light" ? "Switch to dark theme" : "Switch to light theme";
    toggle.setAttribute("aria-label", toggle.title);
  }
  setPsuMapTheme(nextTheme);
  window.dispatchEvent(new CustomEvent("psu:theme-changed", { detail: { theme: nextTheme } }));
  window.setTimeout(() => window.__PSU_MAP__?.resize?.(), 80);
  if (persist) {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
    } catch (_) {
      // localStorage may be unavailable in restricted contexts.
    }
  }
}

function initTheme() {
  let theme = normalizedTheme(document.documentElement.dataset.theme);
  try {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    if (saved === "light" || saved === "dark") theme = saved;
  } catch (_) {
    // Keep bootstrap theme.
  }
  applyTheme(theme);
}

function tabIdFromHash() {
  const value = String(window.location.hash || "").replace(/^#/, "");
  return $$("[data-panel]").some((panel) => panel.dataset.panel === value) ? value : "strategic-plans";
}

function setActiveTab(tabId, updateHash = true) {
  const target = $$("[data-panel]").some((panel) => panel.dataset.panel === tabId) ? tabId : "strategic-plans";
  state.activeTab = target;
  for (const tab of $$("[data-tab]")) {
    const active = tab.dataset.tab === target;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", active ? "true" : "false");
  }
  for (const panel of $$("[data-panel]")) {
    const active = panel.dataset.panel === target;
    panel.hidden = !active;
    panel.classList.toggle("is-active-panel", active);
  }
  if (updateHash && window.location.hash !== `#${target}`) {
    window.history.replaceState(null, "", `#${target}`);
  }
  if (target === "tactical-monitoring") {
    bootMap();
    window.setTimeout(() => window.__PSU_MAP__?.resize?.(), 90);
  }
}

async function refreshStatus() {
  try {
    const payload = await fetchJson("/api/status");
    const stream = payload.vehicle_stream || {};
    const stateServer = payload.state_server || {};
    const operationStatus = payload.operation_status || {};
    const fresh = Number(stream.fresh_vehicle_count || 0);
    const connected = Boolean(payload.connected || stateServer.connected || operationStatus.connected);
    const label = fresh ? `Live tracks ${fresh}` : connected ? "Connected, waiting for live tracks" : "Waiting for live tracks";
    setConnectionState(connected, label);
    setText("[data-server-time]", payload.time?.display || label);
  } catch (error) {
    setConnectionState(false, "DTAM connection failed");
    setText("[data-server-time]", error instanceof Error ? error.message : String(error));
  }
}

function selectedPlan() {
  const plans = state.strategic?.plans || [];
  return plans.find((plan) => String(plan.key) === String(state.selectedPlanKey)) || null;
}

function selectedPlanIssues(plan) {
  return plan?.validationIssues || [];
}

function normalizeSavedPlanDrafts(value) {
  return Array.isArray(value)
    ? value.filter((item) => item && typeof item === "object" && item.result && typeof item.result === "object")
    : [];
}

function loadSavedPlanDrafts() {
  try {
    const parsed = JSON.parse(localStorage.getItem(PLAN_DRAFT_STORAGE_KEY) || "[]");
    state.savedPlanDrafts = normalizeSavedPlanDrafts(parsed);
  } catch (_) {
    state.savedPlanDrafts = [];
  }
}

function persistSavedPlanDrafts() {
  try {
    localStorage.setItem(PLAN_DRAFT_STORAGE_KEY, JSON.stringify(state.savedPlanDrafts.slice(0, 100)));
  } catch (_) {
    // Keep the in-memory queue if localStorage is unavailable.
  }
}

function loadSavedActionDrafts() {
  try {
    const parsed = JSON.parse(localStorage.getItem(ACTION_COMMAND_STORAGE_KEY) || "[]");
    state.savedActionDrafts = normalizeSavedPlanDrafts(parsed);
  } catch (_) {
    state.savedActionDrafts = [];
  }
}

function persistSavedActionDrafts() {
  try {
    localStorage.setItem(ACTION_COMMAND_STORAGE_KEY, JSON.stringify(state.savedActionDrafts.slice(0, 100)));
  } catch (_) {
    // Keep the in-memory queue if localStorage is unavailable.
  }
}

function planDraftsFor(plan) {
  if (!plan) return [];
  return state.savedPlanDrafts.filter((item) => {
    const payload = item?.result?.payload || {};
    return (
      String(payload.flightPlanNumber || "") === String(plan.flightPlanNumber || "") &&
      String(payload.aircraftId || "") === String(plan.aircraftId || "")
    );
  });
}

function latestPlanDraft(plan) {
  return planDraftsFor(plan)[0] || null;
}

function planDraftNoticeMarkup(plan) {
  const draft = latestPlanDraft(plan);
  if (!draft) return "";
  const payload = draft.result?.payload || {};
  const status = commandResultStatus(draft.result || {});
  return `
    <div class="draft-status ${status.className}">
      <strong>Modification request ${escapeHtml(status.label.toLowerCase())}.</strong>
      <small>${escapeHtml(payload.commandId || "--")} targets v${escapeHtml(payload.planVersion || "--")}. ${escapeHtml(commandResultMessage(draft.result || {}))}</small>
    </div>
  `;
}

function draftPlanKey(draft) {
  const payload = draft?.result?.payload || {};
  return `${payload.flightPlanNumber || "--"} / ${payload.aircraftId || "--"}`;
}

function renderModificationQueue() {
  const container = $("[data-modification-request-list]");
  const countEl = $("[data-modification-request-count]");
  const drafts = state.savedPlanDrafts;
  if (countEl) countEl.textContent = `${drafts.length} Requests`;
  if (!container) return;
  if (!drafts.length) {
    container.innerHTML = `
      <div class="empty-state">
        <strong>No modification requests sent.</strong>
        <small>3002 requests created from flight-plan details will appear here.</small>
      </div>
    `;
    return;
  }
  container.innerHTML = drafts
    .map((draft, index) => {
      const result = draft.result || {};
      const payload = result.payload || {};
      const status = commandResultStatus(result);
      return `
        <button class="modification-request ${status.blocked ? "is-blocked" : ""}" type="button" data-plan-draft-index="${escapeHtml(index)}">
          <span>
            <strong>${escapeHtml(draftPlanKey(draft))}</strong>
            <small>${escapeHtml(payload.commandId || "--")}</small>
          </span>
          <span>
            <strong>${escapeHtml(payload.modificationType || "--")}</strong>
            <small>${escapeHtml(payload.reasonCode || "--")} / ${escapeHtml(payload.modifyScope || "--")}</small>
          </span>
          <span>
            <strong>v${escapeHtml(payload.planVersion || "--")}</strong>
            <small>${escapeHtml(status.label)}</small>
          </span>
        </button>
      `;
    })
    .join("");
}

function openPlanDraftModal(index) {
  const draft = state.savedPlanDrafts[Number(index)];
  if (!draft) return;
  const result = draft.result || {};
  const payload = result.payload || {};
  openInfoModal({
    kicker: "Modification Request",
    title: `${payload.flightPlanNumber || "--"} / ${payload.aircraftId || "--"}`,
    body: `
      <div class="command-context-bar">
        <div><span>Command</span><strong>${escapeHtml(payload.commandId || "--")}</strong></div>
        <div><span>Target Plan</span><strong>${escapeHtml(draftPlanKey(draft))}</strong></div>
        <div><span>Requested Version</span><strong>v${escapeHtml(payload.planVersion || "--")}</strong></div>
        <div><span>Status</span><strong>${escapeHtml(commandResultStatus(result).label)}</strong></div>
      </div>
      <dl class="detail-grid detail-grid--wide">
        <div><dt>Modification Type</dt><dd>${escapeHtml(payload.modificationType || "--")}</dd></div>
        <div><dt>Reason Code</dt><dd>${escapeHtml(payload.reasonCode || "--")}</dd></div>
        <div><dt>Modify Scope</dt><dd>${escapeHtml(payload.modifyScope || "--")}</dd></div>
        <div><dt>Created</dt><dd>${escapeHtml(draft.createdAt || "--")}</dd></div>
      </dl>
      ${dispatchDetailMarkup(result)}
      ${(result.validationIssues || []).length ? `<div class="validation-list">${(result.validationIssues || []).map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>` : ""}
      <details class="technical-preview" open>
        <summary>Technical Payload</summary>
        <pre class="payload-preview">${escapeHtml(JSON.stringify(payload, null, 2))}</pre>
      </details>
    `,
    panelClass: "app-modal__panel--command",
  });
}

function actionRequestKey(draft) {
  const payload = draft?.result?.payload || {};
  return `${payload.commandId || "--"} / ${payload.aircraftId || "--"}`;
}

function actionRequestSummary(payload = {}) {
  const actions = Array.isArray(payload.actions) ? payload.actions : [];
  if (!actions.length) return "--";
  return actions.map((action) => ACTION_LABELS[action.type] || action.type || "--").join(", ");
}

function renderActionRequestQueue() {
  const container = $("[data-action-request-list]");
  const drafts = state.savedActionDrafts;
  for (const countEl of $$('[data-tactical-count="actions"]')) {
    countEl.textContent = String(drafts.length);
  }
  if (!container) return;
  if (!drafts.length) {
    container.innerHTML = `
      <div class="empty-state">
        <strong>No tactical commands sent.</strong>
        <small>3003 tactical commands created from aircraft status will appear here.</small>
      </div>
    `;
    return;
  }
  container.innerHTML = drafts
    .map((draft, index) => {
      const result = draft.result || {};
      const payload = result.payload || {};
      const status = commandResultStatus(result);
      return `
        <button class="action-request ${status.blocked ? "is-blocked" : ""}" type="button" data-action-request-index="${escapeHtml(index)}">
          <span>
            <strong>${escapeHtml(payload.aircraftId || "--")}</strong>
            <small>${escapeHtml(payload.commandId || "--")}</small>
          </span>
          <span>
            <strong>${escapeHtml(payload.reasonCode || "--")}</strong>
            <small>${escapeHtml(actionRequestSummary(payload))}</small>
          </span>
          <span>
            <strong>${escapeHtml(status.label)}</strong>
            <small>${escapeHtml(draft.createdAt || "--")}</small>
          </span>
        </button>
      `;
    })
    .join("");
}

function openActionRequestModal(index) {
  const draft = state.savedActionDrafts[Number(index)];
  if (!draft) return;
  const result = draft.result || {};
  const payload = result.payload || {};
  openInfoModal({
    kicker: "Tactical Command",
    title: actionRequestKey(draft),
    body: `
      <div class="command-context-bar">
        <div><span>Command</span><strong>${escapeHtml(payload.commandId || "--")}</strong></div>
        <div><span>Aircraft</span><strong>${escapeHtml(payload.aircraftId || "--")}</strong></div>
        <div><span>Reason</span><strong>${escapeHtml(payload.reasonCode || "--")}</strong></div>
        <div><span>Status</span><strong>${escapeHtml(commandResultStatus(result).label)}</strong></div>
      </div>
      <dl class="detail-grid detail-grid--wide">
        <div><dt>Action</dt><dd>${escapeHtml(actionRequestSummary(payload))}</dd></div>
        <div><dt>Created</dt><dd>${escapeHtml(draft.createdAt || "--")}</dd></div>
      </dl>
      ${dispatchDetailMarkup(result)}
      ${(result.validationIssues || []).length ? `<div class="validation-list">${(result.validationIssues || []).map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>` : ""}
      <details class="technical-preview" open>
        <summary>Technical Payload</summary>
        <pre class="payload-preview">${escapeHtml(JSON.stringify(payload, null, 2))}</pre>
      </details>
    `,
    panelClass: "app-modal__panel--command",
  });
}

function formatLla(value) {
  if (!value || typeof value !== "object") return "--";
  return `${formatCoord(value.lat)}, ${formatCoord(value.lon)}, ${escapeHtml(value.alt ?? "--")} m`;
}

function routeRows(plan) {
  const rows = Array.isArray(plan?.enRoute) ? plan.enRoute : [];
  if (!rows.length) {
    return `<tr><td colspan="6">No en-route segments.</td></tr>`;
  }
  return rows
    .map((item) => `
      <tr>
        <td>${escapeHtml(item.seq ?? "--")}</td>
        <td>${escapeHtml(item.phase || "--")}</td>
        <td>${formatLla(item.startLLA)}</td>
        <td>${formatLla(item.endLLA)}</td>
        <td>${escapeHtml(formatSpeed(item.targetSpeed))}</td>
        <td>${escapeHtml(item.turnDirection || "--")}</td>
      </tr>
    `)
    .join("");
}

function planDetailMarkup(plan, { modal = false } = {}) {
  const issues = selectedPlanIssues(plan);
  return `
    <dl class="detail-grid ${modal ? "detail-grid--wide" : ""}">
      <div><dt>Flight Plan</dt><dd>${escapeHtml(plan.flightPlanNumber)}</dd></div>
      <div><dt>Aircraft</dt><dd>${escapeHtml(plan.aircraftId)}</dd></div>
      <div><dt>Version</dt><dd>v${escapeHtml(plan.planVersion)}</dd></div>
      <div><dt>Status</dt><dd>${escapeHtml(plan.planStatus)}</dd></div>
      <div><dt>Departure Vertiport</dt><dd>${escapeHtml(plan.departureVertiport || "--")}</dd></div>
      <div><dt>Departure Gate/FATO</dt><dd>${escapeHtml(plan.departureGate || "--")} / ${escapeHtml(plan.departureFato || "--")}</dd></div>
      <div><dt>STD / EOBT / ETOT</dt><dd>${escapeHtml(formatTime(plan.std))} / ${escapeHtml(formatTime(plan.eobt))} / ${escapeHtml(formatTime(plan.etot))}</dd></div>
      <div><dt>Arrival Vertiport</dt><dd>${escapeHtml(plan.arrivalVertiport || "--")}</dd></div>
      <div><dt>Arrival Gate/FATO</dt><dd>${escapeHtml(plan.arrivalGate || "--")} / ${escapeHtml(plan.arrivalFato || "--")}</dd></div>
      <div><dt>STA / EIBT / ELDT</dt><dd>${escapeHtml(formatTime(plan.sta))} / ${escapeHtml(formatTime(plan.eibt))} / ${escapeHtml(formatTime(plan.eldt))}</dd></div>
      <div><dt>Route Seq</dt><dd>${escapeHtml(plan.routeSeqCount ?? 0)}</dd></div>
      <div><dt>Source</dt><dd>${escapeHtml(plan.source || "--")}</dd></div>
    </dl>
    <div class="route-table-wrap">
      <table class="route-table">
        <thead>
          <tr>
            <th>Seq</th>
            <th>Phase</th>
            <th>Start LLA</th>
            <th>End LLA</th>
            <th>Speed</th>
            <th>Turn</th>
          </tr>
        </thead>
        <tbody>${routeRows(plan)}</tbody>
      </table>
    </div>
    ${issues.length ? `<div class="validation-list">${issues.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>` : ""}
  `;
}

function displaySource(source) {
  const value = String(source || "").trim();
  if (!value) return "Live Feed";
  return value.replace(/ICD[-\s]?4001/gi, "Live Feed").replace(/4001/g, "Live Feed");
}

async function ensureOperationalLayers() {
  if (state.operationalLayers) return state.operationalLayers;
  try {
    state.operationalLayers = await fetchJson("/api/map/layers");
  } catch (_) {
    state.operationalLayers = {};
  }
  return state.operationalLayers;
}

function vertiportChoices() {
  const features = state.operationalLayers?.vertiports?.features || [];
  return features
    .map((feature) => {
      const props = feature?.properties || {};
      const id = String(props.vertiport_id || props.id || props.name || "").trim();
      const name = String(props.name || props.vertiport_name || id || "").trim();
      return id ? [id, name && name !== id ? `${name} (${id})` : id] : null;
    })
    .filter(Boolean);
}

function vertiportFeature(value) {
  const key = String(value || "").trim();
  if (!key) return null;
  const features = state.operationalLayers?.vertiports?.features || [];
  return features.find((feature) => {
    const props = feature?.properties || {};
    return [feature?.id, props.name, props.vertiport_id, props.id]
      .some((item) => String(item || "").trim() === key);
  }) || null;
}

function vertiportCoords(value) {
  const feature = vertiportFeature(value);
  const coordinates = feature?.geometry?.coordinates;
  if (!Array.isArray(coordinates) || coordinates.length < 2) return null;
  return { lat: Number(coordinates[1]), lon: Number(coordinates[0]), alt: selectedVehicle()?.altitude ?? 0 };
}

function formatCoordsText(coords) {
  if (!coords) return "--";
  return `${formatCoord(coords.lat)}, ${formatCoord(coords.lon)}, ${escapeHtml(coords.alt ?? "--")} m`;
}

function routePointPrefix(index) {
  return `routePoint${index}`;
}

function normalizeRoutePoint(point = {}, fallback = {}) {
  return {
    lat: String(point.lat ?? fallback.lat ?? ""),
    lon: String(point.lon ?? fallback.lon ?? ""),
    alt: String(point.alt ?? fallback.alt ?? ""),
    targetSpeed: String(point.targetSpeed ?? point.speed ?? fallback.targetSpeed ?? "20"),
  };
}

function collectRoutePointsFromForm(form = $("[data-action-command-form]")) {
  if (!form) return [];
  return $$("[data-route-point-row]", form).map((row, index) => {
    const prefix = row.dataset.routePointPrefix || routePointPrefix(index);
    const value = (suffix) => String(form.elements.namedItem(`${prefix}${suffix}`)?.value ?? "");
    return {
      lat: value("Lat"),
      lon: value("Lon"),
      alt: value("Alt"),
      targetSpeed: value("Speed"),
    };
  });
}

function routePointsFromDraft(draft = {}, fallback = {}) {
  if (Array.isArray(draft.routePoints) && draft.routePoints.length) {
    return draft.routePoints.map((point) => normalizeRoutePoint(point, fallback));
  }
  const indexes = new Set();
  for (const key of Object.keys(draft || {})) {
    const match = /^routePoint(\d+)(Lat|Lon|Alt|Speed)$/.exec(key);
    if (match) indexes.add(Number(match[1]));
  }
  if (indexes.size) {
    return Array.from(indexes)
      .sort((a, b) => a - b)
      .map((index) => {
        const prefix = routePointPrefix(index);
        return normalizeRoutePoint({
          lat: draft[`${prefix}Lat`],
          lon: draft[`${prefix}Lon`],
          alt: draft[`${prefix}Alt`],
          targetSpeed: draft[`${prefix}Speed`],
        }, fallback);
      });
  }
  if ("targetLat" in draft || "targetLon" in draft || "targetAlt" in draft || "targetSpeed" in draft) {
    return [normalizeRoutePoint({
      lat: draft.targetLat,
      lon: draft.targetLon,
      alt: draft.targetAlt,
      targetSpeed: draft.targetSpeed,
    }, fallback)];
  }
  return [];
}

function routePointOrigin() {
  const vehicle = selectedVehicle();
  const lat = asNumber(vehicle?.latitude);
  const lon = asNumber(vehicle?.longitude);
  if (lat === null || lon === null) return null;
  return { lat, lon };
}

function syncDraftRouteVisualization(points = routePointsFromDraft(state.actionDraftForm || {})) {
  const numericPoints = (points || [])
    .map((point) => ({
      lat: asNumber(point.lat),
      lon: asNumber(point.lon),
      alt: asNumber(point.alt),
      targetSpeed: asNumber(point.targetSpeed),
    }))
    .filter((point) => point.lat !== null && point.lon !== null);
  setDraftRouteOnMap(numericPoints, routePointOrigin());
}

function captureActionDraftForm() {
  const form = $("[data-action-command-form]");
  if (!form) return state.actionDraftForm || {};
  const draft = {};
  for (const [key, value] of new FormData(form).entries()) {
    draft[key] = String(value ?? "");
  }
  const routePoints = collectRoutePointsFromForm(form);
  if (routePoints.length) draft.routePoints = routePoints;
  state.actionDraftForm = draft;
  return draft;
}

function applyActionDraftForm() {
  const draft = state.actionDraftForm || {};
  const form = $("[data-action-command-form]");
  if (!form) return;
  for (const [key, value] of Object.entries(draft)) {
    const field = form.elements.namedItem(key);
    if (field && "value" in field) {
      field.value = value;
    }
  }
}

function setActionDraftFields(values) {
  state.actionDraftForm = { ...(state.actionDraftForm || {}), ...values };
  applyActionDraftForm();
  renderModalActionPreview();
}

function selectedReasonCode() {
  return $("[data-modal-reason-code]")?.value || state.actionDraftForm?.reasonCode || "LOSS_OF_SEPARATION_RISK";
}

function selectedActionType() {
  return $("[data-modal-action-type]")?.value || state.actionDraftForm?.actionType || "directTo";
}

function setLlaFields(prefix, coords) {
  if (!coords) return;
  const values = {
    [`${prefix}Lat`]: Number(coords.lat).toFixed(6),
    [`${prefix}Lon`]: Number(coords.lon).toFixed(6),
    [`${prefix}Alt`]: String(Math.round(Number(coords.alt ?? selectedVehicle()?.altitude ?? 0))),
  };
  const routePointMatch = /^routePoint(\d+)$/.exec(String(prefix || ""));
  if (routePointMatch) {
    const index = Number(routePointMatch[1]);
    const points = routePointsFromDraft(state.actionDraftForm || {}, {
      lat: selectedVehicle()?.latitude ?? "",
      lon: selectedVehicle()?.longitude ?? "",
      alt: selectedVehicle()?.altitude ?? "",
      targetSpeed: "20",
    });
    while (points.length <= index) {
      points.push(normalizeRoutePoint({}, { alt: selectedVehicle()?.altitude ?? "", targetSpeed: "20" }));
    }
    points[index] = {
      ...points[index],
      lat: values[`${prefix}Lat`],
      lon: values[`${prefix}Lon`],
      alt: values[`${prefix}Alt`],
    };
    values.routePoints = points;
  }
  setActionDraftFields(values);
}

function updateMapPickBanner() {
  const banner = $("[data-map-pick-banner]");
  if (!banner) return;
  banner.hidden = !state.mapPick;
  setText("[data-map-pick-label]", state.mapPick?.label || "");
  setText("[data-map-pick-hint]", state.mapPick?.hint || "Click the map to fill command coordinates.");
  const finish = $("[data-map-pick-finish]");
  if (finish) finish.hidden = state.mapPick?.mode !== "route";
}

async function startMapPick(prefix) {
  captureActionDraftForm();
  const routePointMatch = /^routePoint(\d+)$/.exec(String(prefix || ""));
  const labels = {
    target: "Pick route point",
    hold: "Pick holding point",
    land: "Pick landing point",
  };
  state.mapPick = {
    prefix,
    mode: "single",
    label: routePointMatch ? `Pick route point ${Number(routePointMatch[1]) + 1}` : labels[prefix] || "Pick point",
    hint: "Click the map once to fill this coordinate.",
  };
  closeInfoModal();
  setActiveTab("tactical-monitoring");
  await bootMap();
  updateMapPickBanner();
}

async function startRouteDraw() {
  const draft = stripRoutePointDraftFields(captureActionDraftForm());
  const existingPoints = routePointsFromDraft(state.actionDraftForm || {})
    .filter((point) => String(point.lat || "").trim() && String(point.lon || "").trim());
  state.actionDraftForm = { ...draft, actionType: "directTo", routePoints: existingPoints };
  state.mapPick = {
    mode: "route",
    label: "Draw avoidance route",
    hint: "Click the map to add route points in order.",
  };
  setActiveTab("tactical-monitoring");
  await bootMap();
  syncDraftRouteVisualization(existingPoints);
  updateMapPickBanner();
}

function appendRoutePoint(coords) {
  if (!coords) return;
  const points = routePointsFromDraft(state.actionDraftForm || {})
    .filter((point) => String(point.lat || "").trim() || String(point.lon || "").trim());
  points.push(normalizeRoutePoint({
    lat: Number(coords.lat).toFixed(6),
    lon: Number(coords.lon).toFixed(6),
    alt: String(Math.round(Number(coords.alt ?? selectedVehicle()?.altitude ?? 0))),
    targetSpeed: points[points.length - 1]?.targetSpeed || "20",
  }));
  state.actionDraftForm = { ...(state.actionDraftForm || {}), actionType: "directTo", routePoints: points };
  renderModalActionFields();
  applyActionDraftForm();
  renderModalActionPreview();
  syncDraftRouteVisualization(points);
  state.mapPick = {
    ...(state.mapPick || {}),
    mode: "route",
    label: `Draw avoidance route (${points.length} points)`,
    hint: "Click more points, or finish the route.",
  };
  updateMapPickBanner();
}

function stripRoutePointDraftFields(draft = {}) {
  const clean = { ...draft };
  for (const key of Object.keys(clean)) {
    if (/^routePoint\d+(Lat|Lon|Alt|Speed)$/.test(key) || ["targetLat", "targetLon", "targetAlt", "targetSpeed"].includes(key)) {
      delete clean[key];
    }
  }
  return clean;
}

function clearRoutePoints() {
  const draft = stripRoutePointDraftFields(captureActionDraftForm());
  state.actionDraftForm = {
    ...draft,
    actionType: "directTo",
    routePoints: [],
  };
  renderModalActionFields();
  applyActionDraftForm();
  renderModalActionPreview();
  setDraftRouteOnMap([]);
}

function completeMapPick(coords, extraDraft = {}) {
  if (!state.mapPick || !coords) return;
  if (state.mapPick.mode === "route") {
    appendRoutePoint(coords);
    return;
  }
  const prefix = state.mapPick.prefix;
  if (prefix === "land") {
    state.actionDraftForm = {
      ...(state.actionDraftForm || {}),
      landingMode: extraDraft.landingMode || "emergencyPoint",
    };
  }
  state.actionDraftForm = { ...(state.actionDraftForm || {}), ...extraDraft };
  setLlaFields(prefix, coords);
  state.mapPick = null;
  updateMapPickBanner();
  openActionCommandForm(selectedVehicle(), { preserveDraft: true });
}

function cancelMapPick() {
  state.mapPick = null;
  updateMapPickBanner();
}

function finishMapPick() {
  state.mapPick = null;
  updateMapPickBanner();
}

function openInfoModal({ kicker = "Details", title = "Details", body = "", panelClass = "" } = {}) {
  const modal = $("[data-modal]");
  if (!modal) return;
  const panel = $(".app-modal__panel", modal);
  if (panel) {
    panel.classList.remove("app-modal__panel--command", "app-modal__panel--wide");
    if (panelClass) panel.classList.add(panelClass);
  }
  setText("[data-modal-kicker]", kicker);
  setText("[data-modal-title]", title);
  const bodyEl = $("[data-modal-body]");
  if (bodyEl) bodyEl.innerHTML = body;
  modal.hidden = false;
  document.body.classList.add("has-modal");
  $("[data-modal-close]", modal)?.focus?.();
}

function closeInfoModal() {
  const modal = $("[data-modal]");
  if (!modal) return;
  $(".app-modal__panel", modal)?.classList.remove("app-modal__panel--command", "app-modal__panel--wide");
  modal.hidden = true;
  document.body.classList.remove("has-modal");
}

function dispatchInfo(result = {}) {
  return result?.dispatch && typeof result.dispatch === "object" ? result.dispatch : {};
}

function commandResultStatus(result = {}) {
  const issues = result?.validationIssues || [];
  const dispatch = dispatchInfo(result);
  if (issues.length) return { label: "REVIEW", blocked: true, className: "is-blocked" };
  if (dispatch.attempted) {
    const acceptedOnly = dispatch.status === "accepted_by_state_server";
    return dispatch.ok
      ? { label: acceptedOnly ? "ACCEPTED" : "SENT", blocked: false, className: "is-ready" }
      : { label: "NOT SENT", blocked: true, className: "is-blocked" };
  }
  return result?.ok
    ? { label: "READY", blocked: false, className: "is-ready" }
    : { label: "REVIEW", blocked: true, className: "is-blocked" };
}

function commandResultMessage(result = {}) {
  const issues = result?.validationIssues || [];
  const dispatch = dispatchInfo(result);
  if (issues.length) return issues.join(", ");
  if (dispatch.attempted) return dispatch.message || (dispatch.ok ? "Delivered through StateServer." : "Dispatch failed.");
  return "Payload is valid but has not been dispatched.";
}

function dispatchDetailMarkup(result = {}) {
  const dispatch = dispatchInfo(result);
  if (!dispatch.attempted) return "";
  const status = commandResultStatus(result);
  return `
    <div class="draft-status ${status.className}">
      <strong>${escapeHtml(status.label)}</strong>
      <small>${escapeHtml(commandResultMessage(result))}</small>
    </div>
  `;
}

function renderDraftStatus(result, label) {
  const issues = result?.validationIssues || [];
  const dispatch = dispatchInfo(result);
  const status = commandResultStatus(result);
  let title = `${label} ready.`;
  if (issues.length) {
    title = `${label} has validation issues.`;
  } else if (dispatch.attempted && dispatch.ok) {
    title = `${label} sent.`;
  } else if (dispatch.attempted) {
    title = `${label} not sent.`;
  }
  return `
    <div class="draft-status ${status.className}">
      <strong>${escapeHtml(title)}</strong>
      <small>${escapeHtml(commandResultMessage(result))}</small>
    </div>
  `;
}

function openPlanModal(plan) {
  if (!plan) return;
  openInfoModal({
    kicker: "Flight Plan",
    title: `${plan.flightPlanNumber || "--"} / ${plan.aircraftId || "--"}`,
    body: `
      ${planDraftNoticeMarkup(plan)}
      ${planDetailMarkup(plan, { modal: true })}
      <div class="modal-actions">
        <button class="chip command-button command-button--modify" type="button" data-open-plan-modification>Modify Flight Plan</button>
      </div>
    `,
  });
}

function planModificationSummaryMarkup(plan) {
  return `
    <div class="plan-current-grid">
      <div><span>Flight Plan</span><strong>${escapeHtml(plan.flightPlanNumber || "--")}</strong></div>
      <div><span>Aircraft</span><strong>${escapeHtml(plan.aircraftId || "--")}</strong></div>
      <div><span>Version</span><strong>v${escapeHtml(plan.planVersion || "--")}</strong></div>
      <div><span>Status</span><strong>${escapeHtml(plan.planStatus || "--")}</strong></div>
      <div><span>Departure</span><strong>${escapeHtml(plan.departureVertiport || "--")}</strong><small>${escapeHtml(plan.departureGate || "--")} / ${escapeHtml(plan.departureFato || "--")}</small></div>
      <div><span>ETOT / STD</span><strong>${escapeHtml(formatTime(plan.etot))} / ${escapeHtml(formatTime(plan.std))}</strong></div>
      <div><span>Arrival</span><strong>${escapeHtml(plan.arrivalVertiport || "--")}</strong><small>${escapeHtml(plan.arrivalGate || "--")} / ${escapeHtml(plan.arrivalFato || "--")}</small></div>
      <div><span>ELDT / STA</span><strong>${escapeHtml(formatTime(plan.eldt))} / ${escapeHtml(formatTime(plan.sta))}</strong></div>
    </div>
  `;
}

function currentPlanModificationPayload(form = $("[data-plan-modification-form]"), plan = selectedPlan()) {
  if (!form) return {};
  const data = new FormData(form);
  const flightPlanNumber = plan?.flightPlanNumber ?? asNumber(data.get("flightPlanNumber"));
  const aircraftId = plan?.aircraftId ?? String(data.get("aircraftId") || "");
  return {
    timestamp: String(data.get("timestamp") || state.planModificationTimestamp || new Date().toISOString()),
    commandId: String(data.get("commandId") || state.planModificationCommandId || nextStrategicCommandId()),
    flightPlanNumber,
    aircraftId,
    planVersion: asNumber(data.get("planVersion"), Number(plan?.planVersion || data.get("currentPlanVersion") || 1) + 1),
    modificationType: String(data.get("modificationType") || "routeUpdate"),
    reasonCode: String(data.get("reasonCode") || "VERTIPORT_CAPACITY"),
    modifyScope: String(data.get("modifyScope") || "enRouteOnly"),
  };
}

function planFromModificationForm(form) {
  if (!form) return null;
  const data = new FormData(form);
  const flightPlanNumber = asNumber(data.get("flightPlanNumber"));
  const aircraftId = String(data.get("aircraftId") || "").trim();
  const planVersion = asNumber(data.get("currentPlanVersion"), 1);
  if (!flightPlanNumber || !aircraftId) return null;
  return { flightPlanNumber, aircraftId, planVersion };
}

function renderPlanModificationPreview(result = null) {
  const preview = $("[data-plan-draft-preview]");
  if (!preview) return;
  preview.textContent = JSON.stringify(result?.payload || currentPlanModificationPayload(), null, 2);
}

function planModificationWorkspaceMarkup(plan, commandId, timestamp) {
  const nextVersion = Number(plan.planVersion || 1) + 1;
  return `
    <form class="plan-modification-workspace modal-command-form" data-plan-modification-form>
      <input name="timestamp" type="hidden" value="${escapeHtml(timestamp)}" />
      <input name="commandId" type="hidden" value="${escapeHtml(commandId)}" />
      <input name="flightPlanNumber" type="hidden" value="${escapeHtml(plan.flightPlanNumber || "")}" />
      <input name="aircraftId" type="hidden" value="${escapeHtml(plan.aircraftId || "")}" />
      <input name="currentPlanVersion" type="hidden" value="${escapeHtml(plan.planVersion || 1)}" />
      <section class="plan-mod-column plan-mod-column--current">
        <div class="command-panel-head">
          <span>${bilingualLabel("Current 3001", "현재 비행계획")}</span>
          <strong>${escapeHtml(plan.flightPlanNumber || "--")} / ${escapeHtml(plan.aircraftId || "--")}</strong>
        </div>
        ${planModificationSummaryMarkup(plan)}
      </section>
      <section class="plan-mod-column plan-mod-column--request">
        <div class="option-group">
          <span>${bilingualLabel("Modification Type", "수정 유형")}</span>
          <div class="option-card-grid" data-plan-option-cards="modificationType">
            ${planOptionCardMarkup("modificationType", STRATEGIC_MODIFICATION_TYPES, "routeUpdate", STRATEGIC_MODIFICATION_KO)}
          </div>
        </div>
        <div class="option-group">
          <span>${bilingualLabel("Reason Code", "사유 코드")}</span>
          <div class="option-card-grid" data-plan-option-cards="reasonCode">
            ${planOptionCardMarkup("reasonCode", STRATEGIC_REASONS, "VERTIPORT_CAPACITY", STRATEGIC_REASON_KO)}
          </div>
        </div>
        <div class="option-group">
          <span>${bilingualLabel("Modify Scope", "수정 범위")}</span>
          <div class="option-card-grid" data-plan-option-cards="modifyScope">
            ${planOptionCardMarkup("modifyScope", STRATEGIC_SCOPES, "enRouteOnly", STRATEGIC_SCOPE_KO)}
          </div>
        </div>
        <label class="visually-hidden-field">
          <span>Modification Type</span>
          <select name="modificationType" tabindex="-1">${optionMarkup(STRATEGIC_MODIFICATION_TYPES, "routeUpdate")}</select>
        </label>
        <label class="visually-hidden-field">
          <span>Reason Code</span>
          <select name="reasonCode" tabindex="-1">${optionMarkup(STRATEGIC_REASONS, "VERTIPORT_CAPACITY")}</select>
        </label>
        <label class="visually-hidden-field">
          <span>Modify Scope</span>
          <select name="modifyScope" tabindex="-1">${optionMarkup(STRATEGIC_SCOPES, "enRouteOnly")}</select>
        </label>
      </section>
      <section class="plan-mod-column plan-mod-column--draft">
        <div class="command-panel-head">
          <span>${bilingualLabel("3002 Request", "수정요청")}</span>
          <strong>${escapeHtml(commandId)}</strong>
        </div>
        <div class="plan-command-meta">
          <div>
            <span>${bilingualLabel("Command ID", "명령 식별자")}</span>
            <strong>${escapeHtml(commandId)}</strong>
          </div>
          <div>
            <span>${bilingualLabel("Created UTC", "생성 시각")}</span>
            <strong>${escapeHtml(timestamp)}</strong>
          </div>
        </div>
        <label>
          <span>${bilingualLabel("Target Version", "대상 버전")}</span>
          <input name="planVersion" type="number" min="1" step="1" value="${escapeHtml(nextVersion)}" />
        </label>
        <div data-plan-draft-status></div>
        <details class="technical-preview command-technical-preview" open>
          <summary>Technical Payload</summary>
          <pre class="payload-preview" data-plan-draft-preview>{}</pre>
        </details>
        <div class="command-footer">
          <div></div>
          <div>
            <button class="chip" type="button" data-back-plan-detail>Back to Details</button>
            <button class="chip command-button command-button--save" type="submit" data-stage-plan-request>Send Request</button>
          </div>
        </div>
      </section>
    </form>
  `;
}

function openPlanModificationForm(plan = selectedPlan()) {
  if (!plan) return;
  state.planModificationCommandId = nextStrategicCommandId();
  state.planModificationTimestamp = new Date().toISOString();
  openInfoModal({
    kicker: "Plan Modification",
    title: `${plan.flightPlanNumber || "--"} Modification Request`,
    body: planModificationWorkspaceMarkup(plan, state.planModificationCommandId, state.planModificationTimestamp),
    panelClass: "app-modal__panel--command",
  });
  renderPlanModificationPreview();
}

async function savePlanModification(event) {
  event.preventDefault();
  await savePlanModificationForm(event.currentTarget);
}

async function savePlanModificationForm(form) {
  const plan = selectedPlan() || planFromModificationForm(form);
  const status = $("[data-plan-draft-status]");
  if (!form || !plan) {
    if (status) {
      status.innerHTML = `
        <div class="draft-status is-blocked">
          <strong>Cannot send request.</strong>
          <small>Flight plan context is missing. Close this modal and reopen the flight plan details.</small>
        </div>
      `;
    }
    return;
  }
  const payload = currentPlanModificationPayload(form, plan);
  const preview = $("[data-plan-draft-preview]");
  const submitButton = $("[data-stage-plan-request]", form);
  if (status) {
    status.innerHTML = `
      <div class="draft-status">
        <strong>Sending request...</strong>
        <small>Submitting MSG 3002 to StateServer for VehicleModule dispatch.</small>
      </div>
    `;
  }
  if (submitButton) submitButton.disabled = true;
  try {
    const result = await postJson("/api/strategic/modification/dispatch", payload);
    state.savedPlanDrafts.unshift({ createdAt: new Date().toISOString(), result });
    persistSavedPlanDrafts();
    if (preview) preview.textContent = JSON.stringify(result?.payload || result, null, 2);
    if (status) status.innerHTML = renderDraftStatus(result, "Plan modification request");
    renderStrategic();
    if (result?.ok) {
      openPlanDraftModal(0);
    }
  } catch (error) {
    if (status) status.innerHTML = `<div class="draft-status is-blocked"><strong>Failed to send request.</strong><small>${escapeHtml(error.message || error)}</small></div>`;
  } finally {
    if (submitButton) submitButton.disabled = false;
  }
}

function renderPlanSummary(summary = {}) {
  const container = $("[data-plan-summary]");
  if (!container) return;
  const items = [
    ["Pending", summary.pending ?? 0],
    ["Active", summary.active ?? 0],
    ["Need Review", summary.need_review ?? 0],
    ["Modification", (summary.modification ?? 0) + state.savedPlanDrafts.length],
  ];
  container.innerHTML = items
    .map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`)
    .join("");
}

function renderPlanGroups() {
  const container = $("[data-plan-groups]");
  if (!container) return;
  const groups = state.strategic?.groups?.[state.planGroup] || [];
  if (!groups.length) {
    container.innerHTML = `<span class="empty-pill">No received flight plan data</span>`;
    return;
  }
  container.innerHTML = groups
    .slice(0, 12)
    .map((item) => `<span><strong>${escapeHtml(item.key)}</strong>${escapeHtml(item.count)}</span>`)
    .join("");
}

function validationBadge(plan) {
  if (latestPlanDraft(plan)) return `<span class="status-badge status-badge--CAUTION">Request</span>`;
  const issues = plan.validationIssues || [];
  if (!issues.length) return `<span class="status-badge status-badge--NORMAL">OK</span>`;
  return `<span class="status-badge status-badge--CAUTION">Review ${issues.length}</span>`;
}

function renderPlanTable() {
  const tbody = $("[data-plan-table]");
  if (!tbody) return;
  const plans = state.strategic?.plans || [];
  setText("[data-plan-count]", `${plans.length} Plans`);
  if (!plans.length) {
    tbody.innerHTML = `
      <tr>
        <td colspan="10">
          <div class="empty-state">
            <strong>No scheduled flights received.</strong>
            <small>Only received flight plan data from the StateServer is displayed.</small>
          </div>
        </td>
      </tr>
    `;
    return;
  }
  tbody.innerHTML = plans
    .map((plan) => {
      const selected = String(plan.key) === String(state.selectedPlanKey);
      return `
        <tr class="${selected ? "is-selected" : ""}" data-plan-key="${escapeHtml(plan.key)}" tabindex="0">
          <td>${escapeHtml(plan.flightPlanNumber)}</td>
          <td>v${escapeHtml(plan.planVersion)}</td>
          <td>${escapeHtml(plan.aircraftId)}</td>
          <td>${escapeHtml(plan.planStatus)}</td>
          <td>${escapeHtml(plan.departureVertiport || "--")}</td>
          <td>${escapeHtml(formatTime(plan.etot || plan.std))}</td>
          <td>${escapeHtml(plan.arrivalVertiport || "--")}</td>
          <td>${escapeHtml(formatTime(plan.eldt || plan.sta))}</td>
          <td>${escapeHtml(plan.routeSeqCount ?? 0)}</td>
          <td>${validationBadge(plan)}</td>
        </tr>
      `;
    })
    .join("");
}

function renderPlanDetail() {
  const container = $("[data-plan-detail]");
  const plan = selectedPlan();
  setText("[data-selected-plan-label]", plan ? `${plan.flightPlanNumber} / ${plan.aircraftId}` : "--");
  if (!container) return;
  if (!plan) {
    container.innerHTML = "<p>Select a flight plan to inspect details.</p>";
    return;
  }
  container.innerHTML = `${planDraftNoticeMarkup(plan)}${planDetailMarkup(plan)}`;
}

function renderStrategic() {
  renderPlanSummary(state.strategic?.summary || {});
  renderPlanGroups();
  renderPlanTable();
  renderPlanDetail();
  renderModificationQueue();
}

async function refreshStrategic() {
  try {
    state.strategic = await fetchJson("/api/strategic/plans");
    const plans = state.strategic.plans || [];
    if (!plans.some((plan) => String(plan.key) === String(state.selectedPlanKey))) {
      state.selectedPlanKey = plans[0]?.key || null;
    }
    renderStrategic();
  } catch (error) {
    const tbody = $("[data-plan-table]");
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="10">Failed to load flight plans: ${escapeHtml(error.message || error)}</td></tr>`;
    }
  }
}

function vehicleId(vehicle) {
  return String(vehicle.aircraft_id || vehicle.aircraftId || vehicle.vehicle_id || vehicle.id || "");
}

function selectedVehicle() {
  const vehicles = state.tactical?.vehicles || [];
  return vehicles.find((vehicle) => vehicleId(vehicle) === state.selectedAircraftId) || null;
}

function vehicleDetailMarkup(vehicle, { modal = false } = {}) {
  return `
    <dl class="detail-grid ${modal ? "detail-grid--wide" : ""}">
      <div><dt>Aircraft</dt><dd>${escapeHtml(vehicleId(vehicle))}</dd></div>
      <div><dt>Flight Plan</dt><dd>${escapeHtml(vehicle.flight_plan_id || vehicle.flightPlanNumber || "--")}</dd></div>
      <div><dt>Position</dt><dd>${formatCoord(vehicle.latitude)}, ${formatCoord(vehicle.longitude)}</dd></div>
      <div><dt>Altitude</dt><dd>${escapeHtml(vehicle.altitude ?? "--")} m</dd></div>
      <div><dt>Speed</dt><dd>${escapeHtml(formatSpeed(vehicle.ground_speed_mps || vehicle.speed_mps))}</dd></div>
      <div><dt>Heading</dt><dd>${escapeHtml(vehicle.heading_deg ?? vehicle.heading ?? "--")}</dd></div>
      <div><dt>Waypoint</dt><dd>${escapeHtml(vehicle.currentWaypointId || vehicle.current_waypoint_id || "--")}</dd></div>
      <div><dt>Age</dt><dd>${escapeHtml(vehicle.age_s ?? "--")} s</dd></div>
      <div><dt>Source</dt><dd>${escapeHtml(displaySource(vehicle.source))}</dd></div>
      <div><dt>Status</dt><dd>${vehicle.stale ? "STALE" : "LIVE"}</dd></div>
    </dl>
  `;
}

function vehicleCommandContextMarkup(vehicle) {
  return `
    <div class="command-context-bar">
      <div>
        <span>Aircraft</span>
        <strong>${escapeHtml(vehicleId(vehicle))}</strong>
      </div>
      <div>
        <span>Flight Plan</span>
        <strong>${escapeHtml(vehicle.flight_plan_id || vehicle.flightPlanNumber || "--")}</strong>
      </div>
      <div>
        <span>Position</span>
        <strong>${formatCoord(vehicle.latitude)}, ${formatCoord(vehicle.longitude)}</strong>
      </div>
      <div>
        <span>Status</span>
        <strong>${vehicle.stale ? "STALE" : "LIVE"}</strong>
      </div>
    </div>
  `;
}

function openAircraftModal(vehicle) {
  if (!vehicle) return;
  state.aircraftPanelOpen = true;
  state.aircraftPanelMode = "status";
  renderSelectedAircraftPanel();
}

function hydrateActionCommandPanel() {
  renderModalActionFields();
  applyActionDraftForm();
  renderActionQuickSelectors();
  renderModalActionPreview();
}

function renderSelectedAircraftPanel({ force = false } = {}) {
  const panel = $("[data-selected-aircraft-panel]");
  const title = $("[data-selected-aircraft-panel-title]");
  const body = $("[data-selected-aircraft-panel-body]");
  const vehicle = selectedVehicle();
  if (!panel || !body) return;
  const visible = Boolean(state.aircraftPanelOpen && vehicle);
  panel.hidden = !visible;
  if (!visible) return;
  const commandMode = state.aircraftPanelMode === "command";
  panel.classList.toggle("is-command-mode", commandMode);
  body.classList.toggle("selected-aircraft-panel__body--command", commandMode);
  if (title) title.textContent = commandMode ? `${vehicleId(vehicle)} Tactical Command` : vehicleId(vehicle);
  const currentMode = body.dataset.panelMode || "";
  const currentAircraftId = body.dataset.panelAircraftId || "";
  const aircraftId = vehicleId(vehicle);
  if (commandMode && !force && currentMode === "command" && currentAircraftId === aircraftId && $("[data-action-command-form]", body)) {
    renderModalActionPreview();
    return;
  }
  body.dataset.panelMode = commandMode ? "command" : "status";
  body.dataset.panelAircraftId = aircraftId;
  if (commandMode) {
    body.innerHTML = actionCommandFormMarkup(vehicle);
    hydrateActionCommandPanel();
    return;
  }
  body.innerHTML = `
      ${vehicleDetailMarkup(vehicle)}
      <div class="selected-aircraft-panel__actions">
        <button class="chip command-button command-button--traffic" type="button" data-open-action-command>Traffic Management Action</button>
        <button class="chip" type="button" data-toggle-tactical-panel="aircraft">Aircraft List</button>
      </div>
    `;
}

function actionOptionsForReason(reason) {
  const allowed = TACTICAL_REASON_ACTIONS[reason] || Object.keys(ACTION_LABELS);
  return allowed.map((type) => [type, ACTION_LABELS[type] || type]);
}

function actionCommandFormMarkup(vehicle) {
  const draft = state.actionDraftForm || {};
  const reason = draft.reasonCode || "LOSS_OF_SEPARATION_RISK";
  const actionType = draft.actionType || actionOptionsForReason(reason)[0]?.[0] || "directTo";
  const commandId = state.actionCommandId || nextTacticalCommandId();
  const timestamp = state.actionCommandTimestamp || new Date().toISOString();
  return `
    ${vehicleCommandContextMarkup(vehicle)}
    <form class="command-form command-workspace modal-command-form" data-action-command-form>
      <input name="timestamp" type="hidden" value="${escapeHtml(timestamp)}" />
      <input name="commandId" type="hidden" value="${escapeHtml(commandId)}" />
      <input name="aircraftId" type="hidden" value="${escapeHtml(vehicleId(vehicle))}" />
      <section class="command-workspace__choices">
        <div class="option-group">
          <span>${bilingualLabel("Reason Code", "사유 코드")}</span>
          <div class="option-card-grid option-card-grid--reasons" data-modal-reason-cards>
            ${buttonCardMarkup(Object.entries(TACTICAL_REASON_LABELS), reason, "data-modal-reason-pick", TACTICAL_REASON_KO)}
          </div>
        </div>
        <div class="option-group">
          <span>${bilingualLabel("Action", "조치")}</span>
          <div class="option-card-grid" data-modal-action-cards>
            ${buttonCardMarkup(actionOptionsForReason(reason), actionType, "data-modal-action-pick", ACTION_KO)}
          </div>
        </div>
      </section>
      <label class="visually-hidden-field">
        <span>Reason Code</span>
        <select name="reasonCode" data-modal-reason-code tabindex="-1">
          ${optionMarkup(Object.entries(TACTICAL_REASON_LABELS), reason)}
        </select>
      </label>
      <label class="visually-hidden-field">
        <span>Action Type</span>
        <select name="actionType" data-modal-action-type tabindex="-1">
          ${optionMarkup(actionOptionsForReason(reason), actionType)}
        </select>
      </label>
      <section class="command-workspace__details">
        <div class="command-panel-head">
          <span>${bilingualLabel("Command Parameters", "명령 파라미터")}</span>
          <strong data-command-action-title>${escapeHtml(ACTION_LABELS[actionType] || actionType)}</strong>
        </div>
        <p class="form-hint" data-modal-action-guidance>${escapeHtml(TACTICAL_REASON_HINTS[reason])}</p>
        <div class="action-fields" data-modal-action-fields></div>
        <div class="action-stack" data-modal-action-stack></div>
        <div data-action-draft-status></div>
      </section>
      <div class="command-footer">
        <div>
          <button class="chip command-button command-button--traffic" type="button" data-modal-add-action>Queue Action</button>
          <button class="chip command-button command-button--danger" type="button" data-modal-clear-actions>Clear Queue</button>
        </div>
        <div>
          <button class="chip" type="button" data-back-aircraft-detail>Back to Status</button>
          <button class="chip command-button command-button--save" type="submit" data-stage-action-command>Send Command</button>
        </div>
      </div>
    </form>
    <details class="technical-preview command-technical-preview">
      <summary>Technical Payload</summary>
      <pre class="payload-preview" data-action-draft-preview>{}</pre>
    </details>
  `;
}

function openActionCommandForm(vehicle = selectedVehicle(), { preserveDraft = false } = {}) {
  vehicle = vehicle || selectedVehicle() || state.tactical?.vehicles?.[0] || null;
  if (!vehicle) return;
  const id = vehicleId(vehicle);
  if (id) state.selectedAircraftId = id;
  if (!preserveDraft) {
    state.modalActions = [];
    state.actionDraftForm = null;
    state.actionCommandId = nextTacticalCommandId();
    state.actionCommandTimestamp = new Date().toISOString();
  } else {
    state.actionCommandId = state.actionCommandId || nextTacticalCommandId();
    state.actionCommandTimestamp = state.actionCommandTimestamp || new Date().toISOString();
  }
  state.aircraftPanelOpen = true;
  state.aircraftPanelMode = "command";
  renderSelectedAircraftPanel({ force: true });
  ensureOperationalLayers()
    .then(() => {
      if (state.aircraftPanelOpen && state.aircraftPanelMode === "command" && selectedVehicle()) {
        state.actionDraftForm = captureActionDraftForm();
        renderSelectedAircraftPanel({ force: true });
      }
    })
    .catch((error) => console.error("Failed to refresh operational layers", error));
}

function syncModalActionOptions({ preserveCurrent = true } = {}) {
  const reasonSelect = $("[data-modal-reason-code]");
  const actionSelect = $("[data-modal-action-type]");
  const reason = reasonSelect?.value || "LOSS_OF_SEPARATION_RISK";
  const options = actionOptionsForReason(reason);
  if (actionSelect) {
    const current = actionSelect.value;
    actionSelect.innerHTML = optionMarkup(options, preserveCurrent ? current : options[0]?.[0]);
    if (preserveCurrent && options.some(([type]) => type === current)) {
      actionSelect.value = current;
    } else if (options[0]) {
      actionSelect.value = options[0][0];
    }
  }
  setText("[data-modal-action-guidance]", TACTICAL_REASON_HINTS[reason] || "Select an action for the selected aircraft.");
}

function renderActionQuickSelectors() {
  const reason = selectedReasonCode();
  const action = selectedActionType();
  const reasonCards = $("[data-modal-reason-cards]");
  const actionCards = $("[data-modal-action-cards]");
  if (reasonCards) {
    reasonCards.innerHTML = buttonCardMarkup(Object.entries(TACTICAL_REASON_LABELS), reason, "data-modal-reason-pick", TACTICAL_REASON_KO);
  }
  if (actionCards) {
    actionCards.innerHTML = buttonCardMarkup(actionOptionsForReason(reason), action, "data-modal-action-pick", ACTION_KO);
  }
  const reasonSelect = $("[data-modal-reason-code]");
  const actionSelect = $("[data-modal-action-type]");
  if (reasonSelect) reasonSelect.value = reason;
  if (actionSelect) actionSelect.value = action;
}

function renderModalActionFields() {
  syncModalActionOptions();
  const type = $("[data-modal-action-type]")?.value || "directTo";
  setText("[data-command-action-title]", ACTION_LABELS[type] || type);
  const draft = state.actionDraftForm || {};
  const vehicle = selectedVehicle();
  const lat = vehicle?.latitude ?? "";
  const lon = vehicle?.longitude ?? "";
  const alt = vehicle?.altitude ?? "";
  const container = $("[data-modal-action-fields]");
  if (!container) return;
  const llaFields = (prefix, defaultAlt = alt, title = "Target", pickLabel = "Pick on Map") => `
    <div class="lla-tools form-wide">
      <strong>${escapeHtml(title)}</strong>
      <button class="chip command-button command-button--map" type="button" data-map-pick="${escapeHtml(prefix)}">${escapeHtml(pickLabel)}</button>
    </div>
    <label><span>${title} Lat</span><input name="${prefix}Lat" type="number" step="0.000001" value="${escapeHtml(lat)}" /></label>
    <label><span>${title} Lon</span><input name="${prefix}Lon" type="number" step="0.000001" value="${escapeHtml(lon)}" /></label>
    <label><span>${title} Alt</span><input name="${prefix}Alt" type="number" step="1" value="${escapeHtml(defaultAlt)}" /></label>
  `;
  const routePointMarkup = (points) => `
    <div class="route-point-list form-wide" data-route-point-list>
      <div class="lla-tools route-point-toolbar">
        <strong>Route Points <small>targetLLAs</small></strong>
        <button class="chip command-button command-button--map" type="button" data-start-route-draw>Draw Route</button>
        <button class="chip command-button command-button--danger" type="button" data-clear-route-points>Clear</button>
      </div>
      ${points.length ? `
        <div class="route-point-table">
          <div class="route-point-table__head">
            <span>#</span>
            <span>Lat</span>
            <span>Lon</span>
            <span>Alt</span>
            <span>Speed</span>
            <span></span>
          </div>
          ${points.map((point, index) => {
        const prefix = routePointPrefix(index);
        return `
          <div class="route-point-row" data-route-point-row data-route-point-prefix="${escapeHtml(prefix)}">
            <strong>${escapeHtml(index + 1)}</strong>
            <input aria-label="Point ${escapeHtml(index + 1)} latitude" name="${prefix}Lat" type="number" step="0.000001" value="${escapeHtml(point.lat)}" />
            <input aria-label="Point ${escapeHtml(index + 1)} longitude" name="${prefix}Lon" type="number" step="0.000001" value="${escapeHtml(point.lon)}" />
            <input aria-label="Point ${escapeHtml(index + 1)} altitude" name="${prefix}Alt" type="number" step="1" value="${escapeHtml(point.alt)}" />
            <input aria-label="Point ${escapeHtml(index + 1)} target speed" name="${prefix}Speed" type="number" min="0" max="200" step="0.1" value="${escapeHtml(point.targetSpeed)}" />
            <button class="chip command-button command-button--danger route-point-remove" type="button" data-remove-route-point="${escapeHtml(index)}" ${points.length <= 1 ? "disabled" : ""}>Remove</button>
          </div>
        `;
      }).join("")}
        </div>
      ` : `
        <div class="route-point-empty">
          <strong>No route points selected.</strong>
          <span>Use Draw Route and click the map in flight order.</span>
        </div>
      `}
    </div>
  `;
  if (type === "setSpeed") {
    container.innerHTML = `<label><span>Target Speed m/s</span><input name="targetSpeed" type="number" min="0" max="200" step="0.1" value="20" /></label>`;
  } else if (type === "directTo") {
    let routePoints = routePointsFromDraft(draft, { lat: "", lon: "", alt, targetSpeed: draft.targetSpeed || "20" });
    const hasDrawnPoints = routePoints.some((point) => String(point.lat || "").trim() && String(point.lon || "").trim());
    if (hasDrawnPoints) {
      routePoints = routePoints.filter((point) => String(point.lat || "").trim() && String(point.lon || "").trim());
    }
    container.innerHTML = `
      <label class="form-wide"><span>Route Objective</span><input name="routeObjective" type="text" placeholder="Avoid conflict, blocked corridor, or weather cell" /></label>
      ${routePointMarkup(routePoints)}
    `;
  } else if (type === "hold") {
    container.innerHTML = `
      ${llaFields("hold", alt, "Hold Point", "Pick Hold Point")}
      <label><span>Turn</span><select name="turnDirection"><option value="CW">CW</option><option value="CCW">CCW</option></select></label>
      <label><span>Radius m</span><input name="holdingRadiusM" type="number" min="1" max="5000" step="1" value="120" /></label>
      <label><span>Max Count</span><input name="maxHoldingCount" type="number" min="0" max="9999" step="1" value="1" /></label>
    `;
  } else if (type === "rejoinPlan") {
    container.innerHTML = `<label><span>Route Sequence</span><input name="atSeq" type="number" min="1" max="9999" step="1" value="1" /></label>`;
  } else {
    const choices = vertiportChoices();
    const landingMode = draft.landingMode || "alternateVertiport";
    const selectedVertiport = draft.vertiport || choices[0]?.[0] || "";
    const selectedVertiportCoords = vertiportCoords(selectedVertiport);
    container.innerHTML = `
      <label>
        <span>${bilingualLabel("Landing Target", "착륙 대상")}</span>
        <select name="landingMode" data-landing-mode>
          <option value="alternateVertiport" ${landingMode === "alternateVertiport" ? "selected" : ""}>Alternate vertiport · 대체 버티포트</option>
          <option value="emergencyPoint" ${landingMode === "emergencyPoint" ? "selected" : ""}>Emergency landing point · 비상 착륙 지점</option>
        </select>
      </label>
      ${
        landingMode === "alternateVertiport"
          ? `
            <label>
              <span>${bilingualLabel("Alternate Vertiport", "대체 버티포트")}</span>
              <select name="vertiport" data-vertiport-select>
                <option value="">${choices.length ? "Select vertiport" : "No connected vertiports"}</option>
                ${optionMarkup(choices, selectedVertiport)}
              </select>
            </label>
            <label><span>${bilingualLabel("FATO", "착륙 FATO")}</span><select name="fatoNumber">${optionMarkup(FATO_OPTIONS, draft.fatoNumber || "FATO-1")}</select></label>
            <div class="readonly-coordinate form-wide">
              <span>Vertiport LLA <small>버티포트 좌표</small></span>
              <strong>${formatCoordsText(selectedVertiportCoords)}</strong>
            </div>
          `
          : llaFields("land", "", "Emergency Landing Point", "Pick Emergency Point")
      }
    `;
  }
  applyActionDraftForm();
}

function modalActionFromForm() {
  const form = $("[data-action-command-form]");
  if (!form) return null;
  const data = new FormData(form);
  const type = String(data.get("actionType") || "directTo");
  if (type === "setSpeed") {
    return { type, targetSpeed: asNumber(data.get("targetSpeed"), 0) };
  }
  if (type === "directTo") {
    const routePoints = collectRoutePointsFromForm(form);
    const targetLLAs = (routePoints.length ? routePoints : routePointsFromDraft(state.actionDraftForm || {}))
      .map((point) => ({
        lat: asNumber(point.lat),
        lon: asNumber(point.lon),
        alt: asNumber(point.alt),
        targetSpeed: asNumber(point.targetSpeed),
      }))
      .filter((point) => [point.lat, point.lon, point.alt, point.targetSpeed].every((value) => value !== null));
    return {
      type,
      routeObjective: String(data.get("routeObjective") || "").trim(),
      targetLLAs,
    };
  }
  if (type === "hold") {
    return {
      type,
      holdLLA: {
        lat: asNumber(data.get("holdLat"), 0),
        lon: asNumber(data.get("holdLon"), 0),
        alt: asNumber(data.get("holdAlt"), 0),
      },
      turnDirection: String(data.get("turnDirection") || "CW"),
      holdingRadiusM: asNumber(data.get("holdingRadiusM"), 120),
      maxHoldingCount: asNumber(data.get("maxHoldingCount"), 1),
    };
  }
  if (type === "rejoinPlan") {
    return { type, atSeq: asNumber(data.get("atSeq"), 1) };
  }
  const action = {
    type,
    landingMode: String(data.get("landingMode") || "alternateVertiport"),
  };
  if (action.landingMode === "emergencyPoint") {
    const lat = asNumber(data.get("landLat"));
    const lon = asNumber(data.get("landLon"));
    const alt = asNumber(data.get("landAlt"));
    if (lat !== null && lon !== null && alt !== null) {
      action.targetLLA = { lat, lon, alt };
    }
  } else {
    action.vertiport = String(data.get("vertiport") || "").trim();
    action.fatoNumber = String(data.get("fatoNumber") || "").trim();
  }
  return action;
}

function vehicleFromActionForm(form) {
  if (!form) return null;
  const data = new FormData(form);
  const aircraftId = String(data.get("aircraftId") || "").trim();
  return aircraftId ? { aircraft_id: aircraftId } : null;
}

function currentActionCommandPayload(form = $("[data-action-command-form]")) {
  const data = form ? new FormData(form) : new FormData();
  const currentAction = modalActionFromForm();
  const actions = state.modalActions.length ? state.modalActions : currentAction ? [currentAction] : [];
  return {
    timestamp: String(data.get("timestamp") || state.actionCommandTimestamp || new Date().toISOString()),
    commandId: String(data.get("commandId") || state.actionCommandId || nextTacticalCommandId()),
    aircraftId: String(data.get("aircraftId") || state.selectedAircraftId || ""),
    reasonCode: data.get("reasonCode") || "LOSS_OF_SEPARATION_RISK",
    actions,
  };
}

function renderModalActionStack() {
  const container = $("[data-modal-action-stack]");
  if (!container) return;
  if (!state.modalActions.length) {
    container.innerHTML = `<span class="empty-pill">Current form selection will be saved as one action.</span>`;
    return;
  }
  container.innerHTML = state.modalActions
    .map((action, index) => `
      <span class="action-pill">
        ${escapeHtml(index + 1)}. ${escapeHtml(ACTION_LABELS[action.type] || action.type)}
        <button type="button" data-modal-remove-action="${index}" aria-label="Remove action">x</button>
      </span>
    `)
    .join("");
}

function renderModalActionPreview(result = null) {
  renderModalActionStack();
  const preview = $("[data-action-draft-preview]");
  if (preview) preview.textContent = JSON.stringify(result || currentActionCommandPayload(), null, 2);
  if (selectedActionType() === "directTo") {
    syncDraftRouteVisualization(collectRoutePointsFromForm());
  } else {
    setDraftRouteOnMap([]);
  }
}

function vehicleBatteryPct(vehicle = {}) {
  const energy = vehicle.energy && typeof vehicle.energy === "object" ? vehicle.energy : {};
  return asNumber(
    vehicle.batteryPct ??
      vehicle.battery_pct ??
      vehicle.batteryRemainingPct ??
      energy.batteryRemainingPct ??
      energy.batteryPct ??
      energy.battery_pct ??
      energy.state_of_charge_pct,
  );
}

function vehicleCollisionActive(vehicle = {}) {
  const collision = vehicle.collision && typeof vehicle.collision === "object" ? vehicle.collision : {};
  return Boolean(vehicle.collisionActive || collision.active || collision.hasCollision);
}

function tacticalEvents() {
  const events = [];
  for (const vehicle of state.tactical?.vehicles || []) {
    const id = vehicleId(vehicle);
    const battery = vehicleBatteryPct(vehicle);
    if (vehicle.stale) {
      events.push({
        severity: "CAUTION",
        title: "Track stale",
        aircraftId: id,
        detail: `Last update age ${vehicle.age_s ?? "--"} s`,
      });
    }
    if (battery !== null && battery <= 20) {
      events.push({
        severity: "WARNING",
        title: "Low battery",
        aircraftId: id,
        detail: `${battery.toFixed(1)}% remaining`,
      });
    }
    if (vehicleCollisionActive(vehicle)) {
      events.push({
        severity: "WARNING",
        title: "Collision event",
        aircraftId: id,
        detail: "Collision flag is active in live status.",
      });
    }
  }
  return events;
}

function renderTacticalEvents() {
  const container = $("[data-tactical-event-list]");
  const events = tacticalEvents();
  for (const countEl of $$('[data-tactical-count="events"]')) {
    countEl.textContent = String(events.length);
  }
  if (!container) return;
  if (!events.length) {
    container.innerHTML = `
      <div class="empty-state">
        <strong>No tactical events detected.</strong>
        <small>This panel is reserved for live event sources. Current temporary detection uses stale, low-battery, and collision flags from 4001.</small>
      </div>
    `;
    return;
  }
  container.innerHTML = events
    .map((event) => `
      <button class="tactical-event ${event.severity === "WARNING" ? "is-warning" : ""}" type="button" data-aircraft-id="${escapeHtml(event.aircraftId)}">
        <span>
          <strong>${escapeHtml(event.title)}</strong>
          <small>${escapeHtml(event.aircraftId)}</small>
        </span>
        <span>
          <strong>${escapeHtml(event.severity)}</strong>
          <small>${escapeHtml(event.detail)}</small>
        </span>
      </button>
    `)
    .join("");
}

function warningSeverityBadge(severity) {
  const value = String(severity || "").toLowerCase();
  if (value === "critical" || value === "fatal") return "WARNING";
  if (value === "warning") return "CAUTION";
  return "NORMAL";
}

function renderWarningEvents() {
  const container = $("[data-warning-event-list]");
  const events = state.warnings?.events || [];
  for (const countEl of $$('[data-tactical-count="warnings"]')) {
    countEl.textContent = String(events.length);
  }
  if (!container) return;
  if (!events.length) {
    container.innerHTML = `
      <div class="empty-state">
        <strong>No vehicle warning events received.</strong>
        <small>MSG 4002 warnings stored by the StateServer will appear here.</small>
      </div>
    `;
    return;
  }
  container.innerHTML = events
    .map((event) => {
      const battery = asNumber(event.battery_pct);
      return `
      <div class="warning-event ${event.isCritical ? "is-critical" : ""}">
        <span>
          <strong>${escapeHtml(event.vehicleId)}</strong>
          <small>${escapeHtml(event.eventType || "--")} / ${escapeHtml(formatTime(event.timestamp))}</small>
        </span>
        <span>
          <span class="status-badge status-badge--${warningSeverityBadge(event.severity)}">${escapeHtml(String(event.severity || "").toUpperCase())}</span>
          <small>${battery !== null ? `${escapeHtml(battery.toFixed(1))}% battery` : "battery --"}</small>
        </span>
        <button class="chip command-button command-button--danger" type="button" data-warning-draft-event="${escapeHtml(event.eventId)}">비상 착륙 draft</button>
      </div>
    `;
    })
    .join("");
}

async function refreshWarnings() {
  try {
    state.warnings = await fetchJson("/api/psu/warning-events");
    renderWarningEvents();
  } catch (error) {
    const container = $("[data-warning-event-list]");
    if (container) {
      container.innerHTML = `<div class="empty-state"><strong>Failed to load warning events</strong><small>${escapeHtml(error.message || error)}</small></div>`;
    }
  }
}

async function prefillLandDraftFromWarning(eventId, button = null) {
  if (button) button.disabled = true;
  try {
    const draft = await postJson("/api/psu/warning-events/draft-3003", { eventId });
    const payload = draft?.payload || {};
    const aircraftId = String(payload.aircraftId || "");
    if (!aircraftId) return;
    const vehicle = (state.tactical?.vehicles || []).find((item) => vehicleId(item) === aircraftId) || { aircraft_id: aircraftId };
    state.modalActions = [];
    state.actionDraftForm = {
      reasonCode: payload.reasonCode || "LOW_BATTERY",
      actionType: "land",
      landingMode: "alternateVertiport",
    };
    state.actionCommandId = String(payload.commandId || "") || nextTacticalCommandId();
    state.actionCommandTimestamp = String(payload.timestamp || "") || new Date().toISOString();
    openActionCommandForm(vehicle, { preserveDraft: true });
  } catch (error) {
    console.error("Failed to prefill 3003 land draft from 4002 warning", error);
  } finally {
    if (button) button.disabled = false;
  }
}

async function saveActionCommand(event) {
  event.preventDefault();
  await saveActionCommandForm(event.currentTarget);
}

async function saveActionCommandForm(form) {
  const vehicle = selectedVehicle() || vehicleFromActionForm(form);
  const status = $("[data-action-draft-status]");
  if (!form || !vehicle) {
    if (status) {
      status.innerHTML = `
        <div class="draft-status is-blocked">
          <strong>Cannot send command.</strong>
          <small>Aircraft context is missing. Close this modal and reopen the aircraft status.</small>
        </div>
      `;
    }
    return;
  }
  if (!state.modalActions.length) {
    const action = modalActionFromForm();
    if (action) state.modalActions.push(action);
  }
  const submitButton = $("[data-stage-action-command]", form);
  if (status) {
    status.innerHTML = `
      <div class="draft-status">
        <strong>Sending command...</strong>
        <small>Submitting MSG 3003 to StateServer for VehicleModule dispatch.</small>
      </div>
    `;
  }
  if (submitButton) submitButton.disabled = true;
  try {
    const result = await postJson("/api/tactical/command/dispatch", currentActionCommandPayload(form));
    state.savedActionDrafts.unshift({ createdAt: new Date().toISOString(), result });
    persistSavedActionDrafts();
    renderModalActionPreview(result?.payload || result);
    if (status) status.innerHTML = renderDraftStatus(result, "Traffic management command");
    renderActionRequestQueue();
    if (result?.ok) {
      setTacticalPanelOpen("actions", true);
    }
  } catch (error) {
    if (status) status.innerHTML = `<div class="draft-status is-blocked"><strong>Failed to send command.</strong><small>${escapeHtml(error.message || error)}</small></div>`;
  } finally {
    if (submitButton) submitButton.disabled = false;
  }
}

function renderVehicleSummary(summary = {}) {
  const container = $("[data-vehicle-summary]");
  if (!container) return;
  const items = [
    ["Live", summary.live ?? 0],
    ["Stale", summary.stale ?? 0],
    ["Low Battery", summary.low_battery ?? 0],
    ["Collision", summary.collision ?? 0],
  ];
  container.innerHTML = items
    .map(([label, value]) => `<span><strong>${escapeHtml(value)}</strong> ${escapeHtml(label)}</span>`)
    .join("");
}

function renderVehicleList() {
  const container = $("[data-vehicle-list]");
  const vehicles = state.tactical?.vehicles || [];
  setText("[data-vehicle-count]", `${vehicles.length} Vehicles`);
  for (const countEl of $$('[data-tactical-count="aircraft"]')) {
    countEl.textContent = String(vehicles.length);
  }
  if (!container) return;
  if (!vehicles.length) {
    const link = state.tactical?.data_link || {};
    container.innerHTML = `
      <div class="empty-state">
        <strong>No live aircraft status is available.</strong>
        <small>${escapeHtml(link.message_en || link.message || "Waiting for OperationModule or StateServer live track data.")}</small>
      </div>
    `;
    return;
  }
  container.innerHTML = vehicles
    .map((vehicle) => {
      const id = vehicleId(vehicle);
      const selected = id === state.selectedAircraftId;
      return `
        <button class="vehicle-row ${selected ? "is-selected" : ""}" type="button" data-aircraft-id="${escapeHtml(id)}">
          <span>
            <strong>${escapeHtml(id)}</strong>
            <small>${escapeHtml(vehicle.currentWaypointId || vehicle.current_waypoint_id || "no waypoint")}</small>
          </span>
          <span>
            <strong>${escapeHtml(formatSpeed(vehicle.ground_speed_mps || vehicle.speed_mps))}</strong>
            <small>${vehicle.stale ? "STALE" : "LIVE"} / ${escapeHtml(displaySource(vehicle.source))}</small>
          </span>
        </button>
      `;
    })
    .join("");
}

function renderTactical() {
  renderVehicleSummary(state.tactical?.summary || {});
  renderVehicleList();
  renderTacticalEvents();
  renderActionRequestQueue();
  renderSelectedAircraftPanel();
  updateTacticalDrawers();
}

function updateTacticalDrawers() {
  for (const drawer of $$("[data-tactical-drawer]")) {
    const hasOpenPanel = Boolean($(".tactical-fold:not(.is-collapsed)", drawer));
    drawer.classList.toggle("is-empty", !hasOpenPanel);
    drawer.setAttribute("aria-hidden", hasOpenPanel ? "false" : "true");
  }
}

function setTacticalPanelOpen(name, open) {
  const section = $(`[data-tactical-fold="${name}"]`);
  if (!section) return;
  section.classList.toggle("is-collapsed", !open);
  section.classList.toggle("is-open", open);
  for (const button of $$(`[data-toggle-tactical-panel="${name}"]`)) {
    button.classList.toggle("is-active", open);
    button.setAttribute("aria-expanded", open ? "true" : "false");
  }
  updateTacticalDrawers();
  window.setTimeout(() => window.__PSU_MAP__?.resize?.(), 90);
}

function toggleTacticalPanel(name) {
  const section = $(`[data-tactical-fold="${name}"]`);
  if (!section) return;
  const willOpen = section.classList.contains("is-collapsed");
  setTacticalPanelOpen(name, willOpen);
}

async function refreshTactical() {
  try {
    state.tactical = await fetchJson("/api/tactical/vehicles");
    const vehicles = state.tactical.vehicles || [];
    if (!vehicles.some((vehicle) => vehicleId(vehicle) === state.selectedAircraftId)) {
      state.selectedAircraftId = vehicleId(vehicles[0] || {}) || null;
    }
    renderTactical();
  } catch (error) {
    const container = $("[data-vehicle-list]");
    if (container) {
      container.innerHTML = `<div class="empty-state"><strong>Failed to load live aircraft status</strong><small>${escapeHtml(error.message || error)}</small></div>`;
    }
  }
}

function replayFrames() {
  return state.replay?.frames || [];
}

function findReplayFrame(step) {
  return replayFrames().find((frame) => Number(frame.step) === Number(step)) || null;
}

function replayProgressPct() {
  const frames = replayFrames();
  if (!frames.length) return 0;
  const index = frames.findIndex((frame) => Number(frame.step) === Number(state.selectedReplayStep));
  if (frames.length === 1) return 100;
  return Math.max(0, Math.min(100, (index / (frames.length - 1)) * 100));
}

function removedReplayNotice() {
  return (state.replay?.removed_demo || state.report?.removed_demo || state.validation?.removed_demo || [])[0] || null;
}

function demoRemovedBox(notice, fallback) {
  const message = notice?.message || fallback || "The previous static demo content was removed.";
  const replacement = notice?.replacement || "This view waits for real execution logs or analysis output.";
  return `
    <div class="demo-removed-box">
      <strong>${escapeHtml(message)}</strong>
      <small>${escapeHtml(replacement)}</small>
    </div>
  `;
}

function renderReplaySummary() {
  const summary = state.replay?.summary || {};
  const playback = state.replay?.playback || {};
  const completion = state.validation?.completion || {};
  setText("[data-replay-summary='frame_count']", playback.frame_count ?? replayFrames().length ?? 0);
  setText("[data-replay-summary='candidate_count']", summary.decision_candidates ?? 0);
  setText("[data-replay-summary='report_id']", summary.report_id || "REMOVED");
  setText("[data-replay-summary='validation']", completion.percentage != null ? `${completion.percentage}%` : "REMOVED");
  const progress = $("[data-replay-progress]");
  if (progress) progress.style.width = `${replayProgressPct().toFixed(0)}%`;
}

function renderReplayTimeline() {
  const container = $("[data-replay-timeline]");
  const frames = replayFrames();
  setText("[data-replay-count]", `${frames.length} Frames`);
  if (!container) return;
  if (!frames.length) {
    container.innerHTML = demoRemovedBox(removedReplayNotice(), "The previous replay timeline demo was removed.");
    return;
  }
  container.innerHTML = frames
    .map((frame) => `
      <button type="button" class="replay-step ${Number(frame.step) === Number(state.selectedReplayStep) ? "is-selected" : ""}" data-replay-step="${escapeHtml(frame.step)}">
        <span class="replay-step__index">${escapeHtml(frame.step)}</span>
        <span class="status-badge status-badge--${escapeHtml(frame.severity || "NORMAL")}">${escapeHtml(frame.severity || "NORMAL")}</span>
        <strong>${escapeHtml(frame.time_label || formatTime(frame.timestamp))} / ${escapeHtml(frame.title || "Replay frame")}</strong>
        <small>${escapeHtml(frame.screen || "--")} / ${escapeHtml(frame.operator_focus || "--")}</small>
      </button>
    `)
    .join("");
}

function renderReplayDetail() {
  const container = $("[data-replay-detail]");
  const frame = findReplayFrame(state.selectedReplayStep);
  setText("[data-replay-selected]", frame ? `Step ${frame.step}` : "--");
  if (!container) return;
  if (!frame) {
    container.innerHTML = demoRemovedBox(removedReplayNotice(), "The previous current-frame demo was removed.");
    return;
  }
  container.innerHTML = `
    <div class="replay-frame-head">
      <span class="status-badge status-badge--${escapeHtml(frame.severity || "NORMAL")}">${escapeHtml(frame.severity || "NORMAL")}</span>
      <strong>${escapeHtml(frame.title || "Replay frame")}</strong>
      <small>${escapeHtml(formatTime(frame.timestamp))} / ${escapeHtml(frame.screen || "--")} / ${escapeHtml(frame.operator_focus || "--")}</small>
    </div>
    <p>${escapeHtml(frame.description || "")}</p>
  `;
}

function renderReportExport() {
  const container = $("[data-report-export]");
  setText("[data-report-export-status]", state.report?.report_id || "REMOVED");
  if (!container) return;
  container.innerHTML = `
    <div class="report-export-head">
      <strong>${escapeHtml(state.report?.title || "PSU Scenario Result Report")}</strong>
      <small>${escapeHtml(state.report?.report_id || "removed-demo-data")}</small>
    </div>
    <div class="report-links">
      <a href="/api/reports/scenario-result" target="_blank" rel="noreferrer">JSON</a>
      <a href="/api/reports/scenario-result.md" target="_blank" rel="noreferrer">Markdown</a>
      <a href="/api/reports/scenario-result.html" target="_blank" rel="noreferrer">HTML</a>
    </div>
    ${state.report?.removed ? demoRemovedBox(removedReplayNotice(), "The previous report export demo was removed.") : ""}
  `;
}

function renderValidationBoard() {
  const container = $("[data-validation-board]");
  const completion = state.validation?.completion || {};
  const checks = state.validation?.checks || [];
  setText("[data-validation-count]", `${completion.passed ?? 0}/${completion.total ?? 0} PASS`);
  if (!container) return;
  if (!checks.length) {
    container.innerHTML = demoRemovedBox(removedReplayNotice(), "The previous final validation demo was removed.");
    return;
  }
  container.innerHTML = checks
    .map((section) => `
      <section>
        <h5>${escapeHtml(section.section || "Validation")}</h5>
        <ul>
          ${(section.items || []).map((item) => `<li>${escapeHtml(item.name || "")} / ${escapeHtml(item.status || "")}</li>`).join("")}
        </ul>
      </section>
    `)
    .join("");
}

function renderReplayReport() {
  renderReplaySummary();
  renderReplayTimeline();
  renderReplayDetail();
  renderReportExport();
  renderValidationBoard();
}

async function refreshReplay() {
  try {
    const [replay, validation, report] = await Promise.all([
      fetchJson("/api/replay"),
      fetchJson("/api/final-validation"),
      fetchJson("/api/reports/scenario-result"),
    ]);
    state.replay = replay;
    state.validation = validation;
    state.report = report;
    if (!findReplayFrame(state.selectedReplayStep)) {
      state.selectedReplayStep = replayFrames()[0]?.step || 1;
    }
    renderReplayReport();
  } catch (error) {
    setText("[data-replay-count]", "API error");
    const container = $("[data-replay-timeline]");
    if (container) container.innerHTML = `<p>Failed to load post-operation review data: ${escapeHtml(error.message || error)}</p>`;
  }
}

function stopReplay() {
  if (state.replayTimer) {
    window.clearInterval(state.replayTimer);
    state.replayTimer = null;
  }
}

function selectReplayStep(step) {
  const frames = replayFrames();
  if (!frames.length) return;
  const first = Number(frames[0].step);
  const last = Number(frames[frames.length - 1].step);
  state.selectedReplayStep = Math.max(first, Math.min(last, Number(step)));
  renderReplayReport();
}

function handleReplayControl(control) {
  const frames = replayFrames();
  if (!frames.length) return;
  const currentIndex = frames.findIndex((frame) => Number(frame.step) === Number(state.selectedReplayStep));
  if (control === "play") {
    stopReplay();
    state.replayTimer = window.setInterval(() => {
      const index = frames.findIndex((frame) => Number(frame.step) === Number(state.selectedReplayStep));
      if (index >= frames.length - 1) {
        stopReplay();
        return;
      }
      selectReplayStep(frames[index + 1].step);
    }, state.replayIntervalMs);
    return;
  }
  stopReplay();
  if (control === "pause") return;
  if (control === "reset") {
    state.selectedReplayStep = frames[0].step;
  } else if (control === "next") {
    state.selectedReplayStep = (frames[Math.min(frames.length - 1, currentIndex + 1)] || frames[0]).step;
  } else if (control === "prev") {
    state.selectedReplayStep = (frames[Math.max(0, currentIndex - 1)] || frames[0]).step;
  }
  renderReplayReport();
}

async function bootMap() {
  if (state.mapReady) {
    window.__PSU_MAP__?.resize?.();
    return;
  }
  const statusEl = $("[data-map-status]");
  try {
    const map = await initPsuMap({ statusEl });
    state.mapReady = Boolean(map);
    window.setTimeout(() => window.__PSU_MAP__?.resize?.(), 160);
  } catch (error) {
    if (statusEl) statusEl.textContent = error instanceof Error ? error.message : String(error);
  }
}

function bindEvents() {
  for (const tab of $$("[data-tab]")) {
    tab.addEventListener("click", () => setActiveTab(tab.dataset.tab || "strategic-plans"));
  }
  window.addEventListener("hashchange", () => setActiveTab(tabIdFromHash(), false));

  $("[data-theme-toggle]")?.addEventListener("click", () => {
    applyTheme(normalizedTheme(document.documentElement.dataset.theme) === "light" ? "dark" : "light", { persist: true });
  });

  $("[data-refresh-strategic]")?.addEventListener("click", refreshStrategic);
  $("[data-refresh-tactical]")?.addEventListener("click", refreshTactical);

  for (const button of $$("[data-plan-group]")) {
    button.addEventListener("click", () => {
      state.planGroup = button.dataset.planGroup || "byDestination";
      for (const item of $$("[data-plan-group]")) item.classList.toggle("is-active", item === button);
      renderPlanGroups();
    });
  }

  document.addEventListener("click", (event) => {
    if (event.target.closest("[data-modal-close]")) {
      closeInfoModal();
      return;
    }
    const planRow = event.target.closest("[data-plan-key]");
    if (planRow) {
      state.selectedPlanKey = planRow.dataset.planKey;
      renderStrategic();
      openPlanModal(selectedPlan());
      return;
    }
    if (event.target.closest("[data-open-plan-modification]")) {
      openPlanModificationForm();
      return;
    }
    if (event.target.closest("[data-back-plan-detail]")) {
      openPlanModal(selectedPlan());
      return;
    }
    const stagePlanButton = event.target.closest("[data-stage-plan-request]");
    if (stagePlanButton) {
      event.preventDefault();
      const form = stagePlanButton.closest("[data-plan-modification-form]");
      if (form) savePlanModificationForm(form);
      return;
    }
    const tacticalPanelToggle = event.target.closest("[data-toggle-tactical-panel]");
    if (tacticalPanelToggle) {
      toggleTacticalPanel(tacticalPanelToggle.dataset.toggleTacticalPanel || "");
      return;
    }
    const planOption = event.target.closest("[data-plan-option-value]");
    if (planOption) {
      const name = planOption.dataset.planOptionName || "";
      const value = planOption.dataset.planOptionValue || "";
      const form = planOption.closest("[data-plan-modification-form]");
      const field = form?.elements?.namedItem(name);
      if (field && "value" in field) field.value = value;
      for (const card of $$(`[data-plan-option-name="${name}"]`, form || document)) {
        card.classList.toggle("is-selected", card === planOption);
      }
      renderPlanModificationPreview();
      return;
    }
    const planDraftItem = event.target.closest("[data-plan-draft-index]");
    if (planDraftItem) {
      openPlanDraftModal(planDraftItem.dataset.planDraftIndex);
      return;
    }
    const actionRequestItem = event.target.closest("[data-action-request-index]");
    if (actionRequestItem) {
      openActionRequestModal(actionRequestItem.dataset.actionRequestIndex);
      return;
    }
    if (event.target.closest("[data-open-action-command]")) {
      openActionCommandForm();
      return;
    }
    const warningDraftButton = event.target.closest("[data-warning-draft-event]");
    if (warningDraftButton) {
      prefillLandDraftFromWarning(warningDraftButton.getAttribute("data-warning-draft-event") || "", warningDraftButton);
      return;
    }
    const vehicleRow = event.target.closest(".vehicle-row[data-aircraft-id], .tactical-event[data-aircraft-id]");
    if (vehicleRow) {
      state.selectedAircraftId = vehicleRow.dataset.aircraftId;
      state.aircraftPanelOpen = true;
      state.aircraftPanelMode = "status";
      renderTactical();
      selectAircraftOnMap(state.selectedAircraftId, { fly: false });
      return;
    }
    if (event.target.closest("[data-back-aircraft-detail]")) {
      finishMapPick();
      setDraftRouteOnMap([]);
      state.aircraftPanelOpen = true;
      state.aircraftPanelMode = "status";
      renderSelectedAircraftPanel();
      return;
    }
    if (event.target.closest("[data-close-aircraft-panel]")) {
      finishMapPick();
      setDraftRouteOnMap([]);
      state.aircraftPanelOpen = false;
      state.aircraftPanelMode = "status";
      renderSelectedAircraftPanel();
      return;
    }
    const reasonCard = event.target.closest("[data-modal-reason-pick]");
    if (reasonCard) {
      const reason = reasonCard.dataset.modalReasonPick || "LOSS_OF_SEPARATION_RISK";
      const firstAction = actionOptionsForReason(reason)[0]?.[0] || "directTo";
      state.actionDraftForm = { ...captureActionDraftForm(), reasonCode: reason, actionType: firstAction };
      const reasonSelect = $("[data-modal-reason-code]");
      const actionSelect = $("[data-modal-action-type]");
      if (reasonSelect) reasonSelect.value = reason;
      if (actionSelect) actionSelect.value = firstAction;
      syncModalActionOptions({ preserveCurrent: false });
      renderModalActionFields();
      applyActionDraftForm();
      renderActionQuickSelectors();
      renderModalActionPreview();
      return;
    }
    const actionCard = event.target.closest("[data-modal-action-pick]");
    if (actionCard) {
      const actionType = actionCard.dataset.modalActionPick || "directTo";
      state.actionDraftForm = { ...captureActionDraftForm(), actionType };
      const actionSelect = $("[data-modal-action-type]");
      if (actionSelect) actionSelect.value = actionType;
      renderModalActionFields();
      applyActionDraftForm();
      renderActionQuickSelectors();
      renderModalActionPreview();
      return;
    }
    if (event.target.closest("[data-start-route-draw]")) {
      startRouteDraw();
      return;
    }
    if (event.target.closest("[data-clear-route-points]")) {
      clearRoutePoints();
      return;
    }
    const removeRoutePoint = event.target.closest("[data-remove-route-point]");
    if (removeRoutePoint) {
      state.actionDraftForm = captureActionDraftForm();
      const removeIndex = Number(removeRoutePoint.dataset.removeRoutePoint);
      const points = routePointsFromDraft(state.actionDraftForm);
      if (points.length > 1 && Number.isInteger(removeIndex)) {
        points.splice(removeIndex, 1);
        state.actionDraftForm = { ...state.actionDraftForm, routePoints: points };
        renderModalActionFields();
        applyActionDraftForm();
        renderModalActionPreview();
      }
      return;
    }
    const mapPickButton = event.target.closest("[data-map-pick]");
    if (mapPickButton) {
      startMapPick(mapPickButton.dataset.mapPick || "target");
      return;
    }
    if (event.target.closest("[data-map-pick-cancel]")) {
      cancelMapPick();
      return;
    }
    if (event.target.closest("[data-map-pick-finish]")) {
      finishMapPick();
      return;
    }
    const modalRemoveAction = event.target.closest("[data-modal-remove-action]");
    if (modalRemoveAction) {
      state.modalActions.splice(Number(modalRemoveAction.dataset.modalRemoveAction), 1);
      renderModalActionPreview();
      return;
    }
    if (event.target.closest("[data-modal-add-action]")) {
      const action = modalActionFromForm();
      if (action) state.modalActions.push(action);
      renderModalActionPreview();
      return;
    }
    if (event.target.closest("[data-modal-clear-actions]")) {
      state.modalActions = [];
      renderModalActionPreview();
      return;
    }
    const stageActionButton = event.target.closest("[data-stage-action-command]");
    if (stageActionButton) {
      event.preventDefault();
      const form = stageActionButton.closest("[data-action-command-form]");
      if (form) saveActionCommandForm(form);
      return;
    }
    const replayStep = event.target.closest("[data-replay-step]");
    if (replayStep) {
      stopReplay();
      selectReplayStep(replayStep.dataset.replayStep);
      return;
    }
    const replayControl = event.target.closest("[data-replay-control]");
    if (replayControl) {
      handleReplayControl(replayControl.dataset.replayControl);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      if (state.mapPick) {
        cancelMapPick();
        return;
      }
      closeInfoModal();
      return;
    }
    if (event.key !== "Enter" && event.key !== " ") return;
    const item = event.target.closest("[data-plan-key], [data-aircraft-id], [data-replay-step], [data-replay-control]");
    if (!item) return;
    event.preventDefault();
    item.click();
  });

  document.addEventListener("change", (event) => {
    const landingModeSelect = event.target.closest("[data-landing-mode]");
    if (landingModeSelect) {
      state.actionDraftForm = {
        ...captureActionDraftForm(),
        landingMode: landingModeSelect.value || "alternateVertiport",
      };
      renderModalActionFields();
      renderModalActionPreview();
      return;
    }
    const vertiportSelect = event.target.closest("[data-vertiport-select]");
    if (vertiportSelect) {
      state.actionDraftForm = {
        ...captureActionDraftForm(),
        landingMode: "alternateVertiport",
        vertiport: vertiportSelect.value,
      };
      renderModalActionFields();
      renderModalActionPreview();
      return;
    }
    if (event.target.closest("[data-modal-reason-code]")) {
      state.actionDraftForm = captureActionDraftForm();
      syncModalActionOptions({ preserveCurrent: false });
      renderModalActionFields();
      renderActionQuickSelectors();
      renderModalActionPreview();
      return;
    }
    if (event.target.closest("[data-modal-action-type]")) {
      state.actionDraftForm = captureActionDraftForm();
      renderModalActionFields();
      renderActionQuickSelectors();
      renderModalActionPreview();
    }
  });

  document.addEventListener("input", (event) => {
    if (event.target.closest("[data-plan-modification-form]")) {
      renderPlanModificationPreview();
      return;
    }
    if (event.target.closest("[data-action-command-form]")) {
      state.actionDraftForm = captureActionDraftForm();
      renderModalActionPreview();
    }
  });

  document.addEventListener("submit", (event) => {
    if (event.target.matches("[data-plan-modification-form]")) {
      savePlanModification(event);
      return;
    }
    if (event.target.matches("[data-action-command-form]")) {
      saveActionCommand(event);
    }
  });

  $("[data-replay-speed]")?.addEventListener("change", (event) => {
    state.replayIntervalMs = Number(event.target.value || 1600);
    if (state.replayTimer) {
      handleReplayControl("play");
    }
  });

  window.addEventListener("psu:aircraft-selected", (event) => {
    if (state.mapPick) return;
    const aircraftId = event.detail?.aircraftId;
    if (!aircraftId) return;
    state.selectedAircraftId = String(aircraftId);
    state.aircraftPanelOpen = true;
    state.aircraftPanelMode = "status";
    renderTactical();
  });

  window.addEventListener("psu:map-click", (event) => {
    if (!state.mapPick) return;
    const lat = Number(event.detail?.lat);
    const lon = Number(event.detail?.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
    completeMapPick({ lat, lon, alt: selectedVehicle()?.altitude ?? 0 });
  });

  window.addEventListener("psu:vertiport-selected", (event) => {
    if (!state.mapPick || state.mapPick.prefix !== "land") return;
    const vertiport = String(event.detail?.vertiportId || event.detail?.name || "").trim();
    const coords = vertiportCoords(vertiport);
    if (!coords) return;
    completeMapPick(coords, {
      landingMode: "alternateVertiport",
      vertiport,
    });
  });
}

initTheme();
loadSavedPlanDrafts();
loadSavedActionDrafts();
bindEvents();
setActiveTab(tabIdFromHash(), false);
refreshStatus();
refreshStrategic();
refreshTactical();
refreshWarnings();
refreshReplay();

window.setInterval(refreshStatus, 10_000);
window.setInterval(refreshStrategic, 10_000);
window.setInterval(refreshTactical, 3_000);
window.setInterval(refreshWarnings, 3_000);
