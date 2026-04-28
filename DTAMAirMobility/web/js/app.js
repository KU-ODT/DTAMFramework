(() => {
  const $ = (id) => document.getElementById(id);
  const targetIp = $("targetIp");
  const wsPort = $("wsPort");
  const applyPublisher = $("applyPublisher");
  const publisherStatus = $("publisherStatus");
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
  [targetIp, wsPort].forEach((el) =>
    el.addEventListener("input", () => { dirtyPublisher = true; })
  );

  async function api(path, { method = "GET", body } = {}) {
    const res = await fetch(path, {
      method,
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json()).detail || detail; } catch {}
      throw new Error(detail);
    }
    return res.json();
  }

  const YESNO = (v) => (v ? "예" : "아니오");
  const MODE_KO = { external: "외부", wall: "실시간", manual: "수동" };

  function renderStatus(status) {
    publisherStatus.textContent =
      `WS=${status.server_url || `ws://${status.target_ip}:${status.ws_port}/ws/dtam`}  `
      + `연결=${YESNO(status.publisher_connected)}`
      + (status.publisher_error ? `  오류=${status.publisher_error}` : "");
    serviceStatus.textContent =
      `모드=${MODE_KO[status.clock_mode] || status.clock_mode}  `
      + `실행중=${YESNO(status.running)}  `
      + `시각=${status.sim_time_hms} (${status.sim_time_s.toFixed(2)}초)`;
    startService.disabled = !!status.running;
    stopService.disabled = !status.running;

    if (rxStatus) {
      rxStatus.innerHTML =
        `3001 (비행계획) 수신 ${status.rx_3001_count ?? 0}건 `
        + `· 최근: <code>${escapeHtml(status.last_rx_3001 || "—")}</code><br>`
        + `0003 (공통 시간) 수신 ${status.rx_0003_count ?? 0}건 `
        + `· 최근 simTime: <code>${escapeHtml(status.last_rx_0003 || "—")}</code>`;
    }

    if (!dirtyPublisher) {
      targetIp.value = status.target_ip;
      wsPort.value = status.ws_port;
    }
    if (clockMode.value !== status.clock_mode && document.activeElement !== clockMode) {
      clockMode.value = status.clock_mode;
    }

    renderPlans(status.vehicles);
    renderFleet(status.vehicles);
  }

  const STATE_KO = {
    waiting: "대기",
    active: "비행중",
    completed: "완료",
    error: "오류",
  };

  function renderPlans(vehicles) {
    if (!vehicles || vehicles.length === 0) {
      planList.innerHTML = `<li class="empty">등록된 비행계획이 없습니다.</li>`;
      return;
    }
    planList.innerHTML = "";
    vehicles.forEach((v) => {
      const li = document.createElement("li");
      const info = document.createElement("span");
      info.textContent =
        `${v.vehicle_id}  계획번호=${v.flight_plan_number}  `
        + `이륙=${fmtHms(v.etot_s)}`;
      const btn = document.createElement("button");
      btn.className = "remove";
      btn.textContent = "삭제";
      btn.onclick = async () => {
        try {
          const s = await api(`/api/plans/${encodeURIComponent(v.vehicle_id)}`, { method: "DELETE" });
          renderStatus(s);
        } catch (e) { alert(e.message); }
      };
      li.appendChild(info);
      li.appendChild(btn);
      planList.appendChild(li);
    });
  }

  function renderFleet(vehicles) {
    if (!vehicles || vehicles.length === 0) {
      fleetBody.innerHTML =
        `<tr><td colspan="8" class="empty">진행 중인 비행이 없습니다.</td></tr>`;
      return;
    }
    fleetBody.innerHTML = "";
    vehicles.forEach((v) => {
      const lp = v.last_point || {};
      const lla = (lp.lat != null && lp.lon != null && lp.alt_m != null)
        ? `${lp.lat.toFixed(5)}/${lp.lon.toFixed(5)}/${lp.alt_m.toFixed(1)}`
        : "—";
      const ned = (lp.north != null && lp.east != null && lp.down != null)
        ? `${lp.north.toFixed(1)}/${lp.east.toFixed(1)}/${lp.down.toFixed(1)}`
        : "—";
      const stateLabel = STATE_KO[v.state] || v.state;
      const stateTxt = v.last_error ? `${stateLabel} (${v.last_error})` : stateLabel;
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${v.vehicle_id}</td>
        <td>${v.flight_plan_number}</td>
        <td class="state-${v.state}">${stateTxt}</td>
        <td>${fmtHms(v.etot_s)}</td>
        <td>${v.elapsed_s.toFixed(1)}초</td>
        <td>${lp.waypoint_id || "—"}</td>
        <td>${lla}</td>
        <td>${ned}</td>
      `;
      fleetBody.appendChild(tr);
    });
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
    }[ch]));
  }

  function fmtHms(totalS) {
    const t = Math.max(0, Number(totalS) || 0);
    const h = String(Math.floor(t / 3600) % 24).padStart(2, "0");
    const m = String(Math.floor((t % 3600) / 60)).padStart(2, "0");
    const s = String(Math.floor(t) % 60).padStart(2, "0");
    return `${h}:${m}:${s}`;
  }

  applyPublisher.onclick = async () => {
    try {
      const s = await api("/api/publisher", {
        method: "POST",
        body: {
          target_ip: targetIp.value.trim() || "127.0.0.1",
          ws_port: Number(wsPort.value),
        },
      });
      dirtyPublisher = false;
      renderStatus(s);
    } catch (e) { alert(e.message); }
  };

  uploadPlans.onclick = async () => {
    if (!planFiles.files || planFiles.files.length === 0) {
      alert("업로드할 JSON 파일을 선택해 주세요.");
      return;
    }
    const payloads = [];
    const parseErrors = [];
    for (const f of planFiles.files) {
      try {
        const text = await f.text();
        payloads.push(JSON.parse(text));
      } catch (e) {
        parseErrors.push(`${f.name}: ${e.message}`);
      }
    }
    if (parseErrors.length) {
      alert("JSON 파싱에 실패한 파일이 있습니다:\n" + parseErrors.join("\n"));
    }
    if (payloads.length === 0) return;
    try {
      const data = await api("/api/plans/batch", { method: "POST", body: payloads });
      if (data.errors && data.errors.length) {
        alert("일부 비행계획 등록에 실패했습니다:\n" + data.errors.join("\n"));
      }
      planFiles.value = "";
      renderStatus(data.status);
    } catch (e) { alert(e.message); }
  };

  clearPlans.onclick = async () => {
    if (!confirm("등록된 모든 비행계획을 삭제하시겠습니까?")) return;
    try {
      const s = await api("/api/plans", { method: "DELETE" });
      renderStatus(s);
    } catch (e) { alert(e.message); }
  };

  feedTime.onclick = async () => {
    try {
      const s = await api("/api/clock/feed", { method: "POST", body: { hms: hms.value.trim() } });
      renderStatus(s);
    } catch (e) { alert(e.message); }
  };
  stepOnce.onclick = async () => {
    try {
      const s = await api("/api/clock/step", { method: "POST", body: { hms: hms.value.trim() } });
      renderStatus(s);
    } catch (e) { alert(e.message); }
  };
  startService.onclick = async () => {
    try {
      const s = await api("/api/service/start", {
        method: "POST",
        body: { mode: clockMode.value },
      });
      renderStatus(s);
    } catch (e) { alert(e.message); }
  };
  stopService.onclick = async () => {
    try {
      const s = await api("/api/service/stop", { method: "POST" });
      renderStatus(s);
    } catch (e) { alert(e.message); }
  };
  clockMode.onchange = async () => {
    try {
      const s = await api("/api/clock/mode", {
        method: "POST",
        body: { mode: clockMode.value },
      });
      renderStatus(s);
    } catch (e) { alert(e.message); }
  };

  async function tick() {
    try {
      const s = await api("/api/status");
      renderStatus(s);
    } catch (e) {
      serviceStatus.textContent = `상태 조회 실패: ${e.message}`;
    }
  }
  tick();
  setInterval(tick, 500);
})();
