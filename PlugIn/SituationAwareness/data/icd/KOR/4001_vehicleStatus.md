# ICD — Vehicle Status (MSG 4001)

| 항목 | 값 |
|---|---|
| Message ID | `4001` |
| Message Name | 비행체 상태 정보 |
| 전송 방식 | WebSocket (`/ws/dtam`) |
| 인코딩 | JSON (UTF-8) |
| 주기 | 송신측 재량 |

> Forwarding targets: `monitoring`, `visual`, `situation_awareness`.

## 1. 최상위 구조

```json
{
  "timestamp": "<ISO-8601 UTC>",
  "<VEHICLE_ID_1>": { "...": "..." },
  "<VEHICLE_ID_2>": { "...": "..." }
}
```

- `timestamp` 필수. 그 외 모든 키는 비행체 ID.
- 비행체 수 1~N 가변.

### 1.1 비행체 ID 규칙
- 정규식: `^[A-Z]{2,8}\d{4}$` (예: `UAM0001`)

### 1.2 timestamp
- 형식: `YYYY-MM-DDTHH:MM:SS.sssZ` (UTC)

## 2. 비행체 하위 구조

```json
{
  "currentWaypointId": "<FLIGHT_PLAN_NUMBER>-<SEQ | VERTIPORT-GATE>",
  "position": { "...": "..." },
  "attitude": { "...": "..." },
  "actuator": { "...": "..." },
  "propulsion": { "...": "..." },
  "gps": { "...": "..." },
  "imu": { "...": "..." },
  "barometer": { "...": "..." }
}
```

### 2.0 currentWaypointId

현재 비행체가 향하고 있는 목표 웨이포인트 식별자. 3001 정기편의 `flightPlanNumber`와 연계된다.

| 필드 | 타입 | 패턴 | 설명 |
|---|---|---|---|
| `currentWaypointId` | str | `^\d+-(\d+\|[A-Za-z0-9]+-[A-Za-z0-9]+)$` | 현재 목표 웨이포인트 |

**값 형식:**

| 상황 | 형식 | 예시 | 의미 |
|---|---|---|---|
| 비행 구간 진행 중 | `{flightPlanNumber}-{seq}` | `1201-5` | 1201편 enRoute seq 5로 향하는 중 |
| 출발 버티포트 | `{flightPlanNumber}-{vertiport}-{gate}` | `1201-Yeouido-G3` | 1201편 여의도 게이트 G3 |
| 도착 버티포트 | `{flightPlanNumber}-{vertiport}-{gate}` | `1201-Jamsil-G8` | 1201편 잠실 게이트 G8 |

### 2.1 position (NED)

`position`은 local NED 좌표이다. Mission replay 모드에서는 Air Mobility가
첫 송출 trajectory point를 replay 원점으로 사용하므로 첫 `4001` 샘플은
대략 `{ "north": 0, "east": 0, "down": 0 }`에서 시작한다.
AirSim/Unreal spawn 좌표는 이 필드에 더하지 않는다.

| 필드 | 타입 | 단위 | 범위 | 설명 |
|---|---|---:|---:|---|
| `north` | float | m | -10000 ~ 10000 | 북쪽 위치 |
| `east` | float | m | -10000 ~ 10000 | 동쪽 위치 |
| `down` | float | m | -5000 ~ 500 | 아래 위치 (음수 = 고도) |

### 2.2 attitude

| 필드 | 타입 | 단위 | 범위 | 설명 |
|---|---|---:|---:|---|
| `roll` | float | rad | -π ~ π | 롤 각도 |
| `pitch` | float | rad | -π/2 ~ π/2 | 피치 각도 |
| `yaw` | float | rad | -π ~ π | 요 각도 |

### 2.3 actuator

| 필드 | 타입 | 단위 | 범위 | 설명 |
|---|---|---:|---:|---|
| `tilt_left` | float | ratio | 0.0 ~ 1.0 | 좌측 틸트 명령/상태 |
| `tilt_right` | float | ratio | 0.0 ~ 1.0 | 우측 틸트 명령/상태 |
| `aileron` | float | deg | -30 ~ 30 | 에일러론 명령/상태 |
| `rudder_left` | float | deg | -30 ~ 30 | 좌측 러더베이터 명령/상태 |
| `rudder_right` | float | deg | -30 ~ 30 | 우측 러더베이터 명령/상태 |

### 2.4 propulsion

| 필드 | 타입 | 단위 | 길이 | 항목 범위 | 설명 |
|---|---|---:|---:|---:|---|
| `motor_rpm` | list\<float\> | rpm | 4 | 0 ~ 6000 | 모터 RPM (모터 1~4 순서) |

### 2.5 gps

