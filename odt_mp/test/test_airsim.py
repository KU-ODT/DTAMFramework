from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Optional
import math


def _load_qt():
    try:
        from PyQt6 import QtCore, QtWidgets
    except ImportError:
        from PyQt5 import QtCore, QtWidgets  # type: ignore
    return QtCore, QtWidgets


def _load_airsim():
    try:
        import airsim as _airsim

        return _airsim, "airsim"
    except Exception:
        root = Path(__file__).resolve().parents[1]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        try:
            from app import airsim as _airsim

            return _airsim, "app.airsim"
        except Exception as exc:
            raise RuntimeError(f"AirSim import error: {exc}") from exc


QtCore, QtWidgets = _load_qt()


class AirsimController:
    def __init__(self, log_fn: Callable[[str], None]) -> None:
        self._client = None
        self._vehicle_name = ""
        self._airsim = None
        self._log = log_fn

    def connect(self, host: str, port: int, vehicle_name: str) -> bool:
        if self._client is not None:
            self._log("Already connected.")
            return True
        try:
            airsim, label = _load_airsim()
        except Exception as exc:
            self._log(str(exc))
            return False
        client = airsim.MultirotorClient(ip=host, port=port)
        try:
            client.confirmConnection()
            if vehicle_name:
                client.enableApiControl(True, vehicle_name=vehicle_name)
                client.armDisarm(True, vehicle_name=vehicle_name)
                client.takeoffAsync(vehicle_name=vehicle_name).join()
            else:
                client.enableApiControl(True)
                client.armDisarm(True)
                client.takeoffAsync().join()
        except Exception as exc:
            self._log(f"Connect failed: {exc}")
            return False
        self._airsim = airsim
        self._client = client
        self._vehicle_name = vehicle_name
        self._log(f"Connected via {label}.")
        return True

    def disconnect(self) -> None:
        if self._client is None:
            self._log("Not connected.")
            return
        client = self._client
        vehicle_name = self._vehicle_name
        try:
            try:
                client.cancelLastTask()
            except Exception:
                pass
            try:
                if vehicle_name:
                    client.hoverAsync(vehicle_name=vehicle_name).join(timeout=2)
                else:
                    client.hoverAsync().join(timeout=2)
            except Exception:
                pass
            try:
                if vehicle_name:
                    client.landAsync(vehicle_name=vehicle_name).join(timeout=2)
                else:
                    client.landAsync().join(timeout=2)
            except Exception:
                pass
            try:
                client.reset()
            except Exception:
                pass
            try:
                if vehicle_name:
                    client.armDisarm(False, vehicle_name=vehicle_name)
                    client.enableApiControl(False, vehicle_name=vehicle_name)
                else:
                    client.armDisarm(False)
                    client.enableApiControl(False)
            except Exception:
                pass
        finally:
            self._client = None
            self._vehicle_name = ""
            self._airsim = None
            self._log("Disconnected and reset.")

    def move_to_position(
        self,
        x: float,
        y: float,
        z: float,
        speed: float,
        body_relative: bool,
        yaw_follow: bool,
    ) -> None:
        if self._client is None:
            self._log("Not connected.")
            return
        client = self._client
        vehicle_name = self._vehicle_name
        try:
            base, yaw = self._get_current_state()
            if base is None:
                base = (0.0, 0.0, 0.0)
            if body_relative:
                offset = self._body_to_world(x, y, z, yaw)
            else:
                offset = (x, y, z)
            target = (base[0] + offset[0], base[1] + offset[1], base[2] + offset[2])
            yaw_mode = None
            if yaw_follow:
                dn, de = offset[0], offset[1]
                if abs(dn) > 1e-3 or abs(de) > 1e-3:
                    yaw_deg = math.degrees(math.atan2(de, dn))
                    yaw_mode = self._airsim.YawMode(False, yaw_deg) if self._airsim else None
            if vehicle_name:
                if yaw_mode is None:
                    client.moveToPositionAsync(*target, speed, vehicle_name=vehicle_name).join()
                else:
                    client.moveToPositionAsync(
                        *target, speed, yaw_mode=yaw_mode, vehicle_name=vehicle_name
                    ).join()
            else:
                if yaw_mode is None:
                    client.moveToPositionAsync(*target, speed).join()
                else:
                    client.moveToPositionAsync(*target, speed, yaw_mode=yaw_mode).join()
            self._log(
                f"moveToPosition ({'body' if body_relative else 'ned'}): "
                f"{x:.3f}, {y:.3f}, {z:.3f} -> {target[0]:.3f}, {target[1]:.3f}, {target[2]:.3f}"
            )
        except Exception as exc:
            self._log(f"Move failed: {exc}")

    def move_to_gps(self, lat: float, lon: float, alt: float, speed: float) -> None:
        if self._client is None:
            self._log("Not connected.")
            return
        client = self._client
        vehicle_name = self._vehicle_name
        try:
            if vehicle_name:
                client.moveToGPSAsync(lat, lon, alt, speed, vehicle_name=vehicle_name).join()
            else:
                client.moveToGPSAsync(lat, lon, alt, speed).join()
            self._log(f"moveToGPS: {lat:.6f}, {lon:.6f}, {alt:.3f} @ {speed:.2f} m/s")
        except Exception as exc:
            self._log(f"Move failed: {exc}")

    def move_on_path(
        self,
        points: list[tuple[float, float, float]],
        speed: float,
        body_relative: bool,
        yaw_follow: bool,
    ) -> None:
        if self._client is None:
            self._log("Not connected.")
            return
        if not points:
            self._log("Path is empty.")
            return
        if self._airsim is None:
            self._log("AirSim module not available.")
            return
        client = self._client
        vehicle_name = self._vehicle_name
        try:
            base, yaw = self._get_current_state()
            if base is None:
                base = (0.0, 0.0, 0.0)
            abs_points = []
            for x, y, z in points:
                if body_relative:
                    off = self._body_to_world(x, y, z, yaw)
                else:
                    off = (x, y, z)
                abs_points.append((base[0] + off[0], base[1] + off[1], base[2] + off[2]))
            vecs = [self._airsim.Vector3r(x, y, z) for x, y, z in abs_points]
            yaw_mode = None
            if yaw_follow and abs_points:
                dn = abs_points[0][0] - base[0]
                de = abs_points[0][1] - base[1]
                if abs(dn) > 1e-3 or abs(de) > 1e-3:
                    yaw_deg = math.degrees(math.atan2(de, dn))
                    yaw_mode = self._airsim.YawMode(False, yaw_deg) if self._airsim else None
            if vehicle_name:
                if yaw_mode is None:
                    client.moveOnPathAsync(vecs, speed, vehicle_name=vehicle_name).join()
                else:
                    client.moveOnPathAsync(
                        vecs, speed, yaw_mode=yaw_mode, vehicle_name=vehicle_name
                    ).join()
            else:
                if yaw_mode is None:
                    client.moveOnPathAsync(vecs, speed).join()
                else:
                    client.moveOnPathAsync(vecs, speed, yaw_mode=yaw_mode).join()
            self._log(f"moveOnPath ({'body' if body_relative else 'ned'}): {len(points)} points")
        except Exception as exc:
            self._log(f"Move failed: {exc}")

    def _get_current_state(self) -> tuple[Optional[tuple[float, float, float]], Optional[float]]:
        if self._client is None:
            return None, None
        client = self._client
        vehicle_name = self._vehicle_name
        try:
            if vehicle_name:
                state = client.getMultirotorState(vehicle_name=vehicle_name)
            else:
                state = client.getMultirotorState()
        except Exception as exc:
            self._log(f"Current position unavailable: {exc}")
            return None, None
        if state is None or not hasattr(state, "kinematics_estimated"):
            return None, None
        pos = state.kinematics_estimated.position
        if pos is None:
            return None, None
        yaw = None
        if self._airsim and hasattr(state.kinematics_estimated, "orientation"):
            orientation = state.kinematics_estimated.orientation
            try:
                _, _, yaw = self._airsim.to_eularian_angles(orientation)
            except Exception:
                yaw = None
        return (float(pos.x_val), float(pos.y_val), float(pos.z_val)), yaw

    def _body_to_world(
        self, forward: float, right: float, down: float, yaw: Optional[float]
    ) -> tuple[float, float, float]:
        if yaw is None:
            return (forward, right, down)
        n = math.cos(yaw) * forward - math.sin(yaw) * right
        e = math.sin(yaw) * forward + math.cos(yaw) * right
        return (n, e, down)


