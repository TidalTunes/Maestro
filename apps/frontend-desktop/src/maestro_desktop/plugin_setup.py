from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import shutil
import subprocess

from maestro_musescore_bridge import BridgeError, MuseScoreBridgeClient

from .runtime_support import (
    PLUGIN_FILENAMES,
    detect_musescore_app,
    detect_musescore_plugin_dir,
    plugin_source_dir,
)


PLUGIN_DISPLAY_NAME = "Maestro Plugin"


@dataclass(frozen=True)
class PluginInstallState:
    source_dir: Path
    plugin_dir: Path
    missing_files: tuple[str, ...]
    outdated_files: tuple[str, ...]
    musescore_app_path: Path | None

    @property
    def installed(self) -> bool:
        return not self.missing_files

    @property
    def up_to_date(self) -> bool:
        return self.installed and not self.outdated_files


def _file_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def inspect_plugin_install(
    *,
    source_dir: Path | None = None,
    plugin_dir: Path | None = None,
    musescore_app_path: Path | None = None,
) -> PluginInstallState:
    resolved_source_dir = plugin_source_dir() if source_dir is None else Path(source_dir)
    resolved_plugin_dir = (
        detect_musescore_plugin_dir() if plugin_dir is None else Path(plugin_dir).expanduser()
    )
    resolved_app_path = detect_musescore_app() if musescore_app_path is None else musescore_app_path

    missing: list[str] = []
    outdated: list[str] = []
    for name in PLUGIN_FILENAMES:
        source_path = resolved_source_dir / name
        target_path = resolved_plugin_dir / name
        if not target_path.is_file():
            missing.append(name)
            continue
        if _file_digest(source_path) != _file_digest(target_path):
            outdated.append(name)

    return PluginInstallState(
        source_dir=resolved_source_dir,
        plugin_dir=resolved_plugin_dir,
        missing_files=tuple(missing),
        outdated_files=tuple(outdated),
        musescore_app_path=resolved_app_path,
    )


def install_plugin(
    *,
    source_dir: Path | None = None,
    plugin_dir: Path | None = None,
) -> PluginInstallState:
    resolved_source_dir = plugin_source_dir() if source_dir is None else Path(source_dir)
    resolved_plugin_dir = (
        detect_musescore_plugin_dir() if plugin_dir is None else Path(plugin_dir).expanduser()
    )
    resolved_plugin_dir.mkdir(parents=True, exist_ok=True)

    for name in PLUGIN_FILENAMES:
        shutil.copy2(resolved_source_dir / name, resolved_plugin_dir / name)

    return inspect_plugin_install(
        source_dir=resolved_source_dir,
        plugin_dir=resolved_plugin_dir,
    )


def launch_musescore(
    *,
    musescore_app_path: Path | None = None,
) -> Path:
    target = detect_musescore_app() if musescore_app_path is None else musescore_app_path
    if target is None or not target.is_dir():
        raise FileNotFoundError("MuseScore 4.app was not found in /Applications or ~/Applications.")

    subprocess.Popen(
        ["open", "-a", str(target)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return target


def verify_bridge_connection(
    *,
    timeout: float = 1.0,
    poll_interval: float = 0.05,
    client_factory=MuseScoreBridgeClient,
) -> tuple[bool, str]:
    try:
        client = client_factory(timeout=timeout, poll_interval=poll_interval)
        result = client.ping()
    except BridgeError as exc:
        return False, str(exc)

    message = result.get("message")
    if isinstance(message, str) and message.strip().lower() == "pong":
        return True, f"{PLUGIN_DISPLAY_NAME} is connected."
    return False, "MuseScore responded, but the Maestro bridge did not report a healthy status."
