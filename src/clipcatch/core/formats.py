"""保存形式・最大解像度・Cookie の取得元。yt-dlp に渡す指定もここで決める。"""

from __future__ import annotations

from enum import Enum

from clipcatch.core.i18n import tr
from clipcatch.core.platform import IS_MACOS


class DownloadFormat(str, Enum):
    MP4 = "mp4"
    BEST_VIDEO = "bestVideo"
    MP3 = "mp3"
    M4A = "m4a"

    @property
    def title(self) -> str:
        return {
            DownloadFormat.MP4: "MP4",
            DownloadFormat.BEST_VIDEO: tr("最高画質", "Best"),
            DownloadFormat.MP3: "MP3",
            DownloadFormat.M4A: "M4A",
        }[self]

    @property
    def summary(self) -> str:
        return {
            DownloadFormat.MP4: tr(
                "H.264 の MP4。ほとんどの機器でそのまま再生できます。",
                "H.264 MP4 that plays on almost any device.",
            ),
            DownloadFormat.BEST_VIDEO: tr(
                "サイトが配信する最良の映像と音声。VP9 / AV1 になることがあります。",
                "The best video and audio the site offers. May be VP9 or AV1.",
            ),
            DownloadFormat.MP3: tr(
                "音声だけを MP3（192 kbps）に変換して保存します。",
                "Extracts the audio and converts it to MP3 (192 kbps).",
            ),
            DownloadFormat.M4A: tr(
                "音声だけを変換せずそのまま保存します（最速）。",
                "Saves the original audio track without re-encoding (fastest).",
            ),
        }[self]

    @property
    def is_audio_only(self) -> bool:
        return self in (DownloadFormat.MP3, DownloadFormat.M4A)

    @property
    def requires_ffmpeg(self) -> bool:
        """映像と音声の結合、および MP3 変換に ffmpeg が要る。
        M4A は単一ストリームをそのまま保存するだけなので不要。"""
        return self is not DownloadFormat.M4A

    def format_selector(self, max_height: int | None) -> str:
        """yt-dlp の `-f` に渡すフォーマット選択式。"""
        if self is DownloadFormat.MP3:
            return "bestaudio/best"
        if self is DownloadFormat.M4A:
            return "bestaudio[ext=m4a]/bestaudio/best"
        if self is DownloadFormat.BEST_VIDEO:
            if max_height:
                h = max_height
                return f"bestvideo[height<={h}]+bestaudio/best[height<={h}]/best"
            return "bestvideo+bestaudio/best"
        if max_height:
            h = max_height
            return (
                f"bestvideo[ext=mp4][vcodec^=avc][height<={h}]+bestaudio[ext=m4a]"
                f"/bestvideo[ext=mp4][vcodec^=avc][height<={h}]+bestaudio"
                f"/best[ext=mp4][height<={h}]/best[height<={h}]/best"
            )
        return (
            "bestvideo[ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]"
            "/bestvideo[ext=mp4][vcodec^=avc]+bestaudio/best[ext=mp4]/best"
        )

    @property
    def post_processing_arguments(self) -> list[str]:
        if self is DownloadFormat.MP3:
            return ["-x", "--audio-format", "mp3", "--audio-quality", "192K"]
        return []


class VideoQuality(str, Enum):
    UNLIMITED = "unlimited"
    UHD_2160 = "uhd2160"
    QHD_1440 = "qhd1440"
    FHD_1080 = "fhd1080"
    HD_720 = "hd720"
    SD_480 = "sd480"

    @property
    def title(self) -> str:
        return {
            VideoQuality.UNLIMITED: tr("制限なし", "No limit"),
            VideoQuality.UHD_2160: "4K (2160p)",
            VideoQuality.QHD_1440: "2K (1440p)",
            VideoQuality.FHD_1080: tr("フル HD (1080p)", "Full HD (1080p)"),
            VideoQuality.HD_720: "HD (720p)",
            VideoQuality.SD_480: "SD (480p)",
        }[self]

    @property
    def max_height(self) -> int | None:
        return {
            VideoQuality.UNLIMITED: None,
            VideoQuality.UHD_2160: 2160,
            VideoQuality.QHD_1440: 1440,
            VideoQuality.FHD_1080: 1080,
            VideoQuality.HD_720: 720,
            VideoQuality.SD_480: 480,
        }[self]


class CookieBrowser(str, Enum):
    """`--cookies-from-browser` に渡すブラウザ。"""

    NONE = "none"
    SAFARI = "safari"
    CHROME = "chrome"
    EDGE = "edge"
    FIREFOX = "firefox"
    BRAVE = "brave"

    @classmethod
    def available(cls) -> list[CookieBrowser]:
        """この OS で選べるもの。Safari は macOS だけ。"""
        return [b for b in cls if b is not cls.SAFARI or IS_MACOS]

    @property
    def title(self) -> str:
        if self is CookieBrowser.NONE:
            return tr("使わない", "Don't use")
        return {
            CookieBrowser.SAFARI: "Safari",
            CookieBrowser.CHROME: "Chrome",
            CookieBrowser.EDGE: "Edge",
            CookieBrowser.FIREFOX: "Firefox",
            CookieBrowser.BRAVE: "Brave",
        }[self]

    @property
    def arguments(self) -> list[str]:
        return [] if self is CookieBrowser.NONE else ["--cookies-from-browser", self.value]
