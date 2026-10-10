"""QApplication の組み立てと起動。"""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QLocale, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from clipcatch import APP_NAME, __version__
from clipcatch.core import i18n


def self_test(app: QApplication, window) -> int:
    """配布物が正しく組み上がっているかを確かめて終了する（CI 用）。

    TLS のプラグイン・SVG の描画・アイコンが同梱されていないと、起動はしても
    ダウンロードやアイコン表示が失敗するため、ここでまとめて確認する。
    """
    from PySide6.QtNetwork import QSslSocket

    from clipcatch.ui import theme
    from clipcatch.ui.resources import app_icon

    checks = {
        "tls": QSslSocket.supportsSsl(),
        "svg": not theme.pixmap("link", "#000000", 16).isNull(),
        "icon": not app_icon().isNull(),
        "window": window.isVisible(),
    }
    for name, ok in checks.items():
        print(f"{name}: {'ok' if ok else 'FAILED'}", flush=True)
    window.close()
    app.processEvents()
    return 0 if all(checks.values()) else 1


def run(argv: list[str]) -> int:
    QCoreApplication.setOrganizationName(APP_NAME)
    QCoreApplication.setOrganizationDomain("myuto2490.github.io")
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

    if "--self-test" in argv:
        return self_test(app, window)

    app.applicationStateChanged.connect(on_state)
    # 起動直後のセットアップはウインドウを描いてから始める
    QTimer.singleShot(0, controller.bootstrap)
    app.aboutToQuit.connect(controller.toolchain.cleanup_staging)
    return app.exec()
