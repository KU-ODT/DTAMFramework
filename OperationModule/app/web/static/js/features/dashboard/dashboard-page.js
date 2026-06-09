// Page-level controller that loads modules and updates the main dashboard view.
import { getJSON, postJSON } from "../../api/client.js";
import { renderError, renderLoading, renderModuleManagement, renderOverview, renderPlaceholder } from "../../components/detail-panel.js?v=20260520-vfds-server1";
import { renderScenarioSetupForm } from "../../components/icd-forms.js?v=20260519-exec-guard1";
import { createModuleCard, getModuleCopy, setActiveCard } from "../../components/module-card.js?v=20260512-dock-align1";
import { renderSimulationWorkspace } from "../simulation/simulation-workspace.js?v=20260522-uam-gate2";
import { renderExtensionWorkspace, renderPluginWorkspace } from "../modules/plugin.js?v=20260515-cardclick1";
import { moduleLoaders } from "../modules/index.js";

const moduleGrid = document.querySelector("#module-grid");
const dashboardLayout = document.querySelector(".dashboard-layout");
const detailPanel = document.querySelector("#detail-panel");
const detailModal = document.querySelector("#detail-modal");
const detailCloseButton = document.querySelector("#detail-close");
const closeBackdrop = document.querySelector("[data-close-modal]");
const detailWindow = document.querySelector(".detail-window");
const simulationWorkspaceRoot = document.querySelector("#simulation-workspace-root");

const icdFormRenderers = {
  environment: renderScenarioSetupForm,
};

let lastFocusedCard = null;
let loadedModules = [];
let activeSlug = null;
let currentLanguage = document.documentElement.lang === "ko" ? "ko" : "en";
let simulationWorkspaceController = null;

function clearDetailPanelModes() {
  detailPanel?.classList.remove("detail-panel--module-management", "detail-panel--plugin");
}

async function loadModules() {
  return getJSON("/api/v1/dashboard/modules");
}

function openModal(moduleTitle) {
  if (!detailModal) {
    return;
  }

  detailModal.hidden = false;
  detailModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
  if (detailCloseButton) {
    const closeLabel = currentLanguage === "ko" ? "닫기" : "Close";
    detailCloseButton.textContent = closeLabel;
    detailCloseButton.setAttribute("aria-label", `${closeLabel} ${moduleTitle}`);
  }
}

function setIcdMode(enabled) {
  detailModal?.classList.toggle("detail-modal--icd", enabled);
  detailWindow?.classList.toggle("detail-window--icd", enabled);
  detailPanel?.classList.toggle("detail-panel--icd", enabled);
}

function closeModal() {
  if (!detailModal || detailModal.hidden) {
    return;
  }

  detailModal.hidden = true;
  detailModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");
  lastFocusedCard?.focus();
}

function closeSimulationWorkspace() {
  if (simulationWorkspaceRoot) {
    simulationWorkspaceRoot.hidden = true;
  }
  if (dashboardLayout) {
    dashboardLayout.hidden = false;
  }
  document.body.classList.remove("simulation-workspace-open");
  lastFocusedCard?.focus();
}

function openSimulationWorkspace(sourceButton = null) {
  if (!simulationWorkspaceRoot || !dashboardLayout) {
    return;
  }

  closeModal();
  lastFocusedCard = sourceButton;
  activeSlug = "mission";
  setActiveCard(moduleGrid, activeSlug);
  dashboardLayout.hidden = true;
  simulationWorkspaceRoot.hidden = false;
  window.scrollTo({ top: 0, left: 0 });
  document.body.classList.add("simulation-workspace-open");
  if (simulationWorkspaceController) {
    simulationWorkspaceController.updateLanguage?.(currentLanguage);
    simulationWorkspaceController.show?.();
    return;
  }
  simulationWorkspaceController = renderSimulationWorkspace(simulationWorkspaceRoot, {
    language: currentLanguage,
    onBack: closeSimulationWorkspace,
  });
}

