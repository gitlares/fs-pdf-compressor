# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

"""Move files to the platform trash without permanently deleting them."""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import uuid
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
        _move_to_windows_recycle_bin(path)
    elif sys.platform == "darwin":
        _move_to_macos_trash(path)
    else:
        _move_to_freedesktop_trash(path)


def _move_to_windows_recycle_bin(path: Path) -> None:
    """Use the Windows Shell so the file appears in the Recycle Bin."""
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", ctypes.c_ushort),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    FO_DELETE = 3
    FOF_SILENT = 0x0004
    FOF_NOCONFIRMATION = 0x0010
    FOF_ALLOWUNDO = 0x0040
    FOF_NOERRORUI = 0x0400
    source = str(path.resolve()) + "\0\0"
    operation = SHFILEOPSTRUCTW(
        None,
        FO_DELETE,
        source,
        None,
        FOF_SILENT | FOF_NOCONFIRMATION | FOF_ALLOWUNDO | FOF_NOERRORUI,
        False,
        None,
        None,
    )
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
    if result != 0 or operation.fAnyOperationsAborted:
        raise TrashError(f"Windows could not move the original PDF to the Recycle Bin ({result})")


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


def _move_to_freedesktop_trash(path: Path) -> None:
    """Prefer GIO, then use the standard per-user FreeDesktop trash layout."""
    gio = shutil.which("gio")
    if gio:
        result = subprocess.run(
            [gio, "trash", str(path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode == 0:
            return

    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    trash_root = data_home / "Trash"
    files = trash_root / "files"
    info = trash_root / "info"
    files.mkdir(parents=True, exist_ok=True)
    info.mkdir(parents=True, exist_ok=True)
    destination = files / path.name
    while destination.exists():
        destination = files / f"{path.stem} {uuid.uuid4().hex[:8]}{path.suffix}"
    try:
        shutil.move(str(path), str(destination))
        trash_info = info / f"{destination.name}.trashinfo"
        trash_info.write_text(
            "[Trash Info]\n"
            f"Path={quote(str(path.resolve()))}\n"
            f"DeletionDate={datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S')}\n",
            encoding="utf-8",
        )
    except OSError as error:
        raise TrashError(f"Linux could not move the original PDF to the Trash: {error}") from error
