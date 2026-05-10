from __future__ import annotations

from typing import Optional

from app.gui.qt import QUrl, QtCore, QtWidgets, QtWebChannel, QtWebEngineWidgets
from app.airsim.telemetry import AirsimTelemetry


class AirsimBridge(QtCore.QObject):
    positionUpdated = QtCore.pyqtSignal("QVariant")

    def __init__(self, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._runner = None
        self._runner_error: Optional[Exception] = None
        self._telemetry = AirsimTelemetry(self._emit_telemetry)
        try:
            from app.airsim.mission_runner import AirsimMissionRunner

            self._runner = AirsimMissionRunner()
        except Exception as exc:
            self._runner_error = exc

    @QtCore.pyqtSlot("QVariant")
    def startMission(self, payload: object) -> None:
        if self._runner is None:
            if self._runner_error:
                print(f"[AirSim] Mission runner unavailable: {self._runner_error}")
            else:
                print("[AirSim] Mission runner unavailable.")
            return
        if isinstance(payload, dict):
            self._runner.start_mission(payload)
        else:
            print("[AirSim] Invalid mission payload.")

    @QtCore.pyqtSlot("QVariant")
    def startTelemetry(self, payload: object) -> None:
        if not isinstance(payload, dict):
            print("[AirSim] Invalid telemetry payload.")
            return
        host = str(payload.get("host") or "127.0.0.1")
        port = int(payload.get("port") or 41451)
        vehicle_name = str(payload.get("vehicle_name") or "")
        print(f"[AirSim] Telemetry request for {host}:{port} {vehicle_name or 'default'}")
        self._telemetry.start(host, port, vehicle_name)

    @QtCore.pyqtSlot()
    def stopTelemetry(self) -> None:
        self._telemetry.stop()

    @QtCore.pyqtSlot()
    def stopMission(self) -> None:
        if self._runner is None:
            return
        self._runner.stop_mission()
        self._telemetry.stop()

    def _emit_telemetry(self, payload: dict) -> None:
        self.positionUpdated.emit(payload)


class MapView(QtWebEngineWidgets.QWebEngineView):
    def __init__(self, url: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setUrl(QUrl(url))


class MapWindow(QtWidgets.QMainWindow):
    def __init__(self, url: str, title: Optional[str] = None) -> None:
        super().__init__()
        if title:
            self.setWindowTitle(title)

        self._view = MapView(url, parent=self)
        self._channel = QtWebChannel.QWebChannel(self._view.page())
        self._bridge = AirsimBridge(self)
        self._channel.registerObject("airsimBridge", self._bridge)
        self._view.page().setWebChannel(self._channel)
        self.setCentralWidget(self._view)
        self.setMinimumSize(800, 600)
