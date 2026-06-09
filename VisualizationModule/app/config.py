"""DTAM Visualization Manager configuration.

- AirSim RPC endpoint (default 127.0.0.1:41451)
- DTAM WebSocket endpoint (SimulationState ``/ws/dtam``)
- GUI HTTP port
- Periodic task rates (0002 heartbeat / 4101 camera)

By default this reads ``data/configs/vm_config.json``.  Legacy root-level
paths are accepted and rewritten to the current layout when possible.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT_DIR = Path(__file__).resolve().parents[1]                # VisualizationModule/
FRAMEWORK_ROOT = ROOT_DIR.parent                              # DTAMFramework/
DTAMSDK_ROOT = FRAMEWORK_ROOT / "DTAMSDK"
RUNTIME_DIR = ROOT_DIR / "runtime"
DATA_DIR = ROOT_DIR / "data"
CONFIG_DIR = DATA_DIR / "configs"
UNREAL_ROOT = RUNTIME_DIR / "Unreal"
AIRSIM_PY_ROOT = RUNTIME_DIR / "PythonClient"
WEB_DIR = ROOT_DIR / "app" / "web"

DEFAULT_CONFIG_FILE = CONFIG_DIR / "vm_config.json"
VISUALIZATION_FRAMEWORK_FILE = CONFIG_DIR / "visualization_framework.json"
LEGACY_CONFIG_FILE = ROOT_DIR / "vm_config.json"
_LEGACY_UNREAL_ROOT = ROOT_DIR / "Unreal"
_LEGACY_AIRSIM_PY_ROOT = ROOT_DIR / "PythonClient"

# ICD messages that this module handles.
INBOUND_MIDS: List[str] = ["1001", "1002", "1003", "2002", "3001", "0003", "4001", "5002", "5003"]
OUTBOUND_MIDS: List[str] = ["0002", "4101", "4102", "4103"]

MODULE_SOURCE_NAME = "VisualizationModule"


def normalize_module_path_text(value: Any) -> str:
    """Rewrite legacy VM-local paths to the current VisualizationModule layout.

    Older config files may still contain paths such as
    ``VisualizationModule\\Unreal\\...``, ``VisualizationModule\\PythonClient``,
    or absolute paths from a previous checkout such as
    ``D:\\DTAMFramework\\VisualizationModule\\...``. Keeping this small
    compatibility shim prevents stale absolute paths from breaking Unreal
    launch or AirSim SDK imports after the folder cleanup.
    """
    text = str(value or "").strip()
    if not text:
        return ""

    replacements = {
        str(_LEGACY_UNREAL_ROOT): str(UNREAL_ROOT),
        str(_LEGACY_UNREAL_ROOT).replace("\\", "/"): str(UNREAL_ROOT),
        str(_LEGACY_AIRSIM_PY_ROOT): str(AIRSIM_PY_ROOT),
        str(_LEGACY_AIRSIM_PY_ROOT).replace("\\", "/"): str(AIRSIM_PY_ROOT),
    }
    for old, new in replacements.items():
        if old and old in text:
            text = text.replace(old, new)

    # Configs are commonly copied between machines/drives. If a value still
    # points at another DTAMFramework checkout, keep any command-line prefix
    # such as "-settings=" and rewrite only the stale repository root.
    for marker in (
        "DTAMFramework\\VisualizationModule",
        "DTAMFramework/VisualizationModule",
    ):
        marker_index = text.casefold().find(marker.casefold())
        if marker_index < 0:
            continue
        prefix_end = marker_index + len("DTAMFramework")
        stale_root_start = max(text.rfind("=", 0, marker_index) + 1, 0)
        text = text[:stale_root_start] + str(FRAMEWORK_ROOT) + text[prefix_end:]
        break
    return text


def resolve_config_path(path: Optional[Path] = None) -> Path:
    """Resolve VM config path, including the previous root-level location."""
    if path is None:
        return DEFAULT_CONFIG_FILE

    cfg_path = Path(path).expanduser()
    if cfg_path.is_file():
        return cfg_path

    candidates: List[Path] = []
    if not cfg_path.is_absolute():
        candidates.extend([ROOT_DIR / cfg_path, CONFIG_DIR / cfg_path])
    if cfg_path.name:
        candidates.append(CONFIG_DIR / cfg_path.name)
    if cfg_path == LEGACY_CONFIG_FILE:
        candidates.append(DEFAULT_CONFIG_FILE)

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return cfg_path


def _bool_from_raw(value: Any, default: bool = False) -> bool:
    """Parse bool-like config values without Python's ``bool("false")`` trap."""
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "y", "on", "enable", "enabled"):
        return True
    if text in ("0", "false", "no", "n", "off", "disable", "disabled"):
        return False
    return bool(default)


