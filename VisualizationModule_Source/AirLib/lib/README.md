# AirLib 빌드 산출물 (Git 제외)

이 폴더에는 **AirLib (Cosys-AirSim) 의 C++ 빌드 산출물** 이 들어간다.
약 **306 MB** (정적 라이브러리 + dependency lib + obj 파일).

## 들어가야 할 내용

```
AirLib/lib/
├── airlib.a / airlib.lib                   # AirLib 정적 라이브러리
├── x64/Release/, x64/Debug/                # 구성별 빌드
└── (자동 생성 obj/pdb)
```

## 어떻게 얻나

```bash
cd VisualizationModule_Source/AirLib/
./build.bat                                  # Windows
./build.sh                                   # Linux
```

build.bat / build.sh 는 Cosys-AirSim 공식 빌드 스크립트를 따른다:
https://github.com/Cosys-Lab/Cosys-AirSim

## AirLib/temp/ 는?

`temp/` (237 MB) 는 빌드 임시 산출물 (vcpkg cache, intermediate obj 등) —
빌드 도중 자동 생성된다. 마찬가지로 git 제외.

> `.gitignore` 가 `VisualizationModule_Source/AirLib/{lib,temp}/**` 를 무시.
