"""配布アーカイブ（zip / tar.xz）から必要な実行ファイルだけを取り出す。"""

from __future__ import annotations

import os
import shutil
import tarfile
import zipfile
from pathlib import Path, PurePosixPath


class ArchiveError(Exception):
    pass


def _basename(member: str) -> str:
    return PurePosixPath(member.replace("\\", "/")).name


def extract_executables(archive: Path, names: list[str], destination: Path) -> list[Path]:
    """`names` に一致するファイル（階層は問わない）を `destination` 直下に取り出す。

    アーカイブ内のパスは使わず名前だけで置くので、`../` を含む細工された
    アーカイブでも外に書き出されることはない。
    """
    destination.mkdir(parents=True, exist_ok=True)
    wanted = set(names)
    written: dict[str, Path] = {}

    def install(name: str, source) -> None:
        target = destination / name
        partial = target.with_name(target.name + ".part")
        with open(partial, "wb") as out:
            shutil.copyfileobj(source, out)
        os.chmod(partial, 0o755)
        os.replace(partial, target)
        written[name] = target

    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                name = _basename(info.filename)
                if not info.is_dir() and name in wanted and name not in written:
                    with zf.open(info) as source:
                        install(name, source)
    elif tarfile.is_tarfile(archive):
        with tarfile.open(archive) as tf:
            for member in tf.getmembers():
                name = _basename(member.name)
                if member.isfile() and name in wanted and name not in written:
                    source = tf.extractfile(member)
                    if source is not None:
                        with source:
                            install(name, source)
    else:
        raise ArchiveError(f"unsupported archive: {archive.name}")

    missing = wanted - written.keys()
    if missing:
        raise ArchiveError("not found in archive: " + ", ".join(sorted(missing)))
    return [written[n] for n in names]
