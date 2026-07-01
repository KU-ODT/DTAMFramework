# IntegrationHub

IntegrationHub contains the DTAM server-side modules.

```text
IntegrationHub/
  CoreServerModule/
    DSE_main.py
    app/
    data/
  StateServerModule/
    SS_main.py
    app/
    data/
```

## CoreServerModule

Control plane server. It provides ICD document APIs, module process lifecycle controls, and launches StateServerModule as the data plane.

Default port: `8095`.

## StateServerModule

Data plane server. It owns `/ws/dtam`, message forwarding, file DB logging, simulation time, and the live monitor UI.

Default port: `8096`.

## Run

```powershell
python IntegrationHub/CoreServerModule/DSE_main.py
```

Normally this is started through:

```powershell
python Start_DTAM.py
```

---

## 통합/개발 규칙 (Integration Hub)

> IntegrationHub 를 개발하거나, 다른 모듈을 허브에 붙이는 개발자를 위한 규칙.
> 모듈 폴더 구조 규칙은 [DTAMSDK/MODULE_AUTHORING.md](../DTAMSDK/MODULE_AUTHORING.md) 를 기준으로 하고,
> 이 문서는 허브(StateServer)를 경유하는 **메시지 라우팅·주입·관측 규칙**만 다룬다.

### 1. FORWARD_RULES 는 단일 권위 — 허브에 라우팅을 복제하지 않는다

- 메시지별 수신 대상 role 은 SDK 의 `dtam_client/policy.py` 의 `FORWARD_RULES` 하나뿐이다.
  허브(`CoreServerModule/app/model/message.py`)는 이걸 **import 해서 파생**할 뿐, 자체 라우팅 표를 만들지 않는다.
- 라우팅을 바꿀 일이 생기면 **SDK `policy.py` 만 수정**한다. 허브 코드에 특정 mid→role 을 하드코딩하지 않는다.
- role base stub / subscription 도 같은 표에서 파생되므로, `policy.py` 변경 후 `role_modules.py` 의
  drift 검증(import 시 AssertionError)이 통과하는지 확인한다.

### 2. 허브로 메시지를 보내는 두 경로

| 경로 | 용도 | sender(발신자 신원) |
| --- | --- | --- |
| **SDK WebSocket** `/ws/dtam` | 정상 경로. 모듈이 자기 role 로 송수신 | 모듈의 실제 role |
| **REST** `POST /api/msg/{mid}` | SDK 를 못 쓰는 모듈의 주입/발행, 운영자 명령, 테스트 | 아래 §3 규칙에 따름 |

- 기능 모듈은 가능하면 **SDK WebSocket** 을 쓴다 (`domain/` 이 아니라 `app/dtam/` 에서).
- REST `/api/msg/{mid}` 는 **SDK 미사용 모듈**(예: 현 PSU) 이나 운영자/테스트 주입을 위한 보조 경로다.
  raw TCP/UDP 를 새로 여는 대신 항상 이 REST 를 쓴다.

### 3. REST `/api/msg/{mid}` — body 는 `{role, payload}`, **role 을 함부로 못박지 않는다**

body: `{"role": "<선택>", "payload": { ...ICD wire... }}`
`payload` 는 허브가 SDK `parse_payload(mid, ...)` 로 정적 검증한다 (실패 시 422). 모든 push 는 DB 에도 기록된다.

- **`role` 비움(권장 기본)** → `FORWARD_RULES[mid]` 의 **모든 대상**에게 브로드캐스트. 발신자는
  `operator` 로 기록되어 기존 `user->server` 라우팅(예: 2002→monitoring)과 호환된다. 응답에 `targets` 를 돌려준다.
- **`role` 지정** → **그 role 한 곳에만** 단독 전달 (`push_to_role`) — **FORWARD_RULES fan-out 을 우회한다.**
  꼭 한 모듈에만 찔러야 하는 특수 상황이 아니면 쓰지 않는다.

> ⚠️ **실측 버그 (2026-06-11):** PSU 가 `3003` 을 `role="vehicle"` 로 못박아 dispatch 하는 바람에,
> `FORWARD_RULES["3003"] = [vehicle, mission]` 인데도 **Mission 이 3003 을 못 받았다** (plan 장부 추적 M-1 무력화).
> 다중 수신 메시지는 **role 을 비워 브로드캐스트**해야 한다. dispatch 코드에서 `target_role` 을 고정하지 말 것.

### 4. 수신 여부 검증 (관측 엔드포인트)

메시지가 실제로 전달됐는지는 소스를 안 고치고 아래로 확인한다.

| 확인 대상 | 엔드포인트 (허브 8096) |
| --- | --- |
| 모듈 연결 + role 별 rx/tx 카운터·hz | `GET /api/state` → `registry.modules[].messages[mid].{rx_count,tx_count,hz}` |
| 특정 mid 최신 payload | `GET /api/db/messages/{mid}/latest` (`field`+`value` 필터 가능) |
| DB 저장 폴더명 | `message.py` 의 `DB_FOLDER_FOR_MID` |

- "role 로 전달됐나" = 허브 registry 의 해당 role `tx_count` 증가로 본다.
- "핸들러까지 도달했나" = 수신 모듈 자체 카운터(예: Mission `/api/dtam/status` 의 `rx_per_mid`,
  Vehicle 상태의 `rx_3003_count`)로 본다.

### 5. 시뮬레이션 시계(0003) 규칙

- StateServer 의 시계는 `playState=play` 일 때만 전진한다. 부팅 직후·pause 상태의 정지는 정상이다.
- **0003 emit 루프는 어떤 예외에도 죽으면 안 된다.** 모듈 WS 단절 시점에 `push_to_role` 이 예외를 내면
  시계 스레드가 통째로 멈춰(무로그) 전 기체가 이륙 대기에 갇힌다 — tick/대상별 이중 `try` 로 보호한다
  (`StateServerModule/app/services/engine.py`).

