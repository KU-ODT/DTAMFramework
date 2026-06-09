import { getJSON, postJSON } from "../../api/client.js";

const PLUGIN_SLOTS = [
  {
    id: "vertisim",
    title: "VertiSim",
    subtitle: "Vertiport design and simulation SW",
    subtitleKo: "버티포트 설계 및 시뮬레이션 SW",
    accent: "#7dd3fc",
    summary: "Vertiport design and simulation software slot reserved for DTAM plug-in integration.",
    summaryKo: "버티포트 설계 및 시뮬레이션 SW 연동을 위한 DTAM 플러그인 슬롯입니다.",
    kind: "runtime",
  },
  {
    id: "uam-scheduler",
    title: "UAM Flight Scheduler",
    subtitle: "Detailed UAM flight plan generation SW",
    subtitleKo: "UAM 상세 비행계획 생성 SW",
    accent: "#8b5cf6",
    summary: "Detailed UAM flight-plan generation software slot reserved for DTAM plug-in integration.",
    summaryKo: "UAM 상세 비행계획 생성 SW 연동을 위한 DTAM 플러그인 슬롯입니다.",
    kind: "runtime",
    launchUrl: "/api/v1/plugins/uam-scheduler/launch",
    statusUrl: "/api/v1/plugins/uam-scheduler/status",
    stopUrl: "/api/v1/plugins/uam-scheduler/stop",
  },
  {
    id: "uam-traffics",
    title: "UAM TrafficS",
    subtitle: "UAM traffic simulator",
    subtitleKo: "UAM 교통 시뮬레이터",
    accent: "#34d399",
    summary: "UAM traffic simulation software slot reserved for DTAM plug-in integration.",
    summaryKo: "UAM 교통 시뮬레이터 연동을 위한 DTAM 플러그인 슬롯입니다.",
    kind: "runtime",
    launchUrl: "/api/v1/plugins/uam-traffics/launch",
    statusUrl: "/api/v1/plugins/uam-traffics/status",
    stopUrl: "/api/v1/plugins/uam-traffics/stop",
  },
  {
    id: "situation-awareness",
    title: "AI Model - 1 : Detection and Prediction",
    titleKo: "AI Model - 1 : Detection and Prediction",
    subtitle: "Risk awareness AI model",
    subtitleKo: "위험 인식 AI 모델",
    accent: "#22d3ee",
    summary: "Risk awareness AI model for detection and prediction using DTAM 4001/4101 ICD streams.",
    summaryKo: "DTAM 4001/4101 ICD 스트림을 활용하는 위험 인식 및 예측 AI 모델입니다.",
    kind: "runtime",
    launchUrl: "/api/v1/plugins/situation-awareness/launch",
    statusUrl: "/api/v1/plugins/situation-awareness/status",
    stopUrl: "/api/v1/plugins/situation-awareness/stop",
    aboutUrl: "https://sites.google.com/view/kadalab/",
  },
  {
    id: "teststream",
    title: "DTAM TestStream",
    titleKo: "DTAM TestStream",
    subtitle: "Real-time media stream test module",
    subtitleKo: "실시간 영상 스트림 테스트 모듈",
    accent: "#38bdf8",
    summary: "Receives direct VisualizationModule MJPEG video and sends camera commands through ICD 5002.",
    summaryKo: "VisualizationModule 직접 MJPEG 영상을 수신하고 카메라 명령은 ICD 5002로 전송하는 테스트 모듈입니다.",
    kind: "runtime",
    launchUrl: "/api/v1/plugins/teststream/launch",
    statusUrl: "/api/v1/plugins/teststream/status",
    stopUrl: "/api/v1/plugins/teststream/stop",
  },
];

