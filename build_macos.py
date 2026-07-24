#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

"""Build an Apple Silicon FS PDF Compressor.app with embedded Ghostscript.

Run with the project's build virtual environment:
    MACOS_SIGNING_IDENTITY="Developer ID Application: ..." \
        .build-venv/bin/python build_macos.py

Without ``MACOS_SIGNING_IDENTITY`` the build falls back to an ad-hoc signature
for local development. Release builds use Developer ID, hardened runtime and a
secure timestamp. Notarization is performed after the build with ``notarytool``.
"""

from __future__ import annotations

import os
import json
import hashlib
import plistlib
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
# A test build must never replace an artifact already submitted to Apple.
# Set DIST_DIR for a separate local build directory (for example, release-test).
DIST = Path(os.environ.get("DIST_DIR", str(ROOT / "release")))
APP_NAME = "FS PDF Compressor"
APP_VERSION = os.environ.get("APP_VERSION", "1.0.4")
APP = DIST / f"{APP_NAME}.app"
DMG_NAME = f"FS-PDF-Compressor-{APP_VERSION}-arm64.dmg"
GHOSTSCRIPT_PREFIX = Path("/opt/homebrew/opt/ghostscript").resolve()
SIGNING_IDENTITY = os.environ.get("MACOS_SIGNING_IDENTITY", "-")
REPOSITORY_URL = "https://github.com/gitlares/fs-pdf-compressor"
SPARKLE_VERSION = "2.9.4"
SPARKLE_ARCHIVE_URL = (
    "https://github.com/sparkle-project/Sparkle/releases/download/"
    f"{SPARKLE_VERSION}/Sparkle-{SPARKLE_VERSION}.tar.xz"
)
SPARKLE_ARCHIVE_SHA256 = "ce89daf967db1e1893ed3ebd67575ed82d3902563e3191ca92aaec9164fbdef9"
SPARKLE_CACHE = Path.home() / "Library" / "Caches" / APP_NAME / f"Sparkle-{SPARKLE_VERSION}"
SPARKLE_FEED_URL = "https://gitlares.github.io/fs-pdf-compressor/appcast.xml"


def run(*args: str) -> None:
    print("+", " ".join(args))
    subprocess.run(args, check=True)


def sign(
    path: Path, *, hardened: bool = True, preserve_entitlements: bool = False
) -> None:
    command = ["codesign", "--force", "--sign", SIGNING_IDENTITY]
    if SIGNING_IDENTITY == "-":
        command.append("--timestamp=none")
    else:
        command.append("--timestamp")
        if hardened:
            command.extend(("--options", "runtime"))
    if preserve_entitlements:
        command.append("--preserve-metadata=entitlements")
    command.append(str(path))
    run(*command)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_sparkle(archive: Path, destination: Path) -> None:
    with tarfile.open(archive, "r:xz") as package:
        root = destination.resolve()
        for member in package.getmembers():
            target = (root / member.name).resolve()
            if target != root and root not in target.parents:
                raise RuntimeError("Refusing an unsafe path in the Sparkle archive")
        package.extractall(destination)


def ensure_sparkle_distribution() -> Path:
    """Fetch the pinned Sparkle framework without placing it in Git."""
    framework = SPARKLE_CACHE / "Sparkle.framework"
    if framework.is_dir():
        return framework

    SPARKLE_CACHE.mkdir(parents=True, exist_ok=True)
    archive = SPARKLE_CACHE / f"Sparkle-{SPARKLE_VERSION}.tar.xz"
    if not archive.is_file():
        print(f"+ download Sparkle {SPARKLE_VERSION}")
        urllib.request.urlretrieve(SPARKLE_ARCHIVE_URL, archive)
    if _sha256(archive) != SPARKLE_ARCHIVE_SHA256:
        raise RuntimeError("Sparkle archive checksum did not match the pinned release")
    _extract_sparkle(archive, SPARKLE_CACHE)
    if not framework.is_dir():
        raise RuntimeError("The pinned Sparkle archive did not contain Sparkle.framework")
    return framework


