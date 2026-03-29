#!/usr/bin/env python3
"""Compatibility launcher for the promoted desktop frontend."""

from __future__ import annotations

from pathlib import Path
import sys


SRC = Path(__file__).resolve().parent / "apps" / "frontend-desktop" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from maestro_desktop.app import main


if __name__ == "__main__":
    main()
