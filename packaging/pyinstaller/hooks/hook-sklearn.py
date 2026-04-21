from __future__ import annotations

from PyInstaller.utils.hooks import collect_data_files


datas = collect_data_files(
    "sklearn",
    excludes=[
        "**/tests",
        "**/tests/**",
        "**/testing",
        "**/testing/**",
        "**/__pycache__",
        "**/__pycache__/**",
    ],
)
