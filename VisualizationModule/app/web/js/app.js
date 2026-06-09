/* DTAM Visualization Manager single-page GUI. */
(function () {
  "use strict";

  const INBOUND_MIDS = ["1001", "1002", "1003", "2002", "0003", "4001"];
  const OUTBOUND_MIDS = ["0002", "4101"];
  const MID_NAMES = {
    "0002": "Module Status",
    "0003": "Common Time Info",
    "1001": "Sim Mode Setup",
    "1002": "Simulation Setup",
    "1003": "Scenario Setup",
    "2001": "Flight Plan Request",
    "2002": "DTAM Execute",
    "3001": "Scheduled Flight",
    "3002": "Strategic Separation",
    "3003": "Tactical Separation",
    "4001": "Vehicle Status",
    "4101": "Camera Image Frame",
  };

  const state = {
    snapshot: null,
    filters: { rx: true, tx: true, translate: true, airsim: true, error: true },
    uptime: 0,
  };

  const els = {};
  [
    "brand-subtitle", "stat-airsim", "stat-dtam-rx", "stat-dtam-tx", "stat-uptime",
    "dtam-running-tag", "dtam-server-ip", "dtam-server-port",
    "btn-dtam-apply", "tbl-inbound", "tbl-outbound",
    "status-hz", "camera-enabled", "camera-name", "camera-image-type", "camera-hz",
    "camera-quality", "camera-vehicle", "btn-streaming-apply", "btn-capture-once",
    "airsim-conn-tag", "airsim-host", "airsim-port",
    "btn-airsim-connect", "btn-airsim-disconnect",
    "btn-unreal-launch", "unreal-status", "unreal-pid", "unreal-exe",
    "airsim-ping", "airsim-server-ver", "airsim-client-ver", "airsim-last-error",
    "tbl-vehicle-map", "map-uam", "map-name", "btn-map-add",
    "filter-rx", "filter-tx", "filter-translate", "filter-airsim", "filter-error",
    "btn-clear-events", "event-feed",
  ].forEach((id) => {
    els[id] = document.getElementById(id);
  });

  async function api(path, options) {
    const resp = await fetch(path, options || {});
    const ctype = resp.headers.get("content-type") || "";
    const data = ctype.includes("json") ? await resp.json().catch(() => ({})) : await resp.text();
    if (!resp.ok) {
      const detail = typeof data === "object" && data ? data.detail || data.error : data;
      throw new Error(detail || `${resp.status} ${resp.statusText}`);
    }
    return data;
  }

  function humanTime(ts) {
    if (!ts) return "--";
    const d = new Date(ts * 1000);
    if (Number.isNaN(d.getTime())) return "--";
    return d.toISOString().slice(11, 23);
  }

  function humanUptime(seconds) {
    let s = Math.max(0, Math.floor(Number(seconds) || 0));
    const h = Math.floor(s / 3600);
    s -= h * 3600;
    const m = Math.floor(s / 60);
    const r = s - m * 60;
    if (h > 0) return `${h}h ${String(m).padStart(2, "0")}m`;
    if (m > 0) return `${m}m ${String(r).padStart(2, "0")}s`;
    return `${r}s`;
  }

  function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function setText(id, value) {
    if (els[id]) {
      els[id].textContent = value;
    }
  }

  function setValIfBlurred(id, value) {
    const el = els[id];
    if (!el) return;
    if (document.activeElement !== el) {
      el.value = value;
    }
  }

  function sumCounts(counts) {
    return Object.values(counts || {}).reduce((total, item) => total + (Number(item) || 0), 0);
  }

  function renderSnapshot(snapshot) {
    state.snapshot = snapshot;
    state.uptime = snapshot.uptime_s || 0;
    setText("stat-uptime", humanUptime(state.uptime));

    const airsim = snapshot.airsim || {};
    const asCfg = snapshot.airsim_config || {};
    setText("stat-airsim", airsim.connected ? `${airsim.host}:${airsim.port}` : "offline");
    setText("airsim-conn-tag", airsim.connected ? "connected" : "disconnected");
    els["airsim-conn-tag"]?.classList.toggle("online", !!airsim.connected);
    els["airsim-conn-tag"]?.classList.toggle("offline", !airsim.connected);
    setValIfBlurred("airsim-host", airsim.host || asCfg.host || "127.0.0.1");
    setValIfBlurred("airsim-port", airsim.port || asCfg.port || 41451);
    setText("airsim-ping", airsim.last_ping_ms ? `${Number(airsim.last_ping_ms).toFixed(1)} ms` : "--");
    setText("airsim-server-ver", airsim.server_version ?? "--");
    setText("airsim-client-ver", airsim.client_version ?? "--");
    setText("airsim-last-error", airsim.last_error || "--");
    els["airsim-last-error"]?.classList.toggle("err", !!airsim.last_error);

    const unreal = snapshot.unreal || {};
    setText("unreal-status", unreal.running ? "running" : "stopped");
    setText("unreal-pid", unreal.pid || "-");
    setText("unreal-exe", unreal.executable || "-");

    renderVehicleMap(asCfg.vehicle_map || {});

    const dtam = snapshot.dtam || {};
    const ep = snapshot.dtam_endpoint || {};
    const wsUrl = `ws://${ep.server_ip || "127.0.0.1"}:${ep.server_port || 8096}/ws/dtam`;
    setText("dtam-running-tag", dtam.running ? "running" : "offline");
    els["dtam-running-tag"]?.classList.toggle("running", !!dtam.running);
    els["dtam-running-tag"]?.classList.toggle("offline", !dtam.running);
    setValIfBlurred("dtam-server-ip", ep.server_ip || "127.0.0.1");
    setValIfBlurred("dtam-server-port", ep.server_port || 8096);
    setText("brand-subtitle", `DTAM ${dtam.transport || "ws"} ${wsUrl}`);

    setText("stat-dtam-rx", sumCounts(dtam.rx_counts || {}));
    setText("stat-dtam-tx", sumCounts(dtam.tx_counts || {}));
    renderMsgTable(els["tbl-inbound"], INBOUND_MIDS, dtam, "rx");
    renderMsgTable(els["tbl-outbound"], OUTBOUND_MIDS, dtam, "tx");

    const stream = snapshot.streaming || {};
    setValIfBlurred("status-hz", stream.module_status_hz ?? 1);
    setValIfBlurred("camera-name", stream.camera_name ?? "front_center");
    setValIfBlurred("camera-image-type", stream.camera_image_type ?? 0);
    setValIfBlurred("camera-hz", stream.camera_hz ?? 2);
    setValIfBlurred("camera-quality", stream.camera_quality ?? 65);
    setValIfBlurred("camera-vehicle", stream.camera_vehicle ?? "");
    if (els["camera-enabled"] && document.activeElement !== els["camera-enabled"]) {
      els["camera-enabled"].checked = !!stream.camera_enabled;
    }

    renderEvents(snapshot.events || []);
  }

  function renderMsgTable(table, mids, dtam, kind) {
    if (!table) return;
    const tbody = table.querySelector("tbody");
    if (!tbody) return;
    const counts = kind === "rx" ? (dtam.rx_counts || {}) : (dtam.tx_counts || {});
    const lastTs = kind === "rx" ? (dtam.last_rx_ts || {}) : (dtam.last_tx_ts || {});
    const hz = dtam.rx_hz || {};
    tbody.innerHTML = mids.map((mid) => {
      const count = counts[mid] || 0;
      const last = lastTs[mid];
      if (kind === "rx") {
        const rate = hz[mid] ? Number(hz[mid]).toFixed(2) : "--";
        return `<tr><td class="mid">${mid}</td><td>${escapeHtml(MID_NAMES[mid] || "")}</td><td>${count}</td><td class="hz">${rate}</td><td>${humanTime(last)}</td></tr>`;
      }
      return `<tr><td class="mid">${mid}</td><td>${escapeHtml(MID_NAMES[mid] || "")}</td><td>${count}</td><td>${humanTime(last)}</td></tr>`;
    }).join("");
  }

  function renderVehicleMap(map) {
    const table = els["tbl-vehicle-map"];
    if (!table) return;
    const tbody = table.querySelector("tbody");
    if (!tbody) return;
    const entries = Object.entries(map || {});
    if (!entries.length) {
      tbody.innerHTML = '<tr><td colspan="3" style="color:var(--text-dim);text-align:center">(empty)</td></tr>';
      return;
    }
    tbody.innerHTML = entries.map(([uam, name]) => `
      <tr>
        <td class="mid">${escapeHtml(uam)}</td>
        <td>${escapeHtml(name)}</td>
        <td><button class="btn btn-ghost btn-sm" data-uam="${escapeHtml(uam)}">Remove</button></td>
      </tr>
    `).join("");
    tbody.querySelectorAll("button[data-uam]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const uam = btn.getAttribute("data-uam");
        if (!uam) return;
        await api("/api/airsim/vehicle-map", {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ [uam]: "" }),
        }).catch((err) => console.warn(err));
        refreshState();
      });
    });
  }

  function renderEvents(events) {
    const feed = els["event-feed"];
    if (!feed) return;
    feed.innerHTML = "";
    events.slice(-300).forEach(appendEvent);
  }

  function appendEvent(evt) {
    if (!passFilter(evt) || !els["event-feed"]) return;
    const row = document.createElement("div");
    row.className = `event-row ${evt.kind || ""}`;
    row.innerHTML = `
      <span class="ev-ts">${humanTime(evt.ts)}</span>
      <span class="ev-kind ${escapeHtml(evt.kind || "")}">${escapeHtml(evt.kind || "")}</span>
      <span class="ev-mid">${escapeHtml(evt.mid || "")}</span>
      <span class="ev-summary" title="${escapeHtml(JSON.stringify(evt.detail || {}))}">${escapeHtml(evt.summary || "")}</span>
    `;
    els["event-feed"].appendChild(row);
    while (els["event-feed"].children.length > 400) {
      els["event-feed"].removeChild(els["event-feed"].firstChild);
    }
    els["event-feed"].scrollTop = els["event-feed"].scrollHeight;
  }

  function passFilter(evt) {
    const kind = evt?.kind || "";
    return !!state.filters[kind];
  }

  let ws = null;
  let reconnectHandle = 0;

  function connectWs() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${proto}//${location.host}/ws/events`);
    ws.onmessage = (ev) => {
      let msg;
      try {
        msg = JSON.parse(ev.data);
      } catch {
        return;
      }
      if (msg.type === "snapshot") {
        renderSnapshot(msg);
      } else if (msg.type === "event") {
        appendEvent(msg);
      }
    };
    ws.onclose = () => {
      if (reconnectHandle) clearTimeout(reconnectHandle);
      reconnectHandle = setTimeout(connectWs, 1500);
    };
    ws.onerror = () => {
      try {
        ws.close();
      } catch {}
    };
  }

  async function refreshState() {
    try {
      const snap = await api("/api/state");
      renderSnapshot(snap);
    } catch (err) {
      console.warn("refreshState failed", err);
    }
  }

  function wire() {
    [
      ["rx", "filter-rx"],
      ["tx", "filter-tx"],
      ["translate", "filter-translate"],
      ["airsim", "filter-airsim"],
      ["error", "filter-error"],
    ].forEach(([kind, id]) => {
      els[id]?.addEventListener("change", () => {
        state.filters[kind] = !!els[id].checked;
      });
    });

    els["btn-clear-events"]?.addEventListener("click", () => {
      if (els["event-feed"]) {
        els["event-feed"].innerHTML = "";
      }
    });

    els["btn-airsim-connect"]?.addEventListener("click", async () => {
      await api("/api/airsim/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          host: els["airsim-host"]?.value || "127.0.0.1",
          port: Number(els["airsim-port"]?.value || 41451),
        }),
      }).catch((err) => console.warn(err));
      refreshState();
    });

    els["btn-airsim-disconnect"]?.addEventListener("click", async () => {
      await api("/api/airsim/disconnect", { method: "POST" }).catch((err) => console.warn(err));
      refreshState();
    });

    els["btn-unreal-launch"]?.addEventListener("click", async () => {
      els["btn-unreal-launch"].disabled = true;
      await api("/api/unreal/launch", { method: "POST" }).catch((err) => console.warn(err));
      els["btn-unreal-launch"].disabled = false;
      refreshState();
    });

    els["btn-dtam-apply"]?.addEventListener("click", async () => {
      await api("/api/dtam/endpoint", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          server_ip: els["dtam-server-ip"]?.value || "127.0.0.1",
          server_port: Number(els["dtam-server-port"]?.value || 8096),
        }),
      }).catch((err) => console.warn(err));
      refreshState();
    });

    els["btn-streaming-apply"]?.addEventListener("click", async () => {
      await api("/api/streaming", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          module_status_hz: Number(els["status-hz"]?.value || 1),
          camera_enabled: !!els["camera-enabled"]?.checked,
          camera_name: els["camera-name"]?.value || "front_center",
          camera_image_type: Number(els["camera-image-type"]?.value || 0),
          camera_hz: Number(els["camera-hz"]?.value || 2),
          camera_quality: Number(els["camera-quality"]?.value || 65),
          camera_vehicle: els["camera-vehicle"]?.value || "",
        }),
      }).catch((err) => console.warn(err));
      refreshState();
    });

    els["btn-capture-once"]?.addEventListener("click", async () => {
      await api("/api/airsim/capture-once", { method: "POST" }).catch((err) => console.warn(err));
    });

    els["btn-map-add"]?.addEventListener("click", async () => {
      const uam = (els["map-uam"]?.value || "").trim();
      const name = (els["map-name"]?.value || "").trim();
      if (!uam || !name) return;
      await api("/api/airsim/vehicle-map", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [uam]: name }),
      }).catch((err) => console.warn(err));
      if (els["map-uam"]) els["map-uam"].value = "";
      if (els["map-name"]) els["map-name"].value = "";
      refreshState();
    });
  }

  function startTicker() {
    setInterval(() => {
      if (state.snapshot) {
        state.uptime += 1;
        setText("stat-uptime", humanUptime(state.uptime));
      }
    }, 1000);
    setInterval(refreshState, 3000);
  }

  document.addEventListener("DOMContentLoaded", async () => {
    wire();
    await refreshState();
    connectWs();
    startTicker();
  });
})();
