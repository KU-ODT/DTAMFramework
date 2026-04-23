const $ = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => [...r.querySelectorAll(s)];

let STATE_CACHE = {self_rx: {}, targets: [], messages: []};
let modalCtx = null;
let SELF_RX_DIRTY = false;

// ---------- toast ----------
function toast(msg, err=false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = err ? "show err" : "show";
  clearTimeout(t._to);
  t._to = setTimeout(() => t.className = "", 1800);
}

// ---------- tabs ----------
$$(".tab").forEach(b => b.addEventListener("click", () => {
  $$(".tab").forEach(x => x.classList.toggle("active", x === b));
  $$(".tab-panel").forEach(p => p.classList.toggle("active", p.id === "tab-" + b.dataset.tab));
}));
$$(".mtab").forEach(b => b.addEventListener("click", () => {
  $$(".mtab").forEach(x => x.classList.toggle("active", x === b));
  $$(".mpanel").forEach(p => p.classList.toggle("active", p.id === "mpanel-" + b.dataset.mtab));
}));

// ---------- fetch ----------
async function api(method, url, body) {
  const r = await fetch(url, {
    method,
    headers: {"Content-Type": "application/json"},
    body: body ? JSON.stringify(body) : undefined,
  });
  return r.json();
}

// ---------- format ----------
function tsFmt(ts) {
  if (!ts) return "-";
  const d = new Date(ts * 1000);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  const ms = String(d.getMilliseconds()).padStart(3, "0");
  return `${hh}:${mm}:${ss}.${ms}`;
}
function rxStatus(m) {
  if (!m.rx_enabled) return {text: "수신 대기", cls: "status-idle"};
  if (!m.rx_count) return {text: "수신 전", cls: "status-idle"};
  if (m.rx_age != null && m.rx_age > 2) return {text: `수신 중단 (${m.rx_age.toFixed(1)}s)`, cls: "status-stale"};
  return {text: `수신 중 (${m.rx_count})`, cls: "status-active"};
}
function pingStatus(m) {
  const p = m.ping || {};
  if (p.ok === null || p.ok === undefined) return {text: "미확인", cls: "status-idle"};
  return {text: p.msg || (p.ok ? "OK" : "실패"), cls: p.ok ? "status-ok" : "status-err"};
}

