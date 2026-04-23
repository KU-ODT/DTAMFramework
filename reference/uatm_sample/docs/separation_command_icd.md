# UATM 전략적/전술적 분리 명령 설계안

작성일: 2026-04-16

## 1. 목적

본 문서는 현재 `uatm_sample` 프로젝트의 구조를 바탕으로, 새 시뮬레이션에서 생성해야 할 항공 교통관리 명령을 `전략적 분리`와 `전술적 분리`로 나누어 정리한다.

이 문서는 실제 관제 절차나 법정 분리 기준을 대체하지 않는다. 목적은 시뮬레이션 내부에서 사용할 명령 종류, 적용 범위, 입력 필드, 검증 조건, 상태 반영 방식을 설계하는 것이다. 실제 운용 수치가 필요한 항목은 별도 기준 문서와 캘리브레이션을 거쳐 확정해야 한다.

## 2. 현재 프로젝트에서 가져올 기준

현재 프로젝트는 별도의 강한 타입 command 객체보다 `payload: dict`와 문자열 `method/action`을 중심으로 명령을 처리한다.

주요 기준은 다음과 같다.

| 축 | 현재 근거 | 새 명령 설계 반영 |
| --- | --- | --- |
| 비행계획 | `docs/mission_icd_v1.md`의 `flightPlanNumber`, `aircraftId`, `departure`, `enRoute`, `arrival` | 전략적 분리의 기본 입력 레코드 |
| 스케줄 | `app/schedule_random_mode.py`, `app/schedule_flightplan_mode.py`, `app/sim_core.py`의 `FlightSchedule` | 슬롯, 지연, 출발 간격, 수요 조절 명령 |
| 공역/경로 | `app/pathplanner.py`의 `Port`, `Waypoint`, `RoutePlanner`, `closed_edges`, `spare_edges` | 회랑 상태, 예비 회랑, 경로 재계획 명령 |
| 비행 상태 | `app/sim_core.py`의 `Flight`, `FlightControl`, `flight_state` | 전술적 속도/대기/우회/비상 명령 |
| 분리/위험 | `SimulationRules`의 `separation_m`, `risk_*`, `rnp_*`, `warning/caution` | 위험 기반 명령 트리거와 검증 조건 |
| 현행 API | `/api/control`, `/api/rules`, `/api/traffic`, `/api/wind`, `/api/sim/start` | 초기 구현은 기존 API에 매핑하고, 이후 구조화 command envelope로 확장 |

## 3. 분리 계층 정의

### 3.1 전략적 분리

전략적 분리는 충돌이 임박하기 전에 교통 수요, 경로, 시간, 자원 배정을 조정해 애초에 위험한 조합이 발생하지 않도록 만드는 계층이다.

권장 범위:

| 항목 | 범위 |
| --- | --- |
| 시간 범위 | 시뮬레이션 시작 전, 비행 전, 또는 최소 수 분 이상 여유가 있는 재계획 구간 |
| 대상 | 비행계획 묶음, 출발/도착 슬롯, 버티포트, FATO, 게이트, 회랑, 웨이포인트, 고도 레이어, 트래픽 레벨 |
| 효과 | 계획 수정, 스케줄 재배치, 경로 사전 할당, 수요 제한, 공역 예약, 회랑 운영 상태 변경 |
| 판단 지표 | 예상 동시 항공기 수, 회랑 밀도, 버티포트 처리량, 예상 지연, 기상/공역 제한, 계획 간 예상 근접 |
| 제외 | 즉시 속도 변경, 개별 기체 긴급 회피, 현재 위치 기반 선회 지시 |

### 3.2 전술적 분리

전술적 분리는 이미 운항 중인 항공기 사이의 근접, 경로 이탈, 기상 영향, 회랑 폐쇄 등 즉시 처리해야 하는 위험에 대응하는 계층이다.

권장 범위:

| 항목 | 범위 |
| --- | --- |
| 시간 범위 | 현재 시각부터 수 초~수 분 이내 |
| 대상 | 개별 항공기, 항공기 쌍, 특정 회랑 구간, 특정 위험 이벤트 |
| 효과 | 속도 조정, holding, direct/via 이동, 즉시 회랑 폐쇄, 예비 회랑 개방, 비상착륙, 자동 감속 |
| 판단 지표 | `risk_level`, `risk_reason`, 예측 경로, 근접 거리, TTV, RNP 이탈, 배터리, 풍향/풍속 영향 |
| 제외 | 하루 전체 수요 계획, 장기 회랑망 설계, 공역 구조 변경 |

