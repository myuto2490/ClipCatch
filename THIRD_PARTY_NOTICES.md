# Third-party notices

ClipCatch is distributed under the [MIT License](LICENSE). It includes or downloads the following software,
each distributed under its own license.

## Bundled with the application

| Software | License | Project |
| --- | --- | --- |
| Qt for Python (PySide6, Shiboken6) and Qt 6 | LGPL-3.0-only | https://www.qt.io/qt-for-python |
| Python and the libraries in its standard distribution | PSF-2.0 and others (see `Python-LICENSE.txt`) | https://www.python.org |
| PyInstaller bootloader | GPL-2.0-or-later with an exception that allows distributing bundled apps under any license | https://pyinstaller.org |

Every release package contains a `licenses` folder with the full license texts:

| File | Contents |
| --- | --- |
| `LICENSE` | ClipCatch (MIT) |
| `THIRD_PARTY_NOTICES.md` | This document |
| `LGPL-3.0-only.txt`, `GPL-3.0-only.txt` | GNU LGPL v3 and the GNU GPL v3 it builds on (Qt / PySide6) |
| `Python-LICENSE.txt` | The license file shipped with the Python runtime used for the build |

On macOS the folder is inside `ClipCatch.app/Contents/Resources/`; on Windows it is in the `_internal`
folder next to `ClipCatch.exe`. You can also open it from **About ClipCatch › Open Source Licenses**.

### Qt and PySide6 (LGPL-3.0)

ClipCatch uses Qt and PySide6 as dynamically linked libraries and does not modify them. Release packages use
a "one-folder" layout, so you can replace the Qt and PySide6 libraries inside the application with your own
compatible builds. The corresponding source code is available from https://download.qt.io/official_releases/
and https://code.qt.io/. The ClipCatch source code needed to rebuild the application is available in this
repository.

## Downloaded at runtime (not bundled)

These tools are downloaded from their official distribution channels on first launch and stored in the user's
data folder.

| Software | License | Project |
| --- | --- | --- |
| yt-dlp | Unlicense | https://github.com/yt-dlp/yt-dlp |
| FFmpeg (static builds) | GPL-3.0 / LGPL-2.1 depending on the build | https://ffmpeg.org |
| Deno | MIT | https://deno.com |
| aria2 (optional) | GPL-2.0 | https://aria2.github.io |

## Artwork

The application icon and the interface icons were drawn for ClipCatch and are covered by the MIT License.
They follow the style of, but do not include, Apple's SF Symbols.

The README screenshots show *Big Buck Bunny* © Blender Foundation, licensed under
[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) (https://peach.blender.org).
