from __future__ import annotations

import asyncio
import math
import threading
from typing import Any, Callable, Dict, List, Optional, Sequence

from app.airsim.coord_transform import wgs84_to_airsim_ned
from app.converter_tool import (
    DEFAULT_CUSTOM_X_AXIS_HEADING_DEG,
    DEFAULT_CUSTOM_Y_AXIS_HEADING_DEG,
    convert_target_to_unreal,
)
from modules.simpleDynamics.core.types import FlightTrajectoryPoint, SimulationConfig
from modules.simpleDynamics.simulator import UAMFlightSimulator


class SimpleDynamicsSimulatorService:
    def __init__(self, emit_fn: Callable[[dict], None]) -> None:
        self._emit = emit_fn
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._threads: List[threading.Thread] = []

        self._connected = False
        self._host = "127.0.0.1"
        self._port = 41451
        self._connected_vehicles: List[str] = []
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._last_error = ""

    def connect(
        self,
        host: str,
        port: int,
        vehicle_names: Optional[Sequence[str] | str] = None,
    ) -> Dict[str, Any]:
        host_text = str(host or "127.0.0.1")
        port_num = int(port)
        requested_count = 1
        if isinstance(vehicle_names, str):
            requested_count = 1
        elif vehicle_names is not None:
            try:
                requested_count = max(len(list(vehicle_names)), 1)
            except TypeError:
                requested_count = 1
        requested_vehicles = _normalize_vehicle_names(vehicle_names, count=requested_count)
        airsim, client = self._open_airsim_client(host_text, port_num)

        try:
            reachable = bool(client.ping())
        except Exception as exc:
            raise RuntimeError(
                f"Cannot reach AirSim RPC at {host_text}:{port_num}. "
                "Check that AirSim is running and the port is correct."
            ) from exc
        if not reachable:
            raise RuntimeError(
                f"AirSim RPC at {host_text}:{port_num} did not respond. "
                "Check that AirSim is running and API access is available."
            )

        validated: List[str] = []
        for vehicle in requested_vehicles:
            try:
                client.getMultirotorState(vehicle_name=vehicle)
            except Exception as exc:
                raise RuntimeError(
                    f"Connected to AirSim at {host_text}:{port_num}, but vehicle "
                    f"'{vehicle}' is not available."
                ) from exc

            try:
                client.enableApiControl(True, vehicle_name=vehicle)
            except Exception:
                pass

            try:
                client.armDisarm(True, vehicle_name=vehicle)
            except Exception:
                pass

            validated.append(vehicle)

        with self._lock:
            self._connected = True
            self._host = host_text
            self._port = port_num
            self._connected_vehicles = validated
            self._last_error = ""
        return self.get_status()

    def disconnect(self) -> Dict[str, Any]:
        self.stop()
        with self._lock:
            host = self._host
            port = self._port
            vehicles = list(self._connected_vehicles)
            self._connected = False
            self._connected_vehicles = []
        try:
            _, client = self._open_airsim_client(host, port)
            for vehicle in vehicles:
                try:
                    client.enableApiControl(False, vehicle_name=vehicle)
                except Exception:
                    continue
        except Exception:
            pass
        return self.get_status()

    def start(
        self,
        mission_records: List[Dict[str, Any]] | Dict[str, Any],
        replay_step_s: float = 0.1,
        playback_speed_x: float = 1.0,
        sync_to_airsim: bool = True,
        vehicle_names: Optional[Sequence[str] | str] = None,
    ) -> Dict[str, Any]:
        self.stop()

        records = mission_records if isinstance(mission_records, list) else [mission_records]
        if not records:
            raise RuntimeError("No mission records were provided for simulation.")

        config = SimulationConfig(tick_s=0.1)
        simulator = UAMFlightSimulator(config=config)
        results = simulator.run_from_json(records)
        if not results:
            raise RuntimeError("simpleDynamics did not return a trajectory.")

        replay_step = max(float(replay_step_s), 0.1)
        playback_speed = min(max(float(playback_speed_x), 1.0), 8.0)
        assigned_vehicles = _normalize_vehicle_names(vehicle_names, count=len(results))

        with self._lock:
            if sync_to_airsim and not self._connected:
                raise RuntimeError("AirSim sync requested before connect.")
            if sync_to_airsim:
                missing_vehicles = [
                    vehicle
                    for vehicle in assigned_vehicles
                    if vehicle not in self._connected_vehicles
                ]
                if missing_vehicles:
                    missing_text = ", ".join(missing_vehicles)
                    raise RuntimeError(
                        f"AirSim sync is missing connected vehicles: {missing_text}"
                    )

        jobs: Dict[str, Dict[str, Any]] = {}
        for index, result in enumerate(results):
            trajectory = list(result.trajectory)
            if sync_to_airsim:
                trajectory = _trim_airsim_sync_trajectory(trajectory)
            report_points = _sample_replay_points(trajectory, replay_step)
            if not report_points:
                raise RuntimeError(
                    f"The generated trajectory is empty for {result.aircraft_id}."
                )

            vehicle_name = assigned_vehicles[index]
            job_id = f"job-{index + 1}-{vehicle_name}-{result.aircraft_id}"
            jobs[job_id] = {
                "job_id": job_id,
                "order": index,
                "vehicle_name": vehicle_name,
                "aircraft_id": result.aircraft_id,
                "flight_plan_number": result.flight_plan_number,
                "replay_step_s": replay_step,
                "playback_speed_x": playback_speed,
                "sample_count": len(report_points),
                "current_index": -1,
                "summary": {
                    **result.summary(),
                    "sample_count": len(report_points),
                    "pose_point_count": len(trajectory),
                    "replay_step_s": replay_step,
                    "playback_speed_x": playback_speed,
                },
                "last_point": None,
                "last_error": "",
                "last_collision": None,
                "alignment_mode": "absolute_affine",
                "alignment_origin": None,
                "frame_x_heading_deg": float(DEFAULT_CUSTOM_X_AXIS_HEADING_DEG),
                "frame_y_heading_deg": float(DEFAULT_CUSTOM_Y_AXIS_HEADING_DEG),
                "running": True,
                "completed": False,
                "trajectory": trajectory,
                "report_points": report_points,
            }

        threads: List[threading.Thread] = []
        with self._lock:
            self._stop_event.clear()
            self._last_error = ""
            self._jobs = jobs
            self._threads = []
            for job_id in sorted(jobs.keys(), key=lambda key: jobs[key]["order"]):
                thread = threading.Thread(
                    target=self._run_replay_job,
                    args=(job_id, bool(sync_to_airsim)),
                    daemon=True,
                )
                self._threads.append(thread)
                threads.append(thread)

        for thread in threads:
            thread.start()

        return self.get_status()

    def stop(self) -> Dict[str, Any]:
        self._stop_event.set()
        with self._lock:
            threads = list(self._threads)
        for thread in threads:
            if thread.is_alive():
                thread.join(timeout=2.0)
        with self._lock:
            self._threads = []
            for job in self._jobs.values():
                job["running"] = False
        return self.get_status()

    def set_playback_speed(self, playback_speed_x: float) -> Dict[str, Any]:
        playback_speed = min(max(float(playback_speed_x), 1.0), 8.0)
        with self._lock:
            for job in self._jobs.values():
                job["playback_speed_x"] = playback_speed
                summary = dict(job.get("summary") or {})
                summary["playback_speed_x"] = playback_speed
                job["summary"] = summary
        return self.get_status()

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            fleet = [
                self._serialize_job(self._jobs[key])
                for key in sorted(self._jobs.keys(), key=lambda item: self._jobs[item]["order"])
            ]
            running = any(bool(job.get("running")) for job in self._jobs.values())
            completed = bool(self._jobs) and all(
                bool(job.get("completed")) for job in self._jobs.values()
            )
            primary = self._select_primary_job_locked()
            connected_vehicles = list(self._connected_vehicles)
            primary_vehicle = (
                (primary or {}).get("vehicle_name")
                or (connected_vehicles[0] if connected_vehicles else "Drone1")
            )
            return {
                "connected": self._connected,
                "running": running,
                "completed": completed and not running,
                "host": self._host,
                "port": self._port,
                "vehicle_name": primary_vehicle,
                "connected_vehicles": connected_vehicles,
                "replay_step_s": (primary or {}).get("replay_step_s", 0.1),
                "playback_speed_x": (primary or {}).get("playback_speed_x", 1.0),
                "sample_count": (primary or {}).get("sample_count", 0),
                "current_index": (primary or {}).get("current_index", -1),
                "summary": dict((primary or {}).get("summary") or {}),
                "last_point": dict((primary or {}).get("last_point") or {})
                if (primary or {}).get("last_point")
                else None,
                "last_error": self._last_error or str((primary or {}).get("last_error") or ""),
                "last_collision": dict((primary or {}).get("last_collision") or {})
                if (primary or {}).get("last_collision")
                else None,
                "alignment_mode": str((primary or {}).get("alignment_mode") or "absolute_affine"),
                "alignment_origin": dict((primary or {}).get("alignment_origin") or {})
                if (primary or {}).get("alignment_origin")
                else None,
                "frame_x_heading_deg": float(
                    (primary or {}).get("frame_x_heading_deg", DEFAULT_CUSTOM_X_AXIS_HEADING_DEG)
                ),
                "frame_y_heading_deg": float(
                    (primary or {}).get("frame_y_heading_deg", DEFAULT_CUSTOM_Y_AXIS_HEADING_DEG)
                ),
                "mission_count": len(fleet),
                "fleet": fleet,
            }

    def _serialize_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "job_id": job["job_id"],
            "vehicle_name": job["vehicle_name"],
            "aircraft_id": job["aircraft_id"],
            "flight_plan_number": job["flight_plan_number"],
            "replay_step_s": job["replay_step_s"],
            "playback_speed_x": job.get("playback_speed_x", 1.0),
            "sample_count": job["sample_count"],
            "current_index": job["current_index"],
            "summary": dict(job.get("summary") or {}),
            "last_point": dict(job.get("last_point") or {}) if job.get("last_point") else None,
            "last_error": str(job.get("last_error") or ""),
            "last_collision": dict(job.get("last_collision") or {})
            if job.get("last_collision")
            else None,
            "alignment_mode": str(job.get("alignment_mode") or "absolute_affine"),
            "alignment_origin": dict(job.get("alignment_origin") or {})
            if job.get("alignment_origin")
            else None,
            "frame_x_heading_deg": float(
                job.get("frame_x_heading_deg", DEFAULT_CUSTOM_X_AXIS_HEADING_DEG)
            ),
            "frame_y_heading_deg": float(
                job.get("frame_y_heading_deg", DEFAULT_CUSTOM_Y_AXIS_HEADING_DEG)
            ),
            "running": bool(job.get("running")),
            "completed": bool(job.get("completed")),
        }

    def _select_primary_job_locked(self) -> Optional[Dict[str, Any]]:
        primary: Optional[Dict[str, Any]] = None
        best_score = (-1, -1)
        for job in self._jobs.values():
            has_point = 1 if job.get("last_point") else 0
            current_index = int(job.get("current_index", -1))
            score = (has_point, current_index)
            if primary is None or score > best_score:
                primary = job
                best_score = score
        if primary is not None:
            return primary
        if not self._jobs:
            return None
        first_key = sorted(self._jobs.keys(), key=lambda item: self._jobs[item]["order"])[0]
        return self._jobs[first_key]

    def _run_replay_job(self, job_id: str, sync_to_airsim: bool) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            pose_points = list(job["trajectory"])
            report_points = list(job["report_points"])
            vehicle_name = str(job["vehicle_name"])
            aircraft_id = str(job["aircraft_id"])
            flight_plan_number = int(job["flight_plan_number"])

        completed = False
        pose_context: Optional[Dict[str, Any]] = None
        if sync_to_airsim:
            try:
                pose_context = self._create_replay_pose_context(
                    pose_points[0] if pose_points else None,
                    vehicle_name,
                    job_id,
                )
            except Exception as exc:
                self._set_job_error(job_id, str(exc))
                pose_context = None

        report_index = 0
        for pose_index, point in enumerate(pose_points):
            if self._stop_event.is_set():
                break

            payload = self._point_to_payload(
                point,
                vehicle_name=vehicle_name,
                aircraft_id=aircraft_id,
                flight_plan_number=flight_plan_number,
            )

            if pose_context is not None:
                collision = self._apply_pose(payload, pose_context, job_id)
                if collision:
                    if self._should_ignore_initial_collision(collision, payload):
                        collision = None
                    else:
                        self._set_job_collision(job_id, collision)
                        self._set_job_error(
                            job_id,
                            (
                                f"Collision detected with "
                                f"{collision.get('object_name') or 'unknown object'} "
                                f"at t={float(payload.get('time_s', 0.0)):.1f}s."
                            ),
                        )
                        self._stop_event.set()
                        break

            while report_index < len(report_points):
                report_point = report_points[report_index]
                if float(report_point.time_s) - float(point.time_s) > 1e-6:
                    break
                report_payload = self._point_to_payload(
                    report_point,
                    vehicle_name=vehicle_name,
                    aircraft_id=aircraft_id,
                    flight_plan_number=flight_plan_number,
                )
                if pose_context is not None:
                    projected = self._project_payload_to_pose_frame(
                        report_payload,
                        pose_context,
                    )
                    if projected is not None:
                        report_payload["frame_x_m"] = float(projected["relative_x_m"])
                        report_payload["frame_y_m"] = float(projected["relative_y_m"])
                        report_payload["frame_z_m"] = float(projected["relative_z_m"])
                        report_payload["world_x_m"] = float(projected["x_m"])
                        report_payload["world_y_m"] = float(projected["y_m"])
                        report_payload["world_z_m"] = float(projected["z_m"])
                        report_payload["frame_yaw_deg"] = float(projected["yaw_deg"])
                self._set_job_progress(job_id, report_index, report_payload)
                self._emit(report_payload)
                report_index += 1

            if pose_index >= len(pose_points) - 1:
                completed = True
                break

            next_point = pose_points[pose_index + 1]
            playback_speed = min(max(float(job.get("playback_speed_x", 1.0)), 1.0), 8.0)
            wait_s = max(0.0, float(next_point.time_s) - float(point.time_s)) / playback_speed
            if self._stop_event.wait(wait_s):
                break

        while not self._stop_event.is_set() and report_index < len(report_points):
            report_point = report_points[report_index]
            report_payload = self._point_to_payload(
                report_point,
                vehicle_name=vehicle_name,
                aircraft_id=aircraft_id,
                flight_plan_number=flight_plan_number,
            )
            if pose_context is not None:
                projected = self._project_payload_to_pose_frame(report_payload, pose_context)
                if projected is not None:
                    report_payload["frame_x_m"] = float(projected["relative_x_m"])
                    report_payload["frame_y_m"] = float(projected["relative_y_m"])
                    report_payload["frame_z_m"] = float(projected["relative_z_m"])
                    report_payload["world_x_m"] = float(projected["x_m"])
                    report_payload["world_y_m"] = float(projected["y_m"])
                    report_payload["world_z_m"] = float(projected["z_m"])
                    report_payload["frame_yaw_deg"] = float(projected["yaw_deg"])
            self._set_job_progress(job_id, report_index, report_payload)
            self._emit(report_payload)
            report_index += 1

        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job["running"] = False
            job["completed"] = completed and not self._stop_event.is_set()

    def _set_job_progress(
        self,
        job_id: str,
        current_index: int,
        payload: Dict[str, Any],
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job["current_index"] = int(current_index)
            job["last_point"] = dict(payload)

    def _set_job_error(self, job_id: str, message: str) -> None:
        text = str(message or "")
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job["last_error"] = text
            self._last_error = text

    def _set_job_collision(self, job_id: str, collision: Dict[str, Any]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job["last_collision"] = dict(collision)

    def _set_job_alignment(
        self,
        job_id: str,
        *,
        mode: str,
        origin: Optional[Dict[str, float]],
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job["alignment_mode"] = mode
            job["alignment_origin"] = dict(origin) if origin else None
            job["frame_x_heading_deg"] = float(DEFAULT_CUSTOM_X_AXIS_HEADING_DEG)
            job["frame_y_heading_deg"] = float(DEFAULT_CUSTOM_Y_AXIS_HEADING_DEG)

    def _create_replay_pose_context(
        self,
        first_point: Optional[FlightTrajectoryPoint],
        vehicle_name: str,
        job_id: str,
    ) -> Dict[str, Any]:
        with self._lock:
            host = self._host
            port = self._port

        airsim, client = self._open_airsim_client(host, port)
        try:
            client.enableApiControl(True, vehicle_name=vehicle_name)
        except Exception:
            pass

        context: Dict[str, Any] = {
            "airsim": airsim,
            "client": client,
            "vehicle": vehicle_name,
            "mode": "absolute_affine",
        }
        spawn_pose_xyz = self._get_current_pose_ned(client, vehicle_name)
        if first_point is not None and spawn_pose_xyz is not None:
            context.update({
                "mode": "mission_relative_custom_frame",
                "mission_origin_geo": (
                    float(first_point.lat),
                    float(first_point.lon),
                    float(first_point.alt_m),
                ),
                "spawn_pose_xyz": (
                    float(spawn_pose_xyz[0]),
                    float(spawn_pose_xyz[1]),
                    float(spawn_pose_xyz[2]),
                ),
                "frame_x_heading_deg": float(DEFAULT_CUSTOM_X_AXIS_HEADING_DEG),
                "frame_y_heading_deg": float(DEFAULT_CUSTOM_Y_AXIS_HEADING_DEG),
            })
            self._set_job_alignment(
                job_id,
                mode="mission_relative_custom_frame",
                origin={
                    "lat": float(first_point.lat),
                    "lon": float(first_point.lon),
                    "alt_m": float(first_point.alt_m),
                    "spawn_x_m": float(spawn_pose_xyz[0]),
                    "spawn_y_m": float(spawn_pose_xyz[1]),
                    "spawn_z_m": float(spawn_pose_xyz[2]),
                    "frame_x_heading_deg": float(DEFAULT_CUSTOM_X_AXIS_HEADING_DEG),
                    "frame_y_heading_deg": float(DEFAULT_CUSTOM_Y_AXIS_HEADING_DEG),
                },
            )
        else:
            self._set_job_alignment(job_id, mode="absolute_affine", origin=None)
        return context

    def _point_to_payload(
        self,
        point: FlightTrajectoryPoint,
        *,
        vehicle_name: str,
        aircraft_id: str,
        flight_plan_number: int,
    ) -> Dict[str, Any]:
        return {
            "source": "simulator",
            "simulated": True,
            "name": vehicle_name,
            "vehicle_name": vehicle_name,
            "aircraft_id": aircraft_id,
            "flight_plan_number": int(flight_plan_number),
            "lat": float(point.lat),
            "lon": float(point.lon),
            "alt_m": float(point.alt_m),
            "speed_mps": float(point.speed_mps),
            "heading_deg": float(point.heading_deg),
            "track_heading_deg": float(point.track_heading_deg),
            "yaw_deg": float(point.heading_deg),
            "pitch_deg": 0.0,
            "roll_deg": 0.0,
            "phase": point.phase,
            "mode": point.mode,
            "clock": point.clock,
            "time_s": float(point.time_s),
        }

    def _apply_pose(
        self,
        payload: Dict[str, Any],
        pose_context: Dict[str, Any],
        job_id: str,
    ) -> Optional[Dict[str, Any]]:
        airsim = pose_context["airsim"]
        client = pose_context["client"]
        vehicle = pose_context["vehicle"]
        try:
            projected = self._project_payload_to_pose_frame(payload, pose_context)
            if projected is not None:
                x_m = float(projected["x_m"])
                y_m = float(projected["y_m"])
                z_m = float(projected["z_m"])
                yaw_deg = float(projected["yaw_deg"])
                payload["frame_x_m"] = float(projected["relative_x_m"])
                payload["frame_y_m"] = float(projected["relative_y_m"])
                payload["frame_z_m"] = float(projected["relative_z_m"])
                payload["world_x_m"] = x_m
                payload["world_y_m"] = y_m
                payload["world_z_m"] = z_m
                payload["frame_yaw_deg"] = yaw_deg
            else:
                x_m, y_m, z_m = wgs84_to_airsim_ned(
                    float(payload["lat"]),
                    float(payload["lon"]),
                    float(payload["alt_m"]),
                )
                yaw_deg = float(payload.get("yaw_deg", 0.0))
                payload["world_x_m"] = float(x_m)
                payload["world_y_m"] = float(y_m)
                payload["world_z_m"] = float(z_m)
            pose = airsim.Pose(
                airsim.Vector3r(float(x_m), float(y_m), float(z_m)),
                _to_airsim_quaternion(
                    airsim,
                    math.radians(float(payload.get("pitch_deg", 0.0))),
                    math.radians(float(payload.get("roll_deg", 0.0))),
                    math.radians(float(yaw_deg)),
                ),
            )
            client.simSetVehiclePose(pose, ignore_collision=False, vehicle_name=vehicle)
            return self._read_collision_info(client, vehicle)
        except Exception as exc:
            self._set_job_error(job_id, str(exc))
            return None

    def _read_collision_info(
        self,
        client: Any,
        vehicle_name: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            info = client.simGetCollisionInfo(vehicle_name=vehicle_name)
        except Exception:
            return None
        if info is None or not bool(getattr(info, "has_collided", False)):
            return None

        impact = getattr(info, "impact_point", None)
        normal = getattr(info, "normal", None)
        position = getattr(info, "position", None)
        return {
            "has_collided": True,
            "object_name": str(getattr(info, "object_name", "") or ""),
            "object_id": int(getattr(info, "object_id", -1) or -1),
            "time_stamp": _to_float(getattr(info, "time_stamp", None)),
            "penetration_depth": _to_float(getattr(info, "penetration_depth", None)),
            "impact_point": _vector3_to_dict(impact),
            "normal": _vector3_to_dict(normal),
            "position": _vector3_to_dict(position),
        }

    def _project_payload_to_pose_frame(
        self,
        payload: Dict[str, Any],
        pose_context: Dict[str, Any],
    ) -> Optional[Dict[str, float]]:
        if pose_context.get("mode") != "mission_relative_custom_frame":
            return None
        origin_lat, origin_lon, origin_alt = pose_context["mission_origin_geo"]
        spawn_x, spawn_y, spawn_z = pose_context["spawn_pose_xyz"]
        frame_x_heading = float(
            pose_context.get("frame_x_heading_deg", DEFAULT_CUSTOM_X_AXIS_HEADING_DEG)
        )
        frame_y_heading = float(
            pose_context.get("frame_y_heading_deg", DEFAULT_CUSTOM_Y_AXIS_HEADING_DEG)
        )
        offset = convert_target_to_unreal(
            player_start_lat=float(origin_lat),
            player_start_lon=float(origin_lon),
            player_start_alt_m=float(origin_alt),
            target_lat=float(payload["lat"]),
            target_lon=float(payload["lon"]),
            target_alt_m=float(payload["alt_m"]),
            x_axis_heading_deg=frame_x_heading,
            y_axis_heading_deg=frame_y_heading,
        )
        rel = offset["custom_unreal_m"]
        heading_deg = float(payload.get("yaw_deg", payload.get("heading_deg", 0.0)))
        frame_yaw_deg = _geo_heading_to_frame_yaw(
            heading_deg,
            frame_x_heading,
            frame_y_heading,
        )
        return {
            "relative_x_m": float(rel["x"]),
            "relative_y_m": float(rel["y"]),
            "relative_z_m": float(rel["z"]),
            "x_m": float(spawn_x) + float(rel["x"]),
            "y_m": float(spawn_y) + float(rel["y"]),
            "z_m": float(spawn_z) + float(rel["z"]),
            "yaw_deg": float(frame_yaw_deg),
        }

    def _should_ignore_initial_collision(
        self,
        collision: Dict[str, Any],
        payload: Dict[str, Any],
    ) -> bool:
        object_name = str(collision.get("object_name") or "")
        time_s = _to_float(payload.get("time_s")) or 0.0
        frame_x = _to_float(payload.get("frame_x_m")) or 0.0
        frame_y = _to_float(payload.get("frame_y_m")) or 0.0
        frame_z = _to_float(payload.get("frame_z_m")) or 0.0
        distance_m = math.sqrt((frame_x**2) + (frame_y**2) + (frame_z**2))
        if object_name.startswith("Cesium3DTileset") and time_s <= 0.2 and distance_m <= 0.5:
            return True
        return False

    def _open_airsim_client(self, host: str, port: int) -> tuple[Any, Any]:
        _ensure_thread_event_loop()
        airsim = _load_airsim()
        client = airsim.MultirotorClient(ip=str(host), port=int(port))
        return airsim, client

    def _get_gps_origin(
        self,
        client: Any,
        vehicle_name: str,
    ) -> Optional[tuple[float, float, float]]:
        try:
            gps = client.getGpsData(vehicle_name=vehicle_name) if vehicle_name else client.getGpsData()
        except Exception:
            return None
        if gps is None:
            return None
        loc = getattr(gps, "gps_location", None)
        if loc is None and hasattr(gps, "gnss") and hasattr(gps.gnss, "geo_point"):
            loc = gps.gnss.geo_point
        if loc is None:
            return None
        lat = _to_float(getattr(loc, "latitude", None))
        lon = _to_float(getattr(loc, "longitude", None))
        alt = _to_float(getattr(loc, "altitude", None))
        return _validate_geo(lat, lon, alt)

    def _get_current_pose_ned(
        self,
        client: Any,
        vehicle_name: str,
    ) -> Optional[tuple[float, float, float]]:
        try:
            state = (
                client.getMultirotorState(vehicle_name=vehicle_name)
                if vehicle_name
                else client.getMultirotorState()
            )
        except Exception:
            return None
        if state is None or not hasattr(state, "kinematics_estimated"):
            return None
        pos = getattr(state.kinematics_estimated, "position", None)
        if pos is None:
            return None
        n = _to_float(getattr(pos, "x_val", None))
        e = _to_float(getattr(pos, "y_val", None))
        d = _to_float(getattr(pos, "z_val", None))
        if n is None or e is None or d is None:
            return None
        return float(n), float(e), float(d)


def _load_airsim() -> Any:
    try:
        import airsim as _airsim

        return _airsim
    except Exception:
        from app import airsim as _airsim

        return _airsim


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


def _ensure_thread_event_loop() -> None:
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


def _normalize_vehicle_names(
    vehicle_names: Optional[Sequence[str] | str],
    count: int = 1,
) -> List[str]:
    if isinstance(vehicle_names, str):
        items = [vehicle_names]
    elif vehicle_names is None:
        items = []
    else:
        items = list(vehicle_names)

    normalized: List[str] = []
    for item in items:
        text = str(item or "").strip()
        if text and text not in normalized:
            normalized.append(text)

    if not normalized:
        normalized.append("Drone1")

    while len(normalized) < count:
        candidate = f"Drone{len(normalized) + 1}"
        if candidate not in normalized:
            normalized.append(candidate)

    return normalized[: max(count, 1)]


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _vector3_to_dict(value: Any) -> Optional[Dict[str, float]]:
    if value is None:
        return None
    x = _to_float(getattr(value, "x_val", None))
    y = _to_float(getattr(value, "y_val", None))
    z = _to_float(getattr(value, "z_val", None))
    if x is None or y is None or z is None:
        return None
    return {
        "x": float(x),
        "y": float(y),
        "z": float(z),
    }


def _validate_geo(
    lat: Optional[float],
    lon: Optional[float],
    alt: Optional[float],
) -> Optional[tuple[float, float, float]]:
    if lat is None or lon is None or alt is None:
        return None
    if not (math.isfinite(lat) and math.isfinite(lon) and math.isfinite(alt)):
        return None
    if abs(lat) < 0.1 and abs(lon) < 0.1:
        return None
    return float(lat), float(lon), float(alt)


def _heading_to_ne_unit(heading_deg: float) -> tuple[float, float]:
    radians = math.radians(float(heading_deg))
    return math.cos(radians), math.sin(radians)


def _geo_heading_to_frame_yaw(
    heading_deg: float,
    x_axis_heading_deg: float,
    y_axis_heading_deg: float,
) -> float:
    north, east = _heading_to_ne_unit(heading_deg)
    x_axis_n, x_axis_e = _heading_to_ne_unit(x_axis_heading_deg)
    y_axis_n, y_axis_e = _heading_to_ne_unit(y_axis_heading_deg)
    x_component = (north * x_axis_n) + (east * x_axis_e)
    y_component = (north * y_axis_n) + (east * y_axis_e)
    yaw_deg = math.degrees(math.atan2(y_component, x_component))
    return float(yaw_deg)


def _trim_airsim_sync_trajectory(
    trajectory: List[FlightTrajectoryPoint],
) -> List[FlightTrajectoryPoint]:
    if not trajectory:
        return []

    start_index = 0
    while (
        start_index < len(trajectory) - 1
        and str(trajectory[start_index].phase or "").strip().upper() == "A"
    ):
        start_index += 1

    end_index = len(trajectory) - 1
    while (
        end_index > start_index
        and str(trajectory[end_index].phase or "").strip().upper() == "K"
    ):
        end_index -= 1

    trimmed = list(trajectory[start_index : end_index + 1])
    return trimmed or list(trajectory)


def _sample_replay_points(
    trajectory: List[FlightTrajectoryPoint],
    replay_step_s: float,
) -> List[FlightTrajectoryPoint]:
    if not trajectory:
        return []

    step = max(float(replay_step_s), 0.1)
    sampled: List[FlightTrajectoryPoint] = []
    target_s = 0.0
    search_index = 0
    max_time_s = float(trajectory[-1].time_s)

    while target_s <= max_time_s + 1e-6:
        while (
            search_index + 1 < len(trajectory)
            and float(trajectory[search_index + 1].time_s) <= target_s
        ):
            search_index += 1

        chosen = trajectory[search_index]
        if search_index + 1 < len(trajectory):
            next_point = trajectory[search_index + 1]
            if abs(float(next_point.time_s) - target_s) < abs(float(chosen.time_s) - target_s):
                chosen = next_point

        if not sampled or float(sampled[-1].time_s) != float(chosen.time_s):
            sampled.append(chosen)
        target_s += step

    if float(sampled[-1].time_s) != float(trajectory[-1].time_s):
        sampled.append(trajectory[-1])
    return sampled
