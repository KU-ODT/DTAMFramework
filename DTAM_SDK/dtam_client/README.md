# dtam_client

`dtam_client` is the SDK package every DTAM module imports. It is GUI-free
and assumes one transport: WebSocket `/ws/dtam` on the SimulationState
server.

## Public API (re-exported from `dtam_client/__init__.py`)

```python
from dtam_client import (
    DtamModule, ModuleStats, on_receive,           # WebSocket client
    set_strict_dataclass, is_strict_dataclass,     # send-mode toggle
    DtamRest, DtamRestError,                       # REST helper
    Role, ModuleIdentity, KNOWN_MODULES,           # identity
    identity_of, role_of,
    CATALOG, MessageSpec, PHASE_INFO,              # message catalog
    resolve_message, callback_name, push_name,
    FORWARD_RULES, subscriptions_for,              # routing policy
)
from dtam_client.schema import Msg3001_ScheduledFlight, Msg4001_VehicleStatus, ...
```

## Typical use

```python
from dtam_client import DtamModule, Role, on_receive
from dtam_client.schema import Msg4001_VehicleStatus

class Vehicle(DtamModule):
    role = Role.VEHICLE

    @on_receive("3001")
    def on_plan(self, plan):
        ...

svc = Vehicle(server_url="ws://127.0.0.1:8096/ws/dtam", heartbeat=True)
svc.send(Msg4001_VehicleStatus(timestamp="...", vehicles={}))
```

## Submodules

- `module.py`       — `DtamModule`, `on_receive`, strict-mode toggle
- `_ws_client.py`   — low-level WebSocket transport (advanced)
- `rest.py`         — `DtamRest` helper
- `catalog.py`      — single message catalog (mid ↔ alias ↔ phase ↔ db_folder)
- `identity.py`     — `Role` enum + `KNOWN_MODULES`
- `policy.py`       — forward rules and `subscriptions_for(role)`
- `schema/`         — ICD dataclasses (one file per phase)
- `samples.py`      — canned sample payloads for tests/fixtures
- `icd/{KOR,ENG}/`  — per-message ICD documents

## Adding a new ICD message

See [NEW_MESSAGE_PROMPT.md](NEW_MESSAGE_PROMPT.md). The five steps are:

1. add to `catalog.py` (mid, alias, direction, phase, db_folder)
2. add a dataclass under `schema/msg_phaseN.py` and register in `icd_registry.py`
3. add subscription/forward rules in `policy.py` if the server should fan out
4. add markdown specs to `icd/KOR/` and `icd/ENG/`
5. add a sample payload to `samples.py`
