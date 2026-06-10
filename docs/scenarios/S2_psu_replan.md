# S2 — 실시간 PSU 전술 개입 (바람 → 궤적 변화 → 충돌 예방)

## 1. 개요

- **목적**: 운영자 콘솔의 **"데모 날씨" 버튼**으로 5004 Wind Effect Data 를 발행하면 두 비행체(UAM0001, UAM0002)의 궤적이 바람 영향(crossTrackDrift)으로 흔들리고, **PSU가 4001 스트림(10 Hz) + 5004 바람 데이터를 결합한 지속 궤적 예측(외삽)** 으로 분리 손실(loss of separation)을 사전 감지하여 **3003 Tactical Separation 을 직접 발행**, 충돌을 예방하는 시나리오를 검증한다. Vehicle 은 3003 액션(setSpeed / directTo)을 즉시 수행하고, Mission 은 3003 을 **수신만** 하여 plan 정합성을 추적한다. 전략 재계획 경로(2001 확장 → 3001 v2 + 3002)는 SDK 인터페이스로 유지되지만 **S2 데모 흐름에서는 사용하지 않는다**.
- **주요 참여 모듈 (역할)**
  - **IntegrationHub (SERVER)**: 메시지 포워딩 (FORWARD_RULES 기반) — 5004 → VEHICLE/VISUAL/PSU, 3003 → VEHICLE/MISSION
  - **SimulationStateModule (SIM_STATE)**: CommonTime(0003) 발생, 1001/1002/1003 소비, playState 제어
  - **VehicleModule (VEHICLE)** × 2: UAM0001, UAM0002 비행 상태 머신, 4001 송출 (10 Hz), 5004 바람 보정(WindModel) 적용, 3003 액션 즉시 수행
  - **MissionModule (MISSION)**: 초기 2001(기본) 소비, 3001 v1 발행. 이후 3003 **수신 전용** (plan 정합성 추적) — S2 트리거 구간에서 발행 없음
  - **PSU (Provider of Services for UAM)**: 4001/5004 기반 궤적 예측, 충돌 예상 기체 쌍 식별, **3003 발행 주체**
  - **OperationModule / OpsConsole (MONITORING)**: 0001/0002/4001/4101 시각화, **"데모 날씨" 버튼으로 5004 발행 주체**
  - **VisualizationModule (VISUAL)**: 3001 v1 항적, 4001 메쉬 갱신, 5004 바람 시각화, 4101 카메라 프레임 (5 Hz)
- **시나리오 길이**: 약 50 sim-minutes (T+00:00 ~ T+50:00)
  - T+00:00 ~ T+20:00: S1 정상 운항 흐름 (부팅 → 이륙 → 순항 진입)
  - T+20:00: 운영자 "데모 날씨" 버튼 → 5004 발행, 바람 영향 시작
  - T+20:00 ~ T+25:00: PSU 지속 궤적 외삽 → loss of separation 예측
  - T+25:00: PSU 3003 직접 발행, Vehicle 즉시 회피
  - T+25:00 ~ T+50:00: 분리 회복, 양 비행체 원 계획(planVersion=1)대로 정상 도착
- **트리거 메커니즘**:
  - 외부 트리거: 1003 `scenarioFileName` = `S2_psu_replan.json` 로딩
  - 시뮬레이션 시작: 1002 `playState=play`, `playbackSpeed=4`
  - 바람 트리거: OpsConsole "데모 날씨" 버튼 → 5004 `profileId=DEMO_WIND_01` 발행 (T+20:00)
  - 개입 트리거: PSU 내부 4001+5004 궤적 외삽 → 3003 `reasonCode=LOSS_OF_SEPARATION_RISK` 자동 발행 (T+25:00 sim time)

## 2. 시뮬레이션 timeline

