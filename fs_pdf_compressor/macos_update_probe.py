# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

"""Small, untrusted appcast probe used before loading Sparkle on macOS.

The probe never downloads or installs an update. Sparkle remains responsible for
signature verification, user interaction, download, and installation.
"""

from __future__ import annotations

from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree


SPARKLE_NAMESPACE = "http://www.andymatuschak.org/xml-namespaces/sparkle"
MAX_APPCAST_BYTES = 1_048_576


def _version_parts(version: str) -> tuple[int, ...] | None:
    parts = version.split(".")
    if not parts or any(not part.isdecimal() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def _is_newer_or_unknown(candidate: str, installed: str) -> bool:
    candidate_parts = _version_parts(candidate)
    installed_parts = _version_parts(installed)
    if candidate_parts is None or installed_parts is None:
        return True
    width = max(len(candidate_parts), len(installed_parts))
    candidate_parts += (0,) * (width - len(candidate_parts))
    installed_parts += (0,) * (width - len(installed_parts))
    return candidate_parts > installed_parts


def appcast_may_offer_update(appcast: bytes, installed_version: str) -> bool:
    """Return whether Sparkle should inspect a successfully fetched appcast.

    The comparison intentionally errs on the side of loading Sparkle if a
    version cannot be interpreted safely. This function is only a memory-saving
    preflight; it is never an authorization to install an update.
    """
    root = ElementTree.fromstring(appcast)
    version_tag = f"{{{SPARKLE_NAMESPACE}}}version"
    short_version_tag = f"{{{SPARKLE_NAMESPACE}}}shortVersionString"
    for item in root.findall(".//item"):
        if item.find("enclosure") is None:
            continue
        version = item.findtext(version_tag) or item.findtext(short_version_tag)
        if version and _is_newer_or_unknown(version.strip(), installed_version):
            return True
    return False


def probe_for_update(
    feed_url: str,
    installed_version: str,
    *,
    timeout: float = 5.0,
) -> bool | None:
    """Fetch an HTTPS appcast and return ``None`` when it cannot be inspected."""
    parsed_url = urlparse(feed_url)
    if parsed_url.scheme != "https":
        return None
    request = Request(feed_url, headers={"User-Agent": "FS PDF Compressor"})
    try:
        with urlopen(request, timeout=timeout) as response:
            appcast = response.read(MAX_APPCAST_BYTES + 1)
    except (OSError, URLError, ValueError):
        return None
    if len(appcast) > MAX_APPCAST_BYTES:
        return None
    try:
        return appcast_may_offer_update(appcast, installed_version)
    except ElementTree.ParseError:
        return None
