"""バージョン文字列の比較。"""

from __future__ import annotations

import re


def parse(version: str) -> tuple[int, ...] | None:
    """`v1.2.0` `2026.07.04` `2026.7.4` などを数値の組にする。読めなければ None。"""
    text = version.strip().lstrip("vV")
    if not re.fullmatch(r"\d+(\.\d+)*", text):
        return None
    parts = [int(p) for p in text.split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def same(a: str, b: str) -> bool:
    """`2026.07.04` と `2026.7.4` を同じものとして扱う。"""
    x, y = parse(a), parse(b)
    if x is not None and y is not None:
        return x == y
    return a.strip() == b.strip()


def is_newer(candidate: str, current: str) -> bool:
    x, y = parse(candidate), parse(current)
    if x is None or y is None:
        return False
    return x > y
