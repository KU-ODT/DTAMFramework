# PSU Monitoring SW 설계 명세서 및 체크리스트 끝판왕

작성 기준일: 2026-05-14 18:59:14 KST  
대상: 학교 연구개발용 UAM PSU Monitoring SW  
문서 목적: PSU Monitoring SW의 화면 구성, 내부 모듈, 데이터 모델, 분석 기능, 개발 체크리스트, 검증 체크리스트, 시연 시나리오를 한 문서로 정리

---

## 0. 문서 요약

본 문서는 UAM 운용 이해관계자 중 **PSU, Provider of Services for UAM**를 대상으로 하는 모니터링 소프트웨어 설계 문서이다.  
학교 연구개발 환경을 고려하여 화면은 지나치게 복잡하게 확장하지 않고, 다음 3개 핵심 화면으로 구성한다.

1. **Overview**  
   전체 UAM 교통 상황, 위험 이벤트, 주요 KPI를 보는 메인 화면

2. **Traffic Map / Strategic Conflict**  
   지도 기반 실시간 위치, 계획 경로, 회랑, 예측 충돌, 시간 창 중복, 버티포트 접근 충돌을 분석하는 화면

3. **Flow and Capacity**  
   수요 수용량 균형, 회랑별 밀도, 버티포트별 처리량, 지연 예측, 병목 원인을 분석하는 화면

핵심 방향은 **단순 관제 화면**이 아니라, PSU가 UAM 운항 상황을 통합 인지하고, 충돌과 혼잡을 사전에 분석하며, 교통관리 의사결정을 지원받는 **연구용 운영 콘솔**이다.

---

## 1. 시스템 정의

### 1.1 시스템명

권장 명칭:

- PSU Monitoring SW
- PSU Operations Monitoring Console
- UAM 교통관리 서비스 제공자 통합 모니터링 시스템

---

### 1.2 한 줄 정의

**PSU Monitoring SW는 UAM 운항 의도, 실시간 비행 상태, 회랑 및 버티포트 자원 정보를 통합하여 예측 충돌, 교통 혼잡, 수용량 초과, 지연 및 병목 원인을 분석하고 PSU의 전략적 교통관리 의사결정을 지원하는 연구용 운영 콘솔이다.**

---

### 1.3 시스템 목표

본 시스템의 목표는 다음과 같다.

- UAM 운항 현황을 실시간 또는 시뮬레이션 기반으로 통합 표시
- 운항 의도와 실시간 위치를 비교하여 계획 대비 편차 확인
- 웨이포인트, 회랑, 버티포트 접근 구간에서 전략적 충돌 위험 탐지
- 수요 수용량 균형을 분석하여 혼잡과 병목 예측
- 버티포트 FATO, Gate, 충전 자원 상태를 기반으로 지연 원인 분류
- 위험 이벤트를 우선순위화하여 PSU 운영자에게 제공
- 출발 지연, 속도 조정, 경로 변경, 도착 순서 조정 등 조치 후보 제공

---

### 1.4 학교 연구개발용 범위

본 문서의 설계 범위는 다음과 같다.

포함 범위:

- 더미 데이터 또는 시뮬레이션 데이터 기반 화면 구현
- 지도 기반 UAM 위치 및 경로 표시
- 운항 의도 기반 ETA 계산
- 웨이포인트 시간 창 기반 충돌 탐지
- 회랑 밀도 분석
- 버티포트 자원 점유율 분석
- 지연 및 병목 분석
- 시연용 이벤트 생성 및 리플레이

초기 단계에서 제외하거나 후순위로 둘 항목:

- 실제 항공당국 시스템 연동
- 실제 ADS-B 또는 감시 데이터 연동
- 실제 운항 승인 권한 처리
- 완전 자동 최적화 기반 운항 재계획
- 실제 항공 안전 인증 수준의 검증

---

## 2. 사용자와 사용 시나리오

### 2.1 주요 사용자

| 사용자 | 역할 | SW에서 필요한 기능 |
|---|---|---|
| PSU 운영자 | UAM 교통관리 서비스 제공 | 전체 상황 감시, 충돌 위험 확인, 조치 후보 검토 |
| 연구자 | 알고리즘 및 운영개념 검증 | 충돌 탐지, 수용량 분석, 지연 전파 분석 |
| 시연자 | 과제 또는 발표 시연 | 시나리오 리플레이, KPI 변화 설명, 이벤트 클릭 시연 |
| 버티포트 운영 연계 사용자 | 버티포트 자원 상태 확인 | FATO, Gate, 충전, Queue 상태 확인 |

---

### 2.2 대표 운영 질문

Overview에서 답해야 할 질문:

- 현재 운항 중인 UAM은 몇 대인가?
- 충돌 위험은 몇 건인가?
- 수용량 초과가 예상되는 자원은 어디인가?
- 평균 지연과 최대 지연은 얼마인가?
- 지금 가장 우선적으로 조치해야 할 이벤트는 무엇인가?

Traffic Map / Strategic Conflict에서 답해야 할 질문:

- UAM이 현재 어디에 있는가?
- 계획 경로와 실제 궤적이 일치하는가?
- 어떤 웨이포인트 또는 회랑에서 시간 창 중복이 발생하는가?
- 버티포트 접근 순서 충돌이 발생하는가?
- 충돌 완화를 위해 어떤 조치 후보가 가능한가?

Flow and Capacity에서 답해야 할 질문:

- 특정 시간대 수요가 수용량을 초과하는가?
- 어느 회랑이 혼잡한가?
- 어느 버티포트가 병목인가?
- 지연 원인이 FATO인지, Gate인지, 회랑인지 구분되는가?
- 지연이 후속 운항으로 전파되는가?

---

## 3. 전체 화면 구성

### 3.1 핵심 화면 3종

| 번호 | 화면명 | 핵심 목적 | 대표 기능 |
|---|---|---|---|
| 1 | Overview | 전체 상황 인지 | KPI, 미니 지도, 우선 이벤트, 버티포트 요약 |
| 2 | Traffic Map / Strategic Conflict | 실시간 위치 및 충돌 분석 | 지도, 경로, 회랑, 웨이포인트 ETA 충돌, 조치 후보 |
| 3 | Flow and Capacity | 흐름 및 수용량 분석 | DCB, 회랑 밀도, 버티포트 처리량, 지연 전파, 병목 진단 |

---

### 3.2 전체 GUI 공통 프레임

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ PSU Monitoring Console                                      14:32:10 KST    │
├────────────────────────────────────────────────────────────────────────────┤
│ [Overview] [Traffic Map / Conflict] [Flow & Capacity] [Replay] [Settings]  │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│                       Selected Main View Area                              │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

공통 상단 바 표시 항목:

- 시스템명
- 현재 시각
- 실시간 모드 또는 시뮬레이션 모드
- 데이터 수신 상태
- 전체 경고 상태
- 화면 전환 탭
- 시나리오 재생, 일시정지, 초기화 버튼

---

### 3.3 상태 색상 기준

| 상태 | 의미 | 예시 |
|---|---|---|
| Normal | 정상 | 분리 기준 충분, 자원 여유 |
| Caution | 주의 | 기준에 근접, 혼잡 증가 추세 |
| Warning | 위험 또는 조치 필요 | 분리 기준 미달, 수용량 초과 |
| Closed | 폐쇄 또는 사용 불가 | 회랑 폐쇄, FATO 사용 불가 |
| Unknown | 데이터 불명 | 위치 미수신, 상태 미확인 |

---

## 4. Overview 화면 설계

### 4.1 화면 목적