const EXTENSION_SLOTS = [
  {
    id: "stakeholder-psu",
    title: "PSU",
    subtitle: "Public stakeholder",
    subtitleKo: "공공 이해관계자",
    accent: "#7dd3fc",
    summary: "Launches the PSU Monitoring Console with ICD 4001 server readiness, live aircraft positions, and vertiport/node-link map layers.",
    summaryKo: "ICD 4001 서버 수신 상태, 실시간 비행체 위치, 버티포트/Node-Link 지도 레이어를 포함한 PSU Monitoring Console을 실행합니다.",
    kind: "runtime",
    launchUrl: "/api/v1/plugins/stakeholder-psu/launch",
    statusUrl: "/api/v1/plugins/stakeholder-psu/status",
    stopUrl: "/api/v1/plugins/stakeholder-psu/stop",
    launchOnCardClick: true,
  },
  {
    id: "stakeholder-vfds",
    title: "VFDS",
    subtitle: "Vehicle dynamics",
    subtitleKo: "UAM 운용자",
    accent: "#8b5cf6",
    summary: "Reserved DTAM extension module slot for VFDS/vehicle-side workflows.",
    summaryKo: "VFDS 및 비행체 측 워크플로를 위한 DTAM 확장모듈 예약 슬롯입니다.",
    kind: "runtime",
  },
  {
    id: "stakeholder-vpo",
    title: "VPO",
    subtitle: "Vertiport operator",
    subtitleKo: "버티포트 운용자",
    accent: "#34d399",
    summary: "Launches the Vertiport Operations Monitoring dashboard for DT World camera views and ground operations.",
    summaryKo: "DT World 카메라 뷰와 지상 운용을 감시하는 Vertiport Operations Monitoring 대시보드를 실행합니다.",
    kind: "runtime",
    launchUrl: "/api/v1/plugins/stakeholder-vpo/launch",
    statusUrl: "/api/v1/plugins/stakeholder-vpo/status",
    stopUrl: "/api/v1/plugins/stakeholder-vpo/stop",
  },
  {
    id: "stakeholder-future",
    title: "Future Stakeholder",
    titleKo: "이해관계자 추가 예정",
    subtitle: "Expandable slot",
    subtitleKo: "확장 슬롯",
    accent: "#f59e0b",
    summary: "Additional stakeholder module box reserved for future DTAM extensions.",
    summaryKo: "추후 DTAM 확장을 위해 예약된 이해관계자 모듈 박스입니다.",
    kind: "future",
  },
];

const PLUGIN_COPY = {
  en: {
    eyebrow: "Plug-In Runtime",
    title: "DTAM Plugin",
    summary: "Select a plug-in slot, review its reserved runtime role, and prepare the launch surface for a future external instance.",
    railLabel: "Plug-in slot selector",
    selected: "Selected slot",
    run: "Run",
    open: "Open",
    stop: "Stop",
    aboutMore: "About More",
    pending: "Runtime launch hookup is pending for",
    launching: "Launching",
    opened: "Opened",
    running: "Running",
    stopping: "Stopping",
    stopped: "Stopped",
    future: "This slot is reserved for a future plug-in update.",
    error: "Launch failed",
    stopError: "Stop failed",
  },
  ko: {
    eyebrow: "Plug-In Runtime",
    title: "DTAM 플러그인",
    summary: "플러그인 슬롯을 선택하고, 역할을 확인한 뒤, 별도 인스턴스 연결 및 실행 화면을 준비합니다.",
    railLabel: "플러그인 슬롯 선택",
    selected: "선택 슬롯",
    run: "실행",
    open: "열기",
    stop: "종료",
    aboutMore: "About More",
    pending: "실행 연결 대기 중:",
    launching: "실행 중",
    opened: "실행 완료:",
    running: "실행 중",
    stopping: "종료 중",
    stopped: "종료 완료:",
    future: "이 슬롯은 추후 플러그인 업데이트를 위해 예약되어 있습니다.",
    error: "실행 실패",
    stopError: "종료 실패",
  },
};

