# Third-party notices

## Corresponding source

The source code and build scripts for each published release are available from
the matching Git tag at https://github.com/gitlares/fs-pdf-compressor. The
release asset also includes a `SOURCE_OFFER.md` and
`THIRD_PARTY_MANIFEST.json`, which identify the exact runtime component
versions and their upstream source locations.

## Ghostscript and jbig2dec

FS PDF Compressor bundles Ghostscript 10.07.1, obtained from Homebrew.
Ghostscript is licensed under the GNU Affero General Public License, version 3
(AGPL-3.0), unless an Artifex commercial license has been acquired.

The Ghostscript copyright notice and the complete AGPL-3.0 text are included at:

- `Contents/Resources/ghostscript/GHOSTSCRIPT-LICENSE.txt`
- `Contents/Resources/ghostscript/AGPL-3.0.txt`

The exact corresponding source for Ghostscript 10.07.1 is available from:
https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10071/ghostpdl-10.07.1.tar.xz

The bundled jbig2dec runtime is also AGPL-3.0-or-later. Its corresponding
source is listed in the release's `THIRD_PARTY_MANIFEST.json` (the current
Homebrew build uses jbig2dec 0.20).

## Python, PyObjC and PyInstaller

The packaged application contains the Python runtime, PyObjC and the PyInstaller
bootloader. Their license texts are included under
`Contents/Resources/third-party-licenses/python-runtime/`:

- Python: https://www.python.org/about/legal/
- PyObjC: https://github.com/ronaldoussoren/pyobjc
- PyInstaller: https://pyinstaller.org/en/stable/license.html

## Homebrew libraries

Ghostscript dynamically depends on additional open-source libraries distributed
by Homebrew. License files detected from the installed formulae at build time are
included under `Contents/Resources/third-party-licenses/`.

The generated manifest records the source URL and license expression for every
Homebrew runtime dependency bundled with a release.
