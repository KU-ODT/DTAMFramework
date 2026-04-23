// Page-level controller that loads modules and updates the main dashboard view.
import { getJSON } from "../../api/client.js";
import { renderError, renderLoading, renderModuleManagement, renderOverview } from "../../components/detail-panel.js";
import { renderScenarioSetupForm } from "../../components/icd-forms.js";
import { createModuleCard, getModuleCopy, setActiveCard } from "../../components/module-card.js";
import { renderSimulationWorkspace } from "../simulation/simulation-workspace.js";
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
  simulationWorkspaceController?.destroy();
  simulationWorkspaceController = null;

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
  simulationWorkspaceController?.destroy();
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
    setIcdMode(false);
    openModal(moduleTitle);
    renderModuleManagement(detailPanel, currentLanguage);
    return;
  }

  const moduleTitle = getModuleCopy(module, currentLanguage).title;
  const formRenderer = icdFormRenderers[module.slug];
  if (formRenderer) {
    detailPanel.classList.remove("detail-panel--module-management");
    setIcdMode(true);
    openModal(moduleTitle);
    formRenderer(detailPanel, currentLanguage);
    return;
  }

  setIcdMode(false);
  detailPanel.classList.remove("detail-panel--module-management");
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
    simulationWorkspaceController?.updateLanguage(currentLanguage);
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
          <p class="eyebrow">No Modules</p>
          <h3>Dashboard is empty</h3>
          <p>Add module definitions on the backend to populate the dock.</p>
        </div>
      `;
    }
  } catch (error) {
    openModal("module workspace");
    renderError(detailPanel, error.message);
  }
}
