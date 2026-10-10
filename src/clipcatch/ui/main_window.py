"""メインウインドウ。上から「何を」「どの形式で」「どこへ」の順に並べる。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMimeData, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDragEnterEvent,
    QDropEvent,
    QGuiApplication,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSystemTrayIcon,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from clipcatch import APP_NAME, REPOSITORY
from clipcatch.controller import AppController
from clipcatch.core.formats import DownloadFormat, VideoQuality
from clipcatch.core.formatters import display_path
from clipcatch.core.i18n import tr
from clipcatch.core.platform import IS_MACOS, IS_WINDOWS
from clipcatch.core.sources import SUPPORTED_SITES_URL
from clipcatch.services import system
from clipcatch.services.updates import AppRelease
from clipcatch.ui import theme
from clipcatch.ui.about_dialog import AboutDialog
from clipcatch.ui.action_bar import ActionBar
from clipcatch.ui.log_panel import LogPanel
from clipcatch.ui.media_card import MediaCard
from clipcatch.ui.resources import app_icon
from clipcatch.ui.settings_window import SettingsWindow
from clipcatch.ui.tools_menu import ToolsButton
from clipcatch.ui.widgets import (
    Card,
    ElidedLabel,
    IconLabel,
    SegmentedControl,
    label,
    section_header,
)

FORMATS = list(DownloadFormat)
QUALITIES = list(VideoQuality)


class UrlField(QLineEdit):
    """左にリンクのアイコン、右に消去ボタンを持つ大きめの入力欄。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("urlField")
        self.setPlaceholderText(
            tr("動画のページの URL を貼り付け", "Paste the URL of a video page")
        )
        self.setClearButtonEnabled(False)
        self._link = QAction(self)
        self._clear = QAction(self)
        self.addAction(self._link, QLineEdit.ActionPosition.LeadingPosition)
        self.addAction(self._clear, QLineEdit.ActionPosition.TrailingPosition)
        self._clear.setToolTip(tr("入力を消去", "Clear"))
        self._clear.triggered.connect(self.clear)
        self.textChanged.connect(lambda text: self._clear.setVisible(bool(text)))
        self._clear.setVisible(False)
        theme.notifier().changed.connect(self._refresh_icons)
        self._refresh_icons()

    def _refresh_icons(self) -> None:
        p = theme.current()
        self._link.setIcon(theme.icon("link", p.secondary, 18))
        self._clear.setIcon(theme.icon("xmark.circle.fill", p.tertiary, 18, background=p.field))