## 4. 공통 Command Envelope

초기 구현은 현재처럼 `/api/control`의 `method + args`를 유지할 수 있다. 다만 새 시뮬레이션에서는 아래 envelope를 내부 표준으로 두면 전략/전술 명령을 같은 방식으로 로깅, 재생, 검증할 수 있다.

```json
{
  "commandId": "CMD-20260416-000001",
  "commandType": "TACTICAL_SPEED_ADJUST",
  "separationLayer": "tactical",
  "priority": "warning",
  "issueTime": "09:12:30",
  "effectiveTime": "09:12:31",
  "expiresAt": "09:13:00",
  "source": {
    "type": "system",
    "name": "risk_resolver"
  },
  "target": {
    "type": "flight",
    "flightId": 1201,
    "aircraftId": "UAM0001"
  },
  "scope": {
    "timeWindowS": 30,
    "airspace": ["여의도", "선유도 17고지"],
    "altitudeBandM": [250, 350]
  },
  "parameters": {},
  "reason": {
    "riskLevel": 2,
    "riskReason": "근접 <300m",
    "trigger": "predicted_proximity"
  },
  "constraints": {
    "minSafeSpeedMps": 25,
    "maxTurnRateDegS": 3,
    "preserveMissionDestination": true
  },
  "expectedEffect": {
    "minSeparationGainM": 150,
    "delayS": 20
  },
  "audit": {
    "requiresAck": false,
    "rollbackCommand": "TACTICAL_RESUME_PLAN"
  }
}
```

공통 필드 의미:

| 필드 | 필수 | 의미 |
| --- | --- | --- |
| `commandId` | Y | 재생/로그/취소를 위한 유일 ID |
| `commandType` | Y | 아래 카탈로그의 명령명 |
| `separationLayer` | Y | `strategic` 또는 `tactical` |
| `priority` | Y | `routine`, `advisory`, `caution`, `warning`, `emergency` |
| `issueTime` | Y | 명령 생성 시각, 시뮬레이션 시계 기준 |
| `effectiveTime` | N | 적용 시작 시각. 없으면 즉시 적용 |
| `expiresAt` | N | 명령 유효 만료 시각 |
| `source` | Y | `human`, `system`, `autopilot`, `scenario` |
| `target` | Y | `flight`, `flightPair`, `flow`, `corridor`, `vertiport`, `airspace`, `scenario` |
| `scope` | Y | 시간/공간/고도/운항 단계 범위 |
| `parameters` | Y | 명령별 세부 파라미터 |
| `reason` | Y | 위험도, 혼잡도, 기상, 스케줄 등 생성 근거 |
| `constraints` | N | 최소 속도, 최대 선회율, 고도 범위, 회랑 사용 가능성 |
| `expectedEffect` | N | 지연, 분리 증가, 처리량 변화, 우회 거리 |
| `audit` | N | 승인 필요 여부, 롤백 명령, 로그 태그 |

## 5. 전략적 분리 명령 카탈로그

### 5.1 수요/스케줄 명령

