# DTAM 시뮬레이션 시나리오 명세

> 본 폴더 = 편집용 source of truth. 모든 시나리오 자료를 한 파일에서 읽으려면 통합 reading view: C:/Users/HJW/Desktop/DTAM_시나리오_통합_2026-06-10.md 참조.

## Single Source of Truth
본 폴더 (`docs/scenarios/`) 가 S1/S2/S3 3개 시나리오 명세의 단일 원천. 다른 문서 (02_technical_architecture.md, DTAM_정리_2026-06-10.md, 외부 paste 자료 등) 는 본 폴더를 참조만 하고 시나리오 흐름을 중복 기술하지 않는다.
본 폴더를 외부 협업자에게 그대로 전달하면 시퀀스 다이어그램 작성, 시뮬레이션 입력 작성, end-to-end 테스트 구성 모두 가능.

## 외부 작업자에게 전달 시
다음 4개 파일을 묶음으로 공유:
- `README.md` (본 파일)
- `S1_nominal.md`
- `S2_psu_replan.md`
- `S3_uao_battery_alt_vertiport.md`
- `MODULE_TASKS.md` — 모듈별 구현 작업 목록 (Vehicle/PSU/Mission/Visualization — 현재 동작 상태 + 남은 일 + acceptance)

보조 자료 (ICD 4002 vehicleWarningEvent 스펙):
- `DTAMSDK/dtam_client/icd/KOR/4002_vehicleWarningEvent.md`
- `DTAMSDK/dtam_client/icd/ENG/4002_vehicleWarningEvent.md` (영문판)

## 개요
본 문서는 DTAM 통합 시뮬레이터에서 사용되는 3종 시나리오의 목적, 공통 가정, 트리거 메커니즘을 정리한다. 모든 시나리오는 동일한 ICD 메시지 집합 위에서 동작하며, 차이는 (1) 초기 조건과 (2) 운영 중 발생하는 이벤트의 종류로 결정된다.

## 시나리오 목록
| ID | 제목 | 트리거 | 핵심 ICD | 명세 |
|----|------|--------|----------|------|
| S1 | 정상 운항 | (없음, 기본 흐름) | 1001, 1003, 2001, 3001, 1002, 2002, 4001, 4101, 0003 | [S1_nominal.md](./S1_nominal.md) |
| S2 | 실시간 PSU 재계획 | PSU의 4001 분석에서 충돌 위험 감지 | + 확장된 2001(TRAFFIC_CONFLICT), 3001 v2, 3002, 3003 | [S2_psu_replan.md](./S2_psu_replan.md) |
| S3 | UAO 배터리 대체 vertiport | Vehicle의 4002 LOW_BATTERY critical | + 4002, 확장된 2001(LOW_BATTERY + arrivalVertiportHint), 3001 v2, 3003 land | [S3_uao_battery_alt_vertiport.md](./S3_uao_battery_alt_vertiport.md) |

## 공통 가정
- 시뮬레이션 시각의 표시는 KST(UTC+09:00) 기준이지만, **모든 ICD timestamp 는 UTC ISO-8601** 로 직렬화한다.
- 1003 ScenarioSetup 의 `scenarioFileName` 으로 시나리오를 식별한다.
- vehicle ID 는 `^[A-Z]{2,8}\d{4}$` 패턴을 만족해야 한다 (예: `UAM0001`).
- vertiport ID 는 string (예: `KU`, `Yeouido`, `Jamsil`) 이며 PSU/VPO 가 정적 카탈로그로 보유한다고 가정한다.
- 시뮬레이션 배속 `speed_x` 는 1 (real-time) ~ 10x 사이.

## 모듈 매트릭스
| 모듈 | S1 | S2 | S3 |
|------|----|----|----|
| OperationModule | 사용자 입력 → 1001/1003/2001/1002 송신, 4001 dashboard | 동일 + revise 알림 표시 | 동일 + 4002 alert 표시 |
| MissionModule | 2001 수신 → 3001 발행 | 2001 수신 → 3001 v2 + 3002 + 3003 directTo | 2001 수신 → 3001 v2 + 3003 land (긴급) |
| VehicleModule | 3001 수신 후 비행, 4001 10Hz 송신 | 3001 v2 수신 후 경로 갱신 | 4002 LOW_BATTERY 송신 + 3003 land 수행 |
| VisualizationModule | 3001 수신 후 시각화, 4101 5Hz 송신 | 갱신된 3001 v2 시각화 | 4101 송신 (필요 시 4103) |
| PSU | 4001 모니터링 | 4001 분석 → 2001 송신 (트리거) | 4002 수신 후 가용 vertiport 분석 → 2001 (alt vertiport hint) |
| VPO | 4001 수신 후 패드 통계 | 동일 | 알림 수신 (필요 시 패드 reserve) |
| UAO | 알림 수신 | 알림 수신 | 4002/4003 수신 후 운영자에게 보고 (수동 개입 권한) |
| Monitoring(Ops) | 운영자 dashboard | 운영자 dashboard + alert | 운영자 dashboard + 긴급 alert |

## 시나리오 트리거 방법
- **S1**: 일반 `scenarioFileName` 으로 1003 발행 후 1002 play 만으로 충분.
- **S2**: `scenarioFileName` 에 두 vehicle (`UAM0001`, `UAM0002`) 을 정의하고 **동일 corridor 진입 시간**을 부여. PSU 가 4001 stream 을 분석해 자동으로 conflict 를 감지한다.
- **S3**: `scenarioFileName` 에서 대상 vehicle 의 시작 SOC(battery) 를 80% 수준으로 낮춰 설정. 또는 5003 (AbnormalSituationCommand) 로 LOW_BATTERY 를 강제 주입 가능.

## 향후 확장 (선택)
- VPO 가 패드 점유 broadcast 메시지(예: 6001 류)를 송신하는 안 — 현재 명세에서는 PSU 가 정적 vertiport 카탈로그를 보유한다고 가정.
- UAO 가 1차 트리거 권한을 갖는 구조 — 현재는 PSU 가 1차이며, UAO 가 트리거 주체가 되려면 별도 거버넌스 결정이 필요.

## Last verified
- 2026-06-10
- SDK FORWARD_RULES["4001"] 에 PSU 추가됨 → S2 흐름 시뮬레이터 실행 가능.
