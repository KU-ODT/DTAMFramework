# S2 — 실시간 PSU 재계획 (회랑 충돌 회피)

## 1. 개요

- **목적**: 동일 회랑 구간을 시간차 없이 통과하려는 두 비행체(UAM0001, UAM0002)에 대해 PSU가 4001 스트림을 실시간 분석하여 분리 손실(loss of separation)을 사전 감지하고, MissionModule에 재계획(2001 TRAFFIC_CONFLICT)을 요청하여 회랑 충돌을 회피하는 시나리오를 검증한다. 기존 S1(정상 운항) 흐름 위에 PSU 트리거를 얹어 **3001 v2 / 3002 routeUpdate** 발행 경로가 정상 작동하는지 end-to-end로 확인한다.
- **주요 참여 모듈 (역할)**
  - **IntegrationHub (SERVER)**: 메시지 포워딩 (FORWARD_RULES 기반)
  - **SimulationStateModule (SIM_STATE)**: CommonTime(0003) 발생, 1001/1002/1003 소비, playState 제어
  - **VehicleModule (VEHICLE)** × 2: UAM0001, UAM0002 비행 상태 머신, 4001 송출 (10 Hz)
  - **MissionModule (MISSION)**: 2001 소비, 3001/3002/3003 발행 (재계획 엔진)
  - **PSU (Provider of Services for UAM)**: 4001/4002 모니터링, TRAFFIC_CONFLICT 사전 감지, 2001 발행
  - **OperationModule / OpsConsole (MONITORING)**: 0001/0002/4001/4002 시각화
  - **VisualizationModule (VISUAL)**: 3001/3002/3003 반영, 회랑 경로 갱신
- **시나리오 길이**: 약 50 sim-minutes (T+00:00 ~ T+50:00)
  - T+00:00 ~ T+25:00: S1 정상 운항 (이륙 → 순항 진입)
  - T+25:00: PSU TRAFFIC_CONFLICT 감지 및 재계획 트리거
  - T+25:00 ~ T+50:00: 재계획된 enRoute로 양 비행체 회피 및 정상 도착
- **트리거 메커니즘**:
  - 외부 트리거: 1003 `scenarioFileName` = `S2_psu_replan.json` 로딩
  - 시뮬레이션 시작: 1002 `playState=play`, `playbackSpeed=4`
  - 재계획 트리거: PSU 내부 4001 분석 로직 → 2001 `reasonCode=TRAFFIC_CONFLICT` 자동 발행 (T+25:00 sim time)

## 2. 시뮬레이션 timeline

