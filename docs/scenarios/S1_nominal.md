# S1 — 정상 운항 (Nominal Flight)

## 1. 개요

- **목적**: 1대의 UAM(UAM0001)이 여의도(Yeouido) 버티포트에서 출발하여 3개의 경유 waypoint를 거쳐 잠실(Jamsil) 버티포트까지 도착하는 표준 정상 운항 시나리오. 어떠한 이상 상황(LOW_BATTERY, TRAFFIC_CONFLICT, WEATHER 등)도 발생하지 않으며, PSU / VPO / UAO / Monitoring 은 관찰만 하고 개입하지 않는 baseline 시나리오.
- **주요 참여 모듈 (역할)**:
  - `SERVER` — IntegrationHub: 전 메시지의 forwarder
  - `SIM_STATE` — Simulation State: 1001/1002/1003 소비, 0003 CommonTime emitter
  - `MISSION` — Mission Planner: 2001 → 3001 변환, 정상 비행계획 발행
  - `VEHICLE` — Air Mobility (UAM0001): 3001 plan 수신 → 4001 비행 상태 발행 (10 Hz)
  - `VISUAL` — Visualization (Unreal/AirSim): 1003 scene load, 4101 카메라 프레임 (5 Hz)
  - `MONITORING` — Operations Console: 0001/0002/4001/4101 관찰 only
  - `PSU` — Provider of Services for UAM: 4002 수신 listener (S1 에서는 수신 이벤트 없음)
  - `SITUATION_AWARENESS` — SA 플러그인: 4001/4101 관찰 only
- **시나리오 길이**: 시뮬레이션 시간 약 45분 (T+00:00 도구 부팅 ~ T+45:45 종료). `playbackSpeed=8x` 로 wall-clock 약 5~6분 진행.
- **트리거 메커니즘**:
  - `1003` ScenarioSetup 의 `scenarioFileName="S1_nominal.json"` 로딩
  - `1001` SimModeSetup `operationMode="single"`, `singleFlight.missionPlanning.activeMissionId="UAM0001"`
  - `2001` Flight Plan Request (`reasonCode=null`, baseline) → `3001` Scheduled Flight 생성
  - `1002` SimulationSetup `playState="play"` + `2002` DtamExecute 로 본격 진행

---

## 2. 시뮬레이션 timeline

