# DTAM Collision Integration 개발 체크리스트

작성일: 2026-05-16  
대상: `VisualizationModule`, `VisualizationModule_Source`, `IntegrationHub`, `DTAMSDK`, `VehicleModule`, `OperationModule`

## 0. 목적

현재 DTAM은 `VehicleModule -> 4001 -> VisualizationModule -> AirSim simSetVehiclePose()` 흐름으로 외부 비행 상태를 Unreal에 시각화한다. 이 구조는 위치를 외부에서 계속 주입하기 때문에 Unreal/AirSim의 충돌 정보가 실제 VehicleModule 상태에 반영되지 않는다.

이 개발의 목표는 다음과 같다.

1. Unreal/AirSim에서 발생한 충돌을 감지한다.
2. 감지된 충돌을 DTAM 서버/SDK ICD로 전달한다.
3. VehicleModule이 충돌 이벤트를 받아 실제 비행 상태/제어 상태에 반영한다.
4. OperationModule/Monitoring에서 충돌 상태를 볼 수 있게 한다.
5. 기존 4001 기반 시각화/수동/오토파일럿 흐름을 깨지 않는다.

---

## 1. 현재 확인된 AirSim Collision 흐름

Subagent 조사 기준 핵심 흐름은 다음과 같다.

```text
AFlyingPawn::NotifyHit
→ PawnEvents / MultirotorPawnEvents CollisionSignal
→ PawnSimApi::onCollision
→ PawnSimApi::state_.collision_info 저장
→ RpcLibServerBase::simGetCollisionInfo
→ Python cosysairsim VehicleClient.simGetCollisionInfo(vehicle_name)
```

주요 파일:

- `D:\DTAMFramework\VisualizationModule_Source\Unreal\Environments\DTAMVisualization\Plugins\AirSim\Source\Vehicles\Multirotor\FlyingPawn.cpp`
- `D:\DTAMFramework\VisualizationModule_Source\Unreal\Environments\DTAMVisualization\Plugins\AirSim\Source\PawnSimApi.cpp`
- `D:\DTAMFramework\VisualizationModule_Source\Unreal\Environments\DTAMVisualization\Plugins\AirSim\Source\AirLib\src\api\RpcLibServerBase.cpp`
- `D:\DTAMFramework\VisualizationModule\runtime\PythonClient\cosysairsim\client.py`

현재 DTAM 측 주요 병목:

- `VisualizationModule\app\adapters\airsim.py`에서 `simSetVehiclePose(pose, ignore_collisions, vehicle_name)` 사용.
- `VisualizationModule\app\config.py`의 기본값이 `ignore_collisions=True`.
- 즉, 외부 pose 주입이 teleport 성격으로 동작하여 Unreal hit/sweep 충돌이 우회될 수 있다.
- 설령 Unreal에서 충돌 반응이 생겨도 VehicleModule이 다음 4001 pose를 다시 밀어 넣으면 물리 반응이 덮인다.

따라서 권장 구조는 다음이다.

```text
Unreal/AirSim = 충돌 감지자
VisualizationModule = 충돌 이벤트 수집/ICD 송신자
IntegrationHub = 충돌 ICD 기록/전달자
VehicleModule = 충돌 반응/비행 상태 권한자
OperationModule = 충돌 상태 표시/운용자 확인 UI
```

---

## 2. 개발 세션 분할 제안

권장 개발 세션 수: **총 6회**

이유:

- Unreal/AirSim 물리 충돌, SDK/ICD, 서버 forwarding, VehicleModule 상태 반영, UI 표시, end-to-end 검증이 서로 다른 위험도를 가진다.
- 한 번에 구현하면 기존 수동/오토파일럿/4001 시각화 흐름을 깨뜨릴 가능성이 높다.
- 특히 `ignore_collisions=False` 전환은 회귀 위험이 크므로, 먼저 이벤트 감지/전달을 안정화한 뒤 별도 세션에서 물리 반영을 실험하는 것이 안전하다.

요약:

