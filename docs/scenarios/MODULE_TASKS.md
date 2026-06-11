# 데모 시나리오 (S1/S2/S3) — 모듈별 구현 작업 목록

> **기준: 2026-06-11, branch `JW`.** 전달 인프라 (Ops Console → IntegrationHub → Mission 데모 플랜 팩 → Vehicle → 지도 표출) 는 **S1 기준 end-to-end 라이브 검증 완료** (이륙 + 50 m/s 순항 실측).
> 남은 것은 각 모듈의 도메인 동작. 자기 모듈 섹션 + 해당 시나리오 명세의 **§4 모듈별 동작표** 만 보면 구현 가능하도록 작성.

## 현재 동작 상태 (라이브 검증 결과)

| 시나리오 | 지금 되는 것 | 막혀 있는 것 (담당 작업) |
|---|---|---|
| S1 정상 운항 | ✅ **전 구간 검증** — 데모 선택→설정 저장→Play→1001→2001→3001(팩)→2002→이륙→순항 (4001 10Hz, 지도 표출) | 없음 |
| S2 PSU 속도 조정 | 3,360편 prebuilt 일괄 발행 ✓ (Mission 직로딩) / 반자동 PSU 개입 (UI dispatch) 시연 가능 | setSpeed 수행 (**V-1**) / Vehicle 의 1002 wind.weather 적용 (**V-2**) |
| S3 배터리 비상 | plan 로드·비행 ✓, scenarioId=S3 전달 ✓, PSU 4001 배터리 감시로 반자동 시연 가능 (운영자 dispatch) | 배터리 열화+4002 발행 (**V-3, V-4**) / land 수행 (**V-1**). 4002 정식 트리거는 PSU 4002 폴링 추가 (**P-4**) 후 |

**공통 전제**: `git pull origin JW`. ICD 스키마·라우팅·role base stub 은 SDK 에 전부 준비됨 — **base 메서드 override + 도메인 로직만** 구현하면 됨.

**참조 문서**: 시나리오 명세 `docs/scenarios/S{1,2,3}*.md` (§2 timeline / §4 모듈별 동작표 / §5 acceptance), ICD docs `DTAMSDK/dtam_client/icd/KOR/`.

---

## 🟢 Vehicle 모듈 (UAO 겸업) — 4건

**통신 구조 (확인됨)**: `IntegratedAirMobilityService(VehicleModule)` — SDK 100% 사용.
수신 stub 8개 전부 override 돼 있음 (`integrated_service.py` L3680~3701), 송신은 `self.send(parse_payload(...))` 단일 경로, 4001 은 `_Latest4001Publisher` (latest-only 비동기 10Hz).

| # | 작업 | 정확한 구현 위치 | 내용 |
|---|---|---|---|
| **V-1** | **3003 수신 → 액션 실제 수행** ★최우선 (발행 아님 — 3003 발행은 PSU/Mission 전용) | `integrated_service.py` — `on_tactical_separation` (L3695) → `_on_tactical_separation` (L3871). **override 는 이미 있음, 본문이 log-only** (수신 카운트만 올림) — 본문만 채우면 됨 | **setSpeed**: 대상 세션 targetSpeed 즉시 변경 (S2). **land**: 정상 plan 중단 → `action.vertiport` (또는 `targetLLA`) 로 강하·착륙 (S3). hold/directTo/rejoinPlan 은 데모 비필수. 시나리오별 세부 세팅 분기는 **2002 의 scenarioId** (V-3 에서 저장) 를 참조 — 3003 자체는 시나리오 정보를 싣지 않음 |
| **V-2** | **1002 wind.weather 수신 → 바람장 적용** (콘솔이 지정한 파라미터가 유일한 바람 소스) | `on_simulation_setup(msg)` — `msg.wind.weather` 읽기 | 콘솔이 날씨 선택 시 1002 의 `wind.weather` 에 **uamodt standalone_weather 양식 그대로** (`preset/season/localHour/seed/includeGust/t`) 동봉함 — 기존 weather_core snapshot 에 무변환 투입 → 그 파라미터로 바람장 구성·dynamics 적용 (grade 매핑: normal→good, warning→fair, serious→bad). 기체별 격자 계산은 weather_core 가 수행. |
| **V-3** | **2002 scenarioId 분기** | `integrated_service.py` — `on_dtam_execute` (L3689) 안에 `msg.scenarioId` 분기 추가 | `"S3"`: 배터리 열화 프로필 활성화 (faultStartSec=600, criticalAtSec=1500 → T+25 부근 9.4%) + UAO 겸업 판단 로직 무장. `"S1"`/`"S2"`/`None`: 분기 없음 |
| **V-4** | **4002 발행 로직 (UAO 겸업)** | 신규 — 자가진단 루프 (30Hz tick 또는 1Hz 별도) + `self.send(parse_payload("4002", {...}))` | battery_pct 감시: <20% → 4002 warning (`recommendedAction="return_to_base"`), <10% → 4002 critical (`eventType="BATTERY_VOLTAGE_LOW"`, `recommendedAction="emergency_landing"`, `availableDistance` 계산). 착륙 후 **같은 eventId 로 `status="cleared"`**. eventId: `WARN-{vehicleId}-{YYYYMMDD}-{seq}` |
| **V-5** | **다회 운항(시간표) 지원** ★S2 전제 | `integrated_service.py` — `_on_scheduled_flight` 의 plan 교체 모델 (`기존 계획이 있으면 교체`) → **기체당 plan 큐** 로 확장 | 현재 같은 aircraftId 의 새 3001 이 오면 기존 plan 을 폐기 — S2 셋 (3,360편/136대, 기체당 ~25편) 이 기체당 1편으로 붕괴됨 (실측: 세션 22, 비행 2대). 편 종료 (착륙·turnaround) 후 같은 기체의 다음 std 편을 자동 시작하는 시간표 실행 모델 필요. **임시 우회**: 스케줄러에서 기체당 1편 셋 (예: 136편/136대) 을 export 하면 현 구조로도 전 기체 비행 가능 |