def sparkle_public_key() -> str:
    """Read the public half of the existing Sparkle key from the Keychain."""
    distribution = ensure_sparkle_distribution()
    command = distribution.parent / "bin" / "generate_keys"
    result = subprocess.run([str(command), "-p"], check=True, text=True, capture_output=True)
    public_key = result.stdout.strip()
    if not re.fullmatch(r"[A-Za-z0-9+/]{43}=", public_key):
        raise RuntimeError("Could not read the existing Sparkle public key from Keychain")
    return public_key


def bundle_sparkle() -> Path:
    framework = ensure_sparkle_distribution()
    destination = APP / "Contents" / "Frameworks" / "Sparkle.framework"
    shutil.copytree(framework, destination, symlinks=True)
    license_source = SPARKLE_CACHE / "LICENSE"
    if not license_source.is_file():
        raise RuntimeError("Could not locate Sparkle's MIT license")
    license_destination = APP / "Contents" / "Resources" / "third-party-licenses" / "sparkle"
    license_destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(license_source, license_destination / "MIT-LICENSE.txt")
    return destination


def sign_sparkle_framework(framework: Path) -> None:
    """Re-sign Sparkle's nested helpers bottom-up for notarization.

    Sparkle distributes its helpers with ad-hoc signatures. Unlike Xcode's
    Archive/Export path, this custom build must explicitly sign each helper.
    """
    version = framework / "Versions" / "Current"
    services = version / "XPCServices"
    sign(services / "Installer.xpc")
    sign(services / "Downloader.xpc", preserve_entitlements=True)
    sign(version / "Autoupdate")
    sign(version / "Updater.app")
    sign(framework)


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
            "Ghostscript for Apple Silicon is not installed. Run: brew install ghostscript"
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


def _copy_required_license(destination: Path, candidates: list[Path]) -> None:
    """Copy the first available license file, failing rather than omitting it."""
    for source in candidates:
        if source.is_file():
            shutil.copy2(source, destination)
            return
    names = ", ".join(str(candidate) for candidate in candidates)
    raise RuntimeError(f"Could not locate required third-party license: {names}")


def package_version(package: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "show", package],
        check=True,
        text=True,
        capture_output=True,
    )
    for line in result.stdout.splitlines():
        if line.startswith("Version: "):
            return line.removeprefix("Version: ")
    raise RuntimeError(f"Could not determine the installed version of {package}")


def bundle_python_runtime_licenses() -> dict[str, str]:
    """Bundle licenses for runtime components PyInstaller copies into the app."""
    site_packages = next(
        (Path(entry) for entry in sys.path if entry.endswith("site-packages")), None
    )
    if site_packages is None:
        raise RuntimeError("Could not locate the build environment site-packages directory")

    destination = APP / "Contents" / "Resources" / "third-party-licenses" / "python-runtime"
    destination.mkdir(parents=True, exist_ok=True)
    python_executable = Path(sys.executable).resolve()
    _copy_required_license(
        destination / "Python-PSF-LICENSE.txt",
        [parent / "LICENSE" for parent in python_executable.parents],
    )
    _copy_required_license(
        destination / "PyInstaller-GPL-2.0-with-exception.txt",
        list(site_packages.glob("pyinstaller-*.dist-info/licenses/COPYING.txt")),
    )
    _copy_required_license(
        destination / "PyObjC-MIT-LICENSE.txt",
        list(site_packages.glob("pyobjc_framework_cocoa-*.dist-info/licenses/LICENSE.txt")),
    )
    return {
        "python": sys.version.split()[0],
        "pyinstaller": package_version("PyInstaller"),
        "pyobjc_core": package_version("pyobjc-core"),
        "pyobjc_framework_cocoa": package_version("pyobjc-framework-Cocoa"),
    }