| 세션 | 목표 | 산출물 |
|---|---|---|
| 1 | ICD/SDK/Forwarding 기반 준비 | `4103_vehicleCollisionEvent` ICD, SDK catalog/policy, sequence diagram |
| 2 | VisualizationModule 충돌 감지 | AirSim `simGetCollisionInfo()` polling, 내부 이벤트/로그 |
| 3 | 서버 경유 전달 완성 | IntegrationHub forwarding/DB 기록, VM -> 서버 -> VehicleModule 전달 |
| 4 | VehicleModule 충돌 반응 | 4103 수신, hold/stop/emergency 상태 반영, 4001 확장 |
| 5 | Unreal 물리 충돌 모드 검증 | `ignore_collisions` 옵션화, sweep/trace fallback, EXE 반영 |
| 6 | UI/통합 검증/튜닝 | OperationModule 표시, E2E 테스트, 회귀 테스트, 문서 정리 |


### Subagent 검토 메모: 압축형 4세션 대안

Subagent는 최소 개발 단위를 **4회 세션**으로 압축하는 안도 가능하다고 제안했다. 단, 실제 구현 안정성을 고려하면 본 문서의 6세션 계획을 권장하고, 일정이 촉박할 때만 아래처럼 묶어 진행한다.

| 압축 세션 | 포함 범위 | 본 문서 기준 |
|---|---|---|
| A | 현행 충돌/pose 주입 정책 확정, ICD 초안 | Session 1 + 일부 Session 5 |
| B | VisualizationModule 충돌 수집 설계/구현 | Session 2 |
| C | 서버/VehicleModule 전달 및 상태 반영 | Session 3 + Session 4 |
| D | 통합 검증/운영 정책/UI 최소 반영 | Session 5 + Session 6 |

압축형 진행 시에도 반드시 지켜야 하는 검증 포인트:

- [ ] `simGetCollisionInfo()`가 실제 충돌 후 `has_collided=true`를 반환하는지 확인
- [ ] `simGetCollisionInfo()` 호출 후 reset되는 동작 확인
- [ ] AirSim RPC polling이 4001 pose 적용 루프를 막지 않는 구조인지 확인
- [ ] 다중 vehicle에서 vehicle name/aircraftId 매핑이 틀리지 않는지 확인
- [ ] `ignore_collisions=True/False` 비교 테스트 수행
---

## 3. 세션별 상세 체크리스트

### Session 1. ICD / SDK / Forwarding 설계 반영

목표:

- 충돌 이벤트를 DTAM 공식 ICD로 정의한다.
- 모든 모듈이 서버를 통해 충돌 이벤트를 주고받도록 SDK 정책에 반영한다.

개발 대상:

- `D:\DTAMFramework\DTAMSDK\dtam_client\icd\KOR\4103_vehicleCollisionEvent.md`
- `D:\DTAMFramework\DTAMSDK\dtam_client\icd\ENG\4103_vehicleCollisionEvent.md`
- `D:\DTAMFramework\DTAMSDK\dtam_client\catalog.py`
- `D:\DTAMFramework\DTAMSDK\dtam_client\policy.py`
- `D:\DTAMFramework\DTAMSDK\dtam_client\samples.py`
- `D:\DTAMFramework\DTAMSDK\dtam_client\role_modules.py`
- `D:\DTAMFramework\IntegrationHub\StateServerModule\app\web\data\sequence_diagram*.json` 또는 현재 sequence diagram 위치

신규 ICD 권장:

```text
MID: 4103
Name: Vehicle Collision Event
Direction: VisualizationModule -> IntegrationHub -> VehicleModule / Monitoring / SituationAwareness / OperationModule
Rate: event-driven
Transport: WebSocket /ws/dtam JSON
```

권장 payload:

```json
{
  "message_id": 4103,
  "message_name": "Vehicle Collision Event",
  "timestamp": "2026-05-16T15:30:00.000Z",
  "aircraftId": "UAM0001",
  "airsimVehicleName": "Drone1",
  "hasCollided": true,
  "objectName": "ObstacleActor_01",
  "objectId": -1,
  "positionNed": {
    "north": 120.3,
    "east": -55.1,
    "down": -18.2
  },
  "impactPointNed": {
    "north": 120.1,
    "east": -54.9,
    "down": -18.0
  },
  "normalNed": {
    "north": 0.0,
    "east": 0.1,
    "down": -0.99
  },
  "penetrationDepth": 0.25,
  "collisionTimeNanos": 1234567890,
  "severity": "warning",
  "recommendedAction": "hold",
  "source": "airsim.simGetCollisionInfo"
}
```

