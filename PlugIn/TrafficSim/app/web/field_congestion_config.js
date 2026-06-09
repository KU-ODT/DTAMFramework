(() => {
  "use strict";

  // 혼잡장(congestion field) 수식 파라미터.
  // 단위: 거리(m), 시간(s), 속도(m/s).
  // 논문에 수치가 명시되지 않은 항목은 현재 시뮬레이터 기본 규칙/운용 기준을 근거로 한 초기값이며,
  // 추후 레퍼런스 확보 시 여기만 수정하면 전체에 반영되도록 한 곳에 모았습니다.
  const CONFIG = {
    // 자유흐름 속도 v_f.
    // 근거: 시뮬레이터 기본 규칙 speed_mps = 100 kt ≈ 51.4 m/s (app.js).
    // 초기값은 50 m/s로 근사.
    freeflow_mps: 50,

    // 지연 누적 구간 T와 임계 D_thr.
    // 근거: 논문에 값 미제시 → 1초 내외 업데이트 주기 + 조종 개입 체감 지연을 고려한 초기값.
    delay_window_s: 30,
    delay_threshold_s: 5,
    // 적분 안정화를 위한 최대 dt.
    // 근거: 시뮬레이터 업데이트 주기(약 1s) 대비 상한.
    delay_max_dt_s: 1.0,
    // ε 변화가 작으면 구간 병합(메모리 절약).
    // 근거: 무차원 ε 변화 0.02 이하는 동일 상태로 간주.
    delay_merge_eps: 0.02,

    // 기체 중심 상호작용 강도 ρ_i 커널 폭.
    // 근거: 현재 항로 스케일에서 순항 기체 간 간격이 1~2 km 수준이라
    //       400/200 m에서는 ρ가 거의 0에 수렴 → 시각화가 사라짐.
    //       따라서 시뮬레이션 공간 스케일에 맞춰 커널 폭을 확대.
    rho_sigma_parallel_m: 200,
    rho_sigma_perp_m: 200,
    // 커널 컷오프(σ 배수).
    // 근거: 2σ 밖은 가우시안 영향이 급감.
    rho_cutoff_sigma: 1.0,

    // 전방 지연 탐색 박스.
    // 근거: freeflow 50 m/s 기준 800 m는 약 16 s 전방,
    //       400 m는 회랑 측방 여유 포함.
    front_box_longitudinal_m: 1000,
    front_box_lateral_m: 500,
    neighbor_epsilon: 1e-6,

    // ρ̂ 정규화 파라미터.
    // 근거: 상위 10% 분위수로 스케일을 잡아 outlier 과증폭을 완화.
    rho_norm_quantile: 0.9,
    rho_norm_min: 0.1,
    rho_norm_cap: 1.0,

    // 공간 그리드 셀 크기.
    // 근거: rho_sigma_parallel_m와 동일 스케일로 이웃 탐색을 제한.
    neighbor_cell_m: 400,
    // 지연 상태 보관 최대 시간.
    // 근거: 10분 이상 무활동 상태는 제거.
    stale_state_s: 600,

    // 버티포트 반경 컷(0은 사용 안 함).
    // 근거: 회랑이 포트 인근을 지나가므로 기본은 0.
    exclude_vertiport_radius_m: 0,

    // 혼잡 계산에 포함할 최소 속도.
    // 근거: 정지/지상 계류 제거용.
    min_speed_mps: 1.0,

    // 순항 고도 기준 비율.
    // 근거: FLIGHT_ALT_M(1000 ft ≈ 304.8 m)의 90% 이상만 혼잡 계산.
    min_altitude_ratio: 0.9,

    // 혼잡장 시각화 스케일.
    // 근거: 혼잡 값이 작게 나올 때 가시성을 높이기 위해 기본값을 낮춤.
    field_scale_congestion: 0.7,
  };

  if (typeof self !== "undefined") {
    self.FIELD_CONGESTION_CONFIG = CONFIG;
  }
})();
