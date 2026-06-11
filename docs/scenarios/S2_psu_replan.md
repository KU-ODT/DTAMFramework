# S2 — 실traffic 운용 중 PSU 반자동 속도 조정 개입 (3,360편)

## 1. 개요

- **목적**: 하루 전체 실traffic 셋 — **3,360편 / 기체 136대 / vertiport 17개 / std 06:30~21:30** — 을 **prebuilt 3001 ScheduledFlight 로 일괄 투입**하고, 운영 중 운영자가 Ops Console 기상 패널에서 **바람 등급 serious 를 선택 (1002 `wind.weather`)** 하여 외란을 가한다. 외란 누적으로 근접/위험 상황이 발생하면 **운영자가 PSU 콘솔(4001 폴링 감시 화면)에서 근접/위험 기체를 식별**하고, **PSU UI 의 3003 draft → dispatch (반자동)** 로 해당 기체에 `setSpeed` 개입을 내린다. Vehicle 은 3003 의 setSpeed 를 즉시 수행하고, Mission 은 3003 을 수신해 plan 장부에 전술 이탈을 마킹한다 (수신 전용).
- **반자동 (D-2, 2026-06-11 확정)**: PSU 의 충돌 **자동 예측·자동 발행은 추후 선택 과제 (P-3)** 로 격하. S2 데모의 개입 주체는 **운영자** — PSU UI 가 3003 draft 를 만들어 주고, 운영자가 dispatch 버튼을 눌러 발행한다 (허브 `POST /api/msg/3003` 호환 검증 완료).
- **traffic 투입 (D-5, 2026-06-11 확정)**: 콘솔 S2 버튼 → `scenarioFileName="20260611_131306_98f166edc22f.json"` → Mission 이 prebuilt 3001 JSON 3,360개를 **직로딩**하여 일괄 발행 (계산 파이프라인 우회). 스폰은 기체별 dedupe 로 **136 entries** (검증 완료). 기존 2기체 데모 팩 (`demo_plans/S2_psu_replan`) 은 보존용으로 유지.
- **바람은 외란 환경 요소**일 뿐 — Vehicle 의 1002 `wind.weather` 수신·적용은 시나리오 무관 표준 처리. 전략 재계획 경로 (2001 확장 → 3001 v2 + 3002) 는 SDK 인터페이스로 유지되지만 **S2 데모 흐름에서는 사용하지 않는다**. (3002 의 발행 주체는 D-3 에 따라 `psu|mission` 으로 확장 — catalog direction `psu|mission->server` 코드 반영 완료, 단 S2 데모에서 3002 발행 0건.)
- **주요 참여 모듈 (역할)**
  - **IntegrationHub (SERVER)**: 메시지 포워딩 (FORWARD_RULES) + `POST /api/msg/{mid}` REST 수신 — 1002 → 전 모듈, 3001 → VEHICLE/VISUAL, 3003 → VEHICLE/MISSION
  - **MissionModule (MISSION)**: 2001(기본, 1회) 소비 → **prebuilt 3001 직로딩 3,360편 일괄 발행**. 이후 3003 수신 전용 (장부 마킹)
  - **VehicleModule (VEHICLE)**: 다수 기체 세션 (136 spawn entries, dedupe) — 4001 송출, 1002 `wind.weather` 바람장 적용, **3003 setSpeed 즉시 수행**
  - **PSU (신규 반입 모듈)**: 4001/3001 **DB/REST 폴링** 수신 감시 (SDK 미사용 — REST, 동작 검증됨), **3002/3003 draft→dispatch UI (운영자 주도)**. 4002 수신 없음 (D-1), 4001 `battery_pct` 저전력 감시 (≤20% 카운트) 는 수행
  - **OperationModule / OpsConsole (MONITORING)**: **S2 선택(잠금)/설정 저장/Play** + 기상 패널 바람 등급 선택 → 1002 발행
  - **SimulationStateModule / VisualizationModule**: S1 동일 (0003 1 Hz / 4001 메쉬·4101 프레임)