| 명령 | 목적 | 대상 범위 | 주요 입력 | 상태 반영 |
| --- | --- | --- | --- | --- |
| `STRATEGIC_TRAFFIC_SCENARIO_SET` | Low/Middle/High 같은 교통량 시나리오 설정 | 전체 시뮬레이션 | `trafficLevel`, `operationStart`, `operationEnd`, `goalCount` | 현행 `/api/traffic`, `SimulationRules.operation_*` |
| `STRATEGIC_FLIGHTPLAN_LOAD` | 외부 비행계획 묶음 로드 | 비행계획 배치 | `plans[]`, `sourceName`, `validationMode` | `FlightSchedule` 목록 생성 |
| `STRATEGIC_FLIGHTPLAN_APPROVE` | 계획 승인/거절/보류 | 단일 또는 배치 비행계획 | `flightPlanNumber`, `decision`, `reason` | 승인된 계획만 스케줄 반영 |
| `STRATEGIC_SLOT_ASSIGN` | ETOT/ELDT/FATO/gate 슬롯 배정 | 버티포트, FATO, gate, 항공기 | `etot`, `eldt`, `depFato`, `arrFato`, `gate` | `departure`, `arrival`, `FlightSchedule.planned_takeoff_offset_s` |
| `STRATEGIC_DEPARTURE_DELAY` | 출발 전 지연으로 예상 근접 해소 | 비행계획, origin, flow | `delayS`, `newEtot`, `reason` | `start_offset_s`, `eobt/etot` 갱신 |
| `STRATEGIC_METERING_INTERVAL_SET` | 동일 회랑/버티포트 진입 간격 확보 | flow, corridor, vertiport | `minIntervalS`, `meterPoint`, `timeWindow` | 스케줄러가 출발 순서를 재배치 |
| `STRATEGIC_FLOW_CAPACITY_SET` | 회랑/버티포트 처리량 제한 | corridor, vertiport, altitudeBand | `maxAircraft`, `ratePerMin`, `timeWindow` | 계획 생성/승인 단계에서 초과 수요 지연 |
| `STRATEGIC_SEQUENCE_ASSIGN` | 출발/도착/merge 순서 고정 | flight list, merge point, FATO | `orderedFlightIds[]`, `meterPoint` | 슬롯과 속도 계획의 기준 순서 |

권장 생성 조건:

1. 동일 origin 또는 동일 FATO에 단시간 출발이 몰릴 때 `STRATEGIC_METERING_INTERVAL_SET`.
2. 특정 회랑 예상 밀도가 기준 이상이면 `STRATEGIC_FLOW_CAPACITY_SET` 또는 `STRATEGIC_DEPARTURE_DELAY`.
3. 도착 FATO의 `eldt/eibt`가 겹치면 `STRATEGIC_SLOT_ASSIGN`.
4. 같은 항공기 `aircraftId`가 turnaround 전에 다시 출발하면 `STRATEGIC_DEPARTURE_DELAY`.

### 5.2 경로/공역 명령

| 명령 | 목적 | 대상 범위 | 주요 입력 | 상태 반영 |
| --- | --- | --- | --- | --- |
| `STRATEGIC_ROUTE_ASSIGN` | 사전 경로 지정 | flight plan | `routeNodes[]`, `enRoute[]`, `altitudeBandM`, `targetSpeedMps` | `enRoute`, `Flight.path_nodes` |
| `STRATEGIC_ROUTE_REROUTE_BATCH` | 여러 계획의 회랑 분산 | plan batch, corridor group | `affectedPlans[]`, `avoidCorridors[]`, `preferCorridors[]` | 출발 전 경로 재계산 |
| `STRATEGIC_CORRIDOR_STATUS_SCHEDULE` | 회랑 폐쇄/개방 예약 | corridor edge | `from`, `to`, `status`, `startTime`, `endTime`, `reason` | 지정 시각에 `closed_edges` 변경 |
| `STRATEGIC_SPARE_CORRIDOR_POLICY` | 예비 회랑 사용 정책 | spare corridor edge | `from`, `to`, `openWindow`, `allowedFlows` | `spare_edges` 개방 조건 |
| `STRATEGIC_ALTITUDE_BAND_ASSIGN` | 고도 레이어로 교통 분산 | flight, flow, corridor | `altitudeBandM`, `directionRule`, `phaseScope` | `points_alt_m`, `enRoute.alt` |
| `STRATEGIC_AIRSPACE_RESERVATION` | 특정 공역/시간 예약 또는 제한 | polygon/corridor/vertiport | `geometry`, `timeWindow`, `allowedUsers`, `blockedUsers` | 경로 탐색 비용 또는 금지구역 반영 |
| `STRATEGIC_WEATHER_CONSTRAINT_SET` | 기상 영향이 큰 구간 사전 제한 | area/corridor/time | `preset`, `windLimit`, `avoidArea`, `timeWindow` | 경로 비용, 회랑 폐쇄, 슬롯 지연 |

권장 생성 조건:

