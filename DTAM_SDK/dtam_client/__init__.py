"""DTAM SDK public API.

Most module developers only need ``DtamClient``:

    from dtam_client import DtamClient

    dtam = DtamClient.module(
        my_ip="0.0.0.0",
        my_port=17000,
        peer_ip="192.168.0.43",
        peer_port=17000,
        auto_listen=True,
    )

    dtam.push_vehicle_status_async({...})

UDP uses ``port``. TCP uses ``port + 1`` by default.
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

import os
print(f"[dtam_client] Loaded from: {os.path.abspath(__file__)}")

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
