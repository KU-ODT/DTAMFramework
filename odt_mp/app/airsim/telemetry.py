from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional


class AirsimTelemetry:
    def __init__(self, emit_fn: Callable[[dict], None], poll_sec: float = 0.5) -> None:
        self._emit = emit_fn
        self._poll_sec = poll_sec
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._client = None
        self._host = "127.0.0.1"
        self._port = 41451
        self._vehicle_name = ""
        self._last_log = 0.0
        self._last_miss_log = 0.0
        self._last_flip_log = 0.0

    def start(self, host: str, port: int, vehicle_name: str = "") -> None:
        self.stop()
        self._host = host
        self._port = port
        self._vehicle_name = vehicle_name
        self._last_log = 0.0
        print(
            f"[AirSim] Telemetry start: host={self._host}, port={self._port}, "
            f"vehicle={self._vehicle_name or 'default'}"
        )
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
        self._thread = None
        self._client = None

    def _run(self) -> None:
        airsim = None
        try:
            import airsim as _airsim

            airsim = _airsim
        except Exception:
            try:
                from app import airsim as _airsim

                airsim = _airsim
                print("[AirSim] Telemetry using bundled client (app.airsim).")
            except Exception as exc:
                print(f"[AirSim] Telemetry import error: {exc}")
                return

        client = airsim.MultirotorClient(ip=self._host, port=self._port)
        self._client = client
        try:
            client.confirmConnection()
        except Exception as exc:
            print(f"[AirSim] Telemetry connect failed: {exc}")
            return
        print("[AirSim] Telemetry connected.")

        while not self._stop_event.is_set():
            try:
                if self._vehicle_name:
                    gps = client.getGpsData(vehicle_name=self._vehicle_name)
                else:
                    gps = client.getGpsData()
                if gps is None:
                    self._log_missing("gps data missing")
                    time.sleep(self._poll_sec)
                    continue
                loc = None
                if hasattr(gps, "gps_location"):
                    loc = gps.gps_location
                elif hasattr(gps, "gnss") and hasattr(gps.gnss, "geo_point"):
                    loc = gps.gnss.geo_point
                elif hasattr(gps, "geo_point"):
                    loc = gps.geo_point
                if loc is None:
                    self._log_missing("gps_location missing")
                    time.sleep(self._poll_sec)
                    continue
                lat = _to_float(getattr(loc, "latitude", None))
                lon = _to_float(getattr(loc, "longitude", None))
                alt = _to_float(getattr(loc, "altitude", None))
                if lat is None or lon is None or alt is None:
                    self._log_missing("gps values missing")
                    time.sleep(self._poll_sec)
                    continue
                if abs(lat) < 0.1 and abs(lon) < 0.1:
                    self._log_missing("gps values near zero")
                    time.sleep(self._poll_sec)
                    continue
                if alt < 0:
                    alt = -alt
                    now = time.time()
                    if now - self._last_flip_log >= 2.0:
                        self._last_flip_log = now
                        print("[AirSim] Telemetry: altitude flipped from NED.")
                payload = {
                    "name": self._vehicle_name or "UAM1",
                    "lat": lat,
                    "lon": lon,
                    "alt_m": alt,
                }
                self._emit(payload)
                now = time.time()
                if now - self._last_log >= 2.0:
                    self._last_log = now
                    print(
                        f"[AirSim] Telemetry: {payload['name']} "
                        f"{lat:.6f}, {lon:.6f}, {alt:.2f}"
                    )
            except Exception as exc:
                print(f"[AirSim] Telemetry error: {exc}")
                time.sleep(1.0)
            time.sleep(self._poll_sec)

    def _log_missing(self, reason: str) -> None:
        now = time.time()
        if now - self._last_miss_log >= 2.0:
            self._last_miss_log = now
            print(f"[AirSim] Telemetry skipped: {reason}")


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
