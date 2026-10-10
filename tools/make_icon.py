"""ClipCatch のアプリアイコンを作る。

    python tools/make_icon.py            # すべて作り直す
    python tools/make_icon.py --preview  # 1024px の確認用画像だけを書き出す

形は Apple の App Icon グリッド（1024 のキャンバスに 824 の本体、角はスーパー楕円）に
合わせる。各サイズを拡大縮小ではなくその大きさで直接描くので、16px でもぼやけない。
小さいサイズでは線を太くして形を保つ。

出力:
    src/clipcatch/assets/icon_<size>.png   実行時のウインドウアイコン
    packaging/icon.icns                     macOS（iconutil が必要）
    packaging/icon.ico                      Windows（Pillow が必要）
"""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "src" / "clipcatch" / "assets"
PACKAGING = ROOT / "packaging"
RUNTIME_SIZES = [16, 32, 64, 128, 256, 512, 1024]
ICNS_SIZES = [16, 32, 64, 128, 256, 512, 1024]
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]

TOP = QColor("#7B61FF")  # 紫がかった青
BOTTOM = QColor("#1E7BFF")  # 鮮やかな青


def squircle(rect: QRectF, exponent: float = 5.0, steps: int = 720) -> QPainterPath:
    """スーパー楕円（|x|^n + |y|^n = 1）で、Apple のアイコンと同じ連続的な角を作る。"""
    cx, cy = rect.center().x(), rect.center().y()
    rx, ry = rect.width() / 2, rect.height() / 2
    path = QPainterPath()
    for i in range(steps + 1):
        t = 2 * math.pi * i / steps
        c, s = math.cos(t), math.sin(t)
        x = cx + rx * math.copysign(abs(c) ** (2 / exponent), c)
        y = cy + ry * math.copysign(abs(s) ** (2 / exponent), s)
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    path.closeSubpath()
    return path


def draw(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 1024, size / 1024)

    # 小さいサイズでは影を省き、本体をキャンバスいっぱいに近づける
    small = size <= 32
    body = QRectF(100, 100, 824, 824) if not small else QRectF(40, 40, 944, 944)
    shape = squircle(body)

    if not small:
        for offset, alpha in ((18, 0.10), (10, 0.12), (4, 0.16)):
            p.fillPath(shape.translated(0, offset), QColor(0, 0, 0, round(255 * alpha)))

    gradient = QLinearGradient(body.topLeft(), body.bottomRight())
    gradient.setColorAt(0, TOP)
    gradient.setColorAt(1, BOTTOM)
    p.fillPath(shape, gradient)

    # 上からの柔らかい光（立体感）
    glow = QRadialGradient(QPointF(body.center().x(), body.top()), body.width() * 0.9)
    glow.setColorAt(0, QColor(255, 255, 255, 70))
    glow.setColorAt(1, QColor(255, 255, 255, 0))
    p.fillPath(shape, glow)

    # 縁のハイライト
    if not small:
        p.setPen(QPen(QColor(255, 255, 255, 40), 3))
        p.drawPath(shape)

    white = QColor("#FFFFFF")
    cx, cy = body.center().x(), body.center().y()
    scale = body.width() / 824

    # ファインダーの四隅（クリップを「捕まえる」枠）
    stroke = (58 if small else 44) * scale
    pen = QPen(white, stroke)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    half = 250 * scale
    arm = 112 * scale
    radius = 60 * scale
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        corner = QPointF(cx + sx * half, cy + sy * half)
        path = QPainterPath()
        path.moveTo(corner.x(), corner.y() - sy * arm)
        path.lineTo(corner.x(), corner.y() - sy * radius)
        path.quadTo(corner, QPointF(corner.x() - sx * radius, corner.y()))
        path.lineTo(corner.x() - sx * arm, corner.y())
        p.drawPath(path)

    # 中央の下向き矢印（保存）
    arrow = QPen(white, (70 if small else 54) * scale)
    arrow.setCapStyle(Qt.PenCapStyle.RoundCap)
    arrow.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(arrow)
    top, tip = cy - 120 * scale, cy + 105 * scale
    wing = 92 * scale
    p.drawLine(QPointF(cx, top), QPointF(cx, tip))
    head = QPainterPath()
    head.moveTo(cx - wing, tip - wing)
    head.lineTo(cx, tip)
    head.lineTo(cx + wing, tip - wing)
    p.drawPath(head)

    p.end()
    return image


def write_runtime_pngs() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    for size in RUNTIME_SIZES:
        draw(size).save(str(ASSETS / f"icon_{size}.png"))


def write_icns() -> None:
    if shutil.which("iconutil") is None:
        print("iconutil が無いため icon.icns は作りません（macOS でのみ作成できます）")
        return
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "icon.iconset"
        iconset.mkdir()
        for size in ICNS_SIZES[:-1]:
            draw(size).save(str(iconset / f"icon_{size}x{size}.png"))
            draw(size * 2).save(str(iconset / f"icon_{size}x{size}@2x.png"))
        PACKAGING.mkdir(exist_ok=True)
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(PACKAGING / "icon.icns")],
            check=True,
        )


def write_ico() -> None:
    try:
        from PIL import Image
    except ImportError:
        print("Pillow が無いため icon.ico は作りません（pip install pillow）")
        return
    with tempfile.TemporaryDirectory() as tmp:
        frames = []
        for size in ICO_SIZES:
            path = Path(tmp) / f"{size}.png"
            draw(size).save(str(path))
            frames.append(Image.open(path).convert("RGBA"))
        PACKAGING.mkdir(exist_ok=True)
        largest = frames[-1]
        largest.save(
            PACKAGING / "icon.ico",
            format="ICO",
            sizes=[(s, s) for s in ICO_SIZES],
            append_images=frames[:-1],
        )


def main() -> None:
    QGuiApplication([*sys.argv[:1], "-platform", "offscreen"])
    if "--preview" in sys.argv:
        out = ROOT / "dist" / "icon-preview.png"
        out.parent.mkdir(exist_ok=True)
        draw(1024).save(str(out))
        print(out)
        return
    write_runtime_pngs()
    write_icns()
    write_ico()
    print("icons written")


if __name__ == "__main__":
    main()
