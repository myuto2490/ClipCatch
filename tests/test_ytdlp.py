from pathlib import Path

import pytest

from clipcatch.core import ytdlp
from clipcatch.core.formats import CookieBrowser, DownloadFormat, VideoQuality
from clipcatch.core.i18n import set_language
from clipcatch.core.models import LogLevel
from clipcatch.core.ytdlp import (
    PROGRESS_MARKER,
    RESULT_MARKER,
    SEPARATOR,
    DownloadRequest,
    LogEvent,
    OutputParser,
    ProgressEvent,
    StageEvent,
)


@pytest.fixture(autouse=True)
def english():
    set_language("en")


def make_request(**overrides) -> DownloadRequest:
    values = dict(
        url="https://example.com/watch?v=1",
        output_directory=Path("/tmp/out"),
        format=DownloadFormat.MP4,
        quality=VideoQuality.UNLIMITED,
    )
    values.update(overrides)
    return DownloadRequest(**values)


def option_value(args: list[str], option: str) -> str:
    return args[args.index(option) + 1]


class TestDownloadArguments:
    def test_url_is_last_and_after_double_dash(self):
        args = ytdlp.download_arguments(make_request(url="-not-an-option"))
        assert args[-2:] == ["--", "-not-an-option"]

    def test_defaults(self):
        args = ytdlp.download_arguments(make_request())
        assert "--no-playlist" in args
        assert "--ignore-config" in args
        assert option_value(args, "--merge-output-format") == "mp4"
        assert option_value(args, "-o") == str(Path("/tmp/out") / "%(title)s.%(ext)s")
        assert "--downloader" not in args
        assert "--cookies-from-browser" not in args

    def test_progress_and_result_templates(self):
        args = ytdlp.download_arguments(make_request())
        assert option_value(args, "--progress-template").startswith("download:" + PROGRESS_MARKER)
        assert option_value(args, "--print").startswith("after_move:" + RESULT_MARKER)

    def test_audio_only_skips_merge_and_adds_extraction(self):
        args = ytdlp.download_arguments(make_request(format=DownloadFormat.MP3))
        assert "--merge-output-format" not in args
        assert option_value(args, "--audio-format") == "mp3"

    def test_aria2c_keeps_fragmented_formats_on_native_downloader(self):
        args = ytdlp.download_arguments(make_request(aria2c=Path("/opt/bin/aria2c")))
        downloaders = [args[i + 1] for i, a in enumerate(args) if a == "--downloader"]
        assert downloaders == [str(Path("/opt/bin/aria2c")), "dash,m3u8:native"]
        assert option_value(args, "--downloader-args") == "aria2c:--summary-interval=1"

    def test_ffmpeg_location_is_directory(self):
        args = ytdlp.download_arguments(make_request(ffmpeg=Path("/opt/bin/ffmpeg")))
        assert option_value(args, "--ffmpeg-location") == str(Path("/opt/bin"))

    def test_cookies_and_user_config(self):
        args = ytdlp.download_arguments(
            make_request(cookie_browser=CookieBrowser.FIREFOX, use_user_config=True)
        )
        assert option_value(args, "--cookies-from-browser") == "firefox"
        assert "--ignore-config" not in args

    def test_js_runtime(self):
        args = ytdlp.download_arguments(make_request(js_runtime=Path("/bin/deno")))
        assert option_value(args, "--js-runtimes") == f"deno:{Path('/bin/deno')}"
        assert "--js-runtimes" not in ytdlp.download_arguments(make_request())
        meta = ytdlp.metadata_arguments("u", js_runtime=Path("/bin/deno"))
        assert option_value(meta, "--js-runtimes") == f"deno:{Path('/bin/deno')}"

    def test_playlist(self):
        args = ytdlp.download_arguments(make_request(allow_playlist=True))
        assert "--yes-playlist" in args
        assert "--no-playlist" not in args


