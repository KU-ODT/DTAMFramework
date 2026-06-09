# Unreal Engine 런타임 바이너리 (Git 제외)

이 폴더에는 **Unreal Engine 으로 빌드된 시각화 실행 바이너리** 가 들어가야 한다.
실제 용량이 약 **21 GB** 이라 Git 에 올리지 않는다.

## 들어가야 할 내용

```
Unreal/
├── DTAMVisualization.exe                   # 메인 실행 파일
├── DTAMVisualization/
│   ├── Binaries/Win64/                     # UE 엔진 + DTAMVisualization 바이너리
│   │   ├── D3D12/, DML/                    # Direct3D / DirectML 런타임
│   │   ├── boost_*.dll, tbb.dll, ...       # C++ 의존성
│   │   └── DTAMVisualization.exe
│   ├── Content/Paks/                       # 패키징된 콘텐츠 (.pak, .ucas, .utoc)
│   │   ├── DTAMVisualization-Windows.pak
│   │   ├── DTAMVisualization-Windows.ucas
│   │   └── DTAMVisualization-Windows.utoc
│   └── Saved/Config/                       # 사용자 환경설정 (자동 생성)
└── Engine/                                  # UE 엔진 런타임 (ThirdParty 포함)
    └── Binaries/ThirdParty/                # NVIDIA Aftermath, Vulkan, XAudio2 ...
```

## 어떻게 얻나

1. `VisualizationModule_Source/Unreal/Environments/DTAMVisualization/` 에서 UE 5.x 로
   빌드 (Development Editor 또는 Shipping).
2. UE → Platforms → Windows → Package Project 로 실행 패키지 생성.
3. 출력물을 이 폴더로 복사.

또는 팀 내부 배포 서버 / S3 / Google Drive 등에서 미리 빌드된 zip 을 받아
이 폴더에 압축 해제.

## 패키지 검증

```python
from DTAMVisualization import runtime_paths
runtime_paths.verify_unreal_binary()   # 필수 파일 존재 확인
```

> 이 README 와 다른 파일이 같이 있어도 무방 — git 은 `.gitignore` 의
> `VisualizationModule/runtime/Unreal/**` 패턴으로 무시한다.
