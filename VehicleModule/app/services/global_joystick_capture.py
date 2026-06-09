"""Global joystick capture for DTAM Air Mobility manual control."""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from ..domain.manual_dynamics import ManualControlInput


os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

try:
    import pygame
except Exception:
    pygame = None


def _clamp_axis(value: float) -> float:
    return max(-1.0, min(1.0, float(value)))


def _apply_deadzone(value: float, deadzone: float) -> float:
    clipped = _clamp_axis(value)
    threshold = max(0.0, min(0.95, float(deadzone)))
    magnitude = abs(clipped)
    if magnitude <= threshold:
        return 0.0
    scaled = (magnitude - threshold) / max(1e-6, 1.0 - threshold)
    return float((1.0 if clipped >= 0.0 else -1.0) * scaled)


def _exp_smooth_axis(current: float, target: float, dt: float, tau: float) -> float:
    if tau <= 1.0e-6:
        return float(target)
    alpha = 1.0 - pow(2.718281828459045, -max(0.0, float(dt)) / float(tau))
    return float(current) + (float(target) - float(current)) * alpha


def _zero_small(value: float, threshold: float) -> float:
    return 0.0 if abs(float(value)) < max(0.0, float(threshold)) else float(value)


def _smooth_input(
    current: ManualControlInput,
    target: ManualControlInput,
    dt: float,
    tau: float,
    zero_threshold: float,
) -> ManualControlInput:
    return ManualControlInput(
        roll=_zero_small(_exp_smooth_axis(current.roll, target.roll, dt, tau), zero_threshold),
        pitch=_zero_small(_exp_smooth_axis(current.pitch, target.pitch, dt, tau), zero_threshold),
        yaw=_zero_small(_exp_smooth_axis(current.yaw, target.yaw, dt, tau), zero_threshold),
        throttle=_zero_small(_exp_smooth_axis(current.throttle, target.throttle, dt, tau), zero_threshold),
    )


def _input_changed(a: ManualControlInput, b: ManualControlInput, epsilon: float) -> bool:
    eps = max(0.0, float(epsilon))
    return any(
        abs(float(left) - float(right)) > eps
        for left, right in (
            (a.roll, b.roll),
            (a.pitch, b.pitch),
            (a.yaw, b.yaw),
            (a.throttle, b.throttle),
        )
    )


def _summarize_dispatch_result(result: object) -> Dict[str, object]:
    """Keep only the useful, JSON-safe part of the VehicleModule input result."""
    if not isinstance(result, dict):
        return {"type": type(result).__name__} if result is not None else {}
    summary: Dict[str, object] = {}
    for key in ("ok", "ignored", "sent", "send_error"):
        if key in result:
            summary[key] = result.get(key)
    payload = result.get("payload")
    if isinstance(payload, dict):
        summary["aircraftId"] = payload.get("aircraftId")
        axes = payload.get("axes")
        if isinstance(axes, dict):
            summary["axes"] = {
                axis: float(axes.get(axis, 0.0) or 0.0)
                for axis in ("roll", "pitch", "yaw", "throttle")
            }
    view_target = result.get("view_target")
    if isinstance(view_target, dict):
        summary["view_target"] = {
            key: view_target.get(key)
            for key in (
                "target",
                "view_vehicle_id",
                "view_airsim_vehicle",
                "expected_mode",
                "actual_mode",
                "explicit_mode",
                "fallback",
                "reason",
                "error",
            )
            if key in view_target
        }
    return summary


@dataclass(frozen=True)
class AxisBinding:
    index: int
    invert: bool = False
    deadzone: float = 0.08


JOYSTICK_AXIS_BINDINGS: Dict[str, AxisBinding] = {
    "roll": AxisBinding(index=0, invert=False, deadzone=0.08),
    "pitch": AxisBinding(index=1, invert=True, deadzone=0.08),
    "yaw": AxisBinding(index=2, invert=False, deadzone=0.10),
    "throttle": AxisBinding(index=3, invert=True, deadzone=0.05),
}

