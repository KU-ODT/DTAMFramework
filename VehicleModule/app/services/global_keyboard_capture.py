"""Windows global keyboard capture for DTAM Air Mobility.

This module polls GetAsyncKeyState so operator input can keep driving the
manual dynamics even when the Air Mobility browser tab is not focused.
"""

from __future__ import annotations

import ctypes
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from ..domain.manual_dynamics import ManualControlInput


_VK_A = 0x41
_VK_D = 0x44
_VK_W = 0x57
_VK_S = 0x53
_VK_Q = 0x51
_VK_E = 0x45
_VK_SPACE = 0x20
_VK_SHIFT = 0x10
_VK_LSHIFT = 0xA0
_VK_RSHIFT = 0xA1


def _clamp_axis(value: float) -> float:
    return max(-1.0, min(1.0, float(value)))


def _summarize_dispatch_result(result: object) -> dict[str, object]:
    if not isinstance(result, dict):
        return {"type": type(result).__name__} if result is not None else {}
    summary: dict[str, object] = {}
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


@dataclass
class KeyboardCaptureStatus:
    supported: bool
    active: bool = False
    source: str = ""
    poll_hz: float = 60.0
    last_error: str = ""
    mapped_input: dict[str, float] = field(default_factory=dict)
    last_dispatch_result: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "supported": bool(self.supported),
            "active": bool(self.active),
            "source": str(self.source),
            "poll_hz": float(self.poll_hz),
            "last_error": str(self.last_error or ""),
            "mapped_input": {key: float(value) for key, value in (self.mapped_input or {}).items()},
            "last_dispatch_result": dict(self.last_dispatch_result or {}),
        }


class GlobalKeyboardCapture:
    """Poll Windows global keyboard state and feed normalized manual input."""

    def __init__(
        self,
        on_input: Callable[[dict[str, float]], object],
        *,
        poll_hz: float = 60.0,
    ) -> None:
        self._on_input = on_input
        self._poll_hz = max(5.0, float(poll_hz))
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_input = ManualControlInput()
        self._last_push_ts = 0.0
        self._repeat_interval_s = 0.20
        self._status = KeyboardCaptureStatus(
            supported=(os.name == "nt"),
            active=False,
            source="windows-global" if os.name == "nt" else "unsupported",
            poll_hz=self._poll_hz,
            last_error="",
            mapped_input=self._last_input.to_dict(),
            last_dispatch_result={},
        )
        self._user32 = ctypes.windll.user32 if os.name == "nt" else None

    def start(self) -> KeyboardCaptureStatus:
        with self._lock:
            if not self._status.supported or self._user32 is None:
                self._status.active = False
                self._status.last_error = "Windows global keyboard capture is unsupported on this platform"
                return self.status()
            if self._thread is not None and self._thread.is_alive():
                self._status.active = True
                self._status.last_error = ""
                return self.status()

            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._loop,
                name="dtam-airmobility-keyboard",
                daemon=True,
            )
            self._status.active = True
            self._status.last_error = ""
            self._thread.start()
            self._push_input(ManualControlInput())
            return self.status()

    def stop(self) -> KeyboardCaptureStatus:
        thread: Optional[threading.Thread] = None
        with self._lock:
            self._status.active = False
            self._stop_event.set()
            thread = self._thread
            self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.5)
        self._push_input(ManualControlInput())
        return self.status()

    def status(self) -> KeyboardCaptureStatus:
        with self._lock:
            return KeyboardCaptureStatus(**self._status.__dict__)

    def _loop(self) -> None:
        interval = 1.0 / self._poll_hz
        while not self._stop_event.is_set():
            try:
                current = self._read_input()
                now = time.monotonic()
                if current != self._last_input or now - self._last_push_ts >= self._repeat_interval_s:
                    self._push_input(current)
                with self._lock:
                    self._status.last_error = ""
                    self._status.mapped_input = current.to_dict()
            except Exception as exc:
                with self._lock:
                    self._status.last_error = f"{type(exc).__name__}: {exc}"
            if self._stop_event.wait(interval):
                break

    def _read_input(self) -> ManualControlInput:
        return ManualControlInput(
            roll=_clamp_axis(float(self._is_pressed(_VK_D)) - float(self._is_pressed(_VK_A))),
            pitch=_clamp_axis(float(self._is_pressed(_VK_W)) - float(self._is_pressed(_VK_S))),
            yaw=_clamp_axis(float(self._is_pressed(_VK_E)) - float(self._is_pressed(_VK_Q))),
            throttle=_clamp_axis(
                float(self._is_pressed(_VK_SPACE))
                - float(
                    self._is_pressed(_VK_SHIFT)
                    or self._is_pressed(_VK_LSHIFT)
                    or self._is_pressed(_VK_RSHIFT)
                )
            ),
        )

    def _push_input(self, command: ManualControlInput) -> None:
        payload = command.__dict__.copy()
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

    def _is_pressed(self, virtual_key: int) -> bool:
        if self._user32 is None:
            return False
        return bool(self._user32.GetAsyncKeyState(int(virtual_key)) & 0x8000)


__all__ = ["GlobalKeyboardCapture", "KeyboardCaptureStatus"]