// ---------- render: 정보관리 ----------
function renderInfoTab() {
  const txTb = $("#tx-tbody");
  const rxTb = $("#rx-tbody");
  txTb.innerHTML = "";
  rxTb.innerHTML = "";

  const CATEGORIES = {
    "0": {name: "Module Status",    cls: "cat-0"},
    "1": {name: "Setting",          cls: "cat-1"},
    "2": {name: "User Request",     cls: "cat-2"},
    "3": {name: "Flight Plan",      cls: "cat-3"},
    "4": {name: "Vehicle Data",     cls: "cat-4"},
  };
  const msgs = [...STATE_CACHE.messages].sort((a, b) => a.id.localeCompare(b.id));

  if (msgs.length === 0) {
    txTb.innerHTML = `<tr><td colspan="6" class="empty">메시지 없음</td></tr>`;
    rxTb.innerHTML = `<tr><td colspan="5" class="empty">메시지 없음</td></tr>`;
    return;
  }

  let lastCat = "";
  for (const msg of msgs) {
    const cat = msg.id.charAt(0);
    if (cat !== lastCat) {
      lastCat = cat;
      const c = CATEGORIES[cat] || {name: `Category ${cat}xxx`, cls: "cat-x"};
      const hdrTx = document.createElement("tr");
      hdrTx.className = `cat-header ${c.cls}`;
      hdrTx.innerHTML = `<td colspan="7"><span class="cat-dot"></span>${c.name}</td>`;
      txTb.appendChild(hdrTx);
      const hdrRx = document.createElement("tr");
      hdrRx.className = `cat-header ${c.cls}`;
      hdrRx.innerHTML = `<td colspan="5"><span class="cat-dot"></span>${c.name}</td>`;
      rxTb.appendChild(hdrRx);
    }
    const txStatus = msg.tx_count
      ? {text: `송신 ${msg.tx_count}회 · ${tsFmt(msg.tx_last_ts)}`, cls: "status-active"}
      : {text: "발신 전", cls: "status-idle"};
    const tr = document.createElement("tr");
    const proto = (msg.protocol || "udp").toUpperCase();
    const protoCls = proto === "TCP" ? "proto-tcp" : "proto-udp";
    tr.innerHTML = `
      <td>${msg.id}</td>
      <td>${escapeHtml(msg.name)}</td>
      <td class="name-en">${escapeHtml(msg.name_en || "")}</td>
      <td><button class="btn-proto ${protoCls}" data-toggle-proto="${msg.id}">${proto}</button></td>
      <td class="col-status ${txStatus.cls}">${txStatus.text}</td>
      <td><button class="btn-primary" data-send="${msg.id}">발신</button></td>
      <td><button class="btn" data-view-tx="${msg.id}">보기</button></td>`;
    txTb.appendChild(tr);

    const rxS = msg.rx_count
      ? {text: `수신 ${msg.rx_count}회 · ${tsFmt(msg.rx_last_ts)}`, cls: "status-active"}
      : {text: "수신 전", cls: "status-idle"};
    const tr2 = document.createElement("tr");
    tr2.innerHTML = `
      <td>${msg.id}</td>
      <td>${escapeHtml(msg.name)}</td>
      <td class="name-en">${escapeHtml(msg.name_en || "")}</td>
      <td class="col-status ${rxS.cls}">${rxS.text}</td>
      <td><button class="btn" data-view-rx="${msg.id}">보기</button></td>`;
    rxTb.appendChild(tr2);
  }
}

