from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
from typing import Sequence

from maestro_musescore_bridge import BridgeError, MuseScoreBridgeClient

from .runtime_support import (
    PLUGIN_FILENAMES,
    detect_musescore_app,
    detect_musescore_plugin_dir,
    plugin_source_dir,
    supports_guided_macos_setup,
)


PLUGIN_DISPLAY_NAME = "Maestro Plugin"
MANUAL_PLUGIN_OPEN_STEP = f"Open MuseScore and run Plugins > Maestro > {PLUGIN_DISPLAY_NAME}."


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


def describe_plugin_status(state: PluginInstallState) -> str:
    if state.up_to_date:
        return f"{PLUGIN_DISPLAY_NAME} is installed and up to date."

    details: list[str] = []
    if state.missing_files:
        details.append("Missing: " + ", ".join(state.missing_files))
    if state.outdated_files:
        details.append("Needs update: " + ", ".join(state.outdated_files))
    return "; ".join(details)


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
    if not supports_guided_macos_setup():
        raise FileNotFoundError(
            "Automatic MuseScore launch is only available in the packaged macOS app. "
            f"{MANUAL_PLUGIN_OPEN_STEP}"
        )

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


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="maestro-install-plugin",
        description="Install or inspect the Maestro MuseScore plugin files.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command_name in ("status", "install"):
        subparser = subparsers.add_parser(command_name)
        subparser.add_argument(
            "--plugin-dir",
            help="Override the destination MuseScore plugin directory.",
        )
        subparser.add_argument(
            "--source-dir",
            help=argparse.SUPPRESS,
        )

    return parser


def _resolve_cli_dir(path_text: str | None) -> Path | None:
    if not path_text:
        return None
    return Path(path_text).expanduser()


def _print_state(state: PluginInstallState) -> None:
    print(f"Plugin source: {state.source_dir}")
    print(f"Plugin folder: {state.plugin_dir}")
    print(f"Plugin status: {describe_plugin_status(state)}")

    if supports_guided_macos_setup():
        if state.musescore_app_path is not None:
            print(f"MuseScore app: {state.musescore_app_path}")
        else:
            print("MuseScore app: not found in /Applications or ~/Applications")
    else:
        print("MuseScore app: open MuseScore manually on this platform/install mode")

    print(f"Next step: {MANUAL_PLUGIN_OPEN_STEP}")


def cli_main(argv: Sequence[str] | None = None) -> int:
    parser = _build_cli_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    plugin_dir = _resolve_cli_dir(args.plugin_dir)
    source_dir = _resolve_cli_dir(args.source_dir)

    if args.command == "status":
        state = inspect_plugin_install(source_dir=source_dir, plugin_dir=plugin_dir)
        _print_state(state)
        return 0

    if args.command == "install":
        state = install_plugin(source_dir=source_dir, plugin_dir=plugin_dir)
        print(f"Installed {PLUGIN_DISPLAY_NAME} into {state.plugin_dir}")
        _print_state(state)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2
