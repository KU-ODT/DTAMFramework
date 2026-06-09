"""
VFDS Dynamics Dispatch System — SCP Client

paramiko를 사용하여 원격 호스트에 스크립트를 전송한다.
SITL 컨테이너 또는 실제 항공기 컴퓨터를 대상으로 한다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SCPConfig:
    """SCP 접속 설정"""
    hostname: str
    port: int = 22
    username: str = "px4"
    password: Optional[str] = None
    key_filename: Optional[str] = None


class SCPClient:
    """
    SCP 기반 원격 파일 전송 클라이언트.

    paramiko를 사용하여 SSH 연결 후 SFTP로 파일을 전송한다.
    paramiko가 설치되지 않은 환경에서는 graceful하게 실패한다.
    """

    def __init__(self, config: SCPConfig):
        self._config = config

    def upload(self, local_path: Path, remote_dir: str) -> str:
        """
        로컬 파일을 원격 호스트에 업로드한다.

        Args:
            local_path: 로컬 스크립트 파일 경로
            remote_dir: 원격 대상 디렉토리

        Returns:
            원격 파일 경로 문자열
        """
        try:
            import paramiko
        except ImportError:
            logger.warning(
                "paramiko not installed. SCP upload skipped. "
                "Install with: pip install paramiko"
            )
            remote_path = f"{remote_dir.rstrip('/')}/{local_path.name}"
            return remote_path

        remote_path = f"{remote_dir.rstrip('/')}/{local_path.name}"

        import os

        if not os.path.exists(local_path):
            logger.error("Local file not found: %s", local_path)
            raise FileNotFoundError(f"Local file not found: {local_path}")

        remote_path_target = f"{remote_dir.rstrip('/')}/{local_path.name}"

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            connect_kwargs = {
                "hostname": self._config.hostname,
                "port": self._config.port,
                "username": self._config.username,
            }
            if self._config.key_filename:
                connect_kwargs["key_filename"] = self._config.key_filename
            elif self._config.password:
                connect_kwargs["password"] = self._config.password
                # 비밀번호 사용 시 로컬 키 파일을 찾지 않도록 설정
                connect_kwargs["look_for_keys"] = False
                connect_kwargs["allow_agent"] = False

            ssh.connect(**connect_kwargs)
            sftp = ssh.open_sftp()

            # 원격 디렉토리 처리 (~ 지원 및 생성)
            target_dir = remote_dir
            if target_dir.startswith("~/"):
                home = sftp.normalize('.')
                target_dir = target_dir.replace("~", home)
                logger.info("Expanded remote dir: %s -> %s", remote_dir, target_dir)
            
            # 디렉토리 계층별 생성
            parts = [p for p in target_dir.split('/') if p]
            current = "/" if target_dir.startswith('/') else ""
            
            for part in parts:
                current = os.path.join(current, part).replace('\\', '/')
                try:
                    sftp.stat(current)
                except FileNotFoundError:
                    logger.info("Creating remote directory: %s", current)
                    sftp.mkdir(current)

            final_remote_path = f"{target_dir.rstrip('/')}/{local_path.name}"
            logger.info("SFTP putting: %s -> %s", local_path, final_remote_path)
            sftp.put(str(local_path), final_remote_path)
            sftp.close()

            logger.info(
                "SCP upload success: %s → %s:%s",
                local_path.name, self._config.hostname, final_remote_path,
            )
            return final_remote_path

        except Exception as e:
            logger.error("SCP upload failed: %s", e)
            raise
        finally:
            ssh.close()
