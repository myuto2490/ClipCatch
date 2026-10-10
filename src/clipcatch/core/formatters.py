"""サイズ・速度・時間・パスの表記。"""

from __future__ import annotations

from pathlib import Path

from clipcatch.core.i18n import tr


def file_size(value: float) -> str:
    """Finder / エクスプローラと同じ 10 進の単位で表す（12.3 MB など）。"""
    value = max(float(value), 0.0)
    if value < 1000:
        return f"{int(value)} bytes" if value != 1 else "1 byte"
    for unit in ("KB", "MB", "GB", "TB"):
        value /= 1000
        if value < 1000 or unit == "TB":
            if value >= 100 or unit == "KB":
                return f"{value:.0f} {unit}"
            return f"{value:.1f} {unit}"
    raise AssertionError("unreachable")


def speed(bytes_per_second: float) -> str:
    return f"{file_size(bytes_per_second)}/s"


def duration(seconds: float) -> str:
    """秒を「1時間5分」「3分20秒」「45秒」（英語では 1h 5m / 3m 20s / 45s）にする。"""
    total = round(max(seconds, 0))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        if minutes:
            return tr(f"{hours}時間{minutes}分", f"{hours}h {minutes}m")
        return tr(f"{hours}時間", f"{hours}h")
    if minutes:
        if secs:
            return tr(f"{minutes}分{secs}秒", f"{minutes}m {secs}s")
        return tr(f"{minutes}分", f"{minutes}m")
    return tr(f"{secs}秒", f"{secs}s")


def clock(seconds: float) -> str:
    """再生時間の表示（1:05:09 / 3:20）。"""
    total = round(max(seconds, 0))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def display_path(path: Path | str, home: Path | None = None) -> str:
    """ホームディレクトリ基準の短い表記にする（~/Movies）。"""
    path = Path(path)
    home = home or Path.home()
    try:
        relative = path.relative_to(home)
    except ValueError:
        return str(path)
    return "~" if str(relative) == "." else str(Path("~") / relative)