**acceptance**: S3 — 4002 active 2건 (warning+critical) + cleared 1건, 3003 land 수신 후 VP_KU 50m 이내 착륙. S2 — setSpeed 1초 내 반영, planVersion=1 유지.

---

## 🩷 PSU 모듈 — 신모듈 반입 후 잔여 (2026-06-11 개선판 기준)

> **2026-06-11 개선판 PSU 반입됨** (`psu_icd_gateway.py` 신설). 코드 검토 결과:
> 3002/3003 draft→dispatch (운영자 UI 주도) 가 **허브 `POST /api/msg/{mid}` 와 정확히 호환** (SDK round-trip 검증 통과),
> **3002 발행 주체는 psu|mission 으로 확정** (D-3 — PSU 가 1차 발행자, sender 표기 psu 먼저).
> 4001/3001 수신 (DB/REST 폴링) 정상. **REST 경로가 검증되어 SDK 전환 (구 P-0) 은 필수→선택으로 격하.**

| # | 작업 | 상태 | 내용 |
|---|---|---|---|
| ~~P-0~~ | ~~SDK 전환~~ | **해소** | REST dispatch (`/api/msg/3003`) 가 허브와 호환 검증됨 — SDK 전환은 선택 (장기 권장) |
| P-1 | 4001 시계열 추적 | 부분 구현 | 4001 폴링은 있음 — S2 외삽용 시계열 누적/예측 입력화는 추가 필요 |
| P-3 | S2: 자동 충돌 예측 → 3003 setSpeed 자동 발행 | **선택 (자동화 — 반자동 시연으로 충족, D-2)** | 현재는 운영자 draft→dispatch **반자동** — S2 는 이대로 시연 (D-2 확정). 자동 예측 엔진 (90s lookahead, 분리<300m) 은 추후 선택 과제 |
| **P-4** | **S3: 4002 critical → 3003 land** | **차단** | ★ 신모듈에 **4002 수신 경로가 전무** (폴링/폴더 읽기 모두 없음) — 허브는 4002→PSU forward 준비 완료 상태. PSU 개발자에게 `/api/db/messages/4002/latest` 폴링 추가 요청 필요. **4001 battery_pct 감시는 있음 (≤20% 카운트) — 반자동 S3 가능 (운영자가 저전력 표시 보고 3003 land dispatch), 4002 폴링은 정식 트리거용 후속** |

**acceptance**: S2 — 3003 setSpeed ≥1건 (directTo 0건), S3 — 3003 land 정확히 1건, S1 — 발행 0건.

---

## 🟣 Mission 모듈 — 1건 (가장 적음)

데모 플랜 팩 + 2001 분기는 **구현·라이브 검증 완료** (`data/demo_plans/` + `on_flight_plan_request` — 2001 1발에 팩 plan 일괄 발행 확인).

| # | 작업 | 구현 위치 | 내용 |
|---|---|---|---|
| **M-1** | **3003 수신 → plan 장부 마킹** | `MissionModule/app/services/mission_service.py` — **`on_tactical_separation` override 없음 (신규 추가)**. SDK base stub 이 현재 조용히 버리는 중 | PSU 발 3003 수신 시 `msg.aircraftId` 로 자기 plan 찾아 — S2: fpn=1202 "전술 이탈 활성" 마킹 (plan 유지), S3: fpn=1201 superseded 마킹. **발행 없음** (3001 v2 재발행 금지). unknown fpn 무시 |

