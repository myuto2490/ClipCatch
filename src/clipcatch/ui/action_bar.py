"""ウィンドウ下端の固定バー。進行状況と主ボタンを常に同じ場所に置く。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from clipcatch.controller import AppController
from clipcatch.core.i18n import tr
from clipcatch.core.models import Phase
from clipcatch.core.platform import IS_MACOS
from clipcatch.ui import theme
from clipcatch.ui.widgets import ElidedLabel, IconLabel, ProgressLine, Spinner

_TINT = {
    Phase.FINISHED: "green",
    Phase.FAILED: "red",
    Phase.CANCELLED: "orange",
}
_SYMBOL = {
    Phase.FINISHED: "checkmark.circle.fill",
    Phase.FAILED: "exclamationmark.triangle.fill",
    Phase.CANCELLED: "minus.circle.fill",
}


class ActionBar(QWidget):
    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setObjectName("actionBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.progress = ProgressLine()
        self.spinner = Spinner(14)
        self.symbol = IconLabel("checkmark.circle.fill", "green", 16)
        self.status = ElidedLabel("", Qt.TextElideMode.ElideMiddle)
        self.detail = ElidedLabel("")
        self.detail.setObjectName("caption")
        font = self.detail.font()
        font.setStyleHint(font.StyleHint.Monospace)
        self.detail.setFont(font)

        self.cancel = QPushButton(tr("キャンセル", "Cancel"))
        self.cancel.setObjectName("large")
        self.cancel.clicked.connect(controller.cancel_download)
        self.cancel.setToolTip(tr("ダウンロードを中止します", "Stop the download"))

        self.start = QPushButton(tr("ダウンロード", "Download"))
        self.start.setObjectName("primary")
        self.start.setDefault(True)
        self.start.clicked.connect(controller.start_download)
        theme.bind_icon(self.start, "arrow.down.to.line", "on_accent", 16)

        status_row = QHBoxLayout()
        status_row.setSpacing(7)
        status_row.addWidget(self.spinner)
        status_row.addWidget(self.symbol)
        status_row.addWidget(self.status, 1)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        texts.addLayout(status_row)
        texts.addWidget(self.detail)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addLayout(texts, 1)
        row.addWidget(self.cancel)
        row.addWidget(self.start)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 14)
        layout.setSpacing(10)
        layout.addWidget(self.progress)
        layout.addLayout(row)

        controller.changed.connect(self.refresh)
        theme.notifier().changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        c = self.controller
        phase = c.phase
        busy = phase.is_busy

        self.progress.setVisible(phase is not Phase.IDLE)
        self.progress.set_value(c.progress_fraction, _TINT.get(phase, "accent"))

        self.spinner.setVisible(busy)
        symbol = _SYMBOL.get(phase)
        self.symbol.setVisible(symbol is not None)
        if symbol:
            self.symbol.set_icon(symbol, _TINT[phase])

        self.status.setText(self._status_text())
        self.status.setObjectName("" if phase is not Phase.IDLE else "secondary")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        detail = c.progress.detail_text if busy else ""
        self.detail.setVisible(bool(detail))
        self.detail.setText(detail)

        self.cancel.setVisible(busy)
        self.start.setText(
            tr("ダウンロード中…", "Downloading…") if busy else tr("ダウンロード", "Download")
        )
        self.start.setEnabled(c.can_start_download)
        if not c.toolchain.ytdlp.ready and not busy:
            self.start.setToolTip(tr("yt-dlp を準備しています…", "Preparing yt-dlp…"))
        else:
            self.start.setToolTip("⌘↩" if IS_MACOS else "Ctrl+Enter")

    def _status_text(self) -> str:
        c = self.controller
        text = c.status_text
        if c.phase is Phase.IDLE and not c.toolchain.ytdlp.ready:
            state = c.toolchain.ytdlp
            if state.progress is not None:
                return tr(
                    f"yt-dlp を準備中… {state.progress:.0%}",
                    f"Preparing yt-dlp… {state.progress:.0%}",
                )
            return tr("yt-dlp を準備中…", "Preparing yt-dlp…")
        if c.phase is Phase.DOWNLOADING and c.progress.fraction is not None:
            text = f"{c.progress.fraction * 100:.1f}%  ·  {text}"
        if c.playlist_position and c.phase.is_busy:
            index, count = c.playlist_position
            text = f"[{index}/{count}]  {text}"
        return text
