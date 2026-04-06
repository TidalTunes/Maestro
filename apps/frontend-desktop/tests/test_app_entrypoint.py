import runpy
import unittest
from unittest.mock import patch


class AppEntrypointTests(unittest.TestCase):
    def test_module_exec_invokes_main(self):
        with patch("maestro_desktop.gui_runtime.main", return_value=0) as runtime_main:
            with self.assertRaises(SystemExit) as ctx:
                runpy.run_module("maestro_desktop.app", run_name="__main__")

        self.assertEqual(ctx.exception.code, 0)
        runtime_main.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
