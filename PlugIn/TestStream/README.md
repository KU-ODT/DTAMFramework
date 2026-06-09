# DTAM TestStream Plug-in

VisualizationModule이 공지하는 direct MJPEG media-plane stream을 테스트하는 경량 플러그인입니다.

- 영상 데이터: VisualizationModule `/api/media/stream` MJPEG URL 직접 수신
- 스트림 발견/감사: MSG 4102 Camera Stream Descriptor
- 카메라 제어: StateServer `/api/msg/5002`를 통한 ICD 5002
- 영상 프레임: VisualizationModule이 AirSim/Cosys-AirSim `simGetCameraFrame` JPEG를 background producer로 받아 최신 프레임 1장만 캐시한 뒤 MJPEG로 전송
- 기본값: 640x360 캡처 설정, 20 FPS 요청, JPEG quality 60, 브라우저 표시 단계에서 fit/upscale
- 진단: UI의 `스트림 통계` 버튼 또는 VisualizationModule `/api/media/stats`로 producer/cache actual FPS 확인

이 모듈은 VPO와 연결하지 않고 실시간 영상 구조를 검증하기 위한 테스트용입니다.