const EXTENSION_COPY = {
  en: {
    eyebrow: "DTAM Extension Modules",
    title: "DTAM Extension Modules",
    summary: "Select a stakeholder extension module slot and prepare the same runtime surface used by DTAM plug-ins.",
    railLabel: "Stakeholder extension module selector",
    selected: "Selected stakeholder",
    run: "Run",
    open: "Open",
    stop: "Stop",
    aboutMore: "About More",
    pending: "Extension module launch hookup is pending for",
    launching: "Launching",
    opened: "Opened",
    running: "Running",
    stopping: "Stopping",
    stopped: "Stopped",
    future: "This slot is reserved for a future stakeholder extension module.",
    error: "Launch failed",
    stopError: "Stop failed",
  },
  ko: {
    eyebrow: "DTAM 확장모듈",
    title: "DTAM 확장모듈",
    summary: "이해관계자 확장모듈 슬롯을 선택하고, DTAM 플러그인과 동일한 실행 화면을 준비합니다.",
    railLabel: "이해관계자 확장모듈 선택",
    selected: "선택 이해관계자",
    run: "실행",
    open: "열기",
    stop: "종료",
    aboutMore: "About More",
    pending: "확장모듈 실행 연결 대기 중:",
    launching: "실행 중",
    opened: "실행 완료:",
    running: "실행 중",
    stopping: "종료 중",
    stopped: "종료 완료:",
    future: "이 슬롯은 추후 이해관계자 확장모듈을 위해 예약되어 있습니다.",
    error: "실행 실패",
    stopError: "종료 실패",
  },
};

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

function iconMarkup(slotId) {
  const normalizedId = String(slotId || "").replace(/^stakeholder-/, "");
  const icons = {
    vertisim: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M5 17h14" />
        <path d="M7 17 12 7l5 10" />
        <path d="M9.5 13h5" />
        <path d="M12 7v10" />
        <circle cx="12" cy="17" r="4" />
      </svg>
    `,
    "uam-scheduler": `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M5 5h14v14H5Z" />
        <path d="M5 9h14" />
        <path d="M8 3v4" />
        <path d="M16 3v4" />
        <path d="M8 15h5" />
        <path d="M13 15l3-3 3 3" />
      </svg>
    `,
    "uam-traffics": `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="6" cy="12" r="2" />
        <circle cx="18" cy="7" r="2" />
        <circle cx="18" cy="17" r="2" />
        <path d="M8 12h4" />
        <path d="M12 12l4-4" />
        <path d="M12 12l4 4" />
        <path d="M14 7h2" />
        <path d="M14 17h2" />
      </svg>
    `,
    "situation-awareness": `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3 20 7v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7l8-4Z" />
        <path d="M8 12h2.2l1.2-2.8 2.2 5.6 1.2-2.8H18" />
        <circle cx="12" cy="12" r="7" />
      </svg>
    `,
    teststream: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="4" y="6" width="12" height="10" rx="2" />
        <path d="M16 10l4-2v6l-4-2" />
        <path d="M7 19h10" />
        <path d="M12 16v3" />
        <path d="M8 10h4" />
      </svg>
    `,
    psu: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3 18 7v10l-6 4-6-4V7l6-4Z" />
        <path d="M9 12h6" />
        <path d="M12 9v6" />
      </svg>
    `,
    vfds: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M5 12c0-4 3.1-7 7-7s7 3 7 7-3.1 7-7 7-7-3-7-7Z" />
        <path d="M12 9v6" />
        <path d="M9 12h6" />
      </svg>
    `,
    vpo: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 7h16" />
        <path d="M4 12h16" />
        <path d="M4 17h10" />
        <path d="M17 15 20 12l-3-3" />
      </svg>
    `,
    future: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 5v14" />
        <path d="M5 12h14" />
      </svg>
    `,
  };

  return icons[normalizedId] || icons.future;
}

function normalizeLanguage(language) {
  return language === "ko" ? "ko" : "en";
}

function localizedSlot(slot, language) {
  if (normalizeLanguage(language) !== "ko") {
    return {
      title: slot.title,
      subtitle: slot.subtitle,
      summary: slot.summary,
    };
  }

  return {
    title: slot.titleKo || slot.title,
    subtitle: slot.subtitleKo || slot.subtitle,
    summary: slot.summaryKo || slot.summary,
  };
}

