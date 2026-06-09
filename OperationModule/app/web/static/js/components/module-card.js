// Module card renderer used by the dashboard button dock.

const MODULE_COPY = {
  simulation: {
    en: { title: "Mode Selection", subtitle: "" },
    ko: { title: "모드 선택", subtitle: "" },
  },
  mission: {
    en: { title: "Mission and Operation", subtitle: "" },
    ko: { title: "임무 및 운용", subtitle: "" },
  },
  "dtam-extensions": {
    en: { title: "DTAM Extension Modules", subtitle: "Stakeholders" },
    ko: { title: "DTAM 확장모듈", subtitle: "이해관계자" },
  },
  "dtam-modules": {
    en: { title: "System Settings", subtitle: "" },
    ko: { title: "시스템 설정", subtitle: "" },
  },
  operations: {
    en: { title: "Mission Operation", subtitle: "" },
    ko: { title: "임무 운용", subtitle: "" },
  },
  fleet: {
    en: { title: "Fleet Monitor", subtitle: "" },
    ko: { title: "비행체 모니터", subtitle: "" },
  },
  plugin: {
    en: { title: "DTAM Plugin", subtitle: "" },
    ko: { title: "DTAM 플러그인", subtitle: "" },
  },
  data: {
    en: { title: "Server Console", subtitle: "" },
    ko: { title: "서버 콘솔", subtitle: "" },
  },
  system: {
    en: { title: "System Setting", subtitle: "" },
    ko: { title: "시스템 설정", subtitle: "" },
  },
};

const MODULE_ICONS = {
  simulation: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3 18 15H6L12 3Z" />
      <path d="M12 15v6" />
      <path d="M9 18h6" />
    </svg>
  `,
  mission: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 7h14" />
      <path d="M5 12h10" />
      <path d="M5 17h8" />
      <path d="M17 8.5 20 12l-3 3.5" />
    </svg>
  `,
  "dtam-extensions": `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 4 19 8v8l-7 4-7-4V8l7-4Z" />
      <path d="M12 12 19 8" />
      <path d="M12 12v8" />
      <path d="M12 12 5 8" />
      <circle cx="12" cy="4" r="1.5" />
      <circle cx="5" cy="16" r="1.5" />
      <circle cx="19" cy="16" r="1.5" />
    </svg>
  `,
  "dtam-modules": `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 7h14" />
      <path d="M5 17h14" />
      <path d="M8 7v10" />
      <path d="M16 7v10" />
      <circle cx="8" cy="7" r="2" />
      <circle cx="16" cy="17" r="2" />
    </svg>
  `,
  operations: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 12h16" />
      <path d="M12 4v16" />
      <circle cx="12" cy="12" r="7" />
    </svg>
  `,
  fleet: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 15h16" />
      <path d="M7 11h10l3 4H4l3-4Z" />
      <circle cx="8" cy="18" r="1.5" />
      <circle cx="16" cy="18" r="1.5" />
    </svg>
  `,
  plugin: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 6h5v5H6Z" />
      <path d="M13 6h5v5h-5Z" />
      <path d="M6 13h5v5H6Z" />
      <path d="M13 13h5v5h-5Z" />
      <path d="M11 8.5h2" />
      <path d="M11 15.5h2" />
      <path d="M8.5 11v2" />
      <path d="M15.5 11v2" />
    </svg>
  `,
  data: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 6c0 1.7 3.1 3 7 3s7-1.3 7-3-3.1-3-7-3-7 1.3-7 3Z" />
      <path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6" />
      <path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
    </svg>
  `,
  system: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z" />
      <path d="M12 3v3" />
      <path d="M12 18v3" />
      <path d="M3 12h3" />
      <path d="M18 12h3" />
    </svg>
  `,
};

function hexToRgba(hex, alpha) {
  const normalized = hex.replace("#", "");
  const full = normalized.length === 3 ? normalized.split("").map((value) => value + value).join("") : normalized;
  const int = Number.parseInt(full, 16);
  const red = (int >> 16) & 255;
  const green = (int >> 8) & 255;
  const blue = int & 255;

  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

export function getModuleCopy(module, language = "en") {
  const normalizedLanguage = language === "ko" ? "ko" : "en";
  const localizedCopy = MODULE_COPY[module.slug]?.[normalizedLanguage] || MODULE_COPY[module.slug]?.en;

  return {
    title: localizedCopy?.title || module.title,
    subtitle: localizedCopy?.subtitle ?? module.subtitle,
  };
}

export function createModuleCard(module, onSelect, language = "en") {
  const copy = getModuleCopy(module, language);
  const moduleIcon = MODULE_ICONS[module.slug] || "";
  const button = document.createElement("button");
  button.type = "button";
  button.className = "module-card";
  button.dataset.slug = module.slug;
  button.setAttribute("aria-haspopup", "dialog");
  button.setAttribute("aria-label", copy.title);
  button.style.setProperty("--module-accent", module.accent);
  button.style.setProperty("--module-accent-soft", hexToRgba(module.accent, 0.22));
  button.innerHTML = `
    <span class="module-card__accent" aria-hidden="true"></span>
    <div class="module-card__content">
      <span class="module-card__icon" aria-hidden="true">${moduleIcon}</span>
      <h4 class="module-card__label">${copy.title}</h4>
      <p class="module-card__meta${copy.subtitle ? "" : " module-card__meta--empty"}">${copy.subtitle || "&nbsp;"}</p>
    </div>
  `;

  button.addEventListener("click", () => onSelect(module, button));
  return button;
}

export function setActiveCard(container, slug) {
  for (const card of container.querySelectorAll(".module-card")) {
    card.classList.toggle("is-active", card.dataset.slug === slug);
  }
}