Overview는 PSU 운영자가 가장 먼저 확인하는 통합 상황판이다.  
세부 분석보다 전체 상황을 빠르게 파악하는 데 목적이 있다.

핵심 기능:

- 전체 운항 수 파악
- 검토 대기 운항 의도 파악
- 충돌 및 수용량 경고 확인
- 주요 버티포트 상태 확인
- 우선 조치 이벤트 확인
- 최근 및 미래 교통 흐름 추세 확인

---

### 4.2 Overview GUI 구성도

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ PSU Monitoring Console                                      14:32:10 KST    │
├────────────────────────────────────────────────────────────────────────────┤
│ [Overview] [Traffic Map / Conflict] [Flow & Capacity] [Replay] [Settings]  │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│ │ Active UAM   │ │ Pending Plan │ │ Conflict     │ │ Avg Delay    │       │
│ │     42       │ │     13       │ │   4 Warning  │ │   03:40      │       │
│ └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘       │
│                                                                            │
│ ┌──────────────────────────────────────┐ ┌───────────────────────────────┐ │
│ │ Mini Traffic Situation Map           │ │ Priority Event List            │ │
│ │                                      │ │ 1. UAM-021 conflict risk       │ │
│ │  - UAM positions                     │ │ 2. VP-03 FATO saturation       │ │
│ │  - corridor status                   │ │ 3. Corridor C2 density high    │ │
│ │  - vertiport status                  │ │ 4. UAM-014 ETA deviation       │ │
│ └──────────────────────────────────────┘ └───────────────────────────────┘ │
│                                                                            │
│ ┌──────────────────────────────┐ ┌───────────────────────────────────────┐ │
│ │ Vertiport Status Summary     │ │ Traffic Trend                         │ │
│ │ VP-01 Normal                 │ │ Active flights / delay / conflicts    │ │
│ │ VP-02 Caution                │ │ over next 30 min                      │ │
│ │ VP-03 Warning                │ │                                       │ │
│ └──────────────────────────────┘ └───────────────────────────────────────┘ │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

### 4.3 Overview 패널 구성

#### 4.3.1 KPI 카드

| KPI | 설명 | 갱신 기준 |
|---|---|---|
| Active UAM | 현재 운항 중인 UAM 수 | 실시간 위치 데이터 또는 운항 상태 |
| Pending Intent | 검토 대기 운항 의도 수 | 운항 계획 상태 |
| Conflict Alert | 충돌 위험 건수 | 충돌 탐지 모듈 결과 |
| Capacity Alert | 수용량 초과 예상 건수 | DCB 분석 결과 |
| Average Delay | 평균 지연 시간 | 지연 분석 결과 |
| Max Delay | 최대 지연 시간 | 지연 분석 결과 |
| Off-nominal Event | 비정상 이벤트 수 | 이벤트 로그 |
| Data Link Health | 데이터 연결 상태 | 인터페이스 상태 |

---

#### 4.3.2 Mini Traffic Situation Map

표시 요소:

- UAM 현재 위치
- 주요 회랑 상태
- 버티포트 상태
- 혼잡 구간
- 위험 이벤트 발생 위치
- 폐쇄 또는 제한 구역

설계 기준:

- 상세 분석보다 한눈에 보는 상황 인지 목적
- 레이어를 과도하게 넣지 않음
- 위험 이벤트 발생 위치만 강조
- 클릭 시 Traffic Map / Strategic Conflict로 이동

---

#### 4.3.3 Priority Event List

위험 이벤트를 우선순위로 정렬하여 표시한다.

예시:

```text
1. UAM-021 / UAM-034 predicted conflict at WP-07 in 06:20
2. VP-03 FATO saturation expected from 14:40 to 14:55
3. Corridor C2 density exceeds threshold
4. UAM-014 deviated from planned ETA by +03:10
```

이벤트 클릭 이동 규칙:

| 이벤트 유형 | 이동 화면 |
|---|---|
| 웨이포인트 충돌 | Traffic Map / Strategic Conflict |
| 회랑 혼잡 | Traffic Map / Strategic Conflict 또는 Flow and Capacity |
| 버티포트 수용량 초과 | Flow and Capacity |
| 지연 전파 | Flow and Capacity |
| 계획 경로 이탈 | Traffic Map / Strategic Conflict |
| 데이터 미수신 | Overview 상세 이벤트 |

---

#### 4.3.4 Vertiport Status Summary

버티포트별 상태 요약을 표시한다.

표시 항목:

- 버티포트 ID
- 출발 대기 수
- 도착 예정 수
- FATO 점유율
- Gate 점유율
- 평균 지연
- 상태 등급

예시:

```text
VP-01  Normal   FATO 62%   Gate 71%   Delay 01:20
VP-02  Caution  FATO 78%   Gate 84%   Delay 03:10
VP-03  Warning  FATO 96%   Gate 91%   Delay 07:40
```

---

### 4.4 Overview 내부 모듈

```text
Overview Dashboard Module
├─ KPI Aggregation Module
├─ Event Prioritization Module
├─ System Health Monitoring Module
├─ Mini Map Rendering Module
├─ Vertiport Summary Module
└─ Traffic Trend Summary Module
```

#### 4.4.1 KPI Aggregation Module

역할:

- 전체 운항 상태를 KPI로 변환
- 충돌, 지연, 수용량, 이벤트 정보를 집계

입력:

- FlightPlan
- TrackState
- ConflictEvent
- CapacityMetric
- VertiportState
- EventLog

출력:

- 운항 수
- 계획 수
- 경고 수
- 평균 지연
- 최대 지연
- 버티포트 포화도

---

#### 4.4.2 Event Prioritization Module

역할:

- 이벤트를 시간순이 아닌 운영 중요도 기준으로 정렬

우선순위 점수 예시:

```text
Event Priority Score =
위험도 점수 × 0.4
+ 영향 항공기 수 점수 × 0.2
+ 긴급도 점수 × 0.2
+ 지연 전파 점수 × 0.2
```

---

## 5. Traffic Map / Strategic Conflict 화면 설계

### 5.1 화면 목적

Traffic Map / Strategic Conflict는 UAM의 실시간 위치와 계획 경로를 지도 기반으로 표시하고, 예측 충돌 및 전략적 분리 문제를 분석하는 핵심 화면이다.

이 화면에서는 다음을 확인한다.

- UAM 현재 위치
- 계획 경로와 실제 궤적
- 회랑 점유 상태
- 웨이포인트 시간 창 중복
- 버티포트 접근 순서 충돌
- 충돌 상세 정보
- 조치 후보

---

