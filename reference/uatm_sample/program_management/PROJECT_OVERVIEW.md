# UATM Sample 프로젝트 정리

작성일: 2026-03-02
대상 경로: `c:\Users\AISIMULATOR2\Desktop\Code\uatm_sample`

## 1) 프로젝트 한 줄 요약
- `TrafficS`(KADA AAM Traffic Sim) 기반의 UAM/UATM 트래픽 시뮬레이션 프로젝트입니다.
- Python 서버(시뮬레이션/API/타일) + 웹 프론트엔드(MapLibre) + CSV 기반 공역/비행계획 데이터 구조입니다.

## 2) 현재 저장소 구성(스캔 결과)
- 최상위 주요 폴더
  - `app/`: Python 서버 + 웹 정적 리소스
  - `data/`: 기본 공역 데이터 + 고밀도 비행계획 CSV
  - `resources/`: 아이콘/이미지/패치노트/맵 리소스
  - `scripts/`: 실행/빌드/패키징 스크립트
  - `docs/`: 최근 개선 작업 문서
  - `log/`: 시뮬레이션 로그 누적 데이터
- 최상위 파일
  - `app.py`: 서비스 실행 진입점
  - `requirements.txt`: Python 의존성 고정 버전

### 파일 분포(현재 워크스페이스)
- 폴더별 파일 수(대략)
  - `log`: 2302 (대부분 실행 로그)
  - `app`: 70
  - `resources`: 46
  - `data`: 20
  - `docs`: 8
  - `scripts`: 7
- 확장자 분포(상위)
  - `.csv`: 2322
  - `.py`: 22
  - `.js`: 14
  - `.md`: 8
  - `.txt`: 7

## 3) 런타임 구조

### 실행 진입점
- `python app.py [service]`
- `service` 선택: `api | tiles | frontend | all` (기본 `all`)

### 서비스 역할
- API 서버: `app/fastapi_server.py`
  - `/api/state`, `/api/history`, `/api/logs.zip`
  - 시뮬레이션 제어 `/api/sim/*`
  - 데이터파일 편집 `/api/datafiles/*`
- 타일/DEM 서버: `app/tile_fastapi_server.py`
  - `/tiles/metadata`, `/tiles/{z}/{x}/{y}.{ext}`, `/dem/{z}/{x}/{y}.png`
- 프론트 프록시 서버: `app/frontend_server.py`
  - `/api/*`를 API 서버로 프록시
  - `/tiles/*`, `/dem/*`를 타일 서버로 프록시
  - 정적 파일(`app/web`) 서빙

### 기본 포트/호스트
- API: `8002`
- Tiles: `8001`
- Frontend: `5173`
- 호스트 기본 정책은 `UATM_ENV` 기반
  - `local/dev`: `127.0.0.1`
  - `prod`: `0.0.0.0`

## 4) 핵심 코드 모듈

### 시뮬레이션/도메인
- `app/sim_core.py`
  - 시뮬레이션 규칙, 비행체 상태, 위험도/분리/배터리/풍향 영향 계산 핵심
  - 랜덤 스케줄/플라이트플랜 스케줄 둘 다 지원
- `app/pathplanner.py`
  - 버티포트/웨이포인트 CSV 로딩
  - 그래프 기반 경로 탐색 및 경로 캐시
- `app/wind_model.py`
  - Perlin 기반 풍장 모델

### 스케줄링
- `app/schedule_random_mode.py`: 트래픽 레벨 기반 랜덤 운항 생성
- `app/schedule_flightplan_mode.py`: 외부 CSV(폴더) 기반 스케줄 파싱/정규화

### 데이터파일 편집 서비스
- `app/datafile_service.py`
  - vertiport/corridor/basestation CSV clone/append/update/delete/apply 처리
  - UTF-8/CP949 혼용 대응 로직 포함

### 지도 데이터
- `app/mbtiles.py`: MBTiles(SQLite) 로딩/캐시
- `app/dem.py`: DEM 타일(terrarium 인코딩 PNG) 생성

### 레거시/병행 코드
- `app/web_server.py`: 기존 HTTPServer 기반 구현(상대적으로 대형 파일)
- `app/gui.py`, `app/web_gui.py`: PyQt 계열 GUI 진입점
- 현재는 FastAPI 계층(`fastapi_server.py`, `tile_fastapi_server.py`, `frontend_server.py`)이 주 실행 축

