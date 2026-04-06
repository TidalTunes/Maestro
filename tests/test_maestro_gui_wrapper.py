from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = ROOT / "apps" / "frontend-desktop" / "src"
for extra in (ROOT, FRONTEND_SRC):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))


class MaestroGuiWrapperTests(unittest.TestCase):
    def test_wrapper_delegates_to_packaged_main(self) -> None:
        import maestro_gui

        with patch("maestro_desktop.app.main", return_value=123) as main_mock:
            self.assertEqual(maestro_gui.main(), 123)

        main_mock.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
