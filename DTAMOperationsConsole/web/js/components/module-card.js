// Module card renderer used by the dashboard button dock.

const MODULE_COPY = {
  simulation: {
    en: { title: "Mode Selection", subtitle: "" },
    ko: { title: "모드 선택", subtitle: "" },
  },
  mission: {
    en: { title: "Simulation Ops", subtitle: "" },
    ko: { title: "시뮬레이션 운용", subtitle: "" },
  },
  "dtam-modules": {
    en: { title: "DTAM Module Management", subtitle: "" },
    ko: { title: "DTAM 모듈 관리", subtitle: "" },
  },
  operations: {
    en: { title: "Mission Operation", subtitle: "" },
    ko: { title: "임무 운용", subtitle: "" },
  },
  fleet: {
    en: { title: "Fleet Monitor", subtitle: "" },
    ko: { title: "기체 모니터", subtitle: "" },
  },
  airspace: {
    en: { title: "Airspace Control", subtitle: "" },
    ko: { title: "공역 제어", subtitle: "" },
  },
  data: {
    en: { title: "Data Console", subtitle: "" },
    ko: { title: "데이터 콘솔", subtitle: "" },
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
      <path d="M8 5v14l11-7-11-7Z" />
      <path d="M4 5v14" />
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
  airspace: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 19 20 5" />
      <path d="M8 5h12v12" />
      <path d="M5 12h6" />
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
      ${copy.subtitle ? `<p class="module-card__meta">${copy.subtitle}</p>` : ""}
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
