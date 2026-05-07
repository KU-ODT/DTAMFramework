# DTAM SDK

Version: `0.0.1`

DTAM SDK is the Python package every DTAM module uses to talk to the
SimulationState data plane (`ws://<host>:8096/ws/dtam`). It provides:

- a single message catalog (`CATALOG`) shared by SDK, server, and modules
- `Role` enum + `KNOWN_MODULES` registry — single source of identity
- `DtamModule` — WebSocket client with auto-register, heartbeat, and
  dataclass-typed send/receive
- `DtamRest` — small helper for REST one-shots against the same server
- ICD message dataclasses + `to_wire()`/`from_wire()` adapters

Guides:

- 한국어 SDK 사용법: [README_KOR.md](README_KOR.md)
- English SDK reference: [README_ENG.md](README_ENG.md)
- 새 모듈을 처음부터 작성: [MODULE_AUTHORING.md](MODULE_AUTHORING.md)
- ICD documents: [dtam_client/icd](dtam_client/icd)
- 새 ICD 메시지 추가: [dtam_client/NEW_MESSAGE_PROMPT.md](dtam_client/NEW_MESSAGE_PROMPT.md)

Quick start:

```python
from dtam_client import DtamModule, Role, on_receive
from dtam_client.schema import Msg3001_ScheduledFlight, Msg4001_VehicleStatus

class VehicleService(DtamModule):
    role = Role.VEHICLE

    def __init__(self):
        super().__init__(server_url="ws://127.0.0.1:8096/ws/dtam", heartbeat=True)

    @on_receive("3001")
    def handle_plan(self, plan: Msg3001_ScheduledFlight):
        print("got plan:", plan.aircraftId)

svc = VehicleService()
svc.send(Msg4001_VehicleStatus(timestamp="2026-04-28T00:00:00.000Z", vehicles={}))
```

Network model: every module is a WebSocket *client* that connects to
`DTAM_SimulationState` at port `8096`. `DTAM_CoreServer` (8095) is the REST
control plane only. There is no UDP/TCP module-to-module path.
