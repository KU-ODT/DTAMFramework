// Detail panel renderer for module summaries, metrics, and suggested actions.
import { getJSON, postJSON } from "../api/client.js";

function escapeHtml(value) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderMetric(metric) {
  return `
    <article class="metric-card">
      <p class="metric-card__label">${escapeHtml(metric.label)}</p>
      <p class="metric-card__value">${escapeHtml(metric.value)}</p>
      <p class="metric-card__hint">${escapeHtml(metric.hint)}</p>
    </article>
  `;
}

function renderAction(action) {
  return `
    <div class="action-item" data-action-id="${escapeHtml(action.id)}">
      <strong>${escapeHtml(action.label)}</strong>
      <p>${escapeHtml(action.description)}</p>
    </div>
  `;
}

function currentLanguage() {
  return document.documentElement.lang === "ko" ? "ko" : "en";
}

export function renderLoading(container, moduleTitle = "workspace") {
  const language = currentLanguage();
  container.innerHTML = `
    <div class="detail-loading">
      <p class="eyebrow">${language === "ko" ? "로딩" : "Loading"}</p>
      <h3 id="detail-modal-title">${language === "ko" ? `${escapeHtml(moduleTitle)} 여는 중` : `Opening ${escapeHtml(moduleTitle)}`}</h3>
      <p>${language === "ko" ? "백엔드에서 모듈 상태를 수집하는 중입니다." : "Collecting module state from the backend."}</p>
    </div>
  `;
}

export function renderError(container, message) {
  const language = currentLanguage();
  container.innerHTML = `
    <div class="detail-error">
      <p class="eyebrow">${language === "ko" ? "모듈 오류" : "Module Error"}</p>
      <h3 id="detail-modal-title">${language === "ko" ? "작업 영역을 불러올 수 없습니다" : "Could not load workspace"}</h3>
      <p>${escapeHtml(message)}</p>
    </div>
  `;
}

export function renderPlaceholder(container, options = {}) {
  const language = currentLanguage();
  const eyebrow = options.eyebrow || "Workspace";
  const title = options.title || "Coming Soon";
  const summary = options.summary || "This surface is reserved for a later integration.";
  const detail = options.detail || "No runtime action is connected yet.";
  const sidebarEyebrow = language === "ko" ? "상태" : "Status";
  const reservedLabel = language === "ko" ? "준비 중" : "Reserved";
  const pendingLabel = language === "ko" ? "연결 대기" : "Pending hookup";

  container.innerHTML = `
    <section class="detail-main">
      <p class="eyebrow">${escapeHtml(eyebrow)}</p>
      <h3 id="detail-modal-title">${escapeHtml(title)}</h3>
      <div class="detail-status">${escapeHtml(summary)}</div>
      <p class="detail-summary">${escapeHtml(detail)}</p>
    </section>
    <aside class="detail-sidebar">
      <p class="eyebrow">${sidebarEyebrow}</p>
      <h4>${reservedLabel}</h4>
      <div class="action-list">
        <div class="action-item">
          <strong>${pendingLabel}</strong>
          <p>${escapeHtml(detail)}</p>
        </div>
      </div>
    </aside>
  `;
}

export function renderOverview(container, overview) {
  const language = currentLanguage();
  container.innerHTML = `
    <section class="detail-main">
      <p class="eyebrow">${escapeHtml(overview.slug)}</p>
      <h3 id="detail-modal-title">${escapeHtml(overview.headline)}</h3>
      <div class="detail-status">${escapeHtml(overview.status)}</div>
      <p class="detail-summary">${escapeHtml(overview.summary)}</p>
      <div class="metric-grid">
        ${overview.metrics.map(renderMetric).join("")}
      </div>
    </section>
    <aside class="detail-sidebar">
      <p class="eyebrow">${language === "ko" ? "제안 폴더" : "Suggested folders"}</p>
      <h4>${language === "ko" ? "권장 기능 분리" : "Recommended feature split"}</h4>
      <div class="action-list">
        ${overview.actions.map(renderAction).join("")}
      </div>
    </aside>
  `;
}

