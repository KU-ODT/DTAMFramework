/* simulator.js (DTAM Mission Planner 전용)
 *
 * odt_mp 의 simulator.js 를 대체한다. AirSim / simpleDynamics 재생 대신
 * DTAM 3001 (Scheduled Flight) 송신만 담당한다. 기존 mission.js 가 호출하던
 * `ODT.Simulator.startMission` 인터페이스는 그대로 유지하되, 실제 동작은
 * `/api/dtam/send` 로 3001 메시지를 전송하는 것으로 치환된다.
 *
 * 또한 `ODT.Dtam` 별칭도 노출하여, 필요 시 명시적으로 DTAM API 를 호출할
 * 수 있도록 한다.
 */
window.ODT = window.ODT || {};

ODT.Simulator = (function () {
  let state = {
    connected: true,            // DTAM 은 "transient" — 송신 시점에만 의미가 있으므로 기본 true
    sending: false,
    ready: false,
    target_ip: '127.0.0.1',
    ws_port: 8096,
    server_url: '',
    last_error: '',
    last_result: null,
  };
  let pollHandle = 0;

  function init() {
    document.addEventListener('odt:languagechange', render);
    window.addEventListener('beforeunload', teardown);

    // 하단바 speed 버튼은 DTAM 에서 의미 없음 — DTAM 상태 갱신 트리거로 재사용
    const speedBtn = document.getElementById('playback-speed-btn');
    if (speedBtn) {
      speedBtn.textContent = '⟳';
      speedBtn.title = 'Refresh DTAM status';
      speedBtn.addEventListener('click', () => refreshStatus(false));
    }

    refreshStatus(true);
    pollHandle = window.setInterval(() => refreshStatus(true), 4000);
    render();
  }

  function messages() {
    if (ODT.I18n?.getLanguage?.() === 'ko') {
      return {
        ready: 'DTAM 서버 준비됨. 하단 Send 3001 을 눌러 송신하세요.',
        notReady: 'DTAM 송신기가 초기화되지 않았습니다.',
        sendingTitle: '3001 송신',
        sendingOk: (count) => `3001 ${count}건 송신 완료.`,
        sendingFail: '3001 송신 실패.',
        validationFail: 'Mission ICD validation 에 실패했습니다.',
        noMission: '먼저 route 를 계산하거나 free mission waypoint 를 구성하세요.',
        statusConnected: 'DTAM',
        statusDisconnected: 'DTAM 미설정',
        sendBtn: 'Send 3001',
        sendBtnBusy: '송신 중...',
        noFleet: '편대를 아직 구성하지 않았습니다.',
        fleetCount: (count) => `기체 ${count}대`,
      };
    }
    return {
      ready: 'DTAM sender is ready. Use Send 3001 to push plans.',
      notReady: 'DTAM sender is not initialised.',
      sendingTitle: '3001 send',
      sendingOk: (count) => `Pushed ${count} scheduled-flight record(s).`,
      sendingFail: 'Failed to push 3001 message(s).',
      validationFail: 'Mission ICD validation failed.',
      noMission: 'Compute a route or create a free mission first.',
      statusConnected: 'DTAM',
      statusDisconnected: 'DTAM offline',
      sendBtn: 'Send 3001',
      sendBtnBusy: 'Sending…',
      noFleet: 'No fleet configured yet.',
      fleetCount: (count) => `${count} aircraft`,
    };
  }

  async function refreshStatus(silent = true) {
    try {
      const status = await ODT.api('/api/dtam/status');
      applyStatus(status);
    } catch (error) {
      if (!silent) {
        ODT.OperatorLog?.error(
          messages().sendingTitle,
          ODT.humanizeError(error, messages().sendingFail)
        );
      }
    }
  }

  function applyStatus(status) {
    if (!status || typeof status !== 'object') return;
    state = {
      ...state,
      ...status,
      ready: !!status.ready,
    };
    // Mission 카드의 DTAM target 입력 기본값을 채워 둔다 (사용자가 수정 중이면 덮어쓰지 않음)
    const ipInput = document.getElementById('mission-sim-dtam-target-ip');
    const wsInput = document.getElementById('mission-sim-dtam-ws-port');
    if (ipInput && !ipInput.dataset.userEdited) ipInput.value = status.target_ip || '';
    if (wsInput && !wsInput.dataset.userEdited) wsInput.value = status.ws_port || '';
    render();
  }

  async function applyTargetConfig(partial) {
    try {
      const status = await ODT.postJSON('/api/dtam/config', partial || {});
      applyStatus(status);
      return status;
    } catch (error) {
      ODT.OperatorLog?.error(
        messages().sendingTitle,
        ODT.humanizeError(error, messages().sendingFail)
      );
      throw error;
    }
  }

  // --------------------------------------------------------
  // mission.js 가 호출하는 기존 인터페이스 호환 구현부
  // --------------------------------------------------------
  async function startMission(missionPayload /*, options*/) {
    const text = messages();
    if (!missionPayload) {
      ODT.OperatorLog?.warn(text.sendingTitle, text.noMission);
      return;
    }
    const fleetError = ODT.Mission?.validateSimulationFleet?.();
    if (fleetError) {
      ODT.OperatorLog?.warn(text.sendingTitle, fleetError);
      return;
    }

    state.sending = true;
    render();

    try {
      const result = await ODT.postJSON('/api/dtam/send', missionPayload);
      state.last_result = result;
      if (!result?.ok) {
        const detail = result?.validation?.errors?.join('\n')
          || result?.results?.map((item) => (item.errors || []).join('; ')).filter(Boolean).join('\n')
          || result?.error
          || text.sendingFail;
        ODT.OperatorLog?.error(text.sendingTitle, detail);
        return result;
      }
      ODT.OperatorLog?.success(text.sendingTitle, text.sendingOk(result.count));
      return result;
    } catch (error) {
      const message = ODT.humanizeError(error, text.sendingFail);
      ODT.OperatorLog?.error(text.sendingTitle, message);
      state.last_error = message;
      throw error;
    } finally {
      state.sending = false;
      render();
      refreshStatus(true).catch(() => {});
    }
  }

  async function stopSimulation() {
    // 3001 송신은 stateless — 별도의 "중지" 개념이 없다.
    ODT.OperatorLog?.info(messages().sendingTitle, 'DTAM send is one-shot (nothing to stop).');
  }

  async function toggleConnection() {
    // "연결" 이란 개념이 없으므로 상태 새로고침으로 매핑
    await refreshStatus(false);
  }

  function getPlaybackSpeed() {
    return 1;
  }
  function cyclePlaybackSpeed() {
    return 1;
  }
  function refreshMissionState() {
    render();
  }

  // --------------------------------------------------------
  // 렌더링
  // --------------------------------------------------------
  function render() {
    const text = messages();
    const cfg = ODT.Mission?.getSimulationFleet?.() || [];

    setText(
      'mission-sim-airsim-status',
      state.ready
        ? `${text.statusConnected} ${state.target_ip || '--'}:${state.ws_port || '--'}`
        : text.statusDisconnected
    );
    setText(
      'mission-sim-replay-status',
      state.sending ? text.sendBtnBusy : (state.ready ? 'Idle' : 'Offline')
    );
    setText('mission-sim-fleet-count', text.fleetCount(cfg.length));

    const lastResult = state.last_result;
    let progress = '--';
    if (lastResult && Array.isArray(lastResult.results)) {
      const total = lastResult.results.length;
      const ok = lastResult.results.filter((item) => item.ok).length;
      progress = `${ok}/${total}`;
    }
    setText('mission-sim-progress', progress);

    const summaryLines = [];
    if (state.last_error) {
      summaryLines.push(state.last_error);
    } else if (!state.ready) {
      summaryLines.push(text.notReady);
    } else {
      summaryLines.push(text.ready);
    }
    if (lastResult && Array.isArray(lastResult.results)) {
      lastResult.results.forEach((item) => {
        const status = item.ok ? 'OK' : 'FAIL';
        const errs = (item.errors || []).slice(0, 2).join('; ');
        summaryLines.push(
          `${item.aircraftId} / FP${item.flightPlanNumber} → ${status}${errs ? ' — ' + errs : ''}`
        );
      });
    }
    setText('mission-sim-status', summaryLines.join('\n'));

    const dot = document.getElementById('connection-dot');
    const label = document.getElementById('connection-label');
    const connectBtn = document.getElementById('connect-btn');
    const playBtn = document.getElementById('play-btn');
    const stopBtn = document.getElementById('stop-btn');
    const speedBtn = document.getElementById('playback-speed-btn');

    if (dot) {
      dot.classList.toggle('connected', !!state.ready);
      dot.classList.toggle('waiting', !!state.sending);
    }
    if (label) {
      label.textContent = state.ready
        ? `${text.statusConnected} ${state.target_ip || '--'}:${state.ws_port || '--'}`
        : text.statusDisconnected;
    }
    if (connectBtn) {
      connectBtn.textContent = state.ready ? 'Target' : 'Offline';
      connectBtn.classList.toggle('connected', !!state.ready);
      connectBtn.disabled = false;
      connectBtn.title = state.target_ip
        ? (state.server_url || `ws://${state.target_ip}:${state.ws_port}/ws/dtam`)
        : 'DTAM target not configured';
    }
    if (playBtn) {
      playBtn.textContent = state.sending ? text.sendBtnBusy : text.sendBtn;
      playBtn.disabled = !!state.sending;
      playBtn.title = state.sending ? text.sendBtnBusy : text.sendBtn;
      playBtn.classList.add('dtam-send-btn');
    }
    if (stopBtn) {
      stopBtn.style.display = 'none';
    }
    if (speedBtn) {
      speedBtn.textContent = '⟳';
      speedBtn.classList.remove('active');
      speedBtn.disabled = false;
      speedBtn.title = 'Refresh DTAM status';
    }
  }

  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function teardown() {
    if (pollHandle) {
      window.clearInterval(pollHandle);
      pollHandle = 0;
    }
  }

  const api = {
    init,
    refreshStatus,
    refreshMissionState,
    applyTargetConfig,
    getPlaybackSpeed,
    cyclePlaybackSpeed,
    toggleConnection,
    startMission,
    stopSimulation,
    sendMission: startMission,   // 명시적 별칭
  };
  // 별칭 — 명시적으로 DTAM 을 부르고 싶을 때
  window.ODT.Dtam = api;
  return api;
})();