```text
# Phase 0: 부팅 + 모듈 등록 (T+00:00 ~ T+00:10) — S1 동일
T+00:00  VEHICLE×2  → SERVER     [0001]  ModuleSettingInfo
                                          payload preview: { moduleId: "VEH-UAM0001" | "VEH-UAM0002", role: "VEHICLE" }
                                          note: 두 Air Mobility 모듈 부팅 후 자기 식별

T+00:01  VISUAL     → SERVER     [0001]  ModuleSettingInfo { moduleId: "VIZ-Unreal", role: "VISUAL" }
T+00:02  MISSION    → SERVER     [0001]  ModuleSettingInfo { moduleId: "MIS-Planner", role: "MISSION" }
T+00:03  SIM_STATE  → SERVER     [0001]  ModuleSettingInfo { moduleId: "SIM-State", role: "SIM_STATE" }
T+00:04  MONITORING → SERVER     [0001]  ModuleSettingInfo { moduleId: "OPS-Console", role: "MONITORING" }
T+00:05  PSU        → SERVER     [0001]  ModuleSettingInfo { moduleId: "EXT-PSU", role: "PSU" }
                                          note: FORWARD_RULES[0001]=[MONITORING] — 전부 Ops Console 로 forward

T+00:08  ALL        → SERVER     [0002]  ModuleStatus (1 Hz heartbeat 시작)
                                          payload preview: { moduleId, state: "READY" }

# Phase 1: Sim Mode + Scenario setup (T+00:10 ~ T+00:20)
T+00:10  User       → SERVER     [1001]  SimModeSetup
                                          payload preview: { operationMode: "traffic", traffic: { trafficScenario: "customed" } }
                                          note: 다중 비행체 traffic 모드로 부팅 → SIM_STATE 수신

T+00:15  User       → SERVER     [1003]  ScenarioSetup
                                          payload preview: { scenarioFileName: "S2_psu_replan.json", totalAircraftCount: 2, mainVehicleType: "KP2A" }
                                          note: 두 대(UAM0001, UAM0002)와 회랑 라우트 네트워크 로드 → SIM_STATE, VISUAL 수신

# Phase 2: Flight Plan Request + Scheduled Flight (T+00:20 ~ T+00:25)
T+00:20  User       → SERVER     [2001]  FlightPlanRequest (UAM0001 초기, 기본형)
                                          payload preview: { scenarioFileName: "S2_psu_replan.json", flightPlanNumber: null, reasonCode: null, triggeringEventId: null, arrivalVertiportHint: null }
                                          note: S1과 동일한 base form. MISSION이 신규 계획 생성

T+00:20  User       → SERVER     [2001]  FlightPlanRequest (UAM0002 초기, 기본형)
                                          payload preview: { scenarioFileName: "S2_psu_replan.json" }
                                          note: 두 번째 비행체용 base form 2001

T+00:23  MISSION    → SERVER     [3001]  ScheduledFlight v1 (UAM0001)
                                          payload preview: { flightPlanNumber: 1201, planVersion: 1, planStatus: "active", aircraftId: "UAM0001" }
                                          note: enRoute가 회랑 C-NORTH 통과하도록 설정 → VEHICLE, VISUAL 수신

T+00:23  MISSION    → SERVER     [3001]  ScheduledFlight v1 (UAM0002)
                                          payload preview: { flightPlanNumber: 1202, planVersion: 1, planStatus: "active", aircraftId: "UAM0002" }
                                          note: 동일 회랑 C-NORTH를 ~90초 차이로 통과 — 정상 시 분리 충분

# Phase 3: 실행 시작 (T+00:25 ~ T+00:30)
T+00:25  User       → SERVER     [1002]  SimulationSetup (play)
                                          payload preview: { playState: "play", playbackSpeed: 4, simSecondsOfDay: 32400.0, wind: { grade: "normal", gust: null } }
                                          note: SIM 시작 (KST 09:00 기준). 초기 바람은 normal

T+00:28  User       → SERVER     [2002]  DtamExecute
                                          payload preview: { simModeFileName: "S2.sim.json", scenarioFileName: "S2_psu_replan.json", flightPlanFolderName: "flights/S2/" }
                                          note: 모든 모듈에 활성 계획 폴더 통지 (MISSION, MONITORING, VEHICLE, VISUAL, SA)

T+00:30  SIM_STATE  → SERVER     [0003]  CommonTimeInfo (1 Hz)
                                          payload preview: { simSecondsOfDay: 32400.0 }
                                          note: 이후 1초마다 발행, VEHICLE/VISUAL 동기화

T+00:30  VEHICLE    → SERVER     [4001]  VehicleStatus (UAM0001, UAM0002) — 10 Hz 연속
                                          payload preview: { UAM0001: { position, gps, energy: { battery_pct: 100 } } }
                                          note: 시나리오 전 구간 지속. PSU/MONITORING/VISUAL/SA 수신. PSU 시계열 추적 시작

T+00:30  VISUAL     → SERVER     [4101]  CameraImageFrame (5 Hz)
                                          payload preview: { vehicle_id: "UAM0001", camera_name: "front", encoding: "jpeg" }
                                          note: MONITORING/SA forward

# Phase 4: 정상 운항 (T+02:00 ~ T+20:00)
T+02:00  VEHICLE    → SERVER     [4001]  (UAM0001 이륙 완료, climb out 진입)
                                          note: phase=E (climb out), departure 절차 완료

T+02:30  VEHICLE    → SERVER     [4001]  (UAM0002 이륙 완료, climb out 진입)
                                          note: UAM0001 대비 ~30초 지연 (계획 상 의도된 간격)

T+10:00  VEHICLE    → SERVER     [4001]  (양 비행체 순항 진입)
                                          note: phase=F (cruise), enRoute seq=2 진입, targetSpeed 도달

# Phase 5: 데모 날씨 → 바람 영향 (T+20:00 ~ T+25:00)
T+20:00  User(OpsConsole) → SERVER  [5004]  WindEffectData — "데모 날씨" 버튼 — TRIGGER 1
                                          payload preview: {
                                            profileId: "DEMO_WIND_01",
                                            windGrade: "serious", windPreset: "bad", windSeed: 20260610,
                                            vehicleWindEffects: [ { aircraftId: "UAM0001", crossTrackDriftM: 120.0 },
                                                                  { aircraftId: "UAM0002", crossTrackDriftM: 90.0 } ]
                                          }
                                          note: FORWARD_RULES[5004]=[VEHICLE, VISUAL, PSU]. full JSON 은 §3.1

T+20:01  VEHICLE    (internal)            5004 적용 — WindModel preset="bad" + localZone(serious) 활성화
                                          note: dynamics 바람 보정 시작 → 궤적이 횡방향으로 흔들리기 시작

T+20:05  VEHICLE    → SERVER     [4001]  (양 비행체 궤적 drift 발생)
                                          note: crossTrack 오차 누적 — UAM0001 +120 m, UAM0002 +90 m 수준으로 발산

T+20:05  PSU        (internal)            지속 궤적 예측 시작 (4001 10 Hz + 5004 보정)
                                          note: crossTrackDriftM / alongTrackDeltaMps 를 외삽 모델에 반영

T+24:30  PSU        (internal)            충돌 예상 기체 쌍 식별 — TRIGGER 2 준비
                                          note: 90 s lookahead 에서 UAM0001-UAM0002 수평 분리 < 임계치(300 m) 수렴 예측
                                                (loss of separation 예측)

# Phase 6: PSU 전술 직접 개입 (T+25:00 ~ T+25:10)
T+25:00  PSU        → SERVER     [3003]  TacticalSeparation (PSU 직접 발행) — TRIGGER 2
                                          payload preview: {
                                            commandId: "TMP-PSU-UAM0001-20260610-0001",
                                            aircraftId: "UAM0001",
                                            reasonCode: "LOSS_OF_SEPARATION_RISK",
                                            actions: [ { type: "setSpeed", targetSpeed: 45.0 },
                                                       { type: "directTo", targetLLAs: [...] } ]
                                          }
                                          note: FORWARD_RULES[3003]=[VEHICLE, MISSION] — Mission 도 수신 (수신만).
                                                2001 확장 / 3001 v2 / 3002 는 발행되지 않음. full JSON 은 §3.2

T+25:01  VEHICLE    → SERVER     [4001]  (UAM0001 즉시 액션 수행)
                                          note: setSpeed 45.0 적용 후 directTo 진입점으로 헤딩 전환.
                                                plan 은 그대로 planVersion=1 (전술 이탈 상태)

T+25:01  MISSION    (internal)            3003 수신 — on_tactical_separation
                                          note: fpn=1201 에 "tactical deviation active (TMP-PSU-...)" 마킹.
                                                plan 정합성 추적만 수행, 어떤 메시지도 발행하지 않음

T+25:10  PSU        (internal)            재평가
                                          note: 분리 거리 회복 확인 (>= 300 m), 추가 3003 없음

# Phase 7: 분리 회복 → 정상 도착 (T+30:00 ~ T+50:00)
T+30:00  VEHICLE    → SERVER     [4001]  (UAM0001 directTo 종료, 원 enRoute 복귀)
                                          note: phase=F (cruise), planVersion=1 의 기존 세그먼트로 재합류

T+32:00  VEHICLE    → SERVER     [4001]  (UAM0002 기존 회랑 정상 통과)
                                          note: UAM0002 는 어떤 전술 명령도 받지 않음 — 계획(1202) 불변

T+45:00  VEHICLE    → SERVER     [4001]  (UAM0001 도착 접근, arrival transition)
                                          note: phase=G (arrival transition); 도착 vertiport 는 v1 그대로 GIMPO_VP

T+47:30  VEHICLE    → SERVER     [4001]  (UAM0002 도착 접근, arrival transition)
                                          note: phase=G (arrival transition)

T+49:30  VEHICLE    → SERVER     [4001]  (UAM0001 착륙 완료)
                                          note: phase=K (gate-in taxi), battery_pct ≈ 35%

T+50:00  VEHICLE    → SERVER     [4001]  (UAM0002 착륙 완료)
                                          note: 시나리오 종료 — User 1002 playState="pause"
```

