# PyInstaller の設定。直接ではなく packaging/build.py から使う。
#
# onedir で作る。onefile は起動のたびに一時フォルダへ展開するので遅く、
# ウイルス対策ソフトに誤検知されやすい。また PySide6（LGPL）のライブラリを
# 利用者が差し替えられる形にしておくためでもある。

import os
import re
import sys
import sysconfig
from pathlib import Path

ROOT = Path(SPECPATH).parent  # noqa: F821 (PyInstaller が定義する)
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

VERSION = re.search(
    r'__version__ = "([^"]+)"', (SRC / "clipcatch" / "__init__.py").read_text(encoding="utf-8")
).group(1)
APP_NAME = "ClipCatch"
BUNDLE_ID = "io.github.myuto2490.clipcatch"
TARGET_ARCH = os.environ.get("CLIPCATCH_TARGET_ARCH") or None

# 使っていない Qt のモジュール。入れると配布物が数百 MB 増える。
EXCLUDES = [
    "tkinter",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtMultimedia",
    "PySide6.QtPdf",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.Qt3DCore",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtDesigner",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
]

# 配布物に同梱するライセンス文書。LGPL-3.0（Qt / PySide6）は、ライブラリと一緒に
# LGPL と GPL の全文を渡すことを求めている。Python 本体のライセンスは、ビルドに使った
# インタプリタに付属するもの（同梱ライブラリの表示を含む）をそのまま入れる。
LICENSE_STAGING = Path(workpath) / "licenses"  # noqa: F821
LICENSE_STAGING.mkdir(parents=True, exist_ok=True)
for source in [
    ROOT / "LICENSE",
    ROOT / "THIRD_PARTY_NOTICES.md",
    *sorted((ROOT / "LICENSES").glob("*.txt")),
]:
    (LICENSE_STAGING / source.name).write_bytes(source.read_bytes())
python_license = Path(sysconfig.get_paths()["stdlib"]) / "LICENSE.txt"
if python_license.exists():
    (LICENSE_STAGING / "Python-LICENSE.txt").write_bytes(python_license.read_bytes())

a = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(SRC)],
    datas=[
        (str(SRC / "clipcatch" / "assets"), "clipcatch/assets"),
        (str(LICENSE_STAGING), "licenses"),
    ],
    hiddenimports=["PySide6.QtSvg"],
    excludes=EXCLUDES,
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

version_file = None
if sys.platform == "win32":
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo,
        StringFileInfo,
        StringStruct,
        StringTable,
        VarFileInfo,
        VarStruct,
        VSVersionInfo,
    )

    numbers = tuple(int(n) for n in VERSION.split(".")) + (0,)
    version_file = VSVersionInfo(
        ffi=FixedFileInfo(filevers=numbers, prodvers=numbers),
        kids=[
            StringFileInfo(
                [
                    StringTable(
                        "040904B0",
                        [
                            StringStruct("CompanyName", "myuto2490"),
                            StringStruct("FileDescription", APP_NAME),
                            StringStruct("FileVersion", VERSION),
                            StringStruct("InternalName", APP_NAME),
                            StringStruct("LegalCopyright", "© 2026 myuto2490. MIT License."),
                            StringStruct("OriginalFilename", f"{APP_NAME}.exe"),
                            StringStruct("ProductName", APP_NAME),
                            StringStruct("ProductVersion", VERSION),
                        ],
                    )
                ]
            ),
            VarFileInfo([VarStruct("Translation", [1033, 1200])]),
        ],
    )

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    disable_windowed_traceback=False,
    target_arch=TARGET_ARCH,
    codesign_identity=None,  # 署名は build.py で .app 全体に行う
    icon=str(ROOT / "packaging" / ("icon.ico" if sys.platform == "win32" else "icon.icns")),
    version=version_file,
    upx=False,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)

if sys.platform == "darwin":
    app = BUNDLE(  # noqa: F821
        coll,
        name=f"{APP_NAME}.app",
        icon=str(ROOT / "packaging" / "icon.icns"),
        bundle_identifier=BUNDLE_ID,
        version=VERSION,
        info_plist={
            "CFBundleDisplayName": APP_NAME,
            "CFBundleName": APP_NAME,
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "CFBundleDevelopmentRegion": "en",
            # システムが出すメニュー項目（サービス・隠す など）を日本語にするため
            "CFBundleLocalizations": ["en", "ja"],
            "LSApplicationCategoryType": "public.app-category.utilities",
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            "NSSupportsAutomaticGraphicsSwitching": True,
            "NSHumanReadableCopyright": "© 2026 myuto2490. MIT License.",
        },
    )
