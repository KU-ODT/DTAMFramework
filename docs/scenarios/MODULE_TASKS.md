# 데모 시나리오 (S1/S2/S3) — 모듈별 구현 작업 목록

> **기준: 2026-06-11, branch `JW`.** 전달 인프라 (Ops Console → IntegrationHub → Mission 데모 플랜 팩 → Vehicle → 지도 표출) 는 **S1 기준 end-to-end 라이브 검증 완료** (이륙 + 50 m/s 순항 실측).
> 남은 것은 각 모듈의 도메인 동작. 자기 모듈 섹션 + 해당 시나리오 명세의 **§4 모듈별 동작표** 만 보면 구현 가능하도록 작성.

## 현재 동작 상태 (라이브 검증 결과)

| 시나리오 | 지금 되는 것 | 막혀 있는 것 (담당 작업) |
|---|---|---|
| S1 정상 운항 | ✅ **전 구간 검증** — 데모 선택→설정 저장→Play→1001→2001→3001(팩)→2002→이륙→순항 (4001 10Hz, 지도 표출) | 없음 |
| S2 PSU 속도 조정 | 2기체 plan 로드·비행 ✓, "데모 날씨" 5004 발행 ✓ | Vehicle 자체 바람 생성 (**V-2**) / 충돌 예측·3003 발행 (**P-0~P-3**) / setSpeed 수행 (**V-1**) |
| S3 배터리 비상 | plan 로드·비행 ✓, scenarioId=S3 전달 ✓ | 배터리 열화+4002 발행 (**V-3, V-4**) / PSU 판단·3003 land (**P-4**) / land 수행 (**V-1**) |

**공통 전제**: `git pull origin JW`. ICD 스키마·라우팅·role base stub 은 SDK 에 전부 준비됨 — **base 메서드 override + 도메인 로직만** 구현하면 됨.

**참조 문서**: 시나리오 명세 `docs/scenarios/S{1,2,3}*.md` (§2 timeline / §4 모듈별 동작표 / §5 acceptance), ICD docs `DTAMSDK/dtam_client/icd/KOR/`.

---

## 🟢 Vehicle 모듈 (UAO 겸업) — 4건

**통신 구조 (확인됨)**: `IntegratedAirMobilityService(VehicleModule)` — SDK 100% 사용.
수신 stub 8개 전부 override 돼 있음 (`integrated_service.py` L3680~3701), 송신은 `self.send(parse_payload(...))` 단일 경로, 4001 은 `_Latest4001Publisher` (latest-only 비동기 10Hz).

| # | 작업 | 정확한 구현 위치 | 내용 |
|---|---|---|---|
| **V-1** | **3003 액션 실제 실행** ★최우선 | `integrated_service.py` — `on_tactical_separation` (L3695) → `_on_tactical_separation` (L3871). **override 는 이미 있음, 본문이 log-only** (수신 카운트만 올림) — 본문만 채우면 됨 | **setSpeed**: 대상 세션 targetSpeed 즉시 변경 (S2). **land**: 정상 plan 중단 → `action.vertiport` (또는 `targetLLA`) 로 강하·착륙 (S3). hold/directTo/rejoinPlan 은 데모 비필수. **`msg.scenarioId`** ("S1"\|"S2"\|"S3", optional) 가 PSU 발 3003 에 동봉됨 — 시나리오별 세부 세팅 분기 (예: S3 비상 강하율) 에 사용 가능 |
| **V-2** | **데모 바람 자체 생성** (5004 적용 아님) | Vehicle 내부 — 자체 WindModel / 바람 데이터 생성 (트리거: 2002 `scenarioId="S2"` 또는 1002 `wind.grade=serious`, 구현 선택) | Vehicle 은 **자체적으로 바람을 생성·적용** (사용자 결정). **5004 는 Vehicle 에서 처리 불필요** — base stub 이 조용히 소화하므로 무시해도 안전. 5004 의 실수요자는 PSU (궤적 예측) 와 Visual (표시). 참고: 현재 `config.wind_enabled=False` 로 부팅 |
| **V-3** | **2002 scenarioId 분기** | `integrated_service.py` — `on_dtam_execute` (L3689) 안에 `msg.scenarioId` 분기 추가 | `"S3"`: 배터리 열화 프로필 활성화 (faultStartSec=600, criticalAtSec=1500 → T+25 부근 9.4%) + UAO 겸업 판단 로직 무장. `"S1"`/`"S2"`/`None`: 분기 없음 |
| **V-4** | **4002 발행 로직 (UAO 겸업)** | 신규 — 자가진단 루프 (30Hz tick 또는 1Hz 별도) + `self.send(parse_payload("4002", {...}))` | battery_pct 감시: <20% → 4002 warning (`recommendedAction="return_to_base"`), <10% → 4002 critical (`eventType="BATTERY_VOLTAGE_LOW"`, `recommendedAction="emergency_landing"`, `availableDistance` 계산). 착륙 후 **같은 eventId 로 `status="cleared"`**. eventId: `WARN-{vehicleId}-{YYYYMMDD}-{seq}` |

