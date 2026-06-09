# ICD - Camera Stream Descriptor (MSG 4102)

| Item | Value |
|---|---|
| Message ID | 4102 |
| Message Name | Camera Stream Descriptor |
| Transport | WebSocket (`/ws/dtam`) |
| Encoding | JSON only |
| Direction | `visual -> server -> monitoring/situation_awareness` |
| Rate | Event-based / on demand |

MSG 4102 announces a real-time media-plane stream without carrying image bytes. Use it to discover a direct VisualizationModule stream URL, while high-rate video frames bypass IntegrationHub to avoid server load. MSG 4101 remains available for low-rate image snapshots or AI consumers that need ICD-forwarded frames.

## Payload fields

| Field | Type | Required | Description |
|---|---|---:|---|
| `message_id` | int | yes | Fixed value `4102`. |
| `message_name` | string | no | `Camera Stream Descriptor`. |
| `timestamp` | string | yes | UTC ISO-8601 descriptor creation time. |
| `stream_id` | string | yes | Stable stream identifier, e.g. `UAM0001-front_center-mjpeg`. |
| `vehicle_id` | string | yes | DTAM aircraft ID, e.g. `UAM0001`. |
| `airsim_vehicle_name` | string | no | AirSim vehicle name when different from DTAM ID. |
| `camera_name` | string | yes | Camera name such as `front_center`. |
| `camera_id` | string | no | VPO/fixed CCTV camera ID, e.g. `VPO-001-01`. |
| `vertiport_id` | string | no | VPO-selected vertiport ID. |
| `vertiport_name` | string | no | Human-readable vertiport name. |
| `stream_type` | string | yes | `mjpeg` now; reserved for `webrtc`, `rtsp`, etc. |
| `transport` | string | yes | `http` for the current test path. |
| `codec` | string | yes | `mjpeg`. |
| `encoding` | string | yes | `jpeg`. |
| `url` | string | yes | Direct media endpoint. This may point to VisualizationModule, not IntegrationHub. |
| `control_mid` | string | no | Camera control ICD. Current value: `5002`. |
| `fps` | float | no | Recommended client FPS. Default low-load value: `2.0`. |
| `quality` | int | no | JPEG quality hint, default `70`. |
| `width` | int | no | Optional width, `0` if unknown. |
| `height` | int | no | Optional height, `0` if unknown. |
| `status` | string | yes | `available`, `disabled`, or `error`. |
| `source` | string | no | Actual media source such as `airsim` or `unreal_scene_capture`. |
| `media_plane` | string | no | High-rate byte path such as `direct-mjpeg` or `direct-vpo-mjpeg`. |
| `cache_policy` | string | no | Example: `latest-frame-only`. |
| `expires_at` | string/null | no | Optional UTC expiration time. |
| `note` | string/null | no | Human-readable note. |

## Processing

- VisualizationModule publishes MSG 4102 when an on-demand stream descriptor is requested or announced.
- StateServer forwards 4102 according to SDK policy and can keep the latest descriptors for REST lookup.
- Consumers open `url` directly for real-time media. Do not proxy high-rate frames through `/ws/dtam`.
- Camera movement/control should use MSG 5002 through the DTAM server.
- VPO vertiport CCTV descriptors can include `camera_id` and `vertiport_id`; fixed SceneCapture streams may leave `control_mid` empty.
