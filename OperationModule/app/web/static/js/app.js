// Frontend entry file that boots the dashboard page.
import { postJSON } from "./api/client.js";
import { initDashboard } from "./features/dashboard/dashboard-page.js?v=20260522-uam-gate2";

const DEFAULT_LANGUAGE = "ko";

const patchNoteState = {
  data: null,
  language: DEFAULT_LANGUAGE,
};

function initLanguageToggle() {
  const toggle = document.querySelector("#language-toggle");
  const description = document.querySelector("#hero-description");
  if (!toggle || !description) {
    return;
  }

  const descriptions = {
    en: description.dataset.descriptionEn,
    ko: description.dataset.descriptionKo,
  };

  function setLanguage(language) {
    const nextLanguage = descriptions[language] ? language : DEFAULT_LANGUAGE;
    description.textContent = descriptions[nextLanguage];
    document.documentElement.lang = nextLanguage === "ko" ? "ko" : "en";
    toggle.dataset.currentLanguage = nextLanguage;
    toggle.setAttribute("aria-pressed", nextLanguage === "ko" ? "true" : "false");
    toggle.setAttribute(
      "aria-label",
      nextLanguage === "ko" ? "Switch language to English" : "Switch language to Korean",
    );
    localStorage.setItem("dtam-operations-console-language", nextLanguage);
    patchNoteState.language = nextLanguage;
    renderPatchNotes();
    window.dispatchEvent(new CustomEvent("dtam-language-change", { detail: { language: nextLanguage } }));
  }

  toggle.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    const currentLanguage = toggle.dataset.currentLanguage === "ko" ? "ko" : "en";
    setLanguage(currentLanguage === "ko" ? "en" : "ko");
  });

  setLanguage(localStorage.getItem("dtam-operations-console-language") || DEFAULT_LANGUAGE);
}

function parsePatchNotesSection(sectionText, language) {
  const heading = language === "ko" ? "배포버전" : "Release Version";
  const updatesHeading = language === "ko" ? "업데이트 내용" : "Updates";
  const releaseMatch = sectionText.match(new RegExp(`(?:^|\\n)${heading}\\s*\\n([\\s\\S]*?)(?=\\n\\s*${updatesHeading}\\s*\\n|$)`));
  const updatesMatch = sectionText.match(new RegExp(`(?:^|\\n)${updatesHeading}\\s*\\n([\\s\\S]*)$`));
  const fallbackRelease = language === "ko" ? "배포버전 정보를 불러올 수 없습니다." : "Release version unavailable";
  const fallbackUpdate = language === "ko" ? "업데이트 내용을 불러올 수 없습니다." : "Update notes unavailable";
  const releaseVersion = releaseMatch?.[1]?.trim() || fallbackRelease;
  const updateLines = (updatesMatch?.[1] || "")
    .split("\n")
    .map((line) => line.trim().replace(/^[-*]\s*/, ""))
    .filter(Boolean);

  return {
    releaseVersion,
    updateLines: updateLines.length > 0 ? updateLines : [fallbackUpdate],
  };
}

function parsePatchNotes(rawText) {
  const normalized = rawText.replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
  const koreanSection = normalized.match(/\[ko\]\s*\n([\s\S]*?)(?=\n\[en\]\s*\n|$)/)?.[1]?.trim() || "";
  const englishSection = normalized.match(/\[en\]\s*\n([\s\S]*?)(?=\n\[ko\]\s*\n|$)/)?.[1]?.trim() || "";

  return {
    ko: parsePatchNotesSection(koreanSection || normalized, "ko"),
    en: parsePatchNotesSection(englishSection || normalized, "en"),
  };
}

function renderPatchNotes() {
  const releaseVersion = document.querySelector("#patch-release-version");
  const updateList = document.querySelector("#patch-update-list");
  const noteTitle = document.querySelector("#patch-note-title");
  const releaseHeading = document.querySelector("#patch-release-heading");
  const updatesHeading = document.querySelector("#patch-updates-heading");
  if (!releaseVersion || !updateList || !patchNoteState.data) {
    return;
  }

  const language = patchNoteState.language === "ko" ? "ko" : "en";
  const patchNotes = patchNoteState.data[language];
  if (noteTitle) {
    noteTitle.textContent = language === "ko" ? "패치노트" : "Patch Notes";
  }
  if (releaseHeading) {
    releaseHeading.textContent = language === "ko" ? "배포버전" : "Release Version";
  }
  if (updatesHeading) {
    updatesHeading.textContent = language === "ko" ? "업데이트 내용" : "Updates";
  }
  releaseVersion.textContent = patchNotes.releaseVersion;
  updateList.replaceChildren(
    ...patchNotes.updateLines.map((line) => {
      const item = document.createElement("li");
      item.textContent = line;
      return item;
    }),
  );
}