JOYSTICK_HAT_NOTE = {
    "left": "camera rotate left",
    "right": "camera rotate right",
    "up": "camera zoom in",
    "down": "camera zoom out",
}

HAT_REPEAT_INTERVAL_SEC = 0.12
JOYSTICK_AXIS_SMOOTH_TAU_SEC = 0.08
JOYSTICK_AXIS_ZERO_THRESHOLD = 0.012
JOYSTICK_DISPATCH_EPSILON = 0.008


@dataclass
class JoystickCaptureStatus:
    supported: bool
    active: bool = False
    source: str = ""
    poll_hz: float = 60.0
    backend: str = "pygame"
    device_name: str = ""
    device_index: int = -1
    last_error: str = ""
    raw_axes: Dict[str, float] = field(default_factory=dict)
    hats: List[Tuple[int, int]] = field(default_factory=list)
    pressed_buttons: List[int] = field(default_factory=list)
    mapped_input: Dict[str, float] = field(default_factory=dict)
    last_dispatch_result: Dict[str, object] = field(default_factory=dict)
    hat_note: Dict[str, str] = field(default_factory=lambda: dict(JOYSTICK_HAT_NOTE))
    last_hat_action: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "supported": bool(self.supported),
            "active": bool(self.active),
            "source": str(self.source),
            "poll_hz": float(self.poll_hz),
            "backend": str(self.backend),
            "device_name": str(self.device_name),
            "device_index": int(self.device_index),
            "last_error": str(self.last_error or ""),
            "raw_axes": {key: float(value) for key, value in (self.raw_axes or {}).items()},
            "hats": [list(item) for item in (self.hats or [])],
            "pressed_buttons": [int(item) for item in (self.pressed_buttons or [])],
            "mapped_input": {key: float(value) for key, value in (self.mapped_input or {}).items()},
            "last_dispatch_result": dict(self.last_dispatch_result or {}),
            "hat_note": dict(self.hat_note or {}),
            "last_hat_action": str(self.last_hat_action or ""),
        }


