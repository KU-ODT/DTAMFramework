# UAO Mission Dispatch System

UAM 기체에 대한 미션 디스패치·비행 스크립트 컴파일·원격 실행·텔레메트리 모니터링을 수행하는 통합 시스템입니다.

## 요구사항

- Python 3.12+
- 기체 PC(SITL 서버)에 대한 SSH 접근 가능

## 설치 및 실행

```bash
# 1. 가상환경 생성 및 활성화
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 서버 실행
python -m src.main
```

서버가 시작되면 `http://localhost:8000` 에서 대시보드에 접속할 수 있습니다.

## 설정

- `config/server_config.yaml` — 서버 포트, 스케줄러 설정
- `config/aircraft_registry.yaml` — 기체별 접속 정보 (IP, SSH, 포트 등)

## 디렉토리 구조

```
├── config/          설정 파일 (YAML)
├── src/
│   ├── main.py      서버 진입점
│   ├── pipeline.py  미션 파이프라인 오케스트레이터
│   ├── compiler/    미션 JSON → Python 비행 스크립트 컴파일러
│   ├── dispatcher/  미션 큐 관리 및 스케줄링
│   ├── receiver/    FastAPI 서버 + 대시보드 UI
│   ├── status/      텔레메트리 수신·캐시·정규화
│   ├── uploader/    SCP 전송 + SSH 원격 실행
│   └── validator/   미션 JSON 스키마/의미 검증
├── output/          컴파일된 스크립트 출력 (자동 생성)
├── inbox/           파일 드롭 자동 제출 폴더 (선택)
├── requirements.txt Python 의존성
└── pyproject.toml   IDE 타입체커 설정
```
