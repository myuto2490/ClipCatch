"""配色・文字・アイコン。Apple Human Interface Guidelines の考え方に沿う。

- 色は役割（ラベル・区切り線・塗り）で決め、ライト／ダークで値だけを差し替える
- アクセントカラーは OS の設定（macOS のアクセントカラー、Windows のテーマ色）に従う
- 文字はシステムフォント。大きさの段階を少なく保ち、太さと色で階層を作る

Fusion スタイルに独自のスタイルシートを当てて、macOS と Windows で同じ見た目にする。
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QByteArray, QObject, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QGuiApplication,
    QIcon,
    QPainter,
    QPalette,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

from clipcatch.core.platform import IS_MACOS, IS_WINDOWS

FALLBACK_ACCENT = "#0A84FF"


@dataclass(frozen=True)
class Palette:
    dark: bool
    window: str  # 一番奥の背景（グループ化された背景）
    card: str  # グループの面
    bar: str  # 下端のバー
    elevated: str  # メニュー・ポップアップ
    label: str
    secondary: str
    tertiary: str
    separator: str
    fill: str  # ボタンなどの塗り
    fill_hover: str
    fill_pressed: str
    field: str  # 入力欄
    log: str
    accent: str
    on_accent: str
    green: str
    orange: str
    red: str

    def color(self, name: str, alpha: float | None = None) -> QColor:
        color = QColor(getattr(self, name))
        if alpha is not None:
            color.setAlphaF(alpha)
        return color


def _light(accent: str) -> Palette:
    return Palette(
        dark=False,
        window="#F2F2F7",
        card="#FFFFFF",
        bar="#FBFBFD",
        elevated="#FFFFFF",
        label="#1D1D1F",
        secondary="#6E6E73",
        tertiary="#AEAEB2",
        separator="#DEDEE3",
        fill="#E9E9EE",
        fill_hover="#E1E1E6",
        fill_pressed="#D5D5DB",
        field="#FFFFFF",
        log="#FAFAFC",
        accent=accent,
        on_accent="#FFFFFF",
        green="#28A745",
        orange="#F08A00",
        red="#E5383B",
    )


def _dark(accent: str) -> Palette:
    return Palette(
        dark=True,
        window="#161618",
        card="#232325",
        bar="#1C1C1E",
        elevated="#2C2C2E",
        label="#F5F5F7",
        secondary="#A1A1A6",
        tertiary="#636366",
        separator="#38383A",
        fill="#36363A",
        fill_hover="#3E3E42",
        fill_pressed="#48484C",
        field="#1C1C1E",
        log="#1A1A1C",
        accent=accent,
        on_accent="#FFFFFF",
        green="#30D158",
        orange="#FF9F0A",
        red="#FF453A",
    )


class _Notifier(QObject):
    changed = Signal()


_notifier: _Notifier | None = None


def notifier() -> _Notifier:
    """外観（ライト／ダーク）が切り替わったときに `changed` を出す。"""
    global _notifier
    if _notifier is None:
        _notifier = _Notifier()
    return _notifier


_system_accent: str | None = None
_current: Palette = _light(FALLBACK_ACCENT)
_icon_dir = Path(tempfile.mkdtemp(prefix="clipcatch-theme-"))


def current() -> Palette:
    return _current


def is_dark_mode() -> bool:
    hints = QGuiApplication.styleHints()
    return hints.colorScheme() == Qt.ColorScheme.Dark


def capture_system_accent(app: QApplication) -> None:
    """OS のアクセントカラーを覚えておく。スタイルを Fusion に切り替える前に呼ぶ。"""
    global _system_accent
    _system_accent = _read_system_accent(app)


def _read_system_accent(app: QApplication) -> str:
    palette = app.palette()
    role = getattr(QPalette.ColorRole, "Accent", QPalette.ColorRole.Highlight)
    color = palette.color(role)
    # 彩度が低すぎる（グラファイトなど）ときも読みやすい青に寄せない。OS の選択を尊重する。
    return color.name() if color.isValid() else FALLBACK_ACCENT


def ui_font_family() -> str:
    if IS_WINDOWS:
        families = set(QFontDatabase.families())
        for name in ("Segoe UI Variable Text", "Segoe UI", "Yu Gothic UI"):
            if name in families:
                return name
    return QApplication.font().family()


MONO_FAMILIES = ["SF Mono", "Menlo", "Cascadia Mono", "Consolas", "monospace"]


def apply(app: QApplication, dark: bool | None = None) -> Palette:
    """現在の外観モードに合わせて配色を作り、アプリ全体に当てる。

    `dark` を渡すと OS の設定より優先する（スクリーンショットの作成用）。
    """
    global _system_accent, _current
    if _system_accent is None:
        _system_accent = _read_system_accent(app)
    use_dark = is_dark_mode() if dark is None else dark
    _current = _dark(_system_accent) if use_dark else _light(_system_accent)
    p = _current

    palette = QPalette()
    role = QPalette.ColorRole
    palette.setColor(role.Window, QColor(p.window))
    palette.setColor(role.WindowText, QColor(p.label))
    palette.setColor(role.Base, QColor(p.field))
    palette.setColor(role.AlternateBase, QColor(p.card))
    palette.setColor(role.Text, QColor(p.label))
    palette.setColor(role.Button, QColor(p.fill))
    palette.setColor(role.ButtonText, QColor(p.label))
    palette.setColor(role.Highlight, QColor(p.accent))
    palette.setColor(role.HighlightedText, QColor(p.on_accent))
    palette.setColor(role.ToolTipBase, QColor(p.elevated))
    palette.setColor(role.ToolTipText, QColor(p.label))
    palette.setColor(role.PlaceholderText, QColor(p.tertiary))
    palette.setColor(role.Link, QColor(p.accent))
    if hasattr(role, "Accent"):
        palette.setColor(role.Accent, QColor(p.accent))
    for group in (QPalette.ColorGroup.Disabled,):
        palette.setColor(group, role.WindowText, QColor(p.tertiary))
        palette.setColor(group, role.Text, QColor(p.tertiary))
        palette.setColor(group, role.ButtonText, QColor(p.tertiary))
    app.setPalette(palette)
    app.setStyleSheet(stylesheet(p))
    notifier().changed.emit()
    return p


# MARK: - スタイルシート


def _rgba(hex_color: str, alpha: float) -> str:
    c = QColor(hex_color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha:.3f})"


def _icon_file(name: str, color: str) -> str:
    """スタイルシートの `image:` で使えるよう、色付きの SVG をファイルに書き出す。"""
    path = _icon_dir / f"{name}-{color.lstrip('#')}.svg"
    if not path.exists():
        path.write_text(svg(name, color), encoding="utf-8")
    return path.as_posix()


def stylesheet(p: Palette) -> str:
    chevron = _icon_file("chevron.down", p.secondary)
    chevron_disabled = _icon_file("chevron.down", p.tertiary)
    mono = ", ".join(f'"{f}"' for f in MONO_FAMILIES)
    return f"""
