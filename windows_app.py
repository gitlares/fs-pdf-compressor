#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

"""Windows entry point for the native-looking shared Qt desktop interface."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtNetwork, QtWidgets

from linux_app import APP_NAME, PDFCompressorWindow
from fs_pdf_compressor.version import WINDOWS_APP_VERSION as APP_VERSION
from fs_pdf_compressor.windows_update import WindowsUpdater, is_installed_application


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

    update_shutdown_requested = QtCore.Signal()

    def __init__(self):
        self._windows_updater = None
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
        self.update_shutdown_requested.connect(self._quit_for_update, QtCore.Qt.QueuedConnection)
        self._updater_idle_timer = QtCore.QTimer(self)
        self._updater_idle_timer.setInterval(200)
        self._updater_idle_timer.timeout.connect(self._refresh_updater_busy)

    def initialize_updater(self):
        if self._windows_updater is not None or not is_installed_application():
            return
        try:
            updater = WindowsUpdater(self.update_shutdown_requested.emit)
            self._windows_updater = updater
            self._refresh_updater_busy()
            updater.start()
        except (OSError, AttributeError, RuntimeError):
            self._windows_updater = None
            return
        self._updater_idle_timer.start()
        QtWidgets.QApplication.instance().aboutToQuit.connect(updater.cleanup)

    def _refresh_updater_busy(self):
        if self._windows_updater is not None:
            self._windows_updater.set_busy(bool(
                self.processing or self.thread is not None
                or self.discovery_thread is not None or self.update_thread is not None
                or self._external_paths or self._external_paths_timer.isActive()
            ))

    def _quit_for_update(self):
        # The native callback reserved the idle app before launching Inno Setup.
        # This slot runs on the Qt main thread, never on WinSparkle's worker.
        self.request_quit()

    def start_paths(self, paths, from_drop_zone=False):
        if self._windows_updater is not None and not self._windows_updater.begin_work():
            self.status_label.setText("An update is being installed")
            return False
        return super().start_paths(paths, from_drop_zone)

    def start_compression(self):
        if self._windows_updater is not None and not self._windows_updater.begin_work():
            self.status_label.setText("An update is being installed")
            return
        return super().start_compression()

    def check_for_updates(self):
        if self._windows_updater is not None:
            self._windows_updater.check()
        else:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl("https://github.com/gitlares/fs-pdf-compressor/releases"))

    def show_about(self):
        QtWidgets.QMessageBox.about(
            self, f"About {APP_NAME}",
            f"{APP_NAME} {APP_VERSION}\nFast and Simple PDF compression, entirely local.",
        )

    def queue_external_paths(self, paths: list[str]) -> None:
        """Combine Explorer launches into one drop-zone compression batch."""
        if self._windows_updater is not None and not self._windows_updater.begin_work():
            return
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
    QtCore.QTimer.singleShot(0, window.initialize_updater)
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
