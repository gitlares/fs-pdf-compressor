#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

"""Build an x86_64 AppImage with the Qt UI and embedded Ghostscript.

Run this on Ubuntu (GitHub Actions does this for releases):
    python3 -m venv .linux-build-venv
    .linux-build-venv/bin/pip install -r requirements-linux.txt
    APPIMAGETOOL=/path/to/appimagetool .linux-build-venv/bin/python build_linux.py
"""

from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
import sys
import hashlib
import json
from importlib.metadata import version as package_version
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DIST = ROOT / os.environ.get("DIST_DIR", "release-linux")
BUILD = ROOT / ".linux-build"
APP_NAME = "FS PDF Compressor"
APP_VERSION = os.environ.get("APP_VERSION", "1.0.7")
ARCHITECTURE = "x86_64"
APPDIR = BUILD / "AppDir"
APPIMAGE_NAME = f"FS-PDF-Compressor-{ARCHITECTURE}.AppImage"
UPDATE_INFORMATION = (
    "zsync|https://github.com/gitlares/fs-pdf-compressor/releases/latest/download/"
    f"{APPIMAGE_NAME}.zsync"
)


def run(*args: str) -> None:
    print("+", " ".join(args))
    subprocess.run(args, check=True)


def command_output(*args: str) -> str:
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout


def write_sha256(path: Path) -> Path:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    checksum_path = path.with_suffix(f"{path.suffix}.sha256")
    checksum_path.write_text(f"{digest.hexdigest()}  {path.name}\n", encoding="utf-8")
    return checksum_path


def require_linux_x86_64() -> None:
    if sys.platform != "linux" or platform.machine() != ARCHITECTURE:
        raise RuntimeError("Linux AppImage builds must run on an x86_64 Linux machine")


def ghostscript_data_dir() -> Path:
    candidates = sorted(Path("/usr/share/ghostscript").glob("*/Resource"))
    if not candidates:
        raise RuntimeError("Ghostscript resources were not found; install the ghostscript package")
    return candidates[-1].parent


def copy_shared_libraries(binary: Path, destination: Path) -> None:
    """Bundle Ghostscript's non-loader shared objects for portable execution."""
    destination.mkdir(parents=True, exist_ok=True)
    for line in command_output("ldd", str(binary)).splitlines():
        if " => " not in line:
            continue
        _, location = line.split(" => ", 1)
        library = Path(location.split(" ", 1)[0])
        if library.is_file():
            shutil.copy2(library, destination / library.name)


def bundle_ghostscript(pyinstaller_resources: Path) -> None:
    source_gs = Path(shutil.which("gs") or "")
    if not source_gs.is_file():
        raise RuntimeError("Ghostscript is not installed. Run: sudo apt-get install ghostscript")
    destination = pyinstaller_resources / "ghostscript"
    (destination / "bin").mkdir(parents=True)
    shutil.copy2(source_gs, destination / "bin" / "gs")
    shutil.copytree(ghostscript_data_dir(), destination / "share" / "ghostscript")
    copy_shared_libraries(source_gs, destination / "lib")
    for candidate in (Path("/usr/share/doc/ghostscript/copyright"), ROOT / "LICENSE"):
        if candidate.is_file():
            shutil.copy2(candidate, destination / candidate.name)
    (destination / "SOURCE_OFFER.md").write_text(
        "Ghostscript is distributed under GNU AGPL-3.0-or-later.\n"
        "Corresponding source: https://github.com/ArtifexSoftware/ghostpdl-downloads\n",
        encoding="utf-8",
    )


