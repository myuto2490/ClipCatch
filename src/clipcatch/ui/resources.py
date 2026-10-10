"""同梱する画像（アプリアイコン）の読み込み。"""

from __future__ import annotations

import sys
from functools import cache
from pathlib import Path

from PySide6.QtGui import QIcon

ASSETS = Path(__file__).resolve().parent.parent / "assets"


@cache
def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 32, 64, 128, 256, 512, 1024):
        path = ASSETS / f"icon_{size}.png"
        if path.exists():
            icon.addFile(str(path))
    return icon


def licenses_directory() -> Path | None:
    """同梱したライセンス文書の場所。ソースから動かしているときはリポジトリの直下。"""
    if getattr(sys, "frozen", False):
        candidate = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "licenses"
    else:
        candidate = ASSETS.parent.parent.parent / "LICENSES"
    return candidate if candidate.is_dir() else None
