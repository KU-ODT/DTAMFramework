# DTAM SDK 사용 가이드 (한국어)

버전: `0.0.1`

DTAM SDK는 모든 DTAM 모듈이 SimulationState 서버와 ICD 메시지를 주고받기 위해
쓰는 Python 클라이언트입니다. 통신은 단일 WebSocket 채널(`/ws/dtam`, 포트
8096) 만 사용합니다. 메시지 카탈로그·ICD dataclass·역할(Role) 정의 같은
공통 메타도 SDK가 권위 있는 단일 출처입니다.

## 1. 아키텍처

- **Control plane** — `DTAM_CoreServer` (포트 8095). REST·GUI·프로세스
  supervisor만 담당.
- **Data plane** — `DTAM_SimulationState` (포트 8096). HTTP + WebSocket
  (`/ws/dtam`), DB 기록, 라이브 모니터.
- **모듈** (Mission Planner / Air Mobility / Operations Console /
  Visualization) — 각 모듈은 data plane에 *접속하는 WebSocket 클라이언트*.
  모듈 간 직접 통신은 없고, 서버가 `FORWARD_RULES` 와 client role 에 따라
  forwarding 합니다.

## 2. 권장 패턴 — `DtamModule` 서브클래스

```python
from dtam_client import DtamModule, Role, on_receive
from dtam_client.schema import (
    Msg3001_ScheduledFlight,
    Msg4001_VehicleStatus,
    Msg0003_CommonTimeInfo,
)

class VehicleService(DtamModule):
    role = Role.VEHICLE

    def __init__(self):
        super().__init__(
            server_url="ws://127.0.0.1:8096/ws/dtam",
            heartbeat=True,            # 0002 1Hz 자동 송신
        )
        self._plans: dict[str, Msg3001_ScheduledFlight] = {}

    @on_receive("3001")
    def on_plan(self, plan: Msg3001_ScheduledFlight) -> None:
        self._plans[plan.aircraftId] = plan

    @on_receive("0003")
    def on_clock(self, clock: Msg0003_CommonTimeInfo) -> None:
        ...

    def publish_status(self, vehicles: dict) -> bool:
        return self.send(Msg4001_VehicleStatus(
            timestamp="2026-04-28T00:00:00.000Z",
            vehicles=vehicles,
        ))
```

`@on_receive("MID")` 가 붙은 메서드는 인스턴스 생성 시 자동으로 등록됩니다.
인자는 ICD 메시지 ID(`"3001"` 등)이고, callback은 dict가 아니라 파싱된
dataclass 인스턴스를 받습니다.

## 3. 단발 패턴 — `DtamModule.start(...)` + `.on(alias, cb)`

스크립트·테스트 같이 서브클래스가 과한 경우에 사용합니다:

```python
from dtam_client import DtamModule, Role

mod = DtamModule.start(
    role=Role.MISSION,
    server_url="ws://127.0.0.1:8096/ws/dtam",
    heartbeat=True,
)
mod.on("scheduled_flight", lambda plan: print(plan.aircraftId))
mod.on("3001",             lambda plan: print(plan))   # mid도 그대로 받음
```

alias 는 카탈로그의 `alias` 필드(`scheduled_flight` ↔ `3001`)를 따릅니다.

## 4. 송신 — dataclass 우선

```python
from dtam_client.schema import Msg2002_DtamExecute

mod.send(Msg2002_DtamExecute(timestamp="...", flightPlanFolderName="abc"))
```

SDK가 알맞은 `mid`를 찾고, 4001처럼 wire 포맷이 다른 메시지는 dataclass의
`to_wire()` 어댑터를 통해 ICD 모양으로 직렬화한 뒤 보냅니다.
`set_strict_dataclass(True)` 를 켜면 `mod.send_legacy(mid, dict)` 경로가
`TypeError` 로 막히고, 끄면 `DeprecationWarning` 으로 흘려보냅니다. 신규
코드에는 strict 활성화를 권장합니다.

## 5. 정체성과 역할

모든 모듈은 `Role` 로 자기를 식별하고, SDK 가 단일 권위입니다:

```python
from dtam_client import Role, identity_of, role_of

identity_of(Role.VEHICLE).source   # "DTAMAirMobility"
role_of("DTAM_MissionPlanner")     # Role.MISSION
```

서버는 heartbeat(`0002 Module Status`)의 `source` 필드를 `KNOWN_MODULES`
와 매칭해 어떤 role이 살아 있는지 추적합니다.

## 6. Subscription

`FORWARD_RULES` 가 "어느 역할이 어느 메시지를 받는가"를 선언합니다.
`subscriptions_for(role)` 는 해당 role이 listen 해야 하는 mid 목록을
반환하고, `start()` / 서브클래스 생성 시 SDK가 자동으로 구독을 걸어줍니다.

## 7. REST 헬퍼

서버 snapshot·module list 같이 단발성 호출은 WebSocket 없이 `DtamRest` 로
가능합니다:

```python
from dtam_client import DtamRest

rest = DtamRest("http://127.0.0.1:8096")
rest.snapshot()        # GET /api/state
rest.modules()         # GET /api/modules
```

## 8. 상태/라이프사이클

```python
mod.connected       # WebSocket 연결 여부
mod.registered      # register 핸드셰이크 응답 받은 상태인지
mod.subscriptions   # 이 모듈이 받게 되는 mid 목록
mod.stats.to_dict() # rx/tx 통계
mod.close()
```

`DtamModule` 은 자체 백그라운드 스레드에서 소켓을 굴리므로 메인 루프에서
`send()` / `close()` 를 호출해도 안전합니다.

## 9. 새 모듈 작성

새 DTAM 모듈을 처음부터 만들고 싶다면 [MODULE_AUTHORING.md](MODULE_AUTHORING.md)
를 참고하세요. 표준 폴더 구조, `comm.py` 패턴, FastAPI factory, CLI 진입점,
흔한 실수까지 단계별로 정리돼 있습니다.

## 10. ICD 문서

메시지별 명세는 SDK 안에 같이 들어있습니다:

- 한국어: `dtam_client/icd/KOR/`
- 영어:   `dtam_client/icd/ENG/`

새 ICD 메시지를 추가할 때는 [dtam_client/NEW_MESSAGE_PROMPT.md](dtam_client/NEW_MESSAGE_PROMPT.md)
를 따르세요 — `catalog.py` 등록, `dtam_client/schema/` 에 dataclass 추가,
`policy.py` 의 forward 규칙 갱신, `KOR/` · `ENG/` 양쪽에 markdown 추가.