class AirsimTestWindow(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AirSim Test Console")
        self._controller = AirsimController(self._append_log)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QGridLayout()

        self.host_input = QtWidgets.QLineEdit("127.0.0.1")
        self.port_input = QtWidgets.QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(41451)
        self.vehicle_input = QtWidgets.QLineEdit("UAM1")

        self.x_input = self._make_double(-100000.0, 100000.0, 10.0)
        self.y_input = self._make_double(-100000.0, 100000.0, 10.0)
        self.z_input = self._make_double(-100000.0, 100000.0, -10.0)
        self.speed_input = self._make_double(0.1, 100.0, 8.0, 1)

        self.gps_lat_input = self._make_double(-90.0, 90.0, 37.514097, 6)
        self.gps_lon_input = self._make_double(-180.0, 180.0, 127.069388, 6)
        self.gps_alt_input = self._make_double(-10000.0, 100000.0, 5.0, 3)

        form.addWidget(QtWidgets.QLabel("Host"), 0, 0)
        form.addWidget(self.host_input, 0, 1)
        form.addWidget(QtWidgets.QLabel("Port"), 0, 2)
        form.addWidget(self.port_input, 0, 3)
        form.addWidget(QtWidgets.QLabel("Vehicle"), 0, 4)
        form.addWidget(self.vehicle_input, 0, 5)

        form.addWidget(QtWidgets.QLabel("Forward (x)"), 1, 0)
        form.addWidget(self.x_input, 1, 1)
        form.addWidget(QtWidgets.QLabel("Right (y)"), 1, 2)
        form.addWidget(self.y_input, 1, 3)
        form.addWidget(QtWidgets.QLabel("Down (z)"), 1, 4)
        form.addWidget(self.z_input, 1, 5)

        form.addWidget(QtWidgets.QLabel("Speed (m/s)"), 2, 0)
        form.addWidget(self.speed_input, 2, 1)

        form.addWidget(QtWidgets.QLabel("GPS Lat"), 3, 0)
        form.addWidget(self.gps_lat_input, 3, 1)
        form.addWidget(QtWidgets.QLabel("GPS Lon"), 3, 2)
        form.addWidget(self.gps_lon_input, 3, 3)
        form.addWidget(QtWidgets.QLabel("GPS Alt"), 3, 4)
        form.addWidget(self.gps_alt_input, 3, 5)

        layout.addLayout(form)

        button_row = QtWidgets.QHBoxLayout()
        self.connect_button = QtWidgets.QPushButton("Connect")
        self.disconnect_button = QtWidgets.QPushButton("Disconnect")
        self.move_pos_button = QtWidgets.QPushButton("MoveToPosition")
        self.move_gps_button = QtWidgets.QPushButton("MoveToGPS")
        self.move_path_button = QtWidgets.QPushButton("MoveOnPath")
        self.body_frame_check = QtWidgets.QCheckBox("Body-relative")
        self.body_frame_check.setChecked(True)
        self.yaw_follow_check = QtWidgets.QCheckBox("Align heading")
        self.yaw_follow_check.setChecked(True)
        button_row.addWidget(self.connect_button)
        button_row.addWidget(self.move_pos_button)
        button_row.addWidget(self.move_gps_button)
        button_row.addWidget(self.move_path_button)
        button_row.addWidget(self.body_frame_check)
        button_row.addWidget(self.yaw_follow_check)
        button_row.addWidget(self.disconnect_button)
        layout.addLayout(button_row)

        layout.addWidget(QtWidgets.QLabel("Path (Forward, Right, Down per line):"))
        self.path_input = QtWidgets.QPlainTextEdit()
        self.path_input.setPlaceholderText("0, 0, -5\n10, 0, -5\n10, 10, -5")
        layout.addWidget(self.path_input)

        self.log_view = QtWidgets.QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)

        self.connect_button.clicked.connect(self._handle_connect)
        self.disconnect_button.clicked.connect(self._handle_disconnect)
        self.move_pos_button.clicked.connect(self._handle_move_position)
        self.move_gps_button.clicked.connect(self._handle_move_gps)
        self.move_path_button.clicked.connect(self._handle_move_path)

    def _make_double(self, minimum: float, maximum: float, value: float, decimals: int = 3):
        box = QtWidgets.QDoubleSpinBox()
        box.setRange(minimum, maximum)
        box.setDecimals(decimals)
        box.setValue(value)
        return box

    def _append_log(self, message: str) -> None:
        self.log_view.append(message)

    def _handle_connect(self) -> None:
        host = self.host_input.text().strip() or "127.0.0.1"
        port = int(self.port_input.value())
        vehicle = self.vehicle_input.text().strip()
        if self._controller.connect(host, port, vehicle):
            self.connect_button.setEnabled(False)

    def _handle_disconnect(self) -> None:
        self._controller.disconnect()
        self.connect_button.setEnabled(True)

    def _handle_move_position(self) -> None:
        x = float(self.x_input.value())
        y = float(self.y_input.value())
        z = float(self.z_input.value())
        speed = float(self.speed_input.value())
        body_relative = self.body_frame_check.isChecked()
        yaw_follow = self.yaw_follow_check.isChecked()
        self._controller.move_to_position(x, y, z, speed, body_relative, yaw_follow)

    def _handle_move_gps(self) -> None:
        lat = float(self.gps_lat_input.value())
        lon = float(self.gps_lon_input.value())
        alt = float(self.gps_alt_input.value())
        speed = float(self.speed_input.value())
        self._controller.move_to_gps(lat, lon, alt, speed)

    def _handle_move_path(self) -> None:
        points = self._parse_path_points()
        if points is None:
            return
        speed = float(self.speed_input.value())
        body_relative = self.body_frame_check.isChecked()
        yaw_follow = self.yaw_follow_check.isChecked()
        self._controller.move_on_path(points, speed, body_relative, yaw_follow)

    def _parse_path_points(self) -> Optional[list[tuple[float, float, float]]]:
        text = self.path_input.toPlainText()
        points: list[tuple[float, float, float]] = []
        for index, raw in enumerate(text.splitlines(), start=1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            cleaned = line.replace(",", " ").replace(";", " ").replace("\t", " ")
            parts = [part for part in cleaned.split(" ") if part]
            if len(parts) != 3:
                self._append_log(f"Invalid path line {index}: {raw}")
                return None
            try:
                x, y, z = (float(part) for part in parts)
            except ValueError:
                self._append_log(f"Invalid path line {index}: {raw}")
                return None
            points.append((x, y, z))
        if not points:
            self._append_log("Path is empty.")
            return None
        return points


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    window = AirsimTestWindow()
    window.resize(860, 520)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