### 5.2 Traffic Map / Strategic Conflict GUI 구성도

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ PSU Monitoring Console > Traffic Map / Strategic Conflict                  │
├────────────────────────────────────────────────────────────────────────────┤
│ [Overview] [Traffic Map / Conflict] [Flow & Capacity] [Replay] [Settings]  │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│ ┌─────────────────────┐ ┌───────────────────────────────────────────────┐ │
│ │ Flight Filter        │ │ Main Traffic Map                              │ │
│ │ - Active             │ │                                               │ │
│ │ - Planned            │ │   UAM icons                                    │ │
│ │ - Warning only       │ │   planned route                                │ │
│ │ - Corridor           │ │   actual trajectory                            │ │
│ │ - Vertiport          │ │   corridor layer                               │ │
│ └─────────────────────┘ │   conflict point                               │ │
│                         │   time-window overlap area                      │ │
│ ┌─────────────────────┐ │                                               │ │
│ │ Flight List          │ │                                               │ │
│ │ UAM-001 Normal       │ │                                               │ │
│ │ UAM-014 Caution      │ │                                               │ │
│ │ UAM-021 Warning      │ │                                               │ │
│ │ UAM-034 Warning      │ │                                               │ │
│ └─────────────────────┘ └───────────────────────────────────────────────┘ │
│                                                                            │
│ ┌──────────────────────────────────────────────┐ ┌──────────────────────┐ │
│ │ Conflict Timeline                            │ │ Conflict Detail       │ │
│ │ WP-07  14:38  UAM-021 / UAM-034              │ │ Type: Waypoint overlap │ │
│ │ C2     14:42  UAM-018 / UAM-029              │ │ ETA Gap: 32 sec        │ │
│ │ VP-03  14:46  Arrival sequence conflict      │ │ Severity: Warning      │ │
│ └──────────────────────────────────────────────┘ │ Suggested Action      │ │
│                                                  │ - Delay UAM-034 90 sec │ │
│                                                  │ - Speed adjust         │ │
│                                                  │ - Re-route candidate   │ │
│                                                  └──────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
```

---

### 5.3 주요 GUI 요소

#### 5.3.1 Main Traffic Map

표시 레이어:

- UAM 실시간 위치
- 계획 경로
- 실제 궤적
- 회랑 구간
- 웨이포인트
- 버티포트
- 충돌 예측 지점
- 시간 창 중복 영역
- 제한 공역
- 기상 위험 구역
- 대체 경로 후보

시각화 규칙:

| 항목 | 표현 방식 |
|---|---|
| 현재 위치 | 진한 UAM 아이콘 |
| 미래 예측 위치 | 반투명 UAM 아이콘 |
| 계획 경로 | 실선 |
| 실제 궤적 | 점선 |
| 회랑 | 반투명 선 또는 영역 |
| 위험 구간 | 강조선 |
| 충돌 지점 | 경고 마커 |
| 폐쇄 구역 | 회색 또는 사선 패턴 |

---

#### 5.3.2 Flight Filter

필터 항목:

- 운항 상태: Active, Planned, Delayed, Conflict Risk, Off-nominal
- 회랑: Corridor A, Corridor B, Corridor C
- 버티포트: VP-01, VP-02, VP-03
- 위험도: Normal, Caution, Warning

---

#### 5.3.3 Flight List

표시 항목:

- UAM ID
- 운항 ID
- 출발지
- 도착지
- 현재 상태
- ETA
- 지연
- 위험 등급

예시:

```text
UAM-001  VP-01 → VP-03  Active   ETA 14:42   Normal
UAM-014  VP-02 → VP-05  Active   ETA 14:46   Caution
UAM-021  VP-01 → VP-04  Active   ETA 14:38   Warning
UAM-034  VP-03 → VP-06  Planned  ETA 14:39   Warning
```

---

#### 5.3.4 Conflict Timeline

충돌 예상 이벤트를 시간축으로 표시한다.

예시:

```text
14:35 ───── 14:40 ───── 14:45 ───── 14:50
        ▲ WP-07 conflict
              ▲ Corridor C2 density high
                    ▲ VP-03 arrival sequence conflict
```

---

#### 5.3.5 Conflict Detail Panel

필수 표시 항목:

- Conflict ID
- 충돌 유형
- 위치
- 관련 항공기
- 예상 발생 시각
- ETA 차이
- 요구 분리 기준
- 위험 등급
- 영향 범위
- 추천 조치 후보

예시:

```text
Conflict ID: CF-20260514-001
Type: Waypoint time-window overlap
Location: WP-07
Aircraft: UAM-021 / UAM-034
Predicted Time: 14:38:20
ETA Difference: 32 sec
Required Separation: 90 sec
Severity: Warning

Suggested Actions:
1. Delay UAM-034 departure by 90 sec
2. Reduce UAM-021 speed by 8 kt
3. Assign alternate route R-2B to UAM-034
```

---

### 5.4 Traffic Map / Strategic Conflict 내부 모듈

```text
Traffic Map / Strategic Conflict Module
├─ Real-time Track Monitoring Module
├─ Operational Intent Overlay Module
├─ ETA Prediction Module
├─ Corridor Occupancy Monitoring Module
├─ Waypoint Time-window Conflict Detection Module
├─ Route Intersection Conflict Detection Module
├─ Vertiport Approach Conflict Detection Module
├─ Conflict Severity Assessment Module
├─ Suggested Action Generation Module
└─ Map Layer Rendering Module
```

#### 5.4.1 Real-time Track Monitoring Module

입력 데이터 예시:

```json
{
  "aircraft_id": "UAM-021",
  "latitude": 37.5123,
  "longitude": 127.1023,
  "altitude": 450,
  "ground_speed": 82,
  "heading": 135,
  "timestamp": "2026-05-14T14:32:10+09:00",
  "flight_status": "ACTIVE"
}
```

출력:

- 현재 위치
- 최근 궤적
- 계획 대비 편차
- 갱신 ETA
- 상태 등급

---

#### 5.4.2 Operational Intent Overlay Module

입력 데이터 예시:

```json
{
  "flight_plan_id": "FP-20260514-001",
  "aircraft_id": "UAM-021",
  "origin_vertiport": "VP-01",
  "destination_vertiport": "VP-04",
  "route_id": "R-01",
  "waypoint_sequence": ["WP-01", "WP-03", "WP-07", "WP-11"],
  "planned_departure_time": "2026-05-14T14:30:00+09:00",
  "planned_arrival_time": "2026-05-14T14:48:00+09:00",
  "planned_altitude": 450,
  "planned_speed": 80
}
```

출력:

- 계획 경로 레이어
- 웨이포인트별 예상 통과 시각
- 예상 도착 시각
- 계획 대비 편차

---

#### 5.4.3 ETA Prediction Module

역할:

- 현재 위치, 속도, 경로 잔여 거리 기반 ETA 갱신
- 웨이포인트별 통과 예상 시각 계산

간단한 계산식:

```text
Remaining Time = Remaining Distance / Ground Speed
Waypoint ETA = Current Time + Remaining Time to Waypoint
```

---

#### 5.4.4 Waypoint Time-window Conflict Detection Module

역할:

- 동일 웨이포인트를 통과하는 UAM 간 ETA 차이를 비교
- 요구 시간 간격보다 작으면 충돌 위험으로 판단

예시:

```text
UAM-021 → WP-07 ETA 14:38:20
UAM-034 → WP-07 ETA 14:38:52

ETA Gap = 32 sec
Required Gap = 90 sec

Result = Conflict Risk
```

판정 기준:

| ETA Gap | 상태 |
|---|---|
| Required Gap 이상 | Normal |
| Required Gap의 70~100% | Caution |
| Required Gap의 70% 미만 | Warning |

---

#### 5.4.5 Corridor Occupancy Monitoring Module

역할:

- 회랑 구간별 현재 점유 항공기 수 계산
- 회랑 구간별 미래 점유 항공기 수 예측
- 기준 초과 시 혼잡 이벤트 생성

예시:

```text
Corridor C2
현재 점유 항공기: 5대
5분 후 예상 점유: 8대
허용 기준: 6대
상태: Warning
```

---

#### 5.4.6 Vertiport Approach Conflict Detection Module

역할:

- 버티포트 접근 구간에서 도착 순서 충돌 분석
- FATO 사용 가능 시각과 도착 ETA 비교

예시:

```text
VP-03 FATO available at 14:42:00

UAM-011 ETA 14:41:40
UAM-019 ETA 14:42:10
UAM-027 ETA 14:42:35

