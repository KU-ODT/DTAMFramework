# ICD - Camera Image Frame (MSG 4101)

| Item | Value |
|---|---|
| Message ID | 4101 |
| Message Name | Camera Image Frame |
| Transport | WebSocket (`/ws/dtam`) |
| Encoding | JSON envelope plus optional Base64 image field |
| Rate | Decided by sender module |

MSG 4101 carries camera image frames from the Visualization module through the server to Operations Console and Situation Awareness plug-in. Image data is separated from MSG 4001 vehicle status because it can be large.

## Payload fields

| Field | Type | Required | Description |
|---|---|---|---|
| `message_id` | int | yes | Fixed value `4101`. |
| `message_name` | string | no | `Camera Image Frame`. |
| `timestamp` | string | yes | Capture time in UTC ISO-8601. |
| `vehicle_id` | string | yes | Vehicle ID, e.g. `UAM0001`. |
| `camera_name` | string | yes | Camera name. |
| `image_type` | string/int | yes | Source image type or AirSim image type. |
| `sequence` | int | yes | Frame sequence number. |
| `width` | int | yes | Image width in pixels. |
| `height` | int | yes | Image height in pixels. |
| `channels` | int | yes | Channel count. |
| `pixel_format` | string | yes | Example: `jpeg`. |
| `encoding` | string | yes | `jpeg`, `png`, or `raw`. |
| `payload_size` | int | yes | Image byte size before Base64 encoding. |
| `checksum` | string | no | Optional payload checksum. |
| `unit` | string | no | Unit for depth/scalar images. |
| `frame_id` | string | no | Coordinate or camera frame ID. |

## Processing

- `DtamWsClient.send(..., image_bytes=...)` converts `image_bytes` to `image_b64`.
- StateServerModule decodes `image_b64`, stores the latest frame, and forwards MSG 4101 to the `monitoring` and `situation_awareness` roles.
- SDK 수신자는 envelope의 `image_b64`를 파싱된 `Msg4101_CameraImageFrame.image_b64` 필드에도 복사해 플러그인이 이미지에 직접 접근할 수 있게 합니다.
