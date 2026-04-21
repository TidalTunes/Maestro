from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "apps" / "frontend-desktop" / "src"
for extra in (ROOT, SRC):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from maestro_desktop.backend import ModelProviderConfig, OllamaProviderConfig, OpenAIProviderConfig
from maestro_desktop.settings_store import ProviderConfigStore


class ProviderConfigStoreTests(unittest.TestCase):
    def test_save_and_load_round_trip_non_secret_settings(self) -> None:
        with TemporaryDirectory() as directory:
            settings_path = Path(directory) / "settings.json"
            store = ProviderConfigStore(settings_path=settings_path)
            config = ModelProviderConfig(
                provider="ollama",
                openai=OpenAIProviderConfig(api_key="", model="gpt-5.4"),
                ollama=OllamaProviderConfig(
                    model="qwen3.5:cloud",
                    base_url="http://localhost:11434/api",
                ),
            )

            with patch.dict("os.environ", {}, clear=True):
                with patch.object(ProviderConfigStore, "secure_key_storage_available", return_value=False):
                    store.save(config)
                    loaded = store.load(ModelProviderConfig.for_ollama(model="fallback"))

        self.assertEqual(loaded.provider, "ollama")
        self.assertEqual(loaded.ollama.model, "qwen3.5:cloud")
        self.assertEqual(loaded.ollama.base_url, "http://localhost:11434/api")
        self.assertEqual(loaded.openai.model, "gpt-5.4")

    def test_load_prefers_environment_values(self) -> None:
        with TemporaryDirectory() as directory:
            settings_path = Path(directory) / "settings.json"
            settings_path.write_text(
                '{\n'
                '  "provider": "ollama",\n'
                '  "openai_model": "gpt-4",\n'
                '  "ollama_model": "old-model",\n'
                '  "ollama_base_url": "http://old.local/api"\n'
                '}\n',
                encoding="utf-8",
            )
            store = ProviderConfigStore(settings_path=settings_path)
            with patch.dict(
                "os.environ",
                {
                    "MAESTRO_MODEL_PROVIDER": "openai",
                    "OPENAI_MODEL": "gpt-5.4",
                    "OPENAI_API_KEY": "sk-from-env",
                },
                clear=True,
            ):
                loaded = store.load(ModelProviderConfig.for_ollama(model="fallback"))

        self.assertEqual(loaded.provider, "openai")
        self.assertEqual(loaded.openai.model, "gpt-5.4")
        self.assertEqual(loaded.openai.api_key, "sk-from-env")

    def test_load_and_save_use_keychain_when_available(self) -> None:
        with TemporaryDirectory() as directory:
            settings_path = Path(directory) / "settings.json"
            store = ProviderConfigStore(settings_path=settings_path)
            config = ModelProviderConfig.for_openai(api_key="sk-test", model="gpt-5.4")
            subprocess_calls: list[list[str]] = []

            def fake_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                subprocess_calls.append(cmd)
                if "find-generic-password" in cmd:
                    return subprocess.CompletedProcess(cmd, 0, stdout="sk-from-keychain\n", stderr="")
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with patch.dict("os.environ", {}, clear=True):
                with patch.object(ProviderConfigStore, "secure_key_storage_available", return_value=True):
                    with patch("maestro_desktop.settings_store.subprocess.run", side_effect=fake_run):
                        store.save(config)
                        loaded = store.load(ModelProviderConfig.for_openai(model="fallback"))

        self.assertEqual(loaded.openai.api_key, "sk-from-keychain")
        self.assertTrue(any("add-generic-password" in call for call in subprocess_calls))
        self.assertTrue(any("find-generic-password" in call for call in subprocess_calls))


if __name__ == "__main__":
    unittest.main()
