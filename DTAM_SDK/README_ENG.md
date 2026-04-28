# DTAM SDK Guide (English)

Version: `0.0.1`

The DTAM SDK is the Python client every module uses to exchange ICD
messages with the DTAM SimulationState server over a single WebSocket
channel (`/ws/dtam` on port 8096). It also bundles the canonical message
catalog, ICD dataclasses, and identity tables shared with the server.

## 1. Architecture

- **Control plane** — `DTAM_CoreServer` on port 8095 (HTTP REST, GUI,
  process supervision).
- **Data plane** — `DTAM_SimulationState` on port 8096 (HTTP + WebSocket
  `/ws/dtam`, DB logging, live monitor).
- **Modules** (Mission Planner, Air Mobility, Operations Console,
  Visualization) — every module connects as a WebSocket *client* to the
  data plane. Modules never reach each other directly; the server forwards
  according to `FORWARD_RULES` and the role of the connected client.

## 2. Recommended pattern — subclass `DtamModule`

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
            heartbeat=True,            # auto-publishes 0002 once per second
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

Decorated handlers are auto-registered on construction. The argument is the
ICD message ID (`"3001"` etc.), and the callback receives a parsed
dataclass instance — never a raw dict in strict mode.

## 3. Imperative pattern — `DtamModule.start(...) + .on(alias, cb)`

When a subclass is overkill (one-off scripts, integration tests):

```python
from dtam_client import DtamModule, Role

mod = DtamModule.start(
    role=Role.MISSION,
    server_url="ws://127.0.0.1:8096/ws/dtam",
    heartbeat=True,
)
mod.on("scheduled_flight", lambda plan: print(plan.aircraftId))
mod.on("3001",             lambda plan: print(plan))   # mid also accepted
```

Aliases come from the catalog (`scheduled_flight` ↔ `3001`).

## 4. Sending — dataclass first

```python
from dtam_client.schema import Msg2002_DtamExecute

mod.send(Msg2002_DtamExecute(timestamp="...", flightPlanFolderName="abc"))
```

The SDK looks up the right `mid`, applies any `to_wire()` adapter (e.g. the
flat layout for 4001), and ships it. Strict mode (`set_strict_dataclass(True)`)
forbids `mod.send_legacy(mid, dict)` and raises a `TypeError` instead of a
DeprecationWarning. Strict mode is recommended for new code; leave it off
when migrating older callers.

## 5. Identity & roles

Every module identifies itself with a `Role`. The SDK is the authority:

```python
from dtam_client import Role, identity_of, role_of

identity_of(Role.VEHICLE).source   # "DTAMAirMobility"
role_of("DTAM_MissionPlanner")     # Role.MISSION
```

The server's heartbeat tracking matches a module's `source` against
`KNOWN_MODULES` to assign it a role.

## 6. Subscriptions

`FORWARD_RULES` declares which roles receive which messages.
`subscriptions_for(role)` returns the list of `mid`s a given role should
listen for — the SDK auto-subscribes for you when you call `start()` /
construct a `DtamModule` subclass.

## 7. REST helper

Use `DtamRest` for stateless calls (server snapshot, module list, etc.)
without opening a WebSocket:

```python
from dtam_client import DtamRest

rest = DtamRest("http://127.0.0.1:8096")
rest.snapshot()        # GET /api/state
rest.modules()         # GET /api/modules
```

## 8. Status & lifecycle

```python
mod.connected      # WebSocket open?
mod.registered     # 'register' handshake acknowledged?
mod.subscriptions  # list of mids this module receives
mod.stats.to_dict()
mod.close()
```

`DtamModule` runs its socket on a background thread, so calling
`send()`/`close()` from your main loop is safe.

## 9. ICD documents

Per-message specs live next to the package:

- 한국어: `dtam_client/icd/KOR/`
- English: `dtam_client/icd/ENG/`

Adding a new ICD message? Follow [dtam_client/NEW_MESSAGE_PROMPT.md](dtam_client/NEW_MESSAGE_PROMPT.md) —
edit `catalog.py`, add a dataclass under `dtam_client/schema/`, register
forward rules in `policy.py`, and drop matching markdown into both `KOR/`
and `ENG/`.
