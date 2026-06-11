# S3 — 배터리 부족 PSU 전술 즉시 개입 (4002 → 3003 land)

## 1. 개요

- **목적**: 운항 중인 UAM 기체의 자가 진단으로 배터리 저전압(critical)이 감지되었을 때, PSU가 4002를 받아 가용 vertiport를 직접 분석·선정하고 **3003 TacticalSeparation(land)을 직접 발행**하여 기체가 즉시 비상 착륙하는 전 과정을 검증한다. 전략 재계획(2001 확장 → Mission → 3001 v2) 경로를 거치지 않는 **PSU 전술 즉시 개입** 사슬: 4002(critical) → PSU 판단 → 3003(land) → Vehicle 즉시 착륙 + Mission plan superseded 마킹.
- **주요 참여 모듈 (역할)**:
  - **VehicleModule (VEHICLE)**: 자가 진단으로 배터리 임계치 위반을 감지하고 4002(critical)을 발행. PSU가 발행한 3003(land)을 수신해 즉시 착륙 수행, 착륙 후 4002 cleared 발행.
  - **MissionModule (MISSION)**: 3003을 수신(`on_tactical_separation`)하여 자기 비행계획(fpn=1201)을 superseded로 마킹. **본 시나리오에서 메시지 발행 없음**.
  - **OperationModule / Monitoring (MONITORING)**: 4002, 3003을 UI에 표출하고 운항자(UAO)에게 경고.
  - **VisualizationModule (VISUAL)**: 3003 land 수신 시 비상 착륙 시각화 및 카메라 트래킹.
  - **PSU (Provider of Services for UAM)**: 4002(critical, LOW_BATTERY 계열)을 받아 주변 vertiport availability/거리 평가 후 VP_KU 선정, **3003(land)을 직접 발행** — 대체 vertiport에 대한 dispatch 권한 보유.
  - **UAO (UAM Air Operator)**: 운항 책임 주체 — **별도 모듈이 아니라 VehicleModule 이 겸업**(사용자 결정). Vehicle 은 2002 DtamExecute 의 `scenarioId: "S3"` 를 수신하면 (a) 배터리 열화 프로필 활성화, (b) UAO 겸업 판단 로직(4002 발행 임계 판정 / 긴급 대응 정책)을 무장(arm)한다. 대체 vertiport 에 대한 **dispatch 권한은 여전히 PSU가 보유**. UAO 명의의 사후 정산/디스패치 책임(post-hoc accountability)은 명목상 유지.
- **시나리오 길이**: 약 32 sim-minutes (정상 운항 ~25분 + 긴급 대응/착륙 ~7분, 배터리 emergency로 단축).
- **트리거 메커니즘**: 1003 ScenarioSetup의 `scenarioFileName` = `S3_uao_battery_alt_vertiport.json`. 내부적으로 `battery.degradation_profile`을 통해 T+25:00 부근에서 battery_pct가 10% 미만으로 떨어지도록 사전 설정.

## 2. 시뮬레이션 timeline

