// Detail panel renderer for module summaries, metrics, and suggested actions.
function renderMetric(metric) {
  return `
    <article class="metric-card">
      <p class="metric-card__label">${metric.label}</p>
      <p class="metric-card__value">${metric.value}</p>
      <p class="metric-card__hint">${metric.hint}</p>
    </article>
  `;
}

function renderAction(action) {
  return `
    <div class="action-item" data-action-id="${action.id}">
      <strong>${action.label}</strong>
      <p>${action.description}</p>
    </div>
  `;
}

export function renderLoading(container, moduleTitle = "workspace") {
  container.innerHTML = `
    <div class="detail-loading">
      <p class="eyebrow">Loading</p>
      <h3 id="detail-modal-title">Opening ${moduleTitle}</h3>
      <p>Collecting module state from the backend.</p>
    </div>
  `;
}

export function renderError(container, message) {
  container.innerHTML = `
    <div class="detail-error">
      <p class="eyebrow">Module Error</p>
      <h3 id="detail-modal-title">Could not load workspace</h3>
      <p>${message}</p>
    </div>
  `;
}

export function renderOverview(container, overview) {
  container.innerHTML = `
    <section class="detail-main">
      <p class="eyebrow">${overview.slug}</p>
      <h3 id="detail-modal-title">${overview.headline}</h3>
      <div class="detail-status">${overview.status}</div>
      <p class="detail-summary">${overview.summary}</p>
      <div class="metric-grid">
        ${overview.metrics.map(renderMetric).join("")}
      </div>
    </section>
    <aside class="detail-sidebar">
      <p class="eyebrow">Suggested folders</p>
      <h4>Recommended feature split</h4>
      <div class="action-list">
        ${overview.actions.map(renderAction).join("")}
      </div>
    </aside>
  `;
}

const MODULE_MANAGEMENT_COPY = {
  en: {
    eyebrow: "CONNECTED MODULES",
    title: "DTAM Module Management",
    summary: "Monitor DTAM module link status and prepare module lifecycle commands.",
    start: "Start Module",
    stop: "Stop Module",
    ready: "Module commands are ready for connection logic.",
    rx: "RX",
    tx: "TX",
    heartbeat: "HEARTBEAT",
    connected: "connected",
    waiting: "waiting",
  },
  ko: {
    eyebrow: "CONNECTED MODULES",
    title: "DTAM 모듈 관리",
    summary: "DTAM 모듈 연결 상태를 확인하고 모듈 실행/종료 명령을 준비합니다.",
    start: "모듈 실행",
    stop: "모듈 종료",
    ready: "연결 로직 연결 대기 중입니다.",
    rx: "RX",
    tx: "TX",
    heartbeat: "HEARTBEAT",
    connected: "connected",
    waiting: "waiting",
  },
};

import { getJSON, postJSON } from "../api/client.js";

function moduleCopy(language = "en") {
  return MODULE_MANAGEMENT_COPY[language === "ko" ? "ko" : "en"];
}

function formatHeartbeat(ts) {
  if (!ts || ts <= 0) return "-";
  const sec = Math.max(0, Date.now() / 1000 - ts);
  if (sec < 1) return "now";
  if (sec < 60) return `${sec.toFixed(1)}s`;
  return `${Math.floor(sec / 60)}m`;
}

