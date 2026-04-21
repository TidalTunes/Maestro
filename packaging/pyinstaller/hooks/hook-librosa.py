from __future__ import annotations

from pathlib import Path

import librosa
from PyInstaller.utils.hooks import copy_metadata, collect_submodules


_LIBROSA_ROOT = Path(librosa.__file__).resolve().parent

datas = copy_metadata("librosa")
intervals_path = _LIBROSA_ROOT / "core" / "intervals.msgpack"
if intervals_path.is_file():
    datas.append((str(intervals_path), "librosa/core"))

hiddenimports = [
    name
    for name in collect_submodules("librosa")
    if ".tests" not in name
    and ".test_" not in name
    and not name.startswith("librosa.decompose")
    and not name.startswith("librosa.display")
]

excludedimports = [
    "pytest",
    "matplotlib",
    "IPython",
]