```text
# Phase 0: 부팅 + 모듈 등록 (T+00:00 ~ T+00:10)
T+00:00  VEHICLE          → SERVER  [0001]  Module Setting Info
         payload: { moduleId:"VEH-UAM0001", role:"VEHICLE", version:"1.4.0" }
         note: Air Mobility 모듈 부팅 후 자기 식별

T+00:01  VISUAL           → SERVER  [0001]  Module Setting Info
         payload: { moduleId:"VIZ-Unreal", role:"VISUAL", version:"2.0.1" }
         note: Unreal/AirSim 측 식별

T+00:02  MISSION          → SERVER  [0001]  Module Setting Info
         payload: { moduleId:"MIS-Planner", role:"MISSION", version:"1.2.0" }

T+00:03  SIM_STATE        → SERVER  [0001]  Module Setting Info
         payload: { moduleId:"SIM-State", role:"SIM_STATE", version:"1.0.0" }

T+00:04  MONITORING       → SERVER  [0001]  Module Setting Info
         payload: { moduleId:"OPS-Console", role:"MONITORING", version:"1.3.0" }

T+00:05  PSU              → SERVER  [0001]  Module Setting Info
         payload: { moduleId:"EXT-PSU", role:"PSU", version:"0.9.0" }

T+00:06  SERVER           → MONITORING  [0001]  Module Setting Info (forward × N)
         note: FORWARD_RULES[0001]=[MONITORING] — 모든 0001 메시지 Ops Console 로 전달

T+00:08  ALL modules      → SERVER  [0002]  Module Status (1 Hz from this point)
         payload: { moduleId, state:"READY", uptimeSec:8 }
         note: 모듈별 1 Hz heartbeat 시작, MONITORING 으로 forward

# Phase 1: Sim Mode + Scenario setup (T+00:10 ~ T+00:20)
T+00:10  user(OpsConsole) → SERVER  [1001]  Sim Mode Setup
         payload: { timestamp:"2026-06-10T09:00:10Z",
                    operationMode:"single",
                    singleFlight:{
                      vehicleSimType:{ dynamics:"highFidelity",
                                       mainVehicleController:"Autopilot" },
                      missionPlanning:{
                        activeMissionId:"UAM0001",
                        missions:[{ aircraftName:"UAM0001",
                                    departureTime:"2026-06-10T09:10:00+09:00",
                                    std:"2026-06-10T09:10:00+09:00",
                                    departureName:"Yeouido",
                                    arrivalName:"Jamsil" }] } } }
         note: SIM_STATE 가 수신 → 단일 비행 모드로 내부 상태 설정

T+00:12  SERVER           → SIM_STATE  [1001]  forward
         note: FORWARD_RULES[1001]=[SIM_STATE]

T+00:15  user(OpsConsole) → SERVER  [1003]  Scenario Setup
         payload: { scenarioFileName:"S1_nominal.json",
                    totalAircraftCount:1,
                    mainVehicleType:"KP2A",
                    operationTime:{ startTime:"2026-06-10T09:10:00+09:00",
                                    endTime:"2026-06-10T09:55:00+09:00" },
                    vertiports:[Yeouido, Jamsil],
                    routeNetwork:{ waypoints:[WP_DEP, WP_EN1, WP_EN2, WP_EN3, WP_ARR] } }
         note: 상세 JSON 은 §6 참조

T+00:16  SERVER           → SIM_STATE  [1003]  forward
T+00:16  SERVER           → VISUAL     [1003]  forward
         note: VISUAL 이 1003 받아 Unreal scene/vertiport actor 배치 시작

# Phase 2: Flight Plan Request + Scheduled Flight (T+00:20 ~ T+00:25)
T+00:20  user(OpsConsole) → SERVER  [2001]  Flight Plan Request (base form)
         payload: { timestamp:"2026-06-10T09:00:20Z",
                    scenarioFileName:"S1_nominal.json",
                    flightPlanNumber:null,
                    reasonCode:null,
                    triggeringEventId:null,
                    arrivalVertiportHint:null }
         note: 정상 초기 비행계획 요청 — reasonCode null = baseline

T+00:21  SERVER           → MISSION  [2001]  forward
         note: FORWARD_RULES[2001]=[MISSION]

T+00:23  MISSION          → SERVER  [3001]  Scheduled Flight (planVersion=1)
         payload preview: { flightPlanNumber:1001,
                            planVersion:1,
                            planStatus:"active",
                            aircraftId:"UAM0001",
                            departure:{ vertiport:"Yeouido",
                                        std:"2026-06-10T09:10:00+09:00",
                                        etot:"2026-06-10T09:10:30+09:00",
                                        depFatoNumber:1, depGateNumber:2 },
                            arrival:{   vertiport:"Jamsil",
                                        sta:"2026-06-10T09:55:00+09:00",
                                        eldt:"2026-06-10T09:54:30+09:00",
                                        arrFatoNumber:1, arrGateNumber:3 },
                            enRoute:[seq1..seq4] }
         note: §3 에 full JSON

T+00:24  SERVER           → VEHICLE  [3001]  forward
T+00:24  SERVER           → VISUAL   [3001]  forward
         note: VEHICLE 가 3001 수신 → 내부 mission state machine 에 plan load

# Phase 3: DTAM Execute (T+00:25 ~ T+00:30)
T+00:25  user(OpsConsole) → SERVER  [1002]  Simulation Setup (play)
         payload: { timestamp:"2026-06-10T09:00:25Z",
                    simulationStartTime:"2026-06-10T09:10:00+09:00",
                    simulationTime:"2026-06-10T09:10:00+09:00",
                    simTimeOfDay:"09:10:00",
                    simSecondsOfDay:33000.0,
                    timeSource:"sim",
                    playbackSpeed:8,
                    playState:"play",
                    weatherEffect:{ precipitation:{type:"none",intensity:0},
                                    fog:{intensity:0} },
                    wind:{ grade:"normal", gust:null } }
         note: VEHICLE / VISUAL / SIM_STATE 동시 forward — sim clock 가동

T+00:26  SERVER           → VEHICLE     [1002]  forward
T+00:26  SERVER           → VISUAL      [1002]  forward
T+00:26  SERVER           → SIM_STATE   [1002]  forward

T+00:28  user(OpsConsole) → SERVER  [2002]  DTAM Execute
         payload: { timestamp:"2026-06-10T09:00:28Z",
                    simModeFileName:"S1_simMode.json",
                    simulationSetupFileName:"S1_simulationSetup.json",
                    scenarioFileName:"S1_nominal.json",
                    flightPlanFolderName:"flightPlans/UAM0001_v1" }
         note: 4-target forward (MISSION/MONITORING/VEHICLE/VISUAL/SA) — 실제 비행 시작

T+00:29  SERVER → MISSION,MONITORING,VEHICLE,VISUAL,SITUATION_AWARENESS  [2002]  fan-out

# Phase 4: 비행 (T+00:30 ~ T+45:30)
T+00:30  SIM_STATE → SERVER  [0003]  Common Time Info (1 Hz, 시작)
         payload: { timestamp:"2026-06-10T09:10:00+09:00",
                    simSecondsOfDay:33000.0, playbackSpeed:8 }
         note: SERVER → VEHICLE/VISUAL forward — 모든 sim 시계 sync

T+00:30+ VEHICLE   → SERVER  [4001]  Vehicle Status (10 Hz)
         payload: { timestamp,
                    UAM0001:{ currentWaypointId:"WP_DEP",
                              position:{north:0,east:0,down:0},
                              gps:{ is_valid:true, fix_type:3,
                                    latitude:37.5283, longitude:126.9343,
                                    altitude:30.0, ... },
                              energy:{ battery_pct:98.0,
                                       state_of_charge_pct:98.0 } } }
         note: SERVER → MONITORING/VISUAL/SITUATION_AWARENESS fan-out

T+00:30+ VISUAL    → SERVER  [4101]  Camera Image Frame (5 Hz)
         payload: { vehicle_id:"UAM0001", camera_name:"front",
                    image_type:"scene", sequence:0,
                    width:640, height:360, encoding:"jpeg",
                    payload_size:24560, image_b64:"..." }
         note: SERVER → MONITORING/SITUATION_AWARENESS forward

T+05:00  VEHICLE   → SERVER  [4001]  (en-route seq=2 진입)
         payload preview: { UAM0001:{ currentWaypointId:"WP_EN1",
                                      position:{ ... },
                                      energy:{ battery_pct:88.0, ... } } }

T+15:00  VEHICLE   → SERVER  [4001]  (en-route seq=3, WP_EN2)
         payload preview: { UAM0001:{ currentWaypointId:"WP_EN2",
                                      energy:{ battery_pct:72.0 } } }

T+30:00  VEHICLE   → SERVER  [4001]  (en-route seq=4, WP_EN3)
         payload preview: { UAM0001:{ currentWaypointId:"WP_EN3",
                                      energy:{ battery_pct:55.0 } } }

T+42:00  VEHICLE   → SERVER  [4001]  (final approach)
         payload preview: { UAM0001:{ currentWaypointId:"WP_ARR",
                                      energy:{ battery_pct:45.0 } } }

# Phase 5: 도착, 종료 (T+45:30 ~ T+45:45)
T+45:30  VEHICLE   → SERVER  [4001]  (touchdown @ Jamsil FATO 1)
         payload preview: { UAM0001:{ currentWaypointId:"WP_ARR",
                                      gps:{ altitude:25.0 },
                                      energy:{ battery_pct:42.0 } } }
         note: navigation.phase="landed", actuator throttle→0

T+45:35  VEHICLE → SERVER  [0002]  Module Status (state="LANDED")
         payload: { moduleId:"VEH-UAM0001", state:"LANDED" }

T+45:40  user(OpsConsole) → SERVER  [1002]  Simulation Setup (pause)
         payload: { timestamp:"2026-06-10T09:55:40+09:00",
                    playState:"pause", playbackSpeed:8 }

T+45:45  user(OpsConsole) → SERVER  [1002]  Simulation Setup (reset)
         payload: { playState:"reset" }
         note: 시나리오 정상 종료
```