// ---------- render: 통신관리 ----------
function renderCommTab() {
  // self_rx
  const sr = STATE_CACHE.self_rx || {};
  if (!SELF_RX_DIRTY) {
    $("#self-ip").value = sr.bind_ip ?? "127.0.0.1";
    $("#self-port").value = sr.bind_port ?? 17000;
  }
  const st = $("#self-status");
  if (sr.enabled) {
    const cnt = sr.rx_count || 0;
    const age = sr.rx_age;
    if (!cnt) { st.textContent = "수신 대기 중"; st.className = "status-active"; }
    else if (age != null && age > 2) { st.textContent = `수신 중단 (${age.toFixed(1)}s)`; st.className = "status-stale"; }
    else { st.textContent = `수신 중 · 누적 ${cnt}`; st.className = "status-active"; }
  } else {
    st.textContent = "중지";
    st.className = "status-idle";
  }

  // targets
  const tb = $("#tgt-tbody");
  if (!STATE_CACHE.targets.length) {
    tb.innerHTML = `<tr><td colspan="8" class="empty">등록된 송신 대상 없음</td></tr>`;
    return;
  }
  tb.innerHTML = "";
  for (const t of STATE_CACHE.targets) {
    const pg = pingStatus(t);
    const tx = t.tx_count
      ? {text: `송신 ${t.tx_count}회 · ${tsFmt(t.tx_last_ts)}`, cls: "status-active"}
      : {text: "송신 전", cls: "status-idle"};
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${escapeHtml(t.name)}</strong></td>
      <td><input data-t-ip="${t.name}" value="${t.ip}" /></td>
      <td><input data-t-port="${t.name}" type="number" value="${t.port}" /></td>
      <td><input data-t-tcp-port="${t.name}" type="number" value="${t.tcp_port}" /></td>
      <td>${(t.protocol || "udp").toUpperCase()}</td>
      <td class="${tx.cls}">${tx.text}</td>
      <td>
        <button class="btn" data-t-ping="${t.name}">Ping</button>
        <span class="${pg.cls}" style="margin-left:6px">${escapeHtml(pg.text)}</span>
      </td>
      <td>
        <button class="btn" data-t-apply="${t.name}">적용</button>
        <button class="btn-ghost" data-t-del="${t.name}">삭제</button>
      </td>`;
    tb.appendChild(tr);
  }
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

// ---------- events ----------
document.addEventListener("click", async (e) => {
  const t = e.target;
  const d = t.dataset;

  // 메시지
  if (d.send) {
    const r = await api("POST", `/api/messages/${d.send}/send`);
    toast(r.msg, !r.ok);
    refresh();
  } else if (d.toggleProto) {
    const mid = d.toggleProto;
    const msg = (STATE_CACHE.messages || []).find(m => m.id === mid);
    const cur = (msg && msg.protocol) || "udp";
    const next = cur === "udp" ? "tcp" : "udp";
    const r = await api("PATCH", `/api/messages/${mid}/protocol`, {protocol: next});
    toast(r.msg, !r.ok);
    refresh();
  } else if (d.viewTx) {
    openTxModal(d.viewTx);
  } else if (d.viewRx) {
    openRxModal(d.viewRx);
  }

  // self_rx
  else if (t.id === "self-apply") {
    const r = await api("PATCH", "/api/self_rx", {
      bind_ip: $("#self-ip").value.trim(),
      bind_port: parseInt($("#self-port").value),
    });
    if (r.ok) SELF_RX_DIRTY = false;
    toast(r.msg, !r.ok); refresh();
  } else if (t.id === "self-start") {
    await api("PATCH", "/api/self_rx", {
      bind_ip: $("#self-ip").value.trim(),
      bind_port: parseInt($("#self-port").value),
    });
    const r = await api("POST", "/api/self_rx/start");
    if (r.ok) SELF_RX_DIRTY = false;
    toast(r.msg, !r.ok); refresh();
  } else if (t.id === "self-stop") {
    const saved = await api("PATCH", "/api/self_rx", {
      bind_ip: $("#self-ip").value.trim(),
      bind_port: parseInt($("#self-port").value),
    });
    if (!saved.ok) { toast(saved.msg, true); return; }
    const r = await api("POST", "/api/self_rx/stop");
    if (r.ok) SELF_RX_DIRTY = false;
    toast(r.msg, !r.ok); refresh();
  }

  // target 추가
  else if (t.id === "tgt-add") {
    const body = {
      name: $("#tgt-name").value.trim(),
      ip: $("#tgt-ip").value.trim(),
      port: parseInt($("#tgt-port").value),
      tcp_port: parseInt($("#tgt-tcp-port").value),
      protocol: $("#tgt-protocol").value,
    };
    if (!body.name) { toast("이름 필수", true); return; }
    const r = await api("POST", "/api/targets", body);
    toast(r.msg, !r.ok);
    if (r.ok) $("#tgt-name").value = "";
    refresh();
  }

  // target 제어
  else if (d.tApply) {
    const n = d.tApply;
    const r = await api("PATCH", `/api/targets/${encodeURIComponent(n)}`, {
      ip: $(`[data-t-ip="${n}"]`).value.trim(),
      port: parseInt($(`[data-t-port="${n}"]`).value),
      tcp_port: parseInt($(`[data-t-tcp-port="${n}"]`).value),
    });
    toast(r.msg, !r.ok); refresh();
  } else if (d.tPing) {
    const r = await api("POST", `/api/targets/${encodeURIComponent(d.tPing)}/ping`);
    toast(r.msg, !r.ok); refresh();
  } else if (d.tDel) {
    if (!confirm(`'${d.tDel}' 삭제?`)) return;
    const r = await api("DELETE", `/api/targets/${encodeURIComponent(d.tDel)}`);
    toast(r.msg, !r.ok); refresh();
  }

  // modal
  else if (t.id === "modal-close") closeModal();
  else if (t.id === "modal-save") saveTemplate();
});

document.addEventListener("change", async (e) => {
  const d = e.target.dataset;
  if (d.msgModule) {
    const r = await api("PATCH", `/api/messages/${d.msgModule}/module`, {module: e.target.value});
    toast(r.msg, !r.ok);
  }
});

document.addEventListener("input", (e) => {
  if (e.target.id === "self-ip" || e.target.id === "self-port") {
    SELF_RX_DIRTY = true;
  }
});

// ---------- modal ----------
function showOnly(panelId) {
  $$(".mpanel").forEach(p => p.classList.toggle("active", p.id === panelId));
}

async function openTxModal(mid) {
  const r = await api("GET", `/api/messages/${mid}/tx_last`);
  modalCtx = {mid, dir: "tx"};
  $("#modal-title").textContent = `[송신] ${r.id} ${r.name}`;
  const sent = r.last_sent;
  // _image_base64 가 있으면 이미지 표시 + JSON에서 제거
  const imgBox = $("#modal-image-box");
  const imgEl = $("#modal-image");
  if (sent && sent._image_base64) {
    imgEl.src = `data:${imageMime(sent)};base64,` + sent._image_base64;
    imgBox.classList.remove("hidden");
    const display = Object.assign({}, sent);
    delete display._image_base64;
    delete display._image_mime;
    display._image = "(아래 이미지 참조)";
    $("#modal-sent").value = JSON.stringify(display, null, 2);
  } else {
    imgBox.classList.add("hidden");
    $("#modal-sent").value = sent ? JSON.stringify(sent, null, 2) : "(아직 송신 없음 — 발신 버튼을 눌러주세요)";
  }
  $("#modal-sent-count").textContent = r.tx_count;
  $("#modal-sent-time").textContent = tsFmt(r.tx_last_ts);
  $("#modal-sent-len").textContent = r.last_sent_bytes_len;
  const proto = (r.protocol || "udp").toUpperCase();
  $("#modal-sent-hint").textContent = `generator 가 ICD 에 맞춰 생성하여 ${proto} 로 송신한 실제 데이터.`;
  showOnly("mpanel-sent");
  $("#modal").classList.remove("hidden");
}

async function openRxModal(mid) {
  const r = await api("GET", `/api/messages/${mid}/rx_last`);
  modalCtx = {mid, dir: "rx"};
  $("#modal-title").textContent = `[수신] ${r.id} ${r.name}`;
  const rx = r.last_received;
  const rxImgBox = $("#modal-rx-image-box");
  const rxImgEl = $("#modal-rx-image");
  if (rx && rx._image_base64) {
    rxImgEl.src = `data:${imageMime(rx)};base64,` + rx._image_base64;
    rxImgBox.classList.remove("hidden");
    const display = Object.assign({}, rx);
    delete display._image_base64;
    delete display._image_mime;
    display._image = "(아래 이미지 참조)";
    $("#modal-rx").value = JSON.stringify(display, null, 2);
  } else {
    rxImgBox.classList.add("hidden");
    $("#modal-rx").value = rx && Object.keys(rx).length
      ? JSON.stringify(rx, null, 2) : "(아직 수신 없음)";
  }
  $("#modal-rx-count").textContent = r.rx_count;
  $("#modal-rx-time").textContent = tsFmt(r.rx_last_ts);
  showOnly("mpanel-rx");
  $("#modal").classList.remove("hidden");
}

function closeModal() { $("#modal").classList.add("hidden"); modalCtx = null; }

function imageMime(obj) {
  if (!obj) return "image/jpeg";
  if (obj._image_mime) return obj._image_mime;
  const enc = String(obj.encoding || "").toLowerCase();
  if (enc === "png" || enc === "depth_png") return "image/png";
  if (enc === "jpeg" || enc === "jpg") return "image/jpeg";
  return "application/octet-stream";
}

async function saveTemplate() {
  if (!modalCtx || modalCtx.dir !== "tx") return;
  let obj;
  try { obj = JSON.parse($("#modal-template").value); }
  catch (e) { toast("JSON 파싱 오류: " + e.message, true); return; }
  const r = await api("PATCH", `/api/messages/${modalCtx.mid}/payload`, {payload: obj});
  toast(r.msg, !r.ok);
  if (r.ok) closeModal();
  refresh();
}

// ---------- sequence diagram ----------
const SEQ_FILES = {
  ko: "/static/data/sequence_diagram_ko.json",
  en: "/static/data/sequence_diagram_en.json",
};
let SEQ_LANG = localStorage.getItem("dtam_seq_lang") || "ko";
if (!SEQ_FILES[SEQ_LANG]) SEQ_LANG = "ko";

function syncSeqLangButtons() {
  $$(".seq-lang-btn").forEach(b => {
    b.classList.toggle("active", b.dataset.seqLang === SEQ_LANG);
  });
}

async function renderSeqDiagram() {
  const el = $("#seq-diagram");
  if (!el) return;

  const dataFile = SEQ_FILES[SEQ_LANG] || SEQ_FILES.ko;
  let data;
  try {
    const r = await fetch(dataFile, {cache: "no-store"});
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    data = await r.json();
  } catch (e) {
    el.innerHTML = `<div style="padding:20px;color:#c0392b">${dataFile} 로드 실패: ${e.message}</div>`;
    return;
  }

  const ACTORS = data.actors;
  const MESSAGES = data.messages;
  const actorIdx = {};
  ACTORS.forEach((a, i) => actorIdx[a.id] = i);

  const colW = 180;
  const totalW = colW * ACTORS.length;
  const rowH = 48;
  const groupH = 38;

  // center X for each actor column
  const cx = (i) => i * colW + colW / 2;

  // build actors bar
  const actorBar = (sticky = false) => {
    const barCls = sticky ? "seq-header-top" : "seq-header";
    let h = `<div class="${barCls}" style="width:${totalW}px">`;
    ACTORS.forEach(a => {
      const cls = a.color ? `actor-${a.color}` : "";
      const label = a.name.replace(/\\n/g, "<br>");
      h += `<div class="seq-actor" style="width:${colW}px">`;
      h += `<div class="seq-actor-box ${cls}">${label}</div>`;
      if (sticky) h += `<div class="seq-actor-lifeline"></div>`;
      h += `</div>`;
    });
    return h + `</div>`;
  };

  // count body height
  let bodyH = 0;
  MESSAGES.forEach(m => bodyH += m.group ? groupH : rowH);

  // SVG lifelines + arrows (마커 없이 line + polygon으로 직접 그림 → 방향 무관 갭 없음)
  let svg = `<svg style="position:absolute;top:0;left:0;width:${totalW}px;height:${bodyH}px;pointer-events:none">`;
  const AH = 9;   // 화살촉 길이
  const AHW = 5;  // 화살촉 반폭

  // lifelines
  ACTORS.forEach((_, i) => {
    svg += `<line x1="${cx(i)}" y1="0" x2="${cx(i)}" y2="${bodyH}" stroke="#d0d6e0" stroke-width="1.5" stroke-dasharray="6,4"/>`;
  });

  // arrows + labels
  let labels = "";
  let y = 0;
  for (const msg of MESSAGES) {
    if (msg.group) { y += groupH; continue; }
    const fi = actorIdx[msg.from];
    const ti = actorIdx[msg.to];
    const x1 = cx(fi);
    const x2 = cx(ti);
    const my = y + rowH / 2 + 6;
    const proto = msg.proto === "TCP" ? "tcp" : msg.proto === "UDP" ? "udp" : "int";
    const strokeColor = proto === "tcp" ? "#3b78d8" : proto === "udp" ? "#43a047" : "#8892a6";

    let txt = `<span class="seq-msg-id">${msg.id ? msg.id + ' ' : ''}</span><span class="seq-msg-name">${escapeHtml(msg.name)}</span>`;
    txt += `<span class="seq-msg-proto">${msg.proto}</span>`;
    if (msg.note) txt += `<span class="seq-msg-proto"> · ${escapeHtml(msg.note)}</span>`;

    if (fi === ti) {
      // self-loop: 오른쪽으로 작은 루프
      const loopW = 36; const loopH = 20;
      const ly1 = my - loopH / 2; const ly2 = my + loopH / 2;
      svg += `<polyline points="${x1},${ly1} ${x1+loopW},${ly1} ${x1+loopW},${ly2} ${x1+AH},${ly2}" fill="none" stroke="${strokeColor}" stroke-width="1.5" stroke-dasharray="4,3"/>`;
      svg += `<polygon points="${x1},${ly2} ${x1+AH},${ly2-AHW} ${x1+AH},${ly2+AHW}" fill="${strokeColor}"/>`;
      labels += `<div class="seq-label" style="left:${x1 + loopW + 5}px;top:${y + 8}px">${txt}</div>`;
    } else {
      // 방향에 따라 선 끝을 화살촉 기저까지만 그림
      const dir = x2 > x1 ? 1 : -1;
      const tipX = x2;
      const baseX = tipX - dir * AH;
      svg += `<line x1="${x1}" y1="${my}" x2="${baseX}" y2="${my}" stroke="${strokeColor}" stroke-width="2"/>`;
      svg += `<polygon points="${tipX},${my} ${baseX},${my - AHW} ${baseX},${my + AHW}" fill="${strokeColor}"/>`;
      const labelX = (x1 + x2) / 2;
      labels += `<div class="seq-label" style="left:${labelX}px;top:${y + 8}px;transform:translateX(-50%)">${txt}</div>`;
    }

    y += rowH;
  }
  svg += `</svg>`;

  // group labels
  let groups = "";
  y = 0;
  for (const msg of MESSAGES) {
    if (msg.group) {
      groups += `<div class="seq-group" style="position:absolute;top:${y}px;left:0;height:${groupH}px;display:flex;align-items:center"><span class="seq-group-label">${escapeHtml(msg.group)}</span></div>`;
      y += groupH;
    } else {
      y += rowH;
    }
  }

  let html = actorBar(true);
  html += `<div class="seq-sticky-group" id="seq-sticky-group"></div>`;
  html += `<div class="seq-body" style="width:${totalW}px;height:${bodyH}px;position:relative">`;
  html += svg;
  html += labels;
  html += groups;
  html += `</div>`;
  html += actorBar();

  el.innerHTML = html;

  // sticky group label: top = actor bar height, text = current phase
  const actorBarEl = el.querySelector('.seq-header-top');
  const stickyGroupEl = el.querySelector('#seq-sticky-group');
  stickyGroupEl.style.top = (actorBarEl ? actorBarEl.offsetHeight : 0) + 'px';

  const groupMap = [];
  let gy = 0;
  for (const msg of MESSAGES) {
    if (msg.group) { groupMap.push({y: gy, label: msg.group}); gy += groupH; }
    else gy += rowH;
  }

  const syncGroup = () => {
    let current = groupMap[0]?.label || "";
    for (const g of groupMap) { if (g.y <= el.scrollTop) current = g.label; }
    stickyGroupEl.textContent = current;
  };
  if (el._scrollHandler) el.removeEventListener('scroll', el._scrollHandler);
  el._scrollHandler = syncGroup;
  el.addEventListener('scroll', syncGroup);
  syncGroup();
}

$$(".seq-lang-btn").forEach(b => b.addEventListener("click", () => {
  const lang = b.dataset.seqLang;
  if (!SEQ_FILES[lang] || lang === SEQ_LANG) return;
  SEQ_LANG = lang;
  localStorage.setItem("dtam_seq_lang", lang);
  syncSeqLangButtons();
  renderSeqDiagram();
}));
syncSeqLangButtons();

// render sequence diagram every time tab is opened (JSON 수정 반영)
$$(".tab").forEach(b => b.addEventListener("click", () => {
  if (b.dataset.tab === "seq") renderSeqDiagram();
}));

// ---------- refresh ----------
async function refresh() {
  try {
    const r = await api("GET", "/api/state");
    STATE_CACHE = r;
    renderInfoTab();
    renderCommTab();
  } catch (e) { console.error(e); }
}

refresh();
setInterval(refresh, 800);