Forwarding 권장:

```python
"4103": [Role.VEHICLE, Role.MONITORING, Role.SITUATION_AWARENESS]
```

검증 체크리스트:

- [ ] ICD KOR/ENG 문서 추가
- [ ] SDK catalog에 4103 추가
- [ ] SDK sample payload 추가
- [ ] SDK alias 추가: `vehicle_collision_event`, `collision_event`
- [ ] policy forwarding rule 추가
- [ ] VehicleModule base stub에 `on_vehicle_collision_event()` 추가
- [ ] VisualModule outbound 목록 또는 문서에 4103 반영
- [ ] sequence diagram에 `visual -> server -> vehicle/monitoring` 경로 추가
- [ ] SDK import/샘플 생성 테스트 통과

완료 기준:

- `sample_by_mid("4103")` 또는 동등 샘플 API가 정상 동작한다.
- IntegrationHub 문서/다이어그램 기준으로 4103 흐름이 보인다.

---

### Session 2. VisualizationModule 충돌 감지 구현

목표:

- Unreal/AirSim의 기존 `simGetCollisionInfo()`를 이용해 차량별 충돌 이벤트를 수집한다.
- 먼저 서버 전송 전 단계에서 VM 내부 이벤트/로그로 안정성을 검증한다.
- 진행 상태: **구현 완료 / 실제 Unreal 충돌 E2E 현장 확인 대기**  
  - `AirSimBridge.poll_collision_events()`가 AirSim `CollisionInfo`를 4103 payload 형태로 정규화한다.
  - `VisualizationManager`가 별도 polling thread에서 충돌을 감지하고 Live Monitor 이벤트로 남긴다.
  - 이번 Session 2에서는 의도적으로 서버 송신을 하지 않는다. 4103 서버 송신은 Session 3에서 활성화한다.

개발 대상:

- `D:\DTAMFramework\VisualizationModule\app\adapters\airsim.py`
- `D:\DTAMFramework\VisualizationModule\app\services\manager.py`
- `D:\DTAMFramework\VisualizationModule\app\config.py`
- `D:\DTAMFramework\VisualizationModule\data\configs\vm_config.json`

구현 방향:

1. `AirSimBridge`에 차량 목록 기준 collision polling 메서드 추가.
2. `simGetCollisionInfo(vehicle_name)` 호출.
3. `has_collided == true`일 때만 normalize된 dict 반환.
4. 중복 이벤트 억제:
   - `vehicle_name + collisionTimeNanos + objectName` 기준 de-dup.
   - 같은 충돌이 연속으로 들어올 경우 throttle.
5. Manager에 collision polling loop 추가.
6. 내부 HubEvent로 표시.

설정 권장:

```json
"collision": {
  "enabled": true,
  "poll_hz": 10.0,
  "dedup_window_sec": 1.0,
  "publish_to_server": true,
  "publish_no_collision": false,
  "default_recommended_action": "hold"
}
```

검증 체크리스트:

- [x] AirSim 연결 안 됐을 때 polling loop가 조용히 대기
- [x] 차량 0대/1대/N대에서 예외 없이 동작하도록 target snapshot 기반으로 구현
- [x] `simGetCollisionInfo` 미지원/실패 시 VM이 죽지 않음
- [x] 충돌 없을 때 이벤트 폭주 없음
- [x] 충돌 발생 시 VM Live Monitor에 collision 이벤트 표시되는 내부 HubEvent 경로 구현
- [x] 동일 충돌 중복 publish 억제
- [ ] 실제 Unreal 충돌 상황에서 `has_collided=true` 현장 확인

완료 기준:

- Unreal에서 충돌 상황을 만들었을 때 VM 내부 이벤트로 aircraftId, objectName, positionNed가 확인된다.

