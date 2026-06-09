from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import sys
import time
import tkinter as tk
from tkinter import filedialog, ttk


os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

try:
    import pygame
except Exception:
    pygame = None


FRAMEWORK_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_DIR = FRAMEWORK_ROOT / ".dtam_runtime" / "joystick_tests"

MAXPNAMELEN = 32
JOYCAPS_HASPOV = 0x0001
JOY_RETURNX = 0x00000001
JOY_RETURNY = 0x00000002
JOY_RETURNZ = 0x00000004
JOY_RETURNR = 0x00000008
JOY_RETURNU = 0x00000010
JOY_RETURNV = 0x00000020
JOY_RETURNPOV = 0x00000040
JOY_RETURNBUTTONS = 0x00000080
JOY_RETURNALL = (
    JOY_RETURNX
    | JOY_RETURNY
    | JOY_RETURNZ
    | JOY_RETURNR
    | JOY_RETURNU
    | JOY_RETURNV
    | JOY_RETURNPOV
    | JOY_RETURNBUTTONS
)
JOY_POVCENTERED = 0xFFFF
JOYERR_NOERROR = 0

WINMM_AXIS_ORDER = (
    ("X", "dwXpos", "wXmin", "wXmax"),
    ("Y", "dwYpos", "wYmin", "wYmax"),
    ("Z", "dwZpos", "wZmin", "wZmax"),
    ("R", "dwRpos", "wRmin", "wRmax"),
    ("U", "dwUpos", "wUmin", "wUmax"),
    ("V", "dwVpos", "wVmin", "wVmax"),
)
WINMM_AXIS_LABELS = {
    "X": "Axis X",
    "Y": "Axis Y",
    "Z": "Axis Z",
    "R": "Axis R",
    "U": "Axis U",
    "V": "Axis V",
}

BACKEND_AUTO = "auto"
BACKEND_PYGAME = "pygame"
BACKEND_WINMM = "winmm"
BACKEND_CHOICES = (BACKEND_AUTO, BACKEND_PYGAME, BACKEND_WINMM)


class JOYCAPSW(ctypes.Structure):
    _fields_ = [
        ("wMid", wintypes.WORD),
        ("wPid", wintypes.WORD),
        ("szPname", wintypes.WCHAR * MAXPNAMELEN),
        ("wXmin", wintypes.UINT),
        ("wXmax", wintypes.UINT),
        ("wYmin", wintypes.UINT),
        ("wYmax", wintypes.UINT),
        ("wZmin", wintypes.UINT),
        ("wZmax", wintypes.UINT),
        ("wNumButtons", wintypes.UINT),
        ("wPeriodMin", wintypes.UINT),
        ("wPeriodMax", wintypes.UINT),
        ("wRmin", wintypes.UINT),
        ("wRmax", wintypes.UINT),
        ("wUmin", wintypes.UINT),
        ("wUmax", wintypes.UINT),
        ("wVmin", wintypes.UINT),
        ("wVmax", wintypes.UINT),
        ("wCaps", wintypes.UINT),
        ("wMaxAxes", wintypes.UINT),
        ("wNumAxes", wintypes.UINT),
        ("wMaxButtons", wintypes.UINT),
        ("szRegKey", wintypes.WCHAR * MAXPNAMELEN),
        ("szOEMVxD", wintypes.WCHAR * MAXPNAMELEN),
    ]


class JOYINFOEX(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("dwXpos", wintypes.DWORD),
        ("dwYpos", wintypes.DWORD),
        ("dwZpos", wintypes.DWORD),
        ("dwRpos", wintypes.DWORD),
        ("dwUpos", wintypes.DWORD),
        ("dwVpos", wintypes.DWORD),
        ("dwButtons", wintypes.DWORD),
        ("dwButtonNumber", wintypes.DWORD),
        ("dwPOV", wintypes.DWORD),
        ("dwReserved1", wintypes.DWORD),
        ("dwReserved2", wintypes.DWORD),
    ]


winmm = ctypes.WinDLL("winmm")
joyGetNumDevs = winmm.joyGetNumDevs
joyGetNumDevs.restype = wintypes.UINT

joyGetDevCapsW = winmm.joyGetDevCapsW
joyGetDevCapsW.argtypes = [wintypes.UINT, ctypes.POINTER(JOYCAPSW), wintypes.UINT]
joyGetDevCapsW.restype = wintypes.UINT

joyGetPosEx = winmm.joyGetPosEx
joyGetPosEx.argtypes = [wintypes.UINT, ctypes.POINTER(JOYINFOEX)]
joyGetPosEx.restype = wintypes.UINT


@dataclass
class AxisState:
    raw: int | float
    normalized: float


@dataclass
class JoystickSnapshot:
    axes: dict[str, AxisState]
    buttons: list[bool]
    hats: list[tuple[int, int]]


@dataclass
class JoystickDevice:
    device_id: int
    name: str
    backend: str
    axis_ids: list[str]
    axis_labels: dict[str, str]
    axis_ranges: dict[str, tuple[int, int]]
    num_buttons: int
    num_hats: int

    @property
    def num_axes(self) -> int:
        return len(self.axis_ids)


@dataclass(frozen=True)
class GuidedStep:
    key: str
    kind: str
    slot: str
    action: str
    instruction: str
    expected_hat: tuple[int, int] | None = None


GUIDED_STEPS = (
    GuidedStep("roll_left", "axis", "roll", "left", "1/14 Roll: move the stick fully left and hold it."),
    GuidedStep("roll_right", "axis", "roll", "right", "2/14 Roll: move the stick fully right and hold it."),
    GuidedStep("pitch_forward", "axis", "pitch", "forward", "3/14 Pitch: push the stick forward and hold it."),
    GuidedStep("pitch_back", "axis", "pitch", "back", "4/14 Pitch: pull the stick back and hold it."),
    GuidedStep("yaw_left", "axis", "yaw", "left", "5/14 Yaw: twist the stick left and hold it."),
    GuidedStep("yaw_right", "axis", "yaw", "right", "6/14 Yaw: twist the stick right and hold it."),
    GuidedStep("throttle_up", "axis", "throttle", "up", "7/14 Throttle: move the throttle up and hold it."),
    GuidedStep("throttle_down", "axis", "throttle", "down", "8/14 Throttle: move the throttle down and hold it."),
    GuidedStep("button_primary", "button", "button", "primary", "9/14 Button: press the first button you want to use."),
    GuidedStep("button_secondary", "button", "button", "secondary", "10/14 Button: press the second button you want to use."),
    GuidedStep("hat_up", "hat", "hat", "up", "11/14 Hat: push the POV / hat switch up.", expected_hat=(0, 1)),
    GuidedStep("hat_down", "hat", "hat", "down", "12/14 Hat: push the POV / hat switch down.", expected_hat=(0, -1)),
    GuidedStep("hat_left", "hat", "hat", "left", "13/14 Hat: push the POV / hat switch left.", expected_hat=(-1, 0)),
    GuidedStep("hat_right", "hat", "hat", "right", "14/14 Hat: push the POV / hat switch right.", expected_hat=(1, 0)),
)


