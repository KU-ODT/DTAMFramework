# ICD - 모듈 세팅 정보 (MSG 0001)

| 항목 | 값 |
|---|---|
| Message ID | `0001` |
| Message Name | 모듈 세팅 정보 |
| 전송 방식 | WebSocket (`/ws/dtam`) |
| 인코딩 | JSON (UTF-8) |
| 용도 | 각 모듈이 자신의 식별 정보(이름·역할)를 서버에 보고 |

> **변경 이력**: 이전(legacy UDP) 명세에는 `IP` / `UDPPort` / `TCPPort` 가 포함되었으나,
> WebSocket 단일 채널 체제에서는 모듈이 서버에 *접속* 하므로 네트워크 endpoint 보고가
> 불필요해 제거되었다. ``Role`` 필드가 추가되어 모듈 역할(vehicle/mission/...) 을 명시한다.

## 1. 최상위 구조

```json
{
  "Timestamp": "<ISO-8601 UTC>",
  "ModuleName": "<module name>",
  "Role": "<role>"
}
```

## 2. 필드 정의

| 필드 | 타입 | 값 / 패턴 | 설명 |
|---|---|---|---|
| `Timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | 보고 시각(UTC) |
| `ModuleName` | str | 비어 있지 않은 문자열 | 보고 모듈 이름 (예: `DTAMAirMobility`) |
| `Role` | str | `mission` \| `monitoring` \| `vehicle` \| `visual` \| `sim_state` | 모듈 역할 |

## 3. 예시

```json
{
  "Timestamp": "2026-04-28T00:00:00.000Z",
  "ModuleName": "DTAM_MissionPlanner",
  "Role": "mission"
}
```

## 4. 검증 정책

- 필수 필드 누락 또는 타입 불일치는 오류이다.
- `ModuleName` 은 빈 문자열일 수 없다.
- `Role` 은 SDK 의 `Role` enum 값 중 하나여야 한다.

## 5. 참고

- 동일 모듈은 별개의 `register` 메시지로도 `role` / `source` 를 서버에 알린다
  (`{"type": "register", "role": "vehicle", "source": "DTAMAirMobility"}`).
  MSG 0001 은 그 외 부가 정보(시작 시각 등)를 ICD 메시지로 정식 송신할 때 사용.
