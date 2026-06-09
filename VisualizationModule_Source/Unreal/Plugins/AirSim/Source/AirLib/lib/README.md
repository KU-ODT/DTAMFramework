# AirSim 플러그인 빌드 산출물 (Git 제외)

이 폴더에는 Unreal AirSim 플러그인의 C++ 빌드 산출물 — 정적 라이브러리
`AirLib.lib` (x64/Release ~150 MB, x64/Debug ~127 MB) 등이 들어간다.
GitHub 단일 파일 100 MB 한도를 초과하므로 git 미포함.

## 어떻게 얻나

UE 프로젝트에서 AirSim 플러그인을 한 번 빌드하면 자동으로 생성된다:

```
Open VisualizationModule_Source/Unreal/Environments/DTAMVisualization/
  DTAMVisualization.uproject in UE Editor
Build → Configurations → Development Editor
Build & Run
```

또는 `cd VisualizationModule_Source/Unreal/Plugins/AirSim/Source/AirLib/`
에서 `./build.bat` (Cosys-AirSim 빌드 스크립트).

> `.gitignore` 가 `VisualizationModule_Source/Unreal/Plugins/**/AirLib/lib/`
> 를 무시.
