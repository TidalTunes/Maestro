from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import os
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
for extra in (
    ROOT / "packages" / "agent-core" / "src",
    ROOT / "packages" / "maestroxml" / "src",
):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from maestro_agent_core import runtime_runner


class RuntimeRunnerTests(unittest.TestCase):
    def test_run_generate_uses_env_pythonpath_for_generated_imports(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            src_dir = root / "src" / "maestroxml"
            src_dir.mkdir(parents=True)
            (src_dir / "__init__.py").write_text(
                "class Score:\n"
                "    def write(self, path):\n"
                "        from pathlib import Path\n"
                "        Path(path).write_text('<score-partwise/>', encoding='utf-8')\n",
                encoding="utf-8",
            )

            script_path = root / "generated_score.py"
            script_path.write_text(
                "from maestroxml import Score\n\n"
                "def build_score(output_path):\n"
                "    Score().write(output_path)\n",
                encoding="utf-8",
            )
            output_path = root / "generated.musicxml"

            excluded_paths = {
                str((ROOT / "packages" / "maestroxml" / "src").resolve()),
                str((ROOT / "packages" / "maestro-musescore-bridge" / "src").resolve()),
            }
            original_sys_path = list(sys.path)
            sys.path[:] = [
                entry for entry in sys.path if str(Path(entry).resolve()) not in excluded_paths
            ]
            original_maestroxml = sys.modules.pop("maestroxml", None)
            try:
                with patch.dict("os.environ", {"PYTHONPATH": str(root / "src")}, clear=False):
                    runtime_runner.run_generate(script_path, output_path)
            finally:
                if original_maestroxml is not None:
                    sys.modules["maestroxml"] = original_maestroxml
                else:
                    sys.modules.pop("maestroxml", None)
                sys.path[:] = original_sys_path

            self.assertEqual(output_path.read_text(encoding="utf-8"), "<score-partwise/>")


if __name__ == "__main__":
    unittest.main()