## 3. 메시지별 상세 payload

### 3.1 5004 WindEffectData — "데모 날씨" 버튼 (T+20:00)

> OperationModule(운영자 콘솔)이 보유한 데모 바람 프로파일(`DEMO_WIND_01`)을 그대로 wire 에 실어 발행.
> `windGrade` 는 1002 `wind.grade` 와 동일 enum, `windPreset`/`localZone.preset` 은 VehicleModule WindModel 프리셋과 1:1.
> UAM0002 는 `localZone` 없이 전역 프로파일만 적용되는 예시 (optional 필드).

```json
{
  "messageId": "5004",
  "messageName": "wind_effect_data",
  "timestamp": "2026-06-10T09:20:00.000+09:00",
  "profileId": "DEMO_WIND_01",
  "windGrade": "serious",
  "windPreset": "bad",
  "windSeed": 20260610,
  "vehicleWindEffects": [
    {
      "aircraftId": "UAM0001",
      "windSpeedMps": 7.5,
      "windDirFromDeg": 270.0,
      "gustFactor": 1.3,
      "crossTrackDriftM": 120.0,
      "alongTrackDeltaMps": -2.0,
      "localZone": {
        "lat": 37.53,
        "lon": 126.98,
        "radiusM": 3000.0,
        "preset": "serious"
      }
    },
    {
      "aircraftId": "UAM0002",
      "windSpeedMps": 6.8,
      "windDirFromDeg": 265.0,
      "gustFactor": 1.25,
      "crossTrackDriftM": 90.0,
      "alongTrackDeltaMps": 1.5,
      "localZone": null
    }
  ]
}
```

