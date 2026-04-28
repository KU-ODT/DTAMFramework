# ICD — Camera Image Frame (MSG 4101)

| 항목 | 값 |
|---|---|
| Message ID | `4101` |
| Message Name | Camera Image Frame |
| 전송 방식 | WebSocket (`/ws/dtam`) |
| 인코딩 | JSON 헤더 (UTF-8) + 바이너리 페이로드 |
| 주기 | 송신측 재량 |

## 1. 목적

MSG 4101은 비행체 또는 시뮬레이터에서 수신 서버로 카메라 이미지 프레임을 전송한다.

이 메시지는 MSG 4001 Vehicle Status와 의도적으로 분리되어 있다. 이미지 데이터는 크기가 크므로 MSG 4001은 소형 상태 메시지로 유지하고, MSG 4101은 이미지 메타데이터와 바이너리 페이로드를 전달한다.

## 2. 프레이밍

```text
[header_length][header_json][payload_binary]
```

| 부분 | 타입 | 크기 | 설명 |
|---|---|---:|---|
| `header_length` | uint32 | 4 bytes | `header_json` 바이트 길이, unsigned little-endian |
| `header_json` | UTF-8 JSON | 가변 | 이미지 프레임 메타데이터 |
| `payload_binary` | byte[] | 가변 | 인코딩된 이미지 바이트 |

## 3. 헤더 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `message_id` | int | ✔ | 고정값 `4101` |
| `message_name` | str | ✔ | 고정값 `Camera Image Frame` |
| `timestamp` | str | ✔ | 촬영 시각 (UTC, ISO-8601) |
| `vehicle_id` | str | ✔ | 비행체 ID (`^[A-Z]{2,8}\d{4}$`) |
| `camera_name` | str | ✔ | 카메라 이름 |
| `image_type` | str | ✔ | 이미지 유형 |
| `sequence` | int | ✔ | 프레임 순번 (비행체-카메라별 단조 증가) |
| `width` | int | ✔ | 이미지 너비 (px) |
| `height` | int | ✔ | 이미지 높이 (px) |
| `channels` | int | ✔ | 채널 수 |
| `pixel_format` | str | ✔ | 픽셀 형식 |
| `encoding` | str | ✔ | 페이로드 인코딩 |
| `payload_size` | int | ✔ | `payload_binary` 바이트 수 |
| `checksum` | str | ✖ | 페이로드 체크섬 (권장) |
| `unit` | str | ✖ | 깊이/스칼라 이미지 물리 단위 |
| `frame_id` | str | ✖ | 좌표계/카메라 프레임 식별자 |

### 3.1 camera_name 권장 값

| 값 | 설명 |
|---|---|
| `front_center` | 전방 카메라 |
| `front_left` | 전방 좌측 |
| `front_right` | 전방 우측 |
| `bottom_center` | 하방 카메라 |
| `back_center` | 후방 카메라 |

### 3.2 image_type 열거형

| 값 | 설명 |
|---|---|
| `scene` | RGB 시각 이미지 |
| `depth_planar` | 평면 깊이 이미지 |
| `depth_perspective` | 원근 깊이 이미지 |
| `depth_vis` | 깊이 시각화 이미지 |
| `segmentation` | 세그멘테이션 이미지 |
| `surface_normals` | 표면 법선 이미지 |
| `infrared` | 적외선 이미지 |
| `optical_flow` | 옵티컬 플로 데이터 |
| `optical_flow_vis` | 옵티컬 플로 시각화 |

### 3.3 pixel_format 열거형

| 값 | 설명 |
|---|---|
| `rgb8` | 8비트 RGB, 3채널 |
| `rgba8` | 8비트 RGBA, 4채널 |
| `gray8` | 8비트 그레이스케일, 1채널 |
| `gray16` | 16비트 그레이스케일, 1채널 |
| `float32` | 32비트 float, 1채널 이상 |
| `vector2_float32` | 2채널 float 벡터 |

### 3.4 encoding 열거형

| 값 | 페이로드 | 권장 용도 |
|---|---|---|
| `jpeg` | JPEG 바이트 | RGB 장면 이미지 |
| `png` | PNG 바이트 | 무손실 RGB, 세그멘테이션, 마스크 |
| `raw` | 원시 픽셀 바이트 | 내부 사용 또는 저해상도 |
| `depth_png` | PNG 바이트 | 깊이 이미지 (정수 인코딩) |

## 4. 예시

### 4.1 RGB 장면 프레임 헤더

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

### 4.2 깊이 프레임 헤더

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

## 5. 수신자 동작

1. 4바이트를 `header_length`로 읽는다.
2. `header_length`를 unsigned little-endian uint32로 디코딩한다.
3. `header_length` 바이트를 UTF-8 JSON으로 읽는다.
4. 헤더를 파싱/검증한다.
5. `payload_size` 바이트를 `payload_binary`로 읽는다.
6. `checksum`이 있으면 검증한다.
7. `encoding`에 따라 `payload_binary`를 디코딩 또는 중계한다.

## 6. 유효성 정책

- 필수 필드 누락 → 오류 (`ok=false`)
- 타입 불일치 → 오류
- 비행체 ID 패턴 불일치 → 오류
- 미지원 `image_type` / `pixel_format` / `encoding` → 오류
- `width <= 0` 또는 `height <= 0` → 오류
- `payload_size` 불일치 → 오류
- 체크섬 불일치 → 오류

## 7. 참고

- 일반 운용 시 `payload_binary`를 JSON 내 Base64로 포함하지 않는다.
- Base64는 디버깅 또는 임시 텍스트 전송에만 사용한다.
- 고프레임레이트 라이브 영상은 H.264/H.265, RTSP, WebRTC 등 별도 스트림 메시지를 정의한다.
- MSG 4101은 프레임 기반 이미지 전송용이며, 연속 비디오 스트리밍 용도가 아니다.
