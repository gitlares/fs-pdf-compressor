# Build FS PDF Compressor on Windows

FS PDF Compressor can be built on Windows from this repository. The Windows
edition uses the same local compression engine and three quality profiles as
the macOS and Linux editions. It is distributed under AGPL-3.0-or-later.

## Install the public build

For Windows 11 x64, download the per-user installer or portable ZIP from the
[1.0.13 release](https://github.com/gitlares/fs-pdf-compressor/releases/tag/v1.0.13).
Each artifact has a matching SHA-256 file. The installer includes the
unmodified AGPL Ghostscript runtime and needs no administrator rights.

The Windows build is not code-signed yet, so Windows may show SmartScreen.
Only install it from the official release after verifying the published
checksum. Updates are manual for now: download a newer installer when a new
release is published.

## Requirements

Build on Windows 11 x64. Windows 11 on ARM also works when using an **x64
Python installation** under Windows emulation. Install:

- Git
- Python 3.12 x64
- [official x64 AGPL Ghostscript](https://ghostscript.com/releases/gsdnld.html)
- [Inno Setup 6](https://jrsoftware.org/isinfo.php)

Use the official AGPL Ghostscript package. The Windows build bundles its
unmodified runtime, its AGPL text, a corresponding-source offer, and a
third-party manifest. Do not substitute a commercial Ghostscript build unless
you have the appropriate commercial licence and have reviewed the resulting
distribution obligations.

## Build an installer

Open PowerShell in the repository and run:

```powershell
py -3.12-64 -m venv .windows-build-venv
.windows-build-venv\Scripts\python -m pip install --upgrade pip
.windows-build-venv\Scripts\python -m pip install -r requirements-windows.txt
.windows-build-venv\Scripts\python build_windows.py
```

Ghostscript is found automatically when installed at
`C:\Program Files\gs\gs<version>`. To use another official x64 installation,
set `GHOSTSCRIPT_ROOT` to its `gs<version>` directory before running the build:

```powershell
$env:GHOSTSCRIPT_ROOT = "D:\tools\gs\gs10.07.1"
.windows-build-venv\Scripts\python build_windows.py
```

The build writes these files to `release-windows/`:

- `FS-PDF-Compressor-<version>-windows-x86_64-setup.exe` — per-user installer.
- `FS-PDF-Compressor-<version>-windows-x86_64.zip` — portable build for
  diagnosis.
- A `.sha256` file for each artifact.

The installer requires no administrator rights. Builds are unsigned unless a
future release process explicitly adds code signing, so Windows may show a
SmartScreen warning. Verify the SHA-256 file before testing a build obtained
from someone else.

The installer also adds **Compress with FS PDF Compressor** to the Explorer
menu for PDF files. It is a per-user entry and accepts multiple selected PDFs.
On Windows 11 it may appear under **Show more options**, depending on the
Explorer context-menu mode in use.

## Test before distributing

Install the setup executable on a clean Windows VM and check:

1. The desktop drop zone appears on first launch and accepts one PDF, several
   PDFs, and a folder of PDFs.
2. The three profiles — Preserve, Balanced, and Maximum — all compress a
   representative PDF without displaying a console window.
3. Launching the installed shortcut again brings the existing app forward
   instead of creating another instance.
4. Closing the main window leaves the desktop drop zone available; double-click
   it to reopen the window.
5. With **Keep original** off, the compressed file retains the original name
   and the previous PDF is in the Windows Recycle Bin. Restore it once to
   confirm it is recoverable.
6. With **Keep original** on, the original remains beside
   `name compressed.pdf`.

Windows does not yet provide an in-app auto-update mechanism. Obtain new
versions from the project's GitHub releases after they are published.

## Reproducible release builds

For ordinary public releases, build from the exact Git tag that defines the
shared version used by macOS, Linux, and Windows. Set `APP_VERSION` and
`SOURCE_REF` to that version/tag when producing the installer.

The first Windows package is published alongside the existing 1.0.13 release
without rebuilding the already published macOS, Linux, or Snap packages. Its
release notes identify the exact public source commit used for the Windows
build. Future shared releases should build every published platform from the
same version tag.
