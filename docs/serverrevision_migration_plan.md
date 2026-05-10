# ServerRevision 기준 DTAM 구조 전환 계획

작성일: 2026-04-28

이 문서는 `D:\DTAMFramework\ServerRevision\DTAMFramework-JW`를 기준 구조로 삼아 현재 `D:\DTAMFramework` 프로젝트를 어떻게 재구성할지 정리한 전환 계획이다. 결론부터 말하면, 단순히 파일을 덮어쓰는 작업이 아니다. 현재 프로젝트는 기능 면에서 더 앞선 부분이 많고, ServerRevision은 서버, SDK, 통신, 모듈 기본 구조를 크게 바꿔 놓은 기준안이다. 따라서 목표는 다음과 같다.

1. 서버와 SDK, 통신 방식은 ServerRevision 구조를 따른다.
2. 모듈 폴더와 앱 기본 구조도 ServerRevision 패턴을 따른다.
3. 현재 프로젝트에만 있는 앞선 기능은 버리지 않고 새 구조 안으로 이식한다.
4. 현행 런타임에서는 신규 WebSocket/SDK 경로를 기준으로 삼고, legacy UDP/TCP 경로는 이력 또는 백업 비교용으로만 남긴다.

## 조사 범위

ServerRevision 기준 파일:

- `ServerRevision/DTAMFramework-JW/Start_DTAM.py`
- `ServerRevision/DTAMFramework-JW/DTAM_CoreServer`
- `ServerRevision/DTAMFramework-JW/DTAM_SimulationState`
- `ServerRevision/DTAMFramework-JW/DTAM_SDK`
- `ServerRevision/DTAMFramework-JW/DTAMOperationsConsole`
- `ServerRevision/DTAMFramework-JW/DTAM_MissionPlanner`
- `ServerRevision/DTAMFramework-JW/DTAMAirMobility`
- `ServerRevision/DTAMFramework-JW/DTAMVisualizationModule`

현재 프로젝트 기준 파일:

- `Start_DTAM.py`
- `DTAM_ServerEmulator`
- `DTAM_SDK`
- `DTAMOperationsConsole`
- `DTAM_MissionPlanner`
- `DTAMAirMobility`
- `DTAMVisualization`

subagent는 세 갈래로 병렬 확인했다.

- ServerRevision 구조 전담: CoreServer, SimulationState, SDK, 모듈 작성 패턴 확인.
- 현재 프로젝트 구조 전담: 현재 서버, SDK, Operations Console, Mission Planner, Air Mobility, Visualization 기능 확인.
- 차이점 및 전환 리스크 전담: SDK/API, 서버/data plane, module orchestration, 폴더 구조 차이 확인.

## 최종 방향

ServerRevision의 방향을 최종 기준으로 삼는다.

```text
DTAM_CoreServer       : control plane, HTTP 8095
DTAM_SimulationState  : data plane, HTTP/WebSocket 8096
DTAMOperationsConsole : operator GUI/facade, HTTP 8000
Mission Planner       : module GUI + MissionModule client, HTTP 8090
Air Mobility          : module GUI + VehicleModule client, HTTP 8100
Visualization         : VisualModule or packaged visualization runtime
DTAM_SDK              : WebSocket-first SDK, role-based module API
```

현재 `DTAM_ServerEmulator` 중심 구조와 UDP/TCP `DtamClient` 구조는 최종 구조가 아니다. 다만 현재 프로젝트에서 구현된 고급 기능은 새 구조로 포팅한다.

## 핵심 차이 요약

| 영역 | 현재 프로젝트 | ServerRevision 목표 |
|---|---|---|
| 서버 | `DTAM_ServerEmulator` 하나가 UDP/TCP 수신, DB 저장, forwarding, GUI 이벤트 담당 | `DTAM_CoreServer`와 `DTAM_SimulationState`로 분리 |
| control plane | Operations Console이 모듈 프로세스 실행을 직접 관리 | CoreServer가 process start/stop 관리 |
| data plane | UDP/TCP `17000/17001` 서버와 모듈별 UDP/TCP 포트 | SimulationState의 `ws://<host>:8096/ws/dtam` 단일 WebSocket |
| SDK | `DtamClient`, `DtamListener`, `push_*`, UDP/TCP transport | `DtamModule`, role module, `@on_receive`, dataclass send, `DtamRest` |
| 모듈 구조 | 모듈마다 `backend/frontend`, 혹은 독자적 구조 | `app/`, `web/`, `resources/`, `data/` 기본 구조 |
| 모듈 식별 | endpoint IP/UDP/TCP port 중심 | role/source identity 중심 |
| DB | ServerEmulator가 `DB`에 직접 저장 | SimulationState가 data plane 이벤트를 저장 |
| 4001 | 현재 Air Mobility는 30 Hz 중심 | ServerRevision은 10 Hz로 문서화 |
| Visualization | Python bridge, AirSim/Unreal manager, Unreal source 포함 | packaged `DTAMVisualizationModule` 중심 |

## ServerRevision 목표 아키텍처

### CoreServer

CoreServer는 control plane만 담당한다.

책임:

- ICD 문서와 phase metadata 제공.
- 모듈 프로세스 start/stop.
- SimulationState 자동 시작.
- 운영자용 admin landing 제공.

주요 파일:

- `ServerRevision/DTAMFramework-JW/DTAM_CoreServer/DSE_main.py`
- `ServerRevision/DTAMFramework-JW/DTAM_CoreServer/config.json`
- `ServerRevision/DTAMFramework-JW/DTAM_CoreServer/app/server.py`
- `ServerRevision/DTAMFramework-JW/DTAM_CoreServer/app/routes/icd.py`
- `ServerRevision/DTAMFramework-JW/DTAM_CoreServer/app/routes/process.py`

주요 endpoint:

```text
GET  /api/icd
GET  /api/icd/{mid}
GET  /api/icd/phases
POST /api/v1/process/{role}/start
POST /api/v1/process/{role}/stop
```

CoreServer는 더 이상 ICD message forwarding의 중심이 아니다. message forwarding, DB 저장, live traffic은 SimulationState로 이동한다.

