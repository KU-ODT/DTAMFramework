# ICD — Scheduled Flight (MSG 3001)

| 항목 | 값 |
|---|---|
| Message ID | `3001` |
| Message Name | 정기편 정보 |
| 전송 방식 | TCP |
| 인코딩 | JSON (UTF-8) |
| 주기 | 이벤트성 (편성 시 1회) |

## 1. 개요

3001은 정기편의 원본 비행계획 정보를 정의하는 메시지이다.
DB에는 `flightPlanNumber`-`planVersion` 형태로 저장할 수 있다.
예: 1201-1, 1201-2, 1201-3

3001은 항상 해당 버전의 전체 계획을 담는다.
새 버전이 생성되면 이전 버전은 더 이상 사용되지 않도록 `planStatus`로 관리한다.

### 1.1 저장 규칙

DTAM Server Emulator 는 세션(부팅) 단위 루트 폴더(`ServerStart_<UTC timestamp>`)
아래에 메시지 타입별 하위 폴더를 만들고, 비행계획은 비행체별 JSON 파일로 저장한다.

```
DB/
└── ServerStart_<timestamp>/
    └── ScheduledFlight/
        ├── 1201_UAM0001.json
        ├── 1202_UAM0002.json
        └── 1203_UAM0003.json
```

- **세션 폴더**: `ServerStart_<UTC timestamp>` (예: `ServerStart_20260420T103500000Z`).
  Server Emulator 가 기동될 때마다 하나씩 생성된다.
- **메시지 하위 폴더**: 세션 아래에 메시지 타입별로 만들어진다
  (`ScheduledFlight/`, `ScheduledFlightModification/` 등).
- **파일명**: `{flightPlanNumber}_{aircraftId}.json` (예: `1201_UAM0001.json`).
- 세션 폴더 경로는 MSG 2002 `DTAM Execute` 의 `flightPlanFolderName` 으로 참조되어,
  실행 당시 사용된 3001 파일들을 하위 모듈이 그대로 찾아볼 수 있다.

## 2. 최상위 구조

```json
{
  "flightPlanNumber": <int>,
  "planVersion": <int>,
  "planStatus": "<PLAN_STATUS>",
  "aircraftId": "<AIRCRAFT_ID>",
  "departure": { ... },
  "enRoute":   [ { ... }, ... ],
  "arrival":   { ... }
}
```

### 2.1 최상위 필드

| 필드 | 타입 | 범위/패턴 | 설명 |
|---|---|---|---|
| `flightPlanNumber` | int | 1 ~ 9,999,999 | 정기편 번호 |
| `planVersion` | int | 1 이상 | 계획 버전 번호 (수정될 때마다 증가) |
| `planStatus` | str | `active` / `superseded` / `discarded` | 계획 상태 |
| `aircraftId` | str | `^[A-Z]{2,8}\d{4}$` | 비행체 ID (예: `UAM0001`) |

### 2.2 planStatus 열거형

| 값 | 설명 |
|---|---|
| `active` | 현재 사용 가능한 최신 계획 |
| `superseded` | 더 최신 버전이 생성되어 사용 불가한 이전 계획 |
| `discarded` | 취소 또는 폐기되어 사용 불가한 계획 |

## 3. departure

| 필드 | 타입 | 형식 | 설명 |
|---|---|---|---|
| `vertiport`      | str | - | 출발 버티포트 |
| `std`            | str | `HH:MM:SS` | 정기 출발 시각 (STD) |
| `depGateNumber`  | str | - | 출발 게이트 번호 |
| `eobt`           | str | `HH:MM:SS` | 예상 블록이탈 시각 (EOBT) |
| `depFatoNumber`  | str | - | 출발 FATO 번호 |
| `etot`           | str | `HH:MM:SS` | 예상 이륙 시각 (ETOT) |

## 4. enRoute (비행 구간 배열)

배열 원소(1개 이상) 각각의 구조:

| 필드 | 타입 | 단위 | 범위/패턴 | 필수 | 설명 |
|---|---|---|---|---|---|
| `seq`           | int   | -   | 1 ~ 9999            | ✔ | 순서 (단조 증가) |
| `phase`         | str   | -   | `^[A-Z]$`           | ✔ | 단계 식별자 |
| `startLLA`      | LLA   | -   | 아래 §4.1           | ✔ | 시작점 |
| `endLLA`        | LLA   | -   | 아래 §4.1           | ✔ | 끝점 |
| `targetSpeed`   | float | m/s | 0 ~ 200             | ✔ | 목표 속도 |
| `turnDirection` | str   | -   | `CW` / `CCW`        | ✖ | 선회 방향 |
| `centerLLA`     | LLA   | -   | 아래 §4.1           | △ | `turnDirection` 있으면 **필수** |

### 4.1 LLA (공통)

| 필드 | 타입 | 단위 | 범위 |
|---|---|---|---|
| `lat` | float | deg | -90 ~ 90 |
| `lon` | float | deg | -180 ~ 180 |
| `alt` | float | m   | -500 ~ 20000 |

## 5. arrival

| 필드 | 타입 | 형식 | 설명 |
|---|---|---|---|
| `vertiport`      | str | - | 도착 버티포트 |
| `sta`            | str | `HH:MM:SS` | 정기 도착 시각 (STA) |
| `arrGateNumber`  | str | - | 도착 게이트 번호 |
| `eibt`           | str | `HH:MM:SS` | 예상 블록인 시각 (EIBT) |
| `arrFatoNumber`  | str | - | 도착 FATO 번호 |
| `eldt`           | str | `HH:MM:SS` | 예상 착륙 시각 (ELDT) |

## 6. 예시

```json
{
  "flightPlanNumber": 1201,
  "planVersion": 2,
  "planStatus": "active",
  "aircraftId": "UAM0001",
  "departure": {
    "vertiport": "Yeouido",
    "std": "09:08:00",
    "depGateNumber": "G5",
    "eobt": "09:10:00",
    "depFatoNumber": "F1",
    "etot": "09:15:00"
  },
  "enRoute": [
    {
      "seq": 1, "phase": "A",
      "startLLA": {"lat": 37.52545, "lon": 126.92142, "alt": 0},
      "endLLA": {"lat": 37.52568, "lon": 126.92205, "alt": 60},
      "targetSpeed": 8
    },
    {
      "seq": 2, "phase": "B",
      "startLLA": {"lat": 37.52568, "lon": 126.92205, "alt": 60},
      "endLLA": {"lat": 37.52490, "lon": 126.92850, "alt": 180},
      "targetSpeed": 30
    },
    {
      "seq": 3, "phase": "C",
      "startLLA": {"lat": 37.52490, "lon": 126.92850, "alt": 180},
      "endLLA": {"lat": 37.52180, "lon": 126.94450, "alt": 180},
      "targetSpeed": 45,
      "turnDirection": "CW",
      "centerLLA": {"lat": 37.52300, "lon": 126.93600, "alt": 180}
    }
  ],
  "arrival": {
    "vertiport": "Jamsil",
    "sta": "10:06:00",
    "arrGateNumber": "G1",
    "eibt": "10:04:00",
    "arrFatoNumber": "F1",
    "eldt": "09:58:00"
  }
}
```

## 7. 유효성 정책

- 필수 필드 누락/타입 불일치/범위 이탈/패턴 불일치 → 오류 (`ok=false`)
- `planVersion` 1 미만 → 오류
- `planStatus` 허용 값 외 → 오류
- `enRoute.seq` 는 단조 증가해야 함
- `turnDirection` 이 있으면 `centerLLA` 필수
- `aircraftId` 는 MSG 4001 과 동일 패턴 공유 (`common.AIRCRAFT_ID_PATTERN`)

## 8. 운용 규칙

- 시뮬레이터와 DB 조회 시 `planStatus`가 `active`인 데이터만 사용한다.
- 같은 `flightPlanNumber`에 대해 새 버전이 `active`가 되면, 이전 `active` 버전은 `superseded`로 변경한다.
- `discarded`는 운영자가 폐기한 계획 또는 무효 처리된 계획에 사용한다.