---

### Session 3. VM -> IntegrationHub -> VehicleModule 전달 완성

목표:

- Session 2에서 수집한 충돌 이벤트를 4103 ICD로 서버에 전송한다.
- IntegrationHub가 DB/Live Monitor/forwarding을 정상 처리한다.
- 진행 상태: **구현 완료 / 실제 Unreal 충돌 E2E 현장 확인 대기**
  - `VisualizationModule` collision loop가 `publish_to_server=true`일 때 4103을 서버로 송신한다.
  - `IntegrationHub`는 4103을 SDK schema로 검증하고 `VehicleCollisionEvent` 폴더에 저장/forwarding한다.
  - `VehicleModule`은 4103을 수신해 최근 충돌 이벤트와 aircraft별 충돌 snapshot을 상태에 저장한다.
  - 실제 비행 hold/stop 반응은 Session 4에서 구현한다.

개발 대상:

- `D:\DTAMFramework\VisualizationModule\app\dtam\io.py`
- `D:\DTAMFramework\VisualizationModule\app\services\manager.py`
- `D:\DTAMFramework\IntegrationHub\StateServerModule\app\services\hub.py` 또는 forwarding 구현 위치
- `D:\DTAMFramework\IntegrationHub\StateServerModule\app\web\data\sequence_diagram*.json`
- `D:\DTAMFramework\VehicleModule\app\server.py`
- `D:\DTAMFramework\VehicleModule\app\services\integrated_service.py`

구현 방향:

1. `DtamIO.send_vehicle_collision_event(payload)` 추가.
2. Manager collision loop에서 4103 송신.
3. IntegrationHub에서 4103 validation/record/forward.
4. VehicleModule에 4103 수신 handler stub 추가.
5. 수신 카운터/최근 충돌 snapshot 표시.

검증 체크리스트:

- [x] VM outbound 4103 송신 카운터 증가 경로 구현
- [x] IntegrationHub Live Monitor에서 4103 수신 가능한 traffic event 경로 확인
- [x] DB 또는 로그에 4103 기록 (`VehicleCollisionEvent`) 확인
- [x] VehicleModule inbound 4103 수신/상태 저장 확인
- [x] 서버 종료/재시작 시 SDK reconnect 경로 유지
- [x] 기존 4001/4101/4102/5001/5002 흐름 회귀를 피하도록 4103은 event-driven으로 유지
- [ ] 실제 Unreal 충돌 발생 → VM 송신 → 서버 → VehicleModule까지 현장 E2E 확인

완료 기준:

- 강제 test payload 또는 실제 collision payload가 서버를 거쳐 VehicleModule까지 도달한다.

---

### Session 4. VehicleModule 충돌 반응 모델 구현

목표:

- VehicleModule이 4103을 받아 실제 비행 상태에 반영한다.
- 충돌 반응은 처음부터 복잡한 물리 반발보다 `hold/stop/emergency` 중심으로 안전하게 시작한다.
- 진행 상태: **구현 완료 / 실제 Unreal 충돌 E2E 현장 확인 대기**
  - `VehicleModule`이 4103 수신 시 `recommendedAction`/`severity`를 `none`, `hold`, `emergency_stop`, `abort`, `clear`로 정규화한다.
  - `hold`, `emergency_stop`, `abort`는 aircraft별 active collision response로 저장된다.
  - Autopilot/mission payload는 마지막 4001 anchor를 재송신하며 속도/가속도를 0으로 만든다.
  - Keyboard/Joystick payload도 동일하게 hold anchor를 재송신하고, active collision 중 operator input은 neutral로 감쇠한다.
  - 4001 per-vehicle payload에 선택 필드 `collision`을 추가했고, SDK 4001 schema가 이 필드를 보존한다.
  - REST clear/resume API: `POST /api/collision/clear`, `POST /api/collision/{vehicle_id}/clear`

개발 대상:

- `D:\DTAMFramework\VehicleModule\app\services\integrated_service.py`
- `D:\DTAMFramework\VehicleModule\app\services\msg4001.py`
- `D:\DTAMFramework\VehicleModule\app\domain\dynamics\*`
- `D:\DTAMFramework\VehicleModule\app\domain\manual_dynamics\*`

