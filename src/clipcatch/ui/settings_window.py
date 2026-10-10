"""設定ウインドウ。頻繁には変えない項目をメイン画面から分けて置く。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from clipcatch.controller import AppController
from clipcatch.core.formats import CookieBrowser
from clipcatch.core.i18n import tr
from clipcatch.core.platform import IS_MACOS
from clipcatch.services import system
from clipcatch.services.toolchain import ToolState
from clipcatch.ui.tools_menu import describe
from clipcatch.ui.widgets import Card, Switch, label, section_header


def _row(title: str, detail: str | None, control: QWidget | None) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    texts = QVBoxLayout()
    texts.setSpacing(2)
    texts.addWidget(label(title, "rowTitle", wrap=True))
    if detail:
        texts.addWidget(label(detail, "rowDetail", wrap=True))
    layout.addLayout(texts, 1)
    if control is not None:
        layout.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
    return row


class SettingsWindow(QDialog):
    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.settings = controller.settings
        self.setWindowTitle(tr("設定", "Settings"))
        self.setMinimumSize(480, 520)
        self.resize(520, 640)

        content = QWidget()
        content.setObjectName("root")
        body = QVBoxLayout(content)
        body.setContentsMargins(20, 18, 20, 20)
        body.setSpacing(8)

        reveal_title = (
            tr("完了したら Finder で表示", "Show in Finder when done")
            if IS_MACOS
            else tr("完了したらエクスプローラーで表示", "Show in File Explorer when done")
        )
        body.addWidget(section_header(tr("動作", "General")))
        general = Card()
        general.add_row(_row(reveal_title, None, self._switch("revealWhenDone")))
        general.add_row(
            _row(
                tr("クリップボードの URL を自動で入力", "Paste copied URLs automatically"),
                tr(
                    "アプリに切り替えたとき、コピーした URL を入力欄に入れます。",
                    "When you switch to ClipCatch, a copied URL is filled in for you.",
                ),
                self._switch("autoPasteURL"),
            )
        )
        general.add_row(
            _row(
                tr("完了を知らせる", "Notify when done"),
                tr(
                    "別のアプリを使っているときに、完了や失敗を知らせます。",
                    "Get notified about finished or failed downloads while you work elsewhere.",
                ),
                self._switch("notifyWhenDone"),
            )
        )
        body.addWidget(general)

        body.addSpacing(10)
        body.addWidget(section_header(tr("言語", "Language")))
        language_card = Card()
        self.language = QComboBox()
        # 言語名はその言語自身で書く（読めない言語に切り替えても戻せるように）
        for value, title in (
            ("system", tr("システムに合わせる", "Match System")),
            ("ja", "日本語"),
            ("en", "English"),
        ):
            self.language.addItem(title, value)
        self.language.setCurrentIndex(max(self.language.findData(self.settings.language), 0))
        self.language.currentIndexChanged.connect(self._language_changed)
        language_card.add_row(
            _row(
                tr("表示する言語", "Display language"),
                tr(
                    "変更は ClipCatch の再起動後に反映されます。",
                    "Takes effect after ClipCatch restarts.",
                ),
                self.language,
            )
        )
        body.addWidget(language_card)

        body.addSpacing(10)
        body.addWidget(section_header(tr("ダウンロード", "Downloads")))
        downloads = Card()
        downloads.add_row(
            _row(
                tr("aria2c で高速ダウンロード", "Faster downloads with aria2c"),
                tr(
                    "1 本のファイルを分割して同時に取得します。接続あたりの速度を"
                    "絞るサイト（bilibili など）で効果があります。",
                    "Splits a file into parts and downloads them in parallel. Helps on sites "
                    "that throttle each connection, such as bilibili.",
                ),
                self._switch("accelerateWithAria2c"),
            )
        )
        self.aria2_status = label("", "rowDetail", wrap=True)
        self.aria2_install = QPushButton(
            tr("Homebrew で導入…", "Install with Homebrew…") if IS_MACOS else tr("導入", "Install")
        )
        self.aria2_install.clicked.connect(controller.toolchain.install_aria2c)
        self.aria2_row = downloads.add_row(_row("aria2c", None, self.aria2_install))
        self.aria2_row.layout().addWidget(self.aria2_status)

        self.cookies = QComboBox()
        for browser in CookieBrowser.available():
            self.cookies.addItem(browser.title, browser)
        self.cookies.setCurrentIndex(max(self.cookies.findData(self.settings.cookie_browser), 0))
        self.cookies.currentIndexChanged.connect(self._cookie_changed)
        downloads.add_row(
            _row(
                tr("ブラウザの Cookie を使う", "Use cookies from browser"),
                tr(
                    "ログインしないと見られない動画や画質を保存するときに使います。",
                    "Needed for videos or qualities that require you to be signed in.",
                ),
                self.cookies,
            )
        )
        downloads.add_row(
            _row(
                tr("プレイリストはすべて保存", "Download entire playlists"),
                tr(
                    "オフのときは、URL が指す 1 本だけを保存します。",
                    "When off, only the single video the URL points to is saved.",
                ),
                self._switch("allowPlaylist"),
            )
        )
        downloads.add_row(
            _row(
                tr("yt-dlp の個人設定ファイルを読み込む", "Use my yt-dlp config file"),
                tr(
                    "既定では、どの環境でも同じ結果になるよう無視します。",
                    "Ignored by default so results are the same on every computer.",
                ),
                self._switch("useUserConfig"),
            )
        )
        body.addWidget(downloads)

        body.addSpacing(10)
        body.addWidget(section_header(tr("アップデート", "Updates")))
        updates = Card()
        updates.add_row(
            _row(
                tr("新しいバージョンを確認", "Check for new versions of ClipCatch"),
                tr("起動時に GitHub のリリースを確認します。", "Checks GitHub releases at launch."),
                self._switch("checkForAppUpdates"),
            )
        )
        self.ytdlp_status = label("", "rowDetail", wrap=True)
        self.ytdlp_update = QPushButton(tr("今すぐ更新", "Update Now"))
        self.ytdlp_update.clicked.connect(controller.toolchain.update_ytdlp)
        ytdlp_row = updates.add_row(
            _row(
                "yt-dlp",
                tr(
                    "サイトの仕様変更に追従するため、定期的な更新をおすすめします。",
                    "Sites change often. Keeping yt-dlp up to date keeps downloads working.",
                ),
                self.ytdlp_update,
            )
        )
        ytdlp_row.layout().addWidget(self.ytdlp_status)
        body.addWidget(updates)
        body.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

        controller.toolchain.changed.connect(self._refresh_tools)
        self.settings.changed.connect(self._refresh_tools)
        self._refresh_tools()

    def _switch(self, key: str) -> Switch:
        switch = Switch()
        switch.setChecked(self.settings.get_flag(key))
        switch.toggled.connect(lambda value: self.settings.set_flag(key, value))
        return switch

    def _language_changed(self, index: int) -> None:
        self.settings.language = self.language.itemData(index)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(tr("言語を変更しました", "Language changed"))
        box.setInformativeText(
            tr(
                "新しい言語は ClipCatch を再起動すると反映されます。",
                "The new language will be used after ClipCatch restarts.",
            )
        )
        restart = box.addButton(
            tr("今すぐ再起動", "Restart Now"), QMessageBox.ButtonRole.AcceptRole
        )
        box.addButton(tr("あとで", "Later"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(restart)
        restart.setEnabled(not self.controller.phase.is_busy)
        box.exec()
        if box.clickedButton() is restart:
            self._restart()

    def _restart(self) -> None:
        """メインウインドウを閉じられたら（ダウンロードの確認を通ったら）起動し直す。"""
        window = self.parentWidget()
        if window is not None and not window.close():
            return
        if system.relaunch():
            QApplication.quit()

    def _cookie_changed(self, index: int) -> None:
        self.settings.cookie_browser = self.cookies.itemData(index)

    def _refresh_tools(self, *_args) -> None:
        tc = self.controller.toolchain
        aria2 = tc.aria2c
        missing = tr(
            "未導入です（内蔵ダウンローダを使います）",
            "Not installed (built-in downloader is used)",
        )
        self.aria2_status.setText(describe(aria2, missing))
        checking = aria2.state in (ToolState.UNKNOWN, ToolState.CHECKING)
        self.aria2_install.setVisible(not aria2.ready and not checking and tc.can_install_aria2c)
        self.aria2_install.setEnabled(not aria2.state.is_busy)
        self.aria2_row.setEnabled(self.settings.accelerate_with_aria2c)

        text = describe(tc.ytdlp, tr("見つかりません", "Not found"))
        if tc.update_available and tc.latest_ytdlp:
            text += tr(f"（最新は {tc.latest_ytdlp}）", f" (latest: {tc.latest_ytdlp})")
        self.ytdlp_status.setText(text)
        self.ytdlp_update.setEnabled(
            tc.ytdlp.state is not ToolState.INSTALLING and not self.controller.phase.is_busy
        )
