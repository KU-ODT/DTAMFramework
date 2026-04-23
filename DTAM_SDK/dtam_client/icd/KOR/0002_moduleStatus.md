# ICD — Module Status (MSG 0002)

| 항목 | 값 |
|---|---|
| Message ID | `0002` |
| Message Name | 모듈 상태 보고 |
| 전송 방식 | UDP |
| 인코딩 | JSON (UTF-8) |
| 주기 | 1 Hz (1초 주기) |

## 1. 최상위 구조

```json
{
  "timestamp": "<ISO-8601 UTC>",
  "source":    "<모듈 영문 이름>",
  "status":    <int>
}
```

## 2. 필드 정의

| 필드 | 타입 | 값/패턴 | 설명 |
|---|---|---|---|
| `timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | 송신 시각 (UTC) |
| `source`    | str | 영문 모듈명 | 보고 모듈의 영문 이름 |
| `status`    | int | `1` | 상태 코드 (1 = 정상) |

## 3. 예시

```json
{
  "timestamp": "2026-04-16T05:30:00.000Z",
  "source": "FlightDynamics",
  "status": 1
}
```

## 4. 유효성 정책

- 누락/타입 불일치 → 오류 (`ok=false`)
- `source`는 빈 문자열 불가
- `status` 값이 허용 범위 외 → 오류