- **시나리오 길이**: 하루 전체 traffic (sim 06:30~21:30). 데모 시연은 playbackSpeed 가속 + 임의 구간 발췌 — **실traffic 이므로 근접/위험 발생 시점은 비결정적**이며, 절대시각 대신 단계 번호로 기술한다 (§2).
- **트리거 메커니즘**:
  - 시나리오 선택: 콘솔 S2 버튼 (잠금) → `scenarioFileName="20260611_131306_98f166edc22f.json"`
  - traffic 투입: 2001 (1회) → Mission prebuilt 3001 ×3,360 → 2002 `scenarioId="S2"`
  - 바람 트리거: 기상 패널 바람 등급 serious → 1002 (T+α)
  - 개입 트리거: **운영자가 PSU UI 에서 대상 기체 선택 → 3003 setSpeed draft → dispatch** (T+β, 반자동)

## 2. 시뮬레이션 timeline (데모 절차)

> 실traffic 3,360편 운용이라 **근접/위험 발생 시점이 비결정적** — 절대시각(T+mm:ss) 대신 **단계 번호** 로 기술한다.
> T+α (바람 인가), T+β (운영자 dispatch) 는 데모 진행자가 상황을 보고 결정한다.

```text
# 단계 0: 부팅 + 모듈 등록
STEP 0   ALL MODULES → SERVER  [0001] ModuleSettingInfo  (VEHICLE/VISUAL/MISSION/SIM_STATE/MONITORING/PSU)
                               [0002] ModuleStatus (1 Hz heartbeat)
                               note: PSU 는 REST 폴링 기반 — 허브 DB/REST 로 4001/3001 수신 준비

# 단계 1: S2 선택 (잠금)
STEP 1   User(OpsConsole)      콘솔 시나리오 패널에서 S2 선택 → 시나리오 잠금
                               note: scenarioFileName="20260611_131306_98f166edc22f.json" 확정.
                                     1001 SimModeSetup { operationMode: "traffic", traffic: { trafficScenario: "customed" } }

# 단계 2: 설정 저장 (스폰 구성)
STEP 2   User(OpsConsole) → SERVER  [1003] ScenarioSetup
                               payload preview: { scenarioFileName: "20260611_131306_98f166edc22f.json",
                                                  totalAircraftCount: 136, mainVehicleType: "KP2A" }
                               note: ★ 스폰은 3,360편이 아니라 기체별 dedupe 136 entries (검증 완료) —
                                     같은 기체가 하루 여러 leg 를 수행. vertiport 17개 로드

# 단계 3: Play — traffic 일괄 투입
STEP 3a  User       → SERVER   [2001] FlightPlanRequest (기본형, 1회)
                               payload preview: { scenarioFileName: "20260611_131306_98f166edc22f.json",
                                                  flightPlanNumber: null, reasonCode: null }
                               note: ★ 2001 은 한 번만 — Mission 이 FPL 폴더의 prebuilt 3001 을 감지·직로딩

STEP 3b  MISSION    → SERVER   [3001] ScheduledFlight ×3,360 (prebuilt 직로딩, 일괄 발행)
                               payload preview: { flightPlanNumber: 109001, planVersion: 1,
                                                  planStatus: "active", aircraftId: "UAM0001", ... }
                               note: PlugIn/FlightScheduler/FPL/20260611_131306_98f166edc22f/ScheduledFlight/
                                     의 JSON 3,360개를 계산 파이프라인 우회로 그대로 발행 → VEHICLE/VISUAL (PSU 폴링)

STEP 3c  User       → SERVER   [2002] DtamExecute
                               payload preview: { scenarioFileName: "20260611_131306_98f166edc22f.json",
                                                  scenarioId: "S2" }
STEP 3d  User       → SERVER   [1002] SimulationSetup { playState: "play", wind: { grade: "normal" } }
                               note: sim 06:30 출발 — 이후 0003 1 Hz, 4001 10 Hz, 4101 5 Hz 흐름 시작

# 단계 4: 운항 (실traffic)
STEP 4   VEHICLE    → SERVER   [4001] VehicleStatus — 활성 기체 다수 동시 송출
                               note: std 06:30~21:30 에 걸쳐 이착륙 반복. PSU 콘솔이 4001 폴링으로 전 기체 감시

# 단계 5 (T+α): 바람 외란 인가
STEP 5   User(OpsConsole) → SERVER  [1002] SimulationSetup — 기상 패널 바람 등급 serious — TRIGGER 1
                               payload preview: { playState: "play", wind: { grade: "serious",
                                 weather: { preset: "bad", season: "summer", localHour: 9,
                                            seed: 20260611, includeGust: true, t: 0.0 } } }
                               note: 기존 콘솔 날씨 선택 기능. Vehicle 이 바람장 적용 → 궤적 drift 발생

# 단계 6 (T+β): 운영자 식별 → PSU 반자동 개입
STEP 6a  Operator(PSU UI)      4001 폴링 화면에서 근접/위험 기체 식별 (수평 분리 수렴 추세)
                               note: 비결정적 — 실traffic 밀도와 바람 seed 에 따라 대상/시점 상이

STEP 6b  Operator(PSU UI) → SERVER  [3003] TacticalSeparation — draft → dispatch (반자동) — TRIGGER 2
                               payload preview: { commandId: "TMP-PSU-UAM0034-20260611-0001",
                                                  aircraftId: "UAM0034",
                                                  reasonCode: "LOSS_OF_SEPARATION_RISK",
                                                  actions: [ { type: "setSpeed", targetSpeed: 40.0 } ] }
                               note: PSU UI 가 draft 생성, 운영자가 dispatch 버튼 클릭 → 허브 POST /api/msg/3003.

# 단계 7: 감속 확인
STEP 7   VEHICLE    → SERVER   [4001] (대상 기체 1초 이내 감속 — speed 변화, 경로/헤딩 불변)
         MISSION    (internal) 3003 수신 — 해당 fpn 에 "tactical deviation active" 장부 마킹 (발행 없음)
                               note: 필요 시 운영자가 두 번째 3003 (setSpeed 복원) dispatch — 선택.
                                     이후 traffic 운항 지속, 데모 발췌 구간 종료 시 1002 playState="pause"
```

