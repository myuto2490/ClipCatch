"""画面全体の状態と操作をまとめる。ビューはここだけを見る。"""

from __future__ import annotations

from collections import deque
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from clipcatch import APP_NAME, __version__
from clipcatch.core import formatters, ytdlp
from clipcatch.core.i18n import tr
from clipcatch.core.integrity import IntegrityReport
from clipcatch.core.models import (
    DownloadResult,
    LogEntry,
    LogLevel,
    MediaInfo,
    Phase,
    TransferProgress,
)
from clipcatch.services import system, updates
from clipcatch.services.engine import DownloadEngine
from clipcatch.services.inspection import fetch_metadata, inspect_file
from clipcatch.services.process import ProcessTask
from clipcatch.services.settings import Settings
from clipcatch.services.toolchain import Toolchain

LOG_LIMIT = 500
METADATA_DELAY_MS = 600


class AppController(QObject):
    changed = Signal()  # 画面の状態が変わった
    metadata_changed = Signal()
    log_appended = Signal(object)  # LogEntry
    log_cleared = Signal()
    alert = Signal(str, str)  # (title, message)
    notify = Signal(str, str)  # (title, message) 背面にいるときの完了通知
    app_update_available = Signal(object)  # updates.AppRelease

    def __init__(self, settings: Settings | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.settings = settings or Settings(parent=self)
        self.toolchain = Toolchain(self)
        self.toolchain.log.connect(self.append_log)
        self.toolchain.changed.connect(self._on_toolchain_changed)

        self.url_text = ""
        self.phase = Phase.IDLE
        self.progress = TransferProgress()
        self.status_text = tr("待機中", "Ready")
        self.media_info: MediaInfo | None = None
        self.is_loading_metadata = False
        self.metadata_error: str | None = None
        self.last_saved_file: Path | None = None
        self.playlist_position: tuple[int, int] | None = None
        self.log: deque[LogEntry] = deque(maxlen=LOG_LIMIT)
        self._last_auto_pasted: str | None = None
        self._metadata_task: ProcessTask | None = None

        self._metadata_timer = QTimer(self)
        self._metadata_timer.setSingleShot(True)
        self._metadata_timer.setInterval(METADATA_DELAY_MS)
        self._metadata_timer.timeout.connect(self._fetch_metadata)

        self.engine = DownloadEngine(self)
        self.engine.progress.connect(self._on_progress)
        self.engine.stage.connect(self._on_stage)
        self.engine.log.connect(self.append_log)
        self.engine.finished.connect(self._on_finished)
        self.engine.failed.connect(self._on_failed)
        self.engine.cancelled.connect(self._on_cancelled)

        self.settings.changed.connect(self._on_setting_changed)

    # MARK: - 起動

    def bootstrap(self) -> None:
        self.append_log(f"{APP_NAME} {__version__}", LogLevel.DETAIL)
        self.toolchain.bootstrap()
        if self.settings.check_for_app_updates:
            updates.check_for_update(self._on_app_update)

    def _on_app_update(self, release: updates.AppRelease) -> None:
        self.append_log(
            tr(
                f"{APP_NAME} の新しいバージョン {release.version} が公開されています。",
                f"{APP_NAME} {release.version} is available.",
            ),
            LogLevel.WARNING,
        )
        self.app_update_available.emit(release)

    # MARK: - 状態

    @property
    def has_valid_url(self) -> bool:
        return system.is_web_url(self.url_text)

    @property
    def can_start_download(self) -> bool:
        return self.has_valid_url and not self.phase.is_busy and self.toolchain.ytdlp.ready

    @property
    def progress_fraction(self) -> float | None:
        """プログレスバーに渡す値。None なら不確定表示にする。"""
        if self.phase is Phase.FINISHED:
            return 1.0
        if self.phase in (Phase.IDLE, Phase.CANCELLED, Phase.FAILED):
            return 0.0
        if self.phase is Phase.DOWNLOADING:
            return self.progress.fraction
        return None

    # MARK: - ログ

    def append_log(self, message: str, level: LogLevel = LogLevel.INFO) -> None:
        entry = LogEntry(message, level)
        self.log.append(entry)
        self.log_appended.emit(entry)

    def clear_log(self) -> None:
        self.log.clear()
        self.log_cleared.emit()

    # MARK: - URL

    def set_url(self, text: str) -> None:
        if text == self.url_text:
            return
        self.url_text = text
        self._schedule_metadata_lookup()
        self.changed.emit()

    def auto_paste_if_appropriate(self) -> bool:
        """アプリが前面に来たとき、クリップボードの URL を入力欄に入れる。"""
        if not self.settings.auto_paste_url or self.url_text or self.phase.is_busy:
            return False
        clipboard = system.clipboard_text()
        if clipboard == self._last_auto_pasted or not system.is_web_url(clipboard):
            return False
        self._last_auto_pasted = clipboard
        self.set_url(clipboard)
        return True

    def paste_from_clipboard(self) -> None:
        clipboard = system.clipboard_text()
        if not clipboard:
            self.alert.emit(
                tr("クリップボードが空です", "The clipboard is empty"),
                tr("コピーした URL が見つかりませんでした。", "Copy a video URL and try again."),
            )
            return
        self.set_url(clipboard)

    def clear_url(self) -> None:
        self.set_url("")

    def _cancel_metadata(self) -> None:
        self._metadata_timer.stop()
        if self._metadata_task is not None:
            self._metadata_task.cancel()
            self._metadata_task = None

    def _schedule_metadata_lookup(self) -> None:
        """入力が落ち着いてから 1 回だけ動画情報を取りに行く。"""
        self._cancel_metadata()
        self.media_info = None
        self.metadata_error = None
        self.is_loading_metadata = self.has_valid_url and self.toolchain.ytdlp.ready
        if self.is_loading_metadata:
            self._metadata_timer.start()
        self.metadata_changed.emit()

    def _fetch_metadata(self) -> None:
        executable = self.toolchain.ytdlp.path
        if executable is None or not self.has_valid_url:
            self.is_loading_metadata = False
            self.metadata_changed.emit()
            return
        target = self.url_text.strip()

        def done(info: MediaInfo | None, error: str | None) -> None:
            if target != self.url_text.strip():
                return  # 結果が届く前に URL が変わった
            self._metadata_task = None
            self.is_loading_metadata = False
            self.media_info = info
            self.metadata_error = error
            self.metadata_changed.emit()

        self._metadata_task = fetch_metadata(
            target,
            executable,
            done,
            allow_playlist=self.settings.allow_playlist,
            js_runtime=self.toolchain.deno.path if self.toolchain.deno.ready else None,
            parent=self,
        )

    def _on_setting_changed(self, key: str) -> None:
        if key == "allowPlaylist" and self.url_text:
            self._schedule_metadata_lookup()
        self.changed.emit()

    def _on_toolchain_changed(self) -> None:
        # yt-dlp の準備が整う前に入力された URL のプレビューを取り直す
        if (
            self.toolchain.ytdlp.ready
            and self.has_valid_url
            and self.media_info is None
            and self.metadata_error is None
            and not self.is_loading_metadata
        ):
            self._schedule_metadata_lookup()
        self.changed.emit()

    # MARK: - 保存先

    def set_output_directory(self, path: Path) -> None:
        self.settings.output_directory = path

    def reveal_output(self) -> None:
        """直前に保存したファイルがあればそれを、無ければ保存先フォルダを開く。"""
        if self.last_saved_file and system.reveal_file(self.last_saved_file):
            return
        directory = self.settings.output_directory
        if not directory.exists():
            self.alert.emit(tr("フォルダが見つかりません", "Folder not found"), str(directory))
            return
        system.open_folder(directory)

    # MARK: - ダウンロード

    def start_download(self) -> None:
        if self.phase.is_busy:
            return
        executable = self.toolchain.ytdlp.path
        if not self.toolchain.ytdlp.ready or executable is None:
            self.alert.emit(
                tr("yt-dlp を準備できていません", "yt-dlp isn't ready"),
                tr(
                    "右上のツールメニューから取得し直してください。",
                    "Use the tools menu in the top-right corner to download it again.",
                ),
            )
            return
        if not self.has_valid_url:
            self.alert.emit(
                tr("URL を確認してください", "Check the URL"),
                tr(
                    "http:// または https:// で始まる URL を入力してください。",
                    "Enter a URL that starts with http:// or https://.",
                ),
            )
            return
        target = self.url_text.strip()
        settings = self.settings
        output = settings.output_directory
        try:
            output.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.alert.emit(tr("保存先を作成できません", "Can't create the folder"), str(exc))
            return

        if settings.format.requires_ffmpeg and not self.toolchain.ffmpeg.ready:
            self.append_log(
                tr(
                    "ffmpeg なしで続行します。結合や MP3 変換に失敗する場合があります。",
                    "Continuing without ffmpeg. Merging or MP3 conversion may fail.",
                ),
                LogLevel.WARNING,
            )

        aria2c = self.toolchain.aria2c.path if settings.accelerate_with_aria2c else None
        if aria2c is not None:
            self.append_log(
                tr(
                    "aria2c で多重接続ダウンロードします。",
                    "Using aria2c with multiple connections.",
                ),
                LogLevel.DETAIL,
            )
        elif settings.accelerate_with_aria2c and ytdlp.is_single_stream_site(target):
            self.append_log(
                tr(
                    "このサイトは 1 本の接続でしか取得できず、時間がかかることがあります。"
                    "aria2c を入れると多重接続で高速化できます。",
                    "This site serves a single stream and may be slow. "
                    "Installing aria2c lets ClipCatch use multiple connections.",
                ),
                LogLevel.WARNING,
            )

        self.last_saved_file = None
        self.playlist_position = None
        self.progress = TransferProgress()
        self.phase = Phase.PREPARING
        self.status_text = tr("動画情報を取得中…", "Fetching video info…")
        self.append_log(tr(f"開始: {target}", f"Start: {target}"), LogLevel.DETAIL)
        self.changed.emit()

        request = ytdlp.DownloadRequest(
            url=target,
            output_directory=output,
            format=settings.format,
            quality=settings.quality,
            ffmpeg=self.toolchain.ffmpeg.path if self.toolchain.ffmpeg.ready else None,
            aria2c=aria2c,
            cookie_browser=settings.cookie_browser,
            use_user_config=settings.use_user_config,
            allow_playlist=settings.allow_playlist,
            js_runtime=self.toolchain.deno.path if self.toolchain.deno.ready else None,
        )
        self.engine.start(request, executable)

    def cancel_download(self) -> None:
        if not self.phase.is_busy:
            return
        self.append_log(tr("キャンセルしています…", "Cancelling…"), LogLevel.WARNING)
        self.engine.cancel()

    def _on_progress(self, event: ytdlp.ProgressEvent) -> None:
        self.progress = event.progress
        if event.playlist_index and event.playlist_count and event.playlist_count > 1:
            self.playlist_position = (event.playlist_index, event.playlist_count)
        self.phase = Phase.DOWNLOADING
        self.status_text = event.progress.file_name or tr("ダウンロード中…", "Downloading…")
        self.changed.emit()

    def _on_stage(self, label: str) -> None:
        self.phase = Phase.PROCESSING
        self.status_text = label
        self.changed.emit()

    def _on_finished(self, results: list[DownloadResult]) -> None:
        self.phase = Phase.FINISHED
        self.progress.fraction = 1.0
        self.status_text = tr("完了", "Done")
        for result in results:
            self.append_log(tr(f"完了: {result.title}", f"Done: {result.title}"), LogLevel.SUCCESS)
            details = []
            if result.resolution:
                details.append(tr(f"解像度 {result.resolution}", f"Resolution {result.resolution}"))
            if result.video_codec and result.video_codec != "none":
                details.append(
                    tr(f"コーデック {result.video_codec}", f"Codec {result.video_codec}")
                )
            if details:
                self.append_log("  ·  ".join(details), LogLevel.DETAIL)
            if result.file_path:
                path = Path(result.file_path)
                self.last_saved_file = path
                self.append_log(tr(f"保存先: {path}", f"Saved to: {path}"), LogLevel.DETAIL)
                self._verify_integrity(path)
        self.changed.emit()

        title = (
            results[-1].title
            if len(results) == 1
            else tr(f"{len(results)} 件", f"{len(results)} items")
        )
        self.notify.emit(tr("ダウンロードが完了しました", "Download complete"), title)
        if self.settings.reveal_when_done:
            self.reveal_output()

    def _on_failed(self, message: str) -> None:
        self.phase = Phase.FAILED
        self.progress = TransferProgress()
        self.status_text = tr("エラー", "Error")
        self.append_log(message, LogLevel.ERROR)
        self.append_log(
            tr(
                "URL が正しいか、動画が公開されているか確認してください。",
                "Check that the URL is correct and the video is publicly available.",
            ),
            LogLevel.DETAIL,
        )
        self.changed.emit()
        self.notify.emit(tr("ダウンロードできませんでした", "Download failed"), message)

    def _on_cancelled(self) -> None:
        self.phase = Phase.CANCELLED
        self.progress = TransferProgress()
        self.status_text = tr("キャンセルしました", "Cancelled")
        self.append_log(
            tr("ダウンロードをキャンセルしました。", "Download cancelled."), LogLevel.WARNING
        )
        self.changed.emit()

    def _verify_integrity(self, file: Path) -> None:
        """完成したファイルの映像が途中で尽きていないか確かめ、おかしければ知らせる。

        取りこぼしを黙って渡すと、再生して初めて気づくことになるため。
        """
        ffprobe = self.toolchain.ffprobe_path
        if self.settings.format.is_audio_only or ffprobe is None or not file.exists():
            return

        def done(report: IntegrityReport | None) -> None:
            if report is None or not report.is_truncated:
                return
            total = formatters.duration(report.container_duration)
            video = formatters.duration(report.video_duration)
            percent = int(report.coverage * 100)
            self.append_log(
                tr(
                    f"⚠️ 映像が途中で終わっています（全体 {total} のうち映像は {video} ＝ 約"
                    f"{percent}%）。この先は音声だけで真っ黒になります。",
                    f"⚠️ The video track ends early ({video} of {total}, about {percent}%). "
                    "The rest will be black with audio only.",
                ),
                LogLevel.ERROR,
            )
            self.append_log(
                tr(
                    "ダウンロードし直してください。続くようなら設定で"
                    "「aria2c で高速ダウンロード」を切って試してください。",
                    "Please download it again. If it keeps happening, turn off "
                    '"Faster downloads with aria2c" in Settings.',
                ),
                LogLevel.WARNING,
            )

        inspect_file(file, ffprobe, done, parent=self)
