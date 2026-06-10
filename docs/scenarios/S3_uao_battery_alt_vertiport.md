# S3 — UAO 배터리 고장 대체 vertiport (긴급 착륙)

## 1. 개요

- **목적**: 운항 중인 UAM 기체의 자가 진단으로 배터리 열화/저전압이 감지되었을 때, PSU가 가장 가까운 대체 vertiport를 선정하고 MissionModule이 비행계획을 재계산하여 긴급 착륙(land)까지 수행하는 전 과정을 검증한다. UAO/PSU/Mission/Vehicle 간의 책임 경계와 4002(critical) → 2001(extended) → 3001 v2 + 3003(land) 사슬을 시뮬레이션한다.
- **주요 참여 모듈 (역할)**:
  - **VehicleModule (VEHICLE)**: 자가 진단으로 배터리 임계치 위반을 감지하고 4002(critical)을 발행. 이후 3001 v2 / 3003(land) 명령을 실행.
  - **MissionModule (MISSION)**: extended 2001을 받아 3001 v2(arrival=VP_KU)와 3003(land, IMMEDIATE)을 발행.
  - **OperationModule / Monitoring (MONITORING)**: 4002, 2001, 3001 v2, 3003을 UI에 표출하고 운항자(UAO)에게 경고.
  - **VisualizationModule (VISUAL)**: 3001 v2로 항로를 갱신, 3003으로 land 시각화.
  - **PSU (Provider of Services for UAM)**: 4002(critical, LOW_BATTERY 계열)을 받아 주변 vertiport availability/거리 평가 후 VP_KU 선정. extended 2001을 server로 송신.
  - **UAO (UAM Air Operator)**: 운항 책임 주체. 이 시나리오에서는 **알림 수신자(informed)** 이며, 대체 vertiport에 대한 **dispatch 권한은 PSU가 보유**(사용자 결정). UAO는 사후 정산/디스패치 책임(post-hoc accountability)에 관여.
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

T+00:01  User       → SERVER     [1002]  SimulationSetup (play)
                                          payload preview: { playState: "play", playbackSpeed: 1, simSecondsOfDay: 32400.0 }
                                          note: 09:00 시작, 실시간 1배속.

T+00:02  User       → SERVER     [2001]  FlightPlanRequest (base)
                                          payload preview: { scenarioFileName: "S3_...", flightPlanNumber: null, reasonCode: null }
                                          note: 최초 요청 — UAM0001 정상 운항 계획.

T+00:03  MISSION    → SERVER     [3001]  ScheduledFlight v1
                                          payload preview: { flightPlanNumber: 1201, planVersion: 1, planStatus: "active",
                                                             aircraftId: "UAM0001",
                                                             departure.vertiport: "VP_YEOUIDO",
                                                             arrival.vertiport: "VP_JAMSIL",
                                                             enRoute: [seq 1..N] }
                                          note: VEHICLE/VISUAL이 정상 비행 plan 수신.

T+00:05  User       → SERVER     [2002]  DtamExecute
                                          payload preview: { simModeFileName, simulationSetupFileName, scenarioFileName, flightPlanFolderName }
                                          note: 모든 모듈 실행 단계 진입.

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

T+25:01  PSU        → SERVER     [2001]  FlightPlanRequest (extended, PSU)
                                          payload preview: { flightPlanNumber: 1201,
                                                             reasonCode: "LOW_BATTERY",
                                                             triggeringEventId: "WARN-UAM0001-20260609-002",
                                                             arrivalVertiportHint: "VP_KU" }
                                          note: PSU가 거리/availability 평가 후 VP_KU를 alternate로 hint. MISSION에 reroute 요청.

T+25:02  MISSION    → SERVER     [3001]  ScheduledFlight v2 (rerouted)
                                          payload preview: { flightPlanNumber: 1201, planVersion: 2, planStatus: "active",
                                                             arrival.vertiport: "VP_KU",
                                                             enRoute: [seq 1..M, shortened] }
                                          note: planVersion=1은 자동 superseded. VEHICLE/VISUAL이 새 항로로 갱신.

T+25:03  MISSION    → SERVER     [3003]  TacticalSeparation (IMMEDIATE land)
                                          payload preview: { commandId: "TAC-1201-LAND-001",
                                                             aircraftId: "UAM0001",
                                                             reasonCode: "LOW_BATTERY",
                                                             actions: [{ type: "land", vertiport: "VP_KU", fatoNumber: "FATO_A" }] }
                                          note: 정상 스케줄링 우회 — 즉시 착륙 명령.

