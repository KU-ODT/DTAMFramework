"""
Mission Dispatch System — Upload Orchestrator

스크립트를 타겟 항공기에 전송하고, 선택적으로 실행을 트리거한다.
AircraftTarget의 send_protocol에 따라 Local/SCP/TCP/UDP 전송을 분기한다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import subprocess
import os
import sys

from src.dispatcher.models import AircraftTarget

from .local_deployer import LocalDeployer
from .scp_client import SCPClient, SCPConfig
from .executor import RemoteExecutor, ExecutionResult

logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    """업로드 + 실행 결과"""
    aircraft_id: str
    flight_plan_number: int
    local_script_path: Path
    deployed_path: Optional[str] = None
    sitl_result: Optional[ExecutionResult] = None
    execution_result: Optional[ExecutionResult] = None
    success: bool = False
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "aircraftId": self.aircraft_id,
            "flightPlanNumber": self.flight_plan_number,
            "deployedPath": self.deployed_path,
            "sitlLaunched": self.sitl_result is not None and self.sitl_result.success,
            "sitlPid": self.sitl_result.pid if self.sitl_result else None,
            "executed": self.execution_result is not None and self.execution_result.success,
            "pid": self.execution_result.pid if self.execution_result else None,
            "success": self.success,
            "message": self.message,
        }


class Uploader:
    """
    업로드 오케스트레이터.

    AircraftTarget 설정값(send_protocol, execution_mode)에 따라 적절한 
    전송 방법과 실행 방법을 선택한다.
    """

    def __init__(self, auto_execute: bool = False, auto_launch_sitl: bool = True):
        self._local_deployer = LocalDeployer()
        self._remote_executor = RemoteExecutor()
        self._auto_execute = auto_execute
        self._auto_launch_sitl = auto_launch_sitl

    def upload(
        self,
        script_path: Path,
        target: AircraftTarget,
        flight_plan_number: int,
        mission_home: Optional[tuple[float, float, float]] = None,
    ) -> UploadResult:
        result = UploadResult(
            aircraft_id=target.aircraft_id,
            flight_plan_number=flight_plan_number,
            local_script_path=script_path,
        )

        try:
            # 1. 파일 전송 (Deploy)
            deployed = self._deploy(script_path, target)
            result.deployed_path = deployed
            result.message = f"Deployed to {deployed} via {target.send_protocol}"

            # 2. 실행 (Execute)
            if self._auto_execute:
                if self._auto_launch_sitl and target.sitl.enabled:
                    sitl_result = self._launch_sitl_remote(target, mission_home)
                        
                    result.sitl_result = sitl_result
                    if not sitl_result.success:
                        result.success = False
                        result.message = sitl_result.message
                        return result

                exec_result = self._execute(target, script_path, deployed)
                result.execution_result = exec_result
                result.success = exec_result.success
                if exec_result.message:
                    result.message = exec_result.message
            else:
                result.success = True

            logger.info(
                "Upload complete: FP%d → %s (%s)",
                flight_plan_number, target.aircraft_id, deployed,
            )

        except Exception as e:
            result.success = False
            result.message = f"Upload failed: {e}"
            logger.error("Upload failed for FP%d: %s", flight_plan_number, e)

        return result

    def _launch_sitl_remote(self, target: AircraftTarget, mission_home: Optional[tuple[float, float, float]] = None) -> ExecutionResult:
        """원격 기체 PC에서 시뮬레이션을 기동한다."""
        spawn_lat, spawn_lon, spawn_alt = mission_home or (
            target.home_lat,
            target.home_lon,
            target.home_alt,
        )
        context = {
            "home_lat": spawn_lat,
            "home_lon": spawn_lon,
            "home_alt": spawn_alt,
        }
        
        vfds_cmd = target.sitl.vfds_command_template.format_map(context)
        px4_cmd = target.sitl.command_template.format_map(context)
        
        return self._remote_executor.launch_sitl(
            hostname=target.send_host,
            port=target.send_port,
            username="kada-vdt",
            password=target.ssh_password or None,
            vfds_command=vfds_cmd,
            px4_command=px4_cmd,
            startup_delay_sec=target.sitl.startup_delay_sec,
            home_lat=spawn_lat,
            home_lon=spawn_lon,
            home_alt=spawn_alt,
        )

    def stop_sitl_remote(self, target: AircraftTarget, stop_pattern: str | None = None) -> ExecutionResult:
        """원격 시뮬레이션을 정리한다. stop_pattern을 지정하면 해당 패턴만 종료한다."""
        pattern = stop_pattern or target.sitl.stop_pattern
        return self._remote_executor.stop_sitl(
            hostname=target.send_host,
            port=target.send_port,
            username="kada-vdt",
            password=target.ssh_password or None,
            stop_pattern=pattern,
        )

    def _deploy(self, script_path: Path, target: AircraftTarget) -> str:
        protocol = target.send_protocol.lower()
        if protocol == "local":
            deploy_dir = (target.script_deploy_path or "").strip()
            if deploy_dir and not deploy_dir.startswith("/"):
                return str(self._local_deployer.deploy(script_path, deploy_dir))
            return str(script_path.resolve())
        elif protocol == "scp":
            scp_config = SCPConfig(
                hostname=target.send_host, 
                username="kada-vdt", 
                port=target.send_port,
                password=target.ssh_password
            )
            client = SCPClient(scp_config)
            return client.upload(script_path, target.script_deploy_path)
        elif protocol == "tcp":
            # TODO: TCP Sender implementation
            logger.warning("TCP deployment not fully implemented, falling back to local path.")
            return str(script_path.resolve())
        elif protocol == "udp":
            # TODO: UDP Sender implementation
            logger.warning("UDP deployment not fully implemented, falling back to local path.")
            return str(script_path.resolve())
        else:
            raise ValueError(f"Unknown send_protocol: {protocol}")

    def _execute(self, target: AircraftTarget, local_script: Path, deployed_path: str) -> ExecutionResult:
        mode = target.execution_mode.lower()
        if mode == "local":
            return self._execute_local(target, local_script)
        elif mode == "remote":
            return self._execute_remote(target, deployed_path)
        else:
            raise ValueError(f"Unknown execution_mode: {mode}")

    def _execute_remote(self, target: AircraftTarget, remote_path: str) -> ExecutionResult:
        return self._remote_executor.execute(
            hostname=target.send_host,
            port=target.send_port,
            username="kada-vdt",
            password=target.ssh_password or None,
            remote_path=remote_path,
            connection_string=target.connection_string,
            grpc_port=target.mavsdk_port,
        )

    def _execute_local(self, target: AircraftTarget, script_path: Path) -> ExecutionResult:
        try:
            conn_str = target.connection_string
            grpc_port = target.mavsdk_port

            cmd = [
                sys.executable,
                str(script_path.resolve()),
                "--connection", conn_str,
                "--grpc-port", str(grpc_port)
            ]
            
            logger.info("Starting local executor: %s", " ".join(cmd))
            
            log_path = script_path.with_suffix(".log")
            log_file = open(log_path, "wb")
            
            try:
                p = subprocess.Popen(
                    cmd, 
                    stdout=log_file, 
                    stderr=subprocess.STDOUT, 
                    cwd=str(script_path.parent),
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
                )

                # 프로세스가 즉시 종료되면 실행 실패로 간주한다.
                try:
                    p.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    pass

                if p.poll() is not None:
                    log_file.close()
                    error_output = ""
                    if log_path.exists():
                        error_output = log_path.read_text(encoding="utf-8", errors="replace").strip()
                    return ExecutionResult(
                        remote_path=str(script_path),
                        hostname="localhost",
                        success=False,
                        pid=p.pid,
                        message=error_output or f"Local execution exited with code {p.returncode}",
                    )

                # 성공 경로: subprocess가 파일 핸들을 상속받았으므로 부모 쪽 핸들을 닫는다.
                log_file.close()

                return ExecutionResult(
                    remote_path=str(script_path),
                    hostname="localhost",
                    success=True, 
                    pid=p.pid, 
                    message=f"Local execution started. PID:{p.pid}, gRPC:{grpc_port}"
                )
            except Exception:
                log_file.close()
                raise

        except Exception as e:
            logger.error("Failed to execute local script: %s", e)
            return ExecutionResult(
                remote_path=str(script_path),
                hostname="localhost",
                success=False, 
                message=str(e)
            )
