# ICD - 수동 조종 입력 (MSG 5001)

| 항목 | 값 |
|---|---|
| Message ID | `5001` |
| Message Name | 수동 조종 입력 |
| 전송 방식 | WebSocket (`/ws/dtam`) |
| 방향 | 운용자/서버 -> 비행체 |
| 기준 주기 | 입력 활성 중 20 Hz |

## 목적

MSG 5001은 키보드, 조이스틱, 수동 API 조종축 입력을 DTAM 서버를 통해 전달하기 위한 ICD이다. 서버는 payload를 파싱/저장한 뒤 Air Mobility(`vehicle`) 모듈로 포워딩한다.

## Payload

```json
{
  "timestamp": "2026-04-29T12:00:00.000Z",
  "aircraftId": "UAM0001",
  "source": "keyboard",
  "controlMode": "keyboard",
  "sequence": 1,
  "active": true,
  "axes": {
    "roll": 0.0,
    "pitch": 0.5,
    "yaw": 0.0,
    "throttle": 0.2
  },
  "buttons": [],
  "hats": [],
  "rawAxes": {}
}
```

## 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `timestamp` | string | 예 | UTC ISO-8601 시각. |
| `aircraftId` | string | 예 | 대상 DTAM 비행체 ID. 예: `UAM0001`. |
| `source` | string | 예 | `keyboard`, `joystick`, `api`, `script`. |
| `controlMode` | string | 예 | `keyboard`, `joystick`, `manual`, `mission`. |
| `sequence` | int | 아니오 | 송신자 측 단조 증가 순번. |
| `active` | bool | 아니오 | `false`이면 중립 조종축/입력 정지로 처리. |
| `axes.roll` | float | 예 | 좌우 조종 명령. `-1.0..1.0`. |
| `axes.pitch` | float | 예 | 전후 조종 명령. `-1.0..1.0`. |
| `axes.yaw` | float | 예 | 요 조종 명령. `-1.0..1.0`. |
| `axes.throttle` | float | 예 | 상승/하강 조종 명령. `-1.0..1.0`. |
| `buttons` | list<int> | 아니오 | 눌린 조이스틱 버튼 번호. |
| `hats` | list<[int,int]> | 아니오 | 조이스틱 hat 상태. |
| `rawAxes` | object | 아니오 | shaping 전 원시 조이스틱 축 값. |

## 라우팅

- 포워딩 규칙: `5001 -> vehicle`
- Air Mobility는 이 입력을 manual kinematic dynamics에 반영하고, 결과 상태를 기존처럼 `4001 Vehicle Status`로 송신한다.
- `controlMode`가 `mission`이면 수동 입력을 중립화하고 임무/오토파일럿 모드로 복귀한다.
