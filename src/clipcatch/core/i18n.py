"""日本語と英語の 2 言語を切り替える最小限の仕組み。

文字列は使う場所にその場で両方書く（`tr("保存先", "Save to")`）。
キーの表を別に持たないので、訳し漏れや表との食い違いが起きない。
"""

from __future__ import annotations

import locale
import os

SUPPORTED = ("ja", "en")

_language = "en"


def detect_language(preferred: list[str] | None = None) -> str:
    """OS の言語設定から使う言語を決める。日本語以外は英語にする。"""
    candidates = list(preferred or [])
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        value = os.environ.get(var)
        if value:
            candidates.append(value)
    try:
        current = locale.getlocale()[0]
    except ValueError:
        current = None
    if current:
        candidates.append(current)
    for value in candidates:
        if value.lower().replace("-", "_").startswith(("ja", "japanese")):
            return "ja"
    return "en"


def set_language(language: str) -> None:
    global _language
    _language = language if language in SUPPORTED else "en"


def language() -> str:
    return _language


def tr(ja: str, en: str) -> str:
    """現在の言語に合う方を返す。"""
    return ja if _language == "ja" else en
