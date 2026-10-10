"""画面とサービスの間で受け渡すデータ型。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from clipcatch.core import formatters
from clipcatch.core.i18n import tr


@dataclass(frozen=True)
class MediaInfo:
    """`yt-dlp -J` で取得した動画のメタデータ（ダウンロード前のプレビュー用）。"""

    title: str
    uploader: str | None = None
    duration_seconds: float | None = None
    thumbnail_url: str | None = None
    extractor: str | None = None
    is_live: bool = False
    playlist_count: int | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> MediaInfo:
        """プレイリストなら、その名前と件数・先頭の動画のサムネイルを見せる。"""
        playlist_count = None
        first: dict[str, Any] = data
        entries = data.get("entries")
        if isinstance(entries, list):
            playlist_count = len(entries)
            first = next((e for e in entries if isinstance(e, dict)), {})

        duration = data.get("duration") if playlist_count is None else None
        title = data.get("title") or first.get("title") or tr("（タイトル不明）", "(Untitled)")
        return cls(
            title=str(title),
            uploader=data.get("uploader") or data.get("channel") or first.get("uploader"),
            duration_seconds=float(duration) if isinstance(duration, (int, float)) else None,
            thumbnail_url=_thumbnail(data) or _thumbnail(first),
            extractor=data.get("extractor_key") or data.get("extractor"),
            is_live=bool(data.get("is_live")),
            playlist_count=playlist_count,
        )

    @property
    def duration_text(self) -> str | None:
        if self.duration_seconds is None:
            return None
        return formatters.clock(self.duration_seconds)


def _thumbnail(data: dict[str, Any]) -> str | None:
    """`thumbnail` が無ければ `thumbnails` の最後（最も大きいもの）を使う。"""
    if isinstance(data.get("thumbnail"), str):
        return data["thumbnail"]
    thumbnails = data.get("thumbnails")
    if isinstance(thumbnails, list):
        for item in reversed(thumbnails):
            if isinstance(item, dict) and isinstance(item.get("url"), str):
                return item["url"]
    return None


@dataclass
class TransferProgress:
    """ダウンロード進行状況の 1 スナップショット。"""

    fraction: float | None = None  # 0.0–1.0。不明なら None（不確定表示）
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    bytes_per_second: float | None = None
    eta_seconds: int | None = None
    file_name: str | None = None

    @property
    def detail_text(self) -> str:
        """「12.3 MB / 48.0 MB · 3.2 MB/s · 残り 12秒」のような補足行。"""
        parts: list[str] = []
        if self.downloaded_bytes is not None and self.total_bytes:
            done = formatters.file_size(self.downloaded_bytes)
            parts.append(f"{done} / {formatters.file_size(self.total_bytes)}")
        elif self.downloaded_bytes is not None:
            parts.append(formatters.file_size(self.downloaded_bytes))
        if self.bytes_per_second is not None:
            parts.append(formatters.speed(self.bytes_per_second))
        if self.eta_seconds is not None:
            eta = formatters.duration(self.eta_seconds)
            parts.append(tr(f"残り {eta}", f"{eta} left"))
        return "  ·  ".join(parts)


@dataclass(frozen=True)
class DownloadResult:
    """ダウンロード完了時に yt-dlp から受け取る結果。"""

    title: str
    resolution: str | None = None
    video_codec: str | None = None
    file_path: str | None = None


class Phase(Enum):
    IDLE = "idle"
    PREPARING = "preparing"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    FINISHED = "finished"
    CANCELLED = "cancelled"
    FAILED = "failed"

    @property
    def is_busy(self) -> bool:
        return self in (Phase.PREPARING, Phase.DOWNLOADING, Phase.PROCESSING)


class LogLevel(Enum):
    INFO = "info"
    DETAIL = "detail"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class LogEntry:
    message: str
    level: LogLevel = LogLevel.INFO
    timestamp: float = field(default_factory=time.time)

    @property
    def time_text(self) -> str:
        return time.strftime("%H:%M:%S", time.localtime(self.timestamp))
