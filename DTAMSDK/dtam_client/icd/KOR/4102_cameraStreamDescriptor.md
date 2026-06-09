# ICD - 카메라 스트림 디스크립터 (MSG 4102)

| 항목 | 값 |
|---|---|
| Message ID | 4102 |
| Message Name | Camera Stream Descriptor |
| 전송 방식 | WebSocket (`/ws/dtam`) |
| 인코딩 | JSON only |
| 방향 | `visual -> server -> monitoring/situation_awareness` |
| 주기 | 이벤트 기반 / 요청 시 |

MSG 4102는 이미지 바이트를 싣지 않고 실시간 미디어 스트림의 위치와 형식을 알려주는 메타데이터 메시지입니다. 고주기 영상 프레임은 IntegrationHub를 통과시키지 않고 VisualizationModule의 직접 media-plane URL로 받습니다. 기존 MSG 4101은 저주기 이미지 스냅샷 또는 ICD 경유 이미지가 필요한 소비자를 위해 유지합니다.

## Payload 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `message_id` | int | 예 | 고정값 `4102`. |
| `message_name` | string | 아니오 | `Camera Stream Descriptor`. |
| `timestamp` | string | 예 | UTC ISO-8601 생성 시각. |
| `stream_id` | string | 예 | 스트림 식별자. 예: `UAM0001-front_center-mjpeg`. |
| `vehicle_id` | string | 예 | DTAM 비행체 ID. 예: `UAM0001`. |
| `airsim_vehicle_name` | string | 아니오 | DTAM ID와 다른 AirSim vehicle name. |
| `camera_name` | string | 예 | `front_center` 등 카메라 이름. |
| `camera_id` | string | 아니오 | VPO/고정 CCTV 카메라 ID. 예: `VPO-001-01`. |
| `vertiport_id` | string | 아니오 | VPO 버티포트 선택 ID. |
| `vertiport_name` | string | 아니오 | 버티포트 표시명. |
| `stream_type` | string | 예 | 현재 `mjpeg`; 추후 `webrtc`, `rtsp` 등 확장 가능. |
| `transport` | string | 예 | 현재 테스트 경로는 `http`. |
| `codec` | string | 예 | `mjpeg`. |
| `encoding` | string | 예 | `jpeg`. |
| `url` | string | 예 | 직접 미디어 엔드포인트. IntegrationHub가 아니라 VisualizationModule URL일 수 있습니다. |
| `control_mid` | string | 아니오 | 카메라 제어 ICD. 현재 `5002`. |
| `fps` | float | 아니오 | 권장 FPS. 기본 저부하 값은 `2.0`. |
| `quality` | int | 아니오 | JPEG 품질 힌트. 기본 `70`. |
| `width` | int | 아니오 | 선택적 폭. 모르면 `0`. |
| `height` | int | 아니오 | 선택적 높이. 모르면 `0`. |
| `status` | string | 예 | `available`, `disabled`, `error`. |
| `source` | string | 아니오 | `airsim`, `unreal_scene_capture` 등 실제 미디어 소스. |
| `media_plane` | string | 아니오 | `direct-mjpeg`, `direct-vpo-mjpeg` 등 고주기 바이트 경로. |
| `cache_policy` | string | 아니오 | 예: `latest-frame-only`. |
| `expires_at` | string/null | 아니오 | 선택적 만료 시각. |
| `note` | string/null | 아니오 | 사람이 읽는 설명. |

## 처리 방식

- VisualizationModule은 요청 또는 공지 시 MSG 4102를 발행합니다.
- StateServer는 SDK 정책에 따라 4102를 forwarding하고 최신 descriptor를 REST 조회용으로 보관할 수 있습니다.
- 소비자는 `url`을 직접 열어 실시간 미디어를 수신합니다. 고주기 프레임을 `/ws/dtam`으로 프록시하지 않습니다.
- 카메라 위치/시점 제어는 DTAM 서버를 경유하는 MSG 5002를 사용합니다.
- VPO 버티포트 CCTV는 `camera_id`/`vertiport_id`를 포함할 수 있으며, 고정 SceneCapture 기반이면 `control_mid`가 비어 있을 수 있습니다.
