# ICD — Flight Plan Request (MSG 2001)

| 항목 | 값 |
|---|---|
| Message ID | `2001` |
| Message Name | 비행계획 생성 요청 |
| 전송 방식 | WebSocket (`/ws/dtam`) |
| 인코딩 | JSON (UTF-8) |
| 주기 | 이벤트성 |

## 1. 개요

1302는 1003 시나리오 설정 데이터를 기반으로 비행계획 생성을 요청하는 메시지이다.
`scenarioFileName`으로 어떤 시나리오에 대한 비행계획을 생성할지 지정한다.

## 2. 구조

```json
{
  "timestamp": "<ISO-8601 UTC>",
  "scenarioFileName": "<SCENARIO_FILE_NAME>"
}
```

## 3. 필드 정의

| 필드 | 타입 | 값/패턴 | 설명 |
|---|---|---|---|
| `timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | 요청 시각 (UTC) |
| `scenarioFileName` | str | 빈 문자열 불가 | 대상 시나리오 파일명 (1301에서 수신한 값) |

## 4. 예시

```json
{
  "timestamp": "2026-04-16T10:35:00.000Z",
  "scenarioFileName": "scenarioSetup_20260416T103000000Z.json"
}
```

## 5. 유효성 정책

- 필수 필드 누락 → 오류 (`ok=false`)
- 타입 불일치 → 오류
- `scenarioFileName` 빈 문자열 → 오류
