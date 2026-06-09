# DTAM 모듈 작성 및 폴더 구조 규칙

이 문서는 DTAMFramework의 각 모듈을 앞으로 같은 방식으로 확장하기 위한 표준 구조를 정의한다.  
기존 통신 구조, SDK 사용 방식, ICD 메시지 흐름은 유지하고, 코드 배치와 책임 분리만 정리한다.

## 핵심 원칙

1. **모듈의 실행 코드는 `app/` 안에 둔다.**
   - FastAPI 서버, HTTP API, DTAM SDK 통신, 도메인 로직, 서비스 로직, 외부 adapter 코드는 모두 `app/` 아래에 둔다.
2. **`data/`는 코드가 아닌 데이터만 둔다.**
   - CSV, DB, mission export, runtime state, 설정 저장값, 로그, 프로파일 등을 둔다.
3. **최상위 `XX_main.py`는 실행 진입점만 담당한다.**
   - 경로 설정, config 로드, `app.server:create_app()` 실행 정도만 둔다.
4. **통신 코드는 `app/dtam/`에 격리한다.**
   - DTAM SDK, ICD handler, publisher, subscription 처리는 `app/dtam/`에 둔다.
   - `domain/` 코드는 WebSocket, FastAPI, DTAM SDK를 직접 알지 않는 것을 원칙으로 한다.
5. **모듈 간 기능 데이터 교환은 StateServerModule의 `/ws/dtam`과 ICD 메시지를 기준으로 한다.**
   - 기능 로직에서 다른 모듈로 직접 raw TCP/UDP를 열지 않는다.
   - 직접 REST 호출이 필요한 경우는 실행/관리/GUI 보조 목적의 명시적 예외로만 둔다.

## 권장 최상위 구조

```text
ModuleName/
  XX_main.py
  app/
  data/
  tests/
  docs/
  README.md
  requirements.txt
```

| 경로 | 역할 |
| --- | --- |
| `XX_main.py` | 모듈 실행 진입점. 복잡한 기능 로직은 넣지 않는다. |
| `app/` | 모듈의 실제 Python 코드와 GUI 정적 파일. |
| `data/` | 코드가 아닌 입력/출력/저장 데이터. |
| `tests/` | 단위/통합 테스트. |
| `docs/` | 모듈별 설계/운영 문서. |
| `README.md` | 모듈 설명과 실행 방법. |
| `requirements.txt` | 모듈 실행 의존성. |

## 권장 `app/` 구조

```text
app/
  __init__.py
  config.py
  server.py
  deps.py

  api/
    routes/
      status.py
      control.py
      config.py

  dtam/
    client.py
    handlers.py
    publishers.py
    schemas.py

  domain/
    ...

  services/
    ...

  adapters/
    ...

  schemas/
    ...

  web/
    index.html
    css/
    js/
```

### `app/api/`

HTTP REST API endpoint 전용 영역이다.  
API 함수는 입력 검증과 service 호출까지만 담당하고, 실제 기능 로직은 `services/` 또는 `domain/`으로 넘긴다.

### `app/dtam/`

DTAM SDK/ICD 통신 전용 영역이다.

| 파일 | 역할 |
| --- | --- |
| `client.py` | `DtamModule` 생성, 연결/재연결 관리. |
| `handlers.py` | 수신 ICD handler. 예: `1002`, `3001`, `5001`. |
| `publishers.py` | 송신 ICD publisher. 예: `0002`, `4001`, `4101`. |
| `schemas.py` | ICD dataclass와 내부 모델 사이 변환 helper. |

규칙:

- DTAM SDK import는 가능하면 `app/dtam/` 안에서만 한다.
- `domain/`은 SDK를 import하지 않는다.
- ICD ID별 책임 위치가 명확해야 한다.

### `app/domain/`

순수 기능 로직 영역이다.

- FastAPI, WebSocket, SDK import 금지 권장
- 입력값을 받아 계산하고 결과를 반환하는 구조
- 테스트하기 쉬워야 함

예:

```text
VehicleModule/app/domain/
  dynamics/
  autopilot/
  manual_control/
  transform/
  vehicle_state/
```

### `app/services/`

도메인 로직, 통신, adapter를 조합해서 실제 기능을 실행하는 영역이다.

예:

- vehicle session 관리
- control mode 결정
- mission 실행 상태 관리
- 3001 수신 후 내부 세션 생성
- 5001 입력을 domain에 전달
- 4001 publish 주기 관리

### `app/adapters/`

외부 시스템 연결부다.

예:

- AirSim RPC client
- Unreal process launcher
- keyboard capture
- joystick capture
- mbtiles reader
- file storage
- camera capture

### `app/schemas/`

HTTP API request/response 모델 또는 모듈 내부 DTO를 둔다.  
DTAM ICD dataclass 원본은 항상 `DTAMSDK/dtam_client/schema/`를 기준으로 한다.

### `app/web/`

모듈 GUI 정적 파일을 둔다.

```text
app/web/
  index.html
  css/
  js/
```

OperationModule처럼 GUI 규모가 큰 경우에는 `app/web/static`, `app/web/templates` 구조를 사용한다. 과거 `frontend/` 폴더는 더 이상 표준 구조가 아니다.

## 권장 `data/` 구조

```text
data/
  configs/
  runtime/
  exports/
  logs/
  geo/
  maps/
  vehicle_profiles/
```

| 경로 | 역할 |
| --- | --- |
| `data/configs/` | 사용자가 저장한 모듈 설정. |
| `data/runtime/` | 실행 중 생성되는 임시 상태. |
| `data/exports/` | mission/export 결과. |
| `data/logs/` | 모듈별 로그. 공통 런타임 로그는 `.dtam_runtime/logs`도 사용 가능. |
| `data/geo/` | 좌표/vertiport/waypoint CSV 등 지리 데이터. |
| `data/maps/` | 지도 타일, mbtiles 등. |
| `data/vehicle_profiles/` | 기체별 파라미터/프로파일. |