Approach sequence conflict detected
```

---

#### 5.4.7 Suggested Action Generation Module

조치 후보:

- 출발 지연
- 속도 조정
- 대체 경로 배정
- 고도 분리
- 도착 순서 재조정
- 대체 버티포트 유도

초기 구현 기준:

- 자동 최적화가 아니라 후보 생성 중심
- 후보별 예상 효과는 간단 지표로 표시
- 예: 충돌 해소 여부, 지연 증가량, 영향 항공기 수

---

## 6. Flow and Capacity 화면 설계

### 6.1 화면 목적

Flow and Capacity 화면은 UAM 교통 흐름, 수요 수용량 균형, 회랑 밀도, 버티포트 처리량, 지연 및 병목 원인을 분석한다.

이 화면은 학교 연구개발 결과를 가장 잘 보여줄 수 있는 분석 화면이다.

핵심 기능:

- Demand-Capacity Balance 분석
- 회랑별 밀도 분석
- 버티포트 처리량 분석
- FATO 및 Gate 점유율 분석
- 지연 추정
- 지연 전파 분석
- 병목 원인 진단
- 완화 시나리오 비교

---

### 6.2 Flow and Capacity GUI 구성도

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ PSU Monitoring Console > Flow and Capacity                                │
├────────────────────────────────────────────────────────────────────────────┤
│ [Overview] [Traffic Map / Conflict] [Flow & Capacity] [Replay] [Settings]  │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│ ┌─────────────────────┐ ┌───────────────────────────────────────────────┐ │
│ │ Analysis Condition   │ │ Demand-Capacity Balance Chart                 │ │
│ │ Time: 14:00-16:00    │ │                                               │ │
│ │ Interval: 5 min      │ │ demand                                        │ │
│ │ Target: All network  │ │ capacity                                      │ │
│ │ Scenario: Baseline   │ │ overload area                                 │ │
│ └─────────────────────┘ └───────────────────────────────────────────────┘ │
│                                                                            │
│ ┌──────────────────────────────┐ ┌───────────────────────────────────────┐ │
│ │ Corridor Density Heatmap      │ │ Vertiport Throughput Panel            │ │
│ │ C1: Normal                   │ │ VP-01 Dep 12 / Arr 10 / Delay 01:20   │ │
│ │ C2: Warning                  │ │ VP-02 Dep 8  / Arr 14 / Delay 03:10   │ │
│ │ C3: Caution                  │ │ VP-03 Dep 6  / Arr 19 / Delay 07:40   │ │
│ └──────────────────────────────┘ └───────────────────────────────────────┘ │
│                                                                            │
│ ┌──────────────────────────────────────────────┐ ┌──────────────────────┐ │
│ │ Delay Propagation Timeline                    │ │ Bottleneck Diagnosis  │ │
│ │ VP-03 delay → C2 holding → VP-05 arrival delay │ │ Main bottleneck: VP-03 │ │
│ │                                               │ │ Cause: FATO saturation │ │
│ │                                               │ │ Expected duration: 15m │ │
│ │                                               │ │ Suggested mitigation   │ │
│ └──────────────────────────────────────────────┘ └──────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
```

---

### 6.3 주요 GUI 요소

#### 6.3.1 Analysis Condition Panel

설정 항목:

- 분석 시간 범위
- 집계 간격
- 분석 대상
- 시나리오
- 필터 조건

분석 대상 예시:

- 전체 네트워크
- 특정 회랑
- 특정 버티포트
- 특정 OD
- 특정 시간대

시나리오 예시:

- Baseline
- Delay mitigation
- Route adjustment
- Vertiport closure
- Increased demand

---

#### 6.3.2 Demand-Capacity Balance Chart

시간대별 수요와 수용량을 비교한다.

예시:

```text
14:00-14:05  Demand 8   Capacity 10   Normal
14:05-14:10  Demand 11  Capacity 10   Caution
14:10-14:15  Demand 15  Capacity 10   Warning
14:15-14:20  Demand 13  Capacity 10   Warning
```

---

#### 6.3.3 Corridor Density Heatmap

회랑별 밀도를 히트맵으로 표시한다.

예시:

```text
Corridor A1  Normal
Corridor A2  Normal
Corridor B1  Caution
Corridor C2  Warning
Corridor C3  Caution
```

---

#### 6.3.4 Vertiport Throughput Panel

버티포트별 처리량과 점유율을 표시한다.

예시:

```text
VP-01
Departure: 12
Arrival: 10
FATO Utilization: 62%
Gate Utilization: 71%
Average Delay: 01:20

VP-03
Departure: 6
Arrival: 19
FATO Utilization: 96%
Gate Utilization: 91%
Average Delay: 07:40
Status: Warning
```

---

#### 6.3.5 Delay Propagation Timeline

지연이 시간과 네트워크를 따라 어떻게 전파되는지 표시한다.

예시:

```text
14:10  VP-03 도착 수요 증가
14:15  VP-03 FATO 점유율 95% 초과
14:18  C2 회랑 접근 대기 발생
14:23  UAM-027 도착 지연 +04:30
14:30  VP-05 후속 출발 지연 발생
```

---

#### 6.3.6 Bottleneck Diagnosis Panel

병목 위치와 원인을 표시한다.

예시:

```text
Main Bottleneck: VP-03
Bottleneck Type: FATO saturation
Affected Flights: 7
Expected Delay: 42 min total
Propagation Risk: High

Suggested Mitigation:
1. Delay departures from VP-01 to VP-03 by 3 min
2. Reassign 2 arrivals to VP-04
3. Increase separation interval in C2 corridor
```

---

### 6.4 Flow and Capacity 내부 모듈

```text
Flow and Capacity Module
├─ Demand Aggregation Module
├─ Capacity Modeling Module
├─ Demand-Capacity Balance Module
├─ Corridor Density Analysis Module
├─ Vertiport Throughput Analysis Module
├─ Delay Estimation Module
├─ Delay Propagation Analysis Module
├─ Bottleneck Diagnosis Module
└─ Mitigation Scenario Evaluation Module
```

#### 6.4.1 Demand Aggregation Module

역할:

- 운항 의도를 시간대별 수요로 변환

입력:

- 운항 계획
- 출발 시각
- 도착 시각
- 출발 버티포트
- 도착 버티포트
- 사용 회랑
- 웨이포인트 통과 예정 시각

출력:

- 시간대별 출발 수요
- 시간대별 도착 수요
- 회랑별 통과 수요
- 버티포트별 처리 요구량

---

#### 6.4.2 Capacity Modeling Module

대상 자원:

- 버티포트 FATO
- Gate
- 충전 스팟
- 회랑
- 웨이포인트
- 접근 경로
- 출발 경로

예시:

```text
VP-03 FATO capacity = 1 operation / 90 sec
VP-03 Gate capacity = 6 aircraft
Corridor C2 capacity = 6 aircraft / 5 min
WP-07 minimum time gap = 90 sec
```

---

#### 6.4.3 Demand-Capacity Balance Module

계산식:

```text
Utilization = Demand / Capacity
```

상태 기준:

| Utilization | 상태 |
|---|---|
| 0.00 ~ 0.60 | Normal |
| 0.60 ~ 0.85 | Caution |
| 0.85 이상 | Warning |

---

#### 6.4.4 Corridor Density Analysis Module

계산식:

```text
Corridor Density = 해당 회랑 내 항공기 수 / 회랑 허용 항공기 수
```

---

#### 6.4.5 Vertiport Throughput Analysis Module

분석 지표:

