"""HTTP 通信（ツールの取得・更新確認・サムネイル）。

Qt のネットワークは OS の TLS 実装と証明書ストアを使うので、配布版でも
CA バンドルを同梱する必要がない。
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QByteArray, QFile, QIODevice, QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from clipcatch import APP_NAME, __version__
from clipcatch.core.platform import IS_MACOS, IS_WINDOWS

_manager: QNetworkAccessManager | None = None


def user_agent() -> str:
    system = "macOS" if IS_MACOS else "Windows" if IS_WINDOWS else "Linux"
    return f"{APP_NAME}/{__version__} ({system})"


def manager() -> QNetworkAccessManager:
    global _manager
    if _manager is None:
        _manager = QNetworkAccessManager()
        _manager.setRedirectPolicy(QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
    return _manager


def make_request(url: str, timeout_ms: int = 30_000) -> QNetworkRequest:
    request = QNetworkRequest(QUrl(url))
    request.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, user_agent())
    request.setTransferTimeout(timeout_ms)
    return request


def _http_status(reply: QNetworkReply) -> int:
    value = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
    return int(value) if value is not None else 0


def fetch(
    url: str,
    on_done: Callable[[bytes | None, str | None], None],
    timeout_ms: int = 20_000,
    headers: dict[str, str] | None = None,
) -> QNetworkReply:
    """`url` の中身を取得し、`on_done(data, error)` を呼ぶ。"""
    request = make_request(url, timeout_ms)
    for key, value in (headers or {}).items():
        request.setRawHeader(QByteArray(key.encode()), QByteArray(value.encode()))
    reply = manager().get(request)

    def finished() -> None:
        status = _http_status(reply)
        if reply.error() != QNetworkReply.NetworkError.NoError:
            on_done(None, reply.errorString())
        elif status and not 200 <= status < 300:
            on_done(None, f"HTTP {status}")
        else:
            on_done(bytes(reply.readAll().data()), None)
        reply.deleteLater()

    reply.finished.connect(finished)
    return reply


# 実行中のダウンロード。途中で GC に回収されないよう参照を保つ。
_running: set[FileDownload] = set()


class FileDownload(QObject):
    """進捗つきでファイルを 1 つ保存する。

    書きかけのファイルを本来の名前で残さないよう、同じフォルダの一時ファイルに
    書き込んでから最後に置き換える。
    """

    progress = Signal(float)  # 0.0–1.0（大きさ不明なら来ない）
    finished = Signal(str)  # 失敗時はメッセージ、成功時は空文字

    MAX_ATTEMPTS = 3

    def __init__(self, url: str, destination: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._url = url
        self._destination = destination
        self._partial = destination.with_name(destination.name + ".part")
        self._file: QFile | None = None
        self._reply: QNetworkReply | None = None
        self._attempt = 0
        self._aborted = False

    def start(self) -> FileDownload:
        _running.add(self)
        self._destination.parent.mkdir(parents=True, exist_ok=True)
        self._begin_attempt()
        return self

    def _begin_attempt(self) -> None:
        self._attempt += 1
        self._file = QFile(str(self._partial))
        if not self._file.open(QIODevice.OpenModeFlag.WriteOnly | QIODevice.OpenModeFlag.Truncate):
            self._finish(self._file.errorString())
            return
        # 大きなファイルでも止まらないよう、転送が途切れたときだけ打ち切る
        self._reply = manager().get(make_request(self._url, timeout_ms=60_000))
        self._reply.readyRead.connect(self._write_available)
        self._reply.downloadProgress.connect(self._on_progress)
        self._reply.finished.connect(self._on_finished)

    def abort(self) -> None:
        self._aborted = True
        if self._reply is not None:
            self._reply.abort()

    def _write_available(self) -> None:
        reply, file = self._reply, self._file
        if reply is not None and file is not None and reply.isOpen():
            file.write(reply.readAll())

    def _on_progress(self, received: int, total: int) -> None:
        if total > 0:
            self.progress.emit(received / total)

    def _on_finished(self) -> None:
        reply = self._reply
        assert reply is not None
        self._write_available()
        self._reply = None
        status = _http_status(reply)
        error: str | None = None
        retryable = False
        if reply.error() != QNetworkReply.NetworkError.NoError:
            error = reply.errorString()
            # 4xx（存在しない・権限なし）はやり直しても変わらない
            retryable = not (400 <= status < 500)
        elif status and not 200 <= status < 300:
            error = f"HTTP {status}"
            retryable = status >= 500
        reply.deleteLater()

        if error and retryable and not self._aborted and self._attempt < self.MAX_ATTEMPTS:
            if self._file is not None:
                self._file.close()
            # 一時的な回線の不調に備えて、少し待ってからやり直す
            QTimer.singleShot(1500 * self._attempt, self._begin_attempt)
            return
        self._finish(error)

    def _finish(self, error: str | None) -> None:
        if self._file is not None:
            self._file.close()
        if error is None:
            try:
                os.replace(self._partial, self._destination)
            except OSError as exc:
                error = str(exc)
        if error is not None:
            self._partial.unlink(missing_ok=True)
        _running.discard(self)
        self.finished.emit(error or "")
        self.deleteLater()


def download_file(
    url: str,
    destination: Path,
    on_done: Callable[[str | None], None],
    on_progress: Callable[[float], None] | None = None,
    parent: QObject | None = None,
) -> FileDownload:
    task = FileDownload(url, destination, parent)
    task.finished.connect(lambda error: on_done(error or None))
    if on_progress is not None:
        task.progress.connect(on_progress)
    return task.start()
