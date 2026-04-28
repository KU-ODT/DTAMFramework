# DTAM 모듈 작성 가이드

> 새로운 DTAM 모듈을 처음부터 끝까지 만드는 절차. SDK API 레퍼런스는
> [README_KOR.md](README_KOR.md), 새 ICD 메시지를 추가하는 절차는
> [dtam_client/NEW_MESSAGE_PROMPT.md](dtam_client/NEW_MESSAGE_PROMPT.md) 참고.

## 0. 사전 지식

- 모든 모듈은 **WebSocket 클라이언트**로서 `DTAM_SimulationState` 서버
  (`ws://<host>:8096/ws/dtam`) 에 접속한다. 서버가 forwarding 허브이고
  모듈끼리는 직접 연결되지 않는다.
- 모듈은 자기 `Role` 을 정한다 (`mission` / `monitoring` / `vehicle` /
  `visual` / `sim_state` 중 하나). SDK 의 `KNOWN_MODULES` 가 단일 권위.
- 모든 ICD 메시지는 dataclass 인스턴스로 송수신.
- **통신 코드는 SDK 가 다 처리한다** — 모듈 작성자는 "역할별 베이스 클래스"
  를 상속해 처리할 핸들러만 override 하면 된다.

## 1. 표준 패턴 — `class XxxService(XxxModule)`

3개 client 모듈 (Mission Planner / Air Mobility / Operations Console) 모두
완전 동일한 패턴을 따른다.

```python
# DTAM_MyModule/app/services/my_service.py

from dtam_client import VehicleModule         # 자기 역할의 베이스
from dtam_client.schema import Msg4001_VehicleStatus

class MyVehicleService(VehicleModule):
    """역할별 베이스(VehicleModule) 가 6개 mid 의 빈 @on_receive stub 을
    이미 갖고 있다. 이 클래스는 처리할 mid 만 override + 도메인 메서드만 추가."""

    def __init__(self, *, target_ip="127.0.0.1", ws_port=8096, **domain_deps):
        # 도메인 상태 초기화
        self._sessions = {}
        # ...
        super().__init__(server_url=f"ws://{target_ip}:{ws_port}/ws/dtam",
                         heartbeat=True)

    # ─── base stub override (내가 처리할 것만) ─────────────────
    def on_scheduled_flight(self, plan):
        """3001 받음 — base 의 빈 stub 을 override."""
        self._sessions[plan.aircraftId] = plan

    # 1002 SimulationSetup 처리 안 하면 그냥 override 안 하면 됨
    # (base 의 빈 stub 이 silent drop)

    # ─── 도메인 메서드 자유 추가 ──────────────────────────────
    def publish_4001(self, payload):
        return self.send(Msg4001_VehicleStatus(**payload))   # self.send 로 송신
```

**한 클래스에 모든 게 들어간다:**
- 통신 (부모 `DtamModule` 상속)
- 핸들러 (`on_*` override)
- 도메인 메서드 (자유)
- 송신 (`self.send(...)`)
- 통계 (`self.stats`)

`comm.py` 같은 별도 파일 / `Comm` wrapper 클래스 / callback wiring **모두 필요 없음**.

### 역할별 베이스 (SDK 가 제공)

| 역할 | Base | 받는 mid (override 가능) |
|---|---|---|
| `mission` | `MissionModule` | 2001, 2002 |
| `vehicle` | `VehicleModule` | 0003, 1002, 2002, 3001, 3002, 3003 |
| `monitoring` | `MonitoringModule` | 0001, 0002, 2002, 4001, 4101 |
| `visual` | `VisualModule` | 0003, 1002, 2002, 4001 |

각 베이스의 메서드 이름은 `on_<alias>` (예: `on_scheduled_flight`, `on_dtam_execute`).
Override 안 하면 silent drop. import 시점에 `subscriptions_for(role)` 와의
일치 자동 검증 (drift 발생 시 `AssertionError`).

## 2. 표준 폴더 구조

