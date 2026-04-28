# DTAM 모듈 작성 가이드

> 새로운 DTAM 모듈을 처음부터 끝까지 만드는 절차를 담은 문서입니다.
> SDK API 레퍼런스는 [README_KOR.md](README_KOR.md), 새 ICD 메시지를 추가하는
> 절차는 [dtam_client/NEW_MESSAGE_PROMPT.md](dtam_client/NEW_MESSAGE_PROMPT.md)
> 를 참고하세요. 이 문서는 그 둘을 잇는 "모듈 한 채를 새로 만드는 법"입니다.

## 0. 사전 지식

- 모든 모듈은 **WebSocket 클라이언트**로서
  `DTAM_SimulationState` 서버(`ws://<host>:8096/ws/dtam`)에 접속한다.
  서버가 forwarding 허브이고, 모듈끼리 직접 연결되지 않는다.
- 모듈은 자기 `Role` 을 정해야 한다 (`mission` / `monitoring` /
  `vehicle` / `visual` / `sim_state` 중 하나). SDK의 `KNOWN_MODULES` 가
  단일 권위.
- 모든 ICD 메시지는 dataclass 인스턴스로 송수신된다. dict를 보낼 일이
  생기면 그건 잘못된 신호이다 — `set_strict_dataclass(True)` 를 켜고 가자.

## 1. 표준 폴더 구조

5개 모듈이 공통으로 따르는 layout. 새 모듈도 이 형태를 그대로 복제하면 된다.

```
MyModule/
├── MM_main.py                 # CLI/run entrypoint (uvicorn 부팅)
├── README.md
├── app/
│   ├── __init__.py
│   ├── config.py              # 경로·포트·기본값 (ENV 변수로 override)
│   ├── server.py              # FastAPI app factory + lifespan
│   ├── comm.py                # DtamModule 서브클래스 (=DTAM 통신 layer)
│   ├── routes/                # FastAPI APIRouter 들 (ws/REST)
│   │   ├── __init__.py
│   │   └── ...
│   ├── services/              # 도메인-독립 서비스 (DB, mbtiles, ...)
│   └── domain/                # 도메인 로직 (계산·변환·시뮬레이션)
├── web/                       # 프런트엔드 (templates + static 통합)
│   ├── index.html
│   ├── css/
│   ├── js/
│   └── vendor/
├── data/                      # 모듈 입력/출력 데이터
└── resources/                 # 큰 바이너리 (mbtiles, dem, png 등)
```

핵심 원칙:

1. **`backend/` · `frontend/` 분리 금지.** 5개 모듈을 한 줄로 정렬하기 위해
   `app/` (Python) + `web/` (자산) + `resources/` (바이너리) 로 통일했다.
2. **`comm.py`** 는 항상 `app/` 바로 아래에 둔다. DTAM 통신 layer 가
   어디 있는지를 다른 모듈과 동일하게 찾을 수 있어야 한다.
3. **`MM_main.py`** 의 prefix는 모듈 약칭. (MP, AM, OC, SS, DSE 패턴)

## 2. Step-by-step

### 2.1 폴더 만들기

```
MyModule/
  MM_main.py
  app/__init__.py
  app/config.py
  app/server.py
  app/comm.py
  app/routes/__init__.py
  web/index.html
  data/
  resources/
```

### 2.2 `Role` 등록

`DTAM_SDK/dtam_client/identity.py` 의 `Role` enum 과 `KNOWN_MODULES` 에
새 역할/source를 추가한다. 기존 5개 역할로 충분하면 그대로 사용.

```python
# identity.py 발췌
class Role(str, Enum):
    ...
    MY_NEW_ROLE = "my_new_role"

KNOWN_MODULES[Role.MY_NEW_ROLE] = ModuleIdentity(
    Role.MY_NEW_ROLE, "MyModule", "My Module"
)
```

`source` 문자열(`"MyModule"`)은 0002 `Module Status` 의 `source` 필드에
실어 보내는 값이다. 서버는 이걸 보고 어느 role 인지 판별한다.

### 2.3 Forwarding 규칙 등록

`DTAM_SDK/dtam_client/policy.py` 의 `FORWARD_RULES` 에 "내 모듈이 어떤
mid를 받아야 하고 / 보내야 하는지" 를 적는다.

```python
FORWARD_RULES["3001"] = {
    "from": Role.MISSION,
    "to":   [Role.VEHICLE, Role.SIM_STATE, Role.MY_NEW_ROLE],  # 내 새 role을 추가
}
```

`subscriptions_for(Role.MY_NEW_ROLE)` 가 알아서 mid 목록을 뽑아 SDK 가
auto-subscribe 해준다.