권장 반응 단계:

| severity | recommendedAction | VehicleModule 반응 |
|---|---|---|
| info | none | 상태 기록만 |
| warning | hold | 현재 위치 유지, 속도 0으로 감쇠 |
| critical | emergency_stop | 속도/가속도 0, mission pause |
| fatal | abort | 임무 중단/비상 상태 유지 |

4001 확장 권장:

```json
{
  "collision": {
    "active": true,
    "lastEventId": "4103-UAM0001-...",
    "objectName": "ObstacleActor_01",
    "severity": "warning",
    "responseMode": "hold",
    "timestamp": "2026-05-16T15:30:00.000Z"
  }
}
```

검증 체크리스트:

- [x] Autopilot 비행 중 4103 수신 시 hold 가능하도록 4001 anchor freeze 구현
- [x] Keyboard/Joystick 수동 제어 중 4103 수신 시 입력 neutral 감쇠 및 4001 anchor freeze 구현
- [x] 충돌 상태 clear 정책 존재 (`/api/collision/clear`, `/api/collision/{vehicle_id}/clear`)
- [x] mission resume/clear command 설계: active response/hold anchor를 clear하면 기존 clock/plan 진행 구조로 복귀
- [x] 4001에 collision snapshot 반영
- [x] SDK 4001 schema가 `collision` 필드를 보존하도록 확장
- [ ] 실제 Unreal 충돌 E2E에서 다음 4001 속도 0/hold 확인
- [ ] 기존 임무 계획/경로/수동 조작 현장 회귀 확인

완료 기준:

- 4103 수신 후 VehicleModule이 다음 4001에서 속도/상태를 변경한다.
- VisualizationModule에서 그 변경된 4001을 받아 실제 Unreal 표시가 정지/hold된다.

---

### Session 5. Unreal/AirSim 물리 충돌 모드 검증 및 fallback

목표:

- `ignore_collisions=True` 때문에 충돌이 우회되는 문제를 제어 가능한 옵션으로 바꾼다.
- `ignore_collisions=False`가 기존 4001 replay를 깨지 않는지 검증한다.
- 필요 시 trace/overlap 기반 fallback 감지기를 추가한다.
- 진행 상태: **구현 완료 / 실제 Unreal sweep collision 현장 확인 대기**
  - `airsim.ignore_collisions`는 기존 파일 설정에 더해 런타임 API로 변경 가능하다.
  - 신규 API: `GET /api/airsim/collision-mode`, `PATCH /api/airsim/collision-mode`
  - `ignore_collisions=false`일 때 AirSim `simSetVehiclePose(..., sweep)` 경로를 사용한다.
  - Python fallback은 `simGetCollisionInfo()`를 추가 호출하지 않고, `simGetVehiclePose()`의 requested/actual pose 차이를 저주기로 비교한다.
  - pose 차이가 threshold를 넘으면 `4001-pose-feedback` warning event로 표시한다.
  - 신뢰도 높은 blocking hit/trace 결과 노출은 Unreal C++ custom RPC 후보로 남긴다.

개발 대상:

- `D:\DTAMFramework\VisualizationModule\app\config.py`
- `D:\DTAMFramework\VisualizationModule\data\configs\vm_config.json`
- `D:\DTAMFramework\VisualizationModule\app\adapters\airsim.py`
- 필요 시 Unreal C++:
  - `D:\DTAMFramework\VisualizationModule_Source\Unreal\Environments\DTAMVisualization\Plugins\AirSim\Source\PawnSimApi.cpp`
  - `D:\DTAMFramework\VisualizationModule_Source\Unreal\Environments\DTAMVisualization\Plugins\AirSim\Source\Vehicles\Multirotor\FlyingPawn.cpp`

검토할 모드:

1. `ignore_collisions=True`
   - 현재 방식.
   - 가장 안정적이나 충돌 감지가 약함.
2. `ignore_collisions=False`
   - SetActorLocationAndRotation sweep 사용.
   - 충돌 감지 가능성 증가.
   - 빠른 외부 pose update 시 떨림/막힘 가능.