T+25:04  VEHICLE    → SERVER     [4001]  VehicleStatus
                                          payload preview: { UAM0001.energy.battery_pct: 9.2, navigation: {...rerouting} }
                                          note: 새 plan에 따라 descent 진입.

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

### 3.1 4002 VehicleWarningEvent — LOW_BATTERY critical (T+25:00)

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

### 3.2 2001 FlightPlanRequest — extended (PSU, LOW_BATTERY) (T+25:01)

```json
{
  "timestamp": "2026-06-09T09:25:01.120Z",
  "scenarioFileName": "S3_uao_battery_alt_vertiport.json",
  "flightPlanNumber": 1201,
  "reasonCode": "LOW_BATTERY",
  "triggeringEventId": "WARN-UAM0001-20260609-002",
  "arrivalVertiportHint": "VP_KU"
}
```

### 3.3 3001 ScheduledFlight v2 — rerouted arrival = VP_KU (T+25:02)

```json
{
  "flightPlanNumber": 1201,
  "planVersion": 2,
  "planStatus": "active",
  "aircraftId": "UAM0001",
  "departure": {
    "vertiport": "VP_YEOUIDO",
    "std": "2026-06-09T09:00:00.000Z",
    "depGateNumber": "G1",
    "eobt": "2026-06-09T09:00:30.000Z",
    "depFatoNumber": "FATO_A",
    "etot": "2026-06-09T09:01:00.000Z"
  },
  "arrival": {
    "vertiport": "VP_KU",
    "sta": "2026-06-09T09:32:00.000Z",
    "arrGateNumber": "G1",
    "eibt": "2026-06-09T09:32:30.000Z",
    "arrFatoNumber": "FATO_A",
    "eldt": "2026-06-09T09:31:30.000Z"
  },
  "enRoute": [
    {
      "seq": 1,
      "phase": "G",
      "targetSpeed": 28.0,
      "startLLA": { "lat": 37.5295, "lon": 127.0123, "alt": 350.0 },
      "endLLA":   { "lat": 37.5400, "lon": 127.0290, "alt": 280.0 }
    },
    {
      "seq": 2,
      "phase": "I",
      "targetSpeed": 18.0,
      "startLLA": { "lat": 37.5400, "lon": 127.0290, "alt": 280.0 },
      "endLLA":   { "lat": 37.5453, "lon": 127.0399, "alt": 120.0 }
    },
    {
      "seq": 3,
      "phase": "J",
      "targetSpeed": 8.0,
      "startLLA": { "lat": 37.5453, "lon": 127.0399, "alt": 120.0 },
      "endLLA":   { "lat": 37.5460, "lon": 127.0415, "alt": 30.0 }
    }
  ]
}
```

### 3.4 3003 TacticalSeparation — IMMEDIATE land at VP_KU (T+25:03)