### 6. CoreServer 프로세스 런처 규칙

- 모듈 자동 기동(`CoreServerModule/app/routes/process.py`)은 `CREATE_NO_WINDOW` 로 스폰하므로
  자식의 표준 핸들이 무효다. **stdout/stderr 를 `.dtam_runtime/logs/module_<role>.log` 로 리다이렉트**해야
  print/uvicorn 배너가 REST 층을 죽이지 않는다.
- 모듈 폴더에 **전용 venv(`<모듈>/.venv311`)** 가 있으면 런처가 그 인터프리터로 구동한다.
  VisualizationModule 의 AirSim 클라이언트(py3.11 고정 의존성)를 메인 venv(py3.13)와 격리하기 위한 규칙.

## 참고 문서

- [DTAMSDK/README.md](../DTAMSDK/README.md) — SDK 개요와 사용법
- [DTAMSDK/MODULE_AUTHORING.md](../DTAMSDK/MODULE_AUTHORING.md) — 모듈 폴더/책임 분리 규칙
- [DTAMSDK/dtam_client/NEW_MESSAGE_PROMPT.md](../DTAMSDK/dtam_client/NEW_MESSAGE_PROMPT.md) — 신규 ICD 추가 체크리스트

---

## 프로젝트 문서 지도 (어디에 무엇이 있나)

레포 안에 흩어진 문서를 목적별로 찾아가는 색인. (경로는 framework root 기준)

### 1. 아키텍처 — "DTAM 이 뭐고 어떻게 연결되나"

`docs/architecture/` — 독자별로 3장 분리 ([README](../docs/architecture/README.md) 에 추천 발표 순서)

| 문서 | 독자 |
| --- | --- |
| [00_intro_architecture.md](../docs/architecture/00_intro_architecture.md) | 연구책임자·외부 발표·신규 참여자 (개념 아키텍처) |
| [01_user_flow.md](../docs/architecture/01_user_flow.md) | 운영자·임무 설계자 (사용자 여정) |
| [02_technical_architecture.md](../docs/architecture/02_technical_architecture.md) | 개발자·통합 엔지니어 (서버/포트/ICD 흐름) |

### 2. 시나리오/데모 — "S1/S2/S3 는 어떻게 동작하나"

`docs/scenarios/` ([README](../docs/scenarios/README.md) 가 색인)

| 문서 | 내용 |
| --- | --- |
| [S1_nominal.md](../docs/scenarios/S1_nominal.md) | 정상 운항 (baseline) |
| [S2_psu_replan.md](../docs/scenarios/S2_psu_replan.md) | 실traffic + PSU 반자동 속도 조정 |
| [S3_uao_battery_alt_vertiport.md](../docs/scenarios/S3_uao_battery_alt_vertiport.md) | 배터리 비상 → PSU 3003 land |
| [MODULE_TASKS.md](../docs/scenarios/MODULE_TASKS.md) | **모듈 개발자용 잔여 작업 목록** (Vehicle V-1~V-5 / PSU P-* / Mission M-1 / Visual VZ-*) — 데모 구현의 단일 권위 |

### 3. ICD 메시지 명세 — "메시지 필드가 어떻게 생겼나"

- `DTAMSDK/dtam_client/icd/KOR/` · `.../ENG/` — mid 별 19개 문서 (한/영)
- 스키마 원본(dataclass): `DTAMSDK/dtam_client/schema/`
- 신규 추가 절차: [NEW_MESSAGE_PROMPT.md](../DTAMSDK/dtam_client/NEW_MESSAGE_PROMPT.md)

### 4. SDK/모듈 규칙

- [DTAMSDK/README.md](../DTAMSDK/README.md) · [MODULE_AUTHORING.md](../DTAMSDK/MODULE_AUTHORING.md) · `DTAMSDK/CHANGELOG.md`
- 이 문서(§통합/개발 규칙) — 허브 경유 라우팅·주입·관측 규칙

### 5. 모듈별 README (각 모듈 폴더)

`MissionModule/` · `VehicleModule/` · `OperationModule/` · `VisualizationModule/` ·
`ExtenstionModule/PSUModule/` · `ExtenstionModule/VPOModule/` · `PlugIn/SituationAwareness/` — 각 폴더의 `README.md`

### 6. 지리/좌표 참조 (vertiport·spawn)

`docs/` 아래 — [vertiport_KU_gate_fato_reference_map.md](../docs/vertiport_KU_gate_fato_reference_map.md),
`unreal_vertiport_spawn_points_calibrated.md`, `unreal_editor_s_points.md` 등 (png/svg 지도 동반)

### 7. 런타임에서만 보는 "라이브 문서" (스택 켠 뒤)

| 문서 | 위치 |
| --- | --- |
| **시퀀스 다이어그램** (Phase별 메시지 흐름, SVG) | 허브 8096 → `GET /docs/sequence` (데이터: `GET /api/sequence-diagram?lang=ko\|en`) |
| **라이브 메시지 모니터** (MESSAGE COUNTERS, rx/tx/hz) | 허브 8096 루트 GUI |
| **ICD 문서 API / Swagger** | CoreServer 8095, 허브 8096 `/docs` (FastAPI Swagger) |
| **DB 최신 payload** | `GET /api/db/messages/{mid}/latest` |

> **배포용 통합본**: `docs/scenarios/` 원본을 한 파일로 합친 리딩 뷰(`DTAM_시나리오_통합_*.md`)는
> 배포 산출물이라 git 에 넣지 않는다. 편집·검토는 항상 `docs/scenarios/` 원본을 기준으로 한다.