def _float_from_raw(value: Any, default: float, minimum: float, maximum: float) -> float:
    """Parse a bounded float config value."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = float(default)
    return max(float(minimum), min(float(maximum), parsed))


def _int_from_raw(value: Any, default: int, minimum: int, maximum: int) -> int:
    """Parse a bounded integer config value."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(int(minimum), min(int(maximum), parsed))


def _normalize_rendering_preset(value: Any) -> str:
    text = str(value or "balanced").strip().lower()
    aliases = {
        "low": "performance",
        "lite": "performance",
        "fast": "performance",
        "perf": "performance",
        "normal": "balanced",
        "medium": "balanced",
        "high": "quality",
        "best": "quality",
    }
    text = aliases.get(text, text)
    if text not in ("performance", "balanced", "quality", "custom"):
        return "balanced"
    return text


def rendering_preset_defaults(preset: Any = "balanced") -> Dict[str, Any]:
    """Return conservative Unreal/Cesium rendering defaults for a preset.

    These values are intentionally low-risk: they only affect launch/runtime
    rendering cost and Cesium streaming pressure, not vehicle or mission logic.
    """
    normalized = _normalize_rendering_preset(preset)
    presets: Dict[str, Dict[str, Any]] = {
        "performance": {
            "maximum_screen_space_error": 128.0,
            "maximum_simultaneous_tile_loads": 2,
            "maximum_cached_megabytes": 1536,
            "loading_descendant_limit": 2,
            "culled_screen_space_error": 768.0,
            "distance_fog_density": 0.0,
            "distance_fog_start_distance_m": 5000.0,
            "distance_fog_max_opacity": 0.0,
            "frame_rate_limit": 30,
            "screen_percentage": 60,
            "scalability_level": 0,
        },
        "balanced": {
            "maximum_screen_space_error": 96.0,
            "maximum_simultaneous_tile_loads": 4,
            "maximum_cached_megabytes": 2048,
            "loading_descendant_limit": 3,
            "culled_screen_space_error": 512.0,
            "distance_fog_density": 0.0,
            "distance_fog_start_distance_m": 5000.0,
            "distance_fog_max_opacity": 0.0,
            "frame_rate_limit": 30,
            "screen_percentage": 70,
            "scalability_level": 1,
        },
        "quality": {
            "maximum_screen_space_error": 64.0,
            "maximum_simultaneous_tile_loads": 6,
            "maximum_cached_megabytes": 3072,
            "loading_descendant_limit": 4,
            "culled_screen_space_error": 384.0,
            "distance_fog_density": 0.0,
            "distance_fog_start_distance_m": 5000.0,
            "distance_fog_max_opacity": 0.0,
            "frame_rate_limit": 40,
            "screen_percentage": 85,
            "scalability_level": 2,
        },
    }
    out = dict(presets.get(normalized, presets["balanced"]))
    out["preset"] = normalized
    return out


@dataclass
class AirSimConfig:
    host: str = "127.0.0.1"
    port: int = 41451
    vehicle_prefix: str = ""      # Optional prefix for mapping UAM IDs to AirSim vehicle names.
    # Keep normal DTAM 4001 replay in teleport mode by default.  The incoming
    # vehicle state is authoritative; Unreal collision sweep is useful for a
    # dedicated collision test, but it can also clamp/freeze altitude when a
    # spawned pawn is already touching a FATO/ground mesh.
    ignore_collisions: bool = True
    # Direct UAM-to-AirSim vehicle name mapping; takes precedence over prefix. Example: {"UAM0001": "Drone1"}
    vehicle_map: Dict[str, str] = field(default_factory=dict)


@dataclass
class DtamEndpoint:
    server_ip: str = "127.0.0.1"
    server_port: int = 8096      # SimulationState HTTP/WebSocket port


@dataclass
class StreamingConfig:
    module_status_hz: float = 1.0
    camera_enabled: bool = False
    camera_name: str = "front_center"
    camera_image_type: int = 0       # Scene
    camera_hz: float = 2.0           # 4101 is snapshot only; realtime video uses 4102 direct stream.
    camera_quality: int = 60
    camera_vehicle: str = ""         # Empty string uses the default AirSim vehicle.


