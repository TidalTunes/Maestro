from __future__ import annotations

from pathlib import Path

import soundfile


_SITE_PACKAGES_ROOT = Path(soundfile.__file__).resolve().parent
_SOUNDFILE_DATA = _SITE_PACKAGES_ROOT / "_soundfile_data"

datas = []
if _SOUNDFILE_DATA.is_dir():
    for binary_path in sorted(_SOUNDFILE_DATA.glob("libsndfile*")):
        if binary_path.is_file():
            datas.append((str(binary_path), "_soundfile_data"))

excludedimports = [
    "pytest",
    "IPython",
]
