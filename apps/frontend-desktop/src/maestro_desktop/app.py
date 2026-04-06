from __future__ import annotations


def main():
    from .gui_runtime import main as runtime_main

    return runtime_main()


__all__ = ["main"]