def write_compliance_manifest(python_runtime: dict[str, str]) -> None:
    """Record versions, licenses, and source locations for the exact bundle."""
    formulae = ["ghostscript"]
    result = subprocess.run(
        ["brew", "deps", "--installed", "--formula", "ghostscript"],
        check=True,
        text=True,
        capture_output=True,
    )
    formulae.extend(result.stdout.splitlines())
    formula_info = subprocess.run(
        ["brew", "info", "--json=v2", *formulae],
        check=True,
        text=True,
        capture_output=True,
    )
    manifest = json.loads(formula_info.stdout)
    homebrew = []
    for formula in manifest["formulae"]:
        stable = formula.get("urls", {}).get("stable", {})
        homebrew.append(
            {
                "name": formula["name"],
                "version": formula.get("versions", {}).get("stable"),
                "license": formula.get("license"),
                "source_url": stable.get("url"),
            }
        )

    source_ref = os.environ.get("SOURCE_REF", f"v{APP_VERSION}")
    resources = APP / "Contents" / "Resources"
    (resources / "THIRD_PARTY_MANIFEST.json").write_text(
        json.dumps(
            {
                "application_version": APP_VERSION,
                "source_ref": source_ref,
                "python_runtime": python_runtime,
                "homebrew_dependencies": sorted(homebrew, key=lambda item: item["name"]),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    (resources / "SOURCE_OFFER.md").write_text(
        "# Corresponding source\n\n"
        f"This FS PDF Compressor {APP_VERSION} distribution corresponds to source ref "
        f"`{source_ref}` in:\n\n{REPOSITORY_URL}/tree/{source_ref}\n\n"
        "The bundled component and Ghostscript dependency versions, licenses, and upstream source URLs are "
        "listed in `THIRD_PARTY_MANIFEST.json`. The application source and build script "
        "are distributed under AGPL-3.0-or-later.\n"
    )


def write_info_plist(update_public_key: str) -> None:
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
            "SUFeedURL": SPARKLE_FEED_URL,
            "SUPublicEDKey": update_public_key,
            "SUEnableAutomaticChecks": True,
            "SUScheduledCheckInterval": 86400,
            "SUAutomaticallyUpdate": False,
        }
    )
    with info_plist.open("wb") as file:
        plistlib.dump(info, file)


def main() -> None:
    if os.uname().machine != "arm64":
        raise RuntimeError("Este constructor genera una app Apple Silicon (arm64).")
    shutil.rmtree(DIST, ignore_errors=True)
    pyinstaller = [
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
    ]
    if SIGNING_IDENTITY != "-":
        pyinstaller.extend(("--codesign-identity", SIGNING_IDENTITY))
    pyinstaller.append("native_app.py")
    run(*pyinstaller)
    update_public_key = sparkle_public_key()
    write_info_plist(update_public_key)
    sparkle_framework = bundle_sparkle()
    bundle_ghostscript()
    bundle_homebrew_licenses()
    python_runtime = bundle_python_runtime_licenses()
    write_compliance_manifest(python_runtime)
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
        sign(binary)
    sign_sparkle_framework(sparkle_framework)
    sign(APP)
    run("codesign", "--verify", "--deep", "--strict", "--verbose=2", str(APP))
    update_zip = DIST / f"FS-PDF-Compressor-{APP_VERSION}-arm64.zip"
    run("ditto", "-c", "-k", "--keepParent", str(APP), str(update_zip))
    dmg_root = DIST / "dmg-root"
    shutil.rmtree(dmg_root, ignore_errors=True)
    dmg_root.mkdir()
    shutil.copytree(APP, dmg_root / APP.name, symlinks=True)
    (dmg_root / "Applications").symlink_to("/Applications")
    dmg_path = DIST / DMG_NAME
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
        str(dmg_path),
    )
    if SIGNING_IDENTITY != "-":
        sign(dmg_path, hardened=False)
        run("codesign", "--verify", "--verbose=2", str(dmg_path))
    print(f"\nCreated:\n  {APP}\n  {dmg_path}\n  {update_zip}")


if __name__ == "__main__":
    main()
