// GUI forms for DTAM ICD setup messages 1001, 1002, and 1003.
import { postJSON } from "../api/client.js";

const MESSAGE_TITLES = {
  "1001": { en: "Mode Selection", ko: "모드 선택" },
  "1002": { en: "Simulation", ko: "시뮬레이션" },
  "1003": { en: "Scenario Setting", ko: "시나리오 설정" },
};

const MODE_DETAILS = {
  single: {
    ko: {
      title: "단일 비행",
      description: "주 비행체 1대만 선택한 동역학 모델로 운용합니다.",
    },
    en: {
      title: "Single Flight",
      description: "Runs one primary aircraft with the selected dynamics model.",
    },
  },
  traffic: {
    ko: {
      title: "교통 흐름 모사",
      description: "항공 교통 시뮬레이션으로 다수의 UAM 비행 흐름을 모사합니다.",
    },
    en: {
      title: "Traffic Flow Simulation",
      description: "Simulates multiple UAM flight flows through air traffic simulation.",
    },
  },
  integrated: {
    ko: {
      title: "통합 비행 모드",
      description: "주 비행체 1대는 선택한 동역학 모델로 운용하고, 주변 UAM 비행체는 항공 교통 시뮬레이션으로 함께 모사합니다.",
    },
    en: {
      title: "Integrated Flight Mode",
      description: "Runs one primary aircraft with the selected dynamics model while surrounding UAM traffic is simulated.",
    },
  },
};

const ICONS = {
  confirm: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 12.5 9.5 17 19 7" />
    </svg>
  `,
  plus: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </svg>
  `,
  remove: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7 7 17 17" />
      <path d="M17 7 7 17" />
    </svg>
  `,
  singleMode: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3 18 15H6L12 3Z" />
      <path d="M12 15v6" />
      <path d="M9 18h6" />
    </svg>
  `,
  trafficMode: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 7h14" />
      <path d="M5 17h14" />
      <path d="M8 4v6" />
      <path d="M16 14v6" />
      <circle cx="8" cy="7" r="2.2" />
      <circle cx="16" cy="17" r="2.2" />
    </svg>
  `,
  integratedMode: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3 18 8.5 12 14 6 8.5 12 3Z" />
      <path d="M6 12.5 12 18 18 12.5" />
      <path d="M6 16.5 12 22 18 16.5" />
    </svg>
  `,
};

function icon(name) {
  return ICONS[name] || "";
}

function normalizeLanguage(language) {
  return language === "ko" ? "ko" : "en";
}

function text(ko, en, language = "en") {
  return normalizeLanguage(language) === "ko" ? ko : en;
}

function duo(ko, en, language = "en") {
  return `<span class="label-duo"><strong>${text(ko, en, language)}</strong></span>`;
}

function buttonContent(iconName, ko, en, language = "en") {
  return `
    ${icon(iconName)}
    <span class="button-label">
      <strong>${text(ko, en, language)}</strong>
    </span>
  `;
}

function messageTitle(messageId, language = "en") {
  const normalizedLanguage = normalizeLanguage(language);
  return MESSAGE_TITLES[messageId]?.[normalizedLanguage] || MESSAGE_TITLES[messageId]?.en || messageId;
}

function modeSummary(mode, language = "en") {
  const detail = MODE_DETAILS[mode]?.[normalizeLanguage(language)] || MODE_DETAILS.integrated.en;
  const iconName = `${mode}Mode`;
  return `
    <div class="mode-summary__icon" aria-hidden="true">${icon(iconName)}</div>
    <div>
      <strong>${detail.title}</strong>
      <span>${detail.description}</span>
    </div>
  `;
}

function nowIso() {
  return new Date().toISOString();
}

function compactTimestamp(date = new Date()) {
  return date.toISOString().replace(/[-:]/g, "").replace(".", "");
}

function scenarioFileName() {
  return `scenarioSetup_${compactTimestamp()}.json`;
}

function readNumber(form, name) {
  return Number.parseFloat(form.elements[name].value);
}

function readInteger(form, name) {
  return Number.parseInt(form.elements[name].value, 10);
}

function normalizeTime(value) {
  if (!value) {
    return "";
  }
  return value.length === 5 ? `${value}:00` : value;
}

