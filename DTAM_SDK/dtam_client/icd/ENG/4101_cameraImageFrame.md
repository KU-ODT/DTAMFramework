# ICD - Camera Image Frame (MSG 4101)

| Item | Value |
|---|---|
| Message ID | `4101` |
| Message Name | Camera Image Frame |
| Transport | WebSocket (`/ws/dtam`) |
| Wire Encoding | Single JSON WebSocket message with optional Base64 image field |
| Rate | Sender discretion |

## 1. Purpose

MSG 4101 transfers camera image frames from Visualization to the server and Operations Console. It is separate from MSG 4001 because images are large while 4001 must remain a small vehicle-status message.

## 2. WebSocket Framing

The current ServerRevision runtime sends 4101 as the same JSON envelope used by all ICD WebSocket messages. Binary WebSocket frames are not used.

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

`image_b64` is optional only for metadata-only/status testing. In normal camera streaming it should contain the encoded image bytes.

## 3. Payload Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `message_id` | int | Yes | Must be `4101` |
| `message_name` | str | No | `Camera Image Frame` |
| `timestamp` | str | Yes | Capture time, UTC ISO-8601 |
| `vehicle_id` | str | Yes | Vehicle ID, for example `UAM0001` |
| `camera_name` | str | Yes | Camera name |
| `image_type` | str/int | Yes | Logical image type or AirSim image type |
| `sequence` | int | Yes | Monotonic frame sequence |
| `width` | int | Yes | Image width in pixels |
| `height` | int | Yes | Image height in pixels |
| `channels` | int | Yes | Channel count |
| `pixel_format` | str | Yes | Current runtime uses `jpeg` for JPEG frames |
| `encoding` | str | Yes | `jpeg`, `png`, or `raw` |
| `payload_size` | int | Yes | Number of bytes before Base64 encoding |
| `checksum` | str | No | Optional payload checksum |
| `unit` | str | No | Physical unit for depth/scalar images |
| `frame_id` | str | No | Coordinate/camera frame identifier |

## 4. Notes

- `DTAM_SDK.dtam_client._ws_client.DtamWsClient.send(..., image_bytes=...)` converts `image_bytes` to `image_b64`.
- `DTAM_SimulationState` decodes `image_b64`, stores the latest frame, and forwards MSG 4101 through the server to the `monitoring` role.
- Do not implement `header_length + header_json + payload_binary` for the current runtime. That framing belongs to the previous draft and is not compatible with `/ws/dtam`.