class MainWindow(QMainWindow):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self.settings = controller.settings
        self._settings_window: SettingsWindow | None = None
        self._tray: QSystemTrayIcon | None = None
        self._release: AppRelease | None = None

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.setMinimumSize(560, 600)
        self.setAcceptDrops(True)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        content = QWidget()
        content.setObjectName("root")
        body = QVBoxLayout(content)
        body.setContentsMargins(22, 16, 22, 18)
        body.setSpacing(8)
        body.addLayout(self._build_header())
        self.banner = self._build_banner()
        body.addWidget(self.banner)
        body.addSpacing(4)
        body.addLayout(self._build_url_row())
        self.url_hint = label("", "footnote", wrap=True)
        self.url_hint.setOpenExternalLinks(True)
        self.url_hint.setContentsMargins(4, 0, 4, 0)
        body.addWidget(self.url_hint)
        self.media_card = MediaCard(controller)
        body.addWidget(self.media_card)
        body.addSpacing(10)
        body.addWidget(section_header(tr("保存する形式", "Format")))
        body.addWidget(self._build_format_card())
        body.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll, 1)
        self.log_panel = LogPanel(controller)
        outer.addWidget(self.log_panel)
        self.action_bar = ActionBar(controller)
        outer.addWidget(self.action_bar)

        self._create_actions()
        if IS_MACOS:
            self._build_menu_bar()

        controller.changed.connect(self._refresh)
        controller.alert.connect(self._show_alert)
        controller.notify.connect(self._notify)
        controller.app_update_available.connect(self._show_update)
        theme.notifier().changed.connect(self._refresh_url_hint)
        self.settings.changed.connect(self._settings_changed)
        self._refresh()
        self._restore_geometry()

    # MARK: - 組み立て

    def _build_header(self) -> QHBoxLayout:
        title = label(APP_NAME, "largeTitle")
        subtitle = label(tr("動画と音声を、URL ひとつで。", "Video and audio from a single URL."))
        subtitle.setObjectName("secondary")
        texts = QVBoxLayout()
        texts.setSpacing(0)
        texts.addWidget(title)
        texts.addWidget(subtitle)

        self.tools = ToolsButton(self.controller, self.open_settings, self.open_about)
        settings = QToolButton()
        settings.setToolTip(tr("設定", "Settings"))
        settings.setCursor(Qt.CursorShape.PointingHandCursor)
        settings.clicked.connect(self.open_settings)
        theme.bind_icon(settings, "slider", "secondary", 18)

        row = QHBoxLayout()
        row.setSpacing(4)
        row.addLayout(texts, 1)
        row.addWidget(self.tools, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(settings, 0, Qt.AlignmentFlag.AlignTop)
        return row

    def _build_banner(self) -> QWidget:
        banner = QWidget()
        banner.setObjectName("banner")
        banner.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        icon = IconLabel("arrow.down.circle.fill", "accent", 18)
        self.banner_text = label("", wrap=True)
        download = QPushButton(tr("ダウンロード", "Download"))
        download.clicked.connect(self._open_release)
        close = QToolButton()
        close.setObjectName("plain")
        close.setToolTip(tr("閉じる", "Dismiss"))
        close.clicked.connect(lambda: banner.setVisible(False))
        theme.bind_icon(close, "xmark.circle.fill", "tertiary", 16)
        layout = QHBoxLayout(banner)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(10)
        layout.addWidget(icon)
        layout.addWidget(self.banner_text, 1)
        layout.addWidget(download)
        layout.addWidget(close)
        banner.setVisible(False)
        return banner

    def _build_url_row(self) -> QHBoxLayout:
        self.url_field = UrlField()
        self.url_field.textChanged.connect(self.controller.set_url)
        self.url_field.returnPressed.connect(self.controller.start_download)
        paste = QPushButton(tr("貼り付け", "Paste"))
        paste.setObjectName("large")
        paste.setToolTip(tr("クリップボードの URL を入力します", "Paste a URL from the clipboard"))
        paste.clicked.connect(self.controller.paste_from_clipboard)
        theme.bind_icon(paste, "clipboard", "label", 16)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.url_field, 1)
        row.addWidget(paste)
        return row

    def _build_format_card(self) -> Card:
        card = Card()

        self.format_control = SegmentedControl([f.title for f in FORMATS])
        self.format_control.set_current_index(FORMATS.index(self.settings.format), animate=False)
        self.format_control.currentChanged.connect(
            lambda i: setattr(self.settings, "format", FORMATS[i])
        )
        self.format_summary = label("", "footnote", wrap=True)
        format_box = QWidget()
        format_layout = QVBoxLayout(format_box)
        format_layout.setContentsMargins(0, 2, 0, 0)
        format_layout.setSpacing(8)
        format_layout.addWidget(self.format_control)
        format_layout.addWidget(self.format_summary)
        card.add_row(format_box, padding=(14, 12))

        self.quality = QComboBox()
        for quality in QUALITIES:
            self.quality.addItem(quality.title, quality)
        self.quality.setCurrentIndex(QUALITIES.index(self.settings.quality))
        self.quality.currentIndexChanged.connect(
            lambda i: setattr(self.settings, "quality", QUALITIES[i])
        )
        self.quality_label = label(tr("最大解像度", "Maximum resolution"))
        quality_row = QWidget()
        q = QHBoxLayout(quality_row)
        q.setContentsMargins(0, 0, 0, 0)
        q.addWidget(self.quality_label, 1)
        q.addWidget(self.quality)
        card.add_row(quality_row)

        self.destination = ElidedLabel("", Qt.TextElideMode.ElideMiddle)
        change = QPushButton(tr("変更…", "Change…"))
        change.clicked.connect(self.choose_output_directory)
        reveal = QToolButton()
        reveal.setToolTip(
            tr("Finder で開く", "Open in Finder")
            if IS_MACOS
            else tr("エクスプローラーで開く", "Open in File Explorer")
        )
        reveal.clicked.connect(lambda: system.open_folder(self.settings.output_directory))
        theme.bind_icon(reveal, "arrow.up.forward.square", "secondary", 16)
        destination_row = QWidget()
        d = QHBoxLayout(destination_row)
        d.setContentsMargins(0, 0, 0, 0)
        d.setSpacing(8)
        d.addWidget(label(tr("保存先", "Save to")))
        d.addSpacing(8)
        d.addWidget(IconLabel("folder", "secondary", 16))
        d.addWidget(self.destination, 1)
        d.addWidget(change)
        d.addWidget(reveal)
        card.add_row(destination_row)
        return card

    def _create_actions(self) -> None:
        def action(text: str, shortcut, slot) -> QAction:
            act = QAction(text, self)
            if shortcut is not None:
                act.setShortcuts(shortcut if isinstance(shortcut, list) else [shortcut])
            act.triggered.connect(slot)
            self.addAction(act)  # メニューに入れなくてもショートカットが効くように
            return act

        c = self.controller
        self.act_start = action(
            tr("ダウンロード開始", "Start Download"),
            [QKeySequence("Ctrl+Return"), QKeySequence("Ctrl+Enter")],
            c.start_download,
        )
        self.act_cancel = action(
            tr("キャンセル", "Cancel"),
            [QKeySequence("Ctrl+."), QKeySequence(Qt.Key.Key_Escape)],
            c.cancel_download,
        )
        self.act_paste = action(
            tr("クリップボードから URL を貼り付け", "Paste URL from Clipboard"),
            QKeySequence("Ctrl+Shift+V"),
            c.paste_from_clipboard,
        )
        self.act_reveal = action(
            tr("保存先を開く", "Show Save Folder"), QKeySequence("Ctrl+Shift+O"), c.reveal_output
        )
        self.act_focus = action(
            tr("URL を入力", "Enter URL"),
            QKeySequence("Ctrl+L"),
            lambda: (self.url_field.setFocus(), self.url_field.selectAll()),
        )
        self.act_update = action(
            tr("yt-dlp を更新", "Update yt-dlp"), None, c.toolchain.update_ytdlp
        )
        self.act_settings = action(
            tr("設定…", "Settings…"),
            QKeySequence(QKeySequence.StandardKey.Preferences)
            if IS_MACOS
            else QKeySequence("Ctrl+,"),
            self.open_settings,
        )
        self.act_settings.setMenuRole(QAction.MenuRole.PreferencesRole)
        self.act_about = action(
            tr(f"{APP_NAME} について", f"About {APP_NAME}"), None, self.open_about
        )
        self.act_about.setMenuRole(QAction.MenuRole.AboutRole)
        self.act_quit = action(
            tr("終了", "Quit"), QKeySequence(QKeySequence.StandardKey.Quit), self.close
        )
        self.act_quit.setMenuRole(QAction.MenuRole.QuitRole)

    def _build_menu_bar(self) -> None:
        """macOS の画面上部のメニュー。Windows では右上のメニューとショートカットで代える。"""
        bar = QMenuBar()  # 親を持たせないとアプリ全体のメニューバーになる
        app_menu = bar.addMenu(APP_NAME)
        app_menu.addAction(self.act_about)
        app_menu.addAction(self.act_settings)
        app_menu.addAction(self.act_quit)

        download = bar.addMenu(tr("ダウンロード", "Download"))
        for act in (self.act_start, self.act_cancel):
            download.addAction(act)
        download.addSeparator()
        for act in (self.act_focus, self.act_paste, self.act_reveal):
            download.addAction(act)
        download.addSeparator()
        download.addAction(self.act_update)

        help_menu = bar.addMenu(tr("ヘルプ", "Help"))
        help_menu.addAction(
            tr(f"{APP_NAME} のリポジトリ", f"{APP_NAME} on GitHub"),
            lambda: system.open_url(f"https://github.com/{REPOSITORY}"),
        )
        help_menu.addAction(
            tr("問題を報告…", "Report an Issue…"),
            lambda: system.open_url(f"https://github.com/{REPOSITORY}/issues/new/choose"),
        )
        help_menu.addAction(
            tr("対応サイトの一覧", "Supported Sites"), lambda: system.open_url(SUPPORTED_SITES_URL)
        )
        self._menu_bar = bar

    # MARK: - 状態の反映

    def _refresh(self) -> None:
        c = self.controller
        busy = c.phase.is_busy
        fmt = self.settings.format
        self.format_summary.setText(fmt.summary)
        self.quality.setEnabled(not fmt.is_audio_only and not busy)
        self.quality_label.setEnabled(not fmt.is_audio_only)
        self.format_control.setEnabled(not busy)
        self.destination.setText(display_path(self.settings.output_directory))
        self.destination.setToolTip(str(self.settings.output_directory))
        self.act_start.setEnabled(c.can_start_download)
        self.act_cancel.setEnabled(busy)
        if self.url_field.text() != c.url_text:
            self.url_field.setText(c.url_text)
        self._refresh_url_hint()

    def _refresh_url_hint(self) -> None:
        c = self.controller
        p = theme.current()
        if not c.url_text.strip():
            link = (
                f'<a href="{SUPPORTED_SITES_URL}" style="color:{p.accent}; text-decoration:none">'
            )
            self.url_hint.setText(
                tr(
                    "URL を貼り付けるか、リンクをこのウインドウにドラッグ＆ドロップします。"
                    f"{link}対応サイト</a>",
                    f"Paste a URL or drag a link onto this window. {link}Supported sites</a>",
                )
            )
            self.url_hint.setVisible(True)
        elif not c.has_valid_url:
            self.url_hint.setText(
                tr(
                    "http:// または https:// で始まる URL を入力してください。",
                    "Enter a URL that starts with http:// or https://.",
                )
            )
            self.url_hint.setVisible(True)
        else:
            self.url_hint.setVisible(False)

    def _settings_changed(self, key: str) -> None:
        if key == "format":
            index = FORMATS.index(self.settings.format)
            if self.format_control.current_index() != index:
                self.format_control.set_current_index(index)
        self._refresh()

    # MARK: - 操作

    def choose_output_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            tr("保存先のフォルダを選択", "Choose a Folder to Save To"),
            str(self.settings.output_directory),
        )
        if directory:
            self.controller.set_output_directory(Path(directory))

    def open_settings(self) -> None:
        if self._settings_window is None:
            self._settings_window = SettingsWindow(self.controller, self)
        self._settings_window.show()
        self._settings_window.raise_()
        self._settings_window.activateWindow()

    def open_about(self) -> None:
        AboutDialog(self).exec()

    def _show_alert(self, title: str, message: str) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(title)
        box.setInformativeText(message)
        box.setWindowModality(Qt.WindowModality.WindowModal)  # macOS ではシートになる
        box.open()

    def _show_update(self, release: AppRelease) -> None:
        self._release = release
        self.banner_text.setText(
            tr(
                f"{APP_NAME} {release.version} が利用できます。",
                f"{APP_NAME} {release.version} is available.",
            )
        )
        self.banner.setVisible(True)

    def _open_release(self) -> None:
        if self._release:
            system.open_url(self._release.url)

    def _notify(self, title: str, message: str) -> None:
        """背面にいるときだけ知らせる。前面なら画面の表示で十分。"""
        if not self.settings.notify_when_done or QGuiApplication.applicationState() == (
            Qt.ApplicationState.ApplicationActive
        ):
            return
        QApplication.alert(self)  # Dock のアイコンが弾む／タスクバーが点滅する
        if IS_WINDOWS and QSystemTrayIcon.isSystemTrayAvailable():
            if self._tray is None:
                self._tray = QSystemTrayIcon(app_icon(), self)
                self._tray.messageClicked.connect(self._bring_to_front)
            self._tray.show()
            self._tray.showMessage(title, message, app_icon(), 8000)
            QTimer.singleShot(10_000, self._tray.hide)

    def _bring_to_front(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    # MARK: - ドラッグ＆ドロップ

    @staticmethod
    def _dropped_url(mime: QMimeData) -> str | None:
        if mime.hasUrls():
            for url in mime.urls():
                if url.scheme() in ("http", "https"):
                    return url.toString()
        if mime.hasText() and system.is_web_url(mime.text()):
            return mime.text().strip()
        return None

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if not self.controller.phase.is_busy and self._dropped_url(event.mimeData()):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        url = self._dropped_url(event.mimeData())
        if url:
            self.controller.set_url(url)
            event.acceptProposedAction()

    # MARK: - ウインドウの位置

    def _restore_geometry(self) -> None:
        geometry = self.settings.window_geometry()
        if not geometry or not self.restoreGeometry(geometry):
            self.resize(640, 760)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.controller.phase.is_busy:
            answer = QMessageBox.question(
                self,
                tr("ダウンロード中です", "A download is in progress"),
                tr(
                    "終了するとダウンロードは中止されます。終了しますか？",
                    "Quitting will stop the download. Quit anyway?",
                ),
                QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.controller.cancel_download()
        self.settings.set_window_geometry(self.saveGeometry().data())
        super().closeEvent(event)
