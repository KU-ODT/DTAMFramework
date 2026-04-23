# UAM 혼잡 지표 파라미터/가중치 근거 및 사용처

이 문서는 `field_congestion_config.js`에 있는 파라미터와 가중치가 어디서 사용되는지, 어떤 운용/운항 개념과 맞닿아 있는지를 정리합니다. 또한 외부 레퍼런스로 바로 연결되는 값과 그렇지 않은 값을 구분해, 이후 보정(캘리브레이션) 계획을 세울 수 있게 했습니다.

## 1) 수식 ↔ 구현 매핑(기체 중심 혼잡 지표)
아래는 논문 수식(기체 중심 혼잡 지표)을 코드로 대응한 것입니다.

```text
rho_i(t) = sum_{j!=i} exp( -d_par^2/(2*sigma_par^2) - d_perp^2/(2*sigma_perp^2) )

epsilon_i(t) = max(0, 1 - v_i(t)/v_f)
D_i(t) = ∫_{t-T}^{t} epsilon_i(τ) dτ
I_i(t) = 1{ D_i(t) >= D_thr }

Z_i(t) = { j | 0 < d_par <= L and |d_perp| <= W }
R_i(t) = sum_{j in Z_i} I_j(t) / (|Z_i| + ε)
A_i(t) = max(epsilon_i(t), R_i(t))

rho_hat_i = min(rho_norm_cap, rho_i / rho_scale)
rho_scale = quantile(rho, q) with min floor

c_i(t) = rho_hat_i * A_i(t)
```

구현 위치 요약:
- 계산 핵심: `app/web/field_layers.worker.js` (`computeCongestionWeights`, `updateDelayState`)
- 입력 필터링(모드/고도/속도/버티포트 제외): `app/web/field_layers.worker.js`, `app/web/app.field_layers.js`
- 최종 시각화 스케일: `app/web/field_layers.worker.js`

## 2) 적용 우선순위(값이 덮어써지는 순서)
1. `app/web/field_layers.worker.js`의 `DEFAULT_CONGESTION_CONFIG`
2. `app/web/field_congestion_config.js` (있으면 1을 덮어씀)
3. 런타임 payload의 `config` (있으면 2를 덮어씀)

## 3) 파라미터 카탈로그
### 3-1. 논문 수식 직접 대응 파라미터
| 키 | 의미 | 사용 위치 | 근거/메모 |
|---|---|---|---|
| `freeflow_mps` | 자유흐름 속도 v_f | `field_layers.worker.js` (epsilon 계산) | 시뮬 규칙 기본값(100 kt ≈ 51.4 m/s) 기반. 외부 ConOps에서 직접 제시한 속도는 확인되지 않음. |
| `delay_window_s` | 지연 적분 구간 T | `updateDelayState` | 외부 기준 미확인. 운용 개입 체감/데이터 업데이트 주기를 반영한 초기값 성격. |
| `delay_threshold_s` | 지연 임계 D_thr | `computeCongestionWeights` | 외부 기준 미확인. 지연 상태 판단용 임계값. |
| `rho_sigma_parallel_m` | 전방(기체 진행방향) 커널 폭 σ∥ | `computeCongestionWeights`, `computeField` | 논문에는 σ 수치가 명시되지 않음. 시뮬레이터 항로 스케일에 맞춰 보정 필요. |
| `rho_sigma_perp_m` | 횡방향 커널 폭 σ⊥ | `computeCongestionWeights`, `computeField` | 논문에는 σ 수치가 명시되지 않음. 회랑 폭/노선 밀도에 맞춰 보정 필요. |
| `rho_cutoff_sigma` | 커널 컷오프 배수 | `computeCongestionWeights`, `computeField` | 알고리즘 최적화용(박스 컷오프). 컷오프가 사각형 형태를 만든 원인. |
| `front_box_longitudinal_m` | 전방 탐색 길이 L | `computeCongestionWeights` | 논문 식(전방 지연 탐색) 대응. 구체 수치 근거는 외부에서 확인되지 않음. |
| `front_box_lateral_m` | 전방 탐색 폭 W | `computeCongestionWeights` | 위와 동일. |
| `neighbor_epsilon` | 분모 안정화 ε | `computeCongestionWeights` | 수치 안정화용. 외부 기준 없음. |
| `rho_norm_quantile` | ρ 정규화 기준 분위수 q | `resolveScaleFromQuantile` | 시각화/정규화용. 외부 기준 없음. |
| `rho_norm_min` | ρ 정규화 최소 스케일 | `resolveScaleFromQuantile` | 시각화/정규화용. |
| `rho_norm_cap` | ρ̂ 상한 | `computeCongestionWeights` | 과증폭 방지용. |

