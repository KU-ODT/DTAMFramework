# DTAMAirMobility

UAM 비행 계획을 읽어 궤적을 10 Hz 로 실시간 생성하고, 좌표 변환(WGS84 → NED)을
거친 뒤 **DTAM MSG 4001 (Vehicle Status)** 메시지로 UDP 송신하는 모듈.

`odt_mp` 의 `simpleDynamics` 엔진과 `app/airsim/coord_transform.py` 의 NED
변환 로직을 뽑아와서 **AirSim 및 웹 맵 의존을 제거**하고, DTAM_SDK 를
파이프라인의 최종 출구로 붙였다. GUI 는 `DTAMOperationsConsole` 과 동일한
**FastAPI + HTML/JS** 구성.

## 구성

```
DTAMAirMobility/
├── AM_main.py                # 실행 진입점 (브라우저 열고 FastAPI 기동)
├── __init__.py
├── simpleDynamics/           # 비행체 궤적 시뮬레이터 (odt_mp 에서 발췌)
├── transform/                # WGS84 → local NED 좌표 변환
│   └── coord_transform.py
├── publisher/
│   ├── msg4001.py            # 4001 payload builder
│   └── publisher.py          # DTAM_SDK wrapper (push_vehicle_status_async)
├── service/
│   └── integrated_service.py # 비행계획 + 시계 → 10 Hz 송신 서비스
├── backend/
│   └── app.py                # FastAPI app + REST API
├── frontend/
│   ├── templates/index.html
│   └── static/{css,js}
└── requirements.txt
```

## 동작 흐름

```
FlightPlan(JSON) ─▶ VehicleSession (simpleDynamics.DynamicsEngine)
                      │  FlightTrajectoryPoint (lat/lon/alt, speed, heading…)
                      ▼
Clock (external /    IntegratedAirMobilityService
 wall / manual)      │ 10 Hz tick. sim_time 이 etot 이상인 UAM만 advance.
  ──(sim_time_s)──▶  │
                      ▼
                transform.coord_transform  (WGS84 → local NED)
                      ▼
                publisher.msg4001.build_vehicle_payload  ─▶  build_4001_message
                      ▼
                DTAM_SDK.push_vehicle_status_async  (UDP, 10 Hz)
```

## DTAM 4001 필드 매핑

| 4001 필드              | 소스                                                             |
|-----------------------|------------------------------------------------------------------|
| `timestamp`           | sim time → 오늘 UTC 기준 ISO-8601                                |
| `<vehicle_id>`        | `FlightPlan.aircraftId` (ex. `UAM0001`)                          |
| `currentWaypointId`   | `{flightPlanNumber}-{seq}` 또는 `{fpn}-{vertiport}-{gate}`       |
| `position.{n,e,d}`    | `LocalNEDFrame(origin=첫 세그먼트 start)` 기준 변환              |
| `attitude.{r,p,y}`    | heading_deg → yaw(rad), roll/pitch 0                             |
| `actuator.*`          | 중립 (tilt 0.5 / aileron·rudder 0)                                |
| `propulsion.motor_rpm`| speed + climb 휴리스틱 (4 채널, 0..6000)                         |
| `gps.{lat,lon,alt}`   | 궤적 포인트 직결                                                  |
| `gps.velocity_{n,e,d}`| speed × track_heading → NED                                      |
| `imu.orientation`     | yaw 쿼터니언                                                      |
| `barometer.*`         | 고도 + 표준대기압                                                 |

## 빠른 시작

### 1. DTAM SDK + 의존성 설치

프레임워크 최상위에서:

```bash
pip install -e ./DTAM_SDK
pip install -r DTAMAirMobility/requirements.txt
```

### 2. 실행

```bash
python DTAMAirMobility/AM_main.py
```

기본 포트 `8100` 으로 FastAPI 가 기동되고, 브라우저가 자동으로 열린다.

옵션:

| 플래그              | 설명                                      | 기본값       |
|---------------------|-------------------------------------------|--------------|
| `--host`            | 바인딩 주소                               | `127.0.0.1`  |
| `--port`            | FastAPI 포트                              | `8100`       |
| `--no-browser`      | 브라우저 자동 실행 끄기                   |              |
| `--windowed`        | 전체화면 대신 일반 창                     |              |
| `--target-ip`       | DTAM 4001 수신 IP                         | `127.0.0.1`  |
| `--target-port`     | DTAM 4001 수신 UDP 포트                   | `17000`      |
| `--my-port`         | 로컬 UDP 포트 (SDK 바인딩)                | `17001`      |
| `--plan`            | 비행계획 JSON 경로 (반복 가능)            |              |
| `--clock`           | `external` / `wall` / `manual`            | `external`   |
| `--autostart`       | 부팅 직후 서비스 start                    |              |

예:

```bash
python DTAMAirMobility/AM_main.py \
    --target-ip 203.252.1.10 --target-port 17000 \
    --plan ./DTAMAirMobility/simpleDynamics/example_mission.json \
    --clock wall --autostart
```

### 3. GUI 사용법

1. **Publisher** : 수신 측 IP/Port 지정 후 Apply
2. **Flight Plans** : JSON 파일을 골라 Upload (여러 개 가능)
3. **Clock & Service** :
   - `external` — 외부 시뮬레이터가 `POST /api/clock/feed` 호출
   - `wall` — 실시간 벽시계 (Start 시점부터 flow)
   - `manual` — `Step once` 버튼으로 한 tick 씩 진행
4. **Fleet** : 각 UAM 의 state / elapsed / last NED · LLA 를 0.5 s 주기로 갱신

### 4. 프로그램적 사용 (다른 모듈에서 직접 호출)

```python
import json
from pathlib import Path
from DTAMAirMobility import IntegratedAirMobilityService, ClockMode

svc = IntegratedAirMobilityService(target_ip="127.0.0.1", target_port=17000)
svc.add_plans_from_json(json.loads(Path("mission.json").read_text(encoding="utf-8")))
svc.set_clock_mode(ClockMode.EXTERNAL)
svc.start()

# 시뮬레이터 매 틱마다:
svc.feed_time_hhmmss("09:10:00")
# ...
svc.close()
```

### 5. REST API

| Method | Path                            | 설명                                          |
|--------|---------------------------------|-----------------------------------------------|
| GET    | `/api/status`                   | 전체 상태 (publisher, fleet, sim time)        |
| POST   | `/api/publisher`                | `{target_ip, target_port, my_port}` 적용      |
| POST   | `/api/plans`                    | 단일 dict 또는 list 의 비행계획 등록         |
| POST   | `/api/plans/batch`              | 여러 비행계획을 리스트로 일괄 등록           |
| DELETE | `/api/plans/{vehicle_id}`       | 단일 제거                                     |
| DELETE | `/api/plans`                    | 전체 제거                                     |
| POST   | `/api/clock/mode`               | `{mode: "external|wall|manual"}`              |
| POST   | `/api/clock/feed`               | `{hms: "HH:MM:SS"}` 또는 `{seconds: float}`   |
| POST   | `/api/clock/step`               | manual 모드에서 1 tick 진행                   |
| POST   | `/api/service/start`            | 서비스 시작 (옵션 `{mode}`)                   |
| POST   | `/api/service/stop`             | 서비스 정지                                   |

## 이전 GUI 대비 제외한 기능

- AirSim RPC, pose 설정, 충돌 검사, pose frame 계산
- 웹 맵 / 타일 서버 / DEM / 경로 플래너 / 미션 exporter
- 텔레메트리 브리지, operator log, altitude profile 등
- i18n, 세팅 페이지, sidebar 등 원본 odt_mp 의 프런트 chrome

남긴 핵심은 **FlightPlan 로드 → 궤적 10 Hz → 좌표변환 → 4001 송신**
파이프라인과 그 상태를 보기 위한 얇은 대시보드뿐.
