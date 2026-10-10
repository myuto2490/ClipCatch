import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("ClipCatchTests")
    app.setApplicationName("ClipCatchTests")
    yield app


@pytest.fixture
def wait_for(qapp):
    """条件が満たされるまでイベントループを回す。"""
    from PySide6.QtCore import QDeadlineTimer, QEventLoop

    def wait(predicate, timeout_ms=10_000):
        deadline = QDeadlineTimer(timeout_ms)
        while not predicate():
            if deadline.hasExpired():
                raise TimeoutError("condition not met")
            qapp.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)

    return wait


@pytest.fixture(autouse=True)
def english():
    from clipcatch.core.i18n import set_language

    set_language("en")
    yield
    set_language("en")
