"""Central path and directory settings used by the OperationModule app."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    app_root: Path
    web_dir: Path
    frontend_dir: Path
    templates_dir: Path
    static_dir: Path
    resource_dir: Path

    def ensure_directories(self) -> None:
        for directory in (self.web_dir, self.templates_dir, self.static_dir, self.resource_dir):
            directory.mkdir(parents=True, exist_ok=True)


APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent
WEB_DIR = APP_ROOT / "web"

settings = Settings(
    project_root=PROJECT_ROOT,
    app_root=APP_ROOT,
    web_dir=WEB_DIR,
    # Kept as an alias for code that still asks for the historical frontend_dir.
    frontend_dir=WEB_DIR,
    templates_dir=WEB_DIR / "templates",
    static_dir=WEB_DIR / "static",
    resource_dir=PROJECT_ROOT / "resource",
)