def write_appdir(pyinstaller_bundle: Path) -> None:
    application_root = APPDIR / "usr" / "lib" / "fs-pdf-compressor"
    application_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(pyinstaller_bundle, application_root)
    (APPDIR / "usr" / "share" / "applications").mkdir(parents=True)
    (APPDIR / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps").mkdir(parents=True)
    icon = ROOT / "assets" / "PDFCompresor.png"
    shutil.copy2(icon, APPDIR / "fs-pdf-compressor.png")
    shutil.copy2(icon, APPDIR / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps" / "fs-pdf-compressor.png")
    (APPDIR / "fs-pdf-compressor.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=FS PDF Compressor\n"
        "Comment=Fast and Simple PDF compression\nExec=fs-pdf-compressor\n"
        "Icon=fs-pdf-compressor\nCategories=Office;Utility;\nMimeType=application/pdf;\n",
        encoding="utf-8",
    )
    app_run = APPDIR / "AppRun"
    app_run.write_text(
        "#!/bin/sh\nHERE=$(dirname \"$(readlink -f \"$0\")\")\n"
        "exec \"$HERE/usr/lib/fs-pdf-compressor/FS PDF Compressor\" \"$@\"\n",
        encoding="utf-8",
    )
    app_run.chmod(app_run.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def bundle_compliance_documents() -> None:
    """Place the notices and exact runtime record inside the Linux AppImage."""
    destination = APPDIR / "usr" / "share" / "doc" / "fs-pdf-compressor"
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "LICENSE", destination / "AGPL-3.0.txt")
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", destination)
    for source, name in (
        (Path("/usr/share/common-licenses/LGPL-3"), "LGPL-3.0.txt"),
        (Path("/usr/share/common-licenses/GPL-2"), "PyInstaller-GPL-2.0.txt"),
    ):
        if source.is_file():
            shutil.copy2(source, destination / name)
    (destination / "THIRD_PARTY_MANIFEST.json").write_text(
        json.dumps(
            {
                "application_version": APP_VERSION,
                "source_ref": os.environ.get("SOURCE_REF", f"v{APP_VERSION}"),
                "python": sys.version.split()[0],
                "pyside6": package_version("PySide6"),
                "pyinstaller": package_version("PyInstaller"),
                "ghostscript_license": "AGPL-3.0-or-later",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (destination / "SOURCE_OFFER.md").write_text(
        "# Corresponding source\n\n"
        f"This FS PDF Compressor {APP_VERSION} AppImage corresponds to "
        f"{ROOT.name} source ref `{os.environ.get('SOURCE_REF', f'v{APP_VERSION}')}`.\n\n"
        "Application source: https://github.com/gitlares/fs-pdf-compressor\n"
        "Ghostscript source: https://github.com/ArtifexSoftware/ghostpdl-downloads\n"
        "PySide6 source: https://code.qt.io/pyside/pyside-setup\n"
        "PyInstaller source: https://github.com/pyinstaller/pyinstaller\n",
        encoding="utf-8",
    )


def main() -> None:
    require_linux_x86_64()
    appimagetool = Path(os.environ.get("APPIMAGETOOL", shutil.which("appimagetool") or ""))
    if not appimagetool.is_file():
        raise RuntimeError("Set APPIMAGETOOL to a verified appimagetool executable")
    shutil.rmtree(BUILD, ignore_errors=True)
    shutil.rmtree(DIST, ignore_errors=True)
    DIST.mkdir(parents=True)
    run(
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        APP_NAME,
        "--add-data",
        f"{ROOT / 'assets' / 'desktop-drop-hole.png'}:.",
        "linux_app.py",
    )
    pyinstaller_bundle = ROOT / "dist" / APP_NAME
    bundle_ghostscript(pyinstaller_bundle / "_internal")
    write_appdir(pyinstaller_bundle)
    bundle_compliance_documents()
    output = DIST / APPIMAGE_NAME
    generated_zsync = ROOT / f"{APPIMAGE_NAME}.zsync"
    generated_zsync.unlink(missing_ok=True)
    run(
        str(appimagetool),
        "--appimage-extract-and-run",
        str(APPDIR),
        "-u",
        UPDATE_INFORMATION,
        str(output),
    )
    if not generated_zsync.is_file():
        raise RuntimeError("appimagetool did not generate the expected zsync metadata")
    shutil.move(str(generated_zsync), str(DIST / generated_zsync.name))
    checksum_path = write_sha256(output)
    print(f"Built {output}\nChecksum: {checksum_path}")


if __name__ == "__main__":
    main()