3. Hybrid
   - 평상시 true.
   - 장애물 근접/비정상 상황 구역에서는 false.
   - 또는 별도 trace로 충돌만 감지.
4. Trace fallback
   - 이전 pose -> 새 pose 방향으로 line/sphere trace.
   - Unreal hit 이벤트가 안 떠도 충돌 후보를 감지.

검증 체크리스트:

- [x] `ignore_collisions` 설정을 vm_config에서 바꿀 수 있음
- [x] `ignore_collisions` 런타임 변경 API 구현
- [x] 문자열 `"false"`, `"0"`, `"off"` bool 파싱 보정
- [x] false 모드에서 requested/actual pose feedback 진단 구현
- [ ] false 모드에서 차량이 벽/지면을 통과하지 않는지 실제 Unreal 현장 확인
- [ ] false 모드에서 기존 4001 외부 pose 시각화가 과도하게 끊기지 않음 현장 확인
- [ ] Cesium 지형/건물 collision 존재 여부 확인
- [x] collision mesh가 없는 대상은 Unreal C++ trace/overlap/custom RPC가 필요할 수 있음을 설계상 분리
- [ ] EXE 빌드 및 런타임 반영

완료 기준:

- 최소 1개 collision test scenario에서 AirSim `simGetCollisionInfo()`가 실제로 true를 반환한다.

---

### Session 6. OperationModule UI / End-to-End 검증 / 문서화

목표:

- 운용자가 충돌 상태를 확인하고 clear/resume할 수 있게 한다.
- 전체 DTAM stack에서 회귀 테스트를 수행한다.
- 진행 상태: **구현 완료 / 실제 Unreal 충돌 E2E 현장 확인 대기**
  - `OperationModule` MonitoringService가 4103 `Vehicle Collision Event`를 수신해 운용 콘솔 차량 상태 cache에 기록한다.
  - `GET /api/v1/simulation/vehicle-status` 응답에 `collision_rx_count`, `last_collision_event`, `collisions_by_vehicle`, 차량별 `collision` snapshot이 포함된다.
  - `VehicleModule /api/status` fallback에서도 active collision response를 차량별 `collision`으로 투영한다.
  - `POST /api/v1/simulation/collision/clear`, `POST /api/v1/simulation/collision/{vehicle_id}/clear` OperationModule proxy를 추가했다.
  - 지도 차량 label, popup, 우측 상세 패널, status board에 충돌 상태가 표시되고, 상세/popup에서 `해제 / 재개`를 누르면 VehicleModule clear/resume API로 전달된다.

개발 대상:

- `D:\DTAMFramework\OperationModule\app\web\static\js\features\simulation\simulation-workspace.js`
- `D:\DTAMFramework\OperationModule\app\web\static\css\simulation-workspace.css`
- `D:\DTAMFramework\OperationModule\app\api\routes\simulation.py`
- `D:\DTAMFramework\OperationModule\app\services\vehicle_status_service.py`
- `D:\DTAMFramework\OperationModule\app\services\monitoring_service.py`
- `D:\DTAMFramework\IntegrationHub\StateServerModule\app\web\*`
- 관련 docs

UI 권장:

- 지도 위 비행체 popup에 collision 상태 표시 (**완료**)
- 비정상 상황 대시보드에 최근 충돌 이벤트 목록 표시
- 충돌 aircraft marker 강조 (**label 강조 완료**)
- clear/acknowledge/resume 버튼은 별도 ICD 설계 후 추가 (**이번 세션에서는 OperationModule → VehicleModule REST proxy로 clear/resume 연결**)

E2E 테스트 시나리오:

1. Start_DTAM 실행
2. UAM 모드 선택
3. Mission 계획 및 Play
4. VisualizationModule/AirSim 연결 확인
5. 의도적 collision 발생
6. VM이 4103 송신
7. IntegrationHub에서 4103 forwarding 확인
8. VehicleModule이 hold/stop 반영
9. 다음 4001에서 collision 상태 확인
10. OperationModule UI에서 경고 확인

회귀 테스트:

- [x] OperationModule 4103 cache/API smoke test
- [x] OperationModule Python syntax check
- [x] OperationModule simulation-workspace.js syntax check
- [ ] Autopilot 정상 비행
- [ ] Keyboard 수동 제어 정상
- [ ] Joystick 수동 제어 정상
- [ ] 1/2/3/4/5 view 전환 정상
- [ ] VPO/TestStream 정상
- [ ] DT World M 메뉴 정상
- [ ] Start_DTAM 종료 시 전체 stack cleanup 정상
- [ ] Unreal EXE fatal error 없음

완료 기준:

- 실제 Unreal collision → 4103 → VehicleModule 반응 → 4001 상태 변경 → UI 표시까지 한 번의 시나리오로 확인된다.

---

## 4. 위험 요소 및 대응 방안

| 위험 | 설명 | 대응 |
|---|---|---|
| Unreal collision mesh 부재 | Cesium 지형/건물/일부 asset이 blocking collision을 제공하지 않을 수 있음 | trace/overlap fallback 준비 |
| `ignore_collisions=False` 회귀 | 외부 4001 pose 주입이 sweep에 막혀 떨림/멈춤 가능 | 옵션화, hybrid 모드, 세션 5에서 별도 검증 |
| 이벤트 중복 폭주 | polling 기반 `simGetCollisionInfoAndReset()` 구조라 같은 충돌이 반복될 수 있음 | event id/de-dup/throttle |
| VehicleModule 권한 충돌 | Unreal collision 반응과 VehicleModule 4001 상태 권한이 충돌 | VehicleModule을 최종 상태 권한자로 고정 |
| 기존 수동/오토파일럿 회귀 | collision hold가 입력/미션 상태를 막을 수 있음 | control mode별 정책 명확화, clear/resume 설계 |
| AirSim RPC 실패 | Unreal 미실행/연결 끊김 시 polling 예외 가능 | 예외 흡수, status only, reconnect 후 자동 복구 |
| 성능 저하 | 차량별 10Hz collision polling이 RPC 부하 유발 | 기본 5~10Hz, collision enabled일 때만, 최신 상태만 유지 |

---

## 5. 구현 원칙

- 서버/모듈 간 통신은 반드시 DTAM SDK / IntegrationHub / ICD 경유.
- Unreal/AirSim RPC는 VisualizationModule 내부 adapter에서만 사용.
- VehicleModule이 비행 상태의 최종 권한자다.
- VisualizationModule은 충돌 감지 및 시각화 담당이며, 직접 비행 상태를 영구 변경하지 않는다.
- 첫 구현은 안전한 `event + hold` 방식으로 시작하고, 물리 반발/고급 충돌 역학은 후순위로 둔다.
- 모든 신규 ICD는 KOR/ENG 문서, SDK sample, forwarding rule, sequence diagram을 동시에 갱신한다.

---

## 6. 최종 산출물 체크리스트

- [x] `4103_vehicleCollisionEvent` KOR/ENG ICD 문서
- [x] SDK catalog/policy/samples/role stubs 반영
- [x] IntegrationHub forwarding/DB/sequence diagram 반영
- [x] VisualizationModule collision polling/config/4103 송신
- [x] VehicleModule 4103 수신/상태 반영/4001 collision snapshot
- [x] OperationModule collision 표시 UI
- [x] Unreal collision mode 옵션화
- [ ] EXE 빌드 및 런타임 복사
- [ ] E2E 테스트 로그/결과 문서 (실제 Unreal 충돌 현장 확인 필요)
- [ ] 회귀 테스트 체크 결과

---

## 7. 권장 개발 순서 결론

바로 물리 충돌 반응부터 건드리지 말고, 다음 순서로 가는 것을 권장한다.

```text
ICD 정의
→ VM collision 감지
→ 서버 경유 전달
→ VehicleModule hold/stop 반영
→ Unreal collision mode 실험
→ UI/E2E 검증
```

이렇게 하면 현재 안정화한 4001/5001/5002/4102 구조를 크게 흔들지 않으면서, 충돌 정보를 실제 비행 상태까지 단계적으로 연결할 수 있다.


