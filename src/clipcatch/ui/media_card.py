"""URL を入力すると `yt-dlp -J` で取れた情報をカードで見せる。

「これから何を保存するのか」をボタンを押す前に確認できるようにするための表示。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from clipcatch.controller import AppController
from clipcatch.core.i18n import tr
from clipcatch.core.models import MediaInfo
from clipcatch.services import network
from clipcatch.ui.widgets import Badge, IconLabel, Spinner, Thumbnail


class TwoLineLabel(QLabel):
    """2 行に収まらない分を「…」で省略する見出し。"""

    def __init__(self) -> None:
        super().__init__()
        self._full = ""
        self.setObjectName("title")
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

    def set_full_text(self, text: str) -> None:
        self._full = text
        self.setToolTip(text)
        self._update()

    def _two_lines(self, metrics: QFontMetrics) -> bool:
        return metrics.horizontalAdvance(self._full) > max(self.width(), 50)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update()

    def _update(self) -> None:
        metrics = QFontMetrics(self.font())
        self.setFixedHeight(metrics.lineSpacing() * (2 if self._two_lines(metrics) else 1) + 2)
        width = max(self.width(), 50)
        # 2 行分の幅から少し引いて、折り返し位置のずれを吸収する
        text = metrics.elidedText(self._full, Qt.TextElideMode.ElideRight, width * 2 - 24)
        super().setText(text)


class MediaCard(QWidget):
    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self._thumbnail_url: str | None = None

        self.thumbnail = Thumbnail(144, 81)
        self.title = TwoLineLabel()
        self.subtitle = QLabel()
        self.subtitle.setObjectName("secondary")
        self.badges = QHBoxLayout()
        self.badges.setSpacing(6)
        self.badges.setContentsMargins(0, 2, 0, 0)

        self.spinner = Spinner(14)
        self.status_icon = IconLabel("exclamationmark.triangle.fill", "orange", 16)
        self.status = QLabel()
        self.status.setObjectName("secondary")
        self.status.setWordWrap(True)
        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        status_row.addWidget(self.spinner)
        status_row.addWidget(self.status_icon, 0, Qt.AlignmentFlag.AlignTop)
        status_row.addWidget(self.status, 1)

        text = QVBoxLayout()
        text.setSpacing(3)
        text.addWidget(self.title)
        text.addWidget(self.subtitle)
        text.addLayout(status_row)
        text.addLayout(self.badges)
        text.addStretch()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 14, 12)
        layout.setSpacing(14)
        layout.addWidget(self.thumbnail, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text, 1)

        # 進捗のたびに作り直さないよう、動画情報が変わったときだけ更新する
        controller.metadata_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        c = self.controller
        info = c.media_info
        visible = bool(c.url_text.strip()) and (
            c.is_loading_metadata or info is not None or c.metadata_error is not None
        )
        self.setVisible(visible)
        if not visible:
            self._set_thumbnail_url(None)
            return

        self.spinner.setVisible(c.is_loading_metadata)
        self.status_icon.setVisible(c.metadata_error is not None and not c.is_loading_metadata)
        self.thumbnail.set_loading(c.is_loading_metadata)

        if c.is_loading_metadata:
            self.title.setVisible(False)
            self.subtitle.setVisible(False)
            self.status.setVisible(True)
            self.status.setText(tr("動画の情報を確認しています…", "Looking up the video…"))
            self._set_badges([])
            self._set_thumbnail_url(None)
        elif info is not None:
            self.status.setVisible(False)
            self.title.setVisible(True)
            self.title.set_full_text(info.title)
            self.subtitle.setVisible(bool(info.uploader))
            self.subtitle.setText(info.uploader or "")
            self._set_badges(self._badges_for(info))
            self.thumbnail.set_placeholder("list.bullet" if info.playlist_count else "film")
            self._set_thumbnail_url(info.thumbnail_url)
        else:
            self.title.setVisible(False)
            self.subtitle.setVisible(False)
            self.status.setVisible(True)
            self.status.setText(c.metadata_error or "")
            self._set_badges([])
            self.thumbnail.set_placeholder("film")
            self._set_thumbnail_url(None)

    def _badges_for(self, info: MediaInfo) -> list[Badge]:
        badges = []
        if info.is_live:
            badges.append(Badge(tr("ライブ", "LIVE"), "red"))
        if info.playlist_count:
            count = info.playlist_count
            badges.append(Badge(tr(f"プレイリスト · {count} 本", f"Playlist · {count}"), "accent"))
        if info.duration_text:
            badges.append(Badge(info.duration_text))
        if info.extractor:
            badges.append(Badge(info.extractor))
        return badges

    def _set_badges(self, badges: list[Badge]) -> None:
        while self.badges.count():
            item = self.badges.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for badge in badges:
            self.badges.addWidget(badge)
        self.badges.addStretch()

    def _set_thumbnail_url(self, url: str | None) -> None:
        if url == self._thumbnail_url:
            return
        self._thumbnail_url = url
        self.thumbnail.set_pixmap(None)
        if not url:
            return

        def loaded(data: bytes | None, _error: str | None) -> None:
            if url != self._thumbnail_url or not data:
                return
            pixmap = QPixmap()
            if pixmap.loadFromData(data):
                self.thumbnail.set_pixmap(pixmap)

        network.fetch(url, loaded)
