from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import platform

from .backend import ModelProviderConfig
from .plugin_setup import inspect_plugin_install, describe_plugin_status, verify_bridge_connection
from .runtime_support import app_log_dir, is_macos, macos_version
from .version import APP_VERSION, PRODUCT_POSITIONING


LOGGER = logging.getLogger("maestro.desktop")
LOG_FILENAME = "maestro.log"
MAX_LOG_BYTES = 512 * 1024
BACKUP_LOG_COUNT = 4


def log_path() -> Path:
    return app_log_dir() / LOG_FILENAME


def configure_logging() -> Path:
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if not any(isinstance(handler, RotatingFileHandler) for handler in LOGGER.handlers):
        handler = RotatingFileHandler(
            path,
            maxBytes=MAX_LOG_BYTES,
            backupCount=BACKUP_LOG_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False
    return path


def log_event(event: str, *, level: int = logging.INFO, **fields: object) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": logging.getLevelName(level),
        "event": event,
        "fields": {
            key: value
            for key, value in fields.items()
            if value is not None
        },
    }
    LOGGER.log(level, json.dumps(payload, sort_keys=True))


def recent_log_lines(*, limit: int = 40) -> list[str]:
    path = log_path()
    if not path.is_file():
        return []

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-limit:]


def provider_summary(provider_config: ModelProviderConfig) -> str:
    provider = provider_config.provider.strip().lower()
    if provider == "openai":
        model = ""
        if provider_config.openai is not None:
            model = provider_config.openai.model.strip()
        return f"OpenAI ({model or 'default model'})"

    model = ""
    base_url = ""
    if provider_config.ollama is not None:
        model = provider_config.ollama.model.strip()
        base_url = provider_config.ollama.base_url.strip()
    summary = f"Ollama ({model or 'default model'})"
    if base_url:
        summary += f" via {base_url}"
    return summary


def build_diagnostics_report(provider_config: ModelProviderConfig) -> str:
    install_state = inspect_plugin_install()
    bridge_ok, bridge_message = verify_bridge_connection(timeout=0.5, poll_interval=0.05)
    lines = [
        "Maestro Diagnostics",
        f"App version: {APP_VERSION}",
        f"Platform: {_platform_summary()}",
        f"Product: {PRODUCT_POSITIONING}",
        f"Provider mode: {provider_summary(provider_config)}",
        f"Plugin status: {describe_plugin_status(install_state)}",
        f"Plugin folder: {install_state.plugin_dir}",
        f"Bridge status: {bridge_message}",
        f"Log file: {log_path()}",
        "",
        "Recent logs:",
    ]
    logs = recent_log_lines()
    if logs:
        lines.extend(logs)
    else:
        lines.append("(no local logs yet)")

    if not bridge_ok:
        log_event("diagnostics_copied", bridge_status="offline")
    else:
        log_event("diagnostics_copied", bridge_status="connected")
    return "\n".join(lines)


def _platform_summary() -> str:
    if is_macos():
        return f"macOS {macos_version()}"
    return platform.platform()