function slotMarkup(slot, language) {
  const copy = localizedSlot(slot, language);
  const futureClass = slot.kind === "future" ? " plugin-hub__card--future" : "";
  return `
    <button
      type="button"
      class="plugin-hub__card${futureClass}"
      data-plugin-card="${escapeHtml(slot.id)}"
      style="--plugin-accent: ${escapeHtml(slot.accent)};"
      aria-pressed="false"
    >
      <span class="plugin-hub__runtime-badge" data-plugin-runtime-badge hidden></span>
      <span class="plugin-hub__card-glow" aria-hidden="true"></span>
      <span class="plugin-hub__card-icon" aria-hidden="true">${iconMarkup(slot.id)}</span>
      <span class="plugin-hub__card-copy">
        <strong>${escapeHtml(copy.title)}</strong>
        <span>${escapeHtml(copy.subtitle)}</span>
      </span>
    </button>
  `;
}

function setupHorizontalDragScroll(track) {
  if (!track) {
    return () => {};
  }

  let pointerDown = false;
  let dragging = false;
  let startX = 0;
  let startScrollLeft = 0;
  let activePointerId = null;
  const dragThreshold = 6;

  const releasePointer = () => {
    if (activePointerId !== null && track.hasPointerCapture?.(activePointerId)) {
      track.releasePointerCapture(activePointerId);
    }
    if (dragging) {
      track.__pluginSuppressClick = true;
      window.setTimeout(() => {
        track.__pluginSuppressClick = false;
      }, 0);
    }
    pointerDown = false;
    dragging = false;
    activePointerId = null;
    track.classList.remove("is-dragging");
    track.classList.remove("is-pointer-down");
  };

  const onPointerDown = (event) => {
    if (event.button !== 0 || event.pointerType === "touch") {
      return;
    }
    pointerDown = true;
    dragging = false;
    startX = event.clientX;
    startScrollLeft = track.scrollLeft;
    activePointerId = event.pointerId;
    track.classList.add("is-pointer-down");
  };

  const onPointerMove = (event) => {
    if (!pointerDown) {
      return;
    }
    const deltaX = event.clientX - startX;
    if (!dragging && Math.abs(deltaX) < dragThreshold) {
      return;
    }
    if (!dragging) {
      dragging = true;
      track.setPointerCapture?.(event.pointerId);
    }
    track.classList.add("is-dragging");
    track.scrollLeft = startScrollLeft - deltaX;
    event.preventDefault();
  };

  const onClickCapture = (event) => {
    if (!track.__pluginSuppressClick) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
  };

  const onDragStart = (event) => {
    event.preventDefault();
  };

  track.addEventListener("pointerdown", onPointerDown);
  track.addEventListener("pointermove", onPointerMove);
  track.addEventListener("pointerup", releasePointer);
  track.addEventListener("pointercancel", releasePointer);
  track.addEventListener("lostpointercapture", releasePointer);
  track.addEventListener("click", onClickCapture, true);
  track.addEventListener("dragstart", onDragStart);

  return () => {
    track.removeEventListener("pointerdown", onPointerDown);
    track.removeEventListener("pointermove", onPointerMove);
    track.removeEventListener("pointerup", releasePointer);
    track.removeEventListener("pointercancel", releasePointer);
    track.removeEventListener("lostpointercapture", releasePointer);
    track.removeEventListener("click", onClickCapture, true);
    track.removeEventListener("dragstart", onDragStart);
  };
}