QWidget {{
    color: {p.label};
    font-size: 13px;
}}
QMainWindow, QDialog, #root {{
    background: {p.window};
}}
QLabel {{ background: transparent; }}
QLabel:disabled {{ color: {p.tertiary}; }}

/* グループ（カード） */
#card {{
    background: {p.card};
    border: 1px solid {p.separator};
    border-radius: 12px;
}}
#separator {{ background: {p.separator}; min-height: 1px; max-height: 1px; border: none; }}
#sectionHeader {{
    color: {p.secondary};
    font-size: 12px;
    font-weight: 600;
    padding-left: 4px;
}}
#largeTitle {{ font-size: 22px; font-weight: 700; }}
#title {{ font-size: 15px; font-weight: 600; }}
#secondary {{ color: {p.secondary}; }}
#footnote {{ color: {p.secondary}; font-size: 12px; }}
#caption {{ color: {p.secondary}; font-size: 11px; }}
#rowTitle {{ font-size: 13px; }}
#rowDetail {{ color: {p.secondary}; font-size: 11px; }}

/* URL 入力 */
QLineEdit {{
    background: {p.field};
    border: 1px solid {p.separator};
    border-radius: 8px;
    padding: 5px 8px;
    selection-background-color: {p.accent};
    selection-color: {p.on_accent};
}}
QLineEdit:focus {{ border: 1px solid {p.accent}; }}
QLineEdit#urlField {{
    font-size: 15px;
    padding: 10px 8px;
    border-radius: 10px;
}}

