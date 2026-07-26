# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

"""Qt views shared by the Linux main window."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets


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
        paths = [
            url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()
        ]
        if paths:
            self.paths_dropped.emit(paths)
        event.acceptProposedAction()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor("#fbfbfc"))
        side = min(188, int(self.width() * 0.34), int(self.height() * 0.56))
        target = QtCore.QRect(
            (self.width() - side) // 2,
            (self.height() - side) // 2,
            side,
            side,
        )
        border = (
            QtGui.QColor("#7aa7e8") if self._drag_active else QtGui.QColor("#d6d7dc")
        )
        pen = QtGui.QPen(border, 2)
        pen.setDashPattern([7, 6])
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRoundedRect(target, 19, 19)

        arrow = (
            QtGui.QColor("#4b8ff7") if self._drag_active else QtGui.QColor("#b7bac2")
        )
        painter.setPen(
            QtGui.QPen(
                arrow,
                3,
                QtCore.Qt.SolidLine,
                QtCore.Qt.RoundCap,
                QtCore.Qt.RoundJoin,
            )
        )
        center = target.center()
        painter.drawLine(center.x(), center.y() - 30, center.x(), center.y() + 26)
        painter.drawLine(
            center.x() - 21,
            center.y() + 4,
            center.x(),
            center.y() + 26,
        )
        painter.drawLine(
            center.x(),
            center.y() + 26,
            center.x() + 21,
            center.y() + 4,
        )


class ResultsTable(QtWidgets.QTableWidget):
    """Continue accepting PDF drops after the first batch."""

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
        paths = [
            url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()
        ]
        if paths:
            self.paths_dropped.emit(paths)
        event.acceptProposedAction()
