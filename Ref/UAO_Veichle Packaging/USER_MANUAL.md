# UAO Mission Dispatch System — User Manual

## 1. 개요

UAO Mission Dispatch System은 UAM(Urban Air Mobility) 기체에 대한 **미션 수신 → 비행 스크립트 자동 생성 → 원격 배포 및 실행 → 실시간 텔레메트리 모니터링**을 수행하는 통합 모듈입니다.

---

## 2. 설치 및 실행

### 2.1 요구사항

- Python 3.12 이상
- 기체 PC(SITL 서버)에 대한 네트워크 접근 및 SSH 인증 정보
- 기체 PC에 PX4 Autopilot, VFDS, MAVSDK가 사전 설치되어 있어야 함

### 2.2 설치

```bash
# 1. 프로젝트 폴더로 이동
cd UAO_Veichle_Packaging

# 2. 가상환경 생성 및 활성화
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 3. 의존성 설치
pip install -r requirements.txt
```

### 2.3 서버 실행

```bash
python -m src.main
```

서버가 정상 기동되면 아래 로그가 출력됩니다:

```
2026-05-14 18:00:00 [INFO] mission_dispatch: Aircraft registry loaded: 5 aircraft
2026-05-14 18:00:00 [INFO] mission_dispatch: Starting HTTP server on 0.0.0.0:8000
```

### 2.4 대시보드 접속

웹 브라우저에서 `http://localhost:8000` 으로 접속하면 실시간 대시보드를 사용할 수 있습니다.

- **좌측 패널**: Mission JSON 업로드 (드래그 앤 드롭 / 직접 입력) + 미션 상태 목록
- **우측 상단**: Leaflet 지도 (비행 경로 + 기체 위치 실시간 표시)
- **우측 하단**: 선택한 기체의 텔레메트리 데이터 실시간 표출

---

## 3. 미션 업로드 방법

### 3.1 대시보드 UI를 통한 직접 업로드

1. `http://localhost:8000` 접속
2. 좌측 "Mission Submit" 패널에 Mission ICD v1 JSON 파일을 **드래그 앤 드롭**하거나, 텍스트 영역에 직접 붙여넣기
3. **🚀 Submit Mission** 버튼 클릭
4. 하단 "Mission Status" 패널에서 진행 상태 확인 (QUEUED → COMPILING → UPLOADING → EXECUTING → COMPLETED)

### 3.2 REST API를 통한 프로그래밍 방식 업로드

#### 단건 미션 전송

```bash
curl -X POST http://localhost:8000/api/v1/missions \
  -H "Content-Type: application/json" \
  -d @mission_icd_v1_UAM0001.json
```

#### 배치 (복수) 미션 전송

```bash
curl -X POST http://localhost:8000/api/v1/missions \
  -H "Content-Type: application/json" \
  -d '[{...미션1...}, {...미션2...}, {...미션3...}]'
```

#### 응답 예시 (성공: 202 Accepted)

```json
{
  "status": "accepted",
  "missionId": "uuid-xxxx",
  "flightPlanNumber": 5071803,
  "aircraftId": "UAM0004"
}
```

#### 응답 예시 (검증 실패: 422)

```json
{
  "status": "rejected",
  "errors": [
    {"field": "enRoute[3].startLLA", "message": "Coordinate discontinuity detected"}
  ]
}
```

### 3.3 파일 드롭 자동 제출 (File Watcher)

`config/server_config.yaml`에서 `file_watcher.enabled: true`로 설정된 경우, `inbox/` 폴더에 `.json` 파일을 놓으면 자동으로 감지되어 미션이 제출됩니다.

```
inbox/
  └── mission_UAM0001.json   ← 파일 감지 → 자동 제출
```

---

## 4. 외부 모듈과의 연동 (Data Integration)

### 4.1 외부 모듈에서 UAO로 미션 전송 (Mission Ingestion)

외부 시스템(예: DTAM Operator, Traffic Simulator)이 UAO에 미션을 자동 전송하려면 다음 인터페이스를 사용합니다.

#### 방법 1: REST API (Stateless, 단발성)

```
POST http://<UAO_IP>:8000/api/v1/missions/realtime
Content-Type: application/json

{
  "flightPlanNumber": 5071803,
  "aircraftId": "UAM0004",
  "departure": { ... },
  "enRoute": [ ... ],
  "arrival": { ... }
}
```

