"""重い同期処理（アーカイブの展開など）を別スレッドで走らせ、結果を UI スレッドへ返す。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Relay(QObject):
    done = Signal(object, object)  # (result, error)


class _Job(QRunnable):
    def __init__(self, fn: Callable[[], Any], relay: _Relay) -> None:
        super().__init__()
        self._fn = fn
        self._relay = relay

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:
            self._relay.done.emit(None, exc)
        else:
            self._relay.done.emit(result, None)


_alive: set[_Relay] = set()


def run_in_background(
    fn: Callable[[], Any], on_done: Callable[[Any, BaseException | None], None]
) -> None:
    """`fn` を別スレッドで実行し、終わったら UI スレッドで `on_done(result, error)` を呼ぶ。"""
    relay = _Relay()
    _alive.add(relay)  # 完了まで参照を保つ

    def finish(result: Any, error: BaseException | None) -> None:
        _alive.discard(relay)
        relay.deleteLater()
        on_done(result, error)

    relay.done.connect(finish)
    QThreadPool.globalInstance().start(_Job(fn, relay))
