from pathlib import Path

import pytest

from clipcatch.core import formatters, i18n, integrity, versions
from clipcatch.core.formats import CookieBrowser
from clipcatch.core.models import Phase, TransferProgress


@pytest.fixture(autouse=True)
def english():
    i18n.set_language("en")
    yield
    i18n.set_language("en")


class TestI18n:
    def test_switch(self):
        assert i18n.tr("日本語", "English") == "English"
        i18n.set_language("ja")
        assert i18n.tr("日本語", "English") == "日本語"

    def test_unknown_language_falls_back_to_english(self):
        i18n.set_language("fr")
        assert i18n.language() == "en"

    @pytest.mark.parametrize(
        ("preferred", "expected"),
        [(["ja_JP"], "ja"), (["ja-JP"], "ja"), (["Japanese_Japan"], "ja")],
    )
    def test_detect(self, preferred, expected):
        assert i18n.detect_language(preferred) == expected


class TestFormatters:
    @pytest.mark.parametrize(
        ("value", "text"),
        [
            (0, "0 bytes"),
            (1, "1 byte"),
            (999, "999 bytes"),
            (1500, "2 KB"),
            (12_300_000, "12.3 MB"),
            (123_400_000, "123 MB"),
            (4_800_000_000, "4.8 GB"),
        ],
    )
    def test_file_size(self, value, text):
        assert formatters.file_size(value) == text

    def test_speed(self):
        assert formatters.speed(3_200_000) == "3.2 MB/s"

    @pytest.mark.parametrize(
        ("seconds", "en", "ja"),
        [
            (45, "45s", "45秒"),
            (200, "3m 20s", "3分20秒"),
            (180, "3m", "3分"),
            (3900, "1h 5m", "1時間5分"),
            (7200, "2h", "2時間"),
        ],
    )
    def test_duration(self, seconds, en, ja):
        assert formatters.duration(seconds) == en
        i18n.set_language("ja")
        assert formatters.duration(seconds) == ja

    @pytest.mark.parametrize(("seconds", "text"), [(5, "0:05"), (200, "3:20"), (3909, "1:05:09")])
    def test_clock(self, seconds, text):
        assert formatters.clock(seconds) == text

    def test_display_path(self):
        home = Path("/Users/me")
        assert formatters.display_path(home, home) == "~"
        assert formatters.display_path(home / "Movies", home) == str(Path("~/Movies"))
        assert formatters.display_path(Path("/Volumes/x"), home) == str(Path("/Volumes/x"))


class TestVersions:
    def test_same(self):
        assert versions.same("2026.07.04", "2026.7.4")
        assert versions.same("v1.0", "1.0.0")
        assert not versions.same("2026.07.04", "2026.07.05")
        assert versions.same("nightly", "nightly")

    def test_is_newer(self):
        assert versions.is_newer("v1.2.0", "1.1.9")
        assert not versions.is_newer("v1.0.0", "1.0.0")
        assert not versions.is_newer("garbage", "1.0.0")


class TestIntegrity:
    def test_truncated(self):
        report = integrity.report_from_ffprobe(
            {
                "format": {"duration": "100.0"},
                "streams": [
                    {"codec_type": "audio", "duration": "100.0"},
                    {"codec_type": "video", "duration": "60.0"},
                ],
            }
        )
        assert report.is_truncated
        assert report.coverage == pytest.approx(0.6)

    def test_complete(self):
        report = integrity.report_from_ffprobe(
            {"format": {"duration": "100"}, "streams": [{"codec_type": "video", "duration": "99"}]}
        )
        assert not report.is_truncated

    @pytest.mark.parametrize(
        "data",
        [
            {},
            {"format": {"duration": "N/A"}},
            {"format": {"duration": "10"}, "streams": [{"codec_type": "audio"}]},
            {"format": {"duration": "10"}, "streams": [{"codec_type": "video"}]},
        ],
    )
    def test_undecidable(self, data):
        assert integrity.report_from_ffprobe(data) is None


def test_progress_detail_text():
    p = TransferProgress(
        downloaded_bytes=12_300_000,
        total_bytes=48_000_000,
        bytes_per_second=3_200_000,
        eta_seconds=12,
    )
    assert p.detail_text == "12.3 MB / 48.0 MB  ·  3.2 MB/s  ·  12s left"
    assert TransferProgress().detail_text == ""


def test_phase_busy():
    assert Phase.DOWNLOADING.is_busy
    assert not Phase.FINISHED.is_busy


def test_cookie_browser_arguments():
    assert CookieBrowser.NONE.arguments == []
    assert CookieBrowser.CHROME.arguments == ["--cookies-from-browser", "chrome"]
    assert CookieBrowser.NONE in CookieBrowser.available()