1. 특정 회랑이 전략적으로 닫히면 그 회랑을 포함한 아직 출발 전 계획은 `STRATEGIC_ROUTE_REROUTE_BATCH`.
2. 교차/합류점에 도착 예정 시간이 겹치면 `STRATEGIC_ALTITUDE_BAND_ASSIGN` 또는 `STRATEGIC_METERING_INTERVAL_SET`.
3. 예비 회랑이 존재하고 주 회랑 밀도가 높으면 `STRATEGIC_SPARE_CORRIDOR_POLICY`.
4. 강풍/기상 구역이 일정 시간 지속되면 `STRATEGIC_WEATHER_CONSTRAINT_SET`.

### 5.3 규칙/파라미터 명령

| 명령 | 목적 | 대상 범위 | 주요 입력 | 상태 반영 |
| --- | --- | --- | --- | --- |
| `STRATEGIC_SEPARATION_RULE_SET` | 분리/위험 판단 파라미터 세트 변경 | 전체 또는 시나리오 | `separationM`, `riskProximityM`, `riskHorizonS`, `rnpLimit` | 현행 `/api/rules`, `SimulationRules` |
| `STRATEGIC_CONGESTION_MODEL_SET` | 혼잡장 계산 파라미터 변경 | 시나리오/맵 레이어 | `freeflowMps`, `delayWindowS`, `rhoSigma`, `frontBox` | `field_congestion_config.js` 계열 |
| `STRATEGIC_PRIORITY_POLICY_SET` | 우선순위 정책 설정 | flow, aircraft class, emergency class | `priorityRules[]`, `tieBreakers[]` | 슬롯/경로/전술 자동명령의 우선순위 기준 |
| `STRATEGIC_AUTOMATION_POLICY_SET` | 자동 개입 허용 범위 설정 | 전체/구간/비행단계 | `enabled`, `maxAuthority`, `requiresAck` | `setAutopilot`, 향후 resolver |

주의할 점:

- `separation_m`, `risk_proximity_lv*`, `warning_m`, `caution_m` 같은 값은 프로젝트 기본값으로만 보아야 한다.
- 실제 운용 기준으로 확정하기 전에는 문서와 UI에 `simulation parameter`로 표시하는 것이 안전하다.
- 전략적 규칙 변경은 실행 중 적용 시 기존 `risk_level`과 로그 해석이 바뀌므로 `commandId`와 적용 시각을 반드시 남긴다.

## 6. 전술적 분리 명령 카탈로그

### 6.1 개별 항공기 제어 명령

| 명령 | 목적 | 대상 범위 | 주요 입력 | 현재 프로젝트 매핑 |
| --- | --- | --- | --- | --- |
| `TACTICAL_SPEED_ADJUST` | 선행/후행 간격 확보를 위한 속도 조정 | flight | `flightId`, `targetSpeedMps`, `durationS`, `minSafeSpeedMps` | `setFlightSpeed` |
| `TACTICAL_SPEED_CLEAR` | 수동 속도 제한 해제 | flight | `flightId` | `clearFlightSpeed` |
| `TACTICAL_HOLD_ENTER` | 원형 대기 진입 | flight | `flightId`, `loops`, `center`, `radiusM`, `altitudeM`, `exitCondition` | `startHolding` |
| `TACTICAL_HOLD_EXIT` | 대기 해제/복귀 | flight | `flightId`, `exitMode` | `stopHolding` |
| `TACTICAL_DIRECT_VIA` | 특정 waypoint를 경유하도록 즉시 재경로 | flight | `flightId`, `waypoint`, `preserveDestination` | `forceMoveVia` |
| `TACTICAL_VECTOR_ASSIGN` | 헤딩/선회 벡터 지시 | flight | `headingDeg`, `turnDirection`, `durationS`, `resumeMode` | 신규 필요 |
| `TACTICAL_ALTITUDE_ADJUST` | 수직 분리 확보 | flight | `targetAltitudeM`, `climbRateMps`, `altitudeBandM`, `until` | 신규 필요 |
| `TACTICAL_LATERAL_OFFSET` | 회랑 내 횡방향 분리 확보 | flight | `offsetM`, `side`, `durationS`, `returnMode` | 신규 필요 |
| `TACTICAL_RESUME_PLAN` | 전술 개입 후 원 계획 복귀 | flight | `flightId`, `clearSpeed`, `clearHold`, `clearVector` | 부분 신규 |