```
T+00:00  User       → SERVER     [1001]  SimModeSetup
                                          payload preview: { operationMode: "single", singleFlight.vehicleSimType.dynamics: "highFidelity" }
                                          note: 단일 비행 모드, 자율 운항.

T+00:00  User       → SERVER     [1003]  ScenarioSetup
                                          payload preview: { scenarioFileName: "S3_uao_battery_alt_vertiport.json",
                                                             mainVehicleType: "KP2A",
                                                             vertiports: [VP_YEOUIDO, VP_JAMSIL, VP_KU(alt)] }
                                          note: SIM_STATE/VISUAL이 vertiport 3개 + 항로망 로드.

T+00:01  User       → SERVER     [2001]  FlightPlanRequest (base, 1회)
                                          payload preview: { scenarioFileName: "S3_...", flightPlanNumber: null, reasonCode: null,
                                                             triggeringEventId: null, arrivalVertiportHint: null }
                                          note: 최초 요청 — MISSION 이 scenarioFileName 으로 데모 플랜 팩
                                                (data/demo_plans/S3_uao_battery_alt_vertiport/) 감지 → 사전 작성 plan 발행.

T+00:02  MISSION    → SERVER     [3001]  ScheduledFlight v1
                                          payload preview: { flightPlanNumber: 1201, planVersion: 1, planStatus: "active",
                                                             aircraftId: "UAM0001",
                                                             departure.vertiport: "VP_YEOUIDO",
                                                             arrival.vertiport: "VP_JAMSIL",
                                                             enRoute: [seq 1..N] }
                                          note: 데모 플랜 팩 로드 (계산 파이프라인 우회) — VEHICLE/VISUAL 수신.

T+00:04  User       → SERVER     [1002]  SimulationSetup (play)
                                          payload preview: { playState: "play", playbackSpeed: 1, simSecondsOfDay: 23400.0 }
                                          note: 06:30 시작(sim 기본), 실시간 1배속 — 데모 플랜 팩 std 06:32 직전.
                                                (S1/S2 와 동일하게 plan 수신 후 play — 순서 통일)

T+00:05  User       → SERVER     [2002]  DtamExecute
                                          payload preview: { simModeFileName, simulationSetupFileName, scenarioFileName, flightPlanFolderName,
                                                             scenarioId: "S3" }
                                          note: 모든 모듈 실행 단계 진입. Vehicle 이 scenarioId=S3 수신 → 배터리 열화 프로필 + UAO 겸업 로직 활성화.

T+00:10  VEHICLE    → SERVER     [4001]  VehicleStatus (10 Hz)
                                          payload preview: { UAM0001.energy.battery_pct: 99.5, gps: {...}, position: {...} }
                                          note: 정상 telemetry 시작.

T+05:00  VEHICLE    → SERVER     [4001]  VehicleStatus
                                          payload preview: { UAM0001.energy.battery_pct: 82.0 }
                                          note: 정상 cruise.

T+15:00  VEHICLE    → SERVER     [4001]  VehicleStatus
                                          payload preview: { UAM0001.energy.battery_pct: 45.0, state_of_charge_pct: 44.2 }
                                          note: 시나리오 사전 설정된 가속 소모 곡선 진입.

T+22:00  VEHICLE    → SERVER     [4002]  VehicleWarningEvent (warning)
                                          payload preview: { eventId: "WARN-UAM0001-20260609-001",
                                                             eventType: "LOW_BATTERY", severity: "warning",
                                                             status: "active",
                                                             detectedValue.battery_pct: 18.0,
                                                             threshold.warning_pct: 20.0,
                                                             recommendedAction: "return_to_base" }
                                          note: 1차 경고. MONITORING/SA/PSU 수신. PSU는 아직 critical 아님 → 관찰만.

T+25:00  VEHICLE    → SERVER     [4002]  VehicleWarningEvent (critical) — TRIGGER
                                          payload preview: { eventId: "WARN-UAM0001-20260609-002",
                                                             category: "energy", subsystem: "battery",
                                                             eventType: "BATTERY_VOLTAGE_LOW", severity: "critical",
                                                             status: "active",
                                                             detectedValue.battery_pct: 9.4,
                                                             threshold.critical_pct: 10.0,
                                                             recommendedAction: "emergency_landing",
                                                             availableDistance: 4200.0 }
                                          note: critical 임계 — MONITORING/SA/PSU 동시 수신. PSU 의사결정 트리거.

T+25:01  PSU        (내부 판단)
                                          note: 현재 position 기준 가용 vertiport 분석 (거리/availability/class).
                                                후보 [VP_KU, VP_JAMSIL, VP_YEOUIDO] 중 가장 가까운 VP_KU 선정.
                                                메시지 발행 없음 — PSU 판단 로직 단계.

T+25:02  PSU        → SERVER     [3003]  TacticalSeparation (IMMEDIATE land) — PSU 직접 발행
                                          payload preview: { commandId: "TMP-PSU-1201-LAND-001",
                                                             aircraftId: "UAM0001",
                                                             reasonCode: "LOW_BATTERY",
                                                             actions: [{ type: "land", vertiport: "VP_KU", fatoNumber: "FATO_A" }] }
                                          note: Hub → VEHICLE + MISSION 양쪽 전달. 전략 재계획(2001 확장) 우회 — 즉시 착륙 명령.

T+25:03  MISSION    (내부 처리)
                                          note: 3003 수신(on_tactical_separation) → fpn=1201 plan을 superseded로 마킹.
                                                메시지 발행 없음 (3001 v2 재발행하지 않음).

T+25:04  VEHICLE    → SERVER     [4001]  VehicleStatus
                                          payload preview: { UAM0001.energy.battery_pct: 9.2, navigation: {...divert_to_VP_KU} }
                                          note: 3003 land 수행 — VP_KU 향해 즉시 descent 진입.

T+27:00  VEHICLE    → SERVER     [4001]  VehicleStatus
                                          payload preview: { UAM0001.energy.battery_pct: 6.1, position: {VP_KU 접근} }
                                          note: 최종 접근.

T+30:00  VEHICLE    → SERVER     [4001]  VehicleStatus
                                          payload preview: { UAM0001.energy.battery_pct: 4.0, attitude: {...flare} }
                                          note: VP_KU FATO_A touchdown 직전.

T+31:30  VEHICLE    → SERVER     [4001]  VehicleStatus
                                          payload preview: { UAM0001.position: {VP_KU FATO_A onGround} }
                                          note: 착륙 완료, motor_rpm → 0.

T+31:35  VEHICLE    → SERVER     [4002]  VehicleWarningEvent (cleared)
                                          payload preview: { eventId: "WARN-UAM0001-20260609-002",
                                                             eventType: "BATTERY_VOLTAGE_LOW",
                                                             severity: "critical", status: "cleared",
                                                             recommendedAction: "continue" }
                                          note: 동일 eventId로 cleared 발행 — PSU/MONITORING/SA 종결 처리.

T+32:00  User       → SERVER     [1002]  SimulationSetup (pause)
                                          payload preview: { playState: "pause" }
                                          note: 시나리오 종료 (운영자가 pause).
```

