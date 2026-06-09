"""
VFDS Dynamics Dispatch System - MAVLink multi-aircraft telemetry receiver.

This receiver listens on the shared GCS UDP port, separates traffic by MAVLink
sysid, requests the telemetry streams needed by the dashboard, and normalizes
incoming packets into AircraftStatus cache updates.
"""

from __future__ import annotations

import asyncio
import logging
import math
import threading
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from .cache import status_cache
from .models import ActuatorData, AircraftStatus, AttitudeData, PositionData, VelocityNedData
from .normalizer import get_home

logger = logging.getLogger(__name__)

_PWM_MIN = 1000
_PWM_MAX = 2000
_PWM_CTR = 1500
_REQUEST_RATE_HZ = 10


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _pwm_to_01(pwm: int) -> float:
    return max(0.0, min(1.0, (pwm - _PWM_MIN) / (_PWM_MAX - _PWM_MIN)))


def _pwm_to_deg(pwm: int, max_deg: float = 30.0) -> float:
    half = _PWM_CTR - _PWM_MIN
    return max(-max_deg, min(max_deg, (pwm - _PWM_CTR) / half * max_deg))


def _ned_to_lla(
    north_m: float,
    east_m: float,
    down_m: float,
    home_lat: float,
    home_lon: float,
    home_alt: float,
) -> tuple[float, float, float]:
    radius = 6378137.0
    d_lat = north_m / radius
    cos_lat = math.cos(math.radians(home_lat)) or 1e-9
    d_lon = east_m / (radius * cos_lat)
    lat_deg = home_lat + math.degrees(d_lat)
    lon_deg = home_lon + math.degrees(d_lon)
    alt_m = home_alt - down_m
    return lat_deg, lon_deg, alt_m


class _AircraftBuffer:
    def __init__(self) -> None:
        self.position: dict[str, float] | None = None
        self.attitude: dict[str, float] | None = None
        self.velocity_ned: dict[str, float] = {"north": 0.0, "east": 0.0, "down": 0.0}
        self.actuator: dict[str, float] = {
            "tilt_left": 0.0,
            "tilt_right": 0.0,
            "aileron": 0.0,
            "rudder_left": 0.0,
            "rudder_right": 0.0,
        }
        self.motor_rpm: list[float] | None = None
        self.ts: str = ""


