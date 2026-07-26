# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

"""Background workers used by the Linux Qt interface."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore

from fs_pdf_compressor.core import compress_pdf, compression_logger
from fs_pdf_compressor.linux_update import (
    available_release,
    download_verified_appimage,
)


class CompressionWorker(QtCore.QObject):
    result = QtCore.Signal(int, str, object)
    finished = QtCore.Signal()

    def __init__(self, paths, setting, keep_original):
        super().__init__()
        self.paths = paths
        self.setting = setting
        self.keep_original = keep_original

    @QtCore.Slot()
    def run(self):
        try:
            for index, path in enumerate(self.paths):
                status, metric = compress_pdf(path, self.setting, self.keep_original)
                self.result.emit(index, status, metric)
        except Exception:
            compression_logger().exception("Unexpected Linux batch worker failure")
        finally:
            self.finished.emit()


class UpdateWorker(QtCore.QObject):
    checked = QtCore.Signal(object)
    progress = QtCore.Signal(int, int)
    failed = QtCore.Signal(str)
    downloaded = QtCore.Signal(object)
    finished = QtCore.Signal()

    def __init__(self, app_version):
        super().__init__()
        self.app_version = app_version

    @QtCore.Slot()
    def check(self):
        try:
            self.checked.emit(available_release(self.app_version))
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()

    @QtCore.Slot(object, object)
    def download(self, release, destination):
        try:
            self.downloaded.emit(
                download_verified_appimage(
                    release, Path(destination), self.progress.emit
                )
            )
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()
