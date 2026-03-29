from __future__ import annotations

from pathlib import Path
import importlib.util
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
for extra in (
    ROOT / "apps" / "service" / "src",
    ROOT / "apps" / "frontend-desktop" / "src",
    ROOT / "packages" / "agent-core" / "src",
    ROOT / "packages" / "maestroxml" / "src",
    ROOT / "packages" / "humming-detector" / "src",
):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))


class MonorepoSmokeTests(unittest.TestCase):
    def test_imports_service_and_shared_packages(self) -> None:
        import maestro_agent_core
        import maestro_humming_detector
        import maestro_service
        import maestroxml

        self.assertTrue(hasattr(maestro_agent_core, "build_model_input"))
        self.assertTrue(hasattr(maestro_humming_detector, "transcribe_humming"))
        self.assertTrue(hasattr(maestro_service, "app"))
        self.assertTrue(hasattr(maestroxml, "Score"))

    @unittest.skipUnless(importlib.util.find_spec("PyQt6") is not None, "PyQt6 is not installed")
    def test_imports_desktop_frontend(self) -> None:
        import maestro_desktop

        self.assertTrue(hasattr(maestro_desktop, "main"))


if __name__ == "__main__":
    unittest.main()