class MavlinkMultiReceiver:
    def __init__(
        self,
        port: int,
        sysid_to_id: dict[int, str],
        ws_manager: Any,
        dtam_manager: Any | None = None,
    ) -> None:
        self.port = port
        self.sysid_to_id = sysid_to_id
        self.ws_manager = ws_manager
        self.dtam_manager = dtam_manager

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._buffers: dict[str, _AircraftBuffer] = {}
        self._requested_streams: set[int] = set()
        self._published: set[str] = set()
        self._message_counts: Counter[str] = Counter()
        self._lock = threading.Lock()
        self._debug: dict[str, Any] = {
            "running": False,
            "port": self.port,
            "knownSysids": dict(self.sysid_to_id),
            "firstHeartbeatReceived": False,
            "lastMessageType": None,
            "lastAircraftId": None,
            "lastSysid": None,
            "lastRxTs": None,
            "lastError": None,
            "requestedSysids": [],
            "publishedAircraft": [],
        }

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._set_debug(running=True, lastError=None)
        self._thread = threading.Thread(
            target=self._run,
            name="mavlink-multi-rx",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "MAVLink multi-receiver started on UDP port %d | sysid map: %s",
            self.port,
            self.sysid_to_id,
        )

    def stop(self) -> None:
        self._stop_event.set()
        self._set_debug(running=False)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            data = dict(self._debug)
            data["messageCounts"] = dict(self._message_counts)
            data["requestedSysids"] = sorted(self._requested_streams)
            data["publishedAircraft"] = sorted(self._published)
            data["cacheSize"] = len(status_cache.get_all())
            return data

    def _set_debug(self, **updates: Any) -> None:
        with self._lock:
            self._debug.update(updates)

    def _record_message(self, msg_type: str, aircraft_id: str | None, sysid: int) -> None:
        with self._lock:
            self._message_counts[msg_type] += 1
            self._debug["lastMessageType"] = msg_type
            self._debug["lastAircraftId"] = aircraft_id
            self._debug["lastSysid"] = sysid
            self._debug["lastRxTs"] = _utc_now()

    def _run(self) -> None:
        try:
            from pymavlink import mavutil
        except ImportError:
            error = "pymavlink is not installed. Run 'pip install pymavlink'."
            self._set_debug(running=False, lastError=error)
            logger.error(error)
            return

        try:
            mav = mavutil.mavlink_connection(
                f"udpin:0.0.0.0:{self.port}",
                dialect="ardupilotmega",
            )
            logger.info("UDP %d: socket opened, waiting for MAVLink packets...", self.port)
        except Exception as e:
            error = f"MAVLink connection failed on port {self.port}: {e}"
            self._set_debug(running=False, lastError=error)
            logger.error(error)
            return

        wanted_types = [
            "HEARTBEAT",
            "GLOBAL_POSITION_INT",
            "LOCAL_POSITION_NED",
            "ATTITUDE",
            "SERVO_OUTPUT_RAW",
            "ACTUATOR_OUTPUT_STATUS",
            "ESC_STATUS",
        ]
        unknown_sysids: set[int] = set()

        while not self._stop_event.is_set():
            try:
                msg = mav.recv_match(type=wanted_types, blocking=True, timeout=0.5)
            except Exception as e:
                error = f"recv_match failed: {e}"
                self._set_debug(lastError=error)
                logger.error("UDP %d: %s", self.port, error)
                continue

            if msg is None:
                continue

            msg_type = msg.get_type()
            sysid = int(msg.get_srcSystem())
            compid = int(msg.get_srcComponent())
            aircraft_id = self.sysid_to_id.get(sysid)
            self._record_message(msg_type, aircraft_id, sysid)

            if aircraft_id is None:
                if sysid not in unknown_sysids:
                    logger.warning(
                        "UDP %d: ignoring unknown sysid=%d (known sysids: %s)",
                        self.port,
                        sysid,
                        sorted(self.sysid_to_id.keys()),
                    )
                    unknown_sysids.add(sysid)
                continue

            if msg_type == "HEARTBEAT":
                if not self.snapshot()["firstHeartbeatReceived"]:
                    logger.info("UDP %d: first heartbeat from %s (sysid=%d)", self.port, aircraft_id, sysid)
                self._set_debug(firstHeartbeatReceived=True)

            if sysid not in self._requested_streams:
                self._request_streams(mav, sysid, compid)

            buf = self._buffers.setdefault(aircraft_id, _AircraftBuffer())
            self._handle(msg, buf, aircraft_id)

    def _request_streams(self, mav: Any, sysid: int, compid: int) -> None:
        mavlink = getattr(mav, "mavlink", None)
        if mavlink is None:
            try:
                from pymavlink import mavutil

                mavlink = mavutil.mavlink
            except Exception as e:
                logger.debug("UDP %d: MAVLink definitions unavailable: %s", self.port, e)
                mavlink = None

        try:
            mav.mav.request_data_stream_send(
                sysid,
                compid,
                mavlink.MAV_DATA_STREAM_ALL if mavlink is not None else 0,
                _REQUEST_RATE_HZ,
                1,
            )
        except Exception as e:
            logger.debug("UDP %d: request_data_stream failed for sysid=%d: %s", self.port, sysid, e)

        interval_us = int(1_000_000 / _REQUEST_RATE_HZ)
        for name in [
            "GLOBAL_POSITION_INT",
            "LOCAL_POSITION_NED",
            "ATTITUDE",
            "SERVO_OUTPUT_RAW",
            "ACTUATOR_OUTPUT_STATUS",
            "ESC_STATUS",
        ]:
            if mavlink is None:
                continue
            msg_id = getattr(mavlink, f"MAVLINK_MSG_ID_{name}", None)
            if msg_id is None:
                continue
            try:
                mav.mav.command_long_send(
                    sysid,
                    compid,
                    mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                    0,
                    float(msg_id),
                    float(interval_us),
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                )
            except Exception as e:
                logger.debug(
                    "UDP %d: interval request failed for sysid=%d msg=%s: %s",
                    self.port,
                    sysid,
                    name,
                    e,
                )

        self._requested_streams.add(sysid)
        self._set_debug(requestedSysids=sorted(self._requested_streams))
        logger.info("UDP %d: requested telemetry streams for sysid=%d", self.port, sysid)

    def _handle(self, msg: Any, buf: _AircraftBuffer, aircraft_id: str) -> None:
        msg_type = msg.get_type()

        if msg_type == "GLOBAL_POSITION_INT":
            buf.ts = _utc_now()
            prev = buf.position or {}
            buf.position = {
                "lat": msg.lat / 1e7,
                "lon": msg.lon / 1e7,
                "alt": msg.alt / 1000.0,
                "north": prev.get("north", 0.0),
                "east": prev.get("east", 0.0),
                "down": -(msg.relative_alt / 1000.0),
            }

        elif msg_type == "LOCAL_POSITION_NED":
            buf.ts = _utc_now()
            north = float(msg.x)
            east = float(msg.y)
            down = float(msg.z)
            buf.velocity_ned = {
                "north": float(getattr(msg, "vx", 0.0)),
                "east": float(getattr(msg, "vy", 0.0)),
                "down": float(getattr(msg, "vz", 0.0)),
            }
            if buf.position is not None:
                buf.position.update({"north": north, "east": east, "down": down})
            else:
                home = get_home(aircraft_id)
                lat, lon, alt = _ned_to_lla(
                    north,
                    east,
                    down,
                    home["lat"],
                    home["lon"],
                    home["alt"],
                )
                buf.position = {
                    "lat": lat,
                    "lon": lon,
                    "alt": alt,
                    "north": north,
                    "east": east,
                    "down": down,
                }

        elif msg_type == "ATTITUDE":
            buf.ts = buf.ts or _utc_now()
            buf.attitude = {
                "roll": math.degrees(float(msg.roll)),
                "pitch": math.degrees(float(msg.pitch)),
                "yaw": math.degrees(float(msg.yaw)),
            }

        elif msg_type == "SERVO_OUTPUT_RAW":
            s = lambda ch: getattr(msg, f"servo{ch}_raw", _PWM_CTR)
            buf.actuator = {
                "tilt_left": _pwm_to_01(s(5)),
                "tilt_right": _pwm_to_01(s(6)),
                "aileron": _pwm_to_deg(s(7)),
                "rudder_left": _pwm_to_deg(s(9)),
                "rudder_right": _pwm_to_deg(s(10)),
            }

        elif msg_type == "ACTUATOR_OUTPUT_STATUS":
            outputs = list(getattr(msg, "actuator", []))
            if outputs:
                def output(idx: int, default: float = 0.0) -> float:
                    return float(outputs[idx]) if idx < len(outputs) else default

                buf.actuator = {
                    "tilt_left": max(0.0, min(1.0, output(4))),
                    "tilt_right": max(0.0, min(1.0, output(5))),
                    "aileron": max(-30.0, min(30.0, output(6) * 30.0)),
                    "rudder_left": max(-30.0, min(30.0, output(8) * 30.0)),
                    "rudder_right": max(-30.0, min(30.0, output(9) * 30.0)),
                }

        elif msg_type == "ESC_STATUS":
            rpms = getattr(msg, "rpm", [0.0, 0.0, 0.0, 0.0])
            buf.motor_rpm = [float(r) for r in list(rpms)[:4]]
            while len(buf.motor_rpm) < 4:
                buf.motor_rpm.append(0.0)

        if msg_type != "HEARTBEAT" and (buf.position is not None or buf.attitude is not None):
            self._publish(aircraft_id, buf)

    def _publish(self, aircraft_id: str, buf: _AircraftBuffer) -> None:
        existing = status_cache.get_status(aircraft_id)
        motor_rpm = (
            buf.motor_rpm
            if buf.motor_rpm is not None
            else (existing.motorRpm if existing else [0.0, 0.0, 0.0, 0.0])
        )
        status = AircraftStatus(
            aircraftId=aircraft_id,
            flightPlanNumber=existing.flightPlanNumber if existing else 0,
            ts=buf.ts or (existing.ts if existing else "") or _utc_now(),
            missionState=existing.missionState if existing else "WAITING",
            phase=existing.phase if existing else "N/A",
            seq=existing.seq if existing else 0,
            position=PositionData(**(buf.position or {})),
            attitude=AttitudeData(**(buf.attitude or {})),
            velocityNed=VelocityNedData(**buf.velocity_ned),
            actuator=ActuatorData(**buf.actuator),
            motorRpm=list(motor_rpm),
        )

        status_cache.update_status(aircraft_id, status)

        if aircraft_id not in self._published:
            self._published.add(aircraft_id)
            self._set_debug(publishedAircraft=sorted(self._published))
            logger.info(
                "UDP %d: first telemetry publish for %s | lat=%.6f lon=%.6f alt=%.1f",
                self.port,
                aircraft_id,
                status.position.lat,
                status.position.lon,
                status.position.alt,
            )

        if self._loop and not self._loop.is_closed():
            try:
                asyncio.run_coroutine_threadsafe(
                    self.ws_manager.broadcast(status.model_dump_json()),
                    self._loop,
                )
                if self.dtam_manager is not None:
                    asyncio.run_coroutine_threadsafe(
                        self.dtam_manager.broadcast_status(status),
                        self._loop,
                    )
            except Exception as e:
                logger.error("WebSocket broadcast failed for %s: %s", aircraft_id, e)
        else:
            logger.warning("Event loop unavailable; broadcast skipped for %s", aircraft_id)


_receiver: MavlinkMultiReceiver | None = None
MAVLINK_GCS_PORT = 14550


def get_mavlink_debug_snapshot() -> dict[str, Any]:
    if _receiver is None:
        return {
            "running": False,
            "port": MAVLINK_GCS_PORT,
            "knownSysids": {},
            "firstHeartbeatReceived": False,
            "lastMessageType": None,
            "lastAircraftId": None,
            "lastSysid": None,
            "lastRxTs": None,
            "lastError": "receiver not started",
            "requestedSysids": [],
            "publishedAircraft": [],
            "messageCounts": {},
            "cacheSize": len(status_cache.get_all()),
        }
    return _receiver.snapshot()


async def start_mavlink_receiver(
    sysid_to_id: dict[int, str],
    ws_manager: Any,
    port: int = MAVLINK_GCS_PORT,
    dtam_manager: Any | None = None,
) -> None:
    global _receiver
    loop = asyncio.get_running_loop()
    _receiver = MavlinkMultiReceiver(port, sysid_to_id, ws_manager, dtam_manager)
    _receiver.start(loop)


def stop_mavlink_receiver() -> None:
    global _receiver
    if _receiver is not None:
        _receiver.stop()
        _receiver = None
