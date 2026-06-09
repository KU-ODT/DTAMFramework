(() => {
  const $ = (id) => document.getElementById(id);

  const targetIp = $("targetIp");
  const wsPort = $("wsPort");
  const applyPublisher = $("applyPublisher");
  const publisherStatus = $("publisherStatus");
  const controlMode = $("controlMode");
  const manualVehicleId = $("manualVehicleId");
  const manualLat = $("manualLat");
  const manualLon = $("manualLon");
  const manualAlt = $("manualAlt");
  const airsimVehicleName = $("airsimVehicleName");
  const refreshVehicles = $("refreshVehicles");
  const applyManualConfig = $("applyManualConfig");
  const activateKeyboard = $("activateKeyboard");
  const activateJoystick = $("activateJoystick");
  const releaseKeyboard = $("releaseKeyboard");
  const visualizationStatus = $("visualizationStatus");
  const controlStatus = $("controlStatus");
  const manualActuatorStatus = $("manualActuatorStatus");
  const manualSensorStatus = $("manualSensorStatus");
  const axisRoll = $("axisRoll");
  const axisPitch = $("axisPitch");
  const axisYaw = $("axisYaw");
  const axisThrottle = $("axisThrottle");
  const planFiles = $("planFiles");
  const uploadPlans = $("uploadPlans");
  const clearPlans = $("clearPlans");
  const planList = $("planList");
  const clockMode = $("clockMode");
  const hms = $("hms");
  const feedTime = $("feedTime");
  const stepOnce = $("stepOnce");
  const startService = $("startService");
  const stopService = $("stopService");
  const serviceStatus = $("serviceStatus");
  const fleetBody = $("fleetBody");
  const rxStatus = $("rxStatus");

  let dirtyPublisher = false;
  let manualCapture = false;
  let manualCaptureSource = "";
  let manualCaptureKind = "";
  let visualizationState = {
    reachable: false,
    connected: false,
    selected_vehicle_id: "",
    selected_airsim_vehicle: "",
    suggested_airsim_vehicle: "",
    vehicle_map: {},
    vehicles: [],
    error: "",
  };
  const pressed = new Set();

  [targetIp, wsPort].forEach((el) => {
    el?.addEventListener("input", () => {
      dirtyPublisher = true;
    });
  });

  manualVehicleId.addEventListener("change", () => {
    syncVehicleSelectionFromManual(manualVehicleId.value.trim());
  });

  function updateCaptureButtons() {
    const selectedMode = controlMode.value;
    activateKeyboard.classList.toggle("is-active", manualCapture && manualCaptureKind === "keyboard");
    activateJoystick.classList.toggle("is-active", manualCapture && manualCaptureKind === "joystick");
    activateKeyboard.disabled = manualCapture && manualCaptureKind === "joystick";
    activateJoystick.disabled = manualCapture && manualCaptureKind === "keyboard";
    releaseKeyboard.textContent = selectedMode === "joystick" ? "Release Joystick" : "Release";
  }

  async function api(path, { method = "GET", body } = {}) {
    const response = await fetch(path, {
      method,
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) {
      let detail = response.statusText;
      try {
        const payload = await response.json();
        detail = payload.detail || detail;
      } catch {}
      throw new Error(detail);
    }
    return response.json();
  }

  const yesNo = (value) => (value ? "yes" : "no");
  const stateLabel = {
    waiting: "waiting",
    active: "active",
    completed: "completed",
    error: "error",
  };

  function renderStatus(status) {
    const serverUrl = status.server_url || `ws://${status.target_ip || "127.0.0.1"}:${status.ws_port || 8096}/ws/dtam`;
    publisherStatus.textContent =
      `${serverUrl}  connected=${yesNo(status.publisher_connected)}`
      + (status.publisher_error ? `  error=${status.publisher_error}` : "");

    serviceStatus.textContent =
      `control=${status.control_mode}  dynamics=${status.dynamics_model}  `
      + `clock=${status.clock_mode}  running=${yesNo(status.running)}  `
      + `time=${status.sim_time_hms} (${Number(status.sim_time_s || 0).toFixed(2)}s)`;

    const manual = status.manual || {};
    const keyboardCaptureStatus = status.keyboard_capture || {};
    const joystickCaptureStatus = status.joystick_capture || {};
    const activeCapture = joystickCaptureStatus.active
      ? { ...joystickCaptureStatus, kind: "joystick" }
      : (keyboardCaptureStatus.active ? { ...keyboardCaptureStatus, kind: "keyboard" } : null);

    if (activeCapture) {
      setManualCapture(true, activeCapture.source || activeCapture.kind, activeCapture.kind);
      if (manual.input) {
        renderAxes({
          roll: clampAxis(manual.input.roll),
          pitch: clampAxis(manual.input.pitch),
          yaw: clampAxis(manual.input.yaw),
          throttle: clampAxis(manual.input.throttle),
        });
      }
    } else if (manualCaptureKind === "joystick" || manualCaptureSource === "windows-global") {
      setManualCapture(false, "", "");
    }
    const origin = manual.origin || {};
    const position = manual.position || {};
    const actuator = manual.actuator || {};
    const propulsion = manual.propulsion || {};
    const gps = manual.gps || {};
    const imu = manual.imu || {};
    const imuAngular = imu.angular_velocity || {};
    const imuLinear = imu.linear_acceleration || {};
    const barometer = manual.barometer || {};
    const motorRpm = Array.isArray(propulsion.motor_rpm) ? propulsion.motor_rpm : [];
    controlStatus.textContent =
      `manual=${manual.vehicle_id || "-"}  `
      + `origin=${fmtNum(origin.origin_lat, 6)}/${fmtNum(origin.origin_lon, 6)}/${fmtNum(origin.origin_alt_m, 1)}  `
      + `ned=${fmtNum(position.north, 1)}/${fmtNum(position.east, 1)}/${fmtNum(position.down, 1)}  `
      + `heading=${fmtNum(manual.heading_deg, 1)}  `
      + `capture=${activeCapture ? `${activeCapture.kind}:${activeCapture.source || "unknown"}` : "off"}`
      + ((activeCapture?.device_name) ? `  device=${activeCapture.device_name}` : "")
      + ((joystickCaptureStatus.last_error || keyboardCaptureStatus.last_error)
        ? `  capture_error=${joystickCaptureStatus.last_error || keyboardCaptureStatus.last_error}`
        : "");
    manualActuatorStatus.textContent =
      `actuator=tilt(${fmtNum(actuator.tilt_left, 2)}/${fmtNum(actuator.tilt_right, 2)})  `
      + `aileron=${fmtNum(actuator.aileron, 1)}  `
      + `rudder=${fmtNum(actuator.rudder_left, 1)}/${fmtNum(actuator.rudder_right, 1)}  `
      + `rpm=${motorRpm.length ? motorRpm.map((value) => fmtNum(value, 0)).join("/") : "-"}`;
    manualSensorStatus.textContent =
      `gps_vel=${fmtNum(gps.velocity_north, 2)}/${fmtNum(gps.velocity_east, 2)}/${fmtNum(gps.velocity_down, 2)}  `
      + `imu_w=${fmtNum(imuAngular.x, 2)}/${fmtNum(imuAngular.y, 2)}/${fmtNum(imuAngular.z, 2)}  `
      + `imu_a=${fmtNum(imuLinear.x, 2)}/${fmtNum(imuLinear.y, 2)}/${fmtNum(imuLinear.z, 2)}  `
      + `baro=${fmtNum(barometer.altitude, 1)}m ${fmtNum(barometer.pressure, 0)}Pa`;

    startService.disabled = !!status.running;
    stopService.disabled = !status.running;
    updateCaptureButtons();

    rxStatus.innerHTML =
      `3001=${status.rx_3001_count ?? 0} <code>${escapeHtml(status.last_rx_3001 || "-")}</code><br>`
      + `0003=${status.rx_0003_count ?? 0} <code>${escapeHtml(status.last_rx_0003 || "-")}</code><br>`
      + `2002=${status.rx_2002_count ?? 0} <code>${escapeHtml(status.last_rx_2002 || "-")}</code>`;

    if (!dirtyPublisher) {
      targetIp.value = status.target_ip;
      wsPort.value = status.ws_port || 8096;
    }
    if (controlMode.value !== status.control_mode && document.activeElement !== controlMode) {
      controlMode.value = status.control_mode || "mission";
    }
    if (clockMode.value !== status.clock_mode && document.activeElement !== clockMode) {
      clockMode.value = status.clock_mode || "external";
    }
    if (manual.vehicle_id && document.activeElement !== manualVehicleId) {
      manualVehicleId.value = manual.vehicle_id;
    }
    if (origin.origin_lat !== undefined && document.activeElement !== manualLat) {
      manualLat.value = origin.origin_lat;
    }
    if (origin.origin_lon !== undefined && document.activeElement !== manualLon) {
      manualLon.value = origin.origin_lon;
    }
    if (origin.origin_alt_m !== undefined && document.activeElement !== manualAlt) {
      manualAlt.value = origin.origin_alt_m;
    }

    renderPlans(status.vehicles || []);
    renderFleet(status);
    syncVehicleSelectionFromManual(manual.vehicle_id || manualVehicleId.value.trim());
  }

  function renderVisualization(data) {
    visualizationState = {
      reachable: !!data?.reachable,
      connected: !!data?.connected,
      selected_vehicle_id: data?.selected_vehicle_id || manualVehicleId.value.trim(),
      selected_airsim_vehicle: data?.selected_airsim_vehicle || "",
      suggested_airsim_vehicle: data?.suggested_airsim_vehicle || "",
      vehicle_map: data?.vehicle_map || {},
      vehicles: data?.vehicles || [],
      error: data?.error || "",
      base_url: data?.base_url || "",
      origin_geopoint: data?.origin_geopoint || {},
    };

    const currentValue = airsimVehicleName.value;
    const knownNames = new Set(
      visualizationState.vehicles
        .map((item) => String(item.name || "").trim())
        .filter(Boolean)
    );
    const mappedName = visualizationState.vehicle_map[manualVehicleId.value.trim()] || "";
    let desiredValue = "";
    if (document.activeElement === airsimVehicleName && knownNames.has(currentValue)) {
      desiredValue = currentValue;
    } else if (knownNames.has(mappedName)) {
      desiredValue = mappedName;
    } else if (knownNames.has(visualizationState.selected_airsim_vehicle)) {
      desiredValue = visualizationState.selected_airsim_vehicle;
    } else if (knownNames.has(visualizationState.suggested_airsim_vehicle)) {
      desiredValue = visualizationState.suggested_airsim_vehicle;
    } else if (knownNames.size === 1) {
      desiredValue = Array.from(knownNames)[0];
    }

    airsimVehicleName.innerHTML = "";
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = visualizationState.reachable
      ? (visualizationState.vehicles.length ? "Select vehicle" : "No AirSim vehicles")
      : "Visualization unavailable";
    airsimVehicleName.appendChild(placeholder);

    visualizationState.vehicles.forEach((vehicle) => {
      const option = document.createElement("option");
      option.value = vehicle.name;
      let label = vehicle.name;
      if (Array.isArray(vehicle.mapped_ids) && vehicle.mapped_ids.length) {
        label += ` <- ${vehicle.mapped_ids.join(", ")}`;
      }
      if (!vehicle.available) {
        label += " (map only)";
      }
      option.textContent = label;
      airsimVehicleName.appendChild(option);
    });
    airsimVehicleName.value = desiredValue;

    const selectedVehicle = visualizationState.selected_vehicle_id || manualVehicleId.value.trim() || "-";
    const selectedName = airsimVehicleName.value || visualizationState.selected_airsim_vehicle || "-";
    const selectedRecord = visualizationState.vehicles.find((vehicle) => vehicle.name === airsimVehicleName.value)
      || visualizationState.vehicles.find((vehicle) => vehicle.name === visualizationState.selected_airsim_vehicle)
      || null;
    const pose = selectedRecord?.pose || null;
    const poseText = pose
      ? `  ned=${fmtNum(pose.north, 1)}/${fmtNum(pose.east, 1)}/${fmtNum(pose.down, 1)}  yaw=${fmtNum(pose.yaw_deg, 1)}`
      : "";
    visualizationStatus.textContent = visualizationState.reachable
      ? `vm=${visualizationState.base_url}  connected=${yesNo(visualizationState.connected)}  `
        + `vehicles=${visualizationState.vehicles.length}  mapping=${selectedVehicle}->${selectedName}`
        + poseText
        + (visualizationState.error ? `  error=${visualizationState.error}` : "")
      : `vm=${visualizationState.base_url || "-"}  unavailable`
        + (visualizationState.error ? `  error=${visualizationState.error}` : "");
  }

  function syncVehicleSelectionFromManual(vehicleId) {
    const mappedName = (visualizationState.vehicle_map || {})[vehicleId || ""];
    if (!mappedName || document.activeElement === airsimVehicleName) {
      return;
    }
    const optionValues = Array.from(airsimVehicleName.options).map((option) => option.value);
    if (optionValues.includes(mappedName)) {
      airsimVehicleName.value = mappedName;
    }
  }

  function applyResult(result) {
    if (result?.visualization) {
      renderVisualization(result.visualization);
    }
    if (result?.status) {
      renderStatus(result.status);
      return;
    }
    renderStatus(result);
  }

  function renderPlans(vehicles) {
    if (!vehicles.length) {
      planList.innerHTML = `<li class="empty">No flight plans loaded.</li>`;
      return;
    }
    planList.innerHTML = "";
    vehicles.forEach((vehicle) => {
      const li = document.createElement("li");
      const info = document.createElement("span");
      info.textContent = `${vehicle.vehicle_id}  plan=${vehicle.flight_plan_number}  etot=${fmtHms(vehicle.etot_s)}`;
      const button = document.createElement("button");
      button.className = "remove";
      button.textContent = "Remove";
      button.onclick = async () => {
        try {
          renderStatus(await api(`/api/plans/${encodeURIComponent(vehicle.vehicle_id)}`, { method: "DELETE" }));
        } catch (error) {
          alert(error.message);
        }
      };
      li.append(info, button);
      planList.appendChild(li);
    });
  }

  function renderFleet(status) {
    const vehicles = [...(status.vehicles || [])];
    const manual = status.manual || {};
    if (status.control_mode !== "mission" && manual.vehicle_id) {
      vehicles.unshift({
        vehicle_id: manual.vehicle_id,
        flight_plan_number: manual.flight_plan_number,
        state: status.control_mode,
        etot_s: 0,
        elapsed_s: status.sim_time_s || 0,
        last_point: {
          waypoint_id: `${manual.flight_plan_number}-MANUAL-1`,
          lat: null,
          lon: null,
          alt_m: null,
          north: manual.position?.north,
          east: manual.position?.east,
          down: manual.position?.down,
        },
      });
    }

    if (!vehicles.length) {
      fleetBody.innerHTML = `<tr><td colspan="8" class="empty">No active vehicles.</td></tr>`;
      return;
    }
    fleetBody.innerHTML = "";
    vehicles.forEach((vehicle) => {
      const lastPoint = vehicle.last_point || {};
      const lla = (lastPoint.lat != null && lastPoint.lon != null && lastPoint.alt_m != null)
        ? `${fmtNum(lastPoint.lat, 5)}/${fmtNum(lastPoint.lon, 5)}/${fmtNum(lastPoint.alt_m, 1)}`
        : "-";
      const ned = (lastPoint.north != null && lastPoint.east != null && lastPoint.down != null)
        ? `${fmtNum(lastPoint.north, 1)}/${fmtNum(lastPoint.east, 1)}/${fmtNum(lastPoint.down, 1)}`
        : "-";
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(vehicle.vehicle_id)}</td>
        <td>${escapeHtml(vehicle.flight_plan_number)}</td>
        <td class="state-${escapeHtml(vehicle.state)}">${escapeHtml(stateLabel[vehicle.state] || vehicle.state)}</td>
        <td>${fmtHms(vehicle.etot_s)}</td>
        <td>${fmtNum(vehicle.elapsed_s, 1)}s</td>
        <td>${escapeHtml(lastPoint.waypoint_id || "-")}</td>
        <td>${lla}</td>
        <td>${ned}</td>
      `;
      fleetBody.appendChild(tr);
    });
  }

  function currentManualInput() {
    const roll = (pressed.has("KeyD") ? 1 : 0) + (pressed.has("KeyA") ? -1 : 0);
    const pitch = (pressed.has("KeyW") ? 1 : 0) + (pressed.has("KeyS") ? -1 : 0);
    const yaw = (pressed.has("KeyE") ? 1 : 0) + (pressed.has("KeyQ") ? -1 : 0);
    const throttle = (pressed.has("Space") ? 1 : 0)
      + (pressed.has("ShiftLeft") || pressed.has("ShiftRight") ? -1 : 0);
    return {
      roll: clampAxis(roll),
      pitch: clampAxis(pitch),
      yaw: clampAxis(yaw),
      throttle: clampAxis(throttle),
    };
  }

  function renderAxes(input) {
    axisRoll.textContent = input.roll.toFixed(2);
    axisPitch.textContent = input.pitch.toFixed(2);
    axisYaw.textContent = input.yaw.toFixed(2);
    axisThrottle.textContent = input.throttle.toFixed(2);
  }

  function setManualCapture(enabled, source = "", kind = "") {
    manualCapture = enabled;
    manualCaptureSource = enabled ? (source || "browser") : "";
    manualCaptureKind = enabled ? (kind || "keyboard") : "";
    if (!enabled) {
      pressed.clear();
    }
    updateCaptureButtons();
    if (!enabled || manualCaptureSource === "browser") {
      renderAxes(currentManualInput());
    }
  }

  async function startManualCapture(kind) {
    const resolvedKind = kind === "joystick" ? "joystick" : "keyboard";
    controlMode.value = resolvedKind;
    try {
      if (resolvedKind === "joystick") {
        const result = await api("/api/control/joystick/start", {
          method: "POST",
          body: manualConfigPayload(),
        });
        applyResult(result);
        const capture = result?.status?.joystick_capture || result?.joystick_capture || {};
        if (capture.active) {
          setManualCapture(true, capture.source || "pygame-joystick", "joystick");
        }
        return;
      }

      const result = await api("/api/control/keyboard/start", {
        method: "POST",
        body: manualConfigPayload(),
      });
      applyResult(result);
      const capture = result?.status?.keyboard_capture || result?.keyboard_capture || {};
      if (capture.active) {
        setManualCapture(true, capture.source || "windows-global", "keyboard");
      } else {
        setManualCapture(true, "browser", "keyboard");
        await sendManualInput();
      }
    } catch (error) {
      alert(error.message);
    }
  }

  function manualConfigPayload() {
    const body = {
      vehicle_id: manualVehicleId.value.trim() || "UAM0001",
      origin_lat: numericInputOrNull(manualLat),
      origin_lon: numericInputOrNull(manualLon),
      origin_alt_m: numericInputOrNull(manualAlt),
    };
    const selectedName = airsimVehicleName.value.trim();
    if (selectedName) {
      body.airsim_vehicle_name = selectedName;
    }
    return body;
  }

  function numericInputOrNull(input) {
    const raw = String(input?.value ?? "").trim();
    if (!raw) {
      return null;
    }
    const value = Number(raw);
    return Number.isFinite(value) ? value : null;
  }

  function clampAxis(value) {
    return Math.max(-1, Math.min(1, Number(value) || 0));
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "\"": "&quot;",
      "'": "&#39;",
    }[ch]));
  }

  function fmtNum(value, digits) {
    const n = Number(value);
    return Number.isFinite(n) ? n.toFixed(digits) : "-";
  }

  function fmtHms(totalSeconds) {
    const total = Math.max(0, Number(totalSeconds) || 0);
    const hours = String(Math.floor(total / 3600) % 24).padStart(2, "0");
    const minutes = String(Math.floor((total % 3600) / 60)).padStart(2, "0");
    const seconds = String(Math.floor(total) % 60).padStart(2, "0");
    return `${hours}:${minutes}:${seconds}`;
  }

  async function loadVisualizationVehicles(refresh = true) {
    refreshVehicles.disabled = true;
    try {
      renderVisualization(await api(`/api/visualization/vehicles?refresh=${refresh ? "true" : "false"}`));
    } catch (error) {
      renderVisualization({
        base_url: visualizationState.base_url || "http://127.0.0.1:8096",
        reachable: false,
        connected: false,
        selected_vehicle_id: manualVehicleId.value.trim() || "UAM0001",
        selected_airsim_vehicle: "",
        suggested_airsim_vehicle: "",
        vehicle_map: {},
        vehicles: [],
        airsim: {},
        origin_geopoint: {},
        unreal: {},
        error: error.message,
      });
    } finally {
      refreshVehicles.disabled = false;
    }
  }

  applyPublisher.onclick = async () => {
    try {
      const status = await api("/api/publisher", {
        method: "POST",
        body: {
          target_ip: targetIp.value.trim() || "127.0.0.1",
          ws_port: Number(wsPort.value || 8096),
        },
      });
      dirtyPublisher = false;
      renderStatus(status);
    } catch (error) {
      alert(error.message);
    }
  };

  controlMode.onchange = async () => {
    try {
      updateCaptureButtons();
      if (controlMode.value !== "keyboard" && manualCaptureSource === "browser") {
        setManualCapture(false, "", "");
      }
      renderStatus(await api("/api/control/mode", {
        method: "POST",
        body: { mode: controlMode.value },
      }));
    } catch (error) {
      alert(error.message);
    }
  };

  refreshVehicles.onclick = async () => {
    await loadVisualizationVehicles(true);
  };

  applyManualConfig.onclick = async () => {
    try {
      applyResult(await api("/api/control/manual/config", {
        method: "POST",
        body: manualConfigPayload(),
      }));
    } catch (error) {
      alert(error.message);
    }
  };

  activateKeyboard.onclick = async () => {
    await startManualCapture("keyboard");
  };

  activateJoystick.onclick = async () => {
    await startManualCapture("joystick");
  };

  releaseKeyboard.onclick = async () => {
    try {
      const releasePath = (manualCaptureKind === "joystick" || controlMode.value === "joystick")
        ? "/api/control/joystick/stop"
        : "/api/control/keyboard/stop";
      const result = await api(releasePath, { method: "POST" });
      applyResult(result);
    } catch {
      try {
        await api("/api/control/input", {
          method: "POST",
          body: { roll: 0, pitch: 0, yaw: 0, throttle: 0 },
        });
      } catch {}
    } finally {
      setManualCapture(false, "", "");
    }
  };

  uploadPlans.onclick = async () => {
    if (!planFiles.files || planFiles.files.length === 0) {
      alert("Select one or more JSON files.");
      return;
    }
    const payloads = [];
    const parseErrors = [];
    for (const file of planFiles.files) {
      try {
        payloads.push(JSON.parse(await file.text()));
      } catch (error) {
        parseErrors.push(`${file.name}: ${error.message}`);
      }
    }
    if (parseErrors.length) {
      alert(`JSON parse failed:\n${parseErrors.join("\n")}`);
    }
    if (!payloads.length) {
      return;
    }
    try {
      const data = await api("/api/plans/batch", { method: "POST", body: payloads });
      if (data.errors && data.errors.length) {
        alert(`Some plans failed:\n${data.errors.join("\n")}`);
      }
      planFiles.value = "";
      renderStatus(data.status);
    } catch (error) {
      alert(error.message);
    }
  };

  clearPlans.onclick = async () => {
    if (!confirm("Clear all loaded flight plans?")) {
      return;
    }
    try {
      renderStatus(await api("/api/plans", { method: "DELETE" }));
    } catch (error) {
      alert(error.message);
    }
  };

  feedTime.onclick = async () => {
    try {
      renderStatus(await api("/api/clock/feed", {
        method: "POST",
        body: { hms: hms.value.trim() },
      }));
    } catch (error) {
      alert(error.message);
    }
  };

  stepOnce.onclick = async () => {
    try {
      renderStatus(await api("/api/clock/step", {
        method: "POST",
        body: { hms: hms.value.trim() },
      }));
    } catch (error) {
      alert(error.message);
    }
  };

  startService.onclick = async () => {
    try {
      renderStatus(await api("/api/service/start", {
        method: "POST",
        body: { mode: clockMode.value },
      }));
    } catch (error) {
      alert(error.message);
    }
  };

  stopService.onclick = async () => {
    try {
      renderStatus(await api("/api/service/stop", { method: "POST" }));
    } catch (error) {
      alert(error.message);
    }
  };

  clockMode.onchange = async () => {
    try {
      renderStatus(await api("/api/clock/mode", {
        method: "POST",
        body: { mode: clockMode.value },
      }));
    } catch (error) {
      alert(error.message);
    }
  };

  window.addEventListener("keydown", (event) => {
    if (!manualCapture || manualCaptureSource !== "browser") {
      return;
    }
    if (["KeyW", "KeyA", "KeyS", "KeyD", "KeyQ", "KeyE", "Space", "ShiftLeft", "ShiftRight"].includes(event.code)) {
      event.preventDefault();
      pressed.add(event.code);
      renderAxes(currentManualInput());
    }
  });

  window.addEventListener("keyup", (event) => {
    if (!manualCapture || manualCaptureSource !== "browser") {
      return;
    }
    pressed.delete(event.code);
    renderAxes(currentManualInput());
  });

  window.addEventListener("blur", async () => {
    if (!manualCapture || manualCaptureSource !== "browser") {
      return;
    }
    pressed.clear();
    renderAxes(currentManualInput());
    try {
      await api("/api/control/input", {
        method: "POST",
        body: { roll: 0, pitch: 0, yaw: 0, throttle: 0 },
      });
    } catch {}
  });

  async function sendManualInput() {
    const input = currentManualInput();
    if (manualCaptureSource !== "windows-global" && manualCaptureKind !== "joystick") {
      renderAxes(input);
    }
    if (!manualCapture || manualCaptureSource !== "browser") {
      return;
    }
    try {
      await api("/api/control/input", { method: "POST", body: input });
    } catch (error) {
      controlStatus.textContent = `input error=${error.message}`;
    }
  }

  async function tick() {
    try {
      renderStatus(await api("/api/status"));
    } catch (error) {
      serviceStatus.textContent = `status error=${error.message}`;
    }
  }

  tick();
  updateCaptureButtons();
  loadVisualizationVehicles(true);
  setInterval(tick, 500);
  setInterval(sendManualInput, 100);
})();