/* ボタン */
QPushButton {{
    background: {p.fill};
    border: none;
    border-radius: 7px;
    padding: 6px 14px;
    min-height: 18px;
}}
QPushButton:hover {{ background: {p.fill_hover}; }}
QPushButton:pressed {{ background: {p.fill_pressed}; }}
QPushButton:disabled {{ color: {p.tertiary}; background: {_rgba(p.fill, 0.6)}; }}
QPushButton:focus {{ outline: none; }}
QPushButton#primary {{
    background: {p.accent};
    color: {p.on_accent};
    font-weight: 600;
    border-radius: 9px;
    padding: 9px 20px;
}}
QPushButton#primary:hover {{ background: {QColor(p.accent).lighter(108).name()}; }}
QPushButton#primary:pressed {{ background: {QColor(p.accent).darker(112).name()}; }}
QPushButton#primary:disabled {{
    background: {_rgba(p.accent, 0.35)};
    color: {_rgba(p.on_accent, 0.75)};
}}
QPushButton#large {{ padding: 9px 16px; border-radius: 9px; }}
QPushButton#plain, QToolButton#plain {{
    background: transparent;
    border: none;
    padding: 4px;
    border-radius: 6px;
}}
QPushButton#plain:hover, QToolButton#plain:hover {{ background: {p.fill}; }}
QPushButton#link {{
    background: transparent;
    color: {p.accent};
    padding: 2px 4px;
}}
QPushButton#link:hover {{ text-decoration: underline; }}

QToolButton {{
    background: transparent;
    border: none;
    border-radius: 7px;
    padding: 5px 8px;
}}
QToolButton:hover {{ background: {p.fill}; }}
QToolButton:pressed {{ background: {p.fill_pressed}; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}

/* ポップアップ */
QComboBox {{
    background: {p.fill};
    border: none;
    border-radius: 7px;
    padding: 5px 30px 5px 11px;
    min-height: 18px;
}}
QComboBox:hover {{ background: {p.fill_hover}; }}
QComboBox:disabled {{ color: {p.tertiary}; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ image: url("{chevron}"); width: 12px; height: 12px; }}
QComboBox::down-arrow:disabled {{ image: url("{chevron_disabled}"); }}
QComboBox QAbstractItemView {{
    background: {p.elevated};
    border: 1px solid {p.separator};
    border-radius: 8px;
    padding: 4px;
    outline: 0;
    selection-background-color: {p.accent};
    selection-color: {p.on_accent};
}}

QMenu {{
    background: {p.elevated};
    border: 1px solid {p.separator};
    border-radius: 10px;
    padding: 5px;
}}
QMenu::item {{
    padding: 6px 22px 6px 12px;
    border-radius: 6px;
    background: transparent;
}}
QMenu::item:selected {{ background: {p.accent}; color: {p.on_accent}; }}
QMenu::item:disabled {{ color: {p.secondary}; }}
QMenu::separator {{ height: 1px; background: {p.separator}; margin: 5px 8px; }}
QMenu::section {{
    color: {p.secondary};
    font-size: 11px;
    font-weight: 600;
    padding: 6px 12px 2px 12px;
    background: transparent;
}}
QMenu::icon {{ padding-left: 8px; }}

QToolTip {{
    background: {p.elevated};
    color: {p.label};
    border: 1px solid {p.separator};
    border-radius: 6px;
    padding: 4px 8px;
}}

/* ログ */
QTextEdit#log {{
    background: {p.log};
    border: none;
    border-top: 1px solid {p.separator};
    font-family: {mono};
    font-size: 11px;
    padding: 8px 14px;
    selection-background-color: {p.accent};
}}
#logPanel {{ background: {p.window}; }}
#actionBar {{
    background: {p.bar};
    border-top: 1px solid {p.separator};
}}
#banner {{
    background: {_rgba(p.accent, 0.12)};
    border: 1px solid {_rgba(p.accent, 0.35)};
    border-radius: 10px;
}}

