"""ウィンドウ右上のツールメニュー。yt-dlp などの状態を示し、更新操作をまとめる。"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QToolButton, QWidget

from clipcatch.controller import AppController
from clipcatch.core.formatters import display_path
from clipcatch.core.i18n import tr
from clipcatch.core.platform import IS_MACOS
from clipcatch.services.toolchain import ToolState, ToolStatus
from clipcatch.ui import theme


def styled_menu(parent: QWidget | None = None) -> QMenu:
    """角の丸いメニュー。四隅に背景色が残らないよう、窓を透過させる。"""
    menu = QMenu(parent)
    menu.setWindowFlags(
        menu.windowFlags()
        | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.NoDropShadowWindowHint
    )
    menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    return menu


def describe(status: ToolStatus, missing: str) -> str:
    match status.state:
        case ToolState.READY:
            parts = [status.version] if status.version else []
            if status.path:
                parts.append(display_path(status.path))
            return "  ·  ".join(parts) or tr("利用できます", "Available")
        case ToolState.INSTALLING:
            if status.progress is not None:
                return tr(f"取得中… {status.progress:.0%}", f"Downloading… {status.progress:.0%}")
            return tr("取得中…", "Downloading…")
        case ToolState.CHECKING | ToolState.UNKNOWN:
            return tr("確認しています…", "Checking…")
        case ToolState.MISSING:
            return missing
        case ToolState.FAILED:
            return status.message or tr("失敗しました", "Failed")
    return ""


class ToolsButton(QToolButton):
    def __init__(
        self,
        controller: AppController,
        open_settings: Callable[[], None],
        open_about: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self._open_settings = open_settings
        self._open_about = open_about
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tr("yt-dlp と関連ツールの状態", "Status of yt-dlp and helper tools"))
        self.menu_ = styled_menu(self)
        self.menu_.aboutToShow.connect(self._rebuild)
        self.setMenu(self.menu_)
        controller.toolchain.changed.connect(self.refresh)
        theme.notifier().changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        tc = self.controller.toolchain
        state = tc.ytdlp.state
        if state is ToolState.READY:
            if tc.update_available:
                text, symbol, color = tr("更新あり", "Update"), "arrow.down.circle.fill", "orange"
            else:
                text, symbol, color = (
                    f"yt-dlp {tc.ytdlp.version or ''}",
                    "checkmark.seal",
                    "secondary",
                )
        elif state in (ToolState.FAILED, ToolState.MISSING):
            text, symbol, color = (
                tr("取得に失敗", "Setup failed"),
                "exclamationmark.triangle.fill",
                "red",
            )
        elif state is ToolState.INSTALLING and tc.ytdlp.progress is not None:
            text = tr(f"取得中 {tc.ytdlp.progress:.0%}", f"Downloading {tc.ytdlp.progress:.0%}")
            symbol, color = "arrow.clockwise", "secondary"
        else:
            text, symbol, color = tr("確認中…", "Checking…"), "arrow.clockwise", "secondary"
        p = theme.current()
        self.setText(text)
        self.setIcon(theme.icon(symbol, getattr(p, color), 16))
        self.setStyleSheet(f"QToolButton {{ color: {getattr(p, color)}; }}")

    def _section(self, title: str) -> None:
        self.menu_.addSection(title)

    def _info(self, text: str) -> None:
        action = QAction(text, self.menu_)
        action.setEnabled(False)
        self.menu_.addAction(action)

    def _rebuild(self) -> None:
        c = self.controller
        tc = c.toolchain
        menu = self.menu_
        menu.clear()

        self._section("yt-dlp")
        ytdlp_text = describe(tc.ytdlp, tr("見つかりません", "Not found"))
        if tc.update_available and tc.latest_ytdlp:
            ytdlp_text += tr(f"（最新は {tc.latest_ytdlp}）", f" (latest: {tc.latest_ytdlp})")
        self._info(ytdlp_text)
        update = menu.addAction(tr("最新版に更新", "Update to the Latest Version"))
        update.setEnabled(not tc.ytdlp.state.is_busy and not c.phase.is_busy)
        update.triggered.connect(tc.update_ytdlp)

        self._section("ffmpeg")
        self._info(describe(tc.ffmpeg, tr("見つかりません", "Not found")))
        retry = menu.addAction(tr("再確認して取得", "Check Again"))
        retry.setEnabled(not tc.ffmpeg.state.is_busy and not tc.ffmpeg.ready)
        retry.triggered.connect(tc.ensure_ffmpeg)

        self._section(tr("Deno（YouTube の解析）", "Deno (for YouTube)"))
        self._info(describe(tc.deno, tr("見つかりません", "Not found")))
        if not tc.deno.ready:
            deno = menu.addAction(tr("再確認して取得", "Check Again"))
            deno.setEnabled(not tc.deno.state.is_busy)
            deno.triggered.connect(tc.ensure_deno)

        self._section(tr("aria2c（高速化・任意）", "aria2c (optional, faster)"))
        self._info(describe(tc.aria2c, tr("未導入（内蔵ダウンローダを使います）", "Not installed")))
        if not tc.aria2c.ready and tc.can_install_aria2c:
            label = (
                tr("Homebrew で導入", "Install with Homebrew")
                if IS_MACOS
                else tr("導入", "Install")
            )
            install = menu.addAction(label)
            install.setEnabled(not tc.aria2c.state.is_busy)
            install.triggered.connect(tc.install_aria2c)

        menu.addSeparator()
        menu.addAction(tr("保存先を開く", "Open Save Folder"), c.reveal_output)
        menu.addSeparator()
        menu.addAction(tr("設定…", "Settings…"), self._open_settings)
        menu.addAction(tr("ClipCatch について", "About ClipCatch"), self._open_about)
