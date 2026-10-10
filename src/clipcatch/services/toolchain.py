"""yt-dlp / ffmpeg / aria2c の在りかを解決し、無ければ公式配布物を取得する。

取得したものはアプリ本体ではなく `platform.tools_directory()` に置く。
（macOS の .app を書き換えると署名が壊れ、Windows の Program Files は
管理者権限が要るため）
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from clipcatch.core import sources, versions
from clipcatch.core.archive import extract_executables
from clipcatch.core.formatters import display_path
from clipcatch.core.i18n import tr
from clipcatch.core.models import LogLevel
from clipcatch.core.platform import (
    IS_MACOS,
    IS_WINDOWS,
    executable_name,
    find_on_system,
    is_executable,
    managed_tool,
    tools_directory,
)
from clipcatch.services import network
from clipcatch.services.background import run_in_background
from clipcatch.services.process import ProcessOutput, run_process


class ToolState(Enum):
    UNKNOWN = "unknown"
    CHECKING = "checking"
    MISSING = "missing"
    INSTALLING = "installing"
    READY = "ready"
    FAILED = "failed"

    @property
    def is_busy(self) -> bool:
        return self in (ToolState.CHECKING, ToolState.INSTALLING)


@dataclass(frozen=True)
class ToolStatus:
    state: ToolState = ToolState.UNKNOWN
    path: Path | None = None
    version: str | None = None
    progress: float | None = None
    message: str | None = None

    @property
    def ready(self) -> bool:
        return self.state is ToolState.READY and self.path is not None


def bundled_tool(name: str) -> Path | None:
    """配布物の `tools/` に同梱された実行ファイル（同梱版を作った場合だけ）。"""
    if not getattr(sys, "frozen", False):
        return None
    base = Path(sys.executable).resolve().parent
    candidates = [base / "tools", base.parent / "Resources" / "tools"]
    for directory in candidates:
        path = directory / executable_name(name)
        if is_executable(path):
            return path
    return None


def locate(name: str) -> Path | None:
    """アプリが取得したもの → 同梱 → システムの順に探す。"""
    for path in (managed_tool(name), bundled_tool(name)):
        if is_executable(path):
            return path
    return find_on_system(name)


def remove_quarantine(path: Path) -> None:
    """Gatekeeper の隔離属性を外す。付いたままだと起動時にブロックされる。"""
    if IS_MACOS:
        subprocess.run(
            ["/usr/bin/xattr", "-d", "com.apple.quarantine", str(path)],
            capture_output=True,
            check=False,
        )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Toolchain(QObject):
    changed = Signal()
    log = Signal(str, object)  # (message, LogLevel)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.ytdlp = ToolStatus()
        self.ffmpeg = ToolStatus()
        self.aria2c = ToolStatus()
        self.deno = ToolStatus()
        self.latest_ytdlp: str | None = None
        self._staging = tools_directory() / ".download"

    # MARK: - 状態

    @property
    def update_available(self) -> bool:
        if not self.latest_ytdlp or not self.ytdlp.version:
            return False
        return not versions.same(self.ytdlp.version, self.latest_ytdlp)

    @property
    def ffprobe_path(self) -> Path | None:
        """ffprobe は ffmpeg と同じ場所に入る。完成したファイルの検査に使う。"""
        if self.ffmpeg.path is not None:
            sibling = self.ffmpeg.path.with_name(executable_name("ffprobe"))
            if is_executable(sibling):
                return sibling
        return locate("ffprobe")

    @property
    def homebrew_path(self) -> Path | None:
        return find_on_system("brew") if IS_MACOS else None

    @property
    def can_install_aria2c(self) -> bool:
        return IS_WINDOWS or self.homebrew_path is not None

    def _set(self, tool: str, **changes) -> None:
        setattr(self, tool, replace(getattr(self, tool), **changes))
        self.changed.emit()

    def _log(self, message: str, level: LogLevel = LogLevel.INFO) -> None:
        self.log.emit(message, level)

    # MARK: - 起動時のセットアップ

    def bootstrap(self) -> None:
        self.resolve_ytdlp()
        self.check_ytdlp_update()
        self.ensure_ffmpeg()
        self.ensure_deno()
        self.resolve_aria2c()

    # MARK: - yt-dlp

    def resolve_ytdlp(self) -> None:
        """既にある yt-dlp を探し、無ければダウンロードする。"""
        self._set("ytdlp", state=ToolState.CHECKING, message=None)
        found = locate("yt-dlp")
        if found is None:
            self._install_ytdlp(tr("yt-dlp を取得しています…", "Downloading yt-dlp…"))
            return

        def done(version: str | None) -> None:
            if version is None:
                self._install_ytdlp(
                    tr(
                        "yt-dlp を実行できなかったため取得し直します…",
                        "yt-dlp could not run. Downloading it again…",
                    )
                )
                return
            self._set("ytdlp", state=ToolState.READY, path=found, version=version)
            self._log(
                tr(
                    f"yt-dlp {version} を使用します（{display_path(found)}）",
                    f"Using yt-dlp {version} ({display_path(found)})",
                ),
                LogLevel.DETAIL,
            )

        self._read_version(found, done)

    def update_ytdlp(self) -> None:
        """手動更新。最新でなければ入れ替える。"""
        if self.ytdlp.state.is_busy:
            return

        def checked() -> None:
            if self.ytdlp.ready and self.latest_ytdlp and not self.update_available:
                self._log(
                    tr(
                        f"yt-dlp はすでに最新です（{self.ytdlp.version}）。",
                        f"yt-dlp is already up to date ({self.ytdlp.version}).",
                    )
                )
                return
            self._install_ytdlp(tr("yt-dlp を更新しています…", "Updating yt-dlp…"))

        self.check_ytdlp_update(checked)

    def check_ytdlp_update(self, then: Callable[[], None] | None = None) -> None:
        def done(data: bytes | None, _error: str | None) -> None:
            tag = None
            if data:
                try:
                    tag = json.loads(data).get("tag_name")
                except (ValueError, AttributeError):
                    tag = None
            if isinstance(tag, str):
                self.latest_ytdlp = tag
                self.changed.emit()
                if self.update_available:
                    self._log(
                        tr(
                            f"yt-dlp の新しいバージョン {tag} が公開されています。",
                            f"A new version of yt-dlp ({tag}) is available.",
                        ),
                        LogLevel.WARNING,
                    )
            if then is not None:
                then()

        network.fetch(
            sources.YTDLP_RELEASE_API, done, headers={"Accept": "application/vnd.github+json"}
        )

    def _install_ytdlp(self, reason: str) -> None:
        self._log(reason)
        self._set("ytdlp", state=ToolState.INSTALLING, progress=None, message=None)
        url = sources.ytdlp_download_url()
        asset = url.rsplit("/", 1)[-1]
        self._staging.mkdir(parents=True, exist_ok=True)
        staged = self._staging / asset

        def fail(message: str) -> None:
            staged.unlink(missing_ok=True)
            # 以前のものが残っていれば使い続ける
            previous = self.ytdlp.path if self.ytdlp.version else None
            self._set(
                "ytdlp",
                state=ToolState.READY if previous else ToolState.FAILED,
                progress=None,
                message=message,
            )
            self._log(
                tr(
                    f"yt-dlp を取得できませんでした: {message}",
                    f"Couldn't download yt-dlp: {message}",
                ),
                LogLevel.ERROR,
            )

        def install() -> None:
            target = managed_tool("yt-dlp")
            try:
                os.replace(staged, target)
            except OSError as exc:
                fail(str(exc))
                return
            os.chmod(target, 0o755)
            remove_quarantine(target)

            def version_read(version: str | None) -> None:
                if version is None:
                    fail(tr("取得した yt-dlp を実行できませんでした。", "It could not be run."))
                    return
                self.latest_ytdlp = version
                self._set(
                    "ytdlp", state=ToolState.READY, path=target, version=version, progress=None
                )
                self._log(
                    tr(f"yt-dlp {version} を準備しました。", f"yt-dlp {version} is ready."),
                    LogLevel.SUCCESS,
                )

            self._read_version(target, version_read)

        def verify(checksums: bytes | None, error: str | None) -> None:
            expected = sources.parse_checksums(checksums.decode()).get(asset) if checksums else None
            if expected is None:
                fail(error or tr("チェックサムを確認できませんでした。", "Checksum unavailable."))
                return

            def compared(actual: str | None, exc: BaseException | None) -> None:
                if exc is not None:
                    fail(str(exc))
                elif actual != expected:
                    fail(tr("チェックサムが一致しません。", "Checksum mismatch."))
                else:
                    install()

            run_in_background(lambda: sha256(staged), compared)

        def downloaded(error: str | None) -> None:
            if error:
                fail(error)
            else:
                network.fetch(sources.ytdlp_checksums_url(), verify)

        network.download_file(
            url,
            staged,
            downloaded,
            on_progress=lambda value: self._set("ytdlp", progress=value),
            parent=self,
        )

    def _read_version(self, executable: Path, on_done: Callable[[str | None], None]) -> None:
        def done(output: ProcessOutput) -> None:
            text = output.stdout.strip().splitlines()
            on_done(text[-1].strip() if output.succeeded and text else None)

        # macOS 版の yt-dlp は初回起動時に自己展開するので時間に余裕を持たせる
        run_process(executable, ["--version"], done, timeout_ms=90_000, parent=self)

    # MARK: - ffmpeg

    def ensure_ffmpeg(self) -> None:
        """ffmpeg を探し、無ければ静的ビルドを取得する。"""
        if self.ffmpeg.state.is_busy:
            return
        found = locate("ffmpeg")
        if found is not None:
            self._set("ffmpeg", state=ToolState.READY, path=found, message=None)
            self._log(
                tr(
                    f"ffmpeg を検出しました（{display_path(found)}）",
                    f"Found ffmpeg ({display_path(found)})",
                ),
                LogLevel.DETAIL,
            )
            return
        self._log(
            tr(
                "ffmpeg が見つからないため取得します（映像と音声の結合・MP3 変換に必要）…",
                "ffmpeg not found. Downloading it (needed to merge video/audio and make MP3)…",
            )
        )
        self._set("ffmpeg", state=ToolState.INSTALLING, progress=None, message=None)
        self._try_ffmpeg_sources(sources.ffmpeg_sources(), [])

    def _try_ffmpeg_sources(
        self, alternatives: list[list[sources.ArchiveSource]], errors: list[str]
    ) -> None:
        if not alternatives:
            message = errors[-1] if errors else tr("不明なエラー", "Unknown error")
            self._set("ffmpeg", state=ToolState.FAILED, progress=None, message=message)
            self._log(
                tr(
                    f"ffmpeg を取得できませんでした: {message}",
                    f"Couldn't download ffmpeg: {message}",
                ),
                LogLevel.WARNING,
            )
            hint = (
                "brew install ffmpeg"
                if IS_MACOS
                else "winget install ffmpeg"
                if IS_WINDOWS
                else "apt install ffmpeg"
            )
            self._log(
                tr(f"手動で導入する場合: {hint}", f"To install it manually: {hint}"),
                LogLevel.DETAIL,
            )
            return

        current, rest = alternatives[0], alternatives[1:]

        def done(error: str | None) -> None:
            if error:
                self._try_ffmpeg_sources(rest, [*errors, error])
                return
            path = managed_tool("ffmpeg")
            self._set("ffmpeg", state=ToolState.READY, path=path, progress=None)
            self._log(tr("ffmpeg を準備しました。", "ffmpeg is ready."), LogLevel.SUCCESS)

        self._install_archives(current, "ffmpeg", done)

    def _install_archives(
        self,
        archives: list[sources.ArchiveSource],
        tool: str,
        on_done: Callable[[str | None], None],
        index: int = 0,
    ) -> None:
        """アーカイブを順にダウンロードし、中の実行ファイルを tools に取り出す。"""
        if index >= len(archives):
            on_done(None)
            return
        source = archives[index]
        span = 1 / len(archives)
        self._staging.mkdir(parents=True, exist_ok=True)
        staged = self._staging / f"{tool}-{index}{_archive_suffix(source.url)}"

        def extracted(_result, exc: BaseException | None) -> None:
            staged.unlink(missing_ok=True)
            if exc is not None:
                on_done(str(exc))
                return
            for name in source.members:
                remove_quarantine(tools_directory() / name)
            self._install_archives(archives, tool, on_done, index + 1)

        def extract() -> None:
            run_in_background(
                lambda: extract_executables(staged, list(source.members), tools_directory()),
                extracted,
            )

        def verify(checksums: bytes | None, error: str | None) -> None:
            text = checksums.decode("utf-8", "replace") if checksums else ""
            expected = sources.parse_checksums(text).get(source.asset_name)
            if expected is None:
                staged.unlink(missing_ok=True)
                on_done(
                    error or tr("チェックサムを確認できませんでした。", "Checksum unavailable.")
                )
                return

            def compared(actual: str | None, exc: BaseException | None) -> None:
                if exc is not None or actual != expected:
                    staged.unlink(missing_ok=True)
                    on_done(
                        str(exc)
                        if exc
                        else tr("チェックサムが一致しません。", "Checksum mismatch.")
                    )
                else:
                    extract()

            run_in_background(lambda: sha256(staged), compared)

        def downloaded(error: str | None) -> None:
            if error:
                on_done(error)
            elif source.checksum_url:
                network.fetch(source.checksum_url, verify)
            else:
                extract()

        network.download_file(
            source.url,
            staged,
            downloaded,
            on_progress=lambda value: self._set(tool, progress=(index + value) * span),
            parent=self,
        )

    # MARK: - Deno

    def ensure_deno(self) -> None:
        """YouTube の解析に要る JavaScript ランタイムを探し、無ければ取得する。

        yt-dlp は YouTube の署名を解くのに Deno を使う。無くても動くが、
        取れない形式が出てくる。
        """
        if self.deno.state.is_busy:
            return
        found = locate("deno")
        if found is not None:
            self._set("deno", state=ToolState.READY, path=found, message=None)
            self._log(
                tr(
                    f"Deno を検出しました（{display_path(found)}）",
                    f"Found Deno ({display_path(found)})",
                ),
                LogLevel.DETAIL,
            )
            return
        self._log(
            tr(
                "Deno を取得します（YouTube の解析に使います）…",
                "Downloading Deno (used by yt-dlp for YouTube)…",
            )
        )
        self._set("deno", state=ToolState.INSTALLING, progress=None, message=None)

        def done(error: str | None) -> None:
            if error:
                self._set("deno", state=ToolState.FAILED, progress=None, message=error)
                self._log(
                    tr(
                        f"Deno を取得できませんでした: {error}。"
                        "YouTube で一部の形式が取れない場合があります。",
                        f"Couldn't download Deno: {error}. Some YouTube formats may be missing.",
                    ),
                    LogLevel.WARNING,
                )
                return
            self._set("deno", state=ToolState.READY, path=managed_tool("deno"), progress=None)
            self._log(tr("Deno を準備しました。", "Deno is ready."), LogLevel.SUCCESS)

        self._install_archives([sources.deno_source()], "deno", done)

    # MARK: - aria2c（任意）

    def resolve_aria2c(self) -> None:
        """aria2c を探す。無くても動くので、見つからなくてもエラーにはしない。"""
        found = locate("aria2c")
        if found is None:
            self._set("aria2c", state=ToolState.MISSING, path=None)
            return
        self._set("aria2c", state=ToolState.READY, path=found, message=None)
        self._log(
            tr(
                f"aria2c を検出しました（{display_path(found)}）。多重接続で高速化します。",
                f"Found aria2c ({display_path(found)}). Downloads will use multiple connections.",
            ),
            LogLevel.DETAIL,
        )

    def install_aria2c(self) -> None:
        """macOS は Homebrew、Windows は公式リリースの zip から導入する。

        macOS 向けの公式な署名済みビルドは配布されていないため、素性の分かる
        Homebrew 経由に限る。
        """
        if self.aria2c.state.is_busy:
            return
        if IS_MACOS:
            self._install_aria2c_homebrew()
        elif IS_WINDOWS:
            self._install_aria2c_windows()

    def _aria2c_failed(self, message: str) -> None:
        self._set("aria2c", state=ToolState.FAILED, progress=None, message=message)
        self._log(
            tr(
                f"aria2c を導入できませんでした: {message}",
                f"Couldn't install aria2c: {message}",
            ),
            LogLevel.WARNING,
        )

    def _aria2c_installed(self) -> None:
        self.resolve_aria2c()
        if self.aria2c.ready:
            self._log(
                tr(
                    "aria2c を導入しました。次のダウンロードから高速化が有効になります。",
                    "aria2c is installed. Faster downloads apply from the next download.",
                ),
                LogLevel.SUCCESS,
            )
        else:
            self._aria2c_failed(tr("導入後も見つかりませんでした。", "Not found after install."))

    def _install_aria2c_homebrew(self) -> None:
        brew = self.homebrew_path
        if brew is None:
            self._log(
                tr(
                    "Homebrew が見つかりません。https://brew.sh から導入してください。",
                    "Homebrew not found. Install it from https://brew.sh first.",
                ),
                LogLevel.WARNING,
            )
            return
        self._log(
            tr(
                "Homebrew で aria2 を導入しています（数分かかることがあります）…",
                "Installing aria2 with Homebrew (this can take a few minutes)…",
            )
        )
        self._set("aria2c", state=ToolState.INSTALLING, progress=None, message=None)

        def done(output: ProcessOutput) -> None:
            for line in (output.stdout + "\n" + output.stderr).strip().splitlines()[-12:]:
                self._log(line, LogLevel.DETAIL)
            if output.succeeded:
                self._aria2c_installed()
            else:
                self._aria2c_failed("brew install aria2")

        run_process(brew, ["install", "aria2"], done, timeout_ms=900_000, parent=self)

    def _install_aria2c_windows(self) -> None:
        self._log(tr("aria2c を取得しています…", "Downloading aria2c…"))
        self._set("aria2c", state=ToolState.INSTALLING, progress=None, message=None)

        def release(data: bytes | None, error: str | None) -> None:
            try:
                assets = json.loads(data or b"{}").get("assets", [])
            except ValueError:
                assets = []
            url = next(
                (
                    a.get("browser_download_url")
                    for a in assets
                    if sources.aria2_asset_name_matches(str(a.get("name", "")))
                ),
                None,
            )
            if not url:
                self._aria2c_failed(error or tr("配布物が見つかりません。", "No asset found."))
                return
            archive = sources.ArchiveSource(url, (executable_name("aria2c"),))

            def done(install_error: str | None) -> None:
                if install_error:
                    self._aria2c_failed(install_error)
                else:
                    self._aria2c_installed()

            self._install_archives([archive], "aria2c", done)

        network.fetch(
            sources.ARIA2_RELEASE_API, release, headers={"Accept": "application/vnd.github+json"}
        )

    def cleanup_staging(self) -> None:
        shutil.rmtree(self._staging, ignore_errors=True)


def _archive_suffix(url: str) -> str:
    for suffix in (".tar.xz", ".zip"):
        if url.endswith(suffix):
            return suffix
    return ".zip"
