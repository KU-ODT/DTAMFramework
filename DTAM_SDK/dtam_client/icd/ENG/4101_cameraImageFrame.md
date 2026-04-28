# ICD — Camera Image Frame (MSG 4101)

| Item | Value |
|---|---|
| Message ID | `4101` |
| Message Name | Camera Image Frame |
| Transport | WebSocket (`/ws/dtam`) |
| Encoding | JSON header (UTF-8) + binary payload |
| Rate | Sender discretion |

## 1. Purpose

MSG 4101 transfers camera image frames from a vehicle or simulator to a receiving server.

This message is intentionally separated from MSG 4001 Vehicle Status because image data can be large. MSG 4001 should remain a small status message, while MSG 4101 carries image metadata and the associated binary image payload.

## 2. Framing

```text
[header_length][header_json][payload_binary]
```

| Part | Type | Size | Description |
|---|---|---:|---|
| `header_length` | uint32 | 4 bytes | Byte length of `header_json`, unsigned little-endian |
| `header_json` | UTF-8 JSON | variable | Metadata for the image frame |
| `payload_binary` | byte[] | variable | Encoded image bytes |

## 3. Header Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `message_id` | int | ✔ | Must be `4101` |
| `message_name` | str | ✔ | Must be `Camera Image Frame` |
| `timestamp` | str | ✔ | Image capture time (UTC, ISO-8601) |
| `vehicle_id` | str | ✔ | Vehicle ID (`^[A-Z]{2,8}\d{4}$`) |
| `camera_name` | str | ✔ | Camera name |
| `image_type` | str | ✔ | Logical image type |
| `sequence` | int | ✔ | Monotonic frame sequence number per vehicle-camera stream |
| `width` | int | ✔ | Image width in pixels |
| `height` | int | ✔ | Image height in pixels |
| `channels` | int | ✔ | Number of image channels |
| `pixel_format` | str | ✔ | Pixel format |
| `encoding` | str | ✔ | Payload encoding |
| `payload_size` | int | ✔ | Number of bytes in `payload_binary` |
| `checksum` | str | ✖ | Payload checksum (recommended) |
| `unit` | str | ✖ | Physical unit for depth or scalar images |
| `frame_id` | str | ✖ | Coordinate frame or camera frame identifier |

### 3.1 camera_name recommended values

| Value | Description |
|---|---|
| `front_center` | Forward camera |
| `front_left` | Forward-left camera |
| `front_right` | Forward-right camera |
| `bottom_center` | Downward camera |
| `back_center` | Rear camera |

### 3.2 image_type enum

| Value | Description |
|---|---|
| `scene` | RGB visual image |
| `depth_planar` | Planar depth image |
| `depth_perspective` | Perspective depth image |
| `depth_vis` | Depth visualization image |
| `segmentation` | Segmentation image |
| `surface_normals` | Surface normal image |
| `infrared` | Infrared image |
| `optical_flow` | Optical flow data |
| `optical_flow_vis` | Optical flow visualization image |

### 3.3 pixel_format enum

| Value | Description |
|---|---|
| `rgb8` | 8-bit RGB, 3 channels |
| `rgba8` | 8-bit RGBA, 4 channels |
| `gray8` | 8-bit grayscale, 1 channel |
| `gray16` | 16-bit grayscale, 1 channel |
| `float32` | 32-bit float, 1 or more channels |
| `vector2_float32` | 2-channel float vector |

### 3.4 encoding enum

| Value | Payload Type | Recommended Use |
|---|---|---|
| `jpeg` | JPEG bytes | RGB scene images |
| `png` | PNG bytes | Lossless RGB, segmentation, masks |
| `raw` | Raw pixel bytes | Internal use or low-resolution |
| `depth_png` | PNG bytes | Depth encoded as unsigned integer image |

## 4. Examples

### 4.1 RGB Scene Frame Header

```json
{
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
  "pixel_format": "rgb8",
  "encoding": "jpeg",
  "payload_size": 86432,
  "checksum": "sha256:3f786850e387550fdab836ed7e6dc881de23001b"
}
```

### 4.2 Depth Frame Header

```json
{
  "message_id": 4101,
  "message_name": "Camera Image Frame",
  "timestamp": "2026-04-16T08:20:00.156Z",
  "vehicle_id": "UAM0001",
  "camera_name": "front_center",
  "image_type": "depth_planar",
  "sequence": 1205,
  "width": 640,
  "height": 480,
  "channels": 1,
  "pixel_format": "gray16",
  "encoding": "depth_png",
  "unit": "mm",
  "payload_size": 92340
}
```

## 5. Receiver Behavior

1. Read 4 bytes as `header_length`.
2. Decode `header_length` as unsigned little-endian uint32.
3. Read `header_length` bytes as UTF-8 JSON.
4. Parse and validate `header_json`.
5. Read exactly `payload_size` bytes as `payload_binary`.
6. Validate checksum if `checksum` is provided.
7. Decode or relay `payload_binary` according to `encoding`.

## 6. Validation Policy

- Missing required field -> error (`ok=false`)
- Type mismatch -> error (`ok=false`)
- Vehicle ID pattern mismatch -> error (`ok=false`)
- Unsupported `image_type` -> error (`ok=false`)
- Unsupported `pixel_format` -> error (`ok=false`)
- Unsupported `encoding` -> error (`ok=false`)
- `width <= 0` or `height <= 0` -> error (`ok=false`)
- `payload_size` mismatch -> error (`ok=false`)
- Checksum mismatch -> error (`ok=false`)

## 7. Notes

- Do not include `payload_binary` as Base64 inside JSON for normal operation.
- Base64 may be used only for debugging or temporary text-only transport.
- For high-frame-rate live video, define a separate stream message using H.264/H.265, RTSP, or WebRTC.
- MSG 4101 is intended for frame-based image transfer, not continuous video streaming.
