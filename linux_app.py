#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

"""Linux desktop interface for FS PDF Compressor.

The layout intentionally mirrors the macOS app: an uncluttered drop surface,
compact results table, and a fixed footer. Qt supplies the platform window
integration while the visual system remains owned by FS PDF Compressor.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from fs_pdf_compressor.core import (
    APP_NAME,
    QUALITY_CONTROL_LABELS,
    QUALITY_PROFILES,
    compress_pdf,
    compression_logger,
    expand_pdf_paths,
    format_file_size,
)
from fs_pdf_compressor.linux_update import (
    available_release,
    download_verified_appimage,
    replace_after_exit,
)


APP_VERSION = os.environ.get("APP_VERSION", "1.0.6")
FOOTER_HEIGHT = 52


class DropSurface(QtWidgets.QWidget):
    paths_dropped = QtCore.Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._drag_active = False

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            self._drag_active = True
            self.update()
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._drag_active = False
        self.update()
        event.accept()

    def dropEvent(self, event):
        self._drag_active = False
        self.update()
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.paths_dropped.emit(paths)
        event.acceptProposedAction()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor("#fbfbfc"))
        side = min(188, int(self.width() * 0.34), int(self.height() * 0.56))
        target = QtCore.QRect((self.width() - side) // 2, (self.height() - side) // 2, side, side)
        border = QtGui.QColor("#7aa7e8") if self._drag_active else QtGui.QColor("#d6d7dc")
        pen = QtGui.QPen(border, 2)
        pen.setDashPattern([7, 6])
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRoundedRect(target, 19, 19)

        arrow = QtGui.QColor("#4b8ff7") if self._drag_active else QtGui.QColor("#b7bac2")
        painter.setPen(QtGui.QPen(arrow, 3, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        center = target.center()
        painter.drawLine(center.x(), center.y() - 30, center.x(), center.y() + 26)
        painter.drawLine(center.x() - 21, center.y() + 4, center.x(), center.y() + 26)
        painter.drawLine(center.x(), center.y() + 26, center.x() + 21, center.y() + 4)


class ResultsTable(QtWidgets.QTableWidget):
    """Keep accepting PDF drops after the first batch replaces the drop surface."""

    paths_dropped = QtCore.Signal(list)

    def __init__(self, parent=None):
        super().__init__(0, 2, parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.paths_dropped.emit(paths)
        event.acceptProposedAction()


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

    @QtCore.Slot()
    def check(self):
        try:
            self.checked.emit(available_release(APP_VERSION))
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()

    @QtCore.Slot(object, object)
    def download(self, release, destination):
        try:
            self.downloaded.emit(download_verified_appimage(release, Path(destination), self.progress.emit))
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()


class PDFCompressorWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.pdf_files = []
        self.statuses = []
        self.metrics = []
        self.quality_index = 1
        self.processing = False
        self.thread = None
        self.update_thread = None
        self.pending_update = None
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(620, 380)
        self.resize(680, 430)
        self._build_ui()

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
        update_action = application_menu.addAction("Check for Updates…")
        update_action.triggered.connect(self.check_for_updates)
        application_menu.addSeparator()
        about_action = application_menu.addAction(f"About {APP_NAME}")
        about_action.triggered.connect(self.show_about)

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

    def start_paths(self, paths):
        if self.processing:
            self.status_label.setText("Wait for the current batch to finish")
            return
        pdfs = expand_pdf_paths(paths)
        if not pdfs:
            self.status_label.setText("Choose PDF files")
            return
        self.pdf_files = pdfs
        self.statuses = [Path(path).name for path in pdfs]
        self.metrics = [None] * len(pdfs)
        self.show_results()
        self.start_compression()

    def show_results(self):
        self.stack.setCurrentWidget(self.results)
        self.results.setRowCount(len(self.statuses))
        for row, filename in enumerate(self.statuses):
            self.results.setRowHeight(row, 40)
            self.results.setItem(row, 0, QtWidgets.QTableWidgetItem(filename))
            self.results.setItem(row, 1, QtWidgets.QTableWidgetItem("Waiting"))
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
        self.thread.start()

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

    def finish_compression(self):
        self.processing = False
        completed = [metric for metric in self.metrics if metric]
        if completed:
            average = sum(metric["saved_size"] / metric["original_size"] * 100 for metric in completed) / len(completed)
            saved = sum(metric["saved_size"] for metric in completed)
            self.status_label.setText(f"Done — {average:.1f}% average · {format_file_size(saved)} saved")
        else:
            self.status_label.setText("Done — no files were reduced")
        self.add_button.setEnabled(True)
        self.keep_original.setEnabled(True)
        self.keep_original.show()
        self.progress.hide()
        self.again_button.setEnabled(bool(self.pdf_files))
        self.quality_menu_button.setEnabled(True)

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
        self.update_worker = UpdateWorker()
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


def main():
    application = QtWidgets.QApplication(sys.argv)
    application.setApplicationName(APP_NAME)
    application.setApplicationVersion(APP_VERSION)
    window = PDFCompressorWindow()
    window.show()
    paths = [argument for argument in sys.argv[1:] if not argument.startswith("-")]
    if paths:
        QtCore.QTimer.singleShot(0, lambda: window.start_paths(paths))
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