```text
T+00:00  User       → SERVER     [1001]  SimModeSetup
                                          payload preview: { operationMode: "traffic", traffic: { trafficScenario: "customed" } }
                                          note: 다중 비행체 traffic 모드로 부팅

T+00:00  User       → SERVER     [1003]  ScenarioSetup
                                          payload preview: { scenarioFileName: "S2_psu_replan.json", totalAircraftCount: 2, mainVehicleType: "KP2A" }
                                          note: 두 대(UAM0001, UAM0002)와 회랑 라우트 네트워크 로드 → SIM_STATE, VISUAL 수신

T+00:01  User       → SERVER     [2001]  FlightPlanRequest (UAM0001 초기)
                                          payload preview: { scenarioFileName: "S2_psu_replan.json", flightPlanNumber: null, reasonCode: null, triggeringEventId: null, arrivalVertiportHint: null }
                                          note: S1과 동일한 base form. MISSION이 신규 계획 생성

T+00:01  User       → SERVER     [2001]  FlightPlanRequest (UAM0002 초기)
                                          payload preview: { scenarioFileName: "S2_psu_replan.json" }
                                          note: 두 번째 비행체용 base form 2001

T+00:02  MISSION    → SERVER     [3001]  ScheduledFlight v1 (UAM0001)
                                          payload preview: { flightPlanNumber: 1201, planVersion: 1, planStatus: "active", aircraftId: "UAM0001" }
                                          note: enRoute가 회랑 C-NORTH 통과하도록 설정 → VEHICLE, VISUAL 수신

T+00:02  MISSION    → SERVER     [3001]  ScheduledFlight v1 (UAM0002)
                                          payload preview: { flightPlanNumber: 1202, planVersion: 1, planStatus: "active", aircraftId: "UAM0002" }
                                          note: 동일 회랑 C-NORTH를 ~90초 차이로 통과 → 경합 시드

T+00:03  User       → SERVER     [2002]  DtamExecute
                                          payload preview: { simModeFileName: "S2.sim.json", scenarioFileName: "S2_psu_replan.json", flightPlanFolderName: "flights/S2/" }
                                          note: 모든 모듈에 활성 계획 폴더 통지 (MISSION, MONITORING, VEHICLE, VISUAL, SA)

T+00:03  User       → SERVER     [1002]  SimulationSetup
                                          payload preview: { playState: "play", playbackSpeed: 4, simSecondsOfDay: 32400.0 }
                                          note: SIM 시작 (KST 09:00 기준)

T+00:04  SIM_STATE  → SERVER     [0003]  CommonTimeInfo (1 Hz)
                                          payload preview: { simSecondsOfDay: 32400.0 }
                                          note: 이후 1초마다 발행, VEHICLE/VISUAL 동기화

T+00:05  VEHICLE    → SERVER     [4001]  VehicleStatus (UAM0001) — 10 Hz 연속
                                          payload preview: { UAM0001: { position, gps, energy: { battery_pct: 100 } } }
                                          note: 이후 시나리오 전 구간 지속. PSU/MONITORING/VISUAL/SA 수신

T+00:05  VEHICLE    → SERVER     [4001]  VehicleStatus (UAM0002) — 10 Hz 연속
                                          payload preview: { UAM0002: { position, gps, energy: { battery_pct: 100 } } }
                                          note: PSU가 두 스트림을 시계열 비교 시작

T+02:00  VEHICLE    → SERVER     [4001]  (UAM0001 이륙 완료, climb out 진입)
                                          note: phase=E (climb out), departure 절차 완료

T+02:30  VEHICLE    → SERVER     [4001]  (UAM0002 이륙 완료, climb out 진입)
                                          note: UAM0001 대비 ~30초 지연 (계획 상 의도된 간격)

T+10:00  VEHICLE    → SERVER     [4001]  (양 비행체 순항 진입)
                                          note: phase=F (cruise), enRoute seq=2 진입, targetSpeed 도달

T+20:00  PSU        (internal)            4001 시계열 외삽 분석
                                          note: 두 비행체의 회랑 진입 시각 차이가 분리 최소치(예: 60s) 미만으로 수렴 예측

T+25:00  PSU        → SERVER     [2001]  FlightPlanRequest (extended, TRAFFIC_CONFLICT)
                                          payload preview: {
                                            scenarioFileName: "S2_psu_replan.json",
                                            flightPlanNumber: 1201,
                                            reasonCode: "TRAFFIC_CONFLICT",
                                            triggeringEventId: "PSU-CONFLICT-1201-20260610-0001",
                                            arrivalVertiportHint: null
                                          }
                                          note: UAM0001 계획을 재라우팅 대상으로 지정. 4개 옵셔널 중 hint만 null (도착지 변경 없음)

T+25:01  MISSION    → SERVER     [3001]  ScheduledFlight v2 (UAM0001 재계획)
                                          payload preview: { flightPlanNumber: 1201, planVersion: 2, planStatus: "active", arrival.vertiport: "GIMPO_VP" (불변), enRoute: [신규 우회 세그먼트] }
                                          note: planVersion=2. v1은 자동으로 superseded 처리. VEHICLE/VISUAL 수신 → 경로 교체

T+25:01  MISSION    → SERVER     [3002]  StrategicSeparation (routeUpdate)
                                          payload preview: {
                                            commandId: "STRAT-1201-V2-...",
                                            flightPlanNumber: 1201,
                                            planVersion: 2,
                                            aircraftId: "UAM0001",
                                            modificationType: "routeUpdate",
                                            reasonCode: "CORRIDOR_BLOCKED",
                                            modifyScope: "enRouteOnly"
                                          }
                                          note: VEHICLE에만 전달 (FORWARD_RULES 기준). 경로 갱신 의도를 명시

T+25:02  MISSION    → SERVER     [3003]  TacticalSeparation (optional immediate directTo)
                                          payload preview: {
                                            commandId: "TAC-1201-V2-DIRECTTO-...",
                                            aircraftId: "UAM0001",
                                            reasonCode: "LOSS_OF_SEPARATION_RISK",
                                            actions: [ { type: "directTo", targetLLAs: [ { lat, lon, alt, targetSpeed } ] } ]
                                          }
                                          note: 즉시 회피 방향 지시. v2 경로의 첫 진입점으로 directTo. VEHICLE 수신

T+25:03  VEHICLE    → SERVER     [4001]  (UAM0001 경로 전환 반영)
                                          note: navigation.activePlanVersion=2, currentWaypointId 변경

T+25:10  PSU        (internal)            재평가
                                          note: 분리 거리 회복 확인, 추가 트리거 없음

T+30:00  VEHICLE    → SERVER     [4001]  (UAM0001 우회 회랑 통과)
                                          note: phase=F (cruise) seq=4 (v2의 신규 세그먼트)

T+32:00  VEHICLE    → SERVER     [4001]  (UAM0002 기존 회랑 정상 통과)
                                          note: UAM0002 계획(1202)은 변경 없음 — planVersion=1 유지

T+45:00  VEHICLE    → SERVER     [4001]  (UAM0001 도착 접근, arrival transition)
                                          note: phase=G (arrival transition); 도착 vertiport는 v1과 동일 (arrivalOnly가 아닌 enRouteOnly 수정이었음)

T+47:30  VEHICLE    → SERVER     [4001]  (UAM0002 도착 접근, arrival transition)
                                          note: phase=G (arrival transition)

T+49:30  VEHICLE    → SERVER     [4001]  (UAM0001 착륙 완료)
                                          note: phase=K (gate-in taxi), battery_pct ≈ 35%

T+50:00  VEHICLE    → SERVER     [4001]  (UAM0002 착륙 완료)
                                          note: 시나리오 종료
```

