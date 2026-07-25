#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

"""Safe, user-initiated updates for the released Linux AppImage.

The AppImage also carries standard zsync update information for external
AppImage tools.  This module provides the small in-app path: GitHub serves the
current release over HTTPS; the downloaded file must match the SHA-256 asset
published alongside it before a separate helper replaces the old AppImage.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path


REPOSITORY = "gitlares/fs-pdf-compressor"
RELEASE_API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
APPIMAGE_ASSET = "FS-PDF-Compressor-x86_64.AppImage"
SHA256_ASSET = f"{APPIMAGE_ASSET}.sha256"


@dataclass(frozen=True)
class Release:
    version: str
    appimage_url: str
    sha256_url: str


def _request(url: str):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "FS-PDF-Compressor"}),
        timeout=20,
    )


def version_key(value: str) -> tuple[int, ...]:
    """Compare the numeric release line without accepting arbitrary labels."""
    normalized = value.removeprefix("v").split("-", 1)[0]
    parts = normalized.split(".")
    if not parts or any(not part.isdecimal() for part in parts):
        raise ValueError(f"Unsupported release version: {value}")
    return tuple(int(part) for part in parts)


def available_release(current_version: str) -> Release | None:
    with _request(RELEASE_API_URL) as response:
        payload = json.load(response)
    version = str(payload["tag_name"]).removeprefix("v")
    if version_key(version) <= version_key(current_version):
        return None
    assets = {asset["name"]: asset["browser_download_url"] for asset in payload["assets"]}
    try:
        return Release(version, assets[APPIMAGE_ASSET], assets[SHA256_ASSET])
    except KeyError as error:
        raise RuntimeError("The latest release is missing its Linux update files") from error


def _expected_sha256(url: str) -> str:
    with _request(url) as response:
        fields = response.read().decode("utf-8").strip().split()
    if not fields or len(fields[0]) != 64:
        raise RuntimeError("The release checksum file is malformed")
    return fields[0].lower()


def download_verified_appimage(release: Release, destination: Path, progress) -> Path:
    """Download ``release`` beside the running AppImage and verify its digest."""
    expected_digest = _expected_sha256(release.sha256_url)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.download")
    digest = hashlib.sha256()
    try:
        with _request(release.appimage_url) as response, temporary.open("wb") as output:
            total = int(response.headers.get("Content-Length", "0"))
            received = 0
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                digest.update(chunk)
                received += len(chunk)
                progress(received, total)
        if digest.hexdigest().lower() != expected_digest:
            raise RuntimeError("The downloaded AppImage did not match its published SHA-256 checksum")
        temporary.chmod(0o755)
        return temporary
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def replace_after_exit(current: Path, replacement: Path) -> None:
    """Start a short-lived helper that atomically swaps the file after exit."""
    script = (
        "while kill -0 {pid} 2>/dev/null; do sleep 0.1; done; "
        "mv -f {replacement} {current}; chmod 755 {current}; exec {current}"
    ).format(
        pid=os.getpid(),
        replacement=shlex.quote(str(replacement)),
        current=shlex.quote(str(current)),
    )
    subprocess.Popen(
        ["/bin/sh", "-c", script],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
