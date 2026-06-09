const body = document.body;
const panelParam = (() => {
  if (!body || typeof window === "undefined") {
    return "";
  }
  try {
    const params = new URLSearchParams(window.location.search);
    return String(params.get("panel") || "").toLowerCase();
  } catch (_err) {
    return "";
  }
})();
if (panelParam) {
  body.classList.add("panel-popout");
  if (panelParam === "noise") {
    body.classList.add("panel-popout-noise");
  } else if (panelParam === "transmission") {
    body.classList.add("panel-popout-transmission");
  }
}
  const I18N_TEXT = {
  en: {
    "dashboard.show_table": "Show table",
    "dashboard.hide_table": "Hide table",
    "label.speed_label": "Speed x{value}",
    "label.operation_total_time": "Total {hours}h {minutes}m",
    "label.operation_per_hour": "~{value} flights/hour",
    "label.traffic_per_hour": "Takeoffs/hour {value}",
    "label.human_workload_note":
      "Workload = weighted interventions in the last {window} (Speed=1, Airspace=2, Emergency=3).",
    "label.no_activity": "No activity yet.",
    "label.no_interventions": "No interventions yet",
    "label.landing_confirm": "Landing Confirm?",
    "label.target_prefix": "Target: {label}",
    "label.lat_lon": "Lat {lat} / Lon {lon}",
    "label.base_station_named": "Base Station {name}",
    "label.corridor_named": "Corridor {name}",
    "label.vertiport_named": "Vertiport {name}",
    "label.delete_corridor_named": "{name} will be removed.",
    "label.delete_corridor": "Corridor will be removed.",
    "label.delete_vertiport_named": "{name} will be removed.",
    "label.delete_vertiport": "Vertiport will be removed.",
    "label.wind_readout": "{speed} m/s, from {dir} deg",
    "status.rules_updated": "Simulation rules updated.",
    "status.autopilot_on": "Autopilot enabled.",
    "status.autopilot_off": "Autopilot disabled.",
    "status.traffic_selection": "Traffic selection: {name}",
    "status.web_mode_connected": "Web mode connected.",
    "status.no_active_datafile": "No active data file.",
    "status.failed_prepare_editable": "Failed to prepare editable file.",
    "status.control_link_not_ready": "Control link not ready yet.",
    "status.failed_send_control": "Failed to send control command.",
    "status.fast_control_web": "Fast control is available in web mode.",
    "status.speed_control_web": "Speed control is available in web mode.",
    "status.pause_control_web": "Pause is available in web mode.",
    "status.edit_disabled": "Edit mode is disabled while the simulation is running.",
    "status.layer_unavailable": "3D layer unavailable: base map source not ready.",
    "status.request_failed": "Request failed: {status}",
    "status.invalid_response": "Invalid response.",
    "status.request_failed_generic": "Request failed.",
    "status.select_valid_flight": "Select a valid flight first.",
    "status.emergency_select_target": "Emergency landing: select a vertiport or point.",
    "status.emergency_canceled": "Emergency landing canceled.",
    "status.pick_landing_point": "Pick a landing point first.",
    "status.emergency_set": "{flight} emergency landing set: {label}.",
    "status.force_move_select_wp": "Force move: select a waypoint.",
    "status.force_move_canceled": "Force move canceled.",
    "status.force_move_requested": "{flight} force move direct to {wp} requested.",
    "status.enter_valid_speed": "Enter a valid speed.",
    "status.speed_set": "{name} speed set.",
    "status.speed_reset": "{name} speed reset.",
    "status.holding_started": "{name} holding started.",
    "status.holding_exit": "{name} holding will exit after current loop.",
    "status.wind_hold_strong": "{name} route keep (Strong) applied.",
    "status.wind_hold_normal": "{name} route keep (Normal) applied.",
    "status.select_corridor_target": "Select target corridor node for {name}.",
    "status.wind_grade": "Wind grade: {grade}.",
    "status.wind_grade_set": "Wind grade set to {grade}.",
    "status.apply_mode_on": "Apply mode on: click map to place a local zone.",
    "status.apply_mode_off": "Apply mode off.",
    "status.local_wind_applied": "Local wind applied: {grade} ({radius} diameter).",
    "status.local_wind_fade": "Local wind is fading back to baseline.",
    "status.highdensity_folder_loaded": "Flight plan folder loaded: {name} ({count} files).",
    "status.highdensity_folder_reset": "Flight plan folder reset.",
    "status.highdensity_folder_invalid":
      "Folder load failed. Select a folder containing valid flight-plan CSV files.",
    "traffic.level.low": "Low",
    "traffic.level.middle": "Middle",
    "traffic.level.high": "High",
    "direction.right": "Right",
    "direction.left": "Left",
    "time.seconds": ({ count }) => `${count} second${count === 1 ? "" : "s"}`,
    "time.minutes": ({ count }) => `${count} minute${count === 1 ? "" : "s"}`,
  },
  ko: {
    "dashboard.show_table": "표 열기",
    "dashboard.hide_table": "표 닫기",
    "label.speed_label": "속도 x{value}",
    "label.operation_total_time": "총 {hours}시간 {minutes}분",
    "label.operation_per_hour": "시간당 약 {value}편",
    "label.traffic_per_hour": "\uC2DC\uAC04\uB2F9 {value}\uB300 \uC774\uB959",
    "label.human_workload_note":
      "작업부하 = 최근 {window} 동안 가중치 적용 개입(속도=1, 공역=2, 비상=3).",
    "label.no_activity": "아직 활동 없음.",
    "label.no_interventions": "아직 개입 없음.",
    "label.landing_confirm": "착륙 확인?",
    "label.target_prefix": "대상: {label}",
    "label.lat_lon": "위도 {lat} / 경도 {lon}",
    "label.base_station_named": "기지국 {name}",
    "label.corridor_named": "회랑 {name}",
    "label.vertiport_named": "버티포트 {name}",
    "label.delete_corridor_named": "{name}이(가) 삭제됩니다.",
    "label.delete_corridor": "회랑이 삭제됩니다.",
    "label.delete_vertiport_named": "{name}이(가) 삭제됩니다.",
    "label.delete_vertiport": "버티포트가 삭제됩니다.",
    "label.wind_readout": "풍속 {speed} m/s, {dir}° 방향",
    "status.rules_updated": "시뮬레이션 규칙이 업데이트되었습니다.",
    "status.autopilot_on": "오토파일럿 활성화.",
    "status.autopilot_off": "오토파일럿 비활성화.",
    "status.traffic_selection": "트래픽 선택: {name}",
    "status.web_mode_connected": "웹 모드가 연결되었습니다.",
    "status.no_active_datafile": "활성 데이터 파일이 없습니다.",
    "status.failed_prepare_editable": "편집 파일 준비에 실패했습니다.",
    "status.control_link_not_ready": "제어 링크가 아직 준비되지 않았습니다.",
    "status.failed_send_control": "제어 명령 전송에 실패했습니다.",
    "status.fast_control_web": "웹 모드에서만 고속 제어가 가능합니다.",
    "status.speed_control_web": "웹 모드에서만 속도 제어가 가능합니다.",
    "status.pause_control_web": "웹 모드에서만 일시정지가 가능합니다.",
    "status.edit_disabled": "시뮬레이션 실행 중에는 편집할 수 없습니다.",
    "status.layer_unavailable": "3D 레이어를 사용할 수 없습니다: 베이스 지도 소스가 준비되지 않았습니다.",
    "status.request_failed": "요청 실패: {status}",
    "status.invalid_response": "유효하지 않은 응답입니다.",
    "status.request_failed_generic": "요청에 실패했습니다.",
    "status.select_valid_flight": "유효한 항공기를 먼저 선택하세요.",
    "status.emergency_select_target": "비상 착륙: 버티포트 또는 지점을 선택하세요.",
    "status.emergency_canceled": "비상 착륙이 취소되었습니다.",
    "status.pick_landing_point": "착륙 지점을 먼저 선택하세요.",
    "status.emergency_set": "{flight} 비상 착륙 설정: {label}.",
    "status.force_move_select_wp": "강제 이동: WP를 선택하세요.",
    "status.force_move_canceled": "강제 이동이 취소되었습니다.",
    "status.force_move_requested": "{flight} 강제 이동 요청: {wp} 직행.",
    "status.enter_valid_speed": "유효한 속도를 입력하세요.",
    "status.speed_set": "{name} 속도를 설정했습니다.",
    "status.speed_reset": "{name} 속도를 초기화했습니다.",
    "status.holding_started": "{name} 홀딩 시작.",
    "status.holding_exit": "{name} 홀딩이 현재 회전 후 종료됩니다.",
    "status.wind_hold_strong": "{name} 경로 유지(강함) 적용.",
    "status.wind_hold_normal": "{name} 경로 유지(보통) 적용.",
    "status.select_corridor_target": "{name}의 대상 회랑 노드를 선택하세요.",
    "status.wind_grade": "풍속 등급: {grade}.",
    "status.wind_grade_set": "풍속 등급을 {grade}로 설정했습니다.",
    "status.apply_mode_on": "적용 모드 켜짐: 지도를 클릭해 로컬 구역을 지정하세요.",
    "status.apply_mode_off": "적용 모드 꺼짐.",
    "status.local_wind_applied": "로컬 바람 적용: {grade} ({radius} 직경).",
    "status.local_wind_fade": "로컬 바람이 기본값으로 서서히 복귀합니다.",
    "status.highdensity_folder_loaded": "비행계획 폴더 로드 완료: {name} ({count}개 파일).",
    "status.highdensity_folder_reset": "비행계획 폴더를 초기화했습니다.",
    "status.highdensity_folder_invalid":
      "폴더 로드에 실패했습니다. 유효한 비행계획 CSV 파일이 있는 폴더를 선택하세요.",
    "traffic.level.low": "저밀도",
    "traffic.level.middle": "중밀도",
    "traffic.level.high": "고밀도",
    "direction.right": "우측",
    "direction.left": "좌측",
    "time.seconds": ({ count }) => `${count}초`,
    "time.minutes": ({ count }) => `${count}분`,
  },
};

  const I18N_LITERAL_PAIRS = [
  ["KADA AAM Traffic Sim", "KADA AAM 교통 시뮬레이션"],
  ["KADA 2025. All rights reserved.", "KADA 2025. All rights reserved."],
  ["Eng", "영어"],
  ["Kor", "한국어"],
  ["Click to start", "클릭하여 시작"],
  ["Release Notes", "업데이트 내용"],
  ["Loading release notes...", "업데이트 내용을 불러오는 중..."],
  ["Release notes unavailable.", "업데이트 내용을 불러오지 못했습니다."],
  ["Map is loading", "지도 로딩 중"],
  ["Preparing tiles and routes...", "타일과 경로를 준비하는 중..."],
  ["Wind (m/s)", "바람 (m/s)"],
  ["Traffic Status", "운항 현황"],
  ["Traffic Management", "운항 관리"],
  ["Human Intervention", "인간 개입"],
  ["Operation History", "운영 기록"],
  ["Operation Failures", "운항 실패"],
  ["In flight", "비행 중"],
  ["Takeoff / Landing", "이착륙 중"],
  ["Num", "번호"],
  ["Name", "이름"],
  ["Risk", "위험"],
  ["Reason", "사유"],
  ["Speed", "속도"],
  ["Battery", "배터리"],
  ["HDG", "방위"],
  ["Position", "위치"],
  ["Mode", "모드"],
  ["Altitude", "고도"],
  ["From", "출발"],
  ["Destination", "도착"],
  ["Route", "경로"],
  ["Risk Trend", "위험 추이"],
  ["Save PNG", "PNG 저장"],
  ["Save CSV", "CSV 저장"],
  ["Density", "밀도"],
  ["Congestion", "혼잡"],
  ["Work Load", "작업 부하"],
  [
    "Workload = weighted interventions (Speed=1, Airspace=2, Emergency=3).",
    "작업부하 = 가중치 적용 개입(속도=1, 공역=2, 비상=3).",
  ],
  ["Speed / Hold Intervention", "속도/홀딩 개입"],
  ["Sim (s)", "시뮬 (s)"],
  ["Time", "시간"],
  ["Flight", "항공기"],
  ["Flight ID", "항공기 ID"],
  ["Action", "조치"],
  ["Speed (m/s)", "속도 (m/s)"],
  ["Airspace Intervention", "공역 개입"],
  ["To", "도착"],
  ["Type", "종류"],
  ["Emergency Intervention", "비상 개입"],
  ["Target", "대상"],
  ["Lon", "경도"],
  ["Lat", "위도"],
  ["Alt (m)", "고도 (m)"],
  ["failed", "실패"],
  ["Battery 0", "배터리 0"],
  ["Simulation Time", "시뮬레이션 시간"],
  ["Simulation Rule", "시뮬레이션 규칙"],
  ["Daily Traffic", "일일 운항량"],
  ["Low", "저밀도"],
  ["Middle", "중밀도"],
  ["High", "고밀도"],
  ["Flight Plan Folder", "비행계획 폴더"],
  ["No folder selected", "폴더 미선택"],
  ["Folder load status", "폴더 로드 상태"],
  ["Load", "불러오기"],
  ["Scheduled for future update", "추후 업데이트 예정"],
  ["Operation Time", "운항 시간"],
  ["Operation Goal", "운항 목표"],
  ["Flight profile", "비행 프로필"],
  ["Flight speed", "비행 속도"],
  ["Acceleration", "가속도"],
  ["Climb rate", "상승률"],
  ["Transition alt", "전환 고도"],
  ["Transition speed", "전환 속도"],
  ["Battery endurance", "배터리 지속 시간"],
  ["Minimum safe speed", "최저 안전 속도"],
  ["Turn rate", "회전률"],
  ["Timing", "시간 설정"],
  ["Holding time", "홀딩 시간"],
  ["Takeoff time", "이륙 시간"],
  ["Landing time", "착륙 시간"],
  ["Separation", "분리 기준"],
  ["Longitudinal sep.", "종방향 분리"],
  ["Prediction horizon", "예측 시간"],
  ["Lateral threshold", "횡방향 임계값"],
  ["Direction filter", "방향 필터"],
  ["Update interval", "업데이트 간격"],
  ["Proximity levels", "근접 단계"],
  ["Battery levels", "배터리 단계"],
  ["RNP lateral limit", "RNP 횡 한계"],
  ["RNP vertical limit", "RNP 수직 한계"],
  ["RNP r(t) levels", "RNP r(t) 기준"],
  ["RNP TTV thresholds", "RNP TTV 임계값"],
  ["Wind influence", "바람 영향"],
  ["Wind enabled", "바람 적용"],
  ["Wind time scale", "바람 시간 배율"],
  ["Wind smoothing", "바람 스무딩"],
  ["Crosswind gain", "횡풍 이득"],
  ["Crosswind return", "횡풍 복귀"],
  ["Crosswind max drift", "횡풍 최대 편차"],
  ["Head/tail gain", "순풍/역풍 이득"],
  ["Head/tail max delta", "순풍/역풍 최대 변화"],
  ["Crab max", "최대 크랩"],
  ["Save", "저장"],
  ["Reset", "초기화"],
  ["Route Custom", "경로 사용자 정의"],
  ["Data Files", "데이터 파일"],
  ["Vertiport", "버티포트"],
  ["Open as", "열기"],
  ["Apply", "적용"],
  ["Corridor", "회랑"],
  ["Base station", "기지국"],
  ["Edit Modes", "편집 모드"],
  ["Airspace Edit", "공역 편집"],
  ["Vertiport Edit", "버티포트 편집"],
  ["Base Station", "기지국"],
  ["Noise", "소음"],
  ["Communication", "통신"],
  ["Average", "평균"],
  ["External tab", "외부 탭"],
  ["Radio Propagation", "전파 전파"],
  ["Section Count", "구간 비행체 수"],
  ["Impact Field", "영향장"],
  ["Density Field", "밀도장"],
  ["DEM: OFF", "DEM: 꺼짐"],
  ["DEM: ON", "DEM: 켜짐"],
  ["DEM: MISSING", "DEM: 없음"],
  ["DEM: LOADING", "DEM: 로딩"],
  ["Height", "높이"],
  ["Scenario", "시나리오"],
  ["Wind grade", "풍속 등급"],
  ["Good", "좋음"],
  ["Fair", "보통"],
  ["Bad", "나쁨"],
  ["Serious", "심각"],
  ["Grade changes blend in smoothly.", "등급 변화가 부드럽게 전환됩니다."],
  ["Local wind", "로컬 바람"],
  ["Apply mode: OFF", "적용 모드: OFF"],
  ["Apply mode: ON", "적용 모드: ON"],
  ["Reset local", "로컬 초기화"],
  ["Radius", "반경"],
  [
    "Enable Apply mode, click the map, then pick Good/Fair/Bad/Serious.",
    "적용 모드를 켠 뒤 지도를 클릭하고 좋음/보통/나쁨/심각 중 선택하세요.",
  ],
  ["Local zones fade out after reset.", "리셋 후 로컬 구역이 서서히 사라집니다."],
  ["White", "화이트"],
  ["Dark", "다크"],
  ["Real", "실사"],
  ["Layer", "레이어"],
  ["Weather", "기상"],
  ["Show table", "표 열기"],
  ["Hide table", "표 닫기"],
  ["Reset view", "뷰 초기화"],
  ["No activity yet.", "아직 활동 없음."],
  ["No interventions yet", "아직 개입 없음."],
  ["Landing Confirm?", "착륙 확인?"],
  ["Confirm", "확인"],
  ["Deny", "거절"],
  ["Cancel", "취소"],
  ["Delete", "삭제"],
  ["Enter name", "이름 입력"],
  ["Select class", "분류 선택"],
  ["Next", "다음"],
  ["Back", "뒤로"],
  ["port", "포트"],
  ["hub", "허브"],
  ["Control", "제어"],
  ["Target Speed", "목표 속도"],
  ["Holding", "홀딩"],
  ["loops", "회"],
  ["Hold", "홀드"],
  ["Resume", "재개"],
  [
    "Right-turn holding circle (radius from turn-rate rule).",
    "우회전 홀딩 원 (회전률 규칙 기준 반경).",
  ],
  ["Emergency Landing", "비상 착륙"],
  ["Force Move (WP)", "강제 이동 (WP)"],
  ["Open noise in external tab", "외부 탭에서 소음 열기"],
  ["Open radio propagation in external tab", "외부 탭에서 전파 전파 열기"],
  ["Close noise", "소음 닫기"],
  ["Close transmission", "전파 닫기"],
  ["Noise view controls", "소음 보기 컨트롤"],
  ["Radio propagation view controls", "전파 전파 보기 컨트롤"],
  ["Theme", "테마"],
  ["Map theme", "지도 테마"],
  ["Simulation rules", "시뮬레이션 규칙"],
  ["Playback", "재생"],
  ["Play", "재생"],
  ["Pause", "일시정지"],
  ["Stop", "정지"],
    ["Reset default files", "기본 파일 초기화"],
    ["Start", "시작"],
    ["Simulation", "시뮬레이션"],
  ["Lateral Deviation (d_lat)", "횡방향 편차 (d_lat)"],
  ["Normal", "보통"],
  ["Route keep", "경로 유지"],
  ["Apply mode on: click map to place a local zone.", "적용 모드 켜짐: 지도를 클릭해 로컬 구역을 지정하세요."],
  ["Apply mode off.", "적용 모드 꺼짐."],
  ["Local wind is fading back to baseline.", "로컬 바람이 기본값으로 서서히 복귀합니다."],
  ["DEM: OFF / hUT / BS", "DEM: 꺼짐 / hUT / BS"],
  ["Min dB", "최소 dB"],
  ["Total flights", "총 운항 수"],
  ["flights", "대"],
  ["Completed", "완료"],
  ["Language", "언어"],
  ["Point", "지점"],
  ["point", "지점"],
  ["Emergency Point", "비상 지점"],
  ["Strong", "강함"],
  ["Wind", "바람"],
  ["Create corridor link", "회랑 링크 생성"],
  ["Normal link", "일반 링크"],
  ["Spare link", "예비 링크"],
  ["Move", "이동"],
  ["Link", "링크"],
  ["Edit", "편집"],
  ["Edit corridor node", "회랑 노드 편집"],
  ["Delete corridor node", "회랑 노드 삭제"],
  ["Edit vertiport", "버티포트 편집"],
  ["Delete vertiport", "버티포트 삭제"],
  ["Enter a name first.", "먼저 이름을 입력하세요."],
  ["Click map to set new base station position.", "지도를 클릭해 새 기지국 위치를 지정하세요."],
  ["Failed to update corridor status.", "회랑 상태 업데이트에 실패했습니다."],
  ["Failed to update spare link status.", "예비 링크 상태 업데이트에 실패했습니다."],
  ["Spare link opened.", "예비 링크가 열렸습니다."],
  ["Spare link closed.", "예비 링크가 닫혔습니다."],
  ["Confirm the node before linking.", "링크 전에 노드를 먼저 확정하세요."],
  ["Click map to set new corridor position.", "지도를 클릭해 새 회랑 위치를 지정하세요."],
  ["Select a different corridor node.", "다른 회랑 노드를 선택하세요."],
  ["Corridor node not found.", "회랑 노드를 찾을 수 없습니다."],
  ["Link already exists.", "이미 링크가 있습니다."],
  ["Link already removed.", "링크가 이미 제거되었습니다."],
  ["Corridor name already exists.", "회랑 이름이 이미 존재합니다."],
  ["No active corridor file.", "활성 회랑 파일이 없습니다."],
  ["Corridor deleted.", "회랑이 삭제되었습니다."],
  ["Failed to append corridor data.", "회랑 데이터 추가에 실패했습니다."],
  ["Corridor node saved.", "회랑 노드가 저장되었습니다."],
  ["Link update in progress.", "링크 업데이트 중입니다."],
  ["Vertiport not found.", "버티포트를 찾을 수 없습니다."],
  ["Select a corridor node.", "회랑 노드를 선택하세요."],
  ["Vertiport name already exists.", "버티포트 이름이 이미 존재합니다."],
  ["No active vertiport file.", "활성 버티포트 파일이 없습니다."],
  ["Invalid vertiport class.", "유효하지 않은 버티포트 분류입니다."],
  ["Vertiport deleted.", "버티포트가 삭제되었습니다."],
  ["Failed to append vertiport data.", "버티포트 데이터 추가에 실패했습니다."],
  ["Vertiport node saved.", "버티포트 노드가 저장되었습니다."],
  ["Base station name already exists.", "기지국 이름이 이미 존재합니다."],
  ["No active base station file.", "활성 기지국 파일이 없습니다."],
  ["Failed to append base station data.", "기지국 데이터 추가에 실패했습니다."],
  ["Base station saved.", "기지국이 저장되었습니다."],
  ["Base station position updated.", "기지국 위치가 업데이트되었습니다."],
  ["Base station deleted.", "기지국이 삭제되었습니다."],
  ["Vertiport link updated.", "버티포트 링크가 업데이트되었습니다."],
  ["Vertiport link removed.", "버티포트 링크가 제거되었습니다."],
  ["Vertiport updated.", "버티포트가 업데이트되었습니다."],
  ["Vertiport position updated.", "버티포트 위치가 업데이트되었습니다."],
  ["Failed to update vertiport.", "버티포트 업데이트에 실패했습니다."],
  ["Failed to delete vertiport.", "버티포트 삭제에 실패했습니다."],
  ["Corridor updated.", "회랑이 업데이트되었습니다."],
  ["Corridor position updated.", "회랑 위치가 업데이트되었습니다."],
  ["Corridor link updated.", "회랑 링크가 업데이트되었습니다."],
  ["Corridor link removed.", "회랑 링크가 제거되었습니다."],
  ["Failed to update corridor.", "회랑 업데이트에 실패했습니다."],
  ["Failed to delete corridor.", "회랑 삭제에 실패했습니다."],
  [
    "Simulation operating time window. Total operation time is calculated from start to end.",
    "시뮬레이션 운항 시간대입니다. 시작~종료 기준으로 총 운영 시간이 계산됩니다.",
  ],
  [
    "Target number of flights. Expected flights per hour/30 minutes/10 minutes are calculated.",
    "목표 운항 대수입니다. 시간/30분/10분당 예상 운항 대수가 계산됩니다.",
  ],
  ["Default cruise speed.", "기본 순항 속도입니다."],
  ["Reference angular speed during turns.", "선회 시 각속도 기준입니다."],
  ["Holding mode duration (minutes).", "홀딩 모드 유지 시간(분)입니다."],
  ["Takeoff phase duration (minutes).", "이륙 단계 지속 시간(분)입니다."],
  ["Landing phase duration (minutes).", "착륙 단계 지속 시간(분)입니다."],
  ["Minimum longitudinal separation distance (meters).", "전후 방향 최소 분리 거리(미터)입니다."],
  [
    "Forward lookahead time for risk prediction. Example: if 20s, it checks the path 20 seconds ahead.",
    "리스크 예측을 위한 전방 탐색 시간입니다. 예: 20s이면 현재 위치에서 20초 뒤 경로까지 미리 확인합니다.",
  ],
  [
    "Lateral distance threshold for route proximity. Example: 50m means within 50m of the route is considered close.",
    "경로 근접 판정에 쓰는 횡방향 거리 기준입니다. 예: 50m이면 경로에서 50m 이내만 근접으로 봅니다.",
  ],
  [
    "Heading cosine threshold for relative direction. Example: 1.0 = same direction, 0 = perpendicular, -1.0 = opposite. Setting 0.5 counts only roughly within 60°.",
    "상대 방향 판정에 쓰는 헤딩 코사인 임계값입니다. 예: 1.0=완전 동일 방향, 0=직교, -1.0=정반대. 0.5로 두면 약 60도 이내의 비슷한 방향만 계산합니다.",
  ],
  [
    "Risk recalculation interval. Example: 1s updates the risk every second.",
    "리스크 재계산 주기입니다. 예: 1s이면 1초마다 위험도를 갱신합니다.",
  ],
  [
    "Proximity distance thresholds by risk level. Example: LV3 150m, LV2 300m, LV1 450m; closer means higher level.",
    "리스크 레벨별 근접 거리 기준입니다. 예: LV3 150m, LV2 300m, LV1 450m처럼 가까울수록 높은 레벨을 부여합니다.",
  ],
  [
    "Battery thresholds by risk level. Example: LV3 <10%, LV2 <25%, LV1 <30%.",
    "리스크 레벨별 배터리 잔량 기준입니다. 예: LV3 10%, LV2 25%, LV1 30% 미만으로 단계적으로 높아집니다.",
  ],
  ["RNP 0.03 lateral limit = 54m. Set to 0 to disable.", "RNP 0.03 횡방향 한계 = 54m. 0으로 설정하면 비활성화됩니다."],
  [
    "Vertical deviation limit. Set to 0 to ignore vertical deviation.",
    "수직 편차 한계입니다. 0으로 설정하면 수직 편차를 무시합니다.",
  ],
  ["Normalized deviation thresholds r(t).", "정규화 편차 임계값 r(t)입니다."],
  ["Time-to-violation thresholds. LV3 is below LV2.", "위반까지 남은 시간 임계값입니다. LV3가 LV2보다 낮습니다."],
  ["Whether to apply wind influence. 1=enabled, 0=disabled.", "바람 영향 적용 여부입니다. 1=적용, 0=미적용입니다."],
  [
    "Wind time scale. 1=real time, 2=doubled so the wind pattern changes faster.",
    "바람 시간 배속입니다. 1=실시간, 2=두 배속으로 바람 패턴이 변합니다.",
  ],
  [
    "Smoothness of wind changes (filter time). Larger values make changes smoother.",
    "바람 변화의 완만함(필터 시간)입니다. 값이 클수록 더 부드럽게 변화합니다.",
  ],
  ["Ratio of crosswind applied to lateral drift.", "횡풍이 횡방향 드리프트로 반영되는 비율입니다."],
  ["Time constant for lateral drift returning to the original path.", "횡방향 드리프트가 원래 경로로 돌아오는 시간 상수입니다."],
  ["Maximum allowed lateral drift distance.", "횡방향 드리프트의 최대 허용 거리입니다."],
  ["Ratio of head/tailwind applied to speed.", "정풍/역풍이 속도에 반영되는 비율입니다."],
  ["Maximum speed delta added by head/tailwind.", "정풍/역풍이 속도에 더해지는 최대 변화량입니다."],
  ["Maximum crab angle to correct crosswind.", "횡풍을 보정하기 위한 최대 크랩 각도입니다."],
  ["Autopilot", "오토파일럿"],
  ["Collision Avoidance", "충돌 방지"],
  ["Risk slowdown", "위험 감속"],
  ["LV1 reduction", "LV1 감속"],
  ["LV2 reduction", "LV2 감속"],
  ["LV3 reduction", "LV3 감속"],
  ["Duration", "지속 시간"],
  ["On", "켜기"],
  ["Off", "끄기"],
  ["Autopilot enabled.", "오토파일럿 활성화."],
  ["Autopilot disabled.", "오토파일럿 비활성화."],
  ["Quick Guide", "빠른 안내"],
  ["Tutorial", "튜토리얼"],
  ["Confirm", "확인"],
  ["Simulation Rules", "시뮬레이션 규칙"],
  ["Set traffic, risk, wind, and operation rules.", "트래픽, 위험, 바람, 운항 규칙을 설정합니다."],
  ["Auto collision avoidance On/Off.", "자동 충돌 회피 On/Off."],
    ["Playback Controls", "재생 제어"],
    ["Sound", "소리"],
    ["Start / Pause / Stop / Speed.", "시작 / 일시정지 / 중지 / 속도."],
    ["Traffic Status", "운항 현황"],
  ["Live aircraft status and history tabs.", "실시간 비행체 상태와 기록 탭."],
  ["Right-click Aircraft", "비행체 우클릭"],
  ["Speed, hold, emergency, force move.", "속도, 홀드, 비상, 강제 이동."],
  ["Mouse wheel", "마우스 휠"],
  ["Zoom in / out.", "확대 / 축소."],
  ["Right-click + drag", "우클릭 + 드래그"],
  ["Rotate / tilt the map (3D).", "지도 회전 / 틸트 (3D)."],
];


const normalizeLang = (value) => {
    const lang = String(value || "").toLowerCase();
    if (lang.startsWith("ko")) {
      return "ko";
    }
    if (lang.startsWith("en")) {
      return "en";
    }
    return "en";
  };

  const resolveDefaultLang = () => {
    if (typeof window === "undefined") {
      return "en";
    }
    try {
      const stored = window.localStorage.getItem("uatm.lang");
      if (stored) {
        return normalizeLang(stored);
      }
    } catch (_err) {
      // ignore storage errors
    }
    if (typeof navigator !== "undefined" && navigator.language) {
      return normalizeLang(navigator.language);
    }
    return "en";
  };

  const buildLiteralMaps = () => {
    const maps = { en: new Map(), ko: new Map() };
    I18N_LITERAL_PAIRS.forEach((pair) => {
      if (!pair || pair.length < 2) {
        return;
      }
      const [en, ko] = pair;
      if (en && ko) {
        maps.ko.set(en, ko);
        maps.en.set(ko, en);
      }
    });
    return maps;
  };

  const formatTemplate = (template, params) => {
    const text = String(template);
    if (!params) {
      return text;
    }
    return text.replace(/\{(\w+)\}/g, (match, key) =>
      Object.prototype.hasOwnProperty.call(params, key) ? String(params[key]) : match,
    );
  };

  const AppI18n = (() => {
    let currentLang = resolveDefaultLang();
    const literalMaps = buildLiteralMaps();
    let applying = false;
    let observer = null;

    const getLang = () => currentLang;

    const t = (key, params, fallback) => {
      const langTable = I18N_TEXT[currentLang] || I18N_TEXT.en;
      const fallbackTable = I18N_TEXT.en;
      let value = langTable && Object.prototype.hasOwnProperty.call(langTable, key) ? langTable[key] : null;
      if (value == null && fallbackTable && Object.prototype.hasOwnProperty.call(fallbackTable, key)) {
        value = fallbackTable[key];
      }
      if (value == null) {
        return fallback != null ? fallback : key;
      }
      if (typeof value === "function") {
        return value(params || {});
      }
      return formatTemplate(value, params);
    };

    const translateLiteral = (text) => {
      if (text == null) {
        return text;
      }
      const value = String(text);
      const trimmed = value.trim();
      if (!trimmed) {
        return value;
      }
      const map = currentLang === "ko" ? literalMaps.ko : literalMaps.en;
      if (!map.has(trimmed)) {
        return value;
      }
      const translated = map.get(trimmed);
      return value.replace(trimmed, translated);
    };

    const translateStatus = (text) => {
      if (!text) {
        return text;
      }
      const base = translateLiteral(text);
      if (currentLang !== "ko" || base !== text) {
        return base;
      }
      const patterns = [
        {
          re: /^Speed set to (\d+)x\.$/,
          to: (match) => `속도 ${match[1]}x로 설정되었습니다.`,
        },
        {
          re: /^Daily Traffic not set; defaulting to (.+)\.$/,
          to: (match) => {
            const level = match[1];
            const label = t(`traffic.level.${String(level).toLowerCase()}`, null, level);
            return `일일 운항량이 설정되지 않아 ${label}(으)로 기본 설정합니다.`;
          },
        },
        {
          re: /^Select Daily Traffic in settings to start\.$/,
          to: () => "시작하려면 설정에서 일일 운항량을 선택하세요.",
        },
        {
          re: /^Simulation started\.$/,
          to: () => "시뮬레이션이 시작되었습니다.",
        },
        {
          re: /^Simulation paused\.$/,
          to: () => "시뮬레이션이 일시정지되었습니다.",
        },
        {
          re: /^Simulation stopped\.$/,
          to: () => "시뮬레이션이 중지되었습니다.",
        },
        {
          re: /^No schedule generated\. Check Daily Traffic and data files\.$/,
          to: () => "스케줄이 생성되지 않았습니다. 일일 운항량과 데이터 파일을 확인하세요.",
        },
        {
          re: /^Airspace data updated\.$/,
          to: () => "공역 데이터가 업데이트되었습니다.",
        },
        {
          re: /^Simulation stopped to apply updated routes\.$/,
          to: () => "업데이트된 경로를 적용하기 위해 시뮬레이션이 중지되었습니다.",
        },
        {
          re: /^Holding radius ~([0-9.]+) km \(turn rate ([0-9.]+) deg\/s\)\.$/,
          to: (match) => `홀딩 반경 약 ${match[1]} km (회전률 ${match[2]}°/s).`,
        },
        {
          re: /^Emergency landing set: (.+)\.$/,
          to: (match) => `비상 착륙 설정: ${match[1]}.`,
        },
        {
          re: /^Force move set: (.+)\.$/,
          to: (match) => `강제 이동 설정: ${match[1]}.`,
        },
        {
          re: /^Force move failed: invalid waypoint\.$/,
          to: () => "강제 이동 실패: 잘못된 WP입니다.",
        },
        {
          re: /^Force move failed: no route from (.+)\.$/,
          to: (match) => `강제 이동 실패: ${match[1]}에서 경로 없음.`,
        },
        {
          re: /^Route keep: wind effect -> (\d+)% \((\d+)s ramp\)\.$/,
          to: (match) => `경로 유지: 바람 영향 ${match[1]}% (${match[2]}초 램프).`,
        },
        {
          re: /^Corridor (closed|reopened): (.+) - (.+)$/,
          to: (match) =>
            match[1] === "closed"
              ? `회랑 폐쇄: ${match[2]} - ${match[3]}`
              : `회랑 재개통: ${match[2]} - ${match[3]}`,
        },
        {
          re: /^Spare link (opened|closed): (.+) - (.+)$/,
          to: (match) =>
            match[1] === "opened"
              ? `예비 링크 개방: ${match[2]} - ${match[3]}`
              : `예비 링크 폐쇄: ${match[2]} - ${match[3]}`,
        },
      ];
      for (const pattern of patterns) {
        const match = base.match(pattern.re);
        if (match) {
          return pattern.to(match);
        }
      }
      return base;
    };

    const applyAttributes = (element) => {
      if (!element || typeof element.getAttribute !== "function") {
        return;
      }
      ["title", "aria-label", "placeholder", "data-tooltip", "alt"].forEach((attr) => {
        const value = element.getAttribute(attr);
        if (!value) {
          return;
        }
        const translated = translateLiteral(value);
        if (translated !== value) {
          element.setAttribute(attr, translated);
        }
      });
    };

    const apply = (root) => {
      if (!root) {
        return;
      }
      if (applying) {
        return;
      }
      applying = true;
      const elementRoot = root.nodeType === Node.ELEMENT_NODE ? root : null;
      if (elementRoot) {
        applyAttributes(elementRoot);
        const elements = elementRoot.querySelectorAll(
          "[title],[aria-label],[placeholder],[data-tooltip],[alt]",
        );
        elements.forEach((el) => applyAttributes(el));
      }
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      let node = walker.nextNode();
      while (node) {
        const nextValue = translateLiteral(node.nodeValue);
        if (nextValue !== node.nodeValue) {
          node.nodeValue = nextValue;
        }
        node = walker.nextNode();
      }
      applying = false;
    };

    const observe = () => {
      if (observer || !document.body) {
        return;
      }
      observer = new MutationObserver((mutations) => {
        if (applying) {
          return;
        }
        applying = true;
        mutations.forEach((mutation) => {
          if (mutation.type === "childList") {
            mutation.addedNodes.forEach((node) => apply(node));
          } else if (mutation.type === "characterData") {
            const node = mutation.target;
            if (node && node.nodeType === Node.TEXT_NODE) {
              const nextValue = translateLiteral(node.nodeValue);
              if (nextValue !== node.nodeValue) {
                node.nodeValue = nextValue;
              }
            }
          } else if (mutation.type === "attributes") {
            applyAttributes(mutation.target);
          }
        });
        applying = false;
      });
      observer.observe(document.body, {
        childList: true,
        subtree: true,
        characterData: true,
        attributes: true,
        attributeFilter: ["title", "aria-label", "placeholder", "data-tooltip", "alt"],
      });
    };

    const setLang = (lang, options = {}) => {
      const next = normalizeLang(lang);
      currentLang = next;
      if (typeof document !== "undefined" && document.documentElement) {
        document.documentElement.lang = next;
        document.documentElement.dataset.lang = next;
      }
      if (options.persist !== false && typeof window !== "undefined") {
        try {
          window.localStorage.setItem("uatm.lang", next);
        } catch (_err) {
          // ignore storage errors
        }
      }
      if (typeof document !== "undefined") {
        apply(document.body || document.documentElement);
      }
      observe();
    };

    return {
      getLang,
      setLang,
      t,
      translateLiteral,
      translateStatus,
      apply,
      observe,
    };
  })();

  if (typeof window !== "undefined") {
    window.AppI18n = AppI18n;
  }
  const resolveBasePath = () => {
    if (typeof window === "undefined" || !window.location) {
      return "/";
    }
    const raw = window.location.pathname || "/";
    if (raw.endsWith("/")) {
      return raw;
    }
    const last = raw.split("/").pop() || "";
    if (last.includes(".")) {
      const trimmed = raw.replace(/\/[^/]*$/, "/");
      return trimmed || "/";
    }
    return `${raw}/`;
  };
  const basePath = resolveBasePath();
  const baseOrigin =
    typeof window !== "undefined" && window.location
      ? `${window.location.origin}${basePath}`
      : "";
  const absolutizeUrl = (path) => {
    if (!path) {
      return path;
    }
    if (!baseOrigin) {
      return path;
    }
    if (/^[a-z][a-z0-9+.-]*:/i.test(path)) {
      return path;
    }
    const normalized = path.startsWith("/") ? path.slice(1) : path;
    const root = baseOrigin.endsWith("/") ? baseOrigin : `${baseOrigin}/`;
    return `${root}${normalized}`;
  };
  if (typeof window !== "undefined") {
    window.AppPaths = {
      basePath,
      baseOrigin,
      resolve: absolutizeUrl,
    };
  }

  const demConfig = {
    tileUrl: absolutizeUrl("dem/{z}/{x}/{y}.png"),
    tileSize: 256,
    maxZoom: 12,
    encoding: "terrarium",
    exaggeration: 1.0,
    pitchThreshold: 6,
    pitchEnableThreshold: 8,
    pitchDisableThreshold: 5,
  };
  const viewConfig = {
    maxZoomBuffer: 6,
    maxPitch: 85,
  };
  const mapPerfConfig = {
    prewarmWorkers: true,
    prefetch: {
      enabled: true,
      delayMs: 1200,
      maxTiles: 180,
      concurrency: 4,
      centerZooms: [10, 11, 12],
      centerRadiusTiles: 1,
      vectorZooms: [9, 10, 11, 12],
      demZooms: [8, 9, 10],
      seoulBounds: [126.734, 37.413, 127.269, 37.715],
    },
  };
  const TILE_METADATA_URL = absolutizeUrl("tiles/metadata");
  const DEFAULT_TILE_FORMAT = "pbf";
  const DEFAULT_MIN_ZOOM = 0;
  const DEFAULT_MAX_ZOOM = 14;
  const DEFAULT_CENTER = [126.978, 37.5665];
  const DEFAULT_START_ZOOM = 11.5;
  const APPLY_METADATA_VIEW = false;
  const START_NOTES_BASE = absolutizeUrl("resources/patch_notes_0.9.5");
  const dataConfig = {
    vertiportCsv: "api/data/default/vertiport_default.csv",
    waypointCsv: "api/data/default/corridor_default.csv",
    // JY - Base station default spawn: fallback to the default CSV when no custom file is set.
    basestationCsv: "api/data/default/basestation_default.csv",
  };
  const airsimConfig = {
    host: "",
    port: "",
  };
  const realTileUrl = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  const config = {
    tileUrl: absolutizeUrl(`tiles/{z}/{x}/{y}.${DEFAULT_TILE_FORMAT}`),
    minZoom: DEFAULT_MIN_ZOOM,
    maxZoom: DEFAULT_MAX_ZOOM,
    center: DEFAULT_CENTER.slice(),
    startZoom: DEFAULT_START_ZOOM,
    bounds: null,
    dem: demConfig,
    view: viewConfig,
    perf: mapPerfConfig,
    data: dataConfig,
    airsim: airsimConfig,
    realTileUrl,
    notesBase: START_NOTES_BASE,
  };

  const loadTileMetadata = async () => {
    try {
      const response = await fetch(TILE_METADATA_URL, { cache: "no-store" });
      if (!response.ok) {
        return null;
      }
      const payload = await response.json();
      return payload && typeof payload === "object" ? payload : null;
    } catch (err) {
      return null;
    }
  };

  const configReady = (async () => {
    const metadata = await loadTileMetadata();
    let centerSet = false;
    if (metadata && typeof metadata.tile_format === "string") {
      config.tileUrl = absolutizeUrl(`tiles/{z}/{x}/{y}.${metadata.tile_format}`);
    }
    if (Number.isFinite(metadata && metadata.min_zoom)) {
      config.minZoom = Number(metadata.min_zoom);
    }
    if (Number.isFinite(metadata && metadata.max_zoom)) {
      config.maxZoom = Number(metadata.max_zoom);
    }
    if (APPLY_METADATA_VIEW) {
      if (Array.isArray(metadata && metadata.center) && metadata.center.length >= 3) {
        const lon = Number(metadata.center[0]);
        const lat = Number(metadata.center[1]);
        const zoom = Number(metadata.center[2]);
        if (Number.isFinite(lon) && Number.isFinite(lat)) {
          config.center = [lon, lat];
          centerSet = true;
        }
        if (Number.isFinite(zoom)) {
          config.startZoom = zoom;
        }
      }
      if (!centerSet && metadata && metadata.start_view) {
        const lon = Number(metadata.start_view.lon);
        const lat = Number(metadata.start_view.lat);
        const zoom = Number(metadata.start_view.zoom);
        if (Number.isFinite(lon) && Number.isFinite(lat)) {
          config.center = [lon, lat];
        }
        if (Number.isFinite(zoom)) {
          config.startZoom = zoom;
        }
      }
      if (Array.isArray(metadata && metadata.bounds)) {
        config.bounds = metadata.bounds;
      }
    }
    return config;
  })();

  if (typeof window !== "undefined") {
    window.AppConfigReady = configReady;
  }

  const parseCsvRows = (text) => {
    const rows = [];
    let row = [];
    let field = "";
    let inQuotes = false;

    for (let i = 0; i < text.length; i += 1) {
      const char = text[i];
      if (inQuotes) {
        if (char === "\"") {
          if (text[i + 1] === "\"") {
            field += "\"";
            i += 1;
          } else {
            inQuotes = false;
          }
        } else {
          field += char;
        }
        continue;
      }

      if (char === "\"") {
        inQuotes = true;
      } else if (char === ",") {
        row.push(field);
        field = "";
      } else if (char === "\n") {
        row.push(field);
        rows.push(row);
        row = [];
        field = "";
      } else if (char !== "\r") {
        field += char;
      }
    }

    if (field.length > 0 || row.length > 0) {
      row.push(field);
      rows.push(row);
    }
    return rows;
  };

  const normalizeRows = (rows) =>
    rows.filter((row) => row.some((cell) => cell.trim().length > 0));
  const getDataRows = (text) => {
    const rows = normalizeRows(parseCsvRows(text));
    return rows.length > 1 ? rows.slice(1) : [];
  };
  const getFileName = (value) => {
    if (!value) {
      return "";
    }
    const parts = value.split(/[\\/]/);
    return parts[parts.length - 1];
  };

  const readCell = (row, index) => (row[index] ? row[index].trim() : "");
  const BASE_MAP_PALETTES = {
    light: {
      background: "#343f28",
      landcover: "#3d4b32",
      landuse: "#445236",
      park: "#4a5f3d",
      water: "#3565b2",
      waterway: "#4b7fc6",
      boundary: "#8d987f",
      transportation: "#9b9266",
      building: "#5a5f45",
      label: "#f1f4e8",
      labelHalo: "rgba(18, 24, 16, 0.7)",
    },
    dark: {
      background: "#0f1820",
      landcover: "#182522",
      landuse: "#1b2320",
      park: "#1d3024",
      water: "#142a3e",
      waterway: "#1f425e",
      boundary: "#5e6872",
      transportation: "#4a453a",
      building: "#2f2c2a",
    },
  };
  const FOG_THEMES = {
    light: {
      color: "#e7f1fb",
      "high-color": "#f6fbff",
      "space-color": "#d7e1ee",
      "horizon-blend": 0.18,
      range: [0.8, 6.0],
      "star-intensity": 0.0,
    },
    dark: {
      color: "#0f1820",
      "high-color": "#1c2a3a",
      "space-color": "#0b0f14",
      "horizon-blend": 0.12,
      range: [0.8, 6.0],
      "star-intensity": 0.0,
    },
  };
  const SKY_THEMES = {
    light: {
      "sky-color": "#cfe0f2",
      "horizon-color": "#e6f0fb",
      "fog-color": "#e7f1fb",
      "fog-blend": 0.2,
      "atmosphere-blend": ["interpolate", ["linear"], ["zoom"], 0, 1, 8, 0.6, 12, 0],
      "atmosphere-sun": [0, 90],
      "atmosphere-sun-intensity": 5,
    },
    dark: {
      "sky-color": "#16212c",
      "horizon-color": "#1f2f3f",
      "fog-color": "#0f1820",
      "fog-blend": 0.2,
      "atmosphere-blend": ["interpolate", ["linear"], ["zoom"], 0, 1, 8, 0.6, 12, 0],
      "atmosphere-sun": [0, 90],
      "atmosphere-sun-intensity": 2,
    },
  };
  const HILLSHADE_THEMES = {
    light: {
      "hillshade-exaggeration": ["interpolate", ["linear"], ["zoom"], 0, 0.35, 8, 0.25, 12, 0.15],
      "hillshade-shadow-color": "#cbd5e1",
      "hillshade-highlight-color": "#f5f8ff",
      "hillshade-accent-color": "#e2e9f2",
      "hillshade-illumination-direction": 315,
      "hillshade-illumination-anchor": "viewport",
    },
    dark: {
      "hillshade-exaggeration": ["interpolate", ["linear"], ["zoom"], 0, 0.25, 8, 0.18, 12, 0.12],
      "hillshade-shadow-color": "#0a121a",
      "hillshade-highlight-color": "#2b3a4a",
      "hillshade-accent-color": "#1b2733",
      "hillshade-illumination-direction": 315,
      "hillshade-illumination-anchor": "viewport",
    },
  };
  const EDIT_MAP_PALETTES = {
    light: {
      background: "#d6d9dc",
      landcover: "#cdd1d4",
      landuse: "#d4d7da",
      park: "#c9cdcf",
      water: "#c2c9d0",
      waterway: "#b8c0c8",
      boundary: "#9aa1a7",
      transportation: "#aeb4b9",
      building: "#c3c7ca",
    },
    dark: {
      background: "#43484d",
      landcover: "#3e4348",
      landuse: "#44494e",
      park: "#3d4246",
      water: "#4b5258",
      waterway: "#566068",
      boundary: "#777e85",
      transportation: "#6c737a",
      building: "#4d5257",
    },
  };
  const BASE_MAP_LAYER_IDS = [
    "background",
    "landcover",
    "landuse",
    "park",
    "water",
    "waterway",
    "boundary",
    "transportation",
    "building",
  ];
  const REAL_MAP_LAYER_ID = "real-raster";
  const BUILDING_3D_LAYER_ID = "building-3d";
  const BUILDING_2D_LAYER_ID = "building";
  const BUILDING_3D_MIN_ZOOM = 13;
  const BUILDING_3D_OPACITY = 0.35;
  const BUILDING_3D_HEIGHT_SCALE = 0.5;
  const BUILDING_3D_MAX_HEIGHT = 160;
  const BUILDING_3D_COLOR = "#9ea687";
  const FT_TO_M = 0.3048;
  const FLIGHT_ALT_FT = 1000;
  const FLIGHT_ALT_M = FLIGHT_ALT_FT * FT_TO_M;
  const VERTIPORT_ALT_M = 5;
  const CORRIDOR_ALT_M = FLIGHT_ALT_M;
  const parseAltitudeMeters = (value) => {
    const parsed = Number.parseFloat(value);
    if (!Number.isFinite(parsed)) {
      return null;
    }
    return parsed * FT_TO_M;
  };
  const formatAltitudeMeters = (value) => {
    const meters = parseAltitudeMeters(value);
    if (meters === null) {
      return "";
    }
    return meters.toFixed(1);
  };
  const toTrafficAltitude = (altitude_m) => {
    const value = Number(altitude_m);
    if (!Number.isFinite(value) || value <= 0) {
      return 0;
    }
    return value * TRAFFIC_ALTITUDE_SCALE;
  };
  const hexToRgba = (hex, alpha = 1) => {
    const cleaned = hex.replace("#", "");
    const full =
      cleaned.length === 3
        ? cleaned
            .split("")
            .map((char) => char + char)
            .join("")
        : cleaned;
    const value = Number.parseInt(full, 16);
    if (!Number.isFinite(value)) {
      return new Float32Array([1, 1, 1, alpha]);
    }
    const r = ((value >> 16) & 255) / 255;
    const g = ((value >> 8) & 255) / 255;
    const b = (value & 255) / 255;
    return new Float32Array([r, g, b, alpha]);
  };
  const HOVER_OUTLINE_COLOR = "#ffe600";
  const CORRIDOR_CLOSED_COLOR = "#ff5f5f";
  const MAP_SIZE_SCALE = 1.2;
  const SCALE_CIRCLE_SOURCE_ID = "scale-circle";
  const SCALE_CIRCLE_LINE_ID = "scale-circle-line";
  const SCALE_CIRCLE_LABEL_ID = "scale-circle-label";
  const SCALE_CIRCLE_STROKE = "#000000";
  const SCALE_CIRCLE_STROKE_WIDTH = 2.2 * MAP_SIZE_SCALE;
  const SCALE_CIRCLE_DASH = [2, 2.5];
  const SCALE_CIRCLE_LABEL_COLOR = "#000000";
  const SCALE_CIRCLE_LABEL_HALO = "rgba(255, 255, 255, 0.85)";
  const SCALE_CIRCLE_LABEL_SIZE = 12 * MAP_SIZE_SCALE;
  const CORRIDOR_LINK_WIDTH_3D = 2.0 * MAP_SIZE_SCALE;
  const CORRIDOR_CLOSED_LINK_WIDTH_3D = 3.2 * MAP_SIZE_SCALE;
  const CORRIDOR_SPARE_LINK_WIDTH_3D = 1.6 * MAP_SIZE_SCALE;
  const CORRIDOR_SPARE_COLOR = "#6aa9ff";
  const CORRIDOR_SPARE_ALPHA = 0.55;
  const CORRIDOR_SPARE_DASH_ON_M = 120;
  const CORRIDOR_SPARE_DASH_OFF_M = 200;
  const CORRIDOR_LINK_PREVIEW_COLOR = "#ffd54f";
  const CORRIDOR_LINK_PREVIEW_WIDTH = 2.4 * MAP_SIZE_SCALE;
  const ROUTE_CROSS_VERTICAL_SCALE = 1.0;
  const LINK_LANE_WIDTH_FACTOR = 0.55;
  const LINK_LANE_OFFSET_METERS = 0;
  const LINK_LANE_ZOOM_BASE = 11.5;
  const LINK_LANE_ZOOM_FACTOR = 0.22;
  const LINK_LANE_ZOOM_MIN = 1.0;
  const LINK_LANE_ZOOM_MAX = 2.6;
  const LINK_LANE_VERTEX_STRIDE = 12;
  const VERTIPORT_LINE_COLOR = "#00e676";
  const VERTIPORT_LINE_HOVER_COLOR = "#8dffbb";
  const VERTIPORT_LINK_WIDTH_3D = 2.0 * MAP_SIZE_SCALE;
  const colorAlpha = 1.0;
  const defaultVerticesPerLine = 2;
  const VERTIPORT_ICON_ID = "vertiport-icon";
  const BASESTATION_ICON_ID = "basestation-icon";
  const VERTIPORT_ZONE_FILL = "rgba(46, 204, 113, 0.25)";
  const VERTIPORT_ZONE_STROKE = "rgba(46, 204, 113, 0.7)";
  const VERTIPORT_ZONE_STROKE_WIDTH = 2.2 * MAP_SIZE_SCALE;
  const VERTIPORT_ZONE_STEPS = 56;
  const VERTIPORT_LINK_DASH_ON_M = 120;
  const VERTIPORT_LINK_DASH_OFF_M = 200;
  const TRAFFIC_GLOW_SUFFIX = "-glow";
  const TRAFFIC_GLOW_COLOR = "rgba(0, 255, 194, 0.9)";
  const TRAFFIC_GLOW_PAD_RATIO = 0.24;
  const TRAFFIC_GLOW_BLUR_RATIO = 0.18;
  const TRAFFIC_GLOW_SIZE_MULTIPLIER = 1.1;
  const TRAFFIC_HALO_RADIUS = 20 * MAP_SIZE_SCALE;
  const TRAFFIC_HALO_BLUR = 0.85;
  const TRAFFIC_HALO_FILL = "rgba(0, 255, 194, 0.32)";
  const TRAFFIC_HALO_STROKE = "rgba(0, 255, 194, 1)";
  const TRAFFIC_HALO_STROKE_WIDTH = 2.5;
  const TRAFFIC_ALTITUDE_SCALE = 1.0;
  const TRAFFIC_HIGHLIGHT_STATE = ["boolean", ["get", "selected"], false];
  const TRAFFIC_GLOW_OPACITY = [
    "case",
    TRAFFIC_HIGHLIGHT_STATE,
    0.95,
    0,
  ];
  const TRAFFIC_HALO_OPACITY = [
    "case",
    TRAFFIC_HIGHLIGHT_STATE,
    1,
    0,
  ];
  const TRAFFIC_3D_HOVER_SCALE = 1.0;
  const TRAFFIC_3D_HOVER_TINT = [0, 1, 0.76];
  const TRAFFIC_3D_MIN_POINT_SIZE = 4.5 * MAP_SIZE_SCALE;
  const TRAFFIC_3D_POINT_SIZE = 13.5 * MAP_SIZE_SCALE;
  const TRAFFIC_3D_ICON_POINT_SIZE = 24 * MAP_SIZE_SCALE;
  const TRAFFIC_3D_ICON_ALPHA = 1.0;
  const TRAFFIC_ICON_ALTITUDE_OFFSET_M = 80;
  const TRAFFIC_3D_COLOR = [0.55, 0.88, 1.0];
  const TRAFFIC_2D_ICON_SIZE = 0.028;
  const TRAFFIC_2D_MAX_PITCH = 6;
  const TRAFFIC_USE_3D_ICON_LAYER = false;
  const TRAFFIC_2D_HALO_RADIUS = 18 * MAP_SIZE_SCALE;
  const TRAFFIC_2D_HALO_BLUR = 0.95;
  const TRAFFIC_2D_HALO_COLOR = "rgba(0, 255, 194, 0.6)";
  const TRAFFIC_2D_HALO_RING_COLOR = "rgba(0, 255, 194, 1)";
  const TRAFFIC_2D_HALO_RING_WIDTH = 1.2;
  const TRAFFIC_2D_HALO_RING_OPACITY = 0.15;
  const TRAFFIC_RISK_RADIUS = 16 * MAP_SIZE_SCALE;
  const TRAFFIC_RISK_BLUR = 0.85;
  const TRAFFIC_RISK_COLOR_EXPR = [
    "case",
    ["==", ["get", "risk_level"], 3],
    "rgba(255, 59, 48, 0.55)",
    ["==", ["get", "risk_level"], 2],
    "rgba(139, 92, 246, 0.5)",
    ["==", ["get", "risk_level"], 1],
    "rgba(255, 214, 10, 0.45)",
    "rgba(0, 0, 0, 0)",
  ];
  const TRAFFIC_RISK_OPACITY = [
    "case",
    [">", ["get", "risk_level"], 0],
    1,
    0,
  ];
  const TRAFFIC_PREDICT_COLOR = "#7cff6b";
  const TRAFFIC_PREDICT_WIDTH = 5.2 * MAP_SIZE_SCALE;
  const TRAFFIC_PREDICT_WIDTH_3D = TRAFFIC_PREDICT_WIDTH * 1.5;
  const TRAFFIC_PREDICT_OPACITY = 0.9;
  const TRAFFIC_PREDICT_DELAY_MS = 0;
  const TRAFFIC_PREDICT_HISTORY_GRACE_MS = 1200;
  const TRAFFIC_PREDICT_FADE_MS = 1200;
  const TRAFFIC_HISTORY_COLOR = "#4b8bff";
  const TRAFFIC_HISTORY_COLOR_3D = "#4b8bff";
  const TRAFFIC_HISTORY_OPACITY = 0.6;
  const TRAFFIC_HISTORY_FADE_MS = 900;
  const TRAFFIC_HISTORY_DOT_COLOR = "#6aa9ff";
  const TRAFFIC_HISTORY_DOT_OPACITY = 0.65;
  const TRAFFIC_HISTORY_DOT_RADIUS = 2.6 * MAP_SIZE_SCALE;
  const TRAFFIC_HISTORY_DOT_INTERVAL_S = 1;
  const TRAFFIC_HISTORY_DOT_FALLBACK_STEP = 15;
  const TRAFFIC_HISTORY_WIDTH = 3.0 * MAP_SIZE_SCALE;
  const TRAFFIC_HISTORY_WIDTH_3D = TRAFFIC_HISTORY_WIDTH * 1;
  const TRAFFIC_PREDICT_MODE_CRUISE = "cruise";
  const TRAFFIC_PREDICT_MODE_HOLD = "hold";
  const TRAFFIC_HIT_RADIUS = 18 * MAP_SIZE_SCALE;
  const TRAFFIC_LEVELS = {
    Low: 100,
    Middle: 2500,
    High: 25000,
  };
  const TRAFFIC_LABELS = {
    Low: "저밀도",
    Middle: "중밀도",
    High: "고밀도",
  };
  const TRAFFIC_ICON_IDS = ["plane1", "plane2", "plane3", "plane4"];
  const TRAFFIC_FALLBACK_ICON = TRAFFIC_ICON_IDS[0];
  const TRAFFIC_ICON_URLS = {
    plane1: absolutizeUrl("resources/plane1.png"),
    plane2: absolutizeUrl("resources/plane2.png"),
    plane3: absolutizeUrl("resources/plane3.png"),
    plane4: absolutizeUrl("resources/plane4.png"),
  };
  const WGS84_A = 6378137.0;
  const WGS84_F = 1.0 / 298.257223563;
  const WGS84_E2 = WGS84_F * (2.0 - WGS84_F);
  const CITY_HALL_LAT = 37.566831;
  const CITY_HALL_LON = 126.978445;
  const CITY_HALL_UE = [217063.379391, -1013419.868553, -220649.796452];
  const AIRSIM_M = [
    [100.0281442606, -0.04714072563858, -14.48008452807, 217305.0259003],
    [-0.01400319634319, -99.95926827854, 22.17141115113, -1014189.34958],
    [-0.07523184332042, -0.06232285328839, 44.59215490766, -221718.536035],
  ];
  const AIRSIM_D_BIAS = 3.0;
  const TELEMETRY_ROTATION_DEG = 90;
  const DEFAULT_OPERATION_START = "06:30";
  const DEFAULT_OPERATION_END = "21:30";
  const DEFAULT_OPERATION_GOAL = 2500;
  const KNOT_TO_MPS = 0.514444;
  const KMH_TO_MPS = 1000 / 3600;
  const MODE_LABELS = {
    waiting: "대기모드",
    takeoff: "이륙 중",
    cruise: "비행 중",
    landing: "착륙 중",
    hold: "홀딩 중",
    ended: "비행 종료",
  };
  const DEFAULT_RULES = {
    speed_mps: 100 * KNOT_TO_MPS,
    accel_mps2: 1.5,
    climb_rate_fpm: 500,
    transition_alt_ft: 50,
    transition_speed_knot: 70,
    holding_s: 2 * 60,
    takeoff_s: 2 * 60,
    landing_s: 2 * 60,
    battery_capacity_s: 30 * 60,
    min_safe_speed_mps: 25,
    turn_rate_deg_s: 3.0,
    separation_m: 300,
    warning_m: 150,
    warning_ec_s: 5,
    warning_trailing_circles: 1,
    warning_leading_knot_delta: 10,
    caution_m: 300,
    caution_ec_s: 10,
    caution_trailing_knot_delta: -10,
    caution_leading_knot_delta: 10,
    risk_predict_horizon_s: 20,
    risk_lateral_m: 50,
    risk_direction_cos: 0.5,
    risk_update_interval_s: 2,
    risk_proximity_lv1_m: 450,
    risk_proximity_lv2_m: 300,
    risk_proximity_lv3_m: 150,
    risk_battery_lv1_pct: 30,
    risk_battery_lv2_pct: 25,
    risk_battery_lv3_pct: 10,
    rnp_max_lat_m: 54,
    rnp_max_ver_m: 0,
    rnp_r_lv1: 0.4,
    rnp_r_lv2: 0.7,
    rnp_r_lv3: 1.0,
    rnp_ttv_lv1_s: 10,
    rnp_ttv_lv2_s: 5,
    wind_enabled: 1,
    wind_time_speed: 60,
    wind_smooth_s: 2,
    wind_cross_gain: 0.6,
    wind_cross_return_s: 12,
    wind_cross_max_m: 600,
    wind_along_gain: 0.5,
    wind_along_max_mps: 8,
    wind_crab_max_deg: 12,
    operation_start_min: 6 * 60 + 30,
    operation_end_min: 21 * 60 + 30,
    operation_goal_count: 2500,
  };
  const DEFAULT_AUTOPILOT = {
    enabled: false,
    duration_s: 10,
    lv1_delta_knot: 10,
    lv2_delta_knot: 20,
    lv3_delta_knot: 30,
  };

  const degToRad = (value) => (value * Math.PI) / 180.0;
  const geodeticToEcef = (latDeg, lonDeg, hMeters = 0) => {
    const lat = degToRad(latDeg);
    const lon = degToRad(lonDeg);
    const sinLat = Math.sin(lat);
    const cosLat = Math.cos(lat);
    const n = WGS84_A / Math.sqrt(1.0 - WGS84_E2 * sinLat * sinLat);
    const x = (n + hMeters) * cosLat * Math.cos(lon);
    const y = (n + hMeters) * cosLat * Math.sin(lon);
    const z = ((1.0 - WGS84_E2) * n + hMeters) * sinLat;
    return [x, y, z];
  };
  const ecefToEnu = (xyz, lat0Deg, lon0Deg, h0Meters = 0) => {
    const [x0, y0, z0] = geodeticToEcef(lat0Deg, lon0Deg, h0Meters);
    const dx = xyz[0] - x0;
    const dy = xyz[1] - y0;
    const dz = xyz[2] - z0;
    const lat0 = degToRad(lat0Deg);
    const lon0 = degToRad(lon0Deg);
    const sinLat = Math.sin(lat0);
    const cosLat = Math.cos(lat0);
    const sinLon = Math.sin(lon0);
    const cosLon = Math.cos(lon0);
    const e = -sinLon * dx + cosLon * dy;
    const n = -sinLat * cosLon * dx - sinLat * sinLon * dy + cosLat * dz;
    const u = cosLat * cosLon * dx + cosLat * sinLon * dy + sinLat * dz;
    return [e, n, u];
  };
  const geodeticToEnu = (latDeg, lonDeg, lat0Deg, lon0Deg, hMeters = 0, h0Meters = 0) =>
    ecefToEnu(geodeticToEcef(latDeg, lonDeg, hMeters), lat0Deg, lon0Deg, h0Meters);
  const metersPerDegLat = (latRad) =>
    111132.92 -
    559.82 * Math.cos(2 * latRad) +
    1.175 * Math.cos(4 * latRad) -
    0.0023 * Math.cos(6 * latRad);
  const metersPerDegLon = (latRad) =>
    111412.84 * Math.cos(latRad) - 93.5 * Math.cos(3 * latRad) + 0.118 * Math.cos(5 * latRad);
  const enuToGeodetic = (e, n, u, lat0Deg, lon0Deg, h0Meters = 0) => {
    const latRad = degToRad(lat0Deg);
    const mLat = metersPerDegLat(latRad);
    const mLon = metersPerDegLon(latRad);
    if (!Number.isFinite(mLat) || !Number.isFinite(mLon) || mLat === 0 || mLon === 0) {
      return { lat: lat0Deg, lon: lon0Deg, alt: h0Meters + u };
    }
    return {
      lat: lat0Deg + n / mLat,
      lon: lon0Deg + e / mLon,
      alt: h0Meters + u,
    };
  };
  const rotateEnu = (e, n, rotationDeg) => {
    if (!rotationDeg) {
      return [e, n];
    }
    const angle = degToRad(-rotationDeg);
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    return [e * cos - n * sin, e * sin + n * cos];
  };
  const computeBearing = (lon1, lat1, lon2, lat2) => {
    const lat1Rad = degToRad(lat1);
    const lat2Rad = degToRad(lat2);
    const dLon = degToRad(lon2 - lon1);
    const y = Math.sin(dLon) * Math.cos(lat2Rad);
    const x =
      Math.cos(lat1Rad) * Math.sin(lat2Rad) -
      Math.sin(lat1Rad) * Math.cos(lat2Rad) * Math.cos(dLon);
    const bearing = (Math.atan2(y, x) * 180) / Math.PI;
    return (bearing + 360) % 360;
  };
  const buildCirclePolygon = (lonDeg, latDeg, radiusKm, steps = VERTIPORT_ZONE_STEPS) => {
    const radiusM = radiusKm * 1000;
    const latRad = degToRad(latDeg);
    const mLat = metersPerDegLat(latRad);
    const mLon = metersPerDegLon(latRad);
    if (!Number.isFinite(mLat) || !Number.isFinite(mLon) || mLat === 0 || mLon === 0) {
      return null;
    }
    const coords = [];
    const count = Math.max(12, steps);
    for (let i = 0; i <= count; i += 1) {
      const angle = (2 * Math.PI * i) / count;
      const north = Math.cos(angle) * radiusM;
      const east = Math.sin(angle) * radiusM;
      coords.push([lonDeg + east / mLon, latDeg + north / mLat]);
    }
    return coords;
  };
  const computeDistanceMeters = (lon1, lat1, lon2, lat2) => {
    const latRad = degToRad((lat1 + lat2) * 0.5);
    const mLat = metersPerDegLat(latRad);
    const mLon = metersPerDegLon(latRad);
    if (!Number.isFinite(mLat) || !Number.isFinite(mLon) || mLat === 0 || mLon === 0) {
      return 0;
    }
    const dLat = (lat2 - lat1) * mLat;
    const dLon = (lon2 - lon1) * mLon;
    return Math.hypot(dLat, dLon);
  };

  class AirsimConverter {
    constructor() {
      this.lat0 = CITY_HALL_LAT;
      this.lon0 = CITY_HALL_LON;
      this.cityHall = CITY_HALL_UE;
      this.matrix = AIRSIM_M;
    }

    geodeticToUe(latDeg, lonDeg, hMeters = 0) {
      const [e, n, u] = geodeticToEnu(latDeg, lonDeg, this.lat0, this.lon0, hMeters, 0);
      const v = [e, n, u, 1.0];
      const x =
        this.matrix[0][0] * v[0] +
        this.matrix[0][1] * v[1] +
        this.matrix[0][2] * v[2] +
        this.matrix[0][3] * v[3];
      const y =
        this.matrix[1][0] * v[0] +
        this.matrix[1][1] * v[1] +
        this.matrix[1][2] * v[2] +
        this.matrix[1][3] * v[3];
      const z =
        this.matrix[2][0] * v[0] +
        this.matrix[2][1] * v[1] +
        this.matrix[2][2] * v[2] +
        this.matrix[2][3] * v[3];
      return [x, y, z];
    }

    wgs84ToAirsimNed(latDeg, lonDeg, altMeters = 0) {
      const [xAbs, yAbs, zAbs] = this.geodeticToUe(latDeg, lonDeg, altMeters);
      const [chx, chy, chz] = this.cityHall;
      const xCm = xAbs - chx;
      const yCm = yAbs - chy;
      const zCm = zAbs - chz;
      const n = xCm / 100.0;
      const e = yCm / 100.0;
      const d = -zCm / 100.0 + AIRSIM_D_BIAS;
      return [n, e, d];
    }
  }

  class CenterControl {
    constructor(onClick) {
      this._onClick = onClick;
      this._container = null;
      this._button = null;
      this._handleClick = () => {
        if (this._onClick) {
          this._onClick();
        }
      };
    }

    onAdd(map) {
      this._map = map;
      const container = document.createElement("div");
      container.className = "maplibregl-ctrl maplibregl-ctrl-group center-control";
      const button = document.createElement("button");
      button.type = "button";
      button.className = "center-control-btn";
      button.title = "Reset view";
      const dot = document.createElement("span");
      dot.className = "center-control-dot";
      button.appendChild(dot);
      button.addEventListener("click", this._handleClick);
      container.appendChild(button);
      this._container = container;
      this._button = button;
      return container;
    }

    onRemove() {
      if (this._button) {
        this._button.removeEventListener("click", this._handleClick);
      }
      if (this._container && this._container.parentNode) {
        this._container.parentNode.removeChild(this._container);
      }
      this._map = undefined;
    }
  }

  class MapApp {
    constructor(config) {
      this.config = config;
      this.map = null;
      this.mapContainer = document.getElementById("map");
      this.playbackPanel = document.getElementById("playback-panel");
      this.playbackConnectButton = null;
      this.playbackPlayButton = null;
      this.playbackFastButton = null;
      this.playbackPauseButton = null;
      this.playbackStopButton = null;
      this.playbackResetButton = null;
      this.playbackSpeedValue = 1;
      this.themeButtons = Array.from(
        document.querySelectorAll(".theme-card:not(.base-card)"),
      );
      this.themePanel = document.getElementById("theme-controls");
      this.themeToggleButton = document.getElementById("theme-toggle");
      this.baseToggleButton = document.getElementById("theme-base");
      this.baseList = document.getElementById("base-list");
      this.baseControls = {
        layer3dButton: document.querySelector('[data-action="layer-3d"]'),
      };
      this.actionButtons = Array.from(document.querySelectorAll(".ui-btn"));
      this.closeButtons = Array.from(document.querySelectorAll(".panel-close"));
      this.panels = {
        vertiport: document.getElementById("vertiport-panel"),
        corridor: document.getElementById("corridor-panel"),
        base: document.getElementById("base-panel"),
        scenario: document.getElementById("scenario-panel"),
        plan: document.getElementById("plan-panel"),
        settings: document.getElementById("settings-panel"),
        autopilot: document.getElementById("autopilot-panel"),
        "sim-settings": document.getElementById("sim-settings-panel"),
      };
      this.tableBodies = {
        vertiport: document.getElementById("vertiport-table-body"),
        corridor: document.getElementById("corridor-table-body"),
      };
      this.fileControls = {
        vertiport: {
          nameInput: document.getElementById("vertiport-file-name"),
          openButton: document.querySelector('[data-action="open-vertiport"]'),
          resetButton: document.querySelector('[data-action="reset-vertiport"]'),
        },
        corridor: {
          nameInput: document.getElementById("corridor-file-name"),
          openButton: document.querySelector('[data-action="open-corridor"]'),
          resetButton: document.querySelector('[data-action="reset-corridor"]'),
        },
        basestation: {
          nameInput: document.getElementById("basestation-file-name"),
          openButton: document.querySelector('[data-action="open-basestation"]'),
        },
      };
      this.datafilesResetButton = document.querySelector('[data-action="reset-datafiles"]');
      this.planControls = {
        selectButton: document.querySelector('[data-action="plan-select"]'),
        resetButton: document.querySelector('[data-action="plan-reset"]'),
        applyButton: document.querySelector('[data-action="plan-apply"]'),
      };
      this.settingsControls = {
        hostInput: document.getElementById("settings-airsim-host"),
        portInput: document.getElementById("settings-airsim-port"),
        applyButton: document.querySelector('[data-action="settings-apply"]'),
        resetButton: document.querySelector('[data-action="settings-reset"]'),
        trafficInputs: Array.from(document.querySelectorAll('input[name="daily-traffic"]')),
        trafficCounts: Array.from(document.querySelectorAll("[data-traffic-count]")),
        highDensityFolderNameInput: document.getElementById("highdensity-folder-name"),
        highDensityFolderLoadButton: document.querySelector(
          '[data-action="load-highdensity-folder"]',
        ),
        highDensityFolderResetButton: document.querySelector(
          '[data-action="reset-highdensity-folder"]',
        ),
        highDensityFolderPicker: document.getElementById("highdensity-folder-picker"),
        highDensityFolderIndicator: document.getElementById("highdensity-folder-indicator"),
        operationStart: document.getElementById("operation-start"),
        operationEnd: document.getElementById("operation-end"),
        operationTimeSummary: document.getElementById("operation-time-summary"),
        operationGoal: document.getElementById("operation-goal"),
        operationGoalSummary: document.getElementById("operation-goal-summary"),
      };
      this.ruleControls = {
        speedInput: document.getElementById("rule-speed"),
        speedUnitButtons: Array.from(document.querySelectorAll("[data-speed-unit]")),
        accelInput: document.getElementById("rule-accel"),
        climbRateInput: document.getElementById("rule-climb-rate"),
        climbRateMps: document.getElementById("rule-climb-rate-ms"),
        transitionAltInput: document.getElementById("rule-transition-alt"),
        transitionAltMeters: document.getElementById("rule-transition-alt-m"),
        transitionSpeedInput: document.getElementById("rule-transition-speed"),
        batteryInput: document.getElementById("rule-battery"),
        minSpeedInput: document.getElementById("rule-min-speed"),
        transitionSpeedMps: document.getElementById("rule-transition-speed-mps"),
        holdingInput: document.getElementById("rule-holding"),
        takeoffInput: document.getElementById("rule-takeoff"),
        landingInput: document.getElementById("rule-landing"),
        turnRateInput: document.getElementById("rule-turn-rate"),
        separationInput: document.getElementById("rule-separation"),
        separationFt: document.getElementById("rule-separation-ft"),
        warningDistInput: document.getElementById("rule-warning-dist"),
        warningFt: document.getElementById("rule-warning-ft"),
        warningEcInput: document.getElementById("rule-warning-ec"),
        warningTrailingInput: document.getElementById("rule-warning-trailing"),
        warningLeadingInput: document.getElementById("rule-warning-leading"),
        cautionDistInput: document.getElementById("rule-caution-dist"),
        cautionFt: document.getElementById("rule-caution-ft"),
        cautionEcInput: document.getElementById("rule-caution-ec"),
        cautionTrailingInput: document.getElementById("rule-caution-trailing"),
        cautionLeadingInput: document.getElementById("rule-caution-leading"),
        riskHorizonInput: document.getElementById("rule-risk-horizon"),
        riskLateralInput: document.getElementById("rule-risk-lateral"),
        riskDirectionInput: document.getElementById("rule-risk-direction"),
        riskIntervalInput: document.getElementById("rule-risk-interval"),
        riskProxLv3Input: document.getElementById("rule-risk-prox-lv3"),
        riskProxLv2Input: document.getElementById("rule-risk-prox-lv2"),
        riskProxLv1Input: document.getElementById("rule-risk-prox-lv1"),
        riskBattLv3Input: document.getElementById("rule-risk-batt-lv3"),
        riskBattLv2Input: document.getElementById("rule-risk-batt-lv2"),
        riskBattLv1Input: document.getElementById("rule-risk-batt-lv1"),
        rnpMaxLatInput: document.getElementById("rule-rnp-max-lat"),
        rnpMaxVerInput: document.getElementById("rule-rnp-max-ver"),
        rnpRLv1Input: document.getElementById("rule-rnp-r-lv1"),
        rnpRLv2Input: document.getElementById("rule-rnp-r-lv2"),
        rnpRLv3Input: document.getElementById("rule-rnp-r-lv3"),
        rnpTtvLv1Input: document.getElementById("rule-rnp-ttv-lv1"),
        rnpTtvLv2Input: document.getElementById("rule-rnp-ttv-lv2"),
        windEnabledInput: document.getElementById("rule-wind-enabled"),
        windTimeSpeedInput: document.getElementById("rule-wind-time-speed"),
        windSmoothInput: document.getElementById("rule-wind-smooth"),
        windCrossGainInput: document.getElementById("rule-wind-cross-gain"),
        windCrossReturnInput: document.getElementById("rule-wind-cross-return"),
        windCrossMaxInput: document.getElementById("rule-wind-cross-max"),
        windAlongGainInput: document.getElementById("rule-wind-along-gain"),
        windAlongMaxInput: document.getElementById("rule-wind-along-max"),
        windCrabMaxInput: document.getElementById("rule-wind-crab-max"),
      };
      this.autopilotControls = {
        lv1Input: document.getElementById("autopilot-lv1"),
        lv2Input: document.getElementById("autopilot-lv2"),
        lv3Input: document.getElementById("autopilot-lv3"),
        durationInput: document.getElementById("autopilot-duration"),
        onButton: document.querySelector('[data-action="autopilot-on"]'),
        offButton: document.querySelector('[data-action="autopilot-off"]'),
      };
      this.filePickers = {};
      this.defaultFiles = {
        vertiport: {
          url: this.config.data.vertiportCsv,
          name: getFileName(this.config.data.vertiportCsv),
        },
        corridor: {
          url: this.config.data.waypointCsv,
          name: getFileName(this.config.data.waypointCsv),
        },
        basestation: {
          url: this.config.data.basestationCsv,
          name: getFileName(this.config.data.basestationCsv),
        },
      };
      this.currentTheme = "dark";
      const basePalette = BASE_MAP_PALETTES[this.currentTheme] || BASE_MAP_PALETTES.dark;
      this.terrainEnabled = false;
      this.building3dEnabled = false;
      this.building3dPending = false;
      this.homeView = null;
      this.airsimDefaults = {
        host: this.config.airsim.host,
        port: this.config.airsim.port,
      };
      this.airsimHost = this.config.airsim.host;
      this.airsimPort = this.config.airsim.port;
      this.airsimChannel = null;
      this.airsimBridge = null;
      this.controlBridge = null;
      this.uiBridge = null;
      this.telemetryMarker = null;
      this.telemetryLabel = null;
      this.telemetryName = "UAM1";
      this.telemetryConnected = false;
      this.telemetryLogAt = 0;
      this.telemetryAltFlipLogAt = 0;
      this.telemetryActive = false;
      this.telemetryPosition = null;
      this.telemetryAltitude = null;
      this.telemetryTrackEnabled = false;
      this.telemetryTrackCoords = [];
      this.telemetryTrackMaxPoints = 1200;
      this.telemetryTrackLayer = null;
      this.telemetryCalibration = null;
      this.telemetryRotationDeg = TELEMETRY_ROTATION_DEG;
      this.isPlaying = false;
      this.airsimConverter = new AirsimConverter();
      this.corridorLayer = null;
      this.corridorLinks3dLayer = null;
      this.corridorSpareLinks3dLayer = null;
      this.corridorSpareOpen3dLayer = null;
      this.corridorClosed3dLayer = null;
      this.corridorHitData = null;
      this.corridorSpareHitData = null;
      this.corridorHover = null;
      this.corridorHoverLabel = null;
      this.corridorSpareHoverIndex = -1;
      this.pendingCorridorRows = null;
      this.lastCorridorRows = null;
      this.corridorLoadToken = 0;
      this.corridorEnsured = false;
      this.corridorLinkUpdateScheduled = false;
      this.corridorSpareLinkUpdateScheduled = false;
      this.corridorSpareOpenLinkUpdateScheduled = false;
      this.corridorClosedUpdateScheduled = false;
      this.corridorLinkResizeBound = false;
      this.corridorSpareLinkResizeBound = false;
      this.corridorSpareOpenLinkResizeBound = false;
      this.corridorClosedResizeBound = false;
      this.corridorPointLookup = new Map();
      this.corridorLinkLookup = new Map();
      this.corridorSpareLinkLookup = new Map();
      this.corridorData = null;
      this.corridorSpareLinkDashIndex = null;
      this.corridorClosedLineIndices = [];
      this.closedCorridorEdges = new Set();
      this.openSpareCorridorEdges = new Set();
      this.corridorPopup = null;
      this.corridorPopupEdge = null;
      this.corridorLinkPopup = null;
      this.corridorLinking = null;
      this.vertiportLinking = null;
      this.vertiportHover = null;
      this.vertiportHoverId = null;
      this.vertiportLinkHover = null;
      this.vertiportLinkHoverId = null;
      this.vertiportLinkHoverIndex = -1;
      this.vertiportLinkUpdateScheduled = false;
      this.vertiportLinkResizeBound = false;
      this.vertiportHoverLabel = null;
      this.vertiportHoverName = null;
      this.vertiportLabels = [];
      this.lastVertiportRows = null;
      this.pendingVertiportRows = null;
      this.vertiportLoadToken = 0;
      this.vertiportEnsured = false;
      this.vertiportIconPromise = null;
      this.vertiportData = null;
      this.vertiportPointLookup = new Map();
      this.vertiportLinkLookup = new Map();
      this.vertiportAltLookup = new Map();
      this.vertiportResourceLookup = new Map();
      this.vertiportLinkHitData = null;
      this.baseStationEnsured = false;
      this.baseStationIconPromise = null;
      this.baseStationData = null;
      this.baseStationPointLookup = new Map();
      this.pendingBaseStationRows = null;
      this.lastBaseStationRows = null;
      this.baseStationSequence = 1;
      this.baseStationPendingNodes = new Map();
      this.baseStationPendingCounter = 0;
      this.baseStationEditPopup = null;
      this.baseStationEditPopupNodeId = null;
      this.baseStationEditPopupName = null;
      this.baseStationEditMovingId = null;
      this.baseStationEditMovingName = null;
      this.baseStationEditHighlightName = "";
      this.pendingTrafficPositions = null;
      this.trafficIconsReady = false;
      this.trafficIconsPromise = null;
      this.trafficIconImages = new Map();
      this.trafficIconScales = new Map();
      this.trafficIconBaseSize = null;
      this.trafficAtlas = null;
      this.traffic3dLayer = null;
      this.traffic3dIconLayer = null;
      this.traffic3dVisible = false;
      this.traffic2dVisible = false;
      this.traffic3dInitScheduled = false;
      this.traffic3dIconInitScheduled = false;
      this.traffic2dInitScheduled = false;
      this.trafficUpdateScheduled = false;
      this.mapRepaintScheduled = false;
      this.scaleCopyBound = false;
      this.scaleCopyActive = false;
      this.scaleCopyGhost = null;
      this.scaleCopyScaleEl = null;
        this.scaleCopyMoveHandler = null;
        this.scaleCopyCancelHandler = null;
        this.scaleCopyUpdateHandler = null;
        this.scaleCopyGap = 8;
        this.scaleCopyContextBound = false;
        this.scaleCopyContextHandler = null;
        this.scaleCircleActive = false;
        this.scaleCircleCenter = null;
        this.scaleCircleRadiusKm = null;
        this.emergencyLandingActive = false;
        this.emergencyLandingFlightId = null;
        this.emergencyLandingFlightName = "";
      this.emergencyLandingTarget = null;
      this.emergencyLandingMarker = null;
      this.emergencyLandingPopup = null;
      this.trafficPopup = null;
      this.trafficPopupFields = null;
      this.trafficPopupFlightId = null;
      this.trafficPopupFlightName = "";
      this.trafficPopupAnchor = null;
      this.trafficNamePopup = null;
      this.trafficNamePopupFields = null;
      this.trafficNamePopupId = null;
      this.trafficNamePopupName = "";
      this.trafficHoverPopup = null;
      this.trafficHoverId = null;
      this.trafficHoverName = "";
      this.trafficInteractionsBound = false;
      this.trafficLastPositions = new Map();
      this.trafficAltitudeById = new Map();
      this.trafficByName = new Map();
      this.trafficById = new Map();
      this.lastTraffic3dEntries = [];
      this.trafficSelectedId = null;
      this.trafficPredictLayer3d = null;
      this.trafficPredictVisible = false;
      this.trafficPredictEnableAt = 0;
      this.trafficPredictFadeTimer = null;
      this.trafficPredictOpacity = TRAFFIC_PREDICT_OPACITY;
      this.trafficHistoryLayer3d = null;
      this.trafficHistoryPoints = [];
      this.trafficHistoryName = "";
      this.trafficHistoryRequestId = 0;
      this.trafficHistoryRefreshTimer = null;
      this.trafficHistoryRefreshIntervalMs = 1000;
      this.trafficHistoryLoading = false;
      this.trafficHistoryLoadingName = "";
      this.trafficHistoryOpacity = TRAFFIC_HISTORY_OPACITY;
      this.trafficHistoryVisible = false;
      this.trafficHistoryFadeTimer = null;
      this.resourcesVpLoaded = false;
      this.routeGraph = null;
      this.routeNodeLookup = new Map();
      this.routeNodeXY = new Map();
      this.routeProjection = null;
      this.planRoute = [];
      this.appliedPlan = [];
      this.planSelectionMarkers = { start: null, end: null };
      this.planState = {
        enabled: false,
        mode: null,
        selection: [],
        viaNodes: [],
        manualPath: [],
        manualPrev: null,
        manualCurrent: null,
      };
      this.activeEdges = [];
      this.planLayersReady = false;
      this.planRouteLayer3d = null;
      this.vertiportLinks3dLayer = null;
      this.vertiportLinkDashIndex = null;
      this.vertiportZoneName = null;
      this.vertiportManagePopup = null;
      this.vertiportManageName = null;
      this.dashboardPanel = document.getElementById("dashboard-panel");
      this.dashboardToggle = document.getElementById("dashboard-toggle");
      this.dashboardTabButtons = Array.from(document.querySelectorAll(".dashboard-tab"));
      this.dashboardTabPanels = new Map();
      this.dashboardTables = new Map();
      this.dashboardRiskCounts = new Map();
      this.dashboardVisible = false;
      this.dashboardData = new Map();
      this.dashboardTimes = new Map();
      this.dashboardFlightMetrics = new Map();
      this.dashboardSequence = 0;
      this.dashboardFailureRows = [];
      this.dashboardFailureSequence = 0;
      this.dashboardSelectedName = null;
      this.dashboardAutoSized = new Map();
      this.dashboardRenderQueued = false;
      this.dashboardRenderAll = false;
      this.dashboardActiveTab = "management";
      this.pendingDashboardTime_s = null;
      this.dashboardToggleDefaultRight = null;
      this.dashboardTogglePositionTimer = null;
      this.dashboardToggleTransitionBound = false;
      this.riskTrendCanvas = document.getElementById("risk-trend-canvas");
      this.riskTrendCtx = this.riskTrendCanvas ? this.riskTrendCanvas.getContext("2d") : null;
      this.riskTrendButtons = Array.from(document.querySelectorAll(".risk-level-toggle"));
      this.riskTrendExportPngButton = document.querySelector('[data-action="risk-export-png"]');
      this.riskTrendExportCsvButton = document.querySelector('[data-action="risk-export-csv"]');
      this.riskTrendLevels = { 1: true, 2: true, 3: true };
      this.riskTrendData = { times: [], level1: [], level2: [], level3: [] };
      this.riskTrendHistory = { times: [], level1: [], level2: [], level3: [] };
      this.riskTrendDisplayPoints = 300;
      this.riskTrendLastTime = null;
      this.riskTrendInitialized = false;
      this.riskTrendResizeQueued = false;
      this.warningSoundContext = null;
      this.warningSoundDurationMs = 120;
      this.warningSoundAttackMs = 8;
      this.warningSoundReleaseMs = 12;
      this.warningSoundFreqHz = 780;
      this.warningSoundVolume = 0.55;
      this.warningSoundIntervalsMs = { 1: 2000, 2: 1200, 3: 700 };
      this.warningSoundLevel = 0;
      this.warningSoundActive = false;
      this.warningSoundTimer = null;
      this.warningSoundPrimed = false;
      this.soundToggleButton = document.getElementById("sound-toggle");
      this.soundMuteStorageKey = "uatm.soundMuted";
      this.soundMuted = false;
      if (typeof window !== "undefined" && window.localStorage) {
        const stored = window.localStorage.getItem(this.soundMuteStorageKey);
        this.soundMuted = stored === "1" || stored === "true";
      }
      this.humanWorkloadCanvas = document.getElementById("human-workload-canvas");
      this.humanWorkloadCtx = this.humanWorkloadCanvas
        ? this.humanWorkloadCanvas.getContext("2d")
        : null;
      this.humanWorkloadNote = document.getElementById("human-workload-note");
      this.humanWorkloadExportCsvButton = document.querySelector(
        '[data-action="human-workload-csv"]',
      );
      this.humanSpeedExportCsvButton = document.querySelector('[data-action="human-speed-csv"]');
      this.humanAirspaceExportCsvButton = document.querySelector(
        '[data-action="human-airspace-csv"]',
      );
      this.humanEmergencyExportCsvButton = document.querySelector(
        '[data-action="human-emergency-csv"]',
      );
      this.humanTableBodies = {
        speed: document.getElementById("human-speed-body"),
        airspace: document.getElementById("human-airspace-body"),
        emergency: document.getElementById("human-emergency-body"),
      };
      this.humanInterventionEvents = [];
      this.humanSpeedEvents = [];
      this.humanAirspaceEvents = [];
      this.humanEmergencyEvents = [];
      this.humanWorkloadData = {
        times: [],
        total: [],
        speed: [],
        airspace: [],
        emergency: [],
      };
      this.humanWorkloadHistory = {
        times: [],
        total: [],
        speed: [],
        airspace: [],
        emergency: [],
      };
      this.humanWorkloadWindow_s = 10;
      this.humanWorkloadDisplayPoints = 300;
      this.humanWorkloadLastTime = null;
      this.humanWorkloadHistoryLastTime = null;
      this.humanWorkloadInitialized = false;
      this.humanSpeedHistory = [];
      this.humanAirspaceHistory = [];
      this.humanEmergencyHistory = [];
      this.humanWorkloadResizeQueued = false;
      this.humanWorkloadWeights = { speed: 1, airspace: 2, emergency: 3 };
      this.humanEventLimit = 1000;
      this.humanTableMaxRows = 50;
      this.corridorPendingNodes = new Map();
      this.corridorPendingCounter = 0;
      this.vertiportPendingNodes = new Map();
      this.vertiportPendingCounter = 0;
      this.editModeButtons = { airspace: null, vertiport: null, basestation: null };
      this.editToolButtons = { airspace: null, vertiport: null, basestation: null };
      this.editToolPanels = { airspace: null, vertiport: null, basestation: null };
      this.activeEditTools = { airspace: null, vertiport: null, basestation: null };
      this.appRoot = document.getElementById("app");
      this.startScreen = document.getElementById("start-screen");
      this.startScreenTrigger = document.getElementById("start-screen-trigger");
      this.startScreenNotes = document.getElementById("start-screen-notes");
      this.startScreenNotesBody = document.getElementById("start-screen-notes-body");
      this.startScreenNotesUrl = null;
      this.startScreenNotesLoaded = false;
      this.languageButtons = Array.from(
        document.querySelectorAll("#start-screen [data-lang]"),
      );
      this.language = null;
      this.startScreenInitialized = false;
      this.startScreenDismissed = false;
      this.startScreenPointerHandler = null;
      this.startResetPromise = null;
      this.loadingScreen = document.getElementById("loading-screen");
      this.loadingStartMs = null;
      this.loadingMinDelayMs = 0;
      this.loadingReady = false;
      this.loadingHideTimer = null;
      this.tutorialOverlay = document.getElementById("tutorial-overlay");
      this.tutorialClose = document.getElementById("tutorial-close");
      this.tutorialOpen = document.getElementById("tutorial-open");
      this.tutorialGuidePanel = document.getElementById("tutorial-guide-panel");
      this.tutorialStepPanel = document.getElementById("tutorial-step-panel");
      this.tutorialStepTitle = document.getElementById("tutorial-step-title");
      this.tutorialStepLabel = document.getElementById("tutorial-step-label");
      this.tutorialStepDesc = document.getElementById("tutorial-step-desc");
      this.tutorialStepConfirm = document.getElementById("tutorial-step-confirm");
      this.tutorialStepArrow = document.getElementById("tutorial-step-arrow");
      this.tutorialCallouts = Array.from(document.querySelectorAll(".tutorial-callout"));
      this.tutorialShown = false;
      this.tutorialDismissed = false;
      this.tutorialResizeHandler = null;
      this.tutorialMode = "guide";
      this.tutorialStepIndex = 0;
      this.tutorialSubstep = 0;
      this.tutorialStepHits = [];
      this.tutorialClickHandler = null;
      this.tutorialAutoDismissHandler = null;
      this.tutorialHighlighted = [];
      this.tutorialSteps = null;
      this.tutorialTargetRect = null;
      this.overlayPitchLocked = false;
      this.overlayPitchState = null;
      this.didInitialDataReset = false;
      this.planReloadToken = 0;
      this.datafilesResetInFlight = null;
      this.simTimeLabel = document.getElementById("sim-time");
      this.simTimeSettingsButton = document.querySelector(".sim-time-settings-btn");
      this.simSettingsPanel = document.getElementById("sim-settings-panel");
      this.simSettingsCloseButton = document.querySelector('[data-action="close-sim-settings"]');
      this.simStats = {
        total: document.getElementById("sim-total-count"),
        active: document.getElementById("sim-active-count"),
        done: document.getElementById("sim-done-count"),
      };
      this.statusLog = document.getElementById("status-log");
      this.statusLogList = this.statusLog ? this.statusLog.querySelector(".status-log-list") : null;
      this.statusMessages = [];
      this.statusPinned = new Map();
      this.statusLogMaxEntries = 5;
      this.statusCleanupTimer = null;
      this.rulesState = null;
      this.rulesInitialized = false;
      this.autopilotState = { ...DEFAULT_AUTOPILOT };
      this.autopilotInitialized = false;
      this.autopilotPendingSync = false;
      this.settingsDownloadLogsButton = document.querySelector(
        '[data-action="settings-download-logs"]',
      );
      this.simSettingsDownloadLogsButton = document.querySelector(
        '[data-action="sim-settings-download-logs"]',
      );
      this.repeatTapState = new Map();
      this.speedUnit = "knot";
      this.editMode = null;
      this.webApiEnabled = false;
      this.webApiPolling = false;
      this.webApiTimer = null;
      this.webApiInFlight = false;
      this.webApiIntervalMs = 300;
      this.webApiActiveIntervalMs = this.webApiIntervalMs;
      this.webApiIdleIntervalMs = 900;
      this.webApiHiddenIntervalMs = 1800;
      this.webApiBaseUrl = "";
      this.webPositionsRev = -1;
      this.webPositionsCache = new Map();
      this.mapWarmupScheduled = false;
      this.mapWarmupStarted = false;
      this.mapWarmupCompleted = false;
      this.flightplanModeEnabled = false;
      this.currentTrafficSelection = null;
      this.highDensityFolderLoaded = false;
      this.highDensityFolderName = "";
      this.highDensityFolderFileCount = 0;
      this.highDensityFolderFiles = [];
      this.highDensityFolderUploadEnabled = false;
      this.lastSimTime_s = 0;
      this.lastDashboardPositions = null;
    }

    t(key, params, fallback) {
      if (typeof window !== "undefined" && window.AppI18n) {
        return window.AppI18n.t(key, params, fallback);
      }
      return fallback != null ? fallback : key;
    }

    translateLiteral(text) {
      if (typeof window !== "undefined" && window.AppI18n) {
        return window.AppI18n.translateLiteral(text);
      }
      return text;
    }

    translateStatusText(text) {
      if (typeof window !== "undefined" && window.AppI18n) {
        return window.AppI18n.translateStatus(text);
      }
      return text;
    }

    shouldTriggerRepeatTapContext(key, point, options = {}) {
      if (!key || !point) {
        return false;
      }
      const now = performance.now();
      const minMs = Math.max(250, Number(options.minMs ?? 400));
      const maxMs = Math.max(minMs, Number(options.maxMs ?? 2200));
      const tolPxBase = Number(options.tolerancePx ?? 18);
      const tolerancePx = Math.max(8, tolPxBase * MAP_SIZE_SCALE);
      const state = this.repeatTapState || new Map();
      this.repeatTapState = state;
      const prev = state.get(key);
      state.set(key, { x: point.x, y: point.y, t: now });
      if (!prev) {
        return false;
      }
      const dt = now - prev.t;
      if (dt < minMs || dt > maxMs) {
        return false;
      }
      const dist = Math.hypot(point.x - prev.x, point.y - prev.y);
      if (dist > tolerancePx) {
        return false;
      }
      state.delete(key);
      return true;
    }

    buildSyntheticContextMenuEvent(point, lngLat) {
      const noop = () => {};
      return {
        point,
        lngLat,
        originalEvent: {
          preventDefault: noop,
          stopPropagation: noop,
          button: 2,
          buttons: 2,
        },
        preventDefault: noop,
      };
    }

    updateLanguageButtons() {
      if (!Array.isArray(this.languageButtons) || !this.languageButtons.length) {
        return;
      }
      const current = this.language || (window.AppI18n ? window.AppI18n.getLang() : "en");
      this.languageButtons.forEach((button) => {
        const isActive = button.dataset.lang === current;
        button.classList.toggle("is-active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
      });
    }

    setLanguage(lang, options = {}) {
      if (typeof window !== "undefined" && window.AppI18n) {
        window.AppI18n.setLang(lang, options);
        this.language = window.AppI18n.getLang();
      } else {
        this.language = lang;
      }
      this.updateLanguageButtons();
      this.loadStartNotes();
      if (typeof this.renderStatusLog === "function") {
        this.renderStatusLog();
      }
      if (typeof this.updateHighDensityFolderUi === "function") {
        this.updateHighDensityFolderUi();
      }
      if (this.tutorialMode === "guided") {
        this.renderTutorialStep();
      }
    }

    initLanguage() {
      const initial = window.AppI18n ? window.AppI18n.getLang() : "en";
      if (Array.isArray(this.languageButtons)) {
        this.languageButtons.forEach((button) => {
          button.addEventListener("click", (event) => {
            if (event && event.preventDefault) {
              event.preventDefault();
            }
            if (event && event.stopPropagation) {
              event.stopPropagation();
            }
            const targetLang = button.dataset.lang || "en";
            this.setLanguage(targetLang);
          });
        });
      }
      this.setLanguage(initial, { persist: false });
    }

    setSoundMuted(muted, options = {}) {
      const next = Boolean(muted);
      if (next === this.soundMuted && options.force !== true) {
        return;
      }
      this.soundMuted = next;
      if (this.soundToggleButton) {
        this.soundToggleButton.classList.toggle("is-active", next);
        this.soundToggleButton.setAttribute("aria-pressed", next ? "true" : "false");
      }
      document.body.classList.toggle("sound-muted", next);
      if (options.persist !== false && typeof window !== "undefined" && window.localStorage) {
        window.localStorage.setItem(this.soundMuteStorageKey, next ? "1" : "0");
      }
      if (next) {
        this.stopWarningSoundLoop();
        return;
      }
      if (this.warningSoundLevel > 0) {
        this.startWarningSoundLoop();
      }
    }

    toggleSoundMuted() {
      this.setSoundMuted(!this.soundMuted);
    }

    init() {
      this.initLanguage();
      this.map = this.createMap();
      this.initStartScreen();
      this.initLoadingScreen();
      this.initTutorialOverlay();
      this.initStatusLog();
      this.normalizeThemeButtons();
      this.bindThemeButtons();
      this.bindThemeToggle();
      this.bindBaseToggle();
      this.bindBaseControls();
      this.bindActionButtons();
      this.setSoundMuted(this.soundMuted, { persist: false, force: true });
      this.bindSimTimeSettingsButton();
      this.bindCloseButtons();
      this.bindPlaybackControls();
      this.bindFileControls();
      this.bindEditModeButtons();
      this.bindEditToolButtons();
      this.syncFileNames();
      void this.loadDefaultTables();
      this.bindPlanControls();
      this.bindSettingsControls();
      this.bindSimSettingsPanel();
      this.bindLogExportButtons();
      this.bindRuleControls();
      this.initSettingsPanel();
      this.bindAutopilotControls();
      this.initAutopilotPanel();
      this.initDashboardPanel();
      this.initRiskTrend();
      this.initWarningSound();
      this.initHumanInterventionPanel();
      this.applyTheme(this.currentTheme);
      this.connectAirsimBridge();
      this.loadResourcesVp();
      this.setupScaleObserver();
      this.setupScaleCopy();
      this.setupTerrainToggle();
      this.setupCorridorHover();
      this.setupCorridorCloseClick();
      this.setupVertiportHover();
      this.setupVertiportZoneClick();
      this.setupTrafficVisibility();
      this.setupTrafficHover();
    }

    createMap() {
      const style = this.buildStyle();
      if (
        this.config &&
        this.config.perf &&
        this.config.perf.prewarmWorkers &&
        typeof maplibregl !== "undefined" &&
        typeof maplibregl.prewarm === "function"
      ) {
        try {
          maplibregl.prewarm();
        } catch (_err) {
          // Best-effort warmup.
        }
      }
      const map = new maplibregl.Map({
        container: "map",
        style: style,
        center: this.config.center,
        zoom: this.config.startZoom,
        minZoom: this.config.minZoom,
        maxZoom: this.config.maxZoom + this.config.view.maxZoomBuffer,
        maxPitch: this.config.view.maxPitch,
        attributionControl: false,
      });

      map.on("styleimagemissing", (event) => {
        if (event && event.id === VERTIPORT_ICON_ID) {
          this.ensureVertiportIcon();
        }
        if (event && event.id === BASESTATION_ICON_ID) {
          this.ensureBaseStationIcon();
        }
      });

      const scaleWidth = Math.round(120 * MAP_SIZE_SCALE);
      map.addControl(
        new maplibregl.ScaleControl({ maxWidth: scaleWidth, unit: "metric" }),
        "bottom-right",
      );
      map.addControl(new CenterControl(() => this.resetView()), "bottom-right");
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");

      const updateTiltClass = () => {
        if (!this.mapContainer || !this.map || typeof this.map.getPitch !== "function") {
          return;
        }
        const pitch = Number(this.map.getPitch());
        this.mapContainer.classList.toggle("is-tilted", Number.isFinite(pitch) && pitch > 0.5);
      };
      updateTiltClass();
      map.on("move", updateTiltClass);

      map.once("load", async () => {
        this.scheduleMapWarmup();
        this.updateMapTheme(this.currentTheme);
        this.ensurePlanLayers();
        await this.ensureVertiportIcon();
        if (this.building3dPending) {
          this.setBuilding3dEnabled(true);
        }
        if (this.pendingTrafficPositions) {
          const positions = this.pendingTrafficPositions;
          this.pendingTrafficPositions = null;
          this.updateTrafficPositions(positions);
        }

        const scheduleLinkUpdates = () => {
          if (this.scheduleCorridorLinkUpdate) {
            this.scheduleCorridorLinkUpdate();
          }
          if (this.scheduleCorridorSpareLinkUpdate) {
            this.scheduleCorridorSpareLinkUpdate();
          }
          if (this.scheduleVertiportLinkUpdate) {
            this.scheduleVertiportLinkUpdate();
          }
        };

        const runAfterIdle = async () => {
          const wait = (ms) =>
            new Promise((resolve) => window.setTimeout(resolve, Math.max(0, ms)));
          const autoReset = async () => {
            try {
              await this.resetDatafilesToDefault();
            } catch (error) {
              console.warn("Auto reset failed.", error);
            }
          };

          if (!this.didInitialDataReset) {
            const deferInitialReset = this.startScreen && !this.startScreenDismissed;
            if (!deferInitialReset) {
              this.didInitialDataReset = true;
              const start = performance.now();
              await autoReset();
              const popoutScale = panelParam ? 0.5 : 1;
              const resetDelayMs = 1000 * popoutScale;
              const minReadyMs = 2000 * popoutScale;
              await wait(resetDelayMs);
              await autoReset();
              const elapsed = performance.now() - start;
              if (elapsed < minReadyMs) {
                await wait(minReadyMs - elapsed);
              }
              this.ensureCorridorReady();
              this.ensureVertiportReady();
              if (this.ensureBaseStationReady) {
                this.ensureBaseStationReady();
              }
              scheduleLinkUpdates();
              this.setLoadingReady();
              return;
            }
          }

          try {
            if (this.pendingCorridorRows) {
              const rows = this.pendingCorridorRows;
              this.pendingCorridorRows = null;
              this.updateCorridorOverlayFromRows(rows);
            } else {
              await this.loadCorridorOverlay();
            }
            if (this.pendingVertiportRows) {
              const rows = this.pendingVertiportRows;
              this.pendingVertiportRows = null;
              this.updateVertiportOverlayFromRows(rows);
            } else {
              await this.loadVertiportOverlay();
            }
            if (this.pendingBaseStationRows) {
              const rows = this.pendingBaseStationRows;
              this.pendingBaseStationRows = null;
              this.updateBaseStationOverlayFromRows(rows);
            } else if (this.loadBaseStationOverlay) {
              await this.loadBaseStationOverlay();
            }
          } catch (error) {
            console.warn("Auto reset fallback failed.", error);
          }
          this.ensureCorridorReady();
          this.ensureVertiportReady();
          if (this.ensureBaseStationReady) {
            this.ensureBaseStationReady();
          }
          scheduleLinkUpdates();
          this.setLoadingReady();
        };

        if (this.config.bounds) {
          map.fitBounds(this.config.bounds, { padding: 20, duration: 0 });
          map.once("idle", () => {
            this.captureHomeView();
            void runAfterIdle();
          });
        } else {
          this.captureHomeView();
          map.once("idle", () => {
            void runAfterIdle();
          });
        }
      });
      return map;
    }

    scheduleMapWarmup() {
      if (this.mapWarmupScheduled || this.mapWarmupStarted || this.mapWarmupCompleted) {
        return;
      }
      const perf = (this.config && this.config.perf) || {};
      const prefetch = perf.prefetch || {};
      if (!prefetch.enabled || typeof fetch !== "function") {
        return;
      }
      this.mapWarmupScheduled = true;
      const delayMs = Number.isFinite(prefetch.delayMs) ? Number(prefetch.delayMs) : 1200;
      const run = () => {
        if (this.mapWarmupStarted || this.mapWarmupCompleted) {
          return;
        }
        this.mapWarmupScheduled = false;
        this.mapWarmupStarted = true;
        void this.runMapWarmup();
      };
      if (typeof window !== "undefined" && typeof window.requestIdleCallback === "function") {
        window.setTimeout(() => {
          window.requestIdleCallback(run, { timeout: Math.max(500, delayMs) });
        }, Math.max(0, delayMs));
        return;
      }
      window.setTimeout(run, Math.max(0, delayMs));
    }

    _normalizeZoomList(values) {
      if (!Array.isArray(values)) {
        return [];
      }
      const seen = new Set();
      const out = [];
      for (const raw of values) {
        const zoom = Math.round(Number(raw));
        if (!Number.isFinite(zoom) || seen.has(zoom)) {
          continue;
        }
        seen.add(zoom);
        out.push(zoom);
      }
      out.sort((a, b) => a - b);
      return out;
    }

    _tileUrl(template, z, x, y) {
      if (typeof template !== "string" || !template) {
        return "";
      }
      return template
        .replace("{z}", String(z))
        .replace("{x}", String(x))
        .replace("{y}", String(y));
    }

    _tileRangeFromBounds(bounds, z) {
      if (!Array.isArray(bounds) || bounds.length < 4) {
        return null;
      }
      const west = Number(bounds[0]);
      const south = Number(bounds[1]);
      const east = Number(bounds[2]);
      const north = Number(bounds[3]);
      if (
        !Number.isFinite(west) ||
        !Number.isFinite(south) ||
        !Number.isFinite(east) ||
        !Number.isFinite(north)
      ) {
        return null;
      }
      const n = Math.pow(2, z);
      if (!Number.isFinite(n) || n <= 0) {
        return null;
      }
      const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
      const normLon = (lon) => {
        let out = Number(lon);
        while (out < -180) out += 360;
        while (out > 180) out -= 360;
        return out;
      };
      const lonToX = (lon) => {
        const normalized = normLon(lon);
        return clamp(Math.floor(((normalized + 180) / 360) * n), 0, n - 1);
      };
      const latToY = (lat) => {
        const limited = clamp(Number(lat), -85.05112878, 85.05112878);
        const rad = (limited * Math.PI) / 180;
        const merc = Math.log(Math.tan(Math.PI / 4 + rad / 2));
        return clamp(Math.floor(((1 - merc / Math.PI) / 2) * n), 0, n - 1);
      };
      const x1 = lonToX(west);
      const x2 = lonToX(east);
      const y1 = latToY(north);
      const y2 = latToY(south);
      return {
        xMin: Math.min(x1, x2),
        xMax: Math.max(x1, x2),
        yMin: Math.min(y1, y2),
        yMax: Math.max(y1, y2),
      };
    }

    _collectPrefetchFromBounds(template, bounds, zooms, limit, seen) {
      const out = [];
      const maxCount = Math.max(0, Math.floor(Number(limit) || 0));
      if (!template || !zooms.length || maxCount <= 0) {
        return out;
      }
      const dedupe = seen || new Set();
      for (const z of zooms) {
        if (out.length >= maxCount) {
          break;
        }
        const range = this._tileRangeFromBounds(bounds, z);
        if (!range) {
          continue;
        }
        for (let y = range.yMin; y <= range.yMax; y += 1) {
          if (out.length >= maxCount) {
            break;
          }
          for (let x = range.xMin; x <= range.xMax; x += 1) {
            if (out.length >= maxCount) {
              break;
            }
            const url = this._tileUrl(template, z, x, y);
            if (!url || dedupe.has(url)) {
              continue;
            }
            dedupe.add(url);
            out.push(url);
          }
        }
      }
      return out;
    }

    _collectPrefetchAroundCenter(template, center, zooms, radiusTiles, limit, seen) {
      if (!Array.isArray(center) || center.length < 2) {
        return [];
      }
      const lon = Number(center[0]);
      const lat = Number(center[1]);
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
        return [];
      }
      const zValues = this._normalizeZoomList(zooms);
      if (!zValues.length) {
        return [];
      }
      const radius = Math.max(0, Math.floor(Number(radiusTiles) || 0));
      const extent = 360 / Math.pow(2, Math.max(0, zValues[zValues.length - 1]));
      const latSpan = Math.max(0.01, extent * (radius + 1.5));
      const lonSpan = Math.max(0.01, extent * (radius + 1.5));
      const bounds = [lon - lonSpan, lat - latSpan, lon + lonSpan, lat + latSpan];
      return this._collectPrefetchFromBounds(template, bounds, zValues, limit, seen);
    }

    async _prefetchUrls(urls, concurrency) {
      const queue = Array.isArray(urls) ? urls.filter(Boolean) : [];
      if (!queue.length || typeof fetch !== "function") {
        return;
      }
      const workerCount = Math.max(1, Math.min(8, Math.floor(Number(concurrency) || 4)));
      let nextIndex = 0;
      const fetchOne = async () => {
        while (nextIndex < queue.length) {
          const index = nextIndex;
          nextIndex += 1;
          const url = queue[index];
          try {
            await fetch(url, { cache: "force-cache", credentials: "same-origin" });
          } catch (_err) {
            // Ignore warmup fetch failures.
          }
        }
      };
      await Promise.all(Array.from({ length: workerCount }, () => fetchOne()));
    }

    async runMapWarmup() {
      try {
        const perf = (this.config && this.config.perf) || {};
        const prefetch = perf.prefetch || {};
        if (!prefetch.enabled) {
          this.mapWarmupCompleted = true;
          return;
        }
        const maxTiles = Math.max(0, Math.floor(Number(prefetch.maxTiles) || 0));
        if (maxTiles <= 0) {
          this.mapWarmupCompleted = true;
          return;
        }
        const vectorBudget = Math.max(0, Math.floor(maxTiles * 0.7));
        const demBudget = Math.max(0, maxTiles - vectorBudget);
        const seen = new Set();
        const queue = [];

        const center = Array.isArray(this.config.center) ? this.config.center.slice(0, 2) : null;
        const centerZooms = this._normalizeZoomList(prefetch.centerZooms);
        const radiusTiles = Math.max(0, Math.floor(Number(prefetch.centerRadiusTiles) || 0));

        const vectorZooms = this._normalizeZoomList(prefetch.vectorZooms);
        const demZooms = this._normalizeZoomList(prefetch.demZooms);
        const seoulBounds = Array.isArray(prefetch.seoulBounds) ? prefetch.seoulBounds : null;

        const vectorTemplate = String(this.config.tileUrl || "");
        const demTemplate = this.config.dem ? String(this.config.dem.tileUrl || "") : "";

        if (vectorTemplate && vectorBudget > 0) {
          const centerTiles = this._collectPrefetchAroundCenter(
            vectorTemplate,
            center,
            centerZooms,
            radiusTiles,
            Math.floor(vectorBudget * 0.35),
            seen,
          );
          queue.push(...centerTiles);
          const remain = Math.max(0, vectorBudget - centerTiles.length);
          if (remain > 0) {
            queue.push(
              ...this._collectPrefetchFromBounds(vectorTemplate, seoulBounds, vectorZooms, remain, seen),
            );
          }
        }

        if (demTemplate && demBudget > 0) {
          const centerTiles = this._collectPrefetchAroundCenter(
            demTemplate,
            center,
            centerZooms,
            radiusTiles,
            Math.floor(demBudget * 0.35),
            seen,
          );
          queue.push(...centerTiles);
          const remain = Math.max(0, demBudget - centerTiles.length);
          if (remain > 0) {
            queue.push(
              ...this._collectPrefetchFromBounds(demTemplate, seoulBounds, demZooms, remain, seen),
            );
          }
        }

        if (queue.length) {
          await this._prefetchUrls(queue, prefetch.concurrency);
        }
      } finally {
        this.mapWarmupCompleted = true;
      }
    }

    syncOverlayPitchLock() {
      if (!this.map) {
        return;
      }
      const shouldLock = Boolean(this.noiseEnabled || this.transmissionEnabled);
      if (shouldLock) {
        if (this.overlayPitchLocked) {
          return;
        }
        this.overlayPitchLocked = true;
        const map = this.map;
        const getNum = (value, fallback) =>
          Number.isFinite(value) ? Number(value) : fallback;
        this.overlayPitchState = {
          pitch: map.getPitch ? getNum(map.getPitch(), 0) : 0,
          bearing: map.getBearing ? getNum(map.getBearing(), 0) : 0,
          maxPitch: map.getMaxPitch
            ? getNum(map.getMaxPitch(), this.config.view.maxPitch)
            : this.config.view.maxPitch,
          dragRotateEnabled:
            map.dragRotate && typeof map.dragRotate.isEnabled === "function"
              ? map.dragRotate.isEnabled()
              : null,
          touchRotateEnabled:
            map.touchZoomRotate && typeof map.touchZoomRotate.isRotationEnabled === "function"
              ? map.touchZoomRotate.isRotationEnabled()
              : map.touchZoomRotate && typeof map.touchZoomRotate.isEnabled === "function"
                ? map.touchZoomRotate.isEnabled()
                : null,
        };
        if (typeof map.setMaxPitch === "function") {
          map.setMaxPitch(0);
        }
        if (typeof map.setPitch === "function") {
          map.setPitch(0);
        }
        if (typeof map.setBearing === "function") {
          map.setBearing(0);
        }
        if (map.dragRotate) {
          map.dragRotate.disable();
        }
        if (map.touchZoomRotate && typeof map.touchZoomRotate.disableRotation === "function") {
          map.touchZoomRotate.disableRotation();
        }
        return;
      }
      if (!this.overlayPitchLocked) {
        return;
      }
      const map = this.map;
      const prev = this.overlayPitchState;
      this.overlayPitchLocked = false;
      this.overlayPitchState = null;
      if (prev && typeof map.setMaxPitch === "function" && Number.isFinite(prev.maxPitch)) {
        map.setMaxPitch(prev.maxPitch);
      }
      if (prev && typeof map.setPitch === "function" && Number.isFinite(prev.pitch)) {
        map.setPitch(prev.pitch);
      }
      if (prev && typeof map.setBearing === "function" && Number.isFinite(prev.bearing)) {
        map.setBearing(prev.bearing);
      }
      if (map.dragRotate) {
        if (prev && prev.dragRotateEnabled === false) {
          map.dragRotate.disable();
        } else {
          map.dragRotate.enable();
        }
      }
    if (map.touchZoomRotate) {
      if (prev && prev.touchRotateEnabled === false) {
        if (typeof map.touchZoomRotate.disableRotation === "function") {
          map.touchZoomRotate.disableRotation();
        }
        } else if (typeof map.touchZoomRotate.enableRotation === "function") {
          map.touchZoomRotate.enableRotation();
      }
    }
  }

  _focusWithoutScroll(element) {
    if (!element || typeof element.focus !== "function") {
      return false;
    }
    try {
      element.focus({ preventScroll: true });
      return true;
    } catch (_error) {}
    try {
      element.focus();
      return true;
    } catch (_error) {}
    return false;
  }

  _moveFocusOutside(container) {
    if (!container) {
      return;
    }
    const active = document.activeElement;
    if (!active || active === document.body || !container.contains(active)) {
      return;
    }
    if (typeof active.blur === "function") {
      active.blur();
    }
    const candidates = [];
    if (this.map && typeof this.map.getCanvas === "function") {
      const canvas = this.map.getCanvas();
      if (canvas) {
        if (!canvas.hasAttribute("tabindex")) {
          canvas.setAttribute("tabindex", "0");
        }
        candidates.push(canvas);
      }
    }
    if (this.appRoot) {
      if (!this.appRoot.hasAttribute("tabindex")) {
        this.appRoot.setAttribute("tabindex", "-1");
      }
      candidates.push(this.appRoot);
    }
    candidates.push(document.body);
    for (const target of candidates) {
      if (target && target !== active && this._focusWithoutScroll(target)) {
        return;
      }
    }
  }

  _setHiddenState(element, hidden) {
    if (!element) {
      return;
    }
    if (hidden) {
      this._moveFocusOutside(element);
      element.classList.add("is-hidden");
      element.setAttribute("aria-hidden", "true");
      if ("inert" in element) {
        element.inert = true;
      } else {
        element.setAttribute("inert", "");
      }
      return;
    }
    if ("inert" in element) {
      element.inert = false;
    } else {
      element.removeAttribute("inert");
    }
    element.classList.remove("is-hidden");
    element.setAttribute("aria-hidden", "false");
  }

  initStartScreen() {
    if (!this.startScreen || this.startScreenInitialized) {
      return;
    }
    this.startScreenInitialized = true;
    this._setHiddenState(this.startScreen, false);
    this.loadStartNotes();
      this.startScreenPointerHandler = (event) => {
        if (event && event.preventDefault) {
          event.preventDefault();
        }
        if (event && event.stopPropagation) {
          event.stopPropagation();
        }
        this.dismissStartScreen();
      };
      if (this.startScreenTrigger) {
        this.startScreenTrigger.addEventListener("click", this.startScreenPointerHandler);
      }
    }

    loadStartNotes() {
      if (!this.startScreenNotes || !this.startScreenNotesBody) {
        return;
      }
      const base = (this.config && this.config.notesBase) || "";
      if (!base) {
        return;
      }
      const currentLang = this.language || (window.AppI18n ? window.AppI18n.getLang() : "en");
      const suffix = String(currentLang).startsWith("ko") ? "_ko" : "_en";
      const url = `${base}${suffix}.txt`;
      if (this.startScreenNotesUrl === url && this.startScreenNotesLoaded) {
        return;
      }
      this.startScreenNotesUrl = url;
      this.startScreenNotesLoaded = false;
      fetch(url, { cache: "no-store" })
        .then((response) => {
          if (!response.ok) {
            throw new Error(`notes ${response.status}`);
          }
          return response.text();
        })
        .then((text) => {
          const value = String(text || "").trim();
          this.startScreenNotesBody.textContent = value || "";
          this.startScreenNotesLoaded = true;
        })
        .catch(() => {
          this.startScreenNotesLoaded = false;
          this.startScreenNotesBody.textContent = this.translateLiteral(
            "Release notes unavailable.",
          );
        });
    }

    async dismissStartScreen() {
      if (!this.startScreen || this.startScreenDismissed) {
        return;
      }
      this.startScreenDismissed = true;
      if (this.startScreenPointerHandler) {
        if (this.startScreenTrigger) {
          this.startScreenTrigger.removeEventListener("click", this.startScreenPointerHandler);
        }
        this.startScreenPointerHandler = null;
      }
      this.beginStartLoading(2000);
    if (this.appRoot) {
      this.appRoot.classList.add("is-booting");
    }
    await new Promise((resolve) => requestAnimationFrame(() => resolve()));
    this._setHiddenState(this.startScreen, true);
    if (this.map) {
      requestAnimationFrame(() => this.map.resize());
    }
      await this.runStartResetSequence();
      if (this.appRoot) {
        this.appRoot.classList.remove("is-booting");
      }
      if (this.loadBaseStationOverlay && this.map) {
        // JY - Base station default spawn: ensure base station overlay loads after start screen.
        const reload = () => {
          const count = this.baseStationPointLookup
            ? this.baseStationPointLookup.size
            : 0;
          if (count > 0) {
            return;
          }
          void this.loadBaseStationOverlay(this.config.data.basestationCsv, true);
        };
        if (this.map.isStyleLoaded && this.map.isStyleLoaded()) {
          reload();
        } else if (this.map.once) {
          this.map.once("idle", reload);
        }
      }
    }

    resetStartScreen() {
      if (!this.startScreen) {
        return;
    }
    this.startScreenInitialized = true;
    this.startScreenDismissed = false;
    this._setHiddenState(this.startScreen, false);
    this.loadStartNotes();
      this.tutorialShown = false;
      this.tutorialDismissed = false;
      this.hideTutorialOverlay();
      if (this.startScreenPointerHandler && this.startScreenTrigger) {
        this.startScreenTrigger.removeEventListener("click", this.startScreenPointerHandler);
      }
      this.startScreenPointerHandler = (event) => {
        if (event && event.preventDefault) {
          event.preventDefault();
        }
        if (event && event.stopPropagation) {
          event.stopPropagation();
        }
        this.dismissStartScreen();
      };
      if (this.startScreenTrigger) {
        this.startScreenTrigger.addEventListener("click", this.startScreenPointerHandler);
      }
      if (this.map) {
        requestAnimationFrame(() => this.map.resize());
      }
    }

    initTutorialOverlay() {
      if (!this.tutorialOverlay) {
        return;
      }
      if (!this.tutorialAutoDismissHandler) {
        this.tutorialAutoDismissHandler = (event) => {
          if (!this.tutorialOverlay || !this.tutorialShown) {
            return;
          }
          if (!this.startScreenDismissed || this.tutorialMode === "guided") {
            return;
          }
          const target = event && event.target ? event.target : null;
          if (!target) {
            return;
          }
          if (this.tutorialOverlay.contains(target)) {
            return;
          }
          if (!target.closest("button, [role='button']")) {
            return;
          }
          this.dismissTutorialOverlay();
        };
        document.addEventListener("click", this.tutorialAutoDismissHandler, true);
      }
      if (this.tutorialClose) {
        this.tutorialClose.addEventListener("click", (event) => {
          if (event && event.preventDefault) {
            event.preventDefault();
          }
          if (event && event.stopPropagation) {
            event.stopPropagation();
          }
          this.dismissTutorialOverlay();
        });
      }
      if (this.tutorialOpen) {
        this.tutorialOpen.addEventListener("click", (event) => {
          if (event && event.preventDefault) {
            event.preventDefault();
          }
          if (event && event.stopPropagation) {
            event.stopPropagation();
          }
          this.startGuidedTutorial();
        });
      }
      if (this.tutorialStepConfirm) {
        this.tutorialStepConfirm.addEventListener("click", (event) => {
          if (event && event.preventDefault) {
            event.preventDefault();
          }
          if (event && event.stopPropagation) {
            event.stopPropagation();
          }
          this.handleTutorialConfirm();
        });
      }
      if (!this.tutorialResizeHandler) {
        this.tutorialResizeHandler = () => {
          if (!this.tutorialOverlay || this.tutorialOverlay.classList.contains("is-hidden")) {
            return;
          }
          this.positionTutorialCallouts();
          this.positionTutorialStepPanel();
        };
      }
      this.hideTutorialOverlay();
    }

    positionTutorialCallouts() {
      if (!this.tutorialOverlay || !Array.isArray(this.tutorialCallouts)) {
        return;
      }
      const overlayRect = this.tutorialOverlay.getBoundingClientRect();
      this.tutorialCallouts.forEach((callout) => {
        const selector = callout.dataset.target;
        if (!selector) {
          callout.style.opacity = "0";
          return;
        }
        const target = document.querySelector(selector);
        if (!target) {
          callout.style.opacity = "0";
          return;
        }
        const rect = target.getBoundingClientRect();
        const align = callout.dataset.align || "right";
        let x = rect.right;
        let y = rect.top + rect.height / 2;
        if (align === "left") {
          x = rect.left;
        } else if (align === "top") {
          x = rect.left + rect.width / 2;
          y = rect.top;
        } else if (align === "bottom") {
          x = rect.left + rect.width / 2;
          y = rect.bottom;
        }
        callout.style.left = `${x - overlayRect.left}px`;
        callout.style.top = `${y - overlayRect.top}px`;
        callout.style.opacity = "1";
      });
    }

  showTutorialOverlay() {
    if (!this.tutorialOverlay) {
      return;
    }
    this._setHiddenState(this.tutorialOverlay, false);
    this.tutorialShown = true;
      if (!this.tutorialMode) {
        this.tutorialMode = "guide";
      }
      if (this.tutorialMode === "guided") {
        this.tutorialOverlay.classList.add("is-guided");
      } else {
        this.tutorialOverlay.classList.remove("is-guided");
      }
      if (this.tutorialResizeHandler) {
        window.addEventListener("resize", this.tutorialResizeHandler);
      }
      requestAnimationFrame(() => this.positionTutorialCallouts());
    }

  hideTutorialOverlay() {
    if (!this.tutorialOverlay) {
      return;
    }
    this.tutorialShown = false;
    this.clearTutorialHighlights();
    this.stopGuidedTutorial();
    this._setHiddenState(this.tutorialOverlay, true);
    if (this.tutorialResizeHandler) {
      window.removeEventListener("resize", this.tutorialResizeHandler);
    }
  }

    dismissTutorialOverlay() {
      this.tutorialDismissed = true;
      this.hideTutorialOverlay();
    }

    maybeShowTutorialOverlay() {
      if (!this.tutorialOverlay || this.tutorialShown || this.tutorialDismissed) {
        return;
      }
      if (this.startScreen && !this.startScreenDismissed) {
        return;
      }
      if (this.loadingScreen && !this.loadingScreen.classList.contains("is-hidden")) {
        return;
      }
      this.showTutorialOverlay();
    }

    getTutorialSteps() {
      if (this.tutorialSteps && this.tutorialSteps.length) {
        return this.tutorialSteps;
      }
      this.tutorialSteps = [
        {
          key: "settings",
          target: "#left-controls [data-action='settings']",
          title: {
            en: "Simulation Rules",
            ko: "시뮬레이션 규칙",
          },
          desc: {
            en:
              "Use this panel to set daily goals, aircraft speed and operating rules, and monitoring parameters.",
            ko:
              "해당 부분에서는 1일 운용 목표, 비행체의 속도 및 운항 규칙, 모니터링 Parameter를 설정할 수 있습니다.",
          },
          allow: ["#settings-panel"],
          requireClick: true,
        },
        {
          key: "autopilot",
          target: "#left-controls [data-action='autopilot']",
          title: {
            en: "Autopilot",
            ko: "오토파일럿",
          },
          desc: {
            en:
              "Design the aircraft's automatic collision avoidance logic here, and turn it on/off.",
            ko:
              "해당 부분에서는 비행체의 자동 충돌 회피 기능에 대해 설계할 수 있으며, 켜고 끌 수 있습니다.",
          },
          allow: ["#autopilot-panel"],
          requireClick: true,
        },
        {
          key: "corridor",
          target: "#left-controls [data-action='corridor']",
          title: {
            en: "Route Custom",
            ko: "경로 사용자 정의",
          },
          desc: {
            en:
              "You can configure vertiports, corridors (including spare corridors), and base stations. Left-click to place, right-click to delete, then Confirm. Corridors and vertiports must be linked to other nodes to activate.",
            ko:
              "경로에는 버티포트, 항로(임시회랑 포함), 기지국 등을 설정할 수 있는 모드가 있습니다. 좌클릭 -> 설정, 우클릭 -> 삭제를 통해 원하는 위치에 Node를 설정하고 Confirm 을 통해 확정하세요, 항로 및 버티포트의 경우 다른 Node와 Link를 연결해야 작동합니다.",
          },
          allow: ["#corridor-panel"],
          requireClick: true,
        },
        {
          key: "scenario",
          target: "#left-controls [data-action='scenario']",
          title: {
            en: "Scenario",
            ko: "시나리오",
          },
          desc: {
            en:
              "Adjust wind strength here. Weather is enabled by default, and you can visualize it with the weather button on the right.",
            ko:
              "시나리오에서 바람을 조정하고, 우측 날씨 버튼으로 시각화하세요.",
          },
          allow: ["#scenario-panel", "[data-action='layer-weather']"],
          focusTargetWhenOpen: "[data-action='layer-weather']",
          requireClick: true,
        },
          {
            key: "playback",
            target: ".playback-btn-play",
            title: {
            en: "Playback Controls",
            ko: "재생 제어",
          },
          desc: {
            en:
              "Run the simulation based on your settings. Order: Play, Speed, Pause, Stop (reset), Full reset.",
            ko:
              "재생 제어를 통해 지금까지 설정된 내용을 바탕으로 시뮬레이션을 할 수 있습니다. 차례대로 재생, 배속, 일시정지, 정지(초기화), 완전 초기화 버튼입니다.",
          },
          substeps: [
            {
              prompt: {
                en: "Click Play to start the simulation.",
                ko: "재생을 눌러 시뮬레이션을 시작하세요.",
              },
              target: ".playback-btn-play",
              allow: [".playback-btn-play", "#playback-panel"],
            },
            {
              prompt: {
                en: "Open Speed and set it to x10.",
                ko: "배속을 열고 x10으로 설정하세요.",
              },
              target: ".playback-btn-fast",
              allow: [
                ".playback-btn-fast",
                "#playback-panel",
                "#playback-speed-menu .playback-speed-option[data-speed='10']",
              ],
            },
            ],
            requireClick: true,
          },
          {
            key: "sound",
            target: "#sound-toggle",
            title: {
              en: "Warning Sound",
              ko: "경고음",
            },
            desc: {
              en: "Toggle alert sounds on or off.",
              ko: "경고음을 켜거나 끌 수 있습니다.",
            },
            requireClick: true,
          },
          {
            key: "dashboard",
            target: "#dashboard-toggle",
            title: {
            en: "Traffic Status",
            ko: "운항 현황",
          },
          desc: {
            en:
              "Open Traffic Status to review flight info, risk messages, and intervention history (human + autopilot).",
            ko:
              "운항 현황에서는 다양한 운항 정보들을 한눈에 볼 수 있습니다. 위험 측정에 따른 경로 메시지, 또는 운항 간 조치한 사항들(인간 개입 및 오토파일럿 개입 정보) 등을 볼 수 있습니다.",
          },
          allow: ["#dashboard-panel"],
          requireClick: true,
        },
        {
          key: "finish",
          target: null,
          title: {
            en: "Ready",
            ko: "준비 완료",
          },
          desc: {
            en: "You're ready. Fly safely with KADA.",
            ko: "이제 준비되었습니다. KADA와 함께 안전한 비행되세요.",
          },
          requireClick: false,
        },
      ];
      return this.tutorialSteps;
    }

    getTutorialStepInfo() {
      const steps = this.getTutorialSteps();
      const step = steps[this.tutorialStepIndex];
      if (!step) {
        return null;
      }
      if (step.key !== "playback" || !step.substeps || !step.substeps.length) {
        return step;
      }
      const sub = step.substeps[Math.min(this.tutorialSubstep, step.substeps.length - 1)];
      return {
        ...step,
        target: sub.target || step.target,
        allow: sub.allow || [],
        prompt: sub.prompt,
      };
    }

    getTutorialStepText(step) {
      const lang = this.language || (window.AppI18n ? window.AppI18n.getLang() : "en");
      const isKo = String(lang).startsWith("ko");
      const title = step.title ? (isKo ? step.title.ko : step.title.en) : "";
      let desc = step.desc ? (isKo ? step.desc.ko : step.desc.en) : "";
      const panelSelectors = Array.isArray(step.allow)
        ? step.allow.filter((selector) => /-panel\b/.test(selector))
        : [];
      if (panelSelectors.length) {
        const isPanelVisible = panelSelectors.some((selector) => this.isTutorialPanelVisible(selector));
        if (!isPanelVisible) {
          desc = "";
        }
      }
      if (step.key === "playback" && step.prompt) {
        const prompt = isKo ? step.prompt.ko : step.prompt.en;
        const combined = desc ? `${desc}\n\n${prompt}` : prompt;
        return { title, desc: combined };
      }
      return { title, desc };
    }

    isTutorialPanelVisible(selector) {
      if (!selector) {
        return false;
      }
      const panel = document.querySelector(selector);
      if (!panel) {
        return false;
      }
      const aria = panel.getAttribute("aria-hidden");
      return (
        panel.classList.contains("is-visible") ||
        panel.classList.contains("is-open") ||
        aria === "false"
      );
    }

    getTutorialTargetRect(step) {
      if (!step) {
        this.tutorialTargetRect = null;
        return null;
      }
      const preferTarget = step.key === "playback";
      const panelSelectors = Array.isArray(step.allow)
        ? step.allow.filter((selector) => /-panel\b/.test(selector))
        : [];
      const panelVisible = panelSelectors.some((selector) => this.isTutorialPanelVisible(selector));

      if (!preferTarget && panelVisible && step.focusTargetWhenOpen) {
        const focusTarget = document.querySelector(step.focusTargetWhenOpen);
        if (focusTarget && typeof focusTarget.getBoundingClientRect === "function") {
          const rect = focusTarget.getBoundingClientRect();
          if (rect && Number.isFinite(rect.width) && Number.isFinite(rect.height)) {
            this.tutorialTargetRect = rect;
            return rect;
          }
        }
      }

      if (!preferTarget && panelVisible) {
        for (const selector of panelSelectors) {
          if (!selector || !this.isTutorialPanelVisible(selector)) {
            continue;
          }
          const panel = document.querySelector(selector);
          if (!panel || typeof panel.getBoundingClientRect !== "function") {
            continue;
          }
          const rect = panel.getBoundingClientRect();
          if (rect && Number.isFinite(rect.width) && Number.isFinite(rect.height)) {
            this.tutorialTargetRect = rect;
            return rect;
          }
        }
      }
      if (!step.target) {
        this.tutorialTargetRect = null;
        return null;
      }
      const target = document.querySelector(step.target);
      if (!target || typeof target.getBoundingClientRect !== "function") {
        this.tutorialTargetRect = null;
        return null;
      }
      const rect = target.getBoundingClientRect();
      if (!rect || !Number.isFinite(rect.width) || !Number.isFinite(rect.height)) {
        this.tutorialTargetRect = null;
        return null;
      }
      this.tutorialTargetRect = rect;
      return rect;
    }

    updateTutorialSpotlight(step, targetRect) {
      if (!this.tutorialOverlay) {
        return;
      }
      const overlayRect = this.tutorialOverlay.getBoundingClientRect();
      if (!overlayRect || overlayRect.width <= 0 || overlayRect.height <= 0) {
        return;
      }
      const hasTarget = Boolean(step && targetRect);
      const dimValue = hasTarget ? (this.tutorialMode === "guided" ? 0.16 : 0.12) : 0.1;
      this.tutorialOverlay.style.setProperty("--tutorial-dim", `${dimValue}`);
      if (!step || !targetRect) {
        this.tutorialOverlay.style.setProperty("--tutorial-hole-size", "0px");
        this.tutorialOverlay.style.setProperty("--tutorial-hole-x", "50%");
        this.tutorialOverlay.style.setProperty("--tutorial-hole-y", "50%");
        return;
      }
      const centerX = targetRect.left + targetRect.width * 0.5;
      const centerY = targetRect.top + targetRect.height * 0.5;
      const localX = centerX - overlayRect.left;
      const localY = centerY - overlayRect.top;
      const pad = 28;
      const radius = Math.max(targetRect.width, targetRect.height) * 0.6 + pad;
      const safeRadius = Math.max(36, Math.round(radius));
      this.tutorialOverlay.style.setProperty("--tutorial-hole-x", `${Math.round(localX)}px`);
      this.tutorialOverlay.style.setProperty("--tutorial-hole-y", `${Math.round(localY)}px`);
      this.tutorialOverlay.style.setProperty("--tutorial-hole-size", `${safeRadius}px`);
    }

    refreshTutorialLayout() {
      if (this.tutorialMode !== "guided") {
        return;
      }
      window.requestAnimationFrame(() => this.renderTutorialStep());
    }

    startGuidedTutorial() {
      if (!this.tutorialOverlay) {
        return;
      }
      this.tutorialMode = "guided";
      this.tutorialStepIndex = 0;
      this.tutorialSubstep = 0;
      this.tutorialStepHits = [];
      this.tutorialDismissed = false;
      this.showTutorialOverlay();
      this.tutorialOverlay.classList.add("is-guided");
      if (this.tutorialStepPanel) {
        this.tutorialStepPanel.classList.remove("is-hidden");
      }
      if (!this.tutorialClickHandler) {
        this.tutorialClickHandler = (event) => {
          this.handleTutorialClick(event);
        };
      }
      document.addEventListener("click", this.tutorialClickHandler, true);
      this.renderTutorialStep();
    }

    stopGuidedTutorial() {
      if (!this.tutorialOverlay) {
        return;
      }
      if (this.tutorialClickHandler) {
        document.removeEventListener("click", this.tutorialClickHandler, true);
      }
      this.tutorialMode = "guide";
      this.tutorialStepIndex = 0;
      this.tutorialSubstep = 0;
      this.tutorialStepHits = [];
      this.clearTutorialHighlights();
      if (this.tutorialOverlay) {
        this.tutorialOverlay.classList.remove("is-guided");
        if (this.tutorialOverlay.style) {
          this.tutorialOverlay.style.setProperty("--tutorial-hole-size", "0px");
          this.tutorialOverlay.style.setProperty("--tutorial-hole-x", "50%");
          this.tutorialOverlay.style.setProperty("--tutorial-hole-y", "50%");
          this.tutorialOverlay.style.setProperty("--tutorial-dim", "0.1");
        }
      }
      if (this.tutorialStepPanel) {
        this.tutorialStepPanel.classList.add("is-hidden");
        this.tutorialStepPanel.classList.remove(
          "arrow-left",
          "arrow-right",
          "arrow-top",
          "arrow-bottom",
        );
        this.tutorialStepPanel.classList.add("arrow-none");
      }
      this.tutorialTargetRect = null;
    }

    handleTutorialConfirm() {
      if (!this.isTutorialConfirmReady()) {
        return;
      }
      const steps = this.getTutorialSteps();
      if (this.tutorialStepIndex >= steps.length - 1) {
        this.dismissTutorialOverlay();
        return;
      }
      this.tutorialStepIndex += 1;
      this.tutorialSubstep = 0;
      this.renderTutorialStep();
    }

    handleTutorialClick(event) {
      if (!this.tutorialOverlay || this.tutorialMode !== "guided") {
        return;
      }
      const target = event && event.target ? event.target : null;
      if (!target) {
        return;
      }
      if (
        (this.tutorialStepPanel && this.tutorialStepPanel.contains(target)) ||
        (this.tutorialClose && this.tutorialClose.contains(target)) ||
        (this.tutorialOpen && this.tutorialOpen.contains(target))
      ) {
        return;
      }
      if (!this.isTutorialAllowedTarget(target)) {
        if (event && event.preventDefault) {
          event.preventDefault();
        }
        if (event && event.stopPropagation) {
          event.stopPropagation();
        }
        return;
      }
      this.handleTutorialAction(target);
    }

    isTutorialAllowedTarget(target) {
      const step = this.getTutorialStepInfo();
      if (!step) {
        return false;
      }
      const selectors = [];
      if (step.target) {
        selectors.push(step.target);
      }
      if (Array.isArray(step.allow)) {
        selectors.push(...step.allow);
      }
      for (const selector of selectors) {
        if (selector && target.closest(selector)) {
          return true;
        }
      }
      return false;
    }

    handleTutorialAction(target) {
      const step = this.getTutorialStepInfo();
      if (!step) {
        return;
      }
      const stepIndex = this.tutorialStepIndex;
      if (step.key === "playback") {
        if (this.tutorialSubstep === 0 && target.closest(".playback-btn-play")) {
          this.tutorialSubstep = 1;
          this.renderTutorialStep();
          return;
        }
        if (
          this.tutorialSubstep === 1 &&
          target.closest("#playback-speed-menu .playback-speed-option[data-speed='10']")
        ) {
          this.tutorialSubstep = 2;
          this.tutorialStepHits[stepIndex] = true;
          this.renderTutorialStep();
          return;
        }
      } else if (step.target && target.closest(step.target)) {
        this.tutorialStepHits[stepIndex] = true;
      }
      this.updateTutorialConfirmState();
      this.refreshTutorialLayout();
    }

    isTutorialConfirmReady() {
      const step = this.getTutorialStepInfo();
      if (!step) {
        return false;
      }
      if (step.key === "playback") {
        return this.tutorialSubstep >= 2;
      }
      if (step.requireClick) {
        return Boolean(this.tutorialStepHits[this.tutorialStepIndex]);
      }
      return true;
    }

    updateTutorialConfirmState() {
      if (!this.tutorialStepConfirm) {
        return;
      }
      this.tutorialStepConfirm.disabled = !this.isTutorialConfirmReady();
    }

    renderTutorialStep() {
      const step = this.getTutorialStepInfo();
      if (!step) {
        return;
      }
      if (step.key === "playback" && this.playbackPanel) {
        if (!this.playbackPanel.classList.contains("is-open")) {
          this.togglePlaybackPanel();
        }
        if (this.tutorialSubstep >= 1) {
          this.setSpeedMenuOpen(true);
        }
      }
      const targetRect = this.getTutorialTargetRect(step);
      const stepNumber = this.tutorialStepIndex + 1;
      const total = this.getTutorialSteps().length;
      const lang = this.language || (window.AppI18n ? window.AppI18n.getLang() : "en");
      const titleText = String(lang).startsWith("ko")
        ? `${stepNumber}/${total} 단계`
        : `Step ${stepNumber}/${total}`;
      if (this.tutorialStepTitle) {
        this.tutorialStepTitle.textContent = titleText;
      }
      const text = this.getTutorialStepText(step);
      if (this.tutorialStepLabel) {
        this.tutorialStepLabel.textContent = text.title || "";
      }
      if (this.tutorialStepDesc) {
        this.tutorialStepDesc.textContent = text.desc || "";
      }
      if (this.tutorialStepConfirm) {
        this.tutorialStepConfirm.textContent = this.translateLiteral("Confirm");
      }
      if (this.tutorialOverlay) {
        this.tutorialOverlay.classList.add("is-guided");
      }
      if (this.tutorialStepPanel) {
        this.tutorialStepPanel.classList.remove("is-hidden");
      }
      this.setTutorialHighlight(step);
      this.updateTutorialSpotlight(step, targetRect);
      this.updateTutorialConfirmState();
      requestAnimationFrame(() => this.positionTutorialStepPanel(step, targetRect));
    }

    setTutorialHighlight(step) {
      const selectors = [];
      const allowList = step && Array.isArray(step.allow) ? step.allow : [];
      const panelSelectors = allowList.filter((selector) => /-panel\b/.test(selector));
      const panelVisible = panelSelectors.some((selector) => this.isTutorialPanelVisible(selector));
      const focusTarget = step && step.focusTargetWhenOpen ? step.focusTargetWhenOpen : null;
      const highlightAllowList = allowList.filter((selector) => {
        if (!selector) {
          return false;
        }
        if (!panelVisible && focusTarget && selector === focusTarget) {
          return false;
        }
        return true;
      });

      if (panelVisible && focusTarget) {
        selectors.push(focusTarget);
      } else if (step && step.target) {
        selectors.push(step.target);
      }
      selectors.push(...highlightAllowList);
      const elements = [];
      selectors.forEach((selector) => {
        if (!selector) {
          return;
        }
        if (/-panel\b/.test(selector)) {
          return;
        }
        const found = Array.from(document.querySelectorAll(selector));
        elements.push(...found);
      });
      this.clearTutorialHighlights();
      elements.forEach((element) => {
        if (element && element.classList) {
          element.classList.add("tutorial-highlight");
          if (typeof window !== "undefined" && window.getComputedStyle) {
            const computed = window.getComputedStyle(element);
            const radius = computed ? computed.borderRadius : "";
            if (radius) {
              element.style.setProperty("--tutorial-highlight-radius", radius);
            }
          }
          this.tutorialHighlighted.push(element);
        }
      });
    }

    clearTutorialHighlights() {
      if (!Array.isArray(this.tutorialHighlighted)) {
        this.tutorialHighlighted = [];
        return;
      }
      this.tutorialHighlighted.forEach((element) => {
        if (element && element.classList) {
          element.classList.remove("tutorial-highlight");
          if (element.style) {
            element.style.removeProperty("--tutorial-highlight-radius");
          }
        }
      });
      this.tutorialHighlighted = [];
    }

    positionTutorialStepPanel(stepArg = null, targetRectArg = null) {
      if (!this.tutorialStepPanel || this.tutorialStepPanel.classList.contains("is-hidden")) {
        return;
      }
      const step = stepArg || this.getTutorialStepInfo();
      if (!step) {
        return;
      }
      const overlayRect = this.tutorialOverlay
        ? this.tutorialOverlay.getBoundingClientRect()
        : null;
      if (!overlayRect) {
        return;
      }
      const scale =
        Number.parseFloat(
          getComputedStyle(document.documentElement).getPropertyValue("--ui-scale"),
        ) || 1;
      const margin = 16 * scale;
      const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
      const panelRect = this.tutorialStepPanel.getBoundingClientRect();
      const targetRect = targetRectArg || this.getTutorialTargetRect(step);
      const minLeft = overlayRect.left + margin;
      const maxLeft = overlayRect.right - panelRect.width - margin;
      const minTop = overlayRect.top + margin;
      const maxTop = overlayRect.bottom - panelRect.height - margin;


      let left = overlayRect.left + (overlayRect.width - panelRect.width) / 2;
      let top = overlayRect.top + (overlayRect.height - panelRect.height) / 2;
      const placement = step.panelPlacement || "";

      if (placement === "top-center") {
        const topMargin = Math.max(margin * 1.5, 64 * scale);
        left = overlayRect.left + (overlayRect.width - panelRect.width) / 2;
        top = overlayRect.top + topMargin;
      } else if (targetRect) {
        let preferTop = step.key === "playback" && this.tutorialSubstep >= 1;
        if (preferTop) {
          left = targetRect.left + targetRect.width * 0.5 - panelRect.width * 0.5;
          top = targetRect.top - panelRect.height - margin;
          if (top < minTop) {
            preferTop = false;
          }
        }
        if (!preferTop) {
          left = targetRect.right + margin;
          top = targetRect.top + targetRect.height * 0.5 - panelRect.height * 0.5;
          if (left + panelRect.width > overlayRect.right - margin) {
            left = targetRect.left - panelRect.width - margin;
          }
        }
                left = clamp(left, minLeft, Math.max(minLeft, maxLeft));
        top = clamp(top, minTop, Math.max(minTop, maxTop));
      }
      // For playback, anchor above the playback controls so nothing is covered.
      if (
        step.key === "playback" &&
        this.playbackPanel &&
        this.playbackPanel.classList.contains("is-open")
      ) {
        const avoidRect = this.playbackPanel.getBoundingClientRect();
        const anchorRect = targetRect || avoidRect;
        const liftMultiplier = this.tutorialSubstep >= 1 ? 5 : 2;
        const desiredTop = avoidRect.top - panelRect.height - margin * liftMultiplier;
        top = clamp(desiredTop, minTop, Math.max(minTop, maxTop));
        const centeredLeft = anchorRect.left + anchorRect.width * 0.5 - panelRect.width * 0.5;
        left = clamp(centeredLeft, minLeft, Math.max(minLeft, maxLeft));
      }

      this.tutorialStepPanel.style.left = `${left - overlayRect.left}px`;
      this.tutorialStepPanel.style.top = `${top - overlayRect.top}px`;

      this.updateTutorialSpotlight(step, targetRect);
      this.updateTutorialArrow(step, targetRect, {
        left,
        top,
        width: panelRect.width,
        height: panelRect.height,
        margin,
      });
    }

    updateTutorialArrow(step, targetRect, panelBox) {
      if (!this.tutorialStepPanel) {
        return;
      }
      const panel = this.tutorialStepPanel;
      panel.classList.remove("arrow-left", "arrow-right", "arrow-top", "arrow-bottom", "arrow-none");
      if (!step || !targetRect || !panelBox) {
        panel.classList.add("arrow-none");
        return;
      }
      const targetCenterX = targetRect.left + targetRect.width * 0.5;
      const targetCenterY = targetRect.top + targetRect.height * 0.5;
      const panelCenterX = panelBox.left + panelBox.width * 0.5;
      const panelCenterY = panelBox.top + panelBox.height * 0.5;
      const dx = panelCenterX - targetCenterX;
      const dy = panelCenterY - targetCenterY;
      const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
      const placement = step.panelPlacement || "";

      if (placement === "top-center") {
        const arrowX = clamp(
          targetCenterX - panelBox.left,
          panelBox.margin,
          panelBox.width - panelBox.margin,
        );
        panel.style.setProperty("--tutorial-arrow-x", `${Math.round(arrowX)}px`);
        panel.classList.add("arrow-bottom");
        return;
      }

      if (Math.abs(dx) >= Math.abs(dy)) {
        const arrowY = clamp(
          targetCenterY - panelBox.top,
          panelBox.margin,
          panelBox.height - panelBox.margin,
        );
        panel.style.setProperty("--tutorial-arrow-y", `${Math.round(arrowY)}px`);
        panel.classList.add(dx > 0 ? "arrow-left" : "arrow-right");
      } else {
        const arrowX = clamp(
          targetCenterX - panelBox.left,
          panelBox.margin,
          panelBox.width - panelBox.margin,
        );
        panel.style.setProperty("--tutorial-arrow-x", `${Math.round(arrowX)}px`);
        panel.classList.add(dy > 0 ? "arrow-top" : "arrow-bottom");
      }
    }

    runStartResetSequence() {
      if (this.startResetPromise) {
        return this.startResetPromise;
      }
      const wait = (ms) =>
        new Promise((resolve) => window.setTimeout(resolve, Math.max(0, ms)));
      this.startResetPromise = (async () => {
        const start = performance.now();
        if (this.map && this.map.isStyleLoaded && !this.map.isStyleLoaded()) {
          await new Promise((resolve) => this.map.once("idle", resolve));
        }
        try {
          await this.resetDatafilesToDefault();
        } catch (error) {
          console.warn("Start reset failed.", error);
        }
        await wait(1000);
        try {
          await this.resetDatafilesToDefault();
        } catch (error) {
          console.warn("Start reset retry failed.", error);
        }
        const elapsed = performance.now() - start;
        if (elapsed < 2000) {
          await wait(2000 - elapsed);
        }
        this.didInitialDataReset = true;
        this.setLoadingReady();
      })().finally(() => {
        this.startResetPromise = null;
      });
      return this.startResetPromise;
    }

    initLoadingScreen() {
      if (!this.loadingScreen) {
        return;
      }
      if (this.startScreen && !this.startScreenDismissed) {
        this.loadingScreen.classList.add("is-hidden");
        this.loadingScreen.setAttribute("aria-busy", "false");
        this.loadingStartMs = null;
        this.loadingReady = false;
        return;
      }
      this.loadingScreen.classList.remove("is-hidden");
      this.loadingScreen.setAttribute("aria-busy", "true");
      this.loadingStartMs = performance.now();
      this.loadingReady = false;
    }

    beginStartLoading(minDelayMs = 2000) {
      if (!this.loadingScreen) {
        return;
      }
      if (this.loadingHideTimer) {
        clearTimeout(this.loadingHideTimer);
        this.loadingHideTimer = null;
      }
      this.loadingMinDelayMs = Math.max(0, minDelayMs);
      this.loadingStartMs = performance.now();
      this.loadingReady = false;
      this.loadingScreen.classList.remove("is-hidden");
      this.loadingScreen.setAttribute("aria-busy", "true");
    }

    setLoadingReady() {
      if (!this.loadingScreen) {
        return;
      }
      this.loadingReady = true;
      this.tryHideLoadingScreen();
    }

    tryHideLoadingScreen() {
      if (!this.loadingScreen || !this.loadingReady || this.loadingStartMs == null) {
        return;
      }
      const elapsed = performance.now() - this.loadingStartMs;
      const remaining = this.loadingMinDelayMs - elapsed;
      if (remaining > 0) {
        if (this.loadingHideTimer) {
          clearTimeout(this.loadingHideTimer);
        }
        this.loadingHideTimer = window.setTimeout(() => {
          this.loadingHideTimer = null;
          this.tryHideLoadingScreen();
        }, remaining);
        return;
      }
      this.loadingScreen.classList.add("is-hidden");
      this.loadingScreen.setAttribute("aria-busy", "false");
      this.maybeShowTutorialOverlay();
    }

    initStatusLog() {
      if (!this.statusLog) {
        return;
      }
      if (!this.statusLogList) {
        const list = document.createElement("div");
        list.className = "status-log-list";
        this.statusLog.appendChild(list);
        this.statusLogList = list;
      }
      this.renderStatusLog();
    }

    clearStatusLog() {
      this.statusMessages = [];
      this.statusPinned.clear();
      if (this.statusCleanupTimer) {
        clearTimeout(this.statusCleanupTimer);
        this.statusCleanupTimer = null;
      }
      this.renderStatusLog();
    }

    setStatusHint(text) {
      if (!this.statusLog) {
        return;
      }
      const rawText = text ? String(text).trim() : "";
      if (!rawText) {
        this.statusPinned.delete("hint");
      } else {
        const translated = this.translateStatusText(rawText);
        this.statusPinned.set("hint", { text: translated, rawText, level: "warn" });
      }
      this.renderStatusLog();
    }

    addStatusMessage(payload) {
      if (!this.statusLog) {
        return;
      }
      const message =
        typeof payload === "string" ? { text: payload } : payload && typeof payload === "object" ? payload : null;
      if (!message) {
        return;
      }
      const rawText = String(message.text || "").trim();
      const text = this.translateStatusText(rawText);
      const level = message.level || "info";
      const key = message.key || null;
      if (!text) {
        if (key) {
          this.statusPinned.delete(key);
          this.renderStatusLog();
        }
        return;
      }
      if (key) {
        this.statusPinned.set(key, { text, rawText, level });
        this.renderStatusLog();
        return;
      }
      const ttlMs = Number.isFinite(message.ttlMs)
        ? message.ttlMs
        : Number.isFinite(message.ttl)
          ? message.ttl
          : 6000;
      const entry = {
        id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
        text,
        rawText,
        level,
        expiresAt: ttlMs ? Date.now() + ttlMs : null,
      };
      this.statusMessages.push(entry);
      if (this.statusMessages.length > this.statusLogMaxEntries * 2) {
        this.statusMessages = this.statusMessages.slice(-this.statusLogMaxEntries * 2);
      }
      this.renderStatusLog();
      if (ttlMs) {
        this.scheduleStatusCleanup();
      }
    }

    renderStatusLog() {
      if (!this.statusLog || !this.statusLogList) {
        return;
      }
      const now = Date.now();
      this.statusMessages = this.statusMessages.filter(
        (entry) => !entry.expiresAt || entry.expiresAt > now,
      );
      const pinned = Array.from(this.statusPinned.values());
      const available = Math.max(0, this.statusLogMaxEntries - pinned.length);
      const recent = available > 0 ? this.statusMessages.slice(-available) : [];
      const combined = pinned.concat(recent);

      this.statusLogList.textContent = "";
      combined.forEach((entry) => {
        const line = document.createElement("div");
        line.className = `status-log-line is-${entry.level || "info"}`;
        const displayText = this.translateStatusText(entry.rawText || entry.text);
        line.textContent = displayText;
        this.statusLogList.appendChild(line);
      });

      if (combined.length) {
        this.statusLog.classList.add("is-visible");
      } else {
        this.statusLog.classList.remove("is-visible");
      }
    }

    scheduleStatusCleanup() {
      const now = Date.now();
      let nextExpiry = null;
      this.statusMessages.forEach((entry) => {
        if (entry.expiresAt && entry.expiresAt > now) {
          if (nextExpiry == null || entry.expiresAt < nextExpiry) {
            nextExpiry = entry.expiresAt;
          }
        }
      });
      if (nextExpiry == null) {
        return;
      }
      const delay = Math.max(200, nextExpiry - now);
      if (this.statusCleanupTimer) {
        clearTimeout(this.statusCleanupTimer);
      }
      this.statusCleanupTimer = window.setTimeout(() => {
        this.statusCleanupTimer = null;
        this.renderStatusLog();
      }, delay);
    }

    createTrafficGlowImage(iconId, image) {
      if (!this.map) {
        return;
      }
      const glowId = `${iconId}${TRAFFIC_GLOW_SUFFIX}`;
      if (this.map.hasImage(glowId)) {
        return;
      }
      const width = image.width || (image.data && image.data.width);
      const height = image.height || (image.data && image.data.height);
      if (!width || !height) {
        return;
      }
      const pad = Math.ceil(Math.max(width, height) * TRAFFIC_GLOW_PAD_RATIO);
      const canvas = document.createElement("canvas");
      canvas.width = width + pad * 2;
      canvas.height = height + pad * 2;
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        return;
      }
      const blur = Math.max(2, Math.round(Math.max(width, height) * TRAFFIC_GLOW_BLUR_RATIO));
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.shadowColor = TRAFFIC_GLOW_COLOR;
      ctx.shadowBlur = blur;
      ctx.drawImage(image, pad, pad, width, height);
      ctx.shadowBlur = 0;
      ctx.globalCompositeOperation = "destination-out";
      ctx.drawImage(image, pad, pad, width, height);
      ctx.globalCompositeOperation = "source-over";
      this.map.addImage(glowId, canvas);
    }

    buildStyle() {
      const sources = {
        mbtiles: {
          type: "vector",
          tiles: [this.config.tileUrl],
          minzoom: this.config.minZoom,
          maxzoom: this.config.maxZoom,
        },
        dem: {
          type: "raster-dem",
          tiles: [this.config.dem.tileUrl],
          tileSize: this.config.dem.tileSize,
          maxzoom: this.config.dem.maxZoom,
          encoding: this.config.dem.encoding,
        },
      };
      if (this.config.realTileUrl) {
        sources[REAL_MAP_LAYER_ID] = {
          type: "raster",
          tiles: [this.config.realTileUrl],
          tileSize: 256,
          attribution: "OpenStreetMap contributors",
        };
      }
      const hillshadeTheme = HILLSHADE_THEMES.light || {};
      const layers = [
        {
          id: "background",
          type: "background",
          paint: { "background-color": "#eef2f3" },
        },
        {
          id: "landcover",
          type: "fill",
          source: "mbtiles",
          "source-layer": "landcover",
          paint: { "fill-color": "#dfe8d8", "fill-opacity": 0.7 },
        },
        {
          id: "landuse",
          type: "fill",
          source: "mbtiles",
          "source-layer": "landuse",
          paint: { "fill-color": "#e8e6d8", "fill-opacity": 0.7 },
        },
        {
          id: "park",
          type: "fill",
          source: "mbtiles",
          "source-layer": "park",
          paint: { "fill-color": "#cfe8c5", "fill-opacity": 0.85 },
        },
        {
          id: "dem-hillshade",
          type: "hillshade",
          source: "dem",
          layout: { visibility: "none" },
          paint: { ...hillshadeTheme },
        },
        {
          id: "water",
          type: "fill",
          source: "mbtiles",
          "source-layer": "water",
          paint: { "fill-color": "#a8c8e6" },
        },
        {
          id: "waterway",
          type: "line",
          source: "mbtiles",
          "source-layer": "waterway",
          paint: { "line-color": "#90b7dd", "line-width": 1 },
        },
        {
          id: "boundary",
          type: "line",
          source: "mbtiles",
          "source-layer": "boundary",
          paint: { "line-color": "#9a9a9a", "line-width": 1, "line-dasharray": [2, 2] },
        },
        {
          id: "transportation",
          type: "line",
          source: "mbtiles",
          "source-layer": "transportation",
          paint: { "line-color": "#c2b59b", "line-width": 1 },
        },
        {
          id: "building",
          type: "fill",
          source: "mbtiles",
          "source-layer": "building",
          minzoom: 13,
          paint: { "fill-color": "#d0c7c2", "fill-opacity": 0.6 },
        },
        {
          id: "water-name",
          type: "symbol",
          source: "mbtiles",
          "source-layer": "water_name",
          minzoom: 10,
          layout: {
            "symbol-placement": "line",
            "text-field": [
              "coalesce",
              ["get", "name:latin"],
              ["get", "name"],
            ],
            "text-font": [
              "Open Sans Regular",
              "Arial Unicode MS Regular",
            ],
            "text-size": ["interpolate", ["linear"], ["zoom"], 10, 11, 14, 15],
            "text-rotation-alignment": "map",
            "text-pitch-alignment": "map",
            "text-allow-overlap": false,
          },
          paint: {
            "text-color": "#2f2f2f",
            "text-halo-color": "#ffffff",
            "text-halo-width": 1.1,
            "text-halo-blur": 0.5,
          },
        },
        {
          id: "transportation-name",
          type: "symbol",
          source: "mbtiles",
          "source-layer": "transportation_name",
          minzoom: 12,
          layout: {
            "symbol-placement": "line",
            "text-field": [
              "coalesce",
              ["get", "name:latin"],
              ["get", "name"],
              ["get", "ref"],
            ],
            "text-font": [
              "Open Sans Regular",
              "Arial Unicode MS Regular",
            ],
            "text-size": ["interpolate", ["linear"], ["zoom"], 12, 11, 16, 14],
            "text-rotation-alignment": "map",
            "text-pitch-alignment": "map",
            "text-allow-overlap": false,
          },
          paint: {
            "text-color": "#2f2f2f",
            "text-halo-color": "#ffffff",
            "text-halo-width": 1.2,
            "text-halo-blur": 0.6,
          },
        },
        {
          id: "place-label-city",
          type: "symbol",
          source: "mbtiles",
          "source-layer": "place",
          minzoom: 7,
          filter: ["in", ["get", "class"], ["literal", ["city", "town"]]],
          layout: {
            "text-field": [
              "coalesce",
              ["get", "name:latin"],
              ["get", "name"],
            ],
            "text-font": [
              "Open Sans Regular",
              "Arial Unicode MS Regular",
            ],
            "text-size": ["interpolate", ["linear"], ["zoom"], 7, 9, 10, 11, 14, 13],
            "text-allow-overlap": false,
            "text-anchor": "center",
          },
          paint: {
            "text-color": "#2f2f2f",
            "text-halo-color": "#ffffff",
            "text-halo-width": 1.4,
            "text-halo-blur": 0.6,
          },
        },
        {
          id: "place-label-suburb",
          type: "symbol",
          source: "mbtiles",
          "source-layer": "place",
          minzoom: 10,
          filter: [
            "in",
            ["get", "class"],
            [
              "literal",
              [
                "suburb",
                "village",
                "hamlet",
                "locality",
                "borough",
                "district",
                "county",
                "municipality",
              ],
            ],
          ],
          layout: {
            "text-field": [
              "coalesce",
              ["get", "name:latin"],
              ["get", "name"],
            ],
            "text-font": [
              "Open Sans Regular",
              "Arial Unicode MS Regular",
            ],
            "text-size": ["interpolate", ["linear"], ["zoom"], 10, 8, 14, 10],
            "text-allow-overlap": false,
            "text-anchor": "center",
          },
          paint: {
            "text-color": "#2f2f2f",
            "text-halo-color": "#ffffff",
            "text-halo-width": 1.2,
            "text-halo-blur": 0.6,
          },
        },
        {
          id: "place-label-neighbourhood",
          type: "symbol",
          source: "mbtiles",
          "source-layer": "place",
          minzoom: 13,
          filter: [
            "in",
            ["get", "class"],
            ["literal", ["neighbourhood", "quarter"]],
          ],
          layout: {
            "text-field": [
              "coalesce",
              ["get", "name:latin"],
              ["get", "name"],
            ],
            "text-font": [
              "Open Sans Regular",
              "Arial Unicode MS Regular",
            ],
            "text-size": ["interpolate", ["linear"], ["zoom"], 13, 7, 16, 9],
            "text-allow-overlap": false,
            "text-anchor": "center",
          },
          paint: {
            "text-color": "#2f2f2f",
            "text-halo-color": "#ffffff",
            "text-halo-width": 1.1,
            "text-halo-blur": 0.6,
          },
        },
      ];
      if (this.config.realTileUrl) {
        layers.splice(1, 0, {
          id: REAL_MAP_LAYER_ID,
          type: "raster",
          source: REAL_MAP_LAYER_ID,
          layout: { visibility: "none" },
          paint: { "raster-opacity": 1 },
        });
      }
      return {
        version: 8,
        glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
        sources,
        layers,
      };
    }

    bindThemeButtons() {
      this.themeButtons.forEach((button) => {
        button.addEventListener("click", () => {
          const theme = button.dataset.theme || "light";
          this.setTheme(theme);
          this.toggleThemePanel(false);
        });
      });
    }

    normalizeThemeButtons() {
      this.themeButtons.forEach((button) => {
        if (button.dataset.theme) {
          return;
        }
        const label = button.querySelector(".label");
        if (!label) {
          return;
        }
        const text = label.textContent.trim().toLowerCase();
        if (text === "dark") {
          button.dataset.theme = "dark";
        } else if (text === "white" || text === "light") {
          button.dataset.theme = "light";
        }
      });
    }

    bindActionButtons() {
      this.actionButtons.forEach((button) => {
        const action = button.dataset.action;
        if (!action) {
          return;
        }
        button.addEventListener("click", () => {
          this.handleAction(action);
        });
      });
    }

    bindSimTimeSettingsButton() {
      const button = this.simTimeSettingsButton;
      if (!button) {
        return;
      }
      button.addEventListener("click", (event) => {
        if (event && typeof event.preventDefault === "function") {
          event.preventDefault();
        }
        this.toggleSimSettingsPanel();
      });
    }

    bindSimSettingsPanel() {
      const panel = this.simSettingsPanel;
      if (!panel) {
        return;
      }
      const closeButton = this.simSettingsCloseButton;
      if (closeButton) {
        closeButton.addEventListener("click", (event) => {
          if (event && typeof event.preventDefault === "function") {
            event.preventDefault();
          }
          this.hideSimSettingsPanel();
        });
      }
    }

    bindLogExportButtons() {
      const buttons = [
        this.settingsDownloadLogsButton,
        this.simSettingsDownloadLogsButton,
      ].filter(Boolean);
      if (!buttons.length) {
        return;
      }
      buttons.forEach((button) => {
        button.addEventListener("click", () => {
          void this.downloadLogsZip();
        });
      });
    }

    showSimSettingsPanel() {
      if (this.showPanel) {
        this.showPanel("sim-settings");
      }
    }

    hideSimSettingsPanel() {
      if (this.hidePanel) {
        this.hidePanel("sim-settings");
      }
    }

    toggleSimSettingsPanel() {
      const panel = this.simSettingsPanel;
      if (!panel) {
        return;
      }
      const isOpen = panel.classList.contains("is-visible");
      if (isOpen) {
        this.hideSimSettingsPanel();
      } else {
        this.showSimSettingsPanel();
      }
    }

    bindCloseButtons() {
      this.closeButtons.forEach((button) => {
        const action = button.dataset.action;
        if (!action || !action.startsWith("close-")) {
          return;
        }
        const panelName = action.replace("close-", "");
        button.addEventListener("click", () => {
          this.hidePanel(panelName);
        });
      });
    }

    bindPlaybackControls() {
      if (!this.playbackPanel) {
        return;
      }
      this.playbackConnectButton = this.playbackPanel.querySelector(".playback-btn-connect");
      this.playbackPlayButton = this.playbackPanel.querySelector(".playback-btn-play");
      this.playbackFastButton = this.playbackPanel.querySelector(".playback-btn-fast");
      this.playbackPauseButton = this.playbackPanel.querySelector(".playback-btn-pause");
      this.playbackStopButton = this.playbackPanel.querySelector(".playback-btn-stop");
      this.playbackResetButton = this.playbackPanel.querySelector(".playback-btn-reset");
      this.playbackSpeedGroup = this.playbackPanel.querySelector(".playback-speed-group");
      this.playbackSpeedMenu = this.playbackPanel.querySelector(".playback-speed-menu");
      this.playbackSpeedOptions = this.playbackSpeedMenu
        ? Array.from(this.playbackSpeedMenu.querySelectorAll("[data-speed]"))
        : [];
      this.playbackSpeedMenuOpen = false;
      if (this.playbackConnectButton) {
        this.playbackConnectButton.addEventListener("click", () => this.handleConnect());
      }
      if (this.playbackPlayButton) {
        this.playbackPlayButton.addEventListener("click", () => this.handlePlay());
      }
      if (this.playbackFastButton) {
        this.playbackFastButton.addEventListener("click", (event) => {
          event.stopPropagation();
          this.handleFast();
        });
      }
      if (this.playbackPauseButton) {
        this.playbackPauseButton.addEventListener("click", () => this.handlePause());
      }
      if (this.playbackStopButton) {
        this.playbackStopButton.addEventListener("click", () => this.handleStop());
      }
      if (this.playbackResetButton) {
        this.playbackResetButton.addEventListener("click", () => {
          void this.handleReset();
        });
      }
      if (this.playbackSpeedMenu) {
        this.playbackSpeedMenu.addEventListener("click", (event) => {
          event.stopPropagation();
        });
      }
      if (this.playbackSpeedOptions && this.playbackSpeedOptions.length) {
        this.playbackSpeedOptions.forEach((button) => {
          button.addEventListener("click", (event) => {
            event.stopPropagation();
            const value = Number(button.dataset.speed);
            this.handleSpeedSelect(value);
          });
        });
      }
      if (!this.playbackSpeedCloseHandler) {
        this.playbackSpeedCloseHandler = (event) => {
          if (!this.playbackSpeedMenuOpen) {
            return;
          }
          if (!this.playbackSpeedGroup) {
            this.setSpeedMenuOpen(false);
            return;
          }
          if (event && this.playbackSpeedGroup.contains(event.target)) {
            return;
          }
          this.setSpeedMenuOpen(false);
        };
        window.addEventListener("click", this.playbackSpeedCloseHandler);
      }
    }

    bindFileControls() {
      this.filePickers.vertiport = this.createFilePicker((text, fileName) => {
        const rows = getDataRows(text);
        if (this.tableBodies.vertiport) {
          this.populateVertiportTable(this.tableBodies.vertiport, rows);
        }
        this.updateVertiportOverlayFromRows(rows);
        const isDefault = this.defaultFiles.vertiport
          ? fileName === this.defaultFiles.vertiport.name
          : false;
        this.updatePanelFileName("vertiport", fileName, { custom: !isDefault });
      });
      this.filePickers.corridor = this.createFilePicker((text, fileName) => {
        const rows = getDataRows(text);
        if (this.tableBodies.corridor) {
          this.populateCorridorTable(this.tableBodies.corridor, rows);
        }
        this.updateCorridorOverlayFromRows(rows);
        this.updatePanelFileName("corridor", fileName);
      });

      const vertiport = this.fileControls.vertiport;
      if (vertiport && vertiport.openButton) {
        vertiport.openButton.addEventListener("click", () => {
          this.filePickers.vertiport.click();
        });
      }
      if (vertiport && vertiport.resetButton) {
        vertiport.resetButton.addEventListener("click", () => {
          void this.resetVertiport();
        });
      }

      const corridor = this.fileControls.corridor;
      if (corridor && corridor.openButton) {
        corridor.openButton.addEventListener("click", () => {
          this.filePickers.corridor.click();
        });
      }
      if (corridor && corridor.resetButton) {
        corridor.resetButton.addEventListener("click", () => {
          void this.resetCorridor();
        });
      }
      if (this.datafilesResetButton) {
        this.datafilesResetButton.addEventListener("click", () => {
          void this.resetDatafilesToDefault();
        });
      }
    }

    bindEditModeButtons() {
      const airspace = document.querySelector('[data-action="edit-airspace"]');
      const vertiport = document.querySelector('[data-action="edit-vertiport"]');
      const basestation = document.querySelector('[data-action="edit-basestation"]');
      this.editModeButtons = { airspace, vertiport, basestation };
      if (airspace) {
        airspace.addEventListener("click", () => this.toggleEditMode("airspace"));
      }
      if (vertiport) {
        vertiport.addEventListener("click", () => this.toggleEditMode("vertiport"));
      }
      if (basestation) {
        basestation.addEventListener("click", () => this.toggleEditMode("basestation"));
      }
      if (this.syncEditModeAvailability) {
        this.syncEditModeAvailability();
      }
    }

    bindEditToolButtons() {
      if (!this.activeEditTools) {
        this.activeEditTools = { airspace: null, vertiport: null, basestation: null };
      }
      if (!this.editToolButtons) {
        this.editToolButtons = { airspace: null, vertiport: null, basestation: null };
      }
      if (!this.editToolPanels) {
        this.editToolPanels = { airspace: null, vertiport: null, basestation: null };
      }
    }

    bindPlanControls() {
      if (this.planControls.selectButton) {
        this.planControls.selectButton.addEventListener("click", () =>
          this.togglePlanSelection(),
        );
      }
      if (this.planControls.resetButton) {
        this.planControls.resetButton.addEventListener("click", () => this.resetPlan());
      }
      if (this.planControls.applyButton) {
        this.planControls.applyButton.addEventListener("click", () => this.applyPlan());
      }
    }

    bindSettingsControls() {
      if (this.settingsControls.applyButton) {
        this.settingsControls.applyButton.addEventListener("click", () =>
          this.applySettingsPanel(),
        );
      }
      if (this.settingsControls.resetButton) {
        this.settingsControls.resetButton.addEventListener("click", () =>
          this.resetSettingsPanel(),
        );
      }
      if (this.settingsControls.trafficInputs && this.settingsControls.trafficInputs.length) {
        this.settingsControls.trafficInputs.forEach((input) => {
          input.addEventListener("change", () => {
            if (input.checked) {
              this.applyTrafficSelection(input.value, {
                notify: true,
                send: this.webApiEnabled,
                updateGoal: true,
              });
            }
          });
        });
      }
      this.bindHighDensityFolderControls();
      const updateOperationLabels = () => {
        this.updateOperationSummary();
        this.updateOperationGoalSummary();
        this.updateTrafficCountLabels();
      };
      if (this.settingsControls.operationStart) {
        this.settingsControls.operationStart.addEventListener("change", updateOperationLabels);
      }
      if (this.settingsControls.operationEnd) {
        this.settingsControls.operationEnd.addEventListener("change", updateOperationLabels);
      }
      if (this.settingsControls.operationGoal) {
        this.settingsControls.operationGoal.addEventListener("input", () =>
          this.updateOperationGoalSummary(),
        );
      }
    }

    bindHighDensityFolderControls() {
      const controls = this.settingsControls || {};
      const picker = controls.highDensityFolderPicker;
      const uploadEnabled = Boolean(this.highDensityFolderUploadEnabled);
      if (controls.highDensityFolderLoadButton) {
        controls.highDensityFolderLoadButton.disabled = !uploadEnabled;
      }
      if (controls.highDensityFolderResetButton) {
        controls.highDensityFolderResetButton.disabled = !uploadEnabled;
      }
      if (picker) {
        picker.disabled = !uploadEnabled;
      }
      if (!uploadEnabled) {
        this.resetHighDensityFolderSelection({ notify: false });
        return;
      }
      if (controls.highDensityFolderLoadButton && picker) {
        controls.highDensityFolderLoadButton.addEventListener("click", () => {
          picker.click();
        });
      }
      if (controls.highDensityFolderResetButton) {
        controls.highDensityFolderResetButton.addEventListener("click", () => {
          this.resetHighDensityFolderSelection({ notify: true });
        });
      }
      if (picker) {
        picker.addEventListener("change", () => {
          void this.handleHighDensityFolderSelection(picker.files);
        });
      }
      this.updateHighDensityFolderUi();
    }

    getHighDensityFolderDefaultLabel() {
      return this.translateLiteral("No folder selected");
    }

    updateHighDensityFolderUi() {
      const controls = this.settingsControls || {};
      const input = controls.highDensityFolderNameInput;
      const indicator = controls.highDensityFolderIndicator;
      const statusLabel = this.translateLiteral("Folder load status");
      const defaultLabel = this.getHighDensityFolderDefaultLabel();
      if (input) {
        input.value = this.highDensityFolderName || defaultLabel;
        input.classList.toggle("is-custom", Boolean(this.highDensityFolderLoaded));
      }
      if (indicator) {
        indicator.classList.toggle("is-ready", Boolean(this.highDensityFolderLoaded));
        const detail = this.highDensityFolderLoaded
          ? this.highDensityFolderName || defaultLabel
          : defaultLabel;
        indicator.setAttribute("aria-label", `${statusLabel}: ${detail}`);
        indicator.title = `${statusLabel}: ${detail}`;
      }
    }

    resetHighDensityFolderSelection(options = {}) {
      const { notify = false } = options;
      this.highDensityFolderLoaded = false;
      this.highDensityFolderName = "";
      this.highDensityFolderFileCount = 0;
      this.highDensityFolderFiles = [];
      const controls = this.settingsControls || {};
      if (controls.highDensityFolderPicker) {
        controls.highDensityFolderPicker.value = "";
      }
      this.updateHighDensityFolderUi();
      if (notify) {
        this.addStatusMessage({
          text: this.t("status.highdensity_folder_reset"),
          level: "info",
          ttlMs: 2200,
        });
      }
    }

    normalizeCsvHeaderKey(value) {
      return String(value || "")
        .trim()
        .toLowerCase()
        .replace(/\s+/g, "")
        .replace(/_/g, "");
    }

    extractFolderNameFromFiles(files) {
      const names = new Set();
      (files || []).forEach((file) => {
        const relative = String(file && file.webkitRelativePath ? file.webkitRelativePath : "");
        if (!relative) {
          return;
        }
        const head = relative.split(/[\\/]/)[0];
        if (head) {
          names.add(head);
        }
      });
      if (names.size === 1) {
        return Array.from(names)[0];
      }
      if (names.size > 1) {
        const list = Array.from(names);
        return `${list[0]} +${names.size - 1}`;
      }
      return "";
    }

    async handleHighDensityFolderSelection(fileList) {
      const files = Array.from(fileList || []);
      const controls = this.settingsControls || {};
      if (controls.highDensityFolderPicker) {
        controls.highDensityFolderPicker.value = "";
      }
      if (!files.length) {
        return;
      }
      const csvFiles = files.filter((file) => file && /\.csv$/i.test(String(file.name || "")));
      const folderName = this.extractFolderNameFromFiles(files) || this.getHighDensityFolderDefaultLabel();
      const markInvalid = () => {
        this.highDensityFolderLoaded = false;
        this.highDensityFolderName = folderName;
        this.highDensityFolderFileCount = 0;
        this.highDensityFolderFiles = [];
        this.updateHighDensityFolderUi();
        this.addStatusMessage({
          text: this.t("status.highdensity_folder_invalid"),
          level: "warn",
          ttlMs: 3200,
        });
      };
      if (!csvFiles.length) {
        markInvalid();
        return;
      }
      const requiredColumns = ["localid", "from", "to", "std", "sta"];
      for (const file of csvFiles) {
        let text = "";
        try {
          text = await file.text();
        } catch (_error) {
          markInvalid();
          return;
        }
        const rows = normalizeRows(parseCsvRows(String(text || "")));
        if (!rows.length) {
          markInvalid();
          return;
        }
        const headerSet = new Set((rows[0] || []).map((cell) => this.normalizeCsvHeaderKey(cell)));
        const isValidHeader = requiredColumns.every((key) => headerSet.has(key));
        if (!isValidHeader) {
          markInvalid();
          return;
        }
      }
      this.highDensityFolderLoaded = true;
      this.highDensityFolderFileCount = csvFiles.length;
      this.highDensityFolderFiles = csvFiles;
      this.highDensityFolderName = `${folderName} (${csvFiles.length})`;
      this.updateHighDensityFolderUi();
      this.addStatusMessage({
        text: this.t("status.highdensity_folder_loaded", {
          name: folderName,
          count: csvFiles.length,
        }),
        level: "success",
        ttlMs: 3000,
      });
    }

    async buildHighDensityFlightplanPayload() {
      if (!this.highDensityFolderLoaded || !Array.isArray(this.highDensityFolderFiles)) {
        return null;
      }
      const sourceFiles = this.highDensityFolderFiles.filter(
        (file) => file && /\.csv$/i.test(String(file.name || "")),
      );
      if (!sourceFiles.length) {
        return null;
      }
      const files = [];
      for (const file of sourceFiles) {
        let text = "";
        try {
          text = await file.text();
        } catch (_error) {
          continue;
        }
        if (!String(text || "").trim()) {
          continue;
        }
        files.push({
          name: String(file.name || ""),
          relativePath: String(file.webkitRelativePath || ""),
          text: String(text),
        });
      }
      if (!files.length) {
        return null;
      }
      const folderName = this.extractFolderNameFromFiles(sourceFiles) || this.highDensityFolderName || "";
      return {
        name: folderName,
        files,
      };
    }

    bindRuleControls() {
      const { speedInput, speedUnitButtons } = this.ruleControls;
      if (Array.isArray(speedUnitButtons) && speedUnitButtons.length) {
        speedUnitButtons.forEach((button) => {
          button.addEventListener("click", () => {
            const unit = button.dataset.speedUnit || "knot";
            this.setSpeedUnit(unit, { preserveValue: true });
          });
        });
      }
      if (speedInput) {
        speedInput.addEventListener("input", () => {
          this.updateSpeedUnitButtons();
        });
      }
      const updateHints = () => this.updateRuleDistanceHints();
      if (this.ruleControls.separationInput) {
        this.ruleControls.separationInput.addEventListener("input", updateHints);
      }
      if (this.ruleControls.warningDistInput) {
        this.ruleControls.warningDistInput.addEventListener("input", updateHints);
      }
      if (this.ruleControls.cautionDistInput) {
        this.ruleControls.cautionDistInput.addEventListener("input", updateHints);
      }
      if (this.ruleControls.climbRateInput) {
        this.ruleControls.climbRateInput.addEventListener("input", updateHints);
      }
      if (this.ruleControls.transitionAltInput) {
        this.ruleControls.transitionAltInput.addEventListener("input", updateHints);
      }
      if (this.ruleControls.transitionSpeedInput) {
        this.ruleControls.transitionSpeedInput.addEventListener("input", updateHints);
      }
    }

    bindAutopilotControls() {
      const controls = this.autopilotControls || {};
      if (controls.onButton) {
        controls.onButton.addEventListener("click", () => this.applyAutopilotSettings(true));
      }
      if (controls.offButton) {
        controls.offButton.addEventListener("click", () => this.applyAutopilotSettings(false));
      }
    }

    initSettingsPanel() {
      this.resetSettingsPanel();
    }

    initAutopilotPanel() {
      this.applyAutopilotState({ ...DEFAULT_AUTOPILOT });
    }

    resetSettingsPanel() {
      this.resetAirsimSettings();
      this.speedUnit = "knot";
      this.updateSpeedUnitButtons();
      this.applyRulesState({ ...DEFAULT_RULES });
      this.applyTrafficSelection("Middle", { notify: false, send: false, updateGoal: true });
    }

    applySettingsPanel() {
      this.applyAirsimSettings();
      const nextRules = this.collectRulesFromInputs();
      this.rulesState = nextRules;
      this.rulesInitialized = true;
      this.applyRulesState(nextRules);
      if (this.webApiEnabled) {
        this.sendWebRequest("api/rules", nextRules);
      }
      this.addStatusMessage({
        text: this.t("status.rules_updated"),
        level: "success",
        ttlMs: 2500,
      });
    }

    collectAutopilotInputs() {
      const controls = this.autopilotControls || {};
      const readDeltaKnot = (input, fallback) => {
        const raw = input ? Number.parseFloat(input.value) : NaN;
        if (!Number.isFinite(raw)) {
          return fallback;
        }
        return Math.max(0, raw);
      };
      const readDuration = (input, fallback) => {
        const raw = input ? Number.parseFloat(input.value) : NaN;
        if (!Number.isFinite(raw)) {
          return fallback;
        }
        return Math.max(0, raw);
      };
      return {
        duration_s: readDuration(controls.durationInput, DEFAULT_AUTOPILOT.duration_s),
        lv1_delta_knot: readDeltaKnot(controls.lv1Input, DEFAULT_AUTOPILOT.lv1_delta_knot),
        lv2_delta_knot: readDeltaKnot(controls.lv2Input, DEFAULT_AUTOPILOT.lv2_delta_knot),
        lv3_delta_knot: readDeltaKnot(controls.lv3Input, DEFAULT_AUTOPILOT.lv3_delta_knot),
      };
    }

    applyAutopilotState(state) {
      const next = { ...DEFAULT_AUTOPILOT, ...(state || {}) };
      this.autopilotState = next;
      const controls = this.autopilotControls || {};
      if (controls.lv1Input) {
        controls.lv1Input.value = this.formatNumber(next.lv1_delta_knot, 0);
      }
      if (controls.lv2Input) {
        controls.lv2Input.value = this.formatNumber(next.lv2_delta_knot, 0);
      }
      if (controls.lv3Input) {
        controls.lv3Input.value = this.formatNumber(next.lv3_delta_knot, 0);
      }
      if (controls.durationInput) {
        controls.durationInput.value = this.formatNumber(next.duration_s, 0);
      }
      if (controls.onButton) {
        controls.onButton.classList.toggle("is-active", Boolean(next.enabled));
      }
      if (controls.offButton) {
        controls.offButton.classList.toggle("is-active", !next.enabled);
      }
    }

    applyAutopilotSettings(enabled) {
      const prevState = { ...this.autopilotState };
      const values = this.collectAutopilotInputs();
      const next = { ...values, enabled: Boolean(enabled) };
      this.autopilotState = next;
      this.autopilotInitialized = true;
      this.autopilotPendingSync = true;
      this.applyAutopilotState(next);
      const ok = this.sendControlCommand(
        "setAutopilot",
        next.enabled,
        next.duration_s,
        next.lv1_delta_knot,
        next.lv2_delta_knot,
        next.lv3_delta_knot,
      );
      if (ok) {
        if (this.webApiEnabled && typeof this.scheduleWebPoll === "function") {
          this.scheduleWebPoll(0);
        }
        this.addStatusMessage({
          text: this.t(next.enabled ? "status.autopilot_on" : "status.autopilot_off"),
          level: "info",
          ttlMs: 2500,
        });
      } else {
        this.autopilotPendingSync = false;
        this.autopilotState = prevState;
        this.applyAutopilotState(prevState);
      }
    }

    applyRulesState(rules) {
      const next = { ...DEFAULT_RULES, ...(rules || {}) };
      this.rulesState = next;
      if (this.ruleControls.speedInput) {
        const speedValue = this.formatSpeedByUnit(next.speed_mps, this.speedUnit);
        this.ruleControls.speedInput.value = speedValue;
      }
      if (this.ruleControls.accelInput) {
        this.ruleControls.accelInput.value = this.formatNumber(next.accel_mps2, 1);
      }
      if (this.ruleControls.climbRateInput) {
        this.ruleControls.climbRateInput.value = this.formatNumber(next.climb_rate_fpm, 0);
      }
      if (this.ruleControls.transitionAltInput) {
        this.ruleControls.transitionAltInput.value = this.formatNumber(next.transition_alt_ft, 0);
      }
      if (this.ruleControls.transitionSpeedInput) {
        this.ruleControls.transitionSpeedInput.value = this.formatNumber(
          next.transition_speed_knot,
          0,
        );
      }
      if (this.ruleControls.batteryInput) {
        this.ruleControls.batteryInput.value = this.formatMinutes(
          (next.battery_capacity_s || 0) / 60,
        );
      }
      if (this.ruleControls.minSpeedInput) {
        this.ruleControls.minSpeedInput.value = this.formatNumber(
          next.min_safe_speed_mps,
          1,
        );
      }
      if (this.ruleControls.holdingInput) {
        this.ruleControls.holdingInput.value = this.formatMinutes(next.holding_s / 60);
      }
      if (this.ruleControls.takeoffInput) {
        this.ruleControls.takeoffInput.value = this.formatMinutes(next.takeoff_s / 60);
      }
      if (this.ruleControls.landingInput) {
        this.ruleControls.landingInput.value = this.formatMinutes(next.landing_s / 60);
      }
      if (this.ruleControls.turnRateInput) {
        this.ruleControls.turnRateInput.value = this.formatNumber(next.turn_rate_deg_s, 1);
      }
      if (this.ruleControls.separationInput) {
        this.ruleControls.separationInput.value = this.formatNumber(next.separation_m, 0);
      }
      if (this.ruleControls.warningDistInput) {
        this.ruleControls.warningDistInput.value = this.formatNumber(next.warning_m, 0);
      }
      if (this.ruleControls.warningEcInput) {
        this.ruleControls.warningEcInput.value = this.formatNumber(next.warning_ec_s, 0);
      }
      if (this.ruleControls.warningTrailingInput) {
        this.ruleControls.warningTrailingInput.value = this.formatNumber(
          next.warning_trailing_circles,
          0,
        );
      }
      if (this.ruleControls.warningLeadingInput) {
        this.ruleControls.warningLeadingInput.value = this.formatNumber(
          next.warning_leading_knot_delta,
          0,
        );
      }
      if (this.ruleControls.cautionDistInput) {
        this.ruleControls.cautionDistInput.value = this.formatNumber(next.caution_m, 0);
      }
      if (this.ruleControls.cautionEcInput) {
        this.ruleControls.cautionEcInput.value = this.formatNumber(next.caution_ec_s, 0);
      }
      if (this.ruleControls.cautionTrailingInput) {
        this.ruleControls.cautionTrailingInput.value = this.formatNumber(
          next.caution_trailing_knot_delta,
          0,
        );
      }
      if (this.ruleControls.cautionLeadingInput) {
        this.ruleControls.cautionLeadingInput.value = this.formatNumber(
          next.caution_leading_knot_delta,
          0,
        );
      }
      if (this.ruleControls.riskHorizonInput) {
        this.ruleControls.riskHorizonInput.value = this.formatNumber(
          next.risk_predict_horizon_s,
          0,
        );
      }
      if (this.ruleControls.riskLateralInput) {
        this.ruleControls.riskLateralInput.value = this.formatNumber(
          next.risk_lateral_m,
          0,
        );
      }
      if (this.ruleControls.riskDirectionInput) {
        this.ruleControls.riskDirectionInput.value = this.formatNumber(
          next.risk_direction_cos,
          2,
        );
      }
      if (this.ruleControls.riskIntervalInput) {
        this.ruleControls.riskIntervalInput.value = this.formatNumber(
          next.risk_update_interval_s,
          1,
        );
      }
      if (this.ruleControls.riskProxLv3Input) {
        this.ruleControls.riskProxLv3Input.value = this.formatNumber(
          next.risk_proximity_lv3_m,
          0,
        );
      }
      if (this.ruleControls.riskProxLv2Input) {
        this.ruleControls.riskProxLv2Input.value = this.formatNumber(
          next.risk_proximity_lv2_m,
          0,
        );
      }
      if (this.ruleControls.riskProxLv1Input) {
        this.ruleControls.riskProxLv1Input.value = this.formatNumber(
          next.risk_proximity_lv1_m,
          0,
        );
      }
      if (this.ruleControls.riskBattLv3Input) {
        this.ruleControls.riskBattLv3Input.value = this.formatNumber(
          next.risk_battery_lv3_pct,
          0,
        );
      }
      if (this.ruleControls.riskBattLv2Input) {
        this.ruleControls.riskBattLv2Input.value = this.formatNumber(
          next.risk_battery_lv2_pct,
          0,
        );
      }
      if (this.ruleControls.riskBattLv1Input) {
        this.ruleControls.riskBattLv1Input.value = this.formatNumber(
          next.risk_battery_lv1_pct,
          0,
        );
      }
      if (this.ruleControls.rnpMaxLatInput) {
        this.ruleControls.rnpMaxLatInput.value = this.formatNumber(next.rnp_max_lat_m, 0);
      }
      if (this.ruleControls.rnpMaxVerInput) {
        this.ruleControls.rnpMaxVerInput.value = this.formatNumber(next.rnp_max_ver_m, 0);
      }
      if (this.ruleControls.rnpRLv1Input) {
        this.ruleControls.rnpRLv1Input.value = this.formatNumber(next.rnp_r_lv1, 2);
      }
      if (this.ruleControls.rnpRLv2Input) {
        this.ruleControls.rnpRLv2Input.value = this.formatNumber(next.rnp_r_lv2, 2);
      }
      if (this.ruleControls.rnpRLv3Input) {
        this.ruleControls.rnpRLv3Input.value = this.formatNumber(next.rnp_r_lv3, 2);
      }
      if (this.ruleControls.rnpTtvLv1Input) {
        this.ruleControls.rnpTtvLv1Input.value = this.formatNumber(next.rnp_ttv_lv1_s, 1);
      }
      if (this.ruleControls.rnpTtvLv2Input) {
        this.ruleControls.rnpTtvLv2Input.value = this.formatNumber(next.rnp_ttv_lv2_s, 1);
      }
      if (this.ruleControls.windEnabledInput) {
        this.ruleControls.windEnabledInput.value = next.wind_enabled ? "1" : "0";
      }
      if (this.ruleControls.windTimeSpeedInput) {
        this.ruleControls.windTimeSpeedInput.value = this.formatNumber(
          next.wind_time_speed,
          1,
        );
      }
      if (this.ruleControls.windSmoothInput) {
        this.ruleControls.windSmoothInput.value = this.formatNumber(
          next.wind_smooth_s,
          1,
        );
      }
      if (this.ruleControls.windCrossGainInput) {
        this.ruleControls.windCrossGainInput.value = this.formatNumber(
          next.wind_cross_gain,
          2,
        );
      }
      if (this.ruleControls.windCrossReturnInput) {
        this.ruleControls.windCrossReturnInput.value = this.formatNumber(
          next.wind_cross_return_s,
          1,
        );
      }
      if (this.ruleControls.windCrossMaxInput) {
        this.ruleControls.windCrossMaxInput.value = this.formatNumber(
          next.wind_cross_max_m,
          0,
        );
      }
      if (this.ruleControls.windAlongGainInput) {
        this.ruleControls.windAlongGainInput.value = this.formatNumber(
          next.wind_along_gain,
          2,
        );
      }
      if (this.ruleControls.windAlongMaxInput) {
        this.ruleControls.windAlongMaxInput.value = this.formatNumber(
          next.wind_along_max_mps,
          1,
        );
      }
      if (this.ruleControls.windCrabMaxInput) {
        this.ruleControls.windCrabMaxInput.value = this.formatNumber(
          next.wind_crab_max_deg,
          1,
        );
      }
      if (this.settingsControls.operationStart) {
        this.settingsControls.operationStart.value = this.formatMinutesToTime(
          next.operation_start_min,
        );
      }
      if (this.settingsControls.operationEnd) {
        this.settingsControls.operationEnd.value = this.formatMinutesToTime(
          next.operation_end_min,
        );
      }
      if (this.settingsControls.operationGoal) {
        this.settingsControls.operationGoal.value = this.formatNumber(
          next.operation_goal_count,
          0,
        );
      }
      if (typeof this.setWeatherTimeSpeed === "function") {
        this.setWeatherTimeSpeed(this.weatherSpeedMultiplier || 1);
      }
      this.updateRuleDistanceHints();
      this.updateOperationSummary();
      this.updateOperationGoalSummary();
      this.updateTrafficCountLabels();
    }

    applyTrafficSelection(selection, options = {}) {
      const { notify = false, send = true, updateGoal = false } = options;
      const name = typeof selection === "string" ? selection : "";
      if (!TRAFFIC_LEVELS[name]) {
        return;
      }
      this.currentTrafficSelection = name;
      if (Array.isArray(this.settingsControls.trafficInputs)) {
        this.settingsControls.trafficInputs.forEach((input) => {
          input.checked = input.value === name;
        });
      }
      this.updateTrafficCountLabels();
      if (updateGoal && this.settingsControls.operationGoal) {
        const goal = TRAFFIC_LEVELS[name];
        this.settingsControls.operationGoal.value = String(goal);
        if (this.rulesState) {
          this.rulesState.operation_goal_count = goal;
        }
        this.updateOperationGoalSummary();
      }
      if (send && this.webApiEnabled) {
        this.sendWebRequest("api/traffic", { selection: name });
      }
      if (notify) {
        const label = this.t(`traffic.level.${String(name).toLowerCase()}`, null, name);
        this.addStatusMessage({
          text: this.t("status.traffic_selection", { name: label }),
          level: "info",
          ttlMs: 2000,
        });
      }
    }

    initDashboardPanel() {
      if (!this.dashboardPanel || !this.dashboardToggle) {
        return;
      }
      this.dashboardToggle.addEventListener("click", () => {
        this.toggleDashboardPanel();
      });
      this.dashboardTabPanels = new Map();
      const panels = Array.from(this.dashboardPanel.querySelectorAll(".dashboard-tab-panel"));
      panels.forEach((panel) => {
        const key = panel.dataset.tabPanel;
        if (key) {
          this.dashboardTabPanels.set(key, panel);
        }
      });
      this.dashboardTables = new Map();
      const tables = Array.from(
        this.dashboardPanel.querySelectorAll("table[data-dashboard-table]"),
      );
      tables.forEach((table) => {
        const key = table.dataset.dashboardTable;
        const body = table.querySelector("tbody");
        if (key && body) {
          this.dashboardTables.set(key, body);
        }
      });
      if (Array.isArray(this.dashboardTabButtons)) {
        this.dashboardTabButtons.forEach((button) => {
          button.addEventListener("click", () => {
            const key = button.dataset.tab || "management";
            this.setDashboardTab(key);
          });
        });
      }
      this.setDashboardTab(this.dashboardActiveTab || "management");
      this.toggleDashboardPanel(this.dashboardVisible);
      if (this.dashboardToggle && this.dashboardToggleDefaultRight === null) {
        this.dashboardToggleDefaultRight = getComputedStyle(this.dashboardToggle).right || "";
      }
      if (this.dashboardPanel && !this.dashboardToggleTransitionBound) {
        this.dashboardPanel.addEventListener("transitionend", () => {
          this.positionDashboardToggle();
          if (this.dashboardActiveTab === "management") {
            this.queueRiskTrendResize();
          } else if (this.dashboardActiveTab === "human-intervention") {
            this.queueHumanWorkloadResize();
          }
        });
        this.dashboardToggleTransitionBound = true;
      }
      this.scheduleDashboardTogglePosition();
      window.addEventListener("resize", () => this.scheduleDashboardTogglePosition());
    }

    toggleDashboardPanel(force) {
      if (!this.dashboardPanel || !this.dashboardToggle) {
        return;
      }
      const isOpen = this.dashboardPanel.classList.contains("is-open");
      const next = typeof force === "boolean" ? force : !isOpen;
      this.dashboardPanel.classList.toggle("is-open", next);
      this.dashboardToggle.setAttribute("aria-expanded", next ? "true" : "false");
      this.dashboardToggle.textContent = next ? ">" : "<";
      const toggleLabel = next
        ? this.t("dashboard.hide_table")
        : this.t("dashboard.show_table");
      this.dashboardToggle.setAttribute("title", toggleLabel);
      this.dashboardToggle.setAttribute("aria-label", toggleLabel);
      this.dashboardVisible = next;
      this.scheduleDashboardTogglePosition();
      if (next && this.dashboardActiveTab === "management") {
        this.queueRiskTrendResize();
      }
      if (next && this.dashboardActiveTab === "human-intervention") {
        this.queueHumanWorkloadResize();
      }
      if (this.tutorialMode === "guided") {
        this.refreshTutorialLayout();
      }
    }

    setDashboardTab(key) {
      const next = key || "management";
      this.dashboardActiveTab = next;
      if (Array.isArray(this.dashboardTabButtons)) {
        this.dashboardTabButtons.forEach((button) => {
          button.classList.toggle("is-active", button.dataset.tab === next);
          button.setAttribute("aria-selected", button.dataset.tab === next ? "true" : "false");
        });
      }
      if (this.dashboardTabPanels) {
        this.dashboardTabPanels.forEach((panel, name) => {
          const isActive = name === next;
          panel.classList.toggle("is-active", isActive);
          panel.setAttribute("aria-hidden", isActive ? "false" : "true");
        });
      }
      if (next === "history") {
        this.updateHistoryTable(true);
      } else if (next === "human-intervention") {
        this.queueHumanWorkloadResize();
        this.updateHumanWorkloadSeries(this.lastSimTime_s, true);
      } else if (next === "management") {
        this.queueRiskTrendResize();
        this.updateRiskTrend();
      }
    }

    positionDashboardToggle() {
      if (!this.dashboardToggle) {
        return;
      }
      if (!this.dashboardPanel || !this.dashboardPanel.classList.contains("is-open")) {
        this.dashboardToggle.style.left = "";
        this.dashboardToggle.style.right =
          this.dashboardToggleDefaultRight != null ? this.dashboardToggleDefaultRight : "";
        return;
      }
      const panelRect = this.dashboardPanel.getBoundingClientRect();
      const scale =
        Number.parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--ui-scale")) ||
        1;
      const gap = 8 * scale;
      const right = window.innerWidth - panelRect.left + gap;
      this.dashboardToggle.style.left = "";
      this.dashboardToggle.style.right = `${Math.max(0, right)}px`;
    }

    scheduleDashboardTogglePosition() {
      this.positionDashboardToggle();
      if (!this.dashboardPanel || !this.dashboardPanel.classList.contains("is-open")) {
        return;
      }
      window.requestAnimationFrame(() => this.positionDashboardToggle());
      if (this.dashboardTogglePositionTimer) {
        window.clearTimeout(this.dashboardTogglePositionTimer);
      }
      this.dashboardTogglePositionTimer = window.setTimeout(
        () => this.positionDashboardToggle(),
        320,
      );
    }

    setDashboardSelection(name) {
      const value = String(name || "");
      if (value === this.dashboardSelectedName) {
        return;
      }
      this.dashboardSelectedName = value;
      const safeName =
        typeof CSS !== "undefined" && CSS.escape
          ? CSS.escape(value)
          : value.replace(/["\\]/g, "\\$&");
      const clearSelection = (body) => {
        if (!body) {
          return;
        }
        body.querySelectorAll(".dashboard-row.is-selected").forEach((row) => {
          row.classList.remove("is-selected");
        });
      };
      this.dashboardTables.forEach((body) => clearSelection(body));
      if (!value) {
        return;
      }
      const markSelection = (body) => {
        if (!body) {
          return;
        }
        const row = body.querySelector(`tr[data-name="${safeName}"]`);
        if (row) {
          row.classList.add("is-selected");
        }
      };
      this.dashboardTables.forEach((body) => markSelection(body));
    }

    clearDashboard() {
      this.dashboardData.clear();
      this.dashboardTimes.clear();
      if (this.dashboardFlightMetrics) {
        this.dashboardFlightMetrics.clear();
      }
      this.dashboardSequence = 0;
      this.dashboardFailureSequence = 0;
      this.dashboardSelectedName = null;
      this.lastDashboardPositions = null;
      if (this.dashboardFailureRows) {
        this.dashboardFailureRows = [];
      }
      this.dashboardTables.forEach((body) => {
        body.innerHTML = "";
      });
      if (this.dashboardRiskCounts) {
        this.dashboardRiskCounts.clear();
      }
      const badges = document.querySelectorAll("[data-risk-count]");
      badges.forEach((badge) => {
        badge.textContent = "0";
      });
      if (this.riskTrendData) {
        this.riskTrendData.times = [];
        this.riskTrendData.level1 = [];
        this.riskTrendData.level2 = [];
        this.riskTrendData.level3 = [];
      }
      if (this.riskTrendHistory) {
        this.riskTrendHistory.times = [];
        this.riskTrendHistory.level1 = [];
        this.riskTrendHistory.level2 = [];
        this.riskTrendHistory.level3 = [];
      }
      this.riskTrendLastTime = null;
      if (this.humanInterventionEvents) {
        this.humanInterventionEvents = [];
      }
      if (this.humanSpeedEvents) {
        this.humanSpeedEvents = [];
      }
      if (this.humanAirspaceEvents) {
        this.humanAirspaceEvents = [];
      }
      if (this.humanEmergencyEvents) {
        this.humanEmergencyEvents = [];
      }
      if (this.humanSpeedHistory) {
        this.humanSpeedHistory = [];
      }
      if (this.humanAirspaceHistory) {
        this.humanAirspaceHistory = [];
      }
      if (this.humanEmergencyHistory) {
        this.humanEmergencyHistory = [];
      }
      if (this.humanWorkloadData) {
        this.humanWorkloadData.times = [];
        this.humanWorkloadData.total = [];
        this.humanWorkloadData.speed = [];
        this.humanWorkloadData.airspace = [];
        this.humanWorkloadData.emergency = [];
      }
      if (this.humanWorkloadHistory) {
        this.humanWorkloadHistory.times = [];
        this.humanWorkloadHistory.total = [];
        this.humanWorkloadHistory.speed = [];
        this.humanWorkloadHistory.airspace = [];
        this.humanWorkloadHistory.emergency = [];
      }
      this.humanWorkloadLastTime = null;
      this.humanWorkloadHistoryLastTime = null;
      this.updateHumanWorkloadChart();
      this.renderHumanInterventionTables();
      this.updateRiskTrend();
      this.updateSimStatsFromDashboard();
    }

    getSimStatSuffix(element) {
      if (!element) {
        return "";
      }
      if (Object.prototype.hasOwnProperty.call(element.dataset, "suffix")) {
        return element.dataset.suffix || "";
      }
      const text = element.textContent ? String(element.textContent) : "";
      const match = text.match(/[^\d\s]+$/);
      const suffix = match ? match[0] : "";
      element.dataset.suffix = suffix;
      return suffix;
    }

    setSimStatValue(element, value, suffixOverride) {
      if (!element) {
        return;
      }
      const suffix =
        typeof suffixOverride === "string" ? suffixOverride : this.getSimStatSuffix(element);
      element.textContent = `${value}${suffix}`;
    }

    updateSimStatsFromDashboard(positions) {
      if (!this.simStats) {
        return;
      }
      if (Array.isArray(positions)) {
        this.lastDashboardPositions = positions;
      }
      const resolvedPositions = Array.isArray(positions)
        ? positions
        : Array.isArray(this.lastDashboardPositions)
          ? this.lastDashboardPositions
          : null;
      const hasPositions = Array.isArray(resolvedPositions);
      let total = 0;
      let done = 0;
      let active = 0;
      const dashboardCount = this.dashboardData ? this.dashboardData.size : 0;
      if (this.dashboardTimes) {
        this.dashboardTimes.forEach((entry) => {
          if (entry && Number.isFinite(entry.ata_s)) {
            done += 1;
          }
        });
      }
      if (dashboardCount > 0) {
        total = dashboardCount;
        if (hasPositions) {
          active = resolvedPositions.length;
          if (active + done > total) {
            total = active + done;
          }
        } else {
          active = Math.max(0, total - done);
        }
      } else if (hasPositions) {
        total = resolvedPositions.length;
        active = resolvedPositions.length;
        done = 0;
      }
      this.setSimStatValue(this.simStats.total, total);
      this.setSimStatValue(this.simStats.active, active);
      this.setSimStatValue(this.simStats.done, done);
    }

    getDashboardTimestamp() {
      if (Number.isFinite(this.pendingDashboardTime_s)) {
        return Number(this.pendingDashboardTime_s);
      }
      return Number.isFinite(this.lastSimTime_s) ? this.lastSimTime_s : 0;
    }

    formatDashboardTime(seconds) {
      if (!Number.isFinite(seconds)) {
        return "-";
      }
      const startMin = this.getOperationMinutes ? this.getOperationMinutes().startMin : 0;
      const offset = Number.isFinite(startMin) ? startMin * 60 : 0;
      return this.formatTime(seconds + offset);
    }

    extractFlightMetrics(payload) {
      if (!payload || typeof payload !== "object") {
        return null;
      }
      const readNumber = (key) => {
        const value = Number(payload[key]);
        return Number.isFinite(value) ? value : null;
      };
      const metrics = {
        std_s: readNumber("std_s"),
        sta_s: readNumber("sta_s"),
        eta_s: readNumber("eta_s"),
        ata_s: readNumber("ata_s"),
        delay_s: readNumber("delay_s"),
        tti: readNumber("tti"),
        remaining_dist_m: readNumber("remaining_dist_m"),
        remaining_time_s: readNumber("remaining_time_s"),
      };
      const hasValue = Object.values(metrics).some((value) => Number.isFinite(value));
      if (!hasValue) {
        return null;
      }
      return metrics;
    }

    mergeDashboardFlightMetrics(name, payload) {
      const key = String(name || "").trim();
      if (!key) {
        return null;
      }
      const incoming = this.extractFlightMetrics(payload);
      if (!incoming) {
        return this.dashboardFlightMetrics.get(key) || null;
      }
      const previous = this.dashboardFlightMetrics.get(key) || {};
      const next = { ...previous };
      const previousStd_s = Number(previous.std_s);
      const incomingStd_s = Number(incoming.std_s);
      const isNextLeg =
        Number.isFinite(previousStd_s) &&
        Number.isFinite(incomingStd_s) &&
        incomingStd_s > previousStd_s + 1;
      if (isNextLeg) {
        delete next.ata_s;
        delete next.delay_s;
        delete next.tti;
        delete next.remaining_dist_m;
        delete next.remaining_time_s;
      }
      Object.keys(incoming).forEach((field) => {
        const value = incoming[field];
        if (Number.isFinite(value)) {
          next[field] = value;
        }
      });
      this.dashboardFlightMetrics.set(key, next);
      const timeEntry = this.dashboardTimes.get(key) || {};
      if (Number.isFinite(next.std_s) && !Number.isFinite(timeEntry.atd_s)) {
        timeEntry.atd_s = Number(next.std_s);
      }
      if (Number.isFinite(next.ata_s)) {
        timeEntry.ata_s = Number(next.ata_s);
      }
      this.dashboardTimes.set(key, timeEntry);
      return next;
    }

    formatSignedDuration(seconds) {
      const value = Number(seconds);
      if (!Number.isFinite(value)) {
        return "-";
      }
      const rounded = Math.round(value);
      if (!rounded) {
        return "0s";
      }
      const sign = rounded > 0 ? "+" : "-";
      const absValue = Math.abs(rounded);
      if (absValue >= 3600) {
        return `${sign}${(absValue / 3600).toFixed(1)}h`;
      }
      if (absValue >= 60) {
        return `${sign}${Math.round(absValue / 60)}m`;
      }
      return `${sign}${absValue}s`;
    }

    formatTravelTimeIndex(value) {
      const parsed = Number(value);
      if (!Number.isFinite(parsed) || parsed < 0) {
        return "-";
      }
      return `${parsed.toFixed(2)}x`;
    }

    sortDashboardByRisk() {
      const body = this.dashboardTables.get("management");
      if (!body) {
        return;
      }
      const rows = Array.from(body.querySelectorAll("tr"));
      if (rows.length < 2) {
        return;
      }
      const parseLevel = (row) => {
        const level = this.parseRiskValue(row.dataset.riskLevel);
        if (Number.isFinite(level)) {
          return level;
        }
        const cells = Array.from(row.children);
        const fallback = this.parseRiskValue(cells[2]?.textContent);
        return Number.isFinite(fallback) ? fallback : 0;
      };
      const parseSeq = (row) => {
        const raw = row.dataset.seq;
        const seq = Number.parseInt(raw || "", 10);
        if (Number.isFinite(seq)) {
          return seq;
        }
        const cells = Array.from(row.children);
        const fallback = Number.parseInt(cells[0]?.textContent || "", 10);
        return Number.isFinite(fallback) ? fallback : 0;
      };
      rows.sort((a, b) => {
        const riskA = parseLevel(a);
        const riskB = parseLevel(b);
        if (riskA !== riskB) {
          return riskB - riskA;
        }
        return parseSeq(a) - parseSeq(b);
      });
      rows.forEach((row) => body.appendChild(row));
    }

    updateHistoryTable(force = false) {
      if (!force && this.dashboardActiveTab !== "history") {
        return;
      }
      const body = this.dashboardTables.get("history");
      if (!body) {
        return;
      }
      body.innerHTML = "";
      if (!this.dashboardData || this.dashboardData.size === 0) {
        return;
      }
      const items = [];
      this.dashboardData.forEach((entry, name) => {
        const times = this.dashboardTimes.get(name) || {};
        const metrics =
          this.dashboardFlightMetrics && this.dashboardFlightMetrics.get(name)
            ? this.dashboardFlightMetrics.get(name)
            : {};
        const std_s = Number.isFinite(metrics && metrics.std_s)
          ? Number(metrics.std_s)
          : Number.isFinite(times.atd_s)
            ? Number(times.atd_s)
            : null;
        const ata_s = Number.isFinite(metrics && metrics.ata_s)
          ? Number(metrics.ata_s)
          : Number.isFinite(times.ata_s)
            ? Number(times.ata_s)
            : null;
        items.push({
          name,
          entry,
          metrics,
          std_s,
          ata_s,
        });
      });
      items.sort((a, b) => {
        const aTime = a.std_s ?? -1;
        const bTime = b.std_s ?? -1;
        if (aTime !== bTime) {
          return bTime - aTime;
        }
        return String(a.name).localeCompare(String(b.name));
      });
      const columnCount = this.getDashboardColumnCount(body);
      items.forEach((item, index) => {
        const sourceRow = item.entry && item.entry.row ? item.entry.row : null;
        const cells = sourceRow ? Array.from(sourceRow.children) : [];
        const cachedValues =
          item.entry && Array.isArray(item.entry.values) ? item.entry.values : [];
        const readCell = (cellIndex, fallback = "-") => {
          if (cells[cellIndex]) {
            return String(cells[cellIndex].textContent || "");
          }
          if (cachedValues[cellIndex] != null) {
            return String(cachedValues[cellIndex]);
          }
          return fallback;
        };
        const num = readCell(0, String(index + 1));
        const name = readCell(1, item.name);
        const risk = readCell(2, "0");
        const reason = readCell(3, "-");
        const speed = readCell(4, "-");
        const battery = readCell(5, "-");
        const heading = readCell(6, "-");
        const position = readCell(7, "-");
        const mode = readCell(8, "-");
        const altitude = readCell(9, "-");
        const from = readCell(10, "-");
        const destination = readCell(11, "-");
        const route = readCell(12, "-");
        const metrics = item.metrics || {};
        const std_s = Number.isFinite(metrics.std_s) ? Number(metrics.std_s) : item.std_s;
        const sta_s = Number.isFinite(metrics.sta_s) ? Number(metrics.sta_s) : null;
        const eta_s = Number.isFinite(metrics.eta_s) ? Number(metrics.eta_s) : null;
        const ata_s = Number.isFinite(metrics.ata_s) ? Number(metrics.ata_s) : item.ata_s;
        const delay_s = Number.isFinite(metrics.delay_s)
          ? Number(metrics.delay_s)
          : Number.isFinite(eta_s) && Number.isFinite(sta_s)
            ? Number(eta_s) - Number(sta_s)
            : null;
        const tti = Number.isFinite(metrics.tti) ? Number(metrics.tti) : null;
        const std = this.formatDashboardTime(std_s);
        const sta = this.formatDashboardTime(sta_s);
        const eta = this.formatDashboardTime(eta_s);
        const ata =
          Number.isFinite(ata_s) && ata_s > 0 ? this.formatDashboardTime(ata_s) : "-";
        const delay = this.formatSignedDuration(delay_s);
        const ttiText = this.formatTravelTimeIndex(tti);
        const values = [
          num,
          std,
          sta,
          eta,
          ata,
          delay,
          ttiText,
          name,
          risk,
          reason,
          speed,
          battery,
          heading,
          position,
          mode,
          altitude,
          from,
          destination,
          route,
        ];
        const fallbackRiskLevel = this.parseRiskValue(risk);
        const riskLevel = sourceRow
          ? Number.parseInt(sourceRow.dataset.riskLevel || "", 10)
          : Number.isFinite(fallbackRiskLevel)
            ? fallbackRiskLevel
            : 0;
        const row = this.createDashboardRow(
          this.normalizeDashboardRow(values, columnCount),
          name,
          Number.isFinite(riskLevel) ? riskLevel : 0,
        );
        if (sourceRow && sourceRow.classList.contains("is-ended")) {
          row.classList.add("is-ended");
        }
        if (sourceRow && sourceRow.classList.contains("is-failed")) {
          row.classList.add("is-failed");
        }
        body.appendChild(row);
      });
    }

    createDashboardRow(values, name, riskLevel) {
      const row = document.createElement("tr");
      row.className = "dashboard-row";
      if (name) {
        row.dataset.name = name;
      }
      if (Number.isFinite(riskLevel)) {
        row.dataset.riskLevel = String(riskLevel);
      }
      values.forEach((value) => {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.appendChild(cell);
      });
      if (name) {
        row.addEventListener(
          "pointerdown",
          (event) => {
          if (row.classList.contains("is-ended") || row.classList.contains("is-failed")) {
            return;
          }
          if (event && typeof event.button === "number" && event.button !== 0) {
            return;
          }
          if (event) {
            event.preventDefault();
            event.stopPropagation();
          }
          this.setDashboardSelection(name);
          const entry =
            this.trafficByName && typeof this.trafficByName.get === "function"
              ? this.trafficByName.get(name)
              : null;
          if (entry && typeof this.focusTrafficByName === "function") {
            this.focusTrafficByName(name);
          } else {
            this.focusTrafficFromRow(row, name);
          }
          },
          { capture: true },
        );
      }
      return row;
    }

    focusTrafficFromRow(row, name) {
      if (!row) {
        return;
      }
      const cells = Array.from(row.children);
      const table = row.closest("table");
      const headerIndex = new Map();
      if (table) {
        const headers = Array.from(table.querySelectorAll("thead th"));
        headers.forEach((header, index) => {
          const label = String(header.textContent || "").trim().toLowerCase();
          if (label) {
            headerIndex.set(label, index);
          }
        });
      }
      const indexFor = (label, fallback = -1) => {
        const key = String(label || "").trim().toLowerCase();
        if (headerIndex.has(key)) {
          return headerIndex.get(key);
        }
        return fallback;
      };
      const getCellText = (index) =>
        index >= 0 && cells[index] ? String(cells[index].textContent || "") : "";
      const getNumber = (value) => {
        const match = String(value || "").match(/-?\d+(?:\.\d+)?/);
        return match ? Number.parseFloat(match[0]) : NaN;
      };
      const getPosition = (value) => {
        const match = String(value || "").match(/-?\d+(?:\.\d+)?/g);
        if (!match || match.length < 2) {
          return null;
        }
        const lat = Number.parseFloat(match[0]);
        const lon = Number.parseFloat(match[1]);
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
          return null;
        }
        return [lon, lat];
      };
      const position = getPosition(getCellText(indexFor("position", 7)));
      if (!position || !this.map) {
        this.notifyFlightSelection(name);
        return;
      }
      const riskRaw = getCellText(indexFor("risk", 2)) || "0";
      const riskReason = String(getCellText(indexFor("reason", 3))).trim();
      const riskLevel = Number.parseInt(row.dataset.riskLevel || "", 10);
      const heading = getNumber(getCellText(indexFor("hdg", 6)));
      const speed = getNumber(getCellText(indexFor("speed", 4)));
      const battery = getNumber(getCellText(indexFor("battery", 5)));
      const altitude = getNumber(getCellText(indexFor("altitude", 9)));
      const mode = String(getCellText(indexFor("mode", 8))).trim();
      const from = String(getCellText(indexFor("from", 10))).trim();
      const to = String(getCellText(indexFor("destination", 11))).trim();
      const routeText = String(getCellText(indexFor("route", 12))).trim();
      const routeParts = routeText.split("->").map((part) => part.trim());
      const routeFrom = routeParts.length > 1 ? routeParts[0] : "";
      const routeTo = routeParts.length > 1 ? routeParts[1] : "";
      const digits = String(name || "").match(/\d+/g);
      const flightId = digits ? Number.parseInt(digits.join(""), 10) : null;
      const props = {
        name,
        from,
        to,
        route_from: routeFrom,
        route_to: routeTo,
        risk: String(riskRaw || "0").trim(),
        risk_level: Number.isFinite(riskLevel) ? riskLevel : 0,
        risk_reason: riskReason,
        speed_mps: Number.isFinite(speed) ? speed : null,
        battery_pct: Number.isFinite(battery) ? battery : null,
        altitude_m: Number.isFinite(altitude) ? altitude : null,
        mode,
        heading: Number.isFinite(heading) ? heading : null,
      };
      if (Number.isFinite(flightId) && typeof this.setTrafficSelectedState === "function") {
        this.setTrafficSelectedState(flightId);
      }
      this.map.easeTo({ center: position, duration: 700 });
      if (typeof this.showTrafficPopup === "function") {
        this.showTrafficPopup(props, position, flightId);
      }
      this.notifyFlightSelection(name);
    }

    addDashboardRows(rows) {
      const body = this.dashboardTables.get("management");
      if (!body || !Array.isArray(rows)) {
        return;
      }
      const columnCount = this.getDashboardColumnCount(body);
      rows.forEach((row) => {
        if (!Array.isArray(row) || row.length === 0) {
          return;
        }
        const values = row.map((value) => String(value ?? ""));
        const expectedColumns = Math.max(0, columnCount - 1);
        if (expectedColumns && values.length === expectedColumns - 1) {
          values.splice(2, 0, "-");
        }
        const name = values[0] || "";
        const riskLevel = this.parseRiskValue(values[1]);
        const seq = String((this.dashboardSequence += 1));
        const cells = [seq, ...values];
        const normalized = this.normalizeDashboardRow(cells, columnCount);
        const element = this.createDashboardRow(normalized, name, riskLevel);
        element.dataset.seq = seq;
        body.appendChild(element);
        if (name) {
          this.dashboardData.set(name, { row: element, values: normalized });
          const spawnTime = this.getDashboardTimestamp();
          this.dashboardTimes.set(name, {
            atd_s: Number.isFinite(spawnTime) ? Number(spawnTime) : null,
            ata_s: null,
          });
          if (this.dashboardFlightMetrics) {
            this.dashboardFlightMetrics.delete(name);
          }
        }
      });
      this.updateSimStatsFromDashboard();
      this.updateHistoryTable();
    }

    addDashboardFailureRows(rows) {
      const body = this.dashboardTables.get("failed");
      if (!body || !Array.isArray(rows)) {
        return;
      }
      const columnCount = this.getDashboardColumnCount(body);
      rows.forEach((row) => {
        if (!Array.isArray(row) || row.length === 0) {
          return;
        }
        const values = row.map((value) => String(value ?? ""));
        const seq = String((this.dashboardFailureSequence += 1));
        const cells = [seq, ...values];
        const normalized = this.normalizeDashboardRow(cells, columnCount);
        const name = values[1] ? String(values[1]) : "";
        const element = this.createDashboardRow(normalized, name, 0);
        element.classList.add("is-failed");
        body.appendChild(element);
        if (this.dashboardFailureRows) {
          this.dashboardFailureRows.push(normalized);
        }
      });
    }

    applyDashboardStatus(statuses) {
      if (!Array.isArray(statuses) || !statuses.length) {
        return;
      }
      const body = this.dashboardTables.get("management");
      if (!body) {
        return;
      }
      statuses.forEach((status) => {
        const name = status && status.name ? String(status.name) : "";
        if (!name) {
          return;
        }
        const entry = this.dashboardData.get(name);
        const row =
          entry && entry.row
            ? entry.row
            : body.querySelector(`tr[data-name="${CSS.escape(name)}"]`);
        if (!row) {
          return;
        }
        const mode = status && status.mode ? String(status.mode) : "";
        const isFailed = mode === "failed";
        const isEnded = mode === "ended" || isFailed;
        const cells = Array.from(row.children);
        if (cells[3] && status && status.reason) {
          cells[3].textContent = String(status.reason);
        }
        if (cells[4]) {
          const speed = Number(status.speed_mps);
          cells[4].textContent = Number.isFinite(speed) ? `${speed.toFixed(1)} m/s` : "-";
        }
        if (cells[5]) {
          const battery = Number(status.battery_pct);
          if (Number.isFinite(battery)) {
            cells[5].textContent = `${battery.toFixed(0)}%`;
          }
        }
        if (cells[8]) {
          cells[8].textContent = mode || "-";
          row.classList.toggle("is-ended", isEnded);
          row.classList.toggle("is-failed", isFailed);
        }
        if (cells[9]) {
          const altitude = Number(status.altitude_m);
          cells[9].textContent = Number.isFinite(altitude) ? `${Math.round(altitude)} m` : "-";
        }
        if (entry) {
          entry.values = cells.map((cell) => String(cell.textContent || ""));
        }
        if (name) {
          this.mergeDashboardFlightMetrics(name, status);
          const timeEntry = this.dashboardTimes.get(name) || {};
          const nowStamp = this.getDashboardTimestamp();
          if (!Number.isFinite(timeEntry.atd_s)) {
            if (Number.isFinite(nowStamp)) {
              timeEntry.atd_s = Number(nowStamp);
            }
          }
          if ((isEnded || isFailed) && !Number.isFinite(timeEntry.ata_s)) {
            if (Number.isFinite(nowStamp) && nowStamp > 0) {
              timeEntry.ata_s = Number(nowStamp);
            }
          }
          this.dashboardTimes.set(name, timeEntry);
        }
        if ((isEnded || isFailed) && row.parentNode) {
          row.parentNode.removeChild(row);
          if (entry) {
            entry.row = null;
          }
        }
      });
      this.updateSimStatsFromDashboard();
      this.updateHistoryTable();
    }

    updateDashboardFromPositions(positions) {
      if (!Array.isArray(positions)) {
        return;
      }
      const inflight = [];
      const takeoff = [];
      const activeNames = new Set();
      const riskCounts = { 0: 0, 1: 0, 2: 0, 3: 0 };
      const body = this.dashboardTables.get("management");
      const columnCount = body ? this.getDashboardColumnCount(body) : 0;
      positions.forEach((item) => {
        const mode = item && item.mode ? String(item.mode) : "";
        const isFailed = mode === "failed";
        const isEnded = mode === "ended" || isFailed;
        const riskLevelRaw = Number.isFinite(item.risk_level) ? Number(item.risk_level) : 0;
        const riskRaw = item && item.risk != null ? String(item.risk).trim() : "";
        const riskValue = this.parseRiskValue(riskRaw);
        const riskResolved = Number.isFinite(riskValue)
          ? Math.max(riskLevelRaw, riskValue)
          : riskLevelRaw;
        const riskLabel = riskResolved > 0 ? String(riskResolved) : riskRaw || "0";
        if (!isEnded && riskCounts[riskResolved] != null) {
          riskCounts[riskResolved] += 1;
        }
        if (mode === "takeoff") {
          takeoff.push(item);
        } else if (mode && !isEnded) {
          inflight.push(item);
        }

        const name = item && item.name ? String(item.name) : "";
        if (name) {
          activeNames.add(name);
          this.mergeDashboardFlightMetrics(name, item);
          let entry = this.dashboardData.get(name);
          let row = entry && entry.row ? entry.row : null;
          if (!row && body && !isEnded) {
            const seq = String((this.dashboardSequence += 1));
            const values = this.buildDashboardRowValues(item, Number(seq));
            const normalized = this.normalizeDashboardRow(values, columnCount);
            row = this.createDashboardRow(normalized, name, riskResolved);
            row.dataset.seq = seq;
            body.appendChild(row);
            entry = { row, values: normalized };
            this.dashboardData.set(name, entry);
          }
          if (row) {
            const cells = Array.from(row.children);
            if (cells[2]) {
              cells[2].textContent = riskLabel;
            }
            if (cells[3]) {
              const reason = item && item.risk_reason ? String(item.risk_reason) : "-";
              cells[3].textContent = reason || "-";
            }
            if (cells[4]) {
              const speed = Number(item && item.speed_mps);
              cells[4].textContent = Number.isFinite(speed) ? `${speed.toFixed(1)} m/s` : "-";
            }
            if (cells[5]) {
              const battery = Number(item && item.battery_pct);
              cells[5].textContent = Number.isFinite(battery) ? `${battery.toFixed(0)}%` : "-";
            }
            if (cells[6]) {
              const heading = Number(item && item.heading_deg);
              cells[6].textContent = Number.isFinite(heading) ? `${Math.round(heading)} deg` : "-";
            }
            if (cells[7]) {
              cells[7].textContent =
                Number.isFinite(item && item.lat) && Number.isFinite(item && item.lon)
                  ? `${Number(item.lat).toFixed(5)}, ${Number(item.lon).toFixed(5)}`
                  : "-";
            }
            if (cells[8]) {
              cells[8].textContent = mode || "-";
              row.classList.toggle("is-ended", isEnded);
              row.classList.toggle("is-failed", isFailed);
            }
            if (cells[9]) {
              const altitude = Number(item && item.altitude_m);
              cells[9].textContent = Number.isFinite(altitude) ? `${Math.round(altitude)} m` : "-";
            }
            if (Number.isFinite(riskResolved)) {
              row.dataset.riskLevel = String(riskResolved);
            }
            if (entry) {
              entry.values = cells.map((cell) => String(cell.textContent || ""));
            }
          }
          const timeEntry = this.dashboardTimes.get(name) || {};
          const nowStamp = this.getDashboardTimestamp();
          if (!Number.isFinite(timeEntry.atd_s)) {
            if (Number.isFinite(nowStamp)) {
              timeEntry.atd_s = Number(nowStamp);
            }
          }
          if (isEnded && !Number.isFinite(timeEntry.ata_s)) {
            if (Number.isFinite(nowStamp) && nowStamp > 0) {
              timeEntry.ata_s = Number(nowStamp);
            }
          }
          this.dashboardTimes.set(name, timeEntry);
          if (isEnded && row && row.parentNode) {
            row.parentNode.removeChild(row);
            if (entry) {
              entry.row = null;
            }
          }
        }
      });

      // Ended status can be missed between web polls. If a tracked flight
      // disappears from current positions, mark it as completed.
      const inferredDoneTime = this.getDashboardTimestamp();
      if (this.dashboardData && this.dashboardData.size) {
        this.dashboardData.forEach((entry, name) => {
          if (!name || activeNames.has(name)) {
            return;
          }
          const timeEntry = this.dashboardTimes.get(name) || {};
          if (!Number.isFinite(timeEntry.atd_s) || Number.isFinite(timeEntry.ata_s)) {
            return;
          }
          if (!Number.isFinite(inferredDoneTime) || inferredDoneTime <= 0) {
            return;
          }
          timeEntry.ata_s = inferredDoneTime;
          this.dashboardTimes.set(name, timeEntry);
          const row = entry && entry.row ? entry.row : null;
          if (row && row.parentNode) {
            row.classList.add("is-ended");
            row.parentNode.removeChild(row);
          }
          if (entry) {
            entry.row = null;
          }
        });
      }

      this.renderDashboardTable("inflight", inflight);
      this.renderDashboardTable("takeoff", takeoff);

      const badges = document.querySelectorAll("[data-risk-count]");
      badges.forEach((badge) => {
        const key = Number.parseInt(badge.dataset.riskCount || "", 10);
        if (Number.isFinite(key) && riskCounts[key] != null) {
          badge.textContent = String(riskCounts[key]);
        }
      });
      this.updateWarningSoundFromRiskCounts(riskCounts);

      const rawTimeValue =
        typeof this.getDashboardTimestamp === "function"
          ? this.getDashboardTimestamp()
          : this.lastSimTime_s;
      const timeValue = Number.isFinite(rawTimeValue) ? rawTimeValue : 0;
      const lastTime = this.riskTrendLastTime;
      if (Number.isFinite(lastTime) && timeValue === lastTime && this.riskTrendData.times.length) {
        const lastIndex = this.riskTrendData.times.length - 1;
        this.riskTrendData.level1[lastIndex] = riskCounts[1] || 0;
        this.riskTrendData.level2[lastIndex] = riskCounts[2] || 0;
        this.riskTrendData.level3[lastIndex] = riskCounts[3] || 0;
        if (this.riskTrendHistory && this.riskTrendHistory.times.length) {
          const historyIndex = this.riskTrendHistory.times.length - 1;
          this.riskTrendHistory.level1[historyIndex] = riskCounts[1] || 0;
          this.riskTrendHistory.level2[historyIndex] = riskCounts[2] || 0;
          this.riskTrendHistory.level3[historyIndex] = riskCounts[3] || 0;
        }
      } else {
        this.riskTrendData.times.push(timeValue);
        this.riskTrendData.level1.push(riskCounts[1] || 0);
        this.riskTrendData.level2.push(riskCounts[2] || 0);
        this.riskTrendData.level3.push(riskCounts[3] || 0);
        if (this.riskTrendHistory) {
          this.riskTrendHistory.times.push(timeValue);
          this.riskTrendHistory.level1.push(riskCounts[1] || 0);
          this.riskTrendHistory.level2.push(riskCounts[2] || 0);
          this.riskTrendHistory.level3.push(riskCounts[3] || 0);
        }
        if (this.riskTrendData.times.length > this.riskTrendDisplayPoints) {
          this.riskTrendData.times.shift();
          this.riskTrendData.level1.shift();
          this.riskTrendData.level2.shift();
          this.riskTrendData.level3.shift();
        }
        this.riskTrendLastTime = timeValue;
      }
      this.updateRiskTrend();
      this.updateSimStatsFromDashboard(positions);
      this.sortDashboardByRisk();
      this.updateHistoryTable();
    }

    renderDashboardTable(key, rows) {
      const body = this.dashboardTables.get(key);
      if (!body) {
        return;
      }
      body.innerHTML = "";
      if (!Array.isArray(rows) || rows.length === 0) {
        return;
      }
      const columnCount = this.getDashboardColumnCount(body);
      rows.forEach((item, index) => {
        const values = this.buildDashboardRowValues(item, index + 1);
        const riskLevel = Number.isFinite(item.risk_level) ? Number(item.risk_level) : 0;
        const row = this.createDashboardRow(
          this.normalizeDashboardRow(values, columnCount),
          item && item.name ? String(item.name) : "",
          riskLevel,
        );
        body.appendChild(row);
      });
    }

    buildDashboardRowValues(item, index) {
      const name = item && item.name ? String(item.name) : "";
      const riskLevel = Number.isFinite(item && item.risk_level)
        ? Number(item.risk_level)
        : 0;
      const riskRaw = item && item.risk != null ? String(item.risk).trim() : "";
      const riskValue = this.parseRiskValue(riskRaw);
      const riskResolved = Number.isFinite(riskValue) ? Math.max(riskLevel, riskValue) : riskLevel;
      const risk = riskResolved > 0 ? String(riskResolved) : riskRaw || "0";
      const riskReason = item && item.risk_reason ? String(item.risk_reason) : "-";
      const speed = Number(item && item.speed_mps);
      const speedText = Number.isFinite(speed) ? `${speed.toFixed(1)} m/s` : "-";
      const battery = Number(item && item.battery_pct);
      const batteryText = Number.isFinite(battery) ? `${battery.toFixed(0)}%` : "-";
      const heading = Number(item && item.heading_deg);
      const headingText = Number.isFinite(heading) ? `${Math.round(heading)}°` : "-";
      const position =
        Number.isFinite(item && item.lat) && Number.isFinite(item && item.lon)
          ? `${Number(item.lat).toFixed(5)}, ${Number(item.lon).toFixed(5)}`
          : "-";
      const mode = item && item.mode ? String(item.mode) : "-";
      const altitude = Number(item && item.altitude_m);
      const altitudeText = Number.isFinite(altitude) ? `${Math.round(altitude)} m` : "-";
      const origin = item && item.from ? String(item.from) : "-";
      const destination = item && item.to ? String(item.to) : "-";
      const route =
        item && item.route_from && item.route_to
          ? `${item.route_from} -> ${item.route_to}`
          : "-";
      return [
        String(index),
        name,
        risk,
        riskReason,
        speedText,
        batteryText,
        headingText,
        position,
        mode,
        altitudeText,
        origin,
        destination,
        route,
      ];
    }

    normalizeDashboardRow(values, columnCount) {
      if (!columnCount) {
        return values;
      }
      const normalized = values.slice(0, columnCount);
      while (normalized.length < columnCount) {
        normalized.push("");
      }
      return normalized;
    }

    getDashboardColumnCount(body) {
      const table = body ? body.closest("table") : null;
      if (!table) {
        return 0;
      }
      const headers = table.querySelectorAll("thead th");
      return headers.length ? headers.length : 0;
    }

    parseRiskValue(value) {
      if (value == null) {
        return Number.NaN;
      }
      const text = String(value).trim();
      if (!text) {
        return Number.NaN;
      }
      const match = text.match(/-?\d+/);
      if (!match) {
        return Number.NaN;
      }
      const parsed = Number.parseInt(match[0], 10);
      return Number.isFinite(parsed) ? parsed : Number.NaN;
    }

    initRiskTrend() {
      if (!this.riskTrendCanvas || this.riskTrendInitialized) {
        return;
      }
      this.riskTrendInitialized = true;
      this.resizeRiskTrendCanvas();
      window.addEventListener("resize", () => this.resizeRiskTrendCanvas());
      if (this.riskTrendExportPngButton) {
        this.riskTrendExportPngButton.addEventListener("click", () =>
          this.exportRiskTrendPng(),
        );
      }
      if (this.riskTrendExportCsvButton) {
        this.riskTrendExportCsvButton.addEventListener("click", () =>
          this.exportRiskTrendCsv(),
        );
      }
      if (Array.isArray(this.riskTrendButtons)) {
        this.riskTrendButtons.forEach((button) => {
          button.addEventListener("click", () => {
            const level = Number.parseInt(button.dataset.riskLevel || "", 10);
            if (!Number.isFinite(level)) {
              return;
            }
            const next = !this.riskTrendLevels[level];
            this.riskTrendLevels[level] = next;
            button.classList.toggle("is-active", next);
            this.updateRiskTrend();
          });
        });
      }
      this.updateRiskTrend();
    }

    initWarningSound() {
      if (this.warningSoundContext) {
        return;
      }
      this.ensureWarningSoundContext();
      document.addEventListener(
        "pointerdown",
        () => {
          this.primeWarningSound();
        },
        { once: true },
      );
    }

    ensureWarningSoundContext() {
      if (this.warningSoundContext) {
        return this.warningSoundContext;
      }
      const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextCtor) {
        return null;
      }
      this.warningSoundContext = new AudioContextCtor();
      return this.warningSoundContext;
    }

    primeWarningSound() {
      if (this.warningSoundPrimed) {
        return;
      }
      const ctx = this.ensureWarningSoundContext();
      if (!ctx) {
        return;
      }
      if (ctx.state === "suspended") {
        const promise = ctx.resume();
        if (promise && typeof promise.catch === "function") {
          promise.catch(() => {});
        }
      }
      this.warningSoundPrimed = true;
    }

    updateWarningSoundFromRiskCounts(riskCounts) {
      const level3 = riskCounts && Number(riskCounts[3]) > 0;
      const level2 = riskCounts && Number(riskCounts[2]) > 0;
      const level1 = riskCounts && Number(riskCounts[1]) > 0;
      const nextLevel = level3 ? 3 : level2 ? 2 : level1 ? 1 : 0;
      this.setWarningSoundLevel(nextLevel);
    }

    setWarningSoundLevel(level) {
      const nextLevel = Number.isFinite(level) ? Math.max(0, Math.min(3, level)) : 0;
      if (nextLevel === this.warningSoundLevel) {
        return;
      }
      this.warningSoundLevel = nextLevel;
      if (this.soundMuted) {
        this.stopWarningSoundLoop();
        return;
      }
      if (nextLevel <= 0) {
        this.stopWarningSoundLoop();
        return;
      }
      if (!this.warningSoundActive) {
        this.startWarningSoundLoop();
        return;
      }
      this.scheduleWarningSoundTick(0);
    }

    startWarningSoundLoop() {
      if (!this.warningSoundContext) {
        this.initWarningSound();
      }
      if (this.soundMuted) {
        this.stopWarningSoundLoop();
        return;
      }
      if (this.warningSoundActive) {
        return;
      }
      this.warningSoundActive = true;
      this.scheduleWarningSoundTick(0);
    }

    stopWarningSoundLoop() {
      this.warningSoundActive = false;
      if (this.warningSoundTimer) {
        window.clearTimeout(this.warningSoundTimer);
        this.warningSoundTimer = null;
      }
    }

    getWarningSoundIntervalMs(level) {
      const base =
        this.warningSoundIntervalsMs && Number(this.warningSoundIntervalsMs[level]);
      const fallback = level >= 3 ? 700 : level === 2 ? 1200 : 2000;
      const target = Number.isFinite(base) ? base : fallback;
      return Math.max(target, this.warningSoundDurationMs + 100);
    }

    scheduleWarningSoundTick(delayMs) {
      if (this.warningSoundTimer) {
        window.clearTimeout(this.warningSoundTimer);
      }
      this.warningSoundTimer = window.setTimeout(
        () => this.handleWarningSoundTick(),
        Math.max(0, delayMs),
      );
    }

    handleWarningSoundTick() {
      if (!this.warningSoundActive) {
        return;
      }
      if (this.soundMuted) {
        this.stopWarningSoundLoop();
        return;
      }
      const level = this.warningSoundLevel;
      if (level <= 0) {
        this.stopWarningSoundLoop();
        return;
      }
      this.playWarningBeep();
      this.scheduleWarningSoundTick(this.getWarningSoundIntervalMs(level));
    }

    playWarningBeep() {
      if (!this.warningSoundContext) {
        this.initWarningSound();
      }
      const ctx = this.warningSoundContext;
      if (!ctx) {
        return;
      }
      if (ctx.state === "suspended") {
        return;
      }
      const now = ctx.currentTime;
      const duration = Math.max(0.03, this.warningSoundDurationMs / 1000);
      const attack = Math.max(0, this.warningSoundAttackMs / 1000);
      const release = Math.max(0, this.warningSoundReleaseMs / 1000);
      const sustainEnd = Math.max(now + attack, now + duration - release);

      const gain = ctx.createGain();
      gain.gain.setValueAtTime(0, now);
      gain.gain.linearRampToValueAtTime(this.warningSoundVolume, now + attack);
      gain.gain.setValueAtTime(this.warningSoundVolume, sustainEnd);
      gain.gain.linearRampToValueAtTime(0, now + duration);

      const osc = ctx.createOscillator();
      osc.type = "sine";
      osc.frequency.setValueAtTime(this.warningSoundFreqHz, now);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + duration + 0.02);
      osc.addEventListener(
        "ended",
        () => {
          osc.disconnect();
          gain.disconnect();
        },
        { once: true },
      );
    }

    clearRiskTrendCanvas() {
      if (!this.riskTrendCtx || !this.riskTrendCanvas) {
        return;
      }
      const ctx = this.riskTrendCtx;
      ctx.save();
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, this.riskTrendCanvas.width, this.riskTrendCanvas.height);
      ctx.restore();
    }

    queueRiskTrendResize() {
      if (this.riskTrendResizeQueued) {
        return;
      }
      this.riskTrendResizeQueued = true;
      const run = () => {
        this.resizeRiskTrendCanvas();
        this.riskTrendResizeQueued = false;
      };
      if (window.requestAnimationFrame) {
        window.requestAnimationFrame(run);
      } else {
        window.setTimeout(run, 0);
      }
      window.setTimeout(run, 320);
    }

    resizeRiskTrendCanvas() {
      if (!this.riskTrendCanvas) {
        return;
      }
      const parent = this.riskTrendCanvas.parentElement;
      const rect = parent ? parent.getBoundingClientRect() : null;
      if (!rect) {
        return;
      }
      if (!Number.isFinite(rect.width) || !Number.isFinite(rect.height)) {
        return;
      }
      if (rect.width < 10 || rect.height < 10) {
        this.clearRiskTrendCanvas();
        return;
      }
      const ratio = window.devicePixelRatio || 1;
      this.riskTrendCanvas.width = Math.max(1, Math.floor(rect.width * ratio));
      this.riskTrendCanvas.height = Math.max(1, Math.floor(rect.height * ratio));
      if (this.riskTrendCtx) {
        this.riskTrendCtx.setTransform(ratio, 0, 0, ratio, 0, 0);
      }
      this.updateRiskTrend();
    }

    updateRiskTrend() {
      if (!this.riskTrendCtx || !this.riskTrendCanvas) {
        return;
      }
      const ctx = this.riskTrendCtx;
      const ratio = window.devicePixelRatio || 1;
      const width = this.riskTrendCanvas.width / ratio;
      const height = this.riskTrendCanvas.height / ratio;
      if (!Number.isFinite(width) || !Number.isFinite(height) || width < 10 || height < 10) {
        this.queueRiskTrendResize();
        return;
      }
      ctx.clearRect(0, 0, width, height);
      const data = this.riskTrendData || { times: [], level1: [], level2: [], level3: [] };
      const times = Array.isArray(data.times) ? data.times : [];
      const level1 = Array.isArray(data.level1) ? data.level1 : [];
      const level2 = Array.isArray(data.level2) ? data.level2 : [];
      const level3 = Array.isArray(data.level3) ? data.level3 : [];
      const count = times.length;
      const uiScaleValue = Number.parseFloat(
        getComputedStyle(document.documentElement).getPropertyValue("--ui-scale"),
      );
      const uiScale = Number.isFinite(uiScaleValue) ? uiScaleValue : 1;
      const padding = {
        left: Math.max(28, 28 * uiScale),
        right: Math.max(6, 6 * uiScale),
        top: Math.max(8, 8 * uiScale),
        bottom: Math.max(18, 18 * uiScale),
      };
      const plotWidth = width - padding.left - padding.right;
      const plotHeight = height - padding.top - padding.bottom;
      if (plotWidth <= 0 || plotHeight <= 0) {
        return;
      }
      const seriesValues = []
        .concat(level1, level2, level3)
        .filter((value) => Number.isFinite(value));
      const maxValue = Math.max(1, ...seriesValues);
      const desiredTicks = 4;
      const rawStep = maxValue / desiredTicks;
      const magnitude = Math.pow(10, Math.floor(Math.log10(Math.max(rawStep, 1))));
      const stepCandidates = [1, 2, 5, 10].map((base) => base * magnitude);
      const step =
        stepCandidates.find((value) => value >= rawStep) || stepCandidates[stepCandidates.length - 1];
      const maxTick = Math.max(step, Math.ceil(maxValue / step) * step);

      ctx.save();
      ctx.strokeStyle = "#e5e7eb";
      ctx.lineWidth = 1;
      for (let value = 0; value <= maxTick; value += step) {
        const y = padding.top + plotHeight - (value / maxTick) * plotHeight;
        ctx.beginPath();
        ctx.moveTo(padding.left, y);
        ctx.lineTo(padding.left + plotWidth, y);
        ctx.stroke();
      }

      ctx.strokeStyle = "#cfd3da";
      ctx.beginPath();
      ctx.moveTo(padding.left, padding.top);
      ctx.lineTo(padding.left, padding.top + plotHeight);
      ctx.lineTo(padding.left + plotWidth, padding.top + plotHeight);
      ctx.stroke();

      ctx.fillStyle = "#6b7280";
      ctx.font = `600 ${Math.max(9, 9 * uiScale)}px system-ui`;
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      for (let value = 0; value <= maxTick; value += step) {
        const y = padding.top + plotHeight - (value / maxTick) * plotHeight;
        ctx.fillText(String(value), padding.left - 6 * uiScale, y);
      }

      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      if (count > 1) {
        const labelCount = Math.min(4, count - 1);
        let lastX = -Infinity;
        for (let i = 0; i <= labelCount; i += 1) {
          const index = Math.round((i / labelCount) * (count - 1));
          const time_s = times[index];
          const label =
            this.formatDashboardTime && Number.isFinite(time_s)
              ? this.formatDashboardTime(time_s)
              : this.formatTime(time_s || 0);
          const x = padding.left + (index / (count - 1)) * plotWidth;
          if (x - lastX < 32 * uiScale) {
            continue;
          }
          lastX = x;
          ctx.fillText(label, x, padding.top + plotHeight + 4 * uiScale);
        }
      }
      ctx.restore();

      if (count < 2) {
        ctx.fillStyle = "#8b94a7";
        ctx.font = `600 ${Math.max(10, 10 * uiScale)}px system-ui`;
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.fillText("No data yet", padding.left + 6 * uiScale, height / 2);
        return;
      }

      const plot = (series, color) => {
        if (!Array.isArray(series) || !series.length) {
          return;
        }
        ctx.strokeStyle = color;
        ctx.lineWidth = Math.max(1.5, 2 * uiScale);
        ctx.lineJoin = "round";
        ctx.lineCap = "round";
        ctx.beginPath();
        const seriesCount = Math.min(series.length, count);
        for (let index = 0; index < seriesCount; index += 1) {
          const value = Number.isFinite(series[index]) ? series[index] : 0;
          const x = padding.left + (index / (count - 1)) * plotWidth;
          const y = padding.top + plotHeight - (value / maxTick) * plotHeight;
          if (index === 0) {
            ctx.moveTo(x, y);
          } else {
            ctx.lineTo(x, y);
          }
        }
        ctx.stroke();
      };
      if (this.riskTrendLevels[1]) {
        plot(level1, "#ffd60a");
      }
      if (this.riskTrendLevels[2]) {
        plot(level2, "#8b5cf6");
      }
      if (this.riskTrendLevels[3]) {
        plot(level3, "#ff3b30");
      }
    }

    exportRiskTrendPng() {
      if (!this.riskTrendCanvas) {
        return;
      }
      const exportCanvas = document.createElement("canvas");
      exportCanvas.width = this.riskTrendCanvas.width;
      exportCanvas.height = this.riskTrendCanvas.height;
      const exportCtx = exportCanvas.getContext("2d");
      if (!exportCtx) {
        return;
      }
      exportCtx.fillStyle = "#ffffff";
      exportCtx.fillRect(0, 0, exportCanvas.width, exportCanvas.height);
      exportCtx.drawImage(this.riskTrendCanvas, 0, 0);
      const dataUrl = exportCanvas.toDataURL("image/png");
      this.downloadDataUrl("risk_trend.png", dataUrl);
    }

    exportRiskTrendCsv() {
      const rows = [["sim_time_s", "time", "lv1", "lv2", "lv3"]];
      const data =
        this.riskTrendHistory && this.riskTrendHistory.times.length
          ? this.riskTrendHistory
          : this.riskTrendData;
      for (let i = 0; i < data.times.length; i += 1) {
        const time_s = data.times[i];
        const timeLabel =
          this.formatDashboardTime && Number.isFinite(time_s)
            ? this.formatDashboardTime(time_s)
            : this.formatTime(time_s || 0);
        rows.push([
          Number.isFinite(time_s) ? String(Math.round(time_s)) : "",
          timeLabel,
          String(data.level1[i] ?? 0),
          String(data.level2[i] ?? 0),
          String(data.level3[i] ?? 0),
        ]);
      }
      this.downloadCsvFile("risk_trend.csv", rows);
    }

    initHumanInterventionPanel() {
      if (this.humanWorkloadCanvas && !this.humanWorkloadInitialized) {
        this.humanWorkloadInitialized = true;
        this.queueHumanWorkloadResize();
        window.addEventListener("resize", () => this.queueHumanWorkloadResize());
      }
      this.updateHumanWorkloadNote();
      const bindCsv = (button, handler) => {
        if (button) {
          button.addEventListener("click", handler);
        }
      };
      bindCsv(this.humanWorkloadExportCsvButton, () => this.exportHumanWorkloadCsv());
      bindCsv(this.humanSpeedExportCsvButton, () => this.exportHumanEventsCsv("speed"));
      bindCsv(this.humanAirspaceExportCsvButton, () => this.exportHumanEventsCsv("airspace"));
      bindCsv(this.humanEmergencyExportCsvButton, () => this.exportHumanEventsCsv("emergency"));
      this.renderHumanInterventionTables();
    }

    queueHumanWorkloadResize() {
      if (this.humanWorkloadResizeQueued) {
        return;
      }
      this.humanWorkloadResizeQueued = true;
      const run = () => {
        this.resizeHumanWorkloadCanvas();
        this.humanWorkloadResizeQueued = false;
      };
      if (window.requestAnimationFrame) {
        window.requestAnimationFrame(run);
      } else {
        window.setTimeout(run, 0);
      }
      window.setTimeout(run, 320);
    }

    clearHumanWorkloadCanvas() {
      if (!this.humanWorkloadCtx || !this.humanWorkloadCanvas) {
        return;
      }
      const ctx = this.humanWorkloadCtx;
      ctx.save();
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, this.humanWorkloadCanvas.width, this.humanWorkloadCanvas.height);
      ctx.restore();
    }

    resizeHumanWorkloadCanvas() {
      if (!this.humanWorkloadCanvas) {
        return;
      }
      const parent = this.humanWorkloadCanvas.parentElement;
      const rect = parent ? parent.getBoundingClientRect() : null;
      if (!rect) {
        return;
      }
      const cssWidth = rect.width;
      const cssHeight = rect.height;
      if (
        !Number.isFinite(cssWidth) ||
        !Number.isFinite(cssHeight) ||
        cssWidth < 10 ||
        cssHeight < 10
      ) {
        this.clearHumanWorkloadCanvas();
        return;
      }
      const ratio = window.devicePixelRatio || 1;
      const nextWidth = Math.max(1, Math.floor(cssWidth * ratio));
      const nextHeight = Math.max(1, Math.floor(cssHeight * ratio));
      if (
        this.humanWorkloadCanvas.width !== nextWidth ||
        this.humanWorkloadCanvas.height !== nextHeight
      ) {
        this.humanWorkloadCanvas.width = nextWidth;
        this.humanWorkloadCanvas.height = nextHeight;
      }
      if (this.humanWorkloadCtx) {
        this.humanWorkloadCtx.setTransform(ratio, 0, 0, ratio, 0, 0);
      }
      this.updateHumanWorkloadChart();
    }

    updateHumanWorkloadSeries(time_s, force = false) {
      if (!this.humanWorkloadInitialized || !Number.isFinite(time_s)) {
        return;
      }
      const data = this.humanWorkloadData;
      const counts = this.computeHumanWorkload(time_s);
      const updateHistory = () => {
        const history = this.humanWorkloadHistory;
        if (!history) {
          return;
        }
        if (
          this.humanWorkloadHistoryLastTime != null &&
          time_s <= this.humanWorkloadHistoryLastTime
        ) {
          if (
            !force ||
            time_s < this.humanWorkloadHistoryLastTime ||
            !history.times.length
          ) {
            return;
          }
          const lastIndex = history.times.length - 1;
          history.times[lastIndex] = time_s;
          history.total[lastIndex] = counts.total;
          history.speed[lastIndex] = counts.speed;
          history.airspace[lastIndex] = counts.airspace;
          history.emergency[lastIndex] = counts.emergency;
          return;
        }
        this.humanWorkloadHistoryLastTime = time_s;
        history.times.push(time_s);
        history.total.push(counts.total);
        history.speed.push(counts.speed);
        history.airspace.push(counts.airspace);
        history.emergency.push(counts.emergency);
      };
      if (this.humanWorkloadLastTime != null && time_s <= this.humanWorkloadLastTime) {
        if (!force || time_s < this.humanWorkloadLastTime || !data.times.length) {
          return;
        }
        const lastIndex = data.times.length - 1;
        data.times[lastIndex] = time_s;
        data.total[lastIndex] = counts.total;
        data.speed[lastIndex] = counts.speed;
        data.airspace[lastIndex] = counts.airspace;
        data.emergency[lastIndex] = counts.emergency;
        updateHistory();
        this.updateHumanWorkloadChart();
        return;
      }
      this.humanWorkloadLastTime = time_s;
      data.times.push(time_s);
      data.total.push(counts.total);
      data.speed.push(counts.speed);
      data.airspace.push(counts.airspace);
      data.emergency.push(counts.emergency);
      if (data.times.length > this.humanWorkloadDisplayPoints) {
        data.times.shift();
        data.total.shift();
        data.speed.shift();
        data.airspace.shift();
        data.emergency.shift();
      }
      updateHistory();
      this.updateHumanWorkloadChart();
    }

    computeHumanWorkload(time_s) {
      const windowStart = time_s - this.humanWorkloadWindow_s;
      let speed = 0;
      let airspace = 0;
      let emergency = 0;
      for (const event of this.humanInterventionEvents) {
        if (!Number.isFinite(event.time_s) || event.time_s < windowStart) {
          continue;
        }
        if (event.kind === "speed") {
          speed += 1;
        } else if (event.kind === "airspace") {
          airspace += 1;
        } else if (event.kind === "emergency") {
          emergency += 1;
        }
      }
      const total =
        speed * this.humanWorkloadWeights.speed +
        airspace * this.humanWorkloadWeights.airspace +
        emergency * this.humanWorkloadWeights.emergency;
      return { total, speed, airspace, emergency };
    }

    updateHumanWorkloadChart() {
      if (!this.humanWorkloadCtx || !this.humanWorkloadCanvas) {
        return;
      }
      const ctx = this.humanWorkloadCtx;
      const ratio = window.devicePixelRatio || 1;
      const width = this.humanWorkloadCanvas.width / ratio;
      const height = this.humanWorkloadCanvas.height / ratio;
      if (!width || !height || width < 10 || height < 10) {
        this.clearHumanWorkloadCanvas();
        return;
      }
      const uiScaleValue = Number.parseFloat(
        getComputedStyle(document.documentElement).getPropertyValue("--ui-scale"),
      );
      const uiScale = Number.isFinite(uiScaleValue) ? uiScaleValue : 1;
      const padding = Math.max(4, 6 * uiScale);
      const chartHeight = Math.max(1, height - padding * 2);
      ctx.clearRect(0, 0, width, height);
      const data = this.humanWorkloadData;
      const count = data.times.length;
      ctx.strokeStyle = "#e5e7eb";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, height - padding);
      ctx.lineTo(width, height - padding);
      ctx.stroke();
      if (count < 2) {
        ctx.fillStyle = "#8b94a7";
        ctx.font = `600 ${Math.max(10, 10 * uiScale)}px system-ui`;
        ctx.textBaseline = "middle";
        ctx.fillText(this.t("label.no_interventions"), 8, height / 2);
        return;
      }
      const maxValue = Math.max(1, ...data.total);
      ctx.strokeStyle = "#0a84ff";
      ctx.lineWidth = Math.max(1.5, 2 * uiScale);
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      ctx.beginPath();
      data.total.forEach((value, index) => {
        const x = (index / (count - 1)) * width;
        const y = height - padding - (value / maxValue) * chartHeight;
        if (index === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });
      ctx.stroke();
    }

    updateHumanWorkloadNote() {
      if (!this.humanWorkloadNote) {
        return;
      }
      const seconds = Math.max(1, Math.round(this.humanWorkloadWindow_s));
      let windowText = this.t("time.seconds", { count: seconds });
      if (seconds % 60 === 0) {
        const minutes = seconds / 60;
        windowText = this.t("time.minutes", { count: minutes });
      }
      this.humanWorkloadNote.textContent = this.t("label.human_workload_note", {
        window: windowText,
      });
    }

    recordHumanIntervention(kind, payload = {}) {
      if (!kind) {
        return;
      }
      const time_s = this.getDashboardTimestamp
        ? this.getDashboardTimestamp()
        : Number.isFinite(this.lastSimTime_s)
          ? this.lastSimTime_s
          : 0;
      const timeLabel =
        this.formatDashboardTime && Number.isFinite(time_s)
          ? this.formatDashboardTime(time_s)
          : this.formatTime(time_s);
      const entry = { time_s, time_label: timeLabel, ...payload };
      this.humanInterventionEvents.push({ time_s, kind });
      this.trimHumanEvents(this.humanInterventionEvents, this.humanEventLimit);
      if (kind === "speed") {
        this.humanSpeedEvents.push(entry);
        this.trimHumanEvents(this.humanSpeedEvents, this.humanEventLimit);
        if (this.humanSpeedHistory) {
          this.humanSpeedHistory.push(entry);
        }
      } else if (kind === "airspace") {
        this.humanAirspaceEvents.push(entry);
        this.trimHumanEvents(this.humanAirspaceEvents, this.humanEventLimit);
        if (this.humanAirspaceHistory) {
          this.humanAirspaceHistory.push(entry);
        }
      } else if (kind === "emergency") {
        this.humanEmergencyEvents.push(entry);
        this.trimHumanEvents(this.humanEmergencyEvents, this.humanEventLimit);
        if (this.humanEmergencyHistory) {
          this.humanEmergencyHistory.push(entry);
        }
      }
      this.renderHumanInterventionTables();
      this.updateHumanWorkloadSeries(time_s, true);
    }

    trimHumanEvents(list, limit) {
      if (!Array.isArray(list) || !Number.isFinite(limit) || limit <= 0) {
        return;
      }
      if (list.length > limit) {
        list.splice(0, list.length - limit);
      }
    }

    renderHumanInterventionTables() {
      this.renderHumanTable(
        this.humanTableBodies.speed,
        this.humanSpeedEvents,
        6,
        (entry) => {
          const speed = Number(entry.speed_mps);
          const speedText = Number.isFinite(speed) ? speed.toFixed(1) : "-";
          const flightId = Number.isFinite(entry.flight_id) ? String(entry.flight_id) : "-";
          return [
            Number.isFinite(entry.time_s) ? String(Math.round(entry.time_s)) : "-",
            entry.time_label || "-",
            entry.flight_name || "-",
            flightId,
            entry.action || "-",
            speedText,
          ];
        },
        "No speed interventions yet.",
      );
      this.renderHumanTable(
        this.humanTableBodies.airspace,
        this.humanAirspaceEvents,
        6,
        (entry) => {
          return [
            Number.isFinite(entry.time_s) ? String(Math.round(entry.time_s)) : "-",
            entry.time_label || "-",
            entry.action || "-",
            entry.from || "-",
            entry.to || "-",
            entry.kind_label || entry.kind || "-",
          ];
        },
        "No airspace interventions yet.",
      );
      this.renderHumanTable(
        this.humanTableBodies.emergency,
        this.humanEmergencyEvents,
        8,
        (entry) => {
          const lon = Number(entry.lon);
          const lat = Number(entry.lat);
          const alt = Number(entry.alt_m);
          return [
            Number.isFinite(entry.time_s) ? String(Math.round(entry.time_s)) : "-",
            entry.time_label || "-",
            entry.flight_name || "-",
            Number.isFinite(entry.flight_id) ? String(entry.flight_id) : "-",
            entry.target || "-",
            Number.isFinite(lon) ? lon.toFixed(5) : "-",
            Number.isFinite(lat) ? lat.toFixed(5) : "-",
            Number.isFinite(alt) ? alt.toFixed(0) : "-",
          ];
        },
        "No emergency interventions yet.",
      );
    }

    renderHumanTable(body, entries, columnCount, buildRow, emptyLabel) {
      if (!body) {
        return;
      }
      body.innerHTML = "";
      const rows = Array.isArray(entries)
        ? entries.slice(-this.humanTableMaxRows).reverse()
        : [];
      if (!rows.length) {
        const emptyRow = document.createElement("tr");
        const emptyCell = document.createElement("td");
        emptyCell.colSpan = columnCount;
        emptyCell.className = "human-table-empty";
        emptyCell.textContent = emptyLabel || "No activity yet.";
        emptyRow.appendChild(emptyCell);
        body.appendChild(emptyRow);
        return;
      }
      rows.forEach((entry) => {
        const row = document.createElement("tr");
        const values = buildRow(entry);
        values.forEach((value) => {
          const cell = document.createElement("td");
          cell.textContent = value;
          row.appendChild(cell);
        });
        body.appendChild(row);
      });
    }

    exportHumanWorkloadCsv() {
      const rows = [
        ["sim_time_s", "time", "workload", "speed_count", "airspace_count", "emergency_count"],
      ];
      const data =
        this.humanWorkloadHistory && this.humanWorkloadHistory.times.length
          ? this.humanWorkloadHistory
          : this.humanWorkloadData;
      for (let i = 0; i < data.times.length; i += 1) {
        const time_s = data.times[i];
        const timeLabel =
          this.formatDashboardTime && Number.isFinite(time_s)
            ? this.formatDashboardTime(time_s)
            : "-";
        rows.push([
          Number.isFinite(time_s) ? String(Math.round(time_s)) : "",
          timeLabel,
          String(data.total[i] ?? 0),
          String(data.speed[i] ?? 0),
          String(data.airspace[i] ?? 0),
          String(data.emergency[i] ?? 0),
        ]);
      }
      this.downloadCsvFile("human_workload.csv", rows);
    }

    exportHumanEventsCsv(kind) {
      const tables = {
        speed: {
          rows:
            this.humanSpeedHistory && this.humanSpeedHistory.length
              ? this.humanSpeedHistory
              : this.humanSpeedEvents,
          headers: ["sim_time_s", "time", "flight", "flight_id", "action", "speed_mps"],
          map: (entry) => [
            Number.isFinite(entry.time_s) ? String(Math.round(entry.time_s)) : "",
            entry.time_label || "",
            entry.flight_name || "",
            Number.isFinite(entry.flight_id) ? String(entry.flight_id) : "",
            entry.action || "",
            Number.isFinite(entry.speed_mps) ? String(entry.speed_mps) : "",
          ],
          file: "human_speed.csv",
        },
        airspace: {
          rows:
            this.humanAirspaceHistory && this.humanAirspaceHistory.length
              ? this.humanAirspaceHistory
              : this.humanAirspaceEvents,
          headers: ["sim_time_s", "time", "action", "from", "to", "type"],
          map: (entry) => [
            Number.isFinite(entry.time_s) ? String(Math.round(entry.time_s)) : "",
            entry.time_label || "",
            entry.action || "",
            entry.from || "",
            entry.to || "",
            entry.kind || "",
          ],
          file: "human_airspace.csv",
        },
        emergency: {
          rows:
            this.humanEmergencyHistory && this.humanEmergencyHistory.length
              ? this.humanEmergencyHistory
              : this.humanEmergencyEvents,
          headers: ["sim_time_s", "time", "flight", "flight_id", "target", "lon", "lat", "alt_m"],
          map: (entry) => [
            Number.isFinite(entry.time_s) ? String(Math.round(entry.time_s)) : "",
            entry.time_label || "",
            entry.flight_name || "",
            Number.isFinite(entry.flight_id) ? String(entry.flight_id) : "",
            entry.target || "",
            Number.isFinite(entry.lon) ? String(entry.lon) : "",
            Number.isFinite(entry.lat) ? String(entry.lat) : "",
            Number.isFinite(entry.alt_m) ? String(entry.alt_m) : "",
          ],
          file: "human_emergency.csv",
        },
      };
      const table = tables[kind];
      if (!table) {
        return;
      }
      const rows = [table.headers];
      if (Array.isArray(table.rows)) {
        table.rows.forEach((entry) => rows.push(table.map(entry)));
      }
      this.downloadCsvFile(table.file, rows);
    }

    downloadCsvFile(fileName, rows) {
      if (!Array.isArray(rows) || !rows.length) {
        return;
      }
      const lines = rows.map((row) =>
        row.map((value) => this.escapeCsvValue(value)).join(","),
      );
      const content = `${lines.join("\r\n")}\r\n`;
      const blob = new Blob([content], { type: "text/csv;charset=utf-8" });
      let url = "";
      try {
        url = URL.createObjectURL(blob);
      } catch (_err) {
        url = "";
      }
      const isIOS =
        typeof navigator !== "undefined" &&
        /iPad|iPhone|iPod/.test(navigator.userAgent || "");
      const link = document.createElement("a");
      link.href = url || `data:text/csv;charset=utf-8,${encodeURIComponent(content)}`;
      link.download = fileName || "export.csv";
      document.body.appendChild(link);
      try {
        link.click();
      } catch (_err) {
        if (typeof window !== "undefined" && window.open) {
          window.open(link.href, "_blank", "noopener");
        }
      }
      link.remove();
      if (url) {
        window.setTimeout(() => URL.revokeObjectURL(url), 0);
      } else if (isIOS && typeof window !== "undefined" && window.open) {
        window.open(link.href, "_blank", "noopener");
      }
    }

    async downloadLogsZip() {
      const lang =
        typeof window !== "undefined" && window.AppI18n && window.AppI18n.getLang
          ? window.AppI18n.getLang()
          : this.language || "en";
      const params = new URLSearchParams();
      params.set("lang", lang || "en");
      if (this.config && this.config.data) {
        if (this.config.data.vertiportCsv) {
          params.set("vertiport", String(this.config.data.vertiportCsv));
        }
        if (this.config.data.waypointCsv) {
          params.set("corridor", String(this.config.data.waypointCsv));
        }
        if (this.config.data.basestationCsv) {
          params.set("basestation", String(this.config.data.basestationCsv));
        }
      }
      const url = this.resolveApiUrl(`api/logs.zip?${params.toString()}`);
      try {
        const response = await fetch(url, { method: "GET" });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const blob = await response.blob();
        const header = response.headers.get("content-disposition") || "";
        const match = header.match(/filename=\"([^\"]+)\"/i);
        const filename = match && match[1] ? match[1] : "uatm_logs.zip";
        const objectUrl = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = objectUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
        this.addStatusMessage({
          level: "success",
          ttlMs: 2500,
        });
      } catch (_error) {
        this.addStatusMessage({
          level: "warn",
          ttlMs: 3200,
        });
      }
    }

    downloadDataUrl(fileName, dataUrl) {
      if (!dataUrl) {
        return;
      }
      const link = document.createElement("a");
      link.href = dataUrl;
      link.download = fileName || "export.png";
      document.body.appendChild(link);
      link.click();
      link.remove();
    }

    escapeCsvValue(value) {
      const text = value == null ? "" : String(value);
      if (/[",\r\n]/.test(text)) {
        return `"${text.replace(/"/g, "\"\"")}"`;
      }
      return text;
    }

    setSpeedUnit(nextUnit, options = {}) {
      const unit = nextUnit || "knot";
      if (!["knot", "mps", "kmh"].includes(unit)) {
        return;
      }
      const preserve = Object.prototype.hasOwnProperty.call(options, "preserveValue")
        ? Boolean(options.preserveValue)
        : true;
      let speedMps = this.rulesState ? Number(this.rulesState.speed_mps) : NaN;
      if (preserve && this.ruleControls.speedInput) {
        const value = Number.parseFloat(this.ruleControls.speedInput.value);
        if (Number.isFinite(value)) {
          speedMps = this.convertSpeedToMps(value, this.speedUnit);
        }
      }
      if (!Number.isFinite(speedMps)) {
        speedMps = DEFAULT_RULES.speed_mps;
      }
      this.speedUnit = unit;
      if (this.ruleControls.speedInput) {
        this.ruleControls.speedInput.value = this.formatSpeedByUnit(speedMps, unit);
      }
      this.updateSpeedUnitButtons();
    }

    updateSpeedUnitButtons() {
      const buttons = this.ruleControls.speedUnitButtons || [];
      buttons.forEach((button) => {
        button.classList.toggle("is-active", button.dataset.speedUnit === this.speedUnit);
      });
    }

    collectRulesFromInputs() {
      const base = this.rulesState ? { ...DEFAULT_RULES, ...this.rulesState } : { ...DEFAULT_RULES };
      const readNumber = (input, fallback) => {
        if (!input) {
          return fallback;
        }
        const value = Number.parseFloat(input.value);
        return Number.isFinite(value) ? value : fallback;
      };
      const holdingMin = readNumber(this.ruleControls.holdingInput, base.holding_s / 60);
      const takeoffMin = readNumber(this.ruleControls.takeoffInput, base.takeoff_s / 60);
      const landingMin = readNumber(this.ruleControls.landingInput, base.landing_s / 60);
      const batteryMin = readNumber(
        this.ruleControls.batteryInput,
        (base.battery_capacity_s || 0) / 60,
      );
      const minSafeSpeedValue = readNumber(
        this.ruleControls.minSpeedInput,
        base.min_safe_speed_mps,
      );
      const speedValue = readNumber(this.ruleControls.speedInput, NaN);
      const speedMps = Number.isFinite(speedValue)
        ? this.convertSpeedToMps(speedValue, this.speedUnit)
        : base.speed_mps;
      const accelValue = readNumber(this.ruleControls.accelInput, base.accel_mps2);
      const climbRateValue = readNumber(this.ruleControls.climbRateInput, base.climb_rate_fpm);
      const transitionAltValue = readNumber(
        this.ruleControls.transitionAltInput,
        base.transition_alt_ft,
      );
      const transitionSpeedValue = readNumber(
        this.ruleControls.transitionSpeedInput,
        base.transition_speed_knot,
      );
      const riskHorizonValue = readNumber(
        this.ruleControls.riskHorizonInput,
        base.risk_predict_horizon_s,
      );
      const riskLateralValue = readNumber(
        this.ruleControls.riskLateralInput,
        base.risk_lateral_m,
      );
      const riskDirectionValue = readNumber(
        this.ruleControls.riskDirectionInput,
        base.risk_direction_cos,
      );
      const riskIntervalValue = readNumber(
        this.ruleControls.riskIntervalInput,
        base.risk_update_interval_s,
      );
      const riskProxLv3Value = readNumber(
        this.ruleControls.riskProxLv3Input,
        base.risk_proximity_lv3_m,
      );
      const riskProxLv2Value = readNumber(
        this.ruleControls.riskProxLv2Input,
        base.risk_proximity_lv2_m,
      );
      const riskProxLv1Value = readNumber(
        this.ruleControls.riskProxLv1Input,
        base.risk_proximity_lv1_m,
      );
      const riskBattLv3Value = readNumber(
        this.ruleControls.riskBattLv3Input,
        base.risk_battery_lv3_pct,
      );
      const riskBattLv2Value = readNumber(
        this.ruleControls.riskBattLv2Input,
        base.risk_battery_lv2_pct,
      );
      const riskBattLv1Value = readNumber(
        this.ruleControls.riskBattLv1Input,
        base.risk_battery_lv1_pct,
      );
      const rnpMaxLatValue = readNumber(this.ruleControls.rnpMaxLatInput, base.rnp_max_lat_m);
      const rnpMaxVerValue = readNumber(this.ruleControls.rnpMaxVerInput, base.rnp_max_ver_m);
      const rnpRLv1Value = readNumber(this.ruleControls.rnpRLv1Input, base.rnp_r_lv1);
      const rnpRLv2Value = readNumber(this.ruleControls.rnpRLv2Input, base.rnp_r_lv2);
      const rnpRLv3Value = readNumber(this.ruleControls.rnpRLv3Input, base.rnp_r_lv3);
      const rnpTtvLv1Value = readNumber(this.ruleControls.rnpTtvLv1Input, base.rnp_ttv_lv1_s);
      const rnpTtvLv2Value = readNumber(this.ruleControls.rnpTtvLv2Input, base.rnp_ttv_lv2_s);
      const windEnabledValue = readNumber(
        this.ruleControls.windEnabledInput,
        base.wind_enabled,
      );
      const windTimeSpeedValue = readNumber(
        this.ruleControls.windTimeSpeedInput,
        base.wind_time_speed,
      );
      const windSmoothValue = readNumber(
        this.ruleControls.windSmoothInput,
        base.wind_smooth_s,
      );
      const windCrossGainValue = readNumber(
        this.ruleControls.windCrossGainInput,
        base.wind_cross_gain,
      );
      const windCrossReturnValue = readNumber(
        this.ruleControls.windCrossReturnInput,
        base.wind_cross_return_s,
      );
      const windCrossMaxValue = readNumber(
        this.ruleControls.windCrossMaxInput,
        base.wind_cross_max_m,
      );
      const windAlongGainValue = readNumber(
        this.ruleControls.windAlongGainInput,
        base.wind_along_gain,
      );
      const windAlongMaxValue = readNumber(
        this.ruleControls.windAlongMaxInput,
        base.wind_along_max_mps,
      );
      const windCrabMaxValue = readNumber(
        this.ruleControls.windCrabMaxInput,
        base.wind_crab_max_deg,
      );
      const { startMin, endMin } = this.getOperationMinutes();
      const goalValue = readNumber(this.settingsControls.operationGoal, base.operation_goal_count);

      return {
        speed_mps: speedMps,
        accel_mps2: Math.max(0, accelValue),
        climb_rate_fpm: Math.max(0, climbRateValue),
        transition_alt_ft: Math.max(0, transitionAltValue),
        transition_speed_knot: Math.max(0, transitionSpeedValue),
        holding_s: Math.max(0, Math.round(holdingMin * 60)),
        takeoff_s: Math.max(0, Math.round(takeoffMin * 60)),
        landing_s: Math.max(0, Math.round(landingMin * 60)),
        battery_capacity_s: Math.max(0, Math.round(batteryMin * 60)),
        min_safe_speed_mps: Math.max(0, minSafeSpeedValue),
        turn_rate_deg_s: readNumber(this.ruleControls.turnRateInput, base.turn_rate_deg_s),
        separation_m: readNumber(this.ruleControls.separationInput, base.separation_m),
        warning_m: readNumber(this.ruleControls.warningDistInput, base.warning_m),
        warning_ec_s: readNumber(this.ruleControls.warningEcInput, base.warning_ec_s),
        warning_trailing_circles: readNumber(
          this.ruleControls.warningTrailingInput,
          base.warning_trailing_circles,
        ),
        warning_leading_knot_delta: readNumber(
          this.ruleControls.warningLeadingInput,
          base.warning_leading_knot_delta,
        ),
        caution_m: readNumber(this.ruleControls.cautionDistInput, base.caution_m),
        caution_ec_s: readNumber(this.ruleControls.cautionEcInput, base.caution_ec_s),
        caution_trailing_knot_delta: readNumber(
          this.ruleControls.cautionTrailingInput,
          base.caution_trailing_knot_delta,
        ),
        caution_leading_knot_delta: readNumber(
          this.ruleControls.cautionLeadingInput,
          base.caution_leading_knot_delta,
        ),
        risk_predict_horizon_s: Math.max(0, riskHorizonValue),
        risk_lateral_m: Math.max(0, riskLateralValue),
        risk_direction_cos: riskDirectionValue,
        risk_update_interval_s: Math.max(0, riskIntervalValue),
        risk_proximity_lv1_m: Math.max(0, riskProxLv1Value),
        risk_proximity_lv2_m: Math.max(0, riskProxLv2Value),
        risk_proximity_lv3_m: Math.max(0, riskProxLv3Value),
        risk_battery_lv1_pct: Math.max(0, riskBattLv1Value),
        risk_battery_lv2_pct: Math.max(0, riskBattLv2Value),
        risk_battery_lv3_pct: Math.max(0, riskBattLv3Value),
        rnp_max_lat_m: Math.max(0, rnpMaxLatValue),
        rnp_max_ver_m: Math.max(0, rnpMaxVerValue),
        rnp_r_lv1: Math.max(0, rnpRLv1Value),
        rnp_r_lv2: Math.max(0, rnpRLv2Value),
        rnp_r_lv3: Math.max(0, rnpRLv3Value),
        rnp_ttv_lv1_s: Math.max(0, rnpTtvLv1Value),
        rnp_ttv_lv2_s: Math.max(0, rnpTtvLv2Value),
        wind_enabled: windEnabledValue > 0 ? 1 : 0,
        wind_time_speed: Math.max(0.1, windTimeSpeedValue),
        wind_smooth_s: Math.max(0, windSmoothValue),
        wind_cross_gain: Math.max(0, windCrossGainValue),
        wind_cross_return_s: Math.max(0, windCrossReturnValue),
        wind_cross_max_m: Math.max(0, windCrossMaxValue),
        wind_along_gain: Math.max(0, windAlongGainValue),
        wind_along_max_mps: Math.max(0, windAlongMaxValue),
        wind_crab_max_deg: Math.max(0, windCrabMaxValue),
        operation_start_min: startMin,
        operation_end_min: endMin,
        operation_goal_count: Math.max(0, Math.round(goalValue)),
      };
    }

    updateRuleDistanceHints() {
      const updateFeet = (input, label) => {
        if (!label) {
          return;
        }
        const meters = input ? Number.parseFloat(input.value) : NaN;
        if (!Number.isFinite(meters)) {
          label.textContent = "";
          return;
        }
        const feet = meters / FT_TO_M;
        label.textContent = `${Math.round(feet)} ft`;
      };
      const updateConverted = (input, label, convert, unit, digits) => {
        if (!label) {
          return;
        }
        const raw = input ? Number.parseFloat(input.value) : NaN;
        if (!Number.isFinite(raw)) {
          label.textContent = "";
          return;
        }
        const value = convert(raw);
        if (!Number.isFinite(value)) {
          label.textContent = "";
          return;
        }
        const formatted = this.formatNumber(value, digits);
        label.textContent = formatted ? `${formatted} ${unit}` : "";
      };
      updateFeet(this.ruleControls.separationInput, this.ruleControls.separationFt);
      updateFeet(this.ruleControls.warningDistInput, this.ruleControls.warningFt);
      updateFeet(this.ruleControls.cautionDistInput, this.ruleControls.cautionFt);
      updateConverted(
        this.ruleControls.climbRateInput,
        this.ruleControls.climbRateMps,
        (value) => (value * FT_TO_M) / 60,
        "m/s",
        2,
      );
      updateConverted(
        this.ruleControls.transitionAltInput,
        this.ruleControls.transitionAltMeters,
        (value) => value * FT_TO_M,
        "m",
        1,
      );
      updateConverted(
        this.ruleControls.transitionSpeedInput,
        this.ruleControls.transitionSpeedMps,
        (value) => value * KNOT_TO_MPS,
        "m/s",
        1,
      );
    }

    updateOperationSummary() {
      if (!this.settingsControls.operationTimeSummary) {
        return;
      }
      const { startMin, endMin } = this.getOperationMinutes();
      const duration = endMin >= startMin ? endMin - startMin : 24 * 60 - startMin + endMin;
      const hours = Math.floor(duration / 60);
      const minutes = duration % 60;
      this.settingsControls.operationTimeSummary.textContent = this.t("label.operation_total_time", {
        hours,
        minutes,
      });
    }

    updateOperationGoalSummary() {
      if (!this.settingsControls.operationGoalSummary) {
        return;
      }
      const goalValue = Number.parseFloat(
        this.settingsControls.operationGoal ? this.settingsControls.operationGoal.value : "",
      );
      const goal = Number.isFinite(goalValue) ? Math.max(0, goalValue) : 0;
      const { startMin, endMin } = this.getOperationMinutes();
      const durationMin = endMin >= startMin ? endMin - startMin : 24 * 60 - startMin + endMin;
      const hours = durationMin > 0 ? durationMin / 60 : 0;
      const perHour = hours > 0 ? goal / hours : 0;
      const summary =
        hours > 0
          ? this.t("label.operation_per_hour", { value: perHour.toFixed(1) })
          : "";
      this.settingsControls.operationGoalSummary.textContent = summary;
    }

    updateTrafficCountLabels() {
      if (!Array.isArray(this.settingsControls.trafficCounts)) {
        return;
      }
      const { startMin, endMin } = this.getOperationMinutes();
      const durationMin = endMin >= startMin ? endMin - startMin : 24 * 60 - startMin + endMin;
      const hours = durationMin / 60;
      this.settingsControls.trafficCounts.forEach((label) => {
        const key = label.dataset.trafficCount;
        if (!key || !Object.prototype.hasOwnProperty.call(TRAFFIC_LEVELS, key)) {
          return;
        }
        const count = Number(TRAFFIC_LEVELS[key]);
        if (!Number.isFinite(count) || hours <= 0) {
          label.textContent = "";
          return;
        }
        const perHour = count / hours;
        const formatted = this.formatNumber(perHour, 0);
        label.textContent = this.t("label.traffic_per_hour", { value: formatted });
      });
    }

    getOperationMinutes() {
      const startValue = this.settingsControls.operationStart
        ? this.settingsControls.operationStart.value
        : DEFAULT_OPERATION_START;
      const endValue = this.settingsControls.operationEnd
        ? this.settingsControls.operationEnd.value
        : DEFAULT_OPERATION_END;
      const startMin = this.parseTimeToMinutes(startValue, DEFAULT_RULES.operation_start_min);
      const endMin = this.parseTimeToMinutes(endValue, DEFAULT_RULES.operation_end_min);
      return { startMin, endMin };
    }

    parseTimeToMinutes(value, fallback) {
      if (!value) {
        return fallback;
      }
      const parts = String(value).split(":");
      if (parts.length < 2) {
        return fallback;
      }
      const hours = Number.parseInt(parts[0], 10);
      const minutes = Number.parseInt(parts[1], 10);
      if (!Number.isFinite(hours) || !Number.isFinite(minutes)) {
        return fallback;
      }
      return Math.min(24 * 60, Math.max(0, hours * 60 + minutes));
    }

    formatMinutesToTime(minutes) {
      const total = Number.isFinite(minutes) ? Math.max(0, Math.round(minutes)) : 0;
      const hours = Math.floor(total / 60) % 24;
      const mins = total % 60;
      return `${String(hours).padStart(2, "0")}:${String(mins).padStart(2, "0")}`;
    }

    formatMinutes(value) {
      const minutes = Number(value);
      if (!Number.isFinite(minutes)) {
        return "";
      }
      return this.formatNumber(minutes, 1);
    }

    formatNumber(value, digits) {
      const num = Number(value);
      if (!Number.isFinite(num)) {
        return "";
      }
      const fixed = typeof digits === "number" ? num.toFixed(digits) : `${num}`;
      return fixed.replace(/\.0+$/, "").replace(/(\.\d)0$/, "$1");
    }

    convertSpeedToMps(value, unit) {
      const speed = Number(value);
      if (!Number.isFinite(speed)) {
        return DEFAULT_RULES.speed_mps;
      }
      if (unit === "kmh") {
        return speed * KMH_TO_MPS;
      }
      if (unit === "knot") {
        return speed * KNOT_TO_MPS;
      }
      return speed;
    }

    formatSpeedByUnit(mps, unit) {
      const value = Number(mps);
      if (!Number.isFinite(value)) {
        return "";
      }
      let result = value;
      if (unit === "kmh") {
        result = value / KMH_TO_MPS;
      } else if (unit === "knot") {
        result = value / KNOT_TO_MPS;
      }
      return this.formatNumber(result, 1);
    }

    connectAirsimBridge() {
      if (!window.qt || !window.QWebChannel) {
        this.connectWebApi();
        return;
      }
      if (this.airsimChannel) {
        return;
      }
      try {
        this.airsimChannel = new QWebChannel(window.qt.webChannelTransport, (channel) => {
          this.airsimBridge = channel.objects.airsimBridge || null;
          this.controlBridge = channel.objects.controlBridge || null;
          this.uiBridge = channel.objects.uiBridge || null;
          if (!this.airsimBridge) {
            console.warn("[AirSim] QWebChannel connected but bridge missing.");
          }
          if (!this.controlBridge) {
            console.warn("[Control] QWebChannel connected but control bridge missing.");
          }
          if (!this.uiBridge) {
            console.warn("[UI] QWebChannel connected but ui bridge missing.");
          }
          if (
            this.airsimBridge &&
            this.airsimBridge.positionUpdated &&
            !this.telemetryConnected
          ) {
            this.airsimBridge.positionUpdated.connect((payload) => {
              this.handleTelemetryUpdate(payload);
            });
            this.telemetryConnected = true;
            console.warn("[AirSim] Telemetry signal connected.");
          } else if (this.airsimBridge && !this.airsimBridge.positionUpdated) {
            console.warn("[AirSim] positionUpdated signal not available.");
          }
        });
      } catch (error) {
        console.warn("Failed to connect AirSim bridge.", error);
        this.connectWebApi();
      }
    }

    connectWebApi() {
      if (this.webApiEnabled) {
        return;
      }
      this.webApiEnabled = true;
      this.webApiBaseUrl = "";
      this.resetWebPositionSync();
        this.controlBridge = {
          setFlightSpeed: (flightId, speed) =>
            this.sendWebControl("setFlightSpeed", [flightId, speed]),
          clearFlightSpeed: (flightId) => this.sendWebControl("clearFlightSpeed", [flightId]),
          startHolding: (flightId, loops) =>
            this.sendWebControl("startHolding", [flightId, loops]),
          stopHolding: (flightId) => this.sendWebControl("stopHolding", [flightId]),
          setCorridorClosed: (start, end, closed) =>
            this.sendWebControl("setCorridorClosed", [start, end, closed]),
          setSpareCorridorOpen: (start, end, open) =>
            this.sendWebControl("setSpareCorridorOpen", [start, end, open]),
          setEmergencyLanding: (flightId, lon, lat, label, alt_m) =>
            this.sendWebControl("setEmergencyLanding", [flightId, lon, lat, label, alt_m]),
          forceMoveVia: (flightId, waypoint) =>
            this.sendWebControl("forceMoveVia", [flightId, waypoint]),
          setWindHold: (flightId, scale, ramp_s) =>
            this.sendWebControl("setWindHold", [flightId, scale, ramp_s]),
          setAutopilot: (enabled, duration_s, lv1, lv2, lv3) =>
            this.sendWebControl("setAutopilot", [enabled, duration_s, lv1, lv2, lv3]),
        };
      this.uiBridge = {
        selectFlight: (name) => this.sendWebSelection(name),
        clearSelection: () => this.sendWebSelection(""),
      };
      this.startWebPolling();
      this.addStatusMessage({
        text: this.t("status.web_mode_connected"),
        level: "info",
        ttlMs: 3000,
      });
    }

    startWebPolling() {
      if (this.webApiPolling) {
        return;
      }
      this.webApiPolling = true;
      this.scheduleWebPoll(0);
    }

    scheduleWebPoll(delayMs = 0) {
      if (!this.webApiPolling) {
        return;
      }
      if (this.webApiTimer) {
        window.clearTimeout(this.webApiTimer);
      }
      const waitMs = Math.max(0, Number(delayMs) || 0);
      this.webApiTimer = window.setTimeout(() => {
        this.webApiTimer = null;
        this.pollWebApiState();
      }, waitMs);
    }

    getWebPollIntervalMs() {
      if (typeof document !== "undefined" && document.hidden) {
        return this.webApiHiddenIntervalMs;
      }
      if (this.isPlaying) {
        return this.webApiActiveIntervalMs;
      }
      return this.webApiIdleIntervalMs;
    }

    buildWebStateUrl() {
      let url = this.resolveApiUrl("api/state");
      if (Number.isFinite(this.webPositionsRev) && this.webPositionsRev >= 0) {
        const rev = Math.max(0, Math.floor(this.webPositionsRev));
        const joiner = url.includes("?") ? "&" : "?";
        url = `${url}${joiner}positions_rev=${encodeURIComponent(String(rev))}`;
      }
      return url;
    }

    getWebPositionKey(item) {
      if (!item) {
        return "";
      }
      if (typeof item === "string") {
        return String(item).trim();
      }
      const id = item.id != null ? String(item.id).trim() : "";
      if (id) {
        return `id:${id}`;
      }
      const name = item.name != null ? String(item.name).trim() : "";
      if (name) {
        return `name:${name}`;
      }
      return "";
    }

    resetWebPositionSync() {
      this.webPositionsRev = -1;
      if (this.webPositionsCache && typeof this.webPositionsCache.clear === "function") {
        this.webPositionsCache.clear();
      } else {
        this.webPositionsCache = new Map();
      }
    }

    applyWebPositions(payload) {
      const mode = payload && typeof payload.positions_mode === "string"
        ? String(payload.positions_mode)
        : "";
      const nextRev = Number(payload && payload.positions_rev);
      const hasNextRev = Number.isFinite(nextRev) && nextRev >= 0;

      const applyFull = (positions) => {
        if (!Array.isArray(positions)) {
          return;
        }
        const cache = new Map();
        positions.forEach((item) => {
          const key = this.getWebPositionKey(item);
          if (!key) {
            return;
          }
          cache.set(key, { ...item });
        });
        this.webPositionsCache = cache;
        if (hasNextRev) {
          this.webPositionsRev = nextRev;
        }
        this.updateTrafficPositions(positions);
      };

      if (mode === "full") {
        applyFull(payload.positions);
        return;
      }

      if (mode === "delta") {
        if (!(this.webPositionsCache instanceof Map)) {
          this.webPositionsCache = new Map();
        }
        const removed = Array.isArray(payload.positions_removed) ? payload.positions_removed : [];
        const updates = Array.isArray(payload.positions_updates) ? payload.positions_updates : [];
        let changed = false;
        removed.forEach((entry) => {
          const key = String(entry || "").trim();
          if (!key) {
            return;
          }
          if (this.webPositionsCache.delete(key)) {
            changed = true;
          }
        });
        updates.forEach((patch) => {
          const key = this.getWebPositionKey(patch);
          if (!key) {
            return;
          }
          const previous = this.webPositionsCache.get(key) || {};
          const merged = { ...previous, ...patch };
          this.webPositionsCache.set(key, merged);
          changed = true;
        });
        if (hasNextRev) {
          this.webPositionsRev = nextRev;
        }
        if (changed) {
          const merged = Array.from(this.webPositionsCache.values()).map((item) => ({ ...item }));
          this.updateTrafficPositions(merged);
        }
        return;
      }

      if (mode === "none") {
        if (hasNextRev) {
          this.webPositionsRev = nextRev;
        }
        return;
      }

      if (payload && Array.isArray(payload.positions)) {
        applyFull(payload.positions);
      }
    }

    pollWebApiState() {
      if (this.webApiInFlight) {
        this.scheduleWebPoll(this.getWebPollIntervalMs());
        return;
      }
      this.webApiInFlight = true;
      const url = this.buildWebStateUrl();
      fetch(url)
        .then((response) => (response.ok ? response.json() : null))
        .then((payload) => {
          if (payload) {
            this.applyWebState(payload);
          }
        })
        .catch(() => {})
        .finally(() => {
          this.webApiInFlight = false;
          this.scheduleWebPoll(this.getWebPollIntervalMs());
        });
    }

    applyWebState(payload) {
      if (payload && typeof payload.flightplan_mode_enabled === "boolean") {
        this.flightplanModeEnabled = Boolean(payload.flightplan_mode_enabled);
      }
      if (payload && Number.isFinite(payload.time_s)) {
        this.pendingDashboardTime_s = payload.time_s;
      } else {
        this.pendingDashboardTime_s = null;
      }
      this.applyWebPositions(payload);
      if (payload && Array.isArray(payload.status_messages)) {
        payload.status_messages.forEach((entry) => this.addStatusMessage(entry));
      }
      if (payload && Array.isArray(payload.human_events)) {
        payload.human_events.forEach((event) => {
          if (!event || !event.kind) {
            return;
          }
          const kind = event.kind;
          const payloadCopy = { ...event };
          delete payloadCopy.kind;
          this.recordHumanIntervention(kind, payloadCopy);
        });
      }
      if (payload && Object.prototype.hasOwnProperty.call(payload, "dashboard_reset")) {
        if (payload.dashboard_reset) {
          this.clearDashboard();
          this.clearTrafficHistory();
        }
      }
      if (payload && Array.isArray(payload.dashboard_new)) {
        this.addDashboardRows(payload.dashboard_new);
      }
      if (payload && Array.isArray(payload.dashboard_status)) {
        this.applyDashboardStatus(payload.dashboard_status);
      }
      if (payload && Array.isArray(payload.dashboard_failed)) {
        this.addDashboardFailureRows(payload.dashboard_failed);
      }
      if (payload && Object.prototype.hasOwnProperty.call(payload, "status_hint")) {
        this.setStatusHint(payload.status_hint);
      }
      if (payload && typeof payload.running === "boolean") {
        this.setPlayActive(payload.running);
      }
      if (payload && Number.isFinite(payload.speed)) {
        this.updateFastLabel(payload.speed);
      }
      if (payload && Number.isFinite(payload.time_s)) {
        this.updateSimTime(payload.time_s);
      }
      if (payload && payload.traffic_selection) {
        this.applyTrafficSelection(payload.traffic_selection, {
          notify: false,
          send: false,
        });
      }
      if (payload && payload.rules) {
        this.rulesState = payload.rules;
        if (!this.rulesInitialized) {
          this.applyRulesState(payload.rules);
          this.rulesInitialized = true;
        }
      }
      if (payload && payload.autopilot) {
        const nextAutopilot = { ...DEFAULT_AUTOPILOT, ...payload.autopilot };
        this.autopilotState = nextAutopilot;
        const autopilotPanel =
          this.panels && this.panels.autopilot ? this.panels.autopilot : null;
        const panelVisible =
          autopilotPanel && autopilotPanel.classList.contains("is-visible");
        const shouldSync =
          this.autopilotPendingSync || !this.autopilotInitialized || !panelVisible;
        if (shouldSync) {
          this.applyAutopilotState(nextAutopilot);
          this.autopilotPendingSync = false;
          this.autopilotInitialized = true;
        }
      }
      this.pendingDashboardTime_s = null;
    }

    updateFastLabel(speed) {
      if (!this.playbackFastButton) {
        return;
      }
      const value = Number(speed);
      if (!Number.isFinite(value) || value <= 0) {
        return;
      }
      this.playbackSpeedValue = value;
      this.playbackFastButton.dataset.speed = String(value);
      const label = this.t("label.speed_label", { value });
      this.playbackFastButton.title = label;
      this.playbackFastButton.setAttribute("aria-label", label);
      if (this.playbackSpeedOptions && this.playbackSpeedOptions.length) {
        this.playbackSpeedOptions.forEach((button) => {
          const optionValue = Number(button.dataset.speed);
          button.classList.toggle("is-active", optionValue === value);
        });
      }
    }

    updateSimTime(seconds) {
      if (!this.simTimeLabel) {
        return;
      }
      const total = Number.isFinite(seconds) ? Math.max(0, Math.floor(seconds)) : 0;
      this.lastSimTime_s = total;
      const startMin = this.getOperationMinutes ? this.getOperationMinutes().startMin : 0;
      const offset = Number.isFinite(startMin) ? startMin * 60 : 0;
      this.simTimeLabel.textContent = this.formatTime(total + offset);
      if (typeof this.checkCorridorTimedChanges === "function") {
        this.checkCorridorTimedChanges(total);
      }
      if (typeof this.applyCorridorSchedules === "function") {
        this.applyCorridorSchedules(total);
      }
      if (typeof this.updateCorridorTimedLabels === "function") {
        this.updateCorridorTimedLabels(total);
      }
      this.updateRiskTrend();
      this.updateHumanWorkloadSeries(total);
    }

    formatTime(totalSeconds) {
      const total = Math.max(0, Math.floor(totalSeconds));
      const normalized = total % (24 * 3600);
      const hours = Math.floor(normalized / 3600);
      const minutes = Math.floor((normalized % 3600) / 60);
      const seconds = normalized % 60;
      return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(
        seconds,
      ).padStart(2, "0")}`;
    }

    sendWebControl(method, args) {
      if (!this.webApiEnabled) {
        return;
      }
      this.sendWebRequest("api/control", { method, args: Array.isArray(args) ? args : [] });
    }

    sendWebSelection(name) {
      if (!this.webApiEnabled) {
        return;
      }
      this.sendWebRequest("api/selection", { name: String(name || "") });
    }

    sendWebRequest(path, payload) {
      const url = this.resolveApiUrl(path);
      fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {}),
      }).catch(() => {});
    }

    async requestDatafile(path, payload) {
      const url = this.resolveApiUrl(path);
      try {
        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload || {}),
        });
        if (!response.ok) {
          return {
            ok: false,
            message: this.t("status.request_failed", { status: response.status }),
          };
        }
        const data = await response.json();
        if (data && typeof data === "object") {
          return data;
        }
        return { ok: false, message: this.t("status.invalid_response") };
      } catch (error) {
        console.warn("Datafile request failed.", error);
        return { ok: false, message: this.t("status.request_failed_generic") };
      }
    }

    requestDatafileClone(payload) {
      return this.requestDatafile("api/datafiles/clone", payload);
    }

    requestDatafileAppend(payload) {
      return this.requestDatafile("api/datafiles/append", payload);
    }

    requestDatafileUpdate(payload) {
      return this.requestDatafile("api/datafiles/update", payload);
    }

    requestDatafileDelete(payload) {
      return this.requestDatafile("api/datafiles/delete", payload);
    }

    applyDatafilesToServer() {
      if (!this.webApiEnabled || panelParam) {
        return;
      }
      const payload = {
        vertiport: this.config.data.vertiportCsv,
        corridor: this.config.data.waypointCsv,
      };
      this.sendWebRequest("api/datafiles/apply", payload);
    }

    isCustomDatafile(kind) {
      if (kind === "vertiport") {
        return String(this.config.data.vertiportCsv || "").includes("api/data/customed/");
      }
      if (kind === "corridor") {
        return String(this.config.data.waypointCsv || "").includes("api/data/customed/");
      }
      if (kind === "basestation") {
        return String(this.config.data.basestationCsv || "").includes("api/data/customed/");
      }
      return false;
    }

    async ensureEditableFile(kind) {
      const control = this.fileControls ? this.fileControls[kind] : null;
      if (!control || !control.nameInput) {
        return false;
      }
      const fileName = control.nameInput.value.trim();
      if (!fileName) {
        this.addStatusMessage({
          text: this.t("status.no_active_datafile"),
          level: "warn",
          ttlMs: 2500,
        });
        return false;
      }
      const isCustom = control.nameInput.classList.contains("is-custom") || this.isCustomDatafile(kind);
      if (isCustom) {
        return true;
      }
      const result = await this.requestDatafileClone({ kind });
      if (!result || !result.ok) {
        this.addStatusMessage({
          text: this.t("status.failed_prepare_editable"),
          level: "warn",
          ttlMs: 3000,
        });
        return false;
      }
      const nextName = typeof result.name === "string" ? result.name : fileName;
      const nextUrl =
        typeof result.url === "string" && result.url
          ? result.url.replace(/^\/+/, "")
          : `api/data/customed/${nextName}`;
      this.updatePanelFileName(kind, nextName, { custom: true });
      if (kind === "vertiport") {
        this.config.data.vertiportCsv = nextUrl;
      } else if (kind === "corridor") {
        this.config.data.waypointCsv = nextUrl;
      } else if (kind === "basestation") {
        this.config.data.basestationCsv = nextUrl;
      }
      return true;
    }

    isControlBridgeReady() {
      return Boolean(this.controlBridge && this.controlBridge.setFlightSpeed);
    }

    sendControlCommand(method, ...args) {
      if (!this.controlBridge || !this.controlBridge[method]) {
        this.addStatusMessage({
          text: this.t("status.control_link_not_ready"),
          level: "warn",
          ttlMs: 2500,
        });
        return false;
      }
      try {
        this.controlBridge[method](...args);
        return true;
      } catch (error) {
        console.warn("Control command failed.", error);
        this.addStatusMessage({
          text: this.t("status.failed_send_control"),
          level: "warn",
          ttlMs: 2500,
        });
        return false;
      }
    }

    notifyFlightSelection(name) {
      if (!this.uiBridge || !this.uiBridge.selectFlight) {
        return;
      }
      try {
        this.uiBridge.selectFlight(String(name || ""));
      } catch (error) {
        console.warn("Failed to notify selection.", error);
      }
    }

    notifySelectionCleared() {
      if (!this.uiBridge) {
        return;
      }
      try {
        if (this.uiBridge.clearSelection) {
          this.uiBridge.clearSelection();
        } else if (this.uiBridge.selectFlight) {
          this.uiBridge.selectFlight("");
        }
      } catch (error) {
        console.warn("Failed to clear selection.", error);
      }
    }

    refreshAirsimInputs() {
      if (this.settingsControls.hostInput) {
        this.settingsControls.hostInput.value = this.airsimHost;
      }
      if (this.settingsControls.portInput) {
        this.settingsControls.portInput.value = String(this.airsimPort);
      }
    }

    applyAirsimSettings() {
      const hostInput = this.settingsControls.hostInput
        ? this.settingsControls.hostInput.value.trim()
        : "";
      const portInput = this.settingsControls.portInput
        ? Number.parseInt(this.settingsControls.portInput.value, 10)
        : NaN;
      this.airsimHost = hostInput || this.airsimDefaults.host;
      this.airsimPort = Number.isFinite(portInput) ? portInput : this.airsimDefaults.port;
      this.refreshAirsimInputs();
    }

    resetAirsimSettings() {
      this.airsimHost = this.airsimDefaults.host;
      this.airsimPort = this.airsimDefaults.port;
      this.refreshAirsimInputs();
    }

    syncFileNames() {
      Object.entries(this.defaultFiles).forEach(([key, info]) => {
        this.updatePanelFileName(key, info.name, { custom: false });
      });
    }

    updatePanelFileName(key, name, options = {}) {
      const control = this.fileControls[key];
      if (!control || !control.nameInput) {
        return;
      }
      control.nameInput.value = name || "";
      if (Object.prototype.hasOwnProperty.call(options, "custom")) {
        control.nameInput.classList.toggle("is-custom", Boolean(options.custom));
      }
    }

    createFilePicker(onSelect) {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = ".csv,text/csv";
      input.style.display = "none";
      input.addEventListener("change", () => {
        const file = input.files && input.files[0];
        if (!file) {
          return;
        }
        const reader = new FileReader();
        reader.onload = () => {
          const text = typeof reader.result === "string" ? reader.result : "";
          onSelect(text, file.name);
        };
        reader.onerror = () => {
          console.warn("Failed to read csv file.");
        };
        reader.readAsText(file);
        input.value = "";
      });
      document.body.appendChild(input);
      return input;
    }

    async resetVertiport(options = {}) {
      const applyToServer = options.applyToServer !== false;
      const info = this.defaultFiles.vertiport;
      if (info) {
        this.updatePanelFileName("vertiport", info.name, { custom: false });
        this.config.data.vertiportCsv = info.url;
        this.vertiportEditMovingId = null;
        this.vertiportEditMovingName = null;
        this.vertiportEditGhostLngLat = null;
        this.vertiportEditGhostVisible = false;
        this.vertiportPendingNodes.clear();
        this.vertiportPendingCounter = 0;
        this.pendingVertiportRows = null;
        this.lastVertiportRows = null;
        if (this.hideVertiportEditPopup) {
          this.hideVertiportEditPopup();
        }
        if (this.hideVertiportEditGhost) {
          this.hideVertiportEditGhost();
        }
        if (this.hideVertiportEditCoordLabel) {
          this.hideVertiportEditCoordLabel();
        }
        if (this.clearVertiportEditHighlight) {
          this.clearVertiportEditHighlight();
        }
        if (this.updateVertiportEditSource) {
          this.updateVertiportEditSource();
        }
        if (this.tableBodies.vertiport) {
          await this.loadVertiportTable(info.url, true);
        } else {
          await this.loadVertiportOverlay(info.url, true);
        }
        if (this.reorderPlanLayers) {
          this.reorderPlanLayers();
        }
        if (this.map) {
          this.map.triggerRepaint();
        }
        if (this.ensureVertiportReady) {
          this.ensureVertiportReady();
        }
        if (applyToServer) {
          void this.applyDatafilesToServer();
        }
      }
    }

    async resetCorridor(options = {}) {
      const applyToServer = options.applyToServer !== false;
      const info = this.defaultFiles.corridor;
      if (info) {
        this.updatePanelFileName("corridor", info.name, { custom: false });
        this.config.data.waypointCsv = info.url;
        this.corridorEditMovingId = null;
        this.corridorEditMovingName = null;
        this.corridorEditGhostLngLat = null;
        this.corridorPendingNodes.clear();
        this.corridorPendingCounter = 0;
        this.pendingCorridorRows = null;
        this.lastCorridorRows = null;
        if (this.clearCorridorLinking) {
          this.clearCorridorLinking();
        }
        if (this.hideCorridorEditPopup) {
          this.hideCorridorEditPopup();
        }
        if (this.hideCorridorEditGhost) {
          this.hideCorridorEditGhost();
        }
        if (this.hideCorridorEditCoordLabel) {
          this.hideCorridorEditCoordLabel();
        }
        if (this.clearCorridorEditHighlight) {
          this.clearCorridorEditHighlight();
        }
        if (this.updateCorridorEditSource) {
          this.updateCorridorEditSource();
        }
        if (this.closedCorridorEdges) {
          this.closedCorridorEdges.clear();
          if (this.refreshClosedCorridorLines) {
            this.refreshClosedCorridorLines();
          }
        }
        if (this.openSpareCorridorEdges) {
          this.openSpareCorridorEdges.clear();
          if (this.updateCorridorSpareOpen3dLayer && this.corridorData) {
            this.updateCorridorSpareOpen3dLayer(this.corridorData);
          }
        }
        if (this.tableBodies.corridor) {
          await this.loadCorridorData(info.url, true);
        } else {
          await this.loadCorridorOverlay(info.url, true);
        }
        if (this.reorderPlanLayers) {
          this.reorderPlanLayers();
        }
        if (this.map) {
          this.map.triggerRepaint();
        }
        if (applyToServer) {
          void this.applyDatafilesToServer();
        }
      }
    }

    async resetDatafilesToDefault() {
      if (this.datafilesResetInFlight) {
        return this.datafilesResetInFlight;
      }
      const task = (async () => {
        this.planLayersReady = false;
        this.corridorEnsured = false;
        this.vertiportEnsured = false;
        await this.resetVertiport({ applyToServer: false });
        await this.resetCorridor({ applyToServer: false });
        if (this.ensurePlanLayers) {
          this.ensurePlanLayers();
        }
        await this.forceReloadPlanData(
          this.config.data.vertiportCsv,
          this.config.data.waypointCsv,
        );
        if (this.ensureCorridorReady) {
          this.ensureCorridorReady();
        }
        if (this.ensureVertiportReady) {
          this.ensureVertiportReady();
        }
        if (this.scheduleCorridorLinkUpdate) {
          this.scheduleCorridorLinkUpdate();
        }
        if (this.scheduleCorridorSpareLinkUpdate) {
          this.scheduleCorridorSpareLinkUpdate();
        }
        if (this.scheduleVertiportLinkUpdate) {
          this.scheduleVertiportLinkUpdate();
        }
        if (this.reorderPlanLayers) {
          this.reorderPlanLayers();
        }
        if (this.map) {
          this.map.triggerRepaint();
        }
        void this.applyDatafilesToServer();
      })();
      this.datafilesResetInFlight = task;
      try {
        await task;
      } finally {
        if (this.datafilesResetInFlight === task) {
          this.datafilesResetInFlight = null;
        }
      }
    }

    async forceReloadPlanData(vertiportUrl, corridorUrl) {
      if (!this.map) {
        return;
      }
      const reloadToken = (this.planReloadToken || 0) + 1;
      this.planReloadToken = reloadToken;
      const vpUrl = vertiportUrl || this.config.data.vertiportCsv;
      const coUrl = corridorUrl || this.config.data.waypointCsv;
      if (!vpUrl || !coUrl) {
        return;
      }
      const previousCorridorRows = this.lastCorridorRows;
      const previousVertiportRows = this.lastVertiportRows;
      let corridorRows = null;
      let vertiportRows = null;
      try {
        [corridorRows, vertiportRows] = await Promise.all([
          this.fetchCsvRows(coUrl),
          this.fetchCsvRows(vpUrl),
        ]);
      } catch (error) {
        if (reloadToken !== this.planReloadToken) {
          return;
        }
        console.warn("Failed to reload plan data.", error);
        if (this.map && this.map.isStyleLoaded && this.map.isStyleLoaded()) {
          const missingCorridor = !this.map.getLayer || !this.map.getLayer("corridor-3d");
          const missingVertiport = !this.map.getLayer || !this.map.getLayer("vertiport-circle");
          if (missingCorridor && previousCorridorRows) {
            this.updateCorridorOverlayFromRows(previousCorridorRows);
          }
          if (missingVertiport && previousVertiportRows) {
            this.updateVertiportOverlayFromRows(previousVertiportRows);
          }
        }
        return;
      }
      if (reloadToken !== this.planReloadToken) {
        return;
      }
      try {
        this.pendingCorridorRows = null;
        this.pendingVertiportRows = null;
        if (this.ensurePlanLayers) {
          this.ensurePlanLayers();
        }
        if (this.tableBodies.corridor) {
          this.populateCorridorTable(this.tableBodies.corridor, corridorRows);
        }
        if (this.tableBodies.vertiport) {
          this.populateVertiportTable(this.tableBodies.vertiport, vertiportRows);
        }
        this.updateCorridorOverlayFromRows(corridorRows);
        this.updateVertiportOverlayFromRows(vertiportRows);
        if (this.scheduleCorridorLinkUpdate) {
          this.scheduleCorridorLinkUpdate();
        }
        if (this.scheduleCorridorSpareLinkUpdate) {
          this.scheduleCorridorSpareLinkUpdate();
        }
        if (this.scheduleVertiportLinkUpdate) {
          this.scheduleVertiportLinkUpdate();
        }
        if (this.reorderPlanLayers) {
          this.reorderPlanLayers();
        }
        if (this.map) {
          this.map.triggerRepaint();
          const map = this.map;
          requestAnimationFrame(() => {
            if (reloadToken !== this.planReloadToken) {
              return;
            }
            if (map.getLayer && !map.getLayer("vertiport-circle") && this.lastVertiportRows) {
              this.updateVertiportOverlayFromRows(this.lastVertiportRows);
            }
          });
        }
      } catch (error) {
        if (reloadToken !== this.planReloadToken) {
          return;
        }
        console.warn("Failed to apply reloaded plan data.", error);
        if (this.map && this.map.isStyleLoaded && this.map.isStyleLoaded()) {
          if (previousCorridorRows) {
            this.updateCorridorOverlayFromRows(previousCorridorRows);
          }
          if (previousVertiportRows) {
            this.updateVertiportOverlayFromRows(previousVertiportRows);
          }
        }
      }
    }

    async loadDefaultTables() {
      const tasks = [
        this.loadVertiportTable(this.config.data.vertiportCsv),
        this.loadCorridorTable(this.config.data.waypointCsv),
      ];
      if (this.loadBaseStationOverlay) {
        tasks.push(this.loadBaseStationOverlay(this.config.data.basestationCsv));
      }
      await Promise.all(tasks);
    }

    async loadVertiportTable(url, force = false) {
      const loadToken = (this.vertiportLoadToken || 0) + 1;
      this.vertiportLoadToken = loadToken;
      const body = this.tableBodies.vertiport;
      try {
        const rows = await this.fetchCsvRows(url);
        if (loadToken !== this.vertiportLoadToken) {
          return;
        }
        if (!force && url !== this.config.data.vertiportCsv) {
          return;
        }
        if (body) {
          this.populateVertiportTable(body, rows);
        }
        this.updateVertiportOverlayFromRows(rows);
      } catch (error) {
        console.warn("Failed to load vertiport data.", error);
      }
    }

    async loadCorridorTable(url, force = false) {
      await this.loadCorridorData(url, force);
    }

    async loadCorridorData(url, force = false) {
      const loadToken = (this.corridorLoadToken || 0) + 1;
      this.corridorLoadToken = loadToken;
      const body = this.tableBodies.corridor;
      try {
        const rows = await this.fetchCsvRows(url);
        if (loadToken !== this.corridorLoadToken) {
          return;
        }
        if (!force && url !== this.config.data.waypointCsv) {
          return;
        }
        if (body) {
          this.populateCorridorTable(body, rows);
        }
        this.updateCorridorOverlayFromRows(rows);
      } catch (error) {
        console.warn("Failed to load corridor data.", error);
      }
    }

    async fetchCsvRows(url, options = {}) {
      const resolved = this.resolveAssetUrl ? this.resolveAssetUrl(url) : url;
      const retryable =
        typeof resolved === "string" &&
        (resolved.includes("/api/data/") || resolved.includes("api/data/"));
      const requestedRetries = Number(options && options.retries);
      const retries = Number.isFinite(requestedRetries)
        ? Math.max(0, Math.floor(requestedRetries))
        : retryable
          ? 5
          : 0;
      const requestedDelayMs = Number(options && options.retryDelayMs);
      const retryDelayMs = Number.isFinite(requestedDelayMs)
        ? Math.max(0, requestedDelayMs)
        : 250;
      const isRetryableStatus = (status) =>
        status === 408 ||
        status === 425 ||
        status === 429 ||
        (status >= 500 && status <= 599);

      let attempt = 0;
      let lastError = null;
      while (attempt <= retries) {
        try {
          const response = await fetch(resolved, { cache: "no-store" });
          if (!response.ok) {
            const status = Number(response.status) || 0;
            const error = new Error(`Request failed: ${status}`);
            if (!isRetryableStatus(status)) {
              error.nonRetryable = true;
            }
            throw error;
          }
          const text = await response.text();
          return getDataRows(text);
        } catch (error) {
          lastError = error;
          if (error && error.nonRetryable) {
            break;
          }
          if (attempt >= retries) {
            break;
          }
          const waitMs = retryDelayMs * Math.pow(2, attempt);
          await new Promise((resolve) => window.setTimeout(resolve, waitMs));
          attempt += 1;
        }
      }
      throw lastError || new Error("Request failed.");
    }

    populateVertiportTable(body, rows) {
      body.innerHTML = "";
      rows.forEach((row, index) => {
        const cells = [
          String(index + 1),
          readCell(row, 0),
          readCell(row, 3),
          readCell(row, 2),
          readCell(row, 1),
        ];
        body.appendChild(this.createTableRow(cells));
      });
    }

    populateCorridorTable(body, rows) {
      body.innerHTML = "";
      rows.forEach((row, index) => {
        const cells = [
          String(index + 1),
          readCell(row, 0),
          readCell(row, 2),
          readCell(row, 1),
          formatAltitudeMeters(readCell(row, 3)),
          readCell(row, 4),
        ];
        body.appendChild(this.createTableRow(cells));
      });
    }

    createTableRow(values) {
      const row = document.createElement("tr");
      values.forEach((value) => {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.appendChild(cell);
      });
      return row;
    }

    handleAction(action) {
      switch (action) {
        case "vertiport":
          this.handleVertiportAction();
          break;
        case "corridor":
          this.handleCorridorAction();
          break;
        case "scenario":
          this.handleScenarioAction();
          break;
        case "plan":
          this.handlePlanAction();
          break;
        case "settings":
          this.handleSettingsAction();
          break;
        case "autopilot":
          this.handleAutopilotAction();
          break;
        case "playback":
          this.togglePlaybackPanel();
          break;
        case "sound":
          this.toggleSoundMuted();
          break;
        default:
          break;
      }
    }

    handleVertiportAction() {
      this.togglePanel("vertiport");
    }

    handleCorridorAction() {
      this.togglePanel("corridor");
    }

    handleScenarioAction() {
      this.togglePanel("scenario");
    }

    handlePlanAction() {
      this.togglePanel("plan");
    }

    handleSettingsAction() {
      this.togglePanel("settings");
    }

    handleAutopilotAction() {
      this.togglePanel("autopilot");
    }

    togglePlaybackPanel() {
      if (!this.playbackPanel) {
        return;
      }
      const isOpen = this.playbackPanel.classList.contains("is-open");
      this.playbackPanel.classList.toggle("is-open", !isOpen);
      this.playbackPanel.setAttribute("aria-hidden", isOpen ? "true" : "false");
      this.setActionButtonActive("playback", !isOpen);
      if (isOpen) {
        this.setSpeedMenuOpen(false);
      }
      if (this.tutorialMode === "guided") {
        this.refreshTutorialLayout();
      }
    }

    async handlePlay() {
      if (this.isPlaying) {
        return;
      }
      if (this.webApiEnabled) {
        if (!this.currentTrafficSelection) {
          const fallback = TRAFFIC_LEVELS.Middle ? "Middle" : Object.keys(TRAFFIC_LEVELS)[0];
          if (fallback) {
            this.applyTrafficSelection(fallback, {
              notify: true,
              send: true,
              updateGoal: true,
            });
          }
        }
        const startPayload = { flightplan: null };
        if (
          this.flightplanModeEnabled &&
          this.highDensityFolderLoaded &&
          Array.isArray(this.highDensityFolderFiles) &&
          this.highDensityFolderFiles.length
        ) {
          const flightplanPayload = await this.buildHighDensityFlightplanPayload();
          if (flightplanPayload && Array.isArray(flightplanPayload.files) && flightplanPayload.files.length) {
            startPayload.flightplan = flightplanPayload;
          } else {
            this.addStatusMessage({
              text: this.t("status.highdensity_folder_invalid"),
              level: "warn",
              ttlMs: 3200,
            });
          }
        } else if (
          !this.flightplanModeEnabled &&
          this.highDensityFolderLoaded
        ) {
          this.addStatusMessage({
            text: "Flight-plan mode is disabled. Random mode will be used.",
            level: "warn",
            ttlMs: 3200,
          });
        }
        this.sendWebRequest("api/sim/start", startPayload);
        this.setPlayActive(true);
        const speedValue = Number(this.playbackSpeedValue);
        if (Number.isFinite(speedValue) && speedValue > 0) {
          this.sendWebRequest("api/sim/speed", { speed: speedValue });
        }
        return;
      }
      if (!this.airsimBridge || !this.airsimBridge.startMission) {
        console.warn("AirSim bridge not available.");
        return;
      }
      const plan = this.getPlanForMission();
      if (!plan.length) {
        console.warn("No flight plan to send.");
        return;
      }
      this.setTelemetryCalibrationFromPlan();
      const payload = {
        host: this.airsimHost,
        port: this.airsimPort,
        relative_to_start: true,
        body_relative: true,
        yaw_follow: true,
        route: plan.map((entry) => ({
          name: entry.name,
          lat: entry.lat,
          lon: entry.lon,
          alt_m: entry.altitude_m,
          ned: { n: entry.n, e: entry.e, d: entry.d },
        })),
      };
      let payloadText = "";
      try {
        payloadText = JSON.stringify(payload);
      } catch (error) {
        payloadText = String(payload);
      }
      console.warn(`[AirSim] payload: ${payloadText}`);
      this.airsimBridge.startMission(payload);
      this.setPlayActive(true);
    }

    handleFast() {
      if (this.playbackSpeedMenu) {
        this.toggleSpeedMenu();
        return;
      }
      if (this.webApiEnabled) {
        this.sendWebRequest("api/sim/fast", {});
        return;
      }
      this.addStatusMessage({
        text: this.t("status.fast_control_web"),
        level: "warn",
        ttlMs: 2200,
      });
    }

    handleSpeedSelect(multiplier) {
      const value = Number(multiplier);
      if (!Number.isFinite(value) || value <= 0) {
        return;
      }
      this.playbackSpeedValue = value;
      if (this.webApiEnabled) {
        this.sendWebRequest("api/sim/speed", { speed: value });
        this.updateFastLabel(value);
      } else {
        this.addStatusMessage({
          text: this.t("status.speed_control_web"),
          level: "warn",
          ttlMs: 2200,
        });
      }
    }

    setSpeedMenuOpen(isOpen) {
      this.playbackSpeedMenuOpen = Boolean(isOpen);
      if (this.playbackSpeedMenu) {
        this.playbackSpeedMenu.classList.toggle("is-open", this.playbackSpeedMenuOpen);
        this.playbackSpeedMenu.setAttribute(
          "aria-hidden",
          this.playbackSpeedMenuOpen ? "false" : "true",
        );
      }
      if (this.playbackFastButton) {
        this.playbackFastButton.setAttribute(
          "aria-expanded",
          this.playbackSpeedMenuOpen ? "true" : "false",
        );
      }
    }

    toggleSpeedMenu() {
      this.setSpeedMenuOpen(!this.playbackSpeedMenuOpen);
    }

    handlePause() {
      if (this.webApiEnabled) {
        this.sendWebRequest("api/sim/pause", {});
        this.setPlayActive(false);
        return;
      }
      this.addStatusMessage({
        text: this.t("status.pause_control_web"),
        level: "warn",
        ttlMs: 2200,
      });
    }

    handleConnect() {
      if (!this.airsimBridge) {
        console.warn("[AirSim] Bridge not available.");
        return;
      }
      if (this.telemetryActive) {
        if (this.airsimBridge.stopTelemetry) {
          this.airsimBridge.stopTelemetry();
          console.warn("[AirSim] Telemetry stopped.");
        }
        this.setTelemetryActive(false);
        this.resetTelemetryCalibration();
        return;
      }
      if (!this.airsimBridge.startTelemetry) {
        console.warn("[AirSim] Telemetry not supported.");
        return;
      }
      const payload = {
        host: this.airsimHost,
        port: this.airsimPort,
        vehicle_name: this.telemetryName || "",
      };
      console.warn(
        `[AirSim] Telemetry connect: ${payload.host}:${payload.port} ${payload.vehicle_name || "default"}`,
      );
      this.resetTelemetryCalibration();
      this.setTelemetryCalibrationFromPlan();
      this.airsimBridge.startTelemetry(payload);
      this.setTelemetryActive(true);
    }

    handleStop() {
      if (this.webApiEnabled) {
        this.sendWebRequest("api/sim/stop", {});
        this.setPlayActive(false);
        return;
      }
      if (this.airsimBridge && this.airsimBridge.stopMission) {
        this.airsimBridge.stopMission();
      }
      if (this.airsimBridge && this.airsimBridge.stopTelemetry) {
        this.airsimBridge.stopTelemetry();
      }
      this.setTelemetryActive(false);
      this.setPlayActive(false);
      this.resetTelemetryCalibration();
      this.resetAirsimSettings();
    }

    async handleReset() {
      this.handleStop();
      this.setPlayActive(false);
      this.setTelemetryActive(false);
      this.resetTelemetryCalibration();
      this.resetAirsimSettings();
      this.resetPlan();
      this.resetSettingsPanel();
      this.toggleThemePanel(false);
      this.setBaseListOpen(false);
      if (typeof this.setTheme === "function") {
        this.setTheme("dark");
      }
      if (typeof this.setBuilding3dEnabled === "function") {
        this.setBuilding3dEnabled(false);
      }
      if (typeof this.setNoiseEnabled === "function") {
        this.setNoiseEnabled(false);
      }
      if (typeof this.setTransmissionEnabled === "function") {
        this.setTransmissionEnabled(false);
      }
      if (typeof this.setWeatherEnabled === "function") {
        this.setWeatherEnabled(false);
      }
      if (typeof this.setWindApplyMode === "function") {
        this.setWindApplyMode(false);
      }
      if (typeof this.setWindScenarioPreset === "function") {
        this.setWindScenarioPreset("good");
      }
      if (typeof this.clearWindLocalZones === "function") {
        this.clearWindLocalZones();
      }
      if (this.windRadiusInput) {
        const defaultValue = Number(this.windRadiusInput.defaultValue || this.windRadiusInput.value);
        if (Number.isFinite(defaultValue) && defaultValue > 0) {
          this.windRadiusInput.value = String(defaultValue);
          this.windLocalRadiusM = defaultValue;
        }
        if (typeof this.updateWindRadiusLabel === "function") {
          this.updateWindRadiusLabel();
        }
      }
      if (this.webApiEnabled) {
        const rulesPayload = this.rulesState ? { ...this.rulesState } : { ...DEFAULT_RULES };
        this.sendWebRequest("api/rules", rulesPayload);
        if (this.currentTrafficSelection) {
          this.sendWebRequest("api/traffic", { selection: this.currentTrafficSelection });
        }
      }
      this.clearDashboard();
      this.clearStatusLog();
      this.pendingDashboardTime_s = null;
      this.updateSimTime(0);
      this.updateFastLabel(1);
      if (typeof this.updateTrafficPositions === "function") {
        this.updateTrafficPositions([]);
      }
      this.resetWebPositionSync();
      if (typeof this.clearTrafficPrediction === "function") {
        this.clearTrafficPrediction();
      }
      if (typeof this.clearTrafficHistory === "function") {
        this.clearTrafficHistory();
      }
      if (typeof this.resetDatafilesToDefault === "function") {
        try {
          await this.resetDatafilesToDefault();
        } catch (error) {
          console.warn("Failed to reset datafiles.", error);
        }
      }
      this.resetStartScreen();
    }

    handleTelemetryUpdate(payload) {
      if (!payload || !this.map) {
        return;
      }
      const rawLat = Number(payload.lat);
      const rawLon = Number(payload.lon);
      let alt = Number(payload.alt_m);
      if (!Number.isFinite(rawLat) || !Number.isFinite(rawLon)) {
        return;
      }
      if (Number.isFinite(alt) && alt < 0) {
        alt = -alt;
        const now = Date.now();
        if (now - this.telemetryAltFlipLogAt > 2000) {
          this.telemetryAltFlipLogAt = now;
          console.warn("[AirSim] Telemetry altitude flipped from NED.");
        }
      }
      const adjusted = this.applyTelemetryCalibration(rawLat, rawLon, alt);
      const lat = adjusted.lat;
      const lon = adjusted.lon;
      alt = adjusted.alt;
      const name = payload.name ? String(payload.name) : this.telemetryName;
      this.telemetryName = name;
      this.telemetryPosition = [lon, lat];
      this.telemetryAltitude = Number.isFinite(alt) ? alt : null;
      if (!this.telemetryActive) {
        this.setTelemetryActive(true);
      }
      const now = Date.now();
      if (now - this.telemetryLogAt > 2000) {
        this.telemetryLogAt = now;
        console.warn(`[AirSim] Telemetry JS: ${name} ${lat.toFixed(6)}, ${lon.toFixed(6)}, ${alt.toFixed(2)}`);
      }
      this.ensureTelemetryMarker();
      if (!this.telemetryMarker) {
        return;
      }
      this.telemetryMarker.setLngLat([lon, lat]);
      if (this.telemetryLabel) {
        const altText = Number.isFinite(alt) ? `${alt.toFixed(1)} m` : "";
        this.telemetryLabel.textContent = altText ? `${name}\n${altText}` : name;
      }
      this.updateTelemetryTrack([lon, lat, Number.isFinite(alt) ? alt : 0]);
    }

    ensureTelemetryMarker() {
      if (this.telemetryMarker || !this.map) {
        return;
      }
      const marker = document.createElement("div");
      marker.className = "telemetry-marker";
      marker.addEventListener("click", (event) => {
        event.stopPropagation();
        this.toggleTelemetryTrack();
      });
      const dot = document.createElement("div");
      dot.className = "telemetry-marker-dot";
      const label = document.createElement("div");
      label.className = "telemetry-marker-label";
      label.textContent = this.telemetryName;
      marker.appendChild(dot);
      marker.appendChild(label);
      this.telemetryLabel = label;
      this.telemetryMarker = new maplibregl.Marker({
        element: marker,
        anchor: "bottom",
      })
        .setLngLat(this.map.getCenter().toArray())
        .addTo(this.map);
      console.warn("[AirSim] Telemetry marker created.");
    }

    ensureTelemetryTrackLayer() {
      if (!this.map || !this.map.isStyleLoaded()) {
        return false;
      }
      if (this.telemetryTrackLayer && this.map.getLayer(this.telemetryTrackLayer.id)) {
        return true;
      }
      const layer = this.createTelemetryTrackLayer();
      this.telemetryTrackLayer = layer;
      this.map.addLayer(layer);
      return true;
    }

    updateTelemetryTrack(coord) {
      if (!this.ensureTelemetryTrackLayer()) {
        return;
      }
      const last = this.telemetryTrackCoords[this.telemetryTrackCoords.length - 1];
      if (
        !last ||
        Math.abs(last[0] - coord[0]) > 1e-6 ||
        Math.abs(last[1] - coord[1]) > 1e-6 ||
        Math.abs((last[2] || 0) - (coord[2] || 0)) > 0.5
      ) {
        this.telemetryTrackCoords.push(coord);
        if (this.telemetryTrackCoords.length > this.telemetryTrackMaxPoints) {
          this.telemetryTrackCoords.splice(
            0,
            this.telemetryTrackCoords.length - this.telemetryTrackMaxPoints,
          );
        }
      }
      const buffers = this.buildTelemetryTrackBuffers();
      if (this.telemetryTrackLayer && this.telemetryTrackLayer.updateBuffers) {
        this.telemetryTrackLayer.updateBuffers(buffers);
      }
      if (this.telemetryTrackEnabled && this.map) {
        this.map.triggerRepaint();
      }
    }

    toggleTelemetryTrack() {
      this.telemetryTrackEnabled = !this.telemetryTrackEnabled;
      if (!this.map || !this.map.isStyleLoaded()) {
        return;
      }
      if (!this.ensureTelemetryTrackLayer()) {
        return;
      }
      if (this.telemetryTrackLayer && this.telemetryTrackLayer.setVisible) {
        this.telemetryTrackLayer.setVisible(this.telemetryTrackEnabled);
      }
      if (this.telemetryTrackEnabled) {
        const altitude = Number.isFinite(this.telemetryAltitude) ? this.telemetryAltitude : 0;
        const coord = this.telemetryPosition
          ? [this.telemetryPosition[0], this.telemetryPosition[1], altitude]
          : [...this.map.getCenter().toArray(), 0];
        this.updateTelemetryTrack(coord);
      }
      if (this.map) {
        this.map.triggerRepaint();
      }
      console.warn(
        `[AirSim] Telemetry track ${this.telemetryTrackEnabled ? "enabled" : "disabled"}.`,
      );
    }

    buildTelemetryTrackBuffers() {
      const linePositions = [];
      for (let i = 1; i < this.telemetryTrackCoords.length; i += 1) {
        const prev = this.telemetryTrackCoords[i - 1];
        const next = this.telemetryTrackCoords[i];
        const startAlt = Number.isFinite(prev[2]) ? prev[2] : 0;
        const endAlt = Number.isFinite(next[2]) ? next[2] : 0;
        const start = maplibregl.MercatorCoordinate.fromLngLat([prev[0], prev[1]], startAlt);
        const end = maplibregl.MercatorCoordinate.fromLngLat([next[0], next[1]], endAlt);
        linePositions.push(start.x, start.y, start.z, end.x, end.y, end.z);
      }
      return { linePositions };
    }

    createTelemetryTrackLayer() {
      const color = "#ffd447";
      const layer = {
        id: "telemetry-track-3d",
        type: "custom",
        renderingMode: "3d",
        _color: color,
        _lineCount: 0,
        _visible: false,
        setVisible(nextVisible) {
          this._visible = Boolean(nextVisible);
        },
        updateBuffers(buffers) {
          this._pendingBuffers = buffers;
          if (!this._gl || !this._lineBuffer) {
            return;
          }
          const gl = this._gl;
          const lineData = new Float32Array(buffers.linePositions);
          gl.bindBuffer(gl.ARRAY_BUFFER, this._lineBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, lineData, gl.STATIC_DRAW);
          this._lineCount = lineData.length / 3;
          this._pendingBuffers = null;
        },
        onAdd(_map, gl) {
          this._gl = gl;
          const vertexSource = `
            attribute vec3 a_pos;
            uniform mat4 u_matrix;
            void main() {
              gl_Position = u_matrix * vec4(a_pos, 1.0);
            }
          `;
          const fragmentSource = `
            precision mediump float;
            uniform vec4 u_color;
            void main() {
              gl_FragColor = u_color;
            }
          `;
          const compile = (type, source) => {
            const shader = gl.createShader(type);
            gl.shaderSource(shader, source);
            gl.compileShader(shader);
            return shader;
          };
          const vertexShader = compile(gl.VERTEX_SHADER, vertexSource);
          const fragmentShader = compile(gl.FRAGMENT_SHADER, fragmentSource);
          const program = gl.createProgram();
          gl.attachShader(program, vertexShader);
          gl.attachShader(program, fragmentShader);
          gl.linkProgram(program);
          this._program = program;
          this._aPos = gl.getAttribLocation(program, "a_pos");
          this._uMatrix = gl.getUniformLocation(program, "u_matrix");
          this._uColor = gl.getUniformLocation(program, "u_color");
          this._lineBuffer = gl.createBuffer();
          gl.bindBuffer(gl.ARRAY_BUFFER, this._lineBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([]), gl.STATIC_DRAW);
          if (this._pendingBuffers) {
            this.updateBuffers(this._pendingBuffers);
          }
        },
        render(gl, matrix) {
          if (!this._program || !this._visible) {
            return;
          }
          gl.useProgram(this._program);
          gl.uniformMatrix4fv(this._uMatrix, false, matrix);
          const rgba = hexToRgba(this._color, 0.95);
          gl.uniform4fv(this._uColor, rgba);
          gl.enableVertexAttribArray(this._aPos);
          gl.enable(gl.BLEND);
          gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
          if (this._lineCount > 0) {
            gl.bindBuffer(gl.ARRAY_BUFFER, this._lineBuffer);
            gl.vertexAttribPointer(this._aPos, 3, gl.FLOAT, false, 0, 0);
            gl.lineWidth(2 * MAP_SIZE_SCALE);
            gl.drawArrays(gl.LINES, 0, this._lineCount);
          }
        },
      };
      return layer;
    }

    setTelemetryActive(isActive) {
      this.telemetryActive = isActive;
      if (this.playbackConnectButton) {
        this.playbackConnectButton.classList.toggle("is-active", isActive);
      }
      if (this.syncEditModeAvailability) {
        this.syncEditModeAvailability();
      }
    }

    setPlayActive(isActive) {
      this.isPlaying = isActive;
      if (this.playbackPlayButton) {
        this.playbackPlayButton.classList.toggle("is-active", isActive);
        this.playbackPlayButton.disabled = isActive;
        this.playbackPlayButton.setAttribute("aria-disabled", isActive ? "true" : "false");
      }
      if (this.syncEditModeAvailability) {
        this.syncEditModeAvailability();
      }
      if (
        isActive &&
        this.panels &&
        this.panels.corridor &&
        this.panels.corridor.classList.contains("is-visible")
      ) {
        this.hidePanel("corridor");
        this.addStatusMessage({
          text: this.t("status.edit_disabled"),
          level: "warn",
          ttlMs: 2500,
        });
      }
    }

    resetTelemetryCalibration() {
      this.telemetryCalibration = null;
    }

    setTelemetryCalibrationTarget(target) {
      if (!target) {
        return;
      }
      const lat = Number(target.lat);
      const lon = Number(target.lon);
      const alt = Number(target.alt_m);
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
        return;
      }
      this.telemetryCalibration = {
        target: {
          lat,
          lon,
          alt_m: Number.isFinite(alt) ? alt : 0,
        },
        source: null,
        rotation_deg: this.telemetryRotationDeg,
      };
      console.warn(
        `[AirSim] Telemetry calibration target: ${lat.toFixed(6)}, ${lon.toFixed(6)}, ` +
          `${Number.isFinite(alt) ? alt.toFixed(2) : "0.00"}`,
      );
      console.warn(
        `[AirSim] Telemetry calibration rotation: ${this.telemetryRotationDeg.toFixed(1)} deg`,
      );
    }

    setTelemetryCalibrationFromPlan() {
      let target = null;
      if (this.planState && Array.isArray(this.planState.selection) && this.planState.selection.length) {
        const name = this.planState.selection[0];
        const geo = this.resolveNodeGeodetic(name);
        if (geo && Number.isFinite(geo.lat) && Number.isFinite(geo.lon)) {
          target = {
            lat: geo.lat,
            lon: geo.lon,
            alt_m: Number.isFinite(geo.altitude_m) ? geo.altitude_m : 0,
          };
        }
      }
      if (!target && this.appliedPlan.length) {
        const start = this.appliedPlan[0];
        target = {
          lat: start.lat,
          lon: start.lon,
          alt_m: start.altitude_m,
        };
      }
      if (!target) {
        return;
      }
      this.setTelemetryCalibrationTarget(target);
    }

    applyTelemetryCalibration(lat, lon, alt) {
      if (!this.telemetryCalibration || !this.telemetryCalibration.target) {
        return { lat, lon, alt, calibrated: false };
      }
      const target = this.telemetryCalibration.target;
      if (!this.telemetryCalibration.source) {
        const baseAlt = Number.isFinite(alt) ? alt : target.alt_m;
        this.telemetryCalibration.source = {
          lat,
          lon,
          alt_m: baseAlt,
        };
        console.warn(
          `[AirSim] Telemetry calibration source: ${lat.toFixed(6)}, ${lon.toFixed(6)}, ` +
            `${Number.isFinite(baseAlt) ? baseAlt.toFixed(2) : "0.00"}`,
        );
      }
      const source = this.telemetryCalibration.source;
      const baseAlt = Number.isFinite(alt) ? alt : source.alt_m;
      const [e, n, u] = geodeticToEnu(lat, lon, source.lat, source.lon, baseAlt, source.alt_m);
      const [eRot, nRot] = rotateEnu(e, n, this.telemetryCalibration.rotation_deg);
      const adjusted = enuToGeodetic(eRot, nRot, u, target.lat, target.lon, target.alt_m);
      return {
        lat: adjusted.lat,
        lon: adjusted.lon,
        alt: adjusted.alt,
        calibrated: true,
      };
    }

    setupPlanInteractions() {
      if (!this.map) {
        return;
      }
      this.map.on("click", (event) => this.handlePlanClick(event));
      window.addEventListener("keydown", (event) => this.handlePlanKeyDown(event));
    }

    togglePlanSelection() {
      this.planState.enabled = !this.planState.enabled;
      console.warn(`[UI] Plan select ${this.planState.enabled ? "on" : "off"}`);
      if (this.planControls.selectButton) {
        this.planControls.selectButton.classList.toggle("is-active", this.planState.enabled);
      }
      if (this.planState.enabled && this.planState.selection.length < 2) {
        this.clearCorridorHover();
        this.clearVertiportHover();
      }
      if (!this.planState.enabled && this.map) {
        this.map.getCanvas().style.cursor = "";
      }
    }

    resetPlan() {
      this.resetPlanState();
      this.appliedPlan = [];
      this.planRoute = [];
      this.resetTelemetryCalibration();
    }

    applyPlan() {
      const result = this.computePlanRoute();
      if (!result || !result.path.length) {
        console.warn("No route to apply.");
        return;
      }
      this.planRoute = result.path;
      this.setPlanRoute(result.path);
      this.appliedPlan = this.buildPlanPoints(result.path);
      this.printPlanRoute(this.appliedPlan);
      this.setTelemetryCalibrationFromPlan();
      this.activeEdges = [];
      this.updateActiveEdges();
      this.planState.manualPath = [];
      this.planState.manualPrev = null;
      this.planState.manualCurrent = null;
      this.updateManualPreview();
      this.hidePanel("plan");
    }

    getPlanForMission() {
      if (this.appliedPlan.length) {
        return this.appliedPlan;
      }
      const result = this.computePlanRoute();
      if (!result || !result.path.length) {
        return [];
      }
      this.planRoute = result.path;
      this.setPlanRoute(result.path);
      this.appliedPlan = this.buildPlanPoints(result.path);
      return this.appliedPlan;
    }

    resetPlanState() {
      this.planState.mode = null;
      this.planState.selection = [];
      this.planState.viaNodes = [];
      this.planState.manualPath = [];
      this.planState.manualPrev = null;
      this.planState.manualCurrent = null;
      this.activeEdges = [];
      this.clearPlanRoute();
      this.updatePlanSelection();
      this.updateViaPoints();
      this.updateActiveEdges();
      this.updateManualPreview();
    }

    handlePlanClick(event) {
      if (this.windApplyMode) {
        return;
      }
      if (this.handleEmergencyLandingClick && this.handleEmergencyLandingClick(event)) {
        return;
      }
      if (this.handleForceMoveClick && this.handleForceMoveClick(event)) {
        return;
      }
      if (!this.planState.enabled || !this.map || !this.map.isStyleLoaded()) {
        return;
      }
      const selection = this.planState.selection;
      const portPick = this.pickVertiportAt(event.point);
      if (selection.length < 2) {
        if (!portPick) {
          console.warn("[UI] Plan pick miss.");
          return;
        }
        console.warn(`[UI] Plan pick: ${portPick}`);
        if (!selection.length) {
          this.planState.selection = [portPick];
          this.updatePlanSelection();
          return;
        }
        if (portPick === selection[0]) {
          return;
        }
        this.planState.selection = [selection[0], portPick];
        this.planState.mode = null;
        this.planState.viaNodes = [];
        this.planState.manualPath = [];
        this.planState.manualPrev = null;
        this.planState.manualCurrent = null;
        this.updatePlanSelection();
        this.updateViaPoints();
        this.updateManualPreview();
        this.setActiveEdges(this.planState.selection[0], null);
        return;
      }

      if (portPick) {
        this.resetPlanState();
        this.planState.selection = [portPick];
        this.updatePlanSelection();
        return;
      }

      if (!this.planState.mode) {
        const edgePick = this.pickActiveEdge(event.point);
        if (edgePick) {
          this.planState.mode = "manual";
          this.planState.manualPath = [edgePick.from, edgePick.to];
          this.planState.manualPrev = edgePick.from;
          this.planState.manualCurrent = edgePick.to;
          this.updateManualPreview();
          if (edgePick.to === selection[1]) {
            this.activeEdges = [];
            this.updateActiveEdges();
          } else {
            this.setActiveEdges(edgePick.to, edgePick.from);
          }
          return;
        }

        const wpPick = this.pickCorridorPoint(event.point);
        if (wpPick) {
          this.planState.mode = "via";
          this.addViaNode(wpPick);
          return;
        }
        return;
      }

      if (this.planState.mode === "manual") {
        const edgePick = this.pickActiveEdge(event.point);
        if (!edgePick) {
          return;
        }
        if (!this.planState.manualCurrent) {
          return;
        }
        const nextNode = edgePick.to;
        this.planState.manualPath = [...this.planState.manualPath, nextNode];
        this.planState.manualPrev = this.planState.manualCurrent;
        this.planState.manualCurrent = nextNode;
        this.updateManualPreview();
        if (nextNode === selection[1]) {
          this.activeEdges = [];
          this.updateActiveEdges();
        } else {
          this.setActiveEdges(nextNode, this.planState.manualPrev);
        }
        return;
      }

      if (this.planState.mode === "via") {
        const wpPick = this.pickCorridorPoint(event.point);
        if (!wpPick) {
          return;
        }
        this.addViaNode(wpPick);
      }
    }

    pickVertiportAt(point) {
      if (!this.map) {
        return null;
      }
      const layers = [];
      if (this.map.getLayer("vertiport-icon")) {
        layers.push("vertiport-icon");
      }
      if (this.map.getLayer("vertiport-circle")) {
        layers.push("vertiport-circle");
      }
      if (!layers.length) {
        return null;
      }
      const features = this.map.queryRenderedFeatures(point, { layers });
      if (!features.length) {
        return null;
      }
      const name = features[0].properties ? String(features[0].properties.name || "") : "";
      return name || null;
    }

    pickBaseStationAt(point) {
      if (!this.map) {
        return null;
      }
      const layers = [];
      if (this.map.getLayer("basestation-icon")) {
        layers.push("basestation-icon");
      }
      if (!layers.length) {
        return null;
      }
      const features = this.map.queryRenderedFeatures(point, { layers });
      if (!features.length) {
        return null;
      }
      const name = features[0].properties ? String(features[0].properties.name || "") : "";
      return name || null;
    }

    pickCorridorPoint(point) {
      if (!this.corridorLayer || !this.corridorLayer.getMatrix) {
        return null;
      }
      const matrix = this.corridorLayer.getMatrix();
      if (!matrix) {
        return null;
      }
      const target = this.findCorridorHoverTarget(point, matrix);
      if (!target || target.type !== "point") {
        return null;
      }
      return target.name || null;
    }

    pickActiveEdge(point) {
      if (!this.map || !this.map.getLayer("flight-plan-active-links-hit")) {
        return null;
      }
      const features = this.map.queryRenderedFeatures(point, {
        layers: ["flight-plan-active-links-hit"],
      });
      if (!features.length) {
        return null;
      }
      const feature = features[0];
      const from = feature.properties ? String(feature.properties.from || "") : "";
      const to = feature.properties ? String(feature.properties.to || "") : "";
      if (!from || !to) {
        return null;
      }
      return { from, to };
    }

    addViaNode(name) {
      if (this.planState.viaNodes.includes(name)) {
        return;
      }
      this.planState.viaNodes = [...this.planState.viaNodes, name];
      this.updateViaPoints();
      this.updatePlanRoutePreview();
    }

    handlePlanKeyDown(event) {
      if (event.key !== "Enter") {
        return;
      }
      const target = event.target;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.tagName === "BUTTON" ||
          target.isContentEditable)
      ) {
        return;
      }
      if (!this.planState.selection || this.planState.selection.length < 2) {
        return;
      }
      const result = this.computePlanRoute();
      if (!result || !result.path.length) {
        console.warn("No route to plan.");
        return;
      }
      this.planRoute = result.path;
      this.setPlanRoute(result.path);
      this.printPlanRoute(this.buildPlanPoints(result.path));
      this.activeEdges = [];
      this.updateActiveEdges();
      this.updateManualPreview();
      event.preventDefault();
    }

    updatePlanSelection() {
      if (!this.map) {
        return;
      }
      if (!this.map.getSource("flight-plan-selection")) {
        this.updatePlanSelectionMarkers();
        return;
      }
      const features = [];
      const [start, end] = this.planState.selection;
      if (start && this.vertiportPointLookup.has(start)) {
        const entry = this.vertiportPointLookup.get(start);
        features.push({
          type: "Feature",
          geometry: { type: "Point", coordinates: entry.coord },
          properties: { role: "start", name: entry.name },
        });
      }
      if (end && this.vertiportPointLookup.has(end)) {
        const entry = this.vertiportPointLookup.get(end);
        features.push({
          type: "Feature",
          geometry: { type: "Point", coordinates: entry.coord },
          properties: { role: "end", name: entry.name },
        });
      }
      this.map.getSource("flight-plan-selection").setData({
        type: "FeatureCollection",
        features,
      });
      this.updatePlanSelectionMarkers();
    }

    updatePlanSelectionMarkers() {
      if (!this.map) {
        return;
      }
      const [start, end] = this.planState.selection;
      this.updatePlanSelectionMarker("start", start, "S");
      this.updatePlanSelectionMarker("end", end, "E");
    }

    updatePlanSelectionMarker(key, name, label) {
      const current = this.planSelectionMarkers[key];
      if (!name || !this.vertiportPointLookup.has(name)) {
        if (current) {
          current.remove();
          this.planSelectionMarkers[key] = null;
        }
        return;
      }
      const entry = this.vertiportPointLookup.get(name);
      if (!entry) {
        return;
      }
      if (current) {
        current.setLngLat(entry.coord);
        current.getElement().textContent = label;
        return;
      }
      const marker = document.createElement("div");
      marker.className = "flight-plan-label";
      marker.textContent = label;
      this.planSelectionMarkers[key] = new maplibregl.Marker({
        element: marker,
        anchor: "center",
      })
        .setLngLat(entry.coord)
        .addTo(this.map);
    }

    updateViaPoints() {
      if (!this.map || !this.map.getSource("flight-plan-via")) {
        return;
      }
      const features = this.planState.viaNodes
        .map((name) => {
          const entry = this.routeNodeLookup.get(name);
          if (!entry) {
            return null;
          }
          return {
            type: "Feature",
            geometry: { type: "Point", coordinates: entry.coord },
            properties: { name: entry.name },
          };
        })
        .filter(Boolean);
      this.map.getSource("flight-plan-via").setData({
        type: "FeatureCollection",
        features,
      });
    }

    bindThemeToggle() {
      if (!this.themeToggleButton || !this.themePanel) {
        return;
      }
      this.themeToggleButton.addEventListener("click", () => {
        this.toggleThemePanel();
      });
    }

    bindBaseToggle() {
      if (!this.baseToggleButton) {
        return;
      }
      this.baseToggleButton.addEventListener("click", () => {
        this.toggleThemePanel(false);
        this.toggleBasePanelWindow();
        this.syncBaseToggleState();
      });
    }

    isBaseListOpen() {
      return Boolean(this.themePanel && this.themePanel.classList.contains("is-base-open"));
    }

    setBaseListOpen(shouldOpen) {
      if (!this.themePanel) {
        return;
      }
      const next = Boolean(shouldOpen);
      this.themePanel.classList.toggle("is-base-open", next);
      if (this.baseList) {
        this.baseList.setAttribute("aria-hidden", next ? "false" : "true");
      }
      if (this.baseToggleButton) {
        this.baseToggleButton.classList.toggle("is-active", next);
        this.baseToggleButton.setAttribute("aria-expanded", next ? "true" : "false");
      }
    }

    disableOtherBaseLayers(activeKey) {
      const active = String(activeKey || "").toLowerCase();
      const layers = [
        {
          key: "noise",
          isEnabled: () => Boolean(this.noiseEnabled),
          disable: () => {
            if (typeof this.setNoiseEnabled === "function") {
              this.setNoiseEnabled(false);
            }
          },
        },
        {
          key: "transmission",
          isEnabled: () => Boolean(this.transmissionEnabled),
          disable: () => {
            if (typeof this.setTransmissionEnabled === "function") {
              this.setTransmissionEnabled(false);
            }
          },
        },
        {
          key: "density",
          isEnabled: () => Boolean(this.densityEnabled),
          disable: () => {
            if (typeof this.setDensityEnabled === "function") {
              this.setDensityEnabled(false);
            }
          },
        },
        {
          key: "segment-congestion",
          isEnabled: () => Boolean(this.congestionEnabled),
          disable: () => {
            if (typeof this.setCongestionEnabled === "function") {
              this.setCongestionEnabled(false);
            }
          },
        },
        {
          key: "impact-field",
          isEnabled: () => this.fieldLayerMode === "impact-field",
          disable: () => {
            if (typeof this.setFieldLayerMode === "function") {
              this.setFieldLayerMode(null);
            }
          },
        },
        {
          key: "density-field",
          isEnabled: () => this.fieldLayerMode === "density-field",
          disable: () => {
            if (typeof this.setFieldLayerMode === "function") {
              this.setFieldLayerMode(null);
            }
          },
        },
        {
          key: "congestion-field",
          isEnabled: () => this.fieldLayerMode === "congestion-field",
          disable: () => {
            if (typeof this.setFieldLayerMode === "function") {
              this.setFieldLayerMode(null);
            }
          },
        },
      ];
      layers.forEach((entry) => {
        if (!entry || entry.key === active) {
          return;
        }
        try {
          if (entry.isEnabled()) {
            entry.disable();
          }
        } catch (_err) {
          // best-effort
        }
      });
    }

    bindBaseControls() {
      if (!this.baseControls || !this.baseControls.layer3dButton) {
        return;
      }
      this.baseControls.layer3dButton.addEventListener("click", () => {
        this.setBuilding3dEnabled(!this.building3dEnabled);
        this.setBaseListOpen(false);
      });
    }

    toggleThemePanel(forceState) {
      if (!this.themePanel || !this.themeToggleButton) {
        return;
      }
      const shouldOpen =
        typeof forceState === "boolean"
          ? forceState
          : !this.themePanel.classList.contains("is-open");
      this.themePanel.classList.toggle("is-open", shouldOpen);
      this.themeToggleButton.classList.toggle("is-active", shouldOpen);
      this.themeToggleButton.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
      if (shouldOpen && this.isBaseListOpen()) {
        this.setBaseListOpen(false);
      }
    }

    syncBaseToggleState() {
      if (!this.baseToggleButton) {
        return;
      }
      const isOpen = this.isBaseListOpen();
      this.baseToggleButton.classList.toggle("is-active", isOpen);
      this.baseToggleButton.setAttribute("aria-expanded", isOpen ? "true" : "false");
      if (this.baseList) {
        this.baseList.setAttribute("aria-hidden", isOpen ? "false" : "true");
      }
    }

    toggleBasePanelWindow() {
      const next = !this.isBaseListOpen();
      this.setBaseListOpen(next);
    }

    setBuilding3dEnabled(enabled) {
      const next = Boolean(enabled);
      this.building3dEnabled = next;
      if (this.baseControls && this.baseControls.layer3dButton) {
        this.baseControls.layer3dButton.classList.toggle("is-active", next);
      }
      if (!this.map || !this.map.isStyleLoaded()) {
        this.building3dPending = next;
        return;
      }
      this.building3dPending = false;
      this.ensureBuilding3dLayer();
      const visibility = next ? "visible" : "none";
      if (this.map.getLayer(BUILDING_3D_LAYER_ID)) {
        try {
          this.map.setLayoutProperty(BUILDING_3D_LAYER_ID, "visibility", visibility);
        } catch (error) {
          console.warn("Failed to toggle 3D layer visibility.", error);
        }
      }
      if (this.map.getLayer(BUILDING_2D_LAYER_ID)) {
        try {
          this.map.setLayoutProperty(BUILDING_2D_LAYER_ID, "visibility", next ? "none" : "visible");
        } catch (error) {
          console.warn("Failed to toggle 2D layer visibility.", error);
        }
      }
      this.map.triggerRepaint();
    }

    ensureBuilding3dLayer() {
      if (!this.map || this.map.getLayer(BUILDING_3D_LAYER_ID)) {
        return;
      }
      if (!this.map.getSource("mbtiles")) {
        this.addStatusMessage({
          text: this.t("status.layer_unavailable"),
          level: "warn",
          ttlMs: 2500,
        });
        return;
      }
      const beforeId = this.map.getLayer("corridor-3d") ? "corridor-3d" : null;
      const layer = {
        id: BUILDING_3D_LAYER_ID,
        type: "fill-extrusion",
        source: "mbtiles",
        "source-layer": "building",
        minzoom: BUILDING_3D_MIN_ZOOM,
        layout: { visibility: "none" },
        paint: {
          "fill-extrusion-color": BUILDING_3D_COLOR,
          "fill-extrusion-opacity": BUILDING_3D_OPACITY,
          "fill-extrusion-height": [
            "min",
            BUILDING_3D_MAX_HEIGHT,
            [
              "*",
              BUILDING_3D_HEIGHT_SCALE,
              ["coalesce", ["get", "render_height"], ["get", "height"], 12],
            ],
          ],
          "fill-extrusion-base": [
            "*",
            BUILDING_3D_HEIGHT_SCALE,
            ["coalesce", ["get", "render_min_height"], ["get", "min_height"], 0],
          ],
          "fill-extrusion-vertical-gradient": true,
        },
      };
      if (beforeId) {
        this.map.addLayer(layer, beforeId);
      } else {
        this.map.addLayer(layer);
      }
      if (this.reorderPlanLayers) {
        this.reorderPlanLayers();
      }
    }

    setActiveEdges(current, prev) {
      if (!this.routeGraph || !current) {
        this.activeEdges = [];
        this.updateActiveEdges();
        return;
      }
      const neighbors = this.routeGraph.get(current) || [];
      const endPort = this.planState.selection[1];
      const isPort = (name) => this.vertiportPointLookup.has(name);
      this.activeEdges = neighbors
        .filter((name) => name !== prev)
        .filter((name) => !isPort(name) || name === endPort)
        .map((name) => ({ from: current, to: name }));
      this.updateActiveEdges();
    }

    updateActiveEdges() {
      if (!this.map || !this.map.getSource("flight-plan-active-links")) {
        return;
      }
      const features = this.activeEdges
        .map((edge, index) => {
          const start = this.routeNodeLookup.get(edge.from);
          const end = this.routeNodeLookup.get(edge.to);
          if (!start || !end) {
            return null;
          }
          return {
            type: "Feature",
            id: index,
            geometry: {
              type: "LineString",
              coordinates: [start.coord, end.coord],
            },
            properties: { from: edge.from, to: edge.to },
          };
        })
        .filter(Boolean);
      const collection = { type: "FeatureCollection", features };
      this.map.getSource("flight-plan-active-links").setData(collection);
      if (this.map.getSource("flight-plan-active-links-hit")) {
        this.map.getSource("flight-plan-active-links-hit").setData(collection);
      }
    }

    updateManualPreview() {
      if (!this.map || !this.map.getSource("flight-plan-manual-preview")) {
        return;
      }
      const coords = this.planState.manualPath
        .map((name) => this.routeNodeLookup.get(name))
        .filter(Boolean)
        .map((entry) => entry.coord);
      const features =
        coords.length >= 2
          ? [
              {
                type: "Feature",
                geometry: { type: "LineString", coordinates: coords },
                properties: {},
              },
            ]
          : [];
      this.map.getSource("flight-plan-manual-preview").setData({
        type: "FeatureCollection",
        features,
      });
    }

    updatePlanRoutePreview() {
      if (!this.planState.mode || this.planState.mode === "manual") {
        return;
      }
      const result = this.computePlanRoute();
      if (!result || !result.path.length) {
        this.clearPlanRoute();
        return;
      }
      this.setPlanRoute(result.path);
    }

    refreshRouteGraph() {
      if (!this.corridorData || !this.vertiportData) {
        return;
      }
      const nodeLookup = new Map();
      this.corridorData.points.forEach((entry) => nodeLookup.set(entry.name, entry));
      this.vertiportData.points.forEach((entry) => nodeLookup.set(entry.name, entry));
      this.routeNodeLookup = nodeLookup;

      const nodes = Array.from(nodeLookup.values());
      if (!nodes.length) {
        return;
      }
      const lon0 = nodes.reduce((sum, entry) => sum + entry.coord[0], 0) / nodes.length;
      const lat0 = nodes.reduce((sum, entry) => sum + entry.coord[1], 0) / nodes.length;
      const kmPerDegLat = 111.32;
      const kmPerDegLon = 111.32 * Math.cos((lat0 * Math.PI) / 180);
      this.routeProjection = { lon0, lat0, kmPerDegLat, kmPerDegLon };
      const nodeXY = new Map();
      nodes.forEach((entry) => {
        const dx = (entry.coord[0] - lon0) * kmPerDegLon;
        const dy = (entry.coord[1] - lat0) * kmPerDegLat;
        nodeXY.set(entry.name, [dx, dy]);
      });
      this.routeNodeXY = nodeXY;

      const graph = new Map();
      const addEdge = (a, b) => {
        if (!graph.has(a)) {
          graph.set(a, new Set());
        }
        graph.get(a).add(b);
      };

      this.corridorData.lines.forEach((line) => {
        addEdge(line.from, line.to);
        addEdge(line.to, line.from);
      });
      if (
        this.openSpareCorridorEdges &&
        this.openSpareCorridorEdges.size &&
        this.corridorData.spareLines
      ) {
        const keyFor =
          typeof this.getCorridorEdgeKey === "function"
            ? (a, b) => this.getCorridorEdgeKey(a, b)
            : (a, b) => [String(a || ""), String(b || "")].sort().join("|");
        this.corridorData.spareLines.forEach((line) => {
          const key = keyFor(line.from, line.to);
          if (key && this.openSpareCorridorEdges.has(key)) {
            addEdge(line.from, line.to);
            addEdge(line.to, line.from);
          }
        });
      }
      this.vertiportData.lines.forEach((line) => {
        addEdge(line.from, line.to);
        addEdge(line.to, line.from);
      });

      const finalized = new Map();
      nodeLookup.forEach((_entry, name) => {
        finalized.set(name, graph.has(name) ? Array.from(graph.get(name)) : []);
      });
      this.routeGraph = finalized;
      this.updatePlanSelection();
      this.updateViaPoints();
      this.updateActiveEdges();
      this.updateManualPreview();
      this.updatePlanRoutePreview();
    }

    computePlanRoute() {
      const selection = this.planState.selection;
      if (!selection || selection.length < 2) {
        return null;
      }
      this.ensureRouteGraph();
      if (!this.routeGraph) {
        return null;
      }
      const start = selection[0];
      const end = selection[1];
      if (this.planState.mode === "manual" && this.planState.manualPath.length) {
        const manualPath = this.planState.manualPath;
        let total = 0;
        for (let i = 0; i < manualPath.length - 1; i += 1) {
          total += this.distanceKm(manualPath[i], manualPath[i + 1]);
        }
        const combined = [...manualPath];
        if (manualPath[manualPath.length - 1] !== end) {
          const tail = this.shortestPath(manualPath[manualPath.length - 1], end);
          if (!tail || !tail.path.length) {
            return null;
          }
          combined.push(...tail.path.slice(1));
          total += tail.distanceKm;
        }
        return { path: combined, distanceKm: total };
      }
      if (this.planState.mode === "via" && this.planState.viaNodes.length) {
        return this.findRouteVia(start, end, this.planState.viaNodes);
      }
      return this.shortestPath(start, end);
    }

    ensureRouteGraph() {
      if (this.routeGraph) {
        return;
      }
      if (!this.corridorData && this.lastCorridorRows) {
        this.corridorData = this.buildCorridorFeatures(this.lastCorridorRows);
        this.corridorPointLookup = new Map(
          this.corridorData.points.map((entry) => [entry.name, entry]),
        );
      }
      if (!this.vertiportData && this.lastVertiportRows) {
        this.vertiportData = this.buildVertiportFeatures(this.lastVertiportRows);
        this.vertiportPointLookup = new Map(
          this.vertiportData.points.map((entry) => [entry.name, entry]),
        );
        this.vertiportLinkLookup = new Map(
          this.vertiportData.points.map((entry) => [entry.name, entry.links || []]),
        );
      }
      if (this.corridorData && this.vertiportData) {
        this.refreshRouteGraph();
      }
    }

    findRouteVia(start, end, viaNodes) {
      const sequence = [start, ...viaNodes, end];
      let fullPath = [];
      let total = 0;
      for (let i = 0; i < sequence.length - 1; i += 1) {
        const segment = this.shortestPath(sequence[i], sequence[i + 1]);
        if (!segment || !segment.path.length) {
          return null;
        }
        if (fullPath.length) {
          fullPath = [...fullPath, ...segment.path.slice(1)];
        } else {
          fullPath = [...segment.path];
        }
        total += segment.distanceKm;
      }
      return { path: fullPath, distanceKm: total };
    }

    shortestPath(start, end) {
      if (!this.routeGraph || !this.routeGraph.has(start) || !this.routeGraph.has(end)) {
        return null;
      }
      if (start === end) {
        return { path: [start], distanceKm: 0 };
      }
      const dist = new Map([[start, 0]]);
      const prev = new Map([[start, null]]);
      const queue = [[0, start]];
      const isPort = (name) => this.vertiportPointLookup.has(name);

      while (queue.length) {
        queue.sort((a, b) => a[0] - b[0]);
        const [cost, node] = queue.shift();
        if (node === end) {
          break;
        }
        if (cost !== dist.get(node)) {
          continue;
        }
        const neighbors = this.routeGraph.get(node) || [];
        neighbors.forEach((nxt) => {
          if (isPort(nxt) && nxt !== end) {
            return;
          }
          const nextCost = cost + this.distanceKm(node, nxt);
          const existing = dist.get(nxt);
          if (existing === undefined || nextCost < existing) {
            dist.set(nxt, nextCost);
            prev.set(nxt, node);
            queue.push([nextCost, nxt]);
          }
        });
      }

      if (!dist.has(end)) {
        return null;
      }
      const path = [];
      let cur = end;
      while (cur) {
        path.push(cur);
        cur = prev.get(cur);
      }
      path.reverse();
      return { path, distanceKm: dist.get(end) || 0 };
    }

    distanceKm(a, b) {
      const axy = this.routeNodeXY.get(a);
      const bxy = this.routeNodeXY.get(b);
      if (!axy || !bxy) {
        return 0;
      }
      const dx = bxy[0] - axy[0];
      const dy = bxy[1] - axy[1];
      return Math.hypot(dx, dy);
    }

    ensurePlanLayers() {
      if (!this.map || !this.map.isStyleLoaded() || this.planLayersReady) {
        return;
      }
      const map = this.map;
      const empty = { type: "FeatureCollection", features: [] };
      if (!map.getSource("flight-plan-selection")) {
        map.addSource("flight-plan-selection", { type: "geojson", data: empty });
      }
      if (!map.getSource("flight-plan-route")) {
        map.addSource("flight-plan-route", { type: "geojson", data: empty });
      }
      if (!map.getSource("flight-plan-via")) {
        map.addSource("flight-plan-via", { type: "geojson", data: empty });
      }
      if (!map.getSource("flight-plan-active-links")) {
        map.addSource("flight-plan-active-links", { type: "geojson", data: empty });
      }
      if (!map.getSource("flight-plan-active-links-hit")) {
        map.addSource("flight-plan-active-links-hit", { type: "geojson", data: empty });
      }
      if (!map.getSource("flight-plan-manual-preview")) {
        map.addSource("flight-plan-manual-preview", { type: "geojson", data: empty });
      }

      if (!map.getLayer("flight-plan-route")) {
        map.addLayer({
          id: "flight-plan-route",
          type: "line",
          source: "flight-plan-route",
          layout: { "line-join": "round", "line-cap": "round" },
          paint: {
            "line-color": "#ff2fd6",
            "line-width": 2 * MAP_SIZE_SCALE,
          },
        });
      }

      if (!map.getLayer("flight-plan-manual-preview")) {
        map.addLayer({
          id: "flight-plan-manual-preview",
          type: "line",
          source: "flight-plan-manual-preview",
          layout: { "line-join": "round", "line-cap": "round" },
          paint: {
            "line-color": "#7cff62",
            "line-width": 2 * MAP_SIZE_SCALE,
            "line-dasharray": [1.5, 1.2],
          },
        });
      }

      if (!map.getLayer("flight-plan-active-links")) {
        map.addLayer({
          id: "flight-plan-active-links",
          type: "line",
          source: "flight-plan-active-links",
          layout: { "line-join": "round", "line-cap": "round" },
          paint: {
            "line-color": "#7cff62",
            "line-width": 2.5 * MAP_SIZE_SCALE,
          },
        });
      }

      if (!map.getLayer("flight-plan-active-links-hit")) {
        map.addLayer({
          id: "flight-plan-active-links-hit",
          type: "line",
          source: "flight-plan-active-links-hit",
          layout: { "line-join": "round", "line-cap": "round" },
          paint: {
            "line-color": "#000000",
            "line-opacity": 0.01,
            "line-width": 10 * MAP_SIZE_SCALE,
          },
        });
      }

      if (!map.getLayer("flight-plan-via-points")) {
        map.addLayer({
          id: "flight-plan-via-points",
          type: "circle",
          source: "flight-plan-via",
          paint: {
            "circle-radius": 6 * MAP_SIZE_SCALE,
            "circle-color": "#8d6bff",
            "circle-stroke-color": "#1a1a1a",
            "circle-stroke-width": 1.5 * MAP_SIZE_SCALE,
          },
        });
      }

      if (!map.getLayer("flight-plan-selection")) {
        map.addLayer({
          id: "flight-plan-selection",
          type: "circle",
          source: "flight-plan-selection",
          paint: {
            "circle-radius": 7 * MAP_SIZE_SCALE,
            "circle-color": [
              "case",
              ["==", ["get", "role"], "start"],
              "#2ecc71",
              "#ff5f5f",
            ],
            "circle-stroke-color": "#1a1a1a",
            "circle-stroke-width": 2 * MAP_SIZE_SCALE,
          },
        });
      }

      if (!this.planRouteLayer3d) {
        this.planRouteLayer3d = this.createLineLayer3d(
          "flight-plan-route-3d",
          "#ff2fd6",
          "LINE_STRIP",
        );
        map.addLayer(this.planRouteLayer3d);
      }

      if (!this.vertiportLinks3dLayer) {
        this.vertiportLinks3dLayer = this.createLineLayer3d(
          "vertiport-links-3d",
          VERTIPORT_LINE_COLOR,
          "TRIANGLES",
          VERTIPORT_LINE_HOVER_COLOR,
          VERTIPORT_LINK_WIDTH_3D,
        );
        if (this.vertiportLinks3dLayer.setVerticesPerLine) {
          this.vertiportLinks3dLayer.setVerticesPerLine(12);
        } else {
          this.vertiportLinks3dLayer._verticesPerLine = 12;
        }
        this.vertiportLinks3dLayer._useDepth = false;
        map.addLayer(this.vertiportLinks3dLayer);
      }
      this.reorderPlanLayers();
      this.planLayersReady = true;
    }

    reorderPlanLayers() {
      if (!this.map) {
        return;
      }
      const baseOrder = [
        "building-3d",
        "corridor-spare-links-3d",
        "corridor-spare-open-3d",
          "corridor-links-3d",
        "corridor-link-preview",
        "corridor-3d",
        "corridor-closed-3d",
        "corridor-timer-markers",
        "corridor-timer-badges",
        "corridor-timer-labels",
        "corridor-edit-ring",
        "corridor-edit-circle",
        "vertiport-zone-fill",
        "vertiport-zone-outline",
        "vertiport-links-3d",
        "vertiport-circle",
        "vertiport-icon",
        "basestation-icon",
        "basestation-edit-ring",
        "basestation-edit-circle",
        "vertiport-hover-ring",
        "vertiport-edit-ring",
        "vertiport-edit-circle",
        "flight-plan-route",
        "flight-plan-route-3d",
        "flight-plan-manual-preview",
        "flight-plan-active-links",
        "flight-plan-active-links-hit",
        "flight-plan-via-points",
        "flight-plan-selection",
        "traffic-predict-line",
        "traffic-glow",
        "traffic-risk",
        "traffic-halo",
        "traffic-halo-core",
        "traffic-points",
        "traffic-hit",
        "traffic-history-3d",
        "traffic-predict-3d",
        "traffic-3d",
        "traffic-3d-icon",
      ].forEach((layerId) => {
        if (this.map.getLayer(layerId)) {
          this.map.moveLayer(layerId);
        }
      });
    }

    createLineLayer3d(id, color, drawModeName, highlightColor = null, lineWidth = 2 * MAP_SIZE_SCALE) {
      const layer = {
        id,
        type: "custom",
        renderingMode: "3d",
        _color: color,
        _highlightColor: highlightColor,
        _drawModeName: drawModeName,
        _lineCount: 0,
        _hoverLine: -1,
        _lastMatrix: null,
        _visible: true,
        _lineWidth: lineWidth,
        _colorAlpha: colorAlpha,
        _useDepth: true,
        _verticesPerLine: defaultVerticesPerLine,
        setColor(nextColor) {
          this._color = nextColor;
        },
        setAlpha(nextAlpha) {
          const value = Number(nextAlpha);
          if (!Number.isFinite(value)) {
            return;
          }
          this._colorAlpha = Math.max(0, Math.min(1, value));
        },
        setVisible(nextVisible) {
          this._visible = Boolean(nextVisible);
        },
        setHoverLine(index) {
          this._hoverLine = Number.isFinite(index) ? index : -1;
        },
        clearHoverLine() {
          this._hoverLine = -1;
        },
        setVerticesPerLine(value) {
          const count = Math.floor(Number(value));
          if (Number.isFinite(count) && count > 0) {
            this._verticesPerLine = count;
          }
        },
        getMatrix() {
          return this._lastMatrix;
        },
        updatePositions(positions) {
          this._pendingPositions = positions;
          if (!this._gl || !this._lineBuffer) {
            return;
          }
          const gl = this._gl;
          const data = new Float32Array(positions);
          gl.bindBuffer(gl.ARRAY_BUFFER, this._lineBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
          this._lineCount = data.length / 3;
          this._pendingPositions = null;
        },
        onAdd(_map, gl) {
          this._gl = gl;
          const vertexSource = `
            attribute vec3 a_pos;
            uniform mat4 u_matrix;
            void main() {
              gl_Position = u_matrix * vec4(a_pos, 1.0);
            }
          `;
          const fragmentSource = `
            precision mediump float;
            uniform vec4 u_color;
            void main() {
              gl_FragColor = u_color;
            }
          `;
          const compile = (type, source) => {
            const shader = gl.createShader(type);
            gl.shaderSource(shader, source);
            gl.compileShader(shader);
            return shader;
          };
          const vertexShader = compile(gl.VERTEX_SHADER, vertexSource);
          const fragmentShader = compile(gl.FRAGMENT_SHADER, fragmentSource);
          const program = gl.createProgram();
          gl.attachShader(program, vertexShader);
          gl.attachShader(program, fragmentShader);
          gl.linkProgram(program);
          this._program = program;
          this._aPos = gl.getAttribLocation(program, "a_pos");
          this._uMatrix = gl.getUniformLocation(program, "u_matrix");
          this._uColor = gl.getUniformLocation(program, "u_color");

          this._lineBuffer = gl.createBuffer();
          gl.bindBuffer(gl.ARRAY_BUFFER, this._lineBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([]), gl.STATIC_DRAW);
          this._lineCount = 0;
          this._drawMode =
            this._drawModeName === "LINE_STRIP"
              ? gl.LINE_STRIP
              : this._drawModeName === "TRIANGLES"
                ? gl.TRIANGLES
                : gl.LINES;

          if (this._pendingPositions) {
            this.updatePositions(this._pendingPositions);
          }
        },
        render(gl, matrix) {
          let drawMatrix = matrix;
          if (
            drawMatrix &&
            typeof drawMatrix.length !== "number" &&
            typeof drawMatrix.toArray === "function"
          ) {
            drawMatrix = drawMatrix.toArray();
          }
          if (!drawMatrix || typeof drawMatrix.length !== "number") {
            return;
          }
          if (!(drawMatrix instanceof Float32Array)) {
            drawMatrix = new Float32Array(drawMatrix);
          }
          this._lastMatrix = drawMatrix;
          if (!this._program || !this._lineCount || !this._visible) {
            return;
          }
          const depthWasEnabled = gl.isEnabled(gl.DEPTH_TEST);
          if (!this._useDepth) {
            gl.disable(gl.DEPTH_TEST);
          }
          gl.useProgram(this._program);
          gl.uniformMatrix4fv(this._uMatrix, false, drawMatrix);
          gl.uniform4fv(this._uColor, hexToRgba(this._color, this._colorAlpha));
          gl.bindBuffer(gl.ARRAY_BUFFER, this._lineBuffer);
          gl.enableVertexAttribArray(this._aPos);
          gl.vertexAttribPointer(this._aPos, 3, gl.FLOAT, false, 0, 0);
          gl.enable(gl.BLEND);
          gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
          gl.lineWidth(this._lineWidth);
          gl.drawArrays(this._drawMode, 0, this._lineCount);
          if (this._hoverLine > -1 && this._highlightColor) {
            gl.uniform4fv(this._uColor, hexToRgba(this._highlightColor, 0.98));
            if (this._drawMode === gl.LINES) {
              const offset = this._hoverLine * 2;
              if (offset + 1 < this._lineCount) {
                gl.lineWidth(this._lineWidth + 1 * MAP_SIZE_SCALE);
                gl.drawArrays(gl.LINES, offset, 2);
              }
            } else if (this._drawMode === gl.TRIANGLES) {
              const stride = this._verticesPerLine || 6;
              const offset = this._hoverLine * stride;
              if (offset + stride - 1 < this._lineCount) {
                gl.drawArrays(gl.TRIANGLES, offset, stride);
              }
            }
          }
          if (!this._useDepth && depthWasEnabled) {
            gl.enable(gl.DEPTH_TEST);
          }
        },
      };
      return layer;
    }

    getMercatorUnitsPerPixel() {
      if (!this.map) {
        return 0;
      }
      const transform = this.map.transform;
      if (transform && Number.isFinite(transform.worldSize) && transform.worldSize > 0) {
        return 1 / transform.worldSize;
      }
      const zoom = this.map.getZoom ? Number(this.map.getZoom()) : 0;
      const safeZoom = Number.isFinite(zoom) ? zoom : 0;
      const tileSize =
        transform && Number.isFinite(transform.tileSize) ? transform.tileSize : 512;
      const denom = tileSize * Math.pow(2, safeZoom);
      return denom > 0 ? 1 / denom : 0;
    }

    getMercatorUnitsPerMeter(lon, lat) {
      const lonValue = Number(lon);
      const latValue = Number(lat);
      if (!Number.isFinite(lonValue) || !Number.isFinite(latValue)) {
        return 0;
      }
      const base = maplibregl.MercatorCoordinate.fromLngLat([lonValue, latValue]);
      if (base && typeof base.meterInMercatorCoordinateUnits === "function") {
        const units = base.meterInMercatorCoordinateUnits();
        return Number.isFinite(units) ? units : 0;
      }
      const latRad = degToRad(latValue);
      const mLon = metersPerDegLon(latRad);
      if (!Number.isFinite(mLon) || mLon === 0) {
        return 0;
      }
      const offsetLon = lonValue + 1 / mLon;
      const offset = maplibregl.MercatorCoordinate.fromLngLat([offsetLon, latValue]);
      const units = Math.hypot(offset.x - base.x, offset.y - base.y);
      return Number.isFinite(units) ? units : 0;
    }

    appendCrossSegmentPositions(positions, start, end, halfWidth) {
      if (!Array.isArray(positions) || !start || !end) {
        return;
      }
      const width = Number(halfWidth);
      if (!Number.isFinite(width) || width <= 0) {
        return;
      }
      const dx = end.x - start.x;
      const dy = end.y - start.y;
      const dz = end.z - start.z;
      const len = Math.hypot(dx, dy, dz);
      if (!Number.isFinite(len) || len === 0) {
        return;
      }
      const ux = dx / len;
      const uy = dy / len;
      const uz = dz / len;
      let nx = uy;
      let ny = -ux;
      let nz = 0;
      let nlen = Math.hypot(nx, ny, nz);
      if (!Number.isFinite(nlen) || nlen < 1e-9) {
        nx = 0;
        ny = uz;
        nz = -uy;
        nlen = Math.hypot(nx, ny, nz);
        if (!Number.isFinite(nlen) || nlen < 1e-9) {
          return;
        }
      }
      nx /= nlen;
      ny /= nlen;
      nz /= nlen;
      let bx = 0;
      let by = 0;
      let bz = 0;
      const len2d = Math.hypot(dx, dy);
      if (Number.isFinite(len2d) && len2d > 1e-9) {
        const crossZ = dx * ny - dy * nx;
        bz = crossZ >= 0 ? 1 : -1;
      } else {
        bx = uy * nz - uz * ny;
        by = uz * nx - ux * nz;
        bz = ux * ny - uy * nx;
        const blen = Math.hypot(bx, by, bz);
        if (!Number.isFinite(blen) || blen < 1e-9) {
          return;
        }
        bx /= blen;
        by /= blen;
        bz /= blen;
      }
      const pushRibbon = (rx, ry, rz, scale = 1) => {
        const factor = Number.isFinite(scale) ? scale : 1;
        const ox = rx * width * factor;
        const oy = ry * width * factor;
        const oz = rz * width * factor;
        positions.push(
          start.x + ox,
          start.y + oy,
          start.z + oz,
          start.x - ox,
          start.y - oy,
          start.z - oz,
          end.x + ox,
          end.y + oy,
          end.z + oz,
          end.x + ox,
          end.y + oy,
          end.z + oz,
          start.x - ox,
          start.y - oy,
          start.z - oz,
          end.x - ox,
          end.y - oy,
          end.z - oz,
        );
      };
      pushRibbon(nx, ny, nz, 1);
      pushRibbon(bx, by, bz, ROUTE_CROSS_VERTICAL_SCALE);
    }

    buildCrossLinePositions(coords, altitudes, widthPx) {
      if (!this.map || !Array.isArray(coords) || coords.length < 2) {
        return [];
      }
      const pixelWidth = Math.max(0, Number(widthPx) || 0);
      if (!pixelWidth) {
        return [];
      }
      const unitsPerPixel = this.getMercatorUnitsPerPixel();
      if (!Number.isFinite(unitsPerPixel) || unitsPerPixel <= 0) {
        return [];
      }
      const halfWidth = (pixelWidth * unitsPerPixel) / 2;
      const positions = [];
      for (let i = 0; i < coords.length - 1; i += 1) {
        const startCoord = coords[i];
        const endCoord = coords[i + 1];
        if (!Array.isArray(startCoord) || !Array.isArray(endCoord)) {
          continue;
        }
        const lonA = Number(startCoord[0]);
        const latA = Number(startCoord[1]);
        const lonB = Number(endCoord[0]);
        const latB = Number(endCoord[1]);
        if (
          !Number.isFinite(lonA) ||
          !Number.isFinite(latA) ||
          !Number.isFinite(lonB) ||
          !Number.isFinite(latB)
        ) {
          continue;
        }
        const altAValue = Array.isArray(altitudes)
          ? Number(altitudes[i])
          : Number(altitudes);
        const altBValue = Array.isArray(altitudes)
          ? Number(altitudes[i + 1])
          : Number(altitudes);
        const altA_m = Number.isFinite(altAValue) ? altAValue : FLIGHT_ALT_M;
        const altB_m = Number.isFinite(altBValue) ? altBValue : FLIGHT_ALT_M;
        const startAlt = toTrafficAltitude(altA_m);
        const endAlt = toTrafficAltitude(altB_m);
        const start = maplibregl.MercatorCoordinate.fromLngLat(
          [lonA, latA],
          startAlt,
        );
        const end = maplibregl.MercatorCoordinate.fromLngLat([lonB, latB], endAlt);
        this.appendCrossSegmentPositions(positions, start, end, halfWidth);
      }
      return positions;
    }

    buildThickLinePositions(coords, altitudes, widthPx) {
      if (!this.map || !Array.isArray(coords) || coords.length < 2) {
        return [];
      }
      const pixelWidth = Math.max(0, Number(widthPx) || 0);
      if (!pixelWidth) {
        return [];
      }
      const unitsPerPixel = this.getMercatorUnitsPerPixel();
      if (!Number.isFinite(unitsPerPixel) || unitsPerPixel <= 0) {
        return [];
      }
      const halfWidth = (pixelWidth * unitsPerPixel) / 2;
      const positions = [];
      for (let i = 0; i < coords.length - 1; i += 1) {
        const startCoord = coords[i];
        const endCoord = coords[i + 1];
        if (!Array.isArray(startCoord) || !Array.isArray(endCoord)) {
          continue;
        }
        const lonA = Number(startCoord[0]);
        const latA = Number(startCoord[1]);
        const lonB = Number(endCoord[0]);
        const latB = Number(endCoord[1]);
        if (
          !Number.isFinite(lonA) ||
          !Number.isFinite(latA) ||
          !Number.isFinite(lonB) ||
          !Number.isFinite(latB)
        ) {
          continue;
        }
        const altAValue = Array.isArray(altitudes)
          ? Number(altitudes[i])
          : Number(altitudes);
        const altBValue = Array.isArray(altitudes)
          ? Number(altitudes[i + 1])
          : Number(altitudes);
        const altA_m = Number.isFinite(altAValue) ? altAValue : FLIGHT_ALT_M;
        const altB_m = Number.isFinite(altBValue) ? altBValue : FLIGHT_ALT_M;
        const startAlt = toTrafficAltitude(altA_m);
        const endAlt = toTrafficAltitude(altB_m);
        const start = maplibregl.MercatorCoordinate.fromLngLat(
          [lonA, latA],
          startAlt,
        );
        const end = maplibregl.MercatorCoordinate.fromLngLat([lonB, latB], endAlt);
        const dx = end.x - start.x;
        const dy = end.y - start.y;
        const len = Math.hypot(dx, dy);
        if (!Number.isFinite(len) || len === 0) {
          continue;
        }
        const ox = (-dy / len) * halfWidth;
        const oy = (dx / len) * halfWidth;
        const sx1 = start.x + ox;
        const sy1 = start.y + oy;
        const sx2 = start.x - ox;
        const sy2 = start.y - oy;
        const ex1 = end.x + ox;
        const ey1 = end.y + oy;
        const ex2 = end.x - ox;
        const ey2 = end.y - oy;
        positions.push(
          sx1,
          sy1,
          start.z,
          sx2,
          sy2,
          start.z,
          ex1,
          ey1,
          end.z,
          ex1,
          ey1,
          end.z,
          sx2,
          sy2,
          start.z,
          ex2,
          ey2,
          end.z,
        );
      }
      return positions;
    }

    getLinkLaneZoomBoost() {
      if (!this.map || !this.map.getZoom) {
        return 1;
      }
      const zoom = Number(this.map.getZoom());
      if (!Number.isFinite(zoom)) {
        return 1;
      }
      const baseZoom =
        this.config && Number.isFinite(this.config.startZoom)
          ? Number(this.config.startZoom)
          : LINK_LANE_ZOOM_BASE;
      const scaled = 1 + (zoom - baseZoom) * LINK_LANE_ZOOM_FACTOR;
      return Math.max(LINK_LANE_ZOOM_MIN, Math.min(LINK_LANE_ZOOM_MAX, scaled));
    }

    getLinkLaneSizing(widthPx) {
      const baseWidth = Math.max(0, Number(widthPx) || 0);
      if (!baseWidth) {
        return { laneWidth: 0, laneOffsetMeters: 0 };
      }
      const zoomBoost = this.getLinkLaneZoomBoost();
      return {
        laneWidth: baseWidth * LINK_LANE_WIDTH_FACTOR * zoomBoost,
        laneOffsetMeters: LINK_LANE_OFFSET_METERS,
      };
    }

    buildDualThickLinePositions(coords, altitudes, widthPx, offsetMeters) {
      if (!this.map || !Array.isArray(coords) || coords.length < 2) {
        return [];
      }
      const pixelWidth = Math.max(0, Number(widthPx) || 0);
      if (!pixelWidth) {
        return [];
      }
      const laneOffsetMeters = Math.max(0, Number(offsetMeters) || 0);
      const unitsPerPixel = this.getMercatorUnitsPerPixel();
      if (!Number.isFinite(unitsPerPixel) || unitsPerPixel <= 0) {
        return [];
      }
      const halfWidth = (pixelWidth * unitsPerPixel) / 2;
      const positions = [];
      for (let i = 0; i < coords.length - 1; i += 1) {
        const startCoord = coords[i];
        const endCoord = coords[i + 1];
        if (!Array.isArray(startCoord) || !Array.isArray(endCoord)) {
          continue;
        }
        const lonA = Number(startCoord[0]);
        const latA = Number(startCoord[1]);
        const lonB = Number(endCoord[0]);
        const latB = Number(endCoord[1]);
        if (
          !Number.isFinite(lonA) ||
          !Number.isFinite(latA) ||
          !Number.isFinite(lonB) ||
          !Number.isFinite(latB)
        ) {
          continue;
        }
        const altAValue = Array.isArray(altitudes)
          ? Number(altitudes[i])
          : Number(altitudes);
        const altBValue = Array.isArray(altitudes)
          ? Number(altitudes[i + 1])
          : Number(altitudes);
        const altA_m = Number.isFinite(altAValue) ? altAValue : FLIGHT_ALT_M;
        const altB_m = Number.isFinite(altBValue) ? altBValue : FLIGHT_ALT_M;
        const startAlt = toTrafficAltitude(altA_m);
        const endAlt = toTrafficAltitude(altB_m);
        const start = maplibregl.MercatorCoordinate.fromLngLat(
          [lonA, latA],
          startAlt,
        );
        const end = maplibregl.MercatorCoordinate.fromLngLat([lonB, latB], endAlt);
        const dx = end.x - start.x;
        const dy = end.y - start.y;
        const len = Math.hypot(dx, dy);
        if (!Number.isFinite(len) || len === 0) {
          continue;
        }
        const px = -dy / len;
        const py = dx / len;
        let offset = 0;
        if (laneOffsetMeters > 0) {
          const midLon = (lonA + lonB) / 2;
          const midLat = (latA + latB) / 2;
          const unitsPerMeter = this.getMercatorUnitsPerMeter(midLon, midLat);
          if (Number.isFinite(unitsPerMeter) && unitsPerMeter > 0) {
            offset = laneOffsetMeters * unitsPerMeter;
          }
        }
        const ox = px * halfWidth;
        const oy = py * halfWidth;
        const shiftX = px * offset;
        const shiftY = py * offset;
        const appendLane = (dir) => {
          const sx = start.x + shiftX * dir;
          const sy = start.y + shiftY * dir;
          const ex = end.x + shiftX * dir;
          const ey = end.y + shiftY * dir;
          positions.push(
            sx + ox,
            sy + oy,
            start.z,
            sx - ox,
            sy - oy,
            start.z,
            ex + ox,
            ey + oy,
            end.z,
            ex + ox,
            ey + oy,
            end.z,
            sx - ox,
            sy - oy,
            start.z,
            ex - ox,
            ey - oy,
            end.z,
          );
        };
        appendLane(1);
        appendLane(-1);
      }
      return positions;
    }

    setupScaleObserver() {
      const root = document.documentElement;
      const baseWidth = 1200;
      const baseHeight = 900;

      const getViewportSize = () => {
        if (window.visualViewport) {
          return { width: window.visualViewport.width, height: window.visualViewport.height };
        }
        return { width: window.innerWidth, height: window.innerHeight };
      };

      const updateScale = () => {
        const { width, height } = getViewportSize();
        if (!width || !height) {
          return;
        }
        const scale = Math.min(width / baseWidth, height / baseHeight);
        const clamped = Math.max(0.75, Math.min(scale, 1.25));
        root.style.setProperty("--ui-scale", clamped.toFixed(3));
        if (this.map) {
          requestAnimationFrame(() => this.map.resize());
        }
      };

      updateScale();
      window.addEventListener("resize", updateScale);
      if (window.visualViewport) {
        window.visualViewport.addEventListener("resize", updateScale);
      }

      if (window.ResizeObserver) {
        const observer = new ResizeObserver(updateScale);
        observer.observe(document.documentElement);
      }
    }

    setupScaleCopy() {
      if (!this.map || this.scaleCopyBound) {
        return;
      }
      const container = this.map.getContainer ? this.map.getContainer() : null;
      if (!container) {
        return;
      }
      const scaleEl = container.querySelector(".maplibregl-ctrl-scale");
      if (!scaleEl) {
        return;
      }
      this.scaleCopyBound = true;
      this.scaleCopyScaleEl = scaleEl;
      if (!this.scaleCopyContextBound && this.map && this.map.on) {
        this.scaleCopyContextBound = true;
        this.scaleCopyContextHandler = (event) =>
          this.handleScaleCopyContextMenu(event);
        this.map.on("contextmenu", this.scaleCopyContextHandler);
      }
      scaleEl.addEventListener("click", (event) => {
        if (event) {
          event.preventDefault();
          event.stopPropagation();
        }
        if (this.scaleCopyActive) {
          this.clearScaleCopy();
          return;
        }
        this.startScaleCopy(event);
      });
    }

    startScaleCopy(event) {
      if (!this.map || this.scaleCopyActive || !this.scaleCopyScaleEl) {
        return;
      }
      const container = this.map.getContainer ? this.map.getContainer() : null;
      if (!container) {
        return;
      }
      this.scaleCopyActive = true;
      const ghost = this.scaleCopyScaleEl.cloneNode(true);
      ghost.classList.add("scale-copy-ghost");
      ghost.setAttribute("aria-hidden", "true");
      ghost.style.position = "absolute";
      ghost.style.pointerEvents = "none";
      ghost.style.margin = "0";
      container.appendChild(ghost);
      this.scaleCopyGhost = ghost;
      this.syncScaleCopyGhost();
      this.updateScaleCopyPosition(event);

      this.scaleCopyMoveHandler = (moveEvent) => this.updateScaleCopyPosition(moveEvent);
      window.addEventListener("mousemove", this.scaleCopyMoveHandler);

      this.scaleCopyCancelHandler = (cancelEvent) => {
        if (!this.scaleCopyActive) {
          return;
        }
        const target = cancelEvent ? cancelEvent.target : null;
        if (this.scaleCopyScaleEl && target && this.scaleCopyScaleEl.contains(target)) {
          return;
        }
        this.clearScaleCopy();
      };
      window.addEventListener("click", this.scaleCopyCancelHandler, true);

      this.scaleCopyUpdateHandler = () => this.syncScaleCopyGhost();
      this.map.on("move", this.scaleCopyUpdateHandler);
      this.map.on("zoom", this.scaleCopyUpdateHandler);
    }

    clearScaleCopy() {
      this.clearScaleCircle();
      if (this.scaleCopyMoveHandler) {
        window.removeEventListener("mousemove", this.scaleCopyMoveHandler);
      }
      if (this.scaleCopyCancelHandler) {
        window.removeEventListener("click", this.scaleCopyCancelHandler, true);
      }
      if (this.scaleCopyUpdateHandler && this.map) {
        this.map.off("move", this.scaleCopyUpdateHandler);
        this.map.off("zoom", this.scaleCopyUpdateHandler);
      }
      if (this.scaleCopyGhost && this.scaleCopyGhost.parentNode) {
        this.scaleCopyGhost.parentNode.removeChild(this.scaleCopyGhost);
      }
      this.scaleCopyActive = false;
      this.scaleCopyGhost = null;
      this.scaleCopyMoveHandler = null;
      this.scaleCopyCancelHandler = null;
      this.scaleCopyUpdateHandler = null;
    }

    getScaleCopyRadiusKm() {
      if (!this.scaleCopyScaleEl) {
        return null;
      }
      const text = String(this.scaleCopyScaleEl.textContent || "")
        .replace(/\u00a0/g, " ")
        .trim();
      if (!text) {
        return null;
      }
      const match = text.match(/([\d.]+)\s*(km|m)\b/i);
      if (!match) {
        return null;
      }
      const value = Number.parseFloat(match[1].replace(/,/g, ""));
      if (!Number.isFinite(value) || value <= 0) {
        return null;
      }
      const unit = match[2].toLowerCase();
      return unit === "m" ? value / 1000 : value;
    }

    formatScaleDistance(km) {
      const value = Number(km);
      if (!Number.isFinite(value) || value <= 0) {
        return "-";
      }
      const meters = value * 1000;
      if (meters < 1000) {
        return `${Math.round(meters)} m`;
      }
      let digits = 0;
      if (value < 10) {
        digits = 2;
      } else if (value < 100) {
        digits = 1;
      }
      const raw = digits ? value.toFixed(digits) : Math.round(value).toString();
      const trimmed = digits
        ? raw.replace(/\.0+$/, "").replace(/(\.\d)0$/, "$1")
        : raw;
      return `${trimmed} km`;
    }

    ensureScaleCircleLayer() {
      if (!this.map) {
        return;
      }
      if (!this.map.getSource(SCALE_CIRCLE_SOURCE_ID)) {
        this.map.addSource(SCALE_CIRCLE_SOURCE_ID, {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
      }
      if (!this.map.getLayer(SCALE_CIRCLE_LINE_ID)) {
        this.map.addLayer({
          id: SCALE_CIRCLE_LINE_ID,
          type: "line",
          source: SCALE_CIRCLE_SOURCE_ID,
          filter: ["==", ["geometry-type"], "Polygon"],
          layout: { "line-join": "round", "line-cap": "round" },
          paint: {
            "line-color": SCALE_CIRCLE_STROKE,
            "line-width": SCALE_CIRCLE_STROKE_WIDTH,
            "line-dasharray": SCALE_CIRCLE_DASH,
          },
        });
      }
      if (!this.map.getLayer(SCALE_CIRCLE_LABEL_ID)) {
        this.map.addLayer({
          id: SCALE_CIRCLE_LABEL_ID,
          type: "symbol",
          source: SCALE_CIRCLE_SOURCE_ID,
          filter: ["==", ["geometry-type"], "Point"],
          layout: {
            "text-field": ["get", "label"],
            "text-size": SCALE_CIRCLE_LABEL_SIZE,
            "text-anchor": "center",
            "text-allow-overlap": true,
            "text-ignore-placement": true,
          },
          paint: {
            "text-color": SCALE_CIRCLE_LABEL_COLOR,
            "text-halo-color": SCALE_CIRCLE_LABEL_HALO,
            "text-halo-width": 1.2,
            "text-halo-blur": 0.2,
          },
        });
      }
      if (this.reorderPlanLayers) {
        this.reorderPlanLayers();
      }
    }

    setScaleCircle(lngLat, radiusKm) {
      if (!this.map || !lngLat) {
        return false;
      }
      const lon = Number(lngLat.lng);
      const lat = Number(lngLat.lat);
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
        return false;
      }
      const km = Number(radiusKm);
      if (!Number.isFinite(km) || km <= 0) {
        return false;
      }
      const coords = buildCirclePolygon(lon, lat, km, VERTIPORT_ZONE_STEPS);
      if (!coords) {
        return false;
      }
      const diameterKm = km * 2;
      const label = `D ${this.formatScaleDistance(diameterKm)}`;
      this.ensureScaleCircleLayer();
      const source = this.map.getSource(SCALE_CIRCLE_SOURCE_ID);
      if (source && source.setData) {
        source.setData({
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              geometry: {
                type: "Polygon",
                coordinates: [coords],
              },
              properties: { kind: "circle" },
            },
            {
              type: "Feature",
              geometry: {
                type: "Point",
                coordinates: [lon, lat],
              },
              properties: { kind: "label", label },
            },
          ],
        });
      }
      this.scaleCircleActive = true;
      this.scaleCircleCenter = { lon, lat };
      this.scaleCircleRadiusKm = km;
      return true;
    }

    clearScaleCircle() {
      if (this.map) {
        const source = this.map.getSource(SCALE_CIRCLE_SOURCE_ID);
        if (source && source.setData) {
          source.setData({ type: "FeatureCollection", features: [] });
        }
      }
      this.scaleCircleActive = false;
      this.scaleCircleCenter = null;
      this.scaleCircleRadiusKm = null;
    }

    handleScaleCopyContextMenu(event) {
      if (!this.map || !this.scaleCopyActive) {
        return false;
      }
      if (event && typeof event.preventDefault === "function") {
        event.preventDefault();
      }
      if (event && event.originalEvent) {
        if (typeof event.originalEvent.preventDefault === "function") {
          event.originalEvent.preventDefault();
        }
        if (typeof event.originalEvent.stopPropagation === "function") {
          event.originalEvent.stopPropagation();
        }
      }
      if (this.scaleCircleActive) {
        this.clearScaleCircle();
        return true;
      }
      const radiusKm = this.getScaleCopyRadiusKm();
      if (!Number.isFinite(radiusKm) || radiusKm <= 0) {
        return true;
      }
      const lngLat = event && event.lngLat ? event.lngLat : null;
      if (!lngLat) {
        return true;
      }
      return this.setScaleCircle(lngLat, radiusKm);
    }

    syncScaleCopyGhost() {
      if (!this.scaleCopyActive || !this.scaleCopyGhost || !this.scaleCopyScaleEl) {
        return;
      }
      const uiScaleValue = Number.parseFloat(
        getComputedStyle(document.documentElement).getPropertyValue("--ui-scale"),
      );
      const uiScale = Number.isFinite(uiScaleValue) ? uiScaleValue : 1;
      this.scaleCopyGap = 16 * uiScale;
      const rect = this.scaleCopyScaleEl.getBoundingClientRect();
      const text = this.scaleCopyScaleEl.textContent || "";
      this.scaleCopyGhost.textContent = text;
      if (Number.isFinite(rect.width) && rect.width > 0) {
        this.scaleCopyGhost.style.width = `${rect.width}px`;
      }
      if (Number.isFinite(rect.height) && rect.height > 0) {
        this.scaleCopyGhost.style.height = `${rect.height}px`;
      }
    }

    updateScaleCopyPosition(event) {
      if (!this.scaleCopyActive || !this.scaleCopyGhost || !this.map) {
        return;
      }
      const container = this.map.getContainer ? this.map.getContainer() : null;
      if (!container) {
        return;
      }
      const rect = container.getBoundingClientRect();
      const clientX = event && Number.isFinite(event.clientX) ? event.clientX : rect.left;
      const clientY = event && Number.isFinite(event.clientY) ? event.clientY : rect.top;
      const x = clientX - rect.left;
      const gap = Number.isFinite(this.scaleCopyGap) ? this.scaleCopyGap : 8;
      const y = clientY - rect.top - gap;
      this.scaleCopyGhost.style.left = `${x}px`;
      this.scaleCopyGhost.style.top = `${y}px`;
    }
  }

  if (typeof MapApp !== "undefined") {
    MapApp.prototype.resolveAssetUrl = function (path) {
      if (!path) {
        return path;
      }
      if (typeof window !== "undefined" && window.AppPaths && window.AppPaths.resolve) {
        return window.AppPaths.resolve(path);
      }
      return path;
    };

    MapApp.prototype.resolveApiUrl = function (path) {
      if (!path) {
        return path;
      }
      if (/^[a-z][a-z0-9+.-]*:/i.test(path)) {
        return path;
      }
      const base = this.webApiBaseUrl || "";
      if (base) {
        const needsSlash = !base.endsWith("/") && !path.startsWith("/");
        const combined = needsSlash ? `${base}/${path}` : `${base}${path}`;
        return this.resolveAssetUrl(combined);
      }
      return this.resolveAssetUrl(path);
    };
  }