---

## 3. 메시지별 상세 payload

### 3.1 `2001` Flight Plan Request — base form (S1 entry)

```json
{
  "messageId": "2001",
  "messageName": "Flight Plan Request",
  "timestamp": "2026-06-10T09:00:20+09:00",
  "scenarioFileName": "S1_nominal.json",
  "flightPlanNumber": null,
  "reasonCode": null,
  "triggeringEventId": null,
  "arrivalVertiportHint": null
}
```

> S1 baseline: `flightPlanNumber=null` (신규 발행), `reasonCode=null` (baseline 진입), 어떤 hint도 없음.

### 3.2 `3001` Scheduled Flight — planVersion=1 (Mission → Vehicle/Visual)

```json
{
  "messageId": "3001",
  "messageName": "Scheduled Flight",
  "timestamp": "2026-06-10T09:00:23+09:00",
  "flightPlanNumber": 1001,
  "planVersion": 1,
  "planStatus": "active",
  "aircraftId": "UAM0001",
  "departure": {
    "vertiport": "Yeouido",
    "std": "2026-06-10T09:10:00+09:00",
    "depGateNumber": 2,
    "eobt": "2026-06-10T09:09:30+09:00",
    "depFatoNumber": 1,
    "etot": "2026-06-10T09:10:30+09:00"
  },
  "arrival": {
    "vertiport": "Jamsil",
    "sta": "2026-06-10T09:55:00+09:00",
    "arrGateNumber": 3,
    "eibt": "2026-06-10T09:55:30+09:00",
    "arrFatoNumber": 1,
    "eldt": "2026-06-10T09:54:30+09:00"
  },
  "enRoute": [
    {
      "seq": 1,
      "phase": "E",
      "targetSpeed": 25.0,
      "startLLA": { "lat": 37.5283, "lon": 126.9343, "alt": 30.0 },
      "endLLA":   { "lat": 37.5290, "lon": 126.9380, "alt": 300.0 }
    },
    {
      "seq": 2,
      "phase": "F",
      "targetSpeed": 55.0,
      "startLLA": { "lat": 37.5290, "lon": 126.9380, "alt": 300.0 },
      "endLLA":   { "lat": 37.5320, "lon": 126.9800, "alt": 450.0 }
    },
    {
      "seq": 3,
      "phase": "F",
      "targetSpeed": 55.0,
      "startLLA": { "lat": 37.5320, "lon": 126.9800, "alt": 450.0 },
      "endLLA":   { "lat": 37.5180, "lon": 127.0500, "alt": 450.0 }
    },
    {
      "seq": 4,
      "phase": "G",
      "targetSpeed": 30.0,
      "startLLA": { "lat": 37.5180, "lon": 127.0500, "alt": 450.0 },
      "endLLA":   { "lat": 37.5125, "lon": 127.0830, "alt": 30.0 }
    }
  ]
}
```

