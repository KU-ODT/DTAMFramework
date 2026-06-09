# Unreal Engine 프로젝트 소스 (Git 제외)

이 폴더에는 **DTAMVisualization 의 UE 5.x 프로젝트 파일** 이 들어간다.
약 **17 GB** (Content/, Saved/, Intermediate/ 포함).

## 들어가야 할 내용

```
Environments/DTAMVisualization/
├── DTAMVisualization.uproject
├── Config/
│   ├── DefaultEngine.ini
│   ├── DefaultGame.ini
│   └── ...
├── Content/                                # ★ 가장 큼
│   ├── Maps/                               # 벤티포트, 도시 맵
│   ├── Vehicles/                           # UAM 메시 + 머티리얼
│   ├── Cesium/                             # CesiumForUnreal 자산
│   ├── BluePrints/
│   └── ...
├── Source/
│   ├── DTAMVisualization/                  # C++ Game module
│   └── DTAMVisualization.Target.cs
├── Plugins/                                # 프로젝트 전용 플러그인 (선택)
│   └── AirSim/ (또는 코심볼릭 링크)
└── (자동 생성) Binaries/, Intermediate/, Saved/   # 빌드 시 자동 생성
```

## 어떻게 얻나

1. 팀 내부 저장소 / S3 / Drive 에서 패키지된 zip 받기.
2. 또는 Git LFS / Perforce 등 별도 VCS 에서 가져오기 (UE 프로젝트는
   일반 Git 으로 다루기 부적합).
3. CesiumForUnreal, AirSim 플러그인은
   `VisualizationModule_Source/Unreal/Plugins/` 와 연결.

## 빌드

```
Open DTAMVisualization.uproject in UE 5.x Editor
File → Generate Visual Studio project files
Build & Run from Visual Studio (DTAMVisualization.sln)
```

빌드 산출물은 `VisualizationModule/runtime/Unreal/` 로 패키징해서 배포.

> `.gitignore` 가 `VisualizationModule_Source/Unreal/Environments/**` 를 무시.