## 3. 메시지별 상세 payload

### 3.1 2002 DtamExecute — scenarioId 포함 (T+00:05)

```json
{
  "timestamp": "2026-06-09T09:00:05.000Z",
  "simModeFileName": "S3_sim_mode.json",
  "simulationSetupFileName": "S3_simulation_setup.json",
  "scenarioFileName": "S3_uao_battery_alt_vertiport.json",
  "flightPlanFolderName": "S3_flight_plans",
  "scenarioId": "S3"
}
```

> `scenarioId`는 SDK `Msg2002_DtamExecute`의 `Optional[str]` 필드(`"S1"|"S2"|"S3"`) — `None`이면
> `to_wire()`에서 omit 되고, `from_wire()`는 unknown key를 무시한다(하위 호환).
> FORWARD_RULES["2002"] = [mission, monitoring, vehicle, visual, situation_awareness] — 라우팅 변경 없음.
> **Vehicle은 `on_dtam_execute(msg)`에서 `msg.scenarioId`로 분기**: S3 → 배터리 열화 프로필 활성화 +
> UAO 겸업 판단 로직(4002 발행 임계/긴급 대응 정책) 무장(arm).

### 3.2 4002 VehicleWarningEvent — LOW_BATTERY critical (T+25:00)

```json
{
  "messageId": "4002",
  "messageName": "vehicle_warning_event",
  "timestamp": "2026-06-09T09:25:00.000Z",
  "eventId": "WARN-UAM0001-20260609-002",
  "vehicleId": "UAM0001",
  "category": "energy",
  "subsystem": "battery",
  "eventType": "BATTERY_VOLTAGE_LOW",
  "severity": "critical",
  "status": "active",
  "detectedValue": {
    "battery_pct": 9.4,
    "state_of_charge_pct": 9.1
  },
  "threshold": {
    "warning_pct": 20.0,
    "critical_pct": 10.0
  },
  "recommendedAction": "emergency_landing",
  "availableDistance": 4200.0,
  "description": "Battery pack voltage dropped below critical threshold; remaining range insufficient for original arrival (VP_JAMSIL)."
}
```

### 3.3 3003 TacticalSeparation — PSU 직접 발행, IMMEDIATE land at VP_KU (T+25:02)