**5004 payload 필드**

| 필드 | 타입 | 단위 | 범위 / 형식 | 설명 |
|---|---|---:|---|---|
| `timestamp` | string | - | ISO-8601 | 발행 시각 |
| `profileId` | string | - | 자유 형식 | 데모 바람 프로파일 식별자 |
| `windGrade` | string | - | `normal`, `warning`, `serious` | 전역 바람 등급 (1002 `wind.grade` 동일 enum) |
| `windPreset` | string | - | `good`, `fair`, `bad`, `serious` | WindModel 강도 프리셋 |
| `windSeed` | int | - | `>= 0` | 재현성 시드 (0 = 모듈 기본값) |
| `vehicleWindEffects` | array | - | 1개 이상 | 기체별 바람 영향 목록 |
| `vehicleWindEffects[].aircraftId` | string | - | `^[A-Z]{2,8}\d{4}$` | 대상 기체 |
| `vehicleWindEffects[].windSpeedMps` | float | m/s | `>= 0` | 기체 위치 기준 풍속 |
| `vehicleWindEffects[].windDirFromDeg` | float | deg | `0 ~ 360` | 풍향 (불어오는 방향, 0 = 북) |
| `vehicleWindEffects[].gustFactor` | float | - | `>= 1.0` | 거스트 배율 |
| `vehicleWindEffects[].crossTrackDriftM` | float | m | - | 예상 횡방향 이탈량 |
| `vehicleWindEffects[].alongTrackDeltaMps` | float | m/s | - | 종방향 속도 영향 (+순풍 / -역풍) |
| `vehicleWindEffects[].localZone` | object | - | optional | 국지 바람 영역 (`WindModel.add_local_zone` 1:1) |
| `vehicleWindEffects[].localZone.lat` | float | deg | `-90 ~ 90` | 영역 중심 위도 |
| `vehicleWindEffects[].localZone.lon` | float | deg | `-180 ~ 180` | 영역 중심 경도 |
| `vehicleWindEffects[].localZone.radiusM` | float | m | `> 0` | 영역 반경 |
| `vehicleWindEffects[].localZone.preset` | string | - | `good`, `fair`, `bad`, `serious` | 영역 내 바람 강도 |