## 3. 메시지별 상세 payload

### 3.1 prebuilt 3001 ScheduledFlight 샘플 — `109001_UAM0001` (여의도 → 성수)

> FPL 폴더 `ScheduledFlight/` 의 3,360개 JSON 중 1번 편. **phase A..K 12 세그먼트** — Mission 이 그대로 발행한다 (직로딩).

```json
{
  "flightPlanNumber": 109001,
  "planVersion": 1,
  "planStatus": "active",
  "aircraftId": "UAM0001",
  "departure": {
    "vertiport": "여의도",
    "std": "06:30:00", "eobt": "06:30:00", "etot": "06:36:55",
    "depGateNumber": "G1", "depFatoNumber": "F1"
  },
  "enRoute": [
    { "seq": 1,  "phase": "A", "startLLA": { "lat": 37.526513, "lon": 126.922845, "alt": 0.0 },   "endLLA": { "lat": 37.526513, "lon": 126.922845, "alt": 0.0 },    "targetSpeed": 3.0 },
    { "seq": 2,  "phase": "B", "startLLA": { "lat": 37.526513, "lon": 126.922845, "alt": 0.0 },   "endLLA": { "lat": 37.526513, "lon": 126.922845, "alt": 15.0 },   "targetSpeed": 10.0 },
    { "seq": 3,  "phase": "C", "startLLA": { "lat": 37.526513, "lon": 126.922845, "alt": 15.0 },  "endLLA": { "lat": 37.519919, "lon": 126.933669, "alt": 100.0 },  "targetSpeed": 36.0 },
    { "seq": 4,  "phase": "E", "startLLA": { "lat": 37.519919, "lon": 126.933669, "alt": 100.0 }, "endLLA": { "lat": 37.508684, "lon": 126.952110, "alt": 219.3 },  "targetSpeed": 51.4 },
    { "seq": 5,  "phase": "E", "startLLA": { "lat": 37.508684, "lon": 126.952110, "alt": 219.3 }, "endLLA": { "lat": 37.503384, "lon": 126.967415, "alt": 305.0 },  "targetSpeed": 51.4 },
    { "seq": 6,  "phase": "F", "startLLA": { "lat": 37.503384, "lon": 126.967415, "alt": 305.0 }, "endLLA": { "lat": 37.497738, "lon": 126.983721, "alt": 305.0 },  "targetSpeed": 51.4 },
    { "seq": 7,  "phase": "F", "startLLA": { "lat": 37.497738, "lon": 126.983721, "alt": 305.0 }, "endLLA": { "lat": 37.507422, "lon": 127.010349, "alt": 305.0 },  "targetSpeed": 51.4 },
    { "seq": 8,  "phase": "G", "startLLA": { "lat": 37.507422, "lon": 127.010349, "alt": 305.0 }, "endLLA": { "lat": 37.509486, "lon": 127.016026, "alt": 272.95 }, "targetSpeed": 36.0 },
    { "seq": 9,  "phase": "G", "startLLA": { "lat": 37.509486, "lon": 127.016026, "alt": 272.95 },"endLLA": { "lat": 37.531492, "lon": 127.035175, "alt": 100.0 },  "targetSpeed": 36.0 },
    { "seq": 10, "phase": "I", "startLLA": { "lat": 37.531492, "lon": 127.035175, "alt": 100.0 }, "endLLA": { "lat": 37.538917, "lon": 127.041635, "alt": 15.0 },   "targetSpeed": 30.0 },
    { "seq": 11, "phase": "J", "startLLA": { "lat": 37.538917, "lon": 127.041635, "alt": 15.0 },  "endLLA": { "lat": 37.538917, "lon": 127.041635, "alt": 0.0 },    "targetSpeed": 10.0 },
    { "seq": 12, "phase": "K", "startLLA": { "lat": 37.538917, "lon": 127.041635, "alt": 0.0 },   "endLLA": { "lat": 37.538917, "lon": 127.041635, "alt": 0.0 },    "targetSpeed": 3.0 }
  ],
  "arrival": {
    "vertiport": "성수",
    "sta": "06:49:00", "eibt": "06:49:00", "eldt": "06:42:10",
    "arrGateNumber": "G4", "arrFatoNumber": "F3"
  }
}
```

