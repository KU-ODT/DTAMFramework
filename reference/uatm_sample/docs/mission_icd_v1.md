# Mission ICD v1 Final

## 1. 목적

본 문서는 최종 합의된 `Mission ICD v1` 비행계획 데이터 구조를 정의한다.

이 문서의 범위는 단일 비행계획 1건을 표현하는 JSON 레코드이며, 최상위 구조는 아래 5개 축으로 고정한다.

- `flightPlanNumber`
- `aircraftId`
- `departure`
- `enRoute`
- `arrival`

권장 전송 형태는 단건 JSON 객체이며, 복수 건 전달이 필요하면 상위에서 배열로 감싼다.

## 2. 검토 결과

최종안의 큰 방향은 적절하다. 다만 구현 전에 아래 사항을 문서 기준으로 고정해야 한다.

### 2.1 반영한 정규화 규칙

- `departure.vertiport` 와 `arrival.vertiport` 는 동일 키를 사용하되, 반드시 각 섹션 내부에 중첩한다.
- `EIBT (Gate In)` 의 변수명은 `eibt` 로 고정한다.
- `ELDT (Landing)` 의 변수명은 `eldt` 로 고정한다.
- `Center_LLA` 의 변수명은 `centerLLA` 로 고정한다.
- `LLA.alt` 의 단위는 `m` 로 고정한다.
- `targetSpeed` 의 단위는 현재 AirSim/SITL 코드 기준에 맞춰 `m/s` 로 고정한다.

### 2.2 구현상 주의점

- 시간 필드는 모두 같은 기준 시계의 `HH:MM:SS` 문자열이어야 한다.
- `enRoute` 는 `seq` 오름차순 배열이어야 한다.
- 이전 세그먼트의 `endLLA` 와 다음 세그먼트의 `startLLA` 는 연속되도록 작성하는 것을 원칙으로 한다.
- 회전 세그먼트는 `phase` 가 `D`, `H` 인 경우로 제한한다.
- 비회전 세그먼트는 기본적으로 `A`, `B`, `C`, `E`, `F`, `G`, `I`, `J` 를 사용한다.
- 향후 `K` 를 다시 포함해야 하면 비회전 세그먼트와 동일한 구조로 표현한다.

## 3. Canonical JSON 구조

아래는 필드 모양을 빠르게 확인하기 위한 축약 예시다. 전체 `A~K` 미션 프로파일 예시는 `7.1` 절을 따른다.

```json
{
  "flightPlanNumber": 1201,
  "aircraftId": "UAM0001",
  "departure": {
    "vertiport": "Yeouido",
    "std": "09:00:00",
    "depGateNumber": "G3",
    "eobt": "09:02:00",
    "depFatoNumber": "F2",
    "etot": "09:10:00"
  },
  "enRoute": [
    {
      "seq": 1,
      "phase": "C",
      "startLLA": {"lat": 37.480790, "lon": 126.878697, "alt": 50},
      "endLLA": {"lat": 37.480790, "lon": 126.884000, "alt": 300},
      "targetSpeed": 40
    },
    {
      "seq": 2,
      "phase": "D",
      "startLLA": {"lat": 37.480790, "lon": 126.884000, "alt": 300},
      "endLLA": {"lat": 37.476500, "lon": 126.889500, "alt": 300},
      "targetSpeed": 60,
      "turnDirection": "CW",
      "centerLLA": {"lat": 37.478000, "lon": 126.887500, "alt": 300}
    }
  ],
  "arrival": {
    "vertiport": "Jamsil",
    "sta": "10:00:00",
    "arrGateNumber": "G1",
    "eibt": "09:58:00",
    "arrFatoNumber": "F1",
    "eldt": "09:50:00"
  }
}
```

## 4. 필드 정의

### 4.1 최상위 필드

| 필드 | 타입 | 필수 | 예시 | 설명 |
| --- | --- | --- | --- | --- |
| `flightPlanNumber` | integer | Y | `1201` | 비행계획 식별 번호 |
| `aircraftId` | string | Y | `UAM0001` | 기체 식별자 |
| `departure` | object | Y | - | 출발 정보 |
| `enRoute` | array | Y | - | 경로 세그먼트 배열 |
| `arrival` | object | Y | - | 도착 정보 |

### 4.2 `departure`

| 필드 | 타입 | 필수 | 예시 | 설명 |
| --- | --- | --- | --- | --- |
| `vertiport` | string | Y | `Yeouido` | 출발 버티포트 |
| `std` | string | Y | `09:00:00` | Scheduled Time of Departure |
| `depGateNumber` | string | Y | `G3` | 출발 게이트 번호 |
| `eobt` | string | Y | `09:02:00` | Estimated Off-Block Time |
| `depFatoNumber` | string | Y | `F2` | 출발 FATO 번호 |
| `etot` | string | Y | `09:10:00` | Estimated Takeoff Time |

### 4.3 `enRoute` 공통 필드

