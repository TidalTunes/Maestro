from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import os
import sys


BUNDLE_DIRNAME = "maestro_bundle"
PLUGIN_FILENAMES = (
    "maestro_python_bridge.qml",
    "bridge_actions.js",
    "score_operations.js",
)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def is_macos() -> bool:
    return sys.platform == "darwin"


def supports_guided_macos_setup() -> bool:
    return is_frozen() and is_macos()


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    return Path(value).expanduser().resolve()


@lru_cache(maxsize=1)
def runtime_root() -> Path:
    explicit_bundle_root = _env_path("MAESTRO_BUNDLE_ROOT")
    if explicit_bundle_root is not None:
        return explicit_bundle_root

    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            return Path(meipass).resolve() / BUNDLE_DIRNAME

    explicit_repo_root = _env_path("MAESTRO_REPO_ROOT")
    if explicit_repo_root is not None:
        return explicit_repo_root

    return Path(__file__).resolve().parents[4]


def resource_path(*parts: str) -> Path:
    return runtime_root().joinpath(*parts)


def readme_path() -> Path:
    return resource_path("README.md")


def images_dir() -> Path:
    return resource_path("images")


def app_icon_path() -> Path:
    return images_dir() / "frame3.png"


def plugin_source_dir() -> Path:
    return resource_path("apps", "plugin", "assets")


def agent_root_dir() -> Path:
    return resource_path("Agent")


def agent_core_src_dir() -> Path:
    return resource_path("packages", "agent-core", "src")


def humming_detector_src_dir() -> Path:
    return resource_path("packages", "humming-detector", "src")


def maestroxml_src_dir() -> Path:
    return resource_path("packages", "maestroxml", "src")


def maestroxml_docs_dir() -> Path:
    return resource_path("packages", "maestroxml", "docs")


def bridge_src_dir() -> Path:
    return resource_path("packages", "maestro-musescore-bridge", "src")


def skill_dir() -> Path:
    bundled = resource_path("skills", "maestroxml-sheet-music")
    if bundled.is_dir():
        return bundled
    return Path.home() / ".codex" / "skills" / "maestroxml-sheet-music"


def bootstrap_runtime_imports() -> None:
    for path in (
        agent_core_src_dir(),
        maestroxml_src_dir(),
        humming_detector_src_dir(),
        bridge_src_dir(),
        agent_root_dir(),
    ):
        resolved = str(path.resolve())
        if resolved not in sys.path:
            sys.path.insert(0, resolved)


def frame_paths() -> list[Path]:
    return [
        images_dir() / "frame1.png",
        images_dir() / "frame2.png",
        images_dir() / "frame3.png",
        images_dir() / "frame4.png",
        images_dir() / "frame5.png",
    ]


def musescore_plugin_dir_candidates(home: Path | None = None) -> tuple[Path, ...]:
    base = Path.home() if home is None else Path(home).expanduser()
    documents = base / "Documents"
    candidates = [
        documents / "MuseScore4" / "Plugins",
        documents / "MuseScore3" / "Plugins",
    ]
    if is_macos():
        candidates.extend(
            [
                documents / "MuseScore4_Deprecated" / "Plugins",
                base / "Library" / "Application Support" / "MuseScore" / "MuseScore4" / "Plugins",
            ]
        )
    return tuple(dict.fromkeys(candidates))


def detect_musescore_plugin_dir(home: Path | None = None) -> Path:
    candidates = musescore_plugin_dir_candidates(home)
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


def musescore_app_candidates(home: Path | None = None) -> tuple[Path, ...]:
    if not supports_guided_macos_setup():
        return tuple()
    base = Path.home() if home is None else Path(home).expanduser()
    return (
        Path("/Applications/MuseScore 4.app"),
        base / "Applications" / "MuseScore 4.app",
        Path("/Applications/MuseScore.app"),
        base / "Applications" / "MuseScore.app",
    )


def detect_musescore_app(home: Path | None = None) -> Path | None:
    for candidate in musescore_app_candidates(home):
        if candidate.is_dir():
            return candidate
    return None


def runtime_runner_executable() -> Path | None:
    explicit = _env_path("MAESTRO_RUNTIME_RUNNER")
    if explicit is not None:
        return explicit
    if not is_frozen():
        return None

    executable_dir = Path(sys.executable).resolve().parent
    for name in ("maestro-runtime-runner", "maestro-runtime-runner.exe"):
        candidate = executable_dir / name
        if candidate.is_file():
            return candidate
    return None
