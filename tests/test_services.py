import io
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from clipcatch.core import sources
from clipcatch.core.archive import ArchiveError, extract_executables
from clipcatch.core.formats import CookieBrowser, DownloadFormat, VideoQuality
from clipcatch.core.ytdlp import RESULT_MARKER, SEPARATOR, DownloadRequest

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="uses a shebang script")


class TestLineSplitter:
    def test_splits_on_cr_and_lf_across_chunks(self):
        from clipcatch.services.process import LineSplitter

        lines = []
        splitter = LineSplitter(lines.append)
        splitter.feed(b"one\rtw")
        splitter.feed(b"o\n\nthr")
        splitter.feed("ee 日本".encode()[:-1])
        assert lines == ["one", "two"]
        splitter.feed("ee 日本".encode()[-1:])
        splitter.flush()
        assert lines[-1].startswith("three")

    def test_invalid_utf8_is_replaced(self):
        from clipcatch.services.process import LineSplitter

        lines = []
        LineSplitter(lines.append).feed(b"bad \xff byte\n")
        assert lines == ["bad � byte"]


class TestArchive:
    def test_zip_flattens_and_ignores_paths(self, tmp_path):
        archive = tmp_path / "a.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("ffmpeg-7/bin/ffmpeg", b"FF")
            zf.writestr("ffmpeg-7/bin/ffprobe", b"FP")
            zf.writestr("../evil", b"x")
        out = tmp_path / "out"
        paths = extract_executables(archive, ["ffmpeg", "ffprobe"], out)
        assert [p.read_bytes() for p in paths] == [b"FF", b"FP"]
        assert sorted(p.name for p in out.iterdir()) == ["ffmpeg", "ffprobe"]
        assert not (tmp_path / "evil").exists()

    def test_tar_xz(self, tmp_path):
        archive = tmp_path / "a.tar.xz"
        with tarfile.open(archive, "w:xz") as tf:
            data = b"bin"
            info = tarfile.TarInfo("dir/bin/ffmpeg")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        (path,) = extract_executables(archive, ["ffmpeg"], tmp_path / "out")
        assert path.read_bytes() == b"bin"

    def test_missing_member(self, tmp_path):
        archive = tmp_path / "a.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("readme.txt", b"")
        with pytest.raises(ArchiveError):
            extract_executables(archive, ["ffmpeg"], tmp_path / "out")

    def test_not_an_archive(self, tmp_path):
        bogus = tmp_path / "x.zip"
        bogus.write_bytes(b"<html>")
        with pytest.raises(ArchiveError):
            extract_executables(bogus, ["ffmpeg"], tmp_path / "out")


class TestSources:
    def test_ytdlp_url_per_platform(self):
        url = sources.ytdlp_download_url()
        assert url.startswith("https://github.com/yt-dlp/yt-dlp/releases/latest/download/")

    def test_ffmpeg_sources_have_both_tools(self):
        for alternative in sources.ffmpeg_sources():
            members = {m for archive in alternative for m in archive.members}
            assert any(m.startswith("ffmpeg") for m in members)
            assert any(m.startswith("ffprobe") for m in members)

    def test_deno(self):
        for arch, fragment in (("arm64", "aarch64"), ("x86_64", "x86_64")):
            source = sources.deno_source(arch)
            assert fragment in source.url
            assert source.url.endswith(".zip")
            assert source.members[0].startswith("deno")

    def test_aria2_asset(self):
        assert sources.aria2_asset_name_matches("aria2-1.37.0-win-64bit-build1.zip", "x86_64")
        assert not sources.aria2_asset_name_matches("aria2-1.37.0-win-32bit-build1.zip", "x86_64")
        assert not sources.aria2_asset_name_matches("aria2-1.37.0.tar.xz", "x86_64")

    def test_parse_checksums(self):
        digest = "a" * 64
        text = f"{digest}  yt-dlp_macos\n{'b' * 64} *yt-dlp.exe\ngarbage\n"
        assert sources.parse_checksums(text) == {"yt-dlp_macos": digest, "yt-dlp.exe": "b" * 64}


class TestReleaseParsing:
    def test_newer(self):
        from clipcatch.services.updates import parse_release

        data = b'{"tag_name": "v9.0.0", "html_url": "https://example/r"}'
        release = parse_release(data, current="1.0.0")
        assert release.version == "9.0.0"
        assert release.url == "https://example/r"

    @pytest.mark.parametrize(
        "data",
        [
            b'{"tag_name": "v1.0.0"}',
            b'{"tag_name": "v9.0.0", "prerelease": true}',
            b'{"tag_name": "v9.0.0", "draft": true}',
            b'{"message": "Not Found"}',
            b"not json",
        ],
    )
    def test_ignored(self, data):
        from clipcatch.services.updates import parse_release

        assert parse_release(data, current="1.0.0") is None