def normalize_axis(raw: float, minimum: float, maximum: float) -> float:
    if maximum <= minimum:
        return 0.0
    midpoint = minimum + (maximum - minimum) / 2.0
    half_range = (maximum - minimum) / 2.0
    if half_range <= 0.0:
        return 0.0
    normalized = (raw - midpoint) / half_range
    return max(-1.0, min(1.0, normalized))


def format_raw_value(value: int | float) -> str:
    if isinstance(value, int):
        return str(value)
    return f"{float(value):+.3f}"


def hat_to_text(hat_value: tuple[int, int]) -> str:
    x_value, y_value = hat_value
    if x_value == 0 and y_value == 0:
        return "Centered"

    parts: list[str] = []
    if y_value > 0:
        parts.append("Up")
    elif y_value < 0:
        parts.append("Down")

    if x_value > 0:
        parts.append("Right")
    elif x_value < 0:
        parts.append("Left")

    return "-".join(parts) if parts else f"{hat_value}"


def pov_to_hat(pov: int) -> tuple[int, int]:
    if pov == JOY_POVCENTERED:
        return (0, 0)
    mapping = {
        0: (0, 1),
        4500: (1, 1),
        9000: (1, 0),
        13500: (1, -1),
        18000: (0, -1),
        22500: (-1, -1),
        27000: (-1, 0),
        31500: (-1, 1),
    }
    return mapping.get(int(pov), (0, 0))


def ensure_pygame_initialized() -> bool:
    if pygame is None:
        return False
    if not pygame.get_init():
        pygame.init()
    if not pygame.joystick.get_init():
        pygame.joystick.init()
    return True


def enumerate_pygame_joysticks() -> list[JoystickDevice]:
    if not ensure_pygame_initialized():
        return []

    devices: list[JoystickDevice] = []
    try:
        pygame.event.pump()
    except Exception:
        pass

    total = int(pygame.joystick.get_count())
    for device_id in range(total):
        joystick = pygame.joystick.Joystick(device_id)
        joystick.init()
        axis_ids = [f"axis_{axis_index}" for axis_index in range(int(joystick.get_numaxes()))]
        devices.append(
            JoystickDevice(
                device_id=device_id,
                name=joystick.get_name() or f"Joystick {device_id}",
                backend=BACKEND_PYGAME,
                axis_ids=axis_ids,
                axis_labels={axis_id: f"Axis {axis_index}" for axis_index, axis_id in enumerate(axis_ids)},
                axis_ranges={},
                num_buttons=int(joystick.get_numbuttons()),
                num_hats=int(joystick.get_numhats()),
            )
        )
    return devices


def enumerate_winmm_joysticks() -> list[JoystickDevice]:
    devices: list[JoystickDevice] = []
    total = int(joyGetNumDevs())
    for device_id in range(total):
        caps = JOYCAPSW()
        result = int(joyGetDevCapsW(device_id, ctypes.byref(caps), ctypes.sizeof(caps)))
        if result != JOYERR_NOERROR:
            continue

        axis_ids = [axis_name for axis_name, _, _, _ in WINMM_AXIS_ORDER[: int(caps.wNumAxes)]]
        axis_ranges = {
            axis_name: (int(getattr(caps, minimum_name)), int(getattr(caps, maximum_name)))
            for axis_name, _, minimum_name, maximum_name in WINMM_AXIS_ORDER
        }
        devices.append(
            JoystickDevice(
                device_id=device_id,
                name=caps.szPname.strip() or f"Joystick {device_id}",
                backend=BACKEND_WINMM,
                axis_ids=axis_ids,
                axis_labels={axis_id: WINMM_AXIS_LABELS.get(axis_id, axis_id) for axis_id in axis_ids},
                axis_ranges=axis_ranges,
                num_buttons=int(caps.wNumButtons),
                num_hats=1 if (int(caps.wCaps) & JOYCAPS_HASPOV) else 0,
            )
        )
    return devices


def enumerate_joysticks(preferred_backend: str = BACKEND_AUTO) -> list[JoystickDevice]:
    if preferred_backend == BACKEND_PYGAME:
        return enumerate_pygame_joysticks()
    if preferred_backend == BACKEND_WINMM:
        return enumerate_winmm_joysticks()

    pygame_devices = enumerate_pygame_joysticks()
    if pygame_devices:
        return pygame_devices
    return enumerate_winmm_joysticks()


def read_pygame_snapshot(device: JoystickDevice) -> JoystickSnapshot:
    if not ensure_pygame_initialized():
        raise RuntimeError("pygame backend is unavailable")

    pygame.event.pump()
    joystick = pygame.joystick.Joystick(device.device_id)
    joystick.init()

    axes: dict[str, AxisState] = {}
    for axis_index, axis_id in enumerate(device.axis_ids):
        raw_value = float(joystick.get_axis(axis_index))
        axes[axis_id] = AxisState(
            raw=raw_value,
            normalized=max(-1.0, min(1.0, raw_value)),
        )

    buttons = [bool(joystick.get_button(button_index)) for button_index in range(device.num_buttons)]
    hats = [tuple(int(value) for value in joystick.get_hat(hat_index)) for hat_index in range(device.num_hats)]
    return JoystickSnapshot(axes=axes, buttons=buttons, hats=hats)


def read_winmm_snapshot(device: JoystickDevice) -> JoystickSnapshot:
    info = JOYINFOEX()
    info.dwSize = ctypes.sizeof(JOYINFOEX)
    info.dwFlags = JOY_RETURNALL
    result = int(joyGetPosEx(device.device_id, ctypes.byref(info)))
    if result != JOYERR_NOERROR:
        raise RuntimeError(f"joyGetPosEx failed for device {device.device_id} with code {result}")

    axes: dict[str, AxisState] = {}
    for axis_name, field_name, _, _ in WINMM_AXIS_ORDER[: device.num_axes]:
        raw_value = int(getattr(info, field_name))
        minimum, maximum = device.axis_ranges[axis_name]
        axes[axis_name] = AxisState(
            raw=raw_value,
            normalized=normalize_axis(float(raw_value), float(minimum), float(maximum)),
        )

    buttons = []
    button_mask = int(info.dwButtons)
    for button_index in range(device.num_buttons):
        buttons.append(bool(button_mask & (1 << button_index)))

    hats = [pov_to_hat(int(info.dwPOV))] if device.num_hats > 0 else []
    return JoystickSnapshot(axes=axes, buttons=buttons, hats=hats)


def read_snapshot(device: JoystickDevice) -> JoystickSnapshot:
    if device.backend == BACKEND_PYGAME:
        return read_pygame_snapshot(device)
    if device.backend == BACKEND_WINMM:
        return read_winmm_snapshot(device)
    raise RuntimeError(f"Unsupported joystick backend: {device.backend}")


