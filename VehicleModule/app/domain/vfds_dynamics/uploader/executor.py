"""
VFDS Dynamics Dispatch System — Remote Executor

원격 호스트에서 업로드된 스크립트를 실행한다.
SSH를 통해 python3 명령을 실행하고, PID를 반환한다.
"""

from __future__ import annotations

import logging
import os
import shlex
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """스크립트 실행 결과"""
    remote_path: str
    hostname: str
    pid: Optional[int] = None
    success: bool = False
    message: str = ""


class RemoteExecutor:
    """
    SSH를 통해 원격 호스트에서 Python 스크립트를 실행한다.

    백그라운드로 실행하고 PID를 반환하여 모니터링 가능하게 한다.
    """

    def execute(
        self,
        hostname: str,
        port: int,
        username: str,
        remote_path: str,
        password: Optional[str] = None,
        key_filename: Optional[str] = None,
        connection_string: str = "",
        grpc_port: int = 50051,
    ) -> ExecutionResult:
        """
        원격 스크립트를 백그라운드로 실행한다.

        Args:
            hostname: 원격 호스트
            port: SSH 포트
            username: SSH 사용자
            remote_path: 원격 스크립트 경로
            password: SSH 비밀번호
            key_filename: SSH 키 파일

        Returns:
            ExecutionResult
        """
        try:
            import paramiko
        except ImportError:
            logger.warning(
                "paramiko not installed. Remote execution skipped."
            )
            return ExecutionResult(
                remote_path=remote_path,
                hostname=hostname,
                success=False,
                message="paramiko not installed",
            )

        ssh = None
        try:
            ssh = self._connect(hostname, port, username, password, key_filename)

            # SSH 연결의 로컬 IP(Windows PC의 IP)를 가져와서 VFDS_HOST로 사용
            local_ip = ssh.get_transport().sock.getsockname()[0]

            # 백그라운드 실행, PID 캡처 (VFDS endpoint 환경변수 주입)
            args = f"--connection {connection_string} --grpc-port {grpc_port}"
            vfds_port = int(os.environ.get("DTAM_VFDS_PORT") or 8098)
            vfds_url = f"http://{local_ip}:{vfds_port}"
            cmd = (
                f"VFDS_HOST={local_ip} VFDS_PORT={vfds_port} VFDS_URL={vfds_url} "
                f"nohup python3 {remote_path} {args} "
                f"> /tmp/mission_$(basename {remote_path} .py).log 2>&1 & echo $!"
            )
            stdin, stdout, stderr = ssh.exec_command(cmd)

            pid_str = stdout.read().decode().strip()
            pid = int(pid_str) if pid_str.isdigit() else None

            logger.info(
                "Remote exec: %s on %s (PID: %s)",
                remote_path, hostname, pid,
            )

            return ExecutionResult(
                remote_path=remote_path,
                hostname=hostname,
                pid=pid,
                success=True,
                message=f"Script started with PID {pid}",
            )

        except Exception as e:
            logger.error("Remote execution failed: %s", e)
            return ExecutionResult(
                remote_path=remote_path,
                hostname=hostname,
                success=False,
                message=str(e),
            )
        finally:
            if ssh:
                ssh.close()

    def launch_sitl(
        self,
        hostname: str,
        port: int,
        username: str,
        vfds_command: str,
        px4_command: str,
        startup_delay_sec: float = 5.0,
        password: Optional[str] = None,
        key_filename: Optional[str] = None,
        home_lat: float = 37.525680,
        home_lon: float = 126.922050,
        home_alt: float = 0.0,
    ) -> ExecutionResult:
        """원격 시뮬레이션(VFDS + PX4)을 기동하고 준비될 때까지 대기한다.

        기존 time.sleep() 방식 대신 프로세스 존재 여부를 능동적으로 폴링하여
        SITL이 일찍 뜨면 즉시 다음 단계로 진행하고,
        실패 시에도 startup_delay_sec 이내로 감지한다.
        """
        ssh = None
        try:
            ssh = self._connect(hostname, port, username, password, key_filename)
            local_ip = ssh.get_transport().sock.getsockname()[0]
            self._start_mavlink_forwarder(ssh, local_ip)

            # 인스턴스별 로그 파일 구분
            instance_suffix = vfds_command.split("--port")[-1].strip().split()[0] if "--port" in vfds_command else "default"
            vfds_log = f"/tmp/vfds_{instance_suffix}.log"
            px4_log = f"/tmp/px4_{instance_suffix}.log"

            # VFDS 기동
            logger.info("Launching VFDS: %s", vfds_command)
            ssh.exec_command(f"nohup bash -c '{vfds_command}' > {vfds_log} 2>&1 &")

            # PX4 기동 (홈 좌표 환경변수 주입)
            home_exports = f'export PX4_HOME="{home_lat},{home_lon},{home_alt},0.0" && '
            px4_cmd_with_home = f"{home_exports}{px4_command}"
            logger.info("Launching PX4: %s", px4_cmd_with_home)
            ssh.exec_command(f"nohup bash -c '{px4_cmd_with_home}' > {px4_log} 2>&1 &")

            # 프로세스 기동 확인: 최대 startup_delay_sec 동안 1초 간격 폴링
            # px4 프로세스가 살아있으면 충분히 준비된 것으로 간주
            px4_keyword = px4_command.split()[-1] if px4_command else "px4"
            ready = False
            poll_interval = 1.0
            elapsed = 0.0
            wait_cap = max(startup_delay_sec, 3.0)  # 최소 3초는 대기
            while elapsed < wait_cap:
                time.sleep(poll_interval)
                elapsed += poll_interval
                _, stdout, _ = ssh.exec_command(f"pgrep -f 'px4.*-i {px4_keyword}' > /dev/null 2>&1 && echo ALIVE || echo WAIT")
                status = stdout.read().decode().strip()
                if status == "ALIVE":
                    logger.info("SITL ready after %.1fs (instance suffix: %s)", elapsed, instance_suffix)
                    ready = True
                    break

            if not ready:
                logger.warning(
                    "SITL did not confirm ready within %.1fs for %s — proceeding anyway.",
                    wait_cap, instance_suffix,
                )

            return ExecutionResult(remote_path="", hostname=hostname, success=True, message=f"SITL/VFDS launched (waited {elapsed:.1f}s)")
        except Exception as e:
            return ExecutionResult(remote_path="", hostname=hostname, success=False, message=str(e))
        finally:
            if ssh:
                ssh.close()

    def _start_mavlink_forwarder(
        self,
        ssh,
        destination_host: str,
        listen_port: int = 14550,
        destination_port: int = 14550,
    ) -> None:
        """Forward PX4 localhost GCS MAVLink packets to the VFDS receiver."""
        marker = f"vfds_dynamics_mavlink_forwarder_{listen_port}"
        script_path = f"/tmp/{marker}.py"
        log_path = f"/tmp/{marker}.log"

        # Always refresh the forwarder on each SITL launch.  The VFDS host can
        # change between runs (different NIC/DHCP), and a stale forwarder can
        # keep sending MAVLink to an old IP while the mission script itself is
        # otherwise running normally.
        ssh.exec_command(
            "pkill -f "
            f"{shlex.quote(script_path)}"
            " >/dev/null 2>&1 || true"
        )

        code = f"""
import socket

listen = ("0.0.0.0", {listen_port})
dest = ({destination_host!r}, {destination_port})
rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
rx.bind(listen)
tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
print(f"[MAVLINK-FWD] {{listen}} -> {{dest}}", flush=True)
while True:
    data, addr = rx.recvfrom(65535)
    if data:
        tx.sendto(data, dest)
""".strip()
        write_cmd = f"cat > {shlex.quote(script_path)} <<'PY'\n{code}\nPY"
        logger.info(
            "Starting MAVLink forwarder on remote host: 127.0.0.1:%d -> %s:%d",
            listen_port,
            destination_host,
            destination_port,
        )
        _, stdout, stderr = ssh.exec_command(write_cmd)
        stdout.channel.recv_exit_status()
        error = stderr.read().decode().strip()
        if error:
            logger.warning("Failed to write MAVLink forwarder script: %s", error)
            return

        cmd = (
            f"nohup python3 -u {shlex.quote(script_path)} "
            f"> {shlex.quote(log_path)} 2>&1 &"
        )
        ssh.exec_command(cmd)

    def stop_sitl(
        self,
        hostname: str,
        port: int,
        username: str,
        stop_pattern: str,
        password: Optional[str] = None,
        key_filename: Optional[str] = None,
    ) -> ExecutionResult:
        """원격 시뮬레이션 프로세스를 정리한다."""
        ssh = None
        try:
            ssh = self._connect(hostname, port, username, password, key_filename)
            # pkill -9 로 확실하게 종료
            cmd = f"pkill -9 -f '{stop_pattern}'"
            logger.info("Stopping remote process with pattern: %s on %s", stop_pattern, hostname)
            ssh.exec_command(cmd)
            return ExecutionResult(remote_path="", hostname=hostname, success=True, message="SITL stopped")
        except Exception as e:
            return ExecutionResult(remote_path="", hostname=hostname, success=False, message=str(e))
        finally:
            if ssh:
                ssh.close()

    def _connect(self, hostname, port, username, password, key_filename):
        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kwargs = {"hostname": hostname, "port": port, "username": username}
        if key_filename: kwargs["key_filename"] = key_filename
        elif password: 
            kwargs["password"] = password
            # 비밀번호 사용 시 로컬 키 파일을 찾지 않도록 설정
            kwargs["look_for_keys"] = False
            kwargs["allow_agent"] = False
        ssh.connect(**kwargs)
        return ssh
