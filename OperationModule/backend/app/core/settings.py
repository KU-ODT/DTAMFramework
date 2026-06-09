"""Compatibility module wrapper for `app.core.settings`."""

from importlib import import_module as _import_module
import sys as _sys

_module = _import_module("app.core.settings")
_sys.modules[__name__] = _module
globals().update(_module.__dict__)