이 엔드포인트는 대시보드 UI를 거치지 않고 외부 모듈이 직접 미션을 주입하기 위한 전용 경로입니다. 내부적으로 `OperatorPayloadAdapter`를 거쳐 ICD v1 포맷으로 변환 후 동일한 디스패치 파이프라인을 탑니다.

#### 방법 2: WebSocket (Persistent, 실시간 스트리밍)

```python
import asyncio
import websockets
import json

async def send_missions():
    uri = "ws://<UAO_IP>:8000/api/v1/missions/ws"
    async with websockets.connect(uri) as ws:
        mission = {
            "flightPlanNumber": 5071803,
            "aircraftId": "UAM0004",
            "departure": { ... },
            "enRoute": [ ... ],
            "arrival": { ... }
        }
        await ws.send(json.dumps(mission))
        response = await ws.recv()
        print(json.loads(response))

asyncio.run(send_missions())
```

WebSocket 연결은 끊기지 않는 한 계속 유지되므로, 여러 미션을 연속으로 전송할 수 있습니다.
각 전송마다 아래 형식의 응답이 돌아옵니다:

```json
{
  "httpStatus": 202,
  "body": {
    "status": "accepted",
    "missionId": "uuid-xxxx",
    "flightPlanNumber": 5071803,
    "aircraftId": "UAM0004"
  }
}
```

#### Adapter 커스터마이징

외부 시스템의 JSON 구조가 ICD v1과 다른 경우, `src/receiver/adapter.py`의 `OperatorPayloadAdapter.adapt()` 메서드를 수정하여 변환 로직을 구현합니다.

```python
# src/receiver/adapter.py
class OperatorPayloadAdapter:
    @staticmethod
    def adapt(payload: dict) -> dict:
        # 현재는 Passthrough (ICD v1 호환 가정)
        # 여기에 외부 포맷 → ICD v1 변환 로직 구현
        if "flightPlanNumber" in payload:
            return payload  # 이미 ICD v1 호환

        # 예시: 외부 시스템이 다른 키 이름을 사용할 경우
        return {
            "flightPlanNumber": payload["fp_num"],
            "aircraftId": payload["vehicle_id"],
            "departure": { ... },
            "enRoute": [ ... ],
            "arrival": { ... },
        }
```

### 4.2 UAO에서 외부 모듈로 기체 데이터 전송 (Data Export)

UAO가 기체로부터 수신한 텔레메트리 데이터를 외부 시스템으로 내보내는 방법입니다.

#### 방법 1: WebSocket 구독 (실시간 Push)

```python
import asyncio
import websockets
import json

async def receive_telemetry():
    uri = "ws://<UAO_IP>:8000/api/v1/ws/live"
    async with websockets.connect(uri) as ws:
        while True:
            data = await ws.recv()
            status = json.loads(data)
            print(f"[{status['aircraftId']}] "
                  f"lat={status['position']['lat']:.6f} "
                  f"lon={status['position']['lon']:.6f} "
                  f"alt={status['position']['alt']:.1f}")

asyncio.run(receive_telemetry())
```

연결 즉시 현재 캐시된 모든 기체 상태가 전송되고, 이후 텔레메트리가 갱신될 때마다 실시간으로 Push됩니다.

#### 방법 2: REST API 폴링 (Snapshot)

```bash
# 모든 기체의 현재 텔레메트리 스냅샷
GET http://<UAO_IP>:8000/api/v1/telemetry

# 모든 미션의 진행 상태
GET http://<UAO_IP>:8000/api/v1/missions/status

# 등록된 기체 목록
GET http://<UAO_IP>:8000/api/v1/aircraft

# 시스템 헬스체크
GET http://<UAO_IP>:8000/health
```

#### WebSocket으로 수신되는 텔레메트리 JSON 구조

```json
{
  "aircraftId": "UAM0001",
  "flightPlanNumber": 5071803,
  "ts": "2026-05-14T09:15:30.123Z",
  "missionState": "EXECUTING",
  "phase": "F",
  "seq": 5,
  "position": {
    "lat": 37.497702,
    "lon": 127.073855,
    "alt": 304.8,
    "north": 1234.5,
    "east": -567.8,
    "down": -304.8
  },
  "attitude": {
    "roll": 2.34,
    "pitch": -1.56,
    "yaw": 215.7
  },
  "actuator": {
    "tilt_left": 0.95,
    "tilt_right": 0.95,
    "aileron": 3.2,
    "rudder_left": -5.1,
    "rudder_right": 2.8
  },
  "motorRpm": [0.0, 0.0, 5420.0, 0.0]
}
```

