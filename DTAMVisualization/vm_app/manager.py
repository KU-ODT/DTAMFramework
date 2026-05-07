"""Visualization Manager 중앙 허브.

- DtamIO 가 수신한 ICD 메시지를 AirSimBridge 메서드로 변환 (inbound 번역).
- 주기 작업 스레드: 0002 Module Status 1 Hz, 4101 Camera Image (선택적 N Hz).
- REST / WebSocket 에서 요청되는 조회/수동제어를 위한 퍼블릭 API 도 제공.

외부 모듈 → DTAM_SDK 네트워킹 → DtamIO → Manager → AirSimBridge → AirSim RPC
AirSim / 주기 작업 → Manager → DtamIO → DTAM_SDK 네트워킹 → 외부 모듈(서버)
"""
from __future__ import annotations

import logging
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional

from .airsim_bridge import AirSimBridge, BridgeStatus
from .config import FRAMEWORK_ROOT, ROOT_DIR, VMConfig
from .dtam_io import DtamIO

logger = logging.getLogger(__name__)

MAX_EVENTS = 400
MISSION_GUIDE_PATH = ROOT_DIR / "Unreal" / "Environments" / "DTAMVisualization" / "Data" / "mission_guides.json"
MISSION_GUIDE_TOGGLE_VK = 0x55  # U


@dataclass
class HubEvent:
    ts: float
    kind: str            # "rx" | "tx" | "translate" | "airsim" | "error"
    mid: str
    summary: str
    detail: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "kind": self.kind,
            "mid": self.mid,
            "summary": self.summary,
            "detail": self.detail,
        }