class GlobalJoystickCapture:
    """Poll a joystick and feed normalized manual input into the AM service."""

    def __init__(
        self,
        on_input: Callable[[dict[str, float]], object],
        *,
        on_hat_action: Optional[Callable[[str], object]] = None,
        poll_hz: float = 60.0,
        hat_repeat_sec: float = HAT_REPEAT_INTERVAL_SEC,
        preferred_name: str = "T.16000M",
    ) -> None:
        self._on_input = on_input
        self._on_hat_action = on_hat_action
        self._poll_hz = max(5.0, float(poll_hz))
        self._hat_repeat_sec = max(0.05, float(hat_repeat_sec))
        self._preferred_name = str(preferred_name or "").strip()
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_input = ManualControlInput()
        self._filtered_input = ManualControlInput()
        self._last_poll_ts = 0.0
        self._last_push_ts = 0.0
        self._repeat_interval_s = 0.12
        self._last_hat_action = ""
        self._last_hat_dispatch_ts = 0.0
        self._joystick = None
        self._status = JoystickCaptureStatus(
            supported=(os.name == "nt" and pygame is not None),
            active=False,
            source="pygame-joystick" if (os.name == "nt" and pygame is not None) else "unsupported",
            poll_hz=self._poll_hz,
            backend="pygame",
            device_name="",
            device_index=-1,
            last_error="",
            raw_axes={},
            hats=[],
            pressed_buttons=[],
            mapped_input=self._last_input.to_dict(),
            last_dispatch_result={},
            last_hat_action="",
        )

    def start(self) -> JoystickCaptureStatus:
        with self._lock:
            if not self._status.supported or pygame is None:
                self._status.active = False
                self._status.last_error = "pygame joystick capture is unavailable on this platform"
                return self.status()
            if self._thread is not None and self._thread.is_alive():
                self._status.active = True
                self._status.last_error = ""
                return self.status()

            self._initialize_joystick()
            if self._joystick is None:
                self._status.active = False
                if not self._status.last_error:
                    self._status.last_error = "No joystick detected"
                return self.status()

            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._loop,
                name="dtam-airmobility-joystick",
                daemon=True,
            )
            self._status.active = True
            self._status.last_error = ""
            self._status.last_hat_action = ""
            self._last_hat_action = ""
            self._last_hat_dispatch_ts = 0.0
            self._filtered_input = ManualControlInput()
            self._last_poll_ts = 0.0
            self._thread.start()
            self._push_input(ManualControlInput())
            return self.status()

    def stop(self) -> JoystickCaptureStatus:
        thread: Optional[threading.Thread] = None
        with self._lock:
            self._status.active = False
            self._status.last_hat_action = ""
            self._stop_event.set()
            thread = self._thread
            self._thread = None
            self._last_hat_action = ""
            self._last_hat_dispatch_ts = 0.0
            self._filtered_input = ManualControlInput()
            self._last_poll_ts = 0.0
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.5)
        self._shutdown_joystick()
        self._push_input(ManualControlInput())
        return self.status()

    def status(self) -> JoystickCaptureStatus:
        with self._lock:
            return JoystickCaptureStatus(
                supported=bool(self._status.supported),
                active=bool(self._status.active),
                source=str(self._status.source),
                poll_hz=float(self._status.poll_hz),
                backend=str(self._status.backend),
                device_name=str(self._status.device_name),
                device_index=int(self._status.device_index),
                last_error=str(self._status.last_error),
                raw_axes=dict(self._status.raw_axes),
                hats=list(self._status.hats),
                pressed_buttons=list(self._status.pressed_buttons),
                mapped_input=dict(self._status.mapped_input),
                last_dispatch_result=dict(self._status.last_dispatch_result),
                hat_note=dict(self._status.hat_note),
                last_hat_action=str(self._status.last_hat_action),
            )

    def _initialize_joystick(self) -> None:
        if pygame is None:
            return
        if not pygame.get_init():
            pygame.init()
        if not pygame.joystick.get_init():
            pygame.joystick.init()
        try:
            pygame.event.pump()
        except Exception:
            pass

        joystick = self._select_joystick()
        if joystick is None:
            self._status.device_name = ""
            self._status.device_index = -1
            self._status.last_error = "No joystick detected"
            self._joystick = None
            return

        joystick.init()
        self._joystick = joystick
        self._status.device_name = str(joystick.get_name() or "")
        self._status.device_index = int(joystick.get_id())
        self._status.last_error = ""

    def _shutdown_joystick(self) -> None:
        joystick = self._joystick
        self._joystick = None
        if joystick is not None:
            try:
                joystick.quit()
            except Exception:
                pass
        if pygame is not None:
            try:
                if pygame.joystick.get_init():
                    pygame.joystick.quit()
            except Exception:
                pass
            try:
                if pygame.get_init():
                    pygame.quit()
            except Exception:
                pass

    def _select_joystick(self):
        if pygame is None:
            return None
        total = int(pygame.joystick.get_count())
        if total <= 0:
            return None

        preferred = self._preferred_name.lower()
        first_available = None
        for device_index in range(total):
            joystick = pygame.joystick.Joystick(device_index)
            if first_available is None:
                first_available = joystick
            name = str(joystick.get_name() or "").lower()
            if preferred and preferred in name:
                return joystick
        return first_available

    def _loop(self) -> None:
        interval = 1.0 / self._poll_hz
        while not self._stop_event.is_set():
            try:
                raw_command, raw_axes, hats, pressed_buttons = self._read_input()
                hat_action = self._resolve_hat_action(hats)
                hat_error = self._dispatch_hat_action(hat_action)
                now = time.monotonic()
                raw_dt = interval if self._last_poll_ts <= 0.0 else max(0.0, now - self._last_poll_ts)
                dt = min(raw_dt, interval * 1.5)
                self._last_poll_ts = now
                command = _smooth_input(
                    self._filtered_input,
                    raw_command,
                    dt,
                    JOYSTICK_AXIS_SMOOTH_TAU_SEC,
                    JOYSTICK_AXIS_ZERO_THRESHOLD,
                )
                self._filtered_input = command
                if _input_changed(command, self._last_input, JOYSTICK_DISPATCH_EPSILON) or now - self._last_push_ts >= self._repeat_interval_s:
                    self._push_input(command)
                with self._lock:
                    self._status.last_error = str(hat_error or "")
                    self._status.raw_axes = raw_axes
                    self._status.hats = hats
                    self._status.pressed_buttons = pressed_buttons
                    self._status.mapped_input = command.to_dict()
                    self._status.last_hat_action = hat_action
            except Exception as exc:
                with self._lock:
                    self._status.last_error = f"{type(exc).__name__}: {exc}"
            if self._stop_event.wait(interval):
                break

    def _read_input(self) -> tuple[ManualControlInput, Dict[str, float], List[Tuple[int, int]], List[int]]:
        joystick = self._joystick
        if joystick is None:
            raise RuntimeError("Joystick is not initialized")
        if pygame is None:
            raise RuntimeError("pygame is unavailable")

        pygame.event.pump()

        raw_axes = {
            f"axis_{axis_index}": float(joystick.get_axis(axis_index))
            for axis_index in range(int(joystick.get_numaxes()))
        }
        hats = [
            (int(values[0]), int(values[1]))
            for values in (joystick.get_hat(hat_index) for hat_index in range(int(joystick.get_numhats())))
        ]
        pressed_buttons = [
            int(button_index)
            for button_index in range(int(joystick.get_numbuttons()))
            if joystick.get_button(button_index)
        ]

        mapped = {}
        for key, binding in JOYSTICK_AXIS_BINDINGS.items():
            raw_value = raw_axes.get(f"axis_{binding.index}", 0.0)
            shaped = _apply_deadzone(raw_value, binding.deadzone)
            mapped[key] = -shaped if binding.invert else shaped

        command = ManualControlInput(
            roll=_clamp_axis(mapped.get("roll", 0.0)),
            pitch=_clamp_axis(mapped.get("pitch", 0.0)),
            yaw=_clamp_axis(mapped.get("yaw", 0.0)),
            throttle=_clamp_axis(mapped.get("throttle", 0.0)),
        )
        return command, raw_axes, hats, pressed_buttons

    def _push_input(self, command: ManualControlInput) -> None:
        payload = command.to_dict()
        payload["active"] = any(
            abs(float(value)) > 1.0e-6
            for value in (command.roll, command.pitch, command.yaw, command.throttle)
        )
        result = self._on_input(payload)
        with self._lock:
            self._status.last_dispatch_result = _summarize_dispatch_result(result)
        self._last_input = ManualControlInput(
            roll=float(command.roll),
            pitch=float(command.pitch),
            yaw=float(command.yaw),
            throttle=float(command.throttle),
        )
        self._last_push_ts = time.monotonic()

    def _resolve_hat_action(self, hats: List[Tuple[int, int]]) -> str:
        for x_value, y_value in hats:
            if x_value < 0:
                return "left"
            if x_value > 0:
                return "right"
            if y_value > 0:
                return "up"
            if y_value < 0:
                return "down"
        return ""

    def _dispatch_hat_action(self, action: str) -> str:
        if not action:
            self._last_hat_action = ""
            self._last_hat_dispatch_ts = 0.0
            return ""
        if self._on_hat_action is None:
            self._last_hat_action = action
            return ""

        now = time.monotonic()
        should_dispatch = (
            action != self._last_hat_action
            or (now - self._last_hat_dispatch_ts) >= self._hat_repeat_sec
        )
        self._last_hat_action = action
        if not should_dispatch:
            return ""

        try:
            self._on_hat_action(action)
            self._last_hat_dispatch_ts = now
            return ""
        except Exception as exc:
            self._last_hat_dispatch_ts = now
            return f"hat {action}: {type(exc).__name__}: {exc}"


__all__ = [
    "GlobalJoystickCapture",
    "JoystickCaptureStatus",
    "JOYSTICK_AXIS_BINDINGS",
    "JOYSTICK_HAT_NOTE",
    "HAT_REPEAT_INTERVAL_SEC",
]

