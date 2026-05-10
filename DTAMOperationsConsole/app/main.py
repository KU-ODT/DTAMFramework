"""Compatibility wrapper exposing the Operations Console FastAPI app."""

import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))
SDK_ROOT = MODULE_ROOT.parent / "DTAM_SDK"
if SDK_ROOT.is_dir() and str(SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(SDK_ROOT))

from backend.app.main import app  # noqa: E402

__all__ = ["app"]