권장 생성 조건:

1. 후행 항공기가 선행 항공기에 접근하고 `risk_level=1`이면 `TACTICAL_SPEED_ADJUST`를 후보로 생성한다.
2. `risk_level=2`이고 속도 조정만으로 예측 분리가 회복되지 않으면 `TACTICAL_HOLD_ENTER` 또는 `TACTICAL_DIRECT_VIA`.
3. `risk_level=3`이면 즉시성이 높은 `TACTICAL_HOLD_ENTER`, `TACTICAL_ALTITUDE_ADJUST`, `TACTICAL_DIRECT_VIA`를 우선 검토한다.
4. 전술 명령은 `expiresAt` 또는 `exitCondition`을 가져야 한다. 해제 조건이 없으면 수동 명령이 누적되어 시뮬레이션 해석이 어려워진다.

### 6.2 공역/회랑 즉시 명령

| 명령 | 목적 | 대상 범위 | 주요 입력 | 현재 프로젝트 매핑 |
| --- | --- | --- | --- | --- |
| `TACTICAL_CORRIDOR_CLOSE` | 위험/기상/장애로 회랑 즉시 폐쇄 | corridor edge | `from`, `to`, `reason`, `replanActiveFlights` | `setCorridorClosed(..., true)` |
| `TACTICAL_CORRIDOR_REOPEN` | 회랑 즉시 재개방 | corridor edge | `from`, `to`, `reason` | `setCorridorClosed(..., false)` |
| `TACTICAL_SPARE_CORRIDOR_OPEN` | 예비 회랑 즉시 개방 | spare edge | `from`, `to`, `durationS`, `allowedFlows` | `setSpareCorridorOpen(..., true)` |
| `TACTICAL_SPARE_CORRIDOR_CLOSE` | 예비 회랑 닫기 | spare edge | `from`, `to`, `reason` | `setSpareCorridorOpen(..., false)` |
| `TACTICAL_LOCAL_WEATHER_SET` | 특정 지역 기상 영향 부여 | area | `lon`, `lat`, `radiusM`, `preset`, `durationS` | `/api/wind` local |
| `TACTICAL_ROUTE_KEEP_WIND` | 횡풍 영향 보정/완화 | flight | `flightId`, `targetScale`, `rampS` | `setWindHold` |

권장 생성 조건:

1. 회랑 내 다중 항공기 위험이 반복되면 개별 항공기 명령보다 `TACTICAL_CORRIDOR_CLOSE`가 더 일관적이다.
2. 주 회랑 폐쇄 후 대체 경로가 없으면 `TACTICAL_SPARE_CORRIDOR_OPEN`.
3. 기상 영향으로 RNP 이탈이 발생하면 `TACTICAL_LOCAL_WEATHER_SET` 또는 `TACTICAL_ROUTE_KEEP_WIND`.
4. 공역 명령은 영향을 받는 active flight 목록을 함께 계산해야 한다.

### 6.3 위험 대응/자동화 명령

| 명령 | 목적 | 대상 범위 | 주요 입력 | 현재 프로젝트 매핑 |
| --- | --- | --- | --- | --- |
| `TACTICAL_AUTOPILOT_SET` | 위험 레벨별 자동 감속 정책 활성화 | 전체/flight group | `enabled`, `durationS`, `lv1DeltaKt`, `lv2DeltaKt`, `lv3DeltaKt` | `setAutopilot` |
| `TACTICAL_CONFLICT_PAIR_RESOLVE` | 두 항공기 간 해소 명령 묶음 생성 | flightPair | `ownship`, `intruder`, `resolutionSet[]` | 신규 resolver |
| `TACTICAL_ALERT_ACK` | warning/caution 확인 처리 | alert/risk event | `riskEventId`, `ackBy`, `ackTime` | 신규 필요 |
| `TACTICAL_EMERGENCY_LAND` | 비상착륙 지시 | flight | `flightId`, `lon`, `lat`, `label`, `altM` | `setEmergencyLanding` |
| `TACTICAL_COMMAND_CANCEL` | 특정 명령 취소 | command | `commandId`, `cancelReason` | 신규 필요 |

권장 생성 조건:

