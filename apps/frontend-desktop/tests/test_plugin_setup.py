from __future__ import annotations

import io
from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import redirect_stdout
from unittest.mock import patch
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
for extra in (
    ROOT / "apps" / "frontend-desktop" / "src",
    ROOT / "packages" / "maestro-musescore-bridge" / "src",
):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from maestro_desktop import plugin_setup


class _SuccessfulBridgeClient:
    def __init__(self, **_: object) -> None:
        pass

    def ping(self):
        return {"message": "pong"}


class _FailingBridgeClient:
    def __init__(self, **_: object) -> None:
        pass

    def ping(self):
        raise plugin_setup.BridgeError("bridge offline")


class PluginSetupTests(unittest.TestCase):
    def test_install_plugin_copies_missing_files(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            plugin_dir = root / "plugins"
            source.mkdir()

            for name in plugin_setup.PLUGIN_FILENAMES:
                (source / name).write_text(f"contents:{name}", encoding="utf-8")

            initial_state = plugin_setup.inspect_plugin_install(
                source_dir=source,
                plugin_dir=plugin_dir,
            )
            self.assertFalse(initial_state.installed)

            installed_state = plugin_setup.install_plugin(
                source_dir=source,
                plugin_dir=plugin_dir,
            )

            self.assertTrue(installed_state.up_to_date)
            for name in plugin_setup.PLUGIN_FILENAMES:
                self.assertEqual(
                    (plugin_dir / name).read_text(encoding="utf-8"),
                    f"contents:{name}",
                )

    def test_inspect_plugin_install_reports_outdated_files(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            plugin_dir = root / "plugins"
            source.mkdir()
            plugin_dir.mkdir()

            for name in plugin_setup.PLUGIN_FILENAMES:
                (source / name).write_text(f"new:{name}", encoding="utf-8")
                (plugin_dir / name).write_text(f"old:{name}", encoding="utf-8")

            state = plugin_setup.inspect_plugin_install(
                source_dir=source,
                plugin_dir=plugin_dir,
            )

        self.assertEqual(set(state.outdated_files), set(plugin_setup.PLUGIN_FILENAMES))
        self.assertFalse(state.up_to_date)

    def test_verify_bridge_connection_reports_success(self) -> None:
        ok, message = plugin_setup.verify_bridge_connection(
            client_factory=_SuccessfulBridgeClient,
        )

        self.assertTrue(ok)
        self.assertIn("connected", message.lower())

    def test_verify_bridge_connection_reports_bridge_errors(self) -> None:
        ok, message = plugin_setup.verify_bridge_connection(
            client_factory=_FailingBridgeClient,
        )

        self.assertFalse(ok)
        self.assertIn("bridge offline", message)

    def test_launch_musescore_requires_packaged_macos_mode(self) -> None:
        with patch("maestro_desktop.plugin_setup.supports_guided_macos_setup", return_value=False):
            with self.assertRaises(FileNotFoundError) as ctx:
                plugin_setup.launch_musescore()

        self.assertIn("packaged macOS app", str(ctx.exception))

    def test_cli_status_reports_missing_files(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            plugin_dir = root / "plugins"
            source.mkdir()
            for name in plugin_setup.PLUGIN_FILENAMES:
                (source / name).write_text(f"contents:{name}", encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = plugin_setup.cli_main(
                    [
                        "status",
                        "--plugin-dir",
                        str(plugin_dir),
                        "--source-dir",
                        str(source),
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertIn("Plugin folder:", stdout.getvalue())
        self.assertIn("Missing:", stdout.getvalue())

    def test_cli_install_copies_plugin_files(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            plugin_dir = root / "plugins"
            source.mkdir()
            for name in plugin_setup.PLUGIN_FILENAMES:
                (source / name).write_text(f"contents:{name}", encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = plugin_setup.cli_main(
                    [
                        "install",
                        "--plugin-dir",
                        str(plugin_dir),
                        "--source-dir",
                        str(source),
                    ]
                )

            copied = {(plugin_dir / name).read_text(encoding="utf-8") for name in plugin_setup.PLUGIN_FILENAMES}

        self.assertEqual(exit_code, 0)
        self.assertIn("Installed Maestro Plugin", stdout.getvalue())
        self.assertEqual(copied, {f"contents:{name}" for name in plugin_setup.PLUGIN_FILENAMES})
