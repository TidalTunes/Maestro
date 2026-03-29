from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


ROOT_DIR = Path(__file__).resolve().parents[5]
DEFAULT_SKILL_DIR = Path.home() / ".codex" / "skills" / "maestroxml-sheet-music"
DEFAULT_DOCS_DIR = ROOT_DIR / "packages" / "maestroxml" / "docs"
DEFAULT_MAESTROXML_SRC_DIR = ROOT_DIR / "packages" / "maestroxml" / "src"


def _resolve_path(value: str, default: Path) -> Path:
    if not value:
        return default.resolve()
    path = Path(value)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path.resolve()


@dataclass(frozen=True)
class ServiceSettings:
    root_dir: Path
    maestro_skill_dir: Path
    maestro_docs_dir: Path
    maestroxml_src_dir: Path
    openai_model: str
    openai_reasoning_effort: str
    openai_max_output_tokens: int
    execution_timeout_seconds: int


def get_settings() -> ServiceSettings:
    skill_dir = os.environ.get("MAESTRO_SKILL_DIR") or os.environ.get("MAESTRO_SKILL_PATH", "")
    docs_dir = os.environ.get("MAESTRO_DOCS_DIR", "")
    maestroxml_src_dir = os.environ.get("MAESTRO_MAESTROXML_SRC_DIR", "")
    return ServiceSettings(
        root_dir=ROOT_DIR,
        maestro_skill_dir=_resolve_path(skill_dir, DEFAULT_SKILL_DIR),
        maestro_docs_dir=_resolve_path(docs_dir, DEFAULT_DOCS_DIR),
        maestroxml_src_dir=_resolve_path(maestroxml_src_dir, DEFAULT_MAESTROXML_SRC_DIR),
        openai_model=os.environ.get("OPENAI_MODEL", "gpt-5.4"),
        openai_reasoning_effort=os.environ.get("OPENAI_REASONING_EFFORT", "low"),
        openai_max_output_tokens=int(os.environ.get("OPENAI_MAX_OUTPUT_TOKENS", "20000")),
        execution_timeout_seconds=int(os.environ.get("EXECUTION_TIMEOUT_SECONDS", "20")),
    )