class JoystickTesterApp:
    POLL_MS = 50
    AXIS_CHANGE_THRESHOLD = 0.02
    GUIDED_STEP_COOLDOWN_SEC = 1.5
    GUIDED_AXIS_TRIGGER_THRESHOLD = 0.60
    GUIDED_AXIS_CONFIRM_POLLS = 3
    GUIDED_BUTTON_CONFIRM_POLLS = 2
    GUIDED_HAT_CONFIRM_POLLS = 2
    GUIDED_NEUTRAL_AXIS_TOLERANCE = 0.18

    def __init__(self, root: tk.Tk, preferred_backend: str = BACKEND_AUTO) -> None:
        self.root = root
        self.root.title("Joystick Input Tester")
        self.root.geometry("1120x760")
        self.root.minsize(960, 640)

        self.preferred_backend = preferred_backend
        self.devices: list[JoystickDevice] = []
        self.selected_device: JoystickDevice | None = None
        self.previous_snapshot: JoystickSnapshot | None = None
        self.logging_enabled = False
        self.log_file_path: Path | None = None
        self.log_handle = None
        self.capture_armed = False
        self.last_input_event: str | None = None
        self.guided_active = False
        self.guided_step_index = -1
        self.guided_neutral_snapshot: JoystickSnapshot | None = None
        self.guided_axis_bindings: dict[str, dict[str, object]] = {}
        self.guided_button_bindings: dict[str, int] = {}
        self.guided_hat_index: int | None = None
        self.guided_hat_actions: dict[str, tuple[int, int]] = {}
        self.guided_step_cooldown_until = 0.0
        self.guided_waiting_for_neutral = False
        self.guided_axis_candidate: tuple[str, int] | None = None
        self.guided_axis_candidate_count = 0
        self.guided_button_candidate: int | None = None
        self.guided_button_candidate_count = 0
        self.guided_hat_candidate: tuple[int, tuple[int, int]] | None = None
        self.guided_hat_candidate_count = 0

        self.device_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")
        self.log_path_var = tk.StringVar(value="No log file selected")
        self.hint_var = tk.StringVar(value="Move an axis or press a button to record which input changed.")
        self.mapping_note_var = tk.StringVar()
        self.last_input_var = tk.StringVar(value="Last input: -")
        self.capture_status_var = tk.StringVar(value="Type a note, then annotate the last input or arm the next input.")
        self.guided_instruction_var = tk.StringVar(
            value="Guided detect is idle. Center the controls, then start the guided check."
        )
        self.guided_status_var = tk.StringVar(value="Guided detect status will appear here.")
        self.guided_summary_var = tk.StringVar(value="No guided mapping captured yet.")
        self.axis_enabled_flags: dict[str, bool] = {}
        self.axis_toggle_vars: dict[str, tk.StringVar] = {}
        self.axis_rows: dict[str, dict[str, object]] = {}
        self.button_labels: list[tk.Label] = []
        self.hat_vars: list[tk.StringVar] = []

        self._build_ui()
        self.refresh_devices()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(self.POLL_MS, self.poll_inputs)

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        self.root.rowconfigure(2, weight=2)

        top = ttk.Frame(self.root, padding=12)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Joystick").grid(row=0, column=0, sticky="w")
        self.device_combo = ttk.Combobox(top, textvariable=self.device_var, state="readonly")
        self.device_combo.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        self.device_combo.bind("<<ComboboxSelected>>", self.on_device_selected)

        ttk.Button(top, text="Refresh", command=self.refresh_devices).grid(row=0, column=2, padx=(0, 8))
        self.log_button = ttk.Button(top, text="Start Recording", command=self.toggle_logging)
        self.log_button.grid(row=0, column=3)

        ttk.Label(top, textvariable=self.status_var).grid(row=1, column=0, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Label(top, textvariable=self.log_path_var, foreground="#4b5563").grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(4, 0)
        )
        ttk.Label(top, textvariable=self.hint_var, foreground="#1f2937").grid(
            row=3, column=0, columnspan=4, sticky="w", pady=(6, 0)
        )
        ttk.Label(top, text="Mapping note").grid(row=4, column=0, sticky="w", pady=(10, 0))
        self.mapping_note_entry = ttk.Entry(top, textvariable=self.mapping_note_var)
        self.mapping_note_entry.grid(row=4, column=1, sticky="ew", padx=(8, 8), pady=(10, 0))
        ttk.Button(top, text="Annotate Last Input", command=self.annotate_last_input).grid(
            row=4, column=2, padx=(0, 8), pady=(10, 0)
        )
        self.capture_button = ttk.Button(top, text="Arm Next Input", command=self.toggle_capture_arm)
        self.capture_button.grid(row=4, column=3, pady=(10, 0))
        ttk.Label(top, textvariable=self.last_input_var, foreground="#1f2937").grid(
            row=5, column=0, columnspan=4, sticky="w", pady=(6, 0)
        )
        ttk.Label(top, textvariable=self.capture_status_var, foreground="#065f46").grid(
            row=6, column=0, columnspan=4, sticky="w", pady=(4, 0)
        )

        guided_group = ttk.LabelFrame(top, text="Guided Detect", padding=12)
        guided_group.grid(row=7, column=0, columnspan=4, sticky="ew", pady=(12, 0))
        guided_group.columnconfigure(0, weight=1)

        ttk.Label(guided_group, textvariable=self.guided_instruction_var, wraplength=980).grid(
            row=0, column=0, columnspan=4, sticky="w"
        )
        ttk.Label(guided_group, textvariable=self.guided_status_var, foreground="#1d4ed8", wraplength=980).grid(
            row=1, column=0, columnspan=4, sticky="w", pady=(6, 0)
        )
        ttk.Button(guided_group, text="Start Guided Detect", command=self.start_guided_detection).grid(
            row=2, column=0, sticky="w", pady=(10, 0)
        )
        ttk.Button(guided_group, text="Retry Step", command=self.retry_guided_step).grid(
            row=2, column=1, sticky="w", padx=(8, 0), pady=(10, 0)
        )
        ttk.Button(guided_group, text="Skip Step", command=self.skip_guided_step).grid(
            row=2, column=2, sticky="w", padx=(8, 0), pady=(10, 0)
        )
        ttk.Button(guided_group, text="Stop Guided Detect", command=self.stop_guided_detection).grid(
            row=2, column=3, sticky="w", padx=(8, 0), pady=(10, 0)
        )
        ttk.Label(guided_group, textvariable=self.guided_summary_var, wraplength=980, foreground="#374151").grid(
            row=3, column=0, columnspan=4, sticky="w", pady=(10, 0)
        )

        state_frame = ttk.Frame(self.root, padding=(12, 0, 12, 0))
        state_frame.grid(row=1, column=0, sticky="nsew")
        state_frame.columnconfigure(0, weight=3)
        state_frame.columnconfigure(1, weight=2)
        state_frame.rowconfigure(0, weight=1)

        axes_group = ttk.LabelFrame(state_frame, text="Axes", padding=12)
        axes_group.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        axes_group.columnconfigure(0, weight=1)
        axes_group.rowconfigure(0, weight=1)
        self.axes_container = ttk.Frame(axes_group)
        self.axes_container.grid(row=0, column=0, sticky="nsew")

        right_group = ttk.Frame(state_frame)
        right_group.grid(row=0, column=1, sticky="nsew")
        right_group.columnconfigure(0, weight=1)
        right_group.rowconfigure(1, weight=1)

        hats_group = ttk.LabelFrame(right_group, text="Hat / POV", padding=12)
        hats_group.grid(row=0, column=0, sticky="ew")
        hats_group.columnconfigure(0, weight=1)
        self.hats_container = ttk.Frame(hats_group)
        self.hats_container.grid(row=0, column=0, sticky="ew")

        buttons_group = ttk.LabelFrame(right_group, text="Buttons", padding=12)
        buttons_group.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        buttons_group.columnconfigure(0, weight=1)
        self.buttons_container = ttk.Frame(buttons_group)
        self.buttons_container.grid(row=0, column=0, sticky="nsew")

        log_group = ttk.LabelFrame(self.root, text="Event Log", padding=12)
        log_group.grid(row=2, column=0, sticky="nsew", padx=12, pady=12)
        log_group.columnconfigure(0, weight=1)
        log_group.rowconfigure(0, weight=1)

        self.log_text = tk.Text(log_group, wrap="none", height=18)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scroll_y = ttk.Scrollbar(log_group, orient="vertical", command=self.log_text.yview)
        scroll_y.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll_y.set)

    def refresh_devices(self) -> None:
        self.devices = enumerate_joysticks(self.preferred_backend)
        labels = [
            (
                f"{device.name} "
                f"(backend={device.backend}, id={device.device_id}, axes={device.num_axes}, "
                f"buttons={device.num_buttons}, hats={device.num_hats})"
            )
            for device in self.devices
        ]
        self.device_combo["values"] = labels
        if not self.devices:
            self.selected_device = None
            self.device_var.set("")
            self.status_var.set("No joystick detected")
            self._reset_mapping_state()
            self._reset_guided_state()
            self._render_axes(None)
            self._render_hats(0)
            self._render_buttons(0)
            self._clear_state()
            return

        selected_index = 0
        if self.selected_device is not None:
            for index, device in enumerate(self.devices):
                if device.backend == self.selected_device.backend and device.device_id == self.selected_device.device_id:
                    selected_index = index
                    break
        self.device_combo.current(selected_index)
        self.selected_device = self.devices[selected_index]
        self.previous_snapshot = None
        self._reset_mapping_state()
        self._reset_guided_state()
        self._render_axes(self.selected_device)
        self._render_hats(self.selected_device.num_hats)
        self._render_buttons(self.selected_device.num_buttons)
        self.status_var.set(f"Connected: {self.selected_device.name} via {self.selected_device.backend}")
        self.log_event(f"Selected device: {self.selected_device.name} via {self.selected_device.backend}")

    def _render_axes(self, device: JoystickDevice | None) -> None:
        for child in self.axes_container.winfo_children():
            child.destroy()
        self.axis_rows = {}
        self.axis_toggle_vars = {}

        if device is None or not device.axis_ids:
            ttk.Label(self.axes_container, text="No axes detected").grid(row=0, column=0, sticky="w")
            return

        self.axes_container.columnconfigure(1, weight=1)
        self.axes_container.columnconfigure(2, weight=1)
        ttk.Label(self.axes_container, text="Input").grid(row=0, column=0, sticky="w")
        ttk.Label(self.axes_container, text="Raw").grid(row=0, column=1, sticky="w")
        ttk.Label(self.axes_container, text="Normalized").grid(row=0, column=2, sticky="w")
        ttk.Label(self.axes_container, text="State").grid(row=0, column=3, sticky="w")

        for row_index, axis_id in enumerate(device.axis_ids, start=1):
            name_label = ttk.Label(self.axes_container, text=device.axis_labels.get(axis_id, axis_id))
            name_label.grid(
                row=row_index, column=0, sticky="w", pady=2
            )
            raw_label = ttk.Label(self.axes_container, text="-")
            norm_label = ttk.Label(self.axes_container, text="-")
            raw_label.grid(row=row_index, column=1, sticky="w", pady=2)
            norm_label.grid(row=row_index, column=2, sticky="w", pady=2)
            if axis_id not in self.axis_enabled_flags:
                self.axis_enabled_flags[axis_id] = True
            toggle_var = tk.StringVar()
            toggle_button = ttk.Button(
                self.axes_container,
                textvariable=toggle_var,
                command=lambda target_axis_id=axis_id: self.toggle_axis_enabled(target_axis_id),
            )
            toggle_button.grid(row=row_index, column=3, sticky="w", pady=2, padx=(8, 0))
            self.axis_toggle_vars[axis_id] = toggle_var
            self.axis_rows[axis_id] = {
                "name_label": name_label,
                "raw_label": raw_label,
                "norm_label": norm_label,
                "toggle_button": toggle_button,
            }
            self._refresh_axis_row_state(axis_id)

    def _render_hats(self, count: int) -> None:
        for child in self.hats_container.winfo_children():
            child.destroy()
        self.hat_vars = []

        if count <= 0:
            ttk.Label(self.hats_container, text="No hat / POV detected").grid(row=0, column=0, sticky="w")
            return

        for hat_index in range(count):
            hat_var = tk.StringVar(value=f"Hat {hat_index + 1}: Centered")
            ttk.Label(self.hats_container, textvariable=hat_var).grid(row=hat_index, column=0, sticky="w", pady=2)
            self.hat_vars.append(hat_var)

    def _render_buttons(self, count: int) -> None:
        for child in self.buttons_container.winfo_children():
            child.destroy()
        self.button_labels = []
        if count <= 0:
            ttk.Label(self.buttons_container, text="No buttons detected").grid(row=0, column=0, sticky="w")
            return

        columns = 4
        for button_index in range(count):
            label = tk.Label(
                self.buttons_container,
                text=f"Button {button_index + 1}: Released",
                relief="solid",
                padx=8,
                pady=4,
                width=22,
                anchor="w",
                bg="#e5e7eb",
                fg="#111827",
            )
            label.grid(
                row=button_index // columns,
                column=button_index % columns,
                sticky="ew",
                padx=4,
                pady=4,
            )
            self.button_labels.append(label)

    def _is_axis_enabled(self, axis_id: str) -> bool:
        return bool(self.axis_enabled_flags.get(axis_id, True))

    def _refresh_axis_row_state(self, axis_id: str) -> None:
        row = self.axis_rows.get(axis_id)
        if not row:
            return
        is_enabled = self._is_axis_enabled(axis_id)
        toggle_var = self.axis_toggle_vars.get(axis_id)
        if toggle_var is not None:
            toggle_var.set("Ignore" if is_enabled else "Use")

        foreground = "#111827" if is_enabled else "#9ca3af"
        for label_key in ("name_label", "raw_label", "norm_label"):
            label_widget = row.get(label_key)
            if label_widget is not None:
                try:
                    label_widget.configure(foreground=foreground)
                except tk.TclError:
                    pass

    def _remove_axis_from_guided_bindings(self, axis_id: str) -> None:
        removed_slots = [
            slot_name
            for slot_name, binding in self.guided_axis_bindings.items()
            if str(binding.get("axis_id")) == axis_id
        ]
        for slot_name in removed_slots:
            self.guided_axis_bindings.pop(slot_name, None)
        if removed_slots:
            self.guided_summary_var.set(self._build_guided_summary())

    def toggle_axis_enabled(self, axis_id: str) -> None:
        new_state = not self._is_axis_enabled(axis_id)
        self.axis_enabled_flags[axis_id] = new_state
        self._refresh_axis_row_state(axis_id)
        if not new_state:
            self._remove_axis_from_guided_bindings(axis_id)
            self.log_event(f"Axis ignored: {self._axis_display_name(axis_id)}")
            self.guided_status_var.set(f"{self._axis_display_name(axis_id)} is now ignored.")
        else:
            self.log_event(f"Axis enabled: {self._axis_display_name(axis_id)}")
            self.guided_status_var.set(f"{self._axis_display_name(axis_id)} is active again.")

    def _clear_state(self) -> None:
        for axis_id, row in self.axis_rows.items():
            raw_label = row.get("raw_label")
            norm_label = row.get("norm_label")
            if raw_label is not None:
                raw_label.configure(text="-")
            if norm_label is not None:
                norm_label.configure(text="-")
            self._refresh_axis_row_state(axis_id)
        for hat_index, hat_var in enumerate(self.hat_vars, start=1):
            hat_var.set(f"Hat {hat_index}: Centered")
        for button_index, button_label in enumerate(self.button_labels, start=1):
            button_label.configure(text=f"Button {button_index}: Released", bg="#e5e7eb", fg="#111827")

    def _reset_mapping_state(self) -> None:
        self.capture_armed = False
        self.last_input_event = None
        self.last_input_var.set("Last input: -")
        self.capture_status_var.set("Type a note, then annotate the last input or arm the next input.")
        if hasattr(self, "capture_button"):
            self.capture_button.configure(text="Arm Next Input")

    def _reset_guided_state(self) -> None:
        self.guided_active = False
        self.guided_step_index = -1
        self.guided_neutral_snapshot = None
        self.guided_axis_bindings = {}
        self.guided_button_bindings = {}
        self.guided_hat_index = None
        self.guided_hat_actions = {}
        self.guided_step_cooldown_until = 0.0
        self.guided_waiting_for_neutral = False
        self.guided_axis_candidate = None
        self.guided_axis_candidate_count = 0
        self.guided_button_candidate = None
        self.guided_button_candidate_count = 0
        self.guided_hat_candidate = None
        self.guided_hat_candidate_count = 0
        self.guided_instruction_var.set("Guided detect is idle. Center the controls, then start the guided check.")
        self.guided_status_var.set("Guided detect status will appear here.")
        self.guided_summary_var.set("No guided mapping captured yet.")

    def on_device_selected(self, _event: object | None = None) -> None:
        if not self.devices:
            return
        selected_index = self.device_combo.current()
        if selected_index < 0 or selected_index >= len(self.devices):
            return
        self.selected_device = self.devices[selected_index]
        self.previous_snapshot = None
        self._reset_mapping_state()
        self._reset_guided_state()
        self._render_axes(self.selected_device)
        self._render_hats(self.selected_device.num_hats)
        self._render_buttons(self.selected_device.num_buttons)
        self._clear_state()
        self.status_var.set(f"Connected: {self.selected_device.name} via {self.selected_device.backend}")
        self.log_event(f"Selected device: {self.selected_device.name} via {self.selected_device.backend}")

    def poll_inputs(self) -> None:
        try:
            self._poll_inputs_once()
        finally:
            self.root.after(self.POLL_MS, self.poll_inputs)

    def _poll_inputs_once(self) -> None:
        if self.selected_device is None:
            return
        try:
            snapshot = read_snapshot(self.selected_device)
        except Exception as exc:
            self.status_var.set(f"Read failed: {exc}")
            return

        self.status_var.set(f"Connected: {self.selected_device.name} via {self.selected_device.backend}")
        self._update_state_display(snapshot)
        self._log_changes(snapshot)
        self._process_guided_detection(snapshot)
        self.previous_snapshot = snapshot

    def _update_state_display(self, snapshot: JoystickSnapshot) -> None:
        for axis_id, row in self.axis_rows.items():
            raw_label = row.get("raw_label")
            norm_label = row.get("norm_label")
            axis_state = snapshot.axes.get(axis_id)
            if raw_label is None or norm_label is None:
                continue
            if axis_state is None:
                raw_label.configure(text="-")
                norm_label.configure(text="-")
                continue
            raw_label.configure(text=format_raw_value(axis_state.raw))
            norm_label.configure(text=f"{axis_state.normalized:+.3f}")
            self._refresh_axis_row_state(axis_id)

        for index, button_label in enumerate(self.button_labels):
            pressed = snapshot.buttons[index] if index < len(snapshot.buttons) else False
            button_label.configure(
                text=f"Button {index + 1}: {'Pressed' if pressed else 'Released'}",
                bg="#bbf7d0" if pressed else "#e5e7eb",
                fg="#064e3b" if pressed else "#111827",
            )

        for index, hat_var in enumerate(self.hat_vars):
            hat_value = snapshot.hats[index] if index < len(snapshot.hats) else (0, 0)
            hat_var.set(f"Hat {index + 1}: {hat_to_text(hat_value)}")

    def _emit_input_event(self, message: str) -> None:
        self.last_input_event = message
        self.last_input_var.set(f"Last input: {message}")
        self.log_event(message)
        if self.capture_armed:
            self._complete_capture(message)

    def _ensure_recording_for_mapping(self) -> bool:
        if self.logging_enabled:
            return True
        self.capture_status_var.set("Select a text file for mapping records.")
        self.start_logging()
        return self.logging_enabled

    def toggle_capture_arm(self) -> None:
        if self.capture_armed:
            self.capture_armed = False
            self.capture_button.configure(text="Arm Next Input")
            self.capture_status_var.set("Next-input capture canceled.")
            return

        note = self.mapping_note_var.get().strip()
        if not note:
            self.capture_status_var.set("Enter a mapping note first.")
            self.mapping_note_entry.focus_set()
            return
        if not self._ensure_recording_for_mapping():
            self.capture_status_var.set("Recording was not started.")
            return
        self.capture_armed = True
        self.capture_button.configure(text="Cancel Capture")
        self.capture_status_var.set(f"Waiting for the next input change for note: {note}")
        self.log_event(f"MAPPING ARM | note={note}")

    def _complete_capture(self, input_message: str) -> None:
        note = self.mapping_note_var.get().strip()
        self.capture_armed = False
        self.capture_button.configure(text="Arm Next Input")
        if not note:
            self.capture_status_var.set(f"Captured input without note: {input_message}")
            return
        self.log_event(f"MAPPING CAPTURE | note={note} | input={input_message}")
        self.capture_status_var.set(f"Captured: {note} <- {input_message}")

    def annotate_last_input(self) -> None:
        note = self.mapping_note_var.get().strip()
        if not note:
            self.capture_status_var.set("Enter a mapping note first.")
            self.mapping_note_entry.focus_set()
            return
        if not self.last_input_event:
            self.capture_status_var.set("Move the joystick first so there is an input to annotate.")
            return
        if not self._ensure_recording_for_mapping():
            self.capture_status_var.set("Recording was not started.")
            return
        self.log_event(f"MAPPING NOTE | note={note} | input={self.last_input_event}")
        self.capture_status_var.set(f"Annotated: {note} <- {self.last_input_event}")

    def _axis_display_name(self, axis_id: str) -> str:
        if self.selected_device is None:
            return axis_id
        return self.selected_device.axis_labels.get(axis_id, axis_id)

    def _current_guided_step(self) -> GuidedStep | None:
        if not self.guided_active:
            return None
        if self.guided_step_index < 0 or self.guided_step_index >= len(GUIDED_STEPS):
            return None
        return GUIDED_STEPS[self.guided_step_index]

    def _reset_guided_candidates(self) -> None:
        self.guided_axis_candidate = None
        self.guided_axis_candidate_count = 0
        self.guided_button_candidate = None
        self.guided_button_candidate_count = 0
        self.guided_hat_candidate = None
        self.guided_hat_candidate_count = 0

    def _is_guided_step_supported(self, step: GuidedStep) -> bool:
        if self.selected_device is None:
            return False
        if step.kind == "axis":
            return any(self._is_axis_enabled(axis_id) for axis_id in self.selected_device.axis_ids)
        if step.kind == "button":
            return self.selected_device.num_buttons > 0
        if step.kind == "hat":
            return self.selected_device.num_hats > 0
        return True

    def _activate_guided_step(self) -> None:
        while self.guided_active and self.guided_step_index < len(GUIDED_STEPS):
            step = GUIDED_STEPS[self.guided_step_index]
            if self._is_guided_step_supported(step):
                self._reset_guided_candidates()
                self.guided_step_cooldown_until = time.monotonic() + self.GUIDED_STEP_COOLDOWN_SEC
                self.guided_waiting_for_neutral = True
                self.guided_instruction_var.set(step.instruction)
                self.guided_status_var.set(
                    f"Step {self.guided_step_index + 1}: release controls. "
                    f"Detect starts in {self.GUIDED_STEP_COOLDOWN_SEC:.1f}s."
                )
                return
            self.log_event(f"GUIDED SKIP | {step.key} unsupported on this device")
            self.guided_step_index += 1

        if self.guided_active:
            self._complete_guided_detection()

    def start_guided_detection(self) -> None:
        if self.selected_device is None:
            self.guided_status_var.set("No joystick selected.")
            return
        try:
            neutral_snapshot = read_snapshot(self.selected_device)
        except Exception as exc:
            self.guided_status_var.set(f"Failed to read baseline: {exc}")
            return

        self._reset_guided_state()
        self.guided_active = True
        self.guided_step_index = 0
        self.guided_neutral_snapshot = neutral_snapshot
        self.guided_status_var.set("Baseline captured. Follow the guided instruction.")
        self.log_event("GUIDED START | baseline captured")
        self._activate_guided_step()

    def retry_guided_step(self) -> None:
        step = self._current_guided_step()
        if step is None:
            self.guided_status_var.set("Guided detect is not running.")
            return
        self._reset_guided_candidates()
        self.guided_step_cooldown_until = time.monotonic() + self.GUIDED_STEP_COOLDOWN_SEC
        self.guided_waiting_for_neutral = True
        self.guided_status_var.set(
            f"Retrying {step.key}. Release controls; detect restarts in {self.GUIDED_STEP_COOLDOWN_SEC:.1f}s."
        )
        self.log_event(f"GUIDED RETRY | {step.key}")

    def skip_guided_step(self) -> None:
        step = self._current_guided_step()
        if step is None:
            self.guided_status_var.set("Guided detect is not running.")
            return
        self.log_event(f"GUIDED SKIP | {step.key}")
        self.guided_step_index += 1
        self._activate_guided_step()

    def stop_guided_detection(self) -> None:
        if not self.guided_active:
            self.guided_status_var.set("Guided detect is already stopped.")
            return
        self.guided_active = False
        self.guided_step_index = -1
        self.guided_step_cooldown_until = 0.0
        self.guided_waiting_for_neutral = False
        self._reset_guided_candidates()
        self.guided_instruction_var.set("Guided detect is idle. Center the controls, then start the guided check.")
        self.guided_status_var.set("Guided detect stopped.")
        self.guided_summary_var.set(self._build_guided_summary())
        self.log_event("GUIDED STOP")

    def _advance_guided_step(self) -> None:
        self.guided_step_index += 1
        self._activate_guided_step()

    def _complete_guided_detection(self) -> None:
        self.guided_active = False
        self.guided_step_index = -1
        self.guided_step_cooldown_until = 0.0
        self.guided_waiting_for_neutral = False
        self._reset_guided_candidates()
        summary = self._build_guided_summary()
        self.guided_instruction_var.set("Guided detect completed.")
        self.guided_status_var.set("Guided detect finished. Review the summary below.")
        self.guided_summary_var.set(summary)
        self.log_event("GUIDED COMPLETE")
        for summary_line in summary.splitlines():
            self.log_event(f"GUIDED RESULT | {summary_line}")

    def _build_guided_summary(self) -> str:
        lines: list[str] = []

        for slot_name in ("roll", "pitch", "yaw", "throttle"):
            binding = self.guided_axis_bindings.get(slot_name)
            if not binding:
                continue
            axis_id = str(binding["axis_id"])
            actions = binding["actions"]
            directions = ", ".join(
                f"{action}={'positive' if int(sign) > 0 else 'negative'}"
                for action, sign in sorted(actions.items())
            )
            lines.append(f"{slot_name}: {self._axis_display_name(axis_id)} [{directions}]")

        if self.guided_button_bindings:
            button_parts = [
                f"{action}=Button {button_index + 1}"
                for action, button_index in sorted(self.guided_button_bindings.items())
            ]
            lines.append("buttons: " + ", ".join(button_parts))

        if self.guided_hat_index is not None and self.guided_hat_actions:
            hat_parts = [
                f"{action}={hat_to_text(direction)}"
                for action, direction in sorted(self.guided_hat_actions.items())
            ]
            lines.append(f"hat {self.guided_hat_index + 1}: " + ", ".join(hat_parts))

        return "\n".join(lines) if lines else "No guided mapping captured yet."

    def _snapshot_is_neutral(self, snapshot: JoystickSnapshot) -> bool:
        if self.guided_neutral_snapshot is None or self.selected_device is None:
            return True

        for axis_id in self.selected_device.axis_ids:
            if not self._is_axis_enabled(axis_id):
                continue
            current_axis = snapshot.axes.get(axis_id)
            baseline_axis = self.guided_neutral_snapshot.axes.get(axis_id)
            if current_axis is None or baseline_axis is None:
                continue
            if abs(current_axis.normalized - baseline_axis.normalized) > self.GUIDED_NEUTRAL_AXIS_TOLERANCE:
                return False

        if any(snapshot.buttons):
            return False
        if any(hat_value != (0, 0) for hat_value in snapshot.hats):
            return False
        return True

    def _detect_guided_axis(self, snapshot: JoystickSnapshot) -> tuple[str, float] | None:
        if self.guided_neutral_snapshot is None or self.selected_device is None:
            return None

        best_axis_id: str | None = None
        best_delta = 0.0
        second_delta = 0.0
        for axis_id in self.selected_device.axis_ids:
            if not self._is_axis_enabled(axis_id):
                continue
            current_axis = snapshot.axes.get(axis_id)
            baseline_axis = self.guided_neutral_snapshot.axes.get(axis_id)
            if current_axis is None or baseline_axis is None:
                continue
            delta = current_axis.normalized - baseline_axis.normalized
            if abs(delta) > abs(best_delta):
                second_delta = best_delta
                best_axis_id = axis_id
                best_delta = delta
            elif abs(delta) > abs(second_delta):
                second_delta = delta

        if best_axis_id is None or abs(best_delta) < self.GUIDED_AXIS_TRIGGER_THRESHOLD:
            return None
        if abs(best_delta) - abs(second_delta) < 0.12:
            return None
        return best_axis_id, best_delta

    def _process_guided_detection(self, snapshot: JoystickSnapshot) -> None:
        step = self._current_guided_step()
        if step is None or self.selected_device is None:
            return

        now = time.monotonic()
        if now < self.guided_step_cooldown_until:
            remaining = max(0.0, self.guided_step_cooldown_until - now)
            self.guided_status_var.set(
                f"Step {self.guided_step_index + 1}: release controls. Detect starts in {remaining:.1f}s."
            )
            self._reset_guided_candidates()
            return

        if self.guided_waiting_for_neutral:
            if not self._snapshot_is_neutral(snapshot):
                self.guided_status_var.set(
                    f"Step {self.guided_step_index + 1}: return all axes, buttons, and hat to neutral first."
                )
                self._reset_guided_candidates()
                return
            self.guided_waiting_for_neutral = False
            self.guided_status_var.set(
                f"Step {self.guided_step_index + 1}: input window is open. {step.instruction}"
            )

        if step.kind == "axis":
            detected_axis = self._detect_guided_axis(snapshot)
            if detected_axis is None:
                self._reset_guided_candidates()
                return
            axis_id, delta = detected_axis
            detected_sign = 1 if delta >= 0.0 else -1
            candidate = (axis_id, detected_sign)
            if self.guided_axis_candidate == candidate:
                self.guided_axis_candidate_count += 1
            else:
                self.guided_axis_candidate = candidate
                self.guided_axis_candidate_count = 1

            if self.guided_axis_candidate_count < self.GUIDED_AXIS_CONFIRM_POLLS:
                self.guided_status_var.set(
                    f"Step {self.guided_step_index + 1}: checking {self._axis_display_name(axis_id)} "
                    f"({'positive' if detected_sign > 0 else 'negative'}) "
                    f"[{self.guided_axis_candidate_count}/{self.GUIDED_AXIS_CONFIRM_POLLS}]"
                )
                return

            binding = self.guided_axis_bindings.get(step.slot)
            if binding is None:
                binding = {"axis_id": axis_id, "actions": {}}
                self.guided_axis_bindings[step.slot] = binding
            elif str(binding["axis_id"]) != axis_id:
                self.guided_status_var.set(
                    f"{step.slot} is already using {self._axis_display_name(str(binding['axis_id']))}. "
                    f"Move that same control for this step."
                )
                return

            actions = binding["actions"]
            for existing_action, existing_sign in actions.items():
                if existing_action != step.action and int(existing_sign) == detected_sign:
                    self.guided_status_var.set(
                        f"{step.action} should be the opposite direction on {self._axis_display_name(axis_id)}. Retry this step."
                    )
                    return

            actions[step.action] = detected_sign
            self.guided_status_var.set(
                f"Captured {step.key}: {self._axis_display_name(axis_id)} "
                f"({'positive' if detected_sign > 0 else 'negative'})."
            )
            self.guided_summary_var.set(self._build_guided_summary())
            self._reset_guided_candidates()
            self.log_event(
                f"GUIDED STEP | {step.key} | input={self._axis_display_name(axis_id)} | delta={delta:+.3f}"
            )
            self._advance_guided_step()
            return

        if step.kind == "button":
            pressed_buttons = [button_index for button_index, pressed in enumerate(snapshot.buttons) if pressed]
            if not pressed_buttons:
                self.guided_button_candidate = None
                self.guided_button_candidate_count = 0
                return

            button_index = pressed_buttons[0]
            if self.guided_button_candidate == button_index:
                self.guided_button_candidate_count += 1
            else:
                self.guided_button_candidate = button_index
                self.guided_button_candidate_count = 1

            if self.guided_button_candidate_count < self.GUIDED_BUTTON_CONFIRM_POLLS:
                self.guided_status_var.set(
                    f"Step {self.guided_step_index + 1}: checking Button {button_index + 1} "
                    f"[{self.guided_button_candidate_count}/{self.GUIDED_BUTTON_CONFIRM_POLLS}]"
                )
                return

            if button_index in self.guided_button_bindings.values():
                self.guided_status_var.set(f"Button {button_index + 1} is already assigned. Press a different button.")
                return

            self.guided_button_bindings[step.action] = button_index
            self.guided_status_var.set(f"Captured {step.key}: Button {button_index + 1}.")
            self.guided_summary_var.set(self._build_guided_summary())
            self.guided_button_candidate = None
            self.guided_button_candidate_count = 0
            self.log_event(f"GUIDED STEP | {step.key} | input=Button {button_index + 1}")
            self._advance_guided_step()
            return

        if step.kind == "hat" and step.expected_hat is not None:
            matching_hat_index: int | None = None
            for hat_index, hat_value in enumerate(snapshot.hats):
                if hat_value == step.expected_hat:
                    matching_hat_index = hat_index
                    break
            if matching_hat_index is None:
                self.guided_hat_candidate = None
                self.guided_hat_candidate_count = 0
                return
            candidate = (matching_hat_index, step.expected_hat)
            if self.guided_hat_candidate == candidate:
                self.guided_hat_candidate_count += 1
            else:
                self.guided_hat_candidate = candidate
                self.guided_hat_candidate_count = 1

            if self.guided_hat_candidate_count < self.GUIDED_HAT_CONFIRM_POLLS:
                self.guided_status_var.set(
                    f"Step {self.guided_step_index + 1}: checking Hat {matching_hat_index + 1} -> "
                    f"{hat_to_text(step.expected_hat)} [{self.guided_hat_candidate_count}/{self.GUIDED_HAT_CONFIRM_POLLS}]"
                )
                return
            if self.guided_hat_index is not None and self.guided_hat_index != matching_hat_index:
                self.guided_status_var.set(
                    f"Hat {self.guided_hat_index + 1} is already being used. Move that same hat switch."
                )
                return

            self.guided_hat_index = matching_hat_index
            self.guided_hat_actions[step.action] = step.expected_hat
            self.guided_status_var.set(
                f"Captured {step.key}: Hat {matching_hat_index + 1} -> {hat_to_text(step.expected_hat)}."
            )
            self.guided_summary_var.set(self._build_guided_summary())
            self.guided_hat_candidate = None
            self.guided_hat_candidate_count = 0
            self.log_event(
                f"GUIDED STEP | {step.key} | input=Hat {matching_hat_index + 1} -> {hat_to_text(step.expected_hat)}"
            )
            self._advance_guided_step()

    def _log_changes(self, snapshot: JoystickSnapshot) -> None:
        if self.selected_device is None:
            return

        if self.previous_snapshot is None:
            for axis_id in self.selected_device.axis_ids:
                if not self._is_axis_enabled(axis_id):
                    continue
                axis_state = snapshot.axes.get(axis_id)
                if axis_state is None:
                    continue
                self.log_event(
                    f"{self.selected_device.axis_labels.get(axis_id, axis_id)} initial -> "
                    f"{axis_state.normalized:+.3f} (raw={format_raw_value(axis_state.raw)})"
                )
            for button_index, pressed in enumerate(snapshot.buttons):
                if pressed:
                    self.log_event(f"Button {button_index + 1} pressed")
            for hat_index, hat_value in enumerate(snapshot.hats, start=1):
                self.log_event(f"Hat {hat_index} initial -> {hat_to_text(hat_value)}")
            return

        for axis_id in self.selected_device.axis_ids:
            if not self._is_axis_enabled(axis_id):
                continue
            axis_state = snapshot.axes.get(axis_id)
            previous_axis = self.previous_snapshot.axes.get(axis_id)
            if axis_state is None:
                continue
            if previous_axis is None:
                self._emit_input_event(
                    f"{self.selected_device.axis_labels.get(axis_id, axis_id)} detected -> "
                    f"{axis_state.normalized:+.3f} (raw={format_raw_value(axis_state.raw)})"
                )
                continue
            if abs(axis_state.normalized - previous_axis.normalized) >= self.AXIS_CHANGE_THRESHOLD:
                self._emit_input_event(
                    f"{self.selected_device.axis_labels.get(axis_id, axis_id)} -> "
                    f"{axis_state.normalized:+.3f} (raw={format_raw_value(axis_state.raw)})"
                )

        for button_index, pressed in enumerate(snapshot.buttons):
            previous_pressed = self.previous_snapshot.buttons[button_index] if button_index < len(self.previous_snapshot.buttons) else False
            if pressed != previous_pressed:
                self._emit_input_event(f"Button {button_index + 1} {'pressed' if pressed else 'released'}")

        for hat_index, hat_value in enumerate(snapshot.hats):
            previous_hat = self.previous_snapshot.hats[hat_index] if hat_index < len(self.previous_snapshot.hats) else (0, 0)
            if hat_value != previous_hat:
                self._emit_input_event(f"Hat {hat_index + 1} -> {hat_to_text(hat_value)}")

    def toggle_logging(self) -> None:
        if self.logging_enabled:
            self.stop_logging()
        else:
            self.start_logging()

    def start_logging(self) -> None:
        if self.logging_enabled:
            return
        DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        default_name = datetime.now().strftime("joystick_input_%Y%m%d_%H%M%S.txt")
        selected_path = filedialog.asksaveasfilename(
            title="Save joystick log",
            defaultextension=".txt",
            initialdir=str(DEFAULT_LOG_DIR),
            initialfile=default_name,
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not selected_path:
            return

        self.log_file_path = Path(selected_path)
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_handle = self.log_file_path.open("a", encoding="utf-8")
        self.logging_enabled = True
        self.log_button.configure(text="Stop Recording")
        self.log_path_var.set(f"Recording to: {self.log_file_path}")
        self.log_event("Recording started")
        if self.selected_device is not None:
            self.log_event(
                f"Recording device: {self.selected_device.name} "
                f"(backend={self.selected_device.backend}, axes={self.selected_device.num_axes}, "
                f"buttons={self.selected_device.num_buttons}, hats={self.selected_device.num_hats})"
            )

    def stop_logging(self) -> None:
        if not self.logging_enabled:
            return
        self.log_event("Recording stopped")
        self.logging_enabled = False
        self.log_button.configure(text="Start Recording")
        self.log_path_var.set("No log file selected")
        if self.log_handle is not None:
            self.log_handle.close()
            self.log_handle = None
        self.log_file_path = None

    def log_event(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        line = f"[{timestamp}] {message}"
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        if self.logging_enabled and self.log_handle is not None:
            self.log_handle.write(line + "\n")
            self.log_handle.flush()

    def on_close(self) -> None:
        if self.logging_enabled:
            self.stop_logging()
        if pygame is not None and pygame.get_init():
            pygame.quit()
        self.root.destroy()


def list_devices_to_stdout(preferred_backend: str) -> int:
    devices = enumerate_joysticks(preferred_backend)
    if not devices:
        print("No joystick detected.")
        return 1
    for device in devices:
        print(
            f"id={device.device_id} backend={device.backend} name={device.name} "
            f"axes={device.num_axes} buttons={device.num_buttons} hats={device.num_hats}"
        )
    return 0


def snapshot_to_stdout(device_id: int | None, preferred_backend: str) -> int:
    devices = enumerate_joysticks(preferred_backend)
    if not devices:
        print("No joystick detected.")
        return 1
    device = devices[0] if device_id is None else next((item for item in devices if item.device_id == device_id), None)
    if device is None:
        print(f"Joystick id={device_id} not found.")
        return 1

    snapshot = read_snapshot(device)
    print(f"Device: {device.name} (id={device.device_id}, backend={device.backend})")
    for axis_id in device.axis_ids:
        axis_state = snapshot.axes.get(axis_id)
        if axis_state is None:
            continue
        print(
            f"{device.axis_labels.get(axis_id, axis_id)} "
            f"raw={format_raw_value(axis_state.raw)} normalized={axis_state.normalized:+.3f}"
        )
    for button_index, pressed in enumerate(snapshot.buttons, start=1):
        print(f"Button {button_index}: {'pressed' if pressed else 'released'}")
    for hat_index, hat_value in enumerate(snapshot.hats, start=1):
        print(f"Hat {hat_index}: {hat_to_text(hat_value)} {hat_value}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Windows joystick input tester")
    parser.add_argument("--list", action="store_true", help="List detected joysticks and exit")
    parser.add_argument("--snapshot", action="store_true", help="Print one input snapshot and exit")
    parser.add_argument("--device-id", type=int, default=None, help="Joystick id to use for --snapshot")
    parser.add_argument(
        "--backend",
        choices=BACKEND_CHOICES,
        default=BACKEND_AUTO,
        help="Joystick backend to use. Default: auto",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.list:
        return list_devices_to_stdout(args.backend)
    if args.snapshot:
        return snapshot_to_stdout(args.device_id, args.backend)

    root = tk.Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    app = JoystickTesterApp(root, preferred_backend=args.backend)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