## 3. 메시지별 상세 payload

### 3.1 Extended 2001 — PSU TRAFFIC_CONFLICT 재계획 요청

> 4개 옵셔널 필드 (`flightPlanNumber`, `reasonCode`, `triggeringEventId`, `arrivalVertiportHint`) 중 **3개가 채워지고 `arrivalVertiportHint`만 null**.
> 이유: PSU는 회랑 우회(경로 조정)만 요구할 뿐, 도착 vertiport 변경은 의도하지 않음. 도착지 hint를 null로 두면 MISSION이 arrival을 보존한 채 enRoute만 재계산한다.

```json
{
  "messageId": "2001",
  "messageName": "flight_plan_request",
  "timestamp": "2026-06-10T09:25:00.000+09:00",
  "scenarioFileName": "S2_psu_replan.json",
  "flightPlanNumber": 1201,
  "reasonCode": "TRAFFIC_CONFLICT",
  "triggeringEventId": "PSU-CONFLICT-1201-20260610-0001",
  "arrivalVertiportHint": null
}
```

### 3.2 3001 v2 — ScheduledFlight 재계획 결과 (UAM0001)

> `planVersion=2`, `arrival.vertiport`는 v1과 동일 (`GIMPO_VP`), `enRoute`만 우회 회랑으로 교체됨.
> v1 계획은 MISSION 내부 상태에서 `planStatus="superseded"`로 마킹된다 (별도 3001 superseded 브로드캐스트 가능, 본 시나리오에서는 생략 가능).

