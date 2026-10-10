"""OS ごとの差（ファイルの置き場所・実行ファイル名・探す場所）をまとめる。"""

from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path

from clipcatch import APP_NAME

IS_MACOS = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"


def machine() -> str:
    """CPU アーキテクチャを `arm64` / `x86_64` に正規化して返す。"""
    value = platform.machine().lower()
    if value in ("arm64", "aarch64"):
        return "arm64"
    if value in ("x86_64", "amd64"):
        return "x86_64"
    return value


def executable_name(name: str) -> str:
    """`yt-dlp` → Windows では `yt-dlp.exe`。"""
    return f"{name}.exe" if IS_WINDOWS else name


def data_directory() -> Path:
    """書き込み可能なアプリ用ディレクトリ。

    アプリ本体（.app や Program Files）は書き換えない。署名が壊れたり、
    管理者権限が要ったりするため。
    """
    if IS_MACOS:
        base = Path.home() / "Library" / "Application Support"
    elif IS_WINDOWS:
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / APP_NAME


def tools_directory() -> Path:
    """自動取得した yt-dlp / ffmpeg / aria2c の置き場所。"""
    return data_directory() / "bin"


def managed_tool(name: str) -> Path:
    return tools_directory() / executable_name(name)


def extra_search_paths() -> list[str]:
    """GUI から起動したときの PATH に入らないことが多い、よくあるインストール先。"""
    if IS_MACOS:
        # Finder から起動した .app の PATH には Homebrew が入らない
        return ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]
    if IS_WINDOWS:
        local = os.environ.get("LOCALAPPDATA", "")
        program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        return [
            os.path.join(local, "Microsoft", "WinGet", "Links"),
            str(Path.home() / "scoop" / "shims"),
            os.path.join(program_data, "chocolatey", "bin"),
        ]
    return ["/usr/local/bin", "/usr/bin"]


def search_path() -> str:
    """現在の PATH によくあるインストール先を足したもの（重複は除く）。"""
    entries = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    for extra in extra_search_paths():
        if extra and extra not in entries:
            entries.append(extra)
    return os.pathsep.join(entries)


def find_on_system(name: str) -> Path | None:
    """PATH とよくあるインストール先から実行ファイルを探す。"""
    found = shutil.which(executable_name(name), path=search_path())
    return Path(found) if found else None


def is_executable(path: Path | None) -> bool:
    return bool(path) and path.is_file() and os.access(path, os.X_OK)


def process_environment(base: dict[str, str] | None = None) -> dict[str, str]:
    """子プロセス（yt-dlp など）に渡す環境変数。"""
    env = dict(os.environ if base is None else base)
    env["PATH"] = os.pathsep.join([search_path(), str(tools_directory())])
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    if IS_MACOS:
        env.setdefault("LC_ALL", "en_US.UTF-8")
    return env
