import re

import clipcatch


def test_version_is_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", clipcatch.__version__)


def test_app_name():
    assert clipcatch.APP_NAME == "ClipCatch"