### 3.2 3003 TacticalSeparation — PSU 직접 발행 (T+25:00)

> **발행 주체가 MISSION 이 아니라 PSU** 인 것이 S2 의 핵심 (SDK 3003 direction: `mission|psu->server`).
> `commandId` 는 `TMP-PSU-{aircraftId}-{YYYYMMDD}-{SEQ}` 포맷.
> 액션 순서: ① `setSpeed` 로 즉시 감속 → ② `directTo` 로 분리 확보 경유점 2개를 거쳐 원 경로 복귀.
> FORWARD_RULES[3003]=[VEHICLE, MISSION] — **MISSION 은 수신만** 하여 plan 정합성을 추적하고, 어떤 재계획 메시지도 발행하지 않는다.

```json
{
  "messageId": "3003",
  "messageName": "tactical_separation",
  "timestamp": "2026-06-10T09:25:00.250+09:00",
  "commandId": "TMP-PSU-UAM0001-20260610-0001",
  "aircraftId": "UAM0001",
  "reasonCode": "LOSS_OF_SEPARATION_RISK",
  "actions": [
    {
      "type": "setSpeed",
      "targetSpeed": 45.0
    },
    {
      "type": "directTo",
      "targetLLAs": [
        { "lat": 37.5480, "lon": 126.9900, "alt": 395.0, "targetSpeed": 45.0 },
        { "lat": 37.5550, "lon": 126.9300, "alt": 365.0, "targetSpeed": 55.0 }
      ]
    }
  ]
}
```

## 4. 모듈별 책임

- **VehicleModule (UAM0001, UAM0002)**:
  - 10 Hz로 4001 송출 (position/gps/energy/navigation).
  - **5004 수신 시 바람 적용**: `windPreset` 을 WindModel preset 으로, `localZone` 을 `WindModel.add_local_zone` 으로 적용 → dynamics 바람 보정으로 궤적 drift 발생.
  - **3003 수신 시 액션 즉시 수행**: setSpeed 로 감속 후 directTo `targetLLAs` 순서대로 추종, 완료 후 원 enRoute(planVersion=1) 재합류.
  - 3001 v1 경로 자체는 시나리오 전 구간 불변 — 전술 이탈만 발생.
