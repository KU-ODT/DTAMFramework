"""Compatibility package wrapper for `app.core`."""

from importlib import import_module as _import_module

_module = _import_module("app.core")
__all__ = getattr(_module, "__all__", [])


def __getattr__(name: str):
    return getattr(_module, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_module)))
