"""同梱する画像（アプリアイコン）の読み込み。"""

from __future__ import annotations

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
