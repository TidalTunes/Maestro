from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import os
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "apps" / "frontend-desktop" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from maestro_desktop import runtime_support


class RuntimeSupportTests(unittest.TestCase):
    def tearDown(self) -> None:
        runtime_support.runtime_root.cache_clear()

    def test_runtime_root_prefers_bundle_override(self) -> None:
        with TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"MAESTRO_BUNDLE_ROOT": directory}, clear=False):
                runtime_support.runtime_root.cache_clear()
                self.assertEqual(runtime_support.runtime_root(), Path(directory).resolve())

    def test_detect_plugin_dir_prefers_existing_musescore4_plugins_folder(self) -> None:
        with TemporaryDirectory() as directory:
            home = Path(directory)
            expected = home / "Documents" / "MuseScore4" / "Plugins"
            expected.mkdir(parents=True)
            fallback = home / "Library" / "Application Support" / "MuseScore" / "MuseScore4" / "Plugins"
            fallback.mkdir(parents=True)

            self.assertEqual(runtime_support.detect_musescore_plugin_dir(home), expected)

    def test_frame_paths_follow_runtime_images_directory(self) -> None:
        with TemporaryDirectory() as directory:
            bundle_root = Path(directory)
            images = bundle_root / "images"
            images.mkdir(parents=True)
            with patch.dict(os.environ, {"MAESTRO_BUNDLE_ROOT": str(bundle_root)}, clear=False):
                runtime_support.runtime_root.cache_clear()
                paths = runtime_support.frame_paths()

        self.assertEqual(paths[0], (bundle_root / "images" / "frame1.png").resolve())
        self.assertEqual(paths[-1], (bundle_root / "images" / "frame5.png").resolve())