- FATO Utilization
- Gate Utilization
- Arrival Throughput
- Departure Throughput
- Turnaround Time
- Queue Length
- Average Delay
- Maximum Delay

---

#### 6.4.6 Delay Estimation Module

기본 계산식:

```text
Departure Delay = Actual Departure Time - Scheduled Departure Time
Arrival Delay = Actual Arrival Time - Scheduled Arrival Time
Resource Delay = Resource Available Time - Requested Resource Time
```

지연 원인 분류:

- 공역 혼잡 지연
- 회랑 점유 지연
- 웨이포인트 분리 지연
- FATO 대기 지연
- Gate 대기 지연
- 충전 지연
- 비정상 이벤트 지연

---

#### 6.4.7 Delay Propagation Analysis Module

예시:

```text
UAM-007 arrival delay +05:00
↓
Turnaround start delay +05:00
↓
Next flight departure delay +05:00
↓
Destination VP-05 arrival slot conflict
```

---

#### 6.4.8 Bottleneck Diagnosis Module

출력:

- 병목 위치
- 병목 유형
- 영향 운항 수
- 총 지연 시간
- 예상 지속 시간
- 완화 조치 후보

병목 유형:

- FATO saturation
- Gate shortage
- Corridor congestion
- Waypoint separation overload
- Charging resource shortage
- Arrival sequence conflict

---

## 7. 전체 시스템 아키텍처

### 7.1 계층 구조

```text
PSU Monitoring SW
├─ Data Interface Layer
│  ├─ UAM Operator Data Interface
│  ├─ Vertiport Data Interface
│  ├─ Surveillance Data Interface
│  ├─ Weather / Constraint Data Interface
│  └─ Other PSU / Authority Interface
│
├─ Core Data Management Layer
│  ├─ Flight Plan Management Module
│  ├─ Real-time Track Management Module
│  ├─ Route / Corridor Management Module
│  ├─ Vertiport Resource Management Module
│  └─ Event Log Management Module
│
├─ Analysis Layer
│  ├─ KPI Aggregation Module
│  ├─ Strategic Conflict Detection Module
│  ├─ Corridor Density Analysis Module
│  ├─ Demand-Capacity Balance Module
│  ├─ Delay Estimation Module
│  ├─ Delay Propagation Analysis Module
│  └─ Bottleneck Diagnosis Module
│
├─ Decision Support Layer
│  ├─ Suggested Action Generation Module
│  ├─ Departure Delay Recommendation Module
│  ├─ Route Adjustment Candidate Module
│  ├─ Arrival Sequencing Support Module
│  └─ Mitigation Scenario Evaluation Module
│
└─ GUI Layer
   ├─ Overview Dashboard
   ├─ Traffic Map / Strategic Conflict View
   ├─ Flow and Capacity View
   ├─ Event Detail Panel
   └─ Replay / Report View
```

---

### 7.2 데이터 흐름 구성도

```text
┌─────────────────┐
│ UAM Operator     │
│ 운항 의도, 상태   │
└────────┬────────┘
         │
┌────────▼────────┐
│ PSU Data Server  │
│ 데이터 수집, 정합 │
└────────┬────────┘
         │
         ├─────────────────────────────┐
         │                             │
┌────────▼────────┐          ┌─────────▼─────────┐
│ Real-time DB     │          │ Analysis Engine    │
│ 위치, 상태, 계획 │          │ 충돌, 혼잡, 지연    │
└────────┬────────┘          └─────────┬─────────┘
         │                             │
         └──────────────┬──────────────┘
                        │
              ┌─────────▼─────────┐
              │ GUI Application    │
              │ Overview           │
              │ Traffic / Conflict │
              │ Flow / Capacity    │
              └───────────────────┘
```

---

### 7.3 화면 간 연동 구조

```text
Overview
  └─ 위험 이벤트 클릭
       ├─ 충돌 이벤트 → Traffic Map / Strategic Conflict 이동
       └─ 수용량 이벤트 → Flow and Capacity 이동

Traffic Map / Strategic Conflict
  └─ 특정 회랑 또는 웨이포인트 클릭
       └─ Flow and Capacity에서 해당 구간 밀도 분석 표시

Flow and Capacity
  └─ 특정 버티포트 병목 클릭
       ├─ Overview 이벤트 목록 업데이트
       └─ Traffic Map에서 관련 운항 강조
```

---

## 8. 데이터 모델 초안

### 8.1 FlightPlan

```json
{
  "flight_plan_id": "FP-20260514-001",
  "aircraft_id": "UAM-021",
  "operator_id": "OP-01",
  "origin_vertiport": "VP-01",
  "destination_vertiport": "VP-04",
  "route_id": "R-01",
  "waypoints": ["WP-01", "WP-03", "WP-07", "WP-11"],
  "planned_departure_time": "2026-05-14T14:30:00+09:00",
  "planned_arrival_time": "2026-05-14T14:48:00+09:00",
  "planned_altitude": 450,
  "planned_speed": 80,
  "status": "ACCEPTED"
}
```

---

### 8.2 TrackState

```json
{
  "aircraft_id": "UAM-021",
  "flight_plan_id": "FP-20260514-001",
  "latitude": 37.5123,
  "longitude": 127.1023,
  "altitude": 450,
  "ground_speed": 82,
  "heading": 135,
  "timestamp": "2026-05-14T14:32:10+09:00",
  "flight_status": "ACTIVE"
}
```

---

### 8.3 VertiportState

```json
{
  "vertiport_id": "VP-03",
  "fato_total": 1,
  "fato_available": 0,
  "gate_total": 6,
  "gate_available": 1,
  "charging_spot_total": 4,
  "charging_spot_available": 1,
  "arrival_queue": 5,
  "departure_queue": 2,
  "average_delay_sec": 460,
  "status": "WARNING"
}
```

---

### 8.4 ConflictEvent

```json
{
  "conflict_id": "CF-20260514-001",
  "conflict_type": "WAYPOINT_TIME_WINDOW_OVERLAP",
  "location_id": "WP-07",
  "related_aircraft": ["UAM-021", "UAM-034"],
  "predicted_time": "2026-05-14T14:38:20+09:00",
  "eta_gap_sec": 32,
  "required_gap_sec": 90,
  "severity": "WARNING",
  "suggested_actions": [
    "Delay UAM-034 departure by 90 sec",
    "Reduce UAM-021 speed by 8 kt",
    "Assign alternate route R-2B to UAM-034"
  ]
}
```

---

### 8.5 CapacityMetric

```json
{
  "target_type": "VERTIPORT",
  "target_id": "VP-03",
  "time_window_start": "2026-05-14T14:10:00+09:00",
  "time_window_end": "2026-05-14T14:15:00+09:00",
  "demand": 15,
  "capacity": 10,
  "utilization": 1.5,
  "status": "WARNING"
}
```

---

### 8.6 EventLog

```json
{
  "event_id": "EV-20260514-001",
  "event_type": "CAPACITY_ALERT",
  "severity": "WARNING",
  "title": "VP-03 FATO saturation expected",
  "related_targets": ["VP-03", "UAM-011", "UAM-019", "UAM-027"],
  "created_time": "2026-05-14T14:15:00+09:00",
  "expected_time": "2026-05-14T14:40:00+09:00",
  "status": "OPEN",
  "recommended_screen": "Flow and Capacity"
}
```

---

## 9. API 초안

### 9.1 Flight Plan API

| Method | Endpoint | 설명 |
|---|---|---|
| GET | /api/flight-plans | 전체 운항 계획 조회 |
| GET | /api/flight-plans/{flight_plan_id} | 특정 운항 계획 조회 |
| POST | /api/flight-plans | 운항 계획 등록 |
| PATCH | /api/flight-plans/{flight_plan_id} | 운항 계획 상태 변경 |