class TestFormatSelector:
    def test_mp4_prefers_avc(self):
        assert "vcodec^=avc" in DownloadFormat.MP4.format_selector(None)

    def test_height_limit_applied_to_every_alternative(self):
        selector = DownloadFormat.MP4.format_selector(720)
        alternatives = selector.split("/")
        assert all("height<=720" in a for a in alternatives[:-1])
        assert alternatives[-1] == "best"

    def test_audio_formats_ignore_height(self):
        assert DownloadFormat.MP3.format_selector(480) == "bestaudio/best"
        assert "m4a" in DownloadFormat.M4A.format_selector(480)

    def test_ffmpeg_requirement(self):
        assert DownloadFormat.MP4.requires_ffmpeg
        assert not DownloadFormat.M4A.requires_ffmpeg


def progress_line(*fields: str) -> str:
    return PROGRESS_MARKER + SEPARATOR.join(fields)


class TestProgressParsing:
    def test_full_progress(self):
        event = ytdlp.parse_progress(
            progress_line("downloading", "512", "1024", "NA", "256.5", "2", "/x/My Video.mp4")
        )
        assert event is not None
        p = event.progress
        assert p.fraction == 0.5
        assert (p.downloaded_bytes, p.total_bytes) == (512, 1024)
        assert p.bytes_per_second == 256.5
        assert p.eta_seconds == 2
        assert p.file_name == "My Video.mp4"

    def test_uses_estimate_when_total_missing(self):
        event = ytdlp.parse_progress(
            progress_line("downloading", "100", "NA", "400", "NA", "NA", "NA")
        )
        assert event.progress.total_bytes == 400
        assert event.progress.fraction == 0.25
        assert event.progress.file_name is None

    def test_unknown_total_gives_indeterminate(self):
        event = ytdlp.parse_progress(progress_line("downloading", "100", "NA", "NA", "", "", ""))
        assert event.progress.fraction is None

    def test_windows_path_file_name(self):
        event = ytdlp.parse_progress(
            progress_line("downloading", "1", "2", "NA", "NA", "NA", r"C:\Users\me\clip.mp4")
        )
        assert event.progress.file_name == "clip.mp4"

    def test_playlist_fields(self):
        event = ytdlp.parse_progress(
            progress_line("downloading", "1", "2", "NA", "NA", "NA", "a.mp4", "3", "10")
        )
        assert (event.playlist_index, event.playlist_count) == (3, 10)

    def test_too_few_fields(self):
        assert ytdlp.parse_progress(progress_line("downloading", "1")) is None

    def test_fraction_is_clamped(self):
        event = ytdlp.parse_progress(progress_line("downloading", "300", "200", "", "", "", ""))
        assert event.progress.fraction == 1.0


class TestResultParsing:
    def test_result(self):
        line = RESULT_MARKER + SEPARATOR.join(["Title", "1920x1080", "avc1", "/out/Title.mp4"])
        result = ytdlp.parse_result(line)
        assert result.title == "Title"
        assert result.resolution == "1920x1080"
        assert result.file_path == "/out/Title.mp4"

    def test_missing_fields(self):
        result = ytdlp.parse_result(RESULT_MARKER + SEPARATOR.join(["NA", "NA"]))
        assert result.title == "(Untitled)"
        assert result.file_path is None


