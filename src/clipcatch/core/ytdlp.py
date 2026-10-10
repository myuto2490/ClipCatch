"""yt-dlp とのやり取り（引数の組み立てと出力の解釈）。

進捗は `--progress-template` で機械可読な 1 行として出させ、最終的なファイル
パスは `--print after_move:` で受け取る。後処理の段階は yt-dlp が出す
`[Merger]` などの行から拾う。プロセスの起動とは切り離してあるので単体で検査できる。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from clipcatch.core.formats import CookieBrowser, DownloadFormat, VideoQuality
from clipcatch.core.i18n import tr
from clipcatch.core.models import DownloadResult, LogLevel, MediaInfo, TransferProgress
from clipcatch.core.platform import IS_WINDOWS

# 進捗行・完了行の目印。通常の出力と混ざっても見分けられるようにする。
PROGRESS_MARKER = "@@CCPROGRESS@@"
RESULT_MARKER = "@@CCRESULT@@"
# フィールド区切り（ASCII の Unit Separator）。タイトルやパスと衝突しない。
SEPARATOR = "\x1f"

# 単一ファイルで配信し、内蔵ダウンローダだと接続 1 本になるサイト。
SINGLE_STREAM_HOSTS = ("bilibili.com", "bilibili.tv", "b23.tv")


@dataclass
class DownloadRequest:
    url: str
    output_directory: Path
    format: DownloadFormat
    quality: VideoQuality
    ffmpeg: Path | None = None
    # あれば外部ダウンローダとして使う。単一ファイルを多重接続で取れる。
    aria2c: Path | None = None
    cookie_browser: CookieBrowser = CookieBrowser.NONE
    # `~/.config/yt-dlp/config` などの個人設定を読ませるか。
    use_user_config: bool = False
    allow_playlist: bool = False
    # YouTube の解析に使う Deno。無いと一部の形式が取れないことがある。
    js_runtime: Path | None = None


def common_arguments(js_runtime: Path | None = None) -> list[str]:
    """どの呼び出しにも付ける引数。"""
    args = ["--no-colors"]
    if js_runtime is not None:
        args += ["--js-runtimes", f"deno:{js_runtime}"]
    if IS_WINDOWS:
        # パイプ越しだとコンソールのコードページ（cp932 など）で出力されるため
        args += ["--encoding", "utf-8"]
    return args


def download_arguments(request: DownloadRequest) -> list[str]:
    progress_template = (
        "download:"
        + PROGRESS_MARKER
        + SEPARATOR.join(
            [
                "%(progress.status)s",
                "%(progress.downloaded_bytes)s",
                "%(progress.total_bytes)s",
                "%(progress.total_bytes_estimate)s",
                "%(progress.speed)s",
                "%(progress.eta)s",
                "%(progress.filename)s",
                "%(info.playlist_index)s",
                "%(info.n_entries)s",
            ]
        )
    )
    result_template = (
        "after_move:"
        + RESULT_MARKER
        + SEPARATOR.join(["%(title)s", "%(resolution)s", "%(vcodec)s", "%(filepath)s"])
    )

    args = [
        "--yes-playlist" if request.allow_playlist else "--no-playlist",
        "--newline",
        "--progress",  # quiet でも進捗を出させる
        "--no-quiet",
        "--no-simulate",
        *common_arguments(request.js_runtime),
        "--progress-template",
        progress_template,
        "--print",
        result_template,
        "--concurrent-fragments",
        "4",
        "--retries",
        "10",
        "--fragment-retries",
        "10",
        "-f",
        request.format.format_selector(request.quality.max_height),
        "-o",
        str(request.output_directory / "%(title)s.%(ext)s"),
    ]
    if not request.use_user_config:
        # 既定では利用者の yt-dlp 設定ファイルに左右されないようにする
        args.append("--ignore-config")
    if request.aria2c:
        # 単一ファイルで配信するサイト（bilibili など）では内蔵ダウンローダが
        # 1 接続しか張らず、接続あたりの帯域制限をまともに受ける。aria2c なら
        # 範囲リクエストで分割して同時に取れる。分割数は yt-dlp が既定で
        # -x16 -j16 -s16 を渡すので指定しない。
        #
        # 断片(DASH/HLS)形式だけは必ず内蔵ダウンローダに戻す。yt-dlp の Aria2cFD は
        # 断片を取りこぼしても黙って読み飛ばし、映像が途中で尽きたファイルを
        # 「成功」として結合してしまう（再生すると途中から真っ黒になる）。
        #
        # 外部ダウンローダ使用時は yt-dlp が途中経過を報告しないので、aria2c に
        # 1 秒ごとの要約を出させてその行を解釈する。
        args += [
            "--downloader",
            str(request.aria2c),
            "--downloader",
            "dash,m3u8:native",
            "--downloader-args",
            "aria2c:--summary-interval=1",
        ]
    args += request.cookie_browser.arguments
    if not request.format.is_audio_only:
        args += ["--merge-output-format", "mp4"]
    args += request.format.post_processing_arguments
    if request.ffmpeg:
        args += ["--ffmpeg-location", str(request.ffmpeg.parent)]
    args += ["--", request.url]
    return args


def metadata_arguments(
    url: str, allow_playlist: bool = False, js_runtime: Path | None = None
) -> list[str]:
    return [
        "-J",
        # プレイリストは中身を 1 本ずつ解析すると遅いので、一覧だけを取る
        "--flat-playlist" if allow_playlist else "--no-playlist",
        "--no-warnings",
        "--ignore-config",
        *common_arguments(js_runtime),
        "--socket-timeout",
        "15",
        "--",
        url,
    ]


def parse_metadata(stdout: str) -> MediaInfo:
    data = json.loads(stdout)
    if not isinstance(data, dict):
        raise ValueError("unexpected JSON")
    return MediaInfo.from_json(data)


def last_error_line(stderr: str) -> str | None:
    """標準エラーの最後の `ERROR:` 行から本文だけを取り出す。"""
    for line in reversed(stderr.splitlines()):
        if line.startswith("ERROR:"):
            return line[len("ERROR:") :].strip()
    return None


def is_single_stream_site(url: str) -> bool:
    match = re.match(r"^[a-z][a-z0-9+.-]*://([^/?#:]+)", url.strip(), re.IGNORECASE)
    if not match:
        return False
    host = match.group(1).lower()
    return any(host == h or host.endswith("." + h) for h in SINGLE_STREAM_HOSTS)


# MARK: - 出力の解釈


@dataclass(frozen=True)
class ProgressEvent:
    progress: TransferProgress
    playlist_index: int | None = None
    playlist_count: int | None = None


@dataclass(frozen=True)
class StageEvent:
    label: str


@dataclass(frozen=True)
class LogEvent:
    message: str
    level: LogLevel


Event = ProgressEvent | StageEvent | LogEvent


def _stage_labels() -> list[tuple[str, str]]:
    return [
        ("[Merger]", tr("映像と音声を結合中…", "Merging video and audio…")),
        ("[ExtractAudio]", tr("音声を変換中…", "Converting audio…")),
        ("[VideoConvertor]", tr("動画を変換中…", "Converting video…")),
        ("[FixupM3u8]", tr("ファイルを修復中…", "Repairing file…")),
        ("[FixupM4a]", tr("ファイルを修復中…", "Repairing file…")),
        ("[MoveFiles]", tr("ファイルを移動中…", "Moving file…")),
        ("[Metadata]", tr("メタデータを書き込み中…", "Writing metadata…")),
    ]


def stage_label(line: str) -> str | None:
    for prefix, label in _stage_labels():
        if line.startswith(prefix):
            return label
    return None


def _number(raw: str) -> float | None:
    value = raw.strip()
    if not value or value in ("NA", "None"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _optional(raw: str) -> str | None:
    value = raw.strip()
    return None if value in ("", "NA", "None") else value


def parse_progress(line: str) -> ProgressEvent | None:
    fields = line[len(PROGRESS_MARKER) :].split(SEPARATOR)
    if len(fields) < 7:
        return None
    downloaded = _number(fields[1])
    total = _number(fields[2]) or _number(fields[3])
    progress = TransferProgress(
        downloaded_bytes=int(downloaded) if downloaded is not None else None,
        total_bytes=int(total) if total is not None else None,
        bytes_per_second=_number(fields[4]),
        eta_seconds=int(eta) if (eta := _number(fields[5])) is not None else None,
    )
    name = _optional(fields[6])
    progress.file_name = Path(name.replace("\\", "/")).name if name else None
    if downloaded is not None and total and total > 0:
        progress.fraction = min(max(downloaded / total, 0.0), 1.0)
    index = _number(fields[7]) if len(fields) > 7 else None
    count = _number(fields[8]) if len(fields) > 8 else None
    return ProgressEvent(
        progress,
        playlist_index=int(index) if index else None,
        playlist_count=int(count) if count else None,
    )


def parse_result(line: str) -> DownloadResult:
    fields = line[len(RESULT_MARKER) :].split(SEPARATOR)

    def value(index: int) -> str | None:
        return _optional(fields[index]) if index < len(fields) else None

    return DownloadResult(
        title=value(0) or tr("（タイトル不明）", "(Untitled)"),
        resolution=value(1),
        video_codec=value(2),
        file_path=value(3),
    )


# aria2c が 1 秒ごとに出す要約の飾り行。進捗はこの中の `[#...]` 行から読む。
_ARIA2_NOISE = re.compile(r"^(\*\*\* Download Progress Summary|FILE: |[=-]{20,}$)")
_ARIA2_FULL = re.compile(r"\[#\S+\s+([0-9.]+[A-Za-z]+)/([0-9.]+[A-Za-z]+)\((\d+)%\)")
_ARIA2_PARTIAL = re.compile(r"\[#\S+\s+([0-9.]+[A-Za-z]+)\s")
_ARIA2_SPEED = re.compile(r"DL:([0-9.]+[A-Za-z]*)")
_ARIA2_ETA = re.compile(r"ETA:(\S+?)[\]\s]")


def aria2_bytes(text: str) -> float | None:
    """aria2c の `45MiB` や `8.2K` のような表記をバイト数にする。"""
    match = re.fullmatch(r"([0-9.]+)([A-Za-z]*)", text)
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    unit = match.group(2).lower()
    scale = {"gib": 1024**3, "gi": 1024**3, "g": 1024**3}
    scale |= {"mib": 1024**2, "mi": 1024**2, "m": 1024**2}
    scale |= {"kib": 1024, "ki": 1024, "k": 1024}
    return value * scale.get(unit, 1)


def aria2_seconds(text: str) -> int | None:
    """aria2c の `21s` `1m21s` `1h1m21s` を秒にする。"""
    parts = re.findall(r"(\d+)([hms])", text)
    if not parts or "".join(n + u for n, u in parts) != text:
        return None
    factor = {"h": 3600, "m": 60, "s": 1}
    return sum(int(n) * factor[u] for n, u in parts)


def parse_aria2_progress(line: str, file_name: str | None) -> TransferProgress | None:
    """aria2c の進捗行を読む。

    コンソール表示と 1 秒ごとの要約、どちらも次の形の断片を含む:
        [#7d2a1b 45MiB/220MiB(20%) CN:16 DL:8.2MiB ETA:21s]
    総サイズが不明なときは `45MiB CN:1 DL:8.2MiB` のように割合と ETA が落ちる。
    """
    start = line.find("[#")
    if start < 0:
        return None
    body = line[start:]
    progress = TransferProgress(file_name=file_name)
    recognised = False

    if m := _ARIA2_FULL.search(body):
        done, total = aria2_bytes(m.group(1)), aria2_bytes(m.group(2))
        progress.downloaded_bytes = int(done) if done is not None else None
        progress.total_bytes = int(total) if total is not None else None
        progress.fraction = int(m.group(3)) / 100
        recognised = True
    elif m := _ARIA2_PARTIAL.search(body):
        done = aria2_bytes(m.group(1))
        progress.downloaded_bytes = int(done) if done is not None else None
        recognised = True

    if m := _ARIA2_SPEED.search(body):
        progress.bytes_per_second = aria2_bytes(m.group(1))
        recognised = True
    if m := _ARIA2_ETA.search(body):
        progress.eta_seconds = aria2_seconds(m.group(1))

    return progress if recognised else None


@dataclass
class OutputParser:
    """yt-dlp の出力を 1 行ずつ受け取り、画面向けのイベントに変える。"""

    result: DownloadResult | None = None
    results: list[DownloadResult] = field(default_factory=list)
    last_error: str | None = None
    # aria2c の進捗行には名前が入らないので、直前の Destination 行から覚えておく。
    current_file_name: str | None = None

    def feed(self, line: str) -> list[Event]:
        line = line.strip()
        if not line:
            return []
        if line.startswith(PROGRESS_MARKER):
            event = parse_progress(line)
            return [event] if event else []
        if line.startswith(RESULT_MARKER):
            self.result = parse_result(line)
            self.results.append(self.result)
            return []

        destination = "[download] Destination: "
        if line.startswith(destination):
            self.current_file_name = Path(line[len(destination) :].replace("\\", "/")).name
            # 進捗表示と重複するのでログには流さない
            return []
        if aria2 := parse_aria2_progress(line, self.current_file_name):
            return [ProgressEvent(aria2)]
        if _ARIA2_NOISE.match(line):
            return []

        events: list[Event] = []
        if label := stage_label(line):
            events.append(StageEvent(label))
        if line.startswith("ERROR:"):
            self.last_error = line[len("ERROR:") :].strip()
            events.append(LogEvent(line, LogLevel.ERROR))
        elif line.startswith("WARNING:"):
            events.append(LogEvent(line, LogLevel.WARNING))
        else:
            events.append(LogEvent(line, LogLevel.DETAIL))
        return events
