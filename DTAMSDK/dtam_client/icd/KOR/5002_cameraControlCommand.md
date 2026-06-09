# ICD - 카메라 제어 명령 (MSG 5002)

| 항목 | 값 |
|---|---|
| Message ID | `5002` |
| Message Name | 카메라 제어 명령 |
| 전송 방식 | WebSocket (`/ws/dtam`) |
| 방향 | 운용자/서버 -> 시각화 |
| 주기 | 이벤트 기반 |

## 목적

MSG 5002는 시각화 카메라 조작 명령을 DTAM 서버를 통해 전달하기 위한 ICD이다. 정상 경로에서는 조이스틱 hat 카메라 pan/zoom을 Air Mobility -> Visualization REST 직결 대신 서버 포워딩으로 처리한다.

## Payload

```json
{
  "timestamp": "2026-04-29T12:00:00.000Z",
  "aircraftId": "UAM0001",
  "vehicleName": "",
  "cameraName": "front_center",
  "source": "joystick",
  "action": "adjust",
  "sequence": 1,
  "yawDeltaDeg": 6.0,
  "pitchDeltaDeg": 0.0,
  "focalLengthDelta": 0.0
}
```

## 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `timestamp` | string | 예 | UTC ISO-8601 시각. |
| `aircraftId` | string | 예 | VM vehicle-map 조회에 사용할 DTAM 비행체 ID. |
| `vehicleName` | string | 아니오 | AirSim 차량 이름. 비어 있으면 VM이 `aircraftId`로 해석한다. |
| `cameraName` | string | 아니오 | AirSim 카메라 이름. 기본값 `front_center`. |
| `source` | string | 아니오 | `joystick`, `keyboard`, `api`, `script`. |
| `action` | string | 아니오 | 현재는 `adjust`; 추후 명령 확장용. |
| `sequence` | int | 아니오 | 송신자 측 단조 증가 순번. |
| `yawDeltaDeg` | float | 아니오 | 카메라 yaw 변화량(deg). |
| `pitchDeltaDeg` | float | 아니오 | 카메라 pitch 변화량(deg). |
| `focalLengthDelta` | float | 아니오 | 초점거리 변화량. 양수는 zoom in, 음수는 zoom out. |

## 라우팅

- 포워딩 규칙: `5002 -> visual`
- `vehicleName`이 비어 있으면 Visualization Manager가 `aircraftId`를 vehicle-map으로 해석한다.
- VM은 AirSim camera director/RPC로 명령을 적용하고 manager event log에 기록한다.
