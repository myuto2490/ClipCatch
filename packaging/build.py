"""配布物を作る。

    python packaging/build.py              # この OS 向けの配布物を dist/ に作る
    python packaging/build.py --self-test  # 作ったあと起動確認まで行う

macOS:   dist/ClipCatch.app → 署名 → dist/ClipCatch-<ver>-macOS-<arch>.dmg
Windows: dist/ClipCatch/    → dist/ClipCatch-<ver>-Windows-x64.zip（ポータブル版）
                              dist/ClipCatch-<ver>-Windows-x64-Setup.exe（Inno Setup があれば）

署名と公証（どちらも任意）は環境変数で指定する:
    MACOS_SIGN_IDENTITY   "Developer ID Application: ..."。無ければ ad-hoc 署名
    MACOS_NOTARY_PROFILE  `xcrun notarytool store-credentials` で保存したプロファイル名
"""

from __future__ import annotations

import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
APP_NAME = "ClipCatch"


def version() -> str:
    text = (ROOT / "src" / "clipcatch" / "__init__.py").read_text(encoding="utf-8")
    return re.search(r'__version__ = "([^"]+)"', text).group(1)


def run(*args: str | Path, **kwargs) -> None:
    printable = " ".join(str(a) for a in args)
    print(f"▸ {printable}", flush=True)
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def arch() -> str:
    machine = platform.machine().lower()
    return "arm64" if machine in ("arm64", "aarch64") else "x64"


def pyinstaller() -> None:
    shutil.rmtree(BUILD, ignore_errors=True)
    shutil.rmtree(DIST / APP_NAME, ignore_errors=True)
    shutil.rmtree(DIST / f"{APP_NAME}.app", ignore_errors=True)
    run(
        sys.executable,
        "-m",
        "PyInstaller",
        ROOT / "packaging" / "clipcatch.spec",
        "--noconfirm",
        "--clean",
        "--distpath",
        DIST,
        "--workpath",
        BUILD,
    )


# MARK: - macOS


def sign_macos(app: Path) -> None:
    identity = os.environ.get("MACOS_SIGN_IDENTITY", "").strip()
    entitlements = ROOT / "packaging" / "macos" / "entitlements.plist"
    if identity:
        # 公証には Hardened Runtime と、中のすべてのバイナリへの署名が必要
        run(
            "codesign",
            "--force",
            "--deep",
            "--options",
            "runtime",
            "--timestamp",
            "--entitlements",
            entitlements,
            "--sign",
            identity,
            app,
        )
    else:
        print("MACOS_SIGN_IDENTITY が無いため ad-hoc 署名します（配布には公証が必要です）")
        run("codesign", "--force", "--deep", "--sign", "-", app)
    run("codesign", "--verify", "--deep", "--strict", "--verbose=2", app)


def make_dmg(app: Path, target: Path) -> None:
    """アプリと「アプリケーション」へのリンクを並べたディスクイメージを作る。"""
    target.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / APP_NAME
        staging.mkdir()
        run("ditto", app, staging / app.name)
        (staging / "Applications").symlink_to("/Applications")
        run(
            "hdiutil",
            "create",
            "-volname",
            APP_NAME,
            "-srcfolder",
            staging,
            "-fs",
            "HFS+",
            "-format",
            "ULFO",
            "-ov",
            target,
        )


def notarize(path: Path) -> None:
    profile = os.environ.get("MACOS_NOTARY_PROFILE", "").strip()
    if not profile:
        return
    run("xcrun", "notarytool", "submit", path, "--keychain-profile", profile, "--wait")
    run("xcrun", "stapler", "staple", path)


def build_macos() -> list[Path]:
    app = DIST / f"{APP_NAME}.app"
    sign_macos(app)
    dmg = DIST / f"{APP_NAME}-{version()}-macOS-{arch()}.dmg"
    make_dmg(app, dmg)
    if os.environ.get("MACOS_SIGN_IDENTITY"):
        run("codesign", "--force", "--sign", os.environ["MACOS_SIGN_IDENTITY"], dmg)
    notarize(dmg)
    return [dmg]


# MARK: - Windows


def build_windows() -> list[Path]:
    folder = DIST / APP_NAME
    portable = DIST / f"{APP_NAME}-{version()}-Windows-{arch()}"
    # with_suffix は「.0-Windows-x64」を拡張子とみなすため、作られたパスをそのまま使う
    outputs = [Path(shutil.make_archive(str(portable), "zip", DIST, APP_NAME))]

    iscc = shutil.which("iscc") or next(
        (
            p
            for p in (
                Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Inno Setup 6" / "ISCC.exe",
                Path(os.environ.get("PROGRAMFILES", "")) / "Inno Setup 6" / "ISCC.exe",
            )
            if p.is_file()
        ),
        None,
    )
    if iscc:
        run(
            iscc,
            f"/DAppVersion={version()}",
            f"/DSourceDir={folder}",
            f"/DOutputDir={DIST}",
            f"/DOutputName={APP_NAME}-{version()}-Windows-{arch()}-Setup",
            ROOT / "packaging" / "windows" / "clipcatch.iss",
        )
        outputs.append(DIST / f"{APP_NAME}-{version()}-Windows-{arch()}-Setup.exe")
    else:
        print("Inno Setup が見つからないため、インストーラは作りません")
    return outputs


# MARK: - 共通


def self_test() -> None:
    if sys.platform == "darwin":
        executable = DIST / f"{APP_NAME}.app" / "Contents" / "MacOS" / APP_NAME
    elif sys.platform == "win32":
        executable = DIST / APP_NAME / f"{APP_NAME}.exe"
    else:
        executable = DIST / APP_NAME / APP_NAME
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run(
        [str(executable), "--self-test"],
        env=env,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    print(result.stdout + result.stderr)
    if result.returncode != 0:
        raise SystemExit(f"self-test failed (exit {result.returncode})")
    print("✔ self-test passed")


def write_checksums(files: list[Path]) -> None:
    lines = []
    for file in files:
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
        lines.append(f"{digest}  {file.name}")
    checksum = DIST / f"SHA256SUMS-{platform.system()}-{arch()}.txt"
    checksum.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(checksum.read_text(encoding="utf-8"))


def main() -> None:
    # Windows の既定の文字コード（cp1252）では「▸」や日本語を出力できない
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    DIST.mkdir(exist_ok=True)
    pyinstaller()
    if "--self-test" in sys.argv:
        self_test()
    if sys.platform == "darwin":
        outputs = build_macos()
    elif sys.platform == "win32":
        outputs = build_windows()
    else:
        raise SystemExit("macOS と Windows 向けの配布物だけを作れます")
    write_checksums(outputs)
    for output in outputs:
        print(f"✔ {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
