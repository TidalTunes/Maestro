from __future__ import annotations

from pathlib import Path


SKILL_FILES = (
    ("Maestro skill", "SKILL.md"),
    ("Maestro skill API patterns", "references/api-patterns.md"),
    ("Maestro skill examples", "references/examples.md"),
)
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


def _load_skill_blocks(skill_dir: Path) -> list[str]:
    if not skill_dir.is_dir():
        raise ReferenceLoadError(f"Maestro skill directory not found: {skill_dir}")

    blocks: list[str] = []
    for label, relative in SKILL_FILES:
        blocks.append(_format_block(label, skill_dir / relative))
    return blocks


def _load_doc_blocks(root_dir: Path, docs_dir: Path) -> list[str]:
    if not docs_dir.is_dir():
        raise ReferenceLoadError(f"Maestro docs directory not found: {docs_dir}")

    chunks: list[str] = []
    for label, relative in ROOT_DOC_FILES:
        chunks.append(_format_block(label, (root_dir / relative).resolve()))
    for label, relative in DOC_FILES:
        chunks.append(_format_block(label, (docs_dir / relative).resolve()))
    return chunks


def load_reference_corpus(root_dir: Path, skill_dir: Path, docs_dir: Path) -> str:
    sections = _load_skill_blocks(skill_dir)
    sections.extend(_load_doc_blocks(root_dir, docs_dir))
    return "\n\n".join(sections)
