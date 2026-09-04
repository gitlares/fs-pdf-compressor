#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

"""Linux desktop interface for FS PDF Compressor."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from fs_pdf_compressor.batch import BatchSummary, completion_text
from fs_pdf_compressor.core import (
    APP_NAME,
    QUALITY_CONTROL_LABELS,
    QUALITY_PROFILES,
    expand_pdf_paths,
)
from fs_pdf_compressor.linux_drop_zone import DropZoneWindow
from fs_pdf_compressor.linux_update import replace_after_exit
from fs_pdf_compressor.linux_views import DropSurface, ResultsTable
from fs_pdf_compressor.linux_workers import CompressionWorker, UpdateWorker


APP_VERSION = os.environ.get("APP_VERSION", "1.0.12")
FOOTER_HEIGHT = 52


def supports_self_updates(environment=None):
    """Return whether the AppImage replacement updater can be offered.

    Flatpak and Snap are updated by their respective stores.  Their installed
    application files are not writable by the app, so offering the AppImage
    updater there would be misleading.
    """
    environment = os.environ if environment is None else environment
    return not (environment.get("FLATPAK_ID") or environment.get("SNAP"))


class PDFCompressorWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.pdf_files = []
        self.statuses = []
        self.metrics = []
        self.quality_index = 1
        self.processing = False
        self.thread = None
        self.worker = None
        self.update_thread = None
        self.pending_update = None
        self._batch_from_drop_zone = False
        self.settings = QtCore.QSettings("gitlares", APP_NAME)
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(620, 380)
        self.resize(680, 430)
        self._build_ui()
        self._build_drop_zone()

    def _build_ui(self):
        root = QtWidgets.QWidget()
        root_layout = QtWidgets.QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.stack = QtWidgets.QStackedWidget()
        self.drop_surface = DropSurface()
        self.drop_surface.paths_dropped.connect(self.start_paths)
        self.stack.addWidget(self.drop_surface)

        self.results = ResultsTable()
        self.results.paths_dropped.connect(self.start_paths)
        self.results.setHorizontalHeaderLabels(["FILE", "REDUCTION"])
        self.results.verticalHeader().hide()
        self.results.setShowGrid(False)
        self.results.setFocusPolicy(QtCore.Qt.NoFocus)
        self.results.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.results.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.results.horizontalHeader().setStretchLastSection(False)
        self.results.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.results.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        self.results.setColumnWidth(1, 120)
        self.stack.addWidget(self.results)
        root_layout.addWidget(self.stack, 1)

        footer = QtWidgets.QFrame()
        footer.setObjectName("footer")
        footer.setFixedHeight(FOOTER_HEIGHT)
        footer_layout = QtWidgets.QHBoxLayout(footer)
        footer_layout.setContentsMargins(14, 10, 14, 10)
        footer_layout.setSpacing(10)

        self.add_button = QtWidgets.QPushButton("+")
        self.add_button.setObjectName("addButton")
        self.add_button.setFixedSize(34, 28)
        self.add_button.setToolTip("Choose PDF files")
        self.add_button.clicked.connect(self.choose_files)
        footer_layout.addWidget(self.add_button)

        self.status_label = QtWidgets.QLabel("Drag PDFs to the area above")
        self.status_label.setObjectName("status")
        self.status_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        footer_layout.addWidget(self.status_label, 1)

        self.keep_original = QtWidgets.QCheckBox("Keep original")
        self.keep_original.setToolTip("Saves “name compressed.pdf” without modifying the original PDF.")
        footer_layout.addWidget(self.keep_original)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setObjectName("progress")
        self.progress.setFixedWidth(132)
        self.progress.setTextVisible(False)
        self.progress.hide()
        footer_layout.addWidget(self.progress)

        self.again_button = QtWidgets.QPushButton("↻  Again")
        self.again_button.setEnabled(False)
        self.again_button.clicked.connect(self.repeat_last_batch)
        footer_layout.addWidget(self.again_button)

        self.quality_menu_button = QtWidgets.QToolButton()
        self.quality_menu_button.setObjectName("qualityMenu")
        self.quality_menu_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.quality_menu_button.setFixedWidth(106)
        self.quality_menu = QtWidgets.QMenu(self)
        self.quality_actions = []
        for index, label in enumerate(QUALITY_CONTROL_LABELS):
            action = self.quality_menu.addAction(label)
            action.setCheckable(True)
            action.triggered.connect(
                lambda checked=False, selected=index: self.select_quality(selected)
            )
            self.quality_actions.append(action)
        self.quality_menu_button.setMenu(self.quality_menu)
        footer_layout.addWidget(self.quality_menu_button)
        root_layout.addWidget(footer)
        self.setCentralWidget(root)
        self.update_quality_tooltip()
        self.setStyleSheet(
            """
            QMainWindow { background: #fbfbfc; }
            #footer { background: #f2f2f4; border-top: 1px solid #d7d7db; }
            QPushButton, #qualityMenu { min-height: 28px; padding: 0 10px; border: 0; border-radius: 8px; background: #e7e7eb; color: #44454a; font-size: 13px; }
            QPushButton:hover, #qualityMenu:hover { background: #ddddE3; }
            QPushButton:disabled { color: #a6a7ad; background: #eeeeF1; }
            #qualityMenu::menu-indicator { width: 12px; subcontrol-position: right center; right: 7px; }
            QMenu { background: #ffffff; border: 1px solid #d8d8dc; border-radius: 8px; padding: 5px; color: #303137; }
            QMenu::item { padding: 7px 28px 7px 10px; border-radius: 5px; }
            QMenu::item:selected { background: #e8f1ff; }
            #addButton { font-size: 21px; padding: 0; }
            #status { color: #48494e; font-size: 14px; }
            QCheckBox { color: #48494e; font-size: 13px; }
            QProgressBar { border: 0; background: #ddddE2; border-radius: 2px; max-height: 4px; }
            QProgressBar::chunk { background: #0a84ff; border-radius: 2px; }
            QTableWidget { background: #fbfbfc; border: 0; padding: 12px; color: #26272b; font-size: 14px; }
            QHeaderView::section { background: #fbfbfc; color: #85868c; border: 0; border-bottom: 1px solid #d8d8dc; padding: 9px 14px; font-size: 10px; font-weight: 600; }
            QTableWidget::item { border-bottom: 1px solid #e2e2e6; padding: 10px 14px; }
            """
        )
        application_menu = self.menuBar().addMenu("Application")
        if supports_self_updates():
            update_action = application_menu.addAction("Check for Updates…")
            update_action.triggered.connect(self.check_for_updates)
            application_menu.addSeparator()
        self.drop_zone_action = application_menu.addAction("Show Drop Zone")
        self.drop_zone_action.setCheckable(True)
        self.drop_zone_action.setChecked(
            self.settings.value("dropZoneEnabled", False, type=bool)
        )
        self.drop_zone_action.toggled.connect(self.set_drop_zone_enabled)
        application_menu.addSeparator()
        about_action = application_menu.addAction(f"About {APP_NAME}")
        about_action.triggered.connect(self.show_about)
        application_menu.addSeparator()
        quit_action = application_menu.addAction(f"Quit {APP_NAME}")
        quit_action.triggered.connect(QtWidgets.QApplication.quit)

    def _build_drop_zone(self):
        self.drop_zone = DropZoneWindow()
        self.drop_zone.paths_dropped.connect(self.start_drop_zone_paths)
        self.drop_zone.open_requested.connect(self.show_main_window)
        if self.drop_zone_action.isChecked():
            self.drop_zone.show_panel()

    def set_drop_zone_enabled(self, enabled):
        self.settings.setValue("dropZoneEnabled", enabled)
        if enabled:
            self.drop_zone.show_panel()
            return
        self.drop_zone.hide()
        if not self.isVisible():
            self.show_main_window()

    def show_main_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def update_quality_tooltip(self):
        label, _, _ = QUALITY_PROFILES[self.quality_index]
        self.quality_menu_button.setText(QUALITY_CONTROL_LABELS[self.quality_index])
        self.quality_menu_button.setToolTip(f"Quality: {label}")
        for index, action in enumerate(self.quality_actions):
            action.setChecked(index == self.quality_index)

    def select_quality(self, index):
        self.quality_index = index
        self.update_quality_tooltip()

    def choose_files(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Choose PDF files", str(Path.home()), "PDF files (*.pdf)")
        self.start_paths(paths)

    def start_paths(self, paths, from_drop_zone=False):
        if self.processing:
            self.status_label.setText("Wait for the current batch to finish")
            return False
        pdfs = expand_pdf_paths(paths)
        if not pdfs:
            self.status_label.setText("Choose PDF files")
            return False
        self._batch_from_drop_zone = from_drop_zone
        self.pdf_files = pdfs
        self.statuses = [Path(path).name for path in pdfs]
        self.metrics = [None] * len(pdfs)
        self.show_results()
        self.start_compression()
        return True

    def start_drop_zone_paths(self, paths):
        was_processing = self.processing
        if self.start_paths(paths, from_drop_zone=True):
            self.drop_zone.set_processing()
        else:
            self.drop_zone.set_result(
                "Busy" if was_processing else "PDF only"
            )

    def show_results(self):
        self.stack.setCurrentWidget(self.results)
        self.results.setUpdatesEnabled(False)
        try:
            self.results.clearContents()
            self.results.setRowCount(len(self.statuses))
            for row, filename in enumerate(self.statuses):
                self.results.setRowHeight(row, 40)
                self.results.setItem(row, 0, QtWidgets.QTableWidgetItem(filename))
                self.results.setItem(row, 1, QtWidgets.QTableWidgetItem("Waiting"))
        finally:
            self.results.setUpdatesEnabled(True)
        self.results.viewport().update()
        target_height = min(460, max(190, 52 + 34 + len(self.statuses) * 40 + 24))
        self.resize(680, target_height)

    def start_compression(self):
        self.processing = True
        self.status_label.setText("Compressing PDFs…")
        self.add_button.setEnabled(False)
        self.keep_original.setEnabled(False)
        self.keep_original.hide()
        self.again_button.setEnabled(False)
        self.quality_menu_button.setEnabled(False)
        self.progress.setValue(0)
        self.progress.show()
        _, setting, _ = QUALITY_PROFILES[self.quality_index]
        self.thread = QtCore.QThread(self)
        self.worker = CompressionWorker(list(self.pdf_files), setting, self.keep_original.isChecked())
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.result.connect(self.update_result)
        self.worker.finished.connect(self.finish_compression)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self._compression_thread_finished)
        self.thread.start()

    def _compression_thread_finished(self):
        self.worker = None
        self.thread = None

    def update_result(self, index, status, metric):
        self.statuses[index] = status
        self.metrics[index] = metric
        filename, marker, reduction = status.partition("   ↓ ")
        detail = f"↓ {reduction}" if marker else status.partition(" — ")[2] or "Waiting"
        file_item = QtWidgets.QTableWidgetItem(filename)
        detail_item = QtWidgets.QTableWidgetItem(detail)
        detail_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        if marker:
            detail_item.setForeground(QtGui.QColor("#26bf5b"))
        self.results.setItem(index, 0, file_item)
        self.results.setItem(index, 1, detail_item)
        self.progress.setValue(round((index + 1) / len(self.pdf_files) * 100))
        if self._batch_from_drop_zone:
            self.drop_zone.set_progress(index + 1, len(self.pdf_files))

    def finish_compression(self):
        self.processing = False
        summary = BatchSummary.from_metrics(self.metrics)
        self.status_label.setText(completion_text(self.metrics))
        self.add_button.setEnabled(True)
        self.keep_original.setEnabled(True)
        self.keep_original.show()
        self.progress.hide()
        self.again_button.setEnabled(bool(self.pdf_files))
        self.quality_menu_button.setEnabled(True)
        if self._batch_from_drop_zone:
            self.drop_zone.set_result(
                summary.compact_text if summary else "No change"
            )
        self._batch_from_drop_zone = False

    def repeat_last_batch(self):
        if self.processing or not self.pdf_files:
            return
        self.statuses = [Path(path).name for path in self.pdf_files]
        self.metrics = [None] * len(self.pdf_files)
        self.show_results()
        self.start_compression()

    def show_about(self):
        QtWidgets.QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"{APP_NAME} {APP_VERSION}\nFast and Simple PDF compression, entirely local.",
        )

    def check_for_updates(self):
        appimage = os.environ.get("APPIMAGE")
        if not appimage:
            QtWidgets.QMessageBox.information(
                self,
                "Check for Updates",
                "Updates are available in the released AppImage. This development build is run from source.",
            )
            return
        self.status_label.setText("Checking for updates…")
        self._run_update_task("check")

    def _run_update_task(self, task, *arguments):
        if self.update_thread is not None:
            return
        self.update_thread = QtCore.QThread(self)
        self.update_worker = UpdateWorker(APP_VERSION)
        self.update_worker.moveToThread(self.update_thread)
        if task == "check":
            self.update_thread.started.connect(self.update_worker.check)
            self.update_worker.checked.connect(self._update_check_finished)
        else:
            release, destination = arguments
            self.update_thread.started.connect(lambda: self.update_worker.download(release, destination))
            self.update_worker.progress.connect(self._update_download_progress)
            self.update_worker.downloaded.connect(self._update_download_finished)
        self.update_worker.failed.connect(self._update_failed)
        self.update_worker.finished.connect(self.update_thread.quit)
        self.update_worker.finished.connect(self.update_worker.deleteLater)
        self.update_thread.finished.connect(self._update_thread_finished)
        self.update_thread.finished.connect(self.update_thread.deleteLater)
        self.update_thread.start()

    def _update_thread_finished(self):
        self.update_thread = None
        if self.pending_update is not None:
            release = self.pending_update
            self.pending_update = None
            self._run_update_task("download", release, Path(os.environ["APPIMAGE"]))

    def _update_check_finished(self, release):
        if release is None:
            self.status_label.setText("You’re up to date")
            QtWidgets.QMessageBox.information(self, "Check for Updates", f"{APP_NAME} is up to date.")
            return
        answer = QtWidgets.QMessageBox.question(
            self,
            "Update available",
            f"Version {release.version} is available. Download and restart now?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes,
        )
        if answer == QtWidgets.QMessageBox.Yes:
            self.status_label.setText(f"Downloading {release.version}…")
            self.pending_update = release
        else:
            self.status_label.setText("Update available")

    def _update_download_progress(self, received, total):
        if total:
            self.status_label.setText(f"Downloading update… {round(received / total * 100)}%")
        else:
            self.status_label.setText("Downloading update…")

    def _update_download_finished(self, replacement):
        current = Path(os.environ["APPIMAGE"])
        replace_after_exit(current, Path(replacement))
        QtWidgets.QMessageBox.information(
            self,
            "Update ready",
            "The verified update is ready. FS PDF Compressor will restart now.",
        )
        QtWidgets.QApplication.quit()

    def _update_failed(self, detail):
        self.status_label.setText("Could not check for updates")
        QtWidgets.QMessageBox.warning(self, "Check for Updates", f"Could not complete the update.\n\n{detail}")

    def closeEvent(self, event):
        if self.drop_zone_action.isChecked():
            self.hide()
            event.ignore()
            return
        event.accept()
        QtWidgets.QApplication.quit()


def main():
    application = QtWidgets.QApplication(sys.argv)
    application.setApplicationName(APP_NAME)
    application.setApplicationVersion(APP_VERSION)
    application.setQuitOnLastWindowClosed(False)
    window = PDFCompressorWindow()
    window.show()
    paths = [argument for argument in sys.argv[1:] if not argument.startswith("-")]
    if paths:
        QtCore.QTimer.singleShot(0, lambda: window.start_paths(paths))
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