### 2.4 `app/config.py`

ENV 변수로 override 가능한 형태로 기본값을 둔다. 다른 모듈의 config.py
를 그대로 복제 후 prefix만 바꾸면 된다.

```python
from __future__ import annotations
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
FRAMEWORK_ROOT = ROOT_DIR.parent

RESOURCES_DIR = Path(os.getenv("DTAM_MM_RESOURCES", ROOT_DIR / "resources"))
DATA_DIR      = Path(os.getenv("DTAM_MM_DATA",      ROOT_DIR / "data"))
WEB_DIR       = ROOT_DIR / "web"

SERVER_HOST = os.getenv("DTAM_MM_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("DTAM_MM_PORT", "8200"))   # 모듈마다 고유 포트

# DTAM 통신 (WebSocket)
DTAM_TARGET_IP = os.getenv("DTAM_MM_TARGET_IP", "127.0.0.1")
DTAM_WS_PORT   = int(os.getenv("DTAM_MM_WS_PORT", "8096"))

APP_TITLE = "My Module"
```

### 2.5 `app/comm.py` — DTAM 통신 layer

`DtamModule` 을 서브클래싱하고 받을 메시지에 `@on_receive("MID")` 데코레이터.

```python
from __future__ import annotations
import logging
from dtam_client import DtamModule, Role, on_receive
from dtam_client.schema import (
    Msg3001_ScheduledFlight,
    Msg0003_CommonTimeInfo,
)

logger = logging.getLogger(__name__)


class MyModuleComm(DtamModule):
    role = Role.MY_NEW_ROLE          # 또는 기존 Role 중 하나

    def __init__(self, server_url: str):
        super().__init__(
            server_url=server_url,
            heartbeat=True,           # 0002 Module Status 1Hz 자동
        )

    @on_receive("3001")
    def on_scheduled_flight(self, plan: Msg3001_ScheduledFlight) -> None:
        logger.info("got plan %s", plan.aircraftId)
        # ... 도메인 로직 ...

    @on_receive("0003")
    def on_clock(self, clock: Msg0003_CommonTimeInfo) -> None:
        # ... 시간 동기화 ...
        ...
```

내부 도메인 로직(`app/services/...`, `app/domain/...`)을 직접 import하지
말고, 통신 layer는 *얇게* 유지하자. 데이터를 받은 뒤 도메인 객체로
forwarding 하는 정도면 충분하다.

### 2.6 `app/server.py` — FastAPI factory

```python
from __future__ import annotations
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import WEB_DIR, DTAM_TARGET_IP, DTAM_WS_PORT, APP_TITLE
from .comm import MyModuleComm

# 모듈 전역 싱글턴
comm: Optional[MyModuleComm] = None


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        global comm
        url = f"ws://{DTAM_TARGET_IP}:{DTAM_WS_PORT}/ws/dtam"
        comm = MyModuleComm(server_url=url)
        yield
        if comm is not None:
            comm.close()

    app = FastAPI(title=APP_TITLE, lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    # routes 등록
    from .routes import index, status   # 예시
    app.include_router(index.router)
    app.include_router(status.router)
    return app
```

### 2.7 `MM_main.py` — uvicorn 진입점

```python
from __future__ import annotations
import argparse, logging, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRAMEWORK_ROOT = ROOT.parent
DTAM_SDK_ROOT  = FRAMEWORK_ROOT / "DTAM_SDK"
for extra in (str(FRAMEWORK_ROOT), str(DTAM_SDK_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from dtam_client.ports import find_available_tcp_port  # noqa: E402
from MyModule.app.server import create_app             # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="My DTAM Module")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8200)
    parser.add_argument("--target-ip", default="127.0.0.1",
                        help="DTAM SimulationState 서버 IP")
    parser.add_argument("--ws-port", type=int, default=8096,
                        help="DTAM SimulationState WebSocket 포트")
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args()

    os.environ["DTAM_MM_TARGET_IP"] = args.target_ip
    os.environ["DTAM_MM_WS_PORT"]   = str(args.ws_port)

    args.port = find_available_tcp_port(args.host, args.port)

    logging.basicConfig(level=getattr(logging, args.log_level.upper()))
    import uvicorn
    uvicorn.run(create_app(), host=args.host, port=args.port,
                log_level=args.log_level.lower())


if __name__ == "__main__":
    main()
```

### 2.8 routes / web / data / resources

- `routes/` 는 FastAPI APIRouter 단위로 잘게 쪼갠다 (e.g. `index.py`,
  `status.py`, `dtam.py`, `tiles.py`).