```
DTAM_MyModule/
├── MM_main.py                              # CLI/run entrypoint (uvicorn)
├── README.md
├── app/
│   ├── __init__.py
│   ├── config.py                           # 경로·포트·기본값 (ENV override)
│   ├── server.py                           # FastAPI factory + lifespan
│   ├── routes/                             # APIRouter 들 (REST)
│   │   ├── __init__.py
│   │   └── ...
│   ├── services/
│   │   ├── __init__.py
│   │   ├── my_service.py                   # ⬅ XxxService(XxxModule) — 통신 + 도메인
│   │   └── ...                             # 다른 도메인 서비스
│   └── domain/                             # 순수 도메인 로직 (계산·변환·dynamics)
├── web/                                    # 프런트엔드 (선택)
│   ├── index.html
│   ├── css/
│   └── js/
├── data/                                   # 모듈 입력/출력 데이터
└── resources/                              # 큰 바이너리 (mbtiles, dem 등)
```

핵심 원칙:

1. **`backend/` · `frontend/` 분리 금지.** 5개 모듈 통일을 위해 `app/`
   (Python) + `web/` (자산) + `resources/` (바이너리).
2. **DTAM 통신 service 는 `app/services/<module>_service.py`** 에 둔다.
   `app/comm.py` 는 더 이상 사용하지 않는다.
3. **`MM_main.py`** 의 prefix 는 모듈 약칭 (MP, AM, OC, SS, DSE 패턴).

## 3. Step-by-step

### 3.1 Role 결정 + (필요 시) SDK 등록

새 역할이 필요하면 [`DTAM_SDK/dtam_client/identity.py`](dtam_client/identity.py)
의 `Role` enum 과 `KNOWN_MODULES` 에 추가, 그리고
[`policy.py`](dtam_client/policy.py) 의 `FORWARD_RULES` 에 어떤 mid 를 받을지
선언, 마지막으로 [`role_modules.py`](dtam_client/role_modules.py) 에
`MyNewRoleModule` 베이스 클래스 추가 (subscriptions_for(role) 와 일치하는
빈 stub 들). 기존 5개 역할로 충분하면 이 단계 생략.

### 3.2 `app/config.py`

```python
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
FRAMEWORK_ROOT = ROOT_DIR.parent

SERVER_HOST = os.getenv("DTAM_MM_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("DTAM_MM_PORT", "8200"))

DTAM_TARGET_IP = os.getenv("DTAM_MM_TARGET_IP", "127.0.0.1")
DTAM_WS_PORT   = int(os.getenv("DTAM_MM_WS_PORT", "8096"))
```

### 3.3 `app/services/<module>_service.py`

표준 패턴 그대로 작성 (위 §1 의 예시). 처리할 mid 만 override.

#### 도메인 도메인이 클 때

도메인이 무거우면 (시뮬레이션 엔진, 세션 매니저 등) 별도 서비스 파일로
분리하고 `MyService` 의 `__init__` 에 의존성으로 주입.

```python
# app/services/session_manager.py
class SessionManager:
    """순수 도메인 — DTAM/SDK 모름."""
    ...

# app/services/my_service.py
class MyVehicleService(VehicleModule):
    def __init__(self, *, target_ip, ws_port, sessions: SessionManager):
        self._sessions = sessions
        super().__init__(...)
    
    def on_scheduled_flight(self, plan):
        self._sessions.add_plan(plan)
```

#### 도메인이 다른 service 와 공유될 때 (예: route_planner)

생성자에 명시 주입:

```python
class MissionService(MissionModule):
    def __init__(self, *, target_ip, ws_port,
                 route_planner, settings, ...):
        self.route_planner = route_planner
        self.settings = settings
        super().__init__(...)
```

### 3.4 `app/server.py` (FastAPI factory + lifespan)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

from .services.my_service import MyVehicleService
from .services.session_manager import SessionManager
from .config import DTAM_TARGET_IP, DTAM_WS_PORT

# 모듈 전역 (또는 app.state 사용)
service: Optional[MyVehicleService] = None

def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        global service
        sessions = SessionManager()
        service = MyVehicleService(
            target_ip=DTAM_TARGET_IP,
            ws_port=DTAM_WS_PORT,
            sessions=sessions,
        )
        yield
        if service is not None:
            service.close()

    app = FastAPI(title="My Module", lifespan=lifespan)
    
    # routes 등록
    from .routes import status as status_routes
    app.include_router(status_routes.router)
    
    return app