| 필드 | 단위 | 설명 |
|------|------|------|
| `position.lat/lon` | 도(deg) | WGS-84 위경도 |
| `position.alt` | m (AMSL) | 해발고도 |
| `position.north/east/down` | m | NED 좌표 (Home 기준) |
| `attitude.roll/pitch/yaw` | 도(deg) | 오일러 자세각 |
| `actuator.tilt_left/right` | 0.0~1.0 | 틸트 서보 위치 (0=수직, 1=수평) |
| `actuator.aileron` | 도(deg) | 에일러론 편향 (±30°) |
| `actuator.rudder_left/right` | 도(deg) | V-tail 러더베이터 편향 (±30°) |
| `motorRpm` | RPM | 모터 1~4 회전수 |
| `missionState` | 문자열 | WAITING / EXECUTING / COMPLETED / FAILED |
| `phase` | 문자열 | 현재 비행 페이즈 (A~K) |

### 4.3 시뮬레이션 시각 동기화

외부 시뮬레이션 시스템이 시뮬레이션 시각을 UAO에 주입하여, 미션의 STD(출발예정시간)와 동기화할 수 있습니다.

```bash
# 시뮬레이션 시각 전송
POST http://<UAO_IP>:8000/api/v1/time
Content-Type: application/json

{"time": "18:01:00"}

# 현재 시뮬레이션 시각 조회
GET http://<UAO_IP>:8000/api/v1/time
```

---

## 5. UAM 기체 번호별 인스턴스 / 포트 매핑

### 5.1 포트 할당 규칙

UAM 기체 번호에 따라 PX4 인스턴스 ID, MAVSDK gRPC 포트, MAVLink 연결 포트가 순차적으로 할당됩니다.

| 기체 ID | Instance ID | MAVLink 연결 포트 (MAVSDK) | MAVSDK gRPC 포트 | VFDS 시뮬레이터 포트 | MAVLink SysID |
|---------|-------------|---------------------------|------------------|---------------------|---------------|
| **UAM0001** | 0 | `udpin://0.0.0.0:14540` | 50051 | 4560 | 1 |
| **UAM0002** | 1 | `udpin://0.0.0.0:14541` | 50052 | 4561 | 2 |
| **UAM0003** | 2 | `udpin://0.0.0.0:14542` | 50053 | 4562 | 3 |
| **UAM0004** | 3 | `udpin://0.0.0.0:14543` | 50054 | 4563 | 4 |
| **UAM0005** | 4 | `udpin://0.0.0.0:14544` | 50055 | 4564 | 5 |

### 5.2 포트 계산 공식

새로운 기체를 추가할 때 다음 공식으로 포트를 계산합니다:

```
Instance ID     = N - 1           (UAM000N → instance N-1)
MAVLink Port    = 14540 + (N - 1)
MAVSDK gRPC     = 50051 + (N - 1)
VFDS Port       = 4560 + (N - 1)
MAVLink SysID   = N
```

### 5.3 기체 추가 방법

`config/aircraft_registry.yaml`에 새로운 항목을 추가합니다:

```yaml
  UAM0006:
    type: "SITL"
    instance_id: 5
    connection_string: "udpin://0.0.0.0:14545"
    mavsdk_port: 50056
    send_protocol: "scp"
    send_host: "203.252.161.188"     # 기체 PC IP
    send_port: 22
    execution_mode: "remote"
    script_deploy_path: "~/missions"
    python_executable: "python3"
    ssh_password: "kada123"
    status: "available"
    home_lat: 37.525680
    home_lon: 126.922050
    home_alt: 0.0
    mavlink_sysid: 6
    sitl:
      enabled: true
      vfds_command_template: "cd ~/git/vfds/run && python3.12 run_vehicle_multi.py --port 4565 --no-px4 --lat {home_lat} --lon {home_lon} --alt {home_alt}"
      command_template: "cd ~/PX4-Autopilot && PX4_HOME_LAT={home_lat} PX4_HOME_LON={home_lon} PX4_HOME_ALT={home_alt} PX4_SIM_MODEL=kp2 ./build/px4_sitl_default/bin/px4 -i 5"
      stop_pattern: "px4 -i 5|run_vehicle_multi.py --port 4565|mavsdk_server.*50056|python3.*UAM0006"
```

### 5.4 MAVLink 텔레메트리 수신 구조