### SimulationState

SimulationState는 data plane이다.

책임:

- `/ws/dtam`에서 모든 모듈 WebSocket 연결 수락.
- ICD message 수신.
- SDK dataclass 기반 검증 및 dict 변환.
- module registry와 rx/tx counter 갱신.
- file DB 저장.
- `FORWARD_RULES`에 따른 역할별 forwarding.
- `/ws/events`로 live monitor event 제공.
- `/api/msg/{mid}`로 운영자 REST push 제공.
- `/api/state`, `/api/modules`, `/api/db/*` 제공.
- `1001`, `1002`에 대한 workflow trigger 처리.
- `0003 Common Time Info` clock 발행.

주요 파일:

- `ServerRevision/DTAMFramework-JW/DTAM_SimulationState/SS_main.py`
- `ServerRevision/DTAMFramework-JW/DTAM_SimulationState/app/server.py`
- `ServerRevision/DTAMFramework-JW/DTAM_SimulationState/app/routes/ws_dtam.py`
- `ServerRevision/DTAMFramework-JW/DTAM_SimulationState/app/routes/ws_events.py`
- `ServerRevision/DTAMFramework-JW/DTAM_SimulationState/app/routes/push.py`
- `ServerRevision/DTAMFramework-JW/DTAM_SimulationState/app/routes/state.py`
- `ServerRevision/DTAMFramework-JW/DTAM_SimulationState/app/services/hub.py`
- `ServerRevision/DTAMFramework-JW/DTAM_SimulationState/app/services/engine.py`
- `ServerRevision/DTAMFramework-JW/DTAM_SimulationState/app/database/file_db.py`

주요 endpoint:

```text
WS   /ws/dtam
WS   /ws/events
POST /api/msg/{mid}
GET  /api/state
GET  /api/modules
PATCH /api/modules/{role}
POST /api/heartbeat
GET  /api/db/stats
GET  /api/db/messages/{mid}/latest
GET  /docs/websocket
GET  /docs/sequence
```

### WebSocket protocol

모듈은 직접 서로 연결하지 않는다. 모든 모듈은 SimulationState의 `/ws/dtam`에 client로 붙는다.

등록:

```json
{
  "type": "register",
  "role": "vehicle",
  "source": "DTAMAirMobility"
}
```

등록 응답:

```json
{
  "type": "registered",
  "role": "vehicle",
  "source": "DTAMAirMobility",
  "subscriptions": ["0003", "1002", "2002", "3001", "3002", "3003", "5001"]
}
```

메시지 송신:

```json
{
  "type": "message",
  "mid": "4001",
  "payload": {}
}
```

카메라 `4101`은 `image_b64`를 포함할 수 있다.

```json
{
  "type": "message",
  "mid": "4101",
  "payload": {},
  "image_b64": "..."
}
```

## SDK 전환 방향

현재 SDK는 UDP/TCP facade다.

현재 주요 API:

- `DtamClient`
- `DtamListener`
- `DtamChannel`
- `push_vehicle_status`
- `push_scheduled_flight`
- `client.on_vehicle_status = callback`
- `client.listen(...)`

ServerRevision SDK의 목표 API:

- `DtamModule`
- `MissionModule`
- `VehicleModule`
- `MonitoringModule`
- `VisualModule`
- `Role`
- `@on_receive("MID")`
- `send(dataclass_instance)`
- `send("mid_or_alias", dict)`는 migration-only 경로
- `DtamRest`

### SDK 파일 교체 기준

현재 SDK에서 최종적으로 제거되거나 legacy로 내려갈 파일:

```text
DTAM_SDK/dtam_client/_client.py
DTAM_SDK/dtam_client/_listener.py
DTAM_SDK/dtam_client/_transport.py
DTAM_SDK/dtam_client/_channel.py
DTAM_SDK/dtam_client/_router.py
DTAM_SDK/dtam_client/_config.py
DTAM_SDK/dtam_client/msg/
DTAM_SDK/dtam_client/receiver/
```

ServerRevision SDK 기준 파일:

```text
DTAM_SDK/dtam_client/catalog.py
DTAM_SDK/dtam_client/identity.py
DTAM_SDK/dtam_client/policy.py
DTAM_SDK/dtam_client/module.py
DTAM_SDK/dtam_client/role_modules.py
DTAM_SDK/dtam_client/rest.py
DTAM_SDK/dtam_client/_ws_client.py
DTAM_SDK/dtam_client/schema/
```

### 모듈 작성 표준

모듈은 자기 역할에 맞는 base class를 상속한다.

```python
from dtam_client import VehicleModule, on_receive
from dtam_client.schema import Msg4001_VehicleStatus

class AirMobilityService(VehicleModule):
    def __init__(self, *, target_ip="127.0.0.1", ws_port=8096):
        super().__init__(
            server_url=f"ws://{target_ip}:{ws_port}/ws/dtam",
            heartbeat=True,
        )

    @on_receive("3001")
    def on_scheduled_flight(self, msg):
        ...

    @on_receive("0003")
    def on_common_time_info(self, msg):
        ...

    def publish_status(self, vehicles):
        return self.send(Msg4001_VehicleStatus(
            timestamp="...",
            vehicles=vehicles,
        ))
```

전환 원칙:

- 신규 코드는 `DtamClient`를 직접 쓰지 않는다.
- `send("4001", dict)`는 임시 호환 경로로만 사용한다.
- 최종적으로는 `dtam_client.schema.MsgXXXX_*` dataclass를 사용한다.
- callback은 `@on_receive("MID")`로 명시한다.
- role별 수신 mid는 `policy.py`의 `FORWARD_RULES`와 `role_modules.py` stub이 일치해야 한다.

## 역할과 forwarding 정책

ServerRevision 기준 역할:

| role | source | 의미 |
|---|---|---|
| `mission` | `DTAM_MissionPlanner` | 비행계획 생성, 3001/3002/3003 발행 |
| `monitoring` | `DTAMOperationsConsole` | 운영 콘솔, 0001/0002/4001/4101 수신 |
| `vehicle` | `DTAMAirMobility` | 비행체 시뮬레이션, 4001 발행 |
| `visual` | `DTAMVisualization` | Unreal/AirSim 시각화 |
| `sim_state` | `DTAM_SimulationState` | data plane 내부 역할 |

