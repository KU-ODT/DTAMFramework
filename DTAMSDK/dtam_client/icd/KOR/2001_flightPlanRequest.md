# ICD — Flight Plan Request (MSG 2001)

| 항목 | 값 |
|---|---|
| Message ID | `2001` |
| Message Name | 비행계획 생성 요청 |
| 방향 | `user|psu|uao -> server` |
| 전송 방식 | WebSocket (`/ws/dtam`) |
| 인코딩 | JSON (UTF-8) |
| 주기 | 이벤트성 |

## 1. 개요

2001은 1003 시나리오 설정 데이터를 기반으로 비행계획 생성을 요청하는 메시지이다.
`scenarioFileName`으로 어떤 시나리오에 대한 비행계획을 생성할지 지정한다.

## 2. 구조

```json
{
  "timestamp": "<ISO-8601 UTC>",
  "scenarioFileName": "<SCENARIO_FILE_NAME>",
  "flightPlanNumber": "<TARGET_3001_NUMBER>",
  "reasonCode": "<REASON_CODE>",
  "triggeringEventId": "<EVENT_ID>",
  "arrivalVertiportHint": "<VERTIPORT_ID>"
}
```

송신자(Senders): `user` (OperationModule 경유), `psu`, `uao`
수신자(Receivers): `mission` (IntegrationHub가 포워딩)

## 3. 필드 정의

| 필드 | 타입 | 값/패턴 | 설명 |
|---|---|---|---|
| `timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | 요청 시각 (UTC) |
| `scenarioFileName` | str | 빈 문자열 불가 | 대상 시나리오 파일명 (1003에서 수신한 값) |
| `flightPlanNumber` | int (옵션) | 기존 3001 번호 | 재계획(re-plan) 대상이 되는 기존 비행계획 번호. 신규 생성 시 생략 |
| `reasonCode` | str (옵션) | enum (아래 표) | 본 요청을 발생시킨 사유 코드 |
| `triggeringEventId` | str (옵션) | 예: `WARN-UAM0001-20260610-0001` (4002.eventId), `COL-UAM0001-000001` (4103.eventId) | 본 요청을 트리거한 이벤트 ID |
| `arrivalVertiportHint` | str (옵션) | 버티포트 ID | 송신자(PSU/UAO)가 권고하는 대체 도착 버티포트. Mission Planner는 이를 강한 힌트로 취급하나, 최종 라우팅 책임은 Mission에 있다 |

### 3.1 `reasonCode` enum

| 코드 | 출처/의미 |
|---|---|
| `LOW_BATTERY` | 4002.eventType=LOW_BATTERY 에서 유래 |
| `BATTERY_OVERHEAT` | 4002.eventType 에서 유래 |
| `BATTERY_VOLTAGE_LOW` | 4002.eventType 에서 유래 |
| `TRAFFIC_CONFLICT` | PSU 트래픽 디컨플릭션 |
| `LOSS_OF_SEPARATION_RISK` | PSU 코리도 분석 |
| `CORRIDOR_BLOCKED` | PSU |
| `WEATHER` | PSU/UAO |
| `VERTIPORT_CAPACITY` | VPO |
| `VERTIPORT_UNAVAILABLE` | VPO |
| `OPERATOR_REQUEST` | OperationModule 경유 수동 요청 |

## 4. 예시

```json
{
  "timestamp": "2026-04-16T10:35:00.000Z",
  "scenarioFileName": "scenarioSetup_20260416T103000000Z.json"
}
```

### 4.1 시나리오별 사용 예시

#### S1 — Nominal (신규 비행계획 생성)

4개의 옵션 필드가 모두 부재(absent)한다.

```json
{
  "timestamp": "2026-06-10T09:00:00.000Z",
  "scenarioFileName": "morning_route_KU_Yeouido.json"
}
```

#### S2 — PSU 트래픽 충돌에 의한 재계획

```json
{
  "timestamp": "2026-06-10T09:15:00.000Z",
  "scenarioFileName": "morning_route_KU_Yeouido.json",
  "flightPlanNumber": 1201,
  "reasonCode": "TRAFFIC_CONFLICT",
  "triggeringEventId": "PSU-CONFLICT-1201-20260610-0001"
}
```

#### S3 — UAO/PSU 저전압 대체 버티포트 (4002 LOW_BATTERY 후속)

```json
{
  "timestamp": "2026-06-10T09:30:15.000Z",
  "scenarioFileName": "morning_route_KU_Yeouido.json",
  "flightPlanNumber": 1201,
  "reasonCode": "LOW_BATTERY",
  "triggeringEventId": "WARN-UAM0001-20260610-0001",
  "arrivalVertiportHint": "VP_KU"
}
```

> 참고: 4개의 옵션 필드(`flightPlanNumber`, `reasonCode`, `triggeringEventId`, `arrivalVertiportHint`)는 **S1에서는 모두 부재**하며, **S2/S3에서는 존재**한다 (S2는 `arrivalVertiportHint` 미사용, S3는 4개 모두 사용).

## 5. 유효성 정책

- 필수 필드 누락 → 오류 (`ok=false`)
- 타입 불일치 → 오류
- `scenarioFileName` 빈 문자열 → 오류