async function selectModule(module, sourceButton = null) {
  setActiveCard(moduleGrid, module.slug);
  lastFocusedCard = sourceButton;
  activeSlug = module.slug;

  if (module.slug === "mission") {
    openSimulationWorkspace(sourceButton);
    return;
  }

  if (module.slug === "dtam-modules") {
    const moduleTitle = getModuleCopy(module, currentLanguage).title;
    clearDetailPanelModes();
    setIcdMode(false);
    openModal(moduleTitle);
    renderModuleManagement(detailPanel, currentLanguage);
    return;
  }

  if (module.slug === "dtam-extensions") {
    const moduleTitle = getModuleCopy(module, currentLanguage).title;
    clearDetailPanelModes();
    setIcdMode(false);
    openModal(moduleTitle);
    renderExtensionWorkspace(detailPanel, currentLanguage);
    return;
  }

  if (module.slug === "data") {
    const moduleTitle = getModuleCopy(module, currentLanguage).title;
    clearDetailPanelModes();
    setIcdMode(false);
    openModal(moduleTitle);
    renderLoading(detailPanel, moduleTitle);
    try {
      await postJSON("/api/v1/data/open-console", {});
      closeModal();
    } catch (error) {
      renderError(detailPanel, error.message);
    }
    return;
  }

  if (module.slug === "plugin") {
    const moduleTitle = getModuleCopy(module, currentLanguage).title;
    clearDetailPanelModes();
    setIcdMode(false);
    openModal(moduleTitle);
    renderPluginWorkspace(detailPanel, currentLanguage);
    return;
  }

  if (module.slug === "system") {
    const moduleTitle = getModuleCopy(module, currentLanguage).title;
    clearDetailPanelModes();
    setIcdMode(false);
    openModal(moduleTitle);
    renderPlaceholder(detailPanel, {
      eyebrow: currentLanguage === "ko" ? "시스템" : "System",
      title: moduleTitle,
      summary: currentLanguage === "ko" ? "시스템 설정 화면은 준비 중입니다." : "System Setting surface reserved.",
      detail: currentLanguage === "ko"
        ? "아직 연결된 실행 동작은 없습니다. 추후 시스템 제어 기능을 연결하기 위한 작업 영역입니다."
        : "No runtime action is connected yet. This workspace is intentionally left empty for later system controls.",
    });
    return;
  }

  const moduleTitle = getModuleCopy(module, currentLanguage).title;
  const formRenderer = icdFormRenderers[module.slug];
  if (formRenderer) {
    clearDetailPanelModes();
    setIcdMode(true);
    openModal(moduleTitle);
    formRenderer(detailPanel, currentLanguage);
    return;
  }

  setIcdMode(false);
  clearDetailPanelModes();
  openModal(moduleTitle);
  renderLoading(detailPanel, moduleTitle);

  try {
    const loader = moduleLoaders[module.slug];
    const overview = loader ? await loader(module.endpoint) : await getJSON(module.endpoint);
    renderOverview(detailPanel, overview);
  } catch (error) {
    renderError(detailPanel, error.message);
  }
}

function renderModuleDock(modules) {
  moduleGrid.innerHTML = "";

  for (const module of modules) {
    const card = createModuleCard(module, selectModule, currentLanguage);
    moduleGrid.append(card);
  }

  if (activeSlug) {
    setActiveCard(moduleGrid, activeSlug);
  }
}

function bindModalEvents() {
  detailCloseButton?.addEventListener("click", closeModal);
  closeBackdrop?.addEventListener("click", closeModal);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      if (simulationWorkspaceController) {
        closeSimulationWorkspace();
      } else {
        closeModal();
      }
    }
  });

  window.addEventListener("dtam-language-change", (event) => {
    currentLanguage = event.detail?.language === "ko" ? "ko" : "en";
    if (simulationWorkspaceController && simulationWorkspaceRoot && !simulationWorkspaceRoot.hidden) {
      simulationWorkspaceController.updateLanguage(currentLanguage);
    }
    if (loadedModules.length > 0) {
      renderModuleDock(loadedModules);
    }
  });
}

export async function initDashboard() {
  if (!moduleGrid || !detailPanel || !detailModal || !simulationWorkspaceRoot || !dashboardLayout) {
    return;
  }

  currentLanguage = document.documentElement.lang === "ko" ? "ko" : "en";
  bindModalEvents();

  try {
    const modules = await loadModules();
    loadedModules = modules;

    if (modules.length > 0) {
      renderModuleDock(modules);
    } else {
      moduleGrid.innerHTML = `
        <div class="module-grid__empty">
          <p class="eyebrow">${currentLanguage === "ko" ? "紐⑤뱢 ?놁쓬" : "No Modules"}</p>
          <h3>${currentLanguage === "ko" ? "??쒕낫?쒓? 鍮꾩뼱 ?덉뒿?덈떎" : "Dashboard is empty"}</h3>
          <p>${currentLanguage === "ko" ? "諛깆뿏?쒖뿉 紐⑤뱢 ?뺤쓽瑜?異붽??섎㈃ ?꾪겕???쒖떆?⑸땲??" : "Add module definitions on the backend to populate the dock."}</p>
        </div>
      `;
    }
  } catch (error) {
    openModal("module workspace");
    renderError(detailPanel, error.message);
  }
}