/* スクロールバー（細く、背景に溶け込ませる） */
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: {_rgba(p.secondary, 0.45)};
    border-radius: 3px;
    min-height: 30px;
    margin: 0 2px;
}}
QScrollBar::handle:vertical:hover {{ background: {_rgba(p.secondary, 0.7)}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollBar:horizontal {{ height: 0; }}

QMessageBox QLabel {{ font-size: 13px; }}
"""


# MARK: - アイコン
#
# SF Symbols は Apple 製品以外での利用が許されていないため、同じ考え方
# （線の太さを揃えた、角の丸いアウトライン）で独自に描いている。
# viewBox は 24×24。`{fg}` が前景色、`{bg}` が背景色（塗りつぶしアイコンの抜き）。

_ICONS: dict[str, str] = {
    "link": '<g transform="rotate(-45 12 12)"><rect x="2.5" y="8.5" width="11" height="7" '
    'rx="3.5"/><rect x="10.5" y="8.5" width="11" height="7" rx="3.5"/></g>',
    "clipboard": '<rect x="5" y="4.5" width="14" height="16.5" rx="2.5"/>'
    '<rect x="8.8" y="2.8" width="6.4" height="3.6" rx="1.2" fill="{bg}"/>'
    '<path d="M9 12h6M9 16h4"/>',
    "xmark.circle.fill": '<circle cx="12" cy="12" r="9" fill="{fg}" stroke="none"/>'
    '<path d="M9.2 9.2l5.6 5.6M14.8 9.2l-5.6 5.6" stroke="{bg}" stroke-width="2"/>',
    "folder": '<path d="M3 7.5A2.5 2.5 0 0 1 5.5 5h3.6l2.1 2.1h7.3A2.5 2.5 0 0 1 21 9.6v7.9'
    'a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z"/>',
    "arrow.up.forward.square": '<path d="M13.5 4.5H19.5V10.5M19.5 4.5l-8.5 8.5"/>'
    '<path d="M18 14v4.5a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 4 18.5v-11A1.5 1.5 0 0 1 '
    '5.5 6H10"/>',
    "arrow.down.circle.fill": '<circle cx="12" cy="12" r="9.5" fill="{fg}" stroke="none"/>'
    '<path d="M12 7v9.5M8 12.7l4 4 4-4" stroke="{bg}" stroke-width="2"/>',
    "arrow.down.to.line": '<path d="M12 3.5v12M7 10.5l5 5 5-5M5 20.5h14"/>',
    "slider": '<path d="M4 7h9M18.5 7H20M4 17h3.5M12.5 17H20"/><circle cx="15.8" cy="7" '
    'r="2.4"/><circle cx="10" cy="17" r="2.4"/>',
    "chevron.right": '<path d="M9.5 5.5L16 12l-6.5 6.5"/>',
    "chevron.down": '<path d="M5.5 9.5L12 16l6.5-6.5" stroke-width="2.4"/>',
    "checkmark.circle.fill": '<circle cx="12" cy="12" r="9.5" fill="{fg}" stroke="none"/>'
    '<path d="M7.8 12.4l2.8 2.8 5.6-6" stroke="{bg}" stroke-width="2"/>',
    "checkmark.seal": '<path d="M12 2.8l2.2 1.6 2.7-.2.9 2.6 2.3 1.5-.6 2.7 1 2.5-2 1.8-.4 '
    "2.7-2.7.5-1.6 2.2-2.6-.9-2.6.9-1.6-2.2-2.7-.5-.4-2.7-2-1.8 1-2.5-.6-2.7 2.3-1.5.9-2.6 "
    '2.7.2z"/><path d="M8.5 12.2l2.4 2.4 4.6-4.8"/>',
    "exclamationmark.triangle.fill": '<path d="M10.3 4.2a2 2 0 0 1 3.4 0l7.6 13.2A2 2 0 0 1 '
    '19.6 20.4H4.4a2 2 0 0 1-1.7-3z" fill="{fg}" stroke="none"/><path d="M12 9v4.6" '
    'stroke="{bg}" stroke-width="2.1"/><circle cx="12" cy="16.9" r="1.2" fill="{bg}" '
    'stroke="none"/>',
    "xmark.octagon.fill": '<path d="M8.3 3h7.4L21 8.3v7.4L15.7 21H8.3L3 15.7V8.3z" '
    'fill="{fg}" stroke="none"/><path d="M9.2 9.2l5.6 5.6M14.8 9.2l-5.6 5.6" stroke="{bg}" '
    'stroke-width="2"/>',
    "minus.circle.fill": '<circle cx="12" cy="12" r="9.5" fill="{fg}" stroke="none"/>'
    '<path d="M8 12h8" stroke="{bg}" stroke-width="2.2"/>',
    "film": '<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M7.5 5v14M16.5 '
    '5v14M3 9.7h4.5M3 14.3h4.5M16.5 9.7H21M16.5 14.3H21"/>',
    "music.note": '<path d="M9 17.5V6.2l10.5-2v11.3"/><circle cx="6.6" cy="17.6" r="2.5"/>'
    '<circle cx="17" cy="15.6" r="2.5"/>',
    "sparkles": '<path d="M11 3.5l1.7 4.8 4.8 1.7-4.8 1.7L11 16.5l-1.7-4.8L4.5 10l4.8-1.7z"/>'
    '<path d="M18 14.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"/>',
    "arrow.clockwise": '<path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3"/><path d="M19.8 4v4.2h-4.2"/>',
    "ellipsis.circle": '<circle cx="12" cy="12" r="9"/><circle cx="8" cy="12" r=".6" '
    'fill="{fg}"/><circle cx="12" cy="12" r=".6" fill="{fg}"/><circle cx="16" cy="12" '
    'r=".6" fill="{fg}"/>',
    "wrench": '<path d="M14.7 6.3a4.2 4.2 0 0 0 5 5.4l-8.6 8.6a2.1 2.1 0 0 1-3-3l8.6-8.6a4.2 '
    '4.2 0 0 0-2-2.4z"/><path d="M14.7 6.3a4.2 4.2 0 0 1 5.6-1l-2.8 2.8.4 2.2 2.2.4 2.8-2.8"/>',
    "list.bullet": '<path d="M9 6.5h11M9 12h11M9 17.5h11"/><circle cx="4.8" cy="6.5" r=".9" '
    'fill="{fg}"/><circle cx="4.8" cy="12" r=".9" fill="{fg}"/><circle cx="4.8" cy="17.5" '
    'r=".9" fill="{fg}"/>',
    "info.circle": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5"/><circle cx="12" '
    'cy="7.8" r=".9" fill="{fg}" stroke="none"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.7 5.6 3.7 9s-1.2 '
    '6.4-3.7 9c-2.5-2.6-3.7-5.6-3.7-9S9.5 5.6 12 3z"/>',
    "stop.fill": '<rect x="6" y="6" width="12" height="12" rx="2.5" fill="{fg}" stroke="none"/>',
}


def svg(name: str, color: str, background: str | None = None) -> str:
    body = _ICONS[name].replace("{fg}", color).replace("{bg}", background or current().card)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'
        f"{body}</svg>"
    )


def pixmap(name: str, color: str | QColor, size: int, background: str | None = None) -> QPixmap:
    """高解像度ディスプレイでもぼやけないよう、画面の倍率に合わせて描く。"""
    if isinstance(color, QColor):
        color = color.name()
    screen = QGuiApplication.primaryScreen()
    ratio = max(screen.devicePixelRatio() if screen else 2.0, 2.0)
    renderer = QSvgRenderer(QByteArray(svg(name, color, background).encode()))
    image = QPixmap(round(size * ratio), round(size * ratio))
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, image.width(), image.height()))
    painter.end()
    image.setDevicePixelRatio(ratio)
    return image


def icon(
    name: str, color: str | None = None, size: int = 18, background: str | None = None
) -> QIcon:
    p = current()
    result = QIcon()
    result.addPixmap(pixmap(name, color or p.label, size, background), QIcon.Mode.Normal)
    result.addPixmap(pixmap(name, p.tertiary, size, background), QIcon.Mode.Disabled)
    return result


def bind_icon(widget, name: str, color: str = "label", size: int = 18) -> None:
    """ボタンにアイコンを付け、外観が変わったら色を付け直す。`color` は Palette の項目名。"""

    def refresh() -> None:
        p = current()
        widget.setIcon(icon(name, getattr(p, color, color), size))
        widget.setIconSize(QSize(size, size))

    refresh()
    notifier().changed.connect(refresh)


def icon_size(size: int = 18) -> QSize:
    return QSize(size, size)


def configure_application_font(app: QApplication) -> None:
    font = QFont(ui_font_family())
    # Windows の既定 9pt は小さいので、macOS の本文（13px）に揃える
    if IS_WINDOWS:
        font.setPointSizeF(10)
    elif IS_MACOS:
        font.setPointSizeF(13)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)