**acceptance**: S3 — 4002 active 2건 (warning+critical) + cleared 1건, 3003 land 수신 후 VP_KU 50m 이내 착륙. S2 — setSpeed 1초 내 반영, planVersion=1 유지.

---

## 🩷 PSU 모듈 — 5건 (가장 큼)

| # | 작업 | 구현 위치 | 내용 |
|---|---|---|---|
| **P-0** | **★ 전제: SDK 전환** | `ExtenstionModule/PSUModule/app/services/dtam_live.py` 재작성 | 현재 REST/DB 폴링 (송신 불가) → `from dtam_client import PSUModule` 상속 + WS 연결 (`ws://허브:8096/ws/dtam`). Role.PSU 정식 등록돼 있어 socket 충돌 없음. **이거 없이는 3003 발행 자체가 불가** |
| **P-1** | 4001 수신 → 시계열 추적 | `on_vehicle_status(msg)` override | 기체별 position/속도 10Hz 누적 (S2 외삽의 입력). 주의: 4001 wire 는 `{vehicleId: {...}}` 다중 기체 형태 |
| **P-2** | 5004 수신 → 바람 반영 | `on_wind_effect_data(msg)` override | `vehicleWindEffects[]` 의 crossTrackDriftM / alongTrackDeltaMps 를 외삽 모델에 반영 |
| **P-3** | **S2: 궤적 외삽 + 3003 setSpeed 발행** | 내부 로직 + `self.send(parse_payload("3003", {...}))` | 90s lookahead 외삽 → 수평 분리 <300m 수렴 예측 → **3003**: `actions=[{type:"setSpeed", targetSpeed:40.0}]`, `reasonCode="LOSS_OF_SEPARATION_RISK"`, `commandId="TMP-PSU-{aircraftId}-{YYYYMMDD}-{seq}"`, **`scenarioId:"S2"` 동봉** (Vehicle 세부 세팅 분기용). 분리 ≥300m 회복 후 (선택) setSpeed 복원 또는 rejoinPlan(atSeq) |
| **P-4** | **S3: 4002 critical → 3003 land 발행** | `on_vehicle_warning_event(msg)` override | severity=critical & energy 계열만: 후보 [VP_KU, VP_JAMSIL, VP_YEOUIDO] 중 nearest_available → **3003**: `actions=[{type:"land", vertiport:"VP_KU", fatoNumber:"FATO_A"}]`, `reasonCode="LOW_BATTERY"`, **`scenarioId:"S3"` 동봉**. **warning 은 관찰만 (개입 금지)** |

(P-5 선택: 기존 PSU UI 의 Priority Event List 에 4002 수신·3003 개입 이력 표시)

**acceptance**: S2 — 3003 setSpeed ≥1건 (directTo 0건), S3 — 3003 land 정확히 1건, S1 — 발행 0건.

