"""Import helper for the sibling DTAM_SDK project."""
from __future__ import annotations

import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = APP_ROOT.parent
SDK_ROOT = WORKSPACE_ROOT / "DTAM_SDK"


def ensure_sdk_path() -> Path:
    """Make the sibling DTAM_SDK package importable."""
    if not SDK_ROOT.is_dir():
        raise RuntimeError(f"DTAM_SDK folder not found: {SDK_ROOT}")
    sdk_path = str(SDK_ROOT)
    if sdk_path not in sys.path:
        sys.path.insert(0, sdk_path)
    return SDK_ROOT
