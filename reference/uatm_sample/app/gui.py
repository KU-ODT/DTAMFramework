from __future__ import annotations

import json
import math
import random
import sys
from dataclasses import dataclass, replace
from typing import Callable

from PyQt5 import QtCore, QtGui, QtWebChannel, QtWebEngineWidgets, QtWidgets

from app.config import (
    APP_TITLE,
    DATA_DIR,
    MBTILES_PATH,
    RESOURCES_DIR,
    SERVER_HOST,
    SERVER_PORT,
    WEB_DIR,
)
from app.mbtiles import MBTiles
from app.tile_server import TileServer
from app.pathplanner import RoutePlanner

DASHBOARD_HEADERS = [
    "Num",
    "Name",
    "Risk",
    "Speed",
    "HDG",
    "Position",
    "Mode",
    "Altitude",
    "From",
    "Destination",
]
COL_NUM = 0
COL_NAME = 1
COL_RISK = 2
COL_SPEED = 3
COL_HDG = 4
COL_POS = 5
COL_MODE = 6
COL_ALT = 7
COL_FROM = 8
COL_DEST = 9
DASHBOARD_ROWS = 8
SIM_START_SECONDS = 6 * 3600 + 30 * 60
SIM_DURATION_S = 15 * 3600
SIM_TICK_MS = 100
ACCEL_MPS2 = 1.5
FT_TO_M = 0.3048
M_TO_FT = 1.0 / FT_TO_M
KNOT_TO_MPS = 0.514444
FLIGHT_ALT_M = 1000 * FT_TO_M
VERTIPORT_ALT_M = 5.0
PREFLIGHT_WAIT_S = 10
FAST_SPEEDS = (1, 2, 5, 10, 20)
PLANE_ICON_IDS = ["plane1", "plane2", "plane3", "plane4"]
TRAFFIC_LEVELS = {
    "Low": 100,
    "Middle": 2500,
    "High": 25000,
}
TRAFFIC_LABELS = {
    "Low": "저밀도",
    "Middle": "중밀도",
    "High": "고밀도",
}
MODE_WAITING = "대기모드"
MODE_TAKEOFF = "이륙 중"
MODE_CRUISE = "비행 중"
MODE_LANDING = "착륙 중"
MODE_HOLD = "홀딩 중"
MODE_ENDED = "비행 종료"
HOLD_RADIUS_M = 1500.0
HOLD_RADIUS_KM = HOLD_RADIUS_M / 1000.0


@dataclass
class SimulationRules:
    speed_mps: float
    holding_s: int
    takeoff_s: int
    landing_s: int
    turn_rate_deg_s: float
    separation_m: int
    warning_m: int
    warning_ec_s: int
    warning_trailing_circles: int
    warning_leading_knot_delta: int
    caution_m: int
    caution_ec_s: int
    caution_trailing_knot_delta: int
    caution_leading_knot_delta: int
    operation_start_min: int
    operation_end_min: int
    operation_goal_count: int


DEFAULT_RULES = SimulationRules(
    speed_mps=100.0 * KNOT_TO_MPS,
    holding_s=2 * 60,
    takeoff_s=60,
    landing_s=2 * 60,
    turn_rate_deg_s=3.0,
    separation_m=300,
    warning_m=150,
    warning_ec_s=5,
    warning_trailing_circles=1,
    warning_leading_knot_delta=10,
    caution_m=300,
    caution_ec_s=10,
    caution_trailing_knot_delta=-10,
    caution_leading_knot_delta=10,
    operation_start_min=6 * 60 + 30,
    operation_end_min=21 * 60 + 30,
    operation_goal_count=2500,
)
APPLE_STYLE = """
QWidget {
  font-family: "SF Pro Text", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  font-size: 12px;
  color: #1d1d1f;
}

QWidget#appRoot {
  background: #f5f5f7;
}

QWidget#mapOverlay {
  background: transparent;
}

QFrame#appLoadingOverlay {
  background: rgba(10, 16, 24, 0.92);
}

QFrame#appLoadingCard {
  background: rgba(18, 28, 40, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 12px;
}

QLabel#appLoadingTitle {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #f2f6f9;
}

QLabel#appLoadingSubtitle {
  font-size: 11px;
  color: rgba(242, 246, 249, 0.78);
}

QProgressBar#appLoadingBar {
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 6px;
  background: rgba(8, 14, 20, 0.6);
  height: 10px;
  text-align: center;
  color: transparent;
}

QProgressBar#appLoadingBar::chunk {
  background: #2ecc71;
  border-radius: 5px;
}

QFrame#settingsPanel {
  background: #ffffff;
  border: 1px solid #d0d2dc;
  border-radius: 14px;
}

QFrame#ruleCard {
  background: #f7f7fb;
  border: 1px solid #e3e3ea;
  border-radius: 10px;
}

QLabel#ruleFieldLabel {
  font-weight: 600;
  color: #2b2b2d;
}

QLabel#ruleSubLabel {
  color: #6e6e73;
  font-size: 11px;
}

QLabel#ruleHint {
  color: #7b7b86;
  font-size: 11px;
}

QFrame#mapFrame,
QFrame#dashboardFrame,
QFrame#bottomFrame {
  background: #ffffff;
  border: 1px solid #dadbe1;
  border-radius: 16px;
}

QPushButton#dashboardToggle {
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid #d0d0d8;
  border-radius: 12px;
  padding: 0;
  font-weight: 700;
}

QPushButton#dashboardToggle:hover {
  background: #f7f7fb;
}

QPushButton#dashboardToggle:pressed {
  background: #e6e6ec;
}

QFrame#controlFrame {
  background: #f6f6fa;
  border: 1px solid #e2e2e8;
  border-radius: 12px;
}

QGroupBox#trafficGroup {
  background: #f6f6fa;
  border: 1px solid #e2e2e8;
  border-radius: 12px;
  margin-top: 16px;
}

QGroupBox#trafficGroup::title {
  subcontrol-origin: margin;
  left: 12px;
  top: 6px;
  padding: 0 6px;
  color: #5c5c62;
  font-weight: 600;
}

QGroupBox#panelTrafficGroup {
  background: #f6f6fa;
  border: 1px solid #e2e2e8;
  border-radius: 12px;
  margin-top: 16px;
}

QGroupBox#panelTrafficGroup::title {
  subcontrol-origin: margin;
  left: 12px;
  top: 6px;
  padding: 0 6px;
  color: #5c5c62;
  font-weight: 600;
}

QToolTip {
  background: #1f2226;
  color: #f5f7fa;
  border: 1px solid #2f3338;
  border-radius: 6px;
  padding: 6px 8px;
}

QCheckBox {
  spacing: 8px;
  padding: 2px 6px;
}

QCheckBox::indicator {
  width: 16px;
  height: 16px;
  border-radius: 8px;
  border: 1px solid #c7c7cf;
  background: #ffffff;
}

QCheckBox::indicator:hover {
  border: 1px solid #9ab9ff;
}

QCheckBox::indicator:checked {
  background: #0a84ff;
  border: 1px solid #0a84ff;
}

QRadioButton {
  spacing: 8px;
  padding: 2px 6px;
}

QRadioButton::indicator {
  width: 16px;
  height: 16px;
  border-radius: 8px;
  border: 1px solid #c7c7cf;
  background: #ffffff;
}

QRadioButton::indicator:hover {
  border: 1px solid #9ab9ff;
}

QRadioButton::indicator:checked {
  background: #0a84ff;
  border: 1px solid #0a84ff;
}

QPushButton {
  background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffffff, stop:1 #f0f0f4);
  border: 1px solid #d0d0d8;
  border-radius: 12px;
  padding: 6px 16px;
}

QPushButton:hover {
  background: #f7f7fb;
}

QPushButton:pressed {
  background: #e6e6ec;
}

QPushButton:disabled {
  background: #f2f2f2;
  color: #a0a0a5;
  border-color: #e0e0e5;
}

QPushButton#primaryButton {
  background: #0a84ff;
  border: 1px solid #0a84ff;
  color: #ffffff;
  font-weight: 600;
}

QPushButton#primaryButton:hover {
  background: #3395ff;
}

QPushButton#primaryButton:pressed {
  background: #0569d4;
}

QPushButton#mapIconButton {
  padding: 6px;
  min-width: 36px;
  min-height: 36px;
}

QPushButton#unitButton {
  padding: 4px 8px;
  border-radius: 8px;
}

QPushButton#unitButton:checked {
  background: #0a84ff;
  border: 1px solid #0a84ff;
  color: #ffffff;
  font-weight: 600;
}

QLabel#panelTitle {
  font-size: 13px;
  font-weight: 600;
  color: #2b2b2d;
}

QLabel#timeLabel {
  font-size: 14px;
  font-weight: 600;
  color: #1d1d1f;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid #d0d2dc;
  border-radius: 10px;
  padding: 6px 12px;
}

QLabel#speedLabel {
  font-size: 12px;
  color: #6e6e73;
}

QPushButton#playbackToggle {
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid #d0d0d8;
  border-radius: 12px;
  padding: 0;
}

QPushButton#playbackToggle:hover {
  background: #f7f7fb;
}

QPushButton#playbackToggle:pressed {
  background: #e6e6ec;
}

QFrame#playbackPanel {
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #d0d2dc;
  border-radius: 12px;
}

QPushButton#playbackButton {
  background: #ffffff;
  border: 1px solid #d0d0d8;
  border-radius: 10px;
  padding: 4px 12px;
}

QPushButton#playbackButton:hover {
  background: #f7f7fb;
}

QPushButton#playbackButton:pressed {
  background: #e6e6ec;
}

QPushButton#playbackButtonPrimary {
  background: #0a84ff;
  border: 1px solid #0a84ff;
  color: #ffffff;
  font-weight: 600;
  border-radius: 10px;
  padding: 4px 12px;
}

QPushButton#playbackButtonPrimary:hover {
  background: #3395ff;
}

QPushButton#playbackButtonPrimary:pressed {
  background: #0569d4;
}

QTableWidget {
  border: none;
  background: #ffffff;
  gridline-color: #ececf2;
  alternate-background-color: #f7f7fb;
  selection-background-color: #dbe9ff;
  selection-color: #1d1d1f;
}

QSpinBox,
QDoubleSpinBox,
QLineEdit,
QComboBox {
  background: #ffffff;
  border: 1px solid #d6d6de;
  border-radius: 8px;
  padding: 4px 8px;
}

QSpinBox:focus,
QDoubleSpinBox:focus,
QLineEdit:focus,
QComboBox:focus {
  border: 1px solid #0a84ff;
}

QTableWidget#ruleTable {
  border: 1px solid #e0e0e6;
  border-radius: 8px;
  background: #ffffff;
}

QHeaderView::section {
  background: #f2f2f7;
  border: none;
  border-bottom: 1px solid #e0e0e6;
  padding: 6px 4px;
  color: #3a3a3c;
  font-weight: 600;
}

QTableCornerButton::section {
  background: #f2f2f7;
  border: none;
  border-bottom: 1px solid #e0e0e6;
}

QScrollBar:vertical {
  border: none;
  background: #f1f1f6;
  width: 10px;
  margin: 4px 2px 4px 2px;
  border-radius: 5px;
}

QScrollBar::handle:vertical {
  background: #c9c9d1;
  border-radius: 5px;
  min-height: 24px;
}

QScrollBar::handle:vertical:hover {
  background: #b0b0bb;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
  border: none;
  height: 0px;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
  background: none;
}
"""


