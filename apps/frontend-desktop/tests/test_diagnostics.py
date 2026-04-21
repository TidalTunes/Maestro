from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "apps" / "frontend-desktop" / "src"
for extra in (ROOT, SRC):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from maestro_desktop.backend import ModelProviderConfig, OpenAIProviderConfig
from maestro_desktop.diagnostics import LOGGER, build_diagnostics_report, configure_logging, log_event, recent_log_lines
from maestro_desktop.plugin_setup import PluginInstallState


class DiagnosticsTests(unittest.TestCase):
    def tearDown(self) -> None:
        for handler in list(LOGGER.handlers):
            handler.close()
            LOGGER.removeHandler(handler)

    def test_configure_logging_writes_structured_lines(self) -> None:
        with TemporaryDirectory() as directory:
            with patch.dict("os.environ", {"MAESTRO_LOG_DIR": directory}, clear=False):
                configure_logging()
                log_event("test_event", provider="openai", action_count=2)
                lines = recent_log_lines(limit=5)

        self.assertEqual(len(lines), 1)
        self.assertIn('"event": "test_event"', lines[0])
        self.assertIn('"provider": "openai"', lines[0])

    def test_build_diagnostics_report_omits_api_key(self) -> None:
        with TemporaryDirectory() as directory:
            with patch.dict("os.environ", {"MAESTRO_LOG_DIR": directory}, clear=False):
                configure_logging()
                log_event("live_edit_failed", error="bridge offline")

                provider = ModelProviderConfig(
                    provider="openai",
                    openai=OpenAIProviderConfig(api_key="sk-secret", model="gpt-5.4"),
                )
                install_state = PluginInstallState(
                    source_dir=Path("/source"),
                    plugin_dir=Path("/plugins"),
                    missing_files=(),
                    outdated_files=(),
                    musescore_app_path=Path("/Applications/MuseScore 4.app"),
                )

                with patch(
                    "maestro_desktop.diagnostics.inspect_plugin_install",
                    return_value=install_state,
                ), patch(
                    "maestro_desktop.diagnostics.describe_plugin_status",
                    return_value="Maestro Plugin is installed and up to date.",
                ), patch(
                    "maestro_desktop.diagnostics.verify_bridge_connection",
                    return_value=(False, "bridge offline"),
                ):
                    report = build_diagnostics_report(provider)

        self.assertIn("App version: 0.1.1", report)
        self.assertIn("Provider mode: OpenAI (gpt-5.4)", report)
        self.assertIn("Plugin status: Maestro Plugin is installed and up to date.", report)
        self.assertIn("bridge offline", report)
        self.assertNotIn("sk-secret", report)


if __name__ == "__main__":
    unittest.main()
