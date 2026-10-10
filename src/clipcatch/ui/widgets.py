"""独自に描く部品。OS に依らず同じ見た目・同じ動きにするため。"""

from __future__ import annotations

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFontMetrics,
    QKeyEvent,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from clipcatch.ui import theme


class Card(QFrame):
    """角の丸いグループ。中の行は区切り線で分ける（macOS の設定画面と同じ構成）。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._rows: list[QWidget] = []

    def add_row(self, widget: QWidget, padding: tuple[int, int] = (14, 10)) -> QWidget:
        if self._rows:
            self._layout.addWidget(Separator(inset=14))
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(padding[0], padding[1], padding[0], padding[1])
        layout.addWidget(widget)
        self._layout.addWidget(container)
        self._rows.append(container)
        return container


class Separator(QWidget):
    def __init__(self, inset: int = 0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(inset, 0, 0, 0)
        line = QFrame()
        line.setObjectName("separator")
        layout.addWidget(line)
        self.setFixedHeight(1)


def section_header(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("sectionHeader")
    return label


def label(text: str = "", name: str | None = None, wrap: bool = False) -> QLabel:
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget


class IconLabel(QLabel):
    """テーマが変わったら描き直せるアイコン。"""

    def __init__(self, name: str, color: str = "secondary", size: int = 16) -> None:
        super().__init__()
        self._name, self._color, self._size = name, color, size
        self.setFixedSize(size, size)
        self.refresh()
        theme.notifier().changed.connect(self.refresh)

    def set_icon(self, name: str, color: str | None = None) -> None:
        self._name = name
        if color:
            self._color = color
        self.refresh()

    def refresh(self) -> None:
        p = theme.current()
        color = getattr(p, self._color, self._color)
        self.setPixmap(theme.pixmap(self._name, color, self._size))


class ElidedLabel(QLabel):
    """幅に収まらないとき「…」で省略する。パスは中央、タイトルは末尾を省く。"""

    def __init__(self, text: str = "", mode: Qt.TextElideMode = Qt.TextElideMode.ElideRight):
        super().__init__()
        self._full = text
        self._mode = mode
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(40)
        super().setText(text)

    def setText(self, text: str) -> None:
        self._full = text
        self._update()

    def full_text(self) -> str:
        return self._full

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update()

    def _update(self) -> None:
        metrics = QFontMetrics(self.font())
        super().setText(metrics.elidedText(self._full, self._mode, max(self.width(), 10)))


class SegmentedControl(QWidget):
    """macOS のセグメンテッドコントロール。選択中の項目が滑らかに移る。"""

    currentChanged = Signal(int)

    PADDING = 2
    HEIGHT = 30

    def __init__(self, items: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items = items
        self._index = 0
        self._hover = -1
        self._position = 0.0  # 選択ピルの位置（項目単位、アニメーションする）
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(180)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._set_position)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setFixedHeight(self.HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName(" / ".join(items))

    def set_items(self, items: list[str]) -> None:
        self._items = items
        self.update()

    def current_index(self) -> int:
        return self._index

    def set_current_index(self, index: int, animate: bool = True) -> None:
        index = max(0, min(index, len(self._items) - 1))
        if index == self._index and not self._animation.state():
            self._position = float(index)
            self.update()
            return
        changed = index != self._index
        self._index = index
        if animate and self.isVisible():
            self._animation.stop()
            self._animation.setStartValue(self._position)
            self._animation.setEndValue(float(index))
            self._animation.start()
        else:
            self._position = float(index)
            self.update()
        self.setAccessibleDescription(self._items[index])
        if changed:
            self.currentChanged.emit(index)

    def sizeHint(self) -> QSize:
        metrics = QFontMetrics(self.font())
        widest = max((metrics.horizontalAdvance(t) for t in self._items), default=40)
        return QSize((widest + 28) * max(len(self._items), 1), self.HEIGHT)

    def _set_position(self, value: float) -> None:
        self._position = float(value)
        self.update()

    def _segment_width(self) -> float:
        return (self.width() - self.PADDING * 2) / max(len(self._items), 1)

    def _index_at(self, x: float) -> int:
        return int(max(0, min((x - self.PADDING) // self._segment_width(), len(self._items) - 1)))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.set_current_index(self._index_at(event.position().x()))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        hover = self._index_at(event.position().x())
        if hover != self._hover:
            self._hover = hover
            self.update()

    def leaveEvent(self, _event) -> None:
        self._hover = -1
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            self.set_current_index(self._index - 1)
        elif event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            self.set_current_index(self._index + 1)
        else:
            super().keyPressEvent(event)

    def paintEvent(self, _event: QPaintEvent) -> None:
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        radius = 8.0

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(p.color("fill"))
        painter.drawRoundedRect(rect, radius, radius)

        width = self._segment_width()
        # 区切り線（選択中の両隣には出さない）
        painter.setPen(QPen(p.color("tertiary", 0.35), 1))
        for i in range(1, len(self._items)):
            if abs(i - self._position) < 1 or abs(i - 1 - self._position) < 1:
                continue
            x = self.PADDING + width * i
            painter.drawLine(QPointF(x, 8), QPointF(x, self.height() - 8))

        # 選択ピル
        pill = QRectF(
            self.PADDING + width * self._position,
            self.PADDING,
            width,
            self.height() - self.PADDING * 2,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        if not p.dark:
            painter.setBrush(QColor(0, 0, 0, 18))
            painter.drawRoundedRect(pill.translated(0, 0.8), radius - 1.5, radius - 1.5)
        painter.setBrush(QColor("#636366") if p.dark else QColor("#FFFFFF"))
        painter.drawRoundedRect(pill, radius - 1.5, radius - 1.5)

        for i, text in enumerate(self._items):
            segment = QRectF(self.PADDING + width * i, 0, width, self.height())
            if i == self._hover and i != self._index and self.isEnabled():
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(p.color("fill_hover"))
                painter.drawRoundedRect(
                    segment.adjusted(1, self.PADDING, -1, -self.PADDING), radius - 2, radius - 2
                )
            font = self.font()
            font.setWeight(font.Weight.DemiBold if i == self._index else font.Weight.Normal)
            painter.setFont(font)
            color = p.label if self.isEnabled() else p.tertiary
            painter.setPen(QColor(color))
            painter.drawText(segment, Qt.AlignmentFlag.AlignCenter, text)

        if self.hasFocus():
            painter.setPen(QPen(p.color("accent", 0.55), 2.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1.25, 1.25, -1.25, -1.25), radius, radius)


class Switch(QAbstractButton):
    """オン／オフのスイッチ。オンのときはアクセントカラーになる。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._offset = 0.0
        self._animation = QPropertyAnimation(self, b"offset", self)
        self._animation.setDuration(160)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)
        self.setFixedSize(38, 22)

    def sizeHint(self) -> QSize:
        return QSize(38, 22)

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float) -> None:
        self._offset = value
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def setChecked(self, checked: bool) -> None:
        super().setChecked(checked)
        self._animation.stop()
        self._offset = 1.0 if checked else 0.0
        self.update()

    def _animate(self, checked: bool) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._offset)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def paintEvent(self, _event: QPaintEvent) -> None:
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(1, 1, self.width() - 2, self.height() - 2)
        off, on = p.color("fill_pressed"), p.color("accent")
        t = self._offset
        color = QColor(
            round(off.red() + (on.red() - off.red()) * t),
            round(off.green() + (on.green() - off.green()) * t),
            round(off.blue() + (on.blue() - off.blue()) * t),
        )
        if not self.isEnabled():
            color.setAlphaF(0.45)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)

        knob = track.height() - 4
        x = track.left() + 2 + (track.width() - knob - 4) * t
        painter.setBrush(QColor(0, 0, 0, 40))
        painter.drawEllipse(QRectF(x, track.top() + 2.6, knob, knob))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(x, track.top() + 2, knob, knob))

        if self.hasFocus():
            painter.setPen(QPen(p.color("accent", 0.5), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)


class ProgressLine(QWidget):
    """細いプログレスバー。値が不明なときは光の帯が流れる不確定表示になる。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value: float | None = 0.0
        self._shown = 0.0
        self._phase = 0.0
        self._tint = "accent"
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self.setFixedHeight(6)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_value(self, value: float | None, tint: str = "accent") -> None:
        self._value = value
        self._tint = tint
        moving = value is None or abs(self._shown - value) > 0.001
        if moving and not self._timer.isActive():
            self._timer.start()
        self.update()

    def _tick(self) -> None:
        if self._value is None:
            self._phase = (self._phase + 0.012) % 1.0
        else:
            # 進捗は飛ばずに追いかける（細かく揺れても目が疲れない）
            self._shown += (self._value - self._shown) * 0.25
            if abs(self._value - self._shown) < 0.001:
                self._shown = self._value
                self._timer.stop()
        self.update()

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, _event: QPaintEvent) -> None:
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        radius = rect.height() / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(p.color("fill"))
        painter.drawRoundedRect(rect, radius, radius)

        tint = p.color(self._tint)
        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        painter.setClipPath(clip)
        if self._value is None:
            band = rect.width() * 0.35
            x = -band + (rect.width() + band) * self._phase
            gradient = QLinearGradient(x, 0, x + band, 0)
            transparent = QColor(tint)
            transparent.setAlphaF(0.0)
            gradient.setColorAt(0, transparent)
            gradient.setColorAt(0.5, tint)
            gradient.setColorAt(1, transparent)
            painter.setBrush(gradient)
            painter.drawRect(QRectF(x, 0, band, rect.height()))
        elif self._shown > 0:
            painter.setBrush(tint)
            width = max(rect.width() * self._shown, rect.height())
            painter.drawRoundedRect(QRectF(0, 0, width, rect.height()), radius, radius)


class Spinner(QWidget):
    """小さな回転インジケータ（macOS の小サイズ ProgressView に相当）。"""

    def __init__(self, size: int = 16, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(size, size)

    def showEvent(self, event) -> None:
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def _tick(self) -> None:
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = self.width() / 2
        painter.translate(center, center)
        painter.rotate(self._angle)
        for i in range(12):
            color = p.color("secondary", 0.15 + 0.85 * (i / 11))
            pen = QPen(color, max(1.5, self.width() / 10))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(0, -center * 0.45), QPointF(0, -center * 0.9))
            painter.rotate(30)


class Badge(QLabel):
    """再生時間やサイト名を示す小さなラベル。"""

    def __init__(self, text: str, tint: str = "secondary") -> None:
        super().__init__(text)
        self._tint = tint
        self.refresh()
        theme.notifier().changed.connect(self.refresh)

    def refresh(self) -> None:
        p = theme.current()
        color = QColor(getattr(p, self._tint))
        bg = QColor(color)
        bg.setAlphaF(0.13)
        self.setStyleSheet(
            f"color: {color.name()}; background: rgba({bg.red()},{bg.green()},{bg.blue()},"
            f"{bg.alphaF():.2f}); border-radius: 8px; padding: 1px 7px; font-size: 11px;"
            "font-weight: 500;"
        )


class Thumbnail(QWidget):
    """角を丸めたサムネイル。画像が無いときはアイコンを置く。"""

    def __init__(self, width: int = 144, height: int = 81, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._placeholder = "film"
        self._shimmer = 0.0
        self._loading = False
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(width, height)

    def set_pixmap(self, pixmap: QPixmap | None) -> None:
        self._pixmap = pixmap
        self.update()

    def set_placeholder(self, name: str) -> None:
        self._placeholder = name
        self.update()

    def set_loading(self, loading: bool) -> None:
        self._loading = loading
        if loading:
            self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def _tick(self) -> None:
        self._shimmer = (self._shimmer + 0.02) % 1.0
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        painter.setClipPath(path)
        painter.fillRect(rect, p.color("fill"))

        if self._pixmap is not None and not self._pixmap.isNull():
            # アスペクト比を保ったまま枠いっぱいに切り抜く
            ratio = self._pixmap.devicePixelRatio()
            source = QRectF(0, 0, self._pixmap.width() / ratio, self._pixmap.height() / ratio)
            scale = max(rect.width() / source.width(), rect.height() / source.height())
            w, h = source.width() * scale, source.height() * scale
            target = QRectF((rect.width() - w) / 2, (rect.height() - h) / 2, w, h)
            painter.drawPixmap(target, self._pixmap, QRectF(self._pixmap.rect()))
        elif self._loading:
            band = rect.width() * 0.6
            x = -band + (rect.width() + band) * self._shimmer
            gradient = QLinearGradient(x, 0, x + band, 0)
            highlight = p.color("card", 0.0)
            gradient.setColorAt(0, highlight)
            gradient.setColorAt(0.5, p.color("card", 0.55))
            gradient.setColorAt(1, highlight)
            painter.fillRect(rect, gradient)
        else:
            size = 24
            icon = theme.pixmap(self._placeholder, p.secondary, size)
            painter.drawPixmap(
                round((rect.width() - size) / 2), round((rect.height() - size) / 2), icon
            )

        painter.setClipping(False)
        painter.setPen(QPen(p.color("label", 0.08), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
