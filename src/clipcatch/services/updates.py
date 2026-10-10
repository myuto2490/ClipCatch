"""ClipCatch 自身の新しいリリースを GitHub に問い合わせる。"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from clipcatch import REPOSITORY, __version__
from clipcatch.core import versions
from clipcatch.services import network

RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPOSITORY}/releases/latest"


@dataclass(frozen=True)
class AppRelease:
    version: str
    url: str


def parse_release(data: bytes, current: str = __version__) -> AppRelease | None:
    """現在より新しい正式リリースなら返す。下書き・プレリリースは無視する。"""
    try:
        payload = json.loads(data)
    except ValueError:
        return None
    if not isinstance(payload, dict) or payload.get("draft") or payload.get("prerelease"):
        return None
    tag = payload.get("tag_name")
    if not isinstance(tag, str) or not versions.is_newer(tag, current):
        return None
    return AppRelease(version=tag.lstrip("vV"), url=payload.get("html_url") or RELEASES_PAGE)


def check_for_update(on_found: Callable[[AppRelease], None]) -> None:
    """新しいリリースがあるときだけ `on_found` を呼ぶ。失敗は黙って無視する。"""

    def done(data: bytes | None, _error: str | None) -> None:
        if data and (release := parse_release(data)):
            on_found(release)

    network.fetch(RELEASE_API, done, headers={"Accept": "application/vnd.github+json"})
