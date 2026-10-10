"""QApplication の組み立てと起動。"""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QLocale, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from clipcatch import APP_NAME, __version__
from clipcatch.core import i18n


def run(argv: list[str]) -> int:
    QCoreApplication.setOrganizationName(APP_NAME)
    QCoreApplication.setOrganizationDomain("io.github.myuto2490")
    QCoreApplication.setApplicationName(APP_NAME)
    QCoreApplication.setApplicationVersion(__version__)
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(argv)
    from clipcatch.ui import theme

    theme.capture_system_accent(app)
    app.setStyle("Fusion")  # スタイルシートを両 OS で同じように効かせるため
    app.setApplicationDisplayName(APP_NAME)

    # 言語は OS の設定に従う（日本語以外は英語）
    languages = QLocale.system().uiLanguages()
    i18n.set_language(i18n.detect_language(languages))

    # 画面を作る前に言語と配色を決める
    from clipcatch.controller import AppController
    from clipcatch.ui.main_window import MainWindow
    from clipcatch.ui.resources import app_icon

    theme.configure_application_font(app)
    theme.apply(app)
    app.setWindowIcon(app_icon())
    QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _scheme: theme.apply(app))

    controller = AppController()
    window = MainWindow(controller)
    window.show()
    window.raise_()
    window.activateWindow()

    def on_state(state: Qt.ApplicationState) -> None:
        if state == Qt.ApplicationState.ApplicationActive:
            controller.auto_paste_if_appropriate()

    app.applicationStateChanged.connect(on_state)
    # 起動直後のセットアップはウインドウを描いてから始める
    QTimer.singleShot(0, controller.bootstrap)
    app.aboutToQuit.connect(controller.toolchain.cleanup_staging)
    return app.exec()
