"""yt-dlp / ffmpeg / aria2c の公式配布物の場所（OS と CPU ごと）。"""

from __future__ import annotations

from dataclasses import dataclass

from clipcatch.core.platform import IS_MACOS, IS_WINDOWS, executable_name, machine

YTDLP_RELEASE_API = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
ARIA2_RELEASE_API = "https://api.github.com/repos/aria2/aria2/releases/latest"
SUPPORTED_SITES_URL = "https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md"

_YTDLP_BASE = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/"
_FFMPEG_BUILDS = "https://github.com/yt-dlp/FFmpeg-Builds/releases/latest/download/"
_RIEDL = "https://ffmpeg.martin-riedl.de/redirect/latest/macos/{arch}/release/{name}.zip"
_EVERMEET = "https://evermeet.cx/ffmpeg/getrelease/{name}/zip"


@dataclass(frozen=True)
class ArchiveSource:
    """取り出すべき実行ファイルを含むアーカイブ 1 つ。"""

    url: str
    members: tuple[str, ...]


def ytdlp_download_url(system_machine: str | None = None) -> str:
    """公式のスタンドアロン版。Python が無くても動く。"""
    arch = system_machine or machine()
    if IS_MACOS:
        return _YTDLP_BASE + "yt-dlp_macos"  # universal binary
    if IS_WINDOWS:
        return _YTDLP_BASE + ("yt-dlp_arm64.exe" if arch == "arm64" else "yt-dlp.exe")
    return _YTDLP_BASE + ("yt-dlp_linux_aarch64" if arch == "arm64" else "yt-dlp_linux")


def ffmpeg_sources(system_machine: str | None = None) -> list[list[ArchiveSource]]:
    """ffmpeg と ffprobe の取得元。先頭から順に試し、失敗したら次の候補に移る。"""
    arch = system_machine or machine()
    ffmpeg, ffprobe = executable_name("ffmpeg"), executable_name("ffprobe")
    if IS_MACOS:
        riedl_arch = "arm64" if arch == "arm64" else "amd64"
        return [
            # Apple Silicon ネイティブの静的ビルド
            [
                ArchiveSource(_RIEDL.format(arch=riedl_arch, name="ffmpeg"), (ffmpeg,)),
                ArchiveSource(_RIEDL.format(arch=riedl_arch, name="ffprobe"), (ffprobe,)),
            ],
            # 予備: Intel 向け静的ビルド（Apple Silicon では Rosetta で動く）
            [
                ArchiveSource(_EVERMEET.format(name="ffmpeg"), (ffmpeg,)),
                ArchiveSource(_EVERMEET.format(name="ffprobe"), (ffprobe,)),
            ],
        ]
    if IS_WINDOWS:
        name = "winarm64" if arch == "arm64" else "win64"
        url = _FFMPEG_BUILDS + f"ffmpeg-master-latest-{name}-gpl.zip"
        return [[ArchiveSource(url, (ffmpeg, ffprobe))]]
    name = "linuxarm64" if arch == "arm64" else "linux64"
    url = _FFMPEG_BUILDS + f"ffmpeg-master-latest-{name}-gpl.tar.xz"
    return [[ArchiveSource(url, (ffmpeg, ffprobe))]]


def deno_source(system_machine: str | None = None) -> ArchiveSource:
    """yt-dlp が YouTube の解析に使う JavaScript ランタイム（Deno）。"""
    arch = "aarch64" if (system_machine or machine()) == "arm64" else "x86_64"
    if IS_MACOS:
        target = f"{arch}-apple-darwin"
    elif IS_WINDOWS:
        target = f"{arch}-pc-windows-msvc"
    else:
        target = f"{arch}-unknown-linux-gnu"
    url = f"https://github.com/denoland/deno/releases/latest/download/deno-{target}.zip"
    return ArchiveSource(url, (executable_name("deno"),))


def aria2_asset_name_matches(name: str, system_machine: str | None = None) -> bool:
    """aria2 の GitHub リリースのうち Windows 用 zip を選ぶ。"""
    arch = system_machine or machine()
    bits = "32bit" if arch in ("x86", "i386", "i686") else "64bit"
    return name.endswith(".zip") and f"win-{bits}" in name


def ytdlp_checksums_url() -> str:
    return _YTDLP_BASE + "SHA2-256SUMS"


def parse_checksums(text: str) -> dict[str, str]:
    """`sha256sum` 形式（`<hex>  <name>`）を名前→ハッシュの辞書にする。"""
    result: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) == 2 and len(parts[0]) == 64:
            result[parts[1].lstrip("*")] = parts[0].lower()
    return result
