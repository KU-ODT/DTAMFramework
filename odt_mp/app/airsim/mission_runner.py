from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional
import math
import threading
import time

from app.airsim.coord_transform import wgs84_to_airsim_ned, wgs84_to_local_ned


@dataclass
class MissionWaypoint:
    name: str
    lat: Optional[float]
    lon: Optional[float]
    alt_m: float
    n: float
    e: float
    d: float


class AirsimMissionRunner:
    def __init__(self, speed_mps: float = 30.0) -> None:
        self._speed_mps = speed_mps
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._client = None

    def start_mission(self, payload: dict) -> None:
        host = str(payload.get("host") or "127.0.0.1")
        port = int(payload.get("port") or 41451)
        vehicle_name = str(payload.get("vehicle_name") or "")
        snap_to_first_waypoint = payload.get("snap_to_first_waypoint")
        if snap_to_first_waypoint is None:
            snap_to_first_waypoint = False
        snap_to_first_waypoint = bool(snap_to_first_waypoint)
        snap_to_last_waypoint = payload.get("snap_to_last_waypoint")
        if snap_to_last_waypoint is None:
            snap_to_last_waypoint = False
        snap_to_last_waypoint = bool(snap_to_last_waypoint)
        relative_to_start = payload.get("relative_to_start")
        if relative_to_start is None:
            relative_to_start = True
        relative_to_start = bool(relative_to_start)
        body_relative = payload.get("body_relative")
        if body_relative is None:
            body_relative = False
        body_relative = bool(body_relative)
        yaw_follow = payload.get("yaw_follow")
        if yaw_follow is None:
            yaw_follow = True
        yaw_follow = bool(yaw_follow)
        route = payload.get("route") or []
        waypoints = self._normalize_route(route)
        if not waypoints:
            print("[AirSim] Mission aborted: empty route.")
            return
        self._start_thread(
            host,
            port,
            vehicle_name,
            waypoints,
            snap_to_first_waypoint,
            snap_to_last_waypoint,
            relative_to_start,
            body_relative,
            yaw_follow,
        )

    def stop_mission(self) -> None:
        self._stop_event.set()
        with self._lock:
            client = self._client
        if client is None:
            return
        try:
            client.cancelLastTask()
        except Exception:
            pass
        try:
            client.hoverAsync().join(timeout=2)
        except Exception:
            pass
        try:
            client.landAsync().join(timeout=2)
        except Exception:
            pass
        try:
            client.reset()
        except Exception:
            pass
        try:
            client.armDisarm(False)
            client.enableApiControl(False)
        except Exception:
            pass

    def _start_thread(
        self,
        host: str,
        port: int,
        vehicle_name: str,
        waypoints: list[MissionWaypoint],
        snap_to_first_waypoint: bool,
        snap_to_last_waypoint: bool,
        relative_to_start: bool,
        body_relative: bool,
        yaw_follow: bool,
    ) -> None:
        self._stop_event.clear()
        if self._thread and self._thread.is_alive():
            self.stop_mission()
            self._thread.join(timeout=2)
        self._thread = threading.Thread(
            target=self._run_mission,
            args=(
                host,
                port,
                vehicle_name,
                waypoints,
                snap_to_first_waypoint,
                snap_to_last_waypoint,
                relative_to_start,
                body_relative,
                yaw_follow,
            ),
            daemon=True,
        )
        self._thread.start()

    def _run_mission(
        self,
        host: str,
        port: int,
        vehicle_name: str,
        waypoints: list[MissionWaypoint],
        snap_to_first_waypoint: bool,
        snap_to_last_waypoint: bool,
        relative_to_start: bool,
        body_relative: bool,
        yaw_follow: bool,
    ) -> None:
        airsim = None
        try:
            import airsim as _airsim
            airsim = _airsim
        except Exception:
            try:
                from app import airsim as _airsim
                airsim = _airsim
                print("[AirSim] Using bundled client (app.airsim).")
            except Exception as exc:
                print(f"[AirSim] Import error: {exc}")
                return

        client = airsim.MultirotorClient(ip=host, port=port)
        with self._lock:
            self._client = client
        try:
            client.confirmConnection()
            if vehicle_name:
                client.enableApiControl(True, vehicle_name=vehicle_name)
                client.armDisarm(True, vehicle_name=vehicle_name)
            else:
                client.enableApiControl(True)
                client.armDisarm(True)

            origin = self._get_local_origin(client, vehicle_name)
            if origin:
                self._apply_local_ned(waypoints, origin)
                if waypoints:
                    first = waypoints[0]
                    print(
                        f"[AirSim] Local NED start {first.name}: "
                        f"{first.n:.3f}, {first.e:.3f}, {first.d:.3f}"
                    )
            if snap_to_first_waypoint and waypoints:
                self._snap_vehicle_to_waypoint(client, vehicle_name, waypoints[0], airsim)
            if relative_to_start:
                self._apply_relative_to_start(waypoints)
            self._log_final_route(waypoints, relative_to_start)

            if self._stop_event.is_set():
                return

            if vehicle_name:
                client.takeoffAsync(vehicle_name=vehicle_name).join()
            else:
                client.takeoffAsync().join()

            self._climb_takeoff_clearance(client, vehicle_name, 150.0, airsim)
            base_pos, base_yaw = self._get_current_state(client, vehicle_name, airsim)
            if base_pos is None:
                base_pos = (0.0, 0.0, 0.0)
            print(f"[AirSim] Base NED: {base_pos[0]:.3f}, {base_pos[1]:.3f}, {base_pos[2]:.3f}")
            if body_relative and base_yaw is not None:
                print(f"[AirSim] Base yaw (rad): {base_yaw:.3f}")

            takeoff_d = base_pos[2]
            last_target = base_pos
            last_index = len(waypoints) - 1
            for index, wp in enumerate(waypoints):
                if self._stop_event.is_set():
                    break
                target_n, target_e, target_d = self._resolve_target(
                    wp, base_pos, relative_to_start, body_relative, base_yaw
                )
                if index == 0 or index == last_index:
                    target_d = takeoff_d
                yaw_mode = None
                if yaw_follow:
                    dn = target_n - last_target[0]
                    de = target_e - last_target[1]
                    if abs(dn) > 1e-3 or abs(de) > 1e-3:
                        yaw_deg = math.degrees(math.atan2(de, dn))
                        yaw_mode = airsim.YawMode(False, yaw_deg)
                if vehicle_name:
                    if yaw_mode is None:
                        client.moveToPositionAsync(
                            target_n, target_e, target_d, self._speed_mps, vehicle_name=vehicle_name
                        ).join()
                    else:
                        client.moveToPositionAsync(
                            target_n,
                            target_e,
                            target_d,
                            self._speed_mps,
                            yaw_mode=yaw_mode,
                            vehicle_name=vehicle_name,
                        ).join()
                else:
                    if yaw_mode is None:
                        client.moveToPositionAsync(target_n, target_e, target_d, self._speed_mps).join()
                    else:
                        client.moveToPositionAsync(
                            target_n, target_e, target_d, self._speed_mps, yaw_mode=yaw_mode
                        ).join()
                last_target = (target_n, target_e, target_d)
                time.sleep(0.05)

            if not self._stop_event.is_set() and waypoints:
                final_wp = waypoints[-1]
                target_n, target_e, target_d = self._resolve_target(
                    final_wp, base_pos, relative_to_start, body_relative, base_yaw
                )
                yaw_mode = None
                if yaw_follow:
                    dn = target_n - last_target[0]
                    de = target_e - last_target[1]
                    if abs(dn) > 1e-3 or abs(de) > 1e-3:
                        yaw_deg = math.degrees(math.atan2(de, dn))
                        yaw_mode = airsim.YawMode(False, yaw_deg)
                if vehicle_name:
                    if yaw_mode is None:
                        client.moveToPositionAsync(
                            target_n, target_e, target_d, self._speed_mps, vehicle_name=vehicle_name
                        ).join()
                    else:
                        client.moveToPositionAsync(
                            target_n,
                            target_e,
                            target_d,
                            self._speed_mps,
                            yaw_mode=yaw_mode,
                            vehicle_name=vehicle_name,
                        ).join()
                else:
                    if yaw_mode is None:
                        client.moveToPositionAsync(target_n, target_e, target_d, self._speed_mps).join()
                    else:
                        client.moveToPositionAsync(
                            target_n, target_e, target_d, self._speed_mps, yaw_mode=yaw_mode
                        ).join()

            if not self._stop_event.is_set():
                if vehicle_name:
                    client.landAsync(vehicle_name=vehicle_name).join()
                else:
                    client.landAsync().join()
                if snap_to_last_waypoint and waypoints:
                    self._snap_vehicle_to_waypoint(client, vehicle_name, waypoints[-1], airsim)
        except Exception as exc:
            print(f"[AirSim] Mission error: {exc}")
        finally:
            try:
                if vehicle_name:
                    client.armDisarm(False, vehicle_name=vehicle_name)
                    client.enableApiControl(False, vehicle_name=vehicle_name)
                else:
                    client.armDisarm(False)
                    client.enableApiControl(False)
            except Exception:
                pass
            with self._lock:
                self._client = None

    def _normalize_route(self, route: Iterable[Any]) -> list[MissionWaypoint]:
        waypoints: list[MissionWaypoint] = []
        for idx, item in enumerate(route):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or f"WP{idx + 1}")
            lat = _to_float(item.get("lat"))
            lon = _to_float(item.get("lon"))
            alt_m = _to_float(item.get("alt_m") or item.get("altitude_m")) or 0.0
            ned = _extract_ned(item.get("ned"))
            if ned is None and lat is not None and lon is not None:
                n, e, d = wgs84_to_airsim_ned(lat, lon, alt_m)
            elif ned is not None:
                n, e, d = ned
            else:
                continue
            waypoints.append(
                MissionWaypoint(
                    name=name,
                    lat=lat,
                    lon=lon,
                    alt_m=alt_m,
                    n=float(n),
                    e=float(e),
                    d=float(d),
                )
            )
        return waypoints

    def _get_local_origin(
        self, client: Any, vehicle_name: str
    ) -> Optional[tuple[float, float, float]]:
        origin = self._get_home_geopoint(client, vehicle_name)
        if origin is not None:
            lat, lon, alt = origin
            print(f"[AirSim] Local NED origin (home): {lat:.6f}, {lon:.6f}, {alt:.2f}")
            return origin
        origin = self._get_gps_origin(client, vehicle_name)
        if origin is not None:
            lat, lon, alt = origin
            print(f"[AirSim] Local NED origin (gps): {lat:.6f}, {lon:.6f}, {alt:.2f}")
            return origin
        print("[AirSim] Local NED origin unavailable; using payload NED.")
        return None

    def _get_home_geopoint(
        self, client: Any, vehicle_name: str
    ) -> Optional[tuple[float, float, float]]:
        try:
            if vehicle_name:
                geo = client.getHomeGeoPoint(vehicle_name=vehicle_name)
            else:
                geo = client.getHomeGeoPoint()
        except Exception as exc:
            print(f"[AirSim] Home geopoint unavailable: {exc}")
            return None
        if geo is None:
            return None
        lat = _to_float(getattr(geo, "latitude", None))
        lon = _to_float(getattr(geo, "longitude", None))
        alt = _to_float(getattr(geo, "altitude", None))
        return _validate_geo(lat, lon, alt)

    def _get_gps_origin(self, client: Any, vehicle_name: str) -> Optional[tuple[float, float, float]]:
        try:
            if vehicle_name:
                gps = client.getGpsData(vehicle_name=vehicle_name)
            else:
                gps = client.getGpsData()
        except Exception as exc:
            print(f"[AirSim] GPS origin unavailable: {exc}")
            return None
        if gps is None or not hasattr(gps, "gps_location"):
            return None
        loc = gps.gps_location
        lat = _to_float(getattr(loc, "latitude", None))
        lon = _to_float(getattr(loc, "longitude", None))
        alt = _to_float(getattr(loc, "altitude", None))
        return _validate_geo(lat, lon, alt)

    def _apply_local_ned(self, waypoints: list[MissionWaypoint], origin: tuple[float, float, float]) -> None:
        lat0, lon0, alt0 = origin
        for wp in waypoints:
            if wp.lat is None or wp.lon is None:
                continue
            n, e, d = wgs84_to_local_ned(wp.lat, wp.lon, wp.alt_m, lat0, lon0, alt0)
            wp.n = float(n)
            wp.e = float(e)
            wp.d = float(d)

    def _apply_relative_to_start(self, waypoints: list[MissionWaypoint]) -> None:
        if not waypoints:
            return
        start = waypoints[0]
        base_n, base_e, base_d = start.n, start.e, start.d
        for wp in waypoints:
            wp.n -= base_n
            wp.e -= base_e
            wp.d -= base_d

    def _snap_vehicle_to_waypoint(
        self,
        client: Any,
        vehicle_name: str,
        waypoint: MissionWaypoint,
        airsim: Any,
    ) -> None:
        _pos, yaw = self._get_current_state(client, vehicle_name, airsim)
        target_yaw = yaw if yaw is not None else 0.0
        pose = airsim.Pose(
            airsim.Vector3r(float(waypoint.n), float(waypoint.e), float(waypoint.d)),
            _to_airsim_quaternion(airsim, 0.0, 0.0, float(target_yaw)),
        )
        try:
            if vehicle_name:
                client.simSetVehiclePose(pose, ignore_collision=True, vehicle_name=vehicle_name)
            else:
                client.simSetVehiclePose(pose, ignore_collision=True)
            time.sleep(0.1)
            print(
                f"[AirSim] Snapped to first waypoint {waypoint.name}: "
                f"{waypoint.n:.3f}, {waypoint.e:.3f}, {waypoint.d:.3f}"
            )
        except Exception as exc:
            print(f"[AirSim] Snap to first waypoint failed: {exc}")

    def _climb_takeoff_clearance(
        self,
        client: Any,
        vehicle_name: str,
        climb_m: float,
        airsim: Any,
        hold_sec: float = 0.0,
    ) -> None:
        if climb_m <= 0:
            return
        pos, _ = self._get_current_state(client, vehicle_name, airsim)
        if pos is None:
            return
        target_z = float(pos[2] - climb_m)
        try:
            if vehicle_name:
                client.moveToZAsync(target_z, self._speed_mps, vehicle_name=vehicle_name).join()
            else:
                client.moveToZAsync(target_z, self._speed_mps).join()
            print(f"[AirSim] Takeoff clearance: {climb_m:.1f}m (z={target_z:.2f})")
            if hold_sec > 0:
                time.sleep(hold_sec)
                print(f"[AirSim] Takeoff hold: {hold_sec:.1f}s")
        except Exception as exc:
            print(f"[AirSim] Takeoff clearance failed: {exc}")

    def _log_final_route(self, waypoints: list[MissionWaypoint], relative_to_start: bool) -> None:
        if not waypoints:
            return
        label = "Final NED route (relative)" if relative_to_start else "Final NED route"
        print(f"[AirSim] {label}:")
        for wp in waypoints:
            if wp.lat is None or wp.lon is None:
                print(f"[AirSim] {wp.name} : {wp.n:.3f} : {wp.e:.3f} : {wp.d:.3f}")
            else:
                print(
                    f"[AirSim] {wp.name} : {wp.lat:.6f} : {wp.lon:.6f} : {wp.alt_m:.3f} : "
                    f"{wp.n:.3f} : {wp.e:.3f} : {wp.d:.3f}"
                )

    def _get_current_state(
        self, client: Any, vehicle_name: str, airsim: Any
    ) -> tuple[Optional[tuple[float, float, float]], Optional[float]]:
        try:
            if vehicle_name:
                state = client.getMultirotorState(vehicle_name=vehicle_name)
            else:
                state = client.getMultirotorState()
        except Exception as exc:
            print(f"[AirSim] Current position unavailable: {exc}")
            return None, None
        if state is None or not hasattr(state, "kinematics_estimated"):
            return None, None
        kin = state.kinematics_estimated
        pos = getattr(kin, "position", None)
        if pos is None:
            return None, None
        yaw = None
        try:
            orientation = getattr(kin, "orientation", None)
            if orientation is not None:
                _, _, yaw = airsim.to_eularian_angles(orientation)
        except Exception:
            yaw = None
        return (float(pos.x_val), float(pos.y_val), float(pos.z_val)), yaw

    def _body_to_world(
        self, forward: float, right: float, down: float, yaw: Optional[float]
    ) -> tuple[float, float, float]:
        if yaw is None:
            return forward, right, down
        n = math.cos(yaw) * forward - math.sin(yaw) * right
        e = math.sin(yaw) * forward + math.cos(yaw) * right
        return n, e, down

    def _resolve_target(
        self,
        wp: MissionWaypoint,
        base_pos: tuple[float, float, float],
        relative_to_start: bool,
        body_relative: bool,
        base_yaw: Optional[float],
    ) -> tuple[float, float, float]:
        offset_n = wp.n
        offset_e = wp.e
        offset_d = wp.d
        if body_relative:
            offset_n, offset_e, offset_d = self._body_to_world(
                offset_n, offset_e, offset_d, base_yaw
            )
        target_n = offset_n + base_pos[0] if relative_to_start else offset_n
        target_e = offset_e + base_pos[1] if relative_to_start else offset_e
        target_d = offset_d + base_pos[2] if relative_to_start else offset_d
        return target_n, target_e, target_d


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_airsim_quaternion(airsim: Any, pitch: float, roll: float, yaw: float) -> Any:
    if hasattr(airsim, "to_quaternion"):
        return airsim.to_quaternion(pitch, roll, yaw)
    if hasattr(airsim, "euler_to_quaternion"):
        return airsim.euler_to_quaternion(roll, pitch, yaw)

    cr = math.cos(roll * 0.5)
    sr = math.sin(roll * 0.5)
    cp = math.cos(pitch * 0.5)
    sp = math.sin(pitch * 0.5)
    cy = math.cos(yaw * 0.5)
    sy = math.sin(yaw * 0.5)
    return airsim.Quaternionr(
        cy * sr * cp - sy * cr * sp,
        cy * cr * sp + sy * sr * cp,
        sy * cr * cp - cy * sr * sp,
        cy * cr * cp + sy * sr * sp,
    )


def _extract_ned(value: Any) -> Optional[Tuple[float, float, float]]:
    if value is None:
        return None
    if isinstance(value, dict):
        n = _to_float(value.get("n"))
        e = _to_float(value.get("e"))
        d = _to_float(value.get("d"))
        if n is None or e is None or d is None:
            return None
        return (n, e, d)
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        n = _to_float(value[0])
        e = _to_float(value[1])
        d = _to_float(value[2])
        if n is None or e is None or d is None:
            return None
        return (n, e, d)
    return None


def _validate_geo(
    lat: Optional[float], lon: Optional[float], alt: Optional[float]
) -> Optional[tuple[float, float, float]]:
    if lat is None or lon is None or alt is None:
        return None
    if not (math.isfinite(lat) and math.isfinite(lon) and math.isfinite(alt)):
        return None
    if abs(lat) < 0.1 and abs(lon) < 0.1:
        return None
    return (float(lat), float(lon), float(alt))