1. `TACTICAL_CONFLICT_PAIR_RESOLVE`는 단일 지시가 아니라 후보 지시 묶음이다. 예: 후행기 감속 + 선행기 유지 + 필요 시 후행기 holding.
2. 자동화 정책이 켜져 있으면 `risk_level`에 따라 `TACTICAL_SPEED_ADJUST`를 자동 발행할 수 있다.
3. 배터리 위험이 근접 위험보다 높으면 `TACTICAL_EMERGENCY_LAND`가 속도/holding보다 우선한다.
4. `TACTICAL_ALERT_ACK`는 상태 변경보다 로그/운용자 워크로드 산정에 중요하다.

## 7. 전략/전술 명령 선택 로직

### 7.1 기본 우선순위

| 상황 | 우선 명령 계층 | 후보 명령 |
| --- | --- | --- |
| 아직 출발 전이고 예상 근접만 존재 | 전략적 | `STRATEGIC_DEPARTURE_DELAY`, `STRATEGIC_SLOT_ASSIGN`, `STRATEGIC_ROUTE_ASSIGN` |
| 동일 회랑에 수요가 장시간 집중 | 전략적 | `STRATEGIC_FLOW_CAPACITY_SET`, `STRATEGIC_ROUTE_REROUTE_BATCH` |
| active flight 간 근접 예측 | 전술적 | `TACTICAL_SPEED_ADJUST`, `TACTICAL_HOLD_ENTER`, `TACTICAL_DIRECT_VIA` |
| 회랑 자체가 사용 불가 | 전술적 또는 전략적 | 즉시면 `TACTICAL_CORRIDOR_CLOSE`, 예약이면 `STRATEGIC_CORRIDOR_STATUS_SCHEDULE` |
| 배터리/비상 상태 | 전술적 | `TACTICAL_EMERGENCY_LAND` |
| RNP/기상 이탈 | 전술적 | `TACTICAL_ROUTE_KEEP_WIND`, `TACTICAL_ALTITUDE_ADJUST`, `TACTICAL_DIRECT_VIA` |

### 7.2 Risk level 기반 전술 후보

| Risk | 의미 | 권장 명령 생성 |
| --- | --- | --- |
| LV0 | 정상 | 명령 없음 또는 모니터링 |
| LV1 | advisory | `TACTICAL_SPEED_ADJUST` 후보 생성, 자동 적용은 정책에 따름 |
| LV2 | caution | 속도 조정 우선, 부족하면 holding/direct-via 후보 생성 |
| LV3 | warning | 즉시 명령. holding, direct-via, altitude adjust, emergency 여부 평가 |

현재 코드의 위험 이유 예시는 `근접 <150m`, `전력 <10%`, `RNP r=...`, `TTV ...s` 형태다. 새 시뮬레이션에서도 `risk_reason`은 명령의 `reason.trigger`로 그대로 연결할 수 있다.

### 7.3 전략 명령과 전술 명령 충돌 처리

1. 전술 명령이 항상 현재 안전을 우선한다.
2. 전술 명령이 끝나면 `TACTICAL_RESUME_PLAN`으로 전략 계획에 복귀한다.
3. 전략 명령이 active flight에 영향을 줄 경우 `effectiveTime`을 두고 전술 상태와 충돌하지 않는지 검증한다.
4. 같은 항공기에 동시에 적용 가능한 전술 명령은 `emergency > hold/direct/altitude > speed > resume` 순으로 정렬한다.
5. 명령마다 `expiresAt` 또는 종료 조건을 둔다.

## 8. 명령 생성에 필요한 판단 데이터

전략적 분리 판단 데이터:

| 데이터 | 필요 이유 |
| --- | --- |
| `flightPlanNumber`, `aircraftId` | 계획/항공기 식별 |
| `std/eobt/etot/eldt/eibt/sta` | 슬롯, 지연, turnaround 판단 |
| `departure/arrival vertiport`, `gate`, `FATO` | 자원 충돌 판단 |
| `enRoute`, `phase`, `targetSpeed`, `LLA.alt` | 경로/고도/속도 계획 충돌 판단 |
| `corridor_default.csv`의 waypoint/link/spare_link | 회랑망과 대체 경로 판단 |
| 트래픽 레벨/목표 운항 수 | 수요 제어 |
| 기상/공역 제한 | 회랑 폐쇄, 우회, 속도 제한 |