ServerRevision `FORWARD_RULES` 기준:

| MID | 이름 | target role |
|---|---|---|
| `0001` | Module Setting Info | monitoring |
| `0002` | Module Status | monitoring |
| `0003` | Common Time Info | vehicle, visual |
| `1001` | Sim Mode Setup | sim_state |
| `1002` | Simulation Setup | vehicle, visual, sim_state |
| `1003` | Scenario Setup | sim_state, visual |
| `2001` | Flight Plan Request | mission |
| `2002` | DTAM Execute | mission, monitoring, vehicle, visual |
| `3001` | Scheduled Flight | vehicle, visual |
| `3002` | Strategic Separation | vehicle |
| `3003` | Tactical Separation | vehicle |
| `4001` | Vehicle Status | monitoring, visual |
| `4101` | Camera Image Frame | monitoring |
| `5001` | Operator Control Input | vehicle |
| `5002` | Camera Control Command | visual |

주의할 점:

- legacy `DTAM_ServerEmulator`에는 `0001`, `0002`, `1001`, `1003`, `sim_state` forwarding 개념이 약했다.
- 현행 구현에서는 `DTAM_SDK/dtam_client/policy.py`를 forwarding 단일 원천으로 삼고, CoreServer `model/message.py`는 SDK policy에서 `FORWARD_RULES`를 파생한다.
- 새 ICD를 추가할 때는 SDK `policy.py`와 role base stub을 먼저 갱신하고, 서버는 해당 정책을 import해 동일한 forwarding 결과를 사용한다.

## 현재 기능 중 반드시 보존할 것

현재 프로젝트가 ServerRevision보다 앞선 기능들이다. 이 기능들은 구조 전환 중 빠지면 안 된다.

### Operations Console

보존 대상:

- module dashboard와 plugin page.
- operational environment editor/service.
- module start/stop/open GUI UX.
- DTAM 실행 준비 workflow.
- Unreal/AirSim 설정 자동 생성.
- 다중 기체 vehicle map 생성.
- mission guide JSON 생성.
- 4001 지도 시각화, UAM marker, track line.
- commercial traffic overlay.
- mission route overlay.

현재 주요 파일:

- `DTAMOperationsConsole/backend/app/services/module_process_service.py`
- `DTAMOperationsConsole/backend/app/services/dtam_execution_service.py`
- `DTAMOperationsConsole/backend/app/services/dtam_sdk_service.py`
- `DTAMOperationsConsole/backend/app/services/vehicle_status_service.py`
- `DTAMOperationsConsole/backend/app/services/operational_environment.py`
- `DTAMOperationsConsole/frontend/static/js/features/modules/plugin.js`
- `DTAMOperationsConsole/frontend/static/js/features/simulation/simulation-workspace.js`

ServerRevision 구조로 옮길 때:

- `backend/app`은 `app`으로 이동.
- `frontend/static`, `frontend/templates`는 `web`으로 이동.
- `dtam_sdk_service.py`는 `comm.py` 스타일 REST facade로 재작성.
- `module_process_service.py`의 process ownership은 CoreServer로 이동.
- `vehicle_status_service.py`는 `MonitoringService(MonitoringModule)`의 `on_vehicle_status`로 재작성하거나 SimulationState `/api/state`/`/ws/events`에서 가져오게 변경.
- `dtam_execution_service.py`는 남기되 모듈 start/stop은 CoreServer API로 호출해야 한다.

### Mission Planner

보존 대상:

- 현재 route planner UI와 map/DEM/tiles.
- mission ICD export.
- scenario 기반 `2001 -> 3001` 자동 생성.
- 다중 mission/fleet payload 처리.
- 현재 Operations Console과 연계되는 mission route/mission guide용 payload.

현재 주요 파일:

- `DTAM_MissionPlanner/app/server.py`
- `DTAM_MissionPlanner/app/route_planner.py`
- `DTAM_MissionPlanner/app/mission_icd_export.py`
- `DTAM_MissionPlanner/app/dtam_sender.py`

ServerRevision 구조로 옮길 때:

- `app/server.py`의 route, tiles, settings, converter endpoint는 `app/routes/*`로 분리.
- route planner와 converter logic은 `app/domain` 또는 `app/services`로 분리.
- `dtam_sender.py`의 `DtamClient` 사용은 제거하고 `MissionService(MissionModule)`로 통합.
- `MissionService.on_flight_plan_request(2001)`가 3001을 발행한다.
- 3001 발행은 최종적으로 `Msg3001_ScheduledFlight` dataclass를 사용한다.

### Air Mobility

보존 대상:

- 현재 30 Hz simpleDynamics 기반 시뮬레이션.
- manual/keyboard/joystick control.
- `ControlMode`: mission, keyboard, joystick.
- visualization vehicle sync.
- `odt_pose_frame` 기반 AirSim pose frame 보정.
- tactical/strategic separation 명령 처리.
- AirMobility backend UI와 status API.
- Operations Console 직접 fallback으로 쓰던 `/api/status`.

현재 주요 파일:

- `DTAMAirMobility/service/integrated_service.py`
- `DTAMAirMobility/service/manual_dynamics.py`
- `DTAMAirMobility/service/global_keyboard_capture.py`
- `DTAMAirMobility/service/global_joystick_capture.py`
- `DTAMAirMobility/publisher/publisher.py`
- `DTAMAirMobility/publisher/msg4001.py`
- `DTAMAirMobility/transform/odt_pose_frame.py`
- `DTAMAirMobility/backend/app.py`

ServerRevision 구조로 옮길 때:

- `simpleDynamics`는 `app/domain/dynamics`로 이동.
- `transform`은 `app/domain/transform`로 이동.
- `service/integrated_service.py`는 `app/services/integrated_service.py`로 이동하고 `VehicleModule`을 상속하도록 변경.
- `publisher/publisher.py`는 제거 대상이다. WebSocket SDK가 전송을 담당한다.
- `publisher/msg4001.py`는 `app/services/msg4001.py`로 이동하거나 SDK dataclass builder로 흡수한다.
- 현재 4001 30 Hz와 ServerRevision 10 Hz 충돌은 결정해야 한다. 기준은 ServerRevision 10 Hz이며, 현재 고주사율이 필요하면 `DTAM_4001_HZ` 같은 config로만 허용한다.
- 기존 Operations Console fallback `/api/status`는 migration 중 유지할 수 있지만 최종 UI는 SimulationState의 4001 stream을 기준으로 한다.

### Visualization

보존 대상:

- 현재 `DTAMVisualization/vm_app` AirSim/Unreal manager.
- Unreal launch/connect/disconnect.
- vehicle map patch.
- AirSim vehicle catalog.
- camera control.
- 4101 camera image stream.
- 4001 기반 `simSetVehiclePose`.
- Unreal mission guide actor, `mission_guides.json`, U key toggle.
- Unreal source project and build workflow.

현재 주요 파일:

- `DTAMVisualization/VM_main.py`
- `DTAMVisualization/vm_app/server.py`
- `DTAMVisualization/vm_app/manager.py`
- `DTAMVisualization/vm_app/dtam_io.py`
- `DTAMVisualization/vm_app/airsim_bridge.py`
- `DTAMVisualization/Unreal/Environments/DTAMVisualization/Source/DTAMVisualization/DTAMVisualizationMissionGuideActor.*`

ServerRevision 구조로 옮길 때:

- ServerRevision의 `DTAMVisualizationModule`은 packaged executable 중심이다.
- 현재 Python bridge는 없애면 기능 손실이 크다.
- 최종 구조는 둘 중 하나로 결정해야 한다.
  - 선택 A: `DTAMVisualizationModule`은 packaged runtime만 담당하고, 개발용 source bridge는 `DTAMVisualization`에 별도 유지.
  - 선택 B: 현재 `vm_app`을 `DTAMVisualizationModule/app`으로 이동하고 `VisualModule` WebSocket adapter를 붙인다.
- 사용자 요청 기준으로는 “모듈 구조도 ServerRevision을 따른다”가 우선이므로 선택 B를 권장한다.
- Unreal packaged output은 `DTAMVisualizationModule/DTAMVisualization.exe` 형태로 배치하되, source build는 `DTAMVisualization/Unreal/...`에 계속 유지할 수 있다.

## 폴더 구조 전환 매핑

| 현재 | ServerRevision 기준 위치 | 처리 |
|---|---|---|
| `DTAM_ServerEmulator` | `DTAM_CoreServer` + `DTAM_SimulationState` | 기능 분리, 기존은 legacy로 격하 |
| `DTAMOperationsConsole/backend/app` | `DTAMOperationsConsole/app` | 이동 및 import 경로 수정 |
| `DTAMOperationsConsole/frontend` | `DTAMOperationsConsole/web` | 이동 및 StaticFiles/Jinja 경로 수정 |
| `DTAM_MissionPlanner/app/*.py` | `DTAM_MissionPlanner/app/domain`, `app/services`, `app/routes` | 역할별 분리 |
| `DTAM_MissionPlanner/app/web` | `DTAM_MissionPlanner/web` | 정적/템플릿 이동 |
| `DTAMAirMobility/simpleDynamics` | `DTAMAirMobility/app/domain/dynamics` | 이동 |
| `DTAMAirMobility/transform` | `DTAMAirMobility/app/domain/transform` | 이동 |
| `DTAMAirMobility/service` | `DTAMAirMobility/app/services` | 이동 및 SDK 변경 |
| `DTAMAirMobility/publisher` | `DTAMAirMobility/app/services` 또는 SDK dataclass builder | `DtamClient` 제거 |
| `DTAMAirMobility/backend`, `frontend` | `DTAMAirMobility/app`, `web` | 구조 통일 |
| `DTAMVisualization/vm_app` | `DTAMVisualizationModule/app` 권장 | VisualModule adapter 추가 |
| `DTAMVisualization/Unreal/...` | `DTAMVisualizationModule` packaged output + source 유지 | runtime/source 분리 |

## 통신 흐름 전환

### 현재 흐름

```text
Operations Console
  -> DTAM_SDK DtamClient
  -> UDP/TCP DTAM_ServerEmulator 17000/17001
  -> role별 IP/port forwarding
  -> module DtamListener
```

### 목표 흐름

```text
Operations Console
  -> DtamRest POST /api/msg/{mid}
  -> DTAM_SimulationState 8096
  -> /ws/dtam role forwarding
  -> module DtamModule
```

### 대표 workflow

1. 운영자가 Operations Console에서 simulation mode를 설정한다.
2. Operations Console은 `DtamRest.push("1001", payload)` 또는 State REST `POST /api/msg/1001`을 호출한다.
3. SimulationState가 `1001`을 수신하고 `2001 Flight Plan Request`를 Mission Planner로 자동 발행한다.
4. Mission Planner는 `MissionModule.on_flight_plan_request`에서 mission ICD를 만들고 `3001 Scheduled Flight`를 송신한다.
5. SimulationState가 `3001`을 VehicleModule로 forward한다.
6. Air Mobility는 `VehicleModule.on_scheduled_flight`에서 flight plan을 등록한다.
7. 운영자가 play 또는 execute를 누르면 `1002` 또는 `2002`가 State를 통해 각 모듈에 전달된다.
8. SimulationState clock이 `0003`을 Vehicle/Visual에 1 Hz로 전달한다.
9. Air Mobility가 `4001`을 발행한다.
10. SimulationState가 `4001`을 Monitoring/Visual로 forward한다.
11. Operations Console은 4001을 표시하고, Visualization은 Unreal/AirSim pose를 갱신한다.

## 구현 단계

### Phase 0 - 기준 고정

목표:

- ServerRevision 구조를 기준으로 삼는다는 결정을 코드와 문서에 명시한다.
- 현재 구조는 legacy로 표기한다.

작업:

- `docs/serverrevision_migration_plan.md` 유지.
- `README.md` 또는 root docs index에서 본 문서를 링크.
- ServerRevision의 깨진 한글 주석/문서 인코딩 문제는 복사하지 말고, 새 문서는 UTF-8로 다시 작성.
- `4001` rate 정책 결정: 기본은 ServerRevision의 10 Hz. 현재 30 Hz는 config option으로만 유지.

완료 기준:

- 팀 문서에서 “최종 서버는 CoreServer + SimulationState”라고 명확히 확인 가능.

### Phase 1 - SDK 교체 기반

목표:

- `DTAM_SDK`를 ServerRevision SDK 구조로 교체한다.
- 현재 message schema 중 필요한 필드와 helper를 ServerRevision schema로 통합한다.

작업:

- ServerRevision의 `dtam_client/catalog.py`, `identity.py`, `policy.py`, `module.py`, `role_modules.py`, `rest.py`, `_ws_client.py`, `schema`를 현재 `DTAM_SDK`에 도입.
- current `DtamClient`는 `legacy_udp_tcp` namespace 또는 `dtam_client_legacy`로 격리한다.
- `dtam_client.__init__`의 public API를 ServerRevision 기준으로 변경.
- `set_strict_dataclass(False)`를 migration default로 두고, 새 코드부터 dataclass send를 사용.
- 기존 코드에서 `from dtam_client import DtamClient`를 쓰는 위치를 목록화한다.

수정 대상 예시:

```text
DTAMOperationsConsole/backend/app/services/dtam_sdk_service.py
DTAMOperationsConsole/backend/app/services/vehicle_status_service.py
DTAM_MissionPlanner/app/dtam_sender.py
DTAMAirMobility/publisher/publisher.py
DTAMVisualization/vm_app/dtam_io.py
DTAM_ServerEmulator/app/hub.py
```

완료 기준:

- 새 SDK import가 가능하다.
- `MissionModule`, `VehicleModule`, `MonitoringModule`, `VisualModule` import가 가능하다.
- `subscriptions_for(role)` 결과와 role base stub이 일치한다.

### Phase 2 - 서버 분리

목표:

- `DTAM_ServerEmulator` 기능을 CoreServer와 SimulationState로 분리한다.

작업:

- `DTAM_CoreServer`를 현재 root에 도입.
- `DTAM_SimulationState`를 현재 root에 도입.
- `DTAM_ServerEmulator/app/config.py`의 `MESSAGE_TABLE`, `FORWARD_RULES`, `DB_FOLDER_FOR_MID`를 ServerRevision model로 이동 또는 폐기.
- `DTAM_ServerEmulator/app/hub.py`의 DB 저장, forwarding, traffic event 기능을 `DTAM_SimulationState/app/services/hub.py`로 통합.
- `DTAM_ServerEmulator/app/server.py`의 live monitor 기능은 SimulationState로 이동.
- CoreServer에는 process control과 ICD docs만 둔다.

현재 기능 보존:

- DB folder open.
- latest message lookup.
- live traffic monitor.
- sequence diagram.
- camera stream endpoint.

완료 기준:

- `python DTAM_CoreServer/DSE_main.py`가 CoreServer를 띄우고 SimulationState를 자동 실행한다.
- `http://127.0.0.1:8095`는 control plane이다.
- `http://127.0.0.1:8096`은 live monitor/data plane이다.
- `/ws/dtam` 연결이 가능하다.

### Phase 3 - Operations Console 포팅

목표:

- Operations Console을 ServerRevision 구조로 옮기되 현재 기능을 유지한다.

작업:

- `backend/app` -> `app`.
- `frontend/static`, `frontend/templates` -> `web`.
- `backend.app.*` import를 `app.*`로 변경.
- `app/server.py`는 lifespan에서 `MonitoringService(MonitoringModule)`를 시작한다.
- `dtam_sdk_service.py`를 `app/comm.py` 형태로 재작성한다.
- ICD send는 State REST `/api/msg/{mid}`로 보낸다.
- module process control은 Core REST `/api/v1/process/{role}/{start|stop}`로 보낸다.
- current `module_process_service.py`는 CoreServer process router로 옮기거나 삭제한다.
- `vehicle_status_service.py`는 `MonitoringService.on_vehicle_status` 캐시로 재작성한다.
- `dtam_execution_service.py`는 다음 호출 대상을 바꾼다.
  - server start -> CoreServer process API.
  - mission/airmobility/visualization start -> CoreServer process API.
  - ICD send -> SimulationState REST.
  - 4001 read -> MonitoringService cache 또는 State `/api/state`.

보존 기능:

- plugin page.
- operational environment editor.
- UAM marker/track/route overlay.
- Unreal mission guide JSON 생성.
- module dashboard.

완료 기준:

- Operations Console이 UDP/TCP server target 없이도 실행된다.
- `1001/1002/1003/2001/2002` send가 `/api/msg/{mid}`로 작동한다.
- 4001 지도 표시가 MonitoringModule 기반으로 작동한다.

### Phase 4 - Mission Planner 포팅

목표:

- Mission Planner를 `MissionModule` 기반으로 전환한다.

작업:

- ServerRevision `MissionService`를 기준으로 현재 `dtam_sender.py` 기능을 통합한다.
- 현재 `server.py`의 endpoint를 `app/routes/*`로 분리한다.
- route planner, DEM, tiles, converter는 `app/domain`과 `app/services`로 재배치한다.
- 2001 수신 handler에서 현재 자동 mission ICD export와 3001 발행 로직을 유지한다.
- `send_scheduled_flight`는 dataclass 기반으로 바꾼다.

완료 기준:

- Mission Planner가 `/ws/dtam`에 `mission` role로 등록된다.
- `2001`을 받으면 `3001`을 State로 송신한다.
- 기존 route UI와 ICD export API가 동작한다.

### Phase 5 - Air Mobility 포팅

목표:

- Air Mobility를 `VehicleModule` 기반으로 전환한다.

작업:

- 현재 `IntegratedAirMobilityService`를 `VehicleModule` 상속 구조로 변경.
- `DtamVehiclePublisher` 제거 또는 legacy adapter화.
- 수신 handler 전환:
  - `on_common_time_info(0003)`
  - `on_simulation_setup(1002)`
  - `on_dtam_execute(2002)`
  - `on_scheduled_flight(3001)`
  - `on_strategic_separation(3002)`
  - `on_tactical_separation(3003)`
- 4001 publish는 `self.send(Msg4001_VehicleStatus(...))`로 변경.
- manual/keyboard/joystick capture는 유지.
- visualization sync REST는 유지하되, 최종적으로 VisualModule/WebSocket 기반으로 연결 가능한지 별도 검토.

완료 기준:

- Air Mobility가 `/ws/dtam`에 `vehicle` role로 등록된다.
- `3001` 수신 후 vehicle session이 생성된다.
- `0003` clock에 맞춰 4001이 발행된다.
- manual mode와 joystick/keyboard mode가 보존된다.

### Phase 6 - Visualization 포팅

목표:

- Visualization을 ServerRevision 모듈 구조로 맞추면서 현재 AirSim/Unreal bridge 기능을 보존한다.

권장 구조:

```text
DTAMVisualizationModule/
  app/
    server.py
    services/
      visual_service.py
      airsim_bridge.py
      manager.py
      mission_guide.py
  web/
  Config/
  Data/
  run.bat
  DTAMVisualization.exe
```

작업:

- 현재 `DTAMVisualization/vm_app`을 `DTAMVisualizationModule/app`로 포팅.
- `dtam_io.py`의 `DtamClient` 수신/송신을 `VisualModule`로 변경.
- 수신 handler 전환:
  - `0003`
  - `1002`
  - `2002`
  - `4001`
- `4001` 수신 시 AirSim pose update 유지.
- `4101` 송신이 필요하면 WebSocket `image_b64` 경로로 구현.
- Unreal mission guide 파일 경로를 `DTAMVisualizationModule/Data` 또는 Unreal project `Data`로 명확히 정의.
- packaged exe와 source build의 위치를 문서상 분리한다.

완료 기준:

- Visual module이 `/ws/dtam`에 `visual` role로 등록된다.
- 4001 수신으로 Unreal/AirSim 기체 pose가 갱신된다.
- mission guide line 기능이 유지된다.
- packaged 실행과 개발 실행 절차가 각각 문서화된다.

### Phase 7 - 통합 검증

목표:

- ServerRevision 구조에서 현재 workflow가 end-to-end로 돌아간다.

검증 항목:

- Start:
  - `Start_DTAM.py` 실행.
  - CoreServer `8095` 확인.
  - SimulationState `8096` 확인.
  - Operations Console `8000` 확인.
- WebSocket:
  - Mission role registered.
  - Vehicle role registered.
  - Monitoring role registered.
  - Visual role registered.
- Flow:
  - `1001` -> State -> auto `2001` -> Mission.
  - Mission -> `3001` -> Vehicle.
  - `1002 play` -> State clock start -> `0003`.
  - Vehicle -> `4001` -> Monitoring/Visual.
  - Monitoring UI map marker update.
  - Visual pose update.
- DB:
  - `1001`, `1002`, `2001`, `3001`, `4001` 저장 확인.
- UI:
  - Operations Console simulation workspace.
  - Mission Planner route/ICD export.
  - Air Mobility status/manual control.
  - Visualization AirSim vehicle map/camera.

## 구체적인 코드 변경 목록

### Root

- `Start_DTAM.py`
  - 현재: Operations Console만 시작.
  - 변경: ServerRevision처럼 CoreServer와 Operations Console을 시작.
  - CoreServer가 SimulationState를 자동 시작하므로 root launcher는 State를 직접 시작하지 않는다.

### `DTAM_SDK`

- ServerRevision SDK를 기준으로 재배치.
- current `DtamClient`는 legacy namespace로 이동.
- schema dataclass와 sample payload를 정리.
- `NEW_MESSAGE_PROMPT.md`를 ServerRevision 기준으로 갱신.
- Korean/English ICD docs는 유지하되 encoding 깨짐 여부를 검토한다.

### `DTAM_CoreServer`

- 현재 root에 신규 도입.
- process router에는 current module process 관리 기능을 흡수한다.
- ServerRevision의 process router는 단순하므로 현재 `module_process_service.py`의 장점도 가져와야 한다.
  - runtime pid tracking.
  - logs.
  - hidden subprocess.
  - port readiness wait.
  - robust stop by PID/port/process marker.
- 단, Operations Console이 직접 process를 소유하지 않게 한다.

### `DTAM_SimulationState`

- 현재 `DTAM_ServerEmulator`의 다음 기능을 이관한다.
  - file DB.
  - live traffic event.
  - latest message lookup.
  - sequence diagram.
  - camera frame stream.
- `/ws/dtam`을 단일 data plane으로 유지.
- REST push는 `/api/msg/{mid}`만 공식 경로로 둔다.

### `DTAMOperationsConsole`

- ServerRevision folder structure로 변경.
- `app/comm.py`를 중심 facade로 사용.
- `app/services/monitoring_service.py`에서 4001/4101 수신 캐시를 구현한다.
- current advanced UI는 그대로 이동한다.
- module management UI는 CoreServer process API와 연결한다.
- `dtam_execution_service.py`는 Core/State/Module REST 조합으로 재작성한다.

### `DTAM_MissionPlanner`

- ServerRevision의 `MissionService(MissionModule)` 구조 사용.
- current route planner와 mission ICD export 기능을 service/domain으로 유지.
- `dtam_sender.py`는 제거하고 `MissionService`로 통합한다.

### `DTAMAirMobility`

- `IntegratedAirMobilityService`가 `VehicleModule`을 상속한다.
- `publisher` package는 제거 또는 legacy 처리.
- manual control과 visualization sync는 유지한다.
- 4001 rate는 config로 둔다. 기본값은 10 Hz.

### `DTAMVisualizationModule`

- current `DTAMVisualization/vm_app`을 포팅한다.
- `VisualModule` 기반 WebSocket adapter를 추가한다.
- Unreal packaged runtime과 source project를 분리 문서화한다.

## 리스크와 결정 필요 사항