- `web/index.html` 에서 SDK 가 발행하는 mid를 받아 표시할 거면
  `/static/...` 으로 마운트해 사용한다.
- `data/` 는 기본 입력 / 산출물. `resources/` 는 큰 바이너리 (mbtiles,
  png, dem 등) — `.gitignore` 으로 untrack 한다.

## 3. 메시지를 보낼 때

```python
from dtam_client.schema import Msg4001_VehicleStatus

self.send(Msg4001_VehicleStatus(
    timestamp="2026-04-28T00:00:00.000Z",
    vehicles={"UAM0001": {...}},
))
```

- `send(message)` 는 dataclass 우선이다. SDK가 `mid`를 알아서 찾고,
  4001처럼 wire 모양이 다른 메시지는 `to_wire()` 어댑터로 직렬화한다.
- 검증 실패 / 연결 끊김 / register 미완료 시 `False` 가 반환된다 —
  caller 에서 처리 또는 stats에서 모니터링.
- dict로 보내고 싶으면 `send_legacy(mid, dict)` (DeprecationWarning).
  strict 모드(`set_strict_dataclass(True)`)에서는 `TypeError`.

## 4. 서버에 새 메시지를 흘려보내야 할 때

→ [dtam_client/NEW_MESSAGE_PROMPT.md](dtam_client/NEW_MESSAGE_PROMPT.md) 의
5단계를 따른다 (catalog 등록, dataclass 추가, policy 갱신, ICD markdown,
sample 추가).

## 5. 흔한 실수 / 체크리스트

- [ ] **`role` 을 안 정함** → `DtamModule` 서브클래스에 `role = Role.X`
      를 반드시 클래스 변수로 둔다. 안 두면 register 할 때 서버가 거부.
- [ ] **`server_url` 에 `/ws/dtam` 누락** → 정확히
      `ws://<host>:<port>/ws/dtam` 이어야 한다.
- [ ] **`heartbeat=False` 로 두고 받기만 함** → 서버는 일정 시간
      heartbeat 가 안 오면 모듈을 disconnected 로 마킹한다.
      `heartbeat=True` 가 기본값.
- [ ] **`@on_receive` 인자에 alias 사용** → mid (`"3001"`) 를 쓴다.
      alias (`"scheduled_flight"`) 는 명시적 `module.on(...)` 콜에서만 쓴다.
- [ ] **dict로 보내려고 함** → dataclass 만들기 귀찮아도 그냥 만든다.
      strict 모드 켜두면 잊어버릴 일도 없다.
- [ ] **legacy UDP/TCP 흔적 (`udp_port`, `target_port`, `my_port`)** →
      현재 시스템에 더 이상 없다. 새 모듈에서 도입하지 말 것.
- [ ] **`comm.py` 에 도메인 로직 섞기** → 통신 layer 는 얇게. 도메인은
      `services/` / `domain/` 으로.

## 6. 통합 테스트 체크포인트

새 모듈이 잘 붙었는지 확인하는 순서:

1. SimulationState 서버를 띄운다 (`python DTAM_SimulationState/SS_main.py`)
2. 새 모듈을 띄운다 (`python MyModule/MM_main.py`)
3. 라이브 모니터(`http://127.0.0.1:8096/`)에서 내 role이 connected 로
   잡히는지 확인 (heartbeat 1Hz 들어오면 됨)
4. 내가 받기로 한 mid를 다른 모듈에서 보내고 콘솔/UI에 도달했는지 확인
5. 내가 보낸 mid가 SimulationState 의 DB(`DB/<session>/`) 에 기록됐는지
   확인 (자동 forwarding 결과)

## 7. 참고 모듈

다섯 모듈이 모두 같은 layout 을 따른다 — 가장 가까운 형태를 골라서
복제하면 된다.

| 모듈                       | 추천 사유                                         |
|----------------------------|---------------------------------------------------|
| `DTAMAirMobility`          | 송신 위주(4001 10Hz), 도메인 시뮬레이터 포함       |
| `DTAM_MissionPlanner`      | 송수신 양방향, 라우트가 풍부, 지도 UI 포함          |
| `DTAMOperationsConsole`    | 모니터링 위주, 라우트 기반 + 풍부한 web/js 구조     |
| `DTAM_SimulationState`     | 서버측이라 약간 다름 — 모듈 reference 로는 비추천    |
| `DTAM_CoreServer`          | Control plane(REST 위주) — 일반 모듈과 형태 다름    |

가장 일반적인 모듈을 만들 거면 `DTAMAirMobility` 또는
`DTAM_MissionPlanner` 를 베끼는 것을 권장한다.