## VehicleModule 권장 구조

```text
VehicleModule/
  AM_main.py
  app/
    config.py
    server.py
    deps.py

    api/
      routes/
        control.py
        status.py
        config.py
        vehicles.py

    dtam/
      client.py
      handlers.py
      publishers.py
      message_4001.py

    domain/
      dynamics/
      autopilot/
      manual_control/
      transform/
      vehicle_state/

    services/
      vehicle_session_service.py
      control_mode_service.py
      flight_execution_service.py
      input_service.py

    adapters/
      keyboard_capture.py
      joystick_capture.py

    schemas/
      control.py
      vehicle.py
      status.py

    web/
      index.html
      css/
      js/

  data/
    configs/
    runtime/
    flight_records/
    vehicle_profiles/
```

## VehicleModule 책임 분리 예시

| 책임 | 위치 |
| --- | --- |
| 3001 계획 비행 수신 | `app/dtam/handlers.py` |
| 1002 play/pause/stop 수신 | `app/dtam/handlers.py` |
| 5001 keyboard/joystick 입력 수신 | `app/dtam/handlers.py` |
| 4001 비행체 상태 송신 | `app/dtam/publishers.py` 또는 `message_4001.py` |
| 자동비행 경로 추종 계산 | `app/domain/autopilot/` |
| 키보드/조이스틱 수동 동역학 | `app/domain/manual_control/` |
| NED/LLA/Unreal 좌표 변환 | `app/domain/transform/` |
| 현재 활성 비행체 세션 관리 | `app/services/vehicle_session_service.py` |
| 제어 모드 공통/개별 override 판단 | `app/services/control_mode_service.py` |
| 키보드/조이스틱 장치 입력 | `app/adapters/keyboard_capture.py`, `app/adapters/joystick_capture.py` |

## IntegrationHub 예외 규칙

`IntegrationHub`는 서버 묶음이므로 아래 구조를 유지한다.

```text
IntegrationHub/
  CoreServerModule/
    DSE_main.py
    app/
    data/
  StateServerModule/
    SS_main.py
    app/
    data/
```

- CoreServerModule: control plane, ICD docs, process lifecycle
- StateServerModule: data plane, `/ws/dtam`, DB, live monitor

## VisualizationModule layout exception

VisualizationModule owns Unreal/AirSim runtime artifacts, so it follows the common `app/` and `data/` rule with the extra runtime folders below.

```text
VisualizationModule/
  VM_main.py
  app/
    config.py
    api/          # FastAPI GUI/API/WebSocket
    services/     # VM orchestration, periodic tasks, Unreal lifecycle
    dtam/         # DTAM SDK ICD I/O
    adapters/     # AirSim/Unreal/cosysairsim adapters
    web/
  data/
    configs/      # vm_config.json, visualization_framework.json
    runtime/
    exports/
    logs/
  runtime/
    PythonClient/ # cosysairsim Python client
    Unreal/       # Unreal project, packaged exe, runtime assets
  docs/
    external/     # upstream Cosys-AirSim docs/licenses
  requirements.txt
```

Rules:

- VM Python code lives in `app/`.
- REST/WebSocket API code goes under `app/api/`; DTAM SDK transport goes under `app/dtam/`; external AirSim/Unreal access goes under `app/adapters/`; orchestration/state code goes under `app/services/`.
- `runtime/PythonClient` and `runtime/Unreal` are external runtime/build artifacts and stay outside `app/`.
- The default VM config is `data/configs/vm_config.json`.
- The old `vm_app/` compatibility wrappers are removed. New code and docs use the `VisualizationModule.app.*` structure.

## OperationModule 예외 규칙

OperationModule은 GUI 규모가 크지만, 실제 runtime backend와 web UI는 `app/` 아래에 둔다. 과거 `backend/app` 경로가 필요하면 `app.*`를 re-export하는 compatibility wrapper만 둔다.

권장 구조:

```text
OperationModule/
  DOC_main.py
  app/
    api/
    services/
    schemas/
    web/
      static/
      templates/
  data/
  resource/
```

## 마이그레이션 체크리스트

1. 현재 동작 테스트 기준을 먼저 확보한다.
2. `XX_main.py`는 실행 진입점만 남긴다.
3. HTTP route는 `app/api/routes/`로 이동한다.
4. SDK/ICD 송수신 코드는 `app/dtam/`로 이동한다.
5. 순수 계산 로직은 `app/domain/`으로 이동한다.
6. 외부 장치/시뮬레이터/파일 IO는 `app/adapters/`로 이동한다.
7. orchestration/stateful service는 `app/services/`로 이동한다.
8. 데이터 파일은 `data/` 하위로 정리한다.
9. import 경로를 수정한다.
10. `py_compile`, 모듈 실행, `/ws/dtam` 연결, ICD 송수신을 확인한다.

## 금지/주의 사항

- 기능 수정과 폴더 이동을 한 번에 크게 섞지 않는다.
- `domain/`에서 `dtam_client`, `fastapi`, `websockets`, `requests`를 직접 import하지 않는다.
- 모듈 간 직접 raw TCP/UDP 통신을 새로 추가하지 않는다.
- ICD 스키마 원본을 모듈 내부에 복사하지 않는다. 기준은 항상 `DTAMSDK/dtam_client/schema/`다.
- Unreal/PythonClient 같은 외부 런타임은 무리하게 `app/` 안으로 넣지 않는다.