### 3.3 `1002` Simulation Setup — `playState="play"` (DTAM 본 실행 직전)

```json
{
  "messageId": "1002",
  "messageName": "Simulation Setup",
  "timestamp": "2026-06-10T09:00:25+09:00",
  "simulationStartTime": "2026-06-10T09:10:00+09:00",
  "simulationTime": "2026-06-10T09:10:00+09:00",
  "simTimeOfDay": "09:10:00",
  "simSecondsOfDay": 33000.0,
  "timeSource": "sim",
  "playbackSpeed": 8,
  "playState": "play",
  "weatherEffect": {
    "precipitation": { "type": "none", "intensity": 0 },
    "fog":           { "intensity": 0 }
  },
  "wind": {
    "grade": "normal",
    "gust": null
  }
}
```

> `playbackSpeed=8` → 약 45 sim-min 이 ~5.6 wall-clock min 으로 압축. S1 은 weather/wind 모두 nominal.

---

## 4. 모듈별 책임

- **VehicleModule (Air Mobility, UAM0001)**:
  - `0001` 자기 등록, `0002` 1 Hz 상태 보고
  - `1002 playState="play"` 수신 후 sim clock 따라 비행 state machine 가동
  - `3001` plan 수신 → 내부 mission queue 에 enRoute seq=1..4 load
  - `0003` CommonTime 으로 시계 sync, `4001` 10 Hz 발행 (정상 비행 trajectory)
  - **S1 에서는 4002 / 4103 발행하지 않음** (이상/충돌 없음)
