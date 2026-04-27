"""DTAM SDK public API.

권장 (신규):
    from dtam_client import DtamModule, Role

    mod = DtamModule.start(
        role=Role.VEHICLE,
        server_url="ws://127.0.0.1:8096/ws/dtam",
        heartbeat=True,
    )
    mod.on("scheduled_flight", on_3001)
    mod.send("vehicle_status", payload)

레거시 (UDP/TCP — 마이그레이션 후 제거 예정):
    from dtam_client import DtamClient
    dtam = DtamClient.module(my_ip=..., my_port=..., peer_ip=..., peer_port=...)
    dtam.push_vehicle_status_async({...})
"""

from ._version import VERSION, __version__
from ._config import (
    DtamConfig,
    DtamNetworkConfig,
    Endpoint,
    configure,
    get_config,
    load_network_config,
)
from ._result import PushResult
from ._listener import DtamListener
from ._channel import DtamChannel
from ._client import DtamClient, create_client
from ._ws_client import DtamWsClient

# 신규 통합 layer (catalog/identity/policy/module/rest).
# 향후 모든 모듈은 이 layer 만 사용하도록 마이그레이션됩니다.
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
from .msg import (
    push_camera_image,
    push_common_time_info,
    push_dtam_execute,
    push_flight_plan_request,
    push_module_setting_info,
    push_module_status,
    push_scenario_setup,
    push_scheduled_flight,
    push_sim_mode_setup,
    push_simulation_setup,
    push_strategic_separation,
    push_tactical_separation,
    push_vehicle_status,
)

__all__ = [
    "__version__",
    "VERSION",
    # 신규 통합 layer
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
    # 레거시 (UDP/TCP)
    "configure",
    "get_config",
    "load_network_config",
    "DtamConfig",
    "DtamNetworkConfig",
    "Endpoint",
    "PushResult",
    "DtamClient",
    "DtamWsClient",
    "create_client",
    "DtamChannel",
    "DtamListener",
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
    "push_module_status",
    "push_module_setting_info",
    "push_common_time_info",
    "push_sim_mode_setup",
    "push_simulation_setup",
    "push_scenario_setup",
    "push_flight_plan_request",
    "push_dtam_execute",
    "push_scheduled_flight",
    "push_strategic_separation",
    "push_tactical_separation",
    "push_vehicle_status",
    "push_camera_image",
]
