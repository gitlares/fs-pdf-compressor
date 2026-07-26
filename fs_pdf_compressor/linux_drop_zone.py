# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

"""Qt Drop Zone used by the Linux edition."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets


PANEL_WIDTH = 96
PANEL_HEIGHT = 96


class DropZoneWindow(QtWidgets.QWidget):
    """A passive drop target that stays with the Linux desktop."""

    paths_dropped = QtCore.Signal(list)
    open_requested = QtCore.Signal()

    def __init__(self):
        flags = (
            QtCore.Qt.Tool
            | QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnBottomHint
        )
        super().__init__(None, flags)
        self.setObjectName("dropZone")
        self.setFixedSize(PANEL_WIDTH, PANEL_HEIGHT)
        self.setAcceptDrops(True)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.setAccessibleName("Drop Zone for PDF compression")
        self._drag_active = False
        self._mode = "idle"
        self._progress = 0.0
        self._result_text = ""
        self._drag_offset = None
        self._hole_pixmap = QtGui.QPixmap(str(self._hole_asset_path()))
        self._settings = QtCore.QSettings("gitlares", "FS PDF Compressor")
        self._reset_timer = QtCore.QTimer(self)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.timeout.connect(self.set_idle)

    @staticmethod
    def _hole_asset_path():
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        bundled = bundle_root / "desktop-drop-hole.png"
        if bundled.is_file():
            return bundled
        return bundle_root / "assets" / "desktop-drop-hole.png"

    def show_panel(self):
        saved_position = self._settings.value("dropZonePosition")
        if isinstance(saved_position, QtCore.QPoint):
            self.move(saved_position)
        elif not self.isVisible():
            screen = QtGui.QGuiApplication.primaryScreen()
            if screen is not None:
                available = screen.availableGeometry()
                self.move(
                    available.right() - self.width() - 28,
                    available.bottom() - self.height() - 28,
                )
        self.show()

    def hideEvent(self, event):
        self._settings.setValue("dropZonePosition", self.pos())
        super().hideEvent(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        center = QtCore.QPointF(self.width() / 2, self.height() / 2)
        outer = QtCore.QRectF(center.x() - 38, center.y() - 38, 76, 76)
        inner = outer.adjusted(8, 8, -8, -8)

        if not self._hole_pixmap.isNull():
            painter.drawPixmap(outer.toRect(), self._hole_pixmap)
        else:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(0, 0, 0))
            painter.drawEllipse(outer)

        if self._drag_active:
            painter.setPen(QtGui.QPen(QtGui.QColor("#0a84ff"), 2))
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(outer)

        if self._mode == "processing":
            self._draw_progress(painter, inner)
        elif self._mode == "result":
            self._draw_result(painter, inner)
        elif self._drag_active:
            self._draw_pdf_mark(painter, outer)

    def _draw_pdf_mark(self, painter, outer):
        font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
        font.setPointSizeF(9)
        font.setWeight(QtGui.QFont.DemiBold)
        font.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, 1.1)
        painter.setFont(font)
        painter.setPen(QtGui.QColor("#0a84ff"))
        painter.drawText(outer, QtCore.Qt.AlignCenter, "PDF")

    def _draw_progress(self, painter, inner):
        ring = inner.adjusted(13, 13, -13, -13)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 45), 4))
        painter.drawEllipse(ring)
        painter.setPen(
            QtGui.QPen(
                QtGui.QColor("#0a84ff"), 4, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap
            )
        )
        painter.drawArc(
            ring,
            90 * 16,
            -round(360 * 16 * min(1.0, self._progress)),
        )

    def _draw_result(self, painter, inner):
        font = painter.font()
        font.setPointSizeF(11)
        font.setWeight(QtGui.QFont.DemiBold)
        painter.setFont(font)
        painter.setPen(QtGui.QColor(255, 255, 255, 220))
        painter.drawText(inner, QtCore.Qt.AlignCenter, self._result_text)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            self._drag_active = True
            self.update()
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._drag_active = False
        self.update()

    def dropEvent(self, event):
        self._drag_active = False
        paths = [
            url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()
        ]
        if paths:
            self.paths_dropped.emit(paths)
            event.acceptProposedAction()
        self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.open_requested.emit()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & QtCore.Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        self._settings.setValue("dropZonePosition", self.pos())

    def set_processing(self):
        self._mode = "processing"
        self._progress = 0.03
        self.update()

    def set_progress(self, completed, total):
        self._mode = "processing"
        self._progress = completed / total if total else 0.0
        self.update()

    def set_result(self, text):
        self._mode = "result"
        self._result_text = text
        self.update()
        self._reset_timer.start(2400)

    def set_idle(self):
        self._mode = "idle"
        self._progress = 0.0
        self._result_text = ""
        self.update()
