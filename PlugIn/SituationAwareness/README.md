# Situation Awareness Plug-In

Reference `CoreSituationAwareness` + `GUISituationAwareness` 기능을 DTAM
플러그인 구조로 이관한 모듈입니다.

## 실행

```powershell
python SA_main.py --host 127.0.0.1 --port 18210 --no-browser
```

기본 입력 모드는 `icd`입니다. 이 경우 StateServerModule `/ws/dtam`에
`situation_awareness` role로 등록하고 다음 ICD를 소비합니다.

- `4001_vehicleStatus`: 비행체 위치/속도 상태
- `4101_cameraImageFrame`: 카메라 프레임 메타데이터 + `image_b64`

레거시 AirSim 직접 연결을 시험하려면 다음처럼 실행합니다.

```powershell
python SA_main.py --input-mode airsim
```

## 구조

- `SA_main.py`: 실행 진입점
- `app/server.py`: FastAPI GUI/API 서버
- `app/services/dtam_bridge.py`: DTAM SDK 기반 4001/4101 ICD 수신 브리지
- `app/core`: Ref의 CoreSituationAwareness 처리 로직
- `app/web`: Ref의 GUISituationAwareness 웹 GUI
- `data/icd`: 이 플러그인이 소비하는 ICD 문서 사본

