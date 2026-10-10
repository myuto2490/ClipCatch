"""ファイルマネージャやクリップボードなど、OS との連携。"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, QUrl
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


def relaunch() -> bool:
    """同じアプリをもう 1 つ起動する。呼び出し側は直後に終了すること。

    macOS の .app は `open -n` で開き直し、Dock やメニューバーが正しく切り替わるようにする。
    """
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        if IS_MACOS and executable.parent.name == "MacOS":
            program, arguments = "/usr/bin/open", ["-n", str(executable.parents[2])]
        else:
            program, arguments = str(executable), []
    else:
        program, arguments = sys.executable, ["-m", "clipcatch"]
    result = QProcess.startDetached(program, arguments)
    # PySide6 のバージョンによって bool か (bool, pid) が返る
    return bool(result[0] if isinstance(result, tuple) else result)
