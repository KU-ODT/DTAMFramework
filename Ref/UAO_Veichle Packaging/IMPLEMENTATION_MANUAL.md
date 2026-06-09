# UAO Mission Dispatch System — Implementation Manual

## 1. 시스템 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────────┐
│                        UAO PC (이 모듈)                              │
│                                                                     │
│  ┌──────────┐   ┌───────────┐   ┌──────────┐   ┌────────────────┐  │
│  │ Receiver  │──▶│Dispatcher │──▶│ Compiler │──▶│   Uploader     │  │
│  │ (FastAPI) │   │ (Queue)   │   │ (Jinja2) │   │ (SCP + SSH)    │──┼──▶ 기체 PC
│  └─────┬────┘   └───────────┘   └──────────┘   └────────────────┘  │
│        │                                                            │
│  ┌─────▼─────────────────────────────────────────┐                  │
│  │ Status Module                                  │                  │
│  │  MAVLink Receiver ◀── UDP 14550 ◀─────────────┼──────────────────┼── 기체 PC
│  │  Cache + Normalizer + WebSocket Broadcaster    │                  │
│  └────────────────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────────┘
```

## 2. 미션 처리 플로우 (상세)

미션 JSON이 수신되었을 때 내부 코드가 동작하는 전체 흐름입니다.

### Phase 1: 수신 및 검증

```
Mission JSON 도착
    │
    ▼
http_server.py: receive_missions()
    │  POST /api/v1/missions 또는 /realtime 또는 WS /missions/ws
    │
    ▼
adapter.py: OperatorPayloadAdapter.adapt()
    │  외부 JSON → ICD v1 포맷 변환 (현재 Passthrough)
    │
    ▼
dispatcher.py: process_single()
    ├── schema_validator.py: validate()
    │     JSON 구조 검증 (필수 필드, 타입, 범위)
    ├── semantic_validator.py: validate()
    │     의미 검증 (좌표 연속성, 속도 제한, Phase 순서)
    ├── aircraft_registry.py: find_target()
    │     aircraftId로 기체 설정 조회 (포트, SSH 정보 등)
    └── dispatch_queue.py: enqueue()
          큐에 DispatchResult 등록 → 비동기 처리 시작
```

### Phase 2: 컴파일 (JSON → Python 비행 스크립트)

```
dispatch_queue.py → pipeline.py: handle()
    │
    ▼
mission_to_ir.py: mission_to_ir()
    │  Mission JSON → MissionIR (중간표현) 변환
    │  - enRoute 세그먼트를 Phase별 LegBlock으로 분류
    │  - Phase A,K → TAXI (건너뜀)
    │  - Phase B → VTOL_CLIMB
    │  - Phase C → TRANSITION_FW
    │  - Phase D,H → RF_ARC (arc_interpolator로 원호 계산)
    │  - Phase E,F,I → TF_LINE (직선 비행)
    │  - Phase G → TRANSITION_MC
    │  - Phase J → VTOL_DESCENT
    │  - Home 좌표 = 첫 번째 비행 구간(Phase B)의 시작점
    │
    ▼
assembler.py: compile()
    │  Jinja2 템플릿 렌더링
    │  - mission_script.py.j2  → 전체 스크립트 골격
    │  - maneuver_blocks.py.j2 → 비행 기동 함수들
    │  - failsafe.py.j2        → 비상 착륙 로직
    │
    ▼
output/UAM0004_FP5071803_20260514_1801.py  (실행 가능한 Python 파일)
```

### Phase 3: 배포 및 실행

```
uploader.py: upload()
    │
    ├── _launch_sitl_remote()  ← SITL 자동 기동
    │     │
    │     ▼
    │   executor.py: launch_sitl()
    │     1. SSH 연결 → 기체 PC 접속
    │     2. MAVLink 포워더 스크립트 설치/기동 (UDP 14550 → UAO PC)
    │     3. VFDS 시뮬레이터 기동 (nohup)
    │     4. PX4 SITL 기동 (PX4_HOME_LAT/LON/ALT 환경변수 주입)
    │     5. pgrep 폴링으로 프로세스 준비 확인
    │
    ├── _deploy()  ← 스크립트 전송
    │     scp_client.py: SCP로 .py 파일을 기체 PC의 ~/missions/에 업로드
    │
    └── _execute()  ← 스크립트 실행
          executor.py: execute()
            SSH로 nohup python3 <script>.py 실행
            UAO_HOST, UAO_PORT, UAO_URL 환경변수 주입
            PID 캡처하여 반환