```json
{
  "messageId": "3001",
  "messageName": "scheduled_flight",
  "flightPlanNumber": 1201,
  "planVersion": 2,
  "planStatus": "active",
  "aircraftId": "UAM0001",
  "departure": {
    "vertiport": "JAMSIL_VP",
    "std": "2026-06-10T09:00:00+09:00",
    "depGateNumber": "G1",
    "eobt": "2026-06-10T08:58:00+09:00",
    "depFatoNumber": "F1",
    "etot": "2026-06-10T09:01:30+09:00"
  },
  "arrival": {
    "vertiport": "GIMPO_VP",
    "sta": "2026-06-10T09:50:00+09:00",
    "arrGateNumber": "G2",
    "eibt": "2026-06-10T09:51:00+09:00",
    "arrFatoNumber": "F2",
    "eldt": "2026-06-10T09:49:30+09:00"
  },
  "enRoute": [
    {
      "seq": 1,
      "phase": "E",
      "targetSpeed": 35.0,
      "startLLA": { "lat": 37.5145, "lon": 127.1020, "alt": 50.0 },
      "endLLA":   { "lat": 37.5200, "lon": 127.0800, "alt": 365.0 }
    },
    {
      "seq": 2,
      "phase": "F",
      "targetSpeed": 55.0,
      "startLLA": { "lat": 37.5200, "lon": 127.0800, "alt": 365.0 },
      "endLLA":   { "lat": 37.5350, "lon": 127.0200, "alt": 365.0 }
    },
    {
      "seq": 3,
      "phase": "H",
      "targetSpeed": 55.0,
      "startLLA": { "lat": 37.5350, "lon": 127.0200, "alt": 365.0 },
      "endLLA":   { "lat": 37.5520, "lon": 126.9750, "alt": 365.0 },
      "turnDirection": "CW",
      "centerLLA":   { "lat": 37.5400, "lon": 126.9900, "alt": 365.0 }
    },
    {
      "seq": 4,
      "phase": "F",
      "targetSpeed": 55.0,
      "startLLA": { "lat": 37.5520, "lon": 126.9750, "alt": 365.0 },
      "endLLA":   { "lat": 37.5620, "lon": 126.8400, "alt": 365.0 }
    },
    {
      "seq": 5,
      "phase": "I",
      "targetSpeed": 30.0,
      "startLLA": { "lat": 37.5620, "lon": 126.8400, "alt": 365.0 },
      "endLLA":   { "lat": 37.5630, "lon": 126.8010, "alt": 50.0 }
    }
  ]
}
```

### 3.3 3002 — StrategicSeparation (routeUpdate / CORRIDOR_BLOCKED / enRouteOnly)

```json
{
  "messageId": "3002",
  "messageName": "strategic_separation",
  "timestamp": "2026-06-10T09:25:01.200+09:00",
  "commandId": "STRAT-1201-V2-20260610-0001",
  "flightPlanNumber": 1201,
  "planVersion": 2,
  "aircraftId": "UAM0001",
  "modificationType": "routeUpdate",
  "reasonCode": "CORRIDOR_BLOCKED",
  "modifyScope": "enRouteOnly"
}
```

## 4. 모듈별 책임

- **VehicleModule (UAM0001, UAM0002)**:
  - 10 Hz로 4001 송출 (position/gps/energy/navigation).
  - 3001 v2 수신 시 `navigation.activePlanVersion`을 2로 갱신하고 새 enRoute에 따라 추종.
  - 3003 directTo 액션을 즉시 적용하여 v2 경로 진입점으로 헤딩 조정.
  - 3002는 정보성으로 수신하여 (commandId, planVersion)을 로그/내부 상태에 기록.
- **MissionModule**:
  - 초기 2001 (base form) → 1201, 1202 신규 계획 생성, 3001 v1 발행.
  - PSU의 extended 2001 (TRAFFIC_CONFLICT, fpn=1201) 수신 → enRoute 재계산.
  - 3001 v2 (planVersion=2, arrival 불변, enRoute 갱신), 3002 (routeUpdate / CORRIDOR_BLOCKED / enRouteOnly / planVersion=2), 3003 (LOSS_OF_SEPARATION_RISK / directTo) 순차 발행.
  - v1 계획은 내부적으로 `superseded`로 마킹.
- **OperationModule (Monitoring / OpsConsole)**:
  - 0001/0002로 모듈 상태 시각화.
  - 4001 두 비행체 trajectory 실시간 표시.
  - PSU 트리거 발생 시 알림 배너 (triggeringEventId, reasonCode 표시).
  - 3001 v2 수신 후 회랑 색상/라벨 변경.
