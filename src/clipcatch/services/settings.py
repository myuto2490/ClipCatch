"""利用者の設定。macOS では plist、Windows ではレジストリに保存される（QSettings）。"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, TypeVar

from PySide6.QtCore import QObject, QSettings, QStandardPaths, Signal

from clipcatch.core.formats import CookieBrowser, DownloadFormat, VideoQuality

E = TypeVar("E", bound=Enum)


def default_download_directory() -> Path:
    """macOS は「ムービー」、Windows は「ビデオ」。移動されていても OS が正しく返す。"""
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.MoviesLocation)
    return Path(location) if location else Path.home()


def _to_bool(value: Any, default: bool) -> bool:
    # QSettings は環境によって bool を "true" / "false" の文字列で返す
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    if isinstance(value, int):
        return bool(value)
    return default


class Settings(QObject):
    changed = Signal(str)  # 変わった項目の名前

    _BOOL_DEFAULTS: ClassVar[dict[str, bool]] = {
        "revealWhenDone": False,
        "autoPasteURL": True,
        "accelerateWithAria2c": True,
        "useUserConfig": False,
        "allowPlaylist": False,
        "notifyWhenDone": True,
        "checkForAppUpdates": True,
    }

    def __init__(self, store: QSettings | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._store = store or QSettings()

    # MARK: - 汎用

    def _enum(self, key: str, kind: type[E], default: E) -> E:
        try:
            return kind(self._store.value(key, default.value))
        except ValueError:
            return default

    def _bool(self, key: str) -> bool:
        default = self._BOOL_DEFAULTS[key]
        return _to_bool(self._store.value(key, default), default)

    def _write(self, key: str, value: Any) -> None:
        if isinstance(value, Enum):
            value = value.value
        self._store.setValue(key, value)
        self.changed.emit(key)

    # MARK: - 項目

    @property
    def format(self) -> DownloadFormat:
        return self._enum("format", DownloadFormat, DownloadFormat.MP4)

    @format.setter
    def format(self, value: DownloadFormat) -> None:
        self._write("format", value)

    @property
    def quality(self) -> VideoQuality:
        return self._enum("quality", VideoQuality, VideoQuality.UNLIMITED)

    @quality.setter
    def quality(self, value: VideoQuality) -> None:
        self._write("quality", value)

    @property
    def cookie_browser(self) -> CookieBrowser:
        value = self._enum("cookieBrowser", CookieBrowser, CookieBrowser.NONE)
        return value if value in CookieBrowser.available() else CookieBrowser.NONE

    @cookie_browser.setter
    def cookie_browser(self, value: CookieBrowser) -> None:
        self._write("cookieBrowser", value)

    @property
    def output_directory(self) -> Path:
        value = self._store.value("outputDirectory")
        return Path(value) if value else default_download_directory()

    @output_directory.setter
    def output_directory(self, value: Path) -> None:
        self._write("outputDirectory", str(value))

    def get_flag(self, key: str) -> bool:
        return self._bool(key)

    def set_flag(self, key: str, value: bool) -> None:
        if key not in self._BOOL_DEFAULTS:
            raise KeyError(key)
        self._write(key, bool(value))

    @property
    def reveal_when_done(self) -> bool:
        """ダウンロード完了後にファイルマネージャで保存先を開く。"""
        return self._bool("revealWhenDone")

    @property
    def auto_paste_url(self) -> bool:
        """アプリを前面にしたとき、クリップボードの URL を自動で入力する。"""
        return self._bool("autoPasteURL")

    @property
    def accelerate_with_aria2c(self) -> bool:
        """aria2c があれば外部ダウンローダとして使い、単一ファイルを多重接続で取る。"""
        return self._bool("accelerateWithAria2c")

    @property
    def use_user_config(self) -> bool:
        """yt-dlp の個人設定ファイルを読ませる。既定では無視して挙動を固定する。"""
        return self._bool("useUserConfig")

    @property
    def allow_playlist(self) -> bool:
        """プレイリストの URL なら中身をすべて保存する。"""
        return self._bool("allowPlaylist")

    @property
    def notify_when_done(self) -> bool:
        """アプリが背面にあるとき、完了を通知で知らせる。"""
        return self._bool("notifyWhenDone")

    @property
    def check_for_app_updates(self) -> bool:
        return self._bool("checkForAppUpdates")

    @property
    def log_expanded(self) -> bool:
        return _to_bool(self._store.value("logExpanded", False), False)

    @log_expanded.setter
    def log_expanded(self, value: bool) -> None:
        self._write("logExpanded", bool(value))

    def window_geometry(self) -> bytes | None:
        value = self._store.value("windowGeometry")
        return bytes(value) if value else None

    def set_window_geometry(self, value: bytes) -> None:
        self._store.setValue("windowGeometry", value)
