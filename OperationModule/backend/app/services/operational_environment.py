"""Compatibility module wrapper for `app.services.operational_environment`."""

from importlib import import_module as _import_module
import sys as _sys

_module = _import_module("app.services.operational_environment")
_sys.modules[__name__] = _module
globals().update(_module.__dict__)