```json
{
  "timestamp": "2026-06-09T09:25:03.045Z",
  "commandId": "TAC-1201-LAND-001",
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

## 4. 모듈별 책임

- **VehicleModule (VEHICLE)**
  - 자가 진단(self-diagnostic) 루프에서 `energy.battery_pct < threshold.critical_pct` 위반 감지 시 4002(critical, BATTERY_VOLTAGE_LOW)를 발행한다.
  - 4001 telemetry(10 Hz)를 지속 publish.
  - 3001 v2(rerouted)와 3003(land, IMMEDIATE)을 수신/실행 — 정상 plan 종료보다 3003 land를 우선 처리.
  - 착륙 완료 후 동일 eventId로 4002 status="cleared" 발행.
- **MissionModule (MISSION)**
  - extended 2001(`reasonCode=LOW_BATTERY`, `triggeringEventId`, `arrivalVertiportHint=VP_KU`)을 수신하면 비행계획 1201의 planVersion을 +1 (v2)로 발행, `arrival.vertiport=VP_KU`로 갱신.
  - 즉시 3003 `actions=[{type:"land", vertiport:"VP_KU", fatoNumber:"FATO_A"}]`을 IMMEDIATE로 발행하여 정상 스케줄링 큐를 우회.
  - planVersion=1은 자동 superseded.
- **OperationModule / Monitoring (MONITORING)**
  - 4002(warning/critical/cleared), 2001(extended), 3001 v2, 3003(land)을 모두 수신하여 UI에 표출.
  - 운항자(UAO) 콘솔에 critical 경보, reroute 결정 출처(PSU), 새 도착지(VP_KU)를 시각/청각 알람으로 안내.
- **VisualizationModule (VISUAL)**
  - 1003으로 vertiport(VP_YEOUIDO, VP_JAMSIL, VP_KU)와 routeNetwork 로드.
  - 3001 v2 수신 시 항로 시각화 갱신, 3003 land 수신 시 강조 표시 및 카메라 트래킹.
- **PSU (Provider of Services for UAM)**
  - 4002 critical(LOW_BATTERY / BATTERY_VOLTAGE_LOW / BATTERY_OVERHEAT 등 energy 계열) 수신을 우선 이벤트 리스트에서 처리.
  - 현재 position과 vertiport DB의 거리/availability/class를 비교, alternate vertiport 선정 알고리즘으로 VP_KU 결정.
  - extended 2001(`flightPlanNumber`, `reasonCode`, `triggeringEventId`, `arrivalVertiportHint`)을 server로 송신 — **대체 vertiport에 대한 dispatch 권한(authority)은 본 시나리오에서 PSU가 보유**.
- **UAO (UAM Air Operator)**
  - 이 시나리오에서 UAO는 **알림 수신자(informed party)**: MONITORING 콘솔을 통해 4002 critical, PSU 의사결정, 3001 v2, 3003 land를 인지.
  - **대체 vertiport 선정/디스패치 권한은 PSU가 행사하며 UAO는 이를 위임/승인한 상태로 모델링**(사용자 결정).
  - UAO의 역할은 사후(financial / dispatching) 책임 — 정산, 사고 보고, 보험, 승객 케어 등 post-hoc accountability에 한정한다.
  - 주의: PSU의 안전/항공교통 의사결정 권한과 UAO의 운항/계약 책임은 분리해 해석할 것 (혼동 금지).
- **(참고) VPO (Vertiport Operator)**
  - 본 시나리오에서는 명시적 메시지 송수신 없음. 향후 vertiport availability를 동적으로 PSU에 공급하는 역할로 확장 가능.

## 5. 검증 가능한 결과 (acceptance criteria)

- T+25:00 ±200 ms 내에 VEHICLE이 4002(critical, BATTERY_VOLTAGE_LOW, severity=critical, recommendedAction=emergency_landing)을 정확히 1회 publish 한다.
- 4002 critical은 FORWARD_RULES에 따라 **MONITORING, SITUATION_AWARENESS, PSU** 세 모듈로 모두 도달한다.
- PSU는 4002 수신 후 1초 이내에 extended 2001을 publish하며, 4개 신규 필드(`flightPlanNumber=1201`, `reasonCode="LOW_BATTERY"`, `triggeringEventId=4002.eventId`, `arrivalVertiportHint="VP_KU"`)가 모두 채워져 있다.
- MISSION은 동일 flightPlanNumber=1201에 대해 `planVersion=2`, `planStatus="active"`, `arrival.vertiport="VP_KU"`인 3001을 publish 하고, 직후 `reasonCode="LOW_BATTERY"`, `actions[0].type="land"`, `actions[0].vertiport="VP_KU"`인 3003을 IMMEDIATE로 publish 한다.
- VEHICLE은 3003 land 수신 후 정상 plan 시퀀스를 중단하고 land action을 우선 실행 — 최종 착륙 위치가 VP_KU FATO_A의 ±15 m 이내.
- 착륙 완료 직후 VEHICLE이 동일 `eventId`로 4002 `status="cleared"`를 발행한다.
- 시뮬레이션 종료 시점 battery_pct ≥ 3.0 (완전 방전 없이 착륙 성공).
- MONITORING UI 로그에 "PSU: alternate vertiport = VP_KU" 와 "UAO: informed" 두 이벤트가 시간순으로 기록.

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
  },
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
          "departureTime": "09:00:00",
          "std":           "09:00:00",
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
    "uaoRole": "informed"
  }
}
```

> 4002 의 `threshold.warning_pct=20`, `threshold.critical_pct=10` 는 위 `thresholds.battery`
> 와 1:1 대응. Vehicle 측 진단 로직이 시작 시점에 이 값을 읽어 자신의 4002 발행
> 기준으로 삼는다.
