/* DTAM Simulation State Monitor — single-page GUI.
 *
 * 호스트: SimulationState (port 8096) — 모든 fetch / ws 가 same-origin.
 *
 * - WebSocket /ws/events  : 초기 snapshot + 실시간 traffic 이벤트
 * - REST     /api/state   : 폴링용 스냅샷 (3초 간격)
 * - REST     /api/modules/{role} (PATCH)  : 모듈 endpoint 수정
 * - REST     /api/db/stats, /api/db/open-folder
 *
 * 새 위젯: Live Sequence Diagram — TrafficEvent 가 도착할 때마다
 * 해당 actor 사이의 화살표를 짧게 깜빡인다.
 */
(function () {
  'use strict';

  const SVG_NS = 'http://www.w3.org/2000/svg';

  const state = {
    snapshot: null,
    modules: [],
    filters: { rx: true, tx: true, '0002': false, '0003': false, '4001': false },
    selectedRole: null,
    sequencePaused: false,
    actors: [],            // sequence_diagram.json 의 actors
    actorIndex: {},        // id -> index
    laneX: {},             // id -> x 좌표
    laneTopY: 36,
    laneBottomY: 270,
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
    seqSvg: document.getElementById('sequence-svg'),
    seqPause: document.getElementById('seq-pause'),
    btnClearSeq: document.getElementById('btn-clear-seq'),
  };

  // ── utility ─────────────────────────────────────────────
  function humanTime(ts) {
    if (!ts) return '—';
    const d = new Date(ts * 1000);
    return d.toISOString().slice(11, 23);
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
    // 8095 (CoreServer) 로 보내야 하는 라우트
    const toCore = ['/api/v1/process/', '/api/icd'];
    const isCoreApi = toCore.some(p => path.startsWith(p));
    const url = isCoreApi
      ? `${location.protocol}//${location.hostname}:8095${path}`
      : path;
    const resp = await fetch(url, options || {});
    if (!resp.ok && resp.status !== 400) throw new Error(`${resp.status} ${resp.statusText}`);
    const ctype = resp.headers.get('content-type') || '';
    if (ctype.includes('json')) return await resp.json();
    return await resp.text();
  }

  // ── snapshot rendering ─────────────────────────────────
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
    // 시퀀스 다이어그램은 라이브 이벤트만 시각화 (초기 스냅샷은 굳이 재생 X)
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

    const controlHtml = `
      <div class="drawer-section">
        <div class="drawer-section-title">Process Control</div>
        <div class="drawer-actions">
          <button class="btn btn-primary" id="drw-start" ${connected ? 'disabled' : ''}>🚀 Execute Module</button>
          <button class="btn btn-ghost" id="drw-stop">🛑 Terminate</button>
        </div>
        <div id="drw-proc-status" class="drawer-sub" style="margin-top:8px"></div>
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

    els.drawerBody.innerHTML = endpointHtml + statusHtml + controlHtml + mpsHtml;
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

    const startBtn = document.getElementById('drw-start');
    const stopBtn = document.getElementById('drw-stop');
    const procStatus = document.getElementById('drw-proc-status');

    if (startBtn) {
      startBtn.addEventListener('click', async () => {
        procStatus.textContent = 'starting…';
        try {
          const res = await api(`/api/v1/process/${module.role}/start`, { method: 'POST' });
          procStatus.textContent = res.message || 'started';
          await refreshState();
        } catch (e) {
          procStatus.textContent = `failed: ${e.message || e}`;
        }
      });
    }

    if (stopBtn) {
      stopBtn.addEventListener('click', async () => {
        procStatus.textContent = 'stopping…';
        try {
          const res = await api(`/api/v1/process/${module.role}/stop`, { method: 'POST' });
          procStatus.textContent = res.message || 'stopped';
          await refreshState();
        } catch (e) {
          procStatus.textContent = `failed: ${e.message || e}`;
        }
      });
    }
  }

  // ── Live Sequence Diagram ──────────────────────────────
  // 우리는 sequence_diagram.json 의 actors 를 사용해 lane 을 그린 뒤
  // TrafficEvent 의 (peer_role, kind) 를 (server, peer_role) 화살표로 변환한다.
  // server (sim_state) 가 가운데, 클라이언트 모듈들이 양옆 배치.

  const ACTOR_ORDER = ['user', 'monitoring', 'mission', 'server', 'sim_state', 'vehicle', 'visual'];

  async function loadSequenceActors() {
    try {
      const data = await api('/api/sequence-diagram?lang=ko');
      let actors = (data && data.actors) || [];
      if (!actors.length) actors = defaultActors();
      // 정렬: ACTOR_ORDER 기준
      actors.sort((a, b) => {
        const ai = ACTOR_ORDER.indexOf(a.id);
        const bi = ACTOR_ORDER.indexOf(b.id);
        return (ai < 0 ? 999 : ai) - (bi < 0 ? 999 : bi);
      });
      state.actors = actors;
      state.actorIndex = {};
      actors.forEach((a, i) => { state.actorIndex[a.id] = i; });
      renderSequenceLanes();
    } catch (e) {
      console.warn('loadSequenceActors failed', e);
      state.actors = defaultActors();
      state.actors.forEach((a, i) => { state.actorIndex[a.id] = i; });
      renderSequenceLanes();
    }
  }

  function defaultActors() {
    return [
      { id: 'user',       name: '사용자',       color: 'user' },
      { id: 'monitoring', name: '운용\n콘솔',    color: 'monitoring' },
      { id: 'mission',    name: '임무\n계획',    color: 'mission' },
      { id: 'server',     name: 'DTAM\nCore',    color: 'server' },
      { id: 'sim_state',  name: '시뮬레이션\n상태', color: 'server' },
      { id: 'vehicle',    name: '비행체',        color: 'vehicle' },
      { id: 'visual',     name: '시각화',        color: 'visual' },
    ];
  }

  function renderSequenceLanes() {
    const svg = els.seqSvg;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const w = Math.max(700, rect.width || 900);
    const h = rect.height || 280;
    svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
    svg.innerHTML = '';

    // arrowhead marker 정의
    const defs = document.createElementNS(SVG_NS, 'defs');
    ['rx', 'tx', 'fail'].forEach((kind) => {
      const color = kind === 'rx' ? '#5ec77a' : kind === 'tx' ? '#5fb3f6' : '#f86a6a';
      const marker = document.createElementNS(SVG_NS, 'marker');
      marker.setAttribute('id', `arrow-${kind}`);
      marker.setAttribute('viewBox', '0 0 10 10');
      marker.setAttribute('refX', '9');
      marker.setAttribute('refY', '5');
      marker.setAttribute('markerWidth', '7');
      marker.setAttribute('markerHeight', '7');
      marker.setAttribute('orient', 'auto-start-reverse');
      const path = document.createElementNS(SVG_NS, 'path');
      path.setAttribute('d', 'M 0 0 L 10 5 L 0 10 z');
      path.setAttribute('fill', color);
      marker.appendChild(path);
      defs.appendChild(marker);
    });
    svg.appendChild(defs);

    const N = state.actors.length;
    if (N === 0) return;
    const margin = 40;
    const usable = w - 2 * margin;
    const step = usable / Math.max(1, N - 1);
    state.laneX = {};
    state.laneTopY = 50;
    state.laneBottomY = h - 14;

    // lane 세로 점선 + actor 라벨
    state.actors.forEach((actor, i) => {
      const x = margin + i * step;
      state.laneX[actor.id] = x;

      const line = document.createElementNS(SVG_NS, 'line');
      line.setAttribute('class', 'seq-lane-line');
      line.setAttribute('x1', x);
      line.setAttribute('x2', x);
      line.setAttribute('y1', state.laneTopY);
      line.setAttribute('y2', state.laneBottomY);
      svg.appendChild(line);

      const lines = (actor.name || actor.id).split('\n');
      const labelH = 18 + (lines.length - 1) * 12;
      const bg = document.createElementNS(SVG_NS, 'rect');
      bg.setAttribute('class', 'seq-lane-label-bg');
      bg.setAttribute('x', x - 48);
      bg.setAttribute('y', 8);
      bg.setAttribute('width', 96);
      bg.setAttribute('height', labelH);
      svg.appendChild(bg);

      lines.forEach((ln, j) => {
        const text = document.createElementNS(SVG_NS, 'text');
        text.setAttribute('class', 'seq-lane-label');
        text.setAttribute('x', x);
        text.setAttribute('y', 8 + (j + 1) * 12 + 2);
        text.textContent = ln;
        svg.appendChild(text);
      });
    });
  }

  // 도착한 TrafficEvent 를 시퀀스 다이어그램 위 화살표로 변환
  function drawTrafficArrow(evt) {
    if (state.sequencePaused) return;
    const svg = els.seqSvg;
    if (!svg || !state.actors.length) return;

    // server-side 는 'sim_state' 로 lane 매핑 (없으면 'server' 폴백)
    const serverLane = state.laneX['sim_state'] !== undefined ? 'sim_state' : 'server';
    const peer = (evt.peer_role || '').toLowerCase();
    const peerLane = state.laneX[peer] !== undefined ? peer : null;
    if (peerLane === null) return;

    let fromId, toId;
    if (evt.kind === 'rx') { fromId = peerLane; toId = serverLane; }
    else                   { fromId = serverLane; toId = peerLane; }
    if (fromId === toId) return;

    const x1 = state.laneX[fromId];
    const x2 = state.laneX[toId];
    const range = state.laneBottomY - state.laneTopY - 30;
    const y = state.laneTopY + 50 + Math.random() * range * 0.7;

    const cls = !evt.ok ? 'proto-fail' : (evt.kind === 'rx' ? 'proto-rx' : 'proto-tx');
    const markerId = !evt.ok ? 'arrow-fail' : (evt.kind === 'rx' ? 'arrow-rx' : 'arrow-tx');

    const line = document.createElementNS(SVG_NS, 'line');
    line.setAttribute('class', `seq-arrow ${cls} flash`);
    line.setAttribute('x1', x1);
    line.setAttribute('x2', x2);
    line.setAttribute('y1', y);
    line.setAttribute('y2', y);
    line.setAttribute('marker-end', `url(#${markerId})`);
    svg.appendChild(line);

    const label = document.createElementNS(SVG_NS, 'text');
    label.setAttribute('class', 'seq-arrow-label flash');
    const midX = (x1 + x2) / 2;
    label.setAttribute('x', midX);
    label.setAttribute('y', y - 4);
    label.setAttribute('text-anchor', 'middle');
    label.textContent = `${evt.mid} ${evt.name || ''}`.trim();
    svg.appendChild(label);

    // 1.2초 후 정리 — 너무 많이 쌓이면 SVG가 무거워짐
    window.setTimeout(() => {
      try { svg.removeChild(line); } catch(_){}
      try { svg.removeChild(label); } catch(_){}
    }, 1300);
  }

  function clearSequence() {
    if (els.seqSvg) {
      els.seqSvg.innerHTML = '';
      renderSequenceLanes();
    }
  }

  // ── WebSocket ───────────────────────────────────────────
  let ws = null;
  let reconnectHandle = 0;
  function connectWs() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    // same-origin: location.host 를 사용
    const url = `${proto}//${location.host}/ws/events`;
    ws = new WebSocket(url);
    ws.onopen = () => { console.log('[SS] ws open'); };
    ws.onmessage = (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch { return; }
      if (msg.type === 'snapshot') renderSnapshot(msg);
      else if (msg.type === 'traffic') {
        appendTraffic(msg);
        drawTrafficArrow(msg);
      }
    };
    ws.onclose = () => {
      if (reconnectHandle) window.clearTimeout(reconnectHandle);
      reconnectHandle = window.setTimeout(connectWs, 1500);
    };
    ws.onerror = () => { try { ws.close(); } catch {} };
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
      if (!el) return;
      el.addEventListener('change', () => {
        state.filters[key] = !!el.checked;
      });
    });
    if (els.btnClearTraffic) {
      els.btnClearTraffic.addEventListener('click', () => {
        els.trafficFeed.innerHTML = '';
      });
    }
    if (els.btnOpenDb) {
      els.btnOpenDb.addEventListener('click', async () => {
        try { await api('/api/db/open-folder', { method: 'POST' }); } catch (_) {}
      });
    }
    if (els.btnRefresh) els.btnRefresh.addEventListener('click', () => refreshState());
    if (els.drawerClose) els.drawerClose.addEventListener('click', closeDrawer);
    if (els.seqPause) {
      els.seqPause.addEventListener('change', () => {
        state.sequencePaused = !!els.seqPause.checked;
      });
    }
    if (els.btnClearSeq) els.btnClearSeq.addEventListener('click', clearSequence);
    window.addEventListener('resize', () => {
      // 리사이즈 시 lane 좌표 재계산
      renderSequenceLanes();
    });
  }

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

  document.addEventListener('DOMContentLoaded', async () => {
    wireFilters();
    await loadSequenceActors();
    await refreshState();
    connectWs();
    startTicker();
  });
})();