def _format_time(elapsed_s: int) -> str:
    total = SIM_START_SECONDS + max(0, int(elapsed_s))
    hours = (total // 3600) % 24
    minutes = (total % 3600) // 60
    seconds = total % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _cumulative_dist_m(points_xy: list[tuple[float, float]]) -> list[float]:
    if not points_xy:
        return [0.0]
    cumulative = [0.0]
    for (x1, y1), (x2, y2) in zip(points_xy, points_xy[1:]):
        dx = (x2 - x1) * 1000.0
        dy = (y2 - y1) * 1000.0
        cumulative.append(cumulative[-1] + math.hypot(dx, dy))
    return cumulative


def _motion_profile(
    total_dist_m: float,
    vmax_mps: float,
    accel_mps2: float,
) -> tuple[float, float, float, float]:
    if total_dist_m <= 0 or vmax_mps <= 0:
        return 0.0, 0.0, 0.0, 0.0
    cruise_time = total_dist_m / vmax_mps
    return 0.0, cruise_time, cruise_time, vmax_mps


def _distance_at_time(
    t_s: float,
    total_dist_m: float,
    accel_time_s: float,
    cruise_time_s: float,
    peak_speed_mps: float,
    accel_mps2: float,
) -> float:
    if total_dist_m <= 0 or t_s <= 0:
        return 0.0
    if cruise_time_s > 0:
        d_acc = 0.5 * accel_mps2 * accel_time_s * accel_time_s
        if t_s <= accel_time_s:
            return 0.5 * accel_mps2 * t_s * t_s
        if t_s <= accel_time_s + cruise_time_s:
            return d_acc + peak_speed_mps * (t_s - accel_time_s)
        if t_s <= accel_time_s + cruise_time_s + accel_time_s:
            t_dec = t_s - accel_time_s - cruise_time_s
            return (
                d_acc
                + peak_speed_mps * cruise_time_s
                + peak_speed_mps * t_dec
                - 0.5 * accel_mps2 * t_dec * t_dec
            )
        return total_dist_m

    if t_s <= accel_time_s:
        return 0.5 * accel_mps2 * t_s * t_s
    if t_s <= 2.0 * accel_time_s:
        d_acc = 0.5 * accel_mps2 * accel_time_s * accel_time_s
        t_dec = t_s - accel_time_s
        return d_acc + peak_speed_mps * t_dec - 0.5 * accel_mps2 * t_dec * t_dec
    return total_dist_m


def _speed_at_time(
    t_s: float,
    accel_time_s: float,
    cruise_time_s: float,
    peak_speed_mps: float,
    accel_mps2: float,
) -> float:
    if t_s <= 0:
        return 0.0
    if cruise_time_s > 0:
        if t_s <= accel_time_s:
            return accel_mps2 * t_s
        if t_s <= accel_time_s + cruise_time_s:
            return peak_speed_mps
        if t_s <= accel_time_s + cruise_time_s + accel_time_s:
            t_dec = t_s - accel_time_s - cruise_time_s
            return max(0.0, peak_speed_mps - accel_mps2 * t_dec)
        return 0.0
    if t_s <= accel_time_s:
        return accel_mps2 * t_s
    if t_s <= 2.0 * accel_time_s:
        t_dec = t_s - accel_time_s
        return max(0.0, peak_speed_mps - accel_mps2 * t_dec)
    return 0.0


def _position_at_distance(
    points_xy: list[tuple[float, float]],
    cum_dist_m: list[float],
    dist_m: float,
) -> tuple[float, float]:
    if not points_xy:
        return 0.0, 0.0
    if dist_m <= 0:
        return points_xy[0]
    if dist_m >= cum_dist_m[-1]:
        return points_xy[-1]
    idx = 0
    while idx < len(cum_dist_m) and cum_dist_m[idx] < dist_m:
        idx += 1
    if idx <= 0:
        return points_xy[0]
    prev_dist = cum_dist_m[idx - 1]
    seg_dist = cum_dist_m[idx] - prev_dist
    if seg_dist <= 0:
        return points_xy[idx]
    ratio = (dist_m - prev_dist) / seg_dist
    x1, y1 = points_xy[idx - 1]
    x2, y2 = points_xy[idx]
    return x1 + (x2 - x1) * ratio, y1 + (y2 - y1) * ratio


def _heading_at_distance(
    points_xy: list[tuple[float, float]],
    cum_dist_m: list[float],
    dist_m: float,
) -> float:
    if len(points_xy) < 2:
        return 0.0
    if dist_m <= 0:
        x1, y1 = points_xy[0]
        x2, y2 = points_xy[1]
    elif dist_m >= cum_dist_m[-1]:
        x1, y1 = points_xy[-2]
        x2, y2 = points_xy[-1]
    else:
        idx = 0
        while idx < len(cum_dist_m) and cum_dist_m[idx] < dist_m:
            idx += 1
        idx = max(1, min(idx, len(points_xy) - 1))
        x1, y1 = points_xy[idx - 1]
        x2, y2 = points_xy[idx]
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return 0.0
    heading = math.degrees(math.atan2(dx, dy))
    if heading < 0:
        heading += 360.0
    return heading


def _value_at_distance(
    values: list[float],
    cum_dist_m: list[float],
    dist_m: float,
) -> float:
    if not values:
        return 0.0
    if dist_m <= 0:
        return values[0]
    if dist_m >= cum_dist_m[-1]:
        return values[-1]
    idx = 0
    while idx < len(cum_dist_m) and cum_dist_m[idx] < dist_m:
        idx += 1
    if idx <= 0:
        return values[0]
    prev_dist = cum_dist_m[idx - 1]
    seg_dist = cum_dist_m[idx] - prev_dist
    if seg_dist <= 0:
        return values[idx]
    ratio = (dist_m - prev_dist) / seg_dist
    return values[idx - 1] + (values[idx] - values[idx - 1]) * ratio


@dataclass
class Flight:
    flight_id: int
    name: str
    origin: str
    destination: str
    risk: str
    icon_id: str
    start_offset_s: int
    speed_mps: float
    points_xy: list[tuple[float, float]]
    points_alt_m: list[float]
    cum_dist_m: list[float]
    total_dist_m: float
    accel_time_s: float
    cruise_time_s: float
    total_time_s: float
    peak_speed_mps: float
    path_nodes: list[str]


@dataclass
class FlightControl:
    speed_override_mps: float | None = None
    manual_active: bool = False
    manual_dist_m: float | None = None
    manual_arrival_s: float | None = None
    manual_landing_alt_m: float | None = None
    hold_active: bool = False
    hold_loops_total: int = 0
    hold_start_time_s: float = 0.0
    hold_start_dist_m: float = 0.0
    hold_center_xy: tuple[float, float] | None = None
    hold_start_angle_rad: float = 0.0
    hold_speed_mps: float = 0.0
    hold_alt_m: float = FLIGHT_ALT_M
    hold_radius_m: float = HOLD_RADIUS_M
    wind_effect_scale: float = 1.0
    wind_effect_target_scale: float | None = None
    wind_effect_start_scale: float = 1.0
    wind_effect_start_s: float = 0.0
    wind_effect_ramp_s: float = 0.0


@dataclass
class FlightSchedule:
    schedule_id: int
    risk: str
    start_offset_s: int
    origin: str
    destination: str


class Simulation(QtCore.QObject):
    def __init__(
        self,
        planner: RoutePlanner,
        rules: SimulationRules,
        get_traffic_selection: Callable[[], str | None],
        update_time: Callable[[int], None],
        set_dashboard_data: Callable[[list[list[str]] | None], None],
        add_dashboard_row: Callable[[list[str]], None],
        update_dashboard_status: Callable[[list[dict[str, object]]], None],
        update_speed: Callable[[int], None],
        update_map: Callable[[list[dict[str, object]]], None],
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.planner = planner
        self.rules = rules
        self.get_traffic_selection = get_traffic_selection
        self.update_time = update_time
        self.set_dashboard_data = set_dashboard_data
        self.add_dashboard_row = add_dashboard_row
        self.update_dashboard_status = update_dashboard_status
        self.update_speed = update_speed
        self.update_map = update_map

        self.flights: list[Flight] = []
        self.schedule: list[FlightSchedule] = []
        self.schedule_index = 0
        self.sim_elapsed_s = 0
        self.running = False
        self.speed_multiplier = 1
        self.port_names = list(self.planner.ports.keys())
        self.flight_controls: dict[int, FlightControl] = {}
        self.flight_state: dict[int, dict[str, object]] = {}
        self.last_positions_time_s: float | None = None
        self.sim_duration_s = self._operation_window_s()

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(SIM_TICK_MS)
        self.timer.timeout.connect(self._tick)
        self.elapsed_timer = QtCore.QElapsedTimer()
        self.last_tick_ms: int | None = None

        self.update_speed(self.speed_multiplier)
        self.update_time(0)

    def _operation_window_s(self) -> int:
        start_min = int(self.rules.operation_start_min)
        end_min = int(self.rules.operation_end_min)
        start_min = max(0, min(24 * 60, start_min))
        end_min = max(0, min(24 * 60, end_min))
        if end_min >= start_min:
            duration_min = end_min - start_min
        else:
            duration_min = 24 * 60 - start_min + end_min
        return max(0, duration_min) * 60

    def update_rules(self, rules: SimulationRules) -> None:
        self.rules = rules
        self.sim_duration_s = self._operation_window_s()

    def start(self) -> None:
        self.set_speed(1)
        if not self.schedule or self.sim_elapsed_s >= self.sim_duration_s:
            self._reset_state()
            self.sim_elapsed_s = 0
            self.flights = []
            self.schedule = self._generate_schedule()
            self.schedule_index = 0
            self.flight_controls.clear()
            self.flight_state.clear()
            self.last_positions_time_s = None
            self.set_dashboard_data([])
            self.update_time(0)
        if not self.schedule:
            return
        self.running = True
        self._update_positions()
        if not self.timer.isActive():
            self.elapsed_timer.restart()
            self.last_tick_ms = None
            self.timer.start()

    def pause(self) -> None:
        self.running = False
        if self.timer.isActive():
            self.timer.stop()

    def stop(self) -> None:
        self.pause()
        self.sim_elapsed_s = 0
        self.flights = []
        self.schedule = []
        self.schedule_index = 0
        self.flight_controls.clear()
        self.flight_state.clear()
        self.set_dashboard_data(None)
        self.update_map([])
        self.update_time(0)
        self.last_tick_ms = None
        self.last_positions_time_s = None

    def fast(self) -> None:
        try:
            idx = FAST_SPEEDS.index(self.speed_multiplier)
        except ValueError:
            idx = -1
        next_speed = FAST_SPEEDS[(idx + 1) % len(FAST_SPEEDS)]
        self.set_speed(next_speed)

    def set_speed(self, multiplier: int) -> None:
        self.speed_multiplier = max(1, int(multiplier))
        self.update_speed(self.speed_multiplier)

    def _get_flight(self, flight_id: int) -> Flight | None:
        for flight in self.flights:
            if flight.flight_id == flight_id:
                return flight
        return None

    def _get_control(self, flight_id: int) -> FlightControl:
        control = self.flight_controls.get(flight_id)
        if not control:
            control = FlightControl()
            self.flight_controls[flight_id] = control
        return control

    def set_flight_speed(self, flight_id: int, speed_mps: float) -> None:
        flight = self._get_flight(flight_id)
        if not flight:
            return
        speed = float(speed_mps)
        if speed <= 0:
            return
        control = self._get_control(flight_id)
        control.speed_override_mps = speed
        control.manual_active = True
        state = self.flight_state.get(flight_id)
        dist_m = state.get("dist_m") if state else None
        if isinstance(dist_m, (int, float)):
            control.manual_dist_m = float(dist_m)
        control.manual_arrival_s = None
        control.manual_landing_alt_m = None
        if control.hold_active:
            control.hold_speed_mps = speed

    def clear_flight_speed(self, flight_id: int) -> None:
        control = self.flight_controls.get(flight_id)
        if not control:
            return
        control.speed_override_mps = None
        control.manual_active = True
        control.manual_arrival_s = None
        control.manual_landing_alt_m = None
        if control.hold_active:
            flight = self._get_flight(flight_id)
            control.hold_speed_mps = flight.speed_mps if flight else 0.0

    def set_wind_hold(self, flight_id: int, target_scale: float, ramp_s: float) -> None:
        control = self._get_control(flight_id)
        current = control.wind_effect_scale
        if not isinstance(current, (int, float)) or not math.isfinite(current):
            current = 1.0
        target = float(target_scale)
        if not math.isfinite(target):
            return
        target = max(0.0, min(0.5, target))
        ramp = float(ramp_s)
        if not math.isfinite(ramp):
            ramp = 0.0
        ramp = max(0.0, ramp)
        control.wind_effect_start_scale = float(current)
        control.wind_effect_target_scale = float(target)
        control.wind_effect_start_s = float(self.sim_elapsed_s)
        control.wind_effect_ramp_s = float(ramp)

    def _holding_radius_m(self, speed_mps: float) -> float:
        rate_deg = float(self.rules.turn_rate_deg_s)
        if speed_mps <= 0 or rate_deg <= 0:
            return HOLD_RADIUS_M
        omega = math.radians(rate_deg)
        if omega <= 0:
            return HOLD_RADIUS_M
        radius = speed_mps / omega
        if not math.isfinite(radius) or radius <= 0:
            return HOLD_RADIUS_M
        return radius

    def start_holding(self, flight_id: int, loops: int) -> float | None:
        flight = self._get_flight(flight_id)
        if not flight:
            return None
        count = max(1, int(loops))
        state = self.flight_state.get(flight_id)
        if not state or state.get("phase") != "cruise":
            return None
        pos_xy = state.get("pos_xy")
        heading = state.get("heading_deg")
        dist_m = state.get("dist_m")
        alt_m = state.get("alt_m")
        if not isinstance(pos_xy, tuple) or len(pos_xy) != 2:
            return None
        if not isinstance(heading, (int, float)):
            return None
        if not isinstance(dist_m, (int, float)):
            return None
        control = self._get_control(flight_id)
        control.manual_active = True
        if control.manual_dist_m is None:
            control.manual_dist_m = float(dist_m)
        heading_rad = math.radians(float(heading))
        right_vec = (math.cos(heading_rad), -math.sin(heading_rad))
        base_speed = float(state.get("speed_mps") or 0.0)
        speed = control.speed_override_mps or base_speed or flight.peak_speed_mps
        radius_m = self._holding_radius_m(speed)
        radius_km = radius_m / 1000.0
        center = (
            pos_xy[0] + right_vec[0] * radius_km,
            pos_xy[1] + right_vec[1] * radius_km,
        )
        start_angle = math.atan2(pos_xy[1] - center[1], pos_xy[0] - center[0])
        control.hold_active = True
        control.hold_loops_total = count
        control.hold_start_time_s = self.sim_elapsed_s
        control.hold_start_dist_m = float(dist_m)
        control.hold_center_xy = center
        control.hold_start_angle_rad = start_angle
        control.hold_speed_mps = float(speed)
        control.hold_alt_m = float(alt_m) if isinstance(alt_m, (int, float)) else FLIGHT_ALT_M
        control.hold_radius_m = float(radius_m)
        return radius_m

    def stop_holding(self, flight_id: int) -> None:
        control = self.flight_controls.get(flight_id)
        if not control:
            return
        if not control.hold_active or not control.hold_center_xy:
            control.hold_active = False
            control.hold_loops_total = 0
            control.hold_start_time_s = 0.0
            control.hold_center_xy = None
            control.hold_start_angle_rad = 0.0
            control.hold_speed_mps = 0.0
            return
        radius_m = control.hold_radius_m if control.hold_radius_m > 0 else HOLD_RADIUS_M
        loop_length = 2.0 * math.pi * radius_m
        if loop_length <= 0 or control.hold_speed_mps <= 0:
            control.hold_active = False
            control.hold_loops_total = 0
            control.hold_start_time_s = 0.0
            control.hold_center_xy = None
            control.hold_start_angle_rad = 0.0
            control.hold_speed_mps = 0.0
            return
        hold_elapsed = max(0.0, self.sim_elapsed_s - control.hold_start_time_s)
        loops_done = hold_elapsed * control.hold_speed_mps / loop_length
        target_loops = max(1, int(math.ceil(loops_done - 1e-6)))
        if control.hold_loops_total <= 0:
            control.hold_loops_total = target_loops
        else:
            control.hold_loops_total = min(control.hold_loops_total, target_loops)

    def set_emergency_landing(
        self,
        flight_id: int,
        lon: float,
        lat: float,
        label: str = "",
        alt_m: float | None = None,
    ) -> bool:
        flight = self._get_flight(flight_id)
        if not flight:
            return False
        if not math.isfinite(lon) or not math.isfinite(lat):
            return False
        state = self.flight_state.get(flight_id)
        start_label = None
        dist_m = state.get("dist_m") if state else None
        if flight.path_nodes and flight.cum_dist_m and isinstance(dist_m, (int, float)):
            idx = self._path_index_for_distance(flight.cum_dist_m, float(dist_m))
            if idx is not None:
                start_idx = max(0, min(idx, len(flight.path_nodes) - 1) - 1)
                start_label = flight.path_nodes[start_idx]
        if not start_label:
            start_label = flight.origin
        pos_xy = state.get("pos_xy") if state else None
        if not isinstance(pos_xy, tuple) or len(pos_xy) != 2:
            pos_xy = flight.points_xy[0] if flight.points_xy else None
        target_xy = self.planner.projection.to_xy_km(lon, lat)
        if not pos_xy:
            pos_xy = target_xy
        alt_start = state.get("alt_m") if state else None
        if not isinstance(alt_start, (int, float)) or not math.isfinite(alt_start):
            alt_start = FLIGHT_ALT_M
        alt_target = float(alt_m) if alt_m is not None else VERTIPORT_ALT_M
        if not math.isfinite(alt_target):
            alt_target = VERTIPORT_ALT_M
        points_xy = [tuple(pos_xy), tuple(target_xy)]
        points_alt_m = [float(alt_start), float(alt_target)]
        cum_dist_m = _cumulative_dist_m(points_xy)
        total_dist_m = float(cum_dist_m[-1]) if cum_dist_m else 0.0
        control = self._get_control(flight_id)
        speed_base = state.get("speed_mps") if state else None
        speed = control.speed_override_mps or speed_base or flight.speed_mps
        if not isinstance(speed, (int, float)) or not math.isfinite(speed) or speed <= 0:
            speed = flight.speed_mps
        accel_time, cruise_time, total_time, peak_speed = _motion_profile(
            total_dist_m,
            float(speed),
            ACCEL_MPS2,
        )
        flight.points_xy = points_xy
        flight.points_alt_m = points_alt_m
        flight.cum_dist_m = cum_dist_m
        flight.total_dist_m = total_dist_m
        flight.accel_time_s = accel_time
        flight.cruise_time_s = cruise_time
        flight.total_time_s = total_time
        flight.peak_speed_mps = peak_speed
        target_label = str(label or "").strip() or "Emergency"
        flight.destination = target_label
        flight.path_nodes = [start_label, target_label]
        control.manual_active = True
        control.manual_dist_m = 0.0
        control.manual_arrival_s = None
        control.manual_landing_alt_m = None
        if control.hold_active:
            control.hold_active = False
            control.hold_loops_total = 0
            control.hold_start_time_s = 0.0
            control.hold_start_dist_m = 0.0
            control.hold_center_xy = None
            control.hold_start_angle_rad = 0.0
            control.hold_speed_mps = 0.0
        return True

    def set_corridor_closed(self, start: str, end: str, closed: bool) -> bool:
        if not start or not end:
            return False
        changed = self.planner.set_edge_closed(start, end, closed)
        if changed and closed:
            self._replan_flights_for_edge(start, end)
        return changed

    def _replan_flights_for_edge(self, start: str, end: str) -> None:
        key = tuple(sorted((start, end)))
        for flight in list(self.flights):
            state = self.flight_state.get(flight.flight_id)
            if not state or state.get("phase") != "cruise":
                continue
            control = self.flight_controls.get(flight.flight_id)
            if control and control.hold_active:
                continue
            dist_m = state.get("dist_m")
            if not isinstance(dist_m, (int, float)):
                continue
            if not flight.path_nodes or not flight.cum_dist_m:
                continue
            idx = self._path_index_for_distance(flight.cum_dist_m, float(dist_m))
            if idx is None:
                continue
            if not self._path_contains_edge(flight.path_nodes, idx, key):
                continue
            self._replan_flight_from_state(flight, state, idx)

    def _path_index_for_distance(self, cum_dist_m: list[float], dist_m: float) -> int | None:
        if not cum_dist_m:
            return None
        for idx, value in enumerate(cum_dist_m):
            if dist_m <= value:
                return idx
        return len(cum_dist_m) - 1

    def _path_contains_edge(
        self,
        path_nodes: list[str],
        idx: int,
        key: tuple[str, str],
    ) -> bool:
        if len(path_nodes) < 2:
            return False
        start_idx = max(0, min(idx, len(path_nodes) - 1) - 1)
        for i in range(start_idx, len(path_nodes) - 1):
            edge_key = tuple(sorted((path_nodes[i], path_nodes[i + 1])))
            if edge_key == key:
                return True
        return False

    def _replan_flight_from_state(self, flight: Flight, state: dict[str, object], idx: int) -> None:
        if idx < 0 or idx >= len(flight.path_nodes):
            return
        start_node = flight.path_nodes[idx]
        try:
            result = self.planner.find_route(start_node, flight.destination)
        except Exception:
            return
        geometry = list(result.points)
        if not geometry:
            return
        pos_xy = state.get("pos_xy")
        if not isinstance(pos_xy, tuple) or len(pos_xy) != 2:
            return
        projection = self.planner.projection
        cur_lon, cur_lat = projection.to_lonlat(pos_xy[0], pos_xy[1])
        first_xy = projection.to_xy_km(geometry[0][0], geometry[0][1])
        dist_km = math.hypot(first_xy[0] - pos_xy[0], first_xy[1] - pos_xy[1])
        path_nodes = list(result.path)
        if dist_km < 0.02:
            new_points = [(cur_lon, cur_lat)] + geometry[1:]
        else:
            new_points = [(cur_lon, cur_lat)] + geometry
            path_nodes = [start_node] + path_nodes
        points_xy = [projection.to_xy_km(lon, lat) for lon, lat in new_points]
        if len(points_xy) < 2:
            return
        points_alt_m = [FLIGHT_ALT_M] * len(points_xy)
        cum_dist_m = _cumulative_dist_m(points_xy)
        total_dist_m = cum_dist_m[-1]
        if total_dist_m <= 0:
            return
        speed_mps = state.get("speed_mps")
        if isinstance(speed_mps, (int, float)) and speed_mps > 0:
            flight.speed_mps = float(speed_mps)
        flight.points_xy = points_xy
        flight.points_alt_m = points_alt_m
        flight.cum_dist_m = cum_dist_m
        flight.total_dist_m = total_dist_m
        flight.path_nodes = path_nodes
        control = self._get_control(flight.flight_id)
        control.manual_active = True
        control.manual_dist_m = 0.0
        control.manual_arrival_s = None

    def _tick(self) -> None:
        if not self.running:
            return
        now_ms = self.elapsed_timer.elapsed()
        if self.last_tick_ms is None:
            self.last_tick_ms = now_ms
            return
        delta_ms = now_ms - self.last_tick_ms
        self.last_tick_ms = now_ms
        if delta_ms <= 0:
            return
        delta_s = delta_ms / 1000.0
        self.sim_elapsed_s += delta_s * self.speed_multiplier
        if self.sim_elapsed_s >= self.sim_duration_s:
            self.sim_elapsed_s = self.sim_duration_s
            self._update_positions()
            self.update_time(int(self.sim_elapsed_s))
            self.running = False
            self.timer.stop()
            return
        self._update_positions()
        self.update_time(int(self.sim_elapsed_s))

    def _flight_phase(self, flight: Flight, elapsed_s: float) -> tuple[str, str, float]:
        wait_s = PREFLIGHT_WAIT_S
        takeoff_s = max(0, int(self.rules.takeoff_s))
        landing_s = max(0, int(self.rules.landing_s))
        if elapsed_s < wait_s:
            return MODE_WAITING, "waiting", elapsed_s
        if elapsed_s < wait_s + takeoff_s:
            return MODE_TAKEOFF, "takeoff", elapsed_s - wait_s
        move_t = elapsed_s - wait_s - takeoff_s
        if move_t < flight.total_time_s:
            return MODE_CRUISE, "cruise", move_t
        landing_t = move_t - flight.total_time_s
        if landing_t < landing_s:
            return MODE_LANDING, "landing", landing_t
        return MODE_ENDED, "ended", landing_t

    def _update_positions(self) -> None:
        self._spawn_ready_flights()
        positions: list[dict[str, object]] = []
        statuses: list[dict[str, object]] = []
        active_flights: list[Flight] = []
        wait_s = PREFLIGHT_WAIT_S
        takeoff_s = max(0, int(self.rules.takeoff_s))
        landing_s = max(0, int(self.rules.landing_s))
        alt_span = FLIGHT_ALT_M - VERTIPORT_ALT_M
        delta_s = 0.0
        if self.last_positions_time_s is not None:
            delta_s = max(0.0, self.sim_elapsed_s - self.last_positions_time_s)
        self.last_positions_time_s = self.sim_elapsed_s
        for flight in self.flights:
            elapsed = self.sim_elapsed_s - flight.start_offset_s
            if elapsed < 0:
                continue
            mode, phase, phase_t = self._flight_phase(flight, elapsed)
            speed_mps = 0.0
            pos_xy = flight.points_xy[0]
            alt_m = VERTIPORT_ALT_M
            dist_m = 0.0
            heading_deg = 0.0
            control = self.flight_controls.get(flight.flight_id)
            manual_active = bool(control and control.manual_active)
            if elapsed < wait_s:
                mode = MODE_WAITING
                phase = "waiting"
            elif elapsed < wait_s + takeoff_s:
                mode = MODE_TAKEOFF
                phase = "takeoff"
                ratio = min(1.0, (elapsed - wait_s) / takeoff_s) if takeoff_s > 0 else 1.0
                alt_m = VERTIPORT_ALT_M + alt_span * ratio
            elif manual_active:
                if not control:
                    control = self._get_control(flight.flight_id)
                if control.manual_dist_m is None:
                    base_phase_t = max(0.0, elapsed - wait_s - takeoff_s)
                    control.manual_dist_m = _distance_at_time(
                        base_phase_t,
                        flight.total_dist_m,
                        flight.accel_time_s,
                        flight.cruise_time_s,
                        flight.peak_speed_mps,
                        ACCEL_MPS2,
                    )
                dist_m = float(control.manual_dist_m or 0.0)
                if control.hold_active and control.hold_center_xy:
                    hold_elapsed = max(0.0, self.sim_elapsed_s - control.hold_start_time_s)
                    radius_m = control.hold_radius_m if control.hold_radius_m > 0 else HOLD_RADIUS_M
                    radius_km = radius_m / 1000.0
                    loop_length = 2.0 * math.pi * radius_m
                    loops_done = (
                        hold_elapsed * control.hold_speed_mps / loop_length if loop_length > 0 else 0.0
                    )
                    if loops_done < control.hold_loops_total:
                        angle = control.hold_start_angle_rad
                        if radius_m > 0:
                            angle -= (control.hold_speed_mps / radius_m) * hold_elapsed
                        center_x, center_y = control.hold_center_xy
                        pos_xy = (
                            center_x + radius_km * math.cos(angle),
                            center_y + radius_km * math.sin(angle),
                        )
                        alt_m = control.hold_alt_m
                        speed_mps = control.hold_speed_mps
                        mode = MODE_HOLD
                        phase = "hold"
                        vel_dx = math.sin(angle)
                        vel_dy = -math.cos(angle)
                        heading_deg = math.degrees(math.atan2(vel_dx, vel_dy))
                        if heading_deg < 0:
                            heading_deg += 360.0
                    else:
                        control.hold_active = False
                if not control.hold_active:
                    speed = control.speed_override_mps or flight.speed_mps
                    if delta_s > 0 and dist_m < flight.total_dist_m:
                        dist_m = min(flight.total_dist_m, dist_m + speed * delta_s)
                        control.manual_dist_m = dist_m
                    pos_xy = _position_at_distance(flight.points_xy, flight.cum_dist_m, dist_m)
                    alt_m = _value_at_distance(flight.points_alt_m, flight.cum_dist_m, dist_m)
                    speed_mps = speed
                    heading_deg = _heading_at_distance(flight.points_xy, flight.cum_dist_m, dist_m)
                    if dist_m >= flight.total_dist_m:
                        if control.manual_arrival_s is None:
                            control.manual_arrival_s = self.sim_elapsed_s
                            control.manual_landing_alt_m = alt_m
                        landing_t = self.sim_elapsed_s - control.manual_arrival_s
                        if landing_t < landing_s:
                            mode = MODE_LANDING
                            phase = "landing"
                            ratio = min(1.0, landing_t / landing_s) if landing_s > 0 else 1.0
                            start_alt_m = control.manual_landing_alt_m
                            if not isinstance(start_alt_m, (int, float)) or not math.isfinite(
                                start_alt_m,
                            ):
                                start_alt_m = alt_m if math.isfinite(alt_m) else FLIGHT_ALT_M
                            alt_drop = max(0.0, float(start_alt_m) - VERTIPORT_ALT_M)
                            alt_m = float(start_alt_m) - alt_drop * ratio
                            pos_xy = flight.points_xy[-1]
                            speed_mps = 0.0
                        else:
                            mode = MODE_ENDED
                    else:
                        mode = MODE_CRUISE
                        phase = "cruise"
            else:
                if phase == "takeoff":
                    ratio = min(1.0, phase_t / takeoff_s) if takeoff_s > 0 else 1.0
                    alt_m = VERTIPORT_ALT_M + alt_span * ratio
                elif phase == "cruise":
                    dist_m = _distance_at_time(
                        phase_t,
                        flight.total_dist_m,
                        flight.accel_time_s,
                        flight.cruise_time_s,
                        flight.peak_speed_mps,
                        ACCEL_MPS2,
                    )
                    pos_xy = _position_at_distance(flight.points_xy, flight.cum_dist_m, dist_m)
                    alt_m = _value_at_distance(flight.points_alt_m, flight.cum_dist_m, dist_m)
                    speed_mps = _speed_at_time(
                        phase_t,
                        flight.accel_time_s,
                        flight.cruise_time_s,
                        flight.peak_speed_mps,
                        ACCEL_MPS2,
                    )
                    heading_deg = _heading_at_distance(flight.points_xy, flight.cum_dist_m, dist_m)
                elif phase == "landing":
                    pos_xy = flight.points_xy[-1]
                    ratio = min(1.0, phase_t / landing_s) if landing_s > 0 else 1.0
                    alt_m = FLIGHT_ALT_M - alt_span * ratio
                elif phase == "ended":
                    statuses.append(
                        {
                            "name": flight.name,
                            "mode": mode,
                            "speed_mps": 0.0,
                            "altitude_m": VERTIPORT_ALT_M,
                        }
                    )
                    self.flight_controls.pop(flight.flight_id, None)
                    self.flight_state.pop(flight.flight_id, None)
                    continue
            if mode == MODE_ENDED:
                statuses.append(
                    {
                        "name": flight.name,
                        "mode": mode,
                        "speed_mps": 0.0,
                        "altitude_m": VERTIPORT_ALT_M,
                    }
                )
                self.flight_controls.pop(flight.flight_id, None)
                self.flight_state.pop(flight.flight_id, None)
                continue
            lon, lat = self.planner.projection.to_lonlat(pos_xy[0], pos_xy[1])
            positions.append(
                {
                    "id": flight.flight_id,
                    "lon": lon,
                    "lat": lat,
                    "altitude_m": alt_m,
                    "name": flight.name,
                    "from": flight.origin,
                    "to": flight.destination,
                    "risk": flight.risk,
                    "speed_mps": speed_mps,
                    "icon": flight.icon_id,
                    "mode": mode,
                    "heading_deg": heading_deg,
                }
            )
            statuses.append(
                {
                    "name": flight.name,
                    "mode": mode,
                    "speed_mps": speed_mps,
                    "altitude_m": alt_m,
                }
            )
            self.flight_state[flight.flight_id] = {
                "phase": phase,
                "dist_m": dist_m,
                "pos_xy": pos_xy,
                "heading_deg": heading_deg,
                "alt_m": alt_m,
                "speed_mps": speed_mps,
            }
            active_flights.append(flight)
        self.flights = active_flights
        self.update_map(positions)
        self.update_dashboard_status(statuses)

    def _reset_state(self) -> None:
        self.update_map([])
        self.flight_state.clear()
        self.flight_controls.clear()
        self.last_positions_time_s = None


    def _spawn_ready_flights(self) -> None:
        while self.schedule_index < len(self.schedule):
            schedule = self.schedule[self.schedule_index]
            if schedule.start_offset_s > self.sim_elapsed_s:
                break
            flight = self._create_flight_from_schedule(schedule)
            if flight:
                self.flights.append(flight)
                self.add_dashboard_row(
                    [
                        flight.name,
                        flight.risk,
                        "0.0 m/s",
                        "-",
                        "-",
                        MODE_WAITING,
                        f"{VERTIPORT_ALT_M:.0f} m",
                        flight.origin,
                        flight.destination,
                    ]
                )
            self.schedule_index += 1

    def _create_flight_from_schedule(self, schedule: FlightSchedule) -> Flight | None:
        if len(self.port_names) < 2:
            return None

        def pick_destination(start: str) -> str | None:
            for _ in range(10):
                candidate = random.choice(self.port_names)
                if candidate != start:
                    return candidate
            for candidate in self.port_names:
                if candidate != start:
                    return candidate
            return None

        def pick_new_pair() -> tuple[str, str] | None:
            start = random.choice(self.port_names)
            dest = pick_destination(start)
            if dest is None:
                return None
            return start, dest

        origin = schedule.origin
        destination = schedule.destination
        for _ in range(6):
            if origin not in self.port_names:
                pair = pick_new_pair()
                if not pair:
                    return None
                origin, destination = pair
            if destination not in self.port_names or destination == origin:
                destination = pick_destination(origin)
                if destination is None:
                    return None
            try:
                result = self.planner.find_route(origin, destination)
            except Exception:
                pair = pick_new_pair()
                if not pair:
                    return None
                origin, destination = pair
                continue
            geometry = result.points
            if len(geometry) < 2:
                pair = pick_new_pair()
                if not pair:
                    return None
                origin, destination = pair
                continue
            speed_mps = self.rules.speed_mps
            points_alt_m = [FLIGHT_ALT_M] * len(geometry)
            points_xy = [self.planner.projection.to_xy_km(lon, lat) for lon, lat in geometry]
            cum_dist_m = _cumulative_dist_m(points_xy)
            if not cum_dist_m:
                pair = pick_new_pair()
                if not pair:
                    return None
                origin, destination = pair
                continue
            total_dist_m = float(cum_dist_m[-1])
            if total_dist_m <= 0:
                pair = pick_new_pair()
                if not pair:
                    return None
                origin, destination = pair
                continue
            accel_time, cruise_time, total_time, peak_speed = _motion_profile(
                total_dist_m,
                speed_mps,
                ACCEL_MPS2,
            )
            flight_id = schedule.schedule_id
            name = f"F{flight_id:05d}"
            return Flight(
                flight_id=flight_id,
                name=name,
                origin=origin,
                destination=destination,
                risk=schedule.risk,
                icon_id=random.choice(PLANE_ICON_IDS),
                start_offset_s=schedule.start_offset_s,
                speed_mps=speed_mps,
                points_xy=points_xy,
                points_alt_m=points_alt_m,
                cum_dist_m=cum_dist_m,
                total_dist_m=total_dist_m,
                accel_time_s=accel_time,
                cruise_time_s=cruise_time,
                total_time_s=total_time,
                peak_speed_mps=peak_speed,
                path_nodes=list(result.path),
            )
        return None

    def _generate_schedule(self) -> list[FlightSchedule]:
        selection = self.get_traffic_selection()
        if not selection:
            return []
        count = TRAFFIC_LEVELS.get(selection)
        if not count:
            return []
        if len(self.port_names) < 2:
            return []

        window_s = int(self.sim_duration_s)
        if window_s <= 0:
            return []

        schedule: list[FlightSchedule] = []
        schedule_id = 1
        max_offset = max(0, window_s - 1)
        for _ in range(count):
            origin = random.choice(self.port_names)
            destination = random.choice(self.port_names)
            while destination == origin:
                destination = random.choice(self.port_names)
            start_offset = random.randint(0, max_offset) if max_offset > 0 else 0
            schedule.append(
                FlightSchedule(
                    schedule_id=schedule_id,
                    risk="0",
                    start_offset_s=start_offset,
                    origin=origin,
                    destination=destination,
                )
            )
            schedule_id += 1

        schedule.sort(key=lambda item: item.start_offset_s)
        return schedule


class ControlBridge(QtCore.QObject):
    def __init__(
        self,
        simulation: Simulation,
        status_callback: Callable[[str, str, int | None], None] | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.simulation = simulation
        self.status_callback = status_callback

    @QtCore.pyqtSlot(int, float)
    def setFlightSpeed(self, flight_id: int, speed_mps: float) -> None:
        self.simulation.set_flight_speed(flight_id, speed_mps)

    @QtCore.pyqtSlot(int)
    def clearFlightSpeed(self, flight_id: int) -> None:
        self.simulation.clear_flight_speed(flight_id)

    @QtCore.pyqtSlot(int, int)
    def startHolding(self, flight_id: int, loops: int) -> None:
        radius_m = self.simulation.start_holding(flight_id, loops)
        if radius_m is None or not self.status_callback:
            return
        radius_km = radius_m / 1000.0
        self.status_callback(
            f"Holding radius ~{radius_km:.1f} km (turn rate {self.simulation.rules.turn_rate_deg_s:.1f} deg/s).",
            "info",
            3500,
        )

    @QtCore.pyqtSlot(int)
    def stopHolding(self, flight_id: int) -> None:
        self.simulation.stop_holding(flight_id)

    @QtCore.pyqtSlot(int, float, float, str, float)
    def setEmergencyLanding(
        self,
        flight_id: int,
        lon: float,
        lat: float,
        label: str,
        alt_m: float,
    ) -> None:
        ok = self.simulation.set_emergency_landing(flight_id, lon, lat, label, alt_m)
        if not ok or not self.status_callback:
            return
        target = label.strip() if label else "point"
        self.status_callback(
            f"Emergency landing set: {target}.",
            "warn",
            4000,
        )

    @QtCore.pyqtSlot(int, str)
    def forceMoveVia(self, flight_id: int, waypoint: str) -> None:
        wp_name = str(waypoint or "").strip()
        if not wp_name or wp_name not in self.simulation.planner.node_xy:
            if self.status_callback:
                self.status_callback("Force move failed: invalid waypoint.", "warn", 3500)
            return
        ok = self.simulation.force_move_via(flight_id, wp_name)
        if not self.status_callback:
            return
        if ok:
            self.status_callback(f"Force move set: {wp_name}.", "info", 3500)
        else:
            self.status_callback(
                f"Force move failed: no route from {wp_name}.",
                "warn",
                4500,
            )

    @QtCore.pyqtSlot(int, float, float)
    def setWindHold(self, flight_id: int, target_scale: float, ramp_s: float) -> None:
        self.simulation.set_wind_hold(flight_id, target_scale, ramp_s)

    @QtCore.pyqtSlot(str, str, bool)
    def setCorridorClosed(self, start: str, end: str, closed: bool) -> None:
        changed = self.simulation.set_corridor_closed(start, end, bool(closed))
        if not changed or not self.status_callback:
            return
        action = "closed" if closed else "reopened"
        self.status_callback(
            f"Corridor {action}: {start} - {end}",
            "info",
            5000,
        )


class UiBridge(QtCore.QObject):
    def __init__(self, window: "MapWindow") -> None:
        super().__init__(window)
        self.window = window

    @QtCore.pyqtSlot(str)
    def selectFlight(self, name: str) -> None:
        self.window.select_flight_by_name(name)

    @QtCore.pyqtSlot()
    def clearSelection(self) -> None:
        self.window.clear_flight_selection()


class MapWindow(QtWidgets.QMainWindow):
    def __init__(self, map_url: str, planner: RoutePlanner) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1600, 1100)

        central = QtWidgets.QWidget(self)
        central.setObjectName("appRoot")
        self.setCentralWidget(central)

        root_layout = QtWidgets.QVBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        top_layout = QtWidgets.QHBoxLayout()
        top_layout.setSpacing(12)

        map_frame = QtWidgets.QFrame()
        map_frame.setObjectName("mapFrame")
        map_frame.setFrameShape(QtWidgets.QFrame.NoFrame)
        map_frame.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        map_layout = QtWidgets.QGridLayout(map_frame)
        map_layout.setContentsMargins(0, 0, 0, 0)
        map_layout.setSpacing(0)
        self.map_view = QtWebEngineWidgets.QWebEngineView(map_frame)
        self.map_view.setUrl(QtCore.QUrl(map_url))
        self.map_view.loadFinished.connect(self._on_map_loaded)
        self._map_ready = False
        self._status_queue: list[dict[str, object]] = []
        self._pending_status_hint: str | None = None
        map_layout.addWidget(self.map_view, 0, 0)

        map_overlay = QtWidgets.QWidget(map_frame)
        map_overlay.setObjectName("mapOverlay")
        map_overlay.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed,
            QtWidgets.QSizePolicy.Fixed,
        )
        map_overlay.setVisible(False)
        self.map_overlay = map_overlay
        overlay_layout = QtWidgets.QHBoxLayout(map_overlay)
        overlay_layout.setContentsMargins(10, 10, 10, 10)
        overlay_layout.setSpacing(10)
        overlay_layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        button_column = QtWidgets.QVBoxLayout()
        button_column.setContentsMargins(0, 0, 0, 0)
        button_column.setSpacing(8)
        self.settings_button = QtWidgets.QPushButton()
        self.settings_button.setObjectName("mapIconButton")
        self.settings_button.setToolTip("Settings")
        self.settings_button.setIcon(QtGui.QIcon(str(RESOURCES_DIR / "simulation_sign.png")))
        self.settings_button.setIconSize(QtCore.QSize(30, 30))
        self.settings_button.setFixedSize(42, 42)
        self.settings_button.clicked.connect(self.toggle_settings_panel)
        button_column.addWidget(self.settings_button, 0, QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        button_column.addStretch(1)
        overlay_layout.addLayout(button_column)

        self.settings_panel = QtWidgets.QFrame(map_overlay)
        self.settings_panel.setObjectName("settingsPanel")
        self.settings_panel.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.settings_panel.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.settings_panel.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed,
            QtWidgets.QSizePolicy.Fixed,
        )
        self.settings_panel.setMinimumWidth(320)
        shadow = QtWidgets.QGraphicsDropShadowEffect(self.settings_panel)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 6)
        shadow.setColor(QtGui.QColor(0, 0, 0, 70))
        self.settings_panel.setGraphicsEffect(shadow)
        self.settings_panel_anim: QtCore.QPropertyAnimation | None = None
        panel_layout = QtWidgets.QVBoxLayout(self.settings_panel)
        panel_layout.setContentsMargins(12, 12, 12, 12)
        panel_layout.setSpacing(10)

        panel_traffic_group = QtWidgets.QGroupBox("Daily Traffic")
        panel_traffic_group.setObjectName("panelTrafficGroup")
        panel_traffic_layout = QtWidgets.QHBoxLayout(panel_traffic_group)
        panel_traffic_layout.setContentsMargins(12, 12, 12, 10)
        panel_traffic_layout.setSpacing(12)
        self.panel_traffic_group = QtWidgets.QButtonGroup(self)
        self.panel_traffic_group.setExclusive(True)
        self.panel_traffic_buttons: dict[str, QtWidgets.QRadioButton] = {}
        for label in TRAFFIC_LEVELS:
            count = TRAFFIC_LEVELS.get(label, 0)
            ko_label = TRAFFIC_LABELS.get(label, label)
            display = f"{label.upper()}\n{ko_label} {count}대"
            radio = QtWidgets.QRadioButton(display)
            radio.setProperty("trafficLevel", label)
            self.panel_traffic_group.addButton(radio)
            panel_traffic_layout.addWidget(radio)
            self.panel_traffic_buttons[label] = radio
        self.panel_traffic_group.buttonToggled.connect(self._on_panel_traffic_changed)
        panel_layout.addWidget(panel_traffic_group)

        rule_tooltips = {
            "Operation Time": "시뮬레이션 운항 시간대입니다. 시작~종료 기준으로 총 운영 시간이 계산됩니다.",
            "Operation Goal": "목표 운항 대수입니다. 시간/30분/10분당 예상 운항 대수가 계산됩니다.",
            "Flight speed": "순항 기준 비행 속도입니다. 단위 버튼에 따라 입력/표시가 바뀝니다.",
            "Holding time": "홀딩(대기) 구간에서 머무는 시간입니다.",
            "Takeoff time": "이륙 단계에서 순항 고도까지 상승하는 데 걸리는 시간입니다.",
            "Landing time": "착륙 단계에서 순항 고도에서 착륙 고도로 내려오는 시간입니다.",
            "Turn rate": "선회 속도(deg/s)로, 방향 전환의 민첩도를 나타냅니다.",
            "Longitudinal sep.": "종적 분리 기준 거리로, 앞뒤 항공기 최소 간격입니다.",
            "Warning": "경고 단계 기준값(거리 또는 EC 시간)입니다.",
            "Warning action": "경고 단계에서 자동 조치(후행/선행)입니다.",
            "Caution": "주의 단계 기준값(거리 또는 EC 시간)입니다.",
            "Caution action": "주의 단계에서 자동 조치(후행/선행)입니다.",
            "Distance": "항공기 간 거리 기준입니다.",
            "EC before": "예상 충돌(EC, Expected Collision)까지 남은 시간 기준입니다.",
            "Trailing": "후행 항공기에 적용되는 조치입니다.",
            "Leading": "선행 항공기에 적용되는 조치입니다.",
        }

        def _apply_rule_tooltip(label: QtWidgets.QLabel, text: str) -> None:
            tooltip = rule_tooltips.get(text)
            if tooltip:
                label.setToolTip(tooltip)
                label.setProperty("ruleTooltipText", tooltip)
                label.setMouseTracking(True)
                label.installEventFilter(self)

        operation_card = QtWidgets.QFrame()
        operation_card.setObjectName("ruleCard")
        operation_layout = QtWidgets.QVBoxLayout(operation_card)
        operation_layout.setContentsMargins(10, 10, 10, 10)
        operation_layout.setSpacing(6)

        operation_time_label = QtWidgets.QLabel("Operation Time")
        operation_time_label.setObjectName("ruleFieldLabel")
        _apply_rule_tooltip(operation_time_label, "Operation Time")
        operation_layout.addWidget(operation_time_label)

        operation_time_row = QtWidgets.QHBoxLayout()
        operation_time_row.setContentsMargins(0, 0, 0, 0)
        operation_time_row.setSpacing(6)
        self.operation_start_time = QtWidgets.QTimeEdit()
        self.operation_start_time.setDisplayFormat("HH:mm")
        self.operation_end_time = QtWidgets.QTimeEdit()
        self.operation_end_time.setDisplayFormat("HH:mm")
        operation_time_row.addWidget(self.operation_start_time)
        operation_time_row.addWidget(QtWidgets.QLabel("~"))
        operation_time_row.addWidget(self.operation_end_time)
        operation_time_row.addStretch(1)
        operation_layout.addLayout(operation_time_row)

        self.operation_time_summary = QtWidgets.QLabel("")
        self.operation_time_summary.setObjectName("ruleHint")
        operation_layout.addWidget(self.operation_time_summary)

        operation_goal_label = QtWidgets.QLabel("Operation Goal")
        operation_goal_label.setObjectName("ruleFieldLabel")
        _apply_rule_tooltip(operation_goal_label, "Operation Goal")
        operation_layout.addWidget(operation_goal_label)

        operation_goal_row = QtWidgets.QHBoxLayout()
        operation_goal_row.setContentsMargins(0, 0, 0, 0)
        operation_goal_row.setSpacing(6)
        self.operation_goal_total = QtWidgets.QSpinBox()
        self.operation_goal_total.setRange(0, 1000000)
        self.operation_goal_total.setSingleStep(50)
        self.operation_goal_total.setSuffix("대")
        operation_goal_row.addWidget(self.operation_goal_total)
        operation_goal_row.addStretch(1)
        operation_layout.addLayout(operation_goal_row)

        self.operation_goal_summary = QtWidgets.QLabel("")
        self.operation_goal_summary.setObjectName("ruleHint")
        operation_layout.addWidget(self.operation_goal_summary)

        panel_layout.addWidget(operation_card)

        panel_title = QtWidgets.QLabel("Simulation Rule")
        panel_title.setObjectName("panelTitle")
        panel_layout.addWidget(panel_title)

        rule_card = QtWidgets.QFrame()
        rule_card.setObjectName("ruleCard")
        rule_layout = QtWidgets.QGridLayout(rule_card)
        rule_layout.setContentsMargins(10, 10, 10, 10)
        rule_layout.setHorizontalSpacing(10)
        rule_layout.setVerticalSpacing(8)
        rule_layout.setColumnStretch(1, 1)

        def _rule_label(text: str, object_name: str = "ruleFieldLabel") -> QtWidgets.QLabel:
            label = QtWidgets.QLabel(text)
            label.setObjectName(object_name)
            _apply_rule_tooltip(label, text)
            return label

        row = 0
        rule_layout.addWidget(_rule_label("Flight speed"), row, 0, QtCore.Qt.AlignLeft)
        speed_widget = QtWidgets.QWidget()
        speed_layout = QtWidgets.QHBoxLayout(speed_widget)
        speed_layout.setContentsMargins(0, 0, 0, 0)
        speed_layout.setSpacing(6)
        self.rule_speed_value = QtWidgets.QDoubleSpinBox()
        self.rule_speed_value.setRange(1, 9999)
        self.rule_speed_value.setDecimals(1)
        self.rule_speed_value.setSingleStep(1.0)
        self.rule_speed_value.setFixedWidth(80)
        speed_layout.addWidget(self.rule_speed_value)
        self.speed_unit_group = QtWidgets.QButtonGroup(self)
        self.speed_unit_group.setExclusive(True)
        self.speed_unit_buttons: dict[str, QtWidgets.QPushButton] = {}
        for unit in ("knot", "m/s", "km/h"):
            button = QtWidgets.QPushButton(unit)
            button.setObjectName("unitButton")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked, name=unit: self._set_speed_unit(name))
            self.speed_unit_group.addButton(button)
            self.speed_unit_buttons[unit] = button
            speed_layout.addWidget(button)
        speed_layout.addStretch(1)
        rule_layout.addWidget(speed_widget, row, 1)
        row += 1

        rule_layout.addWidget(_rule_label("Holding time"), row, 0, QtCore.Qt.AlignLeft)
        self.rule_holding_min = QtWidgets.QSpinBox()
        self.rule_holding_min.setRange(0, 60)
        self.rule_holding_min.setSuffix(" min")
        rule_layout.addWidget(self.rule_holding_min, row, 1)
        row += 1

        rule_layout.addWidget(_rule_label("Turn rate"), row, 0, QtCore.Qt.AlignLeft)
        self.rule_turn_rate = QtWidgets.QDoubleSpinBox()
        self.rule_turn_rate.setRange(0, 10)
        self.rule_turn_rate.setDecimals(1)
        self.rule_turn_rate.setSuffix(" deg/s")
        rule_layout.addWidget(self.rule_turn_rate, row, 1)
        row += 1

        rule_layout.addWidget(_rule_label("Takeoff time"), row, 0, QtCore.Qt.AlignLeft)
        self.rule_takeoff_min = QtWidgets.QSpinBox()
        self.rule_takeoff_min.setRange(0, 60)
        self.rule_takeoff_min.setSuffix(" min")
        rule_layout.addWidget(self.rule_takeoff_min, row, 1)
        row += 1

        rule_layout.addWidget(_rule_label("Landing time"), row, 0, QtCore.Qt.AlignLeft)
        self.rule_landing_min = QtWidgets.QSpinBox()
        self.rule_landing_min.setRange(0, 60)
        self.rule_landing_min.setSuffix(" min")
        rule_layout.addWidget(self.rule_landing_min, row, 1)
        row += 1

        rule_layout.addWidget(_rule_label("Longitudinal sep."), row, 0, QtCore.Qt.AlignLeft)
        sep_widget = QtWidgets.QWidget()
        sep_layout = QtWidgets.QHBoxLayout(sep_widget)
        sep_layout.setContentsMargins(0, 0, 0, 0)
        sep_layout.setSpacing(6)
        self.rule_sep_m = QtWidgets.QSpinBox()
        self.rule_sep_m.setRange(0, 5000)
        self.rule_sep_m.setSuffix(" m")
        self.rule_sep_ft = QtWidgets.QLabel("")
        self.rule_sep_ft.setObjectName("ruleHint")
        sep_layout.addWidget(self.rule_sep_m)
        sep_layout.addWidget(self.rule_sep_ft)
        sep_layout.addStretch(1)
        rule_layout.addWidget(sep_widget, row, 1)
        row += 1

        rule_layout.addWidget(_rule_label("Warning"), row, 0, QtCore.Qt.AlignLeft)
        warning_widget = QtWidgets.QWidget()
        warning_layout = QtWidgets.QGridLayout(warning_widget)
        warning_layout.setContentsMargins(0, 0, 0, 0)
        warning_layout.setHorizontalSpacing(6)
        warning_layout.setVerticalSpacing(4)
        warning_layout.addWidget(_rule_label("Distance", "ruleSubLabel"), 0, 0)
        self.rule_warning_m = QtWidgets.QSpinBox()
        self.rule_warning_m.setRange(0, 5000)
        self.rule_warning_m.setSuffix(" m")
        self.rule_warning_ft = QtWidgets.QLabel("")
        self.rule_warning_ft.setObjectName("ruleHint")
        warning_layout.addWidget(self.rule_warning_m, 0, 1)
        warning_layout.addWidget(self.rule_warning_ft, 0, 2)
        warning_layout.addWidget(_rule_label("EC before", "ruleSubLabel"), 1, 0)
        self.rule_warning_ec_s = QtWidgets.QSpinBox()
        self.rule_warning_ec_s.setRange(0, 120)
        self.rule_warning_ec_s.setSuffix(" s")
        warning_layout.addWidget(self.rule_warning_ec_s, 1, 1)
        rule_layout.addWidget(warning_widget, row, 1)
        row += 1

        rule_layout.addWidget(_rule_label("Warning action"), row, 0, QtCore.Qt.AlignLeft)
        warn_action_widget = QtWidgets.QWidget()
        warn_action_layout = QtWidgets.QGridLayout(warn_action_widget)
        warn_action_layout.setContentsMargins(0, 0, 0, 0)
        warn_action_layout.setHorizontalSpacing(6)
        warn_action_layout.setVerticalSpacing(4)
        warn_action_layout.addWidget(_rule_label("Trailing", "ruleSubLabel"), 0, 0)
        self.rule_warning_trailing_circle = QtWidgets.QSpinBox()
        self.rule_warning_trailing_circle.setRange(0, 10)
        self.rule_warning_trailing_circle.setSuffix(" circle")
        warn_action_layout.addWidget(self.rule_warning_trailing_circle, 0, 1)
        warn_action_layout.addWidget(_rule_label("Leading", "ruleSubLabel"), 1, 0)
        self.rule_warning_leading_knot = QtWidgets.QSpinBox()
        self.rule_warning_leading_knot.setRange(-50, 50)
        self.rule_warning_leading_knot.setSuffix(" knot")
        warn_action_layout.addWidget(self.rule_warning_leading_knot, 1, 1)
        rule_layout.addWidget(warn_action_widget, row, 1)
        row += 1

        rule_layout.addWidget(_rule_label("Caution"), row, 0, QtCore.Qt.AlignLeft)
        caution_widget = QtWidgets.QWidget()
        caution_layout = QtWidgets.QGridLayout(caution_widget)
        caution_layout.setContentsMargins(0, 0, 0, 0)
        caution_layout.setHorizontalSpacing(6)
        caution_layout.setVerticalSpacing(4)
        caution_layout.addWidget(_rule_label("Distance", "ruleSubLabel"), 0, 0)
        self.rule_caution_m = QtWidgets.QSpinBox()
        self.rule_caution_m.setRange(0, 5000)
        self.rule_caution_m.setSuffix(" m")
        self.rule_caution_ft = QtWidgets.QLabel("")
        self.rule_caution_ft.setObjectName("ruleHint")
        caution_layout.addWidget(self.rule_caution_m, 0, 1)
        caution_layout.addWidget(self.rule_caution_ft, 0, 2)
        caution_layout.addWidget(_rule_label("EC before", "ruleSubLabel"), 1, 0)
        self.rule_caution_ec_s = QtWidgets.QSpinBox()
        self.rule_caution_ec_s.setRange(0, 120)
        self.rule_caution_ec_s.setSuffix(" s")
        caution_layout.addWidget(self.rule_caution_ec_s, 1, 1)
        rule_layout.addWidget(caution_widget, row, 1)
        row += 1

        rule_layout.addWidget(_rule_label("Caution action"), row, 0, QtCore.Qt.AlignLeft)
        caution_action_widget = QtWidgets.QWidget()
        caution_action_layout = QtWidgets.QGridLayout(caution_action_widget)
        caution_action_layout.setContentsMargins(0, 0, 0, 0)
        caution_action_layout.setHorizontalSpacing(6)
        caution_action_layout.setVerticalSpacing(4)
        caution_action_layout.addWidget(_rule_label("Trailing", "ruleSubLabel"), 0, 0)
        self.rule_caution_trailing_knot = QtWidgets.QSpinBox()
        self.rule_caution_trailing_knot.setRange(-50, 50)
        self.rule_caution_trailing_knot.setSuffix(" knot")
        caution_action_layout.addWidget(self.rule_caution_trailing_knot, 0, 1)
        caution_action_layout.addWidget(_rule_label("Leading", "ruleSubLabel"), 1, 0)
        self.rule_caution_leading_knot = QtWidgets.QSpinBox()
        self.rule_caution_leading_knot.setRange(-50, 50)
        self.rule_caution_leading_knot.setSuffix(" knot")
        caution_action_layout.addWidget(self.rule_caution_leading_knot, 1, 1)
        rule_layout.addWidget(caution_action_widget, row, 1)

        panel_layout.addWidget(rule_card)

        panel_buttons = QtWidgets.QHBoxLayout()
        panel_buttons.setSpacing(10)
        panel_buttons.addStretch(1)
        self.panel_save_button = QtWidgets.QPushButton("Save")
        self.panel_reset_button = QtWidgets.QPushButton("Reset")
        self.panel_save_button.clicked.connect(self._handle_panel_save)
        self.panel_reset_button.clicked.connect(self._handle_panel_reset)
        panel_buttons.addWidget(self.panel_save_button)
        panel_buttons.addWidget(self.panel_reset_button)
        panel_buttons.addStretch(1)
        panel_layout.addLayout(panel_buttons)

        self.rule_defaults = DEFAULT_RULES
        self.rule_state = replace(DEFAULT_RULES)
        self.speed_unit = "knot"
        self.rule_sep_m.valueChanged.connect(self._update_rule_distance_labels)
        self.rule_warning_m.valueChanged.connect(self._update_rule_distance_labels)
        self.rule_caution_m.valueChanged.connect(self._update_rule_distance_labels)
        self.operation_start_time.timeChanged.connect(self._update_operation_time_summary)
        self.operation_end_time.timeChanged.connect(self._update_operation_time_summary)
        self.operation_goal_total.valueChanged.connect(self._update_operation_goal_summary)
        self._load_rules_into_ui(self.rule_state)

        self.settings_panel.setVisible(False)
        overlay_layout.addWidget(self.settings_panel, 0, QtCore.Qt.AlignTop)
        map_layout.addWidget(map_overlay, 0, 0, QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        self.dashboard_visible = False
        self.dashboard_toggle = QtWidgets.QPushButton("<", map_frame)
        self.dashboard_toggle.setObjectName("dashboardToggle")
        self.dashboard_toggle.setFixedSize(28, 64)
        self.dashboard_toggle.clicked.connect(self.toggle_dashboard_panel)
        self._update_dashboard_toggle()
        map_layout.addWidget(
            self.dashboard_toggle,
            0,
            0,
            QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
        )
        top_layout.addWidget(map_frame, 1)

        dashboard_frame = QtWidgets.QFrame()
        dashboard_frame.setObjectName("dashboardFrame")
        dashboard_frame.setFrameShape(QtWidgets.QFrame.NoFrame)
        dashboard_frame.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        dashboard_frame.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed,
            QtWidgets.QSizePolicy.Expanding,
        )
        dashboard_layout = QtWidgets.QVBoxLayout(dashboard_frame)
        dashboard_layout.setContentsMargins(8, 8, 8, 8)
        self.table = QtWidgets.QTableWidget(
            DASHBOARD_ROWS,
            len(DASHBOARD_HEADERS),
            dashboard_frame,
        )
        self.table.setHorizontalHeaderLabels(DASHBOARD_HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        header.setDefaultAlignment(QtCore.Qt.AlignCenter)
        header.setMinimumHeight(30)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setFocusPolicy(QtCore.Qt.NoFocus)
        self.table.itemSelectionChanged.connect(self._handle_flight_selection)
        dashboard_layout.addWidget(self.table)
        top_layout.addWidget(dashboard_frame, 0)
        self.dashboard_frame = dashboard_frame
        self.dashboard_anim: QtCore.QPropertyAnimation | None = None
        self.dashboard_frame.setVisible(False)
        self.dashboard_frame.setMinimumWidth(0)
        self.dashboard_frame.setMaximumWidth(0)

        root_layout.addLayout(top_layout, 1)

        control_overlay = QtWidgets.QWidget(map_frame)
        control_overlay.setObjectName("controlOverlay")
        control_overlay.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        control_layout = QtWidgets.QHBoxLayout(control_overlay)
        control_layout.setContentsMargins(10, 10, 10, 10)
        control_layout.setSpacing(8)
        self.playback_toggle = QtWidgets.QPushButton()
        self.playback_toggle.setObjectName("playbackToggle")
        self.playback_toggle.setIcon(QtGui.QIcon(str(RESOURCES_DIR / "plan_sign.png")))
        self.playback_toggle.setIconSize(QtCore.QSize(22, 22))
        self.playback_toggle.setFixedSize(42, 42)
        self.playback_toggle.clicked.connect(self.toggle_playback_panel)
        control_layout.addWidget(self.playback_toggle)

        self.playback_panel = QtWidgets.QFrame()
        self.playback_panel.setObjectName("playbackPanel")
        playback_layout = QtWidgets.QHBoxLayout(self.playback_panel)
        playback_layout.setContentsMargins(8, 6, 8, 6)
        playback_layout.setSpacing(8)
        self.play_button = QtWidgets.QPushButton("Play")
        self.play_button.setObjectName("playbackButtonPrimary")
        self.fast_button = QtWidgets.QPushButton("Fast")
        self.fast_button.setObjectName("playbackButton")
        self.pause_button = QtWidgets.QPushButton("Pause")
        self.pause_button.setObjectName("playbackButton")
        self.stop_button = QtWidgets.QPushButton("Stop")
        self.stop_button.setObjectName("playbackButton")
        playback_layout.addWidget(self.play_button)
        playback_layout.addWidget(self.fast_button)
        playback_layout.addWidget(self.pause_button)
        playback_layout.addWidget(self.stop_button)
        self.playback_panel.setVisible(False)
        self.playback_panel.setMaximumWidth(0)
        self.playback_visible = False
        self.playback_anim: QtCore.QPropertyAnimation | None = None
        control_layout.addWidget(self.playback_panel)
        map_layout.addWidget(
            control_overlay,
            0,
            0,
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignBottom,
        )
        control_overlay.raise_()

        self.time_label = QtWidgets.QLabel(map_frame)
        self.time_label.setObjectName("timeLabel")
        self.time_label.setAlignment(QtCore.Qt.AlignCenter)
        time_font = QtGui.QFont()
        time_font.setPointSize(13)
        time_font.setBold(True)
        self.time_label.setFont(time_font)
        map_layout.addWidget(
            self.time_label,
            0,
            0,
            QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter,
        )
        self.time_label.raise_()

        self.loading_overlay = QtWidgets.QFrame(central)
        self.loading_overlay.setObjectName("appLoadingOverlay")
        self.loading_overlay.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.loading_overlay.setGeometry(central.rect())
        overlay_layout = QtWidgets.QVBoxLayout(self.loading_overlay)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        overlay_layout.setAlignment(QtCore.Qt.AlignCenter)
        loading_card = QtWidgets.QFrame()
        loading_card.setObjectName("appLoadingCard")
        loading_layout = QtWidgets.QVBoxLayout(loading_card)
        loading_layout.setContentsMargins(16, 16, 16, 16)
        loading_layout.setSpacing(8)
        loading_title = QtWidgets.QLabel("Loading")
        loading_title.setObjectName("appLoadingTitle")
        loading_title.setAlignment(QtCore.Qt.AlignCenter)
        loading_subtitle = QtWidgets.QLabel("Preparing system resources...")
        loading_subtitle.setObjectName("appLoadingSubtitle")
        loading_subtitle.setAlignment(QtCore.Qt.AlignCenter)
        loading_bar = QtWidgets.QProgressBar()
        loading_bar.setObjectName("appLoadingBar")
        loading_bar.setRange(0, 0)
        loading_bar.setTextVisible(False)
        loading_bar.setFixedWidth(220)
        loading_layout.addWidget(loading_title)
        loading_layout.addWidget(loading_subtitle)
        loading_layout.addWidget(loading_bar, 0, QtCore.Qt.AlignHCenter)
        overlay_layout.addWidget(loading_card)
        self.loading_overlay.raise_()

        self.table_rows = 0
        self.table_speed_timer = QtCore.QElapsedTimer()
        self.table_speed_timer.start()
        self.table_speed_interval_ms = 250
        self.flight_row_lookup: dict[str, int] = {}
        self.flight_mode_cache: dict[str, str] = {}
        self.selected_flight_name: str | None = None
        self.table_auto_sized = False
        self.simulation = Simulation(
            planner=planner,
            rules=self.rule_state,
            get_traffic_selection=self.get_selected_traffic,
            update_time=self.update_time_label,
            set_dashboard_data=self.set_dashboard_data,
            add_dashboard_row=self.add_dashboard_row,
            update_dashboard_status=self.update_dashboard_status,
            update_speed=self.update_speed_label,
            update_map=self.update_map_positions,
        )
        self.web_channel = QtWebChannel.QWebChannel(self.map_view.page())
        self.control_bridge = ControlBridge(self.simulation, self._send_status_message, self)
        self.web_channel.registerObject("controlBridge", self.control_bridge)
        self.ui_bridge = UiBridge(self)
        self.web_channel.registerObject("uiBridge", self.ui_bridge)
        self.map_view.page().setWebChannel(self.web_channel)

        self.play_button.clicked.connect(self._handle_play)
        self.fast_button.clicked.connect(self._handle_fast)
        self.pause_button.clicked.connect(self._handle_pause)
        self.stop_button.clicked.connect(self._handle_stop)

        self.set_dashboard_data(None)
        self.update_time_label(0)

    def get_selected_traffic(self) -> str | None:
        for name, button in self.panel_traffic_buttons.items():
            if button.isChecked():
                return name
        return None

    def set_dashboard_data(self, rows: list[list[str]] | None) -> None:
        if rows is None:
            rows = [[""] * len(DASHBOARD_HEADERS) for _ in range(DASHBOARD_ROWS)]
            self.selected_flight_name = None
            self.table.clearSelection()
            self.flight_row_lookup.clear()
            self.flight_mode_cache.clear()
        elif not rows:
            self.selected_flight_name = None
            self.table.clearSelection()
            self.flight_row_lookup.clear()
            self.flight_mode_cache.clear()
        self.table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            for col_idx in range(len(DASHBOARD_HEADERS)):
                value = row[col_idx] if col_idx < len(row) else ""
                item = QtWidgets.QTableWidgetItem(value)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(row_idx, col_idx, item)
            name_item = self.table.item(row_idx, COL_NAME)
            if name_item and name_item.text().strip():
                self.flight_row_lookup[name_item.text().strip()] = row_idx
        self.table_rows = len(rows)
        self.table_speed_timer.restart()

    def add_dashboard_row(self, row: list[str]) -> None:
        row_idx = self.table_rows
        self.table.insertRow(row_idx)
        values = [str(row_idx + 1)] + row
        for col_idx in range(len(DASHBOARD_HEADERS)):
            value = values[col_idx] if col_idx < len(values) else ""
            item = QtWidgets.QTableWidgetItem(value)
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(row_idx, col_idx, item)
        name = values[COL_NAME] if len(values) > COL_NAME else ""
        if name:
            self.flight_row_lookup[name] = row_idx
            mode_value = values[COL_MODE] if len(values) > COL_MODE else ""
            if mode_value:
                self.flight_mode_cache[name] = mode_value
        self.table_rows = self.table.rowCount()

    def _update_table_speeds(self, positions: list[dict[str, object]]) -> None:
        if not positions or not self.table_speed_timer.isValid():
            return
        if self.table_speed_timer.elapsed() < self.table_speed_interval_ms:
            return
        self.table_speed_timer.restart()
        viewport = self.table.viewport()
        top_row = self.table.rowAt(0)
        if top_row < 0:
            return
        bottom_row = self.table.rowAt(max(0, viewport.height() - 1))
        if bottom_row < 0:
            bottom_row = self.table.rowCount() - 1
        if bottom_row < top_row:
            return

        visible_names: dict[str, int] = {}
        for row in range(top_row, min(bottom_row + 1, self.table.rowCount())):
            item = self.table.item(row, COL_NAME)
            if item:
                name = item.text().strip()
                if name:
                    visible_names[name] = row

        selected = self.selected_flight_name
        if selected and selected not in visible_names:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, COL_NAME)
                if item and item.text().strip() == selected:
                    visible_names[selected] = row
                    break

        if not visible_names:
            return

        remaining = set(visible_names.keys())
        for pos in positions:
            name = pos.get("name")
            if not name:
                continue
            key = str(name)
            if key not in remaining:
                continue
            row = visible_names[key]
            speed = pos.get("speed_mps")
            if isinstance(speed, (int, float)):
                item = self.table.item(row, COL_SPEED)
                if item is None:
                    item = QtWidgets.QTableWidgetItem()
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                    self.table.setItem(row, COL_SPEED, item)
                text = f"{float(speed):.1f} m/s"
                if item.text() != text:
                    item.setText(text)
            heading = pos.get("heading_deg")
            if not isinstance(heading, (int, float)):
                heading = pos.get("heading")
            if isinstance(heading, (int, float)):
                hdg_item = self.table.item(row, COL_HDG)
                if hdg_item is None:
                    hdg_item = QtWidgets.QTableWidgetItem()
                    hdg_item.setTextAlignment(QtCore.Qt.AlignCenter)
                    self.table.setItem(row, COL_HDG, hdg_item)
                hdg_text = f"{float(heading):.0f} deg"
                if hdg_item.text() != hdg_text:
                    hdg_item.setText(hdg_text)
            lat = pos.get("lat")
            lon = pos.get("lon")
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                pos_item = self.table.item(row, COL_POS)
                if pos_item is None:
                    pos_item = QtWidgets.QTableWidgetItem()
                    pos_item.setTextAlignment(QtCore.Qt.AlignCenter)
                    self.table.setItem(row, COL_POS, pos_item)
                pos_text = f"{float(lat):.5f}, {float(lon):.5f}"
                if pos_item.text() != pos_text:
                    pos_item.setText(pos_text)
            altitude = pos.get("altitude_m")
            if isinstance(altitude, (int, float)):
                alt_item = self.table.item(row, COL_ALT)
                if alt_item is None:
                    alt_item = QtWidgets.QTableWidgetItem()
                    alt_item.setTextAlignment(QtCore.Qt.AlignCenter)
                    self.table.setItem(row, COL_ALT, alt_item)
                alt_text = f"{float(altitude):.1f} m"
                if alt_item.text() != alt_text:
                    alt_item.setText(alt_text)
            remaining.discard(key)
            if not remaining:
                break

    def _find_row_by_name(self, name: str) -> int | None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, COL_NAME)
            if item and item.text().strip() == name:
                return row
        return None

    def _set_row_selectable(self, row: int, selectable: bool) -> None:
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if not item:
                continue
            flags = item.flags()
            if selectable:
                flags |= QtCore.Qt.ItemIsSelectable
            else:
                flags &= ~QtCore.Qt.ItemIsSelectable
            item.setFlags(flags)

    def _rebuild_flight_row_lookup(self) -> None:
        self.flight_row_lookup.clear()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, COL_NAME)
            if item:
                name = item.text().strip()
                if name:
                    self.flight_row_lookup[name] = row
        self.table_rows = self.table.rowCount()

    def _refresh_table_numbers(self) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, COL_NUM)
            if item is None:
                item = QtWidgets.QTableWidgetItem()
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(row, COL_NUM, item)
            item.setText(str(row + 1))

    def _move_rows_to_bottom(self, rows: list[int]) -> None:
        if not rows:
            return
        for row in sorted(set(rows), reverse=True):
            if row < 0 or row >= self.table.rowCount():
                continue
            items = [self.table.takeItem(row, col) for col in range(self.table.columnCount())]
            self.table.removeRow(row)
            insert_row = self.table.rowCount()
            self.table.insertRow(insert_row)
            for col, item in enumerate(items):
                if item is None:
                    item = QtWidgets.QTableWidgetItem("")
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(insert_row, col, item)
        self._refresh_table_numbers()
        self._rebuild_flight_row_lookup()

    def update_dashboard_status(self, statuses: list[dict[str, object]]) -> None:
        if not statuses:
            return
        ended_rows: list[int] = []
        for status in statuses:
            name = str(status.get("name") or "").strip()
            if not name:
                continue
            row = self.flight_row_lookup.get(name)
            if row is None:
                row = self._find_row_by_name(name)
                if row is None:
                    continue
                self.flight_row_lookup[name] = row
            mode = str(status.get("mode") or "").strip()
            if not mode:
                continue
            prev_mode = self.flight_mode_cache.get(name)
            mode_changed = prev_mode != mode
            if mode_changed:
                self.flight_mode_cache[name] = mode
                mode_item = self.table.item(row, COL_MODE)
                if mode_item is None:
                    mode_item = QtWidgets.QTableWidgetItem()
                    mode_item.setTextAlignment(QtCore.Qt.AlignCenter)
                    self.table.setItem(row, COL_MODE, mode_item)
                mode_item.setText(mode)
            if mode in {MODE_WAITING, MODE_TAKEOFF, MODE_LANDING, MODE_ENDED}:
                speed_item = self.table.item(row, COL_SPEED)
                if speed_item is None:
                    speed_item = QtWidgets.QTableWidgetItem()
                    speed_item.setTextAlignment(QtCore.Qt.AlignCenter)
                    self.table.setItem(row, COL_SPEED, speed_item)
                speed_item.setText("0.0 m/s")
            altitude = status.get("altitude_m")
            if isinstance(altitude, (int, float)):
                alt_item = self.table.item(row, COL_ALT)
                if alt_item is None:
                    alt_item = QtWidgets.QTableWidgetItem()
                    alt_item.setTextAlignment(QtCore.Qt.AlignCenter)
                    self.table.setItem(row, COL_ALT, alt_item)
                alt_text = f"{float(altitude):.1f} m"
                if alt_item.text() != alt_text:
                    alt_item.setText(alt_text)
            if mode == MODE_ENDED:
                alt_item = self.table.item(row, COL_ALT)
                if alt_item is None:
                    alt_item = QtWidgets.QTableWidgetItem()
                    alt_item.setTextAlignment(QtCore.Qt.AlignCenter)
                    self.table.setItem(row, COL_ALT, alt_item)
                alt_item.setText(f"{VERTIPORT_ALT_M:.1f} m")
            if mode == MODE_ENDED:
                self._set_row_selectable(row, False)
                ended_rows.append(row)
                if self.selected_flight_name == name:
                    self.selected_flight_name = None
                    self.table.clearSelection()
            else:
                self._set_row_selectable(row, True)
        if ended_rows:
            self._move_rows_to_bottom(ended_rows)

    def update_time_label(self, elapsed_s: int) -> None:
        self.time_label.setText(_format_time(elapsed_s))

    def update_speed_label(self, speed: int) -> None:
        self.fast_button.setText(f"Fast {speed}x")

    def _handle_flight_selection(self) -> None:
        if not self.map_view:
            return
        ranges = self.table.selectedRanges()
        if not ranges:
            return
        row = ranges[0].topRow()
        mode_item = self.table.item(row, COL_MODE)
        if mode_item and mode_item.text().strip() == MODE_ENDED:
            self.table.clearSelection()
            return
        item = self.table.item(row, COL_NAME)
        if not item:
            return
        name = item.text().strip()
        if not name or name == self.selected_flight_name:
            return
        self.selected_flight_name = name
        payload = json.dumps(name, separators=(",", ":"))
        script = (
            "if (window.mapApp && window.mapApp.focusTrafficByName) {"
            f"window.mapApp.focusTrafficByName({payload});"
            "}"
        )
        self.map_view.page().runJavaScript(script)

    def select_flight_by_name(self, name: str) -> None:
        if not name:
            self.clear_flight_selection()
            return
        target = name.strip()
        if not target:
            self.clear_flight_selection()
            return
        row = self.flight_row_lookup.get(target)
        if row is None:
            row = self._find_row_by_name(target)
        if row is None:
            return
        mode_item = self.table.item(row, COL_MODE)
        if mode_item and mode_item.text().strip() == MODE_ENDED:
            return
        self.table.blockSignals(True)
        self.table.selectRow(row)
        self.table.blockSignals(False)
        self.selected_flight_name = target
        item = self.table.item(row, COL_NAME)
        if item:
            self.table.scrollToItem(item, QtWidgets.QAbstractItemView.PositionAtCenter)

    def clear_flight_selection(self) -> None:
        self.table.blockSignals(True)
        self.table.clearSelection()
        self.table.blockSignals(False)
        self.selected_flight_name = None

    def _speed_to_mps(self, value: float, unit: str) -> float:
        if unit == "knot":
            return value * KNOT_TO_MPS
        if unit == "km/h":
            return value / 3.6
        return value

    def _speed_from_mps(self, value: float, unit: str) -> float:
        if unit == "knot":
            return value / KNOT_TO_MPS
        if unit == "km/h":
            return value * 3.6
        return value

    def _set_speed_unit(self, unit: str, value_mps: float | None = None) -> None:
        if not hasattr(self, "speed_unit"):
            self.speed_unit = unit
        if value_mps is None:
            value_mps = self._speed_to_mps(self.rule_speed_value.value(), self.speed_unit)
        self.speed_unit = unit
        next_value = self._speed_from_mps(value_mps, unit)
        self.rule_speed_value.blockSignals(True)
        self.rule_speed_value.setValue(next_value)
        self.rule_speed_value.blockSignals(False)
        for name, button in self.speed_unit_buttons.items():
            button.blockSignals(True)
            button.setChecked(name == unit)
            button.blockSignals(False)

    def _load_rules_into_ui(self, rules: SimulationRules) -> None:
        self._set_speed_unit("knot", rules.speed_mps)
        self.rule_holding_min.setValue(max(0, int(round(rules.holding_s / 60))))
        self.rule_takeoff_min.setValue(max(0, int(round(rules.takeoff_s / 60))))
        self.rule_landing_min.setValue(max(0, int(round(rules.landing_s / 60))))
        self.rule_turn_rate.setValue(rules.turn_rate_deg_s)
        self.rule_sep_m.setValue(rules.separation_m)
        self.rule_warning_m.setValue(rules.warning_m)
        self.rule_warning_ec_s.setValue(rules.warning_ec_s)
        self.rule_warning_trailing_circle.setValue(rules.warning_trailing_circles)
        self.rule_warning_leading_knot.setValue(rules.warning_leading_knot_delta)
        self.rule_caution_m.setValue(rules.caution_m)
        self.rule_caution_ec_s.setValue(rules.caution_ec_s)
        self.rule_caution_trailing_knot.setValue(rules.caution_trailing_knot_delta)
        self.rule_caution_leading_knot.setValue(rules.caution_leading_knot_delta)
        self.operation_start_time.setTime(self._minutes_to_time(rules.operation_start_min))
        self.operation_end_time.setTime(self._minutes_to_time(rules.operation_end_min))
        self.operation_goal_total.setValue(rules.operation_goal_count)
        self._update_rule_distance_labels()
        self._update_operation_time_summary()

    def _collect_rules_from_ui(self) -> SimulationRules:
        speed_mps = self._speed_to_mps(self.rule_speed_value.value(), self.speed_unit)
        holding_s = int(self.rule_holding_min.value()) * 60
        takeoff_s = int(self.rule_takeoff_min.value()) * 60
        landing_s = int(self.rule_landing_min.value()) * 60
        start_min, end_min, _total_min = self._operation_minutes()
        return SimulationRules(
            speed_mps=speed_mps,
            holding_s=holding_s,
            takeoff_s=takeoff_s,
            landing_s=landing_s,
            turn_rate_deg_s=float(self.rule_turn_rate.value()),
            separation_m=int(self.rule_sep_m.value()),
            warning_m=int(self.rule_warning_m.value()),
            warning_ec_s=int(self.rule_warning_ec_s.value()),
            warning_trailing_circles=int(self.rule_warning_trailing_circle.value()),
            warning_leading_knot_delta=int(self.rule_warning_leading_knot.value()),
            caution_m=int(self.rule_caution_m.value()),
            caution_ec_s=int(self.rule_caution_ec_s.value()),
            caution_trailing_knot_delta=int(self.rule_caution_trailing_knot.value()),
            caution_leading_knot_delta=int(self.rule_caution_leading_knot.value()),
            operation_start_min=start_min,
            operation_end_min=end_min,
            operation_goal_count=int(self.operation_goal_total.value()),
        )

    def _apply_rules(self, rules: SimulationRules) -> None:
        self.rule_state = replace(rules)
        if self.simulation:
            self.simulation.update_rules(self.rule_state)

    def _update_rule_distance_labels(self) -> None:
        self.rule_sep_ft.setText(f"({self.rule_sep_m.value() * M_TO_FT:.0f} ft)")
        self.rule_warning_ft.setText(f"({self.rule_warning_m.value() * M_TO_FT:.0f} ft)")
        self.rule_caution_ft.setText(f"({self.rule_caution_m.value() * M_TO_FT:.0f} ft)")

    def _minutes_to_time(self, minutes: int) -> QtCore.QTime:
        value = max(0, int(minutes)) % (24 * 60)
        return QtCore.QTime(value // 60, value % 60)

    def _operation_minutes(self) -> tuple[int, int, int]:
        start_time = self.operation_start_time.time()
        end_time = self.operation_end_time.time()
        start_min = start_time.hour() * 60 + start_time.minute()
        end_min = end_time.hour() * 60 + end_time.minute()
        if end_min <= start_min:
            total_min = 24 * 60 - start_min + end_min
        else:
            total_min = end_min - start_min
        return start_min, end_min, total_min

    def _update_operation_time_summary(self) -> None:
        start_min, end_min, total_min = self._operation_minutes()
        start_str = self._minutes_to_time(start_min).toString("HH:mm")
        end_str = self._minutes_to_time(end_min).toString("HH:mm")
        self.operation_time_summary.setText(
            f"{start_str} ~ {end_str} ({total_min} min total)"
        )
        self._update_operation_goal_summary()

    def _update_operation_goal_summary(self) -> None:
        _start_min, _end_min, total_min = self._operation_minutes()
        total = self.operation_goal_total.value()
        if total_min > 0:
            per_hour = total / (total_min / 60)
            per_30 = total / (total_min / 30)
            per_10 = total / (total_min / 10)
        else:
            per_hour = per_30 = per_10 = 0
        self.operation_goal_summary.setText(
            "시간당 "
            f"{int(round(per_hour))}대, "
            f"30분당 {int(round(per_30))}대, "
            f"10분당 {int(round(per_10))}대 운영 예상"
        )

    def _on_map_loaded(self, ok: bool) -> None:
        if not ok:
            return
        if getattr(self, "map_overlay", None):
            self.map_overlay.setVisible(True)
        if getattr(self, "loading_overlay", None):
            self.loading_overlay.setVisible(False)
        self._map_ready = True
        if self._pending_status_hint is not None:
            self._set_status_hint(self._pending_status_hint)
            self._pending_status_hint = None
        elif not self.get_selected_traffic():
            self._set_status_hint("Please select Daily Traffic in settings.")
        self._flush_status_queue()

    def _handle_play(self) -> None:
        if not self.get_selected_traffic():
            self._set_status_hint("Please select Daily Traffic in settings.")
            self._send_status_message(
                "Select Daily Traffic in settings to start.",
                level="warn",
                ttl_ms=7000,
            )
            return
        self._set_status_hint(None)
        self.simulation.start()
        self._send_status_message("Simulation started.", level="info", ttl_ms=5000)

    def _handle_fast(self) -> None:
        self.simulation.fast()
        self._send_status_message(
            f"Speed set to {self.simulation.speed_multiplier}x.",
            level="info",
            ttl_ms=3000,
        )

    def _handle_pause(self) -> None:
        if self.simulation.running:
            self.simulation.pause()
            self._send_status_message("Simulation paused.", level="info", ttl_ms=4000)

    def _handle_stop(self) -> None:
        self.simulation.stop()
        self._send_status_message("Simulation reset.", level="info", ttl_ms=5000)

    def _handle_panel_save(self) -> None:
        rules = self._collect_rules_from_ui()
        self._apply_rules(rules)
        self._send_status_message("Settings saved.", level="success", ttl_ms=3500)
        self._animate_settings_panel(False)

    def _handle_panel_reset(self) -> None:
        self._apply_rules(self.rule_defaults)
        self._load_rules_into_ui(self.rule_state)
        self._send_status_message("Settings reset.", level="info", ttl_ms=3500)

    def _on_panel_traffic_changed(self, button: QtWidgets.QAbstractButton, checked: bool) -> None:
        if not checked:
            return
        self._set_status_hint(None)
        label = ""
        level = ""
        if button:
            label = button.text()
            level = button.property("trafficLevel") or ""
        if not level and label:
            for key in TRAFFIC_LEVELS:
                if label.upper().startswith(key.upper()):
                    level = key
                    break
        if level:
            goal = TRAFFIC_LEVELS.get(level)
            if goal is not None:
                self.operation_goal_total.setValue(goal)
            display_label = label.replace("\n", " ").strip() if label else level
            self._send_status_message(
                f"Traffic set to {display_label}.",
                level="info",
                ttl_ms=4000,
            )

    def _send_status_message(
        self,
        text: str,
        level: str = "info",
        ttl_ms: int | None = 6000,
    ) -> None:
        if not text:
            return
        payload: dict[str, object] = {"text": text, "level": level}
        if ttl_ms is not None:
            payload["ttlMs"] = ttl_ms
        if not self._map_ready:
            self._status_queue.append(payload)
            return
        payload_json = json.dumps(payload, separators=(",", ":"))
        script = (
            "if (window.mapApp && window.mapApp.addStatusMessage) {"
            f"window.mapApp.addStatusMessage({payload_json});"
            "}"
        )
        self.map_view.page().runJavaScript(script)

    def _set_status_hint(self, text: str | None) -> None:
        if not self._map_ready:
            self._pending_status_hint = text
            return
        payload = json.dumps(text or "", separators=(",", ":"))
        script = (
            "if (window.mapApp && window.mapApp.setStatusHint) {"
            f"window.mapApp.setStatusHint({payload});"
            "}"
        )
        self.map_view.page().runJavaScript(script)

    def _flush_status_queue(self) -> None:
        if not self._map_ready or not self._status_queue:
            return
        queued = self._status_queue[:]
        self._status_queue.clear()
        for payload in queued:
            payload_json = json.dumps(payload, separators=(",", ":"))
            script = (
                "if (window.mapApp && window.mapApp.addStatusMessage) {"
                f"window.mapApp.addStatusMessage({payload_json});"
                "}"
            )
            self.map_view.page().runJavaScript(script)

    def toggle_settings_panel(self) -> None:
        if not self.settings_panel:
            return
        if self.settings_panel.isVisible():
            self._animate_settings_panel(False)
        else:
            self._animate_settings_panel(True)

    def toggle_dashboard_panel(self) -> None:
        self._animate_dashboard_panel(not self.dashboard_visible)

    def toggle_playback_panel(self) -> None:
        self._animate_playback_panel(not self.playback_visible)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        if getattr(self, "loading_overlay", None):
            self.loading_overlay.setGeometry(self.centralWidget().rect())
        if getattr(self, "dashboard_visible", False):
            self._sync_dashboard_width()

    def _dashboard_target_width(self) -> int:
        base_width = self.centralWidget().width() if self.centralWidget() else self.width()
        target = int(base_width * 0.34)
        return max(360, min(target, 620))

    def _sync_dashboard_width(self) -> None:
        if not getattr(self, "dashboard_frame", None):
            return
        if not self.dashboard_visible:
            return
        target = self._dashboard_target_width()
        self.dashboard_frame.setMinimumWidth(target)
        self.dashboard_frame.setMaximumWidth(target)

    def _request_map_resize(self) -> None:
        if not getattr(self, "map_view", None):
            return
        script = (
            "if (window.mapApp && window.mapApp.map && window.mapApp.map.resize) {"
            "window.mapApp.map.resize();"
            "}"
        )
        self.map_view.page().runJavaScript(script)

    def _update_dashboard_toggle(self) -> None:
        if not getattr(self, "dashboard_toggle", None):
            return
        if self.dashboard_visible:
            self.dashboard_toggle.setText(">")
            self.dashboard_toggle.setToolTip("Hide table")
        else:
            self.dashboard_toggle.setText("<")
            self.dashboard_toggle.setToolTip("Show table")

    def _animate_dashboard_panel(self, show: bool) -> None:
        if not getattr(self, "dashboard_frame", None):
            return
        if self.dashboard_anim:
            self.dashboard_anim.stop()
        panel = self.dashboard_frame
        target = self._dashboard_target_width()
        if getattr(self, "map_view", None):
            self.map_view.setUpdatesEnabled(False)
        panel.setUpdatesEnabled(False)
        if show:
            panel.setVisible(True)
            panel.setMinimumWidth(0)
            panel.setMaximumWidth(0)
            start_value = 0
            end_value = target
        else:
            start_value = panel.width()
            end_value = 0
            panel.setMinimumWidth(0)

        anim = QtCore.QPropertyAnimation(panel, b"maximumWidth")
        anim.setDuration(180)
        anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        anim.setStartValue(start_value)
        anim.setEndValue(end_value)

        def _finish() -> None:
            self.dashboard_visible = show
            if show:
                panel.setMinimumWidth(target)
                panel.setMaximumWidth(target)
            else:
                panel.setVisible(False)
                panel.setMinimumWidth(0)
                panel.setMaximumWidth(0)
            self._update_dashboard_toggle()
            panel.setUpdatesEnabled(True)
            if getattr(self, "map_view", None):
                self.map_view.setUpdatesEnabled(True)
            self._request_map_resize()

        anim.finished.connect(_finish)
        self.dashboard_anim = anim
        anim.start()

    def _animate_playback_panel(self, show: bool) -> None:
        if not getattr(self, "playback_panel", None):
            return
        if self.playback_anim:
            self.playback_anim.stop()
        panel = self.playback_panel
        target = panel.sizeHint().width()
        if show:
            panel.setVisible(True)
            panel.setMaximumWidth(0)
            start_value = 0
            end_value = target
        else:
            start_value = panel.width()
            end_value = 0

        anim = QtCore.QPropertyAnimation(panel, b"maximumWidth")
        anim.setDuration(220)
        anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        anim.setStartValue(start_value)
        anim.setEndValue(end_value)

        def _finish() -> None:
            self.playback_visible = show
            if show:
                panel.setMaximumWidth(target)
            else:
                panel.setVisible(False)
                panel.setMaximumWidth(target)

        anim.finished.connect(_finish)
        self.playback_anim = anim
        anim.start()

    def _animate_settings_panel(self, show: bool) -> None:
        if not self.settings_panel:
            return
        if not hasattr(self, "settings_panel_anim"):
            self.settings_panel_anim: QtCore.QPropertyAnimation | None = None
        if self.settings_panel_anim:
            self.settings_panel_anim.stop()

        panel = self.settings_panel
        full_height = panel.sizeHint().height()
        if show:
            panel.setVisible(True)
            panel.setMaximumHeight(0)
            start_value = 0
            end_value = full_height
        else:
            start_value = panel.height()
            end_value = 0

        anim = QtCore.QPropertyAnimation(panel, b"maximumHeight")
        anim.setDuration(240)
        anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        anim.setStartValue(start_value)
        anim.setEndValue(end_value)

        def _finish() -> None:
            if show:
                panel.setMaximumHeight(full_height)
            else:
                panel.setVisible(False)
                panel.setMaximumHeight(full_height)

        anim.finished.connect(_finish)
        self.settings_panel_anim = anim
        anim.start()

    def update_map_positions(self, positions: list[dict[str, object]]) -> None:
        if not self.map_view:
            return
        if positions and not self.table_auto_sized:
            for pos in positions:
                if pos.get("name"):
                    self.table.resizeColumnsToContents()
                    self.table_auto_sized = True
                    break
        self._apply_prediction_path(positions)
        payload = json.dumps(positions, separators=(",", ":"))
        script = (
            "if (window.mapApp && window.mapApp.updateTrafficPositions) {"
            f"window.mapApp.updateTrafficPositions({payload});"
            "}"
        )
        self.map_view.page().runJavaScript(script)
        self._update_table_speeds(positions)

    def _apply_prediction_path(self, positions: list[dict[str, object]]) -> None:
        selected = self.selected_flight_name
        if not selected or not positions:
            return
        path = self._build_prediction_path(selected)
        hold_path = self._build_hold_path(selected)
        if not path and not hold_path:
            return
        for item in positions:
            if item.get("name") == selected:
                if path:
                    item["predict_path"] = path
                if hold_path:
                    item["hold_path"] = hold_path
                return

    def _build_prediction_path(self, name: str) -> list[list[float]] | None:
        if not self.simulation:
            return None
        flight = None
        for entry in self.simulation.flights:
            if entry.name == name:
                flight = entry
                break
        if not flight:
            return None
        state = self.simulation.flight_state.get(flight.flight_id)
        if not state or state.get("phase") != "cruise":
            return None
        dist_m = state.get("dist_m")
        speed_mps = state.get("speed_mps")
        if not isinstance(dist_m, (int, float)) or not isinstance(speed_mps, (int, float)):
            return None
        if speed_mps <= 0:
            return None
        horizon_s = float(getattr(self.simulation.rules, "risk_predict_horizon_s", 20.0))
        if not math.isfinite(horizon_s) or horizon_s <= 0.0:
            horizon_s = 20.0
        total_dist_m = float(flight.total_dist_m)
        start_dist = float(dist_m)
        remaining_m = total_dist_m - start_dist
        if remaining_m <= 0.0:
            return None
        max_horizon_s = remaining_m / float(speed_mps)
        horizon_s = min(horizon_s, max_horizon_s)
        if horizon_s <= 0.0:
            return None
        step_s = 4.0
        steps = int(horizon_s // step_s)
        dt_list = [step_s] * steps
        remainder = horizon_s - step_s * steps
        if remainder > 1e-6:
            dt_list.append(remainder)
        if not dt_list:
            dt_list = [horizon_s]
        projection = self.simulation.planner.projection
        points: list[list[float]] = []
        dist = start_dist
        pos_xy = _position_at_distance(flight.points_xy, flight.cum_dist_m, dist)
        lon, lat = projection.to_lonlat(pos_xy[0], pos_xy[1])
        points.append([lon, lat])
        for dt in dt_list:
            dist = min(total_dist_m, dist + float(speed_mps) * dt)
            pos_xy = _position_at_distance(flight.points_xy, flight.cum_dist_m, dist)
            lon, lat = projection.to_lonlat(pos_xy[0], pos_xy[1])
            points.append([lon, lat])
            if dist >= total_dist_m:
                break
        return points

    def _build_hold_path(self, name: str) -> list[list[float]] | None:
        if not self.simulation:
            return None
        flight = None
        for entry in self.simulation.flights:
            if entry.name == name:
                flight = entry
                break
        if not flight:
            return None
        control = self.simulation.flight_controls.get(flight.flight_id)
        if not control or not control.hold_active or not control.hold_center_xy:
            return None
        radius_m = float(control.hold_radius_m)
        if radius_m <= 0:
            return None
        center_x, center_y = control.hold_center_xy
        radius_km = radius_m / 1000.0
        steps = 36
        projection = self.simulation.planner.projection
        points: list[list[float]] = []
        for idx in range(steps + 1):
            angle = (2.0 * math.pi * idx) / steps
            x = center_x + radius_km * math.cos(angle)
            y = center_y + radius_km * math.sin(angle)
            lon, lat = projection.to_lonlat(x, y)
            points.append([lon, lat])
        return points

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        tooltip = None
        if isinstance(obj, QtWidgets.QWidget):
            tooltip = obj.property("ruleTooltipText")
        if tooltip:
            if event.type() == QtCore.QEvent.Enter:
                QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), str(tooltip), obj)
            elif event.type() == QtCore.QEvent.Leave:
                QtWidgets.QToolTip.hideText()
        return super().eventFilter(obj, event)


def main() -> int:
    mbtiles = MBTiles(MBTILES_PATH)
    server = TileServer(
        mbtiles=mbtiles,
        web_dir=WEB_DIR,
        resources_dir=RESOURCES_DIR,
        data_dir=DATA_DIR,
        host=SERVER_HOST,
        port=SERVER_PORT,
    )
    server.start()

    planner = RoutePlanner.from_csv(
        DATA_DIR / "default" / "vertiport_default.csv",
        DATA_DIR / "default" / "csv",
    )

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(APPLE_STYLE)
    window = MapWindow(server.url, planner)

    def _cleanup() -> None:
        server.stop()
        mbtiles.close()

    app.aboutToQuit.connect(_cleanup)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
