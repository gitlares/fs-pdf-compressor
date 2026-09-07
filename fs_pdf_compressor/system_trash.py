# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

"""Move files to the platform trash without permanently deleting them."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import quote


class TrashError(OSError):
    """The operating system rejected a request to move a file to its trash."""


def move_to_system_trash(path: Path) -> None:
    """Move ``path`` to the user's native trash or raise ``TrashError``.

    This module deliberately uses operating-system facilities instead of a
    permanent unlink.  It has no network activity and does not inspect PDF
    content.
    """
    if not path.is_file():
        raise TrashError(f"Cannot move a missing file to trash: {path}")
    if sys.platform == "win32":
        return _move_to_windows_recycle_bin(path)
    elif sys.platform == "darwin":
        return _move_to_macos_trash(path)
    else:
        return _move_to_freedesktop_trash(path)


def _move_to_windows_recycle_bin(path: Path) -> None:
    try:
        from fs_pdf_compressor.windows_trash import recycle
        return recycle(path)
    except Exception as error:
        raise TrashError(f"Windows could not recycle the original: {error}") from error


def _move_to_macos_trash(path: Path) -> None:
    """Use NSFileManager's native Trash API without automating Finder."""
    try:
        from Foundation import NSFileManager, NSURL
    except ImportError as error:  # pragma: no cover - only relevant to broken macOS installs.
        raise TrashError("The macOS Foundation runtime is unavailable") from error

    result = NSFileManager.defaultManager().trashItemAtURL_resultingItemURL_error_(
        NSURL.fileURLWithPath_(str(path)), None, None
    )
    succeeded = result[0] if isinstance(result, tuple) else bool(result)
    if not succeeded:
        raise TrashError("macOS could not move the original PDF to the Trash")
    if isinstance(result, tuple) and result[1] is not None:
        return Path(str(result[1].path()))


def _move_to_freedesktop_trash(path: Path) -> None:
    """Prefer GIO, then use the standard per-user FreeDesktop trash layout."""
    if os.environ.get("SNAP"):
        _move_to_portal_trash(path)
        return
    gio = shutil.which("gio")
    if gio:
        result = subprocess.run(
            [gio, "trash", str(path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return

    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    trash_root = data_home / "Trash"
    files = trash_root / "files"
    info = trash_root / "info"
    files.mkdir(parents=True, exist_ok=True, mode=0o700)
    info.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, reserved = tempfile.mkstemp(prefix=f"{path.stem}-", suffix=path.suffix, dir=files)
    os.close(fd)
    destination = Path(reserved)
    trash_info = info / f"{destination.name}.trashinfo"
    original_location = str(path.resolve())
    try:
        with trash_info.open("x", encoding="utf-8") as metadata:
            metadata.write(
            "[Trash Info]\n"
            f"Path={quote(original_location)}\n"
            f"DeletionDate={datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S')}\n",
            )
        # Cross-device moves must use GIO; never copy then delete here.
        os.replace(path, destination)
    except OSError as error:
        destination.unlink(missing_ok=True)
        trash_info.unlink(missing_ok=True)
        raise TrashError(f"Linux could not move the original PDF to the Trash: {error}") from error


def _move_to_portal_trash(path):
    """Use the host desktop trash from a confined Snap, not a private trash."""
    from PySide6 import QtDBus

    with path.open("r+b") as source:
        message = QtDBus.QDBusMessage.createMethodCall(
            "org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.Trash", "TrashFile",
        )
        message.setArguments([QtDBus.QDBusUnixFileDescriptor(source.fileno())])
        reply = QtDBus.QDBusConnection.sessionBus().call(message, QtDBus.QDBus.Block, 5000)
        if reply.type() == QtDBus.QDBusMessage.ErrorMessage or reply.arguments() != [1]:
            raise TrashError(f"The desktop portal could not recycle the original: {reply.errorMessage()} {reply.arguments()}")