---

### 9.2 Track API

| Method | Endpoint | 설명 |
|---|---|---|
| GET | /api/tracks/current | 현재 UAM 위치 조회 |
| GET | /api/tracks/{aircraft_id} | 특정 UAM 위치 이력 조회 |
| POST | /api/tracks | 위치 데이터 입력 |
| WS | /ws/tracks | 실시간 위치 스트리밍 |

---

### 9.3 Conflict API

| Method | Endpoint | 설명 |
|---|---|---|
| GET | /api/conflicts | 충돌 이벤트 목록 조회 |
| GET | /api/conflicts/{conflict_id} | 충돌 상세 조회 |
| POST | /api/conflicts/run | 충돌 탐지 실행 |

---

### 9.4 Capacity API

| Method | Endpoint | 설명 |
|---|---|---|
| GET | /api/capacity/summary | 전체 수용량 요약 조회 |
| GET | /api/capacity/vertiports | 버티포트 수용량 조회 |
| GET | /api/capacity/corridors | 회랑 수용량 조회 |
| POST | /api/capacity/run | 수요 수용량 분석 실행 |

---

### 9.5 Event API

| Method | Endpoint | 설명 |
|---|---|---|
| GET | /api/events | 이벤트 목록 조회 |
| GET | /api/events/priority | 우선순위 이벤트 조회 |
| PATCH | /api/events/{event_id} | 이벤트 상태 변경 |

---

## 10. 핵심 알고리즘 초안

### 10.1 웨이포인트 ETA 기반 충돌 탐지

```text
입력:
- FlightPlan 목록
- 각 FlightPlan의 waypoint_sequence
- 각 waypoint의 ETA
- required_gap_sec

절차:
1. 모든 운항에 대해 웨이포인트별 ETA를 계산한다.
2. 동일 웨이포인트를 통과하는 운항 쌍을 찾는다.
3. 각 운항 쌍의 ETA 차이를 계산한다.
4. ETA 차이가 required_gap_sec보다 작으면 충돌 후보로 등록한다.
5. ETA 차이에 따라 Caution 또는 Warning 등급을 부여한다.
6. 충돌 후보를 ConflictEvent로 저장한다.

출력:
- ConflictEvent 목록
```

---

### 10.2 회랑 점유율 분석

```text
입력:
- Corridor 목록
- 각 Corridor의 capacity
- 실시간 또는 예측 UAM 위치
- 분석 시간 범위

절차:
1. 회랑별로 현재 점유 항공기 수를 계산한다.
2. 미래 시간대별 예상 점유 항공기 수를 계산한다.
3. Occupancy Ratio = Occupied Aircraft / Corridor Capacity를 계산한다.
4. 기준값에 따라 Normal, Caution, Warning을 부여한다.

출력:
- CorridorDensityMetric 목록
```

---

### 10.3 버티포트 병목 진단

```text
입력:
- VertiportState
- 도착 예정 운항
- 출발 예정 운항
- FATO capacity
- Gate capacity
- turnaround time

절차:
1. 시간대별 도착 수요와 출발 수요를 집계한다.
2. FATO 처리 가능 횟수와 비교한다.
3. Gate 점유율과 비교한다.
4. 초과 수요가 발생한 자원을 병목 후보로 등록한다.
5. 총 지연 시간과 영향 운항 수를 계산한다.
6. 병목 유형을 FATO, Gate, Charging, Approach 중 하나로 분류한다.

출력:
- BottleneckDiagnosis 결과
```

---

### 10.4 지연 전파 분석

```text
입력:
- 운항 스케줄
- 항공기 순환 계획
- 도착 지연
- turnaround time

절차:
1. 지연 운항의 도착 지연을 계산한다.
2. 동일 항공기의 다음 운항 출발 시각을 확인한다.
3. turnaround time을 고려하여 다음 출발 가능 시각을 계산한다.
4. 다음 출발 지연을 계산한다.
5. 후속 운항이 다른 버티포트 슬롯과 충돌하는지 확인한다.
6. 지연 전파 이벤트를 생성한다.

출력:
- DelayPropagationEvent 목록
```

---

## 11. 개발 기술 스택 제안

### 11.1 Frontend

초기 연구용 추천:

```text
React + TypeScript + Tailwind CSS + Leaflet + Recharts
```

3D 회랑 시각화가 필요한 경우:

```text
React + TypeScript + CesiumJS
```

지도 후보:

- Leaflet: 2D 지도 구현이 쉽고 빠름
- Mapbox: 시각화 품질이 좋음
- CesiumJS: 3D 공역 및 고도 표현에 적합

차트 후보:

- Recharts
- ECharts
- Plotly

---

### 11.2 Backend

추천:

```text
Python + FastAPI + WebSocket + Pydantic + Pandas
```

공간 분석 추가 시:

```text
Shapely + GeoPandas + PostGIS
```

네트워크 분석 추가 시:

```text
NetworkX
```

---

### 11.3 Database

초기 시연용:

```text
SQLite
```

연구 확장형:

```text
PostgreSQL + PostGIS
```

실시간 캐시:

```text
Redis
```

---

## 12. 개발 폴더 구조 예시

```text
psu-monitoring-sw/
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ api/
│  │  │  ├─ flight_plan_api.py
│  │  │  ├─ track_api.py
│  │  │  ├─ conflict_api.py
│  │  │  ├─ capacity_api.py
│  │  │  └─ event_api.py
│  │  ├─ models/
│  │  │  ├─ flight_plan.py
│  │  │  ├─ track_state.py
│  │  │  ├─ vertiport_state.py
│  │  │  ├─ conflict_event.py
│  │  │  └─ capacity_metric.py
│  │  ├─ services/
│  │  │  ├─ kpi_service.py
│  │  │  ├─ conflict_detection_service.py
│  │  │  ├─ capacity_analysis_service.py
│  │  │  ├─ delay_estimation_service.py
│  │  │  └─ recommendation_service.py
│  │  ├─ simulation/
│  │  │  ├─ scenario_loader.py
│  │  │  ├─ traffic_generator.py
│  │  │  └─ replay_engine.py
│  │  └─ db/
│  │     ├─ database.py
│  │     └─ seed_data.py
│  └─ requirements.txt
│
├─ frontend/
│  ├─ src/
│  │  ├─ components/
│  │  │  ├─ common/
│  │  │  ├─ overview/
│  │  │  ├─ traffic-map/
│  │  │  └─ flow-capacity/
│  │  ├─ pages/
│  │  │  ├─ OverviewPage.tsx
│  │  │  ├─ TrafficConflictPage.tsx
│  │  │  └─ FlowCapacityPage.tsx
│  │  ├─ stores/
│  │  ├─ services/
│  │  ├─ types/
│  │  └─ App.tsx
│  └─ package.json
│
├─ data/
│  ├─ scenarios/
│  ├─ routes/
│  ├─ vertiports/
│  └─ sample_tracks/
│
├─ docs/
│  ├─ system_design.md
│  ├─ api_spec.md
│  └─ demo_scenario.md
│
└─ README.md
```

---

## 13. 개발 우선순위

### 13.1 1단계: 시연 가능한 기본형

목표: 움직이는 PSU 콘솔 구축

필수 기능:

- Overview KPI 대시보드
- 지도 기반 UAM 위치 표시
- 운항 계획 경로 표시
- 웨이포인트 ETA 기반 충돌 탐지
- 버티포트 FATO, Gate 상태 표시
- 기본 이벤트 리스트
- 화면 간 이동