- **MissionModule (Mission Planner)**:
  - `2001` 수신 → baseline 비행계획 생성, `3001` planVersion=1 발행
  - S1 에서는 `3002` / `3003` 재계획/전술적 분리 발행하지 않음
- **OperationModule (Monitoring / Ops Console)**:
  - 모든 `0001`/`0002` 수신하여 모듈 상태 대시보드 업데이트
  - `4001`/`4101`/`4002` 수신 (S1 에서 4002 는 0건)
  - user actor 로서 `1001`/`1003`/`2001`/`1002`/`2002` 발행
- **VisualizationModule (Unreal/AirSim)**:
  - `1003` 수신 시 vertiport actor 배치 (Yeouido / Jamsil), routeNetwork waypoint 시각화
  - `1002 play` 이후 sim clock 따라 scene 진행
  - `3001` 수신해 trajectory 시각화
  - `4101` Camera Image Frame 5 Hz 발행 (UAM0001 front cam, scene 타입)
- **PSU (Provider of Services for UAM)**:
  - `4002` Vehicle Warning Event 수신 listener만 구독 — **S1 에서는 한 건도 수신하지 않음**
  - 어떤 우선순위 이벤트 처리 / 2001 재요청도 발행하지 않음
- **SimStateModule**:
  - `1001`/`1002`/`1003` 수신해 내부 sim time/mode 관리
  - `0003` CommonTime 1 Hz emit (T+00:30 이후 sim clock 가동)
- **SituationAwareness**:
  - `4001`/`4101`/`4103` 수신해 SA 화면 갱신 (S1 에선 4103 0건)

---

## 5. 검증 가능한 결과 (acceptance criteria)

- [ ] 모든 6개 모듈(VEHICLE/VISUAL/MISSION/SIM_STATE/MONITORING/PSU) 이 `0001` 1회 + `0002` 1 Hz 지속 emit
- [ ] `1001`/`1003` 발행 후 Ops Console 상에 단일 비행(`UAM0001`), 2개 vertiport(`Yeouido`, `Jamsil`), 5개 waypoint 시각화
- [ ] `2001` (`reasonCode=null`) 1회 발행 → `3001` (`planVersion=1`, `planStatus="active"`) 1회 응답
- [ ] `1002 playState="play"` → `0003` 1 Hz 발행 시작 확인
- [ ] `4001` 10 Hz 로 약 (45×60×10)=27,000 frame 발행 (`±5%` 허용)
- [ ] `4101` 5 Hz 로 약 (45×60×5)=13,500 frame 발행 (`±5%` 허용)
- [ ] **`4002` 발행 0건** (LOW_BATTERY 등 어떤 warning 도 없음)
- [ ] **`4103` 발행 0건** (충돌 없음)
- [ ] **`3002`/`3003` 발행 0건** (재계획/전술적 분리 없음)
- [ ] `currentWaypointId` sequence: `WP_DEP → WP_EN1 → WP_EN2 → WP_EN3 → WP_ARR` 순서대로 1회씩
- [ ] 최종 `4001.energy.battery_pct ≥ 40%` (정상 운항 에너지 마진 확보)
- [ ] T+45:40 `1002 playState="pause"` 직전 UAM0001 의 GPS 위치가 Jamsil vertiport(`lat≈37.5125, lon≈127.0830`) 와 50 m 이내
- [ ] Ops Console 의 warning panel 이 시나리오 종료까지 비어 있어야 함

---

## 6. ICD payload 예시

### 6.1 `1003` ScenarioSetup (SDK `Msg1003_ScenarioSetup` 그대로)

Msg1003 의 SDK wire 형식은 `timestamp / scenarioFileName / totalAircraftCount /
mainVehicleType / operationTime / vertiports[] / routeNetwork` 7개 필드뿐.
per-aircraft 정보(aircraftName, std, vehicleSimType)는 §6.2 의 Msg1001 에 있다.