```json
{
  "timestamp": "2026-06-09T09:25:02.045Z",
  "commandId": "TMP-PSU-1201-LAND-001",
  "aircraftId": "UAM0001",
  "reasonCode": "LOW_BATTERY",
  "actions": [
    {
      "type": "land",
      "vertiport": "VP_KU",
      "fatoNumber": "FATO_A",
      "targetLLA": { "lat": 37.5460, "lon": 127.0415, "alt": 30.0 }
    }
  ]
}
```

> Hub의 FORWARD_RULES["3003"] = [vehicle, mission] 에 따라 VEHICLE과 MISSION 양쪽에 전달된다.
> VEHICLE은 즉시 land 수행, MISSION은 `on_tactical_separation`에서 fpn=1201을 superseded로 마킹한다.

> **참고**: 전략 재계획(2001 확장 4필드 — `flightPlanNumber`/`reasonCode`/`triggeringEventId`/`arrivalVertiportHint`) 경로는
> SDK 인터페이스에 유지되지만, 본 데모 시나리오에서는 사용하지 않는다. 3001 v2(rerouted) 발행도 없다.

## 4. 모듈별 동작 → 발행 메시지

> §2 timeline 이 전체 흐름(시간순)이라면, 본 절은 **모듈 관점 재구성** — 각 모듈 개발자는
> 자기 모듈의 표만 보고 "어떤 트리거에 어떤 동작을 하고 무엇을 발행하는지" 구현할 수 있다.
> 모든 행은 `트리거 → 동작 → 발행` 3단 인과로 기술하며, 발행이 없으면 명시한다.

### 4.1 VehicleModule (VEHICLE) — UAO 겸업

| # | 트리거 (수신 메시지/내부 이벤트) | 동작 설명 | 동작 후 발행 메시지 |
|---|---|---|---|
| 1 | **3001** v1 수신 (fpn=1201) | plan 을 mission state machine 에 로드 — VP_YEOUIDO→VP_JAMSIL 정상 운항 준비 | (없음 — 수신만) |
| 2 | **2002** 수신 (scenarioId=S3) | `on_dtam_execute`에서 `scenarioId` 분기: **배터리 열화 프로필 활성화 + UAO 겸업 판단 로직(4002 발행 임계/긴급 대응 정책) 무장(arm)** | (없음 — 내부 처리) |
| 3 | 비행 중 (내부, 10Hz tick) | 위치/자세/에너지 상태 산출 | **4001** VehicleStatus (10 Hz) |
| 4 | 배터리 18.0% (내부 자가 진단) | warning 임계(20%) 위반 판정 — return_to_base 권고 | **4002** (warning) LOW_BATTERY, status=active |
| 5 | 배터리 9.4% (내부 자가 진단) | critical 임계(10%) 위반 판정 — UAO 겸업 정책으로 emergency_landing 권고 | **4002** (critical) BATTERY_VOLTAGE_LOW, status=active, availableDistance=4200.0 |
| 6 | **3003** land 수신 (PSU 발행) | 정상 plan 시퀀스 중단, land action 우선 실행 — VP_KU FATO_A 향해 즉시 강하(descent) | **4001** navigation=divert_to_VP_KU 반영 (10 Hz 지속) |
| 7 | 착륙 완료 (내부 — VP_KU FATO_A onGround, motor_rpm→0) | 동일 eventId 로 critical 이벤트 종결 | **4002** (cleared) eventId 동일, recommendedAction=continue |

자가 진단(self-diagnostic) 루프의 4002 발행 판단은 **UAO 책임의 위임 수행(embedded UAO role)** —
UAO 는 별도 모듈이 아니라 VehicleModule 이 겸업한다(사용자 결정). 임계값(warning 20% / critical 10%)은
§6.3 의 `thresholds.battery` 를 시작 시점에 읽어 사용하며, 대체 vertiport dispatch 권한은 PSU 가 보유한다.

### 4.2 PSU (Provider of Services for UAM)

