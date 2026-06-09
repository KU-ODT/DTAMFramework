"""
Mission Dispatch System — Aircraft Registry

aircraft_registry.yaml을 로드하여 aircraftId → AircraftTarget 매핑을 관리한다.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import yaml

from .models import AircraftTarget, AircraftType, AircraftStatus, SITLLaunchConfig

logger = logging.getLogger(__name__)


class UnknownAircraftError(Exception):
    """레지스트리에 등록되지 않은 aircraftId 조회 시 발생"""

    def __init__(self, aircraft_id: str):
        self.aircraft_id = aircraft_id
        super().__init__(f"Unknown aircraftId: '{aircraft_id}'. Not found in registry.")


class AircraftRegistry:
    """
    항공기 레지스트리 매니저.

    YAML 파일에서 항공기 목록을 로드하고, aircraftId 기반 조회를 제공한다.
    """

    def __init__(self):
        self._registry: dict[str, AircraftTarget] = {}

    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> "AircraftRegistry":
        """YAML 파일에서 레지스트리를 로드한다."""
        registry = cls()
        path = Path(yaml_path)

        if not path.exists():
            raise FileNotFoundError(f"Registry file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        aircraft_dict = data.get("aircraft", {})
        if not aircraft_dict:
            logger.warning("No aircraft entries found in %s", path)
            return registry

        for aircraft_id, info in aircraft_dict.items():
            try:
                sitl_info = info.get("sitl", {}) or {}
                target = AircraftTarget(
                    aircraft_id=aircraft_id,
                    type=AircraftType(info.get("type", "SITL")),
                    connection_string=info.get("connection_string", ""),
                    mavsdk_port=int(info.get("mavsdk_port", 50051)),
                    send_protocol=info.get("send_protocol", "scp"),
                    send_host=info.get("send_host", ""),
                    send_port=int(info.get("send_port", 22)),
                    execution_mode=info.get("execution_mode", "remote"),
                    script_deploy_path=info.get("script_deploy_path", ""),
                    python_executable=info.get("python_executable", "python3"),
                    ssh_password=info.get("ssh_password", ""),
                    status=AircraftStatus(info.get("status", "available")),
                    home_lat=float(info.get("home_lat", 37.525680)),
                    home_lon=float(info.get("home_lon", 126.922050)),
                    home_alt=float(info.get("home_alt", 0.0)),
                    instance_id=int(info.get("instance_id", 0)),
                    mavlink_sysid=int(info.get("mavlink_sysid", 0)),
                    sitl=SITLLaunchConfig(
                        enabled=bool(sitl_info.get("enabled", False)),
                        distro=str(sitl_info.get("distro", "")),
                        workdir=str(sitl_info.get("workdir", "")),
                        prelaunch_template=str(sitl_info.get("prelaunch_template", "")),
                        vfds_command_template=str(sitl_info.get("vfds_command_template", "")),
                        command_template=str(sitl_info.get("command_template", "")),
                        stop_pattern=str(sitl_info.get("stop_pattern", "")),
                        process_pattern=str(sitl_info.get("process_pattern", "")),
                        ready_command=str(sitl_info.get("ready_command", "")),
                        log_path=str(sitl_info.get("log_path", "")),
                        startup_delay_sec=float(sitl_info.get("startup_delay_sec", 5.0)),
                        ready_timeout_sec=int(sitl_info.get("ready_timeout_sec", 20)),
                    ),
                )
                registry._registry[aircraft_id] = target
                logger.info("Registered aircraft: %s (%s)", aircraft_id, target.type.value)
            except (ValueError, KeyError) as e:
                logger.error("Failed to parse aircraft '%s': %s", aircraft_id, e)

        return registry

    def get(self, aircraft_id: str) -> AircraftTarget:
        """
        aircraftId로 타겟을 조회한다.

        Raises:
            UnknownAircraftError: 등록되지 않은 aircraftId
        """
        target = self._registry.get(aircraft_id)
        if target is None:
            raise UnknownAircraftError(aircraft_id)
        return target

    def get_optional(self, aircraft_id: str) -> Optional[AircraftTarget]:
        """등록되지 않은 경우 None 반환"""
        return self._registry.get(aircraft_id)

    def list_all(self) -> list[AircraftTarget]:
        """등록된 모든 항공기 목록 반환"""
        return list(self._registry.values())

    def list_available(self) -> list[AircraftTarget]:
        """available 상태인 항공기만 반환"""
        return [t for t in self._registry.values() if t.status == AircraftStatus.AVAILABLE]

    def update_status(self, aircraft_id: str, status: AircraftStatus) -> None:
        """항공기 상태를 변경한다."""
        target = self.get(aircraft_id)
        target.status = status
        logger.info("Aircraft %s status → %s", aircraft_id, status.value)

    @property
    def count(self) -> int:
        return len(self._registry)

    def __contains__(self, aircraft_id: str) -> bool:
        return aircraft_id in self._registry
