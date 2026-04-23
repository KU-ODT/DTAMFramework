# ICD - 모듈 세팅 정보 (MSG 0001)

| 항목 | 값 |
|---|---|
| Message ID | `0001` |
| Message Name | 모듈 세팅 정보 |
| 전송 방식 | UDP |
| 인코딩 | JSON (UTF-8) |
| 용도 | 각 모듈이 자신의 수신 IP/포트를 서버에 보고 |

## 1. 최상위 구조

```json
{
  "Timestamp": "<ISO-8601 UTC>",
  "ModuleName": "<module name>",
  "IP": "<IPv4 address>",
  "UDPPort": 17000,
  "TCPPort": 17001
}
```

## 2. 필드 정의

| 필드 | 타입 | 값 / 패턴 | 설명 |
|---|---|---|---|
| `Timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | 보고 시각(UTC) |
| `ModuleName` | str | 비어 있지 않은 문자열 | 보고 모듈 이름 |
| `IP` | str | IPv4 주소 | 모듈이 동작 중인 컴퓨터 IP |
| `UDPPort` | int | `1`-`65535` | 모듈이 열어 둔 UDP 수신 포트 |
| `TCPPort` | int | `1`-`65535` | 모듈이 열어 둔 TCP 수신 포트 |

## 3. 예시

```json
{
  "Timestamp": "2026-04-17T00:00:00.000Z",
  "ModuleName": "MissionPlanner",
  "IP": "192.168.0.21",
  "UDPPort": 17000,
  "TCPPort": 17001
}
```

## 4. 검증 정책

- 필수 필드 누락 또는 타입 불일치는 오류이다.
- `ModuleName`은 빈 문자열일 수 없다.
- `IP`는 IPv4 주소 형식이어야 한다.
- `UDPPort`, `TCPPort`는 유효한 TCP/UDP 포트 범위 안에 있어야 한다.