@dataclass
class CollisionConfig:
    """Visualization-side AirSim collision polling settings.

    Session 3 publishes detected collisions as MSG 4103 through IntegrationHub.
    ``pose_feedback_*`` is a diagnostic that compares the requested AirSim pose
    with the actual pose after ``simSetVehiclePose``.  It can be triggered by
    map/streaming/teleport timing mismatches as well as by a real blocked
    sweep, so it must not request VehicleModule hold by default.
    """

    enabled: bool = True
    poll_hz: float = 5.0
    dedup_window_sec: float = 1.0
    publish_to_server: bool = True
    publish_no_collision: bool = False
    default_recommended_action: str = "none"
    pose_feedback_check_enabled: bool = True
    pose_feedback_publish_to_server: bool = False
    pose_feedback_recommended_action: str = "none"
    pose_feedback_error_threshold_m: float = 0.75
    pose_feedback_sample_hz: float = 5.0


@dataclass
class MetricsConfig:
    """Lightweight runtime metrics for Unreal/AirSim performance tuning."""

    enabled: bool = True
    log_interval_sec: float = 5.0
    history_size: int = 120
    include_per_vehicle_rpc: bool = False
    include_camera_latency: bool = True
    log_path: str = ""


@dataclass
class RuntimeOptimizationConfig:
    """Low-risk runtime throttles used to reduce AirSim/Unreal RPC pressure."""

    vehicle_status_apply_hz: float = 30.0
    vehicle_status_apply_hz_by_vehicle_count: List[Dict[str, Any]] = field(default_factory=lambda: [
        {"min": 1, "max": 1, "hz": 30.0},
        {"min": 2, "max": 3, "hz": 20.0},
        {"min": 4, "max": 999, "hz": 15.0},
    ])
    telemetry_hz: float = 10.0
    visual_state_hz: float = 10.0
    direct_camera_default_fps: float = 20.0
    direct_camera_max_fps: float = 30.0
    teststream_default_fps: float = 20.0


@dataclass
class RenderingPerformanceConfig:
    """Unreal/Cesium visual quality controls.

    ``runtime_optimization`` throttles Python/AirSim polling.  This config is
    separate because it controls renderer CVars and Cesium tile-stream pressure.
    The values are merged into Unreal ``-ExecCmds`` at launch and can also be
    applied to a running DT World through the AirSim console-command bridge.
    """

    preset: str = "balanced"
    maximum_screen_space_error: float = 96.0
    maximum_simultaneous_tile_loads: int = 4
    maximum_cached_megabytes: int = 2048
    loading_descendant_limit: int = 3
    culled_screen_space_error: float = 512.0
    distance_fog_density: float = 0.0
    distance_fog_start_distance_m: float = 5000.0
    distance_fog_max_opacity: float = 0.0
    frame_rate_limit: int = 30
    screen_percentage: int = 70
    scalability_level: int = 1
    stream_camera_tile_loading: bool = False
    stream_camera_tile_loading_max_cameras: int = 1
    stream_camera_tile_loading_refresh_s: float = 1.0
    sky_light_realtime_capture: bool = False
    apply_on_launch: bool = True


@dataclass
class UnrealRuntimeConfig:
    executable: str = ""
    args: List[str] = field(default_factory=lambda: ["-windowed"])
    working_dir: str = ""
    # off | stats | trace | full.  The manager expands this into safe Unreal
    # stat/trace arguments at launch time without changing the default runtime.
    profile_mode: str = "off"
    profile_args: List[str] = field(default_factory=list)
    profile_exec_cmds: List[str] = field(default_factory=list)


@dataclass
class PixelStreamingConfig:
    enabled: bool = False
    auto_start_server: bool = False
    player_url: str = "http://127.0.0.1:8080/player.html"
    streamer_url: str = "ws://127.0.0.1:8888"
    player_port: int = 8080
    streamer_port: int = 8888
    signalling_dir: str = ""
    stream_id: str = "DTAMVisualization"


