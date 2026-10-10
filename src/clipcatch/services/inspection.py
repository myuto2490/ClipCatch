"""ダウンロード前のプレビュー取得と、ダウンロード後の整合性検査。"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject

from clipcatch.core import integrity, ytdlp
from clipcatch.core.i18n import tr
from clipcatch.core.models import MediaInfo
from clipcatch.services.process import ProcessOutput, ProcessTask, run_process


def fetch_metadata(
    url: str,
    executable: Path,
    on_done: Callable[[MediaInfo | None, str | None], None],
    allow_playlist: bool = False,
    js_runtime: Path | None = None,
    parent: QObject | None = None,
) -> ProcessTask:
    """`yt-dlp -J` で動画の情報だけを取得する。返した task は取り消しに使う。"""

    def done(output: ProcessOutput) -> None:
        if task.is_cancelled:
            return
        if output.error == "timeout":
            on_done(None, tr("応答がありませんでした。", "The site did not respond."))
            return
        if not output.succeeded:
            message = ytdlp.last_error_line(output.stderr) or output.error
            on_done(None, message or tr("動画の情報を取得できませんでした。", "No video found."))
            return
        try:
            on_done(ytdlp.parse_metadata(output.stdout), None)
        except (ValueError, TypeError):
            on_done(None, tr("動画の情報を読み取れませんでした。", "Couldn't read video info."))

    task = run_process(
        executable,
        ytdlp.metadata_arguments(url, allow_playlist, js_runtime),
        done,
        timeout_ms=60_000,
        parent=parent,
    )
    return task


def inspect_file(
    file: Path,
    ffprobe: Path,
    on_done: Callable[[integrity.IntegrityReport | None], None],
    parent: QObject | None = None,
) -> None:
    """映像トラックの長さとコンテナ全体の長さを比べる。判定できなければ None。"""

    def done(output: ProcessOutput) -> None:
        if not output.succeeded:
            on_done(None)
            return
        try:
            data = json.loads(output.stdout)
        except ValueError:
            on_done(None)
            return
        on_done(integrity.report_from_ffprobe(data) if isinstance(data, dict) else None)

    run_process(ffprobe, [*integrity.FFPROBE_ARGUMENTS, str(file)], done, 120_000, parent)
