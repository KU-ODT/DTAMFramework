const PLUGIN_SLOTS = [
  {
    id: "psu",
    title: "PSU",
    subtitle: "Primary support unit",
    subtitleKo: "주 지원 유닛",
    accent: "#7dd3fc",
    summary: "Reserved runtime slot for PSU-side processing and operator support logic.",
    summaryKo: "PSU 측 처리와 운용자 지원 로직을 위한 예약 실행 슬롯입니다.",
    kind: "runtime",
  },
  {
    id: "uao",
    title: "UAO",
    subtitle: "Operator augmentation",
    subtitleKo: "운용자 보조",
    accent: "#8b5cf6",
    summary: "Reserved runtime slot for UAO assistance, analysis, and operator-side tooling.",
    summaryKo: "UAO 보조, 분석, 운용자 측 도구를 위한 예약 실행 슬롯입니다.",
    kind: "runtime",
  },
  {
    id: "vpo",
    title: "VPO",
    subtitle: "Visual procedure operations",
    subtitleKo: "시각 절차 운용",
    accent: "#34d399",
    summary: "Reserved runtime slot for VPO visual workflows and extended mission-side overlays.",
    summaryKo: "VPO 시각 워크플로와 임무 측 확장 오버레이를 위한 예약 실행 슬롯입니다.",
    kind: "runtime",
  },
  {
    id: "future",
    title: "Future Update",
    titleKo: "업데이트 예정",
    subtitle: "Expandable slot",
    subtitleKo: "확장 슬롯",
    accent: "#f59e0b",
    summary: "Additional plug-in box reserved for future runtime instances and later updates.",
    summaryKo: "추후 실행 인스턴스와 업데이트를 위해 예약한 추가 플러그인 박스입니다.",
    kind: "future",
  },
];

const COPY = {
  en: {
    eyebrow: "Plug-In Runtime",
    title: "Plug-In",
    summary: "Select a plug-in slot, review its reserved runtime role, and prepare the launch surface for a future external instance.",
    railLabel: "Plug-in slot selector",
    selected: "Selected slot",
    run: "Run",
    pending: "Runtime launch hookup is pending for",
    future: "This slot is reserved for a future plug-in update.",
  },
  ko: {
    eyebrow: "Plug-In Runtime",
    title: "플러그 인",
    summary: "Plug-In 슬롯을 선택하고, 역할을 확인한 뒤, 추후 별도 인스턴스를 연결할 실행 표면을 준비합니다.",
    railLabel: "플러그인 슬롯 선택",
    selected: "선택 슬롯",
    run: "실행",
    pending: "실행 연결 대기 중:",
    future: "이 슬롯은 추후 플러그인 업데이트를 위해 예약되어 있습니다.",
  },
};

function iconMarkup(slotId) {
  const icons = {
    psu: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3 18 7v10l-6 4-6-4V7l6-4Z" />
        <path d="M9 12h6" />
        <path d="M12 9v6" />
      </svg>
    `,
    uao: `
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

  return icons[slotId] || icons.future;
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
      data-plugin-card="${slot.id}"
      style="--plugin-accent: ${slot.accent};"
      aria-pressed="false"
    >
      <span class="plugin-hub__card-glow" aria-hidden="true"></span>
      <span class="plugin-hub__card-icon" aria-hidden="true">${iconMarkup(slot.id)}</span>
      <span class="plugin-hub__card-copy">
        <strong>${copy.title}</strong>
        <span>${copy.subtitle}</span>
      </span>
    </button>
  `;
}

function normalizeLanguage(language) {
  return language === "ko" ? "ko" : "en";
}

export function renderPluginWorkspace(container, language = "en") {
  const normalizedLanguage = normalizeLanguage(language);
  const copy = COPY[normalizedLanguage];
  const firstSlot = localizedSlot(PLUGIN_SLOTS[0], normalizedLanguage);
  let selectedId = PLUGIN_SLOTS[0].id;

  container.classList.remove("detail-panel--module-management", "detail-panel--icd");
  container.classList.add("detail-panel--plugin");
  container.innerHTML = `
    <section class="plugin-hub">
      <header class="plugin-hub__header">
        <p class="eyebrow">${copy.eyebrow}</p>
        <h3 id="detail-modal-title">${copy.title}</h3>
        <p class="plugin-hub__summary">${copy.summary}</p>
      </header>

      <section class="plugin-hub__rail" aria-label="${copy.railLabel}">
        <div class="plugin-hub__track" data-plugin-track>
          ${PLUGIN_SLOTS.map((slot) => slotMarkup(slot, normalizedLanguage)).join("")}
        </div>
      </section>

      <section class="plugin-hub__footer">
        <div class="plugin-hub__selection">
          <span>${copy.selected}</span>
          <strong data-plugin-selected-title>${firstSlot.title}</strong>
          <p data-plugin-selected-summary>${firstSlot.summary}</p>
        </div>
        <button type="button" class="plugin-hub__run" data-plugin-run>${copy.run}</button>
        <p class="plugin-hub__status" data-plugin-status></p>
      </section>
    </section>
  `;

  const track = container.querySelector("[data-plugin-track]");
  const cards = Array.from(container.querySelectorAll("[data-plugin-card]"));
  const selectedTitle = container.querySelector("[data-plugin-selected-title]");
  const selectedSummary = container.querySelector("[data-plugin-selected-summary]");
  const status = container.querySelector("[data-plugin-status]");
  const runButton = container.querySelector("[data-plugin-run]");

  const applySelection = (slotId, smooth = false) => {
    const slot = PLUGIN_SLOTS.find((item) => item.id === slotId) || PLUGIN_SLOTS[0];
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
      status.textContent = "";
    }
  };

  for (const card of cards) {
    card.addEventListener("click", () => {
      applySelection(card.dataset.pluginCard || PLUGIN_SLOTS[0].id, true);
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

  runButton?.addEventListener("click", () => {
    const slot = PLUGIN_SLOTS.find((item) => item.id === selectedId) || PLUGIN_SLOTS[0];
    const slotCopy = localizedSlot(slot, normalizedLanguage);
    if (!status) {
      return;
    }
    status.textContent = slot.kind === "future"
      ? copy.future
      : `${copy.pending} ${slotCopy.title}.`;
  });

  applySelection(selectedId, false);
}