```

### 3.5 `app/routes/*.py` — REST 엔드포인트

각 파일이 한 책임. `service.X` 메서드 호출만.

```python
# app/routes/status.py
from fastapi import APIRouter
from .. import server

router = APIRouter(prefix="/api")

@router.get("/status")
async def get_status():
    if server.service is None:
        return {"ready": False}
    return server.service.describe()         # service 의 describe()
```

### 3.6 `MM_main.py` — uvicorn 진입점

```python
import argparse, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRAMEWORK_ROOT = ROOT.parent
DTAM_SDK_ROOT = FRAMEWORK_ROOT / "DTAM_SDK"
for extra in (str(FRAMEWORK_ROOT), str(DTAM_SDK_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from dtam_client.ports import find_available_tcp_port
from DTAM_MyModule.app.server import create_app

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8200)
    parser.add_argument("--target-ip", default="127.0.0.1")
    parser.add_argument("--ws-port", type=int, default=8096)
    args = parser.parse_args()
    
    os.environ["DTAM_MM_TARGET_IP"] = args.target_ip
    os.environ["DTAM_MM_WS_PORT"]   = str(args.ws_port)
    args.port = find_available_tcp_port(args.host, args.port)
    
    import uvicorn
    uvicorn.run(create_app(), host=args.host, port=args.port)

if __name__ == "__main__":
    main()
```

## 4. 메시지 송신

```python
from dtam_client.schema import Msg4001_VehicleStatus

# Service 메서드 안에서
result = self.send(Msg4001_VehicleStatus(
    timestamp="...", vehicles={"UAM01": {...}}
))
```

- `self.send(message)` 는 dataclass 우선이다. SDK 가 mid 를 알아서 찾고,
  4001 처럼 wire 모양이 다른 메시지는 `to_wire()` 어댑터로 직렬화.
- 검증 실패 / 연결 끊김 / register 미완료 시 `False` 반환. 호출자가 처리.

## 5. 흔한 실수 / 체크리스트

- [ ] **`role` 클래스 속성 누락** — 베이스 (`VehicleModule` 등) 가 이미 정의해둠.
      별도로 `role = Role.X` 적을 필요 없음 (오히려 적으면 베이스 검증과 충돌
      가능).
- [ ] **`server_url` 에 `/ws/dtam` 누락** — `ws://<host>:<port>/ws/dtam`.
- [ ] **메서드 이름이 alias 와 안 맞음** — base 의 메서드 이름 (`on_<alias>`)
      을 그대로 쓴다. `_on_3001` 같은 옛 이름은 dispatcher 가 못 찾는다.
- [ ] **`self.send(dict)` 사용** — strict 모드 켜두고 dataclass 만 쓴다.
- [ ] **legacy UDP/TCP 흔적** — 현재 시스템에 없다. 새 모듈에서 도입 금지.
- [ ] **별도 `comm.py` 만들기** — 통신 layer 와 도메인을 한 클래스에 통합 한다
      (XxxService(XxxModule)). 옛 가이드의 comm 분리 패턴은 폐기됐다.

## 6. 통합 테스트 체크포인트

1. SimulationState 서버 띄우기 (`python DTAM_SimulationState/SS_main.py`)
2. 새 모듈 띄우기 (`python DTAM_MyModule/MM_main.py`)
3. 라이브 모니터 (`http://127.0.0.1:8096/`) 에서 내 role 이 connected 로 잡히는지
4. 받기로 한 mid 를 다른 모듈에서 보내고 콘솔/UI 도달 확인
5. 보낸 mid 가 SimulationState 의 DB (`DTAM_SimulationState/data/DB/<session>/`)
   에 기록됐는지

## 7. 참고할 만한 기존 모듈

3 모듈이 모두 같은 패턴이라 어느 거 베껴도 OK.

| 모듈 | 추천 사유 |
|---|---|
| [DTAMOperationsConsole](../../DTAMOperationsConsole/) | 가장 단순 (heartbeat 만, override 0개). 새 모듈 시작용 minimal template. |
| [DTAM_MissionPlanner](../../DTAM_MissionPlanner/) | 도메인이 풍부하고 핸들러가 자체 helpers 사용. 도메인 ↔ 통신 통합의 모범. |
| [DTAMAirMobility](../../DTAMAirMobility/) | 가장 무거운 도메인 (10Hz tick, sessions, dynamics). 큰 모듈을 어떻게 클래스 1개로 묶는지의 예. |

## 8. 새 ICD 메시지 추가

별도 문서 [dtam_client/NEW_MESSAGE_PROMPT.md](dtam_client/NEW_MESSAGE_PROMPT.md) 참조.
모듈 한 채를 만드는 것과 메시지를 추가하는 것은 다른 작업이다.