- **MissionModule**:
  - 초기 2001 (base form) × 2 → 1201, 1202 신규 계획 생성, 3001 v1 발행.
  - **3003 수신 (`on_tactical_separation`) — 수신 전용**: 대상 fpn(1201)에 전술 이탈 활성(commandId, reasonCode) 마킹, 자기 plan 과의 정합성 추적.
  - **S2 에서 3001 v2 / 3002 / 추가 3003 을 발행하지 않음** — 전략 재계획 경로(2001 확장)는 SDK 인터페이스로 유지되나 본 시나리오에서 미사용.
- **OperationModule (Monitoring / OpsConsole)**:
  - 0001/0002 로 모듈 상태 시각화, 4001/4101 실시간 표시.
  - **"데모 날씨" 버튼 → 5004 발행 주체**: 보유 데모 바람 프로파일(`DEMO_WIND_01`)을 wire 로 배포.
  - PSU 3003 발생 시 알림 배너 (commandId, reasonCode 표시).
- **VisualizationModule**:
  - 1003 으로 vertiport/회랑 로드, 3001 v1 항적선 렌더링, 4001 기반 비행체 메쉬 갱신.
  - 5004 수신 시 기체별 바람 영향(풍향/풍속/localZone) 시각화.
  - 4101 카메라 프레임 5 Hz 발행.
- **PSU (ExtensionModule)**:
  - **궤적 예측 + 3003 발행 주체** (S2 의 의사결정 모듈).
  - 4001 두 스트림(10 Hz)을 시계열 외삽하되, 5004 의 `crossTrackDriftM` / `alongTrackDeltaMps` 를 예측 모델에 반영하여 바람 영향 하의 미래 위치를 보정.
  - 90 s lookahead 에서 기체 쌍의 수평 분리가 임계치(300 m) 미만으로 수렴하면 loss of separation 예측 → 충돌 예상 쌍 식별.
  - 3003 직접 발행: `commandId=TMP-PSU-{aircraftId}-{YYYYMMDD}-{SEQ}`, `reasonCode=LOSS_OF_SEPARATION_RISK`, actions 는 setSpeed/directTo/hold 중 상황에 맞게 구성.
  - **2001 확장(전략 재계획 요청)은 발행하지 않음** — S2 는 전술 직접 개입만 사용.
- **SimStateModule**: 1001/1002/1003 소비, 0003 CommonTime 1 Hz emit.
- **(UAO/VPO는 본 시나리오에서 비활성)** — S2 는 PSU 단독 전술 개입.

## 5. 검증 가능한 결과 (acceptance criteria)

- `S2_psu_replan.json` 로드 시 `totalAircraftCount=2`로 인식되며 UAM0001/UAM0002 두 대가 spawn된다.
- T+02:30 이전에 두 비행체 모두 이륙 (4001 `phase` 변화로 확인).
- T+20:00 에 **5004 가 정확히 1회 발행**되며 다음을 만족:
  - `profileId == "DEMO_WIND_01"`, `windGrade == "serious"`, `windPreset == "bad"`
  - `vehicleWindEffects` 에 UAM0001/UAM0002 두 항목 포함
  - FORWARD_RULES 에 따라 **VEHICLE, VISUAL, PSU** 세 모듈로 모두 도달 (IntegrationHub 로그 확인)
- 5004 적용 후 양 비행체의 4001 궤적에 횡방향 drift 가 관측된다 (UAM0001 ≈ 120 m, UAM0002 ≈ 90 m 스케일).
- T+20:05 ~ T+25:00 사이에 PSU 내부 외삽이 loss of separation 을 예측한다 (PSU 로그에 conflict pair `UAM0001-UAM0002` 기록).
- **PSU 가 3003 을 1회 이상 발행**하며 다음을 만족:
  - `commandId` 가 `TMP-PSU-` prefix
  - `reasonCode == "LOSS_OF_SEPARATION_RISK"`
  - `actions[0].type == "setSpeed"`, `actions[1].type == "directTo"` (또는 상황에 따라 `hold`)
  - FORWARD_RULES 에 따라 **VEHICLE 과 MISSION 양쪽** 으로 전달