모든 기체의 텔레메트리는 기체 PC에서 **UDP 14550 포트로 포워딩**되어 UAO PC의 단일 MAVLink 수신기(`receiver_mavlink.py`)에 도착합니다. 수신기는 MAVLink 패킷의 `sysid` 필드로 기체를 구분합니다.

```
기체 PC (203.252.161.188)                    UAO PC
┌─────────────────────────┐                ┌──────────────────┐
│ PX4 Instance 0 (sysid=1)├─┐             │                  │
│ PX4 Instance 1 (sysid=2)├─┤ MAVLink     │  MavlinkMulti    │
│ PX4 Instance 2 (sysid=3)├─┤ UDP 14550 ──┤  Receiver        │
│ PX4 Instance 3 (sysid=4)├─┤ Forwarder   │  (port 14550)    │
│ PX4 Instance 4 (sysid=5)├─┘             │                  │
└─────────────────────────┘                └──────────────────┘
```

---

## 6. 미션 강제 중단

실행 중인 미션을 수동으로 중단하려면:

```bash
DELETE http://<UAO_IP>:8000/api/v1/missions/<flightPlanNumber>
```

이 명령은 원격 기체 PC의 해당 SITL 인스턴스 및 미션 스크립트를 강제 종료하고, 미션 상태를 FAILED로 변경합니다.

---

## 7. 설정 파일 참조

### 7.1 server_config.yaml

```yaml
server:
  host: "0.0.0.0"       # 바인드 주소 (모든 인터페이스)
  port: 8000             # HTTP 서버 포트

file_watcher:
  inbox_path: "./inbox"  # 자동 감지 폴더 경로
  enabled: true          # 파일 감시 활성화 여부

mission_scheduler:
  enabled: true
  timezone: "Asia/Seoul"
  time_field: "departure.std"    # 미션 시작 시각 참조 필드
  arming_lead_sec: 5             # Arming 선행 시간 (초)

output:
  script_dir: "./output"         # 컴파일된 스크립트 출력 경로
```

### 7.2 aircraft_registry.yaml

기체별 상세 설정은 `config/aircraft_registry.yaml`을 참조하세요. 각 항목의 의미:

| 필드 | 설명 |
|------|------|
| `type` | 기체 유형 (현재 "SITL"만 지원) |
| `instance_id` | PX4 인스턴스 번호 (0부터 시작) |
| `connection_string` | MAVSDK가 MAVLink을 수신하는 UDP 주소 |
| `mavsdk_port` | MAVSDK gRPC 서버 포트 |
| `send_host` | 기체 PC의 SSH 접속 IP |
| `send_port` | SSH 포트 (기본 22) |
| `ssh_password` | SSH 비밀번호 |
| `home_lat/lon/alt` | 기본 HOME 좌표 (미션 없을 때 fallback) |
| `mavlink_sysid` | MAVLink System ID (기체 식별) |
| `sitl.command_template` | PX4 SITL 기동 명령 (`{home_lat/lon/alt}` 치환됨) |
| `sitl.vfds_command_template` | VFDS 시뮬레이터 기동 명령 |
| `sitl.stop_pattern` | 프로세스 종료 시 사용할 패턴 |

---

## 8. API 전체 목록

| Method | Endpoint | 용도 |
|--------|----------|------|
| `GET` | `/` | 대시보드 UI |
| `POST` | `/api/v1/missions` | 미션 JSON 제출 (UI/외부) |
| `POST` | `/api/v1/missions/realtime` | 외부 모듈 전용 미션 주입 |
| `WS` | `/api/v1/missions/ws` | WebSocket 실시간 미션 주입 |
| `GET` | `/api/v1/missions/status` | 모든 미션 상태 조회 |
| `DELETE` | `/api/v1/missions/{fp_number}` | 미션 강제 중단 |
| `POST` | `/api/v1/time` | 시뮬레이션 시각 설정 |
| `GET` | `/api/v1/time` | 시뮬레이션 시각 조회 |
| `POST` | `/api/v1/telemetry` | 텔레메트리 데이터 수신 (스크립트→UAO) |
| `GET` | `/api/v1/telemetry` | 텔레메트리 스냅샷 조회 |
| `POST` | `/api/v1/events` | 미션 이벤트 수신 (스크립트→UAO) |
| `WS` | `/api/v1/ws/live` | 실시간 텔레메트리 WebSocket 구독 |
| `GET` | `/api/v1/aircraft` | 등록된 기체 목록 |
| `GET` | `/api/v1/debug/mavlink` | MAVLink 수신기 디버그 정보 |
| `GET` | `/health` | 헬스체크 |
