"""折りたためる実行ログ。既定では畳んでおき、必要なときだけ開く。"""

from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QTextEdit, QVBoxLayout, QWidget

from clipcatch.controller import LOG_LIMIT, AppController
from clipcatch.core.i18n import tr
from clipcatch.core.models import LogEntry, LogLevel
from clipcatch.ui import theme
from clipcatch.ui.widgets import ElidedLabel, label

_LEVEL_COLOR = {
    LogLevel.INFO: "label",
    LogLevel.DETAIL: "secondary",
    LogLevel.SUCCESS: "green",
    LogLevel.WARNING: "orange",
    LogLevel.ERROR: "red",
}
_LEVEL_MARK = {LogLevel.SUCCESS: "✓ ", LogLevel.WARNING: "⚠︎ ", LogLevel.ERROR: "✕ "}


class LogPanel(QWidget):
    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setObjectName("logPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.toggle = QPushButton(tr("ログ", "Log"))
        self.toggle.setObjectName("plain")
        self.toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle.clicked.connect(lambda: self.set_expanded(not self.expanded))
        font = self.toggle.font()
        font.setWeight(font.Weight.Medium)
        self.toggle.setFont(font)
        self.count = label("", "caption")
        self.latest = ElidedLabel("", Qt.TextElideMode.ElideMiddle)
        self.latest.setObjectName("caption")
        self.latest.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.clear = QPushButton(tr("消去", "Clear"))
        self.clear.setObjectName("plain")
        self.clear.clicked.connect(controller.clear_log)

        header = QHBoxLayout()
        header.setContentsMargins(14, 5, 16, 5)
        header.setSpacing(6)
        header.addWidget(self.toggle)
        header.addWidget(self.count)
        header.addSpacing(12)
        header.addWidget(self.latest, 1)
        header.addWidget(self.clear)

        self.view = QTextEdit()
        self.view.setObjectName("log")
        self.view.setReadOnly(True)
        self.view.document().setMaximumBlockCount(LOG_LIMIT)
        self.view.setFixedHeight(180)
        self.view.setUndoRedoEnabled(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addWidget(self.view)

        controller.log_appended.connect(self._append)
        controller.log_cleared.connect(self._cleared)
        theme.notifier().changed.connect(self._rerender)
        self.expanded = controller.settings.log_expanded
        self._apply_expanded()
        self._rerender()

    def set_expanded(self, expanded: bool) -> None:
        self.expanded = expanded
        self.controller.settings.log_expanded = expanded
        self._apply_expanded()

    def _apply_expanded(self) -> None:
        self.view.setVisible(self.expanded)
        self.clear.setVisible(self.expanded)
        # 最新行の欄は畳んだときだけ使うが、配置を保つため隠さずに空にする
        self._update_header()
        self._update_toggle_icon()
        self.toggle.setToolTip(
            tr("ログを隠す", "Hide log") if self.expanded else tr("ログを表示", "Show log")
        )
        if self.expanded:
            self.view.moveCursor(QTextCursor.MoveOperation.End)

    def _update_toggle_icon(self) -> None:
        name = "chevron.down" if self.expanded else "chevron.right"
        self.toggle.setIcon(theme.icon(name, theme.current().secondary, 12))
        self.toggle.setIconSize(theme.icon_size(12))

    def _line_html(self, entry: LogEntry) -> str:
        p = theme.current()
        color = getattr(p, _LEVEL_COLOR[entry.level])
        mark = _LEVEL_MARK.get(entry.level, "")
        text = html.escape(entry.message)
        return (
            f'<span style="color:{p.tertiary}">{entry.time_text}</span>&nbsp;&nbsp;'
            f'<span style="color:{color}">{mark}{text}</span>'
        )

    def _append(self, entry: LogEntry) -> None:
        scrollbar = self.view.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 4
        self.view.append(self._line_html(entry))
        if at_bottom:
            scrollbar.setValue(scrollbar.maximum())
        self._update_header()

    def _cleared(self) -> None:
        self.view.clear()
        self._update_header()

    def _rerender(self) -> None:
        """外観が変わったら色を付け直すため、全行を描き直す。"""
        self._update_toggle_icon()
        self.view.clear()
        for entry in self.controller.log:
            self.view.append(self._line_html(entry))
        self.view.moveCursor(QTextCursor.MoveOperation.End)
        self._update_header()

    def _update_header(self) -> None:
        log = self.controller.log
        self.count.setText(str(len(log)) if log else "")
        if not log:
            self.latest.setText("")
            return
        latest = log[-1]
        self.latest.setText("" if self.expanded else latest.message)
        p = theme.current()
        important = latest.level in (LogLevel.WARNING, LogLevel.ERROR)
        color = getattr(p, _LEVEL_COLOR[latest.level]) if important else p.secondary
        self.latest.setStyleSheet(f"color: {color};")