@dataclass
class VMConfig:
    gui_host: str = "127.0.0.1"
    gui_port: int = 8097
    log_level: str = "info"
    airsim: AirSimConfig = field(default_factory=AirSimConfig)
    dtam: DtamEndpoint = field(default_factory=DtamEndpoint)
    streaming: StreamingConfig = field(default_factory=StreamingConfig)
    collision: CollisionConfig = field(default_factory=CollisionConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    runtime_optimization: RuntimeOptimizationConfig = field(default_factory=RuntimeOptimizationConfig)
    rendering_performance: RenderingPerformanceConfig = field(default_factory=RenderingPerformanceConfig)
    unreal: UnrealRuntimeConfig = field(default_factory=UnrealRuntimeConfig)
    pixel_streaming: PixelStreamingConfig = field(default_factory=PixelStreamingConfig)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gui_host": self.gui_host,
            "gui_port": self.gui_port,
            "log_level": self.log_level,
            "airsim": asdict(self.airsim),
            "dtam": asdict(self.dtam),
            "streaming": asdict(self.streaming),
            "collision": asdict(self.collision),
            "metrics": asdict(self.metrics),
            "runtime_optimization": asdict(self.runtime_optimization),
            "rendering_performance": asdict(self.rendering_performance),
            "unreal": asdict(self.unreal),
            "pixel_streaming": asdict(self.pixel_streaming),
        }