| # | 트리거 (수신 메시지/내부 이벤트) | 동작 설명 | 동작 후 발행 메시지 |
|---|---|---|---|
| 1 | **4002** (warning) 수신 (battery 18.0%) | 아직 critical 아님 — 이벤트 리스트 등재 후 관찰만 | (없음 — 수신만) |
| 2 | **4002** (critical) 수신 (battery 9.4%, BATTERY_VOLTAGE_LOW) | 현재 position 기준 가용 vertiport 분석(거리/availability/class) — 후보 [VP_KU, VP_JAMSIL, VP_YEOUIDO] 중 가장 가까운 VP_KU 선정 (내부 판단, T+25:01) | **3003** TacticalSeparation (IMMEDIATE land) — reasonCode=LOW_BATTERY, actions=[{type:"land", vertiport:"VP_KU", fatoNumber:"FATO_A", targetLLA}] |
| 3 | **4002** (cleared) 수신 | 동일 eventId 이벤트 종결 처리 | (없음 — 수신만) |

4002 critical 중 energy 계열(LOW_BATTERY / BATTERY_VOLTAGE_LOW / BATTERY_OVERHEAT 등)은 우선 이벤트
리스트에서 처리한다. **대체 vertiport 에 대한 dispatch 권한(authority)은 본 시나리오에서 PSU 가 보유** —
전략 재계획(2001 확장 → Mission → 3001 v2) 경로를 우회하는 전술 즉시 개입이다.

### 4.3 MissionModule (MISSION)

| # | 트리거 (수신 메시지/내부 이벤트) | 동작 설명 | 동작 후 발행 메시지 |
|---|---|---|---|
| 1 | **2001** 수신 (`scenarioFileName=S3_uao_battery_alt_vertiport.json`) | 데모 플랜 팩 (`data/demo_plans/S3_uao_battery_alt_vertiport/`) 로드 — 계산 파이프라인 우회 | **3001** ×1 (fpn=1201 UAM0001, 사전 작성) |
| 2 | **3003** 수신 (PSU 발행) | `on_tactical_separation` — 자기 비행계획 fpn=1201 을 **superseded 로 마킹** (plan 정합성 추적) | (없음 — 내부 처리) |

PSU 개입 이후 **본 시나리오에서 메시지 발행 없음** — 3001 v2(rerouted) 재발행, 2001 응답 등 일절 없음.

### 4.4 OperationModule / Monitoring (MONITORING)

| # | 트리거 (수신 메시지/내부 이벤트) | 동작 설명 | 동작 후 발행 메시지 |
|---|---|---|---|
| 1 | **4002** (warning/critical) 수신 | UI alert 표출 — 운항자(UAO) 콘솔에 critical 경보를 시각/청각 알람으로 안내 | (없음 — 수신만) |
| 2 | **3003** (land) 수신 | 착륙 명령 출처(PSU)와 새 도착지(VP_KU) 안내 — "PSU: tactical land → VP_KU", "UAO: informed" 이벤트를 시간순 로그 기록 | (없음 — 수신만) |
| 3 | **4002** (cleared) 수신 | 경보 종결 표출 | (없음 — 수신만) |

### 4.5 IntegrationHub (SIM_STATE — forward/DB 저장)

| # | 트리거 (수신 메시지/내부 이벤트) | 동작 설명 | 동작 후 발행 메시지 |
|---|---|---|---|
| 0 | **1002** 수신 (play/pause) | FORWARD_RULES["1002"] 조회 + DB 저장 — **전 모듈 전체 개방** | **1002** → vehicle/visual/sim_state/mission/monitoring/psu/situation_awareness forward |
| 1 | **2002** 수신 | FORWARD_RULES["2002"] 조회 + DB 저장 | **2002** → mission/monitoring/vehicle/visual/situation_awareness forward |
| 2 | **3001** 수신 | FORWARD_RULES["3001"] 조회 + DB 저장 (plan 이력) | **3001** → vehicle/visual forward |
| 3 | **4001** 수신 (10 Hz) | FORWARD_RULES["4001"] 조회 + DB 저장 — 고주기 메시지는 latest-only forward | **4001** → monitoring/visual/situation_awareness/psu forward |
| 4 | **4002** 수신 (warning/critical/cleared) | FORWARD_RULES["4002"] 조회 + DB 저장 | **4002** → monitoring/situation_awareness/psu forward |
| 5 | **3003** 수신 (PSU 발행) | FORWARD_RULES["3003"] 조회 + DB 저장 | **3003** → vehicle/mission forward |