async function initPatchNotes() {
  const releaseVersion = document.querySelector("#patch-release-version");
  const updateList = document.querySelector("#patch-update-list");
  if (!releaseVersion || !updateList) {
    return;
  }

  try {
    const response = await fetch("/static/patch_notes/patch_notes.txt", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Patch notes request failed: ${response.status}`);
    }

    patchNoteState.data = parsePatchNotes(await response.text());
    renderPatchNotes();
  } catch (error) {
    releaseVersion.textContent = "Release version unavailable";
    const item = document.createElement("li");
    item.textContent = error.message;
    updateList.replaceChildren(item);
  }
}

function initManagedConsoleShutdown() {
  // pagehide/beforeunload fires on refresh, navigation, and some browser
  // lifecycle transitions. Using it to stop the DTAM stack caused false
  // shutdowns while the console was still in use. Window-close ownership is
  // handled by DOC_main.py's managed browser profile watcher instead.
  return;

  const params = new URLSearchParams(window.location.search);
  if (params.get("dtam-managed") !== "1") {
    return;
  }

  const closeToken = params.get("dtam-close-token") || "";
  if (!closeToken) {
    return;
  }

  let sent = false;
  function notifyConsoleClosed(reason) {
    if (sent) {
      return;
    }
    sent = true;
    const payload = JSON.stringify({ reason, token: closeToken });
    const endpoint = "/api/v1/system/console/closed";

    if (navigator.sendBeacon) {
      const blob = new Blob([payload], { type: "application/json" });
      navigator.sendBeacon(endpoint, blob);
      return;
    }

    fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload,
      keepalive: true,
    }).catch(() => {});
  }

  window.addEventListener(
    "pagehide",
    () => {
      notifyConsoleClosed("pagehide");
    },
    { once: true },
  );
}

function initSimModeGate() {
  const screen = document.querySelector("#sim-mode-screen");
  const shell = document.querySelector("#dtam-dashboard-shell");
  if (!screen || !shell) {
    return;
  }

  const message = screen.querySelector("[data-sim-mode-message]");
  const buttons = Array.from(screen.querySelectorAll("[data-sim-mode]"));
  let uamStarting = false;

  function showDashboard() {
    screen.hidden = true;
    shell.hidden = false;
    document.body.classList.add("sim-mode-entered");
    window.requestAnimationFrame(() => {
      document.querySelector(".module-card")?.focus?.();
    });
  }

  function showPreparing(modeLabel) {
    if (!message) {
      return;
    }
    message.textContent = `${modeLabel} 모드는 아직 준비중입니다.`;
  }

  function setModeButtonsDisabled(disabled) {
    for (const button of buttons) {
      button.disabled = disabled;
      button.setAttribute("aria-busy", disabled ? "true" : "false");
    }
  }

  function startUamModulesInBackground() {
    postJSON("/api/v1/system/modules/run", {})
      .catch((error) => {
        console.warn("UAM module auto-start failed", error);
      });
  }

  function enterUamMode() {
    if (uamStarting) {
      return;
    }
    uamStarting = true;
    setModeButtonsDisabled(true);
    if (message) {
      message.textContent = "UAM ??? ?????. DTAM ??? ??????? ?????...";
    }

    showDashboard();
    startUamModulesInBackground();
  }

  for (const button of buttons) {
    button.addEventListener("click", () => {
      const mode = button.dataset.simMode || "";
      if (mode === "uam") {
        enterUamMode();
        return;
      }
      const label = button.querySelector("strong")?.textContent?.trim() || "선택한";
      showPreparing(label);
    });
  }
}

initManagedConsoleShutdown();
initSimModeGate();
initLanguageToggle();
initPatchNotes();
initDashboard();