def load_config(path: Optional[Path] = None) -> VMConfig:
    cfg_path = resolve_config_path(path)
    raw: Dict[str, Any] = {}
    if cfg_path.is_file():
        try:
            raw = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            print(f"[DTAM VM] failed to read {cfg_path}: {exc}")

    gui_host = str(raw.get("gui_host", "127.0.0.1"))
    gui_port = int(raw.get("gui_port", 8097))
    log_level = str(raw.get("log_level", "info"))

    airsim_raw = dict(raw.get("airsim") or {})
    airsim = AirSimConfig(
        host=str(airsim_raw.get("host", "127.0.0.1")),
        port=int(airsim_raw.get("port", 41451)),
        vehicle_prefix=str(airsim_raw.get("vehicle_prefix", "")),
        ignore_collisions=_bool_from_raw(airsim_raw.get("ignore_collisions"), False),
        vehicle_map={str(k): str(v) for k, v in dict(airsim_raw.get("vehicle_map") or {}).items()},
    )

    dtam_raw = dict(raw.get("dtam") or {})
    dtam = DtamEndpoint(
        server_ip=str(dtam_raw.get("server_ip", "127.0.0.1")),
        server_port=int(dtam_raw.get("server_port", 8096)),
    )

    stream_raw = dict(raw.get("streaming") or {})
    streaming = StreamingConfig(
        module_status_hz=_float_from_raw(stream_raw.get("module_status_hz"), 1.0, 0.1, 60.0),
        camera_enabled=_bool_from_raw(stream_raw.get("camera_enabled"), False),
        camera_name=str(stream_raw.get("camera_name", "front_center")),
        camera_image_type=_int_from_raw(stream_raw.get("camera_image_type"), 0, 0, 10),
        camera_hz=_float_from_raw(stream_raw.get("camera_hz"), 2.0, 0.1, 30.0),
        camera_quality=_int_from_raw(stream_raw.get("camera_quality"), 60, 10, 95),
        camera_vehicle=str(stream_raw.get("camera_vehicle", "")),
    )

    collision_raw = dict(raw.get("collision") or {})
    collision = CollisionConfig(
        enabled=_bool_from_raw(collision_raw.get("enabled"), True),
        poll_hz=_float_from_raw(collision_raw.get("poll_hz"), 5.0, 0.2, 60.0),
        dedup_window_sec=_float_from_raw(collision_raw.get("dedup_window_sec"), 1.0, 0.0, 30.0),
        publish_to_server=_bool_from_raw(collision_raw.get("publish_to_server"), True),
        publish_no_collision=_bool_from_raw(collision_raw.get("publish_no_collision"), False),
        default_recommended_action=str(collision_raw.get("default_recommended_action", "none") or "none"),
        pose_feedback_check_enabled=_bool_from_raw(collision_raw.get("pose_feedback_check_enabled"), True),
        pose_feedback_publish_to_server=_bool_from_raw(collision_raw.get("pose_feedback_publish_to_server"), False),
        pose_feedback_recommended_action=str(collision_raw.get("pose_feedback_recommended_action", "none") or "none"),
        pose_feedback_error_threshold_m=_float_from_raw(collision_raw.get("pose_feedback_error_threshold_m"), 0.75, 0.0, 100.0),
        pose_feedback_sample_hz=_float_from_raw(collision_raw.get("pose_feedback_sample_hz"), 5.0, 0.2, 60.0),
    )

    metrics_raw = dict(raw.get("metrics") or {})
    metrics = MetricsConfig(
        enabled=_bool_from_raw(metrics_raw.get("enabled"), True),
        log_interval_sec=_float_from_raw(metrics_raw.get("log_interval_sec"), 5.0, 0.0, 3600.0),
        history_size=_int_from_raw(metrics_raw.get("history_size"), 120, 10, 5000),
        include_per_vehicle_rpc=_bool_from_raw(metrics_raw.get("include_per_vehicle_rpc"), False),
        include_camera_latency=_bool_from_raw(metrics_raw.get("include_camera_latency"), True),
        log_path=normalize_module_path_text(metrics_raw.get("log_path", "")),
    )

    default_runtime_optimization = RuntimeOptimizationConfig()
    runtime_opt_raw = dict(raw.get("runtime_optimization") or {})
    tiers_raw = runtime_opt_raw.get("vehicle_status_apply_hz_by_vehicle_count")
    tiers: List[Dict[str, Any]] = []
    if isinstance(tiers_raw, list):
        for item in tiers_raw:
            if not isinstance(item, dict):
                continue
            try:
                min_count = max(0, int(item.get("min", 0)))
                max_count = max(min_count, int(item.get("max", 999)))
                hz = max(1.0, min(60.0, float(item.get("hz", default_runtime_optimization.vehicle_status_apply_hz))))
            except (TypeError, ValueError):
                continue
            tiers.append({"min": min_count, "max": max_count, "hz": hz})
    if not tiers:
        tiers = list(default_runtime_optimization.vehicle_status_apply_hz_by_vehicle_count)
    runtime_optimization = RuntimeOptimizationConfig(
        vehicle_status_apply_hz=_float_from_raw(runtime_opt_raw.get("vehicle_status_apply_hz"), 30.0, 1.0, 60.0),
        vehicle_status_apply_hz_by_vehicle_count=tiers,
        telemetry_hz=_float_from_raw(runtime_opt_raw.get("telemetry_hz"), 10.0, 0.0, 60.0),
        visual_state_hz=_float_from_raw(runtime_opt_raw.get("visual_state_hz"), 10.0, 0.0, 60.0),
        direct_camera_default_fps=_float_from_raw(runtime_opt_raw.get("direct_camera_default_fps"), 20.0, 0.2, 30.0),
        direct_camera_max_fps=_float_from_raw(runtime_opt_raw.get("direct_camera_max_fps"), 30.0, 0.2, 30.0),
        teststream_default_fps=_float_from_raw(runtime_opt_raw.get("teststream_default_fps"), 20.0, 0.2, 30.0),
    )

    rendering_raw = dict(raw.get("rendering_performance") or raw.get("visual_quality") or {})
    rendering_base = rendering_preset_defaults(rendering_raw.get("preset", "balanced"))
    rendering_performance = RenderingPerformanceConfig(
        preset=_normalize_rendering_preset(rendering_raw.get("preset", rendering_base["preset"])),
        maximum_screen_space_error=_float_from_raw(
            rendering_raw.get("maximum_screen_space_error"),
            float(rendering_base["maximum_screen_space_error"]),
            32.0,
            256.0,
        ),
        maximum_simultaneous_tile_loads=_int_from_raw(
            rendering_raw.get("maximum_simultaneous_tile_loads"),
            int(rendering_base["maximum_simultaneous_tile_loads"]),
            1,
            16,
        ),
        maximum_cached_megabytes=_int_from_raw(
            rendering_raw.get("maximum_cached_megabytes"),
            int(rendering_base["maximum_cached_megabytes"]),
            512,
            8192,
        ),
        loading_descendant_limit=_int_from_raw(
            rendering_raw.get("loading_descendant_limit"),
            int(rendering_base["loading_descendant_limit"]),
            1,
            8,
        ),
        culled_screen_space_error=_float_from_raw(
            rendering_raw.get("culled_screen_space_error"),
            float(rendering_base["culled_screen_space_error"]),
            128.0,
            2048.0,
        ),
        distance_fog_density=_float_from_raw(
            rendering_raw.get("distance_fog_density"),
            float(rendering_base["distance_fog_density"]),
            0.0,
            0.005,
        ),
        distance_fog_start_distance_m=_float_from_raw(
            rendering_raw.get("distance_fog_start_distance_m"),
            float(rendering_base["distance_fog_start_distance_m"]),
            100.0,
            5000.0,
        ),
        distance_fog_max_opacity=_float_from_raw(
            rendering_raw.get("distance_fog_max_opacity"),
            float(rendering_base["distance_fog_max_opacity"]),
            0.0,
            1.0,
        ),
        frame_rate_limit=_int_from_raw(
            rendering_raw.get("frame_rate_limit"),
            int(rendering_base["frame_rate_limit"]),
            20,
            60,
        ),
        screen_percentage=_int_from_raw(
            rendering_raw.get("screen_percentage"),
            int(rendering_base["screen_percentage"]),
            50,
            100,
        ),
        scalability_level=_int_from_raw(
            rendering_raw.get("scalability_level"),
            int(rendering_base["scalability_level"]),
            0,
            3,
        ),
        stream_camera_tile_loading=_bool_from_raw(rendering_raw.get("stream_camera_tile_loading"), False),
        stream_camera_tile_loading_max_cameras=_int_from_raw(
            rendering_raw.get("stream_camera_tile_loading_max_cameras"),
            1,
            1,
            8,
        ),
        stream_camera_tile_loading_refresh_s=_float_from_raw(
            rendering_raw.get("stream_camera_tile_loading_refresh_s"),
            1.0,
            0.1,
            10.0,
        ),
        sky_light_realtime_capture=_bool_from_raw(rendering_raw.get("sky_light_realtime_capture"), False),
        apply_on_launch=_bool_from_raw(rendering_raw.get("apply_on_launch"), True),
    )

    unreal_raw = dict(raw.get("unreal") or {})
    unreal_args_raw = unreal_raw.get("args", ["-windowed"])
    if isinstance(unreal_args_raw, str):
        unreal_args = [unreal_args_raw]
    else:
        unreal_args = [str(item) for item in list(unreal_args_raw or [])]
    unreal_profile_args_raw = unreal_raw.get("profile_args", [])
    if isinstance(unreal_profile_args_raw, str):
        unreal_profile_args = [unreal_profile_args_raw]
    else:
        unreal_profile_args = [str(item) for item in list(unreal_profile_args_raw or [])]
    unreal_profile_exec_cmds_raw = unreal_raw.get("profile_exec_cmds", [])
    if isinstance(unreal_profile_exec_cmds_raw, str):
        unreal_profile_exec_cmds = [unreal_profile_exec_cmds_raw]
    else:
        unreal_profile_exec_cmds = [str(item) for item in list(unreal_profile_exec_cmds_raw or [])]
    unreal = UnrealRuntimeConfig(
        executable=normalize_module_path_text(unreal_raw.get("executable", "")),
        args=[normalize_module_path_text(item) for item in unreal_args],
        working_dir=normalize_module_path_text(unreal_raw.get("working_dir", "")),
        profile_mode=str(unreal_raw.get("profile_mode", "off") or "off"),
        profile_args=[normalize_module_path_text(item) for item in unreal_profile_args],
        profile_exec_cmds=[str(item).strip() for item in unreal_profile_exec_cmds if str(item).strip()],
    )

    pixel_raw = dict(raw.get("pixel_streaming") or {})
    default_signalling = (
        ROOT_DIR
        / "runtime"
        / "PixelStreamingWebServers"
        / "SignallingWebServer"
    )
    pixel_player_url = str(pixel_raw.get("player_url", "http://127.0.0.1:8080/player.html")).strip()
    if not pixel_player_url:
        pixel_player_url = "http://127.0.0.1:8080/player.html"

    pixel_streaming = PixelStreamingConfig(
        enabled=bool(pixel_raw.get("enabled", False)),
        auto_start_server=bool(pixel_raw.get("auto_start_server", False)),
        player_url=pixel_player_url,
        streamer_url=str(pixel_raw.get("streamer_url", "ws://127.0.0.1:8888")),
        player_port=int(pixel_raw.get("player_port", 8080)),
        streamer_port=int(pixel_raw.get("streamer_port", 8888)),
        signalling_dir=normalize_module_path_text(pixel_raw.get("signalling_dir", str(default_signalling))),
        stream_id=str(pixel_raw.get("stream_id", "DTAMVisualization")),
    )

    return VMConfig(
        gui_host=gui_host,
        gui_port=gui_port,
        log_level=log_level,
        airsim=airsim,
        dtam=dtam,
        streaming=streaming,
        collision=collision,
        metrics=metrics,
        runtime_optimization=runtime_optimization,
        rendering_performance=rendering_performance,
        unreal=unreal,
        pixel_streaming=pixel_streaming,
    )


def save_config(cfg: VMConfig, path: Optional[Path] = None) -> Path:
    cfg_path = resolve_config_path(path)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg_path