### 4.6 VisualizationModule (VISUAL)

| # | 트리거 (수신 메시지/내부 이벤트) | 동작 설명 | 동작 후 발행 메시지 |
|---|---|---|---|
| 1 | **1003** 수신 | vertiport 3개(VP_YEOUIDO, VP_JAMSIL, VP_KU) + routeNetwork 로드 | (없음 — 수신만) |
| 2 | **3001** v1 수신 | 정상 비행 plan 표시 | (없음 — 수신만) |
| 3 | **4001** 수신 (10 Hz) | 기체 위치/자세 렌더링 | (없음 — 수신만) |
| 4 | **3003** (land) 수신 | 비상 착륙 강조 표시 + VP_KU 카메라 트래킹 | (없음 — 수신만) |

### 4.7 (참고) UAO / VPO — 메시지 없는 역할

- **UAO (UAM Air Operator)**
  - **별도 모듈 없음 — VehicleModule 겸업**(사용자 결정). UAO 판단 로직(4002 발행 임계 판정/긴급 대응 정책)은 VehicleModule 내부에 들어가며, 2002 `scenarioId="S3"` 수신 시 무장된다.
  - **informed/사후 정산 부분만 명목상 UAO 명의로 남는다** — MONITORING 콘솔 표출(4002 critical, PSU 의사결정, 3003 land 인지) 및 정산, 사고 보고, 보험, 승객 케어 등 post-hoc accountability.
  - **대체 vertiport 선정/디스패치 권한은 여전히 PSU가 행사**(사용자 결정).
  - 주의: PSU의 안전/항공교통 의사결정 권한과 UAO의 운항/계약 책임은 분리해 해석할 것 (혼동 금지).
- **VPO (Vertiport Operator)**
  - 본 시나리오에서는 명시적 메시지 송수신 없음. 향후 vertiport availability를 동적으로 PSU에 공급하는 역할로 확장 가능.

## 5. 검증 가능한 결과 (acceptance criteria)

- T+25:00 ±200 ms 내에 VEHICLE이 4002(critical, BATTERY_VOLTAGE_LOW, severity=critical, recommendedAction=emergency_landing, status=active)를 정확히 **1회** publish 한다.
- 착륙 완료 직후 VEHICLE이 critical 과 동일 `eventId`로 4002 `status="cleared"`를 정확히 **1회** 발행한다 — **4002 active 2건 (warning + critical) + cleared 1건** (warning→critical→cleared lifecycle).
- 4002 critical은 FORWARD_RULES에 따라 **MONITORING, SITUATION_AWARENESS, PSU** 세 모듈로 모두 도달한다.
- PSU는 4002 수신 후 가용 vertiport 분석을 거쳐 `reasonCode="LOW_BATTERY"`, `scenarioId="S3"`, `actions[0].type="land"`, `actions[0].vertiport="VP_KU"`, `actions[0].fatoNumber="FATO_A"`인 **3003을 정확히 1회 직접 발행**한다.
- 3003은 FORWARD_RULES["3003"]에 따라 **VEHICLE과 MISSION 양쪽**에 전달된다.
- **2001(확장) 발행 0건, 3001 v2(rerouted) 발행 0건** — 전략 재계획 경로 미사용 검증.
- MISSION은 3003 수신 후 fpn=1201 plan을 superseded로 마킹하되 어떤 메시지도 발행하지 않는다.
- VEHICLE은 3003 land 수신 후 정상 plan 시퀀스를 중단하고 land action을 우선 실행 — 최종 착륙 위치가 **VP_KU 50 m 이내**.
- 시뮬레이션 종료 시점 battery_pct ≥ 3.0 (완전 방전 없이 착륙 성공).
- MONITORING UI 로그에 "PSU: tactical land → VP_KU" 와 "UAO: informed" 두 이벤트가 시간순으로 기록.

## 6. ICD payload 예시

### 6.1 `1003` ScenarioSetup (SDK `Msg1003_ScenarioSetup` 그대로)