---

## 🟣 Mission 모듈 — 1건 (가장 적음)

데모 플랜 팩 + 2001 분기는 **구현·라이브 검증 완료** (`data/demo_plans/` + `on_flight_plan_request` — 2001 1발에 팩 plan 일괄 발행 확인).

| # | 작업 | 구현 위치 | 내용 |
|---|---|---|---|
| **M-1** | **3003 수신 → plan 장부 마킹** | `MissionModule/app/services/mission_service.py` — **`on_tactical_separation` override 없음 (신규 추가)**. SDK base stub 이 현재 조용히 버리는 중 | PSU 발 3003 수신 시 `msg.aircraftId` 로 자기 plan 찾아 — S2: fpn=1202 "전술 이탈 활성" 마킹 (plan 유지), S3: fpn=1201 superseded 마킹. **발행 없음** (3001 v2 재발행 금지). unknown fpn 무시 |

---

## 🔵 Visualization 모듈 — 선택 2건

| # | 작업 | 내용 |
|---|---|---|
| VZ-1 (선택) | 5004 바람 시각화 | `on_wind_effect_data` — 바람 벡터/영역 오버레이 |
| VZ-2 (선택) | 3003 land 강조 | 비상 착륙 시각화 + 카메라 트래킹 |

---

## 구현·테스트 순서 권장

```
P-0 (PSU SDK 전환) ──┬─▶ P-1/P-2 ─▶ P-3 (S2 사건 발생)
                     └─▶ P-4 (S3 사건 발생) ◀── V-4 (4002 가 먼저 있어야 P-4 테스트 가능)
V-1 (3003 실행) ◀─── P-3/P-4 출력의 수행자
V-2/V-3 독립 — 병렬 가능 / M-1 독립 — 언제든
```

**통합 테스트**: ① V-3+V-4 (배터리→4002) → ② P-0+P-4 (4002→3003 land) → ③ V-1 (land 수행) = **S3 완성** → ④ V-2+P-1~3 = **S2 완성**. S1 은 현행 완성.

**부분 테스트 팁** (상대 모듈 없이도 가능):
- V-1 테스트: 허브 REST 로 3003 직접 주입 — `POST http://허브:8096/api/msg/3003` (payload 는 `dtam_client.sample_tactical_separation()` 참고)
- P-4 테스트: 같은 방식으로 4002 주입 → PSU 가 3003 을 내보내는지 허브 MESSAGE COUNTERS / DB 로 확인
- 검증 도구: 라이브 모니터 `http://허브:8096/docs/sequence` + MESSAGE COUNTERS, DB `GET /api/db/messages/{mid}/latest`

## 데모 운영 절차 (현행, Ops Console — 검증 완료)

```
임무계획 패널 → 데모 시나리오 [S1|S2|S3] 선택 (수동 기체 편집 자동 잠김)
→ 설정 저장 → ▶ Play
→ 자동: 1001 → 2001(팩 파일명) → Mission 팩 3001 일괄 발행 → 2002(scenarioId) → 비행
S2 는 비행 중 기상 패널의 [데모 날씨] 버튼 → 5004 발행
[없음] 선택 시 기존 수동 흐름 (기체 하나씩 + 임무 입력) 그대로 — 데모 변경 무영향
```

**데모 플랜 팩**: `MissionModule/data/demo_plans/{S1_nominal, S2_psu_replan, S3_uao_battery_alt_vertiport}/3001_*.json`
- 기체 추가 = JSON 파일 추가 (코드 수정 0) — fpn 은 데모 대역 (1001, 1201~) 사용
- 출발시각은 sim 기본 시작 (06:30) 직후로 조정됨: S1 06:34 / S2 06:32+06:34 (2분 간격 = 회랑 진입 ~16초 기하) / S3 06:32
- Mission 은 2001 수신 때마다 팩을 디스크에서 새로 읽음 — 팩 수정 후 2001 재발사만 하면 반영
