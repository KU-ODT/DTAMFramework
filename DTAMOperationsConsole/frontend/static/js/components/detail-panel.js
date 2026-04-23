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

const MODULE_CONNECTIONS = [
  {
    name: "DTAM Mission Planner",
    role: "MISSION",
    endpoint: "127.0.0.1:17010",
    tcp: "17011",
    status: "waiting",
    rx: "0",
    tx: "0",
    heartbeat: "-",
    tag: "idle",
    accent: "purple",
  },
  {
    name: "DTAM Air Mobility",
    role: "VEHICLE",
    endpoint: "127.0.0.1:17030",
    tcp: "17031",
    status: "waiting",
    rx: "0",
    tx: "547",
    heartbeat: "-",
    tag: "0003",
    accent: "green",
  },
  {
    name: "DTAM Server",
    role: "SERVER",
    endpoint: "127.0.0.1:17020",
    tcp: "17021",
    status: "connected",
    rx: "552",
    tx: "0",
    heartbeat: "now",
    tag: "0002",
    accent: "cyan",
  },
  {
    name: "DTAM Visualization",
    role: "VISUAL",
    endpoint: "127.0.0.1:17040",
    tcp: "17041",
    status: "waiting",
    rx: "0",
    tx: "547",
    heartbeat: "-",
    tag: "0003",
    accent: "amber",
  },
];

function moduleCopy(language = "en") {
  return MODULE_MANAGEMENT_COPY[language === "ko" ? "ko" : "en"];
}

function renderModuleCard(module, copy) {
  return `
    <article class="dtam-module-card dtam-module-card--${module.accent} ${module.status === "connected" ? "is-connected" : ""}">
      <header class="dtam-module-card__header">
        <div>
          <strong>${module.name}</strong>
          <span>${module.role}</span>
        </div>
        <span class="dtam-module-status dtam-module-status--${module.status}">
          <i aria-hidden="true"></i>
          ${copy[module.status]}
        </span>
      </header>
      <p class="dtam-module-endpoint">${module.endpoint} <span>(TCP ${module.tcp})</span></p>
      <div class="dtam-module-metrics">
        <div>
          <span>${copy.rx}</span>
          <strong>${module.rx}</strong>
        </div>
        <div>
          <span>${copy.tx}</span>
          <strong>${module.tx}</strong>
        </div>
        <div>
          <span>${copy.heartbeat}</span>
          <strong>${module.heartbeat}</strong>
        </div>
      </div>
      <span class="dtam-module-tag">${module.tag}</span>
    </article>
  `;
}

export function renderModuleManagement(container, language = "en") {
  const copy = moduleCopy(language);
  const connectedCount = MODULE_CONNECTIONS.filter((module) => module.status === "connected").length;

  container.classList.remove("detail-panel--icd");
  container.classList.add("detail-panel--module-management");
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
      <div class="dtam-module-count">
        <strong>${copy.eyebrow}</strong>
        <span>${connectedCount} / ${MODULE_CONNECTIONS.length}</span>
      </div>
      <div class="dtam-module-grid">
        ${MODULE_CONNECTIONS.map((module) => renderModuleCard(module, copy)).join("")}
      </div>
      <div class="dtam-module-command-status" data-module-command-status>${copy.ready}</div>
    </section>
  `;

  container.querySelectorAll("[data-module-command]").forEach((button) => {
    button.addEventListener("click", () => {
      const status = container.querySelector("[data-module-command-status]");
      const label = button.dataset.moduleCommand === "start" ? copy.start : copy.stop;
      if (status) {
        status.textContent = `${label}: ${copy.ready}`;
      }
    });
  });
}
