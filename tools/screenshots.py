"""README 用のスクリーンショットを作る（画面には何も表示しない）。

    python tools/screenshots.py            # docs/ に日本語・英語 × ライト・ダークを書き出す

実際に yt-dlp で動画情報を取得するため、ネットワークに接続している必要がある。
設定は一時ファイルに保存するので、普段使いの設定には影響しない。
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "2")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QCoreApplication, QDeadlineTimer, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

# Blender Foundation の短編映画（CC BY 3.0）
SAMPLE_URL = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
OUT = ROOT / "docs"


def main() -> None:
    QCoreApplication.setOrganizationName("ClipCatchScreenshots")
    QCoreApplication.setApplicationName("ClipCatchScreenshots")
    app = QApplication(sys.argv[:1])
    from clipcatch.ui import theme

    theme.capture_system_accent(app)
    app.setStyle("Fusion")

    from clipcatch.controller import AppController
    from clipcatch.core import i18n
    from clipcatch.core.models import Phase, TransferProgress
    from clipcatch.services.settings import Settings
    from clipcatch.ui.main_window import MainWindow

    theme.configure_application_font(app)

    def spin(predicate, ms: int) -> None:
        deadline = QDeadlineTimer(ms)
        while not predicate() and not deadline.hasExpired():
            app.processEvents()

    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for language in ("ja", "en"):
            i18n.set_language(language)
            for dark in (False, True):
                theme.apply(app, dark=dark)
                store = QSettings(
                    str(Path(tmp) / f"{language}{dark}.ini"), QSettings.Format.IniFormat
                )
                controller = AppController(Settings(store))
                window = MainWindow(controller)
                window.resize(640, 720)
                window.show()
                controller.bootstrap()
                spin(
                    lambda c=controller: c.toolchain.ytdlp.ready and c.toolchain.deno.ready, 180_000
                )
                controller.set_url(SAMPLE_URL)
                spin(lambda c=controller: c.media_info or c.metadata_error, 90_000)
                spin(lambda: False, 3000)  # サムネイルの読み込み待ち

                controller.phase = Phase.DOWNLOADING
                controller.progress = TransferProgress(
                    fraction=0.62,
                    downloaded_bytes=186_400_000,
                    total_bytes=301_200_000,
                    bytes_per_second=24_800_000,
                    eta_seconds=5,
                    file_name="Big Buck Bunny.mp4",
                )
                controller.status_text = "Big Buck Bunny.mp4"
                controller.changed.emit()
                spin(lambda: False, 800)
                name = f"screenshot-{language}-{'dark' if dark else 'light'}.png"
                window.grab().save(str(OUT / name))
                print(OUT / name)
                controller.phase = Phase.IDLE
                window.close()
                window.deleteLater()


if __name__ == "__main__":
    main()