완료 기준:

- 더미 데이터 또는 시뮬레이션 데이터로 전체 화면 동작
- UAM 위치와 계획 경로 지도 표시
- 동일 웨이포인트 ETA 충돌 탐지
- Overview 이벤트 클릭 시 관련 화면 이동

---

### 13.2 2단계: 분석 기능 강화형

목표: 연구성과가 보이는 분석 기능 추가

필수 기능:

- 회랑별 밀도 분석
- 수요 수용량 비교
- 버티포트 처리량 분석
- 지연 추정
- 병목 진단
- 충돌 위험도 등급화
- 충돌 상세 패널

완료 기준:

- 회랑 또는 버티포트별 혼잡도 계산
- Demand-Capacity Chart 표시
- 병목 원인을 FATO, Gate, 회랑 등으로 분류
- 운항별 지연 계산

---

### 13.3 3단계: 의사결정 지원형

목표: PSU 판단 지원 기능 구현

필수 기능:

- 출발 지연 권고
- 대체 경로 후보
- 도착 순서 재조정 후보
- 대체 버티포트 추천
- 시나리오별 완화 효과 비교
- 리플레이 및 리포트 출력

완료 기준:

- 충돌 이벤트에 대해 조치 후보 생성
- 조치 적용 전후의 지연, 충돌 건수, 수용량 초과 시간 비교
- 시나리오 결과 리포트 출력 가능

---

## 14. 체크리스트

### 14.1 기획 체크리스트

- [ ] PSU의 역할 정의가 명확한가?
- [ ] SW 목적이 단순 관제가 아니라 PSU 교통관리 지원으로 정의되었는가?
- [ ] 화면 구성이 Overview, Traffic Map / Strategic Conflict, Flow and Capacity로 정리되었는가?
- [ ] 각 화면의 사용자 질문이 정의되었는가?
- [ ] 연구성과로 보여줄 핵심 기능이 정리되었는가?
- [ ] 시연 시나리오가 정의되었는가?
- [ ] 더미 데이터 또는 시뮬레이션 데이터 생성 방식이 정의되었는가?

---

### 14.2 GUI 체크리스트

공통 GUI:

- [ ] 상단 네비게이션이 모든 화면에 존재하는가?
- [ ] 현재 시간과 데이터 수신 상태가 표시되는가?
- [ ] 상태 색상 기준이 일관적인가?
- [ ] 이벤트 클릭 시 관련 화면으로 이동하는가?
- [ ] 반응형 레이아웃 또는 고정 해상도 기준이 정리되었는가?

Overview:

- [ ] Active UAM KPI가 표시되는가?
- [ ] Pending Intent KPI가 표시되는가?
- [ ] Conflict Alert KPI가 표시되는가?
- [ ] Capacity Alert KPI가 표시되는가?
- [ ] Average Delay KPI가 표시되는가?
- [ ] Mini Traffic Situation Map이 표시되는가?
- [ ] Priority Event List가 표시되는가?
- [ ] Vertiport Status Summary가 표시되는가?
- [ ] Traffic Trend가 표시되는가?

Traffic Map / Strategic Conflict:

- [ ] UAM 실시간 위치가 지도에 표시되는가?
- [ ] 계획 경로가 지도에 표시되는가?
- [ ] 실제 궤적이 지도에 표시되는가?
- [ ] 회랑 레이어가 표시되는가?
- [ ] 웨이포인트가 표시되는가?
- [ ] 충돌 위험 지점이 표시되는가?
- [ ] Flight Filter가 작동하는가?
- [ ] Flight List가 표시되는가?
- [ ] Conflict Timeline이 표시되는가?
- [ ] Conflict Detail Panel이 표시되는가?
- [ ] Suggested Action이 표시되는가?

Flow and Capacity:

- [ ] Analysis Condition Panel이 존재하는가?
- [ ] Demand-Capacity Balance Chart가 표시되는가?
- [ ] Corridor Density Heatmap이 표시되는가?
- [ ] Vertiport Throughput Panel이 표시되는가?
- [ ] Delay Propagation Timeline이 표시되는가?
- [ ] Bottleneck Diagnosis Panel이 표시되는가?
- [ ] 특정 회랑 또는 버티포트 선택 시 상세 분석이 표시되는가?

---

### 14.3 데이터 체크리스트

- [ ] FlightPlan 데이터 구조가 정의되었는가?
- [ ] TrackState 데이터 구조가 정의되었는가?
- [ ] VertiportState 데이터 구조가 정의되었는가?
- [ ] ConflictEvent 데이터 구조가 정의되었는가?
- [ ] CapacityMetric 데이터 구조가 정의되었는가?
- [ ] EventLog 데이터 구조가 정의되었는가?
- [ ] 모든 timestamp의 시간대 기준이 통일되었는가?
- [ ] 운항 ID와 항공기 ID가 분리되어 있는가?
- [ ] 운항 계획과 실시간 위치가 flight_plan_id로 연결되는가?
- [ ] 버티포트 자원 상태가 시간에 따라 갱신되는가?
- [ ] 이벤트 로그가 저장되는가?

---

### 14.4 분석 모듈 체크리스트

KPI Aggregation:

- [ ] 현재 운항 수를 계산하는가?
- [ ] 계획 운항 수를 계산하는가?
- [ ] 위험 이벤트 수를 계산하는가?
- [ ] 평균 지연을 계산하는가?
- [ ] 최대 지연을 계산하는가?
- [ ] 수용량 경고 건수를 계산하는가?

Strategic Conflict Detection:

- [ ] 동일 웨이포인트 ETA 비교가 가능한가?
- [ ] 회랑 점유 충돌을 탐지하는가?
- [ ] 버티포트 접근 순서 충돌을 탐지하는가?
- [ ] ETA gap과 required gap을 비교하는가?
- [ ] Normal, Caution, Warning으로 등급화하는가?
- [ ] 충돌 이벤트를 생성하는가?

Flow and Capacity:

- [ ] 시간대별 수요를 집계하는가?
- [ ] 자원별 수용량을 모델링하는가?
- [ ] 회랑 밀도를 계산하는가?
- [ ] 버티포트 처리량을 계산하는가?
- [ ] FATO 점유율을 계산하는가?
- [ ] Gate 점유율을 계산하는가?
- [ ] 지연을 계산하는가?
- [ ] 지연 원인을 분류하는가?
- [ ] 병목 위치를 진단하는가?
- [ ] 지연 전파를 분석하는가?

Decision Support:

- [ ] 출발 지연 후보를 생성하는가?
- [ ] 속도 조정 후보를 생성하는가?
- [ ] 대체 경로 후보를 생성하는가?
- [ ] 도착 순서 조정 후보를 생성하는가?
- [ ] 대체 버티포트 후보를 생성하는가?
- [ ] 조치 전후 효과를 비교하는가?

---

### 14.5 검증 체크리스트

기능 검증:

- [ ] 더미 운항 계획을 정상적으로 불러오는가?
- [ ] UAM 위치가 시간에 따라 갱신되는가?
- [ ] 계획 경로와 실제 위치가 동시에 표시되는가?
- [ ] 동일 웨이포인트 충돌이 정상 탐지되는가?
- [ ] 충돌이 없을 경우 Normal로 표시되는가?
- [ ] 수용량 초과 시 Capacity Alert가 발생하는가?
- [ ] 버티포트 자원 포화 시 Warning이 발생하는가?
- [ ] 지연 발생 시 평균 지연 KPI가 갱신되는가?