### 3.2 3003 TacticalSeparation — PSU UI dispatch (T+β, 반자동)

> **발행 주체는 PSU** (SDK 3003 direction: `mission|psu->server`), 단 **운영자가 draft→dispatch 버튼을 눌러 발행** 하는 반자동.
> 허브 `POST /api/msg/3003` 호환 검증 완료. `commandId` 는 `TMP-PSU-{aircraftId}-{YYYYMMDD}-{SEQ}` 포맷.
> 액션: **`setSpeed` 단일 액션** — directTo 미사용, 경로 불변. FORWARD_RULES[3003]=[VEHICLE, MISSION].

```json
{
  "messageId": "3003",
  "messageName": "tactical_separation",
  "timestamp": "2026-06-11T09:25:00.250+09:00",
  "commandId": "TMP-PSU-UAM0034-20260611-0001",
  "aircraftId": "UAM0034",
  "reasonCode": "LOSS_OF_SEPARATION_RISK",
  "actions": [
    {
      "type": "setSpeed",
      "targetSpeed": 40.0
    }
  ]
}
```


> (선택) 분리 회복 후 운영자가 두 번째 3003 — `actions=[{ "type": "setSpeed", "targetSpeed": 55.0 }]` (속도 복원) 또는 `[{ "type": "rejoinPlan", "atSeq": n }]` — 을 dispatch 할 수 있다. 생략 가능.

## 4. 모듈별 동작 → 발행 메시지

> 각 모듈의 표는 시간순이며, **모듈 개발자가 자기 모듈 표만 보고 구현 가능**하도록 구성한다.
> 모든 행은 "트리거 → 동작 → 발행" 3단 인과. 전체 흐름은 §2 timeline 참조.

### 4.1 OperationModule (OpsConsole, MONITORING)

