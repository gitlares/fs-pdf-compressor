# Third-party notices

## Ghostscript

FS PDF Compressor bundles Ghostscript 10.07.1, obtained from Homebrew.
Ghostscript is licensed under the GNU Affero General Public License, version 3
(AGPL-3.0), unless an Artifex commercial license has been acquired.

The Ghostscript copyright notice and the complete AGPL-3.0 text are included at:

- `Contents/Resources/ghostscript/GHOSTSCRIPT-LICENSE.txt`
- `Contents/Resources/ghostscript/AGPL-3.0.txt`

The exact corresponding source for Ghostscript 10.07.1 is available from:
https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10071/ghostscript-10.07.1.tar.xz

## Python, PyObjC and PyInstaller

The packaged application contains the Python runtime, PyObjC and the PyInstaller
bootloader. Their projects and license information are available from:

- Python: https://www.python.org/about/legal/
- PyObjC: https://github.com/ronaldoussoren/pyobjc
- PyInstaller: https://pyinstaller.org/en/stable/license.html

## Homebrew libraries

Ghostscript dynamically depends on additional open-source libraries distributed
by Homebrew. License files detected from the installed formulae at build time are
included under `Contents/Resources/third-party-licenses/`.

FS PDF Compressor's complete corresponding source and build scripts are at:
https://github.com/gitlares/fs-pdf-compressor