function renderModuleCard(module, copy) {
  const status = module.connected ? "connected" : "waiting";
  const accent = {
    mission: "purple",
    vehicle: "green",
    monitoring: "cyan",
    visual: "amber",
    sim_state: "blue",
  }[module.role] || "gray";

  const mids = Object.keys(module.messages || {}).sort().slice(0, 3).join(", ");

  return `
    <article class="dtam-module-card dtam-module-card--${accent} ${module.connected ? "is-connected" : ""}">
      <header class="dtam-module-card__header">
        <div>
          <strong>${module.display_name || module.role}</strong>
          <span>${module.role.toUpperCase()}</span>
        </div>
        <span class="dtam-module-status dtam-module-status--${status}">
          <i aria-hidden="true"></i>
          ${copy[status]}
        </span>
      </header>
      <p class="dtam-module-endpoint">${module.expected_source || "—"} <span>(${module.last_source || "no source yet"})</span></p>
      <div class="dtam-module-metrics">
        <div>
          <span>${copy.rx}</span>
          <strong>${module.rx_count || 0}</strong>
        </div>
        <div>
          <span>${copy.tx}</span>
          <strong>${module.tx_count || 0}</strong>
        </div>
        <div>
          <span>${copy.heartbeat}</span>
          <strong>${formatHeartbeat(module.last_heartbeat_ts)}</strong>
        </div>
      </div>
      <span class="dtam-module-tag">${mids || "idle"}</span>
    </article>
  `;
}

export async function renderModuleManagement(container, language = "en") {
  const copy = moduleCopy(language);
  
  container.classList.remove("detail-panel--icd");
  container.classList.add("detail-panel--module-management");
  
  // 초기 껍데기 렌더링
  container.innerHTML = `
    <section class="dtam-module-management">
      <header class="dtam-module-management__header">
        <div>
          <p class="eyebrow">${copy.eyebrow}</p>
          <h3 id="detail-modal-title">${copy.title}</h3>
          <p>${copy.summary}</p>
        </div>
        <div class="dtam-module-actions">
          <button type="button" class="dtam-module-action dtam-module-action--start" data-module-command="start">
            <span aria-hidden="true"></span>
            ${copy.start}
          </button>
          <button type="button" class="dtam-module-action dtam-module-action--stop" data-module-command="stop">
            <span aria-hidden="true"></span>
            ${copy.stop}
          </button>
        </div>
      </header>
      <div class="dtam-module-count" data-module-count-wrapper>
        <strong>${copy.eyebrow}</strong>
        <span data-module-count-text>- / -</span>
      </div>
      <div class="dtam-module-grid" data-module-grid-wrapper>
        <div class="detail-loading">Loading status...</div>
      </div>
      <div class="dtam-module-command-status" data-module-command-status>${copy.ready}</div>
    </section>
  `;

  const gridWrapper = container.querySelector("[data-module-grid-wrapper]");
  const countText = container.querySelector("[data-module-count-text]");
  const statusEl = container.querySelector("[data-module-command-status]");

  async function refresh() {
    try {
      const data = await getJSON("/api/v1/system/modules");
      const modules = data.modules || [];
      const connectedCount = modules.filter((m) => m.connected).length;
      
      countText.textContent = `${connectedCount} / ${modules.length}`;
      gridWrapper.innerHTML = modules.map((m) => renderModuleCard(m, copy)).join("");
    } catch (error) {
      gridWrapper.innerHTML = `<div class="detail-error">${error.message}</div>`;
    }
  }

  // 주기적 갱신
  const timer = setInterval(() => {
    if (!document.body.contains(container)) {
      clearInterval(timer);
      return;
    }
    refresh();
  }, 2000);

  refresh();

  // 명령 바인딩
  container.querySelectorAll("[data-module-command]").forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.dataset.moduleCommand;
      const roles = ["mission", "vehicle", "visual"];
      const label = action === "start" ? copy.start : copy.stop;
      
      statusEl.textContent = `${label} 명령 전송 중...`;
      
      try {
        const results = await Promise.all(roles.map(role => 
          postJSON(`/api/v1/system/modules/${role}/${action}`).catch(e => ({ ok: false, error: e.message }))
        ));
        
        const failed = results.filter(r => !r.ok);
        if (failed.length > 0) {
          statusEl.textContent = `${label} 실패: ${failed.map(f => f.error).join(", ")}`;
        } else {
          statusEl.textContent = `${label} 완료`;
          setTimeout(() => { statusEl.textContent = copy.ready; }, 3000);
          refresh();
        }
      } catch (error) {
        statusEl.textContent = `${label} 에러: ${error.message}`;
      }
    });
  });
}