class TestSettings:
    @pytest.fixture
    def settings(self, qapp, tmp_path):
        from PySide6.QtCore import QSettings

        from clipcatch.services.settings import Settings

        store = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
        return Settings(store)

    def test_defaults(self, settings):
        assert settings.format is DownloadFormat.MP4
        assert settings.quality is VideoQuality.UNLIMITED
        assert settings.cookie_browser is CookieBrowser.NONE
        assert settings.auto_paste_url is True
        assert settings.accelerate_with_aria2c is True
        assert settings.reveal_when_done is False
        assert isinstance(settings.output_directory, Path)

    def test_round_trip_and_signal(self, settings, tmp_path):
        changed = []
        settings.changed.connect(changed.append)
        settings.format = DownloadFormat.MP3
        settings.output_directory = tmp_path
        settings.set_flag("revealWhenDone", True)
        assert settings.format is DownloadFormat.MP3
        assert settings.output_directory == tmp_path
        assert settings.reveal_when_done is True
        assert changed == ["format", "outputDirectory", "revealWhenDone"]

    def test_corrupt_values_fall_back(self, settings):
        settings._store.setValue("format", "nope")
        settings._store.setValue("autoPasteURL", "false")
        assert settings.format is DownloadFormat.MP4
        assert settings.auto_paste_url is False

    def test_unknown_flag(self, settings):
        with pytest.raises(KeyError):
            settings.set_flag("nope", True)


class TestUrlValidation:
    @pytest.mark.parametrize(
        ("text", "valid"),
        [
            ("https://www.youtube.com/watch?v=abc", True),
            ("  http://example.com/x  ", True),
            ("ftp://example.com", False),
            ("https://", False),
            ("example.com", False),
            ("https://exa mple.com", False),
            ("", False),
        ],
    )
    def test_is_web_url(self, qapp, text, valid):
        from clipcatch.services.system import is_web_url

        assert is_web_url(text) is valid


class TestProcessTask:
    def test_collects_output(self, wait_for):
        from clipcatch.services.process import run_process

        results = []
        run_process(
            Path(sys.executable),
            ["-c", "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)"],
            results.append,
        )
        wait_for(lambda: results)
        output = results[0]
        assert (output.status, output.stdout.strip(), output.stderr.strip()) == (3, "out", "err")
        assert not output.succeeded

    def test_missing_executable(self, wait_for, tmp_path):
        from clipcatch.services.process import run_process

        results = []
        run_process(tmp_path / "does-not-exist", [], results.append)
        wait_for(lambda: results)
        assert results[0].error

    def test_timeout(self, wait_for):
        from clipcatch.services.process import run_process

        results = []
        run_process(
            Path(sys.executable), ["-c", "import time; time.sleep(30)"], results.append, 300
        )
        wait_for(lambda: results)
        assert results[0].error == "timeout"


def fake_ytdlp(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "yt-dlp"
    script.write_text(f"#!{sys.executable}\nimport sys, time\n{body}\n")
    script.chmod(0o755)
    return script


def request(tmp_path: Path) -> DownloadRequest:
    return DownloadRequest(
        url="https://example.com/v",
        output_directory=tmp_path,
        format=DownloadFormat.MP4,
        quality=VideoQuality.UNLIMITED,
    )


@posix_only
class TestDownloadEngine:
    def test_success_reports_progress_stage_and_result(self, wait_for, tmp_path):
        from clipcatch.core.ytdlp import PROGRESS_MARKER
        from clipcatch.services.engine import DownloadEngine

        progress_line = PROGRESS_MARKER + SEPARATOR.join(
            ["downloading", "50", "100", "NA", "10", "5", "/x/a.mp4"]
        )
        result_line = RESULT_MARKER + SEPARATOR.join(["A", "1280x720", "avc1", "/x/a.mp4"])
        body = (
            f"print({progress_line!r}, flush=True)\n"
            f"print('[Merger] Merging formats', file=sys.stderr, flush=True)\n"
            f"print({result_line!r})"
        )
        engine = DownloadEngine()
        events = {"progress": [], "stage": [], "finished": []}
        engine.progress.connect(events["progress"].append)
        engine.stage.connect(events["stage"].append)
        engine.finished.connect(events["finished"].append)
        engine.start(request(tmp_path), fake_ytdlp(tmp_path, body))
        wait_for(lambda: events["finished"])
        assert events["progress"][0].progress.fraction == 0.5
        assert events["stage"] == ["Merging video and audio…"]
        assert events["finished"][0][0].file_path == "/x/a.mp4"
        assert not engine.is_running

    def test_failure_uses_last_error(self, wait_for, tmp_path):
        from clipcatch.services.engine import DownloadEngine

        body = "print('ERROR: Video unavailable', file=sys.stderr); sys.exit(1)"
        engine = DownloadEngine()
        failures = []
        engine.failed.connect(failures.append)
        engine.start(request(tmp_path), fake_ytdlp(tmp_path, body))
        wait_for(lambda: failures)
        assert failures == ["Video unavailable"]

    def test_cancel(self, wait_for, tmp_path):
        from clipcatch.services.engine import DownloadEngine

        engine = DownloadEngine()
        cancelled = []
        engine.cancelled.connect(lambda: cancelled.append(True))
        engine.start(request(tmp_path), fake_ytdlp(tmp_path, "time.sleep(30)"))
        wait_for(lambda: engine.is_running)
        engine.cancel()
        wait_for(lambda: cancelled)
        assert not engine.is_running