Msg1003 의 SDK wire 형식은 `timestamp / scenarioFileName / totalAircraftCount /
mainVehicleType / operationTime / vertiports[] / routeNetwork` 7개 필드뿐.
per-aircraft 정보(aircraftName, battery, vehicleSimType)는 §6.2 의 Msg1001 에 있고,
배터리 fault profile · PSU 정책 같은 시뮬레이터-side 보조 데이터는 §6.3 에 있다.

```json
{
  "timestamp": "2026-06-09T09:00:00.000Z",
  "scenarioFileName": "S3_uao_battery_alt_vertiport.json",
  "totalAircraftCount": 1,
  "mainVehicleType": "KP2A",
  "operationTime": {
    "startTime": "2026-06-09T09:00:00.000Z",
    "endTime":   "2026-06-09T09:35:00.000Z"
  },
  "vertiports": [
    {
      "name": "VP_YEOUIDO",
      "vertiportClass": "hub",
      "lat": 37.5252,
      "lon": 126.9335,
      "angleDegrees": 90.0
    },
    {
      "name": "VP_JAMSIL",
      "vertiportClass": "hub",
      "lat": 37.5133,
      "lon": 127.1028,
      "angleDegrees": 270.0
    },
    {
      "name": "VP_KU",
      "vertiportClass": "port",
      "lat": 37.5460,
      "lon": 127.0415,
      "angleDegrees": 180.0
    }
  ],
  "routeNetwork": {
    "waypoints": [
      {
        "waypointId": "WP_YEO_DEP",
        "waypointName": "Yeouido Departure",
        "lat": 37.5252, "lon": 126.9335, "altFt": 200,
        "links": ["WP_HAN_01"]
      },
      {
        "waypointId": "WP_HAN_01",
        "waypointName": "Han River 1",
        "lat": 37.5260, "lon": 126.9700, "altFt": 1200,
        "links": ["WP_HAN_02"]
      },
      {
        "waypointId": "WP_HAN_02",
        "waypointName": "Han River 2",
        "lat": 37.5275, "lon": 127.0050, "altFt": 1200,
        "links": ["WP_HAN_03", "WP_KU_DIV"]
      },
      {
        "waypointId": "WP_HAN_03",
        "waypointName": "Han River 3",
        "lat": 37.5295, "lon": 127.0123, "altFt": 1150,
        "links": ["WP_JAM_APP", "WP_KU_DIV"]
      },
      {
        "waypointId": "WP_JAM_APP",
        "waypointName": "Jamsil Approach",
        "lat": 37.5133, "lon": 127.1028, "altFt": 400,
        "links": []
      },
      {
        "waypointId": "WP_KU_DIV",
        "waypointName": "KU Divert Gate",
        "lat": 37.5400, "lon": 127.0290, "altFt": 900,
        "links": ["WP_KU_APP"]
      },
      {
        "waypointId": "WP_KU_APP",
        "waypointName": "KU Approach",
        "lat": 37.5453, "lon": 127.0399, "altFt": 400,
        "links": ["WP_KU_FATO"]
      },
      {
        "waypointId": "WP_KU_FATO",
        "waypointName": "KU FATO A",
        "lat": 37.5460, "lon": 127.0415, "altFt": 100,
        "links": []
      }
    ]
  }
}
```

### 6.2 `1001` SimModeSetup — per-aircraft 정보의 진짜 자리

UAM0001 의 출발지/도착지/std/dynamics 는 SDK 의 `Msg1001_SimModeSetup` 에 들어간다.
`Msg1003` 에는 비행체 리스트가 없다.

```json
{
  "timestamp": "2026-06-09T09:00:00.000Z",
  "operationMode": "single",
  "singleFlight": {
    "vehicleSimType": {
      "dynamics": "highFidelity",
      "mainVehicleController": "Autopilot"
    },
    "missionPlanning": {
      "activeMissionId": "M_S3_UAM0001",
      "missions": [
        {
          "aircraftName":  "UAM0001",
          "departureTime": "06:32:00",
          "std":           "06:32:00",
          "departureName": "VP_YEOUIDO",
          "arrivalName":   "VP_JAMSIL"
        }
      ]
    }
  }
}
```