| 필드 | 타입 | 필수 | 예시 | 설명 |
| --- | --- | --- | --- | --- |
| `seq` | integer | Y | `1` | 세그먼트 순번 |
| `phase` | string | Y | `C` | 미션 프로파일 phase 코드 |
| `startLLA` | object | Y | `{"lat": 37.480790, "lon": 126.878697, "alt": 50}` | 시작 좌표 |
| `endLLA` | object | Y | `{"lat": 37.480790, "lon": 126.884000, "alt": 300}` | 종료 좌표 |
| `targetSpeed` | number | Y | `40` | 목표 속도, 단위 `m/s` |

### 4.4 `LLA` 좌표 객체

| 필드 | 타입 | 필수 | 예시 | 설명 |
| --- | --- | --- | --- | --- |
| `lat` | number | Y | `37.480790` | 위도 |
| `lon` | number | Y | `126.878697` | 경도 |
| `alt` | number | Y | `300` | 고도, 단위 `m` |

### 4.5 회전 세그먼트 전용 필드

회전 세그먼트는 `phase` 가 `D` 또는 `H` 인 경우만 사용한다.

| 필드 | 타입 | 필수 | 예시 | 설명 |
| --- | --- | --- | --- | --- |
| `turnDirection` | string | Y | `CW` | 회전 방향, `CW` 또는 `CCW` |
| `centerLLA` | object | Y | `{"lat": 37.478000, "lon": 126.887500, "alt": 300}` | 회전 중심 좌표 |

### 4.6 `arrival`

| 필드 | 타입 | 필수 | 예시 | 설명 |
| --- | --- | --- | --- | --- |
| `vertiport` | string | Y | `Jamsil` | 도착 버티포트 |
| `sta` | string | Y | `10:00:00` | Scheduled Time of Arrival |
| `arrGateNumber` | string | Y | `G1` | 도착 게이트 번호 |
| `eibt` | string | Y | `09:58:00` | Estimated In-Block Time |
| `arrFatoNumber` | string | Y | `F1` | 도착 FATO 번호 |
| `eldt` | string | Y | `09:50:00` | Estimated Landing Time |

## 5. Phase 규칙

### 5.1 비회전 세그먼트

| Phase | 의미 | 필드 | 예시 동작 |
| --- | --- | --- | --- |
| `A` | gate out taxi | 공통 필드만 사용 | 출발 gate 에서 dep FATO 까지 지상 이동 |
| `B` | vertical takeoff | 공통 필드만 사용 | dep FATO 에서 수직 상승 |
| `C` | departure transition | 공통 필드만 사용 | 이륙 직후 출발 방향으로 전이 |
| `E` | climb out | 공통 필드만 사용 | 순항 고도까지 상승 |
| `F` | cruise | 공통 필드만 사용 | 주 경로를 따라 순항 |
| `G` | arrival transition | 공통 필드만 사용 | 도착 버티포트 접근 전 감속 및 진입 |
| `I` | final approach | 공통 필드만 사용 | arr FATO 정렬 후 최종 접근 |
| `J` | landing | 공통 필드만 사용 | arr FATO 로 착륙 |
| `K` | gate in taxi | 필요 시 공통 필드만 사용 | arr FATO 에서 도착 gate 로 지상 이동 |

### 5.2 회전 세그먼트

| Phase | 의미 | 추가 필드 | 예시 동작 |
| --- | --- | --- | --- |
| `D` | departure turn | `turnDirection`, `centerLLA` | 출발 직후 corridor 진입을 위한 선회 |
| `H` | arrival turn | `turnDirection`, `centerLLA` | 도착 corridor 에서 final 접근 방향으로 선회 |

### 5.3 `A~K` 전체 미션 프로파일 예시

| Seq | Phase | 예시 설명 |
| --- | --- | --- |
| `1` | `A` | `Yeouido G3` 에서 `Yeouido F2` 로 taxi-out |
| `2` | `B` | `Yeouido F2` 에서 수직 상승 |
| `3` | `C` | 출발 전이 구간으로 진입 |
| `4` | `D` | 출발 회전 구간에서 corridor 정렬 |
| `5` | `E` | 순항 고도까지 climb-out |
| `6` | `F` | 주 corridor 구간 순항 |
| `7` | `G` | `Jamsil` 접근 transition |
| `8` | `H` | 도착 회전 구간에서 final 방향 정렬 |
| `9` | `I` | `Jamsil F1` 로 final approach |
| `10` | `J` | `Jamsil F1` 에 착륙 |
| `11` | `K` | `Jamsil F1` 에서 `Jamsil G1` 로 taxi-in |

## 6. 검증 규칙

아래 규칙을 만족해야 유효한 ICD 레코드로 본다.

1. `flightPlanNumber` 는 같은 배치 내에서 유일해야 한다.
2. `seq` 는 1부터 시작하는 연속 정수여야 한다.
3. `phase` 는 정의된 코드만 사용해야 한다.
4. `phase` 가 `D`, `H` 가 아니면 `turnDirection`, `centerLLA` 를 넣지 않는다.
5. `phase` 가 `D`, `H` 이면 `turnDirection`, `centerLLA` 를 반드시 넣는다.
6. 시간 순서는 `std <= eobt <= etot <= eldt <= eibt <= sta` 를 만족하는 것을 권장한다.
7. 모든 `LLA.alt` 는 동일 단위 `m` 를 사용해야 한다.
8. `targetSpeed` 는 모든 세그먼트에서 동일 단위 `m/s` 를 사용해야 한다.
9. 각 세그먼트의 좌표는 가능한 한 연속적으로 이어져야 한다.

