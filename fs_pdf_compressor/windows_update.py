# SPDX-License-Identifier: AGPL-3.0-or-later
"""WinSparkle bridge. Native callbacks never access Qt widgets."""

from __future__ import annotations

import ctypes
import sys
import threading
from pathlib import Path

from fs_pdf_compressor.version import WINDOWS_APP_VERSION as APP_VERSION

WINSPARKLE_VERSION = "0.9.4"
FEED_URL = "https://gitlares.github.io/fs-pdf-compressor/appcast-windows.xml"
# Public verification key shared with the existing macOS Sparkle release key.
# The corresponding private key remains in the release maintainer's Keychain.
PUBLIC_KEY = "vpBiAIADYx+8qPd1IvWCIqzok3ne9PmB2WAaZgsXa8M="
INSTALL_REGISTRY_KEY = r"Software\gitlares\FS PDF Compressor"


def is_installed_application() -> bool:
    """Do not install an EXE update over a portable ZIP or source checkout."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, INSTALL_REGISTRY_KEY) as key:
            directory, _ = winreg.QueryValueEx(key, "InstallDir")
        return Path(directory).resolve() == Path(sys.executable).resolve().parent
    except (OSError, TypeError, ValueError):
        return False


class WindowsUpdater:
    """Keep callback lifetimes and atomically reserve an idle app for install."""

    def __init__(self, shutdown_requested, library=None):
        self._lock = threading.Lock()
        self._busy = True
        self._installing = False
        self._initialized = False
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        self._dll = library if library is not None else ctypes.CDLL(str(root / "WinSparkle.dll"))
        can_shutdown_type = ctypes.CFUNCTYPE(ctypes.c_int)
        shutdown_type = ctypes.CFUNCTYPE(None)
        self._can_shutdown_callback = can_shutdown_type(self._reserve_install)
        self._shutdown_callback = shutdown_type(shutdown_requested)
        self._error_callback = shutdown_type(self._installation_failed)
        signatures = {
            "set_app_details": ([ctypes.c_wchar_p] * 3, None),
            "set_appcast_url": ([ctypes.c_char_p], None),
            "set_eddsa_public_key": ([ctypes.c_char_p], ctypes.c_int),
            "set_lang": ([ctypes.c_char_p], None),
            "set_update_check_interval": ([ctypes.c_int], None),
            "set_can_shutdown_callback": ([can_shutdown_type], None),
            "set_shutdown_request_callback": ([shutdown_type], None),
            "set_error_callback": ([shutdown_type], None),
            "init": ([], None),
            "cleanup": ([], None),
            "check_update_with_ui": ([], None),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self._dll, "win_sparkle_" + name)
            function.argtypes, function.restype = args, result
        self._dll.win_sparkle_set_app_details("gitlares", "FS PDF Compressor", APP_VERSION)
        self._dll.win_sparkle_set_appcast_url(FEED_URL.encode("ascii"))
        if self._dll.win_sparkle_set_eddsa_public_key(PUBLIC_KEY.encode("ascii")) != 1:
            raise RuntimeError("WinSparkle rejected the update verification key")
        self._dll.win_sparkle_set_lang(b"en")
        self._dll.win_sparkle_set_update_check_interval(86400)
        self._dll.win_sparkle_set_can_shutdown_callback(self._can_shutdown_callback)
        self._dll.win_sparkle_set_shutdown_request_callback(self._shutdown_callback)
        self._dll.win_sparkle_set_error_callback(self._error_callback)

    def start(self):
        if not self._initialized:
            # WinSparkle asks on first launch whether to check automatically;
            # subsequent launches preserve that user's registry preference.
            self._dll.win_sparkle_init()
            self._initialized = True

    def begin_work(self) -> bool:
        with self._lock:
            if self._installing:
                return False
            self._busy = True
            return True

    def set_busy(self, busy: bool):
        with self._lock:
            self._busy = busy

    def _reserve_install(self) -> int:
        with self._lock:
            if self._busy or self._installing:
                return 0
            self._installing = True
            return 1

    def check(self):
        self._dll.win_sparkle_check_update_with_ui()

    def _installation_failed(self):
        with self._lock:
            self._installing = False
            self._busy = True

    def cleanup(self):
        if self._initialized:
            self._dll.win_sparkle_cleanup()
            self._initialized = False