function renderSlotWorkspace(container, language, slots, copySet) {
  const normalizedLanguage = normalizeLanguage(language);
  const copy = copySet[normalizedLanguage];
  const firstSlot = localizedSlot(slots[0], normalizedLanguage);
  let selectedId = slots[0].id;
  const runtimeState = new Map();

  if (container.__pluginStatusTimer) {
    window.clearInterval(container.__pluginStatusTimer);
    container.__pluginStatusTimer = null;
  }
  if (container.__pluginDragCleanup) {
    container.__pluginDragCleanup();
    container.__pluginDragCleanup = null;
  }

  container.classList.remove("detail-panel--module-management", "detail-panel--icd");
  container.classList.add("detail-panel--plugin");
  container.innerHTML = `
    <section class="plugin-hub">
      <header class="plugin-hub__header">
        <p class="eyebrow">${escapeHtml(copy.eyebrow)}</p>
        <h3 id="detail-modal-title">${escapeHtml(copy.title)}</h3>
        <p class="plugin-hub__summary">${escapeHtml(copy.summary)}</p>
      </header>

      <section class="plugin-hub__rail" aria-label="${escapeHtml(copy.railLabel)}">
        <div class="plugin-hub__track" data-plugin-track>
          ${slots.map((slot) => slotMarkup(slot, normalizedLanguage)).join("")}
        </div>
      </section>

      <section class="plugin-hub__footer">
        <div class="plugin-hub__selection">
          <span>${escapeHtml(copy.selected)}</span>
          <strong data-plugin-selected-title>${escapeHtml(firstSlot.title)}</strong>
          <p data-plugin-selected-summary>${escapeHtml(firstSlot.summary)}</p>
        </div>
        <div class="plugin-hub__actions">
          <button type="button" class="plugin-hub__run" data-plugin-run>${escapeHtml(copy.run)}</button>
          <button type="button" class="plugin-hub__stop" data-plugin-stop hidden>${escapeHtml(copy.stop)}</button>
          <button type="button" class="plugin-hub__about" data-plugin-about hidden>${escapeHtml(copy.aboutMore)}</button>
        </div>
        <p class="plugin-hub__status" data-plugin-status></p>
      </section>
    </section>
  `;

  const track = container.querySelector("[data-plugin-track]");
  container.__pluginDragCleanup = setupHorizontalDragScroll(track);
  const cards = Array.from(container.querySelectorAll("[data-plugin-card]"));
  const selectedTitle = container.querySelector("[data-plugin-selected-title]");
  const selectedSummary = container.querySelector("[data-plugin-selected-summary]");
  const status = container.querySelector("[data-plugin-status]");
  const runButton = container.querySelector("[data-plugin-run]");
  const stopButton = container.querySelector("[data-plugin-stop]");
  const aboutButton = container.querySelector("[data-plugin-about]");

  const selectedSlot = () => slots.find((item) => item.id === selectedId) || slots[0];

  const updateRuntimeVisuals = () => {
    for (const card of cards) {
      const slotId = card.dataset.pluginCard || "";
      const state = runtimeState.get(slotId) || {};
      const running = Boolean(state.running);
      const badge = card.querySelector("[data-plugin-runtime-badge]");
      card.classList.toggle("is-running", running);
      if (badge) {
        badge.hidden = !running;
        badge.textContent = running ? copy.running : "";
      }
    }

    const slot = selectedSlot();
    const state = runtimeState.get(slot.id) || {};
    const running = Boolean(state.running);
    if (runButton) {
      runButton.textContent = running ? copy.open : copy.run;
    }
    if (stopButton) {
      stopButton.hidden = !running || !slot.stopUrl;
    }
    if (aboutButton) {
      aboutButton.hidden = !slot.aboutUrl;
    }
  };

  const selectedRuntimeText = (slot) => {
    const slotCopy = localizedSlot(slot, normalizedLanguage);
    const state = runtimeState.get(slot.id) || {};
    if (!state.running) {
      return "";
    }
    const url = state.url ? ` (${state.url})` : "";
    return `${copy.running}: ${slotCopy.title}${url}`;
  };

  const refreshPluginStatuses = async (showSelectedStatus = true) => {
    const checks = slots
      .filter((slot) => slot.statusUrl)
      .map(async (slot) => {
        try {
          const payload = await getJSON(slot.statusUrl);
          runtimeState.set(slot.id, payload || {});
        } catch {
          runtimeState.set(slot.id, { running: false });
        }
      });
    await Promise.all(checks);
    updateRuntimeVisuals();
    if (showSelectedStatus && status) {
      const text = selectedRuntimeText(selectedSlot());
      if (text) {
        status.textContent = text;
      }
    }
  };

  const applySelection = (slotId, smooth = false) => {
    const slot = slots.find((item) => item.id === slotId) || slots[0];
    const slotCopy = localizedSlot(slot, normalizedLanguage);
    selectedId = slot.id;

    for (const card of cards) {
      const active = card.dataset.pluginCard === slot.id;
      card.classList.toggle("is-selected", active);
      card.setAttribute("aria-pressed", active ? "true" : "false");
      if (active && smooth) {
        card.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
      }
    }

    if (selectedTitle) {
      selectedTitle.textContent = slotCopy.title;
    }
    if (selectedSummary) {
      selectedSummary.textContent = slotCopy.summary;
    }
    if (status) {
      status.textContent = selectedRuntimeText(slot);
    }
    updateRuntimeVisuals();
  };

  for (const card of cards) {
    card.addEventListener("click", (event) => {
      if (track?.__pluginSuppressClick) {
        event.preventDefault();
        return;
      }
      const slotId = card.dataset.pluginCard || slots[0].id;
      applySelection(slotId, true);
      const slot = slots.find((item) => item.id === slotId);
      if (slot?.launchOnCardClick && runButton && !runButton.disabled) {
        window.setTimeout(() => runButton.click(), 0);
      }
    });
  }

  track?.addEventListener(
    "wheel",
    (event) => {
      if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) {
        return;
      }
      event.preventDefault();
      track.scrollBy({ left: event.deltaY, behavior: "smooth" });
    },
    { passive: false },
  );

  runButton?.addEventListener("click", async () => {
    const slot = slots.find((item) => item.id === selectedId) || slots[0];
    const slotCopy = localizedSlot(slot, normalizedLanguage);
    if (!status) {
      return;
    }
    if (slot.kind === "future") {
      status.textContent = copy.future;
      return;
    }
    if (!slot.launchUrl) {
      status.textContent = `${copy.pending} ${slotCopy.title}.`;
      return;
    }

    runButton.disabled = true;
    if (stopButton) {
      stopButton.disabled = true;
    }
    status.textContent = `${copy.launching} ${slotCopy.title}...`;
    try {
      const payload = await postJSON(slot.launchUrl, {});
      runtimeState.set(slot.id, { ...(payload || {}), running: true, reachable: true });
      updateRuntimeVisuals();
      if (payload?.url) {
        window.open(payload.url, "_blank", "noopener,noreferrer");
      }
      const url = payload?.url ? ` (${payload.url})` : "";
      status.textContent = `${copy.opened} ${slotCopy.title}${url}`;
    } catch (error) {
      status.textContent = `${copy.error}: ${error instanceof Error ? error.message : String(error)}`;
    } finally {
      runButton.disabled = false;
      if (stopButton) {
        stopButton.disabled = false;
      }
    }
  });

  stopButton?.addEventListener("click", async () => {
    const slot = selectedSlot();
    const slotCopy = localizedSlot(slot, normalizedLanguage);
    if (!slot.stopUrl || !status) {
      return;
    }
    runButton.disabled = true;
    stopButton.disabled = true;
    status.textContent = `${copy.stopping} ${slotCopy.title}...`;
    try {
      const payload = await postJSON(slot.stopUrl, {});
      runtimeState.set(slot.id, payload || { running: false });
      updateRuntimeVisuals();
      status.textContent = `${copy.stopped} ${slotCopy.title}`;
    } catch (error) {
      status.textContent = `${copy.stopError}: ${error instanceof Error ? error.message : String(error)}`;
    } finally {
      runButton.disabled = false;
      stopButton.disabled = false;
      await refreshPluginStatuses(false);
    }
  });

  aboutButton?.addEventListener("click", () => {
    const slot = selectedSlot();
    if (!slot.aboutUrl) {
      return;
    }
    window.open(slot.aboutUrl, "_blank", "noopener,noreferrer");
  });

  applySelection(selectedId, false);
  refreshPluginStatuses(true);
  container.__pluginStatusTimer = window.setInterval(() => {
    if (!container.isConnected) {
      window.clearInterval(container.__pluginStatusTimer);
      container.__pluginStatusTimer = null;
      if (container.__pluginDragCleanup) {
        container.__pluginDragCleanup();
        container.__pluginDragCleanup = null;
      }
      return;
    }
    refreshPluginStatuses(false);
  }, 4000);
}

export function renderPluginWorkspace(container, language = "en") {
  renderSlotWorkspace(container, language, PLUGIN_SLOTS, PLUGIN_COPY);
}

export function renderExtensionWorkspace(container, language = "en") {
  renderSlotWorkspace(container, language, EXTENSION_SLOTS, EXTENSION_COPY);
}