- VEHICLE 은 3003 수신 후 1초 이내에 setSpeed/directTo 를 반영 (4001 의 speed/heading 변화로 확인).
- MISSION 은 3003 을 수신해 fpn=1201 에 전술 이탈을 마킹하되 **어떤 메시지도 발행하지 않는다**.
- **3001 v2 발행 0건, 3002 발행 0건, 2001(확장) 발행 0건** — 1201/1202 모두 시나리오 전 구간 `planVersion == 1` 유지.
- T+25:10 이후 **두 기체의 수평 분리 거리가 최소 분리 임계값(300 m) 이상으로 유지**된다.
- 양 비행체가 T+50:00 이전에 각자의 도착 vertiport 에 land 완료 (4001 `phase=K` gate-in taxi).

## 6. ICD payload 예시

### 6.1 `1003` ScenarioSetup payload 예시

`scenarioFileName: "S2_psu_replan.json"` 의 내용 예시. `Msg1003_ScenarioSetup` 스키마 기준.

```json
{
  "messageId": "1003",
  "messageName": "scenario_setup",
  "timestamp": "2026-06-10T08:59:00.000+09:00",
  "scenarioFileName": "S2_psu_replan.json",
  "totalAircraftCount": 2,
  "mainVehicleType": "KP2A",
  "operationTime": {
    "startTime": "2026-06-10T09:00:00+09:00",
    "endTime":   "2026-06-10T09:50:00+09:00"
  },
  "vertiports": [
    {
      "name": "JAMSIL_VP",
      "vertiportClass": "hub",
      "lat": 37.5145,
      "lon": 127.1020,
      "angleDegrees": 0.0
    },
    {
      "name": "GIMPO_VP",
      "vertiportClass": "port",
      "lat": 37.5630,
      "lon": 126.8010,
      "angleDegrees": 90.0
    },
    {
      "name": "YONGSAN_VP",
      "vertiportClass": "port",
      "lat": 37.5300,
      "lon": 126.9650,
      "angleDegrees": 45.0
    }
  ],
  "routeNetwork": {
    "waypoints": [
      {
        "waypointId": "WP-JAM-EXIT",
        "waypointName": "Jamsil Exit",
        "lat": 37.5200,
        "lon": 127.0800,
        "altFt": 1200,
        "links": ["WP-C-NORTH-IN"]
      },
      {
        "waypointId": "WP-C-NORTH-IN",
        "waypointName": "Corridor North Entry",
        "lat": 37.5400,
        "lon": 127.0200,
        "altFt": 1200,
        "links": ["WP-C-NORTH-OUT"]
      },
      {
        "waypointId": "WP-C-NORTH-OUT",
        "waypointName": "Corridor North Exit",
        "lat": 37.5550,
        "lon": 126.9300,
        "altFt": 1200,
        "links": ["WP-GMP-IN"]
      },
      {
        "waypointId": "WP-C-SOUTH-IN",
        "waypointName": "Corridor South Entry (alt)",
        "lat": 37.5350,
        "lon": 127.0200,
        "altFt": 1200,
        "links": ["WP-C-SOUTH-OUT"]
      },
      {
        "waypointId": "WP-C-SOUTH-OUT",
        "waypointName": "Corridor South Exit (alt)",
        "lat": 37.5520,
        "lon": 126.9750,
        "altFt": 1200,
        "links": ["WP-GMP-IN"]
      },
      {
        "waypointId": "WP-GMP-IN",
        "waypointName": "Gimpo Approach",
        "lat": 37.5620,
        "lon": 126.8400,
        "altFt": 1200,
        "links": ["WP-GMP-FINAL"]
      },
      {
        "waypointId": "WP-GMP-FINAL",
        "waypointName": "Gimpo Final",
        "lat": 37.5630,
        "lon": 126.8010,
        "altFt": 200,
        "links": []
      }
    ]
  }
}
```