### 3-2. 필터/운용 조건 파라미터
| 키 | 의미 | 사용 위치 | 근거/메모 |
|---|---|---|---|
| `exclude_vertiport_radius_m` | 버티포트 인근 제외 반경 | `app.field_layers.js`, `field_layers.worker.js` | 회랑 기반 혼잡 측정에서 포트 주변을 제외하려는 운영적 필터. 외부 수치 근거 없음. |
| `min_speed_mps` | 혼잡 계산 최소 속도 | `app.field_layers.js`, `field_layers.worker.js` | 지상 정체/정지체 제거용. 외부 수치 근거 없음. |
| `min_altitude_ratio` / `min_altitude_m` | 혼잡 계산 최소 고도 | `app.field_layers.js`, `field_layers.worker.js` | 기준 고도는 `FLIGHT_ALT_M`(1000 ft ≈ 304.8m). K-UAM ConOps 보도자료에 따르면 도심 저고도 공역 300~600m 운항을 전제로 함. 따라서 기본 설정이 그 범위와 정합. |

### 3-3. 알고리즘/성능 파라미터
| 키 | 의미 | 사용 위치 | 근거/메모 |
|---|---|---|---|
| `delay_max_dt_s` | 지연 적분 최대 dt | `updateDelayState` | 업데이트 주기 안정화 목적. |
| `delay_merge_eps` | ε 변화 미미 구간 병합 | `updateDelayState` | 메모리/성능 최적화용. |
| `neighbor_cell_m` | 공간 인덱스 셀 크기 | `buildSpatialIndex` | 탐색 최적화용. σ와 비슷한 스케일 권장. |
| `stale_state_s` | 지연 상태 보관 최대 시간 | `pruneDelayStates` | 오래된 개체 상태 제거. |

### 3-4. 시각화 파라미터
| 키 | 의미 | 사용 위치 | 근거/메모 |
|---|---|---|---|
| `field_scale_congestion` | 혼잡장 컬러 스케일 계수 | `computeField` | 시각화 가시성 조절용. 외부 기준 없음. |

### 3-5. UI 가중치(혼잡 heatmap fallback)
`app/web/app.field_layers.js`의 `resolveCongestionWeight()`는 `delay_s`, `tti` 기반 가중치를 만들어 GeoJSON 속성 `congestion_weight`로 저장합니다. 이 값은 MapLibre의 heatmap 레이어가 쓰는 값이며, 현재 캔버스 기반 혼잡장 계산(`field_layers.worker.js`)에는 직접 쓰이지 않습니다. 즉, **실제 혼잡장**은 `computeCongestionWeights()`의 결과가 사용됩니다.

## 4) 운용/운항 개념(ConOps) 및 로드맵 맥락
### 4-1. K-UAM 단계(로드맵 요약)
항공정보포털의 K-UAM 페이지는 준비기(2020~2024), 초기(2025~2029), 성장기(2030~2035), 성숙기(2035~)를 제시하며, 회랑 운영 방식이 고정형 → 고정형 회랑망 → 동적 회랑망으로 발전한다고 설명합니다. 이는 혼잡 커널의 전방/측방 범위를 단계별로 다르게 둘 수 있음을 시사합니다.

### 4-2. K-UAM ConOps 1.0 요약(보도자료 기반)
스마트시티 종합포털 보도자료에 따르면, UAM 회랑은 버티포트를 잇는 통로 형태로 개설되며, 도심 저고도 공역 300~600m에서 운항합니다. 회랑은 고정형→고정형 회랑망→동적 회랑망으로 진화하고, 교통관리는 UATM(새 교통관리체계)을 통해 수행됩니다. 또한 PSU(Provider of Service for UAM)가 운항안전정보 공유, 교통흐름 관리, 비행계획 승인 등의 역할을 수행한다고 명시됩니다.

이 내용은 **혼잡 계산을 어떤 공역(고도)과 운항 단계에서 적용할지**를 결정하는 근거로 쓰이고, 커널 폭(σ), 전방 탐색 범위(L/W), 버티포트 제외 반경 등의 **운용 맥락**을 정하는 데 참고할 수 있습니다.

