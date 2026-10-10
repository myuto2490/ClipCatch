"""「ClipCatch について」。バージョン・ライセンス・利用しているソフトウェアを示す。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from clipcatch import APP_NAME, REPOSITORY, __version__
from clipcatch.core.i18n import tr
from clipcatch.services import system
from clipcatch.ui.resources import app_icon
from clipcatch.ui.widgets import label


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr(f"{APP_NAME} について", f"About {APP_NAME}"))
        self.setFixedWidth(360)

        icon = QLabel()
        icon.setPixmap(app_icon().pixmap(96, 96))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        name = label(APP_NAME, "largeTitle")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version = label(tr(f"バージョン {__version__}", f"Version {__version__}"), "secondary")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        summary = label(
            tr(
                "URL を貼るだけで動画や音声を保存できます。",
                "Save video and audio just by pasting a URL.",
            ),
            wrap=True,
        )
        summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credits = label(
            tr(
                "yt-dlp・FFmpeg・Deno・aria2・Qt for Python を利用しています。"
                "各ソフトウェアはそれぞれのライセンスに従います。",
                "Powered by yt-dlp, FFmpeg, Deno, aria2 and Qt for Python, "
                "each under its own license.",
            ),
            "caption",
            wrap=True,
        )
        credits.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyright_ = label("© 2026 myuto2490 · MIT License", "caption")
        copyright_.setAlignment(Qt.AlignmentFlag.AlignCenter)

        links = QHBoxLayout()
        links.addStretch()
        for text, url in (
            ("GitHub", f"https://github.com/{REPOSITORY}"),
            (tr("ライセンス", "License"), f"https://github.com/{REPOSITORY}/blob/main/LICENSE"),
        ):
            button = QPushButton(text)
            button.setObjectName("link")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, u=url: system.open_url(u))
            links.addWidget(button)
        links.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 22)
        layout.setSpacing(6)
        layout.addWidget(icon)
        layout.addSpacing(4)
        layout.addWidget(name)
        layout.addWidget(version)
        layout.addSpacing(8)
        layout.addWidget(summary)
        layout.addSpacing(6)
        layout.addWidget(credits)
        layout.addLayout(links)
        layout.addWidget(copyright_)
