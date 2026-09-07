# SPDX-License-Identifier: AGPL-3.0-or-later
"""Critical Windows Shell policy tests, independent of COM availability."""

import importlib
from pathlib import Path
import sys
import types
import unittest
from unittest import mock


class WindowsRecyclingTests(unittest.TestCase):
    def setUp(self):
        class Policy:
            def _wrap_(self, target):
                pass
        class COMError(Exception):
            def __init__(self, **kwargs):
                super().__init__(kwargs)
        self.shell = mock.Mock()
        self.constants = types.SimpleNamespace(TSF_DELETE_RECYCLE_IF_POSSIBLE=0x80, SIGDN_FILESYSPATH=1, FOF_SILENT=4, FOF_NOCONFIRMATION=16, FOF_NOERRORUI=1024)
        self.pythoncom = mock.Mock()
        modules = {
            "pythoncom": self.pythoncom,
            "win32com": types.ModuleType("win32com"),
            "win32com.shell": types.SimpleNamespace(shell=self.shell, shellcon=self.constants),
            "win32com.server": types.ModuleType("win32com.server"),
            "win32com.server.exception": types.SimpleNamespace(COMException=COMError),
            "win32com.server.policy": types.SimpleNamespace(DesignatedWrapPolicy=Policy),
        }
        self.patches = mock.patch.dict(sys.modules, modules)
        self.patches.start()
        self.addCleanup(self.patches.stop)
        module_name = "fs_pdf_compressor.windows_trash"
        sys.modules.pop(module_name, None)
        self.module = importlib.import_module(module_name)
        self.addCleanup(lambda: sys.modules.pop(module_name, None))

    def test_permanent_delete_is_rejected_before_shell_operation(self):
        progress = self.module.RecycleProgress()
        with self.assertRaises(Exception):
            progress.PreDeleteItem(0, mock.Mock())
        progress.PreDeleteItem(0x80, mock.Mock())

    def test_success_requires_recycle_destination(self):
        progress = self.module.RecycleProgress()
        progress.PostDeleteItem(0, None, 0, None)
        self.assertFalse(progress.recycled)
        destination = mock.Mock()
        destination.GetDisplayName.return_value = "recycled.pdf"
        progress.PostDeleteItem(0x80, None, 0x270004, destination)
        self.assertTrue(progress.recycled)
        self.assertEqual(progress.destination, "recycled.pdf")

    def test_successful_shell_call_without_confirmation_is_rejected(self):
        operation = self.pythoncom.CoCreateInstance.return_value
        operation.PerformOperations.return_value = 0
        operation.GetAnyOperationsAborted.return_value = False
        with self.assertRaises(OSError):
            self.module.recycle(Path("test.pdf"))
        self.pythoncom.CoUninitialize.assert_called_once()
        flags = operation.SetOperationFlags.call_args.args[0]
        self.assertTrue(flags & 0x00080000)
        self.assertTrue(flags & 0x00100000)


if __name__ == "__main__":
    unittest.main()
