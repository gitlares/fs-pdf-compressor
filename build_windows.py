#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

"""Build an unsigned, portable x86_64 Windows candidate with Ghostscript.

Run this from an x64 Python installation on Windows.  The package is intended
for private testing until it has passed the UTM validation checklist; this
script neither signs nor publishes anything.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from importlib.metadata import version as package_version
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DIST = ROOT / os.environ.get("DIST_DIR", "release-windows")
BUILD = ROOT / ".windows-build"
APP_NAME = "FS PDF Compressor"
APP_VERSION = os.environ.get("APP_VERSION", "1.0.13")
ARCHITECTURE = "x86_64"
PACKAGE_NAME = f"FS-PDF-Compressor-{APP_VERSION}-windows-{ARCHITECTURE}"


def run(*args: str) -> None:
    print("+", " ".join(args))
    subprocess.run(args, check=True)


def write_sha256(path: Path) -> Path:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    checksum_path = path.with_suffix(f"{path.suffix}.sha256")
    checksum_path.write_text(f"{digest.hexdigest()}  {path.name}\n", encoding="utf-8")
    return checksum_path


def require_windows_x86_64() -> None:
    machine = platform.machine().lower()
    if sys.platform != "win32" or machine not in {"amd64", "x86_64"}:
        raise RuntimeError(
            "Windows builds require an x64 Python installation on Windows. "
            "On Windows ARM, install the x64 Python build under Windows emulation."
        )


def ghostscript_root() -> Path:
    configured = os.environ.get("GHOSTSCRIPT_ROOT")
    candidates = [Path(configured)] if configured else []
    program_files = os.environ.get("ProgramFiles")
    if program_files:
        candidates.extend(
            sorted((Path(program_files) / "gs").glob("gs*"), reverse=True)
        )
    for candidate in candidates:
        if (candidate / "bin" / "gswin64c.exe").is_file():
            return candidate
    raise RuntimeError(
        "Ghostscript x64 was not found. Install the official AGPL Ghostscript "
        "runtime or set GHOSTSCRIPT_ROOT to its gs10.xx directory."
    )


def inno_setup_compiler() -> Path:
    configured = os.environ.get("ISCC")
    candidates = [Path(configured)] if configured else []
    for variable in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(variable)
        if base:
            candidates.append(Path(base) / "Inno Setup 6" / "ISCC.exe")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError(
        "Inno Setup 6 was not found. Install it for the private Windows installer "
        "or set ISCC to the full path of ISCC.exe."
    )


def ghostscript_version(binary: Path) -> str:
    output = subprocess.run(
        [str(binary), "--version"], check=True, text=True, capture_output=True
    ).stdout
    match = re.search(r"\b(\d+\.\d+\.\d+)\b", output)
    if not match:
        raise RuntimeError("Could not determine the bundled Ghostscript version")
    return match.group(1)


def bundle_ghostscript(resources: Path) -> tuple[Path, str]:
    source_root = ghostscript_root()
    source_binary = source_root / "bin" / "gswin64c.exe"
    version = ghostscript_version(source_binary)
    destination = resources / "ghostscript"
    bin_directory = destination / "bin"
    bin_directory.mkdir(parents=True)
    for source in (source_root / "bin").glob("gs*.exe"):
        shutil.copy2(source, bin_directory / source.name)
    for source in (source_root / "bin").glob("*.dll"):
        shutil.copy2(source, bin_directory / source.name)
    for name in ("Resource", "lib"):
        source = source_root / name
        if source.is_dir():
            shutil.copytree(source, destination / name)
    if not (destination / "Resource" / "Init").is_dir():
        raise RuntimeError("The Ghostscript Resource/Init directory is missing")
    for source in (source_root / "COPYING", source_root / "LICENSE", ROOT / "LICENSE"):
        if source.is_file():
            shutil.copy2(source, destination / "AGPL-3.0.txt")
            break
    else:
        raise RuntimeError("Could not locate the Ghostscript AGPL license text")
    source_tag = f"gs{version.replace('.', '')}"
    (destination / "SOURCE_OFFER.md").write_text(
        "# Corresponding source\n\n"
        f"This package includes unmodified Ghostscript {version}, distributed under "
        "GNU AGPL-3.0-or-later. Corresponding source:\n\n"
        f"https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/{source_tag}/"
        f"ghostpdl-{version}.tar.xz\n",
        encoding="utf-8",
    )
    return destination, version


def bundle_compliance_documents(resources: Path, ghostscript_version_value: str) -> None:
    destination = resources / "licenses"
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "LICENSE", destination / "FS-PDF-Compressor-AGPL-3.0.txt")
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", destination)
    source_tag = f"gs{ghostscript_version_value.replace('.', '')}"
    (resources / "SOURCE_OFFER.md").write_text(
        "# Corresponding source\n\n"
        f"This unsigned private Windows candidate corresponds to FS PDF Compressor {APP_VERSION}.\n\n"
        "Application source: https://github.com/gitlares/fs-pdf-compressor\n"
        f"Ghostscript {ghostscript_version_value} source: "
        f"https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/{source_tag}/"
        f"ghostpdl-{ghostscript_version_value}.tar.xz\n"
        "PySide6 source: https://code.qt.io/pyside/pyside-setup\n"
        "PyInstaller source: https://github.com/pyinstaller/pyinstaller\n",
        encoding="utf-8",
    )
    (resources / "THIRD_PARTY_MANIFEST.json").write_text(
        json.dumps(
            {
                "application_version": APP_VERSION,
                "source_ref": os.environ.get("SOURCE_REF", "codex/windows-trash-support"),
                "python": sys.version.split()[0],
                "pyside6": package_version("PySide6"),
                "pyinstaller": package_version("PyInstaller"),
                "ghostscript": ghostscript_version_value,
                "ghostscript_license": "AGPL-3.0-or-later",
                "ghostscript_modified": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    require_windows_x86_64()
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
        "--icon",
        str(ROOT / "assets" / "PDFCompresor.ico"),
        "--add-data",
        f"{ROOT / 'assets' / 'desktop-drop-hole.png'}{os.pathsep}.",
        "--add-data",
        f"{ROOT / 'assets' / 'PDFCompresor.png'}{os.pathsep}.",
        "--add-data",
        f"{ROOT / 'assets' / 'PDFCompresor.ico'}{os.pathsep}.",
        "windows_app.py",
    )
    application = ROOT / "dist" / APP_NAME
    resources = application / "_internal"
    _, bundled_ghostscript_version = bundle_ghostscript(resources)
    bundle_compliance_documents(resources, bundled_ghostscript_version)
    archive_base = DIST / PACKAGE_NAME
    archive = Path(shutil.make_archive(str(archive_base), "zip", ROOT / "dist", APP_NAME))
    checksum = write_sha256(archive)
    installer = DIST / f"{PACKAGE_NAME}-setup.exe"
    run(
        str(inno_setup_compiler()),
        f"/DSourceDir={application}",
        f"/DOutputDir={DIST}",
        f"/DAppVersion={APP_VERSION}",
        f"/DOutputName={installer.stem}",
        str(ROOT / "installer" / "windows.iss"),
    )
    installer_checksum = write_sha256(installer)
    print(
        "Built unsigned private candidates:\n"
        f"Portable ZIP: {archive}\nChecksum: {checksum}\n"
        f"Installer: {installer}\nChecksum: {installer_checksum}"
    )


if __name__ == "__main__":
    main()