```

### Phase 4: 비행 실행 (기체 PC에서)

```
기체 PC에서 실행되는 생성된 스크립트:
    │
    ├── MAVSDK gRPC로 PX4에 연결
    ├── Arming 대기 → STD 시각까지 대기
    ├── Leg 순차 실행:
    │     VTOL_CLIMB  → do_takeoff() + do_goto_line()
    │     TRANSITION_FW → do_transition_fw()
    │     TF_LINE → do_goto_line() (terminal normal 통과 판정)
    │     RF_ARC → do_orbit_arc() (DO_ORBIT + swept angle 모니터링)
    │     TRANSITION_MC → do_transition_mc()
    │     VTOL_DESCENT → do_land()
    │
    └── TelemetryReporter:
          10Hz로 텔레메트리 수집 → HTTP POST로 UAO에 전송
          /api/v1/telemetry (위치, 자세, 액추에이터)
          /api/v1/events (미션 진행 이벤트)
```

### Phase 5: 텔레메트리 수신 및 표출

```
기체 PC → MAVLink UDP 14550 → UAO PC
    │
    ▼
receiver_mavlink.py: MavlinkMultiReceiver
    │  pymavlink으로 UDP 소켓 수신
    │  패킷의 sysid로 기체 식별 (1=UAM0001, 2=UAM0002, ...)
    │  메시지 타입별 파싱:
    │    GLOBAL_POSITION_INT → 위경도/고도
    │    LOCAL_POSITION_NED  → NED 좌표 (Home 기준 LLA 변환)
    │    ATTITUDE            → Roll/Pitch/Yaw
    │    SERVO_OUTPUT_RAW    → 틸트/에일러론/러더베이터 (MAIN 9,10)
    │    ACTUATOR_OUTPUT_STATUS → 정규화된 액추에이터 출력
    │    ESC_STATUS           → 모터 RPM
    │
    ▼
cache.py: status_cache
    │  기체별 AircraftStatus 인메모리 캐시 갱신
    │
    ▼
