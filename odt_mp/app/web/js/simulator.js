window.ODT = window.ODT || {};

ODT.Simulator = (function () {
  const PLAYBACK_SPEED_SEQUENCE = [1, 2, 4, 8];
  let state = {
    connected: false,
    running: false,
    completed: false,
    host: '127.0.0.1',
    port: 41451,
    playback_speed_x: 1,
    connected_vehicles: [],
    mission_count: 0,
    fleet: [],
    last_error: '',
  };
  let pollHandle = 0;
  let selectedPlaybackSpeed = 1;

  function init() {
    document.addEventListener('odt:languagechange', render);
    window.addEventListener('beforeunload', teardown);
    const speedBtn = document.getElementById('playback-speed-btn');
    if (speedBtn) {
      speedBtn.addEventListener('click', () => {
        cyclePlaybackSpeed();
      });
    }
    refreshStatus(true);
    pollHandle = window.setInterval(() => refreshStatus(true), 1200);
    render();
  }

  function messages() {
    if (ODT.I18n?.getLanguage?.() === 'ko') {
      return {
        connect: '연결',
        disconnect: '해제',
        disconnected: '미연결',
        connected: '연결됨',
        idle: '대기',
        running: '재생 중',
        completed: '완료',
        startTitle: '시뮬레이션 시작',
        startMapOnly: 'simpleDynamics 재생을 시작했습니다.',
        startWithSync: 'simpleDynamics 재생과 AirSim 동기화를 시작했습니다.',
        stopTitle: '시뮬레이션 중지',
        stopMessage: '시뮬레이션 재생을 중지했습니다.',
        failedTitle: '시뮬레이션 실패',
        noMission: '먼저 route를 계산하거나 free mission waypoint를 구성하세요.',
        ready: '편대를 설정하고 하단 연결/재생 버튼으로 실행하세요.',
        noFleet: '편대를 아직 구성하지 않았습니다.',
        fleetCount: (count) => `기체 ${count}대`,
        progress: (current, total) => `${current}/${total}`,
      };
    }
    return {
      connect: 'Connect',
      disconnect: 'Disconnect',
      disconnected: 'Disconnected',
      connected: 'Connected',
      idle: 'Idle',
      running: 'Running',
      completed: 'Completed',
      startTitle: 'Simulation started',
      startMapOnly: 'simpleDynamics replay started.',
      startWithSync: 'simpleDynamics replay with AirSim sync started.',
      stopTitle: 'Simulation stopped',
      stopMessage: 'Simulation replay stopped.',
      failedTitle: 'Simulation failed',
      noMission: 'Compute a route or create a free mission before replay.',
      ready: 'Configure the fleet, then use the bottom controls to connect and replay.',
      noFleet: 'No fleet is configured yet.',
      fleetCount: (count) => `${count} aircraft`,
      progress: (current, total) => `${current}/${total}`,
    };
  }

  function getConfig(replayStepOverride, playbackSpeedOverride) {
    const fleet = ODT.Mission?.getSimulationFleet?.() || [];
    return {
      host: document.getElementById('settings-host')?.value?.trim() || '127.0.0.1',
      port: Number(document.getElementById('settings-port')?.value) || 41451,
      vehicle_names: fleet.map((item) => item.vehicleName),
      replay_step_s:
        replayStepOverride ||
        ODT.Mission?.getSimulationReplayStep?.() ||
        0.1,
      playback_speed_x:
        playbackSpeedOverride ||
        selectedPlaybackSpeed,
      fleet,
    };
  }

  function normalizePlaybackSpeed(speed) {
    const numeric = Number(speed);
    if (!Number.isFinite(numeric) || numeric <= 0) {
      return 1;
    }
    return PLAYBACK_SPEED_SEQUENCE.reduce((closest, candidate) => (
      Math.abs(candidate - numeric) < Math.abs(closest - numeric) ? candidate : closest
    ), PLAYBACK_SPEED_SEQUENCE[0]);
  }

  function formatPlaybackSpeed(speed) {
    return String(normalizePlaybackSpeed(speed));
  }

  function getPlaybackSpeed() {
    return selectedPlaybackSpeed;
  }

  function getNextPlaybackSpeed(speed) {
    const current = normalizePlaybackSpeed(speed);
    const index = PLAYBACK_SPEED_SEQUENCE.indexOf(current);
    return PLAYBACK_SPEED_SEQUENCE[(index + 1) % PLAYBACK_SPEED_SEQUENCE.length];
  }

  async function setPlaybackSpeed(nextSpeed, syncRunning = true) {
    selectedPlaybackSpeed = normalizePlaybackSpeed(nextSpeed);
    render();
    if (!syncRunning || !state.running) {
      return selectedPlaybackSpeed;
    }

    const text = messages();
    try {
      const status = await ODT.postJSON('/api/simulator/speed', {
        playback_speed_x: selectedPlaybackSpeed,
      });
      applyStatus(status);
      return selectedPlaybackSpeed;
    } catch (error) {
      selectedPlaybackSpeed = normalizePlaybackSpeed(state.playback_speed_x || 1);
      render();
      ODT.OperatorLog?.error(text.failedTitle, ODT.humanizeError(error, text.failedTitle));
      throw error;
    }
  }

  function cyclePlaybackSpeed() {
    const current = state.running
      ? normalizePlaybackSpeed(state.playback_speed_x || selectedPlaybackSpeed)
      : selectedPlaybackSpeed;
    const next = getNextPlaybackSpeed(current);
    return setPlaybackSpeed(next, true);
  }

  function sameVehicleSet(left, right) {
    const a = Array.isArray(left) ? left.map((item) => String(item || '').trim()).filter(Boolean).sort() : [];
    const b = Array.isArray(right) ? right.map((item) => String(item || '').trim()).filter(Boolean).sort() : [];
    if (a.length !== b.length) return false;
    return a.every((item, index) => item === b[index]);
  }

  function applyStatus(nextState) {
    if (!nextState || typeof nextState !== 'object') return;
    if (
      Number.isFinite(Number(nextState.playback_speed_x))
      && (nextState.running || nextState.completed)
    ) {
      selectedPlaybackSpeed = normalizePlaybackSpeed(nextState.playback_speed_x);
    }
    state = {
      ...state,
      ...nextState,
      connected_vehicles: Array.isArray(nextState.connected_vehicles)
        ? nextState.connected_vehicles
        : state.connected_vehicles,
      fleet: Array.isArray(nextState.fleet) ? nextState.fleet : state.fleet,
    };
    render();
  }

  async function refreshStatus(silent = false) {
    try {
      const status = await ODT.api('/api/simulator/status');
      applyStatus(status);
    } catch (error) {
      if (!silent) {
        ODT.OperatorLog?.error(messages().failedTitle, ODT.humanizeError(error, messages().failedTitle));
      }
    }
  }

  async function toggleConnection() {
    const cfg = getConfig();
    const text = messages();
    const fleetError = ODT.Mission?.validateSimulationFleet?.();
    if (fleetError) {
      ODT.OperatorLog?.warn(text.failedTitle, fleetError);
      return;
    }

    try {
      if (state.connected) {
        const status = await ODT.postJSON('/api/simulator/disconnect', {});
        applyStatus(status);
        return;
      }

      await ODT.Telemetry?.openRealtimeChannel?.();
      const status = await ODT.postJSON('/api/simulator/connect', {
        host: cfg.host,
        port: cfg.port,
        vehicle_names: cfg.vehicle_names,
      });
      applyStatus(status);
    } catch (error) {
      ODT.OperatorLog?.error(text.failedTitle, ODT.humanizeError(error, text.failedTitle));
    }
  }

  async function startMission(mission, options = {}) {
    const text = messages();
    if (!mission) {
      ODT.OperatorLog?.warn(text.failedTitle, text.noMission);
      return;
    }
    const fleetError = ODT.Mission?.validateSimulationFleet?.();
    if (fleetError) {
      ODT.OperatorLog?.warn(text.failedTitle, fleetError);
      return;
    }

    const cfg = getConfig(options.replayStepS, options.playbackSpeedX);
    try {
      if (state.connected && !sameVehicleSet(state.connected_vehicles, cfg.vehicle_names)) {
        const status = await ODT.postJSON('/api/simulator/connect', {
          host: cfg.host,
          port: cfg.port,
          vehicle_names: cfg.vehicle_names,
        });
        applyStatus(status);
      }

      ODT.Telemetry?.resetSimulationView?.();
      await ODT.Telemetry?.openRealtimeChannel?.();
      const result = await ODT.postJSON('/api/simulator/start', {
        mission,
        host: cfg.host,
        port: cfg.port,
        vehicle_names: cfg.vehicle_names,
        replay_step_s: cfg.replay_step_s,
        playback_speed_x: cfg.playback_speed_x,
        sync_to_airsim: !!state.connected,
      });
      applyStatus(result.simulator || {});
      ODT.OperatorLog?.success(
        text.startTitle,
        state.connected ? text.startWithSync : text.startMapOnly
      );
    } catch (error) {
      ODT.OperatorLog?.error(text.failedTitle, ODT.humanizeError(error, text.failedTitle));
      throw error;
    }
  }

  async function stopSimulation() {
    const text = messages();
    try {
      const status = await ODT.postJSON('/api/simulator/stop', {});
      applyStatus(status);
      ODT.OperatorLog?.info(text.stopTitle, text.stopMessage);
    } catch (error) {
      ODT.OperatorLog?.error(text.failedTitle, ODT.humanizeError(error, text.failedTitle));
    }
  }

  function buildFleetProgress() {
    if (!Array.isArray(state.fleet) || !state.fleet.length) {
      return { current: 0, total: 0 };
    }
    return state.fleet.reduce(
      (acc, item) => {
        acc.current += Math.max(Number(item.current_index || -1) + 1, 0);
        acc.total += Number(item.sample_count || 0);
        return acc;
      },
      { current: 0, total: 0 }
    );
  }

  function render() {
    const text = messages();
    const cfg = getConfig();
    const replayState = state.running ? text.running : state.completed ? text.completed : text.idle;
    const activePlaybackSpeed = selectedPlaybackSpeed;
    const playbackSpeedText = formatPlaybackSpeed(activePlaybackSpeed);
    const fleetCount = Math.max(cfg.fleet.length, Number(state.mission_count || 0));
    const progress = buildFleetProgress();

    setText(
      'mission-sim-airsim-status',
      state.connected ? `${text.connected} ${state.host}:${state.port}` : text.disconnected
    );
    setText(
      'mission-sim-replay-status',
      state.running || state.completed ? `${replayState} x${playbackSpeedText}` : replayState
    );
    setText('mission-sim-fleet-count', text.fleetCount(fleetCount));
    setText(
      'mission-sim-progress',
      progress.total > 0 ? text.progress(progress.current, progress.total) : '--'
    );

    const summaryLines = [];
    if (state.last_error) {
      summaryLines.push(state.last_error);
    } else if (fleetCount) {
      summaryLines.push(text.ready);
    } else {
      summaryLines.push(text.noFleet);
    }
    if (Array.isArray(state.fleet) && state.fleet.length) {
      state.fleet.slice(0, 4).forEach((item) => {
        summaryLines.push(
          `${item.vehicle_name} / ${item.aircraft_id} ${Math.max(
            Number(item.current_index || -1) + 1,
            0
          )}/${Number(item.sample_count || 0)}`
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
      dot.classList.toggle('connected', !!state.connected);
      dot.classList.toggle('waiting', false);
    }
    if (label) {
      label.textContent = state.connected ? text.connected : text.disconnected;
    }
    if (connectBtn) {
      connectBtn.textContent = state.connected ? text.disconnect : text.connect;
      connectBtn.classList.toggle('connected', !!state.connected);
      connectBtn.disabled = false;
    }
    if (playBtn) {
      playBtn.disabled = !!state.running;
    }
    if (stopBtn) {
      stopBtn.disabled = !state.running;
    }
    if (speedBtn) {
      speedBtn.textContent = `${playbackSpeedText}x`;
      speedBtn.title = `Playback speed ${playbackSpeedText}x`;
      speedBtn.classList.toggle('active', activePlaybackSpeed > 1);
      speedBtn.disabled = false;
    }
  }

  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) {
      el.textContent = value;
    }
  }

  function refreshMissionState() {
    render();
  }

  function teardown() {
    if (pollHandle) {
      window.clearInterval(pollHandle);
      pollHandle = 0;
    }
    ODT.Telemetry?.closeRealtimeChannel?.();
  }

  return {
    init,
    refreshStatus,
    refreshMissionState,
    getPlaybackSpeed,
    toggleConnection,
    startMission,
    stopSimulation,
    cyclePlaybackSpeed,
  };
})();
