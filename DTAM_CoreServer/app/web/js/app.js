/* DTAM Server Emulator — single-page GUI.
 *
 * - WebSocket (/ws/events) 로 초기 snapshot + 실시간 traffic 이벤트 수신
 * - REST (/api/state, /api/modules/:role PATCH) 로 구성 조회/수정
 * - 모듈 카드: 연결되면 하이라이트, 클릭 시 drawer 열림
 * - Traffic feed: rx/tx/ok/fail 색상
 */
(function () {
  'use strict';

  const state = {
    snapshot: null,
    modules: [],                 // 마지막으로 알려진 module 상태
    filters: { rx: true, tx: true, '0002': false, '0003': false, '4001': false },
    selectedRole: null,
  };

  const els = {
    brandSub: document.getElementById('brand-subtitle'),
    statUdp: document.getElementById('stat-udp'),
    statTcp: document.getElementById('stat-tcp'),
    statSession: document.getElementById('stat-session'),
    statUptime: document.getElementById('stat-uptime'),
    modulesGrid: document.getElementById('modules-grid'),
    modulesSummary: document.getElementById('modules-summary'),
    trafficFeed: document.getElementById('traffic-feed'),
    counterBody: document.getElementById('counter-body'),
    drawer: document.getElementById('module-drawer'),
    drawerTitle: document.getElementById('drawer-title'),
    drawerSub: document.getElementById('drawer-sub'),
    drawerBody: document.getElementById('drawer-body'),
    filterRx: document.getElementById('filter-rx'),
    filterTx: document.getElementById('filter-tx'),
    filter0002: document.getElementById('filter-0002'),
    filter0003: document.getElementById('filter-0003'),
    filter4001: document.getElementById('filter-4001'),
    btnClearTraffic: document.getElementById('btn-clear-traffic'),
    btnOpenDb: document.getElementById('btn-open-db'),
    btnRefresh: document.getElementById('btn-refresh'),
    drawerClose: document.getElementById('drawer-close'),
  };

  // ── utility ─────────────────────────────────────────────
  function humanTime(ts) {
    if (!ts) return '—';
    const d = new Date(ts * 1000);
    return d.toISOString().slice(11, 23); // HH:MM:SS.mmm
  }

  function humanUptime(seconds) {
    const s = Math.max(0, Math.floor(seconds));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const r = s % 60;
    if (h > 0) return `${h}h ${String(m).padStart(2, '0')}m`;
    if (m > 0) return `${m}m ${String(r).padStart(2, '0')}s`;
    return `${r}s`;
  }

  function secondsSince(ts) {
    if (!ts) return null;
    return Math.max(0, Date.now() / 1000 - ts);
  }

  async function api(path, options) {
    // State Server (8096)으로 프록시
    const url = path.startsWith('/api/') ? `http://127.0.0.1:8096${path}` : path;
    const resp = await fetch(url, options || {});
    if (!resp.ok && resp.status !== 400) throw new Error(`${resp.status} ${resp.statusText}`);
    const ctype = resp.headers.get('content-type') || '';
    if (ctype.includes('json')) return await resp.json();
    return await resp.text();
  }

  // ── rendering ───────────────────────────────────────────
  function renderSnapshot(snapshot) {
    state.snapshot = snapshot;
    const srv = snapshot.server || {};
    els.statUdp.textContent = `${srv.bind_ip}:${srv.udp_port}`;
    els.statTcp.textContent = `${srv.bind_ip}:${srv.tcp_port}`;
    els.statSession.textContent = (snapshot.db && snapshot.db.session_id) || '--';
    els.statUptime.textContent = humanUptime(snapshot.uptime_s || 0);
    els.brandSub.textContent = snapshot.db && snapshot.db.session_dir
      ? `DB: ${snapshot.db.session_dir}`
      : 'Hub standby';

    renderModules(snapshot.registry || {});
    renderCounters(snapshot.registry || {});
    renderTrafficInit(snapshot.traffic || []);
  }

  function renderModules(registry) {
    const modules = registry.modules || [];
    state.modules = modules;
    const connectedCount = modules.filter((m) => m.connected).length;
    els.modulesSummary.textContent = `${connectedCount} / ${modules.length}`;
    els.modulesGrid.innerHTML = '';
    modules.forEach((m) => {
      const card = document.createElement('div');
      card.className = `module-card ${m.connected ? 'connected' : 'disconnected'}`;
      card.dataset.role = m.role;
      card.innerHTML = `
        <div class="module-top">
          <div>
            <div class="module-name">${escapeHtml(m.display_name || m.role)}</div>
            <div class="module-role">${escapeHtml(m.role)}</div>
          </div>
          <div class="module-status">
            <div class="status-dot"></div>
            <span>${m.connected ? 'connected' : (m.last_heartbeat_ts ? 'stale' : 'waiting')}</span>
          </div>
        </div>
        <div class="module-endpoint">${escapeHtml(m.ip)}:${m.udp_port} (TCP ${m.tcp_port})</div>
        <div class="module-metrics">
          <div class="metric"><div class="metric-label">RX</div><div class="metric-value">${m.rx_count || 0}</div></div>
          <div class="metric"><div class="metric-label">TX</div><div class="metric-value">${m.tx_count || 0}</div></div>
          <div class="metric"><div class="metric-label">Heartbeat</div><div class="metric-value">${formatHeartbeat(m.last_heartbeat_ts)}</div></div>
        </div>
        <div class="module-mids">${buildMidChips(m)}</div>
      `;
      card.addEventListener('click', () => openDrawer(m.role));
      els.modulesGrid.appendChild(card);
    });

    if (state.selectedRole) {
      const still = modules.find((m) => m.role === state.selectedRole);
      if (still) renderDrawer(still);
    }
  }

  function buildMidChips(module) {
    const mids = Object.keys(module.messages || {}).sort();
    if (!mids.length) return '<span class="mid-chip">idle</span>';
    return mids.map((mid) => {
      const c = module.messages[mid] || {};
      const active = (c.rx_count + c.tx_count) > 0;
      return `<span class="mid-chip ${active ? 'active' : ''}">${mid}</span>`;
    }).join('');
  }

  function formatHeartbeat(ts) {
    const sec = secondsSince(ts);
    if (sec === null) return '—';
    if (sec < 1) return 'now';
    if (sec < 60) return `${sec.toFixed(1)}s`;
    return `${Math.floor(sec / 60)}m`;
  }

  function renderCounters(registry) {
    const global = registry.global_counters || {};
    const messages = (state.snapshot && state.snapshot.messages) || {};
    const forwardRules = (state.snapshot && state.snapshot.forward_rules) || {};
    const rows = Object.keys(global).sort().map((mid) => {
      const g = global[mid] || {};
      const meta = messages[mid] || {};
      const forward = forwardRules[mid] ? ` → ${forwardRules[mid].join(', ')}` : '';
      return `
        <tr>
          <td class="counter-mid">${mid}</td>
          <td>${escapeHtml(meta.name || g.name || '')}</td>
          <td class="counter-proto">${(meta.proto || '').toUpperCase()}</td>
          <td class="counter-proto">${escapeHtml(meta.direction || '')}${forward}</td>
          <td>${g.rx_count || 0}</td>
          <td>${g.tx_count || 0}</td>
          <td class="counter-hz">${g.hz ? g.hz.toFixed(2) : '—'}</td>
          <td>${g.last_rx_ts ? humanTime(g.last_rx_ts) : '—'}</td>
        </tr>
      `;
    }).join('');
    els.counterBody.innerHTML = rows;
  }

  // ── traffic feed ────────────────────────────────────────
  function renderTrafficInit(events) {
    els.trafficFeed.innerHTML = '';
    events.slice(-120).forEach(appendTraffic);
  }

  function appendTraffic(evt) {
    if (!passesFilter(evt)) return;
    const row = document.createElement('div');
    row.className = `traffic-row ${evt.kind}${evt.ok ? '' : ' fail'}`;
    row.innerHTML = `
      <span class="traffic-ts">${humanTime(evt.ts)}</span>
      <span class="traffic-kind ${evt.kind}">${evt.kind}</span>
      <span class="traffic-mid">${evt.mid}</span>
      <span class="traffic-proto">${(evt.proto || '').toUpperCase()}</span>
      <span class="traffic-peer">${escapeHtml(evt.peer_role || '—')} ${escapeHtml(evt.peer_ip || '')}:${evt.peer_port || ''}</span>
      <span class="traffic-note" title="${escapeAttr(JSON.stringify(evt.payload_preview || ''))}">${escapeHtml(evt.note || evt.name || '')}</span>
    `;
    els.trafficFeed.appendChild(row);
    while (els.trafficFeed.children.length > 300) {
      els.trafficFeed.removeChild(els.trafficFeed.firstChild);
    }
    els.trafficFeed.scrollTop = els.trafficFeed.scrollHeight;
  }

  function passesFilter(evt) {
    if (evt.kind === 'rx' && !state.filters.rx) return false;
    if (evt.kind === 'tx' && !state.filters.tx) return false;
    if (evt.mid === '0002' && !state.filters['0002']) return false;
    if (evt.mid === '0003' && !state.filters['0003']) return false;
    if (evt.mid === '4001' && !state.filters['4001']) return false;
    return true;
  }

  // ── drawer ──────────────────────────────────────────────
  function openDrawer(role) {
    state.selectedRole = role;
    const module = state.modules.find((m) => m.role === role);
    if (!module) return;
    renderDrawer(module);
    els.drawer.classList.add('open');
    els.drawer.setAttribute('aria-hidden', 'false');
  }
  function closeDrawer() {
    els.drawer.classList.remove('open');
    els.drawer.setAttribute('aria-hidden', 'true');
    state.selectedRole = null;
  }

  function renderDrawer(module) {
    els.drawerTitle.textContent = `${module.display_name || module.role}`;
    els.drawerSub.textContent = `role=${module.role} · source=${module.last_source || module.expected_source || '—'}`;

    const connected = module.connected;
    const endpointHtml = `
      <div class="drawer-section">
        <div class="drawer-section-title">Endpoint</div>
        <div class="drawer-fields">
          <div class="drawer-field">
            <label>IP</label>
            <input id="drw-ip" value="${escapeAttr(module.ip)}" />
          </div>
          <div class="drawer-field">
            <label>UDP port</label>
            <input id="drw-udp" type="number" value="${module.udp_port}" />
          </div>
          <div class="drawer-field">
            <label>TCP port</label>
            <input id="drw-tcp" type="number" value="${module.tcp_port}" />
          </div>
          <div class="drawer-field">
            <label>Expected source</label>
            <input id="drw-src" value="${escapeAttr(module.expected_source || '')}" />
          </div>
        </div>
        <div class="drawer-actions">
          <button class="btn btn-primary btn-sm" id="drw-save">Save</button>
          <span class="drawer-sub" id="drw-save-status"></span>
        </div>
      </div>
    `;

    const statusHtml = `
      <div class="drawer-section">
        <div class="drawer-section-title">Module Status (MSG 0002)</div>
        <dl class="drawer-kv">
          <dt>Connected</dt><dd>${connected ? 'yes' : 'no'}</dd>
          <dt>Last heartbeat</dt><dd>${module.last_heartbeat_ts ? new Date(module.last_heartbeat_ts * 1000).toISOString() : '—'}</dd>
          <dt>RX</dt><dd>${module.rx_count || 0}</dd>
          <dt>TX</dt><dd>${module.tx_count || 0}</dd>
        </dl>
        <div class="drawer-sub" style="margin-top:8px">Last payload</div>
        <pre class="json-box">${escapeHtml(JSON.stringify(module.last_status || {}, null, 2))}</pre>
      </div>
    `;

    const mids = Object.keys(module.messages || {}).sort();
    const midRows = mids.map((mid) => {
      const c = module.messages[mid] || {};
      return `<tr>
        <td class="counter-mid">${mid}</td>
        <td>${escapeHtml(c.name || '')}</td>
        <td>${c.rx_count || 0}</td>
        <td>${c.tx_count || 0}</td>
        <td class="counter-hz">${c.hz ? c.hz.toFixed(2) : '—'}</td>
      </tr>`;
    }).join('');
    const mpsHtml = mids.length ? `
      <div class="drawer-section">
        <div class="drawer-section-title">Message Throughput</div>
        <table class="counter-table">
          <thead><tr><th>MID</th><th>Name</th><th>RX</th><th>TX</th><th>Hz</th></tr></thead>
          <tbody>${midRows}</tbody>
        </table>
      </div>
    ` : '';

    els.drawerBody.innerHTML = endpointHtml + statusHtml + mpsHtml;
    const saveBtn = document.getElementById('drw-save');
    saveBtn.addEventListener('click', async () => {
      const payload = {
        ip: document.getElementById('drw-ip').value.trim(),
        udp_port: parseInt(document.getElementById('drw-udp').value, 10),
        tcp_port: parseInt(document.getElementById('drw-tcp').value, 10),
        expected_source: document.getElementById('drw-src').value.trim(),
      };
      const status = document.getElementById('drw-save-status');
      status.textContent = 'saving…';
      try {
        await api(`/api/modules/${encodeURIComponent(module.role)}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        status.textContent = 'saved';
        await refreshState();
      } catch (e) {
        status.textContent = `failed: ${e.message || e}`;
      }
    });
  }

  // ── WebSocket ───────────────────────────────────────────
  let ws = null;
  let reconnectHandle = 0;
  function connectWs() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `ws://127.0.0.1:8096/ws/events`;
    ws = new WebSocket(url);
    ws.onopen = () => {
      console.log('[DSE] ws open');
    };
    ws.onmessage = (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch { return; }
      if (msg.type === 'snapshot') renderSnapshot(msg);
      else if (msg.type === 'traffic') {
        appendTraffic(msg);
        // Hz/counter 를 서버에서 주기적으로 받지 않으므로 state 만 미세 업데이트
      }
    };
    ws.onclose = () => {
      if (reconnectHandle) window.clearTimeout(reconnectHandle);
      reconnectHandle = window.setTimeout(connectWs, 1500);
    };
    ws.onerror = () => {
      try { ws.close(); } catch {}
    };
  }

  async function refreshState() {
    try {
      const snapshot = await api('/api/state');
      renderSnapshot(snapshot);
    } catch (e) {
      console.warn('refreshState failed', e);
    }
  }

  // ── filters / actions ───────────────────────────────────
  function wireFilters() {
    const toggles = [
      ['rx', els.filterRx],
      ['tx', els.filterTx],
      ['0002', els.filter0002],
      ['0003', els.filter0003],
      ['4001', els.filter4001],
    ];
    toggles.forEach(([key, el]) => {
      el.addEventListener('change', () => {
        state.filters[key] = !!el.checked;
      });
    });
    els.btnClearTraffic.addEventListener('click', () => {
      els.trafficFeed.innerHTML = '';
    });
    els.btnOpenDb.addEventListener('click', async () => {
      try { await api('/api/db/open-folder', { method: 'POST' }); } catch (_) {}
    });
    els.btnRefresh.addEventListener('click', () => refreshState());
    els.drawerClose.addEventListener('click', closeDrawer);
  }

  // ── periodic uptime / heartbeat refresh ────────────────
  function startTicker() {
    window.setInterval(() => {
      if (!state.snapshot) return;
      state.snapshot.uptime_s = (state.snapshot.uptime_s || 0) + 1;
      els.statUptime.textContent = humanUptime(state.snapshot.uptime_s);
    }, 1000);
    window.setInterval(() => refreshState(), 3000);
  }

  function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
  function escapeAttr(value) {
    return escapeHtml(value).replace(/'/g, '&#39;');
  }

  // ── bootstrap ───────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', async () => {
    wireFilters();
    await refreshState();
    connectWs();
    startTicker();
  });
})();
