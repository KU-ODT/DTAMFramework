# ICD - Camera Image Frame (MSG 4101)

| 항목 | 값 |
|---|---|
| Message ID | `4101` |
| Message Name | Camera Image Frame |
| 전송 방식 | WebSocket (`/ws/dtam`) |
| Wire Encoding | 단일 JSON WebSocket 메시지 + 선택적 Base64 이미지 필드 |
| 주기 | 송신 모듈 재량 |

## 1. 목적

MSG 4101은 Visualization이 카메라 이미지 프레임을 서버와 Operations Console로 전달할 때 사용한다. 이미지 데이터는 크기가 크기 때문에, 소형 차량 상태 메시지인 MSG 4001과 분리한다.

## 2. WebSocket 프레이밍

현재 ServerRevision 런타임은 4101을 다른 ICD 메시지와 같은 JSON envelope로 보낸다. 별도의 binary WebSocket frame은 사용하지 않는다.

```json
{
  "type": "message",
  "mid": "4101",
  "payload": {
    "message_id": 4101,
    "message_name": "Camera Image Frame",
    "timestamp": "2026-04-16T08:20:00.123Z",
    "vehicle_id": "UAM0001",
    "camera_name": "front_center",
    "image_type": "scene",
    "sequence": 1204,
    "width": 1280,
    "height": 720,
    "channels": 3,
    "pixel_format": "jpeg",
    "encoding": "jpeg",
    "payload_size": 86432
  },
  "image_b64": "<base64-encoded image bytes>"
}
```

`image_b64`는 metadata-only 테스트에서는 생략할 수 있지만, 정상 카메라 스트리밍에서는 인코딩된 이미지 바이트를 Base64로 담아야 한다.

## 3. Payload 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `message_id` | int | 예 | 고정값 `4101` |
| `message_name` | str | 아니오 | `Camera Image Frame` |
| `timestamp` | str | 예 | 캡처 시각, UTC ISO-8601 |
| `vehicle_id` | str | 예 | 비행체 ID, 예: `UAM0001` |
| `camera_name` | str | 예 | 카메라 이름 |
| `image_type` | str/int | 예 | 논리 이미지 타입 또는 AirSim image type |
| `sequence` | int | 예 | 프레임 순번 |
| `width` | int | 예 | 이미지 너비(px) |
| `height` | int | 예 | 이미지 높이(px) |
| `channels` | int | 예 | 채널 수 |
| `pixel_format` | str | 예 | 현재 런타임은 JPEG 프레임에 `jpeg` 사용 |
| `encoding` | str | 예 | `jpeg`, `png`, `raw` |
| `payload_size` | int | 예 | Base64 인코딩 전 이미지 바이트 수 |
| `checksum` | str | 아니오 | 선택적 payload checksum |
| `unit` | str | 아니오 | depth/scalar 이미지 단위 |
| `frame_id` | str | 아니오 | 좌표계 또는 카메라 frame ID |

## 4. 주의

- `DTAM_SDK.dtam_client._ws_client.DtamWsClient.send(..., image_bytes=...)`가 `image_bytes`를 `image_b64`로 변환한다.
- `DTAM_SimulationState`는 `image_b64`를 decode해 최신 프레임을 저장하고, MSG 4101을 서버 경유로 `monitoring` role에 forward한다.
- 현재 런타임에서는 `header_length + header_json + payload_binary` framing을 구현하지 않는다. 해당 방식은 이전 draft이며 `/ws/dtam`과 호환되지 않는다.