const MODULE_MANAGEMENT_COPY = {
  en: {
    eyebrow: "CONNECTED MODULES",
    title: "System Settings",
    summary: "Run backend modules without opening their GUI, then open each module GUI on demand.",
    start: "Run Modules",
    stop: "Stop Modules",
    gui: "Open GUI",
    ready: "Module orchestration is ready.",
    loading: "Loading module status.",
    starting: "Starting backend modules.",
    stopping: "Stopping backend modules.",
    opening: "Opening module GUI.",
    opened: "GUI open command sent.",
    error: "Module command failed.",
    process: "process",
    rx: "IN",
    tx: "OUT",
    heartbeat: "HEARTBEAT",
    connected: "connected",
    waiting: "waiting",
  },
  ko: {
    eyebrow: "CONNECTED MODULES",
    title: "시스템 설정",
    summary: "GUI 없이 백엔드 모듈을 실행하고, 필요한 모듈 GUI만 별도 창으로 엽니다.",
    start: "모듈 실행",
    stop: "모듈 종료",
    gui: "GUI 켜기",
    ready: "모듈 실행 명령 대기 중입니다.",
    loading: "모듈 상태를 불러오는 중입니다.",
    starting: "백엔드 모듈을 실행하는 중입니다.",
    stopping: "백엔드 모듈을 종료하는 중입니다.",
    opening: "모듈 GUI를 여는 중입니다.",
    opened: "GUI 열기 명령을 보냈습니다.",
    error: "모듈 명령 처리에 실패했습니다.",
    process: "프로세스",
    rx: "IN",
    tx: "OUT",
    heartbeat: "HEARTBEAT",
    connected: "connected",
    waiting: "waiting",
  },
};

const DEFAULT_MODULE_CONNECTIONS = [
  {
    id: "mission",
    name: "DTAM Mission Planner",
    role: "MISSION",
    endpoint: "ws://127.0.0.1:8096/ws/dtam",
    transport: "WS 8096",
    status: "waiting",
    rx: "0",
    tx: "0",
    heartbeat: "-",
    tag: "idle",
    accent: "purple",
  },
  {
    id: "airmobility",
    name: "DTAM Air Mobility",
    role: "VEHICLE",
    endpoint: "ws://127.0.0.1:8096/ws/dtam",
    transport: "WS 8096",
    status: "waiting",
    rx: "0",
    tx: "0",
    heartbeat: "-",
    tag: "idle",
    accent: "green",
  },
  {
    id: "vfds",
    name: "VFDS/KP2A Dynamics",
    role: "VFDS/KP2A",
    endpoint: "http://127.0.0.1:8098/api/v1/missions/realtime",
    transport: "HTTP 8098",
    status: "waiting",
    rx: "0",
    tx: "0",
    heartbeat: "-",
    tag: "idle",
    accent: "blue",
  },
  {
    id: "server",
    name: "DTAM Core/State Server",
    role: "SERVER",
    endpoint: "Core 127.0.0.1:8095 / State 127.0.0.1:8096",
    transport: "HTTP 8095 / WS 8096",
    status: "waiting",
    rx: "0",
    tx: "0",
    heartbeat: "-",
    tag: "idle",
    accent: "cyan",
  },
  {
    id: "visualization",
    name: "DTAM Visualization",
    role: "VISUAL",
    endpoint: "ws://127.0.0.1:8096/ws/dtam",
    transport: "WS 8096",
    status: "waiting",
    rx: "0",
    tx: "0",
    heartbeat: "-",
    tag: "idle",
    accent: "amber",
  },
];

function moduleCopy(language = "en") {
  return MODULE_MANAGEMENT_COPY[language === "ko" ? "ko" : "en"];
}

function normalizeModules(payload) {
  const modules = Array.isArray(payload?.modules) && payload.modules.length > 0
    ? payload.modules
    : DEFAULT_MODULE_CONNECTIONS;
  return modules.map((module) => ({
    id: module.id,
    name: module.name,
    role: module.role,
    endpoint: module.endpoint,
    transport: module.transport || "",
    status: module.status || "waiting",
    rx: module.rx ?? "0",
    tx: module.tx ?? "0",
    heartbeat: module.heartbeat || "-",
    tag: module.tag || "idle",
    accent: module.accent || "cyan",
    processState: module.process_state || "stopped",
    pid: module.pid || null,
    guiUrl: module.gui_url || "",
    guiAvailable: Boolean(module.gui_available),
  }));
}

