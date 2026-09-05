#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

"""Windows entry point for the native-looking shared Qt desktop interface."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtNetwork, QtWidgets

from linux_app import APP_NAME, APP_VERSION, PDFCompressorWindow


_INSTANCE_SERVER_NAME = "gitlares.fs-pdf-compressor.windows.instance"


def _app_icon_path() -> Path:
    """Return the icon from a PyInstaller bundle or a source checkout."""
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    bundled = bundle_root / "PDFCompresor.png"
    if bundled.is_file():
        return bundled
    return bundle_root / "assets" / "PDFCompresor.png"


class WindowsPDFCompressorWindow(PDFCompressorWindow):
    """Windows-specific lifecycle behavior for the shared Qt interface."""

    def __init__(self):
        settings = QtCore.QSettings("gitlares", APP_NAME)
        # The desktop drop target is part of the Windows experience from its
        # first launch, while preserving a choice a user has already made.
        if not settings.contains("dropZoneEnabled"):
            settings.setValue("dropZoneEnabled", True)
        super().__init__()
        self.setWindowIcon(QtGui.QIcon(str(_app_icon_path())))
        self._external_paths: list[str] = []
        self._external_paths_timer = QtCore.QTimer(self)
        self._external_paths_timer.setSingleShot(True)
        self._external_paths_timer.timeout.connect(self._start_external_paths)

    def queue_external_paths(self, paths: list[str]) -> None:
        """Combine Explorer launches into one drop-zone compression batch."""
        for path in paths:
            if path not in self._external_paths:
                self._external_paths.append(path)
        self.show_main_window()
        self._external_paths_timer.start(250)

    def _start_external_paths(self) -> None:
        if self.processing:
            self._external_paths_timer.start(250)
            return
        paths, self._external_paths = self._external_paths, []
        if paths:
            self.start_drop_zone_paths(paths)

class WindowsInstanceServer:
    """Bring the existing window forward when a shortcut is launched again."""

    def __init__(self, window: WindowsPDFCompressorWindow):
        self._window = window
        self._server = QtNetwork.QLocalServer(window)
        if not self._server.listen(_INSTANCE_SERVER_NAME):
            raise RuntimeError("Could not reserve the Windows application instance")
        self._server.newConnection.connect(self._show_existing_window)

    @staticmethod
    def notify_existing_instance(paths: list[str]) -> bool:
        client = QtNetwork.QLocalSocket()
        client.connectToServer(_INSTANCE_SERVER_NAME, QtCore.QIODevice.WriteOnly)
        if not client.waitForConnected(400):
            return False
        client.write(json.dumps(paths).encode("utf-8"))
        client.waitForBytesWritten(400)
        client.disconnectFromServer()
        return True

    def _show_existing_window(self):
        while self._server.hasPendingConnections():
            client = self._server.nextPendingConnection()
            client.waitForReadyRead(200)
            try:
                paths = json.loads(bytes(client.readAll()).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                paths = []
            client.disconnectFromServer()
            client.deleteLater()
            if isinstance(paths, list) and all(isinstance(path, str) for path in paths):
                self._window.queue_external_paths(paths)
            else:
                self._window.show_main_window()


def main() -> int:
    application = QtWidgets.QApplication(sys.argv)
    application.setApplicationName(APP_NAME)
    application.setApplicationVersion(APP_VERSION)
    application.setQuitOnLastWindowClosed(False)

    paths = [argument for argument in sys.argv[1:] if not argument.startswith("-")]
    if WindowsInstanceServer.notify_existing_instance(paths):
        return 0

    # A stale server name can remain after a forced shutdown.  It is safe to
    # remove only after proving that no active instance accepted a connection.
    QtNetwork.QLocalServer.removeServer(_INSTANCE_SERVER_NAME)
    window = WindowsPDFCompressorWindow()
    application.instance_server = WindowsInstanceServer(window)
    window.show()

    if paths:
        QtCore.QTimer.singleShot(0, lambda: window.queue_external_paths(paths))
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