### 4-3. NASA UML(밀도 정의)
NASA UML 스케일은 UAM 교통 밀도를 “동시에 공중에 있는 항공기 수”로 정의하며, 저밀도는 100대 미만, 중밀도는 수백대, 고밀도는 수천대, 유비쿼터스는 수만대를 의미한다고 설명합니다. 이는 우리 시뮬레이션의 혼잡 커널 범위/정규화 파라미터를 조정할 때 **밀도 레벨을 정의하는 기준**으로 사용할 수 있습니다.

### 4-4. 유사 연구 사례(혼잡/밀도 지표)
- AIAA SciTech 2022: UAM 공역의 동적 밀도(Dynamic Density) 지표를 다루는 연구(Spirkovska et al., 2022).
- IEEE Access 2022: UTM 적용을 위한 교통 흐름 패턴과 공역 밀도 식별(Alharbi & Petrunin, 2022).

## 5) 밀도 환경에 따른 파라미터 튜닝 가이드(권장 프로세스)
아래는 외부 수치 근거가 없는 파라미터를 **밀도 레벨에 맞춰 보정**하는 실무 가이드입니다.

1. 시뮬레이션 내 “동시 항공기 수”를 계산해 NASA UML의 저/중/고 밀도 범주 중 어디에 해당하는지 분류합니다.
2. 목표 회랑 구조를 결정합니다. 초기 고정형 회랑이면 `rho_sigma_perp_m`을 상대적으로 작게, 성장/성숙 단계의 회랑망이면 `rho_sigma_perp_m`을 확대하는 것이 자연스럽습니다.
3. 전방 탐색(`front_box_longitudinal_m`)은 “지연 전파”의 시간 창을 반영하도록 설정합니다. 예: 평균 순항속도 v에서 L ≈ v * (전파로 보고 싶은 시간)
4. `rho_norm_quantile`는 시나리오별 outlier 존재 여부에 따라 0.8~0.95 범위에서 조정합니다.
5. 시각화 스케일(`field_scale_congestion`)은 “실제 혼잡이 있음에도 안 보이는지”를 기준으로 조정합니다.

이 과정은 **논문 수식은 유지하면서 운용 환경만 반영**하는 방향입니다.

## 6) 용어/약어 정리
- UAM: Urban Air Mobility(도심항공교통)
- K-UAM: Korean UAM(한국형 도심항공교통)
- ConOps: Concept of Operations(운용개념)
- UML: UAM Maturity Level
- UATM: UAM Traffic Management(도심항공교통 관리체계)
- PSU: Provider of Service for UAM(UAM 교통관리 서비스 제공자)
- eVTOL: Electric Vertical Takeoff and Landing
- UAS: Unmanned/Uncrewed Aircraft System
- UTM: UAS Traffic Management
- USS: UTM Service Supplier
- C2 Link: Command and Control Link

## 7) 참고 문헌/출처
- K-UAM 단계 및 회랑 운영 방식: https://www.airportal.go.kr/knowledge/knowledge_all.html?month=0&year=0&searchText=k-uam&searchType=0&tabName=all?menuNo=2019030901
- K-UAM ConOps 1.0 보도자료(회랑/고도/교통관리): https://smartcity.go.kr/2021/09/28/%ed%95%9c%ea%b5%ad%ed%98%95-%eb%8f%84%ec%8b%ac%ed%95%ad%ea%b3%b5%ea%b5%90%ed%86%b5-k-uam-%ec%9a%b4%ec%9a%a9%ea%b0%9c%eb%85%90%ec%84%9c1-0-%eb%b0%9c%ea%b0%84/
- NASA UML 스케일(밀도 정의, 약어): https://ntrs.nasa.gov/api/citations/20205009006/downloads/UML%20paper%20SciTech%202021.pdf
- NASA UAM ConOps(UML-4): https://www.nasa.gov/ames-uram/advance-air-mobility-national-campaign/
- FAA UTM ConOps v2.0: https://www.faa.gov/air_traffic/technology/utm
- 관련 연구(동적 밀도): https://doi.org/10.2514/6.2022-3403
- 관련 연구(UTM 공역 밀도): https://ieeexplore.ieee.org/document/9946858
- 혼잡 지표 수식: `기체 중심 혼잡도 지표 기반 UAM 공역 혼잡 분석 및 비교 연구.pdf` (프로젝트 내부 문서)