class VisualizationManager:
    def __init__(self, config: VMConfig) -> None:
        self._lock = threading.RLock()
        self._config = config
        self._bridge = AirSimBridge(config.airsim)
        self._io = DtamIO(config.dtam)
        self._events: Deque[HubEvent] = deque(maxlen=MAX_EVENTS)
        self._stop_event = threading.Event()
        self._periodic_thread: Optional[threading.Thread] = None
        self._started_at = 0.0
        self.on_event: Optional[Callable[[HubEvent], None]] = None
        self._streaming = config.streaming
        self._unreal_proc: Optional[subprocess.Popen[bytes]] = None
        # Unreal renders mission guides directly from mission_guides.json.
        # Keep AirSim marker output disabled unless explicitly requested for debugging.
        self._mission_guides_visible = False
        self._mission_guide_key_down = False
        self._last_mission_guide_toggle_ts = 0.0

    # ── 라이프사이클 ──────────────────────────────────────────
    def start(self) -> None:
        with self._lock:
            if self._periodic_thread is not None:
                return
            self._started_at = time.time()
            self._stop_event.clear()
            # AirSim is launched later by the Operations Console. Keep the VM
            # HTTP server ready first; /api/airsim/connect performs RPC connect.
            self._io.start(on_rx=self._on_rx)
            self._periodic_thread = threading.Thread(
                target=self._periodic_loop,
                name="dtam-vm-periodic",
                daemon=True,
            )
            self._periodic_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        th = None
        with self._lock:
            th = self._periodic_thread
            self._periodic_thread = None
        if th is not None and th.is_alive():
            th.join(timeout=2.0)
        self._io.close()
        self._bridge.disconnect()
        self._terminate_unreal_process()

    # ── 수신: DTAM → AirSim 변환 ────────────────────────────
    def _on_rx(self, mid: str, payload: Dict[str, Any], raw: Any) -> None:
        try:
            if mid == "4001":
                result = self._bridge.apply_vehicle_status_frame(payload)
                self._emit(HubEvent(
                    ts=time.time(), kind="translate", mid=mid,
                    summary=f"4001 → simSetVehiclePose x{result.get('applied', 0)}",
                    detail=result,
                ))
            elif mid == "1002":
                result = self._bridge.apply_simulation_setup(payload)
                self._emit(HubEvent(
                    ts=time.time(), kind="translate", mid=mid,
                    summary=f"1002 → weather/wind ({len(result.get('applied', []))} params)",
                    detail=result,
                ))
                play_state = str(payload.get("playState") or "").strip().lower()
                if play_state in ("play", "playing", "run", "running", "resume") or (
                    not play_state and payload.get("playbackSpeed") is not None
                ):
                    self._emit_mission_guides(mid)
            elif mid == "1003":
                result = self._bridge.apply_scenario_setup(payload)
                self._emit(HubEvent(
                    ts=time.time(), kind="translate", mid=mid,
                    summary=f"1003 → vehicle_map ({len(result.get('applied', []))} entries)",
                    detail=result,
                ))
            elif mid == "2002":
                result = self._bridge.on_dtam_execute(payload)
                self._emit(HubEvent(
                    ts=time.time(), kind="translate", mid=mid,
                    summary="2002 → AirSim reset",
                    detail=result,
                ))
                self._emit_mission_guides(mid)
            elif mid == "3001":
                result = (
                    self._bridge.apply_scheduled_flight_guide(payload)
                    if self._mission_guides_visible
                    else {"applied": 0, "skipped": 1, "visible": False, "errors": []}
                )
                self._emit(HubEvent(
                    ts=time.time(), kind="translate", mid=mid,
                    summary=f"3001 ??mission guide x{result.get('applied', 0)}",
                    detail=result,
                ))
            elif mid == "1001":
                # 단순 저장 — dynamics 선택은 VM 레벨에서 의미 있는 실제 작업 없음
                self._emit(HubEvent(
                    ts=time.time(), kind="rx", mid=mid,
                    summary=f"1001 received (operationMode={payload.get('operationMode')})",
                    detail=payload,
                ))
            elif mid == "0003":
                self._emit(HubEvent(
                    ts=time.time(), kind="rx", mid=mid,
                    summary=f"0003 simTime={payload.get('simTime')}",
                    detail={"timestamp": payload.get("timestamp"), "simTime": payload.get("simTime")},
                ))
            elif mid == "5002":
                result = self.control_camera(
                    aircraft_id=str(payload.get("aircraftId") or payload.get("vehicleId") or ""),
                    vehicle_name=str(payload.get("vehicleName") or payload.get("airsimVehicleName") or ""),
                    camera_name=str(payload.get("cameraName") or payload.get("camera_name") or "front_center"),
                    yaw_delta_deg=_as_float(payload.get("yawDeltaDeg") or payload.get("yaw_delta_deg")),
                    pitch_delta_deg=_as_float(payload.get("pitchDeltaDeg") or payload.get("pitch_delta_deg")),
                    focal_length_delta=_as_float(payload.get("focalLengthDelta") or payload.get("focal_length_delta")),
                )
                self._emit(HubEvent(
                    ts=time.time(), kind="translate", mid=mid,
                    summary=f"5002 camera ok={bool(result.get('ok'))}",
                    detail=result,
                ))
            else:
                self._emit(HubEvent(
                    ts=time.time(), kind="rx", mid=mid,
                    summary=f"{mid} received",
                    detail={"keys": list(payload.keys())} if isinstance(payload, dict) else {"value": str(payload)},
                ))
        except Exception as exc:
            self._emit(HubEvent(
                ts=time.time(), kind="error", mid=mid,
                summary=f"translate failed: {type(exc).__name__}: {exc}",
                detail={},
            ))
            logger.exception("translate failed for %s", mid)

    # ── 주기: 0002 heartbeat + 4101 camera ──────────────────
    def _periodic_loop(self) -> None:
        last_status_ts = 0.0
        last_camera_ts = 0.0
        while not self._stop_event.is_set():
            now = time.time()
            # 0002 Module Status 1 Hz (기본)
            status_period = 1.0 / max(0.1, float(self._streaming.module_status_hz))
            if now - last_status_ts >= status_period:
                last_status_ts = now
                # MSG 0002 ICD 는 status=1 만 허용한다.
                # AirSim 연결 상태는 VM 내부 state/UI 로 별도 노출하고, heartbeat 는
                # "모듈 프로세스가 살아 있음"만 보고 정상 코드로 보낸다.
                connected = self._bridge.ping() if self._bridge.status().host else False
                status_code = 1
                res = self._io.send_module_status(status_code)
                self._emit(HubEvent(
                    ts=now, kind="tx", mid="0002",
                    summary=f"0002 → status={status_code} airsim_connected={connected}",
                    detail=res,
                ))

            # 4101 Camera Image (선택)
            if self._streaming.camera_enabled:
                cam_period = 1.0 / max(0.1, float(self._streaming.camera_hz))
                if now - last_camera_ts >= cam_period:
                    last_camera_ts = now
                    self._capture_and_send_camera()

            if self._stop_event.wait(timeout=0.05):
                break

    def _capture_and_send_camera(self) -> None:
        now = time.time()
        cfg = self._streaming
        data, meta = self._bridge.capture_camera_frame(
            camera_name=cfg.camera_name,
            image_type=cfg.camera_image_type,
            vehicle_name=cfg.camera_vehicle,
            quality=cfg.camera_quality,
        )
        if not data:
            self._emit(HubEvent(
                ts=now, kind="error", mid="4101",
                summary=f"camera capture failed: {meta.get('error')}",
                detail=meta,
            ))
            return
        from datetime import datetime, timezone
        iso = datetime.fromtimestamp(now, tz=timezone.utc)
        iso_ts = iso.strftime("%Y-%m-%dT%H:%M:%S.") + f"{iso.microsecond // 1000:03d}Z"
        header = {
            "message_id": 4101,
            "message_name": "Camera Image Frame",
            "timestamp": iso_ts,
            "vehicle_id": cfg.camera_vehicle or "UAM0001",
            "camera_name": cfg.camera_name,
            "image_type": cfg.camera_image_type,
            "sequence": int(now * 1000) & 0xFFFFFFFF,
            "width": 0,
            "height": 0,
            "channels": 3,
            "pixel_format": "jpeg",
            "encoding": "jpeg",
            "payload_size": len(data),
        }
        res = self._io.send_camera_image(header, data)
        self._emit(HubEvent(
            ts=now, kind="tx", mid="4101",
            summary=f"4101 → {len(data)} B",
            detail=res,
        ))

    # ── 외부 제어 API ────────────────────────────────────────
    def launch_unreal(self) -> Dict[str, Any]:
        with self._lock:
            if self._unreal_proc is not None and self._unreal_proc.poll() is None:
                return self.unreal_status()

            if _is_tcp_port_open(self._config.airsim.host, self._config.airsim.port):
                status = self.unreal_status()
                status["ok"] = True
                status["running"] = True
                status["external_runtime"] = True
                status["message"] = "AirSim RPC is already available; reusing the existing Unreal runtime."
                self._emit(HubEvent(
                    ts=time.time(), kind="airsim", mid="",
                    summary="Unreal launch skipped: existing AirSim RPC runtime detected",
                    detail=status,
                ))
                return status

            executable = self._resolve_unreal_executable()
            if executable is None:
                status = self.unreal_status()
                status["ok"] = False
                status["error"] = "DTAMVisualization.exe not found"
                self._emit(HubEvent(
                    ts=time.time(), kind="error", mid="",
                    summary="Unreal launch failed: executable not found",
                    detail=status,
                ))
                return status

            working_dir = self._resolve_unreal_working_dir(executable)
            args = [str(executable), *[str(item) for item in self._config.unreal.args]]
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            self._unreal_proc = subprocess.Popen(
                args,
                cwd=str(working_dir),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            status = self.unreal_status()
            status["ok"] = True
            self._emit(HubEvent(
                ts=time.time(), kind="airsim", mid="",
                summary=f"Unreal launch pid={status.get('pid')}",
                detail=status,
            ))
            return status

    def _terminate_unreal_process(self) -> None:
        with self._lock:
            process = self._unreal_proc
            self._unreal_proc = None
        if process is None or process.poll() is not None:
            return
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=8.0,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
            return
        process.terminate()
        try:
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2.0)

    def unreal_status(self) -> Dict[str, Any]:
        process = self._unreal_proc
        exit_code = process.poll() if process is not None else None
        own_running = bool(process is not None and exit_code is None)
        external_runtime = not own_running and _is_tcp_port_open(self._config.airsim.host, self._config.airsim.port)
        executable = self._resolve_unreal_executable()
        return {
            "running": own_running or external_runtime,
            "pid": process.pid if own_running else None,
            "exit_code": exit_code,
            "executable": str(executable) if executable is not None else "",
            "args": [str(item) for item in self._config.unreal.args],
            "external_runtime": external_runtime,
            "airsim_rpc": {
                "host": self._config.airsim.host,
                "port": self._config.airsim.port,
                "open": own_running or external_runtime,
            },
        }

    def _resolve_unreal_executable(self) -> Optional[Path]:
        configured = str(self._config.unreal.executable or "").strip()
        candidates: List[Path] = []
        if configured:
            configured_path = Path(configured).expanduser()
            if configured_path.is_file():
                return configured_path.resolve()

        candidates.extend([
            ROOT_DIR / "Unreal" / "Environments" / "DTAMVisualization" / "Saved" / "StagedBuilds" / "Windows" / "DTAMVisualization.exe",
            ROOT_DIR / "Unreal" / "Environments" / "DTAMVisualization" / "Binaries" / "Win64" / "DTAMVisualization.exe",
        ])
        existing = [path.resolve() for path in candidates if path.is_file()]
        if not existing:
            return None

        def _priority(path: Path) -> tuple[float, int]:
            resolved = str(path)
            if "\\Binaries\\Win64\\" in resolved:
                category = 0
            elif "\\Saved\\StagedBuilds\\Windows\\" in resolved:
                category = 1
            else:
                category = 2
            return (-path.stat().st_mtime, category)

        return min(existing, key=_priority)

    def _resolve_unreal_working_dir(self, executable: Path) -> Path:
        configured = str(self._config.unreal.working_dir or "").strip()
        if configured:
            return Path(configured).expanduser()

        resolved = str(executable.resolve())
        if "\\Binaries\\Win64\\" in resolved:
            return ROOT_DIR / "Unreal" / "Environments" / "DTAMVisualization"
        return executable.parent

    def connect_airsim(self, host: Optional[str] = None, port: Optional[int] = None) -> Dict[str, Any]:
        status = self._bridge.connect(host=host, port=port)
        self._emit(HubEvent(
            ts=time.time(), kind="airsim", mid="",
            summary=f"AirSim connect → {status.host}:{status.port} ok={status.connected}",
            detail=status.to_dict(),
        ))
        return status.to_dict()

    def disconnect_airsim(self) -> Dict[str, Any]:
        status = self._bridge.disconnect()
        return status.to_dict()

    def reconfigure_dtam(self, **kwargs: Any) -> Dict[str, Any]:
        ep = self._io.reconfigure(**kwargs)
        return ep.__dict__

    def update_streaming(
        self,
        *,
        module_status_hz: Optional[float] = None,
        camera_enabled: Optional[bool] = None,
        camera_name: Optional[str] = None,
        camera_image_type: Optional[int] = None,
        camera_hz: Optional[float] = None,
        camera_quality: Optional[int] = None,
        camera_vehicle: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            if module_status_hz is not None:
                self._streaming.module_status_hz = float(module_status_hz)
            if camera_enabled is not None:
                self._streaming.camera_enabled = bool(camera_enabled)
            if camera_name is not None:
                self._streaming.camera_name = str(camera_name)
            if camera_image_type is not None:
                self._streaming.camera_image_type = int(camera_image_type)
            if camera_hz is not None:
                self._streaming.camera_hz = float(camera_hz)
            if camera_quality is not None:
                self._streaming.camera_quality = int(camera_quality)
            if camera_vehicle is not None:
                self._streaming.camera_vehicle = str(camera_vehicle)
            return self._streaming.__dict__.copy()

    def update_vehicle_map(self, mapping: Dict[str, str]) -> Dict[str, str]:
        self._bridge.update_vehicle_map(mapping)
        return self._bridge.get_vehicle_map()

    def list_airsim_vehicles(self) -> Dict[str, Any]:
        catalog = self._bridge.list_vehicles()
        catalog["unreal"] = self.unreal_status()
        return catalog

    def capture_camera_once(self) -> Dict[str, Any]:
        """지금 한 프레임 가져와서 4101 로 송신."""
        self._capture_and_send_camera()
        return {"ok": True}

    # ── 스냅샷 ───────────────────────────────────────────────
    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            events = [e.to_dict() for e in self._events]
        return {
            "started_at": self._started_at,
            "uptime_s": time.time() - self._started_at if self._started_at else 0.0,
            "airsim": self._bridge.status().to_dict(),
            "airsim_config": {
                "host": self._config.airsim.host,
                "port": self._config.airsim.port,
                "vehicle_prefix": self._config.airsim.vehicle_prefix,
                "ignore_collisions": self._config.airsim.ignore_collisions,
                "vehicle_map": self._bridge.get_vehicle_map(),
            },
            "dtam": self._io.stats(),
            "dtam_endpoint": self._io.endpoint().__dict__,
            "streaming": self._streaming.__dict__,
            "unreal": self.unreal_status(),
            "mission_guides": {
                "visible": self._mission_guides_visible,
                "path": str(MISSION_GUIDE_PATH),
                "toggle_key": "U",
            },
            "events": events,
        }

    # ── 이벤트 브로드캐스트 ─────────────────────────────────
    def _emit(self, evt: HubEvent) -> None:
        with self._lock:
            self._events.append(evt)
        hook = self.on_event
        if hook is not None:
            try:
                hook(evt)
            except Exception:
                logger.exception("on_event hook raised")

    def _emit_mission_guides(self, mid: str) -> None:
        if not self._mission_guides_visible:
            result = {"applied": 0, "skipped": 0, "visible": False, "errors": []}
        else:
            result = self._bridge.apply_mission_guides_from_file(MISSION_GUIDE_PATH)
        self._emit(HubEvent(
            ts=time.time(), kind="translate", mid=mid,
            summary=f"mission guide ??simPlotLineStrip x{result.get('applied', 0)}",
            detail=result,
        ))

    def set_mission_guides_visible(self, visible: bool) -> Dict[str, Any]:
        self._mission_guides_visible = bool(visible)
        if self._mission_guides_visible:
            result = self._bridge.apply_mission_guides_from_file(MISSION_GUIDE_PATH)
            action = "show"
        else:
            result = self._bridge.clear_mission_guides()
            action = "hide"
        detail = {"visible": self._mission_guides_visible, **result}
        self._emit(HubEvent(
            ts=time.time(),
            kind="airsim" if not result.get("errors") else "error",
            mid="mission-guide",
            summary=f"mission guide {action}",
            detail=detail,
        ))
        return detail

    def toggle_mission_guides(self) -> Dict[str, Any]:
        return self.set_mission_guides_visible(not self._mission_guides_visible)

    def _poll_mission_guide_toggle(self, now: float) -> None:
        down = _is_key_down(MISSION_GUIDE_TOGGLE_VK)
        if not down:
            self._mission_guide_key_down = False
            return
        if self._mission_guide_key_down or now - self._last_mission_guide_toggle_ts < 0.35:
            return

        self._mission_guide_key_down = True
        self._last_mission_guide_toggle_ts = now
        self.toggle_mission_guides()


def _visualization_manager_control_camera(
    self: VisualizationManager,
    *,
    aircraft_id: str = "",
    camera_name: str,
    vehicle_name: str = "",
    yaw_delta_deg: float = 0.0,
    pitch_delta_deg: float = 0.0,
    focal_length_delta: float = 0.0,
) -> Dict[str, Any]:
    if not str(vehicle_name or "").strip() and str(aircraft_id or "").strip():
        vehicle_name = self._bridge.resolve_vehicle_name(aircraft_id)
    result = self._bridge.adjust_camera_view(
        camera_name=camera_name,
        vehicle_name=vehicle_name,
        yaw_delta_deg=yaw_delta_deg,
        pitch_delta_deg=pitch_delta_deg,
        focal_length_delta=focal_length_delta,
    )
    self._emit(HubEvent(
        ts=time.time(),
        kind="airsim" if result.get("ok") else "error",
        mid="camera-control",
        summary=(
            f"camera {camera_name} yaw={float(yaw_delta_deg):+.1f} "
            f"pitch={float(pitch_delta_deg):+.1f} focal={float(focal_length_delta):+.1f}"
        ),
        detail=result,
    ))
    return result


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _is_key_down(vk_code: int) -> bool:
    try:
        import ctypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        return bool(user32.GetAsyncKeyState(int(vk_code)) & 0x8000)
    except Exception:
        return False


def _is_tcp_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((str(host), int(port)), timeout=0.2):
            return True
    except OSError:
        return False


VisualizationManager.control_camera = _visualization_manager_control_camera


__all__ = ["VisualizationManager", "HubEvent"]
