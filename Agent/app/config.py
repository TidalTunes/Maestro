from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


AGENT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = AGENT_ROOT / "reference-corpus"
DEFAULT_DOCS_DIR = REFERENCE_ROOT / "docs"


def _resolve_path(value: str, default: Path) -> Path:
    if not value:
        return default.resolve()
    path = Path(value)
    if not path.is_absolute():
        path = REFERENCE_ROOT / path
    return path.resolve()


@dataclass(frozen=True)
class Settings:
    root_dir: Path
    maestro_docs_dir: Path
    openai_model: str
    openai_reasoning_effort: str
    openai_max_output_tokens: int


def get_settings() -> Settings:
    docs_dir = os.environ.get("MAESTRO_DOCS_DIR", "")
    return Settings(
        root_dir=REFERENCE_ROOT,
        maestro_docs_dir=_resolve_path(docs_dir, DEFAULT_DOCS_DIR),
        openai_model=os.environ.get("OPENAI_MODEL", "gpt-5.4"),
        openai_reasoning_effort=os.environ.get("OPENAI_REASONING_EFFORT", "low"),
        openai_max_output_tokens=int(os.environ.get("OPENAI_MAX_OUTPUT_TOKENS", "20000")),
    )
