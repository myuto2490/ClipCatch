"""yt-dlp をサブプロセスとして駆動し、進捗を構造化して返す。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal

from clipcatch.core import ytdlp
from clipcatch.core.i18n import tr
from clipcatch.core.models import DownloadResult
from clipcatch.services.process import LineSplitter, configure, stop_process_tree


class DownloadEngine(QObject):
    progress = Signal(object)  # ytdlp.ProgressEvent
    stage = Signal(str)
    log = Signal(str, object)  # (message, LogLevel)
    finished = Signal(object)  # list[DownloadResult]
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._parser = ytdlp.OutputParser()
        self._cancel_requested = False

    @property
    def is_running(self) -> bool:
        return self._process is not None

    def start(self, request: ytdlp.DownloadRequest, executable: Path) -> None:
        if self._process is not None:
            return
        self._parser = ytdlp.OutputParser()
        self._cancel_requested = False

        process = QProcess(self)
        configure(process, executable, ytdlp.download_arguments(request))
        process.setWorkingDirectory(str(request.output_directory))
        stdout = LineSplitter(self._handle_line)
        stderr = LineSplitter(self._handle_line)
        process.readyReadStandardOutput.connect(
            lambda: stdout.feed(bytes(process.readAllStandardOutput().data()))
        )
        process.readyReadStandardError.connect(
            lambda: stderr.feed(bytes(process.readAllStandardError().data()))
        )

        def finished(code: int, _status: QProcess.ExitStatus) -> None:
            stdout.feed(bytes(process.readAllStandardOutput().data()))
            stderr.feed(bytes(process.readAllStandardError().data()))
            stdout.flush()
            stderr.flush()
            self._finish(code)

        def error(kind: QProcess.ProcessError) -> None:
            if kind == QProcess.ProcessError.FailedToStart:
                self._cleanup()
                self.failed.emit(
                    tr(
                        f"yt-dlp を起動できませんでした: {process.errorString()}",
                        f"Couldn't start yt-dlp: {process.errorString()}",
                    )
                )

        process.finished.connect(finished)
        process.errorOccurred.connect(error)
        self._process = process
        process.start()

    def cancel(self) -> None:
        if self._process is None:
            return
        self._cancel_requested = True
        stop_process_tree(self._process)

    def _handle_line(self, line: str) -> None:
        for event in self._parser.feed(line):
            if isinstance(event, ytdlp.ProgressEvent):
                self.progress.emit(event)
            elif isinstance(event, ytdlp.StageEvent):
                self.stage.emit(event.label)
            elif isinstance(event, ytdlp.LogEvent):
                self.log.emit(event.message, event.level)

    def _finish(self, code: int) -> None:
        self._cleanup()
        if self._cancel_requested:
            self.cancelled.emit()
        elif code == 0:
            results = self._parser.results or [DownloadResult(title=tr("ダウンロード", "Download"))]
            self.finished.emit(results)
        else:
            self.failed.emit(
                self._parser.last_error
                or tr(
                    f"yt-dlp が終了コード {code} で終了しました。",
                    f"yt-dlp exited with code {code}.",
                )
            )

    def _cleanup(self) -> None:
        if self._process is not None:
            self._process.deleteLater()
            self._process = None