function formError(errors) {
  const error = new Error(errors.join("\n"));
  error.errors = errors;
  return error;
}

function setStatus(form, state, message, details = []) {
  const status = form.querySelector("[data-send-status]");
  if (!status) {
    return;
  }

  status.className = `send-status send-status--${state}`;
  status.innerHTML = `
    <strong>${message}</strong>
    ${details.length > 0 ? `<ul>${details.map((detail) => `<li>${detail}</li>`).join("")}</ul>` : ""}
  `;
}

function updateTimestampFields(form) {
  const timestamp = nowIso();
  const timestampField = form.querySelector("[data-timestamp-field]");
  const fileNameField = form.querySelector("[data-scenario-file-field]");
  if (timestampField) {
    timestampField.value = timestamp;
  }
  if (fileNameField) {
    fileNameField.value = scenarioFileName();
  }
}

function icdShell(messageId, body, language = "en") {
  const normalizedLanguage = normalizeLanguage(language);
  const title = messageTitle(messageId, normalizedLanguage);

  return `
    <section class="icd-workspace">
      <header class="icd-header">
        <div>
          <p class="icd-kicker">${text("설정 항목", "DTAM ICD Setup", normalizedLanguage)}</p>
          <h3 id="detail-modal-title">${title}</h3>
        </div>
        <div class="icd-badge" aria-label="ICD message ${messageId}">
          <span>ICD</span>
          <strong>${messageId}</strong>
        </div>
      </header>
      ${body}
    </section>
  `;
}

function bindSliderPair(form, name) {
  const slider = form.elements[`${name}Slider`];
  const number = form.elements[name];
  if (!slider || !number) {
    return;
  }

  slider.addEventListener("input", () => {
    number.value = slider.value;
  });
  number.addEventListener("input", () => {
    slider.value = number.value;
  });
}

function bindSubmit(form, messageId, buildPayload, language = "en") {
  const normalizedLanguage = normalizeLanguage(language);
  const title = messageTitle(messageId, normalizedLanguage);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    updateTimestampFields(form);

    const submitButton = form.querySelector("[type='submit']");
    submitButton.disabled = true;
    submitButton.innerHTML = buttonContent("confirm", "처리 중", "Working", normalizedLanguage);
    setStatus(form, "pending", text("설정을 확정하는 중입니다.", "Confirming settings.", normalizedLanguage));

    try {
      const payload = buildPayload(form);
      const result = await postJSON(`/api/v1/icd/${messageId}/send`, { payload });
      if (result.sent) {
        setStatus(form, "success", text(`${title} 확정 완료`, `${title} confirmed.`, normalizedLanguage));
      } else {
        setStatus(form, "error", text("확정 실패", "Confirm failed.", normalizedLanguage), result.errors);
      }
    } catch (error) {
      setStatus(form, "error", text("확정 실패", "Confirm failed.", normalizedLanguage), error.errors || [error.message]);
    } finally {
      submitButton.disabled = false;
      submitButton.innerHTML = buttonContent("confirm", "확정", "Confirm", normalizedLanguage);
    }
  });
}

