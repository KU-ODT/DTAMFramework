// Frontend entry file that boots the dashboard page.
import { initDashboard } from "./features/dashboard/dashboard-page.js";

const patchNoteState = {
  data: null,
  language: "en",
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
    const nextLanguage = descriptions[language] ? language : "en";
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

  toggle.addEventListener("click", () => {
    const currentLanguage = toggle.dataset.currentLanguage === "ko" ? "ko" : "en";
    setLanguage(currentLanguage === "ko" ? "en" : "ko");
  });

  setLanguage(localStorage.getItem("dtam-operations-console-language") || "en");
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

initLanguageToggle();
initPatchNotes();
initDashboard();