WebSocket /api/v1/ws/live 로 대시보드에 브로드캐스트
```

## 3. 주요 모듈 상세

### 3.1 Compiler (`src/compiler/`)

| 파일 | 역할 |
|------|------|
| `mission_to_ir.py` | Mission JSON → `MissionIR` 변환. Phase 코드로 LegType 분류, Home 좌표 결정 (Phase A/K 제외한 첫 비행 구간) |
| `arc_interpolator.py` | Turn Phase(D, H)의 두 직선 구간 사이에서 원호 파라미터(중심점, 반경, sweep 각도, 회전 방향) 계산 |
| `assembler.py` | Jinja2 Environment 설정 및 IR → Python 스크립트 렌더링 |
| `templates/mission_script.py.j2` | 생성되는 비행 스크립트 전체 골격 (연결, Arming, Leg 순차 실행, 텔레메트리 리포터) |
| `templates/maneuver_blocks.py.j2` | `do_goto_line`, `do_orbit_arc`, `do_takeoff`, `do_land`, `do_transition_fw/mc` 등 기동 함수 |
| `templates/failsafe.py.j2` | gRPC 연결 끊김 시 재연결 및 비상 착륙 로직 |

### 3.2 Dispatcher (`src/dispatcher/`)

| 파일 | 역할 |
|------|------|
| `dispatcher.py` | 미션 수신 → 검증 → 기체 배정 → 큐 등록 오케스트레이션 |
| `dispatch_queue.py` | 비동기 FIFO 큐. `enqueue()` 시 `asyncio.create_task`로 파이프라인 핸들러 호출 |
| `aircraft_registry.py` | YAML에서 기체 설정 로드. `aircraftId`로 `AircraftTarget` 검색 |
| `models.py` | `DispatchResult`, `DispatchStatus`, `AircraftTarget`, `SitlConfig` 데이터 모델 |
| `sim_time.py` | `SimulationClock` — 외부 시뮬레이션 시각 수신/관리. 미션 스크립트의 STD 대기에 사용 |

### 3.3 Status (`src/status/`)

| 파일 | 역할 |
|------|------|
| `receiver_mavlink.py` | UDP 14550에서 MAVLink 패킷 수신. `sysid`로 기체 분리, 서보 채널 매핑 (KP2 모델: MAIN 9=V-tail L, MAIN 10=V-tail R) |
| `normalizer.py` | NED→LLA 좌표 변환, 기체별 Home 좌표 관리 (`register_home`) |
| `cache.py` | `AircraftStatus` 인메모리 딕셔너리 캐시 |
| `receiver.py` | FastAPI 라우터: `/telemetry`, `/events`, `/ws/live` 엔드포인트 + WebSocket 매니저 |
| `models.py` | `AircraftStatus`, `PositionData`, `AttitudeData`, `ActuatorData` Pydantic 모델 |

### 3.4 Uploader (`src/uploader/`)

| 파일 | 역할 |
|------|------|
| `uploader.py` | 업로드 오케스트레이터: SITL 기동 → SCP 전송 → SSH 실행 순서 제어 |
| `executor.py` | SSH 원격 실행: PX4/VFDS 프로세스 기동, MAVLink 포워더 설치, 프로세스 폴링 확인 |
| `scp_client.py` | Paramiko 기반 SCP 파일 전송 |
| `local_deployer.py` | 로컬 파일 복사 배포 (개발용) |

## 4. 기체 컴퓨터 연결 상세

### 4.1 연결 수립 과정

```
UAO PC                              기체 PC (203.252.161.188)
  │                                      │
  │  1. SSH 연결 (port 22, user: kada-vdt)│
  │─────────────────────────────────────▶│
  │                                      │
  │  2. MAVLink 포워더 스크립트 설치       │
  │  /tmp/mission_dispatch_mavlink_fwd.py │
  │  (UDP 14550 → UAO PC:14550)          │
  │─────────────────────────────────────▶│
  │                                      │
  │  3. VFDS 시뮬레이터 기동              │
  │  run_vehicle_multi.py --port 456X    │
  │─────────────────────────────────────▶│
  │                                      │
  │  4. PX4 SITL 기동                    │
  │  PX4_HOME_LAT/LON/ALT 주입          │
  │  px4 -i <instance_id>               │
  │─────────────────────────────────────▶│
  │                                      │
  │  5. pgrep 폴링 (1초 간격)            │
  │  px4.*-i <N> 프로세스 확인           │
  │◀────────────────────────────────────│
  │                                      │
  │  6. 미션 스크립트 SCP 전송            │
  │  ~/missions/UAM000X_FP....py         │
  │─────────────────────────────────────▶│
  │                                      │
  │  7. nohup python3 <script> 실행      │
  │  UAO_HOST/PORT 환경변수 주입          │
  │─────────────────────────────────────▶│
  │                                      │
  │  ◀──── MAVLink UDP 14550 텔레메트리 ──│
  │  ◀──── HTTP POST /telemetry, /events ─│
  │                                      │
