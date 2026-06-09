# Pixel Streaming 웹 서버 (Git 제외)

이 폴더에는 **UE Pixel Streaming SignallingWebServer / Matchmaker / TURN** 등
WebRTC 기반 스트리밍 서버 바이너리·설정이 들어간다. 약 **735 MB**.

## 들어가야 할 내용

```
PixelStreamingWebServers/
├── SignallingWebServer/
│   ├── platform_scripts/
│   ├── Public/
│   ├── node_modules/                       # 대용량의 주범
│   ├── package.json, server.js
│   └── ...
├── Matchmaker/
├── SFU/
└── (선택) TURN/
```

## 어떻게 얻나

UE 설치 시 함께 제공되는 `Engine/Plugins/Media/PixelStreaming/Resources/
WebServers/` 를 복사하거나, 공식 저장소
https://github.com/EpicGames/PixelStreamingInfrastructure 에서 클론.

```bash
cd VisualizationModule/runtime/PixelStreamingWebServers/SignallingWebServer/
npm install                                  # node_modules 받기
./platform_scripts/cmd/setup.bat             # 인증서 등 세팅
./platform_scripts/cmd/Start_SignallingServer.bat
```

> `.gitignore` 가 `VisualizationModule/runtime/PixelStreamingWebServers/**`
> 를 무시한다.