| # | 트리거 (수신 메시지/내부 이벤트) | 동작 설명 | 동작 후 발행 메시지 |
|---|---|---|---|
| 1 | 운영자 S2 버튼 클릭 (STEP 1) | 시나리오 S2 선택·잠금 — `scenarioFileName="20260611_131306_98f166edc22f.json"` 확정 | **1001** SimModeSetup (traffic/customed) |
| 2 | 운영자 설정 저장 (STEP 2) | 스폰 구성 — 기체별 dedupe **136 entries**, vertiport 17 | **1003** ScenarioSetup |
| 3 | 운영자 Play (STEP 3) | 2001 1회 → 2002 → play 순 발행 | **2001**, **2002** (`scenarioId="S2"`), **1002** (play) |
| 4 | 0001/0002/4001/4101 수신 | 모듈 상태·비행 상태·카메라 시각화 | (없음 — 수신만) |
| 5 | 운영자 기상 패널 바람 등급 serious (STEP 5, T+α) | 기존 날씨 선택 기능 — wind.weather 자동 동봉 (grade→preset 매핑 serious→bad) | **1002** `wind.grade=serious` |

### 4.2 PSU (신규 반입 모듈 — 반자동)

| # | 트리거 (수신 메시지/내부 이벤트) | 동작 설명 | 동작 후 발행 메시지 |
|---|---|---|---|
| 1 | 3001 수신 (DB/REST 폴링) | 3,360편 계획 적재 — 감시 대상 목록 구성 | (없음 — 내부 처리) |
| 2 | 4001 수신 (DB/REST 폴링, 지속) | 전 기체 위치·속도 감시 화면 갱신 + `battery_pct` 저전력 감시 (≤20% 카운트 — D-1) | (없음 — 내부 처리) |
| 3 | 운영자가 근접/위험 기체 식별 (STEP 6a, T+β) | UI 에서 대상 기체 선택 → 3003 setSpeed **draft** 자동 구성 | (없음 — draft 단계) |
| 5 | (선택) 분리 회복 확인 | 두 번째 draft→dispatch — 속도 복원 | **3003** setSpeed 복원 (선택) |

> **반자동 (D-2)**: 자동 충돌 예측·자동 발행은 **P-3 선택 과제** — S2 데모는 운영자 판단 + dispatch.
> SDK 미사용 (REST 폴링) — 동작 검증됨, SDK 전환은 선택. 4002 수신 없음 (4002 폴링 추가는 후속 요청).
> 3002 draft→dispatch UI 도 보유 (D-3: 3002 sender `psu|mission`) — 단 **S2 데모에서 3002 발행 0건**.

### 4.3 VehicleModule (다수 기체 세션 — 136 spawn entries)

| # | 트리거 (수신 메시지/내부 이벤트) | 동작 설명 | 동작 후 발행 메시지 |
|---|---|---|---|
| 1 | 3001 수신 (×3,360) | 자기 기체(aircraftId) 해당 plan 적재 — 같은 기체가 하루 여러 leg 순차 수행 | (없음 — 수신만) |
| 2 | 2002 수신 (`scenarioId="S2"`) | **특별 무장 없음 (정보성)** — 시나리오 전용 분기 없음 | (없음 — 수신만) |
| 3 | 비행 중 (내부, 10 Hz tick) | position/gps/energy/navigation 산출 — 활성 기체 다수 동시 | **4001** VehicleStatus (10 Hz) |
| 4 | 1002 수신 (`wind.weather.preset="bad"`) | 표준 처리 — weather_core snapshot 투입 → 바람장 적용 → 궤적 drift | (없음 — drift 가 **4001** 에 반영) |
| 5 | 3003 수신 | **setSpeed 즉시 수행** — targetSpeed 변경만, 경로/헤딩 불변 | (없음 — 1초 이내 **4001** speed 변화로 반영) |

### 4.4 MissionModule

| # | 트리거 (수신 메시지/내부 이벤트) | 동작 설명 | 동작 후 발행 메시지 |
|---|---|---|---|
| 1 | 2001 수신 (`scenarioFileName="20260611_131306_98f166edc22f.json"`) | FPL 폴더 prebuilt 감지 → `ScheduledFlight/` JSON 3,360개 **직로딩** (계산 파이프라인 우회) | **3001** ×3,360 일괄 발행 |
| 2 | 3003 수신 (`on_tactical_separation`) | **수신 전용** — 해당 fpn 에 전술 이탈 (commandId, reasonCode) 장부 마킹 | (없음 — 수신만) |