```

### 4.2 미션 스크립트가 UAO에 보고하는 데이터

생성된 미션 스크립트(`TelemetryReporter` 클래스)는 기체 PC에서 실행되면서 UAO PC로 두 종류의 데이터를 HTTP POST합니다:

#### 텔레메트리 (10Hz, `/api/v1/telemetry`)

| 데이터 | 소스 | 설명 |
|--------|------|------|
| 위치 (lat, lon, alt) | `drone.telemetry.position()` | WGS-84 위경도 + 해발고도 |
| NED 좌표 (N, E, D) | LLA→NED 변환 | Home 기준 상대 좌표 |
| 자세 (roll, pitch, yaw) | `drone.telemetry.attitude_euler()` | 오일러 자세각 (deg) |
| 틸트 서보 (L, R) | `actuator_output_status[4,5]` | 0.0~1.0 (수직~수평) |
| 에일러론 | `actuator_output_status[6]` | ±30° |
| V-tail 러더베이터 (L, R) | `actuator_output_status[8,9]` | ±30° (MAIN 9, 10) |
| 모터 RPM (1~4) | `actuator_output_status[0-3]` 또는 `esc_status` | RPM |

#### 미션 이벤트 (Phase 전환 시, `/api/v1/events`)

| 필드 | 값 예시 | 설명 |
|------|---------|------|
| `event` | EXECUTING, COMPLETED, FAILED | 미션 상태 |
| `phase` | A, B, C, ... K | 현재 비행 Phase |
| `seq` | 1, 2, 3, ... | 현재 Leg 번호 |

### 4.3 MAVLink 직접 수신 (receiver_mavlink.py)

스크립트 리포터와 별개로, PX4가 GCS 포트(14550)로 브로드캐스트하는 MAVLink 패킷을 **직접 수신**합니다. 이 경로가 더 높은 빈도와 낮은 지연으로 텔레메트리를 제공합니다.

수신하는 MAVLink 메시지 목록:

| MAVLink 메시지 | 추출 데이터 | 갱신 주기 |
|----------------|-------------|-----------|
| `HEARTBEAT` | 기체 연결 확인 | 1Hz |
| `GLOBAL_POSITION_INT` | 위경도 (1e-7 deg), 고도 (mm) | 10Hz |
| `LOCAL_POSITION_NED` | NED 좌표 (m) | 10Hz |
| `ATTITUDE` | Roll/Pitch/Yaw (rad → deg 변환) | 10Hz |
| `SERVO_OUTPUT_RAW` | 서보 PWM → 틸트/에일러론/러더베이터 | 10Hz |
| `ACTUATOR_OUTPUT_STATUS` | 정규화 액추에이터 출력 | 10Hz |
| `ESC_STATUS` | ESC RPM (지원 시) | 10Hz |

### 4.4 KP2 모델 서보 채널 매핑

```
MAIN 1-4  : 모터 1~4 (쿼드 로터)
MAIN 5    : 틸트 서보 Left        → actuator.tilt_left  (0.0~1.0)
MAIN 6    : 틸트 서보 Right       → actuator.tilt_right (0.0~1.0)
MAIN 7    : 에일러론              → actuator.aileron    (±30°)
MAIN 8    : (미사용)
MAIN 9    : V-tail Left Ruddervator  → actuator.rudder_left  (±30°)
MAIN 10   : V-tail Right Ruddervator → actuator.rudder_right (±30°)
```

## 5. 서버 시작 시 초기화 순서

`src/main.py`의 `main()` 함수 실행 시:

1. **Config 로드** — `server_config.yaml`, `aircraft_registry.yaml` 읽기
2. **Home 좌표 등록** — 각 기체의 `home_lat/lon/alt`를 normalizer에 등록 (NED→LLA 변환 기준점)
3. **Dispatcher 초기화** — `AircraftRegistry`, `DispatchQueue`, `SimulationClock` 조립
4. **Pipeline 초기화** — `Assembler` + `Uploader` + `MissionPipeline` 조립
5. **원격 호스트 클린업** — 이전 실행의 잔류 프로세스(PX4, VFDS, MAVSDK, 미션 스크립트) 강제 종료
6. **File Watcher 시작** — inbox 폴더 감시 (설정 시)
7. **FastAPI 서버 기동** — uvicorn으로 HTTP 서버 실행 (lifespan 내에서 MAVLink 수신기 자동 시작)
8. **종료 시** — `atexit` 핸들러로 모든 원격 SITL 세션 자동 정리

## 6. 비행 구간(Leg) 종료 판정 로직

### do_goto_line (직선 비행)

```
1차 판정: Terminal Normal 통과
    시작점→끝점 벡터에 대한 수선(Normal)을 기체가 넘으면 즉시 완료
    → FW/MC 모두 최우선 적용

2차 판정: 거리 Fallback
    끝점까지 거리가 threshold 이내이면 완료
    MC: 3m / FW: 50m

타임아웃: 동적 계산
    max(120초, (거리/속도) × 2 + 60초)
```

### do_orbit_arc (원호 비행)

```
PX4 DO_ORBIT 명령 → swept angle 모니터링
    누적 sweep 각도가 목표의 95% 이상이면 완료
    → 끝점으로 goto 전환 → terminal normal 또는 거리 fallback으로 최종 도달 확인
```

## 7. 에러 처리 및 Failsafe

| 상황 | 동작 |
|------|------|
| gRPC 연결 끊김 | 자동 재연결 시도 (최대 10회, 5초 간격) |
| Leg 타임아웃 | RuntimeError 발생 → `emergency_land()` 호출 |
| Arming 실패 | 5회 재시도 후 미션 중단, FAILED 이벤트 보고 |
| 텔레메트리 스트림 끊김 | 스트림별 독립 재연결 (위치/자세/액추에이터 각각) |
| 서버 종료 (Ctrl+C) | `atexit` → 모든 원격 SITL 강제 종료 |