- **VisualizationModule**:
  - 1003으로 vertiport/회랑 로드.
  - 3001 v1/v2를 받아 항적선(predicted track) 렌더링 — v2 수신 시 기존 항적선 교체.
  - 4001 기반 비행체 메쉬 갱신.
- **PSU (ExtensionModule)**:
  - 4001 두 스트림을 시계열로 외삽 (예: 5초 lookahead window의 90s 후 위치 예측).
  - 회랑 진입 ETA 간격이 분리 최소치 미만으로 예상되면 `TRAFFIC_CONFLICT` 이벤트 생성 → 2001 발행.
  - `triggeringEventId`는 `PSU-CONFLICT-{flightPlanNumber}-{YYYYMMDD}-{SEQ}` 포맷.
  - `arrivalVertiportHint`는 도착지 변경이 필요한 경우에만 채움 (S2에서는 null).
  - 4002 priority event list도 함께 모니터링하나, 본 시나리오는 4002 발생 없음.
- **(UAO/VPO는 본 시나리오에서 비활성)** — 외부 UAO 시뮬레이션이 있다면 PSU와 동일 채널로 2001 발행 가능하나, S2는 PSU 단독 트리거.

## 5. 검증 가능한 결과 (acceptance criteria)

- `S2_psu_replan.json` 로드 시 `totalAircraftCount=2`로 인식되며 UAM0001/UAM0002 두 대가 spawn된다.
- T+02:00 이전에 두 비행체 모두 이륙 (4001 `phase` 변화로 확인).
- T+20:00 ~ T+25:00 사이에 PSU 내부 외삽이 충돌 위험을 감지한다 (PSU 로그에 conflict prediction 기록).
- T+25:00에 PSU가 정확히 **하나의** extended 2001을 발행하며 다음을 만족:
  - `flightPlanNumber == 1201` (UAM0001 계획)
  - `reasonCode == "TRAFFIC_CONFLICT"`
  - `triggeringEventId`가 `PSU-CONFLICT-1201-` prefix
  - `arrivalVertiportHint == null`
- MissionModule이 1초 이내에 3001 v2를 발행, `planVersion == 2`, `planStatus == "active"`, `arrival.vertiport == "GIMPO_VP"` (v1과 동일), `enRoute`는 v1과 다른 세그먼트 리스트.
- 동시에 3002가 발행되며 `modificationType == "routeUpdate"`, `reasonCode == "CORRIDOR_BLOCKED"`, `modifyScope == "enRouteOnly"`, `planVersion == 2`.
- (선택) 3003가 발행되며 `actions[0].type == "directTo"`, `reasonCode == "LOSS_OF_SEPARATION_RISK"`.
- UAM0002의 계획(1202)은 시나리오 전 구간에서 `planVersion == 1`로 유지 (재계획 영향 없음).
- T+25:10 시점 이후 두 비행체의 수평 분리 거리가 사전 정의된 최소 분리 임계값(예: 300 m) 이상으로 유지된다.
- 양 비행체가 T+50:00 이전에 각자의 도착 vertiport에 land 완료 (4001 `phase=K` gate-in taxi).
- FORWARD_RULES 준수: 2001은 MISSION에만 전달, 3001은 VEHICLE/VISUAL, 3002/3003은 VEHICLE에만 전달된 것이 IntegrationHub 로그에서 확인된다.

## 6. 1003 ScenarioSetup payload 예시

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
- 회랑 C-NORTH (`WP-C-NORTH-IN → WP-C-NORTH-OUT`)는 초기 계획에서 두 비행체가 모두 통과 → 충돌 시드.
- C-SOUTH 우회 회랑이 routeNetwork에 사전 정의되어 있어 MISSION이 재계획 시 enRoute로 채택.
- vertiports 3개를 둔 이유: 도착지 변경 옵션을 PSU가 선택할 수 있도록 환경을 열어두되, 본 시나리오는 `arrivalVertiportHint=null`로 GIMPO_VP를 보존.
