# Simulation Modes (Separated)

이 프로젝트의 스케줄 생성/적용 로직은 아래 2개 모드로 분리되어 있습니다.

## 1) Random Mode (비행계획 없이 랜덤 생성)
- 목적: Daily Traffic(LOW/MIDDLE/HIGH) 기준으로 스케줄 자동 생성
- 핵심 파일:
  - `app/schedule_random_mode.py`
  - `app/sim_core.py` (`_generate_schedule`에서 random mode 호출)
- 동작 요약:
  - `TRAFFIC_LEVELS` 기준 편수 선택
  - 운항 시간 창 내 `start_offset_s` 랜덤 배치
  - 출발지 이륙 간격(`takeoff_s`) 적용

## 2) Flightplan Mode (Load 기반 스케줄)
- 목적: 외부 비행계획(CSV/폴더) 기반 스케줄 실행
- 핵심 파일:
  - `app/schedule_flightplan_mode.py` (파싱/정렬/상태 계산)
  - `app/sim_core.py` (`set_flightplan_schedule`, `get_flightplan_state`)
  - `app/web_server.py` (`start_simulation`에서 payload 파싱 연결)
- 동작 요약:
  - 계획 데이터 파싱 후 `FlightSchedule` 목록 생성
  - 게이트/택시/FATO 시간으로 preflight wait 계산
  - 동일 기체 `turnaround_s` 적용 가능

## Feature Flag
- `UATM_ENABLE_FLIGHTPLAN_MODE`
  - 기본값: `False`
  - 위치: `app/config.py`
  - `False`일 때:
    - 서버는 `flightplan` payload를 받아도 random mode로 실행
    - 상태 payload에 `flightplan_mode_enabled=false` 반환

## Web 연동
- 서버 상태:
  - `schedule_mode`: `"random"` 또는 `"flightplan"`
  - `flightplan_mode_enabled`: `true/false`
- 프론트(`app/web/app.js`)는 `flightplan_mode_enabled`가 `false`면 Load payload를 시작 요청에 포함하지 않음.
