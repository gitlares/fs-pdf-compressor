#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

"""Build an Apple Silicon FS PDF Compressor.app with embedded Ghostscript.

Run with the project's build virtual environment:
    .build-venv/bin/python build_macos.py

The produced app targets Apple Silicon. It applies an ad-hoc signature, but does
not use a Developer ID certificate or Apple notarization.
"""

from __future__ import annotations

import os
import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DIST = ROOT / "release"
APP_NAME = "FS PDF Compressor"
APP_VERSION = "1.0.0"
APP = DIST / f"{APP_NAME}.app"
DMG_NAME = f"FS-PDF-Compressor-{APP_VERSION}-arm64.dmg"
GHOSTSCRIPT_PREFIX = Path("/opt/homebrew/opt/ghostscript").resolve()


def run(*args: str) -> None:
    print("+", " ".join(args))
    subprocess.run(args, check=True)


def dependencies(path: Path) -> list[tuple[str, Path]]:
    """Return install names and resolved non-system dylibs reported by otool."""
    result = subprocess.run(
        ["otool", "-L", str(path)], check=True, text=True, capture_output=True
    )
    paths: list[tuple[str, Path]] = []
    for line in result.stdout.splitlines()[1:]:
        match = re.match(r"\s*(\S+?)(?:\s+\(compatibility version|$)", line)
        if not match:
            continue
        dependency = match.group(1)
        if dependency.startswith(("/usr/lib/", "/System/Library/")):
            continue
        if dependency.startswith(("@rpath/", "@loader_path/")):
            # Homebrew libraries commonly reference a sibling through @rpath.
            # Resolve the source-side symlink now so we can rewrite it in the app.
            candidate = path.parent / Path(dependency).name
        elif dependency.startswith("@"):
            continue
        else:
            candidate = Path(dependency)
        if candidate.exists() and candidate.suffix == ".dylib":
            paths.append((dependency, candidate.resolve()))
    return paths


def bundle_ghostscript() -> None:
    source_gs = GHOSTSCRIPT_PREFIX / "bin" / "gs"
    if not source_gs.is_file():
        raise RuntimeError(
            "Ghostscript para Apple Silicon no está instalado. Ejecuta: brew install ghostscript"
        )

    resources = APP / "Contents" / "Resources" / "ghostscript"
    frameworks = APP / "Contents" / "Frameworks" / "Ghostscript"
    (resources / "bin").mkdir(parents=True)
    frameworks.mkdir(parents=True)
    shutil.copy2(source_gs, resources / "bin" / "gs")
    source_resources = GHOSTSCRIPT_PREFIX / "share" / "ghostscript"
    destination_resources = resources / "share" / "ghostscript"
    # Homebrew includes a `10.xx -> .` compatibility symlink. Copying the whole
    # directory while dereferencing it loops forever, so copy the real folders.
    for name in ("Resource", "fonts", "iccprofiles", "lib"):
        shutil.copytree(source_resources / name, destination_resources / name)
    shutil.copy2(GHOSTSCRIPT_PREFIX / "LICENSE", resources / "GHOSTSCRIPT-LICENSE.txt")

    pending = [source_gs.resolve()]
    copied: dict[Path, Path] = {}
    install_names: dict[Path, set[str]] = {}
    while pending:
        current = pending.pop()
        for install_name, dependency in dependencies(current):
            install_names.setdefault(dependency, set()).add(install_name)
            if dependency in copied:
                continue
            destination = frameworks / dependency.name
            shutil.copy2(dependency, destination)
            copied[dependency] = destination
            pending.append(dependency)

    gs_destination = resources / "bin" / "gs"
    for original, destination in copied.items():
        run("install_name_tool", "-id", f"@loader_path/{destination.name}", str(destination))
    for binary in [gs_destination, *copied.values()]:
        for original, destination in copied.items():
            for install_name in install_names[original]:
                run(
                    "install_name_tool",
                    "-change",
                    install_name,
                    # gs lives in Contents/Resources/ghostscript/bin, so it
                    # needs three parent traversals to reach Contents/Frameworks.
                    f"@loader_path/../../../Frameworks/Ghostscript/{destination.name}"
                    if binary == gs_destination
                    else f"@loader_path/{destination.name}",
                    str(binary),
                )


