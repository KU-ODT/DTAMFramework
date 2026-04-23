/* i18n.js - lightweight English/Korean UI translations */
window.ODT = window.ODT || {};

ODT.I18n = (function () {
  const STORAGE_KEY = 'odt.language';
  const translations = {
    en: {
      app_title: 'ODT Mission Planner',
      sidebar_logo: 'Mission Planner',
      collapse_sidebar: 'Collapse sidebar',
      open_sidebar: 'Open sidebar',
      toggle_theme: 'Toggle theme',
      reset_view: 'Reset view',
      toggle_language: 'Switch language',
      mission_planning: 'Mission Planning',
      route: 'Route',
      free_mission: 'Free Mission',
      departure: 'Departure',
      arrival: 'Arrival',
      select_vertiport: 'Select vertiport...',
      map_pick: 'Map',
      pick_departure_on_map: 'Pick departure on map',
      pick_arrival_on_map: 'Pick arrival on map',
      departure_badge: 'DEP',
      arrival_badge: 'ARR',
      selected_departure: 'Departure',
      selected_arrival: 'Arrival',
      compute_route: 'Compute Route',
      distance: 'Distance',
      waypoints: 'Waypoints',
      path: 'Path',
      altitude_profile: 'Altitude Profile',
      expand_chart: 'Expand',
      expand_altitude_profile: 'Open expanded altitude profile',
      close_altitude_profile: 'Close altitude profile',
      free_mission_hint:
        'Click on the map to place waypoints.<br><strong>Right-click</strong> a waypoint to delete it.<br>Drag waypoint altitude in the profile chart.',
      clear_all: 'Clear All',
      execute: 'Execute',
      name: 'Name',
      lat: 'LAT',
      lon: 'LON',
      alt: 'ALT',
      alt_m: 'Alt(m)',
      vertiports: 'Vertiports',
      corridors: 'Corridors',
      settings: 'Settings',
      airsim_connection: 'AirSim Connection',
      host: 'Host',
      port: 'Port',
      map: 'Map',
      theme: 'Theme',
      buildings: 'Buildings',
      mission_defaults: 'Mission Defaults',
      speed_mps: 'Speed (m/s)',
      altitude_m: 'Altitude (m)',
      save_settings: 'Save Settings',
      toggle_corridors: 'Toggle corridors',
      toggle_buildings: 'Toggle buildings',
      disconnected: 'Disconnected',
      connecting: 'Connecting...',
      connected: 'Connected',
      connect: 'Connect',
      disconnect: 'Disconnect',
      start_mission: 'Start mission',
      stop_mission: 'Stop mission',
      operations_log: 'Operations log',
      operations: 'Operations',
      operator_events: 'Operator-friendly events',
      clear: 'Clear',
      ops_log_empty: 'Connection and mission events will appear here.',
      edit_waypoint: 'Edit Waypoint',
      delete_waypoint: 'Delete Waypoint',
      log_generic_title: 'Event',
      log_no_details: 'No additional details were provided.',
      log_using_fallback_title: 'Using fallback configuration',
      log_using_fallback_message:
        'Server configuration was unavailable, so the planner started with local defaults.',
      log_ready_title: 'Mission planner ready',
      log_ready_message: 'Map layers and baseline operation data are ready.',
      log_mission_stop_requested_title: 'Mission stop requested',
      log_mission_stop_requested_message:
        'A stop command was sent to AirSim for the active mission.',
      log_mission_stop_failed_title: 'Mission stop failed',
      log_mission_stop_failed_message:
        'The mission stop request could not be completed.',
      log_settings_saved_title: 'Operation settings saved',
      log_settings_saved_message:
        'AirSim {host}:{port}, default speed {speed} m/s, default altitude {alt} m.',
      log_settings_save_failed_title: 'Settings save failed',
      log_settings_save_failed_message:
        'The settings could not be saved to the server.',
      log_settings_unavailable_title: 'Settings unavailable',
      log_settings_unavailable_message:
        'The server settings could not be loaded, so screen defaults are in use.',
      log_data_load_failed_title: 'Operation data load failed',
      log_data_load_failed_message:
        'Vertiport or corridor data could not be loaded.',
      log_route_incomplete_title: 'Route selection incomplete',
      log_route_incomplete_message:
        'Select both a departure and an arrival vertiport before computing a route.',
      log_map_pick_started_title: 'Map selection armed',
      log_map_pick_departure_message:
        'Click a vertiport on the map to set the departure.',
      log_map_pick_arrival_message:
        'Click a vertiport on the map to set the arrival.',
      log_map_pick_applied_title: 'Map selection applied',
      log_map_pick_applied_message:
        '{role} was set to {name} from the map.',
      log_route_same_title: 'Route request rejected',
      log_route_same_message:
        'Departure and arrival are the same. Select a different destination.',
      log_route_computed_title: 'Route computed',
      log_route_computed_message:
        '{start} to {end} ready. Total corridor distance: {distance}.',
      log_route_compute_failed_title: 'Route computation failed',
      log_route_compute_failed_message:
        'The selected vertiports could not be connected with a route.',
      log_mission_not_ready_title: 'Mission not ready',
      log_mission_not_ready_message:
        'No route is available yet. Compute a route or place free mission waypoints first.',
      log_mission_uploaded_title: 'Mission uploaded',
      log_mission_uploaded_message:
        '{count} waypoints were sent to AirSim as the active mission.',
      log_mission_start_failed_title: 'Mission start failed',
      log_mission_start_failed_message:
        'AirSim could not accept the mission start request.',
      log_telemetry_waiting_title: 'Telemetry still waiting',
      log_telemetry_waiting_message:
        'The channel is open, but no vehicle position has arrived yet. Check AirSim state and API control.',
      log_connect_ignored_title: 'Connect request ignored',
      log_connect_ignored_message:
        'Telemetry is already connected or a connection is still in progress.',
      log_connecting_title: 'Connecting to AirSim',
      log_connecting_message: 'Starting telemetry for {host}:{port}.',
      log_connect_failed_title: 'AirSim connection failed',
      log_connect_failed_message:
        'The telemetry start request could not be sent.',
      log_realtime_failed_title: 'Realtime channel failed',
      log_realtime_failed_message:
        'The browser could not open a realtime telemetry channel to the server.',
      log_realtime_online_title: 'Realtime channel online',
      log_realtime_online_message:
        'The telemetry channel is open and waiting for the first vehicle update.',
      log_vehicle_updates_title: 'Vehicle updates received',
      log_vehicle_updates_message: 'AirSim telemetry is streaming normally.',
      log_disconnect_complete_title: 'Disconnect complete',
      log_disconnect_complete_message: 'Telemetry was shut down cleanly.',
      log_realtime_closed_title: 'Realtime channel closed',
      log_realtime_closed_message:
        'The realtime telemetry channel has been closed.',
      log_realtime_error_title: 'Realtime channel error',
      log_realtime_error_message:
        'There was a problem with live communication between the browser and server.',
      log_telemetry_stop_unconfirmed_title: 'Telemetry stop not confirmed',
      log_telemetry_stop_unconfirmed_message:
        'The server did not confirm the telemetry stop request.',
    },
    ko: {
      app_title: 'ODT 미션 플래너',
      sidebar_logo: '미션 플래너',
      collapse_sidebar: '사이드바 접기',
      open_sidebar: '사이드바 열기',
      toggle_theme: '테마 전환',
      reset_view: '초기 시점으로 이동',
      toggle_language: '언어 전환',
      mission_planning: '미션 계획',
      route: '경로',
      free_mission: '자유 미션',
      departure: '출발지',
      arrival: '도착지',
      select_vertiport: '버티포트 선택...',
      map_pick: '지도',
      pick_departure_on_map: '지도에서 출발지 선택',
      pick_arrival_on_map: '지도에서 도착지 선택',
      departure_badge: '출발',
      arrival_badge: '도착',
      selected_departure: '출발지',
      selected_arrival: '도착지',
      compute_route: '경로 계산',
      distance: '거리',
      waypoints: '경유점',
      path: '경로',
      altitude_profile: '고도 프로파일',
      expand_chart: '확대',
      expand_altitude_profile: '고도 프로파일 팝업 열기',
      close_altitude_profile: '고도 프로파일 닫기',
      free_mission_hint:
        '지도를 클릭해 경유점을 배치합니다.<br><strong>우클릭</strong>으로 경유점을 삭제할 수 있습니다.<br>프로파일 차트에서 고도를 드래그해 조정할 수 있습니다.',
      clear_all: '전체 삭제',
      execute: '실행',
      name: '이름',
      lat: '위도',
      lon: '경도',
      alt: '고도',
      alt_m: '고도(m)',
      vertiports: '버티포트',
      corridors: '회랑',
      settings: '설정',
      airsim_connection: 'AirSim 연결',
      host: '호스트',
      port: '포트',
      map: '지도',
      theme: '테마',
      buildings: '건물',
      mission_defaults: '미션 기본값',
      speed_mps: '속도 (m/s)',
      altitude_m: '고도 (m)',
      save_settings: '설정 저장',
      toggle_corridors: '회랑 표시 전환',
      toggle_buildings: '건물 표시 전환',
      disconnected: '연결 안 됨',
      connecting: '연결 중...',
      connected: '연결됨',
      connect: '연결',
      disconnect: '해제',
      start_mission: '미션 시작',
      stop_mission: '미션 중지',
      operations_log: '운용 로그',
      operations: '운용 로그',
      operator_events: '운용자 친화 이벤트',
      clear: '지우기',
      ops_log_empty: '연결과 미션 이벤트가 여기에 표시됩니다.',
      edit_waypoint: '경유점 수정',
      delete_waypoint: '경유점 삭제',
      log_generic_title: '이벤트',
      log_no_details: '추가 상세 정보가 없습니다.',
      log_using_fallback_title: '기본 설정으로 시작',
      log_using_fallback_message:
        '서버 설정을 불러오지 못해 로컬 기본값으로 플래너를 시작했습니다.',
      log_ready_title: '미션 플래너 준비 완료',
      log_ready_message: '지도 레이어와 기본 운용 데이터가 준비되었습니다.',
      log_mission_stop_requested_title: '미션 중지 요청 전송',
      log_mission_stop_requested_message:
        '현재 활성 미션을 중지하도록 AirSim에 요청했습니다.',
      log_mission_stop_failed_title: '미션 중지 실패',
      log_mission_stop_failed_message:
        '미션 중지 요청을 완료하지 못했습니다.',
      log_settings_saved_title: '운용 설정 저장 완료',
      log_settings_saved_message:
        'AirSim {host}:{port}, 기본 속도 {speed} m/s, 기본 고도 {alt} m로 저장했습니다.',
      log_settings_save_failed_title: '설정 저장 실패',
      log_settings_save_failed_message:
        '설정을 서버에 저장하지 못했습니다.',
      log_settings_unavailable_title: '설정 불러오기 실패',
      log_settings_unavailable_message:
        '서버 설정을 불러오지 못해 화면 기본값을 사용합니다.',
      log_data_load_failed_title: '운용 데이터 로드 실패',
      log_data_load_failed_message:
        '버티포트 또는 회랑 데이터를 불러오지 못했습니다.',
      log_route_incomplete_title: '경로 선택 미완료',
      log_route_incomplete_message:
        '경로 계산 전에 출발지와 도착지 버티포트를 모두 선택해 주세요.',
      log_map_pick_started_title: '지도 선택 대기 중',
      log_map_pick_departure_message:
        '지도에서 버티포트를 클릭하면 출발지로 설정합니다.',
      log_map_pick_arrival_message:
        '지도에서 버티포트를 클릭하면 도착지로 설정합니다.',
      log_map_pick_applied_title: '지도 선택 적용 완료',
      log_map_pick_applied_message:
        '{role}를 지도에서 {name}(으)로 설정했습니다.',
      log_route_same_title: '경로 요청 거부',
      log_route_same_message:
        '출발지와 도착지가 같습니다. 다른 목적지를 선택해 주세요.',
      log_route_computed_title: '경로 계산 완료',
      log_route_computed_message:
        '{start}에서 {end}까지 경로를 준비했습니다. 총 회랑 거리: {distance}.',
      log_route_compute_failed_title: '경로 계산 실패',
      log_route_compute_failed_message:
        '선택한 버티포트 사이의 경로를 계산하지 못했습니다.',
      log_mission_not_ready_title: '미션 준비 안 됨',
      log_mission_not_ready_message:
        '전송할 경로가 없습니다. 먼저 경로를 계산하거나 자유 미션 경유점을 배치해 주세요.',
      log_mission_uploaded_title: '미션 전송 완료',
      log_mission_uploaded_message:
        '{count}개의 경유점을 AirSim 활성 미션으로 전송했습니다.',
      log_mission_start_failed_title: '미션 시작 실패',
      log_mission_start_failed_message:
        'AirSim이 미션 시작 요청을 수락하지 않았습니다.',
      log_telemetry_waiting_title: '텔레메트리 대기 중',
      log_telemetry_waiting_message:
        '채널은 열렸지만 아직 기체 위치 데이터가 도착하지 않았습니다. AirSim 상태와 API 제어 권한을 확인해 주세요.',
      log_connect_ignored_title: '연결 요청 무시',
      log_connect_ignored_message:
        '이미 연결되어 있거나 연결이 진행 중입니다.',
      log_connecting_title: 'AirSim 연결 시도',
      log_connecting_message: '{host}:{port} 텔레메트리 스트림을 시작합니다.',
      log_connect_failed_title: 'AirSim 연결 실패',
      log_connect_failed_message:
        '텔레메트리 시작 요청을 보내지 못했습니다.',
      log_realtime_failed_title: '실시간 채널 열기 실패',
      log_realtime_failed_message:
        '브라우저가 서버와 실시간 텔레메트리 채널을 열지 못했습니다.',
      log_realtime_online_title: '실시간 채널 연결됨',
      log_realtime_online_message:
        '텔레메트리 채널이 열렸고 첫 기체 업데이트를 기다리는 중입니다.',
      log_vehicle_updates_title: '기체 업데이트 수신 시작',
      log_vehicle_updates_message:
        'AirSim 텔레메트리 스트림이 정상적으로 들어오고 있습니다.',
      log_disconnect_complete_title: '연결 해제 완료',
      log_disconnect_complete_message:
        '텔레메트리 연결을 안전하게 종료했습니다.',
      log_realtime_closed_title: '실시간 채널 종료',
      log_realtime_closed_message:
        '실시간 텔레메트리 채널이 종료되었습니다.',
      log_realtime_error_title: '실시간 채널 오류',
      log_realtime_error_message:
        '브라우저와 서버 간 실시간 통신 중 문제가 발생했습니다.',
      log_telemetry_stop_unconfirmed_title: '텔레메트리 중지 미확인',
      log_telemetry_stop_unconfirmed_message:
        '서버가 텔레메트리 중지 요청을 확인하지 못했습니다.',
    },
  };

  let currentLanguage = 'en';

  function interpolate(template, vars) {
    return String(template).replace(/\{(\w+)\}/g, (_, key) => {
      if (vars && Object.prototype.hasOwnProperty.call(vars, key)) {
        return vars[key];
      }
      return `{${key}}`;
    });
  }

  function translate(key, vars) {
    const dictionary = translations[currentLanguage] || translations.en;
    const fallback = translations.en[key];
    const template = dictionary[key] != null ? dictionary[key] : fallback != null ? fallback : key;
    return interpolate(template, vars);
  }

  function applyTranslations(root) {
    const scope = root || document;
    scope.querySelectorAll('[data-i18n]').forEach((el) => {
      el.textContent = translate(el.dataset.i18n);
    });
    scope.querySelectorAll('[data-i18n-html]').forEach((el) => {
      el.innerHTML = translate(el.dataset.i18nHtml);
    });
    scope.querySelectorAll('[data-i18n-title]').forEach((el) => {
      const value = translate(el.dataset.i18nTitle);
      el.title = value;
      el.setAttribute('aria-label', value);
    });
    scope.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
      el.setAttribute('placeholder', translate(el.dataset.i18nPlaceholder));
    });
    scope.querySelectorAll('[data-i18n-aria-label]').forEach((el) => {
      el.setAttribute('aria-label', translate(el.dataset.i18nAriaLabel));
    });
    document.title = translate('app_title');
    document.documentElement.lang = currentLanguage;
    updateLanguageButton();
  }

  function updateLanguageButton() {
    const button = document.getElementById('language-btn');
    if (!button) return;
    button.textContent = currentLanguage === 'ko' ? 'KO' : 'EN';
    const title = translate('toggle_language');
    button.title = title;
    button.setAttribute('aria-label', title);
  }

  function getStoredLanguage() {
    try {
      return window.localStorage.getItem(STORAGE_KEY);
    } catch (_) {
      return null;
    }
  }

  function storeLanguage(lang) {
    try {
      window.localStorage.setItem(STORAGE_KEY, lang);
    } catch (_) {}
  }

  function detectLanguage() {
    const stored = getStoredLanguage();
    if (stored && translations[stored]) return stored;
    const nav = (navigator.language || '').toLowerCase();
    if (nav.startsWith('ko')) return 'ko';
    return 'en';
  }

  function setLanguage(lang) {
    if (!translations[lang]) return;
    currentLanguage = lang;
    storeLanguage(lang);
    applyTranslations(document);
    document.dispatchEvent(
      new CustomEvent('odt:languagechange', {
        detail: { language: currentLanguage },
      })
    );
  }

  function toggleLanguage() {
    setLanguage(currentLanguage === 'ko' ? 'en' : 'ko');
  }

  function init() {
    const button = document.getElementById('language-btn');
    if (button && !button.dataset.boundLanguageToggle) {
      button.dataset.boundLanguageToggle = 'true';
      button.addEventListener('click', toggleLanguage);
    }
    currentLanguage = detectLanguage();
    applyTranslations(document);
  }

  function getLanguage() {
    return currentLanguage;
  }

  return {
    init,
    t: translate,
    setLanguage,
    toggleLanguage,
    applyTranslations,
    getLanguage,
  };
})();

ODT.t = function (key, vars) {
  return ODT.I18n ? ODT.I18n.t(key, vars) : key;
};