> **S2 에서 3001 v2 / 3002 / 2001 확장을 발행하지 않음** — 전략 재계획 경로는 SDK 인터페이스로만 유지.

### 4.5 IntegrationHub (SERVER)

| # | 트리거 (수신 메시지/내부 이벤트) | 동작 설명 | 동작 후 발행 메시지 |
|---|---|---|---|
| 1 | 0001/0002 수신 | FORWARD_RULES 조회 + DB 저장 | **0001**/**0002** → MONITORING forward |
| 2 | 1002 수신 | FORWARD_RULES[1002] + DB 저장 | **1002** → 전 모듈 fan-out (VEHICLE/VISUAL/SIM_STATE/MISSION/MONITORING/PSU/SA) |
| 3 | 3001 수신 (×3,360 burst) | FORWARD_RULES + DB 저장 — 일괄 투입 burst 처리 | **3001** → VEHICLE/VISUAL forward (PSU 는 DB/REST 폴링으로 취득) |
| 4 | 4001 수신 (10 Hz × 다수 기체) | FORWARD_RULES + DB 저장 | **4001** → MONITORING/VISUAL/SA forward (PSU 는 폴링) |
| 5 | `POST /api/msg/3003` 수신 (PSU UI dispatch) | REST 수신 → FORWARD_RULES[3003] + DB 저장 | **3003** → VEHICLE/MISSION forward |

## 5. 검증 가능한 결과 (acceptance criteria)

- 콘솔 S2 선택·저장 시 `scenarioFileName="20260611_131306_98f166edc22f.json"` 으로 잠기고, 스폰이 기체별 dedupe **136 entries** 로 구성된다.
- Play 후 **3001 이 정확히 3,360건 발행**된다 (Mission prebuilt 직로딩 — IntegrationHub 로그/DB 카운트로 확인).
- **1002 `wind.grade=serious` 가 1회 이상 발행**된다 (기상 패널 — 기존 기능).
- **PSU UI dispatch 로 3003(setSpeed) 이 1회 이상 발행**된다 — **운영자 주도 (반자동)** 이며 다음을 만족:
  - `commandId` 가 `TMP-PSU-` prefix
  - `reasonCode == "LOSS_OF_SEPARATION_RISK"`
  - `actions` 에 `setSpeed` 액션 포함, **`directTo` 액션 0건**
  - FORWARD_RULES 에 따라 **VEHICLE 과 MISSION 양쪽**으로 전달
- **대상 기체가 3003 수신 후 1초 이내 감속**한다 (4001 speed 변화로 확인, heading/경로 불변).
- MISSION 은 3003 을 수신해 해당 fpn 에 전술 이탈을 마킹하되 **어떤 메시지도 발행하지 않는다**.
- **3001 v2 발행 0건, 3002 발행 0건 (데모 흐름), 2001 확장 발행 0건** — 전 plan `planVersion == 1` 유지.
- (선택) 두 번째 3003 (setSpeed 복원) 이 발행될 수 있다 — 미발행 시에도 pass.

## 6. 데이터 출처 (FPL prebuilt 셋)

### 6.1 폴더 구조

```text
PlugIn/FlightScheduler/FPL/20260611_131306_98f166edc22f/
├── manifest.json                  # 셋 메타데이터 (아래 6.2)
├── FPL_all.csv                    # 전체 FPL CSV (3,360 rows)
├── FPL_<vertiport>.csv ×17       # vertiport 별 FPL (가산/강남/광화문/마곡/망우/목동/미아/봉천/
│                                  #   사당/상암/성수/수서/여의도/연신내/용산/잠실/천호)
├── ScheduledFlight/               # ★ prebuilt 3001 JSON ×3,360 — Mission 이 직로딩·발행
│   ├── 109001_UAM0001.json        #   파일명 = {flightPlanNumber}_{aircraftId}.json
│   ├── 116001_UAM0002.json
│   └── … (3,360개)
└── _metrics/                      # 생성기 메트릭 (hourly/type/bottlenecks/resourceEvents — 데모 미사용)
```

### 6.2 manifest.json (요약)

```json
{
  "scenarioId": "98f166edc22f",
  "scenarioDate": "2026-07-11",
  "createdAt": "2026-06-11T13:13:10",
  "primaryFplFile": ".../FPL_all.csv",
  "scheduledFlightDirectory": ".../ScheduledFlight",
  "primaryScheduledFlightFile": ".../ScheduledFlight/109001_UAM0001.json",
  "counts": { "flights": 3360, "scheduledFlightJson": 3360, "vertiportFiles": 17 }
}
```

- **flights = scheduledFlightJson = 3,360** — FPL CSV 와 prebuilt 3001 JSON 이 1:1.
- 기체 136대 (UAM0001~ — 같은 기체가 하루 여러 leg), vertiport 17개, std 06:30~21:30.
- `scenarioDate` 는 traffic 셋 자체의 가정 날짜 (2026-07-11) — 데모 실행 날짜와 무관.

### 6.3 구 2기체 데모 팩 — 보존

> 기존 S2 의 2기체 데모 플랜 팩 (`MissionModule/data/demo_plans/S2_psu_replan/`, UAM0001/UAM0002,
> fpn 1201/1202) 은 **보존용으로 유지** — 3,360편 셋 없이 최소 구성으로 흐름을 점검할 때 사용 가능.
> S2 정식 데모는 본 절의 FPL prebuilt 셋을 사용한다.

## 변경 이력

- **구 흐름 (전략 재계획)**: PSU 가 충돌을 감지하면 2001 확장(TRAFFIC_CONFLICT)을 발행하고 Mission 이 3001 v2 + 3002 + 3003 을 발행하는 전략 재계획 경로였다.
- **신 흐름 (PSU 전술 직접 개입)**: 데모에서 보여주려는 핵심이 "PSU 의 실시간 감시·즉시 개입" 이므로, Mission 을 경유하는 다단계 재계획 대신 PSU 가 3003 을 직접 발행해 반응 시간을 줄이고 책임 경계(PSU=전술, Mission=전략)를 명확히 드러내도록 변경했다. 전략 재계획 경로(2001 확장)는 SDK 인터페이스로 유지된다.
- **S2 재정의 (속도 조정 재계획, 2026-06-10)**: PSU 개입을 3003 `setSpeed` (속도 조정) 중심으로 재정의 — directTo 는 기본 흐름에서 제거. 바람은 외란 환경 요소이며 Vehicle 의 바람 처리는 시나리오 무관 표준 처리 (당시 5004 경유 — 2026-06-11 폐기, 아래 항목). `scenarioId="S2"` 는 Vehicle 측 특별 무장 없음(정보성). 분리 회복 후 두 번째 3003(setSpeed 복원 또는 rejoinPlan)은 선택 단계. `reasonCode=LOSS_OF_SEPARATION_RISK` 유지.
- **바람 트리거 변경 (2026-06-11)**: "데모 날씨" 버튼 및 5004 발행 제거 — 바람 트리거는 기존 기상 패널 바람 등급(serious) 선택 → 1002 발행(기존 기능)으로 대체. Vehicle 이 1002 `wind.weather` 파라미터 기반 바람장 적용, PSU 충돌 예측은 4001 스트림만 사용. 5004 는 같은 날 폐기 확정 (아래 항목), `windDemoProfiles` 도 폐기.
- **바람 구조 확정 (2026-06-11)**: "Vehicle 자체 바람 생성" 개념 폐기 — 바람은 콘솔이 1002 `wind.weather` (uamodt standalone_weather 양식: preset/season/localHour/seed/includeGust/t) 로 지정·전달하고, Vehicle 은 수신한 파라미터를 weather_core 에 투입해 바람장을 구성·적용한다. 콘솔이 유일한 바람 소스.
- **5004 폐기 (2026-06-11)**: 발행처·소비자 없음 + 1002 `wind.weather` 가 역할을 완전 대체하여 ICD 폐기 (SDK/Hub/docs 에서 제거). ICD 총 19개.
- **3003 scenarioId 폐기 (2026-06-11)**: 시나리오 타입은 2002 `scenarioId` 로만 Vehicle 에 전달 (사용자 정정) — 3003 은 순수 전술 명령, SDK 필드 제거.