function segmented(name, options, selected, language = "en", variantClass = "") {
  const className = ["segmented-control", variantClass].filter(Boolean).join(" ");
  return `
    <div class="${className}">
      ${options
        .map(
          (option) => `
            <label>
              <input type="radio" name="${name}" value="${option.value}" ${option.value === selected ? "checked" : ""} />
              <span>
                ${option.icon ? `<span class="segmented-option-icon">${icon(option.icon)}</span>` : ""}
                ${option.ko && option.en ? duo(option.ko, option.en, language) : option.label}
              </span>
            </label>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderForm(container, html, setup) {
  container.classList.add("detail-panel--icd");
  container.innerHTML = html;
  const form = container.querySelector("form");
  updateTimestampFields(form);
  setup(form);
}

function modeSetupPayload(form) {
  const mode = form.elements.operationMode.value;
  const payload = {
    timestamp: form.elements.timestamp.value,
    operationMode: mode,
  };

  if (mode !== "traffic") {
    payload.singleFlight = {
      vehicleSimType: {
        dynamics: form.elements.dynamics.value,
        mainVehicleController: form.elements.mainVehicleController.value,
      },
    };
  }

  if (mode !== "single") {
    payload.traffic = {
      trafficScenario: form.elements.trafficScenario.value,
    };
  }

  return payload;
}

export function renderModeSetupForm(container, language = "en") {
  const normalizedLanguage = normalizeLanguage(language);

  renderForm(
    container,
    icdShell(
      "1001",
      `
        <form class="icd-form icd-form--mode">
          <input data-timestamp-field name="timestamp" type="hidden" />

          <section class="mode-summary mode-summary--integrated form-section--full" data-mode-summary>
            ${modeSummary("integrated", normalizedLanguage)}
          </section>

          <div class="form-section form-section--full">
            <div class="field-heading">
              ${duo("운용 모드", "Operation mode", normalizedLanguage)}
              <small>${text("운용 범위를 선택하세요.", "Choose the operating scope.", normalizedLanguage)}</small>
            </div>
            ${segmented(
              "operationMode",
              [
                { value: "single", ko: "단일 비행", en: "Single Flight", icon: "singleMode" },
                { value: "traffic", ko: "교통 흐름 모사", en: "Traffic Flow Simulation", icon: "trafficMode" },
                { value: "integrated", ko: "통합 비행 모드", en: "Integrated Flight Mode", icon: "integratedMode" },
              ],
              "integrated",
              normalizedLanguage,
              "segmented-control--mode",
            )}
          </div>

          <div class="icd-card" data-single-section>
            <div class="field-heading">
              ${duo("비행체 시뮬레이션", "Vehicle simulation", normalizedLanguage)}
              <small>${text("주 비행체 모델을 지정합니다.", "Select the primary aircraft model.", normalizedLanguage)}</small>
            </div>
            <label class="form-label">
              ${duo("동역학 모델", "Dynamics model", normalizedLanguage)}
              <select name="dynamics">
                <option value="simple">${text("기본", "Simple", normalizedLanguage)}</option>
                <option value="multirotor">${text("멀티로터", "Multirotor", normalizedLanguage)}</option>
                <option value="highFidelity">${text("고정밀", "High Fidelity", normalizedLanguage)}</option>
              </select>
            </label>
            <div>
              <span class="form-label-title">${duo("비행체 제어방식", "Aircraft controller", normalizedLanguage)}</span>
              ${segmented(
                "mainVehicleController",
                [
                  { value: "Joystick", label: "Joystick" },
                  { value: "Keyboard", label: "Keyboard" },
                  { value: "Autopilot", label: "Autopilot" },
                ],
                "Autopilot",
                normalizedLanguage,
              )}
            </div>
          </div>

          <div class="icd-card" data-traffic-section>
            <div class="field-heading">
              ${duo("교통 시나리오", "Traffic scenario", normalizedLanguage)}
              <small>${text("배경 교통 밀도를 지정합니다.", "Set the background traffic density.", normalizedLanguage)}</small>
            </div>
            <label class="form-label">
              ${duo("교통 밀도", "Traffic density", normalizedLanguage)}
              <select name="trafficScenario">
                <option value="low">${text("낮음", "Low", normalizedLanguage)}</option>
                <option value="middle">${text("보통", "Middle", normalizedLanguage)}</option>
                <option value="high">${text("높음", "High", normalizedLanguage)}</option>
                <option value="customed">${text("사용자 정의", "Custom", normalizedLanguage)}</option>
              </select>
            </label>
          </div>

          <div class="send-status send-status--idle" data-send-status>
            <strong>${text("설정값을 확인한 뒤 확정하세요.", "Review settings, then confirm.", normalizedLanguage)}</strong>
          </div>
          <footer class="icd-actions">
            <button class="primary-button" type="submit">${buttonContent("confirm", "확정", "Confirm", normalizedLanguage)}</button>
          </footer>
        </form>
      `,
      normalizedLanguage,
    ),
    (form) => {
      const summary = form.querySelector("[data-mode-summary]");
      const updateVisibility = () => {
        const mode = form.elements.operationMode.value;
        form.querySelector("[data-single-section]").hidden = mode === "traffic";
        form.querySelector("[data-traffic-section]").hidden = mode === "single";
        if (summary) {
          summary.className = `mode-summary mode-summary--${mode} form-section--full`;
          summary.innerHTML = modeSummary(mode, normalizedLanguage);
        }
      };
      form.addEventListener("change", (event) => {
        if (event.target.name === "operationMode") {
          updateVisibility();
        }
      });
      updateVisibility();
      bindSubmit(form, "1001", modeSetupPayload, normalizedLanguage);
    },
  );
}

function simulationSetupPayload(form) {
  const precipitationType = form.elements.precipitationType.value;
  const precipitationIntensity = precipitationType === "none" ? 0 : readNumber(form, "precipitationIntensity");
  const payload = {
    timestamp: form.elements.timestamp.value,
    playbackSpeed: readInteger(form, "playbackSpeed"),
    playState: form.elements.playState.value,
    weatherEffect: {
      precipitation: {
        type: precipitationType,
        intensity: precipitationIntensity,
      },
      fog: {
        intensity: readNumber(form, "fogIntensity"),
      },
    },
    wind: {
      grade: form.elements.windGrade.value,
    },
  };

  if (form.elements.gustEnabled.checked) {
    payload.wind.gust = {
      lat: readNumber(form, "gustLat"),
      lon: readNumber(form, "gustLon"),
      radius: readNumber(form, "gustRadius"),
    };
  }

  return payload;
}

export function renderSimulationSetupForm(container, language = "en") {
  const normalizedLanguage = normalizeLanguage(language);

  renderForm(
    container,
    icdShell(
      "1002",
      `
        <form class="icd-form icd-form--simulation">
          <input data-timestamp-field name="timestamp" type="hidden" />

          <div class="icd-card">
            <div class="field-heading">
              ${duo("재생 제어", "Playback", normalizedLanguage)}
              <small>${text("시뮬레이션 진행 상태를 지정합니다.", "Set the simulation playback state.", normalizedLanguage)}</small>
            </div>
            <div class="form-row">
              <div>
                <span class="form-label-title">${duo("배속", "Speed", normalizedLanguage)}</span>
                ${segmented(
                  "playbackSpeed",
                  [
                    { value: "1", label: "1x" },
                    { value: "2", label: "2x" },
                    { value: "4", label: "4x" },
                    { value: "8", label: "8x" },
                  ],
                  "1",
                  normalizedLanguage,
                )}
              </div>
              <div>
                <span class="form-label-title">${duo("상태", "State", normalizedLanguage)}</span>
                ${segmented(
                  "playState",
                  [
                    { value: "play", ko: "재생", en: "Play" },
                    { value: "pause", ko: "정지", en: "Pause" },
                    { value: "reset", ko: "초기화", en: "Reset" },
                  ],
                  "play",
                  normalizedLanguage,
                )}
              </div>
            </div>
          </div>

          <div class="icd-card">
            <div class="field-heading">
              ${duo("기상 효과", "Weather", normalizedLanguage)}
              <small>${text("강수와 안개 조건을 지정합니다.", "Set precipitation and fog.", normalizedLanguage)}</small>
            </div>
            <label class="form-label">
              ${duo("강수 유형", "Precipitation", normalizedLanguage)}
              <select name="precipitationType">
                <option value="none">${text("없음", "None", normalizedLanguage)}</option>
                <option value="rainy">${text("비", "Rainy", normalizedLanguage)}</option>
                <option value="snow">${text("눈", "Snow", normalizedLanguage)}</option>
              </select>
            </label>
            <label class="range-field">
              ${duo("강수 강도", "Precipitation intensity", normalizedLanguage)}
              <input name="precipitationIntensitySlider" type="range" min="0" max="1" step="0.1" value="0" />
              <input name="precipitationIntensity" type="number" min="0" max="1" step="0.1" value="0" />
            </label>
            <label class="range-field">
              ${duo("안개 강도", "Fog intensity", normalizedLanguage)}
              <input name="fogIntensitySlider" type="range" min="0" max="1" step="0.1" value="0" />
              <input name="fogIntensity" type="number" min="0" max="1" step="0.1" value="0" />
            </label>
          </div>

          <div class="icd-card">
            <div class="field-heading">
              ${duo("바람", "Wind", normalizedLanguage)}
              <small>${text("바람 등급과 돌풍 영역을 지정합니다.", "Set wind grade and gust area.", normalizedLanguage)}</small>
            </div>
            <div>
              <span class="form-label-title">${duo("바람 등급", "Wind grade", normalizedLanguage)}</span>
              ${segmented(
                "windGrade",
                [
                  { value: "normal", ko: "일반", en: "Normal" },
                  { value: "warning", ko: "주의", en: "Warning" },
                  { value: "serious", ko: "심각", en: "Serious" },
                ],
                "normal",
                normalizedLanguage,
              )}
            </div>
            <label class="switch-field">
              <input name="gustEnabled" type="checkbox" />
              <span class="switch-toggle"></span>
              ${duo("돌풍 영역 사용", "Enable gust area", normalizedLanguage)}
            </label>
            <div class="gust-grid" data-gust-panel hidden>
              <label class="form-label">
                ${duo("위도", "Latitude", normalizedLanguage)}
                <input name="gustLat" type="number" min="-90" max="90" step="0.000001" value="37.540000" />
              </label>
              <label class="form-label">
                ${duo("경도", "Longitude", normalizedLanguage)}
                <input name="gustLon" type="number" min="-180" max="180" step="0.000001" value="127.080000" />
              </label>
              <label class="form-label">
                ${duo("반경 (m)", "Radius", normalizedLanguage)}
                <input name="gustRadius" type="number" min="0" max="50000" step="1" value="500" />
              </label>
            </div>
          </div>

          <div class="send-status send-status--idle" data-send-status>
            <strong>${text("설정값을 확인한 뒤 확정하세요.", "Review settings, then confirm.", normalizedLanguage)}</strong>
          </div>
          <footer class="icd-actions">
            <button class="primary-button" type="submit">${buttonContent("confirm", "확정", "Confirm", normalizedLanguage)}</button>
          </footer>
        </form>
      `,
      normalizedLanguage,
    ),
    (form) => {
      bindSliderPair(form, "precipitationIntensity");
      bindSliderPair(form, "fogIntensity");

      const updatePrecipitation = () => {
        const disabled = form.elements.precipitationType.value === "none";
        form.elements.precipitationIntensity.disabled = disabled;
        form.elements.precipitationIntensitySlider.disabled = disabled;
        if (disabled) {
          form.elements.precipitationIntensity.value = "0";
          form.elements.precipitationIntensitySlider.value = "0";
        }
      };
      const updateGust = () => {
        form.querySelector("[data-gust-panel]").hidden = !form.elements.gustEnabled.checked;
      };

      form.elements.precipitationType.addEventListener("change", updatePrecipitation);
      form.elements.gustEnabled.addEventListener("change", updateGust);
      updatePrecipitation();
      updateGust();
      bindSubmit(form, "1002", simulationSetupPayload, normalizedLanguage);
    },
  );
}

function vertiportCard(data = {}, language = "en") {
  const normalizedLanguage = normalizeLanguage(language);

  return `
    <article class="repeat-card" data-vertiport>
      <button class="icon-button" type="button" data-remove-vertiport aria-label="${text("버티포트 삭제", "Remove vertiport", normalizedLanguage)}">
        ${icon("remove")}
        <span class="sr-only">${text("버티포트 삭제", "Remove vertiport", normalizedLanguage)}</span>
      </button>
      <div class="repeat-grid repeat-grid--vertiport">
        <label class="form-label">
          ${duo("이름", "Name", normalizedLanguage)}
          <input name="vertiportName" type="text" required value="${data.name || ""}" />
        </label>
        <label class="form-label">
          ${duo("분류", "Class", normalizedLanguage)}
          <select name="vertiportClass">
            <option value="port" ${data.class === "port" ? "selected" : ""}>${text("포트", "Port", normalizedLanguage)}</option>
            <option value="hub" ${data.class === "hub" ? "selected" : ""}>${text("허브", "Hub", normalizedLanguage)}</option>
          </select>
        </label>
        <label class="form-label">
          ${duo("위도", "Latitude", normalizedLanguage)}
          <input name="vertiportLat" type="number" min="-90" max="90" step="0.000001" required value="${data.lat ?? "37.540000"}" />
        </label>
        <label class="form-label">
          ${duo("경도", "Longitude", normalizedLanguage)}
          <input name="vertiportLon" type="number" min="-180" max="180" step="0.000001" required value="${data.lon ?? "127.080000"}" />
        </label>
        <label class="form-label">
          ${duo("방향각", "Angle", normalizedLanguage)}
          <input name="vertiportAngle" type="number" min="0" max="360" step="0.1" required value="${data.angleDegrees ?? "0"}" />
        </label>
      </div>
    </article>
  `;
}

function waypointCard(data = {}, language = "en") {
  const normalizedLanguage = normalizeLanguage(language);

  return `
    <article class="repeat-card" data-waypoint>
      <button class="icon-button" type="button" data-remove-waypoint aria-label="${text("웨이포인트 삭제", "Remove waypoint", normalizedLanguage)}">
        ${icon("remove")}
        <span class="sr-only">${text("웨이포인트 삭제", "Remove waypoint", normalizedLanguage)}</span>
      </button>
      <div class="repeat-grid repeat-grid--waypoint">
        <label class="form-label">
          <span>ID</span>
          <input name="waypointId" type="text" pattern="[A-Za-z0-9_-]{1,32}" required value="${data.waypointId || ""}" />
        </label>
        <label class="form-label">
          ${duo("이름", "Name", normalizedLanguage)}
          <input name="waypointName" type="text" required value="${data.waypointName || ""}" />
        </label>
        <label class="form-label">
          ${duo("위도", "Latitude", normalizedLanguage)}
          <input name="waypointLat" type="number" min="-90" max="90" step="0.000001" required value="${data.lat ?? "37.540000"}" />
        </label>
        <label class="form-label">
          ${duo("경도", "Longitude", normalizedLanguage)}
          <input name="waypointLon" type="number" min="-180" max="180" step="0.000001" required value="${data.lon ?? "127.080000"}" />
        </label>
        <label class="form-label">
          ${duo("고도 (ft)", "Altitude", normalizedLanguage)}
          <input name="waypointAltFt" type="number" min="0" max="60000" step="1" required value="${data.altFt ?? "500"}" />
        </label>
        <label class="form-label">
          ${duo("연결", "Links", normalizedLanguage)}
          <select name="waypointLinks" data-wp-links data-selected="${(data.links || []).join(",")}" multiple required></select>
        </label>
      </div>
    </article>
  `;
}

function updateRemoveButtons(form) {
  const vertiports = form.querySelectorAll("[data-vertiport]");
  const waypoints = form.querySelectorAll("[data-waypoint]");
  vertiports.forEach((card) => {
    card.querySelector("[data-remove-vertiport]").disabled = vertiports.length <= 1;
  });
  waypoints.forEach((card) => {
    card.querySelector("[data-remove-waypoint]").disabled = waypoints.length <= 2;
  });
}

function selectedValues(select) {
  return Array.from(select.selectedOptions).map((option) => option.value);
}

function updateWaypointLinkOptions(form) {
  const waypointCards = Array.from(form.querySelectorAll("[data-waypoint]"));
  const ids = waypointCards.map((card) => card.querySelector("[name='waypointId']").value.trim()).filter(Boolean);

  waypointCards.forEach((card) => {
    const selfId = card.querySelector("[name='waypointId']").value.trim();
    const select = card.querySelector("[data-wp-links]");
    const previous = new Set((select.dataset.selected || selectedValues(select).join(",")).split(",").filter(Boolean));
    const options = ids.filter((id) => id && id !== selfId);
    if (previous.size === 0 && options.length > 0) {
      previous.add(options[0]);
    }
    select.innerHTML = options
      .map((id) => `<option value="${id}" ${previous.has(id) ? "selected" : ""}>${id}</option>`)
      .join("");
    select.dataset.selected = selectedValues(select).join(",");
  });
}

function collectScenario(form) {
  const errors = [];
  const vertiportNames = new Set();
  const waypointIds = new Set();

  const startTime = normalizeTime(form.elements.startTime.value);
  const endTime = normalizeTime(form.elements.endTime.value);
  if (!startTime || !endTime || startTime >= endTime) {
    errors.push("Operation start time must be earlier than end time.");
  }

  const vertiports = Array.from(form.querySelectorAll("[data-vertiport]")).map((card, index) => {
    const name = card.querySelector("[name='vertiportName']").value.trim();
    if (!name) {
      errors.push(`Vertiport ${index + 1} needs a name.`);
    } else if (vertiportNames.has(name)) {
      errors.push(`Vertiport name is duplicated: ${name}.`);
    }
    vertiportNames.add(name);
    return {
      name,
      class: card.querySelector("[name='vertiportClass']").value,
      lat: Number.parseFloat(card.querySelector("[name='vertiportLat']").value),
      lon: Number.parseFloat(card.querySelector("[name='vertiportLon']").value),
      angleDegrees: Number.parseFloat(card.querySelector("[name='vertiportAngle']").value),
    };
  });

  const waypointCards = Array.from(form.querySelectorAll("[data-waypoint]"));
  const waypoints = waypointCards.map((card, index) => {
    const waypointId = card.querySelector("[name='waypointId']").value.trim();
    const links = selectedValues(card.querySelector("[data-wp-links]"));
    if (!waypointId) {
      errors.push(`Waypoint ${index + 1} needs an ID.`);
    } else if (waypointIds.has(waypointId)) {
      errors.push(`Waypoint ID is duplicated: ${waypointId}.`);
    }
    if (links.length === 0) {
      errors.push(`Waypoint ${waypointId || index + 1} needs at least one link.`);
    }
    waypointIds.add(waypointId);
    return {
      waypointId,
      waypointName: card.querySelector("[name='waypointName']").value.trim(),
      lat: Number.parseFloat(card.querySelector("[name='waypointLat']").value),
      lon: Number.parseFloat(card.querySelector("[name='waypointLon']").value),
      altFt: Number.parseFloat(card.querySelector("[name='waypointAltFt']").value),
      links,
    };
  });

  for (const waypoint of waypoints) {
    for (const link of waypoint.links) {
      if (link === waypoint.waypointId) {
        errors.push(`${waypoint.waypointId} cannot link to itself.`);
      }
      if (!waypointIds.has(link)) {
        errors.push(`${waypoint.waypointId} links to an unknown waypoint: ${link}.`);
      }
    }
  }

  if (errors.length > 0) {
    throw formError(errors);
  }

  return {
    timestamp: form.elements.timestamp.value,
    scenarioFileName: form.elements.scenarioFileName.value,
    totalAircraftCount: readInteger(form, "totalAircraftCount"),
    mainVehicleType: form.elements.mainVehicleType.value,
    operationTime: {
      startTime,
      endTime,
    },
    vertiports,
    routeNetwork: {
      waypoints,
    },
  };
}

export function renderScenarioSetupForm(container, language = "en") {
  const normalizedLanguage = normalizeLanguage(language);

  renderForm(
    container,
    icdShell(
      "1003",
      `
        <form class="icd-form icd-form--scenario">
          <input data-timestamp-field name="timestamp" type="hidden" />

          <div class="form-section form-section--full">
            <label class="form-label">
              ${duo("시나리오 파일", "Scenario file", normalizedLanguage)}
              <input data-scenario-file-field name="scenarioFileName" type="text" readonly />
            </label>
          </div>

          <div class="icd-card">
            <div class="field-heading">
              ${duo("운용 시간", "Operation window", normalizedLanguage)}
              <small>${text("시간 범위와 주 비행체를 지정합니다.", "Set the time window and main aircraft.", normalizedLanguage)}</small>
            </div>
            <div class="form-row form-row--four">
              <label class="form-label">
                ${duo("시작", "Start", normalizedLanguage)}
                <input name="startTime" type="time" step="1" value="09:00:00" required />
              </label>
              <label class="form-label">
                ${duo("종료", "End", normalizedLanguage)}
                <input name="endTime" type="time" step="1" value="10:00:00" required />
              </label>
              <label class="form-label">
                ${duo("비행체 수", "Aircraft count", normalizedLanguage)}
                <input name="totalAircraftCount" type="number" min="1" max="100000" step="1" value="1" required />
              </label>
              <label class="form-label">
                ${duo("비행체 유형", "Vehicle type", normalizedLanguage)}
                <select name="mainVehicleType">
                  <option value="KP2A">KP2A</option>
                  <option value="JobyS4">JobyS4</option>
                </select>
              </label>
            </div>
          </div>

          <div class="icd-card">
            <div class="repeat-header">
              <div class="field-heading">
                ${duo("버티포트", "Vertiports", normalizedLanguage)}
                <small>${text("중복 없는 이름이 필요합니다.", "Names must be unique.", normalizedLanguage)}</small>
              </div>
              <button class="ghost-button" type="button" data-add-vertiport>${buttonContent("plus", "버티포트 추가", "Add Vertiport", normalizedLanguage)}</button>
            </div>
            <div class="repeat-list" data-vertiport-list>
              ${vertiportCard({ name: "VP_A", class: "port", lat: "37.540000", lon: "127.080000", angleDegrees: "0" }, normalizedLanguage)}
            </div>
          </div>

          <div class="icd-card">
            <div class="repeat-header">
              <div class="field-heading">
                ${duo("경로 웨이포인트", "Route waypoints", normalizedLanguage)}
                <small>${text("ID를 연결 대상으로 사용합니다.", "Waypoint IDs are used for links.", normalizedLanguage)}</small>
              </div>
              <button class="ghost-button" type="button" data-add-waypoint>${buttonContent("plus", "웨이포인트 추가", "Add Waypoint", normalizedLanguage)}</button>
            </div>
            <div class="repeat-list" data-waypoint-list>
              ${waypointCard({ waypointId: "WP1", waypointName: "Waypoint 1", lat: "37.540000", lon: "127.080000", altFt: "500", links: ["WP2"] }, normalizedLanguage)}
              ${waypointCard({ waypointId: "WP2", waypointName: "Waypoint 2", lat: "37.545000", lon: "127.090000", altFt: "500", links: ["WP1"] }, normalizedLanguage)}
            </div>
          </div>

          <div class="send-status send-status--idle" data-send-status>
            <strong>${text("설정값을 확인한 뒤 확정하세요.", "Review settings, then confirm.", normalizedLanguage)}</strong>
          </div>
          <footer class="icd-actions">
            <button class="primary-button" type="submit">${buttonContent("confirm", "확정", "Confirm", normalizedLanguage)}</button>
          </footer>
        </form>
      `,
      normalizedLanguage,
    ),
    (form) => {
      const addVertiport = () => {
        const next = form.querySelectorAll("[data-vertiport]").length + 1;
        form.querySelector("[data-vertiport-list]").insertAdjacentHTML(
          "beforeend",
          vertiportCard({ name: `VP_${next}`, class: "port", lat: "37.540000", lon: "127.080000", angleDegrees: "0" }, normalizedLanguage),
        );
        updateRemoveButtons(form);
      };
      const addWaypoint = () => {
        const next = form.querySelectorAll("[data-waypoint]").length + 1;
        form.querySelector("[data-waypoint-list]").insertAdjacentHTML(
          "beforeend",
          waypointCard({
            waypointId: `WP${next}`,
            waypointName: `Waypoint ${next}`,
            lat: "37.540000",
            lon: "127.080000",
            altFt: "500",
            links: ["WP1"],
          }, normalizedLanguage),
        );
        updateWaypointLinkOptions(form);
        updateRemoveButtons(form);
      };

      form.addEventListener("click", (event) => {
        if (event.target.closest("[data-add-vertiport]")) {
          addVertiport();
        }
        if (event.target.closest("[data-add-waypoint]")) {
          addWaypoint();
        }
        const removeVertiport = event.target.closest("[data-remove-vertiport]");
        if (removeVertiport) {
          removeVertiport.closest("[data-vertiport]").remove();
          updateRemoveButtons(form);
        }
        const removeWaypoint = event.target.closest("[data-remove-waypoint]");
        if (removeWaypoint) {
          removeWaypoint.closest("[data-waypoint]").remove();
          updateWaypointLinkOptions(form);
          updateRemoveButtons(form);
        }
      });

      form.addEventListener("input", (event) => {
        if (event.target.name === "waypointId") {
          updateWaypointLinkOptions(form);
        }
      });
      form.addEventListener("change", (event) => {
        if (event.target.matches("[data-wp-links]")) {
          event.target.dataset.selected = selectedValues(event.target).join(",");
        }
      });

      updateWaypointLinkOptions(form);
      updateRemoveButtons(form);
      bindSubmit(form, "1003", collectScenario, normalizedLanguage);
    },
  );
}