| 필드 | 타입 | 단위 | 범위 | 설명 |
|---|---|---:|---:|---|
| `is_valid` | bool | - | `true` / `false` | GPS 유효 플래그 |
| `fix_type` | int | - | 0 ~ 3 | GNSS 수신 유형: 0 없음, 1 시각만, 2 2D, 3 3D |
| `latitude` | float | deg | -90 ~ 90 | WGS84 위도 |
| `longitude` | float | deg | -180 ~ 180 | WGS84 경도 |
| `altitude` | float | m | -1000 ~ 20000 | WGS84 고도 |
| `velocity_north` | float | m/s | -1000 ~ 1000 | NED 북쪽 속도 |
| `velocity_east` | float | m/s | -1000 ~ 1000 | NED 동쪽 속도 |
| `velocity_down` | float | m/s | -1000 ~ 1000 | NED 아래 속도 |
| `eph` | float | - | 0 ~ 100 | 수평 위치 오차 |
| `epv` | float | - | 0 ~ 100 | 수직 위치 오차 |

### 2.6 imu

| 필드 | 타입 | 단위 | 범위 | 설명 |
|---|---|---:|---:|---|
| `orientation` | object | - | 정규화 쿼터니언 | IMU 자세 쿼터니언 |
| `orientation.w` | float | - | -1 ~ 1 | 쿼터니언 W |
| `orientation.x` | float | - | -1 ~ 1 | 쿼터니언 X |
| `orientation.y` | float | - | -1 ~ 1 | 쿼터니언 Y |
| `orientation.z` | float | - | -1 ~ 1 | 쿼터니언 Z |
| `angular_velocity` | object | rad/s | -100 ~ 100 | 각속도 벡터 |
| `angular_velocity.x` | float | rad/s | -100 ~ 100 | 각속도 X |
| `angular_velocity.y` | float | rad/s | -100 ~ 100 | 각속도 Y |
| `angular_velocity.z` | float | rad/s | -100 ~ 100 | 각속도 Z |
| `linear_acceleration` | object | m/s² | -200 ~ 200 | 선형 가속도 벡터 |
| `linear_acceleration.x` | float | m/s² | -200 ~ 200 | 선형 가속도 X |
| `linear_acceleration.y` | float | m/s² | -200 ~ 200 | 선형 가속도 Y |
| `linear_acceleration.z` | float | m/s² | -200 ~ 200 | 선형 가속도 Z |

### 2.7 barometer

| 필드 | 타입 | 단위 | 범위 | 설명 |
|---|---|---:|---:|---|
| `altitude` | float | m | -1000 ~ 20000 | 기압 고도 |
| `pressure` | float | Pa | 10000 ~ 120000 | 대기압 |
| `qnh` | float | hPa | 800 ~ 1200 | 해면 기압 설정 |

## 3. 예시

```json
{
  "timestamp": "2026-04-15T03:01:00.123Z",
  "UAM0001": {
    "currentWaypointId": "1201-5",
    "position": {
      "north": 152.4,
      "east": -37.8,
      "down": -420.0
    },
    "attitude": {
      "roll": 0.04,
      "pitch": -0.09,
      "yaw": 1.57
    },
    "actuator": {
      "tilt_left": 0.32,
      "tilt_right": 0.31,
      "aileron": 6.5,
      "rudder_left": -2.0,
      "rudder_right": 2.0
    },
    "propulsion": {
      "motor_rpm": [2450.0, 2475.0, 2440.0, 2460.0]
    },
    "gps": {
      "is_valid": true,
      "fix_type": 3,
      "latitude": 37.241231,
      "longitude": 127.177412,
      "altitude": 420.0,
      "velocity_north": 12.5,
      "velocity_east": -1.2,
      "velocity_down": -0.4,
      "eph": 0.8,
      "epv": 1.1
    },
    "imu": {
      "orientation": {
        "w": 0.7071,
        "x": 0.0,
        "y": 0.0,
        "z": 0.7071
      },
      "angular_velocity": {
        "x": 0.01,
        "y": -0.02,
        "z": 0.03
      },
      "linear_acceleration": {
        "x": 0.12,
        "y": -0.04,
        "z": 9.78
      }
    },
    "barometer": {
      "altitude": 419.3,
      "pressure": 96422.5,
      "qnh": 1013.25
    }
  }
}
```

## 4. 유효성 정책

- 필수 필드 누락 → 오류 (`ok=false`)
- 타입 불일치 → 오류 (`ok=false`)
- 범위 이탈 → 오류 (`ok=false`)
- 비행체 ID 패턴 불일치 → 오류 (`ok=false`)
- `propulsion.motor_rpm` 길이 불일치 → 오류 (`ok=false`)
- `imu.orientation`은 구현 허용 오차 내에서 정규화되어야 함
