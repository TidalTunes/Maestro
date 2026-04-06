from __future__ import annotations

from importlib import import_module


def main():
    from .app import main as app_main

    return app_main()


def __getattr__(name: str):
    if name == "gui_runtime":
        return import_module(".gui_runtime", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["main", "gui_runtime"]
