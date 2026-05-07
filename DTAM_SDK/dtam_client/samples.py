"""Valid sample DTAM payloads for module developers.

These samples are intentionally small, deterministic, and validated by the
same schema code used by the sender. They are meant for smoke tests,
integration examples, and quick starts.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable, Dict


ISO_TS = "2026-04-17T00:00:00.000Z"
SIM_TS = "2026-04-17T00:00:00Z"


def now_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _merge(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(base)
    for key, value in overrides.items():
        out[key] = value
    return out


def sample_module_status(**overrides: Any) -> Dict[str, Any]:
    return _merge(
        {
            "timestamp": ISO_TS,
            "source": "SampleModule",
            "status": 1,
        },
        overrides,
    )


def sample_module_setting_info(**overrides: Any) -> Dict[str, Any]:
    return _merge(
        {
            "Timestamp": ISO_TS,
            "ModuleName": "SampleModule",
            "Role": "vehicle",
        },
        overrides,
    )


def sample_common_time_info(**overrides: Any) -> Dict[str, Any]:
    return _merge(
        {
            "timestamp": ISO_TS,
            "simTime": SIM_TS,
        },
        overrides,
    )


def sample_sim_mode_setup(**overrides: Any) -> Dict[str, Any]:
    return _merge(
        {
            "timestamp": ISO_TS,
            "operationMode": "integrated",
            "singleFlight": {
                "vehicleSimType": {
                    "dynamics": "simple",
                    "mainVehicleController": "Autopilot",
                },
            },
            "traffic": {
                "trafficScenario": "low",
            },
        },
        overrides,
    )


def sample_simulation_setup(**overrides: Any) -> Dict[str, Any]:
    return _merge(
        {
            "timestamp": ISO_TS,
            "playbackSpeed": 1,
            "playState": "play",
            "weatherEffect": {
                "precipitation": {
                    "type": "none",
                    "intensity": 0.0,
                },
                "fog": {
                    "intensity": 0.0,
                },
            },
            "wind": {
                "grade": "normal",
            },
        },
        overrides,
    )


def sample_scenario_setup(**overrides: Any) -> Dict[str, Any]:
    return _merge(
        {
            "timestamp": ISO_TS,
            "scenarioFileName": "sample_scenario.json",
            "totalAircraftCount": 1,
            "mainVehicleType": "KP2A",
            "operationTime": {
                "startTime": "09:00:00",
                "endTime": "10:00:00",
            },
            "vertiports": [
                {
                    "name": "VP_A",
                    "class": "port",
                    "lat": 37.525,
                    "lon": 126.921,
                    "angleDegrees": 0.0,
                },
            ],
            "routeNetwork": {
                "waypoints": [
                    {
                        "waypointId": "WP1",
                        "waypointName": "Waypoint 1",
                        "lat": 37.525,
                        "lon": 126.921,
                        "altFt": 500.0,
                        "links": ["WP2"],
                    },
                    {
                        "waypointId": "WP2",
                        "waypointName": "Waypoint 2",
                        "lat": 37.526,
                        "lon": 126.922,
                        "altFt": 500.0,
                        "links": ["WP1"],
                    },
                ],
            },
        },
        overrides,
    )


def sample_flight_plan_request(**overrides: Any) -> Dict[str, Any]:
    return _merge(
        {
            "timestamp": ISO_TS,
            "scenarioFileName": "sample_scenario.json",
        },
        overrides,
    )


def sample_dtam_execute(**overrides: Any) -> Dict[str, Any]:
    return _merge(
        {
            "timestamp": ISO_TS,
            "simModeFileName": "sim_mode.json",
            "simulationSetupFileName": "simulation_setup.json",
            "scenarioFileName": "scenario.json",
            "flightPlanFolderName": "FlightPlan_001",
        },
        overrides,
    )


def _lla(lat: float, lon: float, alt: float) -> Dict[str, float]:
    return {"lat": lat, "lon": lon, "alt": alt}


def sample_scheduled_flight(**overrides: Any) -> Dict[str, Any]:
    return _merge(
        {
            "flightPlanNumber": 1001,
            "planVersion": 1,
            "planStatus": "active",
            "aircraftId": "UAM0001",
            "departure": {
                "vertiport": "VP_A",
                "std": "09:00:00",
                "depGateNumber": "G1",
                "eobt": "08:55:00",
                "depFatoNumber": "F1",
                "etot": "09:05:00",
            },
            "arrival": {
                "vertiport": "VP_B",
                "sta": "09:30:00",
                "arrGateNumber": "G2",
                "eibt": "09:35:00",
                "arrFatoNumber": "F2",
                "eldt": "09:28:00",
            },
            "enRoute": [
                {
                    "seq": 1,
                    "phase": "A",
                    "targetSpeed": 30.0,
                    "startLLA": _lla(37.525, 126.921, 120.0),
                    "endLLA": _lla(37.526, 126.922, 140.0),
                },
            ],
        },
        overrides,
    )


def sample_strategic_separation(**overrides: Any) -> Dict[str, Any]:
    return _merge(
        {
            "timestamp": ISO_TS,
            "commandId": "MOD-001",
            "flightPlanNumber": 1001,
            "planVersion": 2,
            "aircraftId": "UAM0001",
            "modificationType": "delayOnly",
            "reasonCode": "WEATHER",
            "modifyScope": "departureOnly",
        },
        overrides,
    )


def sample_tactical_separation(**overrides: Any) -> Dict[str, Any]:
    return _merge(
        {
            "timestamp": ISO_TS,
            "commandId": "TAC-001",
            "aircraftId": "UAM0001",
            "reasonCode": "WEATHER_AVOIDANCE",
            "actions": [
                {
                    "type": "setSpeed",
                    "targetSpeed": 25.0,
                },
            ],
        },
        overrides,
    )


def sample_vehicle_status(**overrides: Any) -> Dict[str, Any]:
    return _merge(
        {
            "timestamp": ISO_TS,
            "UAM0001": {
                "currentWaypointId": "1001-1",
                "position": {
                    "north": 10.0,
                    "east": 20.0,
                    "down": -120.0,
                },
                "attitude": {
                    "roll": 0.0,
                    "pitch": 0.0,
                    "yaw": 0.0,
                },
                "actuator": {
                    "tilt_left": 0.0,
                    "tilt_right": 0.0,
                    "aileron": 0.0,
                    "rudder_left": 0.0,
                    "rudder_right": 0.0,
                },
                "propulsion": {
                    "motor_rpm": [1200.0, 1200.0, 1200.0, 1200.0],
                },
                "gps": {
                    "is_valid": True,
                    "fix_type": 3,
                    "latitude": 37.525,
                    "longitude": 126.921,
                    "altitude": 120.0,
                    "velocity_north": 0.0,
                    "velocity_east": 0.0,
                    "velocity_down": 0.0,
                    "eph": 1.0,
                    "epv": 1.0,
                },
                "imu": {
                    "orientation": {
                        "w": 1.0,
                        "x": 0.0,
                        "y": 0.0,
                        "z": 0.0,
                    },
                    "angular_velocity": {
                        "x": 0.0,
                        "y": 0.0,
                        "z": 0.0,
                    },
                    "linear_acceleration": {
                        "x": 0.0,
                        "y": 0.0,
                        "z": -9.8,
                    },
                },
                "barometer": {
                    "altitude": 120.0,
                    "pressure": 101325.0,
                    "qnh": 1013.25,
                },
            },
        },
        overrides,
    )


def sample_camera_image_header(**overrides: Any) -> Dict[str, Any]:
    return _merge(
        {
            "message_id": 4101,
            "message_name": "Camera Image Frame",
            "timestamp": ISO_TS,
            "vehicle_id": "UAM0001",
            "camera_name": "front_center",
            "image_type": "scene",
            "sequence": 1,
            "width": 1,
            "height": 1,
            "channels": 3,
            "pixel_format": "rgb8",
            "encoding": "raw",
            "payload_size": 3,
        },
        overrides,
    )


def sample_operator_control_input(**overrides: Any) -> Dict[str, Any]:
    return _merge(
        {
            "timestamp": ISO_TS,
            "aircraftId": "UAM0001",
            "source": "keyboard",
            "controlMode": "keyboard",
            "sequence": 1,
            "active": True,
            "axes": {
                "roll": 0.0,
                "pitch": 0.5,
                "yaw": 0.0,
                "throttle": 0.2,
            },
            "buttons": [],
            "hats": [],
            "rawAxes": {},
        },
        overrides,
    )


def sample_camera_control_command(**overrides: Any) -> Dict[str, Any]:
    return _merge(
        {
            "timestamp": ISO_TS,
            "aircraftId": "UAM0001",
            "vehicleName": "",
            "cameraName": "front_center",
            "source": "joystick",
            "action": "adjust",
            "sequence": 1,
            "yawDeltaDeg": 6.0,
            "pitchDeltaDeg": 0.0,
            "focalLengthDelta": 0.0,
        },
        overrides,
    )


def sample_camera_image_bytes() -> bytes:
    return b"\x00\x00\x00"


_SAMPLE_BUILDERS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "0001": sample_module_setting_info,
    "0002": sample_module_status,
    "0003": sample_common_time_info,
    "1001": sample_sim_mode_setup,
    "1002": sample_simulation_setup,
    "1003": sample_scenario_setup,
    "2001": sample_flight_plan_request,
    "2002": sample_dtam_execute,
    "3001": sample_scheduled_flight,
    "3002": sample_strategic_separation,
    "3003": sample_tactical_separation,
    "4001": sample_vehicle_status,
    "4101": sample_camera_image_header,
    "5001": sample_operator_control_input,
    "5002": sample_camera_control_command,
}

_ALIASES = {
    "module_setting_info": "0001",
    "push_module_setting_info": "0001",
    "module_status": "0002",
    "push_module_status": "0002",
    "common_time_info": "0003",
    "push_common_time_info": "0003",
    "sim_mode_setup": "1001",
    "push_sim_mode_setup": "1001",
    "simulation_setup": "1002",
    "push_simulation_setup": "1002",
    "scenario_setup": "1003",
    "push_scenario_setup": "1003",
    "flight_plan_request": "2001",
    "push_flight_plan_request": "2001",
    "dtam_execute": "2002",
    "push_dtam_execute": "2002",
    "scheduled_flight": "3001",
    "push_scheduled_flight": "3001",
    "strategic_separation": "3002",
    "push_strategic_separation": "3002",
    "tactical_separation": "3003",
    "push_tactical_separation": "3003",
    "vehicle_status": "4001",
    "push_vehicle_status": "4001",
    "camera_image": "4101",
    "camera_image_header": "4101",
    "push_camera_image": "4101",
    "operator_control_input": "5001",
    "push_operator_control_input": "5001",
    "manual_control_input": "5001",
    "camera_control_command": "5002",
    "push_camera_control_command": "5002",
}


def sample_payload(message: str | int, **overrides: Any) -> Dict[str, Any]:
    """Return a valid sample payload for a DTAM message ID or alias."""
    key = str(message).strip().lower().replace("-", "_").replace(" ", "_")
    mid = _SAMPLE_BUILDERS.get(key) and key
    if mid is None:
        mid = _ALIASES.get(key)
    if mid is None:
        known = ", ".join(sorted(_SAMPLE_BUILDERS))
        raise ValueError(f"Unknown DTAM sample '{message}'. Known IDs: {known}")
    return _SAMPLE_BUILDERS[mid](**overrides)


def all_sample_payloads() -> Dict[str, Dict[str, Any]]:
    """Return one valid sample payload for every supported message."""
    return {mid: builder() for mid, builder in _SAMPLE_BUILDERS.items()}