### 1. 4001 주기 충돌

- 현재: `DTAMAirMobility` 30 Hz.
- ServerRevision: 10 Hz.
- 결정: 기준은 10 Hz. 고주사율 필요 시 config option으로 허용.

### 2. Visualization 구조

- ServerRevision은 packaged executable 중심.
- 현재는 Python manager와 Unreal source 기능이 많다.
- 결정 필요: `DTAMVisualizationModule`에 Python bridge를 포함할지, packaged runtime만 둘지.
- 권장: Python bridge 포함. 그래야 AirSim/Unreal 제어 기능을 잃지 않는다.

### 3. Operations Console process ownership

- 현재: Operations Console이 모든 module process를 직접 관리.
- ServerRevision: CoreServer가 process control 담당.
- 결정: 최종은 CoreServer ownership. Operations Console은 REST facade만.

### 4. SDK legacy 지원 기간

- 바로 교체하면 현재 모듈이 모두 깨진다.
- 결정: 현행 런타임에서는 legacy UDP/TCP adapter를 보존하지 않는다.
- DTAM ICD는 `SimulationState /ws/dtam` 단일 data plane만 사용한다. GUI REST와 AirSim RPC는 ICD 경로가 아닌 예외로만 유지한다.

### 5. Encoding 문제

- ServerRevision의 일부 한글 주석과 README는 mojibake가 있다.
- 결정: 문서를 그대로 복사하지 않는다. 새 문서는 UTF-8로 재작성한다.

### 6. 중복 message policy

- ServerRevision에는 SDK `policy.py`와 CoreServer `model/message.py` 양쪽에 forwarding 정보가 있다.
- 결정: SDK policy를 기준으로 삼고, server startup test에서 두 정의의 drift를 잡는다.

## 테스트 계획

### 단위 테스트

- SDK:
  - `subscriptions_for(role)` 결과 검증.
  - role base stub과 policy 일치 검증.
  - dataclass -> wire dict 변환 검증.
  - legacy `send(mid, dict)` warning 검증.
- SimulationState:
  - register protocol.
  - invalid role reject.
  - message forward.
  - 4101 image_b64 decode.
  - DB write.
- CoreServer:
  - process start/stop.
  - SimulationState auto start.

### 통합 테스트

- `test_all_modules.py`를 ServerRevision 기준으로 현재 root에 맞게 조정.
- Mission Planner, Air Mobility, Operations Console, Visualization이 모두 `/ws/dtam`에 등록되는지 확인.
- `1001 -> 2001 -> 3001 -> 4001` flow 확인.
- Operations Console map 4001 표시 확인.
- Visualization 4001 pose update 확인.

### 수동 검증

- `Start_DTAM.py` 실행.
- `http://127.0.0.1:8095/docs` 확인.
- `http://127.0.0.1:8096/docs` 확인.
- `http://127.0.0.1:8096/docs/websocket` 확인.
- `http://127.0.0.1:8000` Operations Console 확인.
- Module start buttons가 CoreServer API를 통해 동작하는지 확인.

## 최종 산출물 체크리스트

- `DTAM_CoreServer`가 root에 존재한다.
- `DTAM_SimulationState`가 root에 존재한다.
- `DTAM_ServerEmulator`는 legacy 또는 제거 대상이 명확하다.
- `DTAM_SDK` public API가 ServerRevision 기준이다.
- 모든 Python module이 `app/`, `web/`, `resources/`, `data/` 구조를 따른다.
- Operations Console이 직접 UDP/TCP SDK를 호출하지 않는다.
- Mission Planner가 `MissionModule`을 사용한다.
- Air Mobility가 `VehicleModule`을 사용한다.
- Operations Console이 `MonitoringModule`을 사용한다.
- Visualization이 `VisualModule` 또는 명확한 packaged adapter를 가진다.
- 1001/1002/2001/2002/3001/4001/4101 flow가 SimulationState를 통해 흐른다.
- DB 저장 주체는 SimulationState다.
- module process control 주체는 CoreServer다.
- 현재 프로젝트의 advanced 기능 목록이 새 구조에서 누락되지 않았다.

## 결론

전환의 본질은 서버명 교체가 아니라 통신 중심축의 교체다. 현재 프로젝트는 `Operations Console + DTAM_ServerEmulator + UDP/TCP SDK`로 동작하고 있지만, 목표는 `CoreServer + SimulationState + WebSocket SDK`다. 따라서 구현 순서는 SDK와 서버 data plane을 먼저 고정하고, 그다음 각 모듈의 앞선 기능을 새 role module 구조로 이식하는 것이 가장 안전하다.

가장 위험한 지점은 Air Mobility와 Visualization이다. Air Mobility는 기능이 많이 앞서 있고, Visualization은 ServerRevision의 packaged runtime보다 현재 Python bridge가 훨씬 많은 제어 기능을 갖고 있다. 이 두 모듈은 구조만 ServerRevision을 따르고 기능은 현재 프로젝트 것을 적극적으로 보존해야 한다.
## Final review addendum (2026-04-28)

### Communication fixes applied

- `sim_state` is now treated as a local SimulationState sink, not as a WebSocket client that must register on `/ws/dtam`.
- WebSocket unregister now checks the actual socket instance, preventing an older reconnecting socket from removing a newer registered socket for the same role.
- REST push `/api/msg/{mid}` now normalizes payloads through the SDK schema path and rejects non-object payloads with HTTP 422.
- CoreServer no longer fakes module heartbeats from `Popen` liveness. Registry connectivity now reflects module SDK/WebSocket heartbeat instead of only child process existence.
- CoreServer checks whether SimulationState `:8096` is already healthy before spawning it and waits for readiness after spawning.
- Server and SDK forwarding policies are synchronized. `1003` now reaches `visual` for scenario/vehicle mapping, and `3001` reaches `visual` for mission guide rendering as well as `vehicle`.

### GUI and resource fixes applied

