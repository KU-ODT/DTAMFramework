# ICD — Common Time Info (MSG 0003)

| 항목 | 값 |
|---|---|
| Message ID | `0003` |
| Message Name | 공통 시간 정보 |
| 전송 방식 | WebSocket (`/ws/dtam`) |
| 인코딩 | JSON (UTF-8) |
| 주기 | 1 Hz (1초 주기) |

## 1. 개요

0003은 모든 모듈이 동일한 시간 기준을 공유하기 위한 공통 시간 정보 메시지이다.
`timestamp`는 실제 송신 시각이고, `simTime`은 시뮬레이션 내부에서 흐르는 시간이다.

## 2. 구조

```json
{
  "timestamp": "<ISO-8601 UTC>",
  "simTime": "<ISO-8601 UTC>"
}
```

## 3. 필드 정의

| 필드 | 타입 | 값/패턴 | 설명 |
|---|---|---|---|
| `timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | 실제 송신 시각 (UTC) |
| `simTime` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | 시뮬레이션 내부 시간 (UTC) |

## 4. 예시

```json
{
  "timestamp": "2026-04-16T12:00:01.000Z",
  "simTime": "2026-04-16T09:30:15.000Z"
}
```

## 5. 유효성 정책

- 필수 필드 누락 → 오류 (`ok=false`)
- 타입 불일치 → 오류
- `timestamp`, `simTime` 형식 불일치 → 오류

## 6. 운용 메모

- `timestamp`와 `simTime`은 다를 수 있다 (배속 재생, 일시 정지 등).
- 수신 모듈은 `simTime`을 기준으로 시뮬레이션 로직을 수행한다.
