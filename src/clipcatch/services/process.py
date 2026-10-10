"""外部プロセス（yt-dlp・ffprobe など）の起動と出力の受け取り。

QProcess を使い、イベントループを止めずに結果をシグナルで返す。
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from clipcatch.core.platform import IS_WINDOWS, process_environment


def make_environment() -> QProcessEnvironment:
    env = QProcessEnvironment()
    for key, value in process_environment().items():
        env.insert(key, value)
    return env


def configure(process: QProcess, program: Path, arguments: list[str]) -> None:
    process.setProgram(str(program))
    process.setArguments(arguments)
    process.setProcessEnvironment(make_environment())
    process.setStandardInputFile(QProcess.nullDevice())


def stop_process_tree(process: QProcess) -> None:
    """プロセスを子プロセスごと止める。

    Windows の QProcess.terminate() は WM_CLOSE を送るだけで、コンソールアプリの
    yt-dlp には届かない。yt-dlp が起動した ffmpeg / aria2c も残るので、
    taskkill /T でまとめて止める。macOS では SIGTERM を送れば yt-dlp が
    中間ファイルを片付けて子プロセスも止める。
    """
    if process.state() == QProcess.ProcessState.NotRunning:
        return
    if IS_WINDOWS:
        pid = process.processId()
        if pid:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
        return
    process.terminate()
    # 応答が無ければ強制終了する
    QTimer.singleShot(5000, lambda: _kill_if_running(process))


def _kill_if_running(process: QProcess) -> None:
    try:
        if process.state() != QProcess.ProcessState.NotRunning:
            process.kill()
    except RuntimeError:  # QProcess が既に破棄されている
        pass


class LineSplitter:
    """断片的に届くパイプのデータを 1 行ずつに組み立てる。

    yt-dlp や aria2c は進捗を `\\r` で送ることがあるため、`\\n` と `\\r` の
    どちらも区切りとして扱う。
    """

    def __init__(self, on_line: Callable[[str], None]) -> None:
        self._buffer = bytearray()
        self._on_line = on_line

    def feed(self, data: bytes) -> None:
        self._buffer.extend(data)
        while True:
            indexes = [i for i in (self._buffer.find(b"\n"), self._buffer.find(b"\r")) if i >= 0]
            if not indexes:
                return
            index = min(indexes)
            line = bytes(self._buffer[:index])
            del self._buffer[: index + 1]
            self._emit(line)

    def flush(self) -> None:
        if self._buffer:
            line = bytes(self._buffer)
            self._buffer.clear()
            self._emit(line)

    def _emit(self, data: bytes) -> None:
        text = data.decode("utf-8", errors="replace").strip()
        if text:
            self._on_line(text)


@dataclass(frozen=True)
class ProcessOutput:
    status: int
    stdout: str
    stderr: str
    error: str | None = None  # 起動できなかった・時間切れなど

    @property
    def succeeded(self) -> bool:
        return self.error is None and self.status == 0


# 実行中のタスク。親を持たないタスクが途中で GC に回収されないよう参照を保つ。
_running: set[ProcessTask] = set()


class ProcessTask(QObject):
    """プロセスを最後まで走らせ、出力をまとめて `finished` で返す。"""

    finished = Signal(object)  # ProcessOutput

    def __init__(
        self,
        program: Path,
        arguments: list[str],
        timeout_ms: int = 120_000,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._process = QProcess(self)
        configure(self._process, program, arguments)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(timeout_ms)
        self._timer.timeout.connect(self._on_timeout)
        self._timed_out = False
        self._cancelled = False
        self._done = False
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

    def start(self) -> ProcessTask:
        _running.add(self)
        self._timer.start()
        self._process.start()
        return self

    def cancel(self) -> None:
        self._cancelled = True
        stop_process_tree(self._process)

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def _on_timeout(self) -> None:
        self._timed_out = True
        stop_process_tree(self._process)

    def _on_error(self, error: QProcess.ProcessError) -> None:
        # 起動に失敗したときは finished が来ないので、ここで終わらせる
        if error == QProcess.ProcessError.FailedToStart:
            self._finish(ProcessOutput(-1, "", "", self._process.errorString()))

    def _on_finished(self, code: int, _status: QProcess.ExitStatus) -> None:
        stdout = bytes(self._process.readAllStandardOutput().data()).decode("utf-8", "replace")
        stderr = bytes(self._process.readAllStandardError().data()).decode("utf-8", "replace")
        error = "timeout" if self._timed_out else None
        self._finish(ProcessOutput(code, stdout, stderr, error))

    def _finish(self, output: ProcessOutput) -> None:
        if self._done:
            return
        self._done = True
        self._timer.stop()
        _running.discard(self)
        self.finished.emit(output)
        self.deleteLater()


def run_process(
    program: Path,
    arguments: list[str],
    on_done: Callable[[ProcessOutput], None],
    timeout_ms: int = 120_000,
    parent: QObject | None = None,
) -> ProcessTask:
    task = ProcessTask(program, arguments, timeout_ms, parent)
    task.finished.connect(on_done)
    return task.start()
