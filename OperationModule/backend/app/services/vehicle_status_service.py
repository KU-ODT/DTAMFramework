"""Compatibility module wrapper for `app.services.vehicle_status_service`."""

from importlib import import_module as _import_module
import sys as _sys

_module = _import_module("app.services.vehicle_status_service")
_sys.modules[__name__] = _module
globals().update(_module.__dict__)