### 6.3 시뮬레이터-side 보조 데이터 (SDK ICD 외)

`scenarioFileName` 이 가리키는 시뮬레이터 입력 파일에는 SDK 의 ICD wire 와 별개로
다음 보조 데이터가 들어간다. 이들은 시뮬레이터·PSU 모듈 내부 구현으로 처리되고
ICD 로 송수신되지 않는다.

```json
{
  "traffic": { "trafficScenario": "low" },
  "battery": {
    "UAM0001": {
      "initialPct": 99.5,
      "degradationProfile": {
        "type": "accelerated_fault",
        "faultStartSec": 600,
        "criticalAtSec": 1500,
        "criticalPct": 9.4
      }
    }
  },
  "thresholds": {
    "battery": { "warning_pct": 20.0, "critical_pct": 10.0 }
  },
  "psuConfig": {
    "alternateVertiportPolicy": "nearest_available",
    "candidateVertiports": ["VP_KU", "VP_JAMSIL", "VP_YEOUIDO"],
    "dispatchAuthority": "PSU",
    "uaoRole": "vehicle_embedded"
  }
}
```

> 4002 의 `threshold.warning_pct=20`, `threshold.critical_pct=10` 는 위 `thresholds.battery`
> 와 1:1 대응. Vehicle 측 진단 로직이 시작 시점에 이 값을 읽어 자신의 4002 발행
> 기준으로 삼는다.
>
> `uaoRole: "vehicle_embedded"` — UAO는 별도 모듈이 아니라 **VehicleModule 이 겸업**한다는
> 표시(사용자 결정). UAO 판단 로직은 Vehicle 내부에서 2002 `scenarioId="S3"` 수신 시
> 무장되며, dispatch 권한은 여전히 PSU(`dispatchAuthority: "PSU"`).

> **데모 플랜 팩**: S3 의 3001 은 Mission 계산 파이프라인이 아니라 사전 작성된 데모 플랜 팩
> (`MissionModule/data/demo_plans/S3_uao_battery_alt_vertiport/`)에서 로드되어 발행된다.
> S1 은 데모 팩 없이 기존 계산 경로를 사용한다.

## 변경 이력

- **2026-06-10 — UAO=Vehicle 겸업 (사용자 확정)**: UAO 역할을 별도 모듈이 아닌 **VehicleModule 겸업**으로 확정. SDK `Msg2002_DtamExecute`에 `scenarioId: Optional[str]`(`"S1"|"S2"|"S3"`) 추가 — Operation Console이 실행 시점에 시나리오를 Vehicle에 통지, Vehicle은 `on_dtam_execute`에서 S3 분기 시 배터리 열화 프로필 + UAO 겸업 판단 로직 무장. dispatch 권한은 PSU 유지, `uaoRole: "vehicle_embedded"`로 갱신.
- **2026-06-10 — 시나리오 개편 (사용자 확정)**: 기존 흐름 `4002 → PSU(2001 확장) → Mission(3001 v2 + 3003)` 을 **PSU 전술 즉시 개입** 흐름 `4002 → PSU 판단(가용 vertiport 분석, VP_KU 선정) → PSU 3003 직접 발행(land) → Vehicle 즉시 착륙 + Mission plan superseded 마킹` 으로 교체.
  - SDK 변경 반영: 3003 direction = `mission|psu->server` (PSU 발행 가능), FORWARD_RULES["3003"] = [vehicle, mission], MissionModule `on_tactical_separation(3003)` stub 신설.
  - 전략 재계획(2001 확장) 경로는 SDK 인터페이스로 유지되나 본 데모에서는 미사용. 3001 v2 sample 삭제.
  - 제목 변경: "S3 — UAO 배터리 고장 대체 vertiport (긴급 착륙)" → "S3 — 배터리 부족 PSU 전술 즉시 개입 (4002 → 3003 land)".

- **3003 scenarioId 폐기 (2026-06-11)**: 시나리오 타입은 2002 `scenarioId` 로만 전달 — 3003 은 순수 전술 명령 (SDK 필드 제거).
