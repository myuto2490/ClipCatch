"""QApplication の組み立て。UI は後続のブランチで実装する。"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QLabel

from clipcatch import APP_NAME


def run(argv: list[str]) -> int:
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    label = QLabel(APP_NAME)
    label.resize(400, 200)
    label.show()
    return app.exec()
