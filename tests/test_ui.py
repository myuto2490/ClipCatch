"""画面を実際に組み立てて、状態の変化で壊れないことを確かめる（オフスクリーン）。"""

import pytest

from clipcatch.core.formats import DownloadFormat
from clipcatch.core.models import Phase, TransferProgress


@pytest.fixture
def window(qapp, tmp_path):
    from PySide6.QtCore import QSettings

    from clipcatch.controller import AppController
    from clipcatch.services.settings import Settings
    from clipcatch.ui import theme
    from clipcatch.ui.main_window import MainWindow

    theme.apply(qapp, dark=False)
    store = QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat)
    controller = AppController(Settings(store))
    win = MainWindow(controller)
    win.show()
    yield win
    win.close()


def test_url_round_trip(window):
    c = window.controller
    window.url_field.setText("https://example.com/watch?v=1")
    assert c.url_text == "https://example.com/watch?v=1"
    assert not window.url_hint.isVisible()
    window.url_field.setText("not a url")
    assert window.url_hint.isVisible()
    c.clear_url()
    assert window.url_field.text() == ""


def test_format_selection_updates_settings(window):
    window.format_control.set_current_index(2, animate=False)
    assert window.settings.format is DownloadFormat.MP3
    assert not window.quality.isEnabled()  # 音声のみは解像度を選べない


def test_download_states_render(window):
    c = window.controller
    bar = window.action_bar
    c.phase = Phase.DOWNLOADING
    c.progress = TransferProgress(fraction=0.5, downloaded_bytes=5, total_bytes=10)
    c.status_text = "clip.mp4"
    c.changed.emit()
    assert bar.cancel.isVisible()
    assert "50.0%" in bar.status.full_text()
    assert not window.format_control.isEnabled()

    for phase in (Phase.FINISHED, Phase.FAILED, Phase.CANCELLED):
        c.phase = phase
        c.changed.emit()
        assert not bar.cancel.isVisible()
        assert bar.symbol.isVisible()


def test_start_disabled_until_ytdlp_ready(window):
    window.url_field.setText("https://example.com/v")
    assert not window.action_bar.start.isEnabled()


def test_log_panel(window):
    from clipcatch.core.models import LogLevel

    c = window.controller
    c.append_log("hello", LogLevel.ERROR)
    panel = window.log_panel
    assert panel.count.text() == str(len(c.log))
    panel.set_expanded(True)
    assert "hello" in panel.view.toPlainText()
    c.clear_log()
    assert panel.view.toPlainText() == ""


def test_theme_switch_keeps_working(qapp, window):
    from clipcatch.ui import theme

    theme.apply(qapp, dark=True)
    assert theme.current().dark
    theme.apply(qapp, dark=False)
    assert not theme.current().dark


def test_settings_and_about_open(window):
    from clipcatch.ui.about_dialog import AboutDialog
    from clipcatch.ui.settings_window import SettingsWindow

    settings = SettingsWindow(window.controller, window)
    settings.show()
    settings.close()
    about = AboutDialog(window)
    about.show()
    about.close()


def test_every_icon_renders(qapp):
    from clipcatch.ui import theme

    for name in theme._ICONS:
        assert not theme.pixmap(name, "#000000", 16).isNull(), name
