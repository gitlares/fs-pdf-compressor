#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Sign an already-published Windows installer without exporting private keys."""

from __future__ import annotations

import argparse
import base64
import hashlib
import re
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

from fs_pdf_compressor.windows_update import PUBLIC_KEY

ROOT = Path(__file__).resolve().parents[1]
SPARKLE = "http://www.andymatuschak.org/xml-namespaces/sparkle"
ET.register_namespace("sparkle", SPARKLE)


def release_tag(version: str) -> str:
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:\.\d+)?", version):
        raise ValueError("Expected a stable product version or Windows revision")
    return f"v{version}-windows" if version.count(".") == 3 else f"v{version}"


def verify_signature(installer: Path, signature: str) -> None:
    # Verify against the public key embedded in the Windows app, rather than
    # merely trusting whichever signing identity is in the current Keychain.
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    key = Ed25519PublicKey.from_public_bytes(base64.b64decode(PUBLIC_KEY, validate=True))
    key.verify(base64.b64decode(signature, validate=True), installer.read_bytes())


def update_feed(feed: Path, installer: Path, version: str, signature: str) -> None:
    tag = release_tag(version)
    if installer.name != f"FS-PDF-Compressor-{version}-windows-x86_64-setup.exe":
        raise ValueError("Installer filename does not match the requested version")
    verify_signature(installer, signature)
    document = ET.parse(feed)
    channel = document.getroot().find("channel")
    if channel is None:
        raise ValueError("Appcast channel is missing")
    for item in list(channel.findall("item")):
        enclosure = item.find("enclosure")
        if enclosure is not None and enclosure.get(f"{{{SPARKLE}}}version") == version:
            channel.remove(item)
    item = ET.Element("item")
    ET.SubElement(item, "title").text = f"FS PDF Compressor {version}"
    ET.SubElement(item, "pubDate").text = format_datetime(datetime.now(timezone.utc))
    ET.SubElement(item, f"{{{SPARKLE}}}releaseNotesLink").text = f"https://github.com/gitlares/fs-pdf-compressor/releases/tag/{tag}"
    ET.SubElement(item, "enclosure", {
        "url": f"https://github.com/gitlares/fs-pdf-compressor/releases/download/{tag}/{installer.name}",
        "length": str(installer.stat().st_size),
        "type": "application/octet-stream",
        f"{{{SPARKLE}}}version": version,
        f"{{{SPARKLE}}}shortVersionString": version,
        f"{{{SPARKLE}}}os": "windows-x64",
        f"{{{SPARKLE}}}edSignature": signature,
        f"{{{SPARKLE}}}installerArguments": "/SILENT /SP- /NOICONS /NORESTART",
    })
    channel.append(item)
    items = channel.findall("item")
    for old in items:
        channel.remove(old)
    for old in sorted(items, key=lambda i: tuple(int(p) for p in i.find("enclosure").get(f"{{{SPARKLE}}}version").split(".")), reverse=True):
        channel.append(old)
    ET.indent(document, space="  ")
    pending = feed.with_suffix(".pending.xml")
    document.write(pending, encoding="utf-8", xml_declaration=True)
    pending.replace(feed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("installer", type=Path)
    parser.add_argument("--sign-tool", type=Path, default=Path.home() / "Library/Caches/FS PDF Compressor/Sparkle-2.9.4/bin/sign_update")
    args = parser.parse_args()
    try:
        tag = release_tag(args.version)
    except ValueError as error:
        parser.error(str(error))
    expected = f"FS-PDF-Compressor-{args.version}-windows-x86_64-setup.exe"
    if args.installer.name != expected or not args.installer.is_file():
        parser.error("Expected the matching release installer")
    url = f"https://github.com/gitlares/fs-pdf-compressor/releases/download/{tag}/{expected}.sha256"
    with urllib.request.urlopen(url, timeout=30) as response:
        checksum = response.read(4096).decode("ascii").split()[0]
    if checksum != hashlib.sha256(args.installer.read_bytes()).hexdigest():
        raise RuntimeError("Published installer checksum does not match the local file")
    signature = subprocess.run([str(args.sign_tool), "-p", str(args.installer)], check=True, text=True, capture_output=True).stdout.strip()
    update_feed(ROOT / "docs/appcast-windows.xml", args.installer, args.version, signature)
    print(f"Updated docs/appcast-windows.xml for {args.version}; not published.")


if __name__ == "__main__":
    main()