## 5) 웹 프론트엔드 구조 (`app/web/`)
- `index.html`
  - 시작 화면/튜토리얼/대시보드 UI 뼈대
  - 시작 화면 버전 표기: `v0.9.5`
- `app.js`
  - 메인 앱 상태/초기화/국영문(i18n)/지도 설정/제어 로직 중심
  - 시작 화면 패치노트 로더: `resources/patch_notes_0.9.5_*`
- 기능 분리 파일
  - `app.traffic.js`: 비행체 아이콘/레이어/표시 제어
  - `app.routes.js`: 회랑 타이머/라벨 레이어
  - `app.density.js`: 밀도 시각화
  - `app.congestion.js`: 혼잡 지표/구간 시각화
  - `app.field_layers.js`: 영향장/밀도장/혼잡장(워커 사용)
  - `app.weather.js`: 기상/풍속 시각화
  - `app.noise.js`: 소음 히트맵(팝아웃 지원)
  - `app.transmission.js`: 통신 전파 맵(팝아웃 지원)
  - `*.worker.js`: 연산 분리(브라우저 워커)

## 6) 데이터/리소스

### 데이터 (`data/`)
- 기본 파일
  - `default/vertiport_default.csv`
  - `default/corridor_default.csv`
  - `default/basestation_default.csv`
- 비행계획 샘플
  - `flightplan/highdensity/*.csv` (서울 지역 지명 다수: 강남, 여의도, 잠실, 천호 등)

### 리소스 (`resources/`)
- 시뮬레이션 아이콘/맵/이미지
- 패치노트 텍스트
  - `patch_notes_0.9.2_en.txt`
  - `patch_notes_0.9.3_ko.txt`
  - `patch_notes_0.9.4_en.txt`, `patch_notes_0.9.4_ko.txt`
  - `patch_notes_0.9.5_en.txt`, `patch_notes_0.9.5_ko.txt`

## 7) 문서 (`docs/`) 핵심 주제
- `server_stability_checklist.md`: 서버 안정화 체크리스트 및 완료 로그
- `server_host_strategy.md`: 호스트 바인딩 정책(local/dev/prod)
- `state_transport_optimization.md`: `/api/state` 증분(delta) 전송 및 폴링 최적화
- `logging_io_decoupling.md`: 로그 쓰기 큐/워커 분리
- `api_service_layer_cleanup.md`: 데이터파일 서비스 레이어 분리
- `simulation_modes.md`: Random/Flightplan 모드 분리 설명
- `flightplan_load_checklist.md`: Flightplan 업로드 UI 임시 비활성 결정
- `map_tilt_loading_optimization.md`: 2D→3D 전환 로딩 최적화

## 8) 버전/의존성 관리 포인트

### 확인된 버전 표기
- UI 시작 화면: `v0.9.5` (`app/web/index.html`)
- 시작 패치노트 기준: `0.9.5` (`app/web/app.js`, `resources/patch_notes_0.9.5_*`)
- 인스톨러 스크립트 버전: `0.82` (`scripts/UATM.iss`)

### Python 의존성 (`requirements.txt`)
- fastapi==0.124.4
- uvicorn==0.33.0
- httpx==0.28.1
- numpy==1.24.4
- rasterio==1.3.11
- pydantic==2.10.6
- starlette==0.44.0
- eval_type_backport

## 9) 빌드/배포 스크립트
- `scripts/run_all.py`: api/tiles/frontend 동시 실행, 하나 종료 시 전체 종료
- `scripts/build_web.py`: 웹 배포 번들(`dist_web`) 생성
- `scripts/build_exe.py`: PyInstaller EXE + 옵션으로 Inno Setup 인스톨러
- `scripts/UATM.spec`: PyInstaller 스펙
- `scripts/UATM.iss`: Inno Setup 설정

## 10) 운영 관점 메모
- `log/` 폴더에 실행 로그가 많이 쌓여 있음(세션 폴더 다수).
- 버전 문자열이 `0.9.5`(UI)와 `0.82`(인스톨러)로 이원화되어 있어 릴리스 관리 시 정합성 점검 필요.
- 데이터파일 처리 로직은 UTF-8/CP949를 모두 고려하므로, CSV 인코딩 혼재 환경에서도 동작하도록 설계됨.

---
원본 스캔 기준으로 작성했으며, 이후 구조 변경 시 이 문서를 함께 갱신하면 프로그램 관리 문서로 재사용하기 좋습니다.
