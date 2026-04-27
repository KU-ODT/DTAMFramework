"""DTAM SDK public API (WebSocket-only).

권장 사용:
    from dtam_client import DtamModule, Role

    mod = DtamModule.start(
        role=Role.VEHICLE,
        server_url="ws://127.0.0.1:8096/ws/dtam",
        heartbeat=True,
    )
    mod.on("scheduled_flight", on_3001)
    mod.send("vehicle_status", payload)

REST 단발 호출:
    from dtam_client import DtamRest

    rest = DtamRest("http://127.0.0.1:8096")
    rest.snapshot()
    rest.push("simulation_setup", payload, role="vehicle")
"""

from ._version import VERSION, __version__

# 신규 통합 layer (WS-only).
from .catalog import (
    CATALOG,
    MessageSpec,
    PHASE_INFO,
    resolve as resolve_message,
    callback_name,
    push_name,
    phase_tag,
)
from .identity import (
    KNOWN_MODULES,
    ModuleIdentity,
    Role,
    identity_of,
    role_of,
)
from .policy import FORWARD_RULES, subscriptions_for
from .module import DtamModule, ModuleStats
from .rest import DtamRest, DtamRestError
from ._ws_client import DtamWsClient   # advanced users (DtamModule 내부에서 사용)

from .samples import (
    all_sample_payloads,
    sample_camera_image_bytes,
    sample_camera_image_header,
    sample_common_time_info,
    sample_dtam_execute,
    sample_flight_plan_request,
    sample_module_setting_info,
    sample_module_status,
    sample_payload,
    sample_scenario_setup,
    sample_scheduled_flight,
    sample_sim_mode_setup,
    sample_simulation_setup,
    sample_strategic_separation,
    sample_tactical_separation,
    sample_vehicle_status,
)

__all__ = [
    "__version__",
    "VERSION",
    # 통합 layer
    "CATALOG",
    "MessageSpec",
    "PHASE_INFO",
    "resolve_message",
    "callback_name",
    "push_name",
    "phase_tag",
    "Role",
    "ModuleIdentity",
    "KNOWN_MODULES",
    "identity_of",
    "role_of",
    "FORWARD_RULES",
    "subscriptions_for",
    "DtamModule",
    "ModuleStats",
    "DtamRest",
    "DtamRestError",
    "DtamWsClient",
    # samples
    "sample_payload",
    "all_sample_payloads",
    "sample_module_status",
    "sample_module_setting_info",
    "sample_common_time_info",
    "sample_sim_mode_setup",
    "sample_simulation_setup",
    "sample_scenario_setup",
    "sample_flight_plan_request",
    "sample_dtam_execute",
    "sample_scheduled_flight",
    "sample_strategic_separation",
    "sample_tactical_separation",
    "sample_vehicle_status",
    "sample_camera_image_header",
    "sample_camera_image_bytes",
]