전술적 분리 판단 데이터:

| 데이터 | 필요 이유 |
| --- | --- |
| `flight_state.pos_xy`, `dist_m`, `heading_deg`, `track_heading_deg` | 현재 위치와 진행 방향 |
| `speed_mps`, `speed_target_mps`, `alt_m` | 속도/고도 명령 생성 |
| `route_from`, `route_to`, `path_nodes` | 어느 회랑에서 위험이 생겼는지 판단 |
| `risk_level`, `risk_reason` | 전술 명령 트리거 |
| 예측 경로 | 곧 발생할 근접 판단 |
| `lateral_dev_m`, `vertical_dev_m`, `TTV` | RNP/기상 이탈 판단 |
| `battery_pct` | 비상착륙 우선순위 |
| 현재 `FlightControl` 상태 | 이미 적용 중인 speed/hold/autopilot 명령과 충돌 방지 |

## 9. 검증 규칙

공통 검증:

1. `commandId`는 유일해야 한다.
2. `separationLayer`와 `commandType`의 계층이 일치해야 한다.
3. `target.type`별 필수 ID가 있어야 한다.
4. `effectiveTime <= expiresAt`이어야 한다.
5. 이미 만료된 명령은 적용하지 않는다.
6. 실제 상태 변경이 없는 명령도 로그에는 남길 수 있지만 `applied=false`로 기록한다.
7. 명령 적용 전후의 예상 분리, 지연, 우회 거리 중 최소 하나를 기록한다.

전략 명령 검증:

1. 비행계획 시간 순서는 `std <= eobt <= etot <= eldt <= eibt <= sta`를 유지한다.
2. 같은 FATO/gate/항공기의 중복 점유가 없어야 한다.
3. 폐쇄된 회랑을 포함하는 계획은 승인하지 않는다.
4. `routeNodes[]`는 `RoutePlanner`의 port/waypoint에 존재해야 한다.
5. 고도 레이어는 해당 phase에서 적용 가능한 범위여야 한다.

전술 명령 검증:

1. 대상 항공기는 active 상태여야 한다.
2. 속도 명령은 `min_safe_speed_mps`보다 낮아서는 안 된다.
3. holding은 cruise 또는 안전하게 대기 가능한 phase에서만 허용한다.
4. direct/via waypoint는 현재 planner에 존재해야 한다.
5. 회랑 폐쇄는 영향을 받는 active flight의 대체 경로 또는 holding 가능성을 계산해야 한다.
6. 비상착륙은 기존 목적지를 덮어쓰므로 `priority=emergency` 또는 명시 승인 조건이 필요하다.

## 10. 예시 명령

### 10.1 전략적 출발 지연

```json
{
  "commandId": "CMD-STR-0001",
  "commandType": "STRATEGIC_DEPARTURE_DELAY",
  "separationLayer": "strategic",
  "priority": "caution",
  "issueTime": "08:55:00",
  "effectiveTime": "08:55:00",
  "source": {"type": "system", "name": "strategic_planner"},
  "target": {
    "type": "flightPlan",
    "flightPlanNumber": 1202,
    "aircraftId": "UAM0002"
  },
  "scope": {
    "timeWindowS": 900,
    "airspace": ["여의도", "선유도 17고지"]
  },
  "parameters": {
    "delayS": 180,
    "newEtot": "09:13:00"
  },
  "reason": {
    "trigger": "predicted_merge_conflict",
    "detail": "same corridor entry within metering interval"
  },
  "expectedEffect": {
    "delayS": 180,
    "minSeparationGainM": 300
  }
}
```

### 10.2 전략적 회랑 폐쇄 예약

```json
{
  "commandId": "CMD-STR-0002",
  "commandType": "STRATEGIC_CORRIDOR_STATUS_SCHEDULE",
  "separationLayer": "strategic",
  "priority": "routine",
  "issueTime": "08:00:00",
  "source": {"type": "scenario", "name": "weather_case_a"},
  "target": {
    "type": "corridor",
    "from": "성산대교 중간지점",
    "to": "선유도 17고지"
  },
  "scope": {
    "timeWindow": ["09:00:00", "09:30:00"]
  },
  "parameters": {
    "status": "closed",
    "replanPreDepartureFlights": true
  },
  "reason": {
    "trigger": "scheduled_airspace_constraint"
  }
}
```

