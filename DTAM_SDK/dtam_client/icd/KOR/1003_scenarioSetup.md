# ICD — Scenario Setup (MSG 1003)

| 항목 | 값 |
|---|---|
| Message ID | `1003` |
| Message Name | 시나리오 설정 |
| 전송 방식 | WebSocket (`/ws/dtam`) |
| 인코딩 | JSON (UTF-8) |
| 주기 | 이벤트성 (시나리오 로드/변경 시 1회) |

## 1. 개요

1003은 시뮬레이션에 사용할 시나리오 기본 설정 데이터를 정의하는 메시지이다.

운용 시간, 버티포트 정보, 항로 웨이포인트 네트워크, 총 비행기 투입 수, 대표 비행체 종류를 한 번에 전달한다.

1003은 개별 비행계획을 직접 나타내는 메시지가 아니라, 이후 비행계획 생성 또는 시뮬레이션 초기화에 사용되는 원천 시나리오 데이터이다.

## 2. 최상위 구조

```json
{
  "timestamp": "<ISO-8601 UTC>",
  "operationTime": { ... },
  "vertiports": [ ... ],
  "routeNetwork": { "waypoints": [ ... ] },
  "totalAircraftCount": <int>,
  "mainVehicleType": "<KP2A | JobyS4>"
}
```

### 2.1 최상위 필드

| 필드 | 타입 | 값/범위 | 설명 |
|---|---|---|---|
| `timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | 시나리오 설정 송신 시각 (UTC) |
| `scenarioFileName` | str | `scenarioSetup_<timestamp>.json` | 수신 시 저장할 파일명 |
| `operationTime` | object | - | 시나리오 운용 시간 |
| `vertiports` | array | 1개 이상 | 사용할 버티포트 목록 |
| `routeNetwork` | object | - | 사용할 항로 네트워크 |
| `totalAircraftCount` | int | 1 ~ 100000 | 총 투입 비행기 수 |
| `mainVehicleType` | str | `KP2A` / `JobyS4` | 대표 비행체 종류 |

## 3. operationTime

```json
"operationTime": {
  "startTime": "HH:MM:SS",
  "endTime": "HH:MM:SS"
}
```

| 필드 | 타입 | 형식 | 설명 |
|---|---|---|---|
| `startTime` | str | `HH:MM:SS` | 운용 시작 시각 |
| `endTime` | str | `HH:MM:SS` | 운용 종료 시각 |

## 4. vertiports

```json
{
  "name": "<VERTIPORT_NAME>",
  "class": "<port | hub>",
  "lat": <float>,
  "lon": <float>,
  "angleDegrees": <float>
}
```

| 필드 | 타입 | 단위 | 범위 | 설명 |
|---|---|---|---|---|
| `name` | str | - | 빈 문자열 불가 | 버티포트 이름 |
| `class` | str | - | `port` / `hub` | 버티포트 분류 |
| `lat` | float | deg | -90 ~ 90 | 위도 |
| `lon` | float | deg | -180 ~ 180 | 경도 |
| `angleDegrees` | float | deg | 0 ~ 360 | 버티포트 기준 각도 |

## 5. routeNetwork

```json
"routeNetwork": {
  "waypoints": [
    {
      "waypointId": "<WAYPOINT_ID>",
      "waypointName": "<WAYPOINT_NAME>",
      "lat": <float>,
      "lon": <float>,
      "altFt": <float>,
      "links": ["<WAYPOINT_ID>", "..."]
    }
  ]
}
```

| 필드 | 타입 | 단위 | 범위 | 설명 |
|---|---|---|---|---|
| `waypointId` | str | - | `^[A-Za-z0-9_-]{1,32}$` | 웨이포인트 고유 ID |
| `waypointName` | str | - | 빈 문자열 불가 | 웨이포인트 표시 이름 |
| `lat` | float | deg | -90 ~ 90 | 위도 |
| `lon` | float | deg | -180 ~ 180 | 경도 |
| `altFt` | float | ft | 0 ~ 60000 | 고도 |
| `links` | array\<str\> | - | 1개 이상 | 연결된 인접 웨이포인트 ID 목록 |

### 5.1 links 규칙

- 동일 메시지 내 존재하는 `waypointId`만 참조
- 자기 자신 참조 불가
- 중복 링크 불가

## 6. 예시

```json
{
  "timestamp": "2026-04-16T10:30:00.000Z",
  "scenarioFileName": "scenarioSetup_20260416T103000000Z.json",
  "operationTime": {
    "startTime": "08:00:00",
    "endTime": "20:00:00"
  },
  "vertiports": [
    { "name": "영등포", "class": "port", "lat": 37.526513, "lon": 126.922845, "angleDegrees": 322.0 },
    { "name": "잠실",   "class": "port", "lat": 37.514368, "lon": 127.069068, "angleDegrees": 83.0 },
    { "name": "상암",   "class": "hub",  "lat": 37.562282, "lon": 126.890156, "angleDegrees": 38.0 }
  ],
  "routeNetwork": {
    "waypoints": [
      { "waypointId": "WP001", "waypointName": "가양대교 남단", "lat": 37.569391, "lon": 126.861026, "altFt": 1000.0, "links": ["WP002", "WP003"] },
      { "waypointId": "WP002", "waypointName": "염창교",       "lat": 37.553824, "lon": 126.875819, "altFt": 1000.0, "links": ["WP001", "WP003"] },
      { "waypointId": "WP003", "waypointName": "목동교",       "lat": 37.530667, "lon": 126.888262, "altFt": 1000.0, "links": ["WP002"] }
    ]
  },
  "totalAircraftCount": 20,
  "mainVehicleType": "JobyS4"
}
```

## 7. 유효성 정책

- 필수 필드 누락 → 오류 (`ok=false`)
- 타입 불일치 → 오류
- `operationTime.startTime >= endTime` → 오류
- `vertiports` 길이 0 → 오류
- `vertiports.name` 중복 → 오류
- `routeNetwork.waypoints` 길이 0 → 오류
- `waypointId` 중복 → 오류
- `links`가 존재하지 않는 `waypointId` 참조 → 오류
- `links`에 자기 자신 포함 → 오류
- `totalAircraftCount` 1 미만 → 오류
- `mainVehicleType` 허용 값 외 → 오류

## 8. 운용 메모

- 1003은 시나리오 원천 설정 데이터이며, 개별 비행편을 직접 표현하지 않는다.
- `altFt`는 시나리오 입력 원본 단위인 ft를 유지한다. 비행 수행 시 필요에 따라 m로 변환한다.
- 본 버전은 단일 대표 기종 기준이다. 대표 제어 방식은 1001 메시지의 `singleFlight.vehicleSimType.mainVehicleController`에서 설정한다.