```json
{
  "timestamp": "2026-06-10T09:00:15+09:00",
  "scenarioFileName": "S1_nominal.json",
  "totalAircraftCount": 1,
  "mainVehicleType": "KP2A",
  "operationTime": {
    "startTime": "2026-06-10T09:10:00+09:00",
    "endTime":   "2026-06-10T09:55:00+09:00"
  },
  "vertiports": [
    {
      "name": "Yeouido",
      "vertiportClass": "port",
      "lat": 37.5283,
      "lon": 126.9343,
      "angleDegrees": 75.0
    },
    {
      "name": "Jamsil",
      "vertiportClass": "hub",
      "lat": 37.5125,
      "lon": 127.0830,
      "angleDegrees": 255.0
    }
  ],
  "routeNetwork": {
    "waypoints": [
      {
        "waypointId": "WP_DEP",
        "waypointName": "Yeouido Departure Fix",
        "lat": 37.5283,
        "lon": 126.9343,
        "altFt": 100,
        "links": ["WP_EN1"]
      },
      {
        "waypointId": "WP_EN1",
        "waypointName": "Hangang Bridge North",
        "lat": 37.5290,
        "lon": 126.9380,
        "altFt": 980,
        "links": ["WP_DEP", "WP_EN2"]
      },
      {
        "waypointId": "WP_EN2",
        "waypointName": "Yongsan Crossover",
        "lat": 37.5320,
        "lon": 126.9800,
        "altFt": 1480,
        "links": ["WP_EN1", "WP_EN3"]
      },
      {
        "waypointId": "WP_EN3",
        "waypointName": "Olympic Park West",
        "lat": 37.5180,
        "lon": 127.0500,
        "altFt": 1480,
        "links": ["WP_EN2", "WP_ARR"]
      },
      {
        "waypointId": "WP_ARR",
        "waypointName": "Jamsil Arrival Fix",
        "lat": 37.5125,
        "lon": 127.0830,
        "altFt": 100,
        "links": ["WP_EN3"]
      }
    ]
  },
}
```

### 6.2 `1001` SimModeSetup — per-aircraft 정보의 진짜 자리

S1 의 비행체 (UAM0001) 의 출발지/도착지/std/dynamics 는 SDK 의 `Msg1001_SimModeSetup`
에 들어간다. `Msg1003` 에는 비행체 리스트가 없다.

```json
{
  "timestamp": "2026-06-10T09:00:10+09:00",
  "operationMode": "single",
  "singleFlight": {
    "vehicleSimType": {
      "dynamics": "highFidelity",
      "mainVehicleController": "Autopilot"
    },
    "missionPlanning": {
      "activeMissionId": "M_S1_UAM0001",
      "missions": [
        {
          "aircraftName": "UAM0001",
          "departureTime": "09:10:00",
          "std":           "09:10:00",
          "departureName": "Yeouido",
          "arrivalName":   "Jamsil"
        }
      ]
    }
  }
}
```

### 6.3 시뮬레이터-side 보조 데이터 (SDK ICD 외)

`scenarioFileName` 이 가리키는 시뮬레이터 입력 파일에는 ICD payload 외 보조 데이터
(traffic 설정, 초기 SOC, 환경 thresholds 등) 가 들어갈 수 있다. 이는 모듈 내부
구현 영역이고 wire 송수신되지 않는다.

```json
{
  "traffic": { "trafficScenario": "low" },
  "initialBatteryPct": 100.0
}
```

> `traffic.trafficScenario="low"` 로 단일 비행에 가까운 환경 보장. Msg1003 에는 per-aircraft 필드가 없으며, 항공기 정보는 §2 Phase 1 의 `1001` `singleFlight.missionPlanning.missions[*]` (`aircraftName`/`departureTime`/`std`/`departureName`/`arrivalName`) 에 정의된다. 초기 배터리(%)는 ICD payload 가 아닌 dynamics `SimulationConfig.battery_initial_pct` 로 설정되므로 LOW_BATTERY 트리거가 발생하지 않도록 baseline 보장은 dynamics config 측에서 담당.
