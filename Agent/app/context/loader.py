from __future__ import annotations

from pathlib import Path

from app.config import Settings


ROOT_DOC_FILES = (("Package README", "README.md"),)
DOC_FILES = (
    ("Getting started", "getting-started.md"),
    ("API reference", "api-reference.md"),
    ("Examples", "examples.md"),
)


class ReferenceLoadError(RuntimeError):
    """Raised when Maestro reference material cannot be loaded."""


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _format_block(label: str, path: Path) -> str:
    if not path.is_file():
        raise ReferenceLoadError(f"Required reference file is missing: {path}")
    return f"## {label}\n{_read_text(path)}"


def load_reference_corpus(settings: Settings) -> str:
    if not settings.maestro_docs_dir.is_dir():
        raise ReferenceLoadError(f"Maestro docs directory not found: {settings.maestro_docs_dir}")

    sections: list[str] = []
    for label, relative in ROOT_DOC_FILES:
        sections.append(_format_block(label, (settings.root_dir / relative).resolve()))
    for label, relative in DOC_FILES:
        sections.append(_format_block(label, (settings.maestro_docs_dir / relative).resolve()))
    return "\n\n".join(sections)
