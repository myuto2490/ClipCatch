"""ダウンロード直後のファイルが壊れていないかを判定する。

外部ダウンローダを使うと、yt-dlp は取得できた分だけで「成功」と判断することが
ある（断片を取りこぼしても終了コードは 0）。その場合、映像だけが途中で尽きた
ファイルが音声と結合され、再生すると途中から真っ黒になる。長さの食い違いは
ffprobe の軽い検査で分かるので、黙って壊れたまま渡さないようにする。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

FFPROBE_ARGUMENTS = [
    "-v",
    "error",
    "-show_entries",
    "format=duration:stream=index,codec_type,duration",
    "-of",
    "json",
]


@dataclass(frozen=True)
class IntegrityReport:
    video_duration: float
    container_duration: float

    @property
    def coverage(self) -> float:
        """映像が全体の長さに対してどれだけ足りているか。"""
        if self.container_duration <= 0:
            return 1.0
        return self.video_duration / self.container_duration

    @property
    def is_truncated(self) -> bool:
        """末尾が音声だけの作品も稀にあるため、閾値は控えめに取る。"""
        return self.coverage < 0.98


def _seconds(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def report_from_ffprobe(data: dict[str, Any]) -> IntegrityReport | None:
    """判定できない場合（長さが読めない・音声のみ）は None を返して何も言わない。"""
    container = _seconds((data.get("format") or {}).get("duration"))
    if container is None:
        return None
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        return None
    video_duration = _seconds(video.get("duration"))
    if video_duration is None:
        return None
    return IntegrityReport(video_duration, container)
