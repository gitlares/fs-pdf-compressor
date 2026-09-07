# SPDX-License-Identifier: AGPL-3.0-or-later
"""Nonblocking operating-system locks released automatically on process exit."""

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path


class FileBusyError(OSError):
    pass


@contextmanager
def document_lock(path):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        kernel.CreateMutexW.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.ReleaseMutex.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        key = hashlib.sha256(os.path.normcase(str(Path(path).resolve())).encode()).hexdigest()
        handle = kernel.CreateMutexW(None, False, "Local\\FSPDF-" + key)
        if not handle:
            raise OSError("Cannot create document lock")
        acquired = False
        try:
            acquired = kernel.WaitForSingleObject(handle, 0) in (0, 0x80)
            if not acquired:
                raise FileBusyError("This PDF is already being compressed")
            yield
        finally:
            if acquired:
                kernel.ReleaseMutex(handle)
            kernel.CloseHandle(handle)
    else:
        import fcntl

        with open(path, "rb") as source:
            try:
                fcntl.flock(source, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise FileBusyError("This PDF is already being compressed") from error
            try:
                yield
            finally:
                fcntl.flock(source, fcntl.LOCK_UN)