## 7. 예시 데이터

### 7.1 단건 JSON 예시

```json
{
  "flightPlanNumber": 1201,
  "aircraftId": "UAM0001",
  "departure": {
    "vertiport": "Yeouido",
    "std": "09:00:00",
    "depGateNumber": "G3",
    "eobt": "09:02:00",
    "depFatoNumber": "F2",
    "etot": "09:10:00"
  },
  "enRoute": [
    {
      "seq": 1,
      "phase": "A",
      "startLLA": {"lat": 37.525450, "lon": 126.921420, "alt": 0},
      "endLLA": {"lat": 37.525680, "lon": 126.922050, "alt": 0},
      "targetSpeed": 8
    },
    {
      "seq": 2,
      "phase": "B",
      "startLLA": {"lat": 37.525680, "lon": 126.922050, "alt": 0},
      "endLLA": {"lat": 37.525680, "lon": 126.922050, "alt": 60},
      "targetSpeed": 10
    },
    {
      "seq": 3,
      "phase": "C",
      "startLLA": {"lat": 37.525680, "lon": 126.922050, "alt": 60},
      "endLLA": {"lat": 37.524900, "lon": 126.928500, "alt": 180},
      "targetSpeed": 35
    },
    {
      "seq": 4,
      "phase": "D",
      "startLLA": {"lat": 37.524900, "lon": 126.928500, "alt": 180},
      "endLLA": {"lat": 37.521800, "lon": 126.944500, "alt": 180},
      "targetSpeed": 45,
      "turnDirection": "CW",
      "centerLLA": {"lat": 37.523000, "lon": 126.936000, "alt": 180}
    },
    {
      "seq": 5,
      "phase": "E",
      "startLLA": {"lat": 37.521800, "lon": 126.944500, "alt": 180},
      "endLLA": {"lat": 37.518000, "lon": 126.970000, "alt": 300},
      "targetSpeed": 55
    },
    {
      "seq": 6,
      "phase": "F",
      "startLLA": {"lat": 37.518000, "lon": 126.970000, "alt": 300},
      "endLLA": {"lat": 37.513500, "lon": 127.066000, "alt": 300},
      "targetSpeed": 75
    },
    {
      "seq": 7,
      "phase": "G",
      "startLLA": {"lat": 37.513500, "lon": 127.066000, "alt": 300},
      "endLLA": {"lat": 37.512500, "lon": 127.086500, "alt": 220},
      "targetSpeed": 45
    },
    {
      "seq": 8,
      "phase": "H",
      "startLLA": {"lat": 37.512500, "lon": 127.086500, "alt": 220},
      "endLLA": {"lat": 37.513900, "lon": 127.099000, "alt": 220},
      "targetSpeed": 35,
      "turnDirection": "CCW",
      "centerLLA": {"lat": 37.511800, "lon": 127.092800, "alt": 220}
    },
    {
      "seq": 9,
      "phase": "I",
      "startLLA": {"lat": 37.513900, "lon": 127.099000, "alt": 220},
      "endLLA": {"lat": 37.513650, "lon": 127.104200, "alt": 80},
      "targetSpeed": 22
    },
    {
      "seq": 10,
      "phase": "J",
      "startLLA": {"lat": 37.513650, "lon": 127.104200, "alt": 80},
      "endLLA": {"lat": 37.513600, "lon": 127.104500, "alt": 0},
      "targetSpeed": 8
    },
    {
      "seq": 11,
      "phase": "K",
      "startLLA": {"lat": 37.513600, "lon": 127.104500, "alt": 0},
      "endLLA": {"lat": 37.514020, "lon": 127.103950, "alt": 0},
      "targetSpeed": 6
    }
  ],
  "arrival": {
    "vertiport": "Jamsil",
    "sta": "10:00:00",
    "arrGateNumber": "G1",
    "eibt": "09:58:00",
    "arrFatoNumber": "F1",
    "eldt": "09:50:00"
  }
}
```

### 7.2 시험 데이터 요약

| flightPlanNumber | aircraftId | departure | arrival | std | sta |
| --- | --- | --- | --- | --- | --- |
| `1201` | `UAM0001` | `Yeouido` | `Jamsil` | `09:00:00` | `10:00:00` |
| `1202` | `UAM0002` | `Magok` | `Yeouido` | `09:15:00` | `09:55:00` |
| `1203` | `UAM0003` | `Jamsil` | `Incheon` | `10:10:00` | `10:55:00` |

## 8. 권장 구현 메모

- 파서와 검증기는 본 문서의 중첩 구조를 기준으로 작성한다.
- CSV 또는 기존 포맷이 존재하더라도 최종 내부 표현은 본 JSON 구조로 통일한다.
- 향후 `MissionDispatch`, `MissionStatus`, `SimClock` 를 분리 정의하더라도, 계획 원본은 본 문서의 레코드를 기준으로 삼는다.
