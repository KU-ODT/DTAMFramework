"""Central path and directory settings used by the backend app."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    frontend_dir: Path
    templates_dir: Path
    static_dir: Path
    resource_dir: Path

    def ensure_directories(self) -> None:
        for directory in (self.frontend_dir, self.templates_dir, self.static_dir, self.resource_dir):
            directory.mkdir(parents=True, exist_ok=True)


PROJECT_ROOT = Path(__file__).resolve().parents[3]

settings = Settings(
    project_root=PROJECT_ROOT,
    frontend_dir=PROJECT_ROOT / "frontend",
    templates_dir=PROJECT_ROOT / "frontend" / "templates",
    static_dir=PROJECT_ROOT / "frontend" / "static",
    resource_dir=PROJECT_ROOT / "resource",
)
