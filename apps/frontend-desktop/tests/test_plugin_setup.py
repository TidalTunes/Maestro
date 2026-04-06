from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
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