---

## 🔵 Visualization 모듈 — 선택 1건

| # | 작업 | 내용 |
|---|---|---|
| VZ-2 (선택) | 3003 land 강조 | 비상 착륙 시각화 + 카메라 트래킹 |

---

## 구현·테스트 순서 권장

```
P-0 (PSU SDK 전환) ──┬─▶ P-1 ─▶ P-3 (S2 사건 발생)
                     └─▶ P-4 (S3 사건 발생) ◀── V-4 (4002 가 먼저 있어야 P-4 테스트 가능)
V-1 (3003 실행) ◀─── P-3/P-4 출력의 수행자
V-2/V-3 독립 — 병렬 가능 / M-1 독립 — 언제든
```

**통합 테스트**: ① V-3+V-4 (배터리→4002) → ② P-0+P-4 (4002→3003 land) → ③ V-1 (land 수행) = **S3 완성** → ④ V-2+P-1/P-3 = **S2 완성**. S1 은 현행 완성.

**부분 테스트 팁** (상대 모듈 없이도 가능):
- V-1 테스트: 허브 REST 로 3003 직접 주입 — `POST http://허브:8096/api/msg/3003` (payload 는 `dtam_client.sample_tactical_separation()` 참고)
- P-4 테스트: 같은 방식으로 4002 주입 → PSU 가 3003 을 내보내는지 허브 MESSAGE COUNTERS / DB 로 확인
- 검증 도구: 라이브 모니터 `http://허브:8096/docs/sequence` + MESSAGE COUNTERS, DB `GET /api/db/messages/{mid}/latest`

## 데모 운영 절차 (현행, Ops Console — 검증 완료)

```
임무계획 패널 → 데모 시나리오 [S1|S2|S3] 선택 (수동 기체 편집 자동 잠김)
→ 설정 저장 → ▶ Play
→ 자동: 1001 → 2001(팩 파일명) → Mission 팩 3001 일괄 발행 → 2002(scenarioId) → 비행
S2 는 S2 선택 → 3,360편 prebuilt 일괄 발행 (Mission 직로딩) → 비행 중 기상 패널 바람 등급 serious 선택 → 1002 (wind.weather 자동 동봉) → PSU UI 에서 운영자 draft→dispatch (반자동)
[없음] 선택 시 기존 수동 흐름 (기체 하나씩 + 임무 입력) 그대로 — 데모 변경 무영향
```

**데모 플랜 팩**: `MissionModule/data/demo_plans/{S1_nominal, S2_psu_replan, S3_uao_battery_alt_vertiport}/3001_*.json`
- **S2 는 FPL prebuilt 셋 사용 (D-5)**: `PlugIn/FlightScheduler/FPL/20260611_131306_98f166edc22f` (prebuilt 3001 JSON 3,360개, 기체 136, vertiport 17, std 06:30~21:30). 콘솔 S2 버튼 → scenarioFileName `"20260611_131306_98f166edc22f.json"` → Mission prebuilt 직로딩 3,360편 발행, 스폰은 기체별 dedupe 136 entries (검증 완료). 기존 2기체 팩 (`demo_plans/S2_psu_replan`) 은 보존용으로 유지
- 기체 추가 = JSON 파일 추가 (코드 수정 0) — fpn 은 데모 대역 (1001, 1201~) 사용
- 출발시각은 sim 기본 시작 (06:30) 직후로 조정됨: S1 06:34 / S2 06:32+06:34 (2분 간격 = 회랑 진입 ~16초/880m 기하) / S3 06:32
- **2001 은 런당 1회만 발행 (중복 발행 금지)**. Mission 은 2001 수신 때마다 팩을 디스크에서 새로 읽음 — 팩 수정 후 다음 런의 2001 로 반영

---

## 참고: FPL 정기편 traffic 흐름 (구현 완료 — 데모 시나리오와 별개)

S1/S2/S3 데모 플랜 팩과는 **별개의 흐름**으로, FPL 정기편 traffic 사슬도 구현·동작 완료: 콘솔에서 **정기편 생성 → 불러오기 → 2001 → Mission 이 FPL CSV 를 읽어 3001 발행 → Vehicle 비행** (2001 한 발로 전 기체 비행). 데모 시나리오 선택과 혼용하지 않으며, 본 문서의 모듈 작업 목록 (V/P/M/VZ) 에는 영향 없음.
