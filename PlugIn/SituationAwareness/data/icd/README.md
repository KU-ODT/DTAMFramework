# Situation Awareness ICD subset

Situation Awareness 플러그인은 DTAM 서버의 `/ws/dtam` 단일 WebSocket 채널을
통해 아래 ICD를 구독합니다.

- `4001_vehicleStatus`: 기체 상태/위치/속도
- `4101_cameraImageFrame`: 카메라 프레임 메타데이터 및 `image_b64`

원본 ICD 정의는 `DTAMSDK/dtam_client/icd`를 기준으로 하며, 이 폴더에는
플러그인 배포/참조 편의를 위한 사본만 둡니다.

