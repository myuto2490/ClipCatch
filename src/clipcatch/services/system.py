"""ファイルマネージャやクリップボードなど、OS との連携。"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication

from clipcatch.core.platform import IS_MACOS, IS_WINDOWS

_URL = re.compile(r"^https?://[^\s/$.?#][^\s]*$", re.IGNORECASE)


def is_web_url(text: str) -> bool:
    """http(s) で始まり、ホスト名を持つ URL か。"""
    text = text.strip()
    if not _URL.match(text):
        return False
    url = QUrl(text, QUrl.ParsingMode.StrictMode)
    return url.isValid() and bool(url.host())


def clipboard_text() -> str:
    clipboard = QGuiApplication.clipboard()
    return clipboard.text().strip() if clipboard else ""


def open_folder(path: Path) -> bool:
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def open_url(url: str) -> bool:
    return QDesktopServices.openUrl(QUrl(url))


def reveal_file(path: Path) -> bool:
    """Finder / エクスプローラでファイルを選択した状態で表示する。"""
    if not path.exists():
        return False
    if IS_MACOS:
        subprocess.Popen(["/usr/bin/open", "-R", str(path)])
        return True
    if IS_WINDOWS:
        # explorer は引数の書き方に厳しいので 1 つの文字列で渡す
        subprocess.Popen(f'explorer /select,"{path}"')
        return True
    return open_folder(path.parent)
