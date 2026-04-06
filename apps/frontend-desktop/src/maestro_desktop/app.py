from __future__ import annotations


def main():
    from maestro_desktop.gui_runtime import main as runtime_main

    return runtime_main()


__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
