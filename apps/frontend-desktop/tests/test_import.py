from __future__ import annotations

from pathlib import Path
import importlib.util
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "apps" / "frontend-desktop" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@unittest.skipUnless(importlib.util.find_spec("PyQt6") is not None, "PyQt6 is not installed")
class FrontendImportTests(unittest.TestCase):
    def test_imports_desktop_app_module(self) -> None:
        from maestro_desktop import app

        self.assertTrue(callable(app.main))


if __name__ == "__main__":
    unittest.main()