class TestAria2:
    def test_full_line(self):
        p = ytdlp.parse_aria2_progress(
            "[#7d2a1b 45MiB/220MiB(20%) CN:16 DL:8.2MiB ETA:21s]", "a.mp4"
        )
        assert p.downloaded_bytes == 45 * 1024**2
        assert p.total_bytes == 220 * 1024**2
        assert p.fraction == 0.2
        assert p.bytes_per_second == pytest.approx(8.2 * 1024**2)
        assert p.eta_seconds == 21
        assert p.file_name == "a.mp4"

    def test_unknown_total(self):
        p = ytdlp.parse_aria2_progress("[#7d2a1b 45MiB CN:1 DL:8.2MiB]", None)
        assert p.downloaded_bytes == 45 * 1024**2
        assert p.fraction is None

    def test_summary_line_prefix(self):
        p = ytdlp.parse_aria2_progress(" *** Download Progress Summary [#1 1KiB/2KiB(50%)]", None)
        assert p.fraction == 0.5

    def test_non_progress(self):
        assert ytdlp.parse_aria2_progress("[youtube] abc: Downloading webpage", None) is None

    @pytest.mark.parametrize(
        ("text", "seconds"),
        [("21s", 21), ("1m21s", 81), ("1h1m21s", 3681), ("2h", 7200), ("x", None), ("", None)],
    )
    def test_seconds(self, text, seconds):
        assert ytdlp.aria2_seconds(text) == seconds

    @pytest.mark.parametrize(
        ("text", "value"),
        [("10", 10), ("1K", 1024), ("1.5MiB", 1.5 * 1024**2), ("2GiB", 2 * 1024**3), ("?", None)],
    )
    def test_bytes(self, text, value):
        assert ytdlp.aria2_bytes(text) == value


class TestOutputParser:
    def test_routes_lines(self):
        parser = OutputParser()
        assert parser.feed("") == []
        assert parser.feed("[download] Destination: /out/Clip.f137.mp4") == []
        assert parser.current_file_name == "Clip.f137.mp4"

        (event,) = parser.feed("[#1 1MiB/2MiB(50%) CN:4 DL:1MiB ETA:1s]")
        assert isinstance(event, ProgressEvent)
        assert event.progress.file_name == "Clip.f137.mp4"

        stage, log = parser.feed('[Merger] Merging formats into "/out/Clip.mp4"')
        assert isinstance(stage, StageEvent)
        assert stage.label == "Merging video and audio…"
        assert isinstance(log, LogEvent)

        (warning,) = parser.feed("WARNING: something")
        assert warning.level is LogLevel.WARNING

        (error,) = parser.feed("ERROR: Video unavailable")
        assert error.level is LogLevel.ERROR
        assert parser.last_error == "Video unavailable"

        for noise in (
            "*** Download Progress Summary as of Sat Oct 10 14:52:08 2026 ***",
            "=" * 79,
            "-" * 79,
            "FILE: /out/Clip.f140.m4a.part",
        ):
            assert parser.feed(noise) == []

        parser.feed(RESULT_MARKER + SEPARATOR.join(["T", "NA", "NA", "/out/T.mp4"]))
        assert parser.result.file_path == "/out/T.mp4"


class TestMetadata:
    def test_single_video(self):
        info = ytdlp.parse_metadata(
            '{"title": "T", "uploader": "U", "duration": 125, '
            '"thumbnail": "https://i/t.jpg", "extractor_key": "Youtube"}'
        )
        assert info.title == "T"
        assert info.duration_text == "2:05"
        assert info.thumbnail_url == "https://i/t.jpg"
        assert info.playlist_count is None

    def test_playlist(self):
        info = ytdlp.parse_metadata(
            '{"title": "List", "entries": [{"title": "A", "thumbnails": '
            '[{"url": "small"}, {"url": "big"}]}, {"title": "B"}]}'
        )
        assert info.title == "List"
        assert info.playlist_count == 2
        assert info.thumbnail_url == "big"
        assert info.duration_seconds is None

    def test_last_error_line(self):
        stderr = "WARNING: a\nERROR: first\nERROR: [generic] Unsupported URL\n"
        assert ytdlp.last_error_line(stderr) == "[generic] Unsupported URL"
        assert ytdlp.last_error_line("nothing") is None

    def test_metadata_arguments(self):
        assert "--no-playlist" in ytdlp.metadata_arguments("u")
        assert "--flat-playlist" in ytdlp.metadata_arguments("u", allow_playlist=True)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.bilibili.com/video/BV1", True),
        ("https://b23.tv/abc", True),
        ("https://notbilibili.com/x", False),
        ("https://youtube.com/watch?v=1", False),
        ("not a url", False),
    ],
)
def test_single_stream_site(url, expected):
    assert ytdlp.is_single_stream_site(url) is expected