시나리오 검증:

- [ ] 정상 운항 시나리오
- [ ] 웨이포인트 ETA 충돌 시나리오
- [ ] 회랑 밀도 초과 시나리오
- [ ] 버티포트 FATO 포화 시나리오
- [ ] Gate 부족 시나리오
- [ ] 특정 운항 지연 전파 시나리오
- [ ] 버티포트 폐쇄 시나리오
- [ ] 대체 경로 적용 시나리오

UI 검증:

- [ ] 화면 전환이 자연스러운가?
- [ ] 이벤트 클릭 시 관련 객체가 강조되는가?
- [ ] 지도 레이어가 과도하게 복잡하지 않은가?
- [ ] KPI와 이벤트 정보가 서로 일치하는가?
- [ ] 상태 색상이 일관적으로 적용되는가?
- [ ] 시연자가 설명하기 쉬운 화면 구조인가?

---

### 14.6 시연 체크리스트

- [ ] 시연용 데이터셋이 준비되었는가?
- [ ] 정상 운항 상태에서 시작되는가?
- [ ] 시간이 지나면서 충돌 이벤트가 발생하는가?
- [ ] Overview KPI가 변하는가?
- [ ] 이벤트 클릭 시 Traffic Map / Strategic Conflict로 이동하는가?
- [ ] 충돌 지점이 지도에서 강조되는가?
- [ ] Conflict Detail Panel에 분석 결과가 표시되는가?
- [ ] Suggested Action이 표시되는가?
- [ ] Flow and Capacity에서 수요 수용량 초과가 표시되는가?
- [ ] 병목 원인이 VP, FATO, Gate, Corridor 중 하나로 표시되는가?
- [ ] 조치 후보 적용 전후 비교가 가능한가?
- [ ] 시연 중 오류 발생 시 리셋 버튼 또는 초기화 기능이 있는가?

---

## 15. 시연 시나리오 예시

### 15.1 시나리오명

**도심 UAM 회랑 내 교통 집중 및 버티포트 수용량 초과 상황에서 PSU Monitoring SW의 충돌 및 혼잡 분석 시연**

---

### 15.2 시나리오 흐름

1. 정상 운항 상태에서 30대 UAM이 운항 중이다.
2. 특정 시간대에 VP-03 도착 수요가 증가한다.
3. Corridor C2의 회랑 밀도가 증가한다.
4. UAM-021과 UAM-034가 WP-07을 유사한 시간에 통과할 것으로 예측된다.
5. Overview에서 Conflict Alert와 Capacity Alert가 증가한다.
6. 운영자가 Conflict Alert를 클릭한다.
7. Traffic Map / Strategic Conflict 화면에서 WP-07 충돌 지점이 강조된다.
8. Conflict Detail Panel에서 ETA Gap, Required Gap, Severity가 표시된다.
9. Suggested Action으로 출발 지연, 속도 조정, 대체 경로가 제시된다.
10. 운영자가 Flow and Capacity 화면으로 이동한다.
11. VP-03 FATO 포화와 Gate 점유율 상승이 확인된다.
12. Delay Propagation Timeline에서 후속 지연이 표시된다.
13. Bottleneck Diagnosis Panel에서 병목 원인이 VP-03 FATO saturation으로 표시된다.
14. 완화 조치 후보 적용 전후의 지연 감소 효과를 비교한다.

---

## 16. 최종 산출물 체크리스트

### 16.1 문서 산출물

- [ ] 시스템 개념서
- [ ] GUI 설계서
- [ ] 모듈 설계서
- [ ] 데이터 모델 정의서
- [ ] API 명세서
- [ ] 시연 시나리오 문서
- [ ] 테스트 체크리스트
- [ ] 발표용 요약 자료

---

### 16.2 SW 산출물

- [ ] Overview 화면
- [ ] Traffic Map / Strategic Conflict 화면
- [ ] Flow and Capacity 화면
- [ ] 더미 데이터 생성기
- [ ] 충돌 탐지 엔진
- [ ] 수용량 분석 엔진
- [ ] 지연 분석 엔진
- [ ] 이벤트 관리 기능
- [ ] 시나리오 리플레이 기능
- [ ] 리포트 출력 기능

---

## 17. 발표용 요약 문구

### 17.1 시스템 설명

**PSU Monitoring SW는 UAM 운항 의도, 실시간 비행 상태, 회랑 및 버티포트 자원 정보를 통합하여 PSU의 교통관리 업무를 지원하는 연구용 운영 콘솔이다. 본 시스템은 Overview, Traffic Map / Strategic Conflict, Flow and Capacity의 3개 핵심 화면으로 구성되며, 전체 운항 상황 인지, 예측 충돌 분석, 교통 흐름 및 수용량 기반 병목 진단 기능을 제공한다.**

---

### 17.2 핵심 기능 문구

**본 시스템은 UAM 운항 현황을 통합 감시하고, 웨이포인트 및 회랑 기반의 시간 창 중복을 분석하여 전략적 충돌 위험을 사전에 탐지한다. 또한 버티포트 FATO, Gate, 회랑 수용량을 기반으로 수요 수용량 균형을 분석하고, 지연 및 병목 원인을 진단함으로써 PSU의 운영 의사결정을 지원한다.**

---

### 17.3 최종 한 줄

**PSU Monitoring SW는 UAM 운항 상황을 통합 인지하고, 예측 충돌과 교통 혼잡을 분석하여 PSU의 전략적 교통관리 의사결정을 지원하는 연구용 운영 콘솔이다.**

---

## 18. 문서 자체 점검 결과

본 파일은 다음 항목을 포함하도록 구성되었다.

- [x] Overview GUI 구성도
- [x] Traffic Map / Strategic Conflict GUI 구성도
- [x] Flow and Capacity GUI 구성도
- [x] 전체 시스템 아키텍처
- [x] 데이터 흐름 구성도
- [x] 화면 간 연동 구조
- [x] 내부 모듈 구조
- [x] 데이터 모델 JSON 예시
- [x] API 초안
- [x] 핵심 알고리즘 초안
- [x] 개발 기술 스택
- [x] 개발 폴더 구조
- [x] 개발 우선순위
- [x] GUI 체크리스트
- [x] 데이터 체크리스트
- [x] 분석 모듈 체크리스트
- [x] 검증 체크리스트
- [x] 시연 체크리스트
- [x] 발표용 요약 문구

---

## 19. 다음 확장 아이디어

추후 확장 가능 항목:

- 3D 공역 및 고도 레이어 시각화
- 실제 버티포트 운영 스케줄 반영
- 강화학습 또는 최적화 기반 출발 지연 조정
- 다중 PSU 간 정보 교환 모듈
- 기상 위험도 기반 경로 영향 분석
- 비상 운항 대응 모듈
- 리플레이 기반 사고 또는 지연 원인 분석
- 자동 보고서 생성 기능

---

## 20. 최종 개발 방향

본 SW는 초기에는 더미 데이터와 시뮬레이션 데이터를 기반으로 구현하고, 이후 실제 운항 의도, 실시간 위치, 버티포트 자원 상태, 기상 및 공역 제약 데이터를 단계적으로 연동하는 방향이 적합하다.

최종적으로 본 시스템은 UAM 교통관리 환경에서 PSU가 수행해야 하는 **운항 상황 인지, 전략적 충돌 예방, 수요 수용량 분석, 비정상 상황 대응, 운영 의사결정 지원** 기능을 연구개발 관점에서 검증할 수 있는 통합 플랫폼으로 확장될 수 있다.
