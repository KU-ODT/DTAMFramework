# Mission 데모 플랜 팩 (demo_plans)

Mission 이 **사전 작성된 3001 ScheduledFlight** 를 보유하다가 2001 FlightPlanRequest 수신 시
계산 파이프라인 대신 **그대로 발행**하기 위한 preset 디렉토리.

## 규칙

- **위치**: `MissionModule/data/demo_plans/<scenario_key>/3001_*.json`
- **scenario_key 매칭**: 2001 의 `scenarioFileName` stem 과 디렉토리명이 일치해야 한다.
  - 예: `"S2_psu_replan.json"` → `demo_plans/S2_psu_replan/`
  - 디렉토리가 존재하면 `MissionService.on_flight_plan_request` 가 내부의 `3001_*.json` 을
    **파일명 정렬 순서**로 로드해 `send_scheduled_flights(records)` 로 발행하고 기존 계산 경로를 건너뛴다.
  - 디렉토리가 없으면 기존 계산 파이프라인 그대로 동작.
- **파일명 규칙**: `3001_<aircraftId>.json` (예: `3001_UAM0001.json`). 정렬 순서 = 발행 순서.
- **파일 내용**: SDK `Msg3001_ScheduledFlight` wire 필드만 — `flightPlanNumber` / `planVersion` /
  `planStatus` / `aircraftId` / `departure` / `arrival` / `enRoute`. 메타데이터 키 추가 금지.
  `looks_like_icd_record` (flightPlanNumber/aircraftId/departure/enRoute/arrival 필수) 를 통과해야 한다.
  시각 필드(std/sta/eobt/etot/eibt/eldt)는 `HH:MM:SS`. Turn(D/H) 세그먼트는 `turnDirection`+`centerLLA` 필수.

## 현재 팩

| scenario_key | 파일 | fpn | 비고 |
|---|---|---|---|
| `S1_nominal` | `3001_UAM0001.json` | 1001 | Yeouido→Jamsil 정상 plan, enRoute seq 1..4 (E/F/F/G) |
| `S2_psu_replan` | `3001_UAM0001.json` | 1201 | JAMSIL_VP→GIMPO_VP, 회랑 C-NORTH (seq 4) |
| `S2_psu_replan` | `3001_UAM0002.json` | 1202 | 동일 회랑 구간, std +2분 — T+25 부근 동시 진입 기하 |
| `S3_uao_battery_alt_vertiport` | `3001_UAM0001.json` | 1201 | VP_YEOUIDO→VP_JAMSIL 정상 plan (VP_KU divert 는 런타임 PSU 3003) |

**S1 도 데모 팩 사용 가능** — 콘솔에서 데모 시나리오 S1 선택 시 사용. [없음] 선택 시 기존 계산 파이프라인으로 3001 을 생성한다.