- Operations Console module management JS was restored to valid JavaScript and now calls the ServerRevision lifecycle endpoints: `/api/v1/system/modules`, `/run`, `/stop`, and `/{module}/open-gui`.
- Operations Console resource files were restored from the pre-migration backup, including the real `korea.mbtiles`, `kada.png`, and `Kp2c.png`.
- Mission Planner now uses the real `korea.mbtiles` database instead of the Git LFS pointer file.
- Air Mobility GUI JS was rewritten against the current REST API, including WebSocket publisher configuration, manual vehicle config, keyboard capture, joystick capture, release, clock/service controls, and status rendering.
- Visualization GUI HTML/JS was restored to valid assets for the 8097 FastAPI GUI.
- `DTAMVisualizationModule/run.bat` now launches the real Unreal executable under `DTAMVisualization/Unreal/.../Binaries/Win64` when present instead of the LFS pointer executable in the module folder.

### Verification run

- Python compileall passed for `Start_DTAM.py`, `DTAM_CoreServer`, `DTAM_SimulationState`, `DTAM_SDK`, `DTAMOperationsConsole`, `DTAM_MissionPlanner`, `DTAMAirMobility`, and `DTAMVisualization`.
- Node syntax checks passed for Operations Console, Visualization, and Air Mobility browser JavaScript.
- FastAPI import smoke passed for CoreServer, SimulationState, Operations Console, Air Mobility, Mission Planner, and Visualization.
- Communication smoke passed:
  - `3001` sent from `mission` was received by both `vehicle` and `visual`.
  - REST `1003` sent through SimulationState was forwarded to `visual` and the local `sim_state` sink.
  - Non-object REST payloads are rejected with HTTP 422.
- Endpoint smoke passed for:
  - Operations Console `GET /api/v1/system/modules`
  - Air Mobility `GET /api/status`
  - Mission Planner `GET /api/converter/settings`

## Final correction addendum (2026-04-28)

### Additional issues found during the final subagent review pass

- Air Mobility already computed ODT pose-frame projection metadata, but automatic 4001 publishing did not pass that metadata into `build_vehicle_payload`. The automatic mission tick now forwards `poseFrame` into the 4001 vehicle payload.
- Visualization imported `cosysairsim` at module import time. On hosts without the AirSim Python SDK, the whole Visualization GUI server failed to import. The AirSim bridge now keeps the GUI/DTAM bridge importable and reports the missing SDK only when AirSim connection is attempted.
- REST push validation still had one wrapper edge case: `{"payload": []}` was converted to `{}` because the old code used `or {}`. The handler now preserves the raw wrapper payload and rejects non-object payloads with HTTP 422.

### Final verification after corrections

- Python compile checks passed for changed files and the full migrated module set.
- Browser JavaScript syntax passed for Operations Console, Air Mobility, and Visualization using the bundled Node runtime.
- Import smoke passed for CoreServer, SimulationState, Air Mobility, Visualization, Operations Console, and Mission Planner with the expected SDK/module roots on `PYTHONPATH`.
- Communication smoke passed:
  - `mission` sent `3001`; both `vehicle` and `visual` received it.
  - REST `1003` returned targets `["sim_state", "visual"]`; `visual` received it and SimulationState consumed the local sink path.
  - Invalid REST wrapper payload `{"payload": []}` returned HTTP 422.
- Endpoint smoke passed for:
  - Operations Console `GET /api/v1/system/modules`
  - Air Mobility `GET /api/status`
  - Mission Planner `GET /api/converter/settings`
  - Visualization `GET /api/state`

## Final legacy-behavior parity review (2026-05-01)

Goal: keep the behavior from `.dtam_migration_backup/pre_serverrevision_20260428_210640`
and replace only the transport and module orchestration path with the ServerRevision
SDK/CoreServer/SimulationState structure.

### Current communication path

- Operations Console sends operator/user ICD messages through `DtamRest` to
  `DTAM_SimulationState` `POST /api/msg/{mid}`.
- Mission Planner, Air Mobility, Operations Console monitoring, and Visualization use
  role-based WebSocket clients on `ws://<host>:8096/ws/dtam`.
- CoreServer owns module process start/stop through
  `POST /api/v1/process/{role}/{start|stop}` and passes `--target-ip` plus
  `--ws-port` to modules.
- No active legacy `DtamClient`, UDP socket, TCP listener, `17000/17010/17020/17030`
  module-port path remains in the current runtime modules. Remaining socket usage is
  limited to port availability checks and external AirSim RPC readiness.

### Legacy behavior preserved through new transport

- Mission Planner route planner, coordinate transform, and mission ICD export logic are
  byte-equivalent to the backup except for import-path relocation and WebSocket settings
  UI/API changes.
- Mission Planner `2001 -> auto 3001` is now implemented in
  `MissionService(MissionModule)` and still uses the existing route/ICD bundle helpers.
- Air Mobility dynamics, keyboard capture, joystick capture, manual dynamics, ODT pose
  frame, and 4001 payload builder are preserved; `IntegratedAirMobilityService` now
  inherits `VehicleModule` and publishes/receives through SDK WebSocket.
- Operations Console GUI and feature code remain on the restored backup UI path; DTAM
  send/process/status facades are the changed parts.
- 5001 and 5002 were added because keyboard/joystick/camera-control input did not have
  a legacy ICD message. They are documented in SDK KOR/ENG ICD docs and routed as:
  `5001 -> vehicle`, `5002 -> visual`.

### Final correction in this review

- `DTAM_SimulationState/app/routes/push.py` no longer treats empty-role REST pushes as
  if they came from the `monitoring` module. Empty role now represents an external
  `operator` sender. This restores legacy `user->server` behavior where messages such
  as `2002` are forwarded to every configured target, including `monitoring`.

### Verification

- `python -m compileall DTAM_SDK DTAM_CoreServer DTAM_SimulationState DTAMOperationsConsole DTAM_MissionPlanner DTAMAirMobility DTAMVisualization\vm_app`
  passed.
- SDK and server forwarding policies match as target sets.
- `5001` and `5002` sample payloads parse through the SDK schema registry.
- Simulated operator-origin `2002` forwarding reaches `mission`, `monitoring`,
  `vehicle`, and `visual`.
- Air Mobility manual input clamps and applies through the new 5001-compatible path.
