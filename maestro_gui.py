#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DESKTOP_SRC = ROOT_DIR / "apps" / "frontend-desktop" / "src"
if str(FRONTEND_DESKTOP_SRC.resolve()) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DESKTOP_SRC.resolve()))


def main():
    from maestro_desktop.app import main as app_main

    return app_main()


if __name__ == "__main__":
    raise SystemExit(main())
