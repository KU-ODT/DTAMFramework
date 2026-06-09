# PSU Monitoring SW

DTAM 확장모듈용 PSU(Provider of Services for UAM) 모니터링 콘솔입니다.

## 1회차 범위

- `PSU_main.py` 독립 실행 진입점
- FastAPI 기반 `app/server.py`
- 정적 웹 셸 `app/web/index.html`
- 최소 상태 API

## 2회차 범위

- MissionModule의 MapLibre vendor 파일 이식
- `D:\DTAMFramework\MissionModule\resources\korea.mbtiles` 읽기 참조
- PSU 자체 `/tiles/{z}/{x}/{y}.pbf` 벡터 타일 엔드포인트
- `/api/map/config` 지도 설정 API
- Traffic Map 패널에 MapLibre 기반 지도 표시

## 3회차 범위

- PSU 시연용 서울권 더미 시나리오 데이터셋 작성
- FlightPlan, TrackState, VertiportState, Corridor, ConflictEvent, CapacityMetric, EventLog 데이터 제공
- Overview KPI, Priority Event List, Vertiport Status Summary를 시나리오 API에 연결
- 지도에 PSU 회랑, 계획 경로, 웨이포인트, 버티포트, 현재 UAM 트랙 레이어 표시

## 4회차 범위

- Overview KPI 8종 표시 완성
- 시나리오/시뮬레이션 시각/최우선 이벤트 요약 스트립 추가
- Priority Event 클릭 시 관련 화면 패널로 이동
- Vertiport Status Summary에 FATO/Gate 점유율 바, Queue, Delay 표시
- Traffic Trend 미니 차트 추가
- Operational Snapshot과 Mini Map Summary 추가

## 5회차 범위

- Traffic Map / Conflict 화면에 Flight Filter, Flight List, Conflict Timeline, Conflict Detail Panel, Suggested Actions 연결
- FlightPlan + TrackState + ConflictEvent 조인 API `GET /api/traffic/conflict-view` 추가
- `/api/map/layers`에 실제 궤적 `actual_tracks`와 충돌 지점 `conflicts` GeoJSON 레이어 추가
- 지도에서 충돌 지점/항공기 클릭 시 상세 패널과 선택 강조 연동
- Warning/Caution/Active 필터에 따른 운항 목록, 충돌 타임라인, 지도 충돌 레이어 필터링

## 6회차 범위

- Flow & Capacity 화면에 Analysis Condition, Demand-Capacity Balance Chart, Corridor Density Heatmap 연결
- Vertiport Throughput Panel, Delay Propagation Timeline, Bottleneck Diagnosis Panel 구현
- CapacityMetric + Corridor + Vertiport + EventLog 기반 통합 분석 API `GET /api/capacity/flow-view` 추가
- 회랑/버티포트 선택 시 Selected Capacity Detail 상세 분석 표시
- Priority Event에서 Flow & Capacity 이동 시 관련 수용량 대상 선택 연동

## 7회차 범위

- Decision Support 화면에 Suggested Action 후보 목록, 선택 후보 상세, 전후 효과 비교 패널 추가
- 출발 지연, 속도 조정, 대체 경로, 고도 분리, 도착 순서 재조정, 대체 버티포트 후보를 구조화된 action 모델로 생성
- 조치 전후의 충돌 건수, 수용량 Warning, 평균/최대 지연, 수용량 초과 시간을 정적 demo 규칙 기반으로 비교
- Flow & Capacity 병목 완화안과 Traffic Conflict 조치 후보를 Decision Support 데이터 모델로 통합
- OperationModule 직접 실행은 하지 않고 dry-run preview 명령 패키지와 시나리오 결과 리포트 preview를 제공

## 8회차 범위

- Replay / Report 탭과 최종 시연용 리플레이 타임라인 UI 추가
- Play, Pause, Prev, Next, Reset, Speed 컨트롤 및 진행률 표시 구현
- 리플레이 프레임 선택 시 Traffic, Flow, Decision Support 화면의 관련 대상 선택과 연동
- 시나리오 결과 리포트를 JSON, Markdown, HTML 출력 API와 UI 링크로 제공
- Final Validation 보드에 핵심 화면, 분석 출력, 최종 산출물 검증 상태 표시
- OperationModule dispatch는 안전상 차단하고 dry-run preview-only 범위를 명시

## 실행

```powershell
python D:\DTAMFramework\ExtenstionModule\PSU\PSU_main.py --no-browser
```

기본 주소:

```text
http://127.0.0.1:8120
```

## 주요 API

- `GET /api/health`
- `GET /api/config`
- `GET /api/status`
- `GET /api/navigation`
- `GET /api/map/config`
- `GET /api/map/layers`
- `GET /api/scenarios`
- `GET /api/scenario`
- `GET /api/scenario/metadata`
- `GET /api/overview`
- `GET /api/overview/dashboard`
- `GET /api/flight-plans`
- `GET /api/flight-plans/{flight_plan_id}`
- `GET /api/tracks/current`
- `GET /api/tracks/{aircraft_id}`
- `GET /api/vertiports`
- `GET /api/vertiports/state`
- `GET /api/vertiports/{vertiport_id}`
- `GET /api/corridors`
- `GET /api/conflicts`
- `GET /api/conflicts/{conflict_id}`
- `GET /api/traffic/conflict-view`
- `GET /api/traffic-map/summary`
- `GET /api/capacity/summary`
- `GET /api/capacity/flow-view`
- `GET /api/flow-capacity/summary`
- `GET /api/capacity/bottlenecks`
- `GET /api/capacity/delay-propagation`
- `POST /api/capacity/run`
- `GET /api/capacity/vertiports`
- `GET /api/capacity/corridors`
- `GET /api/capacity/corridors/{corridor_id}`
- `GET /api/capacity/vertiports/{vertiport_id}`
- `GET /api/decision-support`
- `GET /api/decision-support/summary`
- `GET /api/decision-support/actions`
- `GET /api/decision-support/actions/{recommendation_id}`
- `POST /api/decision-support/actions/{recommendation_id}/evaluate`
- `GET /api/decision-support/comparison`
- `POST /api/operation-module/replan/preview`
- `POST /api/operation-module/replan/dispatch`
- `GET /api/replay`
- `GET /api/replay/timeline`
- `GET /api/replay/frame/{step}`
- `GET /api/reports/scenario-result`
- `GET /api/reports/scenario-result.md`
- `GET /api/reports/scenario-result.html`
- `GET /api/final-validation`
- `GET /api/events`
- `GET /api/events/priority`
- `GET /tiles/{z}/{x}/{y}.pbf`

## 최종 상태 및 제한사항

- 현재 구현은 8회차 최종 통합 산출물입니다.
- 시나리오는 연구/시연용 static demo 데이터 기반입니다.
- OperationModule 실제 실행이나 자동 운항 재계획은 수행하지 않습니다.
- `/api/operation-module/replan/dispatch`는 의도적으로 dry-run 차단 응답만 반환합니다.
- 체크리스트의 WebSocket 실시간 스트리밍, 실제 DB 저장, 실제 운항 승인 연동은 후속 연구 범위입니다.
