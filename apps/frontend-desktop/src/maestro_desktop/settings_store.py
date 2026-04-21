from __future__ import annotations

import json
from pathlib import Path
import os
import shutil
import subprocess

from .backend import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    ModelProviderConfig,
    OllamaProviderConfig,
    OpenAIProviderConfig,
)
from .runtime_support import APP_BUNDLE_ID, app_support_dir, is_macos


SETTINGS_FILENAME = "settings.json"
KEYCHAIN_SERVICE = f"{APP_BUNDLE_ID}.openai"
KEYCHAIN_ACCOUNT = "default"


class SettingsStoreError(RuntimeError):
    """Raised when persisted Maestro settings cannot be read or written."""


class ProviderConfigStore:
    def __init__(self, *, settings_path: Path | None = None) -> None:
        self._settings_path = settings_path or (app_support_dir() / SETTINGS_FILENAME)

    def load(self, default_config: ModelProviderConfig) -> ModelProviderConfig:
        stored = self._load_settings_payload()
        provider = self._resolve_provider(default_config, stored)
        openai_model = (
            os.environ.get("OPENAI_MODEL", "").strip()
            or stored.get("openai_model", "").strip()
            or (default_config.openai.model if default_config.openai is not None else "").strip()
        )
        ollama_model = (
            os.environ.get("OLLAMA_MODEL", "").strip()
            or stored.get("ollama_model", "").strip()
            or (default_config.ollama.model if default_config.ollama is not None else "").strip()
            or DEFAULT_OLLAMA_MODEL
        )
        ollama_base_url = (
            os.environ.get("OLLAMA_BASE_URL", "").strip()
            or stored.get("ollama_base_url", "").strip()
            or (default_config.ollama.base_url if default_config.ollama is not None else "").strip()
            or DEFAULT_OLLAMA_BASE_URL
        )
        openai_api_key = (
            os.environ.get("OPENAI_API_KEY", "").strip()
            or self._read_openai_api_key()
            or (default_config.openai.api_key if default_config.openai is not None else "").strip()
        )

        return ModelProviderConfig(
            provider=provider,
            openai=OpenAIProviderConfig(
                api_key=openai_api_key,
                model=openai_model,
            ),
            ollama=OllamaProviderConfig(
                model=ollama_model,
                base_url=ollama_base_url,
            ),
        )

    def save(self, provider_config: ModelProviderConfig) -> None:
        payload = {
            "provider": provider_config.provider.strip().lower() or "ollama",
            "openai_model": (
                provider_config.openai.model.strip()
                if provider_config.openai is not None
                else ""
            ),
            "ollama_model": (
                provider_config.ollama.model.strip()
                if provider_config.ollama is not None
                else DEFAULT_OLLAMA_MODEL
            ),
            "ollama_base_url": (
                provider_config.ollama.base_url.strip()
                if provider_config.ollama is not None
                else ""
            ),
        }

        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._settings_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self._write_openai_api_key(
            provider_config.openai.api_key if provider_config.openai is not None else ""
        )

    def _load_settings_payload(self) -> dict[str, str]:
        if not self._settings_path.is_file():
            return {}

        try:
            payload = json.loads(self._settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SettingsStoreError(
                f"Saved settings at {self._settings_path} are not valid JSON."
            ) from exc

        if not isinstance(payload, dict):
            raise SettingsStoreError(
                f"Saved settings at {self._settings_path} are not a JSON object."
            )

        return {
            key: str(value).strip()
            for key, value in payload.items()
            if isinstance(key, str) and isinstance(value, str)
        }

    @staticmethod
    def _resolve_provider(
        default_config: ModelProviderConfig,
        stored: dict[str, str],
    ) -> str:
        provider = (
            os.environ.get("MAESTRO_MODEL_PROVIDER", "").strip().lower()
            or os.environ.get("MAESTRO_PROVIDER", "").strip().lower()
            or stored.get("provider", "").strip().lower()
            or default_config.provider.strip().lower()
            or "ollama"
        )
        if provider not in {"openai", "ollama"}:
            return "ollama"
        return provider

    @staticmethod
    def secure_key_storage_available() -> bool:
        return is_macos() and shutil.which("security") is not None

    def _read_openai_api_key(self) -> str:
        if not self.secure_key_storage_available():
            return ""

        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-a",
                KEYCHAIN_ACCOUNT,
                "-s",
                KEYCHAIN_SERVICE,
                "-w",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()

    def _write_openai_api_key(self, api_key: str) -> None:
        value = api_key.strip()
        if not value:
            self._delete_openai_api_key()
            return

        if not self.secure_key_storage_available():
            return

        result = subprocess.run(
            [
                "security",
                "add-generic-password",
                "-U",
                "-a",
                KEYCHAIN_ACCOUNT,
                "-s",
                KEYCHAIN_SERVICE,
                "-l",
                "Maestro OpenAI API Key",
                "-w",
                value,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip() or "unknown keychain error"
            raise SettingsStoreError(f"Could not store the OpenAI API key in Keychain: {stderr}")

    def _delete_openai_api_key(self) -> None:
        if not self.secure_key_storage_available():
            return

        subprocess.run(
            [
                "security",
                "delete-generic-password",
                "-a",
                KEYCHAIN_ACCOUNT,
                "-s",
                KEYCHAIN_SERVICE,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