function renderModuleCard(module, copy) {
  const statusLabel = copy[module.status] || module.status;
  const pidLabel = module.pid ? ` / PID ${module.pid}` : "";
  return `
    <article class="dtam-module-card dtam-module-card--${escapeHtml(module.accent)} ${module.status === "connected" ? "is-connected" : ""}">
      <header class="dtam-module-card__header">
        <div>
          <strong>${escapeHtml(module.name)}</strong>
          <span>${escapeHtml(module.role)}</span>
        </div>
        <span class="dtam-module-status dtam-module-status--${escapeHtml(module.status)}">
          <i aria-hidden="true"></i>
          ${escapeHtml(statusLabel)}
        </span>
      </header>
      <p class="dtam-module-endpoint">${escapeHtml(module.endpoint)} <span>${escapeHtml(module.transport)}</span></p>
      <div class="dtam-module-metrics">
        <div>
          <span>${copy.rx}</span>
          <strong>${escapeHtml(module.rx)}</strong>
        </div>
        <div>
          <span>${copy.tx}</span>
          <strong>${escapeHtml(module.tx)}</strong>
        </div>
        <div>
          <span>${copy.heartbeat}</span>
          <strong>${escapeHtml(module.heartbeat)}</strong>
        </div>
      </div>
      <footer class="dtam-module-card__footer">
        <span class="dtam-module-tag">${escapeHtml(module.tag)}</span>
        <button type="button" class="dtam-module-gui" data-module-gui="${escapeHtml(module.id)}" ${module.guiAvailable ? "" : "disabled"}>
          ${copy.gui}
        </button>
      </footer>
      <p class="dtam-module-process">${copy.process}: ${escapeHtml(module.processState)}${escapeHtml(pidLabel)}</p>
    </article>
  `;
}

export function renderModuleManagement(container, language = "en") {
  const copy = moduleCopy(language);

  if (container._dtamModulesTimer) {
    clearInterval(container._dtamModulesTimer);
    container._dtamModulesTimer = null;
  }

  const setStatus = (message) => {
    const status = container.querySelector("[data-module-command-status]");
    if (status) {
      status.textContent = message;
    }
  };

  const setBusy = (busy) => {
    container.querySelectorAll("[data-module-command], [data-module-gui]").forEach((button) => {
      button.disabled = busy;
    });
  };

  const render = (payload = {}) => {
    const modules = normalizeModules(payload);
    const connectedCount = Number.isFinite(payload.running_count)
      ? payload.running_count
      : modules.filter((module) => module.status === "connected").length;
    const totalCount = Number.isFinite(payload.total_count) ? payload.total_count : modules.length;

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
          <span>${connectedCount} / ${totalCount}</span>
        </div>
        <div class="dtam-module-grid">
          ${modules.map((module) => renderModuleCard(module, copy)).join("")}
        </div>
        <div class="dtam-module-command-status" data-module-command-status>${escapeHtml(payload.message || copy.ready)}</div>
      </section>
    `;

    bindModuleManagementEvents();
  };

  const refresh = async (message = "") => {
    try {
      const payload = await getJSON("/api/v1/system/modules");
      if (message) {
        payload.message = message;
      }
      render(payload);
    } catch (error) {
      render({ modules: DEFAULT_MODULE_CONNECTIONS, message: `${copy.error}: ${error.message}` });
    }
  };

  function bindModuleManagementEvents() {
    container.querySelectorAll("[data-module-command]").forEach((button) => {
      button.addEventListener("click", async () => {
        const command = button.dataset.moduleCommand;
        const isStart = command === "start";
        setBusy(true);
        setStatus(isStart ? copy.starting : copy.stopping);
        try {
          const payload = await postJSON(`/api/v1/system/modules/${isStart ? "run" : "stop"}`, {});
          payload.message = copy.ready;
          render(payload);
        } catch (error) {
          setStatus(`${copy.error}: ${error.message}`);
          setBusy(false);
        }
      });
    });

    container.querySelectorAll("[data-module-gui]").forEach((button) => {
      button.addEventListener("click", async () => {
        const moduleId = button.dataset.moduleGui;
        if (!moduleId) {
          return;
        }
        setBusy(true);
        setStatus(copy.opening);
        try {
          const payload = await postJSON(`/api/v1/system/modules/${moduleId}/open-gui`, {});
          payload.message = copy.opened;
          render(payload);
        } catch (error) {
          setStatus(`${copy.error}: ${error.message}`);
          setBusy(false);
        }
      });
    });
  }

  render({ modules: DEFAULT_MODULE_CONNECTIONS, message: copy.loading });
  refresh();
  container._dtamModulesTimer = setInterval(() => {
    if (!container.isConnected || container.closest("[hidden]")) {
      clearInterval(container._dtamModulesTimer);
      container._dtamModulesTimer = null;
      return;
    }
    refresh();
  }, 3000);
}
