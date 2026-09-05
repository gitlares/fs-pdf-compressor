#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

"""Windows entry point for the native-looking shared Qt desktop interface."""

from __future__ import annotations

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

    def closeEvent(self, event):
        """Exit cleanly instead of leaving an orphaned desktop drop target."""
        self.drop_zone.hide()
        event.accept()
        QtWidgets.QApplication.quit()


class WindowsInstanceServer:
    """Bring the existing window forward when a shortcut is launched again."""

    def __init__(self, window: WindowsPDFCompressorWindow):
        self._window = window
        self._server = QtNetwork.QLocalServer(window)
        if not self._server.listen(_INSTANCE_SERVER_NAME):
            raise RuntimeError("Could not reserve the Windows application instance")
        self._server.newConnection.connect(self._show_existing_window)

    @staticmethod
    def notify_existing_instance() -> bool:
        client = QtNetwork.QLocalSocket()
        client.connectToServer(_INSTANCE_SERVER_NAME, QtCore.QIODevice.WriteOnly)
        if not client.waitForConnected(400):
            return False
        client.write(b"show")
        client.waitForBytesWritten(400)
        client.disconnectFromServer()
        return True

    def _show_existing_window(self):
        while self._server.hasPendingConnections():
            client = self._server.nextPendingConnection()
            client.readAll()
            client.disconnectFromServer()
            client.deleteLater()
        self._window.show_main_window()


def main() -> int:
    application = QtWidgets.QApplication(sys.argv)
    application.setApplicationName(APP_NAME)
    application.setApplicationVersion(APP_VERSION)
    application.setQuitOnLastWindowClosed(True)

    if WindowsInstanceServer.notify_existing_instance():
        return 0

    # A stale server name can remain after a forced shutdown.  It is safe to
    # remove only after proving that no active instance accepted a connection.
    QtNetwork.QLocalServer.removeServer(_INSTANCE_SERVER_NAME)
    window = WindowsPDFCompressorWindow()
    application.instance_server = WindowsInstanceServer(window)
    window.show()

    paths = [argument for argument in sys.argv[1:] if not argument.startswith("-")]
    if paths:
        QtCore.QTimer.singleShot(0, lambda: window.start_paths(paths))
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
