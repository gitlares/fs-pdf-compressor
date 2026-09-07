# SPDX-License-Identifier: AGPL-3.0-or-later
"""Recycle through the modern Shell API, rejecting permanent deletion."""

import pythoncom
from win32com.shell import shell, shellcon
from win32com.server.exception import COMException
from win32com.server.policy import DesignatedWrapPolicy


class RecycleProgress(DesignatedWrapPolicy):
    _com_interfaces_ = [shell.IID_IFileOperationProgressSink]
    _public_methods_ = [
        "StartOperations", "FinishOperations", "PreRenameItem", "PostRenameItem",
        "PreMoveItem", "PostMoveItem", "PreCopyItem", "PostCopyItem",
        "PreDeleteItem", "PostDeleteItem", "PreNewItem", "PostNewItem",
        "UpdateProgress", "ResetTimer", "PauseTimer", "ResumeTimer",
    ]

    def __init__(self):
        self._wrap_(self)
        self.recycled = False
        self.destination = None

    def __getattr__(self, name):
        if name in self._public_methods_:
            return lambda *args: None
        raise AttributeError(name)

    def PreDeleteItem(self, flags, item):
        if not flags & shellcon.TSF_DELETE_RECYCLE_IF_POSSIBLE:
            raise COMException(desc="Permanent deletion is not allowed", scode=-2147467260)

    def PostDeleteItem(self, flags, item, result, destination):
        self.recycled = 0 <= result < 0x80000000 and destination is not None
        if self.recycled:
            self.destination = destination.GetDisplayName(shellcon.SIGDN_FILESYSPATH)


def recycle(path):
    pythoncom.CoInitialize()
    operation = sink = item = None
    try:
        operation = pythoncom.CoCreateInstance(shell.CLSID_FileOperation, None, pythoncom.CLSCTX_ALL, shell.IID_IFileOperation)
        # Windows 8+: recycle explicitly, record Undo, stop on any failure.
        operation.SetOperationFlags(shellcon.FOF_SILENT | shellcon.FOF_NOCONFIRMATION | shellcon.FOF_NOERRORUI | 0x00080000 | 0x20000000 | 0x00100000)
        progress = RecycleProgress()
        sink = pythoncom.WrapObject(progress, shell.IID_IFileOperationProgressSink)
        item = shell.SHCreateItemFromParsingName(str(path.resolve()), None, shell.IID_IShellItem)
        operation.DeleteItem(item, sink)
        result = operation.PerformOperations()
        if result or operation.GetAnyOperationsAborted() or not progress.recycled:
            raise OSError("Windows did not confirm moving the PDF to the Recycle Bin")
        return progress.destination
    finally:
        operation = sink = item = None
        pythoncom.CoUninitialize()
