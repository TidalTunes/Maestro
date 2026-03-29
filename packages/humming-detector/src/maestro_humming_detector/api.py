from __future__ import annotations

from pathlib import Path


def transcribe_humming(audio_path: str | Path) -> str:
    """Detect hummed notes from an audio file and return one note per line."""

    from ._pipeline import transcribe_path

    return transcribe_path(Path(audio_path))