def bundle_homebrew_licenses() -> None:
    """Bundle license files for Ghostscript and its installed dependencies."""
    result = subprocess.run(
        ["brew", "deps", "--installed", "--formula", "ghostscript"],
        check=True,
        text=True,
        capture_output=True,
    )
    formulae = ["ghostscript", *result.stdout.splitlines()]
    destination_root = APP / "Contents" / "Resources" / "third-party-licenses"
    destination_root.mkdir(parents=True, exist_ok=True)
    patterns = ("LICENSE*", "COPYING*", "NOTICE*", "COPYRIGHT*")

    for formula in formulae:
        prefix_result = subprocess.run(
            ["brew", "--prefix", formula], check=True, text=True, capture_output=True
        )
        prefix = Path(prefix_result.stdout.strip())
        candidates: list[Path] = []
        for pattern in patterns:
            candidates.extend(prefix.glob(pattern))
            candidates.extend((prefix / "share" / "doc" / formula).glob(pattern))
        files = sorted({path.resolve() for path in candidates if path.is_file()})
        if not files:
            continue
        formula_destination = destination_root / formula
        formula_destination.mkdir()
        for index, source in enumerate(files, start=1):
            name = source.name if index == 1 else f"{index}-{source.name}"
            shutil.copy2(source, formula_destination / name)


def write_info_plist() -> None:
    info_plist = APP / "Contents" / "Info.plist"
    with info_plist.open("rb") as file:
        info = plistlib.load(file)
    info.update(
        {
            "CFBundleDisplayName": APP_NAME,
            "CFBundleIdentifier": "com.daniellares.fspdfcompressor",
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
            "NSHumanReadableCopyright": "© 2026 Daniel Lares",
            "LSApplicationCategoryType": "public.app-category.utilities",
            "LSMinimumSystemVersion": "13.0",
        }
    )
    with info_plist.open("wb") as file:
        plistlib.dump(info, file)


def main() -> None:
    if os.uname().machine != "arm64":
        raise RuntimeError("Este constructor genera una app Apple Silicon (arm64).")
    shutil.rmtree(DIST, ignore_errors=True)
    run(
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        APP_NAME,
        "--icon",
        str(ROOT / "assets" / "PDFCompresor.icns"),
        "--target-arch",
        "arm64",
        "--distpath",
        str(DIST),
        "--workpath",
        str(ROOT / ".pyinstaller-work"),
        "--specpath",
        str(ROOT / ".pyinstaller-spec"),
        "native_app.py",
    )
    write_info_plist()
    bundle_ghostscript()
    bundle_homebrew_licenses()
    shutil.copy2(ROOT / "LICENSE", APP / "Contents" / "Resources" / "LICENSE.txt")
    shutil.copy2(
        ROOT / "LICENSE",
        APP / "Contents" / "Resources" / "ghostscript" / "AGPL-3.0.txt",
    )
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", APP / "Contents" / "Resources")
    # Resources/ghostscript/bin is not a standard macOS nested-code location,
    # therefore `codesign --deep` does not re-sign gs after install_name_tool.
    # Sign modified Mach-O files first, then seal the outer app bundle.
    ghostscript_bin = APP / "Contents" / "Resources" / "ghostscript" / "bin" / "gs"
    ghostscript_libraries = APP / "Contents" / "Frameworks" / "Ghostscript"
    for binary in [ghostscript_bin, *ghostscript_libraries.glob("*.dylib")]:
        run("codesign", "--force", "--sign", "-", str(binary))
    run("codesign", "--force", "--sign", "-", str(APP))
    dmg_root = DIST / "dmg-root"
    shutil.rmtree(dmg_root, ignore_errors=True)
    dmg_root.mkdir()
    shutil.copytree(APP, dmg_root / APP.name, symlinks=True)
    (dmg_root / "Applications").symlink_to("/Applications")
    run(
        "hdiutil",
        "create",
        "-volname",
        APP_NAME,
        "-srcfolder",
        str(dmg_root),
        "-ov",
        "-format",
        "UDZO",
        str(DIST / DMG_NAME),
    )
    print(f"\nCreated:\n  {APP}\n  {DIST / DMG_NAME}")


if __name__ == "__main__":
    main()