비고:
- 회랑 C-NORTH (`WP-C-NORTH-IN → WP-C-NORTH-OUT`)를 두 비행체가 시간차를 두고 통과 — 바람 drift 가 이 간격을 무너뜨리는 것이 충돌 시드.
- C-SOUTH 회랑은 routeNetwork 에 남아 있으나 **S2 에서는 사용되지 않음** (전략 재계획 미발생). PSU 의 directTo 가 일시적으로 C-SOUTH 측 공역을 경유할 수 있다.

### 6.2 `1001` SimModeSetup — traffic 모드

S2 는 다중 비행체 traffic 모드. `trafficScenario="customed"` 인 경우 기체 목록(UAM0001,
UAM0002)과 출발/도착 정보는 `scenarioFileName` 이 가리키는 시뮬레이터 입력 파일(§6.3)에서
로드된다. `Msg1001` 의 `singleFlight` 는 사용하지 않는다.

```json
{
  "timestamp": "2026-06-10T08:59:30.000+09:00",
  "operationMode": "traffic",
  "traffic": {
    "trafficScenario": "customed"
  }
}
```

### 6.3 시뮬레이터-side 보조 데이터 (SDK ICD 외)

`scenarioFileName` 이 가리키는 시뮬레이터 입력 파일에는 ICD payload 외 보조 데이터가
들어간다. 이는 모듈 내부 구현 영역이고 wire 송수신되지 않는다. S2 에서는 **wind demo
profile** 이 추가된다 — OpsConsole "데모 날씨" 버튼이 이 프로파일을 읽어 5004 wire 로
변환·발행한다.

```json
{
  "traffic": {
    "trafficScenario": "customed",
    "aircraft": ["UAM0001", "UAM0002"]
  },
  "initialBatteryPct": 100.0,
  "separation": {
    "minHorizontalM": 300.0,
    "lookaheadSec": 90
  },
  "windDemoProfiles": [
    {
      "profileId": "DEMO_WIND_01",
      "windGrade": "serious",
      "windPreset": "bad",
      "windSeed": 20260610,
      "vehicleWindEffects": [
        {
          "aircraftId": "UAM0001",
          "windSpeedMps": 7.5,
          "windDirFromDeg": 270.0,
          "gustFactor": 1.3,
          "crossTrackDriftM": 120.0,
          "alongTrackDeltaMps": -2.0,
          "localZone": { "lat": 37.53, "lon": 126.98, "radiusM": 3000.0, "preset": "serious" }
        },
        {
          "aircraftId": "UAM0002",
          "windSpeedMps": 6.8,
          "windDirFromDeg": 265.0,
          "gustFactor": 1.25,
          "crossTrackDriftM": 90.0,
          "alongTrackDeltaMps": 1.5
        }
      ]
    }
  ]
}
```

> `separation.minHorizontalM` / `lookaheadSec` 은 PSU 의 충돌 예측 파라미터로, §5 의
> 분리 임계값(300 m)과 1:1 대응. `windDemoProfiles[0]` 는 §3.1 의 5004 wire payload 와
> 필드 단위로 동일하며, `windSeed` 가 0 이 아니므로 동일 시드로 바람 효과가 재현된다.

## 변경 이력

- **구 흐름 (전략 재계획)**: PSU 가 충돌을 감지하면 2001 확장(TRAFFIC_CONFLICT)을 발행하고 Mission 이 3001 v2 + 3002 + 3003 을 발행하는 전략 재계획 경로였다.
- **신 흐름 (PSU 전술 직접 개입)**: 데모에서 보여주려는 핵심이 "PSU 의 실시간 감시·즉시 개입" 이므로, Mission 을 경유하는 다단계 재계획 대신 PSU 가 3003 을 직접 발행해 반응 시간을 줄이고 책임 경계(PSU=전술, Mission=전략)를 명확히 드러내도록 변경했다. 전략 재계획 경로(2001 확장)는 SDK 인터페이스로 유지된다.
