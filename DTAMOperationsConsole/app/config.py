"""Central path and directory settings.

표준 layout:
  app/                — Python 코드
  web/                — 프런트엔드 (templates + static 통합)
  resource/           — 바이너리 (mbtiles, png 등; 다른 모듈은 resources 복수형이지만
                        현재 OS 잠금으로 rename 보류, 기능에는 영향 없음)
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    web_dir: Path
    templates_dir: Path
    static_dir: Path
    resource_dir: Path

    @property
    def frontend_dir(self) -> Path:
        """legacy alias — 옛 코드 호환용."""
        return self.web_dir

    def ensure_directories(self) -> None:
        for directory in (self.web_dir, self.resource_dir):
            directory.mkdir(parents=True, exist_ok=True)


# config.py 가 ``DTAMOperationsConsole/app/config.py`` 에 있으므로 parents[1]
# 가 모듈 루트 (DTAMOperationsConsole/).
PROJECT_ROOT = Path(__file__).resolve().parents[1]

settings = Settings(
    project_root=PROJECT_ROOT,
    web_dir=PROJECT_ROOT / "web",
    templates_dir=PROJECT_ROOT / "web",            # index.html 직접
    static_dir=PROJECT_ROOT / "web",               # css/, js/, vendor/, patch_notes/
    resource_dir=PROJECT_ROOT / "resource",        # 큰 바이너리
)
