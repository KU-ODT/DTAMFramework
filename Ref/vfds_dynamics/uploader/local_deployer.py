"""
VFDS Dynamics Dispatch System — Local Deployer

컴파일된 스크립트를 로컬 디렉토리에 복사한다.
로컬 SITL 환경이나 테스트 시 사용한다.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


class LocalDeployer:
    """로컬 파일 시스템으로 스크립트를 복사하는 배포기"""

    def deploy(self, script_path: Path, deploy_dir: str | Path) -> Path:
        """
        스크립트 파일을 대상 디렉토리로 복사한다.

        Args:
            script_path: 컴파일된 스크립트 파일 경로
            deploy_dir: 배포 대상 디렉토리

        Returns:
            복사된 파일의 절대 경로
        """
        dest_dir = Path(deploy_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = dest_dir / script_path.name
        shutil.copy2(script_path, dest_path)

        logger.info("Local deploy: %s → %s", script_path.name, dest_path)
        return dest_path.resolve()