### 10.3 전술적 속도 조정

```json
{
  "commandId": "CMD-TAC-0001",
  "commandType": "TACTICAL_SPEED_ADJUST",
  "separationLayer": "tactical",
  "priority": "caution",
  "issueTime": "09:12:30",
  "effectiveTime": "09:12:31",
  "expiresAt": "09:13:00",
  "source": {"type": "system", "name": "risk_resolver"},
  "target": {
    "type": "flight",
    "flightId": 42,
    "aircraftId": "UAM0042"
  },
  "scope": {
    "timeWindowS": 30,
    "phase": ["cruise"]
  },
  "parameters": {
    "targetSpeedMps": 41.2,
    "durationS": 25
  },
  "reason": {
    "riskLevel": 2,
    "riskReason": "근접 <300m",
    "trigger": "predicted_proximity"
  },
  "constraints": {
    "minSafeSpeedMps": 25
  },
  "audit": {
    "currentApiMethod": "setFlightSpeed",
    "currentApiArgs": [42, 41.2],
    "rollbackCommand": "TACTICAL_SPEED_CLEAR"
  }
}
```

### 10.4 전술적 Holding 진입

```json
{
  "commandId": "CMD-TAC-0002",
  "commandType": "TACTICAL_HOLD_ENTER",
  "separationLayer": "tactical",
  "priority": "warning",
  "issueTime": "09:14:10",
  "effectiveTime": "09:14:10",
  "source": {"type": "human", "name": "operator"},
  "target": {
    "type": "flight",
    "flightId": 43
  },
  "scope": {
    "phase": ["cruise"],
    "airspace": ["잠실대교 중간지점"]
  },
  "parameters": {
    "loops": 2,
    "exitCondition": "after_loops"
  },
  "reason": {
    "riskLevel": 3,
    "riskReason": "근접 <150m",
    "trigger": "manual_resolution"
  },
  "audit": {
    "currentApiMethod": "startHolding",
    "currentApiArgs": [43, 2],
    "rollbackCommand": "TACTICAL_HOLD_EXIT"
  }
}
```

## 11. 구현 단계 제안

1. 1단계: 기존 API 매핑 유지
   - `/api/control`의 `setFlightSpeed`, `startHolding`, `forceMoveVia`, `setCorridorClosed` 등을 위 command type과 매핑한다.
   - 로그에 `commandType`, `commandId`, `separationLayer`를 추가한다.

2. 2단계: 구조화 명령 엔드포인트 추가
   - `/api/commands`를 추가해 envelope를 직접 받는다.
   - 내부에서 기존 `SimulationApi` 메서드로 변환한다.
   - 적용 결과는 `accepted/applied/rejected/expired`로 반환한다.

3. 3단계: 전략 planner와 전술 resolver 분리
   - 전략 planner는 비행계획/스케줄/회랑/버티포트 자원을 대상으로 명령을 만든다.
   - 전술 resolver는 `flight_state`와 `risk_level`을 대상으로 즉시 명령을 만든다.

4. 4단계: 명령 재생/평가
   - 동일 시나리오를 command log로 재생한다.
   - 지연, 최소 분리, 위험 지속 시간, 개입 횟수, 운영자 workload를 지표로 비교한다.

## 12. 미결정 항목

| 항목 | 결정 필요 내용 |
| --- | --- |
| 실제 분리 기준 | 시뮬레이션 기본값과 실제 운용 기준을 분리해서 관리할지 |
| 고도 레이어 | UAM 회랑 내 고도층을 몇 개로 둘지 |
| 전략/전술 경계 | 예: 5분 전 명령을 전략으로 볼지 전술로 볼지 |
| 자동화 권한 | LV1/LV2/LV3에서 자동 적용 가능한 명령 범위 |
| 회랑 폐쇄 후 no-route 처리 | 즉시 holding, 비상착륙, 출발 지연 중 우선순위 |
| 명령 승인 체계 | human ack가 필요한 명령과 자동 적용 가능한 명령 구분 |
| 로그 스키마 | 기존 `events.csv`에 확장할지 별도 `commands.csv`를 둘지 |

